import os
import sys
import shutil
import random
import asyncio
import logging
from time import sleep
from datetime import datetime
from dataclasses import dataclass

from openai import OpenAI
from telethon import TelegramClient, events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError, MsgIdInvalidError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

@dataclass
class Config:
    api_id: int
    api_hash: str
    openai_api_key: str
    prompt_tone: str = ""
    sleep_duration: int = 30
    comment_limit: int = 10
    join_channel_delay: int = 15
    use_users_prompts: bool = False
    random_prompt: bool = False


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
    def load_config(config_file='config.txt') -> Config:
        config_data = {}
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        config_data[key] = value
            return Config(
                api_id=int(config_data["api_id"]),
                api_hash=config_data["api_hash"],
                openai_api_key=config_data["openai_api_key"],
                prompt_tone=config_data.get("prompt_tone", ""),
                sleep_duration=int(config_data.get("sleep_duration", 30)),
                comment_limit=int(config_data.get("comment_limit", 10)),
                join_channel_delay=int(config_data.get("join_channel_delay", 15)),
                use_users_prompts=config_data.get("use_users_prompts", "False").lower() == "true",
                random_prompt=config_data.get("random_prompt", "False").lower() == "true"
            )
        except FileNotFoundError:
            logging.error("Файл config.txt не найден")
            return None


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
                    if line and not line.startswith("#"):  # Игнорируем комментарии
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
            logging.info(f"Клиент {account} не авторизован, сессия перемещена.")
            return False
        logging.info(f"Клиент {account} успешно авторизован.")
        return True


class CommentGenerator:
    def __init__(self, config, openai_client):
        self.config = config
        self.client = openai_client

    async def generate_prompt(self, post_text, prompt_tone, custom_prompt=None):
        if custom_prompt:
            prompt = custom_prompt.replace("{post_text}", post_text)
            if prompt_tone:
                prompt = prompt.replace("{prompt_tone}", prompt_tone)
        elif not prompt_tone:
            prompt = (f'''
            На основе следующего текста, напиши осознанный и позитивный комментарий.
            Текст поста: {post_text}''')
        else:
            prompt = (f'''
            Оригинальный пост: "{post_text}"
            Тон ответа: {prompt_tone}''')
        return prompt

    async def generate_comment(self, post_text, prompt_tone):
        use_users_prompts = bool(self.config.get("use_users_prompts"))
        random_prompt = bool(self.config.get("random_prompt"))
        custom_prompt = None

        if use_users_prompts:
            custom_prompts = FileManager.read_prompts()
            custom_prompt = random.choice(custom_prompts) if random_prompt else custom_prompts[0] if custom_prompts else None

        prompt = await self.generate_prompt(post_text, prompt_tone, custom_prompt)

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                n=1,
                temperature=0.7)
            comment = response.choices[0].message.content
            logging.info(f"Сгенерирован комментарий: {comment}")
            return comment
        except Exception as e:
            logging.error(f"Ошибка генерации комментария: {e}")
            return None


class ChannelManager:
    def __init__(self, config, comment_generator):
        self.config = config
        self.comment_generator = comment_generator
        self.post_commenting_accounts = {}

    async def is_participant(self, client, channel):
        try:
            await client.get_permissions(channel, 'me')
            return True
        except UserNotParticipantError:
            return False

    async def join_channels(self, client, channels, join_channel_delay):
        for channel in channels:
            try:
                entity = await client.get_entity(channel)
                if await self.is_participant(client, entity):
                    logging.info(f"Клиент уже состоит в канале {channel}")
                    continue
            except Exception:
                try:
                    await asyncio.sleep(join_channel_delay)
                    await client(ImportChatInviteRequest(channel[6:]))
                    logging.info(f"Клиент присоединился к приватному каналу {channel}")
                except Exception as e:
                    logging.error(f"Ошибка при присоединении к каналу {channel}: {e}")
                    continue
            try:
                await asyncio.sleep(join_channel_delay)
                await client(JoinChannelRequest(channel))
                logging.info(f"Клиент присоединился к каналу {channel}")
            except Exception as e:
                logging.error(f"Ошибка при подписке на канал {channel}: {e}")

    async def monitor_channel(self, client, channel, prompt_tone, sleep_duration, account, comment_limit):
        comment_counter = 0

        @client.on(events.NewMessage(chats=channel))
        async def new_post_handler(event):
            nonlocal comment_counter
            account_phone = account.split('.')[0]
            message_id = event.message.id
            post_text = event.message.message

            if message_id in self.post_commenting_accounts:
                logging.info(f"Пропущен пост {message_id} - уже прокомментирован другим аккаунтом.")
                return

            comment = await self.comment_generator.generate_comment(post_text, prompt_tone)
            if not comment:
                return

            try:
                channel_entity = await client.get_entity(channel)
                full_channel = await client(GetFullChannelRequest(channel=channel_entity))

                if not full_channel.full_chat.linked_chat_id:
                    logging.info(f"Канал {channel} не связан с обсуждением, пропуск.")
                    return

                await client.send_message(
                    entity=channel,
                    message=comment,
                    comment_to=message_id
                )
                self.post_commenting_accounts[message_id] = account
                logging.info(f"Комментарий отправлен в пост {message_id} аккаунтом {account_phone}")

                comment_counter += 1
                if comment_counter >= comment_limit:
                    logging.info(f"Аккаунт {account_phone} достиг лимита комментариев, пауза на {sleep_duration} секунд.")
                    await asyncio.sleep(sleep_duration)
                    comment_counter = 0
            except (FloodWaitError, UserBannedInChannelError, MsgIdInvalidError, Exception) as e:
                logging.error(f"Ошибка при отправке комментария: {e}")


class TelegramBot:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.openai_api_key)
        self.comment_generator = CommentGenerator(config, self.client)
        self.channel_manager = ChannelManager(config, self.comment_generator)
        self.active_accounts = []

    async def main(self):
        logging.info("Скрипт запущен")
        api_id = self.config.api_id
        api_hash = self.config.api_hash
        prompt_tone = self.config.prompt_tone
        sleep_duration = self.config.sleep_duration
        comment_limit = self.config.comment_limit
        join_channel_delay = self.config.join_channel_delay
        
        channels = FileManager.read_channels()
        sessions = FileManager.read_sessions()
        proxy = FileManager.read_proxy()
        for session in sessions:
            try:
                client = TelegramClient(session, api_id, api_hash, proxy=proxy)
                await client.connect()
                account_phone = session.split('.')[0]
                if not await SessionManager.check_if_authorized(client, account_phone):
                    continue
                await self.channel_manager.join_channels(client, channels, join_channel_delay)
                for channel in channels:
                    await self.channel_manager.monitor_channel(
                        client, channel, prompt_tone, sleep_duration, account_phone, comment_limit
                    )
                self.active_accounts.append(client)
                logging.info(f"Аккаунт {account_phone} успешно подключен и настроен.")
            except Exception as e:
                logging.error(f"Ошибка при настройке клиента {session}: {e}")

        if self.active_accounts:
            logging.info("Запуск всех подключённых аккаунтов...")
            await asyncio.gather(*[client.run_until_disconnected() for client in self.active_accounts])
            logging.info("Все аккаунты завершили выполнение.")


if __name__ == "__main__":
    logger = LoggerSetup.setup_logger()
    config = ConfigManager.load_config()
    if not config:
        logging.error("Ошибка загрузки конфигурации, завершение работы.")
        sys.exit(1)

    bot = TelegramBot(config)
    asyncio.run(bot.main())