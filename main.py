import sys
import asyncio
import logging

from thon.json_converter import JsonConverter
from src.starter import Starter

from services.console import console
from config import ConfigManager

def main():
    config = ConfigManager.load_config()
    sessions_count = JsonConverter().main()
    if not sessions_count:
        console.log("Нет аккаунтов в папке с сессиями!", style="yellow")
        sys.exit(1)
    if not config:
        logging.error("Ошибка загрузки конфигурации, завершение работы.")
        sys.exit(1)
        
    s = Starter(sessions_count, config)
    asyncio.run(s.main())

if __name__ == "__main__":
    main()