import os
import shutil
import asyncio
import logging

from time import sleep
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import UserNotParticipantError, FloodWaitError
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


def read_groups():
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

async def generate_comment(post_text, prompt_tone):
    # prompt = f"{prompt_tone}: {post_text}"
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

    Текст поста: {post_text}'''

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
        sleep(10)
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
            sleep(1)
            await client.send_message(
                entity=channel,
                message=comment,
                comment_to=message_id
            )
            logging.info(f"Комментарий отправлен в группу {linked_group.title}")
        except FloodWaitError as e:
            logging.warning(f"Флуд-таймаут: {e}")
        except Exception as e:
            logging.error(f"Ошибка отправки комментария в группу {linked_group.title}: {e}")

        if comment_limit <= 0:
            logging.info(f"Аккаунт переходит в режим сна на {sleep_duration} секунд")
            await asyncio.sleep(sleep_duration)


async def join_channels(client, groups):
    for group in groups:
        logging.info(f"Проверяем подписку на канал: {group}")
        try:
            entity = await client.get_entity(group)

            if await is_participant(client, entity):
                logging.info(f"Уже подписан на канал: {group}")
                continue

            if entity.id == -1001583001812:
                logging.warning("Нельзя комментировать в этом чате")
                continue

        except Exception as e:
            logging.error(f"Ошибка получения канала {group}: {e}")
            try:
                await client(ImportChatInviteRequest(group[5:]))
            except Exception as invite_err:
                logging.error(f"Ошибка запроса на подписку: {invite_err}")
            else:
                logging.info(f"Приватный чат: {group}. Отправлен запрос на подписку")
                continue
        try:
            await client(JoinChannelRequest(group))
            logging.info(f"Успешно подписано на канал: {group}")
        except Exception as e:
            logging.error(f"Ошибка при подписке на канал {group}: {e}")

config = get_config()

client = OpenAI(api_key=config["openai_api_key"])

async def main():
    api_id = int(config["api_id"])
    api_hash = config["api_hash"]
    prompt_tone = config.get("prompt_tone", "Создай дружелюбный комментарий")
    comment_limit = int(config.get("comment_limit", 5))
    sleep_duration = int(config.get("sleep_duration", 3600))

    accounts = read_sessions()
    if not accounts:
        logging.warning("Сессии не найдены")
        return

    for account in accounts:
        proxy = get_proxy()
        client = TelegramClient(account, api_id, api_hash, proxy=proxy)

        await client.connect()
        if not await client.is_user_authorized():
            logging.warning(f"Аккаунт {account[9:]} разлогигнен, перемещаем аккаунт и начинаем другую сессию.")
            continue
        logging.info(f"Успешно авторизировано в аккаунт {account[9:]}")
        try:
            groups = read_groups()
            await join_channels(client, groups)
            logging.info("Ждем новый пост в каналах")
            for group in groups:
                client.loop.create_task(monitor_channel(client, group, prompt_tone, comment_limit, sleep_duration))
        except Exception as e:
            logging.error(f"Ошибка: {e}")

    await client.run_until_disconnected()


if __name__ == "__main__":
    logging.info("Запуск скрипта")
    asyncio.run(main())
    logging.info("Завершение работы скрипта")
