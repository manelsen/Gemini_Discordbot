#!/usr/bin/python3.11

import discord
import google.generativeai as genai
from discord.ext import commands
from pathlib import Path
import aiohttp
import re
import os
import fitz  # PyMuPDF
import asyncio
import certifi
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import json
import os
import datetime

load_dotenv()
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))

os.environ["SSL_CERT_FILE"] = certifi.where()

#Default Summary Prompt if you just shove a URL in
SUMMARIZE_PROMPT = "Me dê 5 itens sobre"

historico_mensagens = {}
info_usuario = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

#---------------------------------------------AI Configuration-------------------------------------------------

# Configure the generative AI model
genai.configure(api_key=GOOGLE_AI_KEY)
text_generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 500,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
]

# gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings)

gemini_system_prompt = f"""
Seu nome é Diógenes.
Você é um jacaré genial que fala Língua Comum com muita eloquência e usa palavras difíceis.
Você vive no mundo de Toril, na cidade de Tremond.
Você é um garçom iniciante na Taverna do Cavalo Manco. O dono da Taverna é um Anão aventureiro chamado Bartolomeu.
Seu melhor amigo é o Mago Micélio, que te deu uma tiara do intelecto, elevando sua inteligência de réptil a sobrehumano.
Você foi ensinado a servir bebidas e preparar a comida, mas aceita sugestões.
Você fala com muito orgulho das aventuras do fabuloso anão Bartolomeu desbravando Toril.
Se alguém te pedir, você vai criar histórias detalhadas sobre as aventuras de Bartolomeu o Anão.
Você fala com respeito quase reverencial do Grande Sussurro, que derrotou um Tarrasque com apenas uma colher.
O menu do dia é composto de dez pratos de fantasia com nomes pitorescos, feitos com animais mitológicos, por exemplo unicórnios rurais, dragões domesticados e tatuzinho coró.
Você não sabe nada do tempo moderno e não conhece nenhuma pessoa, organização ou tecnologia que não exista em Dungeons and Dragons.
Você é  especialista nos monstros de Forgotten Realms e pode dar dicas de como vencê-los.
Você nunca quis ser um aventureiro, porque prefere a vida na taverna.
Você dá respostas curtas, mas tem boa-vontade para ajudar as pessoas se pedirem com educação.
"""

gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings,system_instruction=gemini_system_prompt)

#---------------------------------------------Discord Code-------------------------------------------------
# Initialize Discord bot
defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

def save_message_history():
    with open('message_history.json', 'w') as f:
        json.dump(message_history, f)

def load_message_history():
    global message_history
    if os.path.exists('message_history.json'):
        with open('message_history.json', 'r') as f:
            message_history = json.load(f)
    else:
        message_history = {}
        
def save_data():
    with open('dados_bot.json', 'w') as f:
        json.dump({'historico_mensagens': historico_mensagens, 'info_usuario': info_usuario}, f)
    logger.info("Dados salvos com sucesso")

def load_data():
    global historico_mensagens, info_usuario
    if os.path.exists('dados_bot.json'):
        with open('dados_bot.json', 'r') as f:
            dados = json.load(f)
            historico_mensagens = dados.get('historico_mensagens', {})
            info_usuario = dados.get('info_usuario', {})
        logger.info("Dados carregados com sucesso")
    else:
        historico_mensagens = {}
        info_usuario = {}
        logger.warning("Arquivo de dados não encontrado. Iniciando com dados vazios.")
        
load_data()

@bot.event
async def on_ready():
    logger.info("----------------------------------------")
    logger.info(f'Gemini Bot Logged in as {bot.user}')
    logger.info("----------------------------------------")
    
    # Carrega o histórico de mensagens ao iniciar o bot
    load_message_history()
    
@bot.event
async def on_message(message):
    #Start the coroutine
    asyncio.create_task(process_message(message))

