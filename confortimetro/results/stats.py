"""Estatísticas agregadas por sala a partir das planilhas por zona."""

import os

import pandas

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

    id_arquivo = os.path.basename(os.path.normpath(output_path))

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
            raise FileNotFoundError(
                f"{room}.xlsx não encontrado em {output_path}; rode "
                "summary_rooms_results_from_eso antes das estatísticas"
            )

        df = pandas.read_excel(os.path.join(output_path, f"{room}.xlsx"))   
    
        row = {'Nome do arquivo': id_arquivo, 'Nome da sala': room,
               'Número ocupação': len(df[df[people_column.format(room)] != 0]), 'Ar condicionado ligado': None,
               'Aquecimento': None, 'Resfriamento': None, 'Ventilador ligado': None,
               'Ventilador ligado e ar ligado': None, 'Ventilador ligado, ar desligado e janela fechada': None,
               'Janela aberta': None, 'Janela aberta e ventilador ligado': None, 'DOAS ligado': None,
               'Janela fechada, ar desligado e ventilador desligado': None, 'Desconforto': None, 'CO2 máximo': None,
               'Janela aberta sem pessoas': None}

        if row['Número ocupação'] == 0:
            raise ValueError(
                f"A sala {room} nunca é ocupada nos resultados; as estatísticas "
                "são frações do tempo ocupado e não podem ser calculadas"
            )

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
        without_people = df[df[people_column.format(room)] == 0]
        row['Janela aberta sem pessoas'] = len(without_people[without_people[janela_column.format(room)] == 1]) / len(without_people) if len(without_people) else 0

        stats_df = pandas.concat([stats_df, pandas.DataFrame(row, index=[len(stats_df)])])

    stats_df.to_excel(os.path.join(output_path, f"ESTATISTICAS.xlsx"), index=False)
