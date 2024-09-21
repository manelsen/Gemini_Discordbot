from bot_module.bot import bot  # Alterado de 'from bot.bot import bot'
from core.message_processor import raciocinio_mode
from discord.ext import commands
import importlib
import sys

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
    if ctx.author.name.lower() == "voiddragon":tr
        modes = ["cot", "auto", "zero"]
        current_index = modes.index(raciocinio_mode)
        raciocinio_mode = modes[(current_index + 1) % len(modes)]
        await ctx.send(f"Modo de raciocínio alterado para: {raciocinio_mode.upper()}")
    else:
        await ctx.send("Apenas o usuário 'voiddragon' pode alternar o modo de raciocínio.")

@bot.command(name='reload')
@commands.is_owner()
async def reload_module(ctx, module_name: str):
    try:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
            await ctx.send(f"Módulo '{module_name}' recarregado com sucesso.")
        else:
            await ctx.send(f"Módulo '{module_name}' não encontrado.")
    except Exception as e:
        await ctx.send(f"Erro ao recarregar o módulo '{module_name}': {str(e)}")