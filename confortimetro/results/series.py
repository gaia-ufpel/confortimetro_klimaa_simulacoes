"""Leitura das séries temporais por zona, com cache em disco.

Cada `<ZONA>.xlsx` tem 52 mil linhas e leva ~22 s para abrir; um gráfico que
compara quatro execuções esperaria um minuto e meio a cada clique. A primeira
leitura grava um pickle ao lado da planilha e as seguintes saem dele
(milissegundos), invalidado pelo `mtime` da planilha original.
"""

import os

import pandas

CACHE_DIRECTORY = '.series_cache'

# Nomes das colunas do <ZONA>.xlsx, com a zona interpolada.
COLUMNS = {
    'data': 'Date/Time',
    'temp_externa': 'Site Outdoor Air Drybulb Temperature',
    'ocupacao': 'PEOPLE_{room}:People Occupant Count',
    'temp_operativa': '{room}:Zone Operative Temperature',
    'pmv': 'PEOPLE_{room}:Zone Thermal Comfort Fanger Model PMV',
    'clo': 'PEOPLE_{room}:Zone Thermal Comfort Clothing Value',
    'adap_min': 'ADAP_MIN_{room}:Schedule Value',
    'adap_max': 'ADAP_MAX_{room}:Schedule Value',
    'janela': 'JANELA_{room}:Schedule Value',
    'ventilador': 'VENT_{room}:Schedule Value',
    'ac': 'AC_{room}:Schedule Value',
    'doas': 'DOAS_STATUS_{room}:Schedule Value',
    'co2': '{room}:Zone Air CO2 Concentration',
    'aquecimento': '{room} PTHP:Zone Packaged Terminal Heat Pump Total Heating Energy',
    'resfriamento': '{room} PTHP:Zone Packaged Terminal Heat Pump Total Cooling Energy',
}


def column(name, room):
    """Nome real da coluna a partir do apelido e da zona."""
    return COLUMNS[name].format(room=room)


def _cache_path(run_path, room):
    return os.path.join(run_path, CACHE_DIRECTORY, f"{room}.pkl")


def load_zone_series(run_path, room, refresh=False):
    """Série temporal de uma zona, com apelidos de coluna já aplicados.

    As colunas ganham os nomes curtos de `COLUMNS` (`pmv`, `temp_operativa`, …);
    as demais são descartadas. Linhas fora do período simulado — as planilhas
    antigas carimbam o ano inteiro e preenchem o resto com NaN — saem fora.
    """
    excel_path = os.path.join(run_path, f"{room}.xlsx")
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"{room}.xlsx não encontrado em {run_path}")

    cache_path = _cache_path(run_path, room)
    if not refresh and os.path.exists(cache_path):
        if os.path.getmtime(cache_path) >= os.path.getmtime(excel_path):
            return pandas.read_pickle(cache_path)

    raw = pandas.read_excel(excel_path)
    missing = [alias for alias in ('data', 'ocupacao')
               if column(alias, room) not in raw.columns]
    if missing:
        raise ValueError(
            f"{room}.xlsx em {run_path} não tem "
            f"{', '.join(column(alias, room) for alias in missing)}; a planilha "
            "não veio do pós-processamento desta versão")

    df = pandas.DataFrame({
        alias: raw[column(alias, room)]
        for alias in COLUMNS if column(alias, room) in raw.columns
    })
    df = df.dropna(subset=['ocupacao'])

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_pickle(cache_path)
    return df


def clear_cache(run_path):
    """Remove o cache de séries de uma execução."""
    directory = os.path.join(run_path, CACHE_DIRECTORY)
    if not os.path.isdir(directory):
        return 0
    removed = 0
    for name in os.listdir(directory):
        os.remove(os.path.join(directory, name))
        removed += 1
    os.rmdir(directory)
    return removed
