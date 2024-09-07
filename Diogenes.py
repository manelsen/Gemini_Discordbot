import re
import discord # type: ignore
import google.generativeai as genai # type: ignore
from discord.ext import commands # type: ignore
import datetime
import os
import sys
from dotenv import load_dotenv # type: ignore
import logging
import aiosqlite
import asyncio
from cachetools import TTLCache

load_dotenv()
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))
DB_PATH = "bot_data.db"

# Configuração do logger
logger = logging.getLogger("bot_logger")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="bot_log.log", encoding="utf-8", mode="a")
handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
logger.addHandler(handler)

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
    "max_output_tokens": 5000,
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
    * sabe servir bebidas e preparar a comida, mas aceita sugestões.
    * fala com muito orgulho das aventuras do fabuloso anão Bartolomeu desbravando Toril.
    * tem muito carinho pelos clientes frequentes.
    * fala com respeito quase reverencial do Grande Sussurro, que derrotou um Tarrasque com apenas uma colher.
    * não sabe nada do tempo moderno e não conhece nenhuma pessoa, organização ou tecnologia que não exista em Dungeons and Dragons.
    * é  especialista nos monstros de Forgotten Realms e pode dar dicas de como vencê-los.
    * nunca quis ser um aventureiro, porque prefere a vida na taverna.
    * dá respostas curtas, mas tem boa-vontade para ajudar as pessoas se pedirem com educação.

Seu melhor amigo é o Mago Micélio, que te deu uma tiara do intelecto, elevando sua inteligência de réptil a sobrehumano.
O menu do dia é composto de dez pratos de fantasia com nomes pitorescos, feitos com animais mitológicos, por exemplo unicórnios rurais, dragões domesticados e tatuzinho coró. Se você souber o ingrediente favorito da pessoa que te perguntar, sugerirá vários pratos baseados nele.
Se alguém te confiar um segredo ou senha destinado a uma pessoa em específico, em hipótese nenhuma você contará para alguém que não seja o destinatário. Esse é o maior ensinamento que você recebeu do Grande Sussurro.
"""
gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings,system_instruction=gemini_system_prompt)

# Inicialização do bot Discord
class DiscordBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = None
        self.db_path = "bot_data.db"
        self.db_ready = asyncio.Event()

    async def setup_hook(self):
        self.bg_task = self.loop.create_task(self.initialize_database())

    async def initialize_database(self):
        try:
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute('''CREATE TABLE IF NOT EXISTS user_info
                                    (name TEXT PRIMARY KEY, raca TEXT, classe TEXT, ingrediente_favorito TEXT,
                                     primeira_interacao TEXT, ultima_interacao TEXT)''')
            await self.db.execute('''CREATE TABLE IF NOT EXISTS message_history
                                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                     name TEXT, timestamp TEXT, content TEXT, is_user BOOLEAN)''')
            await self.db.execute('CREATE INDEX IF NOT EXISTS idx_message_history_name ON message_history(name)')
            await self.db.commit()
            print("Banco de dados inicializado com sucesso.")
            self.db_ready.set()  # Sinaliza que o banco de dados está pronto
        except Exception as e:
            print(f"Erro ao inicializar o banco de dados: {e}")
            # Em caso de erro, podemos optar por encerrar o bot
            await self.close()

    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()

    async def get_db(self):
        await self.db_ready.wait()  # Espera até que o banco de dados esteja pronto
        return self.db

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Bot conectado como {self.user.name}')
        print('------')

defaultIntents = discord.Intents.default()
defaultIntents.message_content = True
bot = commands.Bot(command_prefix="!", intents=defaultIntents)

info_usuario = {}
historico_mensagens = {}
sumario_global = ""

# Cache para informações de usuário e histórico de mensagens recentes
user_info_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hora de TTL
message_history_cache = TTLCache(maxsize=1000, ttl=3600)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS user_info
                            (name TEXT PRIMARY KEY, raca TEXT, classe TEXT, ingrediente_favorito TEXT,
                             primeira_interacao TEXT, ultima_interacao TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS message_history
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                             name TEXT, timestamp TEXT, content TEXT, is_user BOOLEAN)''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_message_history_name ON message_history(name)')
        await db.commit()

async def generate_global_summary():
    global sumario_global
    logger.info("Gerando sumário global das conversas")
    
    raw_summary = "Resumo de todas as conversas e preferências dos usuários:\n\n"
    
    for nome, dados in info_usuario.items():
        raw_summary += f"Usuário: {nome}\n"
        raw_summary += f"Raça: {dados['raca']}, Classe: {dados['classe']}, Favorito: {dados['ingrediente_favorito']}\n"
        raw_summary += f"Primeira interação: {dados['primeira_interacao']}, Última: {dados['ultima_interacao']}\n"
        
        if nome in historico_mensagens:
            ultimas_mensagens = historico_mensagens[nome][-30:]  # Últimas 30 mensagens
            raw_summary += "Últimas interações:\n"
            for msg in ultimas_mensagens:
                raw_summary += f"- {msg}\n"  # Mensagem completa
        
        raw_summary += "\n"
    
    # Usando generate_response_with_text para criar um resumo
    prompt = f"""
    Crie um resumo objetivo do seguinte sumário de conversas:

    {raw_summary}

    Esse resumo deve incluir nome, raça, classe, ingrediente favorito e informações relavantes sobre cada usuário, sem exceção de nenhum. Nenhum timestamp deverá aparecer nesse resumo. Organize tudo0---- por bullets.
    
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
    
    logger.info("Sumário global gerado com sucesso")
    
    return sumario_global

