"""Extrai o texto dos PDFs do PBE Edifica para o assistente (`assistant/normas.py`).

Uso, a partir da raiz do repositório (precisa do `pdftotext`, do poppler):

    .venv/bin/python scripts/extrair_normas.py
"""

import gzip
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confortimetro.assistant import normas

ORIGEM = os.path.join("docs", "material", "Normas PBE Edifica")


def main():
    for chave, (pdf, _) in normas.DOCUMENTOS.items():
        texto = subprocess.run(["pdftotext", "-layout", os.path.join(ORIGEM, pdf), "-"],
                               capture_output=True, text=True, check=True).stdout
        # O layout preserva as colunas das tabelas; espaços longos viram dois.
        texto = re.sub(r" {3,}", "  ", texto).rstrip("\f")
        destino = os.path.join(normas.PASTA, f"{chave}.txt.gz")
        with gzip.open(destino, "wt", encoding="utf-8", compresslevel=9) as arquivo:
            arquivo.write(texto)
        print(f"{destino}: {texto.count(chr(12)) + 1} páginas")


if __name__ == "__main__":
    main()
