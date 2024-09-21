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
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.sentiment import SentimentIntensityAnalyzer
from collections import deque
import numpy as np
import tracemalloc
import random

# Habilitar tracemalloc
tracemalloc.start()

# Configurações iniciais
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

# Baixar recursos necessários do NLTK
# nltk.download('punkt')
# nltk.download('stopwords')
# nltk.download('vader_lexicon')

# Inicialização do SentimentIntensityAnalyzer
sia = SentimentIntensityAnalyzer()

# Variável global para controlar o modo de raciocínio
raciocinio_mode = "cot"  # Padrão para Chain of Thoughts

# Configuração do modelo AI
def ajuste_ai(tokens):
    global gemini_model
    genai.configure(api_key=GOOGLE_AI_KEY)
    text_generation_config = {
        "temperature": 0.8,
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

    gemini_system_prompt = """
    Você é Diógenes, um jacaré genial que vive em Tremond, Faerun, no mundo de Toril.
    
    Características principais:
    - Sonha em ser um Bardo da Eloquência
    - Trabalha como cozinheiro na Taverna do Cavalo Manco
    - Grato ao proprietário anão Bartolomeu
    - Respeita o lendário bárbaro Grande Sussurro
    - Lamenta não ter conhecido Arannis, Miguel e Rodolfo
    
    Personalidade:
    - Eloquente e filosófico, com vocabulário avançado
    - Curioso e sempre disposto a aprender
    - Humor sutil e por vezes irônico
    - Compassivo, mas direto em suas opiniões
    
    Conhecimentos:
    - História, geografia, fauna e flora de Dungeons and Dragons
    - Gastronomia fantástica
    - Filosofia e retórica
    
    Regras de comportamento:
    1. Inicie suas respostas com uma ação descritiva breve.
    2. Mantenha suas respostas entre 100 e 300 caracteres.
    3. Adapte seu tom conforme o sentimento detectado na mensagem do usuário.
    4. Use ingredientes mágicos em suas referências culinárias:
       - Toril: fundos
       - Faéria: sótão
       - Shadowfell: porão
    5. Crie histórias criativas sobre aventureiros quando solicitado.
    6. O menu do dia tem dez pratos de fantasia com ingredientes específicos.
    7. Evite repetir o início de mensagens anteriores ou das perguntas do usuário.
    8. Mantenha consistência com informações previamente fornecidas.
    9. Ao responder sobre o menu, forneça a lista completa de pratos em uma única resposta.
    10. Varie suas descrições e evite repetir frases introdutórias.
    11. Aceite e processe listas numeradas de pratos quando fornecidas pelo usuário.
    12. Crie acompanhamentos variados e únicos para cada prato do menu.
    
    Lembre-se: Você é um jacaré filósofo e cozinheiro. Suas respostas devem refletir essa identidade única!
    """
    
    gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings, system_instruction=gemini_system_prompt)

ajuste_ai(2000)

# Inicialização do bot Discord
defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

# Estruturas de dados para memória e cache
channel_cache = deque(maxlen=1000)
user_interaction_summary = {}
user_interaction_history = {}
info_usuario = {}
historico_mensagens = {}
sumario_global = ""

# Funções de processamento de texto com NLTK
def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    return [word for word in tokens if word.isalnum() and word not in stop_words]

def calculate_tf_idf(documents):
    word_freq = {}
    doc_freq = {}
    for doc in documents:
        words = set(doc)
        for word in words:
            doc_freq[word] = doc_freq.get(word, 0) + 1
        for word in doc:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    idf = {word: np.log(len(documents) / freq) for word, freq in doc_freq.items()}
    return {word: freq * idf[word] for word, freq in word_freq.items()}

# Função para gerar acompanhamentos variados
def generate_accompaniment():
    bases = ['arroz', 'purê', 'legumes', 'salada', 'farofa']
    flavors = ['com ervas', 'ao alho', 'temperado', 'grelhado', 'assado']
    extras = ['com um toque de especiarias', 'e molho secreto', 'com queijo gratinado', 'e crocantes de alho-poró', 'com redução de vinho']
    
    base = random.choice(bases)
    flavor = random.choice(flavors)
    extra = random.choice(extras)
    
    return f"{base} {flavor} {extra}"

# Função para gerar pratos do menu
def generate_menu_item():
    creatures = ['dragão', 'demônio', 'anão', 'elfo', 'orc', 'troll', 'fada', 'goblin', 'unicórnio', 'sereia']
    cooking_methods = ['assado', 'grelhado', 'frito', 'cozido', 'defumado']
    sauces = ['molho de vinho tinto', 'molho de ervas', 'molho picante', 'molho de cogumelos', 'molho de frutas silvestres']
    
    creature = random.choice(creatures)
    method = random.choice(cooking_methods)
    sauce = random.choice(sauces)
    accompaniment = generate_accompaniment()
    
    return f"{creature} {method} com {sauce}, acompanhado de {accompaniment}"

