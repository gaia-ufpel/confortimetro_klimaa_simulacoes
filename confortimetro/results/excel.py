"""Exportação dos resultados do EnergyPlus (.eso/.csv) para planilhas."""

import os

import esoreader
import pandas

def summary_one_room_results_from_csv(csv_path, room):
    """
    Resumo dos resultados de uma sala em um arquivo .xlsx a partir de um arquivo .csv
    """
    df = pandas.read_csv(csv_path)
    base_path = csv_path[:-13]

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

        df = df.drop(df.index[:288])
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
