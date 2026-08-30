"""Onde a aplicação guarda os arquivos de cada execução.

Antes cada execução gravava onde o usuário apontasse — em geral dentro do
próprio repositório — e ainda deixava `in.idf` e `expanded.idf` ao lado do IDF
de entrada, o que fazia duas execuções paralelas disputarem os mesmos arquivos.
Agora existe uma raiz padrão por plataforma e cada execução é uma subpasta dela.

A raiz pode ser trocada pela variável de ambiente `CONFORTIMETRO_DATA_DIR` —
útil quando os resultados não cabem no disco do sistema, já que uma simulação
anual passa de 1 GB.
"""

import datetime
import os
import platform

APP_NAME = "ConfortimetroKlimaa"
RUNS_DIRECTORY = "execucoes"
DATA_DIR_VARIABLE = "CONFORTIMETRO_DATA_DIR"


def app_data_path() -> str:
    """Pasta de dados da aplicação, conforme a convenção de cada sistema."""
    override = os.environ.get(DATA_DIR_VARIABLE)
    if override:
        return os.path.abspath(os.path.expanduser(override))

    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
    elif system == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")

    return os.path.join(base, APP_NAME)


def runs_root(create: bool = False) -> str:
    """Pasta que contém uma subpasta por execução."""
    path = os.path.join(app_data_path(), RUNS_DIRECTORY)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def new_run_path(name: str = None) -> str:
    """Caminho de uma execução nova, sem repetir uma que já exista."""
    name = name or datetime.datetime.now().strftime("execucao_%Y%m%d_%H%M")
    candidate = os.path.join(runs_root(), name)

    suffix = 2
    while os.path.exists(candidate):
        candidate = os.path.join(runs_root(), f"{name}_{suffix}")
        suffix += 1
    return candidate
