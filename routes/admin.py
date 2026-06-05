from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, Response
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime
from collections import Counter
from db import get_conexao
from psycopg2.extras import RealDictCursor
import math
import os
import csv
import io

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin")
def painel_admin():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        session.clear()
        return redirect(url_for('auth.login'))
        
    restaurante_id = session['restaurante_id']
    
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM categorias WHERE restaurante_id = %s", (restaurante_id,))
    lista_categorias = [dict(c) for c in cursor.fetchall()]

    hoje = datetime.now().strftime("%Y-%m-%d")
    mes_atual = datetime.now().strftime("%Y-%m")

    # Faturamento Diário
    cursor.execute("SELECT SUM(total) as fat FROM pedidos WHERE restaurante_id = %s AND status = 'finalizado' AND data_hora::text LIKE %s", (restaurante_id, hoje + '%'))
    row = cursor.fetchone()
    faturamento_hoje = row['fat'] if row and row['fat'] is not None else 0.0 

    cursor.execute("SELECT COUNT(id) as qtd FROM pedidos WHERE restaurante_id = %s AND data_hora::text LIKE %s", (restaurante_id, hoje + '%'))
    total_pedidos_hoje = cursor.fetchone()['qtd']

    # Faturamento Mensal
    cursor.execute("SELECT SUM(total) as fat FROM pedidos WHERE restaurante_id = %s AND status = 'finalizado' AND data_hora::text LIKE %s", (restaurante_id, '%' + mes_atual + '%'))
    row = cursor.fetchone()
    faturamento_mes = row['fat'] if row and row['fat'] is not None else 0.0

    cursor.execute("SELECT COUNT(id) as qtd FROM pedidos WHERE restaurante_id = %s AND data_hora::text LIKE %s", (restaurante_id, '%' + mes_atual + '%'))
    total_pedidos_mes = cursor.fetchone()['qtd']

    # Top 5 Itens Vendidos
    cursor.execute("SELECT itens FROM pedidos WHERE restaurante_id = %s AND status = 'finalizado'", (restaurante_id,))
    todos_itens_vendidos = cursor.fetchall()
    
    lista_de_todos_os_lanches = []
    for pedido in todos_itens_vendidos:
        if pedido['itens']:
            itens_separados = pedido['itens'].split(', ')
            lista_de_todos_os_lanches.extend(itens_separados)
        
    top_5_itens = Counter(lista_de_todos_os_lanches).most_common(10)

    pagina_card = request.args.get('pagina_card', 1, type=int)
    pagina_hist = request.args.get('pagina_hist', 1, type=int)
   
    itens_por_pagina_card = 15
    itens_por_pagina_hist = 15

    # Cardápio
    offset_card = (pagina_card - 1) * itens_por_pagina_card
    cursor.execute("SELECT * FROM cardapio WHERE restaurante_id = %s LIMIT %s OFFSET %s", (restaurante_id, itens_por_pagina_card, offset_card))
    itens_cardapio = [dict(i) for i in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(id) as qtd FROM cardapio WHERE restaurante_id = %s", (restaurante_id,))
    total_itens_card = cursor.fetchone()['qtd']
    total_paginas_cardapio = math.ceil(total_itens_card / itens_por_pagina_card)

    # Histórico de Pedidos e Busca
    offset_hist = (pagina_hist - 1) * itens_por_pagina_hist
    termo_busca = request.args.get('busca', '').strip()

    if termo_busca:
        busca_like = f"%{termo_busca}%"
        if termo_busca.isdigit():
            termo_int = int(termo_busca)
            cursor.execute('''
                SELECT id, mesa, itens, total, status, data_hora, observacao, nome_cliente, telefone_cliente
                FROM pedidos 
                WHERE restaurante_id = %s AND (id = %s OR telefone_cliente LIKE %s)
                ORDER BY id DESC LIMIT %s OFFSET %s
            ''', (restaurante_id, termo_int, busca_like, itens_por_pagina_hist, offset_hist))
        else:
            cursor.execute('''
                SELECT id, mesa, itens, total, status, data_hora, observacao, nome_cliente, telefone_cliente
                FROM pedidos 
                WHERE restaurante_id = %s AND (nome_cliente ILIKE %s)
                ORDER BY id DESC LIMIT %s OFFSET %s
            ''', (restaurante_id, busca_like, itens_por_pagina_hist, offset_hist))
    else:
        cursor.execute('''
            SELECT id, mesa, itens, total, status, data_hora, observacao, nome_cliente, telefone_cliente
            FROM pedidos 
            WHERE restaurante_id = %s 
            ORDER BY id DESC LIMIT %s OFFSET %s
        ''', (restaurante_id, itens_por_pagina_hist, offset_hist))
        
    historico_pedidos = [dict(p) for p in cursor.fetchall()]

    cursor.execute("SELECT COUNT(id) as qtd FROM pedidos WHERE restaurante_id = %s", (restaurante_id,))
    total_pedidos_historico = cursor.fetchone()['qtd']
    total_paginas_hist = math.ceil(total_pedidos_historico / itens_por_pagina_hist)

    conexao.close()

    return render_template("admin.html",
                           faturamento=faturamento_hoje,
                           qtd_pedidos=total_pedidos_hoje,
                           faturamento_mes=faturamento_mes,
                           qtd_pedidos_mes=total_pedidos_mes,
                           top_itens=top_5_itens,
                           categorias_atuais=lista_categorias,
                           cardapio=itens_cardapio,
                           pagina_atual_cardapio=pagina_card,
                           total_paginas_cardapio=total_paginas_cardapio,
                           historico=historico_pedidos, 
                           pagina_atual_hist=pagina_hist,
                           total_paginas_hist=total_paginas_hist, 
                           termo_busca=termo_busca)


@admin_bp.route("/admin/categorias", methods=["POST"])
def adicionar_categoria():
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    
    nome_cat = request.form.get("nome_categoria")
    res_id = session['restaurante_id']

    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO categorias (nome, restaurante_id) VALUES (%s, %s)", (nome_cat, res_id))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.painel_admin'))


@admin_bp.route("/admin/categorias/excluir/<int:id_cat>", methods=["POST"])
def excluir_categoria(id_cat):
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    
    res_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM categorias WHERE id = %s AND restaurante_id = %s", (id_cat, res_id))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.painel_admin'))


@admin_bp.route("/admin/promocao/<int:id_produto>", methods=["POST"])
def gerenciar_promocao(id_produto):
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    
    res_id = session['restaurante_id']
    status_promo = request.form.get("em_promo") in ['1', 'true', 'on', 'True', True]
    valor_promo = float(request.form.get("preco_promo", 0.0))

    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute('''
        UPDATE cardapio 
        SET em_promo = %s, preco_promo = %s 
        WHERE id = %s AND restaurante_id = %s
    ''', (status_promo, valor_promo, id_produto, res_id))
    
    conexao.commit()
    conexao.close()
    flash("Promoção atualizada!", "success")
    return redirect(url_for('admin.painel_admin'))


@admin_bp.route("/admin/novo", methods=["POST"])
def adicionar_lanche():
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    restaurante_id = session['restaurante_id']

    nome = request.form.get("nome")
    preco = request.form.get("preco")
    categoria = request.form.get("categoria")
    descricao = request.form.get("descricao", "").strip() 

    imagem = request.files.get("imagem")
    caminho_imagem = ""

    if imagem and imagem.filename != "":
        nome_seguro = secure_filename(imagem.filename)
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        caminho_salvar = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_seguro)
        img_aberta = Image.open(imagem)

        if img_aberta.mode != 'RGB':
            img_aberta = img_aberta.convert('RGB')
        img_aberta.thumbnail((800, 800))
        img_aberta.save(caminho_salvar, format='JPEG', optimize=True, quality=70)    
        caminho_imagem = f"uploads/{nome_seguro}"

    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute('''
        INSERT INTO cardapio (nome, preco, categoria, imagem, restaurante_id, descricao)
        VALUES(%s, %s, %s, %s, %s, %s)''', (nome, preco, categoria, caminho_imagem, restaurante_id, descricao))
    
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.painel_admin'))


