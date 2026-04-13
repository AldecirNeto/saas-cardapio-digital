from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from datetime import datetime
import sqlite3

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
    print(f"Buscando restaurante com slug: {slug_restaurante}")
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT id, nome, cor_tema, status, cor_fundo, logo, fundo_imagem, cor_card, cor_texto, cor_texto_botao FROM restaurantes WHERE slug = ?", (slug_restaurante,))
    restaurante = cursor.fetchone()
    
    if not restaurante:
        conexao.close()
        return f"Restaurante '{slug_restaurante}' não encontrado!", 404
    
    # VERIFICA SE ESTÁ ATIVO (Bloqueio de Inadimplência)
    if restaurante[3] != 'ativo':
        conexao.close()
        return "<h1>Serviço Temporariamente Indisponível</h1><p>Este cardápio está em manutenção.</p>", 403
    
    res_id = restaurante[0]
    res_nome = restaurante[1]
    res_cor = restaurante[2]
    res_cor_fundo = restaurante[4] if restaurante[4] else '#f4f4f4'
    res_logo = restaurante[5]
    res_fundo_img = restaurante[6]
    res_cor_card = restaurante[7] if restaurante[7] else '#ffffff'  
    res_cor_texto = restaurante[8] if restaurante[8] else '#2c3e50'
    res_cor_texto_botao = restaurante[9] if restaurante[9] else '#ffffff'

    cursor.execute("SELECT * FROM cardapio WHERE restaurante_id = ? ORDER BY categoria ASC, em_promo DESC, nome ASC", (res_id,))
    itens = cursor.fetchall()

    conexao.close()
    
    carrinho_atual = get_carrinho()
    
    return render_template("index.html", 
                           cardapio=itens, 
                           restaurante_nome=res_nome, 
                           cor_tema=res_cor, 
                           cor_fundo=res_cor_fundo,
                           cor_card=res_cor_card, 
                           cor_texto=res_cor_texto, 
                           logo=res_logo,              
                           fundo_img=res_fundo_img,    
                           restaurante_id=res_id, 
                           carrinho=carrinho_atual,
                           cor_texto_botao=res_cor_texto_botao)

@cliente_bp.route('/carrinho/adicionar/<int:id_produto>', methods=['POST'])
def adicionar_ao_carrinho(id_produto):
    import sqlite3
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    try:
        print(f"\n🛒 CHEGOU PEDIDO DE ADIÇÃO! Produto ID: {id_produto}")
        print(f"📦 DADOS DO FORMULÁRIO: {request.form}")
        # 1. Pegamos tudo que o Modal enviou
        quantidade = int(request.form.get('quantidade', 1))
        observacao = request.form.get('observacao', '')
        variacao_id = request.form.get('variacao_id') 
        complementos_ids = request.form.getlist('complemento_id') 

        # 2. Pega o Produto Original
        cursor.execute("SELECT nome, preco FROM cardapio WHERE id = ?", (id_produto,))
        produto = cursor.fetchone()
        if not produto:
            return jsonify({"sucesso": False, "erro": "Produto não encontrado"})

        nome_final = produto[0]
        preco_unitario = produto[1]

        # 3. Calcula a Variação (Se não for a Original)
        if variacao_id and variacao_id != 'base':
            cursor.execute("SELECT nome, preco_adicional FROM variacoes WHERE id = ?", (variacao_id,))
            var_data = cursor.fetchone()
            if var_data:
                nome_final += f" ({var_data[0]})"
                preco_unitario += var_data[1]

        # 4. Calcula os Complementos (CORRIGIDO: Só busca se a lista NÃO estiver vazia)
        nomes_complementos = []
        if complementos_ids and len(complementos_ids) > 0:
            placeholders = ','.join('?' for _ in complementos_ids)
            cursor.execute(f"SELECT nome, preco FROM complementos WHERE id IN ({placeholders})", complementos_ids)
            comps_data = cursor.fetchall()
            
            for c in comps_data:
                nomes_complementos.append(c[0])
                preco_unitario += c[1]

            if nomes_complementos:
                nome_final += " + " + ", ".join(nomes_complementos)

        # 5. Prepara o pacote pro carrinho
        subtotal = preco_unitario * quantidade
        item_carrinho = {
            "id_produto": id_produto,
            "nome": nome_final,
            "preco_unitario": preco_unitario,
            "quantidade": quantidade,
            "observacao": observacao,
            "subtotal": subtotal
        }

        # 6. Salva na Sessão
        if 'carrinho' not in session:
            session['carrinho'] = []
        
        session['carrinho'].append(item_carrinho)
        session.modified = True

        return jsonify({"sucesso": True, "mensagem": "Adicionado com sucesso!"})

    except Exception as e:
        print(f"🔥 ERRO CRÍTICO AO ADICIONAR NO CARRINHO: {e}")
        return jsonify({"sucesso": False, "erro": "Erro interno no servidor"}), 500

    finally:
        # A BLINDAGEM: Fechar a conexão AQUI garante que o banco nunca trave.
        conexao.close()

