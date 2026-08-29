"""Agrega os ESTATISTICAS.xlsx de várias execuções em uma única tabela.

Uso, a partir da raiz do repositório:

    .venv/bin/python scripts/comparar.py                      # só o que já tem estatísticas
    .venv/bin/python scripts/comparar.py --recompute          # regera as que estão sem as colunas de energia
    .venv/bin/python scripts/comparar.py --runs 'FAURB_ENTORNO_*' --out comparacao.csv
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confortimetro.results.compare import compare_runs, list_runs, recompute_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--outputs', default='./outputs', help='diretório com as execuções')
    parser.add_argument('--runs', nargs='*', default=None,
                        help='padrões glob para filtrar execuções (ex.: FAURB_ENTORNO_*)')
    parser.add_argument('--room', default=None, help='restringe a uma zona')
    parser.add_argument('--out', default='./outputs/COMPARACAO.csv', help='CSV de saída')
    parser.add_argument('--recompute', action='store_true',
                        help='regera ESTATISTICAS.xlsx das execuções desatualizadas '
                             '(lê todas as planilhas por zona; leva minutos)')
    parser.add_argument('--workers', type=int, default=os.cpu_count(),
                        help='processos paralelos na regeração')
    args = parser.parse_args()

    runs = list_runs(args.outputs, args.runs)
    if not runs:
        raise SystemExit(f'nenhuma execução encontrada em {args.outputs}')

    if args.recompute:
        pending = [run['path'] for run in runs
                   if run['status'] in ('sem estatísticas', 'desatualizada')]
        print(f"regerando estatísticas de {len(pending)} execução(ões)...", file=sys.stderr)
        recompute_runs(pending, args.workers, on_result=lambda path, error: print(
            f"  {os.path.basename(path)}: {error or 'ok'}", file=sys.stderr))
        runs = list_runs(args.outputs, args.runs)

    for run in runs:
        if run['status'] != 'pronta':
            print(f"pulando {run['run']} ({run['status']}; use --recompute)", file=sys.stderr)

    df = compare_runs([run['path'] for run in runs if run['status'] == 'pronta'], args.room)
    if df.empty:
        raise SystemExit('nenhuma execução com estatísticas completas encontrada')

    df.to_csv(args.out, index=False)
    print(f"{len(df)} linha(s) de {df['Execução'].nunique()} execução(ões) em {args.out}")


if __name__ == '__main__':
    main()