@admin_bp.route("/admin/editar/<int:id_produto>", methods=["GET", "POST"])
def editar_produto(id_produto):
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    restaurante_id = session['restaurante_id']

    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")
        categoria = request.form.get("categoria")
        descricao = request.form.get("descricao", "").strip()
        imagem = request.files.get("imagem") 

        if imagem and imagem.filename != "":
            nome_seguro = secure_filename(imagem.filename)
            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
            caminho_salvar = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_seguro)
            
            img_aberta = Image.open(imagem)
            if img_aberta.mode != 'RGB':
                img_aberta = img_aberta.convert('RGB')
            img_aberta.thumbnail((800, 800))
            img_aberta.save(caminho_salvar, format='JPEG', optimize=True, quality=70) 
            
            caminho_imagem = f"uploads/{nome_seguro}"

            cursor.execute('''
                UPDATE cardapio
                SET nome = %s, preco = %s, categoria = %s, descricao = %s, imagem = %s
                WHERE id = %s AND restaurante_id = %s
            ''', (nome, preco, categoria, descricao, caminho_imagem, id_produto, restaurante_id))
        else:
            cursor.execute('''
                UPDATE cardapio
                SET nome = %s, preco = %s, categoria = %s, descricao = %s
                WHERE id = %s AND restaurante_id = %s
            ''', (nome, preco, categoria, descricao, id_produto, restaurante_id))
            
        conexao.commit()
        conexao.close()
        return redirect(url_for('admin.painel_admin'))
    
    cursor.execute("SELECT * FROM cardapio WHERE id = %s AND restaurante_id = %s", (id_produto, restaurante_id))
    produto_atual = cursor.fetchone()
    
    cursor.execute("SELECT * FROM categorias WHERE restaurante_id = %s", (restaurante_id,))
    categorias_atuais = cursor.fetchall()
    conexao.close()
    
    if not produto_atual:
        return redirect(url_for('admin.painel_admin'))
    
    return render_template("editar.html", produto=produto_atual, categorias_atuais=categorias_atuais)