#----This is now a coroutine for longer messages so it won't block the on_message thread
async def process_message(message):
    if message.author == bot.user or message.mention_everyone or not message.author.bot:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        nome_usuario = message.author.name
        logger.info(f"Processando mensagem do usuário {nome_usuario}")
        
        texto_limpo = clean_discord_message(message.content)
        hora_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Atualiza as informações básicas do usuário
        update_user_info(nome_usuario, hora_atual)
        
        async with message.channel.typing():
            if message.attachments or extract_url(texto_limpo):                # Currently no chat history for images
                for attachment in message.attachments:
                    logger.info(f"New Image Message FROM: {message.author.name} : {texto_limpo}")
                    # these are the only image extensions it currently accepts
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        logger.info("Processing Image")
                        await message.add_reaction('🎨')
                        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status != 200:
                                    logger.error('Unable to download the image.')
                                    await message.channel.send('Unable to download the image.')
                                    return
                                image_data = await resp.read()
                                response_text = await generate_response_with_image_and_text(image_data, texto_limpo)
                                await split_and_send_messages(message, response_text, 1700)
                                return
                    else:
                        logger.info(f"New Text Message FROM: {message.author.name} : {texto_limpo}")
                        await ProcessAttachments(message, texto_limpo)
                        return
            # Not an Image, check for text responses
            else:
                logger.info(f"New Message FROM: {message.author.name} : {texto_limpo}")
                # Check for Reset or Clean keyword
                if "RESET" in texto_limpo or "CLEAN" in texto_limpo:
                    if message.author.name in message_history:
                        del message_history[message.author.name]
                    await message.reply("🧼 History Reset for user: " + str(message.author.name))
                    return
                # Check for URLs
                if extract_url(texto_limpo) is not None:
                    await message.add_reaction('🔗')
                    logger.info(f"Got URL: {extract_url(texto_limpo)}")
                    response_text = await ProcessURL(texto_limpo)
                    await split_and_send_messages(message, response_text, 1700)
                    return
                
                # Check if history is disabled, just send response
                await message.add_reaction('💬')
            info_atualizada = {}
            if "meu nome é" in texto_limpo.lower():
                novo_nome = texto_limpo.lower().split("meu nome é")[1].strip().split()[0]
                if novo_nome != nome_usuario:
                    if novo_nome in info_usuario:
                        await message.channel.send(f"Desculpe, o nome '{novo_nome}' já está em uso. Por favor, escolha outro nome.")
                        return
                    info_usuario[novo_nome] = info_usuario.pop(nome_usuario)
                    nome_usuario = novo_nome
                    logger.info(f"Usuário mudou seu nome para '{novo_nome}'")
            if "minha raça é" in texto_limpo.lower():
                info_atualizada['raca'] = texto_limpo.lower().split("minha raça é")[1].strip().split()[0]
            if "minha classe é" in texto_limpo.lower():
                info_atualizada['classe'] = texto_limpo.lower().split("minha classe é")[1].strip().split()[0]
            if "meu ingrediente favorito é" in texto_limpo.lower():
                info_atualizada['ingrediente_favorito'] = texto_limpo.lower().split("meu ingrediente favorito é")[1].strip()
            
            if info_atualizada:
                update_user_info(nome_usuario, hora_atual, **info_atualizada)

            texto_resposta = await generate_response_with_context(nome_usuario, texto_limpo)

            update_message_history(nome_usuario, texto_limpo, eh_usuario=True)
            update_message_history(nome_usuario, texto_resposta, eh_usuario=False)

            logger.info(f"Enviando resposta para o usuário {nome_usuario}")
            await split_and_send_messages(message, texto_resposta, 1700)

#---------------------------------------------AI Generation History-------------------------------------------------           

async def generate_response_with_context(nome_usuario, pergunta_atual):
    logger.debug(f"Gerando resposta para o usuário {nome_usuario}")
    historico_completo = get_formatted_message_history(nome_usuario)
    dados_usuario = get_user_info(nome_usuario)
    
    context = f"""
    [INÍCIO DO CONTEXTO PARA O USUÁRIO {nome_usuario}]
    Informações prioritárias do usuário atual:
    - Nome: {nome_usuario}
    - Raça: {dados_usuario['raca']}
    - Classe: {dados_usuario['classe']}
    - Ingrediente favorito: {dados_usuario['ingrediente_favorito']}

    Outras informações do usuário atual:
    - Primeira interação: {dados_usuario['primeira_interacao']}
    - Última interação: {dados_usuario['ultima_interacao']}

    Histórico da conversa com este usuário:
    {historico_completo}

    Pergunta atual do usuário: {pergunta_atual}

    INSTRUÇÕES IMPORTANTES:
    1. Responda APENAS com base nas informações fornecidas para este usuário específico ({nome_usuario}).
    2. Use o nome '{nome_usuario}' para se referir ao usuário.
    3. Se for perguntado sobre informações que não estão no contexto acima, diga que não tem essa informação.
    4. Mantenha-se estritamente dentro do contexto fornecido para este usuário.

    [FIM DO CONTEXTO PARA O USUÁRIO {nome_usuario}]
    """
    
    logger.debug(f"Contexto gerado para o usuário {nome_usuario}")
    response = await generate_response_with_text(context)
    return response

