import os
import subprocess
import shutil

SitesAvailable = os.path.join("/etc", "nginx", "sites-available")
SitesEnabled = os.path.join("/etc", "nginx", "sites-enabled")

def create_config_file(domain, config_content, sites_available=SitesAvailable):
    config_path = os.path.join(sites_available, domain)    
    if os.geteuid() != 0:
        return {"error": "Cần chạy script với quyền root (sudo)"}, 403
    try:
        os.makedirs(sites_available, exist_ok=True)
        with open(config_path, 'w') as f:
            f.write(config_content)
        return {"message": f"Đã tạo file cấu hình tại: {config_path}"}, 200
    except Exception as e:
        return {"error": f"Lỗi khi tạo file cấu hình: {e}"}, 500

def create_symlink(domain, sites_available=SitesAvailable, sites_enabled=SitesEnabled):
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
            return {"error": f"Cú pháp file cấu hình không hợp lệ: {check_result.stderr}"}, 500
    except Exception as e:
        return {"error": f"Lỗi khi reload Nginx: {e}"}, 500

def certbot_ssl(domain):
    try:
        certbot_cmd = ["certbot", "--nginx", "-d", domain, "--non-interactive", "--agree-tos", 
                      "--email", "lokid319@gmail.com"]
        result = subprocess.run(certbot_cmd, capture_output=True, text=True)                
        if result.returncode == 0:
            return {"message": f"Đã cài SSL cho {domain} thành công"}, 200
        else:
            return {"error": f"Lỗi khi cài SSL: {result.stderr}"}, 500
    except Exception as e:
        return {"error": f"Lỗi khi chạy certbot: {e}"}, 500
    
def clear_all_pycache():
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                print(f"Removing {pycache_path}")
                shutil.rmtree(pycache_path, ignore_errors=True)