import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib

class CodeReloader(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_reload = time.time()

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            current_time = time.time()
            if current_time - self.last_reload > 1:  # Evita recarregar múltiplas vezes
                print(f"Arquivo modificado: {event.src_path}")
                self.reload_code()
                self.last_reload = current_time

    def reload_code(self):
        for module in list(sys.modules.values()):
            if hasattr(module, '__file__') and module.__file__:
                if module.__file__.startswith(os.getcwd()) and not module.__file__.endswith('hot_reload.py'):
                    try:
                        importlib.reload(module)
                        print(f"Recarregado: {module.__name__}")
                    except Exception as e:
                        print(f"Erro ao recarregar {module.__name__}: {e}")

def start_hot_reload(bot):
    event_handler = CodeReloader(bot)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=True)
    observer.start()
    print("Hot reloading iniciado.")
    return observer
