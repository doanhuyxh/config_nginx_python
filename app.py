from flask import Flask, request, jsonify, render_template
import os
from flasgger import Flasgger
from tools.config_generator_nginx import create_config_file, create_symlink, reload_nginx, certbot_ssl, clear_all_pycache, deploy_multiple_domains

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
    """Display Swagger UI Documentation"""
    return render_template('swagger.html')

@app.route('/deploy/nginx', methods=['POST'])
def deploy_nginx():
    """
    Deploy Nginx configuration for a single domain
    ---
    tags:
      - Nginx Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - domain
          properties:
            domain:
              type: string
              description: Domain name (e.g., example.com)
              example: example.com
            app_url:
              type: string
              description: Backend application URL
              default: http://localhost:3000
              example: http://localhost:3000
            ssl:
              type: string
              enum: ['yes', 'no']
              default: 'no'
              description: Enable SSL certificate with Certbot
              example: 'yes'
          example:
            domain: example.com
            app_url: http://localhost:3000
            ssl: 'yes'
    responses:
      200:
        description: Nginx configuration deployed successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: Đã triển khai Nginx cho example.com thành công
            ssl_enabled:
              type: boolean
              example: true
      400:
        description: Missing required domain parameter
        schema:
          type: object
          properties:
            error:
              type: string
              example: Vui lòng cung cấp domain
      403:
        description: Root privileges required
        schema:
          type: object
          properties:
            error:
              type: string
              example: API này cần chạy với quyền root (sudo)
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
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

@app.route('/deploy/nginx/batch', methods=['POST'])
def deploy_nginx_batch():
    """
    Deploy Nginx configuration for multiple domains at once
    ---
    tags:
      - Nginx Management
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - domains
          properties:
            domains:
              type: array
              items:
                type: object
                required:
                  - domain
                properties:
                  domain:
                    type: string
                    description: Domain name
                    example: example.com
                  app_url:
                    type: string
                    description: Backend application URL
                    default: http://localhost:3000
                    example: http://localhost:3000
                  ssl:
                    type: string
                    enum: ['yes', 'no']
                    default: 'no'
                    description: Enable SSL certificate
                    example: 'yes'
              example:
                - domain: example1.com
                  app_url: http://localhost:3000
                  ssl: 'yes'
                - domain: example2.com
                  app_url: http://localhost:3001
                  ssl: 'no'
                - domain: example3.com
                  app_url: http://localhost:3002
                  ssl: 'yes'
          example:
            domains:
              - domain: example1.com
                app_url: http://localhost:3000
                ssl: 'yes'
              - domain: example2.com
                app_url: http://localhost:3001
                ssl: 'no'
              - domain: example3.com
                app_url: http://localhost:3002
                ssl: 'yes'
    responses:
      200:
        description: Batch deployment completed with results
        schema:
          type: object
          properties:
            successful:
              type: array
              items:
                type: object
                properties:
                  domain:
                    type: string
                    example: example1.com
                  ssl_enabled:
                    type: boolean
                    example: true
                  message:
                    type: string
                    example: Đã tạo file cấu hình tại /etc/nginx/sites-available/example1.com
            failed:
              type: array
              items:
                type: object
                properties:
                  domain:
                    type: string
                    example: invalid.domain
                  error:
                    type: string
                    example: Lỗi khi tạo symlink
            summary:
              type: string
              example: Đã setup 2 domain(s) thành công
      400:
        description: Invalid input
        schema:
          type: object
          properties:
            error:
              type: string
      403:
        description: Root privileges required
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    if os.geteuid() != 0:
        return jsonify({"error": "API này cần chạy với quyền root (sudo)"}), 403
    
    data = request.get_json()
    domains = data.get('domains', [])
    
    if not domains or not isinstance(domains, list):
        return jsonify({"error": "Vui lòng cung cấp danh sách domains (mảng)"}), 400
    
    if len(domains) == 0:
        return jsonify({"error": "Danh sách domains trống"}), 400
    
    results, status = deploy_multiple_domains(domains)
    return jsonify(results), status

if __name__ == '__main__':
    clear_all_pycache()
    app.run(host='0.0.0.0', port=int(APP_PORT))