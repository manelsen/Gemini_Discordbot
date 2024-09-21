import discord
from discord.ext import commands
from config import MAX_HISTORY
from core.message_processor import process_message

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Diógenes Logado como {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    print(f"Mensagem recebida: {message.content}")
    
    # Processa comandos primeiro
    await bot.process_commands(message)
    
    # Se não for um comando, processa como uma mensagem normal
    if not message.content.startswith(bot.command_prefix):
        await process_message(message)

# ... outros eventos ou configurações ...