import asyncio
import requests
from pathlib import Path

from jsoner import json_write_sync
from telethon import TelegramClient
from telethon.sessions import StringSession
from tooler import ProxyParser

from ask_from_history import ask_from_history
from thon.base_session import BaseSession
from console import console


class JsonConverter(BaseSession):
    def __init__(self):
        super().__init__()
        self.__api_id, self.__api_hash = 2040, "b18441a1ff607e10a989891a5462e627"
        prompt = "Введите прокси (формат socks5:ipaddr:port:user:pswd)"
        proxy = ask_from_history(prompt, console, Path("history_proxies.json"))
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
                raise ValueError("Неправильный формат прокси.")
        except Exception as e:
            console.log(e, style="red")
            raise SystemExit("Ошибка в настройке прокси.") from e

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

    def main(self) -> int:
        count = 0
        for item, json_file, json_data in self.find_sessions():
            self._main(item, json_file, json_data)
            count += 1
        return count
