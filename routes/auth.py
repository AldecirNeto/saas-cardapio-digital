from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
import sqlite3

# Criando o Blueprint de Autenticação
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        print(f"\n🕵️ 1. TENTATIVA DE LOGIN: E-mail -> {email}")

        conexao = sqlite3.connect("Autoatendimento.db")
        cursor = conexao.cursor()
        cursor.execute("SELECT id, senha, restaurante_id, tipo FROM usuarios WHERE email = ?", (email,))
        usuario = cursor.fetchone()
        conexao.close()

        if usuario:
            print(f"🕵️ 2. USUÁRIO ENCONTRADO NO BANCO! ID: {usuario[0]}")
        else:
            print("❌ 2. USUÁRIO NÃO ENCONTRADO!")

        if usuario and check_password_hash(usuario[1], senha):
            print("✅ 3. SENHA CORRETA! Fabricando crachá...")
            session['usuario_id'] = usuario[0]
            session['restaurante_id'] = usuario[2]
            session['tipo'] = usuario[3]
            print(f"🎫 4. CRACHÁ PRONTO NA SESSÃO: {dict(session)}")
            
            # MÁGICA DOS BLUEPRINTS: Apontando para as rotas dos futuros módulos
            if session['tipo'] == 'superadmin':
                return redirect(url_for('superadmin.painel_super_admin'))
            
            return redirect(url_for('admin.painel_admin'))
        else:
            print("❌ 3. SENHA INCORRETA!")
            return "❌ E-mail ou senha incorretos! Tente novamente.", 401

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    # Redireciona para a função login dentro deste próprio blueprint (auth)
    return redirect(url_for('auth.login'))