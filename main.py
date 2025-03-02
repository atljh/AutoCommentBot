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
    # distributed_proxies = distribute_proxies(accounts_count, proxy_list, accounts_per_proxy)
    # print(distributed_proxies)
    ses = JsonConverter().distribute_proxies(proxy_list, config.accounts_per_proxy)
    print(ses)
    return
    sessions_count = JsonConverter().main()
    s = Starter(sessions_count, config)
    asyncio.run(s.main())


if __name__ == "__main__":
    main()
