"""Recorte sazonal das planilhas (verão, inverno e semanas típicas)."""

from datetime import datetime

import pandas

TARGET_PERIODS = {
    "VERAO": (datetime(2015, 12, 23), datetime(2015, 3, 24)),
    "INVERNO": (datetime(2015, 6, 22), datetime(2015, 9, 23)),
    "DIAS_VERAO": (datetime(2015, 1, 30), datetime(2015, 2, 6)),
    "DIAS_INVERNO": (datetime(2015, 7, 31), datetime(2015, 8, 7))
}

def _split_target_period_dataframe(df):
    """
    Separa o dataframe em períodos de verão, inverno, dias de verão e dias de inverno
    """
    summer_1 = df[(df["Date/Time"] >= TARGET_PERIODS["VERAO"][0]) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
    summer_2 = df[(df["Date/Time"] <= TARGET_PERIODS["VERAO"][1]) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
    summer = pandas.concat([summer_1, summer_2])
    winter = df[((df["Date/Time"] >= TARGET_PERIODS["INVERNO"][0]) & (df["Date/Time"] <= TARGET_PERIODS["INVERNO"][1])) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
    days_summer = df[((df["Date/Time"] >= TARGET_PERIODS["DIAS_VERAO"][0]) & (df["Date/Time"] <= TARGET_PERIODS["DIAS_VERAO"][1])) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
    days_winter = df[((df["Date/Time"] >= TARGET_PERIODS["DIAS_INVERNO"][0]) & (df["Date/Time"] <= TARGET_PERIODS["DIAS_INVERNO"][1])) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]

    return summer, winter, days_summer, days_winter

def split_target_period_excel(excel_path):
    """
    Separa o arquivo .excel em períodos de verão, inverno, dias de verão e dias de inverno e salva em várias planilhas dentro de um arquivo .excel
    """
    df = pandas.read_excel(excel_path)
    summer, winter, days_summer, days_winter = _split_target_period_dataframe(df)

    excel_path = excel_path[:-5] + "_SPLIT.xlsx"
    with pandas.ExcelWriter(excel_path) as writer:
        summer.to_excel(writer, sheet_name="VERAO", index=False)
        winter.to_excel(writer, sheet_name="INVERNO", index=False)
        days_summer.to_excel(writer, sheet_name="DIAS_VERAO", index=False)
        days_winter.to_excel(writer, sheet_name="DIAS_INVERNO", index=False)
