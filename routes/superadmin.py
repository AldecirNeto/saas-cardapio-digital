from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from db import get_conexao
from psycopg2.extras import RealDictCursor
import psycopg2
import re
import os

# Criando o Blueprint do Super Admin
superadmin_bp = Blueprint('superadmin', __name__)

# Decorador de segurança isolado para o Super Admin
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('tipo') != 'superadmin':
            flash("Acesso restrito ao Administrador do SaaS.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@superadmin_bp.route("/superadmin")
@superadmin_required
def painel_super_admin():
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT COUNT(*) as qtd FROM restaurantes")
    total_restaurantes = cursor.fetchone()['qtd']

    cursor.execute("SELECT COUNT(*) as qtd FROM pedidos")
    total_pedidos_plataforma = cursor.fetchone()['qtd']

    cursor.execute('''
        SELECT id, nome, slug, status, cor_tema, cor_fundo, cor_card, cor_texto, tema_kds, plano, cor_texto_botao, chave_pix, telefone_whatsapp 
        FROM restaurantes ORDER BY id DESC
    ''')
    lista_restaurantes = cursor.fetchall()
    
    conexao.close()

    return render_template("super_admin.html", 
                           total_res=total_restaurantes, 
                           total_ped=total_pedidos_plataforma, 
                           restaurantes=lista_restaurantes)

@superadmin_bp.route("/superadmin/mudar_plano/<int:id_res>", methods=["POST"])
@superadmin_required
def mudar_plano_restaurante(id_res):
    novo_plano = request.form.get("plano")
    
    conexao = get_conexao()
    cursor = conexao.cursor()
    
    cursor.execute("UPDATE restaurantes SET plano = %s WHERE id = %s", (novo_plano, id_res))
    conexao.commit()
    conexao.close()
    
    flash("Upgrade/Downgrade de plano realizado com sucesso!", "success")
    return redirect(url_for('superadmin.painel_super_admin'))

@superadmin_bp.route("/superadmin/toggle/<int:id_res>")
@superadmin_required
def toggle_restaurante(id_res):
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT status FROM restaurantes WHERE id = %s", (id_res,))
    resultado = cursor.fetchone()
    
    if resultado:
        status_atual = resultado['status']
        novo_status = 'bloqueado' if status_atual == 'ativo' else 'ativo'
        cursor.execute("UPDATE restaurantes SET status = %s WHERE id = %s", (novo_status, id_res))
        conexao.commit()
    
    conexao.close()
    return redirect(url_for('superadmin.painel_super_admin'))

@superadmin_bp.route("/superadmin/financeiro")
@superadmin_required
def painel_financeiro_saas():
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute('''
        SELECT id, nome, plano, status, valor_plano, dia_vencimento 
        FROM restaurantes 
        ORDER BY dia_vencimento ASC
    ''')
    clientes = cursor.fetchall()
    conexao.close()

    mrr_total = 0.0
    valor_inadimplente = 0.0
    qtd_ativos = 0
    qtd_bloqueados = 0

    for c in clientes:
        status = c['status']
        valor = float(c['valor_plano']) if c['valor_plano'] else 0.0
        
        if status == 'ativo':
            mrr_total += valor
            qtd_ativos += 1
        else:
            valor_inadimplente += valor
            qtd_bloqueados += 1

    return render_template("super_financeiro.html", 
                           clientes=clientes, 
                           mrr_total=mrr_total, 
                           valor_inadimplente=valor_inadimplente,
                           qtd_ativos=qtd_ativos,
                           qtd_bloqueados=qtd_bloqueados)

@superadmin_bp.route("/superadmin/editar_financeiro/<int:id_res>", methods=["POST"])
@superadmin_required
def editar_financeiro_cliente(id_res):
    novo_valor = request.form.get("valor_plano", 0.0)
    novo_vencimento = request.form.get("dia_vencimento", 5)
    
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("UPDATE restaurantes SET valor_plano = %s, dia_vencimento = %s WHERE id = %s", (novo_valor, novo_vencimento, id_res))
    conexao.commit()
    conexao.close()
    
    flash("Dados financeiros atualizados!", "success")
    return redirect(url_for('superadmin.painel_financeiro_saas'))

@superadmin_bp.route("/superadmin/cadastrar", methods=["POST"])
@superadmin_required
def cadastrar_restaurante():
    nome = request.form.get("nome_restaurante")
    email = request.form.get("email_dono")
    senha = request.form.get("senha_dono")
    cor = request.form.get("cor_tema", "#e67e22")
    plano = request.form.get("plano", "salao")
    chave_pix = request.form.get("chave_pix", "")
    telefone_whatsapp = request.form.get("telefone_whatsapp", "")

    slug = nome.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)

    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute('''
            INSERT INTO restaurantes (nome, slug, cor_tema, status, plano, chave_pix, telefone_whatsapp)
            VALUES (%s, %s, %s, 'ativo', %s, %s, %s) RETURNING id
        ''', (nome, slug, cor, plano, chave_pix, telefone_whatsapp))
        
        restaurante_id = cursor.fetchone()['id']

        cursor.execute('INSERT INTO categorias (nome, restaurante_id) VALUES (%s, %s)', ("Geral", restaurante_id))

        senha_hash = generate_password_hash(senha)
        
        cursor.execute('''
            INSERT INTO usuarios (email, senha, restaurante_id, tipo)
            VALUES (%s, %s, %s, 'restaurante')
        ''', (email, senha_hash, restaurante_id))

        conexao.commit()
        flash(f"Sucesso! {nome} agora é seu cliente.", "success")
        
    except psycopg2.IntegrityError:
        conexao.rollback()
        flash("Erro: Esse nome ou e-mail já estão em uso.", "danger")
    finally:
        conexao.close()

    return redirect(url_for('superadmin.painel_super_admin'))

