"""Texto integral das normas do PBE Edifica, para o assistente consultar.

Os PDFs ficam fora do git (`docs/material/Normas PBE Edifica/`); o texto
extraído por `scripts/extrair_normas.py` vai em `normas/<documento>.txt.gz`,
uma página do PDF por bloco separado por form feed. `normas/guia_inic.md` é o
guia curado — a "skill" — que o assistente lê antes de buscar no texto.
"""

import functools
import gzip
import os
import re
import unicodedata

PASTA = os.path.join(os.path.dirname(__file__), "normas")
GUIA = os.path.join(PASTA, "guia_inic.md")

# chave: (PDF de origem, descrição para o modelo)
DOCUMENTOS = {
    "portaria": ("Portaria_309_2022_retificada_NT02.pdf",
                 "Portaria Inmetro 309/2022 consolidada e retificada pela Nota Técnica 02: "
                 "Anexo I = INI-C (comerciais, de serviços e públicas), Anexo II = INI-R "
                 "(residenciais), Anexo III = RAC (avaliação da conformidade, ENCE), "
                 "Anexo IV = selo."),
    "definicoes_inic": ("Manual_INI-C_Definicoes_ago23.pdf",
                        "Manual de definições da INI-C (ago/2023), com figuras e exemplos."),
    "definicoes_inir": ("Manual_INI-R_Definicoes_maio25.pdf",
                        "Manual de definições da INI-R (mai/2025)."),
}

TRECHO = 4000   # caracteres por página devolvida
TOTAL = 18000   # caracteres por resposta


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


@functools.lru_cache(maxsize=None)
def paginas(documento: str) -> list:
    """Páginas do documento, a primeira no índice 0."""
    with gzip.open(os.path.join(PASTA, f"{documento}.txt.gz"), "rt", encoding="utf-8") as f:
        return f.read().split("\f")


def guia() -> str:
    with open(GUIA, encoding="utf-8") as arquivo:
        return arquivo.read()


def ler(documento: str, pagina: int, ate: int = None) -> list:
    """`[{"pagina", "texto"}]` das páginas `pagina`…`ate` (no máximo 4)."""
    todas = paginas(documento)
    ate = min(ate or pagina, pagina + 3, len(todas))
    if not 1 <= pagina <= len(todas):
        raise ValueError(f"{documento} tem {len(todas)} páginas.")
    return [{"pagina": numero, "texto": todas[numero - 1][:TRECHO]}
            for numero in range(pagina, ate + 1)]


def buscar(termos: str, documento: str = None, limite: int = 6) -> list:
    """Páginas que mais casam com os `termos`, com as linhas em volta de cada achado.

    Sem acento e sem caixa; páginas com mais termos distintos vêm primeiro.
    Termo entre aspas é buscado como frase.
    """
    frases = re.findall(r'"([^"]+)"', termos)
    palavras = re.sub(r'"[^"]+"', " ", termos).split()
    alvos = [_sem_acento(t) for t in frases + [p for p in palavras if len(p) > 2]]
    if not alvos:
        raise ValueError("Informe ao menos um termo com 3 letras ou mais.")
    achados = []
    for chave in [documento] if documento else DOCUMENTOS:
        for numero, texto in enumerate(paginas(chave), 1):
            normal = _sem_acento(texto)
            casados = [alvo for alvo in alvos if alvo in normal]
            if casados:
                ocorrencias = sum(normal.count(alvo) for alvo in casados)
                achados.append((len(casados), ocorrencias, chave, numero, texto, casados))
    achados.sort(key=lambda a: (-a[0], -a[1]))

    resultado, usado = [], 0
    for distintos, _, chave, numero, texto, casados in achados[:limite]:
        linhas = texto.splitlines()
        perto = {i + d for i, linha in enumerate(linhas)
                 if any(alvo in _sem_acento(linha) for alvo in casados)
                 for d in range(-3, 16)}
        trecho = "\n".join(linhas[i] if i - 1 in perto else "…\n" + linhas[i]
                           for i in sorted(perto) if 0 <= i < len(linhas))[:3000]
        if usado + len(trecho) > TOTAL:
            break
        usado += len(trecho)
        resultado.append({"documento": chave, "pagina": numero,
                          "termos": f"{distintos} de {len(alvos)}", "trecho": trecho})
    return resultado
