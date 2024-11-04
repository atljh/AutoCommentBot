import os
import sys
import yaml
import shutil
import random
import asyncio
import logging
import requests
from collections import deque

from openai import OpenAI
from langdetect import detect
from pydantic import BaseModel, Field, field_validator

from telethon import TelegramClient, events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError, MsgIdInvalidError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

class Config(BaseModel):
    api_id: int
    api_hash: str
    openai_api_key: str
    chat_gpt_model: str
    prompt_tone: str = Field(default="Дружелюбный", description="Тон ответа в комментарии")
    sleep_duration: int = Field(default=30, ge=0, description="Длительность паузы после лимита комментариев")
    comment_limit: int = Field(default=10, ge=1, description="Лимит комментариев на одного пользователя")
    join_channel_delay: int = Field(default=15, ge=0, description="Задержка перед подпиской на канал")
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
        return Config(**config_data['api'], **config_data['settings'])

class FileManager:
    @staticmethod
    def read_channels(file='groups.txt'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return [line.strip().replace("https://", "") for line in f.readlines()]
        except FileNotFoundError:
            logging.error("Файл groups.txt не найден")
            return None

    @staticmethod
    def read_sessions(directory='accounts/'):
        return [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.session')]

    @staticmethod
    def read_prompts(file='prompts.txt'):
        prompts = []
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        prompts.append(line)
            return prompts
        except FileNotFoundError:
            logging.error("Файл prompts.txt не найден")
            return []

    @staticmethod
    def read_proxy(file='proxies.txt'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    proxy_parts = line.strip().split(':')
                    if len(proxy_parts) == 4:
                        ip, port, username, password = proxy_parts
                        return {
                            'proxy_type': 'socks5',
                            'addr': ip,
                            'port': int(port),
                            'username': username,
                            'password': password
                        }
            return None
        except FileNotFoundError:
            logging.error("Файл proxies.txt не найден")
            return None

    @staticmethod
    def check_proxy(proxy):
        proxies = {
            'http': f"socks5://{proxy['username']}:{proxy['password']}@{proxy['addr']}:{proxy['port']}",
            'https': f"socks5://{proxy['username']}:{proxy['password']}@{proxy['addr']}:{proxy['port']}"
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
            
class SessionManager:
    @staticmethod
    def move_session(session_path, reason, directory='accounts/'):
        target_dir = os.path.join(directory, reason)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        basename = os.path.basename(session_path)
        target_path = os.path.join(target_dir, basename)
        shutil.move(session_path, target_path)
        logging.info(f"Сессия {session_path} перемещена в папку {target_dir} по причине '{reason}'")

    @staticmethod
    async def check_if_authorized(client, account):
        if not (await client.is_user_authorized()):
            await client.disconnect()
            SessionManager.move_session(client.session.filename, 'razlog')
            logging.info(f"Аккаунт {account} не авторизован, сессия перемещена.")
            return False
        logging.info(f"Аккаунт {account} успешно авторизован.")
        return True


class CommentGenerator:
    def __init__(self, config, openai_client):
        self.config = config
        self.client = openai_client
        self.prompts = self.load_prompts()

    def load_prompts(self):
        return FileManager.read_prompts()

    def detect_language(self, text):
        try:
            language = detect(text)
            return language
        except Exception as e:
            logging.error(f"Ошибка определения языка: {e}")
            return "ru" 
        
    async def generate_prompt(self, post_text, prompt_tone):

        if not len(self.prompts):
            logging.warning("Промпт не найден")
            return None
        
        random_prompt = bool(self.config.random_prompt)
        prompt = random.choice(self.prompts) if random_prompt else self.prompts[0] if self.prompts else None
        post_language = self.detect_language(post_text)
        
        prompt = prompt.replace("{post_text}", post_text)
        prompt = prompt.replace("{prompt_tone}", prompt_tone)
        if self.config.detect_language:
            prompt = prompt.replace("{post_lang}", post_language)

        return prompt

    async def generate_comment(self, post_text, prompt_tone):
        prompt = await self.generate_prompt(post_text, prompt_tone)
        if not prompt:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.chat_gpt_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                n=1,
                temperature=0.7)
            comment = response.choices[0].message.content
            return comment
        except Exception as e:
            logging.error(f"Ошибка генерации комментария: {e}")
            return None


class ChannelManager:
    def __init__(self, config, comment_generator):
        self.config = config
        self.comment_generator = comment_generator
        self.account_queue = deque()
        self.comment_limits = {}
        self.sleep_durations = {}
        self.active_account = None 


    async def is_participant(self, client, channel):
        try:
            await client.get_permissions(channel, 'me')
            return True
        except UserNotParticipantError:
            return
        except Exception as e:
            logging.error(f"Ошибка при обработке канала {channel}: {e}")
            return

    async def join_channels(self, client, channels, join_channel_delay, account_phone):
        for channel in channels:
            try:
                entity = await client.get_entity(channel)
                if await self.is_participant(client, entity):
                    logging.info(f"Аккаунт {account_phone} уже состоит в канале {channel}")
                    continue
            except Exception:
                try:
                    logging.info(f"Задержка перед подпиской на канал {join_channel_delay} сек")
                    await asyncio.sleep(join_channel_delay)
                    await client(ImportChatInviteRequest(channel[6:]))
                    logging.info(f"Аккаунт присоединился к приватному каналу {channel}")
                    continue
                except Exception as e:
                    logging.error(f"Ошибка при присоединении к каналу {channel}: {e}")
                    continue
            try:
                logging.info(f"Задержка перед подпиской на канал {join_channel_delay} сек")
                await asyncio.sleep(join_channel_delay)
                await client(JoinChannelRequest(channel))
                logging.info(f"Аккаунт присоединился к каналу {channel}")
            except Exception as e:
                logging.error(f"Ошибка при подписке на канал {channel}: {e}")

    def add_account(self, client, account_phone):
        self.account_queue.append((client, account_phone))
        self.comment_limits[account_phone] = self.config.comment_limit
        self.sleep_durations[account_phone] = 0 

    async def rotate_account(self):
        while True:
            self.account_queue.rotate(-1)
            current_client, account_phone = self.account_queue[0]
            
            if self.sleep_durations[account_phone] == 0:
                break
            else:
                await asyncio.sleep(self.sleep_durations[account_phone])
                logging.info(f'Аккаунт {account_phone} выходит с режима сна.')
            self.comment_limits[account_phone] = self.config.comment_limit

        return current_client, account_phone

    async def monitor_channel(self, channel, prompt_tone, sleep_duration):
        current_client, account_phone = await self.rotate_account()

        @current_client.on(events.NewMessage(chats=channel))
        async def new_post_handler(event):
            nonlocal account_phone, current_client
            post_text = event.message.message
            message_id = event.message.id

            logging.info(f"Новый пост в канале {channel}")

            if self.comment_limits[account_phone] <= 0:
                self.sleep_durations[account_phone] = sleep_duration
                logging.info(f"Аккаунт {account_phone} достиг лимита комментариев. Переход к следующему аккаунту.")
                current_client, account_phone = await self.rotate_account()

            comment = await self.comment_generator.generate_comment(post_text, prompt_tone)
            if not comment:
                return

            try:
                await current_client.send_message(
                    entity=channel,
                    message=comment,
                    comment_to=message_id
                )
                logging.info(f"Комментарий отправлен от аккаунта {account_phone} в канал {channel}")

                self.comment_limits[account_phone] -= 1
                if self.comment_limits[account_phone] <= 0:
                    self.sleep_durations[account_phone] = sleep_duration
                    logging.info(f"Аккаунт {account_phone} достиг лимита и переходит в сон на {sleep_duration} секунд.")
                    current_client, account_phone = await self.rotate_account()

            except FloodWaitError as e:
                logging.warning(f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.")
                self.sleep_durations[account_phone] = e.seconds
                current_client, account_phone = await self.rotate_account()
                
            except UserBannedInChannelError:
                logging.warning(f"Аккаунт {account_phone} заблокирован в канале {channel}")
            except MsgIdInvalidError:
                logging.warning("Канал не связан с чатом")
            except Exception as e:
                logging.error(f"Ошибка при отправке комментария: {e}")
                
class TelegramBot:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.comment_generator = CommentGenerator(config, self.client)
        self.channel_manager = ChannelManager(config, self.comment_generator)
        self.active_accounts = []

    async def main(self):
        api_id = self.config.api_id
        api_hash = self.config.api_hash
        prompt_tone = self.config.prompt_tone
        sleep_duration = self.config.sleep_duration
        join_channel_delay = self.config.join_channel_delay

        channels = FileManager.read_channels()
        sessions = FileManager.read_sessions()
        proxy = FileManager.read_proxy()
        logging.info(f"Скрипт запущен. Сессий найдено: {len(sessions)}")

        if proxy and FileManager.check_proxy(proxy):
            logging.info("Прокси успешно проверен и будет использован.")
        else:
            logging.error("Прокси не прошел проверку или не найден. Работа будет продолжена без него.")
            proxy = None

        for session in sessions:
            try:
                client = TelegramClient(session, api_id, api_hash, proxy=proxy)
                await client.connect()
                account_phone = os.path.basename(session).split('.')[0]
                if not await SessionManager.check_if_authorized(client, account_phone):
                    continue
                await self.channel_manager.join_channels(client, channels, join_channel_delay, account_phone)
                self.channel_manager.add_account(client, account_phone) 
                logging.info(f"Аккаунт {account_phone} успешно подключен и добавлен в очередь.")
            except Exception as e:
                logging.error(f"Ошибка при настройке аккаунта {session}: {e}")


        if not self.channel_manager.account_queue:
            logging.error("Не удалось добавить аккаунты в очередь. Завершение работы.")
            return


        self.channel_manager.active_account = self.channel_manager.account_queue[0]
        logging.info("Ждем новые посты в каналах")

        await asyncio.gather(
            *[self.channel_manager.monitor_channel(channel, prompt_tone, sleep_duration) for channel in channels],
            *(client.run_until_disconnected() for client, _ in self.channel_manager.account_queue)
        )

if __name__ == "__main__":
    logger = LoggerSetup.setup_logger()
    config = ConfigManager.load_config()
    if not config:
        logging.error("Ошибка загрузки конфигурации, завершение работы.")
        sys.exit(1)

    bot = TelegramBot(config)
    asyncio.run(bot.main())