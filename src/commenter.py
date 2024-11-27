import os
import asyncio
from pathlib import Path
from collections import deque

from telethon import events

from telethon.types import (
    InputPrivacyValueAllowUsers,
    InputUser,
    MessageMediaPhoto,
    User,
)

from thon.base_thon import BaseThon
from services.managers import ChannelManager
from services.console import console

class Commenter(BaseThon):
    def __init__(
        self,
        item: Path,
        json_file: Path,
        json_data: dict,
        config,
        channels: list,
    ):
        super().__init__(item=item, json_data=json_data)
        self.item = item
        self.config = config
        self.channels = channels
        self.json_file = json_file
        self.account_phone = os.path.basename(self.item).split('.')[0]
        self.channel_manager = ChannelManager(config)

    async def __main(self):
        await self.channel_manager.join_channels(self.client, self.channels, self.account_phone)
        console.log(f"Аккаунт {self.account_phone} успешно подключен и добавлен в очередь.")
        await self.channel_manager.monitor_channels(self.client, self.channels, self.account_phone)

    async def _main(self) -> str:
        r = await self.check()
        if "OK" not in r:
            return r
        await self.__main()
        return r

    async def main(self) -> str:
        r = await self._main()
        return r
