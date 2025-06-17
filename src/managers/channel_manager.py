import random
import asyncio
import logging
from typing import List
from collections import deque
from functools import partial

from openai import OpenAI
from telethon import events
from telethon import TelegramClient
from telethon.tl.types import Channel
from telethon.errors.rpcerrorlist import (
    FloodWaitError,
    UserBannedInChannelError,
    MsgIdInvalidError,
    InviteHashExpiredError,
    UserNotParticipantError,
    ChannelPrivateError,
    ChannelInvalidError,
    InviteHashInvalidError
)
from telethon.tl.functions.channels import (
    JoinChannelRequest, GetFullChannelRequest, LeaveChannelRequest
)
from telethon.tl.functions.messages import (
    ImportChatInviteRequest)

from src.console import console
from .file_manager import FileManager
from .comment_manager import CommentManager
from .blacklist import BlackList
from tooler import move_item


logging.getLogger("telethon").setLevel(logging.CRITICAL)


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
        self.comments_count = FileManager.load_comment_count()
        self.file_manager = FileManager()
        self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.comment_manager = CommentManager(config, self.openai_client)
        self.blacklist = BlackList()
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

    async def validate_channels_access(self, account_phone):
        client = self.accounts.get(account_phone)
        if not client:
            return []
        
        valid_channels = []
        
        for channel_link in self.channels:
            try:
                entity = await client.get_entity(channel_link)
                await client.get_permissions(entity, 'me')
                valid_channels.append(channel_link)
            except ChannelPrivateError:
                console.log(f"Аккаунт {account_phone} исключен из {channel_link}", style="red")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
            except Exception as e:
                console.log(f"Ошибка доступа к {channel_link}", style="yellow")
        
        return valid_channels

    async def switch_to_next_account(self, channel_link: str = None):
        """
        Переключает активный аккаунт на следующий в очереди.
        Если передан channel_link, пропускает аккаунты, которые находятся в черном списке для этого канала.
        """
        if self.active_account:
            self.account_queue.append(self.active_account)

        start_account = self.account_queue[0] if self.account_queue else None
        new_account = None

        while self.account_queue:
            candidate = self.account_queue.popleft()

            if channel_link and self.blacklist.is_group_blacklisted(candidate, channel_link):
                console.log(
                    f"Аккаунт {candidate} в черном списке для канала {channel_link}, пропускаем",
                    style="yellow"
                )

                valid_channels = await self.validate_channels_access(candidate)
                if not valid_channels:
                    console.log(f"Аккаунт {candidate} не имеет доступа к каналам", style="red")
                    continue

                self.account_queue.append(candidate)
                self.channels = valid_channels
                if candidate == start_account:
                    console.log("Все аккаунты в черном списке, переключение невозможно", style="red")
                    return None
                continue

            new_account = candidate
            break

        if new_account:
            self.active_account = new_account
            console.log(
                f"Смена активного аккаунта на {self.active_account}",
                style="green"
            )
        else:
            console.log("Нет доступных аккаунтов для обработки", style="yellow")
            self.stop_event.set()

    async def sleep_account(self, account_phone):
        sleep_time = self.sleep_duration
        console.log(f"Аккаунт {account_phone} будет в режиме сна на {sleep_time} секунд...", style="yellow")
        await asyncio.sleep(sleep_time)
        self.account_comment_count[account_phone] = 0
        console.log(f"Аккаунт {account_phone} проснулся и готов продолжать.",
                    style="green")

    async def is_participant(self, client, channel, account_phone, channel_link, item, json_file, spamblock_dir):
        try:
            await client.get_permissions(channel, 'me')
            return True
        except UserNotParticipantError:
            return False

        except ChannelPrivateError:
            return False

        except Exception as e:
            if "private and you lack permission" in str(e):
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                console.log(f"Канал {channel_link} недоступен для аккаунта {account_phone}. Пропускаем.", style="yellow")
            elif 'FROZEN_METHOD_INVALID' in str(e):
                return "SPAMBLOCK"
            else:
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

    async def join_channels(self, client, account_phone, item, json_file, spamblock_dir) -> List[str]:
        channels = []
        for channel in self.channels:
            if self.blacklist.is_group_blacklisted(
                account_phone, channel
            ):
                console.log(
                    f"Канал {channel} в черном списке аккаунта {account_phone}",
                    style="yellow"
                )
                # channels.append(channel)
                continue
            try:
                entity = await client.get_entity(channel)
                result = await self.is_participant(client, entity, account_phone, channel, item, json_file, spamblock_dir)
                if type(result) == 'str' and "SPAMBLOCK" in result:
                    return result
                if result:
                    channels.append(channel)
                    continue
            except InviteHashExpiredError:
                console.log(f"Такого канала не существует или ссылка истекла: {channel}", style="red")
                self.blacklist.add_to_blacklist(account_phone, channel)
                continue
            except FloodWaitError as e:
                console.log(
                    f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow"
                    )
                return "MUTE"
            except Exception as e:
                try:
                    await self.sleep_before_enter_channel()
                    await client(ImportChatInviteRequest(channel[6:]))
                    console.log(
                        f"Аккаунт {account_phone} присоединился к приватному каналу {channel}"
                    )
                    channels.append(channel)
                    continue
                except Exception as e:
                    if "is not valid anymore" in str(e):
                        console.log(
                            f"Вы забанены в канале {channel}, или такого канала не существует", style="yellow"
                            )
                        continue
                    elif "A wait of" in str(e):
                        console.log(
                            f"Слишком много запросов \
                                от аккаунта {account_phone}.\
                                Ожидание {e.seconds} секунд.", style="yellow"
                                )
                        return "MUTE"
                    elif "is already" in str(e):
                        continue
                    elif "FROZEN_METHOD_INVALID" in str(e):
                        console.log(f"[red]Акканут {account_phone} заморожен[/red]")
                        # await self.switch_to_next_account()
                        return "SPAMBLOCK"
                    else:
                        console.log(f"Ошибка при присоединении к каналу {channel}: {e}")
                        continue
            # if "FROZEN_METHOD_INVALID" in str(e):
            #     console.log(f"[red]Акканут {account_phone} заморожен[/red]")
            #     await self.switch_to_next_account()
            #     return "SPAMBLOCK"
            try:
                await self.sleep_before_enter_channel()
                await client(JoinChannelRequest(channel))
                console.log(f"Аккаунт присоединился к каналу {channel}")
                channels.append(channel)
            except Exception as e:
                if "A wait of" in str(e):
                    console.log(f"Слишком много запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow")
                    continue
                elif "is not valid" in str(e):
                    console.log("Ссылка на чат не рабочая или такого чата не существует", style="yellow")
                    continue
                elif "you were banned" in str(e):
                    console.log(f"Аккаунт {account_phone} забанен в канале {channel}, добавляем в черный список")
                    self.blacklist.add_to_blacklist(account_phone, channel)
                else:
                    console.log(f"Ошибка при подписке на канал {channel}: {e}")
                    continue
        return channels

    async def event_handler(self, client, event, prompt_tone, account_phone, channel, item, json_file, spamblock_dir):
        await self.new_post_handler(client, event, prompt_tone, account_phone, channel, item, json_file, spamblock_dir)

    async def monitor_channels(
        self,
        client: TelegramClient,
        account_phone: str,
        channels: List[str],
        item,
        json_file,
        spamblock_dir
    ) -> None:
        if not channels:
            console.log("Каналы не найдены", style="yellow")
            return
        for channel in channels:
            try:

                client.add_event_handler(
                    partial(self.event_handler, client, prompt_tone=self.prompt_tone, account_phone=account_phone, channel=channel, item=item, json_file=json_file, spamblock_dir=spamblock_dir),
                    events.NewMessage(chats=channel)
                )
            except Exception as e:
                console.log(f'Ошибка, {e}', style="red")
        console.log(f"Мониторинг каналов начался для аккаунта {account_phone}...")
        await self.stop_event.wait()

    async def get_channel_entity(self, client, channel):
        try:
            return await client.get_entity(channel)
        except Exception as e:
            console.log(f"Ошибка получения объекта канала: {e}", style="red")
            return None

    async def send_comment(
        self,
        client: TelegramClient,
        account_phone: str,
        channel: Channel,
        comment: str,
        message_id: int,
        channel_link: str,
        item,
        json_file,
        spamblock_dir,
        attempts=0
    ) -> None:
        try:
            
            if self.blacklist.is_group_blacklisted(
                account_phone, channel_link
            ):
                console.log(f"{channel_link} в черном списке аккаунта {account_phone}, пропускаем")
                self.channels.remove(channel)
                return
            channel_entity = await self.get_channel_entity(client, channel)
            if not channel_entity:
                console.log("Канал не найден или недоступен.", style="red")
                return
            try:
                await client.get_permissions(channel, 'me')
            except ChannelPrivateError:
                console.log(f"Аккаунт {account_phone} был удален из канала {channel_link}", style="red")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                await self.switch_to_next_account(channel_link)
                return
            await client.send_message(
                entity=channel_entity,
                message=comment,
                comment_to=message_id
            )
            console.log(f"Комментарий отправлен от аккаунта {account_phone} в канал {channel_link}", style="green")
            self.account_comment_count[account_phone] = self.account_comment_count.get(account_phone, 0) + 1
            self.file_manager.save_comment_count(account_phone)
            console.log(f"Отправлено {FileManager.load_comment_count()} сообщений.", style="blue")
            if self.account_comment_count[account_phone] >= self.comment_limit:
                await self.switch_to_next_account()
                await self.sleep_account(account_phone)
        except FloodWaitError as e:
            logging.warning(
                f"Превышен лимит запросов от аккаунта {account_phone}. Ожидание {e.seconds} секунд.", style="yellow"
                )
            await asyncio.sleep(e.seconds)
            await self.switch_to_next_account()
        except UserBannedInChannelError:
            console.log(f"Аккаунт {account_phone} заблокирован в канале {channel_link}", style="red")
            self.blacklist.add_to_blacklist(account_phone, channel_link)
            await client(LeaveChannelRequest(channel))
            console.log(f"Аккаунт {account_phone} вышел из канала {channel_link}")
            await self.switch_to_next_account()
        except MsgIdInvalidError:
            console.log("Канал не связан с чатом, пропускаем", style="red")
        except Exception as e:
            if "private and you lack permission" in str(e):
                console.log(f"Канал {channel_link} недоступен для аккаунта {account_phone}. Пропускаем. 1", style="yellow")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                try:
                    await client(LeaveChannelRequest(channel))
                except ChannelInvalidError:
                    pass
                console.log(f"Аккаунт {account_phone} вышел из канала {channel_link}")
            elif "You can't write" in str(e):
                console.log(f"Канал {channel_link} недоступен для аккаунта {account_phone}. Пропускаем.", style="yellow")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                try:
                    await client(LeaveChannelRequest(channel))
                except ChannelInvalidError:
                    pass
                console.log(f"Аккаунт {account_phone} вышел из канала {channel_link}")
            elif "You join the discussion group before commenting" in str(e):
                console.log("Для комментирования необходимо вступить в группу.")
                join_result = await self.join_discussion_group(client, channel_entity, channel_link)
                if join_result:
                    await self.send_comment(client, account_phone, channel, comment, message_id, channel_link, item, json_file, spamblock_dir)
                    return
                else:
                    return
            elif "FROZEN_METHOD_INVALID" in str(e):
                console.log("Аккаунт заморожен, перемещаем в папку spamblock")
                move_item(item, spamblock_dir, True, True)
                move_item(json_file, spamblock_dir, True, True)
                await self.switch_to_next_account()
            elif "ALLOW_PAYMENT_REQUIRED" in str(e):
                console.log(f"Не удалось отправить сообщение в {channel_link}: требуется подписка или оплата.", style="yellow")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                FileManager.remove_channel_from_groups(channel_link)
                try:
                    await client(LeaveChannelRequest(channel))
                    console.log(f"Аккаунт {account_phone} вышел из канала {channel_link}")
                except Exception:
                    pass
                await self.switch_to_next_account()
            elif "RPCError 406" in str(e):
                console.log(f"Не удалось отправить сообщение в {channel_link}: требуется подписка или оплата.", style="yellow")
                self.blacklist.add_to_blacklist(account_phone, channel_link)
                FileManager.remove_channel_from_groups(channel_link)
                try:
                    await client(LeaveChannelRequest(channel))
                    console.log(f"Аккаунт {account_phone} вышел из канала {channel_link}")
                except Exception:
                    pass
                await self.switch_to_next_account()
            else:
                console.log(f"Ошибка при отправке комментария: {e}", style="red")
            if attempts < self.MAX_SEND_ATTEMPTS:
                console.log(f"Попытка {attempts + 1}/{self.MAX_SEND_ATTEMPTS} отправить сообщение c другого аккаунта...")
                await self.switch_to_next_account(channel_link=channel_link)
                next_client = self.accounts.get(self.active_account)
                if next_client:
                    await self.sleep_before_send_message()
                    await self.send_comment(
                        next_client, self.active_account, channel,
                        comment, message_id, channel_link,
                        item, json_file, spamblock_dir,
                        attempts + 1
                    )
                else:
                    console.log("Нет доступных аккаунтов для отправки.", style="red")
            else:
                console.log(f"Не удалось отправить сообщение после {self.MAX_SEND_ATTEMPTS} попыток.", style="red")

    async def join_discussion_group(
        self,
        client: TelegramClient,
        channel_entity: Channel,
        channel_link: str
    ) -> bool:
        try:
            full_channel = await client(GetFullChannelRequest(channel=channel_entity))

            linked_chat_id = full_channel.full_chat.linked_chat_id
            if not linked_chat_id:
                console.log(f"Канал {channel_link} не связан с группой.", style="bold yellow")
                return
            try:
                linked_group = await client.get_entity(linked_chat_id)
                console.log(f"Попытка вступить в группу: {linked_group.title}", style="bold cyan")
            except Exception as e:
                console.log(f"Ошибка при получении связанной группы: {e}", style="bold red")
                return False

            await client(JoinChannelRequest(linked_group))
            console.log(f"Успешно вступили в группу: {linked_group.title}", style="bold green")

            return True

        except Exception as e:
            if "You have successfully requested" in str(e):
                console.log("Запрос на подписку уже отправлен", style="yellow")
                return False
            else:
                console.log(f"Ошибка при попытке вступления в группу: {e}", style="bold red")
                return False

    async def new_post_handler(
        self,
        client: TelegramClient,
        event: events.NewMessage.Event,
        prompt_tone: str,
        account_phone: str,
        channel_link: str,
        item,
        json_file,
        spamblock_dir
    ) -> None:
        if self.blacklist.is_group_blacklisted(self.active_account, channel_link):
            console.log(f"Канал {channel_link} в ЧС аккаунта {self.active_account}", style="yellow")
            await self.switch_to_next_account(channel_link)
            if not self.active_account:
                console.log("Нет доступных аккаунтов", style="red")
                return
            account_phone = self.active_account

        active_client = self.accounts.get(self.active_account)
        if not active_client:
            console.log(f"Клиент для аккаунта {self.active_account} не найден", style="red")
            await self.switch_to_next_account(channel_link)
            return

        try:
            try:
                channel_entity = await active_client.get_entity(channel_link)
            except (ValueError, InviteHashExpiredError, InviteHashInvalidError) as e:
                console.log(f"Приглашение в канал устарело или недействительно: {channel_link}", style="red")
                self.blacklist.add_to_blacklist(self.active_account, channel_link)
                await self.switch_to_next_account(channel_link)
                return
            except Exception as e:
                console.log(f"Ошибка получения entity канала: {e}", style="red")
                return

            try:
                perms = await active_client.get_permissions(channel_entity, 'me')
                if not perms:
                    raise ChannelPrivateError()
            except (ChannelPrivateError, UserNotParticipantError):
                console.log(f"Аккаунт {self.active_account} не в канале {channel_link}", style="red")
                self.blacklist.add_to_blacklist(self.active_account, channel_link)
                await self.switch_to_next_account(channel_link)
                return
            try:
                await active_client.get_messages(channel_entity, limit=1, ids=1)
            except (ChannelPrivateError, UserNotParticipantError):
                console.log(f"Подтверждено: {self.active_account} нет в {channel_link}", style="red")
                self.blacklist.add_to_blacklist(self.active_account, channel_link)
                await self.switch_to_next_account(channel_link)
                return
            except Exception as e:
                console.log(f"Ошибка дополнительной проверки: {e}", style="yellow")

        except FloodWaitError as e:
            console.log(f"Флуд-контроль: ждем {e.seconds} сек", style="yellow")
            await asyncio.sleep(e.seconds)
            return
        except Exception as e:
            console.log(f"Критическая ошибка проверки канала: {e}", style="red")
            return

        if account_phone != self.active_account:
            return

        post_text = event.message.message
        if not post_text or len(post_text) < 3:
            console.log("Пост без текста", style="yellow")
            return

        console.log(f"Новый пост в {channel_link} для {self.active_account}", style="green")

        if self.account_comment_count.get(self.active_account, 0) >= self.comment_limit:
            await self.switch_to_next_account(channel_link)
            await self.sleep_account(self.active_account)
            return

        try:
            comment = await self.comment_manager.generate_comment(post_text, prompt_tone)
            if comment:
                await self.sleep_before_send_message()
                await self.send_comment(
                    active_client,
                    self.active_account,
                    event.chat,
                    comment,
                    event.message.id,
                    channel_link,
                    item,
                    json_file,
                    spamblock_dir
                )
        except Exception as e:
            console.log(f"Ошибка отправки: {e}", style="red")