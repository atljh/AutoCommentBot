import contextlib
import os
import shutil
import subprocess
from pathlib import Path

main_script = "main.py"
if not Path(main_script).exists():
    main_script = "app.py"

APP_NAME = Path.cwd().name + ".exe"


def compile_by_pyinstaller():
    """Компиляция"""
    try:
        # noinspection PyPackageRequirements
        import PyInstaller.__main__  # type:ignore
    except ImportError:
        subprocess.run(["pip", "install", "pyinstaller"])
        # noinspection PyPackageRequirements
        import PyInstaller.__main__  # type:ignore

    cmd = [main_script, "-F", "--collect-all=montydb"]
    for icon in Path(".").glob("*.ico"):
        cmd.append("-i")
        cmd.append(icon.name)
        break
    PyInstaller.__main__.run(cmd)


def after_compile_clean_and_rename():
    """Очистка и переименовывание"""
    distfile = Path(f"dist/{main_script.replace('.py', '.exe')}")
    app_path = Path(APP_NAME)
    if distfile.exists():
        if app_path.exists():
            os.remove(APP_NAME)
        os.rename(distfile, APP_NAME)
        with contextlib.suppress(Exception):
            os.removedirs("dist")
    with contextlib.suppress(Exception):
        os.remove(main_script.replace(".py", ".spec"))
    with contextlib.suppress(Exception):
        shutil.rmtree("build", ignore_errors=True)


def main():
    compile_by_pyinstaller()
    after_compile_clean_and_rename()
    input("Press any key to continue...")


if __name__ == "__main__":
    main()
