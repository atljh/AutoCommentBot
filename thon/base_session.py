from pathlib import Path
from typing import Generator

from jsoner import json_read_sync

class BaseSession:
    def __init__(self):
        self.base_dir = Path("accounts")
        self.base_dir.mkdir(exist_ok=True)
        self.errors_dir = self.base_dir / "errors"
        self.errors_dir.mkdir(exist_ok=True)
        self.banned_dir = self.base_dir / "ban"
        self.banned_dir.mkdir(exist_ok=True)

    def find_sessions(self) -> Generator:
        for item in self.base_dir.glob("*.session"):
            json_file = item.with_suffix(".json")
            if not json_file.is_file():
                print(f"{item.name} | Не найден json файл!")
                continue
            if not (json_data := json_read_sync(json_file)):
                print(f"{item.name} | Ошибка чтения json")
                continue
            yield item, json_file, json_data