import pandas
import os
import esoreader

PORCENT2ADAPTATIVE = {
    "90%": 2.5,
    "80%": 3.5
}

ADAPTATIVE2PORCENT = {
    2.5: "90%",
    3.5: "80%"
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
        df.to_excel(os.path.join(output_path, f"{room}.xlsx"), index=False)

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
        row['Ventilador ligado e ar ligado'] = len(df[(df[people_column.format(room)] != 0) & (df[vent_column.format(room)] == 1) & (df[ac_column.format(room)] == 1)]) / row['Número ocupação']
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

if __name__ == "__main__":
    get_stats_from_simulation("./outputs/FAURB_ENTORNO_2", ["SALA_AULA", "LINSE", "SEC_LINSE", "RECEPCAO", "ATELIE1", "ATELIE2", "ATELIE3"])