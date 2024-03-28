IF NOT EXIST "poetry.lock" (
    poetry install
)

poetry run python src/main.py