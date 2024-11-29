import sys
import json
import asyncio
import requests
import subprocess 

from config import ConfigManager
from src.thon.json_converter import JsonConverter
from src.starter import Starter


def get_settings():
    try:
        with open("settings.json", "r") as f:
            return json.loads(f.read())
    except:
        return {}

def set_settings(data):
    with open("settings.json", "w") as f:
        f.write(json.dumps(data))


settings = get_settings()


def register_user():
    print("Связываемся с сервером...")
    current_machine_id = (
        str(subprocess.check_output("wmic csproduct get uuid"), "utf-8")
        .split("\n")[1]
        .strip()
    )

    admin_username = settings.get("ADMIN_USERNAME")
    script_name = settings.get("SCRIPTNAME")  # Подгружаем SCRIPTNAME из settings.json
    BASE_API_URL = settings.get("BASE_API_URL", "http://142.93.105.98:8000")

    db_id = requests.get(
        f"{BASE_API_URL}/api/{script_name}/{current_machine_id}/{admin_username}"
    )
    db_id = db_id.json()
    if db_id.get("message"):
        print("Неправильный логин")
        sys.exit()
    file_key = settings.get("ACCESS_KEY")
    print(f"Ваш ID в системе: {db_id['id']}")
    if file_key:
        key = file_key
    else:
        key = input("Введите ваш ключ доступа: ")
    while True:
        is_correct = requests.post(
            f"{BASE_API_URL}/api/{script_name}/check/",
            data={"pk": current_machine_id, "key": key},
        ).json()["message"]
        if is_correct:
            print("Вход успешно выполнен!")
            settings["ACCESS_KEY"] = key
            set_settings(settings)
            return
        else:
            print("Неправильный ключ!")
            key = input("Введите ваш ключ доступа: ")


register_user()

def main():
    config = ConfigManager.load_config()
    sessions_count = JsonConverter().main()
    s = Starter(sessions_count, config)
    asyncio.run(s.main())

if __name__ == "__main__":
    main()