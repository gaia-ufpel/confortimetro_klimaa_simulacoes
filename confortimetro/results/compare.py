"""Listagem e comparação de execuções já simuladas dentro de um diretório."""

import concurrent.futures
import datetime
import fnmatch
import json
import os

import pandas

from .stats import get_stats_from_simulation

# Campos do configs.json que descrevem o cenário simulado; viram colunas da tabela.
CONFIG_FIELDS = ['module_type', '_idf_path', 'epw_path', '_met', 'clo_min', 'clo_max',
                 'clo_priority', 'pmv_lowerbound', 'pmv_upperbound', 'adaptative_bound',
                 'max_vel', 'co2_limit', 'temp_ac_min', 'temp_ac_max']

# Colunas de estatística introduzidas junto com a energia agregada; a ausência
# delas marca um ESTATISTICAS.xlsx gerado por uma versão anterior.
REQUIRED_COLUMNS = ['Energia total (kWh)', 'PMV fora da faixa', 'Fora da banda adaptativa']

# Métricas que interessam ao comparar duas execuções, na ordem de leitura.
COMPARISON_COLUMNS = ['Energia total (kWh)', 'Aquecimento (kWh)', 'Resfriamento (kWh)',
                      'Desconforto', 'PMV médio', 'PMV fora da faixa',
                      'Fora da banda adaptativa', 'Janela aberta', 'Ventilador ligado',
                      'DOAS ligado', 'CO2 máximo', 'Timesteps simulados']


def needs_recompute(run_path, known_mtimes=None):
    """A execução tem planilhas por zona mas estatísticas ausentes ou desatualizadas?

    `known_mtimes` mapeia execuções já ingeridas no banco ao `mtime` da planilha
    lida; bater com ele dispensa abrir o arquivo, que é o custo de listar
    dezenas de execuções.
    """
    stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')
    if not os.path.exists(stats_path):
        return True
    if known_mtimes and known_mtimes.get(run_path) == os.path.getmtime(stats_path):
        return False
    columns = pandas.read_excel(stats_path, nrows=0).columns
    return any(column not in columns for column in REQUIRED_COLUMNS)


def _room_files(run_path, rooms):
    """Zonas com planilha na pasta da execução.

    As execuções antigas (`parameters.txt`) não gravam a lista de zonas: nesse
    caso as próprias planilhas são a lista.
    """
    if rooms:
        return [room for room in rooms
                if os.path.exists(os.path.join(run_path, f"{room}.xlsx"))]
    try:
        names = sorted(os.path.splitext(entry.name)[0]
                       for entry in os.scandir(run_path)
                       if entry.is_file() and entry.name.endswith('.xlsx')
                       and entry.name != 'ESTATISTICAS.xlsx')
    except OSError:
        return []
    return names


#: O que marca um diretório como execução. O `parameters.txt` é o formato
#: antigo, anterior ao `configs.json`: as pastas em `./outputs` de antes da
#: mudança só têm ele, e sem isso sumiam da listagem.
RUN_MARKERS = ('configs.json', 'parameters.txt')


def is_run(path) -> bool:
    """Verdadeiro se o diretório é uma execução."""
    return any(os.path.exists(os.path.join(path, marker))
               for marker in RUN_MARKERS)


def read_config(run_path) -> dict:
    """Configuração da execução, do `configs.json` ou do `parameters.txt`."""
    config_path = os.path.join(run_path, 'configs.json')
    if os.path.exists(config_path):
        with open(config_path, encoding='utf-8') as config_file:
            return json.load(config_file)

    legacy_path = os.path.join(run_path, 'parameters.txt')
    if not os.path.exists(legacy_path):
        return {}

    # `chave=valor` por linha; os valores ficam como texto, que é tudo o que a
    # listagem mostra deles.
    config = {}
    with open(legacy_path, encoding='utf-8', errors='replace') as legacy:
        for line in legacy:
            key, separator, value = line.partition('=')
            if separator:
                config[key.strip()] = value.strip()
    return config


