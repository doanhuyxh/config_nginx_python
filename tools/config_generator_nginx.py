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


def clear_all_pycache():
    for root, dirs, files in os.walk("."):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                pycache_path = os.path.join(root, dir_name)
                print(f"Removing {pycache_path}")
                shutil.rmtree(pycache_path, ignore_errors=True)
