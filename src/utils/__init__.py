import pandas
import os
import sys
import esoreader
import threading
from datetime import datetime
import matplotlib.pyplot as plt

PORCENT2ADAPTATIVE = {
    "90%": 2.5,
    "80%": 3.5
}

ADAPTATIVE2PORCENT = {
    2.5: "90%",
    3.5: "80%"
}

TARGET_PERIODS = {
    "VERAO": (datetime(2015, 12, 23), datetime(2015, 3, 24)),
    "INVERNO": (datetime(2015, 6, 22), datetime(2015, 9, 23)),
    "DIAS_VERAO": (datetime(2015, 1, 30), datetime(2015, 2, 6)),
    "DIAS_INVERNO": (datetime(2015, 7, 31), datetime(2015, 8, 7))
}

def summary_one_room_results_from_csv(csv_path, room):
    """
    Resumo dos resultados de uma sala em um arquivo .xlsx a partir de um arquivo .csv
    """

    df = pandas.read_csv(csv_path)
    base_path = csv_path[:-13]
    #print(base_path)

    target_cols = ["Date/Time",
                   "Environment:Site Outdoor Air Drybulb Temperature [C](TimeStep)"
    ]
    target_cols.extend(filter(lambda x: room in x, df.columns))
    result = df[target_cols]
    result = result.drop(result.index[:288])

    result.to_excel(os.path.join(base_path, f"{room}.xlsx"), index=False)

def summary_rooms_results_from_eso(output_path:str, rooms:list[str], timesteps_per_hour:int=6, start_date:str='2015-01-01', end_date:str='2016-1-1 T00:00'):
    """
    Resumo dos resultados de cada sala em um arquivo .xlsx a partir de um arquivo .eso
    """
    start_date = pandas.to_datetime(start_date) + pandas.Timedelta(minutes=60//timesteps_per_hour)
    dates = pandas.Series(pandas.date_range(start_date, end_date, freq=f"{60//timesteps_per_hour}min"))
    eso = esoreader.read_from_path(os.path.join(output_path, "eplusout.eso"))
    variables = eso.find_variable("")

    threads = []

    for room in rooms:
        columns = ["Date/Time", "Site Outdoor Air Drybulb Temperature"]
        df = eso.to_frame("Site Outdoor Air Drybulb Temperature")
        
        for variable in variables:
            if room in variable[1]:
                df = pandas.concat([df, eso.to_frame(variable[2])[variable[1]]], axis=1)
                columns.append(f"{variable[1]}:{variable[2]}")

        df = df.drop(df.index[:288])
        df.index = range(len(df))
        df = pandas.concat([dates, df], axis=1)
        df.columns = columns
        t = threading.Thread(target=lambda df, output_path, room: df.to_excel(os.path.join(output_path, f"{room}.xlsx"), index=False), args=[df, output_path, room])
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def get_stats_from_simulation(output_path, rooms):
    """
    Pega as estatísticas de cada informação, necessário executar a summary_results_from_room antes.
    """
    people_column = 'PEOPLE_{}:People Occupant Count'
    ac_column = 'AC_{}:Schedule Value'
    cooling_column = '{} PTHP:Zone Packaged Terminal Heat Pump Total Cooling Energy'
    heating_column = '{} PTHP:Zone Packaged Terminal Heat Pump Total Heating Energy'
    vent_column = 'VENT_{}:Schedule Value'
    janela_column = 'JANELA_{}:Schedule Value'
    doas_column = 'DOAS_STATUS_{}:Schedule Value'
    co2_column = '{}:Zone Air CO2 Concentration'
    em_conforto_column = 'EM_CONFORTO_{}:Schedule Value'

    id_arquivo = output_path.split("/")[-1]

    stats_df = pandas.DataFrame({'Nome do arquivo': [],
            'Nome da sala': [],
            'Número ocupação': [],
            'Ar condicionado ligado': [],
            'Aquecimento': [],
            'Resfriamento': [],
            'Ventilador ligado': [],
            'Ventilador ligado e ar ligado': [],
            'Ventilador ligado, ar desligado e janela fechada': [],
            'Janela aberta': [],
            'Janela aberta e ventilador ligado': [],
            'DOAS ligado': [],
            'Janela fechada, ar desligado e ventilador desligado': [],
            'Desconforto': [],
            'CO2 máximo': [],
            'Janela aberta sem pessoas': []})

    for room in rooms:
        if not os.path.exists(os.path.join(output_path, f"{room}.xlsx")):
            print(f"File {room}.xlsx not found! Skipping...")
            continue

        df = pandas.read_excel(os.path.join(output_path, f"{room}.xlsx"))   
    
        row = {'Nome do arquivo': None,
                'Nome da sala': None,
                'Número ocupação': None,
                'Ar condicionado ligado': None,
                'Aquecimento': None,
                'Resfriamento': None,
                'Ventilador ligado': None,
                'Ventilador ligado e ar ligado': None,
                'Ventilador ligado, ar desligado e janela fechada': None,
                'Janela aberta': None,
                'Janela aberta e ventilador ligado': None,
                'DOAS ligado': None,
                'Janela fechada, ar desligado e ventilador desligado': None,
                'Desconforto': None,
                'CO2 máximo': None,
                'Janela aberta sem pessoas': None}

        row['Nome do arquivo'] = id_arquivo
        row['Nome da sala'] = room
        row['Número ocupação'] = len(df[df[people_column.format(room)] != 0])
        row['Aquecimento'] = len(df[(df[people_column.format(room)] != 0) & (df[heating_column.format(room)] != 0)]) / row['Número ocupação']
        row['Resfriamento'] = len(df[(df[people_column.format(room)] != 0) & (df[cooling_column.format(room)] != 0)]) / row['Número ocupação']
        row['Ar condicionado ligado'] = row['Aquecimento'] + row['Resfriamento']
        row['Ventilador ligado'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 1)]) / row['Número ocupação']
        row['Ventilador ligado e ar ligado'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 1) & (df[cooling_column.format(room)] != 0)]) / row['Número ocupação']
        row['Ventilador ligado, ar desligado e janela fechada'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 1) & (df[ac_column.format(room)] == 0) & (df[janela_column.format(room)] == 0)]) / row['Número ocupação']
        row['Janela aberta'] = len(df[(df[people_column.format(room)] != 0) & (df[janela_column.format(room)] == 1)]) / row['Número ocupação']
        row['Janela aberta e ventilador ligado'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 1) & (df[janela_column.format(room)] == 1)]) / row['Número ocupação']
        row['DOAS ligado'] = len(df[(df[people_column.format(room)] != 0) & (df[doas_column.format(room)] == 1)]) / row['Número ocupação']
        row['Janela fechada, ar desligado e ventilador desligado'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 0) & (df[janela_column.format(room)] == 0) & (df[ac_column.format(room)] == 0)]) / row['Número ocupação']
        row['Desconforto'] = len(df[(df[people_column.format(room)] != 0) & (df[em_conforto_column.format(room)] == 0)]) / row['Número ocupação']
        row['CO2 máximo'] = df[co2_column.format(room)].max()
        row['Janela aberta sem pessoas'] = len(df[(df[people_column.format(room)] == 0) & (df[janela_column.format(room)] == 1)]) / len(df[df[people_column.format(room)] == 0])

        stats_df = pandas.concat([stats_df, pandas.DataFrame(row, index=[len(stats_df)])])

    stats_df.to_excel(os.path.join(output_path, f"ESTATISTICAS.xlsx"), index=False)

