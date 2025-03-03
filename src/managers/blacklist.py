from typing import Dict, List

from src.managers import FileManager


class BlackList:
    """Class to add accounts to blacklist."""

    @staticmethod
    def get_blacklist() -> Dict[str, List[str]]:
        """
        return
            {account_phone: [groups]}
        """
        return FileManager.read_blacklist()

    @staticmethod
    def add_to_blacklist(
        account_phone: str,
        group_link: str
    ) -> bool:
        return FileManager.add_to_blacklist(
            account_phone,
            group_link
        )

    @staticmethod
    def is_group_blacklisted(
        account_phone: str,
        group_link: str
    ) -> bool:
        blacklist = FileManager.read_blacklist()
        return group_link in blacklist.get(
            account_phone, []
        )
