import sys
import yaml
from typing import Tuple
from pydantic import BaseModel, Field, field_validator
from src.logger import logger
from src.console import console


class Config(BaseModel):
    openai_api_key: str
    chat_gpt_model: str
    prompt_tone: str = Field(default="Дружелюбный", description="Тон ответа в комментарии")
    sleep_duration: int = Field(default=30, ge=0, description="Длительность паузы после лимита комментариев")
    comment_limit: int = Field(default=10, ge=1, description="Лимит комментариев на одного пользователя")
    join_channel_delay: Tuple[int, int] = Field(default=(10, 20), description="Диапазон задержки перед подпиской на канал")
    send_message_delay: Tuple[int, int] = Field(default=(10, 20), description="Задержка перед отправкой сообщения")
    random_prompt: bool = Field(default=False, description="Использовать рандомные пользовательские промпты")
    detect_language: bool = Field(default=False, description="Определять язык поста")
    accounts_per_proxy: int = Field(default=1, description="Аккаунтов на одни прокси")

    @field_validator('openai_api_key')
    def validate_openai_api_key(cls, value):
        if not value:
            logger.error("openai_api_key не найден")
            sys.exit(0)
        return value


class ConfigManager:
    @staticmethod
    def load_config(config_file='config.yaml') -> Config:
        try:
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
        except FileNotFoundError:
            console.log(f"Файл config.yaml не найден", style="red")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            console.log(f"Ошибка загрузки конфигурации: {e}", style="red")
            sys.exit(1)
