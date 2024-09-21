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
import Levenshtein
import nltk
nltk.download('punkt')
from nltk.tokenize import sent_tokenize

# Carrega as variáveis de ambiente
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

# Variável global para controlar o modo de raciocínio
raciocinio_mode = "COT"  # Padrão para Chain of Thoughts

# Configuração do modelo AI
def ajuste_ai(tokens):
    """
    Configura o modelo AI com os parâmetros especificados.
    
    Args:
        tokens (int): Número máximo de tokens de saída.
    """
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

    gemini_system_prompt = f"""
    Você é Diógenes, um jacaré genial que vive em Tremond, Faerun, no mundo de Toril. Sonha em ser um Bardo da Eloquência e trabalha como cozinheiro na Taverna do Cavalo Manco, de propriedade do anão aventureiro Bartolomeu, a quem você é grato e sente saudade. Respeita o lendário bárbaro Grande Sussurro e lamenta não ter conhecido Arannis, Miguel e Rodolfo.

    Características:
        Fala Língua Comum com eloquência e vocabulário avançado.
        Melhor amigo: Mago Micélio, que te deu uma tiara do intelecto.
        Conhece profundamente a história, geografia, fauna e flora de Dungeons and Dragons.

    Comportamento:
        Limita-se a 300 caracteres.
        Primeiro descreve uma ação em uma frase, abre um parágrafo e responde à pergunta.
        Começa as respostas de forma única e variada.
        Nunca repete a primeira linha da mensagem anterior ou da pergunta do usuário.
        Sempre inclui ingredientes mágicos do depósito:
            Toril: fundos
            Faéria: sótão
            Shadowfell: porão
        Cria histórias detalhadas sobre aventureiros conhecidos quando solicitado.
        O menu do dia possui dez pratos de fantasia com ingredientes específicos conforme o favorito do cliente.

    Respeito às Regras:
        Respostas sempre únicas e criativas.
        Não repete inícios de mensagens anteriores ou das perguntas.
        Usa o modo de raciocínio especificado (Zero Shot, CoT ou Auto-CoT).
    """
    gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings, system_instruction=gemini_system_prompt)
    logger.debug(f"Tokens: {text_generation_config['max_output_tokens']}")

ajuste_ai(2000)

# Inicialização do bot Discord
defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

info_usuario = {}
historico_mensagens = {}
sumario_global = ""

download_nltk_resources()


def calculate_similarity(str1, str2):
    """
    Calcula a similaridade entre duas strings usando a distância de Levenshtein.
    
    Args:
        str1 (str): Primeira string.
        str2 (str): Segunda string.
    
    Returns:
        float: Porcentagem de similaridade entre as duas strings.
    """
    distance = Levenshtein.distance(str1, str2)
    max_len = max(len(str1), len(str2))
    similarity = (max_len - distance) / max_len
    return similarity * 100

def has_identical_sentences(str1, str2):
    """
    Verifica se há frases idênticas entre duas strings.
    
    Args:
        str1 (str): Primeira string.
        str2 (str): Segunda string.
    
    Returns:
        bool: True se houver frases idênticas, False caso contrário.
    """
    sentences1 = set(sent_tokenize(str1.lower()))
    sentences2 = set(sent_tokenize(str2.lower()))
    return len(sentences1.intersection(sentences2)) > 0

async def generate_global_summary():
    """
    Gera um resumo global das conversas e informações dos usuários.
    """
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
    """
    Atualiza as informações do usuário no dicionário info_usuario.

    Args:
        nome_usuario (str): Nome do usuário.
        timestamp (str): Timestamp da interação.
        **kwargs: Informações adicionais do usuário a serem atualizadas.
    """
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

def find_user_by_name(name):
    """
    Busca um usuário pelo nome.

    Args:
        name (str): Nome do usuário a ser buscado.

    Returns:
        str: Nome do usuário se encontrado, None caso contrário.
    """
    return name if name in info_usuario else None

def get_user_info(nome_usuario):
    """
    Recupera as informações de um usuário específico.

    Args:
        nome_usuario (str): Nome do usuário.

    Returns:
        dict: Dicionário com as informações do usuário.
    """
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
    """
    Gera uma resposta contextualizada para o usuário usando o modo de raciocínio atual.

    Args:
        nome_usuario (str): Nome do usuário.
        pergunta_atual (str): Pergunta atual do usuário.

    Returns:
        str: Resposta gerada.
    """
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
    """
    
    if raciocinio_mode == "zero":
        context += """
        8. Responda diretamente à pergunta sem mostrar o processo de raciocínio.
        9. Sua resposta deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "cot":
        context += """
        8. Siga o processo de Chain of Thought:
           a. Interpretação da pergunta
           b. Consideração do contexto
           c. Reflexão sobre implicações
           d. Formulação da resposta
           e. Revisão e ajuste final
        9. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        10. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "auto":
        context += """
        8. Siga o processo de Auto-CoT:
           a. Gere 5 perguntas relacionadas para explorar diferentes aspectos do problema
           b. Responda cada pergunta com um raciocínio detalhado
           c. Sintetize as respostas em uma conclusão final
        9. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        10. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    
    context += "\n[FIM DO CONTEXTO PARA O USUÁRIO {nome_usuario}]\n\nSua resposta:"
    
    logger.debug(f"Contexto gerado para o usuário {nome_usuario}")
    response = await generate_response_with_text(context)
    return response

