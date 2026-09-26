"""Versão do código que está rodando, gravada no configs.json de cada execução.

Serve para saber se uma execução antiga rodou o mesmo controlador que está
instalado agora. No executável do Windows não há git nem pyproject: o CI grava
`confortimetro/_build.py` com `VERSAO` antes do PyInstaller. A partir do
código, a versão vem do `pyproject.toml` e o commit do git, com um aviso quando
há alteração não commitada no que decide a simulação (`control/` e `idf/`) —
mexer na GUI não muda resultado.
"""

import functools
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


@functools.lru_cache(maxsize=1)
def code_version() -> dict:
    try:
        from ._build import VERSAO
        return {"versao": VERSAO}
    except ImportError:
        pass
    version = None
    try:
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as handle:
            match = re.search(r'^version\s*=\s*"([^"]+)"', handle.read(), re.M)
            version = match.group(1) if match else None
    except OSError:
        pass
    commit = _git("rev-parse", "--short", "HEAD")
    status = (_git("status", "--porcelain", "--", "confortimetro/control", "confortimetro/idf")
              if commit else None)
    return {"versao": version, "commit": commit,
            "alteracoes_locais": bool(status) if status is not None else None}


if __name__ == "__main__":
    info = code_version()
    assert set(info) >= {"versao"}, info
    print(info)
