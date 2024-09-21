import logging
import sys
import datetime

raciocinio_mode = "COT"


def setup_logging():
    logger = logging.getLogger("bot_logger")
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(filename="bot_log.log", encoding="utf-8", mode="a")
    file_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
    
    logger.addHandler(console_handler)

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

    logger = logging.getLogger("bot_logger")
    logger.info(f"Log da conversa atualizado em: {filename}")