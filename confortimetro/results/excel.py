"""Exportação dos resultados do EnergyPlus (.eso/.csv) para planilhas."""

import os
from concurrent.futures import ThreadPoolExecutor

import esoreader
import pandas

# Dias de aquecimento que o EnergyPlus escreve no .eso antes do período
# simulado. Em 6 timesteps por hora davam as 288 linhas descartadas à mão.
WARMUP_DAYS = 2


def summary_rooms_results_from_eso(output_path:str, rooms:list[str], timesteps_per_hour:int=6, start_date='2015-01-01', end_date='2016-1-1 T00:00'):
    """
    Resumo dos resultados de cada sala em um arquivo .xlsx a partir de um arquivo .eso

    `timesteps_per_hour`, `start_date` e `end_date` descrevem o RunPeriod do IDF
    simulado — a `Simulation` os lê do próprio arquivo. Os padrões só existem
    para quem chama a função à mão sobre uma execução antiga.
    """
    minutes = 60 // timesteps_per_hour
    warmup_rows = WARMUP_DAYS * 24 * timesteps_per_hour
    start_date = pandas.to_datetime(start_date) + pandas.Timedelta(minutes=minutes)
    dates = pandas.Series(pandas.date_range(start_date, end_date, freq=f"{minutes}min"))
    eso = esoreader.read_from_path(os.path.join(output_path, "eplusout.eso"))
    variables = eso.find_variable("")

    frames = {}
    for room in rooms:
        columns = ["Date/Time", "Site Outdoor Air Drybulb Temperature"]
        df = eso.to_frame("Site Outdoor Air Drybulb Temperature")
        
        for variable in variables:
            if variable[1] is None:
                if room in variable[2]:
                    df = pandas.concat([df, eso.to_frame(variable[2])], axis=1)
                    columns.append(f"{variable[2]}")
            elif room in variable[1]:
                df = pandas.concat([df, eso.to_frame(variable[2])[variable[1]]], axis=1)
                columns.append(f"{variable[1]}:{variable[2]}")

        if len(columns) == 2:
            raise ValueError(
                f"Nenhuma variável da sala {room} encontrada no eplusout.eso; "
                "confira o nome da zona em rooms e as Output:Variable do IDF"
            )

        df = df.drop(df.index[:warmup_rows])
        df.index = range(len(df))

        # concat com tamanhos diferentes preenche com NaN em silêncio: uma
        # simulação truncada sairia com datas erradas sem nenhum erro.
        if len(df) != len(dates):
            raise ValueError(
                f"Resultados da sala {room} têm {len(df)} linhas, mas o período "
                f"esperado tem {len(dates)} (timesteps_per_hour={timesteps_per_hour}, "
                f"{start_date} a {end_date}). Simulação truncada ou IDF com outro "
                "RunPeriod/timestep."
            )

        df = pandas.concat([dates, df], axis=1)
        df.columns = columns
        frames[room] = df

    # ThreadPoolExecutor em vez de Thread crua: com Thread, uma exceção no
    # to_excel só era impressa e o join passava, deixando o xlsx faltando.
    futures = []
    with ThreadPoolExecutor(max_workers=len(frames) or 1) as pool:
        futures = [
            pool.submit(df.to_excel, os.path.join(output_path, f"{room}.xlsx"), index=False)
            for room, df in frames.items()
        ]
    for future in futures:
        future.result()
