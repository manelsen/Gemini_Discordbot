import asyncio
from bot_module.bot import bot
from utils.logging_config import setup_logging
from utils.data_management import load_data, close_connection, save_data
from config import DISCORD_BOT_TOKEN
import bot_module.commands
import bot_module.events
import core.message_processor
import core.context_generator
import core.response_generator
import models.user
import models.conversation
import ai.gemini_wrapper
import ai.nlp_tools

setup_logging()

if __name__ == "__main__":
    try:
        load_data()
        bot.run(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        print("Bot encerrado manualmente.")
    except Exception as e:
        print(f"Erro ao executar o bot: {e}")
    finally:
        save_data()
        close_connection()