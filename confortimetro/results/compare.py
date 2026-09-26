"""Listagem e comparação de execuções já simuladas dentro de um diretório."""

import concurrent.futures
import datetime
import fnmatch
import json
import os
import zipfile

import pandas

from .stats import get_stats_from_simulation

# Campos do configs.json que descrevem o cenário simulado; viram colunas da tabela.
CONFIG_FIELDS = ['module_type', '_idf_path', 'epw_path', '_met', 'clo_min', 'clo_max',
                 'clo_priority', 'pmv_lowerbound', 'pmv_upperbound', 'adaptative_bound',
                 'max_vel', 'co2_limit', 'temp_ac_min', 'temp_ac_max']

# Colunas de estatística introduzidas junto com a energia agregada; a ausência
# delas marca um ESTATISTICAS.xlsx gerado por uma versão anterior.
REQUIRED_COLUMNS = ['Energia total (kWh)', 'Ventilador (kWh)', 'PMV fora da faixa', 'Fora da banda adaptativa']

# Métricas que interessam ao comparar duas execuções, na ordem de leitura.
COMPARISON_COLUMNS = ['Energia total (kWh)', 'Aquecimento (kWh)', 'Resfriamento (kWh)',
                      'Ventilador (kWh)',
                      'Desconforto', 'PMV médio', 'PMV fora da faixa',
                      'Fora da banda adaptativa', 'Janela aberta', 'Ventilador ligado',
                      'DOAS ligado', 'CO2 máximo', 'Timesteps simulados']

# Colunas cujos valores representam frações de tempo ocupado (0.0 a 1.0)
# e devem ser exibidas como porcentagem na interface.
PERCENTAGE_COLUMNS = {
    'Desconforto',
    'PMV fora da faixa',
    'Fora da banda adaptativa',
    'Janela aberta',
    'Ventilador ligado',
    'DOAS ligado',
    'Ar condicionado ligado',
    'Aquecimento',
    'Resfriamento',
    'Ventilador ligado e ar ligado',
    'Ventilador ligado, ar desligado e janela fechada',
    'Janela aberta e ventilador ligado',
    'Janela fechada, ar desligado e ventilador desligado',
    'Janela aberta sem pessoas',
}


def needs_recompute(run_path, known_mtimes=None):
    """A execução tem planilhas por zona mas estatísticas ausentes ou desatualizadas?

    `known_mtimes` mapeia execuções já ingeridas no banco ao `mtime` da planilha
    lida; bater com ele dispensa abrir o arquivo, que é o custo de listar
    dezenas de execuções.
    """
    stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')
    if not os.path.exists(stats_path):
        return True
    if not zipfile.is_zipfile(stats_path):
        return True
    if known_mtimes and known_mtimes.get(run_path) == os.path.getmtime(stats_path):
        return False
    try:
        columns = pandas.read_excel(stats_path, nrows=0).columns
        return any(column not in columns for column in REQUIRED_COLUMNS)
    except Exception:
        return True


def _room_files(run_path, rooms):
    """Zonas com planilha válida na pasta da execução.

    As execuções antigas (`parameters.txt`) não gravam a lista de zonas: nesse
    caso as próprias planilhas são a lista. Com uma planilha aberta no Excel,
    o Windows deixa ao lado um `~$NOME.xlsx` de bloqueio, que não é um .xlsx:
    contá-lo como zona quebrava a regeração com "Excel file format cannot be
    determined". Arquivos corrompidos ou incompletos (que não são ZIPs válidos)
    também são ignorados para permitir recuperação automática se eplusout.eso existir.
    """
    def _is_valid_room_xlsx(path):
        return os.path.isfile(path) and zipfile.is_zipfile(path)

    if rooms:
        return [room for room in rooms
                if _is_valid_room_xlsx(os.path.join(run_path, f"{room}.xlsx"))]
    try:
        names = sorted(os.path.splitext(entry.name)[0]
                       for entry in os.scandir(run_path)
                       if entry.is_file() and entry.name.endswith('.xlsx')
                       and not entry.name.startswith('~$')
                       and entry.name != 'ESTATISTICAS.xlsx'
                       and zipfile.is_zipfile(entry.path))
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
    """Regera ESTATISTICAS.xlsx a partir das planilhas por zona já existentes ou do eplusout.eso.

    Devolve `(run_path, erro)`; o erro vem como texto para que uma execução
    quebrada não derrube o lote inteiro.
    """
    try:
        info = read_run(run_path)
        config = read_config(run_path)
        rooms = config.get('rooms') or []
        eso_path = os.path.join(run_path, 'eplusout.eso')

        # Se não há planilhas válidas ou se alguma sala esperada está ausente/corrompida
        # e existe eplusout.eso, extraímos novamente do .eso.
        needs_eso_extraction = (
            not info['rooms_disponiveis']
            or (rooms and any(r not in info['rooms_disponiveis'] for r in rooms))
        )
        if needs_eso_extraction and os.path.exists(eso_path):
            target_rooms = rooms or info['rooms_disponiveis']
            if target_rooms:
                idf_path = (config.get('_idf_path')
                            or config.get('idf_path')
                            or os.path.join(run_path, 'modelo.idf'))
                if not os.path.exists(idf_path) and os.path.exists(os.path.join(run_path, 'modelo.idf')):
                    idf_path = os.path.join(run_path, 'modelo.idf')
                from confortimetro.idf import read_run_period, read_timesteps_per_hour
                from confortimetro.results.excel import summary_rooms_results_from_eso

                start, end = read_run_period(idf_path)
                ts = read_timesteps_per_hour(idf_path)
                summary_rooms_results_from_eso(
                    run_path, target_rooms, timesteps_per_hour=ts,
                    start_date=start, end_date=end,
                )
                info = read_run(run_path)

        if not info['rooms_disponiveis']:
            return run_path, 'sem planilhas por zona nem arquivo eplusout.eso'

        get_stats_from_simulation(run_path, info['rooms_disponiveis'])
        return run_path, None
    except Exception as error:
        return run_path, f"{type(error).__name__}: {error}"


def recompute_runs(run_paths, workers=None, on_result=None):
    """Regera as estatísticas de várias execuções em paralelo."""
    errors = {}
    if not run_paths:
        return errors
    # No executável do Windows cada worker é um processo novo que recarrega o
    # bundle inteiro (centenas de MB): mais workers que execuções só gasta RAM,
    # e o pool do Windows não aceita mais de 61 processos.
    workers = min(workers or os.cpu_count() or 1, len(run_paths), 61)
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
