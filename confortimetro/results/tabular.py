"""Leitura do `eplustbl.csv` — os relatórios tabulares do EnergyPlus.

O arquivo é uma sequência de blocos `REPORT:,<relatório>` com tabelas
separadas por linha em branco: título numa linha própria, cabeçalho começando
com `,,` e as linhas com `,<nome>,<valores>`. Guardamos cada tabela como lista
de dicionários, com a primeira coluna em `nome`.
"""

import csv
import os

FILE_NAME = "eplustbl.csv"


def _value(text):
    try:
        return float(text)
    except ValueError:
        return text.strip()


def read_tables(run_path) -> dict:
    """`{(relatório, título): [linhas]}`; um título repetido no mesmo
    relatório fica com a primeira ocorrência."""
    path = os.path.join(run_path, FILE_NAME)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{FILE_NAME} não encontrado em {run_path}")
    tables, report, title, header, rows = {}, None, None, None, None
    with open(path, newline="", encoding="latin-1") as handle:
        for row in csv.reader(handle):
            if not any(cell.strip() for cell in row):
                header = None
                continue
            if row[0] == "REPORT:":
                report = row[1]
            elif row[0] == "FOR:":
                continue
            elif row[0]:
                title, header = row[0].strip(), None
            elif header is None:
                header = ["nome"] + row[2:]
                rows = []
                tables.setdefault((report, title), rows)
            else:
                rows.append(dict(zip(header, map(_value, row[1:]))))
    return tables


def table(tables, report, title) -> list:
    return tables.get((report, title), [])


def _self_check():
    import tempfile
    text = ("Program Version:,EnergyPlus\n"
            "REPORT:,Zone Report\nFOR:,Entire Facility\nZone Summary\n\n"
            ",,Area [m2],Conditioned (Y/N)\n,SALA,11.23,Yes\n,Total,20.00,\n\n"
            "Nota de rodapé\n\n\nZone Summary\n\n,,Outra\n,X,1\n")
    with tempfile.TemporaryDirectory() as folder:
        with open(os.path.join(folder, FILE_NAME), "w", encoding="latin-1") as handle:
            handle.write(text)
        rows = table(read_tables(folder), "Zone Report", "Zone Summary")
    assert rows == [{"nome": "SALA", "Area [m2]": 11.23, "Conditioned (Y/N)": "Yes"},
                    {"nome": "Total", "Area [m2]": 20.0, "Conditioned (Y/N)": ""}], rows
    print("ok")


if __name__ == "__main__":
    _self_check()
