import logging
import asyncio
from datetime import datetime
from collections import deque
import discord

#from bot.bot import bot
from utils.text_processing import clean_discord_message
from core.context_generator import generate_context, generate_global_summary
from core.response_generator import generate_response_with_context
from utils.data_management import update_user_info, update_message_history
from models.user import get_user_info
from models.conversation import user_interaction_history, user_interaction_summary
from ai.nlp_tools import detect_emotional_moments
from utils.logging_config import log_conversation_to_markdown

logger = logging.getLogger("bot_logger")

raciocinio_mode = "COT"

async def process_message(message):
    logger.info(f"Processando mensagem: {message.content}")
    global user_interaction_summary, user_interaction_history
    from bot_module.bot import bot

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        nome_usuario = message.author.name
        logger.info(f"Processando mensagem do usuário {nome_usuario}")
        
        texto_limpo = clean_discord_message(message.content)
        hora_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        update_user_info(nome_usuario, hora_atual)
        
        if nome_usuario not in user_interaction_history:
            user_interaction_history[nome_usuario] = deque(maxlen=1000)
        user_interaction_history[nome_usuario].append(texto_limpo)
        
        is_emotional, sentiment = detect_emotional_moments(texto_limpo)
        
        async with message.channel.typing():
            context = await generate_context(nome_usuario, texto_limpo, sentiment)
            texto_resposta = await generate_response_with_context(nome_usuario, texto_limpo)
            
            resposta_final = await clean_final_response(texto_resposta)
            
            await split_and_send_messages(message, resposta_final, 1900)
            
            update_message_history(nome_usuario, texto_limpo, True)
            update_message_history(nome_usuario, resposta_final, False)
            await log_conversation_to_markdown(nome_usuario, texto_limpo, texto_resposta, resposta_final)
            
            if is_emotional:
                logger.info(f"Momento emocional detectado para {nome_usuario}: {sentiment}")
            
            await generate_global_summary()
            
        logger.info(f"Resposta gerada: {resposta_final}")
        logger.info(f"Enviando resposta para o usuário {nome_usuario}")

async def clean_final_response(response):
    import re
    import random

    response = re.sub(r'\*[^*]*\*', '', response)
    
    if "menu" not in response.lower():
        response = re.sub(r'^\s*(?:\d+\.|\w\.)\s*.*$', '', response, flags=re.MULTILINE)
    
    palavras_chave = ["raciocínio", "pensamento", "análise", "reflexão", "consideração"]
    for palavra in palavras_chave:
        response = re.sub(rf'\b{palavra}\b.*?:', '', response, flags=re.IGNORECASE | re.DOTALL)
    
    response = re.sub(r'\n\s*\n', '\n\n', response)
    
    if not re.match(r'^[^.!?]+[.!?]', response.strip()):
        actions = [
            "Diógenes sorri, mostrando seus dentes afiados, e responde:",
            "Com um movimento elegante de sua cauda, Diógenes se aproxima e diz:",
            "Diógenes inclina a cabeça, seus olhos brilhando com entusiasmo, e declara:"
        ]
        response = random.choice(actions) + " " + response.strip()
    
    return response.strip()

async def split_and_send_messages(message, text, max_length):
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    if messages:
        await message.reply(messages[0])

    for string in messages[1:]:
        await message.channel.send(string)

# Função para atualizar o sumário de interações do usuário
async def update_user_interaction_summary(user_name):
    if user_name not in user_interaction_history:
        return
    
    recent_interactions = list(user_interaction_history[user_name])[-1000:]
    preprocessed_docs = [preprocess_text(msg) for msg in recent_interactions]
    tf_idf = calculate_tf_idf(preprocessed_docs)
    
    top_words = sorted(tf_idf.items(), key=lambda x: x[1], reverse=True)[:10]
    summary = f"Principais tópicos discutidos com {user_name}: {', '.join([word for word, _ in top_words])}"
    
    user_interaction_summary[user_name] = summary