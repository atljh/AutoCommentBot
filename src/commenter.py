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

class Commenter(BaseThon):
    is_donor_good: bool = True

    def __init__(
        self,
        item: Path,
        json_file: Path,
        json_data: dict,
        config
    ):
        super().__init__(json_data)        
        self.item, self.json_file = item, json_file
        self.config = config
        self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.comment_generator = CommentGenerator(config, self.openai_client)
        self.channel_manager = ChannelManager(config, self.comment_generator)
        self.active_accounts = []

    async def _main(self) -> str:
        r = await self.check()
        if "OK" not in r:
            return r
        me = await self.client.get_me()
        print(me)
        await self.disconnect()
        return r

    async def main(self) -> str:
        r = await self._main()
        print(r)
        return r