@cliente_bp.route('/api/produto/<int:produto_id>')
def api_detalhes_produto(produto_id):
    import sqlite3
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    try:
        # 1. Busca os dados do produto
        cursor.execute("SELECT id, nome, descricao, preco, categoria FROM cardapio WHERE id = ?", (produto_id,))
        prod = cursor.fetchone()
        
        if not prod:
            return jsonify({"erro": "Produto não encontrado"}), 404

        produto_categoria = prod[4]

        # 2. Busca IDs Ocultos da Lista Negra
        cursor.execute("SELECT tipo_opcao, opcao_id FROM opcoes_ocultas WHERE produto_id = ?", (produto_id,))
        ocultas = cursor.fetchall()
        ids_var_ocultas = [o[1] for o in ocultas if o[0] == 'variacao']
        ids_comp_ocultos = [o[1] for o in ocultas if o[0] == 'complemento']

        # 3. Busca Variações (Locais + Categoria)
        cursor.execute("SELECT id, nome, preco_adicional FROM variacoes WHERE produto_id = ? OR categoria_alvo = ?", (produto_id, produto_categoria))
        variacoes_brutas = cursor.fetchall()
        variacoes = [{"id": v[0], "nome": v[1], "preco": v[2]} for v in variacoes_brutas if v[0] not in ids_var_ocultas]

        # 4. Busca Complementos (Locais + Categoria)
        cursor.execute("SELECT id, nome, preco FROM complementos WHERE produto_id = ? OR categoria_alvo = ?", (produto_id, produto_categoria))
        complementos_brutos = cursor.fetchall()
        complementos = [{"id": c[0], "nome": c[1], "preco": c[2]} for c in complementos_brutos if c[0] not in ids_comp_ocultos]

        return jsonify({
            "id": prod[0],
            "nome": prod[1],
            "descricao": prod[2],
            "preco_base": prod[3],
            "variacoes": variacoes,
            "complementos": complementos
        })

    except Exception as e:
        # SE QUEBRAR, ELE VAI GRITAR O ERRO AQUI NO TERMINAL:
        print(f"🔥 ERRO NA API DO MODAL: {e}")
        return jsonify({"erro": "Erro interno no servidor."}), 500

    finally:
        # Isso garante que o banco NUNCA mais vai ficar travado
        conexao.close()

@cliente_bp.route("/remover_carrinho/<int:indice>")
def remover_do_carrinho(indice):
    carrinho = get_carrinho()
    if 0 <= indice < len(carrinho):
        carrinho.pop(indice)
        salvar_carrinho(carrinho)
    return redirect(request.referrer)