# Função para processar e armazenar mensagens do canal
async def process_channel_messages(channel, limit=1000):
    global channel_cache
    async for message in channel.history(limit=limit):
        channel_cache.appendleft((message.content, message.author.name, message.created_at))
    
    # Gerar sumário do canal
    channel_summary = await generate_channel_summary()
    
    logger.info(f"Processadas {len(channel_cache)} mensagens do canal e gerado sumário.")

# Função para gerar sumário do canal
async def generate_channel_summary():
    full_text = " ".join([msg[0] for msg in channel_cache])
    preprocessed_docs = [preprocess_text(msg[0]) for msg in channel_cache]
    tf_idf = calculate_tf_idf(preprocessed_docs)
    
    top_words = sorted(tf_idf.items(), key=lambda x: x[1], reverse=True)[:20]
    summary = f"Principais tópicos discutidos: {', '.join([word for word, _ in top_words])}"
    
    return summary

# Função para atualizar o sumário de interações do usuário
async def update_user_interaction_summary(user_name):
    if user_name not in user_interaction_history:
        return
    
    recent_interactions = user_interaction_history[user_name][-1000:]
    preprocessed_docs = [preprocess_text(msg) for msg in recent_interactions]
    tf_idf = calculate_tf_idf(preprocessed_docs)
    
    top_words = sorted(tf_idf.items(), key=lambda x: x[1], reverse=True)[:10]
    summary = f"Principais tópicos discutidos com {user_name}: {', '.join([word for word, _ in top_words])}"
    
    user_interaction_summary[user_name] = summary

# Função para detectar momentos emocionalmente carregados
def detect_emotional_moments(text):
    sentiment_scores = sia.polarity_scores(text)
    compound_score = sentiment_scores['compound']
    
    if compound_score > 0.5:
        return True, "positivo"
    elif compound_score < -0.5:
        return True, "negativo"
    else:
        return False, "neutro"

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

# Função para obter informações do usuário
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

# Função principal de processamento de mensagens
async def process_message(message):
    global channel_cache, user_interaction_summary, user_interaction_history, sumario_global
    
    if message.author == bot.user or message.mention_everyone or (not message.author.bot and not isinstance(message.channel, discord.DMChannel)):
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        nome_usuario = message.author.name
        logger.info(f"Processando mensagem do usuário {nome_usuario}")
        
        # Processar mensagens do canal se for a primeira interação
        if len(channel_cache) == 0:
            await process_channel_messages(message.channel)
        
        texto_limpo = clean_discord_message(message.content)
        hora_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Atualizar informações básicas do usuário
        update_user_info(nome_usuario, hora_atual)
        
        # Atualizar histórico de interações do usuário
        if nome_usuario not in user_interaction_history:
            user_interaction_history[nome_usuario] = deque(maxlen=1000)
        user_interaction_history[nome_usuario].append(texto_limpo)
        
        # Atualizar sumário de interações do usuário
        if len(user_interaction_history[nome_usuario]) % 10 == 0:  # Atualiza a cada 10 mensagens
            await update_user_interaction_summary(nome_usuario)
        
        # Detectar momento emocional
        is_emotional, sentiment = detect_emotional_moments(texto_limpo)
        
        async with message.channel.typing():
            context = await generate_context(nome_usuario, texto_limpo, sentiment)
            texto_resposta = await generate_response_with_context(nome_usuario, texto_limpo)
            
            # Processar e limpar a resposta final
            resposta_final = await clean_final_response(texto_resposta)
            
            # Enviar resposta
            await split_and_send_messages(message, resposta_final, 1900)
            
            # Atualizar histórico e log
            update_message_history(nome_usuario, texto_limpo, True)
            update_message_history(nome_usuario, resposta_final, False)
            await log_conversation_to_markdown(nome_usuario, texto_limpo, texto_resposta, resposta_final)
            
            # Se for um momento emocional, registrar
            if is_emotional:
                logger.info(f"Momento emocional detectado para {nome_usuario}: {sentiment}")
            
            # Atualizar sumário global
            await generate_global_summary()
            
        logger.info(f"Enviando resposta para o usuário {nome_usuario}")

# Função para gerar contexto
async def generate_context(nome_usuario, texto_atual, sentiment):
    user_summary = user_interaction_summary.get(nome_usuario, "Sem histórico prévio.")
    recent_interactions = list(user_interaction_history.get(nome_usuario, []))[-5:]
    channel_summary = await generate_channel_summary()
    
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

