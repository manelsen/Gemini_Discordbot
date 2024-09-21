from models.conversation import user_interaction_summary, user_interaction_history, historico_mensagens
from models.user import info_usuario, get_user_info
from ai.nlp_tools import calculate_tf_idf, preprocess_text
from ai.gemini_wrapper import generate_response_with_text
from collections import deque
import asyncio

channel_cache = deque(maxlen=1000)

async def generate_context(nome_usuario, texto_atual, sentiment):
    global sumario_global
    user_summary = user_interaction_summary.get(nome_usuario, "Sem histórico prévio.")
    recent_interactions = list(user_interaction_history.get(nome_usuario, []))[-5:]
    channel_summary = await generate_channel_summary()
    info_usuario = get_user_info(nome_usuario)
    
    context = f"""
    Contexto do Usuário:
    Nome: {nome_usuario}
    Sumário de Interações: {user_summary}
    
    Interações Recentes:
    {' '.join(recent_interactions)}
    
    Contexto do Canal:
    {channel_summary}
    
    Mensagem Atual: {texto_atual}
    Sentimento Detectado: {sentiment}
    
    Com base neste contexto, formule uma resposta adequada como Diógenes, o jacaré filósofo e cozinheiro.
    Lembre-se de evitar repetições, especialmente ao falar sobre o menu ou ao iniciar suas respostas.
    Se a mensagem contiver uma lista numerada de pratos, processe-a adequadamente e responda de acordo.
    Ao criar pratos para o menu, use a função generate_menu_item() para cada item.
    """
    return context

async def generate_channel_summary():
    full_text = " ".join([msg[0] for msg in channel_cache])
    preprocessed_docs = [preprocess_text(msg[0]) for msg in channel_cache]
    tf_idf = calculate_tf_idf(preprocessed_docs)
    
    top_words = sorted(tf_idf.items(), key=lambda x: x[1], reverse=True)[:20]
    summary = f"Principais tópicos discutidos: {', '.join([word for word, _ in top_words])}"
    
    return summary

async def generate_global_summary():
    global sumario_global
    
    async def process_user(nome, dados):
        user_summary = f"Usuário: {nome}\n"
        user_summary += f"Raça: {dados['raca']}, Classe: {dados['classe']}, Favorito: {dados['ingrediente_favorito']}\n"
        
        if nome in historico_mensagens:
            ultimas_mensagens = historico_mensagens[nome][-15:]
            user_summary += "Últimas interações:\n"
            user_summary += "\n".join(f"- {msg}" for msg in ultimas_mensagens)
        
        return user_summary

    user_summaries = await asyncio.gather(
        *(process_user(nome, dados) for nome, dados in info_usuario.items())
    )
    
    raw_summary = "Resumo de todas as conversas e preferências dos usuários:\n\n"
    raw_summary += "\n\n".join(user_summaries)

    prompt = f"""
    Crie um resumo objetivo do seguinte sumário de conversas:
    {raw_summary}
    
    Esse resumo deve incluir nome, raça, classe, ingrediente favorito e informações relevantes sobre cada usuário, sem exceção de nenhum. Nenhum timestamp deverá aparecer nesse resumo. Organize por bullets.
   
    O padrão a seguir é:
   
    *Usuário*:
    * Raça:
    * Classe:
    * Cinco pessoas com quem mais interage:
    * Ingrediente Favorito:
    * Lista de Interações:
    ** interação importante resumida 1
    ** interação importante resumida 2
    ** interação importante resumida 3
    ** etc
    """

    sumario_global = await generate_response_with_text(prompt)
    return sumario_global