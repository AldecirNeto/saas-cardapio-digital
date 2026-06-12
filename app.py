from flask import Flask, render_template
import os
from dotenv import load_dotenv

load_dotenv()

# IMPORTANDO OS NOSSOS MÓDULOS (BLUEPRINTS)
from routes.auth import auth_bp
from routes.operacao import operacao_bp
from routes.superadmin import superadmin_bp
from routes.admin import admin_bp
from routes.cliente import cliente_bp

# INICIALIZANDO O NÚCLEO DO SISTEMA
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# 3. CONFIGURAÇÕES DE UPLOAD
PASTA_UPLOADS = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = PASTA_UPLOADS
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

app.register_blueprint(auth_bp)
app.register_blueprint(operacao_bp)
app.register_blueprint(superadmin_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(cliente_bp)

# 5. RODANDO O SERVIDOR
@app.route('/')
def landing_page():
    return render_template("landing.html")

@app.route('/teste')
def teste():
    return "<h1>O Flask está vivo e respondendo!</h1>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)