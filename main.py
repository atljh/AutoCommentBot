import os
import sys
import shutil
import asyncio
import logging

from time import sleep
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from openai import OpenAI


CONFIG_FILE = 'config.txt'
GROUPS_FILE = 'groups.txt'
PROXIES_FILE = 'proxies.txt'
SESSIONS_PATH = "accounts/"


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

def get_config():
    config = {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
        return config
    except FileNotFoundError:
        logging.error("Файл config.txt не найден")
        return None

def read_channels():
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            return [line.strip().replace("https://", "") for line in f.readlines()]
    except FileNotFoundError:
        logging.error("Файл groups.txt не найден")
        return None

def read_sessions():
    accounts = [os.path.join(SESSIONS_PATH, f) for f in os.listdir(SESSIONS_PATH) if f.endswith('.session')]
    return accounts

def get_proxy():
    try:
        with open(PROXIES_FILE, 'r', encoding='utf-8') as f:
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

def move_session(session_path, reason):
    target_dir = os.path.join(SESSIONS_PATH, reason)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    basename = os.path.basename(session_path)
    target_path = os.path.join(target_dir, basename)
    shutil.move(session_path, target_path)

async def is_participant(client, channel) -> bool:
    try:
        await client.get_permissions(channel, 'me')
        return True
    except UserNotParticipantError:
        return False

async def check_if_authorized(client, account) -> bool:
    if not (await client.is_user_authorized()):
        await client.disconnect()
        move_session(account, 'razlog')
        return False
    return True

async def generate_prompt(post_text, prompt_tone):
    if not prompt_tone:
        prompt = f'''
        На основе следующего текста,
        напиши осознанный и позитивный комментарий.
        Сделай его вежливым и поддерживающим,
        используй эмодзи, чтобы передать эмоции
        и показать заинтересованность.
        Вырази благодарность за предоставленную информацию
        и задай вопрос, чтобы продолжить обсуждение.
        Учитывай, что это должен быть дружелюбный
        и конструктивный ответ, который поддерживает
        тему поста и мотивирует автора.
        Ответ должен быть в пару предложений и простой в чтении.
        Важное примечание: Определи язык оригинального поста и ответь на этом же языке.
        Если пост на русском, ответь на русском;
        если на английском — ответь на английском и так далее.
        Сделай так, чтобы ответ выглядел естественным и уместным в контексте разговора.
        
        Текст поста: {post_text}'''
        return prompt
    
    prompt = f'''
    Ты — человек, пол выбери сам, специализирующийся на создании осмысленных и контекстуально подходящих ответов на комментарии в Telegram-чатах.
    Твоя задача — ответить на следующий пост, используя указанный тон.
    Прими во внимание тональность, контекст и детали оригинального поста
    и добавь тонкий намёк на заданный подтекст в свой ответ.

    Оригинальный пост: "{post_text}"

    Тон ответа: {prompt_tone}
    Важное примечание: Определи язык оригинального поста и ответь на этом же языке.
    Если пост на русском, ответь на русском; если на английском — ответь на английском и так далее.
    Сделай так, чтобы ответ выглядел естественным и уместным в контексте разговора.
    Напиши вдумчивый и короткий ответ, делая акцент на тон ответа.
    Вернуть ты должен только текст ответа
    '''
    return prompt

async def generate_comment(post_text, prompt_tone):

    prompt = await generate_prompt(post_text, prompt_tone)

    try:
        response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        n=1,
        temperature=0.7)
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Ошибка генерации комментария: {e}")
        return False

