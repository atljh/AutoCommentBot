import asyncio

from config import ConfigManager
from src.starter import Starter
from src.thon.json_converter import JsonConverter
from src.managers.file_manager import FileManager
from scripts.authorization import register_user  # noqa

# register_user()


def main():
    config = ConfigManager.load_config()
    proxy_list = FileManager.read_proxy()

    sessions_count = JsonConverter().main()
    s = Starter(sessions_count, config)
    asyncio.run(s.main())


if __name__ == "__main__":
    main()
