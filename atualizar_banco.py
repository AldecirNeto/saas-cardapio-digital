# salve como teste_db.py e rode: python teste_db.py
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
url = os.getenv("DATABASE_URL")
print(f"Tentando conectar em: {url}")

try:
    conn = psycopg2.connect(url)
    print("✅ CONEXÃO REAL COM SUPABASE ESTABELECIDA!")
    conn.close()
except Exception as e:
    print(f"❌ ERRO: {e}")