def read_run(run_path, known_mtimes=None):
    """Metadados de uma execução, sem abrir nenhuma planilha grande."""
    config = read_config(run_path)

    rooms = config.get('rooms') or []
    available = _room_files(run_path, rooms)
    stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')

    if not available:
        status = 'sem planilhas'
    elif not os.path.exists(stats_path):
        status = 'sem estatísticas'
    elif needs_recompute(run_path, known_mtimes):
        status = 'desatualizada'
    else:
        status = 'pronta'

    return {
        'run': os.path.basename(os.path.normpath(run_path)),
        'path': run_path,
        'status': status,
        'rooms': rooms,
        'rooms_disponiveis': available,
        'module_type': config.get('module_type'),
        'idf': os.path.basename(config.get('_idf_path') or ''),
        'epw': os.path.basename(config.get('epw_path') or ''),
        'modificado': datetime.datetime.fromtimestamp(os.path.getmtime(run_path)),
        'config': config,
    }


def has_runs(path) -> bool:
    """Verdadeiro se a pasta tem ao menos uma execução dentro."""
    try:
        with os.scandir(path) as entries:
            return any(entry.is_dir() and is_run(entry.path) for entry in entries)
    except OSError:
        return False


def list_runs(outputs_path='./outputs', patterns=None, known_mtimes=None):
    """Todas as execuções (diretórios com configs.json), mais recentes primeiro."""
    if not os.path.isdir(outputs_path):
        return []

    runs = []
    for name in sorted(os.listdir(outputs_path)):
        run_path = os.path.join(outputs_path, name)
        if not os.path.isdir(run_path):
            continue
        if not is_run(run_path):
            continue
        if patterns and not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            continue
        runs.append(read_run(run_path, known_mtimes))

    return sorted(runs, key=lambda run: run['modificado'], reverse=True)


def recompute_run(run_path):
    """Regera ESTATISTICAS.xlsx a partir das planilhas por zona já existentes.

    Devolve `(run_path, erro)`; o erro vem como texto para que uma execução
    quebrada não derrube o lote inteiro.
    """
    info = read_run(run_path)
    if not info['rooms_disponiveis']:
        return run_path, 'sem planilhas por zona'
    try:
        get_stats_from_simulation(run_path, info['rooms_disponiveis'])
    except Exception as error:
        return run_path, f"{type(error).__name__}: {error}"
    return run_path, None


def recompute_runs(run_paths, workers=None, on_result=None):
    """Regera as estatísticas de várias execuções em paralelo."""
    errors = {}
    if not run_paths:
        return errors
    workers = workers or os.cpu_count()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for run_path, error in pool.map(recompute_run, run_paths):
            errors[run_path] = error
            if on_result:
                on_result(run_path, error)
    return errors


def mismatched_periods(df):
    """Execuções cujo período simulado destoa das demais na tabela.

    Comparar o consumo anual de uma com o de outra que rodou só o verão dá um
    resultado sem sentido; a contagem de timesteps é o que denuncia isso.
    """
    if df.empty or 'Timesteps simulados' not in df.columns:
        return []
    counts = df['Timesteps simulados'].dropna()
    if counts.empty:
        return []
    # A execução mais longa é a referência: com duas execuções a moda empata e
    # apontaria a errada. Quem cobre menos tempo é a exceção a sinalizar.
    longest = counts.max()
    divergent = df[df['Timesteps simulados'] < longest]
    return sorted(set(divergent['Execução']))


def compare_runs(run_paths, room=None):
    """Tabela com uma linha por zona de cada execução e as colunas do config.

    Execuções sem estatísticas completas são ignoradas — use `recompute_runs`
    antes para incluí-las.
    """
    frames = []
    for run_path in run_paths:
        if needs_recompute(run_path):
            continue
        df = pandas.read_excel(os.path.join(run_path, 'ESTATISTICAS.xlsx'))
        if room:
            df = df[df['Nome da sala'] == room]
            if df.empty:
                continue
        info = read_run(run_path)
        df.insert(0, 'Execução', info['run'])
        for field in CONFIG_FIELDS:
            value = info['config'].get(field)
            if field.endswith('_path'):
                value = os.path.basename(value) if value else None
            df[field.lstrip('_')] = value
        frames.append(df)

    if not frames:
        return pandas.DataFrame()
    return pandas.concat(frames, ignore_index=True)