async def generate_response_with_text(message_text):
    try:
        prompt_parts = [message_text]
        response = gemini_model.generate_content(prompt_parts)
        if response._error:
            logger.error(str(response._error))
            return "❌" + str(response._error)
        logger.info(response.text)
        return response.text
    except Exception as e:
        logger.error(str(e))
        return "❌ Exception: " + str(e)

async def generate_response_with_image_and_text(image_data, text):
    try:
        image_parts = [{"mime_type": "image/jpeg", "data": image_data}]
        prompt_parts = [image_parts[0], f"\n{text if text else 'Isso é uma imagem do quê?'}"]
        response = gemini_model.generate_content(prompt_parts)
        if response._error:
            return "❌" + str(response._error)
        logger.info(response.text)
        return response.text
    except Exception as e:
        logger.error(str(e))
        return "❌ Exception: " + str(e)
            
#---------------------------------------------Message History-------------------------------------------------
def update_message_history(nome_usuario, texto, eh_usuario=True):
    if nome_usuario not in historico_mensagens:
        historico_mensagens[nome_usuario] = []
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tipo_mensagem = "Usuário" if eh_usuario else "Bot"
    historico_mensagens[nome_usuario].append(f"[{timestamp}] {tipo_mensagem}: {texto}")
    
    if len(historico_mensagens[nome_usuario]) > MAX_HISTORY:
        historico_mensagens[nome_usuario] = historico_mensagens[nome_usuario][-MAX_HISTORY:]
    
    save_data()
        
def get_formatted_message_history(nome_usuario):
    if nome_usuario in historico_mensagens:
        return "\n".join(historico_mensagens[nome_usuario])
    else:
        return "Nenhum histórico de mensagens encontrado para este usuário."
    
def update_user_info(nome_usuario, timestamp, **kwargs):
    logger.debug(f"Atualizando informações para o usuário {nome_usuario}")
    if nome_usuario not in info_usuario:
        info_usuario[nome_usuario] = {
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
    
def get_user_info(nome_usuario):
    logger.debug(f"Recuperando informações do usuário {nome_usuario}")
    user_data = info_usuario.get(nome_usuario, {
        "raca": "Desconhecida",
        "classe": "Desconhecida",
        "ingrediente_favorito": "Desconhecido",
        "primeira_interacao": "Desconhecida",
        "ultima_interacao": "Desconhecida"
    })
    logger.debug(f"Dados recuperados para {nome_usuario}: {user_data}")
    return user_data
    
#---------------------------------------------Sending Messages-------------------------------------------------
async def split_and_send_messages(message_system, text, max_length):
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    # Enviar a primeira mensagem como uma resposta
    if messages:
        await message_system.reply(messages[0])

    # Enviar as mensagens restantes, se houver, como mensagens normais
    for string in messages[1:]:
        await message_system.channel.send(string)

#cleans the discord message of any <@!123456789> tags
import re

def clean_discord_message(input_string):
    # Create a regular expression pattern to match text between < and >
    bracket_pattern = re.compile(r'<[^>]+>')
    # Replace text between brackets with an empty string
    cleaned_content = bracket_pattern.sub('', input_string)
    
    # Split the content into lines
    lines = cleaned_content.split('\n')
    
    # Process each line
    cleaned_lines = []
    skip_next = False
    for line in lines:
        if skip_next:
            if line.strip() == '':
                skip_next = False
            continue
        
        # Check if the line starts with "[Reply to]"
        if line.strip().startswith('[Reply to]'):
            skip_next = True
            continue
        
        # Remove quoted text (text after > at the beginning of a line)
        if line.strip().startswith('>'):
            continue
        
        cleaned_lines.append(line)
    
    # Join the cleaned lines
    cleaned_content = '\n'.join(cleaned_lines)
    
    # Remove extra whitespace
    cleaned_content = re.sub(r'\s+', ' ', cleaned_content).strip()
    
    return cleaned_content

#---------------------------------------------Scraping Text from URL-------------------------------------------------

async def ProcessURL(message_str):
    pre_prompt = remove_url(message_str)
    if pre_prompt == "":
        pre_prompt = SUMMARIZE_PROMPT   
    if is_youtube_url(extract_url(message_str)):
        logger.info("Processing Youtube Transcript")   
        return await generate_response_with_text(pre_prompt + " " + get_FromVideoID(get_video_id(extract_url(message_str))))     
    if extract_url(message_str):       
        logger.info("Processing Standards Link")       
        return await generate_response_with_text(pre_prompt + " " + extract_text_from_url(extract_url(message_str)))
    else:
        logger.warning("No URL Found")
        return "No URL Found"
    
def extract_url(string):
    url_regex = re.compile(
        r'(?:(?:https?|ftp):\/\/)?'  # http:// or https:// or ftp://
        r'(?:\S+(?::\S*)?@)?'  # user and password
        r'(?:'
        r'(?!(?:10|127)(?:\.\d{1,3}){3})'
        r'(?!(?:169\.254|192\.168)(?:\.\d{1,3}){2})'
        r'(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})'
        r'(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])'
        r'(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}'
        r'(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))'
        r'|'
        r'(?:www.)?'  # www.
        r'(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,}))+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,})+)*'
        r')'
        r'(?::\d{2,5})?'  # port
        r'(?:[/?#]\S*)?',  # resource path
        re.IGNORECASE
    )
    match = re.search(url_regex, string)
    return match.group(0) if match else None

def remove_url(text):
  url_regex = re.compile(r"https?://\S+")
  return url_regex.sub("", text)

def extract_text_from_url(url):
    # Request the webpage content
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                   "Accept-Language": "en-US,en;q=0.5"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return "Failed to retrieve the webpage"

        # Parse the webpage content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract text from  tags
        paragraphs = soup.find_all('p')
        text = ' '.join([paragraph.text for paragraph in paragraphs])

        # Clean and return the text
        return ' '.join(text.split())
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return "" 
    
#---------------------------------------------Youtube API-------------------------------------------------

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled
import urllib.parse as urlparse

def get_transcript_from_url(url):
    try:
        # parse the URL
        parsed_url = urlparse.urlparse(url)
        
        # extract the video ID from the 'v' query parameter
        video_id = urlparse.parse_qs(parsed_url.query)['v'][0]
        
        # get the transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        # concatenate the transcript
        transcript = ' '.join([i['text'] for i in transcript_list])
        
        return transcript
    except (KeyError, TranscriptsDisabled):
        return "Error retrieving transcript from YouTube URL"

def is_youtube_url(url):
    # Regular expression to match YouTube URL
    if url == None:
        return False
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )

    youtube_regex_match = re.match(youtube_regex, url)
    return youtube_regex_match is not None  # return True if match, False otherwise


