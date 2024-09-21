from bot_module.bot import bot
from core.message_processor import process_message
import traceback
import sys

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    try:
        if message.content.startswith('!'):
            await bot.process_commands(message)
        else:
            await process_message(message)
    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")
        print("Traceback:")
        traceback.print_exc(file=sys.stdout)

@bot.event
async def on_command_error(ctx, error):
    print(f"Erro ao executar comando: {error}")
    print("Traceback:")
    traceback.print_exc(file=sys.stdout)
    await ctx.send(f"Ocorreu um erro ao executar o comando: {error}")