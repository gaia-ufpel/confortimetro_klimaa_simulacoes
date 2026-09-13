"""Exportação dos resultados do EnergyPlus (.eso/.csv) para planilhas."""

import os
from concurrent.futures import ThreadPoolExecutor

import esoreader
import pandas

# Dias de aquecimento que o EnergyPlus escreve no .eso antes do período
# simulado. Em 6 timesteps por hora davam as 288 linhas descartadas à mão.
WARMUP_DAYS = 2


def _match_room(var, rooms):
    # Ordenar por tamanho decrescente para que 'SEC_LINSE' case antes de 'LINSE'
    sorted_rooms = sorted(rooms, key=len, reverse=True)
    key, name = var[1], var[2]
    for r in sorted_rooms:
        if key:
            if (key == r or 
                key.startswith(f"{r} ") or 
                key.endswith(f"_{r}") or 
                f"_{r}_" in key or 
                f"_{r} " in key):
                return r
        elif name:
            if (name.endswith(f":{r}") or 
                name.endswith(f"_{r}") or 
                name.endswith(f" {r}") or 
                f":{r}:" in name or 
                f"_{r}_" in name or 
                f" {r} " in name):
                return r
    return None


def summary_rooms_results_from_eso(output_path:str, rooms:list[str], timesteps_per_hour:int=6, start_date='2015-01-01', end_date='2016-1-1 T00:00') -> dict[str, pandas.DataFrame]:
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

    outdoor_vars = eso.find_variable("Site Outdoor Air Drybulb Temperature")
    if not outdoor_vars:
        raise ValueError(
            "Variável 'Site Outdoor Air Drybulb Temperature' não encontrada no eplusout.eso; "
            "confira as Output:Variable do IDF"
        )
    outdoor_data = eso.data[eso.dd.index[outdoor_vars[0]]][warmup_rows:]

    room_vars = {room: [] for room in rooms}
    for variable in variables:
        matched_room = _match_room(variable, rooms)
        if matched_room:
            room_vars[matched_room].append(variable)

    frames = {}
    for room in rooms:
        room_cols = {
            "Date/Time": dates,
            "Site Outdoor Air Drybulb Temperature": outdoor_data,
        }
        for variable in room_vars[room]:
            col_name = f"{variable[1]}:{variable[2]}" if variable[1] else variable[2]
            room_cols[col_name] = eso.data[eso.dd.index[variable]][warmup_rows:]

        if len(room_cols) <= 2:
            raise ValueError(
                f"Nenhuma variável da sala {room} encontrada no eplusout.eso; "
                "confira o nome da zona em rooms e as Output:Variable do IDF"
            )

        if len(outdoor_data) != len(dates):
            raise ValueError(
                f"Resultados da sala {room} têm {len(outdoor_data)} linhas, mas o período "
                f"esperado tem {len(dates)} (timesteps_per_hour={timesteps_per_hour}, "
                f"{start_date} a {end_date}). Simulação truncada ou IDF com outro "
                "RunPeriod/timestep."
            )

        df = pandas.DataFrame(room_cols)

        if len(df.columns) <= 2:
            raise ValueError(
                f"Nenhuma variável da sala {room} encontrada no eplusout.eso; "
                "confira o nome da zona em rooms e as Output:Variable do IDF"
            )

        if len(df) != len(dates):
            raise ValueError(
                f"Resultados da sala {room} têm {len(df)} linhas, mas o período "
                f"esperado tem {len(dates)} (timesteps_per_hour={timesteps_per_hour}, "
                f"{start_date} a {end_date}). Simulação truncada ou IDF com outro "
                "RunPeriod/timestep."
            )

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

    return frames
