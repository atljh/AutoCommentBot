import os
from pathlib import Path

from config import Config
from src.console import console
from src.thon import BaseThon
from src.managers import ChannelManager

class Commenter(BaseThon):
    def __init__(
        self,
        item: Path,
        json_file: Path,
        json_data: dict,
        config: Config,
        channel_manager: ChannelManager
    ):
        super().__init__(item=item, json_data=json_data)
        self.item = item
        self.config = config
        self.json_file = json_file
        self.account_phone = os.path.basename(self.item).split('.')[0]
        self.channel_manager = channel_manager
        self.channel_manager.add_accounts_to_queue([self.account_phone])
        self.channel_manager.add_account({self.account_phone: self.client})

    async def __main(self):
        await self.channel_manager.join_channels(self.client, self.account_phone)
        console.log(f"Аккаунт {self.account_phone} успешно подключен и добавлен в очередь.", style="green")
        await self.channel_manager.monitor_channels(self.client, self.account_phone)

    async def _main(self) -> str:
        r = await self.check()
        if "OK" not in r:
            return r
        await self.__main()
        return r

    async def main(self) -> str:
        r = await self._main()
        return r
