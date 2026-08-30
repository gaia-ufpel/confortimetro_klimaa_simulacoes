"""Recorte sazonal: vale para qualquer zona e segue o ano da planilha."""

import pandas

from confortimetro.results.periods import split_target_period_excel

ROOM = "SALA_AULA"


def _planilha(tmp_path, year):
    stamps = pandas.date_range(f"{year}-01-01 00:10", f"{year}-12-31 23:50", freq="6h")
    df = pandas.DataFrame({
        "Date/Time": stamps,
        f"PEOPLE_{ROOM}:People Occupant Count": [1.0] * len(stamps),
        f"{ROOM}:Zone Operative Temperature": [24.0] * len(stamps),
    })
    path = tmp_path / f"{ROOM}.xlsx"
    df.to_excel(path, index=False)
    return path


def test_recorta_qualquer_zona_e_usa_o_ano_da_planilha(tmp_path):
    path = _planilha(tmp_path, 2019)

    destino = split_target_period_excel(str(path))

    abas = pandas.read_excel(destino, sheet_name=None)
    assert set(abas) == {"VERAO", "INVERNO", "DIAS_VERAO", "DIAS_INVERNO"}
    # O verão cruza a virada do ano: pega dezembro e o começo de janeiro.
    verao = pandas.to_datetime(abas["VERAO"]["Date/Time"])
    assert verao.dt.month.isin([12, 1, 2, 3]).all()
    assert verao.dt.year.unique().tolist() == [2019]
    inverno = pandas.to_datetime(abas["INVERNO"]["Date/Time"])
    assert inverno.dt.month.isin([6, 7, 8, 9]).all()


def test_ignora_horas_sem_ocupacao(tmp_path):
    path = _planilha(tmp_path, 2019)
    df = pandas.read_excel(path)
    df[f"PEOPLE_{ROOM}:People Occupant Count"] = 0.0
    df.to_excel(path, index=False)

    destino = split_target_period_excel(str(path), ROOM)

    assert all(aba.empty for aba in pandas.read_excel(destino, sheet_name=None).values())
