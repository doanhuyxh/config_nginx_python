from flask import Flask, request, jsonify, render_template
import os
from tools.config_generator_nginx import create_config_file, create_symlink, reload_nginx, certbot_ssl, clear_all_pycache
app = Flask(__name__)

def generate_nginx_config(domain, app_url):
    with open('templates/nginx.conf', 'r') as f:
        template = f.read()
    return template.format(domain=domain, app_url=app_url)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/deploy/nginx', methods=['POST'])
def deploy_nginx():
    if os.geteuid() != 0:
        return jsonify({"error": "API này cần chạy với quyền root (sudo)"}), 403
    
    data = request.get_json()
    domain = data.get('domain')
    app_url = data.get('app_url', "http://localhost:3000")
    ssl_option = data.get('ssl', 'no')
    if not domain:
        return jsonify({"error": "Vui lòng cung cấp domain"}), 400

    config_result, config_status = create_config_file(domain, generate_nginx_config(domain, app_url))
    if config_status != 200:
        return jsonify(config_result), config_status

    symlink_result, symlink_status = create_symlink(domain)
    if symlink_status != 200:
        return jsonify(symlink_result), symlink_status

    reload_result, reload_status = reload_nginx()
    if reload_status != 200:
        return jsonify(reload_result), reload_status

    ssl_enabled = ssl_option.lower() == 'yes'
    if ssl_enabled:
        ssl_result, ssl_status = certbot_ssl(domain)
        if ssl_status != 200:
            return jsonify(ssl_result), ssl_status

    return jsonify({
        "message": f"Đã triển khai Nginx cho {domain} thành công",
        "ssl_enabled": ssl_enabled
    }), 200

if __name__ == '__main__':
    clear_all_pycache()
    app.run(host='0.0.0.0', port=3000)