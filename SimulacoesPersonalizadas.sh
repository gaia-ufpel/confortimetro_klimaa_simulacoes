#!/bin/sh

if [ ! -f "poetry.lock" ]
then
    poetry install
fi

poetry run python src/main.py