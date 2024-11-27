import asyncio
from asyncio import Semaphore
from pathlib import Path
from typing import Generator

from tooler import move_item

from thon.base_session import BaseSession
from console import console
from src.commenter import Commenter


class Starter(BaseSession):
    def __init__(
        self,
        threads: int,
    ):
        self.semaphore = Semaphore(threads)
        super().__init__()

    async def _main(
        self,
        item: Path,
        json_file: Path,
        json_data: dict,
        config
    ):
        t = Commenter(
            item,
            json_file,
            json_data,
            config
        )
        async with self.semaphore:
            r = await t.main()
        if "OK" not in r:
            console.log(item.name, r, style="red")
        if "ERROR_AUTH" in r:
            move_item(item, self.banned_dir, True, True)
            move_item(json_file, self.banned_dir, True, True)
        if "ERROR_STORY" in r:
            move_item(item, self.errors_dir, True, True)
            move_item(json_file, self.errors_dir, True, True)
        if "OK" in r:
            console.log(item.name, r, style="green")

    def __get_sessions_and_users(self) -> Generator:
        for item, json_file, json_data in self.find_sessions():
            yield item, json_file, json_data

    async def main(self) -> bool:
        tasks = set()
        for item, json_file, json_data, users in self.__get_sessions_and_users():
            tasks.add(self._main(item, json_file, json_data, users))
        if not tasks:
            return False
        await asyncio.gather(*tasks, return_exceptions=True)
        return True
