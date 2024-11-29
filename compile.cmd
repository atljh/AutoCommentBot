if not exist .venv (python -m venv .venv)
cmd /k "pip install poetry & poetry install --no-root & .venv\Scripts\activate & python compile.py"