@admin_bp.route("/admin/excluir/<int:id_produto>", methods=["POST"])
def excluir_produto(id_produto):
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
        
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM cardapio WHERE id = %s AND restaurante_id = %s", (id_produto, restaurante_id))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.painel_admin'))


@admin_bp.route("/admin/clientes")
def painel_crm_clientes():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT plano FROM restaurantes WHERE id = %s", (restaurante_id,))
    resultado_plano = cursor.fetchone()
    plano_atual = resultado_plano['plano'] if resultado_plano else 'salao'

    status_busca = '%finalizado%'

    cursor.execute('''
        SELECT 
            MAX(nome_cliente) as nome, 
            telefone_cliente, 
            COUNT(id) as qtd_pedidos, 
            SUM(total) as valor_gasto,
            MAX(data_hora) as ultimo_pedido
        FROM pedidos 
        WHERE restaurante_id = %s AND status ILIKE %s AND telefone_cliente != '' AND telefone_cliente IS NOT NULL
        GROUP BY telefone_cliente 
        ORDER BY valor_gasto DESC
    ''', (restaurante_id, status_busca))

    clientes_crm = [dict(c) for c in cursor.fetchall()]
    total_clientes_unicos = len(clientes_crm)
    conexao.close()
    
    return render_template("clientes.html", clientes=clientes_crm, total_clientes_unicos=total_clientes_unicos, plano=plano_atual)


@admin_bp.route("/admin/clientes/exportar")
def exportar_clientes_csv():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
        
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    status_busca = '%finalizado%'

    cursor.execute('''
        SELECT 
            MAX(nome_cliente) as nome, 
            telefone_cliente, 
            COUNT(id) as qtd_pedidos, 
            SUM(total) as valor_gasto,
            MAX(data_hora) as ultimo_pedido
        FROM pedidos 
        WHERE restaurante_id = %s AND status ILIKE %s AND telefone_cliente != '' AND telefone_cliente IS NOT NULL
        GROUP BY telefone_cliente 
        ORDER BY valor_gasto DESC
    ''', (restaurante_id, status_busca))
    
    clientes_crm = cursor.fetchall()
    conexao.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Nome do Cliente', 'WhatsApp', 'Qtd. Pedidos', 'Total Gasto ', 'Data do Ultimo Pedido'])
    
    for cliente in clientes_crm:
        nome = cliente['nome'] if cliente['nome'] else 'Cliente Sem Nome'
        telefone = cliente['telefone_cliente']
        qtd = cliente['qtd_pedidos']
        gasto = f"R$ {cliente['valor_gasto']:.2f}".replace('.', ',') 
        data = cliente['ultimo_pedido']
        writer.writerow([nome, telefone, qtd, gasto, data])
    
    resposta = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv')
    resposta.headers["Content-Disposition"] = "attachment; filename=base_clientes_premium.csv"
    return resposta