@cliente_bp.route("/api/validar_cupom", methods=["POST"])
def validar_cupom():
    try:
        dados = request.json
        codigo = dados.get("codigo", "").upper().strip()
        restaurante_id = dados.get("restaurante_id")
        telefone = dados.get("telefone", "").strip()
        valor_carrinho = float(dados.get("total", 0.0))
        device_id = dados.get("device_id", "").strip()
        
        conexao = sqlite3.connect("Autoatendimento.db")
        cursor = conexao.cursor()

        cursor.execute('''SELECT id, tipo, valor, valor_minimo, limite_uso, qtd_usos, validade, status, meta_pedidos, tipo_limite
                        FROM cupons WHERE codigo = ? AND restaurante_id = ?''', (codigo, restaurante_id))
        cupom = cursor.fetchone()

        if not cupom:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Cupom inválido!"}), 404
        
        id_cupom, tipo, valor_desc, v_minimo, limite, usados, validade, status, meta, tipo_limite = cupom

        if status != 'ativo':
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Este cupom não está mais ativo."})

        if validade and datetime.now().strftime("%Y-%m-%d") > validade:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Este cupom expirou."})

        if limite > 0 and usados >= limite:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": "Este cupom já atingiu o limite de usos."})

        if valor_carrinho < v_minimo:
            conexao.close()
            return jsonify({"status": "erro", "mensagem": f"Pedido mínimo para este cupom é R$ {v_minimo:.2f}"})

        if tipo_limite == 'por_cliente':
            cursor.execute('''
                SELECT COUNT(id) FROM pedidos 
                WHERE restaurante_id = ? AND cupom_usado = ? AND (
                    (telefone_cliente = ? AND telefone_cliente != '') OR 
                    (device_id = ? AND device_id != '')
                )
            ''', (restaurante_id, codigo, telefone, device_id))
            
            ja_usou_antes = cursor.fetchone()[0]
            if ja_usou_antes > 0:
                conexao.close()
                return jsonify({"status": "erro", "mensagem": "Este aparelho ou telefone já utilizou este cupom de uso único."})

        if meta > 0:
            cursor.execute("SELECT COUNT(id) FROM pedidos WHERE restaurante_id = ? AND telefone_cliente = ?", (restaurante_id, telefone))
            qtd_pedidos_anteriores = cursor.fetchone()[0]
            proximo_pedido = qtd_pedidos_anteriores + 1

            if proximo_pedido != meta:
                conexao.close()
                return jsonify({
                    "status": "erro", 
                    "mensagem": f"Cupom exclusivo para o seu {meta}º pedido. Você está no {proximo_pedido}º."
                })

        desconto_aplicado = valor_carrinho * (valor_desc / 100) if tipo == 'porcentagem' else valor_desc

        conexao.close()
        return jsonify({
            "status": "sucesso",
            "desconto": desconto_aplicado,
            "mensagem": "Cupom aplicado com sucesso!"
        })

    except Exception as e:
        print(f"Erro no Back-end ao validar cupom: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno no servidor."}), 500

