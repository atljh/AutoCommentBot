from pathlib import Path

from jsoner import json_read_sync, json_write_sync
from rich.console import Console
from rich.prompt import Prompt


DEFAULT_HISTORY = {
    "1": "Без прокси",
}

def ask_from_history(prompt: str, console: Console, history_file: Path) -> str:
    json_data = {}
    if history_file.is_file():
        json_data = json_read_sync(history_file)
    elif str(history_file) == 'history_proxies.json':
        json_write_sync(history_file, DEFAULT_HISTORY)
        json_data = json_read_sync(history_file)

    count = 0
    for value in json_data.values():
        count += 1
        console.print(f"[{count}]", value, end="\n")
    r = Prompt.ask(prompt, console=console)
    if r.isdigit():
        if value := json_data.get(r):
            return value
    if r not in json_data.values():
        json_data[count + 1] = r
        if r:
            json_write_sync(history_file, json_data)
    return r
