from flask import Blueprint, render_template, request, redirect, url_for, session
import sqlite3

# Criando o Blueprint da Operação (KDS e PDV)
operacao_bp = Blueprint('operacao', __name__)

@operacao_bp.route("/cozinha")
def painel_cozinha():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT tema_kds FROM restaurantes WHERE id = ?", (restaurante_id,))
    resultado_tema = cursor.fetchone()
    tema_kds = resultado_tema[0] if resultado_tema and resultado_tema[0] else 'dark'

    # Busca apenas os pendentes e pagos (lógica simples)
    cursor.execute("SELECT * FROM pedidos WHERE restaurante_id = ? AND (status LIKE 'pendente%' OR status LIKE 'pago%') ORDER BY id ASC", (restaurante_id,))

    pedidos_pendentes = cursor.fetchall()
    conexao.close()

    return render_template("cozinha.html", pedidos=pedidos_pendentes, tema_kds=tema_kds)


@operacao_bp.route("/pronto/<int:id_pedido>", methods=["GET", "POST"])
def marcar_pronto(id_pedido):
    if 'usuario_id' not in session: 
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']

    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()
    cursor.execute("SELECT status FROM pedidos WHERE id = ? AND restaurante_id = ?", (id_pedido, restaurante_id))
    resultado = cursor.fetchone()

    if resultado:
        status_atual = resultado[0]

        # A Dupla Validação Simples
        if status_atual.startswith("pendente"):
            novo_status = status_atual.replace("pendente", "pronto")
        elif status_atual.startswith("pago"):
            novo_status = "finalizado"
        else:
            novo_status = status_atual 

        cursor.execute("UPDATE pedidos SET status = ? WHERE id = ? AND restaurante_id = ?", (novo_status, id_pedido, restaurante_id))
        conexao.commit()

    conexao.close()    
    return redirect(url_for('operacao.painel_cozinha'))


@operacao_bp.route("/caixa")
def painel_caixa():
    if 'usuario_id' not in session or 'restaurante_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()
    
    # BUSCA O TEMA DA COZINHA/CAIXA (Dark/Light)
    cursor.execute("SELECT tema_kds FROM restaurantes WHERE id = ?", (restaurante_id,))
    resultado_tema = cursor.fetchone()
    tema_kds = resultado_tema[0] if resultado_tema and resultado_tema[0] else 'dark'

    # O Caixa vê tudo que é "pendente" e tudo que já está "pronto" na cozinha
    cursor.execute("SELECT * FROM pedidos WHERE restaurante_id = ? AND (status LIKE 'pendente%' OR status LIKE 'pronto%') ORDER BY id ASC", (restaurante_id,))
    
    pedidos_caixa = cursor.fetchall()
    conexao.close()

    return render_template("caixa.html", pedidos=pedidos_caixa, restaurante_id=restaurante_id, tema_kds=tema_kds)


@operacao_bp.route("/pagar/<int:id_pedido>", methods=["GET", "POST"])
def confirmar_pagamento(id_pedido):
    restaurante_id = request.form.get("restaurante_id")
    
    if not restaurante_id:
        print("🚨 Erro: O HTML não mandou o ID!")
        return redirect(url_for('operacao.painel_caixa'))

    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()
    
    cursor.execute("SELECT status FROM pedidos WHERE id = ? AND restaurante_id = ?", (id_pedido, restaurante_id))
    resultado = cursor.fetchone()

    if resultado:
        status_atual = resultado[0]

        # MÁGICA 4: A Dupla Validação do Caixa
        if status_atual.startswith("pendente"):
            # O cliente pagou rápido, mas a comida ainda tá no fogo. Avisa a cozinha!
            novo_status = status_atual.replace("pendente", "pago")
        elif status_atual.startswith("pronto"):
            # A comida já tava pronta lá trás, e agora o pagamento saiu. Missão cumprida!
            novo_status = "finalizado"
        else:
            novo_status = status_atual 
            
        cursor.execute("UPDATE pedidos SET status = ? WHERE id = ? AND restaurante_id = ?", (novo_status, id_pedido, restaurante_id))
        conexao.commit()
        
    conexao.close()
    
    print(f"✅ SUCESSO! Pagamento do Pedido {id_pedido} processado!")
    return redirect(url_for('operacao.painel_caixa'))