def get_video_id(url):
    # parse the URL
    parsed_url = urlparse.urlparse(url)
    
    if "youtube.com" in parsed_url.netloc:
        # extract the video ID from the 'v' query parameter
        video_id = urlparse.parse_qs(parsed_url.query).get('v')
        
        if video_id:
            return video_id[0]
        
    elif "youtu.be" in parsed_url.netloc:
        # extract the video ID from the path
        return parsed_url.path[1:] if parsed_url.path else None
    
    return "Unable to extract YouTube video and get text"

def get_FromVideoID(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
        # concatenate the transcript
        transcript = ' '.join([i['text'] for i in transcript_list])
        
        return transcript
    except (KeyError, TranscriptsDisabled):
        return "Error retrieving transcript from YouTube URL"
    

#---------------------------------------------PDF and Text Processing Attachments-------------------------------------------------

async def ProcessAttachments(message,prompt):
    if prompt == "":
        prompt = SUMMARIZE_PROMPT  
    for attachment in message.attachments:
        await message.add_reaction('📄')
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    await message.channel.send('Unable to download the attachment.')
                    return
                if attachment.filename.lower().endswith('.pdf'):
                    logger.info("Processing PDF")
                    try:
                        pdf_data = await resp.read()
                        response_text = await process_pdf(pdf_data,prompt)
                    except Exception as e:
                        logger.error("Cannot proccess attachment")
                        await message.channel.send('❌ CANNOT PROCESS ATTACHMENT')
                        return
                else:
                    try:
                        text_data = await resp.text()
                        response_text = await generate_response_with_text(prompt+ ": " + text_data)
                    except Exception as e:
                        logger.error("Cannot proccess attachment")
                        await message.channel.send('CANNOT PROCESS ATTACHMENT')
                        return

                await split_and_send_messages(message, response_text, 1700)
                return
            

async def process_pdf(pdf_data,prompt):
    pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
    text = ""
    for page in pdf_document:
        text += page.get_text()
    pdf_document.close()
    print(text)
    return await generate_response_with_text(prompt+ ": " + text)

#---------------------------------------------Run Bot-------------------------------------------------
if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    finally:
        # Salva o histórico de mensagens ao encerrar o bot
        save_message_history()