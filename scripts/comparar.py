"""Agrega os ESTATISTICAS.xlsx de várias execuções em uma única tabela.

Uso, a partir da raiz do repositório:

    .venv/bin/python scripts/comparar.py                      # só o que já tem estatísticas
    .venv/bin/python scripts/comparar.py --recompute          # regera as que estão sem as colunas de energia
    .venv/bin/python scripts/comparar.py --runs FAURB_ENTORNO_* --out comparacao.csv
"""

import argparse
import concurrent.futures
import fnmatch
import json
import os
import sys

import pandas

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confortimetro.results.stats import get_stats_from_simulation

# Campos do configs.json que descrevem o cenário simulado; viram colunas da tabela.
CONFIG_FIELDS = ['module_type', '_idf_path', 'epw_path', '_met', 'clo_min', 'clo_max',
                 'clo_priority', 'pmv_lowerbound', 'pmv_upperbound', 'adaptative_bound',
                 'max_vel', 'co2_limit', 'temp_ac_min', 'temp_ac_max']
REQUIRED_COLUMNS = ['Energia total (kWh)', 'PMV fora da faixa', 'Fora da banda adaptativa']


def _needs_recompute(stats_path):
    if not os.path.exists(stats_path):
        return True
    columns = pandas.read_excel(stats_path, nrows=0).columns
    return any(column not in columns for column in REQUIRED_COLUMNS)


def _recompute(run_path):
    """Regera ESTATISTICAS.xlsx a partir das planilhas por zona já existentes."""
    rooms = json.load(open(os.path.join(run_path, 'configs.json')))['rooms']
    rooms = [room for room in rooms if os.path.exists(os.path.join(run_path, f"{room}.xlsx"))]
    if not rooms:
        return run_path, 'sem planilhas por zona'
    try:
        get_stats_from_simulation(run_path, rooms)
    except Exception as error:  # uma execução quebrada não pode derrubar o lote
        return run_path, f"{type(error).__name__}: {error}"
    return run_path, None


def collect(outputs_path, patterns, recompute, workers):
    runs = []
    for name in sorted(os.listdir(outputs_path)):
        run_path = os.path.join(outputs_path, name)
        if not os.path.isdir(run_path) or not os.path.exists(os.path.join(run_path, 'configs.json')):
            continue
        if patterns and not any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            continue
        runs.append(run_path)

    if recompute:
        pending = [run for run in runs if _needs_recompute(os.path.join(run, 'ESTATISTICAS.xlsx'))]
        print(f"regerando estatísticas de {len(pending)} execução(ões)...", file=sys.stderr)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for run_path, error in pool.map(_recompute, pending):
                print(f"  {os.path.basename(run_path)}: {error or 'ok'}", file=sys.stderr)

    frames = []
    for run_path in runs:
        stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')
        if _needs_recompute(stats_path):
            print(f"pulando {os.path.basename(run_path)} (sem estatísticas completas; "
                  "use --recompute)", file=sys.stderr)
            continue
        df = pandas.read_excel(stats_path)
        config = json.load(open(os.path.join(run_path, 'configs.json')))
        df.insert(0, 'Execução', os.path.basename(run_path))
        for field in CONFIG_FIELDS:
            value = config.get(field)
            if field.endswith('_path'):
                value = os.path.basename(value) if value else None
            df[field.lstrip('_')] = value
        frames.append(df)

    if not frames:
        raise SystemExit('nenhuma execução com estatísticas completas encontrada')
    return pandas.concat(frames, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--outputs', default='./outputs', help='diretório com as execuções')
    parser.add_argument('--runs', nargs='*', default=None,
                        help='padrões glob para filtrar execuções (ex.: FAURB_ENTORNO_*)')
    parser.add_argument('--out', default='./outputs/COMPARACAO.csv', help='CSV de saída')
    parser.add_argument('--recompute', action='store_true',
                        help='regera ESTATISTICAS.xlsx das execuções sem as colunas de energia '
                             '(lê todas as planilhas por zona; leva minutos)')
    parser.add_argument('--workers', type=int, default=os.cpu_count(),
                        help='processos paralelos na regeração')
    args = parser.parse_args()

    df = collect(args.outputs, args.runs, args.recompute, args.workers)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} linha(s) de {df['Execução'].nunique()} execução(ões) em {args.out}")


if __name__ == '__main__':
    main()
