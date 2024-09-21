from collections import deque

historico_mensagens = {}
user_interaction_summary = {}
user_interaction_history = {}

def update_message_history(nome_usuario, texto, eh_usuario=True):
    if nome_usuario not in historico_mensagens:
        historico_mensagens[nome_usuario] = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tipo_mensagem = "Usuário" if eh_usuario else "Bot"
    historico_mensagens[nome_usuario].append(f"[{timestamp}] {tipo_mensagem}: {texto}")
    
    if len(historico_mensagens[nome_usuario]) > MAX_HISTORY:
        historico_mensagens[nome_usuario] = historico_mensagens[nome_usuario][-MAX_HISTORY:]

def get_formatted_message_history(nome_usuario):
    if nome_usuario in historico_mensagens:
        return "\n".join(historico_mensagens[nome_usuario])
    else:
        return "Nenhum histórico de mensagens encontrado para este usuário."