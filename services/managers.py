import random
import asyncio
import logging
from collections import deque
from typing import Tuple, List

from langdetect import detect

from telethon import events
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.errors.rpcerrorlist import UserBannedInChannelError, MsgIdInvalidError
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest


from .console import console


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
            console.log(f"Ошибка при обработке канала {channel}: {e}")
            return
    
    def get_random_delay(self, delay_range: Tuple[int, int]) -> int:
        min_delay, max_delay = delay_range
        return random.randint(min_delay, max_delay)

    async def join_channels(self, client, channels, join_channel_delay, account_phone):
        for channel in channels:
            try:
                entity = await client.get_entity(channel)
                if await self.is_participant(client, entity):
                    console.log(f"Аккаунт {account_phone} уже состоит в канале {channel}")
                    continue
            except Exception:
                try:
                    delay = self.get_random_delay(join_channel_delay)
                    console.log(f"Задержка перед подпиской на канал {delay} сек")
                    await asyncio.sleep(delay)
                    await client(ImportChatInviteRequest(channel[6:]))
                    console.log(f"Аккаунт присоединился к приватному каналу {channel}")
                    continue
                except Exception as e:
                    console.log(f"Ошибка при присоединении к каналу {channel}: {e}")
                    continue
            try:
                delay = self.get_random_delay(join_channel_delay)
                console.log(f"Задержка перед подпиской на канал {delay} сек")
                await asyncio.sleep(delay)
                await client(JoinChannelRequest(channel))
                console.log(f"Аккаунт присоединился к каналу {channel}")
            except Exception as e:
                console.log(f"Ошибка при подписке на канал {channel}: {e}")

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
                console.log(f'Аккаунт {account_phone} выходит с режима сна.')
            self.comment_limits[account_phone] = self.config.comment_limit

        return current_client, account_phone

    async def monitor_channel(self, channel, prompt_tone, sleep_duration):
        current_client, account_phone = await self.rotate_account()

        @current_client.on(events.NewMessage(chats=channel))
        async def new_post_handler(event):
            nonlocal account_phone, current_client
            post_text = event.message.message
            message_id = event.message.id

            console.log(f"Новый пост в канале {channel}")

            if self.comment_limits[account_phone] <= 0:
                self.sleep_durations[account_phone] = sleep_duration
                console.log(f"Аккаунт {account_phone} достиг лимита комментариев. Переход к следующему аккаунту.")
                current_client, account_phone = await self.rotate_account()

            comment = await self.comment_generator.generate_comment(post_text, prompt_tone)
            if not comment:
                return

            send_message_delay = self.config.send_message_delay
            delay = self.get_random_delay(send_message_delay)
            console.log(f"Задержка перед отправкой сообщения {delay} сек")
            await asyncio.sleep(delay)
            try:
                await current_client.send_message(
                    entity=channel,
                    message=comment,
                    comment_to=message_id
                )
                console.log(f"Комментарий отправлен от аккаунта {account_phone} в канал {channel}")

                self.comment_limits[account_phone] -= 1
                if self.comment_limits[account_phone] <= 0:
                    self.sleep_durations[account_phone] = sleep_duration
                    console.log(f"Аккаунт {account_phone} достиг лимита и переходит в сон на {sleep_duration} секунд.")
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
                console.log(f"Ошибка при отправке комментария: {e}")
  

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
            console.log(f"Ошибка определения языка: {e}")
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
            console.log(f"Ошибка генерации комментария: {e}")
            return None

class FileManager:
    @staticmethod
    def read_channels(file='groups.txt') -> list:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return [line.strip().replace("https://", "") for line in f.readlines()]
        except FileNotFoundError:
            console.log("Файл groups.txt не найден")
            return None

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
            console.log("Файл prompts.txt не найден")
            return []