@admin_bp.route("/admin/faturamento/exportar")
def exportar_faturamento_csv():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
        
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute('''
        SELECT id, data_hora, nome_cliente, telefone_cliente, total, cupom_usado, status
        FROM pedidos 
        WHERE restaurante_id = %s
        ORDER BY id DESC
    ''', (restaurante_id,))
    
    historico_pedidos = cursor.fetchall()
    conexao.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID do Pedido', 'Data e Hora', 'Cliente', 'WhatsApp', 'Valor Total', 'Cupom Usado', 'Status'])
    
    for pedido in historico_pedidos:
        id_ped = pedido['id']
        data = pedido['data_hora']
        nome = pedido['nome_cliente'] if pedido['nome_cliente'] else 'Sem Nome'
        telefone = pedido['telefone_cliente'] if pedido['telefone_cliente'] else '-'
        valor = f"R$ {pedido['total']:.2f}".replace('.', ',') 
        cupom = pedido['cupom_usado'] if pedido['cupom_usado'] else '-'
        status = pedido['status'].upper()
        writer.writerow([id_ped, data, nome, telefone, valor, cupom, status])
    
    resposta = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv')
    resposta.headers["Content-Disposition"] = "attachment; filename=relatorio_faturamento.csv"
    return resposta


@admin_bp.route("/admin/cupons")
def painel_cupons():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT plano FROM restaurantes WHERE id = %s", (restaurante_id,))
    resultado_plano = cursor.fetchone()
    plano_atual = resultado_plano['plano'] if resultado_plano else 'salao'

    cursor.execute("SELECT * FROM cupons WHERE restaurante_id = %s ORDER BY id DESC", (restaurante_id,))
    cupons = [dict(c) for c in cursor.fetchall()]
    conexao.close()

    return render_template("cupom.html", cupons=cupons, plano=plano_atual)


@admin_bp.route("/admin/cupons/novo", methods=["POST"])
def adicionar_cupom():
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))

    restaurante_id = session['restaurante_id']
    codigo = request.form.get("codigo").upper().strip()
    tipo = request.form.get("tipo")
    valor = float(request.form.get("valor", 0.0))
    valor_minimo = float(request.form.get("valor_minimo", 0.0))
    limite_uso = int(request.form.get("limite_uso", 0))
    validade = request.form.get("validade")
    
    if not validade or validade == "":
        validade = None
        
    meta_pedidos = int(request.form.get("meta_pedidos", 0))
    tipo_limite = request.form.get("tipo_limite", "global")

    conexao = get_conexao()
    cursor = conexao.cursor()

    try:
        cursor.execute('''
            INSERT INTO cupons (restaurante_id, codigo, tipo, valor, valor_minimo, limite_uso, validade, status, meta_pedidos, tipo_limite)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'ativo', %s, %s)''', 
            (restaurante_id, codigo, tipo, valor, valor_minimo, limite_uso, validade, meta_pedidos, tipo_limite))
        conexao.commit()
    except Exception as e:
        print(f"Erro ao criar cupom: {e}")
    finally:
        conexao.close()

    return redirect(url_for('admin.painel_cupons'))


@admin_bp.route("/admin/cupons/toggle/<int:id_cupom>")
def toogle_cupom(id_cupom):
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    restaurante_id = session['restaurante_id']

    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT status FROM cupons WHERE id = %s AND restaurante_id = %s", (id_cupom, restaurante_id))
    resultado = cursor.fetchone()

    if resultado:
        novo_status = 'inativo' if resultado['status'] == 'ativo' else 'ativo'
        cursor.execute("UPDATE cupons SET status = %s WHERE id = %s AND restaurante_id = %s", (novo_status, id_cupom, restaurante_id))
        conexao.commit()
    
    conexao.close()
    return redirect(url_for('admin.painel_cupons'))


@admin_bp.route("/admin/cupons/excluir/<int:id_cupom>", methods=["POST"])
def excluir_cupom(id_cupom):
    if 'usuario_id' not in session: return redirect(url_for('auth.login'))
    restaurante_id = session['restaurante_id']

    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM cupons WHERE id = %s AND restaurante_id = %s", (id_cupom, restaurante_id))
    conexao.commit()
    conexao.close()

    return redirect(url_for('admin.painel_cupons'))


