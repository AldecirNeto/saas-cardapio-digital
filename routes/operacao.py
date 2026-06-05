from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_conexao
from psycopg2.extras import RealDictCursor
#from auth import login_required # Garanta que você tem o decorator ou use a trava manual

# Criando o Blueprint da Operação (KDS e PDV)
operacao_bp = Blueprint('operacao', __name__)

@operacao_bp.route("/cozinha")
def painel_cozinha():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT tema_kds FROM restaurantes WHERE id = %s", (restaurante_id,))
        resultado_tema = cursor.fetchone()
        tema_kds = resultado_tema['tema_kds'] if resultado_tema and resultado_tema['tema_kds'] else 'dark'

        # CORREÇÃO AQUI: Passamos os padrões de busca nas variáveis
        busca_pendente = 'pendente%'
        busca_pago = 'pago%'

        cursor.execute("""
            SELECT * FROM pedidos 
            WHERE restaurante_id = %s 
            AND (status LIKE %s OR status LIKE %s) 
            ORDER BY id ASC
        """, (restaurante_id, busca_pendente, busca_pago))

        pedidos_pendentes = [dict(p) for p in cursor.fetchall()]
        
        return render_template("cozinha.html", pedidos=pedidos_pendentes, tema_kds=tema_kds)
    
    finally:
        cursor.close()
        conexao.close()


@operacao_bp.route("/pronto/<int:id_pedido>", methods=["POST"])
def marcar_pronto(id_pedido):
    if 'usuario_id' not in session: 
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    conexao.autocommit = True
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT status FROM pedidos WHERE id = %s AND restaurante_id = %s", (id_pedido, restaurante_id))
        resultado = cursor.fetchone()

        if resultado:
            status_atual = resultado['status']
            novo_status = status_atual

            # Lógica de Dupla Validação
            if status_atual.startswith("pendente"):
                novo_status = status_atual.replace("pendente", "pronto")
            elif status_atual.startswith("pago"):
                novo_status = "finalizado"

            cursor.execute("UPDATE pedidos SET status = %s WHERE id = %s AND restaurante_id = %s", 
                           (novo_status, id_pedido, restaurante_id))
            
        return redirect(url_for('operacao.painel_cozinha'))
    
    finally:
        cursor.close()
        conexao.close()


@operacao_bp.route("/caixa")
def painel_caixa():
    if 'usuario_id' not in session:
        return redirect(url_for('auth.login'))
    
    restaurante_id = session['restaurante_id']
    conexao = get_conexao()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT tema_kds FROM restaurantes WHERE id = %s", (restaurante_id,))
        resultado_tema = cursor.fetchone()
        tema_kds = resultado_tema['tema_kds'] if resultado_tema and resultado_tema['tema_kds'] else 'dark'

        # CORREÇÃO AQUI: Passamos os padrões de busca nas variáveis
        busca_pendente = 'pendente%'
        busca_pronto = 'pronto%'

        cursor.execute("""
            SELECT * FROM pedidos 
            WHERE restaurante_id = %s 
            AND (status LIKE %s OR status LIKE %s) 
            ORDER BY id ASC
        """, (restaurante_id, busca_pendente, busca_pronto))
        
        pedidos_caixa = [dict(p) for p in cursor.fetchall()]
        return render_template("caixa.html", pedidos=pedidos_caixa, restaurante_id=restaurante_id, tema_kds=tema_kds)
    
    finally:
        cursor.close()
        conexao.close()


@operacao_bp.route("/pagar/<int:id_pedido>", methods=["POST"])
def confirmar_pagamento(id_pedido):
    restaurante_id = session.get('restaurante_id')
    
    conexao = get_conexao()
    conexao.autocommit = True
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT status FROM pedidos WHERE id = %s AND restaurante_id = %s", (id_pedido, restaurante_id))
        resultado = cursor.fetchone()

        if resultado:
            status_atual = resultado['status']
            novo_status = status_atual

            if status_atual.startswith("pendente"):
                novo_status = status_atual.replace("pendente", "pago")
            elif status_atual.startswith("pronto"):
                novo_status = "finalizado"
                
            cursor.execute("UPDATE pedidos SET status = %s WHERE id = %s AND restaurante_id = %s", 
                           (novo_status, id_pedido, restaurante_id))
            
        print(f"✅ SUCESSO! Pagamento do Pedido {id_pedido} processado!")
        return redirect(url_for('operacao.painel_caixa'))
    
    finally:
        cursor.close()
        conexao.close()