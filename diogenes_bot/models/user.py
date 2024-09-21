from datetime import datetime

info_usuario = {}

def update_user_info(nome_usuario, timestamp, **kwargs):
    if nome_usuario not in info_usuario:
        info_usuario[nome_usuario] = {
            "nome": nome_usuario,
            "primeira_interacao": timestamp,
            "ultima_interacao": timestamp,
            "raca": "Desconhecida",
            "classe": "Desconhecida",
            "ingrediente_favorito": "Desconhecido"
        }
    
    info_usuario[nome_usuario]["ultima_interacao"] = timestamp
    
    for chave, valor in kwargs.items():
        if chave in ["raca", "classe", "ingrediente_favorito"]:
            info_usuario[nome_usuario][chave] = valor

def get_user_info(nome_usuario):
    return info_usuario.get(nome_usuario, {
        "raca": "Desconhecida",
        "classe": "Desconhecida",
        "ingrediente_favorito": "Desconhecido",
        "primeira_interacao": "Desconhecida",
        "ultima_interacao": "Desconhecida"
    })