import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_conexao():
    try:
        # Pega a URL do .env ou das variáveis do sistema
        url = os.getenv("DATABASE_URL")
        
        if not url:
            # Se a variável sumiu de novo, vamos colocar um aviso claro
            raise Exception("A variável DATABASE_URL não foi encontrada!")

        # Tenta conectar
        conn = psycopg2.connect(url)
        return conn  # <--- ESSA LINHA É A MAIS IMPORTANTE!
        
    except Exception as e:
        print(f"🚨 ERRO AO CONECTAR NO BANCO: {e}")
        return None