@admin_bp.route('/admin/produto/<int:produto_id>/opcoes', methods=['GET', 'POST'])
def gerenciar_opcoes(produto_id):
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT nome, categoria FROM cardapio WHERE id = %s", (produto_id,))
    produto = cursor.fetchone()
    produto_nome = produto['nome'] if produto else "Produto"
    produto_categoria = produto['categoria'] if produto else ""

    if request.method == 'POST':
        tipo = request.form.get('tipo')
        nome = request.form.get('nome')
        preco = request.form.get('preco')
        escopo = request.form.get('escopo') 
        
        preco = float(preco.replace(',', '.')) if preco else 0.0

        cat_alvo = produto_categoria if escopo == 'global' else None
        prod_id = produto_id if escopo == 'local' else None

        if tipo == 'variacao':
            cursor.execute("INSERT INTO variacoes (produto_id, categoria_alvo, nome, preco_adicional) VALUES (%s, %s, %s, %s)", (prod_id, cat_alvo, nome, preco))
        elif tipo == 'complemento':
            cursor.execute("INSERT INTO complementos (produto_id, categoria_alvo, nome, preco) VALUES (%s, %s, %s, %s)", (prod_id, cat_alvo, nome, preco))
        
        conexao.commit()
        return redirect(url_for('admin.gerenciar_opcoes', produto_id=produto_id))

    cursor.execute("SELECT * FROM variacoes WHERE produto_id = %s", (produto_id,))
    variacoes_locais = cursor.fetchall()
    cursor.execute("SELECT * FROM complementos WHERE produto_id = %s", (produto_id,))
    complementos_locais = cursor.fetchall()

    cursor.execute("SELECT * FROM variacoes WHERE categoria_alvo = %s", (produto_categoria,))
    variacoes_herdadas = cursor.fetchall()
    cursor.execute("SELECT * FROM complementos WHERE categoria_alvo = %s", (produto_categoria,))
    complementos_herdados = cursor.fetchall()

    cursor.execute("SELECT tipo_opcao, opcao_id FROM opcoes_ocultas WHERE produto_id = %s", (produto_id,))
    ocultas = cursor.fetchall()
    
    ids_variacoes_ocultas = [o['opcao_id'] for o in ocultas if o['tipo_opcao'] == 'variacao']
    ids_complementos_ocultos = [o['opcao_id'] for o in ocultas if o['tipo_opcao'] == 'complemento']

    conexao.close()
    
    return render_template('admin_opcoes.html', 
                           produto_id=produto_id, 
                           produto_nome=produto_nome,
                           produto_categoria=produto_categoria,
                           variacoes_locais=variacoes_locais,
                           complementos_locais=complementos_locais,
                           variacoes_herdadas=variacoes_herdadas,
                           complementos_herdados=complementos_herdados,
                           ids_variacoes_ocultas=ids_variacoes_ocultas,
                           ids_complementos_ocultos=ids_complementos_ocultos)


# --- ROTAS DE AÇÃO (EXCLUIR, OCULTAR, RESTAURAR) ---

@admin_bp.route('/admin/deletar_opcao/<tipo>/<int:id_opcao>/<int:produto_id>')
def deletar_opcao(tipo, id_opcao, produto_id):
    conexao = get_conexao()
    cursor = conexao.cursor()
    if tipo == 'variacao':
        cursor.execute("DELETE FROM variacoes WHERE id = %s", (id_opcao,))
    elif tipo == 'complemento':
        cursor.execute("DELETE FROM complementos WHERE id = %s", (id_opcao,))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.gerenciar_opcoes', produto_id=produto_id))

@admin_bp.route('/admin/ocultar_opcao/<tipo>/<int:id_opcao>/<int:produto_id>')
def ocultar_opcao(tipo, id_opcao, produto_id):
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO opcoes_ocultas (produto_id, tipo_opcao, opcao_id) VALUES (%s, %s, %s)", (produto_id, tipo, id_opcao))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.gerenciar_opcoes', produto_id=produto_id))

@admin_bp.route('/admin/restaurar_opcao/<tipo>/<int:id_opcao>/<int:produto_id>')
def restaurar_opcao(tipo, id_opcao, produto_id):
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM opcoes_ocultas WHERE produto_id = %s AND tipo_opcao = %s AND opcao_id = %s", (produto_id, tipo, id_opcao))
    conexao.commit()
    conexao.close()
    return redirect(url_for('admin.gerenciar_opcoes', produto_id=produto_id))