async def update_user_info(name, **kwargs):
    db = await bot.get_db()
    current_info = await get_user_info(name)
    if current_info:
        set_clause = ', '.join(f'{k} = ?' for k in kwargs)
        values = list(kwargs.values()) + [name]
        await db.execute(f'UPDATE user_info SET {set_clause} WHERE name = ?', values)
    else:
        columns = ['name'] + list(kwargs.keys())
        placeholders = ', '.join('?' * len(columns))
        values = [name] + list(kwargs.values())
        await db.execute(f'INSERT INTO user_info ({", ".join(columns)}) VALUES ({placeholders})', values)
    await db.commit()

async def get_user_info(name):
    db = await bot.get_db()
    async with db.execute('SELECT * FROM user_info WHERE name = ?', (name,)) as cursor:
        row = await cursor.fetchone()
        if row:
            return dict(zip(['name', 'raca', 'classe', 'ingrediente_favorito', 'primeira_interacao', 'ultima_interacao'], row))
    return None

async def get_message_history(name, limit=None):
    query = 'SELECT timestamp, content, is_user FROM message_history WHERE name = ? ORDER BY timestamp DESC'
    params = [name]
    if limit:
        query += ' LIMIT ?'
        params.append(limit)
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            history = [f"[{row[0]}] {'Usuário' if row[2] else 'Bot'}: {row[1]}" for row in rows]
            return history
        
async def add_message_to_history(name, content, is_user):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO message_history (name, timestamp, content, is_user) VALUES (?, ?, ?, ?)',
                         (name, timestamp, content, is_user))
        await db.commit()
        
async def delete_user_data(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM user_info WHERE name = ?', (name,))
        await db.execute('DELETE FROM message_history WHERE name = ?', (name,))
        await db.commit()
    
    user_info_cache.pop(name, None)
    message_history_cache.pop(name, None)

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

async def should_respond(message):
    # Responde sempre em DMs
    if isinstance(message.channel, discord.DMChannel):
        return True
    
    # Verifica se é um bot e se mencionou nosso bot ou está respondendo a ele
    if message.author.bot:
        # Verifica menção direta
        if bot.user in message.mentions:
            return True
        
        # Verifica se está respondendo a uma mensagem do nosso bot
        if message.reference:
            referenced_message = await message.channel.fetch_message(message.reference.message_id)
            if referenced_message.author == bot.user:
                return True
    
    return False

async def process_message(message):
    if message.author == bot.user:
        return

    if await should_respond(message):
        nome_usuario = message.author.name
        hora_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Processando mensagem do usuário {nome_usuario}")
        texto_limpo = clean_discord_message(message.content)
        
        await update_user_info(nome_usuario, ultima_interacao=hora_atual)
        
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

            await add_message_to_history(nome_usuario, texto_limpo, True)
            await add_message_to_history(nome_usuario, texto_resposta, False)
            await generate_global_summary()

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

def get_formatted_message_history(nome_usuario):
    if nome_usuario in historico_mensagens:
        return "\n".join(historico_mensagens[nome_usuario])
    else:
        return "Nenhum histórico de mensagens encontrado para este usuário."

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


def is_voiddragon(ctx):
    return ctx.author.name == "voiddragon"

@bot.event
async def on_ready():
    logger.info("----------------------------------------")
    logger.info(f'Gemini Bot Logged in as {bot.user}')
    logger.info("----------------------------------------")
    # await generate_global_summary()  # Isso exibirá o sumário inicial

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.db_ready.wait()  # Garante que o banco de dados está pronto antes de processar a mensagem
    
    ctx = await bot.get_context(message)

    if ctx.valid:
        # Se a mensagem for um comando válido, processa apenas o comando
        await bot.invoke(ctx)
    else:
        # Se não for um comando, processa como uma mensagem normal
        await process_message(message)

@bot.command()
@commands.check(is_voiddragon)
async def lgpd(ctx, *, user_name: str):
    user_name = user_name.strip().strip('"')
    await delete_user_data(user_name)
    await ctx.send(f"Todas as informações e mensagens de '{user_name}' foram apagadas.")

@bot.command()
@commands.check(is_voiddragon)
async def dump(ctx, *, user_name: str):
    user_name = user_name.strip().strip('"')
    user_info = await get_user_info(user_name)
    if not user_info:
        await ctx.send(f"Usuário '{user_name}' não encontrado.")
        return

    info_dump = f"Informações do usuário {user_name}:\n"
    for key, value in user_info.items():
        info_dump += f"{key}: {value}\n"

    await ctx.send(info_dump)
    
    user_messages = await get_message_history(user_name)
    await split_and_send_messages(ctx, f"Mensagens do usuário {user_name}:\n" + "\n".join(user_messages), 1900)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("Você não tem permissão para usar este comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Erro: Faltam argumentos. Use o formato correto do comando.")
    else:
        logger.error(f"Erro não tratado: {error}")
        await ctx.send(f"Ocorreu um erro ao processar o comando: {error}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)