def _split_target_period_dataframe(df):
    """
    Separa o dataframe em períodos de verão, inverno, dias de verão e dias de inverno
    """
    summer_1 = df[(df["Date/Time"] >= TARGET_PERIODS["VERAO"][0]) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
    summer_2 = df[((df["Date/Time"] <= TARGET_PERIODS["VERAO"][1])) & (df["PEOPLE_ATELIE1:People Occupant Count"] != 0)]
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

def plot_graphics(excel_path, sheet_name):
    """
    Cria gráficos para temperatura externa, temperaturas do adaptativo, pmv, temperatura operativa a partir de um arquivo .excel com várias tabelas com os períodos de verão, inverno, dias de verão e dias de inverno.
    """

    df = pandas.read_excel(excel_path, sheet_name=sheet_name)

    # Cria uma figura
    fig = plt.figure(figsize=(30, 10))
    fig.suptitle("Gráficos de Temperatura", fontsize=16)
    
    # Cria um gráfico geral
    ax = fig.add_subplot(111)

    # Plota a linha da temperatura externa
    ax.plot(df["Date/Time"], df["Site Outdoor Air Drybulb Temperature"], label="Temperatura Externa", color="red")

    # Plota a linha da temperatura do adaptativo
    ax.plot(df["Date/Time"], df["ADAP_MIN_ATELIE1:Schedule Value"], label="Temperatura Mínima do Adaptativo", color="blue")
    ax.plot(df["Date/Time"], df["ADAP_MAX_ATELIE1:Schedule Value"], label="Temperatura Máxima do Adaptativo", color="blue")

    # Plota a linha da temperatura operativa
    ax.plot(df["Date/Time"], df["ATELIE1:Zone Operative Temperature"], label="Temperatura Operativa", color="green")

    # Mostra os labels
    plt.legend()
    plt.grid()

    plt.show()



if __name__ == "__main__":
    plot_graphics(sys.argv[1], "INVERNO")