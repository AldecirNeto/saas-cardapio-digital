import sqlite3

def atualizar_banco_v2():
    conexao = sqlite3.connect("Autoatendimento.db")
    cursor = conexao.cursor()

    print("🚀 Iniciando Arquitetura Avançada de Adicionais...")

    # 1. Apaga as tabelas antigas para recriar com a nova lógica
    cursor.execute('DROP TABLE IF EXISTS variacoes')
    cursor.execute('DROP TABLE IF EXISTS complementos')
    cursor.execute('DROP TABLE IF EXISTS opcoes_ocultas')

    # 2. Nova Tabela de Variações (Pode pertencer a um Produto OU a uma Categoria)
    cursor.execute('''
        CREATE TABLE variacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER DEFAULT NULL,
            categoria_alvo TEXT DEFAULT NULL,
            nome TEXT NOT NULL,
            preco_adicional REAL DEFAULT 0,
            FOREIGN KEY (produto_id) REFERENCES cardapio(id) ON DELETE CASCADE
        )
    ''')

    # 3. Nova Tabela de Complementos (Produto OU Categoria)
    cursor.execute('''
        CREATE TABLE complementos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER DEFAULT NULL,
            categoria_alvo TEXT DEFAULT NULL,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES cardapio(id) ON DELETE CASCADE
        )
    ''')

    # 4. A "Lista Negra" (O que o lanche rejeitou da categoria)
    cursor.execute('''
        CREATE TABLE opcoes_ocultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo_opcao TEXT NOT NULL, -- Vai salvar se é 'variacao' ou 'complemento'
            opcao_id INTEGER NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES cardapio(id) ON DELETE CASCADE
        )
    ''')

    conexao.commit()
    conexao.close()
    print("✅ Banco de dados atualizado com a Arquitetura de Herança!")

if __name__ == "__main__":
    atualizar_banco_v2()