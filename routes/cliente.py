from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from datetime import datetime
from db import get_conexao
from psycopg2.extras import RealDictCursor

# Criando o Blueprint do Cliente (Cardápio e Checkout)
cliente_bp = Blueprint('cliente', __name__)

# FUNÇÃO AUXILIAR PARA GARANTIR QUE O CARRINHO EXISTE NA SESSÃO
def get_carrinho():
    if 'carrinho' not in session:
        session['carrinho'] = []
    return session['carrinho']

def salvar_carrinho(carrinho):
    session['carrinho'] = carrinho
    session.modified = True

@cliente_bp.route("/<slug_restaurante>")
def cardapio_cliente(slug_restaurante):
    conexao = get_conexao()
    # Usando RealDictCursor para garantir acesso por nome de coluna (ex: restaurante['id'])
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Busca os dados do restaurante
        cursor.execute("""
            SELECT id, nome, cor_tema, status, cor_fundo, logo, fundo_imagem, 
                   cor_card, cor_texto, cor_texto_botao 
            FROM restaurantes WHERE slug = %s
        """, (slug_restaurante,))
        restaurante = cursor.fetchone()
        
        if not restaurante:
            return f"Restaurante '{slug_restaurante}' não encontrado!", 404
        
        # 2. Verifica se o restaurante está ativo
        if restaurante['status'] != 'ativo':
            return "<h1>Serviço Temporariamente Indisponível</h1><p>Este cardápio está em manutenção.</p>", 403
        
        # 🔥 MÁGICA AQUI: Salva o slug na sessão para a função de remover/adicionar saber para onde voltar
        session['ultimo_slug'] = slug_restaurante
        
        # 3. Busca os itens do cardápio deste restaurante
        cursor.execute("""
            SELECT * FROM cardapio 
            WHERE restaurante_id = %s 
            ORDER BY categoria ASC, em_promo DESC, nome ASC
        """, (restaurante['id'],))
        itens = cursor.fetchall()

        carrinho_atual = get_carrinho()
        
        return render_template("index.html", 
                               cardapio=itens, 
                               restaurante_nome=restaurante['nome'], 
                               cor_tema=restaurante['cor_tema'], 
                               cor_fundo=restaurante['cor_fundo'] or '#f4f4f4',
                               cor_card=restaurante['cor_card'] or '#ffffff', 
                               cor_texto=restaurante['cor_texto'] or '#2c3e50', 
                               logo=restaurante['logo'],              
                               fundo_img=restaurante['fundo_imagem'],    
                               restaurante_id=restaurante['id'], 
                               carrinho=carrinho_atual,
                               cor_texto_botao=restaurante['cor_texto_botao'] or '#ffffff')
    
    except Exception as e:
        print(f"Erro no cardápio: {e}")
        return "Erro interno ao carregar o cardápio.", 500
    finally:
        cursor.close()
        conexao.close()

