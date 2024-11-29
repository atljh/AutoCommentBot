import contextlib
import os
import shutil
import subprocess
from pathlib import Path

main_script = Path(__file__).parent.parent / "main.py" 
if not main_script.exists():
    main_script = Path(__file__).parent.parent / "app.py" 

APP_NAME = Path.cwd().name + ".exe"

dist_dir = Path(__file__).parent.parent / "dist"

def compile_by_pyinstaller():
    """Компиляция"""
    try:
        # noinspection PyPackageRequirements
        import PyInstaller.__main__  # type:ignore
    except ImportError:
        subprocess.run(["pip", "install", "pyinstaller"])
        # noinspection PyPackageRequirements
        import PyInstaller.__main__  # type:ignore

    cmd = [
        str(main_script),
        "--distpath", str(dist_dir) 
    ]
    PyInstaller.__main__.run(cmd)


def after_compile_clean_and_rename():
    """Очистка и переименовывание"""
    distfile = dist_dir / f"{main_script.stem}.exe"  
    app_path = Path(APP_NAME)
    if distfile.exists():
        if app_path.exists():
            os.remove(APP_NAME)
        os.rename(distfile, APP_NAME)
        with contextlib.suppress(Exception):
            os.removedirs(str(dist_dir))
    with contextlib.suppress(Exception):
        os.remove(main_script.with_suffix(".spec").name)
    with contextlib.suppress(Exception):
        shutil.rmtree("build", ignore_errors=True)


def main():
    compile_by_pyinstaller()
    after_compile_clean_and_rename()
    input("Press any key to continue...")


if __name__ == "__main__":
    main()
