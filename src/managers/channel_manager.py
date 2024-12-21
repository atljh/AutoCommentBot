import random
import asyncio
import logging
from typing import List
from collections import deque

from openai import OpenAI
from telethon import events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError, MsgIdInvalidError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from src.console import console
from .file_manager import FileManager
from .comment_manager import CommentManager

class ChannelManager:
    MAX_SEND_ATTEMPTS = 3 

    def __init__(self, config):
        self.config = config
        self.prompt_tone = self.config.prompt_tone
        self.sleep_duration = self.config.sleep_duration
        self.comment_limit = self.config.comment_limit
        self.join_channel_delay = self.config.join_channel_delay
        self.send_comment_delay = self.config.send_message_delay
        self.channels = FileManager.read_channels()
        self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.comment_manager = CommentManager(config, self.openai_client)

        self.account_comment_count = {}
        self.accounts = {}

        self.active_account = None 
        self.account_queue = deque()
        self.stop_event = asyncio.Event()

    def add_accounts_to_queue(self, accounts: List[str]):
        for account in accounts:
            self.account_queue.append(account)
        if not self.active_account and self.account_queue:
            self.active_account = self.account_queue.popleft()
    
    def add_account(self, account: dict):
        self.accounts.update(account)

    async def switch_to_next_account(self):
        if self.active_account:
            self.account_queue.append(self.active_account) 
        if self.account_queue:
            self.active_account = self.account_queue.popleft()
            console.log(f"Смена активного аккаунта на {self.active_account}", style="green")
        else:
            console.log("Все аккаунты завершили работу", style="yellow")
            self.stop_event.set() 

    async def sleep_account(self, account_phone):
        sleep_time = self.sleep_duration
        console.log(f"Аккаунт {account_phone} будет в режиме сна на {sleep_time} секунд...", style="yellow")
        await asyncio.sleep(sleep_time)
        self.account_comment_count[account_phone] = 0
        console.log(f"Аккаунт {account_phone} проснулся и готов продолжать.", style="green")

    async def is_participant(self, client, channel):
            try:
                await client.get_permissions(channel, 'me')
                return True
            except UserNotParticipantError:
                return False
            except Exception as e:
                console.log(f"Ошибка при обработке канала {channel}: {e}")
                return False
        
    async def sleep_before_send_message(self):
        min_delay, max_delay = self.send_comment_delay
        delay = random.randint(min_delay, max_delay)
        console.log(f"Задержка перед отправкой сообщения {delay} сек")
        await asyncio.sleep(delay)

    async def sleep_before_enter_channel(self):
        min_delay, max_delay = self.join_channel_delay
        delay = random.randint(min_delay, max_delay)
        console.log(f"Задержка перед подпиской на канал {delay} сек")
        await asyncio.sleep(delay)

    async def join_channels(self, client, account_phone):
        for channel in self.channels:
            try:
                entity = await client.get_entity(channel)
                if await self.is_participant(client, entity):
                    continue
            except Exception:
                try:
                    await self.sleep_before_enter_channel()
                    await client(ImportChatInviteRequest(channel[6:]))
                    console.log(f"Аккаунт {account_phone} присоединился к приватному каналу {channel}")
                    continue
                except Exception as e:
                    if "is not valid anymore" in str(e):
                        console.log("Вы забанены в канале")
                        continue
                    elif "A wait of" in str(e):
                        console.log(f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow")
                        continue
                    else:
                        console.log(f"Ошибка при присоединении к каналу {channel}: {e}")
                        continue
            try:
                await self.sleep_before_enter_channel()
                await client(JoinChannelRequest(channel))
                console.log(f"Аккаунт присоединился к каналу {channel}")
            except Exception as e:
                if "A wait of" in str(e):
                    console.log(f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow")
                    continue
                else:
                    console.log(f"Ошибка при подписке на канал {channel}: {e}")
                    
    async def monitor_channels(self, client, account_phone):
        for channel in self.channels:
            client.add_event_handler(
                lambda event: self.new_post_handler(client, event, self.prompt_tone, account_phone),
                events.NewMessage(chats=channel)
            )
        console.log(f"Мониторинг каналов начался для аккаунта {account_phone}...")
        await self.stop_event.wait()

    async def get_channel_entity(self, client, channel):
        try:
            return await client.get_entity(channel)
        except Exception as e:
            console.log(f"Ошибка получения объекта канала: {e}", style="red")
            return None

    async def send_comment(self, client, account_phone, channel, comment, message_id, attempts=0):
        try:
            channel_entity = await self.get_channel_entity(client, channel)
            if not channel_entity:
                console.log("Канал не найден или недоступен.", style="red")
                return
            await client.send_message(
                entity=channel_entity,
                message=comment,
                comment_to=message_id
            )
            console.log(f"Комментарий отправлен от аккаунта {account_phone} в канал {channel.title}", style="green")
            self.account_comment_count[account_phone] = self.account_comment_count.get(account_phone, 0) + 1
            if self.account_comment_count[account_phone] >= self.comment_limit:
                await self.switch_to_next_account()
                await self.sleep_account(account_phone)
        except FloodWaitError as e:
            logging.warning(f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow")
            await asyncio.sleep(e.seconds)
            await self.switch_to_next_account()
        except UserBannedInChannelError:
            console.log(f"Аккаунт {account_phone} заблокирован в канале {channel.title}", style="red")
            await self.switch_to_next_account()
        except MsgIdInvalidError:
            console.log("Канал не связан с чатом", style="red")
            await self.switch_to_next_account()
        except Exception as e:
            if "private and you lack permission" in str(e):
                console.log(f"Канал {channel.title} недоступен для аккаунта {account_phone}. Пропускаем.", style="yellow")
            elif "You can't write" in str(e):
                console.log(f"Канал {channel.title} недоступен для аккаунта {account_phone}. Пропускаем.", style="yellow")
            elif "You join the discussion group before commenting" in str(e):
                console.log("Для комментирование необходимо вступить в группу.")
                join_result = await self.join_discussion_group(client, channel_entity)
                if join_result:
                    await self.send_comment(client, account_phone, channel, comment, message_id)
                    return
                else:
                    return
            else:
                console.log(f"Ошибка при отправке комментария: {e}", style="red")
            
            if attempts < self.MAX_SEND_ATTEMPTS:
                console.log(f"Попытка {attempts + 1}/{self.MAX_SEND_ATTEMPTS} отправить сообщение c другого аккаунта...")
                await self.switch_to_next_account()
                next_client = self.accounts.get(self.active_account)
                if next_client:
                    await self.sleep_before_send_message()
                    await self.send_comment(next_client, account_phone, channel, comment, message_id, attempts + 1)
                else:
                    console.log("Нет доступных аккаунтов для отправки.", style="red")
            else:
                console.log(f"Не удалось отправить сообщение после {self.MAX_SEND_ATTEMPTS} попыток.", style="red")


    async def join_discussion_group(self, client, channel_entity):
        try:
            full_channel = await client(GetFullChannelRequest(channel=channel_entity))
            
            linked_chat_id = full_channel.full_chat.linked_chat_id
            if not linked_chat_id:
                console.log(f"Канал {channel_entity.title} не связан с группой.", style="bold yellow")
                return
            
            linked_group = await client.get_entity(linked_chat_id)
            console.log(f"Попытка вступить в группу: {linked_group.title}", style="bold cyan")
            
            await client(JoinChannelRequest(linked_group))
            console.log(f"Успешно вступили в группу: {linked_group.title}", style="bold green")

            return True
        
        except Exception as e:
            if "You have successfully requested" in str(e):
                console.log("Запрос на подписку уже отправлен", style="yellow")
                return False
            console.log(f"Ошибка при попытке вступления в группу: {e}", style="bold red")
            return False

    async def new_post_handler(self, client, event, prompt_tone, account_phone):
        if account_phone != self.active_account:
            return

        post_text = event.message.message
        message_id = event.message.id
        channel = event.chat

        console.log(f"Новый пост в канале {channel.title} для аккаунта {account_phone}", style="green")

        if self.account_comment_count.get(account_phone, 0) >= self.comment_limit:
            await self.switch_to_next_account()
            await self.sleep_account(account_phone)
            return
        
        comment = await self.comment_manager.generate_comment(post_text, prompt_tone)
        if not comment:
            return

        await self.sleep_before_send_message()
        await self.send_comment(client, account_phone, channel, comment, message_id)