@cliente_bp.route("/finalizar", methods=["POST"])
def finalizar_pedido():
    mesa_digitada = request.form.get("numero_mesa")
    forma_pagamento = request.form.get("forma_pagamento")
    observacao_cliente = request.form.get("observacao") 
    restaurante_id = request.form.get("restaurante_id")
    caminho_de_volta = request.form.get("url_voltar")
    nome_cliente = request.form.get("nome_cliente", "")
    telefone_cliente = request.form.get("telefone_cliente", "")
    device_id = request.form.get("device_id", "")

    status = f"pendente - {forma_pagamento}"

    nome_itens = []
    total = 0
    carrinho = get_carrinho()

    for item in carrinho:
        detalhe_item = f"{item['quantidade']}x {item['nome']}"
        if item['observacao'].strip() != "":
            detalhe_item += f" (Obs: {item['observacao']})"
        nome_itens.append(detalhe_item)
        total += item['subtotal']

    itens_juntos = ", ".join(nome_itens)
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()    

    codigo_cupom = request.form.get("cupom_codigo")
    
    if codigo_cupom:
        cursor.execute("SELECT tipo, valor, valor_minimo, limite_uso, qtd_usos, validade, status, meta_pedidos, tipo_limite FROM cupons WHERE codigo = ? AND restaurante_id = ?", (codigo_cupom.upper(), restaurante_id))
        cupom_usado = cursor.fetchone()
        
        if cupom_usado:
            t_desc, v_desc, v_min, lim, usos, val, stat, meta, t_limite = cupom_usado
            cupom_valido = True
            
            if stat != 'ativo': cupom_valido = False
            if lim > 0 and usos >= lim: cupom_valido = False
            if total < v_min: cupom_valido = False
            if val and datetime.now().strftime("%Y-%m-%d") > val: cupom_valido = False
            
            if meta > 0:
                cursor.execute("SELECT COUNT(id) FROM pedidos WHERE restaurante_id = ? AND telefone_cliente = ?", (restaurante_id, telefone_cliente))
                pedidos_ant = cursor.fetchone()[0]
                if (pedidos_ant + 1) != meta: cupom_valido = False
                
            if t_limite == 'por_cliente':
                cursor.execute("SELECT COUNT(id) FROM pedidos WHERE restaurante_id = ? AND cupom_usado = ? AND (telefone_cliente = ? OR (device_id = ? AND device_id != ''))", (restaurante_id, codigo_cupom.upper(), telefone_cliente, device_id))
                ja_usou = cursor.fetchone()[0]
                if ja_usou > 0: cupom_valido = False

            if cupom_valido:
                if t_desc == 'porcentagem':
                    total -= total * (v_desc / 100)
                else:
                    total -= v_desc
                    
                if total < 0: total = 0 
                
                cursor.execute('''UPDATE cupons SET qtd_usos = qtd_usos + 1 WHERE codigo = ? AND restaurante_id = ?''', (codigo_cupom.upper(), restaurante_id))

                if lim > 0 and (usos + 1) >= lim:
                    cursor.execute('''UPDATE cupons SET status = 'inativo' WHERE codigo = ? AND restaurante_id = ?''', (codigo_cupom.upper(), restaurante_id))     

    cursor.execute(''' 
        INSERT INTO pedidos (mesa, itens, total, status, data_hora, observacao, restaurante_id, nome_cliente, telefone_cliente, cupom_usado, device_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (mesa_digitada, itens_juntos, total, status, data_hora, observacao_cliente, restaurante_id, nome_cliente, telefone_cliente, codigo_cupom or '', device_id))

    pedido_id = cursor.lastrowid
    
    cursor.execute("SELECT chave_pix, telefone_whatsapp FROM restaurantes WHERE id = ?", (restaurante_id,))
    dados_res = cursor.fetchone()

    chave_pix_restaurante = dados_res[0] if dados_res and dados_res[0] else "chave não informada"
    whatsapp_restaurante = dados_res[1] if dados_res and dados_res[1] else ""

    conexao.commit()
    conexao.close()
    
    # Esvazia o carrinho apenas deste cliente na sessão!
    session['carrinho'] = []
    session.modified = True
    
    return render_template("pagamento.html", 
                           mesa=mesa_digitada, 
                           total=total, 
                           forma_pagamento=forma_pagamento,
                           url_voltar=caminho_de_volta,
                           pedido_id=pedido_id,
                           itens="\n".join(nome_itens),
                           nome_cliente=nome_cliente,
                           chave_pix=chave_pix_restaurante,
                           telefone_whatsapp=whatsapp_restaurante)

@cliente_bp.route("/api/verificar_recompensas", methods=["POST"])
def verificar_recompensas():
    dados = request.json
    telefone = dados.get("telefone", "").strip()
    restaurante_id = dados.get("restaurante_id")

    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    if telefone:
        cursor.execute('''SELECT COUNT(id) FROM pedidos WHERE restaurante_id = ? AND telefone_cliente = ?''', (restaurante_id, telefone))
        qtd_pedidos_anteriores = cursor.fetchone()[0]
    else:
        qtd_pedidos_anteriores = 0
        
    proximo_pedido = qtd_pedidos_anteriores + 1

    cursor.execute('''
        SELECT codigo, tipo, valor, valor_minimo, limite_uso, qtd_usos, tipo_limite 
        FROM cupons 
        WHERE restaurante_id = ? AND status = 'ativo' AND meta_pedidos = ? AND tipo_limite = 'por_cliente'
    ''', (restaurante_id, proximo_pedido))
    cupom = cursor.fetchone()

    if not cupom:
        cursor.execute('''
            SELECT codigo, tipo, valor, valor_minimo, limite_uso, qtd_usos, tipo_limite 
            FROM cupons 
            WHERE restaurante_id = ? AND status = 'ativo' AND tipo_limite = 'global'
            ORDER BY id DESC LIMIT 1
        ''', (restaurante_id,))
        cupom = cursor.fetchone()

    conexao.close()

    if cupom:
        codigo, tipo, valor, v_minimo, limite, usos, t_limite = cupom
        texto_desconto = f"{int(valor)}% OFF" if tipo == 'porcentagem' else f"R$ {valor:.2f} OFF"
        restantes = limite - usos if limite > 0 else 0
            
        return jsonify({
            "status": "sucesso",
            "codigo": codigo,
            "texto_desconto": texto_desconto,
            "proximo_pedido": proximo_pedido,
            "valor_minimo": v_minimo,
            "tipo_limite": t_limite,
            "limite_total": limite,
            "cupons_restantes": restantes
        })
    
    return jsonify({"status": "vazio"})