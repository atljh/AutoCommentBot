import os
from pathlib import Path

from config import Config
from src.console import console
from src.thon import BaseThon
from src.managers import ChannelManager


from pathlib import Path

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
        
        self.base_dir = Path("accounts")
        self.spamblock_dir = self.base_dir / "spamblock"
        self.spamblock_dir.mkdir(exist_ok=True)

    async def __main(self):
        channels = await self.channel_manager.join_channels(
            self.client, self.account_phone, self.item, self.json_file, self.spamblock_dir
        )
        if "MUTE" in channels:
            return "MUTE"
        if "SPAMBLOCK" in channels:
            return "SPAMBLOCK"
        self.channel_manager.add_accounts_to_queue([self.account_phone])
        self.channel_manager.add_account({self.account_phone: self.client})
        console.log(
            f"Аккаунт {self.account_phone} успешно подключен и добавлен в очередь.",
            style="green"
        )
        try:
            await self.channel_manager.monitor_channels(
                self.client, self.account_phone, channels, self.item, self.json_file, self.spamblock_dir
            )
        except Exception as e:
            console.log(f'Ошибка {e}', style='yellow')
        return "OK"

    async def _main(self) -> str:
        r = await self.check()
        if "OK" not in r:
            return r
        r = await self.__main()
        await self.disconnect()
        return r

    async def main(self) -> str:
        r = await self._main()
        return r
