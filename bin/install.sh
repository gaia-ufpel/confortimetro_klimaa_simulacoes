#!/bin/sh
# Cria o ambiente virtual .venv na raiz do projeto e instala as dependências.
set -e
cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
