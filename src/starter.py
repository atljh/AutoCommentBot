import asyncio
from pathlib import Path
from asyncio import Semaphore
from typing import Generator

from tooler import move_item

from src.console import console
from src.commenter import Commenter
from src.managers import ChannelManager
from src.thon import BaseSession


class Starter(BaseSession):
    def __init__(
        self,
        threads: int,
        config
    ):
        self.semaphore = Semaphore(threads)
        self.channel_manager = ChannelManager(config)
        self.config = config
        super().__init__()

    async def _main(
        self,
        item: Path,
        json_file: Path,
        json_data: dict,
        config
    ):
        try:
            commenter = Commenter(item, json_file, json_data, config, self.channel_manager)
            async with self.semaphore:
                try:
                    r = await commenter.main()
                except Exception as e:
                    console.log(f"Ошибка при работе аккаунта {item}: {e}", style="red")
                    r = "ERROR_UNKNOWN"
            if "ERROR_AUTH" in r:
                console.log(f"Аккаунт {item.name} разлогинен или забанен", style="red")
                move_item(item, self.banned_dir, True, True)
                move_item(json_file, self.banned_dir, True, True)
            if "ERROR_STORY" in r:
                console.log(f"Ошибка при работе аккаунта {item.name}", style="red")
                move_item(item, self.errors_dir, True, True)
                move_item(json_file, self.errors_dir, True, True)
            if "OK" in r:
                console.log(f"Аккаунт {item.name} успешно прокомментировал посты.", style="green")
        except Exception as e:
            console.log(f"Ошибка при работе аккаунта {item}: {e}", style="red")

    def __get_sessions_and_users(self) -> Generator:
        for item, json_file, json_data in self.find_sessions():
            yield item, json_file, json_data

    async def main(self) -> bool:
        tasks = set()
        for item, json_file, json_data in self.__get_sessions_and_users():
            tasks.add(self._main(item, json_file, json_data, self.config))
        if not tasks:
            return False
        await asyncio.gather(*tasks, return_exceptions=True)
        return True
