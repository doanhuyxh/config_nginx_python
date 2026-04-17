import os
import subprocess
import shutil
import platform


def get_nginx_paths():
    """
    Detect Linux distribution and return appropriate Nginx paths.
    - Ubuntu/Debian: uses sites-available and sites-enabled
    - RHEL/CentOS/Fedora: uses conf.d
    """
    try:
        # Try to detect distribution
        with open('/etc/os-release', 'r') as f:
            os_info = f.read().lower()
            
        # Check for Debian/Ubuntu
        if 'debian' in os_info or 'ubuntu' in os_info:
            return {
                'config_dir': os.path.join("/etc", "nginx", "sites-available"),
                'enabled_dir': os.path.join("/etc", "nginx", "sites-enabled"),
                'type': 'debian'
            }
        # Check for RHEL/CentOS/Fedora
        elif any(x in os_info for x in ['fedora', 'centos', 'rhel', 'red hat']):
            return {
                'config_dir': os.path.join("/etc", "nginx", "conf.d"),
                'enabled_dir': None,  # No symlink needed for RHEL-based
                'type': 'rhel'
            }
    except Exception as e:
        print(f"Warning: Could not detect distribution: {e}")
    
    # Fallback: Check if sites-available exists (Debian-based)
    if os.path.exists("/etc/nginx/sites-available"):
        return {
            'config_dir': os.path.join("/etc", "nginx", "sites-available"),
            'enabled_dir': os.path.join("/etc", "nginx", "sites-enabled"),
            'type': 'debian'
        }
    
    # Fallback: Use conf.d (RHEL-based)
    return {
        'config_dir': os.path.join("/etc", "nginx", "conf.d"),
        'enabled_dir': None,
        'type': 'rhel'
    }


# Get paths based on Linux distribution
_nginx_paths = get_nginx_paths()
SitesAvailable = _nginx_paths['config_dir']
SitesEnabled = _nginx_paths['enabled_dir']
NginxPathType = _nginx_paths['type']


def create_config_file(domain, config_content, sites_available=None):
    if sites_available is None:
        sites_available = SitesAvailable
    
    # For RHEL-based systems, ensure domain has .conf extension
    if NginxPathType == 'rhel' and not domain.endswith('.conf'):
        config_filename = domain + '.conf'
    else:
        config_filename = domain
    
    config_path = os.path.join(sites_available, config_filename)
    if os.geteuid() != 0:
        return {"error": "Cần chạy script với quyền root (sudo)"}, 403
    try:
        os.makedirs(sites_available, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config_content)
        return {"message": f"Đã tạo file cấu hình tại: {config_path}"}, 200
    except Exception as e:
        return {"error": f"Lỗi khi tạo file cấu hình: {e}"}, 500


def create_symlink(domain, sites_available=None, sites_enabled=None):
    """
    Create symlink for Debian-based systems.
    For RHEL-based systems, this step is skipped (returns success).
    """
    if sites_available is None:
        sites_available = SitesAvailable
    if sites_enabled is None:
        sites_enabled = SitesEnabled
    
    # Skip symlink creation for RHEL-based systems (conf.d doesn't need symlinks)
    if NginxPathType == 'rhel' or sites_enabled is None:
        return {"message": f"Cấu hình được lưu tại: {sites_available}/{domain}"}, 200
    
    source_path = os.path.join(sites_available, domain)
    target_path = os.path.join(sites_enabled, domain)
    try:
        if os.path.exists(target_path):
            os.remove(target_path)
        os.symlink(source_path, target_path)
        return {"message": f"Đã tạo symlink: {target_path} -> {source_path}"}, 200
    except Exception as e:
        return {"error": f"Lỗi khi tạo symlink: {e}"}, 500


def reload_nginx():
    try:
        check_result = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
        if check_result.returncode == 0:
            reload_result = subprocess.run(["systemctl", "reload", "nginx"])
            if reload_result.returncode == 0:
                return {"message": "Đã reload Nginx thành công"}, 200
            else:
                return {"error": "Lỗi khi reload Nginx"}, 500
        else:
            return {
                "error": f"Cú pháp file cấu hình không hợp lệ: {check_result.stderr}"
            }, 500
    except Exception as e:
        return {"error": f"Lỗi khi reload Nginx: {e}"}, 500


def certbot_ssl(domain):
    try:
        certbot_cmd = [
            "certbot",
            "--nginx",
            "-d",
            domain,
            "--non-interactive",
            "--agree-tos",
            "--email",
            "lokid319@gmail.com",
        ]
        result = subprocess.run(certbot_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"message": f"Đã cài SSL cho {domain} thành công"}, 200
        else:
            return {"error": f"Lỗi khi cài SSL: {result.stderr}"}, 500
    except Exception as e:
        return {"error": f"Lỗi khi chạy certbot: {e}"}, 500


def deploy_multiple_domains(domains_config):
    """
    Deploy multiple domains at once.
    
    Args:
        domains_config: List of dict with keys:
            - domain: domain name
            - app_url: application URL (default: http://localhost:3000)
            - ssl: enable SSL (default: 'no')
    
    Returns:
        dict with results for each domain
    """
    if os.geteuid() != 0:
        return {"error": "Cần chạy script với quyền root (sudo)"}, 403
    
    results = {
        "successful": [],
        "failed": [],
        "summary": ""
    }
    
    for idx, domain_config in enumerate(domains_config, 1):
        domain = domain_config.get('domain')
        app_url = domain_config.get('app_url', 'http://localhost:3000')
        ssl_option = domain_config.get('ssl', 'no')
        
        try:
            # Import here to avoid circular imports
            from app import generate_nginx_config
            
            # Create config file
            config_content = generate_nginx_config(domain, app_url)
            config_result, config_status = create_config_file(domain, config_content)
            
            if config_status != 200:
                results["failed"].append({
                    "domain": domain,
                    "error": config_result.get("error")
                })
                continue
            
            # Create symlink
            symlink_result, symlink_status = create_symlink(domain)
            if symlink_status != 200:
                results["failed"].append({
                    "domain": domain,
                    "error": symlink_result.get("error")
                })
                continue
            
            # Handle SSL
            ssl_enabled = ssl_option.lower() == 'yes'
            if ssl_enabled:
                ssl_result, ssl_status = certbot_ssl(domain)
                if ssl_status != 200:
                    results["failed"].append({
                        "domain": domain,
                        "error": f"SSL error: {ssl_result.get('error')}"
                    })
                    continue
            
            results["successful"].append({
                "domain": domain,
                "ssl_enabled": ssl_enabled,
                "message": config_result.get("message")
            })
        
        except Exception as e:
            results["failed"].append({
                "domain": domain,
                "error": str(e)
            })
    
    # Reload Nginx once after all configs are created
    if results["successful"]:
        reload_result, reload_status = reload_nginx()
        if reload_status == 200:
            results["summary"] = f"Đã setup {len(results['successful'])} domain(s) thành công"
        else:
            results["summary"] = f"Setup thành công nhưng reload Nginx lỗi: {reload_result.get('error')}"
    else:
        results["summary"] = f"Setup thất bại, không có domain nào được tạo"
    
    return results, 200 if results["successful"] else 500


def clear_all_pycache():
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                pycache_path = os.path.join(root, dir_name)
                print(f"Removing {pycache_path}")
                shutil.rmtree(pycache_path, ignore_errors=True)