async def monitor_channel(client, channel, prompt_tone, comment_limit, sleep_duration):
    @client.on(events.NewMessage(chats=channel))
    async def new_post_handler(event):
        logging.info(f"Новый пост в канале {channel}")
        post_text = event.message.message
        message_id = event.message.id
        comment = await generate_comment(post_text, prompt_tone)
        if not comment:
            return
        try:
            channel_entity = await client.get_entity(channel)
            full_channel = await client(GetFullChannelRequest(channel=channel_entity))

            if not full_channel.full_chat.linked_chat_id:
                logging.warning(f"Канал {channel} не связан с группой.")
                return

            linked_group = await client.get_entity(full_channel.full_chat.linked_chat_id)
            
            await client.send_message(
                entity=channel,
                message=comment,
                comment_to=message_id
            )
            logging.info(f"Комментарий отправлен в группу {linked_group.title}")
        except FloodWaitError as e:
            logging.warning(f"Флуд-таймаут: {e}")
        except KeyboardInterrupt:
            logging.info("Завершение работы скрипта")
            sys.exit(0)
        except UserBannedInChannelError:
            logging.info(f"Нельзя отправить сообщение, вы забанены в этом чате: {channel}")
        # except Exception as e:
            # logging.error(f"Ошибка отправки комментария в группу {linked_group.title}: {e}")

        if comment_limit <= 0:
            logging.info(f"Аккаунт переходит в режим сна на {sleep_duration} секунд")
            await asyncio.sleep(sleep_duration)


async def join_channels(client, channels, join_channel_delay):
    for channel in channels:
        logging.info(f"Проверяем подписку на канал: {channel}")
        try:
            entity = await client.get_entity(channel)

            if await is_participant(client, entity):
                logging.info(f"Уже подписан на канал: {channel}")
                continue

        except Exception as e:
            logging.error(f"Ошибка получения канала {channel}: {e}")
            try:
                logging.info(f"Зарежка {join_channel_delay} сек перед подпиской на канал")
                await asyncio.sleep(join_channel_delay)
                await client(ImportChatInviteRequest(channel[5:]))
            except Exception as invite_err:
                logging.error(f"Ошибка запроса на подписку: {invite_err}")
            else:
                logging.info(f"Приватный чат: {channel}. Отправлен запрос на подписку")
                continue
        try:
            logging.info(f"Зарежка {join_channel_delay} сек перед подпиской на канал")
            await asyncio.sleep(join_channel_delay)
            await client(JoinChannelRequest(channel))
            logging.info(f"Успешно подписано на канал: {channel}")
        except Exception as e:
            logging.error(f"Ошибка при подписке на канал {channel}: {e}")

config = get_config()

client = OpenAI(api_key=config["openai_api_key"])

async def main():
    api_id = int(config["api_id"])
    api_hash = config["api_hash"]
    prompt_tone = config.get("prompt_tone") if len(config.get("prompt_tone")) else None
    comment_limit = int(config.get("comment_limit", 5))
    sleep_duration = int(config.get("sleep_duration", 3600))
    join_channel_delay = int(config.get("join_channel_delay", 10))

    proxy = get_proxy()
    accounts = read_sessions()
    if not accounts:
        logging.warning("Сессии не найдены")
        return
    logging.info(f"Аккаунтов найдено: {len(accounts)}")
    for index, account in enumerate(accounts):
        client = TelegramClient(account, api_id, api_hash, proxy=proxy)
        await client.connect()
        if not await client.is_user_authorized():
            logging.warning(f"Аккаунт {account[9:].split('.')[0]} разлогигнен, перемещаем аккаунт и начинаем другую сессию.")
            continue
        logging.info(f"Успешно авторизировано в аккаунт {account[9:].split('.')[0]} ({index+1}/{len(accounts)})")
        try:
            channels = read_channels()
            await join_channels(client, channels, join_channel_delay)
            logging.info("Ждем новый пост в каналах")
            for channel in channels:
                client.loop.create_task(monitor_channel(client, channel, prompt_tone, comment_limit, sleep_duration))
        except KeyboardInterrupt:
            logging.info("Завершение работы скрипта")
            sys.exit(0)
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    await client.run_until_disconnected()


if __name__ == "__main__":
    logging.info("Запуск скрипта")
    asyncio.run(main())
    logging.info("Завершение работы скрипта")
