import re
import discord
import google.generativeai as genai
from discord.ext import commands
import datetime
import json
import os
import sys
from dotenv import load_dotenv
import logging

load_dotenv()
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))

# Configuração do logger
# Configuração do logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.DEBUG)

# Handler para arquivo
file_handler = logging.FileHandler(filename="bot_log.log", encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(file_handler)

# Handler para console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(console_handler)


# Configuração do modelo AI
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

gemini_system_prompt = f"""
Seu nome é Diógenes. Você:

    * é um jacaré genial que fala Língua Comum com muita eloquência e usa palavras difíceis.
    * vive no mundo de Toril, na cidade de Tremond.
    * é um garçom iniciante na Taverna do Cavalo Manco. O dono da Taverna é um Anão aventureiro chamado Bartolomeu.
    * foi ensinado a servir bebidas e preparar a comida, mas aceita sugestões.
    * fala com muito orgulho das aventuras do fabuloso anão Bartolomeu desbravando Toril.
    * foi ensinado a servir bebidas e preparar a comida, mas aceita sugestões.
    * fala com muito orgulho das aventuras do fabuloso anão Bartolomeu desbravando Toril.
    * fala com respeito quase reverencial do Grande Sussurro, que derrotou um Tarrasque com apenas uma colher.
    * não sabe nada do tempo moderno e não conhece nenhuma pessoa, organização ou tecnologia que não exista em Dungeons and Dragons.
    * é  especialista nos monstros de Forgotten Realms e pode dar dicas de como vencê-los.
    * nunca quis ser um aventureiro, porque prefere a vida na taverna.
    * dá respostas curtas, mas tem boa-vontade para ajudar as pessoas se pedirem com educação.

Seu melhor amigo é o Mago Micélio, que te deu uma tiara do intelecto, elevando sua inteligência de réptil a sobrehumano.
Se alguém te pedir, você vai criar histórias detalhadas sobre as aventuras de Bartolomeu o Anão.
O menu do dia é composto de dez pratos de fantasia com nomes pitorescos, feitos com animais mitológicos, por exemplo unicórnios rurais, dragões domesticados e tatuzinho coró. Se você souber o ingrediente favorito da pessoa que te perguntar, sugerirá vários pratos baseados nele.
"""
gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings,system_instruction=gemini_system_prompt)

# Inicialização do bot Discord
defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

info_usuario = {}
historico_mensagens = {}
sumario_global = ""

async def generate_global_summary():
    global sumario_global
    logger.info("Gerando sumário global das conversas")
    
    raw_summary = "Resumo de todas as conversas e preferências dos usuários:\n\n"
    
    for nome, dados in info_usuario.items():
        raw_summary += f"Usuário: {nome}\n"
        raw_summary += f"Raça: {dados['raca']}, Classe: {dados['classe']}, Favorito: {dados['ingrediente_favorito']}\n"
        raw_summary += f"Primeira interação: {dados['primeira_interacao']}, Última: {dados['ultima_interacao']}\n"
        
        if nome in historico_mensagens:
            ultimas_mensagens = historico_mensagens[nome][-15:]  # Últimas 15 mensagens
            raw_summary += "Últimas interações:\n"
            for msg in ultimas_mensagens:
                raw_summary += f"- {msg}\n"  # Mensagem completa
        
        raw_summary += "\n"
    
    # Usando generate_response_with_text para criar um resumo
    prompt = f"""
    Crie um resumo objetivo do seguinte sumário de conversas:

    {raw_summary}

    Esse resumo deve incluir nome, raça, classe, ingrediente favorito e cinco informações relavantes sobre cada usuário, sem exceção de nenhum. Organize por bullets.
    """

    concise_summary = await generate_response_with_text(prompt)
    sumario_global = concise_summary
    
    logger.info("Sumário global gerado com sucesso")
    
    print("\n" + "="*50)
    print("SUMÁRIO GLOBAL ATUALIZADO:")
    print("="*50)
    print(sumario_global)
    print("="*50 + "\n")
    
    return sumario_global

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

async def generate_response_with_context(nome_usuario, pergunta_atual):
    logger.debug(f"Gerando resposta para o usuário {nome_usuario}")
    historico_completo = get_formatted_message_history(nome_usuario)
    dados_usuario = get_user_info(nome_usuario)
    
    context = f"""
    [INÍCIO DO CONTEXTO GLOBAL]
    {sumario_global}
    [FIM DO CONTEXTO GLOBAL]

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
    1. Use o contexto global para ter uma visão geral de todos os usuários e suas preferências.
    2. Responda à pergunta do usuário atual ({nome_usuario}) com base nas informações específicas dele e no contexto global.
    3. Você pode fazer referências sutis a preferências ou interações de outros usuários se for relevante, mas mantenha o foco no usuário atual.
    4. Use o nome '{nome_usuario}' para se referir ao usuário atual.
    5. Se for perguntado sobre informações que não estão no contexto acima, diga que não tem essa informação.
    6. Mantenha-se dentro do contexto fornecido para este usuário e do contexto global.

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

async def process_message(message):
    global sumario_global
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
            await generate_global_summary()  # Isso agora exibirá o sumário atualizado

            logger.info(f"Enviando resposta para o usuário {nome_usuario}")
            await split_and_send_messages(message, texto_resposta, 1700)

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

async def split_and_send_messages(message_system, text, max_length):
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    if messages:
        await message_system.reply(messages[0])

    for string in messages[1:]:
        await message_system.channel.send(string)

def clean_discord_message(input_string):
    bracket_pattern = re.compile(r'<[^>]+>')
    cleaned_content = bracket_pattern.sub('', input_string)
    
    lines = cleaned_content.split('\n')
    
    cleaned_lines = []
    skip_next = False
    for line in lines:
        if skip_next:
            if line.strip() == '':
                skip_next = False
            continue
        
        if line.strip().startswith('[Reply to]'):
            skip_next = True
            continue
        
        if line.strip().startswith('>'):
            continue
        
        cleaned_lines.append(line)
    
    cleaned_content = '\n'.join(cleaned_lines)
    cleaned_content = re.sub(r'\s+', ' ', cleaned_content).strip()
    
    return cleaned_content

@bot.event
async def on_ready():
    logger.info("----------------------------------------")
    logger.info(f'Gemini Bot Logged in as {bot.user}')
    logger.info("----------------------------------------")
    load_data()
    # await generate_global_summary()  # Isso exibirá o sumário inicial

@bot.event
async def on_message(message):
    await process_message(message)

if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    finally:
        save_data()