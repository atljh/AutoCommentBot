import os
import sys
import yaml
import shutil
import random
import asyncio
import logging
import requests
from pathlib import Path
from collections import deque
from typing import Tuple, List, Generator

from langdetect import detect
from pydantic import BaseModel, Field, field_validator

from telethon import TelegramClient, events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError, MsgIdInvalidError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from basethon.base_thon import BaseThon
from basethon.base_session import BaseSession
from basethon.json_converter import JsonConverter
from basethon.starter import Starter


from services.console import console
from tooler import move_item

class Config(BaseModel):
    api_id: int
    api_hash: str
    openai_api_key: str
    chat_gpt_model: str
    prompt_tone: str = Field(default="Дружелюбный", description="Тон ответа в комментарии")
    sleep_duration: int = Field(default=30, ge=0, description="Длительность паузы после лимита комментариев")
    comment_limit: int = Field(default=10, ge=1, description="Лимит комментариев на одного пользователя")
    join_channel_delay: Tuple[int, int] = Field(default=(10, 20), description="Диапазон задержки перед подпиской на канал")
    send_message_delay: Tuple[int, int] = Field(default=(10, 20), description="Задержка перед отправкой сообщения")
    random_prompt: bool = Field(default=False, description="Использовать рандомные пользовательские промпты")
    detect_language: bool = Field(default=False, description="Определять язык поста")
    
    @field_validator('api_id')
    def validate_api_id(cls, value):
        if not value:
            logging.error("api_id не найден")
            sys.exit(0)
        return value

    @field_validator('api_hash')
    def validate_api_hash(cls, value):
        if len(value) < 32:
            logging.error("api_hash должен быть длиной 32 символа")
            sys.exit(0)
        return value

    @field_validator('openai_api_key')
    def validate_openai_api_key(cls, value):
        if not value:
            logging.error("openai_api_key не найден")
            sys.exit(0)
        return value

class LoggerSetup:
    @staticmethod
    def setup_logger():
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        for lib_logger_name in logging.root.manager.loggerDict:
            if lib_logger_name != __name__:
                logging.getLogger(lib_logger_name).setLevel(logging.ERROR)
        return logger

class ConfigManager:
    @staticmethod
    def load_config(config_file='config.yaml') -> Config:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

            join_delay = config_data['settings'].get('join_channel_delay')
            send_message_delay = config_data['settings'].get('send_message_delay')

            if isinstance(join_delay, str) and '-' in join_delay:
                min_delay, max_delay = map(int, join_delay.split('-'))
                config_data['settings']['join_channel_delay'] = (min_delay, max_delay)

            if isinstance(send_message_delay, str) and '-' in send_message_delay:                
                min_delay, max_delay = map(int, send_message_delay.split('-'))
                config_data['settings']['send_message_delay'] = (min_delay, max_delay)


            return Config(**config_data['api'], **config_data['settings'])

              

# for session in sessions:
#     try:
#         client = TelegramClient(session, api_id, api_hash, proxy=proxy)
#         await client.connect()
#         account_phone = os.path.basename(session).split('.')[0]
#         if not await SessionManager.check_if_authorized(client, account_phone):
#             continue
#         await self.channel_manager.join_channels(client, channels, join_channel_delay, account_phone)
#         self.channel_manager.add_account(client, account_phone) 
#         logging.info(f"Аккаунт {account_phone} успешно подключен и добавлен в очередь.")
#     except Exception as e:
#         logging.error(f"Ошибка при настройке аккаунта {session}: {e}")


# if not self.channel_manager.account_queue:
#     logging.error("Не удалось добавить аккаунты в очередь. Завершение работы.")
#     return


# self.channel_manager.active_account = self.channel_manager.account_queue[0]
# logging.info("Ждем новые посты в каналах")

# await asyncio.gather(
#     *[self.channel_manager.monitor_channel(channel, prompt_tone, sleep_duration) for channel in channels],
#     *(client.run_until_disconnected() for client, _ in self.channel_manager.account_queue)
# )


async def _main():
    config = ConfigManager.load_config()
    sessions_count = JsonConverter().main()
    if not sessions_count:
        console.log("Нет аккаунтов в папке с сессиями!", style="yellow")
        sys.exit(1)
    if not config:
        logging.error("Ошибка загрузки конфигурации, завершение работы.")
        sys.exit(1)

        
        # prompt_tone = self.config.prompt_tone
        # sleep_duration = self.config.sleep_duration
        # join_channel_delay = self.config.join_channel_delay

        # channels = FileManager.read_channels()
if __name__ == "__main__":
    asyncio.run(_main())