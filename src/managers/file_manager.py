import os
import sys
import json
from src.console import console
from typing import List, Dict


class FileManager:
    @staticmethod
    def read_channels(file='groups.txt') -> list:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return [
                    line.strip().replace(" ", "").replace("https://", "")
                    for line in f.readlines()
                    if len(line.strip()) > 5
                ]
        except FileNotFoundError:
            console.log("Файл groups.txt не найден", style="bold red")
            sys.exit(1)
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
            console.log("Файл prompts.txt не найден", style="bold red")
            sys.exit(1)
            return []

    @staticmethod
    def read_proxy(file='proxy.txt') -> list:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return [
                    line.strip().replace(" ", "").replace("https://", "")
                    for line in f.readlines()
                    if len(line.strip()) > 5
                ]
        except FileNotFoundError:
            console.log("Файл groups.txt не найден", style="bold red")
            sys.exit(1)
            return None

    @staticmethod
    def read_blacklist(file: str = 'blacklist.txt') -> Dict[str, List[str]]:
        """
        Reads the blacklist from a file.

        Returns:
            Dictionary of account phones and their blacklisted groups.
        """
        blacklist = {}
        if not os.path.exists(file):
            with open(file, 'w', encoding='utf-8') as f:
                console.log(f"Файл {file} создан, так как он отсутствовал.", style="bold yellow")
            return blacklist

        try:
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        phone, group = line.strip().split(':', 1)
                        if phone not in blacklist:
                            blacklist[phone] = []
                        blacklist[phone].append(group)
                    except ValueError:
                        console.log(f"Ошибка формата строки в файле {file}: {line}", style="bold red")
        except IOError as e:
            console.log(f"Ошибка при чтении файла {file}: {e}", style="bold red")
        return blacklist

    @staticmethod
    def add_to_blacklist(
        account_phone: str,
        group: str,
        file: str = 'blacklist.txt'
    ) -> bool:
        """
        Adds a group to the blacklist for a specific account.

        Returns:
            True if successful, False otherwise.
        """
        try:
            with open(file, 'a', encoding='utf-8') as f:
                f.write(f"{account_phone}:{group}\n")
            console.log(f"Группа {group} добавлена в черный список для аккаунта {account_phone}.", style="yellow")
            return True
        except IOError as e:
            console.log(f"Ошибка при добавлении в черный список: {e}", style="red")
            return False

    @staticmethod
    def save_comment_count(self):
        with open("comment_count.json", "w") as file:
            json.dump(self.account_comment_count, file)

    @staticmethod
    def load_comment_count(self):
        try:
            with open("comment_count.json", "r") as file:
                self.account_comment_count = json.load(file)
        except FileNotFoundError:
            self.account_comment_count = {}