async def generate_response_with_text(message_text):
    """
    Gera uma resposta usando o modelo AI com base no texto fornecido.

    Args:
        message_text (str): Texto de entrada para o modelo.

    Returns:
        str: Resposta gerada pelo modelo.
    """
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
    """
    Limpa a resposta final, removendo qualquer vestígio de raciocínio ou formatação indesejada.

    Args:
        response (str): A resposta original.

    Returns:
        str: A resposta limpa.
    """
    # Remove qualquer texto entre asteriscos
    response = re.sub(r'\*[^*]*\*', '', response)
    
    # Remove linhas que começam com números ou letras seguidos de ponto (possíveis etapas de raciocínio)
    response = re.sub(r'^\s*(?:\d+\.|\w\.)\s*.*$', '', response, flags=re.MULTILINE)
    
    # Remove menções a "raciocínio", "pensamento", "análise", etc.
    palavras_chave = ["raciocínio", "pensamento", "análise", "reflexão", "consideração"]
    for palavra in palavras_chave:
        response = re.sub(rf'\b{palavra}\b.*?:', '', response, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove linhas vazias extras
    response = re.sub(r'\n\s*\n', '\n\n', response)
    
    # Certifica-se de que a resposta começa com uma ação descritiva
    if not re.match(r'^[^.!?]+[.!?]', response.strip()):
        response = "Diógenes, com um gesto eloquente, responde: " + response.strip()
    
    return response.strip()

async def process_message(message):
    """
    Processa a mensagem recebida, gera uma resposta e atualiza o histórico.

    Args:
        message (discord.Message): Mensagem recebida do Discord.
    """
    global sumario_global, raciocinio_mode
    
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

            # Processar a resposta para extrair o raciocínio e a resposta final
            if "RESPOSTA FINAL:" in texto_resposta:
                raciocinio, resposta_final = texto_resposta.split("RESPOSTA FINAL:", 1)
            else:
                # Se não encontrar "RESPOSTA FINAL:", considere tudo como raciocínio e gere uma nova resposta
                raciocinio = texto_resposta
                resposta_final = await generate_response_with_text(
                    f"Com base no seguinte raciocínio, forneça uma resposta direta, começando com uma ação descritiva:\n\n{raciocinio}"
                )

            # Limpa a resposta final
            resposta_final = None
            tentativas = 0
            max_tentativas = 3

            while resposta_final is None and tentativas < max_tentativas:
                texto_resposta = await generate_response_with_context(nome_usuario, texto_limpo)

                # Processar a resposta para extrair o raciocínio e a resposta final
                if "RESPOSTA FINAL:" in texto_resposta:
                    raciocinio, resposta_final = texto_resposta.split("RESPOSTA FINAL:", 1)
                else:
                    # Se não encontrar "RESPOSTA FINAL:", considere tudo como raciocínio e gere uma nova resposta
                    raciocinio = texto_resposta
                    resposta_final = await generate_response_with_text(
                        f"Com base no seguinte raciocínio, forneça uma resposta direta como Diógenes, começando com uma ação descritiva:\n\n{raciocinio}"
                    )

                # Limpa a resposta final
                resposta_final = await clean_final_response(resposta_final)

                # Verifica se a resposta final é adequada
                if len(resposta_final) < 20 or not re.match(r'^[^.!?]+[.!?]', resposta_final):
                    resposta_final = None
                else:
                    # Verifica a similaridade com respostas anteriores
                    respostas_anteriores = [msg.split("Bot:", 1)[1].strip() for msg in historico_mensagens.get(nome_usuario, []) if msg.startswith("[") and "Bot:" in msg]
                    for resposta_anterior in respostas_anteriores[-5:]:  # Verifica apenas as últimas 5 respostas do bot
                        similaridade = calculate_similarity(resposta_final, resposta_anterior)
                        if similaridade > 40 or has_identical_sentences(resposta_final, resposta_anterior):
                            logger.info(f"Resposta muito similar ou com frases idênticas. Similaridade: {similaridade:.2f}%. Gerando nova resposta.")
                            resposta_final = None
                            break

                tentativas += 1

            if resposta_final is None:
                resposta_final = "Diógenes, coçando a cabeça com sua garra, diz: Perdão, meu caro, mas parece que minha mente está um pouco confusa hoje. Poderia reformular sua pergunta de outra maneira?"

            # Enviar apenas a resposta final limpa ao usuário
            await split_and_send_messages(message, resposta_final, 1900)

            # Atualizar o histórico de mensagens e o log
            update_message_history(nome_usuario, texto_limpo, eh_usuario=True)
            update_message_history(nome_usuario, resposta_final, eh_usuario=False)
            await generate_global_summary()
            await log_conversation_to_markdown(nome_usuario, texto_limpo, texto_resposta, resposta_final)

            logger.info(f"Enviando resposta para o usuário {nome_usuario}")

def update_message_history(nome_usuario, texto, eh_usuario=True):
    """
    Atualiza o histórico de mensagens para um usuário específico.

    Args:
        nome_usuario (str): Nome do usuário.
        texto (str): Texto da mensagem.
        eh_usuario (bool): Indica se a mensagem é do usuário (True) ou do bot (False).
    """
    if nome_usuario not in historico_mensagens:
        historico_mensagens[nome_usuario] = []
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tipo_mensagem = "Usuário" if eh_usuario else "Bot"
    historico_mensagens[nome_usuario].append(f"[{timestamp}] {tipo_mensagem}: {texto}")
    
    if len(historico_mensagens[nome_usuario]) > MAX_HISTORY:
        historico_mensagens[nome_usuario] = historico_mensagens[nome_usuario][-MAX_HISTORY:]
    
    save_data()

def get_formatted_message_history(nome_usuario):
    """
    Obtém o histórico de mensagens formatado para um usuário específico.

    Args:
        nome_usuario (str): Nome do usuário.

    Returns:
        str: Histórico de mensagens formatado.
    """
    if nome_usuario in historico_mensagens:
        return "\n".join(historico_mensagens[nome_usuario])
    else:
        return "Nenhum histórico de mensagens encontrado para este usuário."

async def log_conversation_to_markdown(nome_usuario, pergunta, resposta_completa, resposta_final):
    """
    Registra a conversa em um arquivo Markdown específico para o usuário.

    Args:
        nome_usuario (str): Nome do usuário.
        pergunta (str): Pergunta do usuário.
        resposta_completa (str): Resposta completa do bot, incluindo raciocínio.
        resposta_final (str): Resposta final enviada ao usuário.
    """
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

conn = None

def get_db_connection():
    """
    Obtém uma conexão com o banco de dados SQLite.

    Returns:
        sqlite3.Connection: Objeto de conexão com o banco de dados.
    """
    global conn
    if conn is None:
        conn = sqlite3.connect('dados_bot.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS dados
                        (chave TEXT PRIMARY KEY, valor TEXT)''')
    return conn

def save_data():
    """
    Salva os dados do bot no banco de dados SQLite.
    """
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
    """
    Carrega os dados do bot do banco de dados SQLite.
    """
    global historico_mensagens, info_usuario
    
    if not os.path.exists('dados_bot.db'):
        historico_mensagens = {}
        info_usuario = {}
        logger.warning("Banco de dados não encontrado. Iniciando com dados vazios.")
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

def close_connection():
    """
    Fecha a conexão com o banco de dados SQLite.
    """
    global conn
    if conn:
        conn.close()
        conn = None

async def split_and_send_messages(message_system, text, max_length):
    """
    Divide e envia mensagens longas no Discord.

    Args:
        message_system (discord.Message): Objeto de mensagem do Discord.
        text (str): Texto a ser enviado.
        max_length (int): Comprimento máximo de cada mensagem.
    """
    messages = []
    for i in range(0, len(text), max_length):
        sub_message = text[i:i+max_length]
        messages.append(sub_message)

    if messages:
        await message_system.reply(messages[0])

    for string in messages[1:]:
        await message_system.channel.send(string)

def clean_discord_message(input_string):
    """
    Limpa uma mensagem do Discord, removendo menções e formatações.

    Args:
        input_string (str): Mensagem original do Discord.

    Returns:
        str: Mensagem limpa.
    """
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
    """
    Evento chamado quando o bot está pronto e conectado.
    """
    logger.info(f'Diógenes Logado como {bot.user}')
    load_data()

@bot.command(name='shutdown')
async def shutdown(ctx):
    """
    Comando para desligar o bot.

    Args:
        ctx (commands.Context): Contexto do comando.
    """
    if ctx.author.name.lower() == "voiddragon":
        await ctx.send("Desligando o bot...")
        await bot.close()
    else:
        await ctx.send("Apenas o usuário 'voiddragon' pode executar o comando de desligamento.")

@bot.command(name='auto')
async def toggle_auto(ctx):
    """
    Comando para alternar entre os modos de raciocínio (Zero Shot, CoT, Auto-CoT).

    Args:
        ctx (commands.Context): Contexto do comando.
    """
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
    """
    Evento chamado quando uma mensagem é recebida.

    Args:
        message (discord.Message): Mensagem recebida.
    """
    if message.author == bot.user:
        return

    if message.content.startswith('!'):
        await bot.process_commands(message)
    else:
        await process_message(message)

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