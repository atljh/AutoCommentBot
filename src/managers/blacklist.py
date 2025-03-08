from typing import Dict, List

from .file_manager import FileManager


class BlackList:
    """Class to add accounts to blacklist."""

    @staticmethod
    def get_blacklist() -> Dict[str, List[str]]:
        """
        return
            {account_phone: [channels]}
        """
        return FileManager.read_blacklist()

    @staticmethod
    def add_to_blacklist(
        account_phone: str,
        channel_link: str
    ) -> bool:
        return FileManager.add_to_blacklist(
            account_phone,
            channel_link
        )

    @staticmethod
    def is_group_blacklisted(
        account_phone: str,
        channel_link: str
    ) -> bool:
        blacklist = FileManager.read_blacklist()
        return channel_link in blacklist.get(
            account_phone, []
        )
