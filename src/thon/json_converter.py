import sys
import asyncio
import requests
import itertools
from typing import List
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from jsoner import json_write_sync
from tooler import ProxyParser

from src.console import console
from src.thon.base_session import BaseSession


class JsonConverter(BaseSession):
    def __init__(self):
        super().__init__()
        self.__api_id, self.__api_hash = 2040, "b18441a1ff607e10a989891a5462e627"
        proxy = ''
        if proxy == 'Без прокси':
            self.__proxy = None
            return
        try:
            proxy_parts = proxy.strip().split(':')[1:]
            if len(proxy_parts) == 4:
                ip, port, username, password = proxy_parts
                self.__proxy = ProxyParser(proxy).asdict_thon
                if not self.check_proxy(ip, port, username, password):
                    console.log("Прокси не работает, продолжаем без прокси", style="red")
                    self.__proxy = None
                    return
            else:
                raise ValueError("Неправильный формат прокси, продолжаем без него")
        except Exception as e:
            console.log(e, style="red")
            self.__proxy = None
            return

    def check_proxy(self, ip, port, username, password):
        proxies = {
            'http': f"socks5://{username}:{password}@{ip}:{port}",
            'https': f"socks5://{username}:{password}@{ip}:{port}"
        }
        try:
            response = requests.get('https://httpbin.org/ip', proxies=proxies, timeout=10)
            if response.status_code == 200:
                print("Прокси работает. Видимый IP:", response.json()['origin'])
                return True
            else:
                print("Прокси не отвечает, код состояния:", response.status_code)
                return False
        except requests.exceptions.RequestException as e:
            console.log(f"Ошибка при проверке прокси {e}")
            return False

    def _main(self, item: Path, json_file: Path, json_data: dict):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TelegramClient(str(item), self.__api_id, self.__api_hash)
        ss = StringSession()
        ss._server_address = client.session.server_address  # type: ignore
        ss._takeout_id = client.session.takeout_id  # type: ignore
        ss._auth_key = client.session.auth_key  # type: ignore
        ss._dc_id = client.session.dc_id  # type: ignore
        ss._port = client.session.port  # type: ignore
        string_session = ss.save()
        del ss, client
        json_data["proxy"] = self.__proxy
        json_data["string_session"] = string_session
        json_write_sync(json_file, json_data)

    def distribute_proxies(self, proxies: List[str], accounts_per_proxy: int):
        accounts = len(list(self.find_sessions()))
        proxy_cycle = itertools.cycle(proxies)
        distribution = {}

        for i in range(1, accounts + 1):
            proxy_index = (i - 1) // accounts_per_proxy
            proxy = proxies[proxy_index] if proxy_index < len(proxies) else proxies[-1]
            distribution[i] = proxy

        return distribution

    def main(self) -> int:
        count = 0
        for item, json_file, json_data in self.find_sessions():
            self._main(item, json_file, json_data)
            count += 1
        if not count:
            console.log("Нет аккаунтов в папке с сессиями!", style="yellow")
            sys.exit(1)
        return count
