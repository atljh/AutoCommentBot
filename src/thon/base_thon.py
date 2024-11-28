import contextlib
import logging
from pathlib import Path
from typing import Self

from telethon.errors import UserDeactivatedBanError, UserDeactivatedError
from telethon.sessions import StringSession

from .base_client import TelegramClient

TelethonBannedError = (UserDeactivatedError, UserDeactivatedBanError)


class BaseData:
    def __init__(self, json_data: dict, raise_error: bool):
        self.__json_data, self.__raise_error = json_data, raise_error

    @property
    def json_data(self) -> dict:
        return self.__json_data

    def json_data_edit(self, key: str, value: str | int | bool | None):
        self.__json_data[key] = value

    @property
    def session_file(self) -> str:
        if not (session_file := self.json_data.get("session_file")):
            if self.__raise_error:
                raise ValueError("ERROR_SESSION_FILE:BASE_THON")
            return ""
        return session_file

    @property
    def string_session(self) -> StringSession:
        if not (string_session := self.json_data.get("string_session")):
            if self.__raise_error:
                raise ValueError("ERROR_STRING_SESSION:BASE_THON")
            return StringSession()
        return StringSession(string_session)

    @property
    def app_id(self) -> int:
        """Api Id"""
        if api_id := self.json_data.get("api_id"):
            return api_id
        if not (app_id := self.json_data.get("app_id")):
            raise ValueError("ERROR_APP_ID:BASE_THON")
        return app_id

    @property
    def app_hash(self) -> str:
        """Api Hash"""
        if api_hash := self.json_data.get("api_hash"):
            return api_hash
        if not (app_hash := self.json_data.get("app_hash")):
            raise ValueError("ERROR_APP_HASH:BASE_THON")
        return app_hash

    @property
    def device(self) -> str:
        """Device Model"""
        if device_model := self.json_data.get("device_model"):
            return device_model
        if not (device := self.json_data.get("device")):
            raise ValueError("ERROR_DEVICE:BASE_THON")
        return device

    @property
    def sdk(self) -> str:
        """System Version"""
        if system_version := self.json_data.get("system_version"):
            return system_version
        if not (sdk := self.json_data.get("sdk")):
            raise ValueError("ERROR_SDK:BASE_THON")
        return sdk

    @property
    def app_version(self) -> str:
        """App Version"""
        if not (app_version := self.json_data.get("app_version")):
            raise ValueError("ERROR_APP_VERSION:BASE_THON")
        return app_version

    @property
    def lang_pack(self) -> str:
        """Lang Pack"""
        if lang_code := self.json_data.get("lang_code"):
            return lang_code
        return self.json_data.get("lang_pack", "en")

    @property
    def system_lang_code(self) -> str:
        """System Lang Code"""
        if system_lang_code := self.json_data.get("system_lang_code"):
            return system_lang_code
        return self.json_data.get("system_lang_pack", "en-us")

    @property
    def twostep(self) -> str | None:
        """2FA"""
        if password := self.json_data.get("password"):
            return password
        if twofa := self.json_data.get("twoFA"):
            return twofa
        if twostep := self.json_data.get("twostep"):
            return twostep

    @property
    def proxy(self) -> dict | tuple:
        if not self.json_data.get("proxy"):
            return {}
        if not (proxy := self.json_data.get("proxy")):
            if self.__raise_error:
                raise ValueError("ERROR_PROXY:BASE_THON")
            return {}
        return proxy


class BaseThon(BaseData):
    def __init__(
        self,
        item: Path | None,
        json_data: dict,
        retries: int = 50,
        timeout: int = 10,
        debug: bool = False,
        raise_error: bool = True,
    ):
        self.__item, self.__retries, self.__timeout = item, retries, timeout
        super().__init__(json_data, raise_error)
        self.__client = self.__get_client()
        self.__debug = debug

    @property
    def client(self) -> TelegramClient:
        return self.__client

    def __get_client(self) -> TelegramClient:
        __session = str(self.__item) if not self.__item else self.string_session
        return TelegramClient(
            session=__session,
            api_id=self.app_id,
            api_hash=self.app_hash,
            device_model=self.device,
            app_version=self.app_version,
            system_lang_code=self.system_lang_code,
            lang_code=self.lang_pack,
            connection_retries=self.__retries,
            request_retries=self.__retries,
            proxy=self.proxy,
            timeout=self.__timeout,
        )

    async def check(self) -> str:
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                return "ERROR_AUTH:BAN_ERROR"
            return "OK"
        except ConnectionError:
            await self.disconnect()
            return "ERROR_AUTH:CONNECTION_ERROR"
        except TelethonBannedError:
            await self.disconnect()
            return "ERROR_AUTH:BAN_ERROR"
        except Exception as e:
            await self.disconnect()
            if self.__debug:
                logging.exception(e)
            return f"ERROR_AUTH:{e}"

    async def disconnect(self):
        with contextlib.suppress(Exception):
            await self.client.disconnect()  # type: ignore

    async def __aenter__(self) -> str | Self:
        r = await self.check()
        if r != "OK":
            return r
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
