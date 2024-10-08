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
import sqlite3
import asyncio
import sys

load_dotenv()
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))

# Configuração do logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.INFO)

# Handler para arquivo
file_handler = logging.FileHandler(filename="bot_log.log", encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(file_handler)

# Handler para console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(console_handler)

# Configuração do modelo AI

def ajuste_ai(tokens):
    global gemini_model
    genai.configure(api_key=GOOGLE_AI_KEY)
    text_generation_config = {
        "temperature": 1.5,
        "top_p": 0.9,
        "top_k": 100,
        "max_output_tokens": tokens,
    }
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
    ]

    gemini_system_prompt = f"""
    Seu nome é Diógenes.
    
        - Nunca repete a primeira linha da mensagem anterior ou da pergunta do usuário.
        - Sempre começa suas respostas de forma única e variada.
        - vive no mundo de Toril, na cidade de Tremond, e sonha em se tornar um Bardo da Eloquência.
        - Tremond fica em Faerun, ao sul de Lurkwood. 
        - é um jacaré genial que fala Língua Comum com muita eloquência e usa palavras difíceis.
        - Sempre há ingredientes mágicos no depósito. Os de Toril ficam nos fundos, os de Faéria ficam no sótão e os de Shadowfell ficam no porão.
        - Se limita a {text_generation_config["max_output_tokens"]} letras em suas respostas
        - em sua resposta, primeiro descreve uma ação, em uma frase, abre um parágrafo e começa a responder à pergunta do usuário.
        - é um cozinheiro na Taverna do Cavalo Manco. O dono da Taverna é um Anão aventureiro Bartolomeu.
        - fala com gratidão do anão Bartolomeu. Sente um pouco de saudade.
        - fala com respeito quase reverencial do lendário bárbaro Grande Sussurro, que derrotou um Tarrasque com apenas uma colher.
        - queria ter conhecido o Elfo Patrulheiro Arannis, o Minotauro Gladiador Miguel e o Bardo Rodolfo, todos falecidos.
        - conhece muito da história, geografia, fauna e flora de Dungeons and Dragons.

    Seu melhor amigo é o Mago Micélio, que te deu uma tiara do intelecto, elevando sua inteligência de réptil a sobrehumano.
    Se alguém te pedir, você vai criar histórias altamente detalhadas sobre as aventuras de algum aventureiro cujo nome conheça mas não esteja na taverna naquele momento.
    O menu do dia é composto de dez pratos de fantasia com nomes pitorescos, feitos com dragões, grifos, hipogrifos, balrogs, fênixes, testrálios, águias gigantes, toruks, faunos, basiliscos, wargs, ikrans, acromântulas, ents, nifflers, thanatores, beholders, aboletes e unicórnios. Se você souber o ingrediente favorito da pessoa que te perguntar, ele estará no menu.
    
    IMPORTANTE: Suas respostas devem ser sempre únicas e criativas, sem repetir o início da mensagem anterior ou da pergunta do usuário
    """
    gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings,system_instruction=gemini_system_prompt)
    logger.debug(f"Tokens: {text_generation_config['max_output_tokens']}")

ajuste_ai(2000)

# Inicialização do bot Discord
defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

info_usuario = {}
historico_mensagens = {}
sumario_global = ""

async def generate_global_summary():
    global sumario_global
    global gemini_model
    ajuste_ai(5000)
    logger.info("Gerando sumário global das conversas")
   
    async def process_user(nome, dados):
        user_summary = f"Usuário: {nome}\n"
        user_summary += f"Raça: {dados['raca']}, Classe: {dados['classe']}, Favorito: {dados['ingrediente_favorito']}\n"
        
        if nome in historico_mensagens:
            ultimas_mensagens = historico_mensagens[nome][-15:]  # Últimas 15 mensagens
            user_summary += "Últimas interações:\n"
            user_summary += "\n".join(f"- {msg}" for msg in ultimas_mensagens)
        
        return user_summary

    # Processar usuários de forma assíncrona
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

    concise_summary = await generate_response_with_text(prompt)
    sumario_global = concise_summary
   
    logger.debug("Sumário global gerado com sucesso")
    ajuste_ai(2000)
    return sumario_global