@cliente_bp.route('/carrinho/adicionar/<int:id_produto>', methods=['POST'])
def adicionar_ao_carrinho(id_produto):
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        quantidade = int(request.form.get('quantidade', 1))
        observacao = request.form.get('observacao', '')
        variacao_id = request.form.get('variacao_id') 
        complementos_ids = request.form.getlist('complemento_id') 

        cursor.execute("SELECT nome, preco FROM cardapio WHERE id = %s", (id_produto,))
        produto = cursor.fetchone()
        if not produto:
            return jsonify({"sucesso": False, "erro": "Produto não encontrado"})

        nome_final = produto['nome']
        preco_unitario = float(produto['preco'])

        if variacao_id and variacao_id != 'base':
            cursor.execute("SELECT nome, preco_adicional FROM variacoes WHERE id = %s", (variacao_id,))
            var_data = cursor.fetchone()
            if var_data:
                nome_final += f" ({var_data['nome']})"
                preco_unitario += float(var_data['preco_adicional'])

        nomes_complementos = []
        if complementos_ids:
            # Postgres IN clause com psycopg2 exige uma tupla
            cursor.execute("SELECT nome, preco FROM complementos WHERE id IN %s", (tuple(complementos_ids),))
            comps_data = cursor.fetchall()
            
            for c in comps_data:
                nomes_complementos.append(c['nome'])
                preco_unitario += float(c['preco'])

            if nomes_complementos:
                nome_final += " + " + ", ".join(nomes_complementos)

        subtotal = preco_unitario * quantidade
        item_carrinho = {
            "id_produto": id_produto,
            "nome": nome_final,
            "preco_unitario": preco_unitario,
            "quantidade": quantidade,
            "observacao": observacao,
            "subtotal": subtotal
        }

        carrinho = get_carrinho()
        carrinho.append(item_carrinho)
        salvar_carrinho(carrinho)

        return jsonify({"sucesso": True, "mensagem": "Adicionado com sucesso!"})

    except Exception as e:
        print(f"🔥 ERRO NO CARRINHO: {e}")
        return jsonify({"sucesso": False, "erro": "Erro interno"}), 500
    finally:
        conexao.close()

@cliente_bp.route('/api/produto/<int:produto_id>')
def api_detalhes_produto(produto_id):
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT id, nome, descricao, preco, categoria FROM cardapio WHERE id = %s", (produto_id,))
        prod = cursor.fetchone()
        if not prod:
            return jsonify({"erro": "Produto não encontrado"}), 404

        cursor.execute("SELECT tipo_opcao, opcao_id FROM opcoes_ocultas WHERE produto_id = %s", (produto_id,))
        ocultas = cursor.fetchall()
        ids_var_ocultas = [o['opcao_id'] for o in ocultas if o['tipo_opcao'] == 'variacao']
        ids_comp_ocultos = [o['opcao_id'] for o in ocultas if o['tipo_opcao'] == 'complemento']

        cursor.execute("""
            SELECT id, nome, preco_adicional FROM variacoes 
            WHERE produto_id = %s OR categoria_alvo = %s
        """, (produto_id, prod['categoria']))
        variacoes = [{"id": v['id'], "nome": v['nome'], "preco": float(v['preco_adicional'])} 
                     for v in cursor.fetchall() if v['id'] not in ids_var_ocultas]

        cursor.execute("""
            SELECT id, nome, preco FROM complementos 
            WHERE produto_id = %s OR categoria_alvo = %s
        """, (produto_id, prod['categoria']))
        complementos = [{"id": c['id'], "nome": c['nome'], "preco": float(c['preco'])} 
                        for c in cursor.fetchall() if c['id'] not in ids_comp_ocultos]

        return jsonify({
            "id": prod['id'],
            "nome": prod['nome'],
            "descricao": prod['descricao'],
            "preco_base": float(prod['preco']),
            "variacoes": variacoes,
            "complementos": complementos
        })
    finally:
        conexao.close()

@cliente_bp.route("/remover_carrinho/<int:indice>")
def remover_do_carrinho(indice):
    carrinho = get_carrinho()
    if 0 <= indice < len(carrinho):
        carrinho.pop(indice)
        salvar_carrinho(carrinho)
    return redirect(request.referrer or url_for('cliente.cardapio_cliente', slug_restaurante=session.get('ultimo_slug', '')))




