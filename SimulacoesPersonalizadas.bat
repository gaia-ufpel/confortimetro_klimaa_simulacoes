IF NOT EXIST "poetry.lock" (
    poetry install
)

poetry run python src/app.py