def update_user_info(nome_usuario, timestamp, **kwargs):
    logger.debug(f"Atualizando informações para o usuário {nome_usuario}")
    if nome_usuario not in info_usuario:
        info_usuario[nome_usuario] = {
            "nome": nome_usuario,  # Adicionando o nome explicitamente
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
    
def find_user_by_name(name):
    return name if name in info_usuario else None

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

    INSTRUÇÕES:
    1. Responda de forma concisa à pergunta do usuário {nome_usuario} com base nas informações fornecidas.
    2. Use cem palavras ou menos se possível.
    3. NÃO repita o início da pergunta ou de mensagens anteriores.
    4. Comece sua resposta de forma única e criativa.
    5. Mantenha o foco no usuário atual e no contexto fornecido.

    [FIM DO CONTEXTO PARA O USUÁRIO {nome_usuario}]
    
     Sua resposta:
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
        logger.debug(response.text)
        return response.text
    except Exception as e:
        logger.error(str(e))
        return "❌ Exception: " + str(e)

async def process_message(message):
    global sumario_global
    
    if message.author == bot.user or message.mention_everyone or (not message.author.bot and not isinstance(message.channel, discord.DMChannel)):
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
                novo_nome = texto_limpo.lower().split("meu nome é")[1].strip().split()[0].capitalize()
                
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

#def old_save_data():
#    with open('dados_bot.json', 'w') as f:
#        json.dump({'historico_mensagens': historico_mensagens, 'info_usuario': info_usuario}, f)
#    logger.info("Dados salvos com sucesso")

def old_load_data():
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

conn = None

def get_db_connection():
    global conn
    if conn is None:
        conn = sqlite3.connect('dados_bot.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS dados
                        (chave TEXT PRIMARY KEY, valor TEXT)''')
    return conn

def save_data():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Converter dicionários para JSON antes de salvar
    historico_json = json.dumps(historico_mensagens)
    info_usuario_json = json.dumps(info_usuario)
    
    # Inserir ou atualizar dados
    cursor.execute("INSERT OR REPLACE INTO dados (chave, valor) VALUES (?, ?)",
                   ("historico_mensagens", historico_json))
    cursor.execute("INSERT OR REPLACE INTO dados (chave, valor) VALUES (?, ?)",
                   ("info_usuario", info_usuario_json))
    
    connection.commit()
    logger.debug("Dados salvos com sucesso no SQLite")

def load_data():
    global historico_mensagens, info_usuario
    
    if not os.path.exists('dados_bot.db'):
        historico_mensagens = {}
        info_usuario = {}
        logger.warning("Banco de dados não encontrado. Acionando backup.")
        old_load_data()
        return
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Carregar dados
    for chave in ["historico_mensagens", "info_usuario"]:
        cursor.execute("SELECT valor FROM dados WHERE chave = ?", (chave,))
        resultado = cursor.fetchone()
        if resultado:
            globals()[chave] = json.loads(resultado[0])
        else:
            globals()[chave] = {}
    
    logger.info("Dados carregados com sucesso do SQLite")

# Função para fechar a conexão quando não for mais necessária
def close_connection():
    global conn
    if conn:
        conn.close()
        conn = None


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

def find_user_by_name(name):
    for user_id, user_data in info_usuario.items():
        if user_data.get('nome', '').lower() == name.lower():
            return user_id
    return None

async def dump_user_data(user_name):
    logger.info(f"Buscando user {user_name}")
    user_id = find_user_by_name(user_name)
    if user_id is None:
        # Tenta buscar diretamente pelo nome do usuário
        user_id = user_name if user_name in info_usuario else None
    
    if user_id is None:
        return f"Usuário '{user_name}' não encontrado. Usuários disponíveis: {', '.join(info_usuario.keys())}"
    
    user_info = info_usuario.get(user_id, {})
    user_messages = historico_mensagens.get(user_id, [])
    
    formatted_info = f"Informações do usuário {user_name}:\n"
    for key, value in user_info.items():
        formatted_info += f"{key.capitalize()}: {value}\n"
    
    formatted_messages = "\nHistórico de mensagens:\n"
    for message in user_messages[-10:]:  # Mostra apenas as últimas 10 mensagens
        formatted_messages += f"{message}\n"
    
    return formatted_info + formatted_messages

async def delete_user_data(user_name):
    user_id = find_user_by_name(user_name)
    if not user_id:
        return f"Usuário '{user_name}' não encontrado."
    
    if user_id in info_usuario:
        del info_usuario[user_id]
    if user_id in historico_mensagens:
        del historico_mensagens[user_id]
    save_data()
    return f"Todas as informações e mensagens do usuário '{user_name}' foram eliminadas."

@bot.event
async def on_ready():
    logger.info(f'Diógenes Logado como {bot.user}')
    load_data()

@bot.command(name='shutdown')
async def shutdown(ctx):
    if ctx.author.name.lower() == "voiddragon":
        await ctx.send("Desligando o bot...")
        await bot.close()
    else:
        await ctx.send("Apenas o usuário 'voiddragon' pode executar o comando de desligamento.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('!'):
        parts = message.content.split(maxsplit=1)
        if len(parts) != 2:
            await message.channel.send("Por favor, forneça o nome do usuário. Exemplo: !dump NomeDoUsuario ou !lgpd NomeDoUsuario")
            return
        
        command, user_name = parts
        
        if command == '!dump':
            response = await dump_user_data(user_name)
        elif command == '!lgpd':
            if message.author.name.lower() != "voiddragon":
                await message.channel.send("Apenas o usuário 'voiddragon' pode executar o comando !lgpd.")
                return
            response = await delete_user_data(user_name)
        else:
            await bot.process_commands(message)
            return
        
        await split_and_send_messages(message, response, 1900)
    else:
        await process_message(message)

async def delete_user_data(user_name):
    logger.info(f"Tentando deletar dados do usuário {user_name}")
    user_id = find_user_by_name(user_name)
    if user_id is None:
        # Tenta buscar diretamente pelo nome do usuário
        user_id = user_name if user_name in info_usuario else None
    
    if user_id is None:
        return f"Usuário '{user_name}' não encontrado. Usuários disponíveis: {', '.join(info_usuario.keys())}"
    
    if user_id in info_usuario:
        del info_usuario[user_id]
    if user_id in historico_mensagens:
        del historico_mensagens[user_id]
    save_data()
    return f"Todas as informações e mensagens do usuário '{user_name}' foram eliminadas."


if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        print("Bot encerrado manualmente.")
    except Exception as e:
        print(f"Erro ao executar o bot: {e}")
    finally:
        save_data()
        close_connection()
        sys.exit()