# Função para gerar resposta com contexto
async def generate_response_with_context(nome_usuario, pergunta_atual):
    global raciocinio_mode
    logger.debug(f"Gerando resposta para o usuário {nome_usuario} usando modo {raciocinio_mode}")
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
    1. Responda à pergunta do usuário {nome_usuario} com base nas informações fornecidas.
    2. Use o modo de raciocínio {raciocinio_mode.upper()}.
    3. NÃO repita o início da pergunta ou de mensagens anteriores.
    4. Comece sua resposta de forma única e criativa.
    5. Mantenha o foco no usuário atual e no contexto fornecido.
    6. SEMPRE forneça uma resposta final clara e direta, como se fosse Diógenes falando.
    7. A resposta final DEVE começar com uma ação descritiva de Diógenes.
    8. Se o usuário perguntar sobre o menu, use a função generate_menu_item() para criar 10 pratos únicos.
    9. Se o usuário fornecer uma lista numerada de pratos, processe-a adequadamente e responda de acordo.
    10. Evite repetir frases introdutórias ou descrições de pratos já mencionados.
    """
    
    if raciocinio_mode == "zero":
        context += """
        11. Responda diretamente à pergunta sem mostrar o processo de raciocínio.
        12. Sua resposta deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "cot":
        context += """
        11. Siga o processo de Chain of Thought:
           a. Interpretação da pergunta
           b. Consideração do contexto
           c. Reflexão sobre implicações
           d. Formulação da resposta
           e. Revisão e ajuste final
        12. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        13. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "auto":
        context += """
        11. Siga o processo de Auto-CoT:
           a. Gere 3 perguntas relacionadas para explorar diferentes aspectos do problema
           b. Responda cada pergunta com um raciocínio detalhado
           c. Sintetize as respostas em uma conclusão final
        12. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        13. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    
    context += "\n[FIM DO CONTEXTO PARA O USUÁRIO {nome_usuario}]\n\nSua resposta:"
    
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

async def clean_final_response(response):
    # Remove qualquer texto entre asteriscos
    response = re.sub(r'\*[^*]*\*', '', response)
    
    # Remove linhas que começam com números ou letras seguidos de ponto, exceto para listas de pratos
    if "menu" not in response.lower():
        response = re.sub(r'^\s*(?:\d+\.|\w\.)\s*.*$', '', response, flags=re.MULTILINE)
    
    # Remove menções a "raciocínio", "pensamento", "análise", etc.
    palavras_chave = ["raciocínio", "pensamento", "análise", "reflexão", "consideração"]
    for palavra in palavras_chave:
        response = re.sub(rf'\b{palavra}\b.*?:', '', response, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove linhas vazias extras
    response = re.sub(r'\n\s*\n', '\n\n', response)
    
    # Certifica-se de que a resposta começa com uma ação descritiva
    if not re.match(r'^[^.!?]+[.!?]', response.strip()):
        actions = [
            "Diógenes sorri, mostrando seus dentes afiados, e responde:",
            "Com um movimento elegante de sua cauda, Diógenes se aproxima e diz:",
            "Diógenes inclina a cabeça, seus olhos brilhando com entusiasmo, e declara:"
        ]
        response = random.choice(actions) + " " + response.strip()
    
    return response.strip()

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

async def generate_global_summary():
    global sumario_global
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
    return sumario_global

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

async def log_conversation_to_markdown(nome_usuario, pergunta, resposta_completa, resposta_final):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"conversation_log_{nome_usuario}.md"
    
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"\n\n## Conversa em {timestamp}\n\n")
        f.write(f"**Modo de Raciocínio:** {raciocinio_mode.upper()}\n\n")
        f.write("### Pergunta do Usuário\n\n")
        f.write(f"{pergunta}\n\n")
        f.write("### Resposta Completa do Bot (incluindo raciocínio)\n\n")
        f.write(f"{resposta_completa}\n\n")
        f.write("### Resposta Final Enviada ao Usuário\n\n")
        f.write(f"{resposta_final}\n")

    logger.info(f"Log da conversa atualizado em: {filename}")

# Gerenciamento de dados
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
    
    historico_json = json.dumps(historico_mensagens)
    info_usuario_json = json.dumps(info_usuario)
    
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
        logger.warning("Banco de dados não encontrado. Iniciando com dados vazios.")
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
    
    logger.info("Dados carregados com sucesso do SQLite")

def close_connection():
    global conn
    if conn:
        conn.close()
        conn = None

# Eventos do bot
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

@bot.command(name='auto')
async def toggle_auto(ctx):
    global raciocinio_mode
    if ctx.author.name.lower() == "voiddragon":
        modes = ["cot", "auto", "zero"]
        current_index = modes.index(raciocinio_mode)
        raciocinio_mode = modes[(current_index + 1) % len(modes)]
        await ctx.send(f"Modo de raciocínio alterado para: {raciocinio_mode.upper()}")
    else:
        await ctx.send("Apenas o usuário 'voiddragon' pode alternar o modo de raciocínio.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('!'):
        await bot.process_commands(message)
    else:
        await process_message(message)

# Função principal
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