@cliente_bp.route("/api/verificar_recompensas", methods=["POST"])
def verificar_recompensas():
    dados = request.json
    tel = dados.get("telefone", "").strip()
    res_id = dados.get("restaurante_id")

    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    # TRAVA PREMIUM (Ignora maiúsculas e espaços)
    cursor.execute("SELECT plano FROM restaurantes WHERE id = %s", (res_id,))
    res_plano = cursor.fetchone()
    
    plano = str(res_plano['plano']).strip().lower() if res_plano and res_plano.get('plano') else ''
    if plano != 'premium':
        conexao.close()
        return jsonify({"status": "vazio"})

    # LÓGICA ORIGINAL DE BUSCA
    cursor.execute("SELECT COUNT(id) as qtd FROM pedidos WHERE restaurante_id = %s AND telefone_cliente = %s", (res_id, tel))
    proximo = cursor.fetchone()['qtd'] + 1

    cursor.execute("""
        SELECT * FROM cupons 
        WHERE restaurante_id = %s AND status = 'ativo' AND (meta_pedidos = %s OR tipo_limite = 'global')
        ORDER BY meta_pedidos DESC, id DESC LIMIT 1
    """, (res_id, proximo))
    cupom = cursor.fetchone()
    conexao.close()

    if cupom:
        texto = f"{int(cupom['valor'])}% OFF" if cupom['tipo'] == 'porcentagem' else f"R$ {cupom['valor']:.2f} OFF"
        return jsonify({
            "status": "sucesso", "codigo": cupom['codigo'], "texto_desconto": texto,
            "proximo_pedido": proximo, "valor_minimo": float(cupom['valor_minimo'])
        })
    
    return jsonify({"status": "vazio"})


