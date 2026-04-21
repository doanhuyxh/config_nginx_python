from flask import Flask, request, jsonify, render_template, send_from_directory
import os
from flasgger import Flasgger
from tools.config_generator_nginx import clear_all_pycache, deploy_single_domain

app = Flask(__name__)
APP_PORT = os.getenv("PORT", "3000")
SWAGGER_HOST = os.getenv("SWAGGER_HOST")

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Nginx Config Manager API",
        "description": "API để quản lý cấu hình Nginx cho nhiều domain trên Linux",
        "version": "1.0.0"
    },
    "basePath": "/",
    "schemes": ["http", "https"]
}

# Set public host/IP for Swagger when deploying to internet.
if SWAGGER_HOST:
    swagger_template["host"] = SWAGGER_HOST if ":" in SWAGGER_HOST else f"{SWAGGER_HOST}:{APP_PORT}"

swagger = Flasgger(app, template=swagger_template)

def generate_nginx_config(domain, app_url):
    with open('templates/nginx.conf', 'r') as f:
        template = f.read()
    return template.format(domain=domain, app_url=app_url)

@app.route('/', methods=['GET'])
def index():
    return render_template('swagger.html')


@app.route('/swagger.json', methods=['GET'])
def swagger_json():
    return send_from_directory('templates', 'swagger.json')

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

    result, status = deploy_single_domain(
      domain=domain,
      app_url=app_url,
      ssl_option=ssl_option,
      reload_after_setup=True
    )
    if status != 200:
      return jsonify(result), status

    return jsonify({
      "message": f"Đã triển khai Nginx cho {domain} thành công",
      "ssl_enabled": result.get("ssl_enabled", False)
    }), 200


if __name__ == '__main__':
    clear_all_pycache()
    app.run(host='0.0.0.0', port=int(APP_PORT))