import sqlite3
import logging
import json
import os
import datetime
from models.user import info_usuario
from models.conversation import historico_mensagens
import datetime

conn = None

raciocinio_mode = "cot"  # Padrão para Chain of Thoughts
logger = logging.getLogger("bot_logger")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))

def get_db_connection():
    global conn
    if conn is None:
        conn = sqlite3.connect('data/database.sqlite')
        conn.execute('''CREATE TABLE IF NOT EXISTS dados
                        (chave TEXT PRIMARY KEY, valor TEXT)''')
    return conn

def save_data():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    historico_json = json.dumps(historico_mensagens)
    info_usuario_json = json.dumps(info_usuario)
    
    cursor.execute("INSERT OR REPLACE INTO dados (chave, valor) VALUES (?, ?)",
                   ("historico_mensagens", historico_json))
    cursor.execute("INSERT OR REPLACE INTO dados (chave, valor) VALUES (?, ?)",
                   ("info_usuario", info_usuario_json))
    
    connection.commit()

def load_data():
    global historico_mensagens, info_usuario
    
    if not os.path.exists('data/database.sqlite'):
        historico_mensagens = {}
        info_usuario = {}
        return
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    for chave in ["historico_mensagens", "info_usuario"]:
        cursor.execute("SELECT valor FROM dados WHERE chave = ?", (chave,))
        resultado = cursor.fetchone()
        if resultado:
            globals()[chave] = json.loads(resultado[0])
        else:
            globals()[chave] = {}

def close_connection():
    global conn
    if conn:
        conn.close()
        conn = None
        
        # Função para atualizar informações do usuário
def update_user_info(nome_usuario, timestamp, **kwargs):
    logger.debug(f"Atualizando informações para o usuário {nome_usuario}")
    if nome_usuario not in info_usuario:
        info_usuario[nome_usuario] = {
            "nome": nome_usuario,
            "primeira_interacao": timestamp,
            "ultima_interacao": timestamp,
            "raca": "Desconhecida",
            "classe": "Desconhecida",
            "ingrediente_favorito": "Desconhecido"
        }
        logger.info(f"Novo usuário criado: {nome_usuario}")
    
    info_usuario[nome_usuario]["ultima_interacao"] = timestamp
    
    for chave, valor in kwargs.items():
        if chave in ["raca", "classe", "ingrediente_favorito"]:
            old_value = info_usuario[nome_usuario].get(chave, "Desconhecido")
            info_usuario[nome_usuario][chave] = valor
            logger.info(f"Usuário {nome_usuario}: {chave} atualizado de '{old_value}' para '{valor}'")
    
    save_data()
    
def update_message_history(nome_usuario, texto, eh_usuario=True):
    if nome_usuario not in historico_mensagens:
        historico_mensagens[nome_usuario] = []
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tipo_mensagem = "Usuário" if eh_usuario else "Bot"
    historico_mensagens[nome_usuario].append(f"[{timestamp}] {tipo_mensagem}: {texto}")
    
    if len(historico_mensagens[nome_usuario]) > MAX_HISTORY:
        historico_mensagens[nome_usuario] = historico_mensagens[nome_usuario][-MAX_HISTORY:]
    
    save_data()


# Outras funções de gerenciamento de dados...