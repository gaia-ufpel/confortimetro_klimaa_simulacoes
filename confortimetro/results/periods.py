"""Recorte sazonal das planilhas (verão, inverno e semanas típicas)."""

import os
from datetime import datetime

import pandas

# Mês e dia de cada recorte; o ano vem da própria planilha, que carrega o
# RunPeriod simulado — fixar 2015 quebrava qualquer modelo de outro ano.
TARGET_PERIODS = {
    "VERAO": ((12, 23), (3, 24)),
    "INVERNO": ((6, 22), (9, 23)),
    "DIAS_VERAO": ((1, 30), (2, 6)),
    "DIAS_INVERNO": ((7, 31), (8, 7)),
}


def _period_dates(name, year):
    (begin_month, begin_day), (end_month, end_day) = TARGET_PERIODS[name]
    return (datetime(year, begin_month, begin_day),
            datetime(year, end_month, end_day))


def _split_target_period_dataframe(df, room, year):
    """Separa o dataframe nos quatro recortes, só com as horas ocupadas."""
    occupied = df[df[f"PEOPLE_{room}:People Occupant Count"] != 0]
    stamps = occupied["Date/Time"]

    # O verão cruza a virada do ano: são as duas pontas do calendário.
    summer_begin, summer_end = _period_dates("VERAO", year)
    summer = pandas.concat([occupied[stamps >= summer_begin],
                            occupied[stamps <= summer_end]])

    slices = [summer]
    for name in ("INVERNO", "DIAS_VERAO", "DIAS_INVERNO"):
        begin, end = _period_dates(name, year)
        slices.append(occupied[(stamps >= begin) & (stamps <= end)])
    return slices


def split_target_period_excel(excel_path, room=None):
    """Grava um `<ZONA>_SPLIT.xlsx` com uma aba por recorte sazonal.

    `room` é deduzido do nome do arquivo quando não é passado.
    """
    df = pandas.read_excel(excel_path)
    room = room or os.path.splitext(os.path.basename(excel_path))[0]
    year = int(pandas.to_datetime(df["Date/Time"]).dt.year.mode().iloc[0])

    summer, winter, days_summer, days_winter = _split_target_period_dataframe(
        df, room, year)

    target_path = excel_path[:-5] + "_SPLIT.xlsx"
    with pandas.ExcelWriter(target_path) as writer:
        summer.to_excel(writer, sheet_name="VERAO", index=False)
        winter.to_excel(writer, sheet_name="INVERNO", index=False)
        days_summer.to_excel(writer, sheet_name="DIAS_VERAO", index=False)
        days_winter.to_excel(writer, sheet_name="DIAS_INVERNO", index=False)
    return target_path
