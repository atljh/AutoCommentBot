import os
from pathlib import Path

from openai import OpenAI

from telethon.functions import stories
from telethon.types import (
    InputPrivacyValueAllowUsers,
    InputUser,
    MessageMediaPhoto,
    User,
)

from thon.base_thon import BaseThon
from services.managers import ChannelManager, CommentGenerator
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
        self.json_file = json_file
        self.config = config
        self.channels = channels
        self.prompt_tone = self.config.prompt_tone
        self.sleep_duration = self.config.sleep_duration
        self.join_channel_delay = self.config.join_channel_delay
        self.account_phone = os.path.basename(self.item).split('.')[0]
        self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.comment_generator = CommentGenerator(config, self.openai_client)
        self.channel_manager = ChannelManager(config, self.comment_generator)
        self.active_accounts = []
    
    async def __main(self):
        for channel in self.channels:
            await self.channel_manager.monitor_channel(channel, self.prompt_tone, self.sleep_duration)

    async def _main(self) -> str:
        r = await self.check()
        if "OK" not in r:
            return r
        await self.channel_manager.join_channels(self.client, self.channels, self.join_channel_delay, self.account_phone)
        self.channel_manager.add_account(self.client, self.account_phone) 
        console.log(f"Аккаунт {self.account_phone} успешно подключен и добавлен в очередь.")
        await self.__main()
        return r

    async def main(self) -> str:
        r = await self._main()
        return r