@cliente_bp.route("/api/validar_cupom", methods=["POST"])
def validar_cupom():
    try:
        dados = request.json
        codigo = dados.get("codigo", "").upper().strip()
        restaurante_id = dados.get("restaurante_id")
        telefone = dados.get("telefone", "").strip()
        valor_carrinho = float(dados.get("total", 0.0))
        device_id = dados.get("device_id", "").strip()
        
        conexao = get_conexao()
        cursor = conexao.cursor(cursor_factory=RealDictCursor)

        # TRAVA PREMIUM (Ignora maiúsculas e espaços)
        cursor.execute("SELECT plano FROM restaurantes WHERE id = %s", (restaurante_id,))
        res_plano = cursor.fetchone()
        
        plano = str(res_plano['plano']).strip().lower() if res_plano and res_plano.get('plano') else ''
        if plano != 'premium':
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Funcionalidade indisponível para este estabelecimento."})

        # LÓGICA ORIGINAL DE VALIDAÇÃO
        cursor.execute("""
            SELECT * FROM cupons WHERE codigo = %s AND restaurante_id = %s
        """, (codigo, restaurante_id))
        cupom = cursor.fetchone()

        if not cupom:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Cupom inválido!"}), 404
        
        if cupom['status'] != 'ativo':
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Cupom inativo."})

        if cupom['validade'] and datetime.now().date() > cupom['validade']:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Cupom expirou."})

        if cupom['limite_uso'] > 0 and cupom['qtd_usos'] >= cupom['limite_uso']:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Limite atingido."})

        if valor_carrinho < float(cupom['valor_minimo']):
            conexao.close()
            return jsonify({"status": "erro", "mensagem": f"Mínimo R$ {cupom['valor_minimo']:.2f}"})

        if cupom['tipo_limite'] == 'por_cliente':
            cursor.execute("""
                SELECT COUNT(id) as qtd FROM pedidos 
                WHERE restaurante_id = %s AND cupom_usado = %s AND (
                    (telefone_cliente = %s AND telefone_cliente != '') OR 
                    (device_id = %s AND device_id != '')
                )
            """, (restaurante_id, codigo, telefone, device_id))
            if cursor.fetchone()['qtd'] > 0:
                conexao.close()
                return jsonify({"status": "erro", "mensagem": "Já utilizou este cupom."})

        desconto = valor_carrinho * (float(cupom['valor']) / 100) if cupom['tipo'] == 'porcentagem' else float(cupom['valor'])

        conexao.close()
        return jsonify({"status": "sucesso", "desconto": desconto, "mensagem": "Cupom aplicado!"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@cliente_bp.route("/finalizar", methods=["POST"])
def finalizar_pedido():
    # 1. Coleta de dados
    mesa = request.form.get("numero_mesa")
    forma_pagamento = request.form.get("forma_pagamento")
    obs_cliente = request.form.get("observacao") 
    res_id = request.form.get("restaurante_id")
    nome_cliente = request.form.get("nome_cliente", "")
    tel_cliente = request.form.get("telefone_cliente", "")
    device_id = request.form.get("device_id", "")
    codigo_cupom = request.form.get("cupom_codigo")
    caminho_de_volta = request.form.get("url_voltar") or "/"

    carrinho = get_carrinho()
    nome_itens = []
    total = 0.0

    for item in carrinho:
        detalhe = f"{item['quantidade']}x {item['nome']}"
        if item.get('observacao') and item['observacao'].strip():
            detalhe += f" (Obs: {item['observacao']})"
        nome_itens.append(detalhe)
        total += float(item['subtotal'])

    # 2. Conexão com AUTOCOMMIT (Força o banco a salvar na hora)
    conexao = get_conexao()
    conexao.autocommit = True # <-- ISSO AQUI É A CHAVE
    cursor = conexao.cursor()

    try:
        # Lógica de Cupom
        if codigo_cupom:
            # TRAVA PREMIUM: Valida o plano antes de aplicar o desconto no banco
            cursor.execute("SELECT plano FROM restaurantes WHERE id = %s", (res_id,))
            res_plano = cursor.fetchone()
            
            if res_plano and res_plano[0] == 'premium':
                cursor.execute("SELECT id, status, tipo, valor FROM cupons WHERE codigo = %s AND restaurante_id = %s", (codigo_cupom.upper(), res_id))
                cupom = cursor.fetchone()
                if cupom and cupom[1] == 'ativo':
                    desconto = total * (float(cupom[3]) / 100) if cupom[2] == 'porcentagem' else float(cupom[3])
                    total -= desconto
                    cursor.execute("UPDATE cupons SET qtd_usos = qtd_usos + 1 WHERE id = %s", (cupom[0],))
            else:
                print(f"⚠️ Tentativa de bypass: Cupom ignorado (restaurante não-premium ID: {res_id})")

        status_txt = f"pendente - {forma_pagamento}"
        itens_txt = ", ".join(nome_itens)

        # 3. Insert com LOG de verificação
        print(f"--- TENTANDO GRAVAR PEDIDO PARA RESTAURANTE {res_id} ---")
        
        cursor.execute("""
            INSERT INTO pedidos (mesa, itens, total, status, data_hora, observacao, restaurante_id, nome_cliente, telefone_cliente, cupom_usado, device_id) 
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (str(mesa), itens_txt, float(total), status_txt, obs_cliente, int(res_id), nome_cliente, tel_cliente, codigo_cupom or '', device_id))
        
        pedido_id = cursor.fetchone()[0]
        print(f"--- PEDIDO GRAVADO COM SUCESSO! ID: {pedido_id} ---")

        # Dados para o template
        cursor.execute("SELECT chave_pix, telefone_whatsapp FROM restaurantes WHERE id = %s", (res_id,))
        # Como o cursor não é RealDict, pegamos por índice
        res_row = cursor.fetchone()
        chave_pix = res_row[0] if res_row else ''
        wpp = res_row[1] if res_row else ''

        # Limpa carrinho e finaliza
        session['carrinho'] = []
        session.modified = True
        
        return render_template("pagamento.html", 
                               mesa=mesa, total=total, forma_pagamento=forma_pagamento,
                               url_voltar=caminho_de_volta,
                               pedido_id=pedido_id, 
                               itens="\n".join(nome_itens),
                               nome_cliente=nome_cliente, 
                               chave_pix=chave_pix,
                               telefone_whatsapp=wpp)

    except Exception as e:
        print(f"🚨 ERRO REAL NO BANCO: {e}")
        return f"Erro: {e}", 500
    finally:
        cursor.close()
        conexao.close()