@superadmin_bp.route("/superadmin/editar_estilo/<int:id_res>", methods=["POST"])
@superadmin_required
def editar_estilo_restaurante(id_res):
    nova_cor = request.form.get("cor_tema")
    nova_cor_fundo = request.form.get("cor_fundo")
    nova_cor_card = request.form.get("cor_card")
    nova_cor_texto = request.form.get("cor_texto")
    nova_cor_texto_botao = request.form.get("cor_texto_botao")
    novo_tema_kds = request.form.get("tema_kds")
    
    nova_chave_pix = request.form.get("chave_pix", "")
    novo_telefone = request.form.get("telefone_whatsapp", "")

    remover_logo = request.form.get("remover_logo")
    remover_fundo = request.form.get("remover_fundo")
    logo = request.files.get("logo")
    fundo = request.files.get("fundo")

    conexao = get_conexao()
    cursor = conexao.cursor()

    campos_sql = ["cor_tema = %s", "tema_kds = %s", "cor_fundo = %s", "cor_card = %s", "cor_texto = %s", "cor_texto_botao = %s", "chave_pix = %s", "telefone_whatsapp = %s"]
    valores_sql = [nova_cor, novo_tema_kds, nova_cor_fundo, nova_cor_card, nova_cor_texto, nova_cor_texto_botao, nova_chave_pix, novo_telefone]

    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

    try:
        if remover_logo == "1":
            campos_sql.append("logo = %s")
            valores_sql.append(None)
        elif logo and logo.filename != "":
            nome_seguro = secure_filename(logo.filename)
            nome_arquivo = f"logo_{id_res}_{nome_seguro}"
            caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo)
            logo.save(caminho)
            campos_sql.append("logo = %s")
            valores_sql.append(f"uploads/{nome_arquivo}")

        if remover_fundo == "1":
            campos_sql.append("fundo_imagem = %s")
            valores_sql.append(None)
        elif fundo and fundo.filename != "":
            nome_seguro = secure_filename(fundo.filename)
            nome_arquivo = f"fundo_{id_res}_{nome_seguro}"
            caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo)
            fundo.save(caminho)
            campos_sql.append("fundo_imagem = %s")
            valores_sql.append(f"uploads/{nome_arquivo}")

        valores_sql.append(id_res)
        query = f"UPDATE restaurantes SET {', '.join(campos_sql)} WHERE id = %s"
        
        cursor.execute(query, tuple(valores_sql))
        conexao.commit()
        flash("Estilo e Contatos atualizados com sucesso!", "success")
        
    except Exception as e:
        conexao.rollback()
        flash(f"Erro ao salvar: {e}", "danger")
    finally:
        conexao.close()

    return redirect(url_for('superadmin.painel_super_admin'))