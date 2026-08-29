"""Move execuções antigas para a pasta de dados da aplicação.

As execuções ficavam onde o usuário apontasse — em geral `./outputs` dentro do
repositório. Este script leva cada uma para `paths.runs_root()`, preservando o
nome, e avisa antes se o destino não tem espaço.

    .venv/bin/python scripts/migrar_saidas.py --de ./outputs            # simula
    .venv/bin/python scripts/migrar_saidas.py --de ./outputs --executar
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confortimetro.paths import runs_root


def directory_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            file_path = os.path.join(root, name)
            if not os.path.islink(file_path):
                total += os.path.getsize(file_path)
    return total


def human(size):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def collect(source):
    """Execuções (diretórios com configs.json) e o tamanho de cada uma."""
    runs = []
    for name in sorted(os.listdir(source)):
        path = os.path.join(source, name)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, 'configs.json')):
            runs.append((name, path, directory_size(path)))
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--de', default='./outputs', help='pasta de origem')
    parser.add_argument('--para', default=None,
                        help='destino (padrão: a pasta de dados da aplicação)')
    parser.add_argument('--executar', action='store_true',
                        help='move de verdade; sem esta flag apenas mostra o plano')
    args = parser.parse_args()

    destination = args.para or runs_root()
    runs = collect(args.de)
    if not runs:
        raise SystemExit(f'nenhuma execução encontrada em {args.de}')

    # O destino pode ainda não existir; o espaço e o disco são os do primeiro
    # diretório que existe subindo a árvore.
    reference = os.path.abspath(destination)
    while not os.path.exists(reference):
        reference = os.path.dirname(reference)

    total = sum(size for _, _, size in runs)
    free = shutil.disk_usage(reference).free
    same_device = os.stat(args.de).st_dev == os.stat(reference).st_dev

    print(f"{len(runs)} execução(ões), {human(total)} em {args.de}")
    print(f"destino: {destination} ({human(free)} livres)")
    print("mesmo disco: " + ("sim, a movida é instantânea" if same_device else
                             "não, os arquivos serão copiados byte a byte"))

    # Só o destino em outro disco consome espaço novo; no mesmo disco o move é
    # um rename e não gasta nada.
    if not same_device and total > free * 0.9:
        raise SystemExit(
            f"espaço insuficiente: {human(total)} não cabem em {human(free)} livres. "
            "Aponte a variável CONFORTIMETRO_DATA_DIR para um disco maior e "
            "rode de novo.")

    if not args.executar:
        print("\nnada foi movido (use --executar). Plano:")
        for name, _, size in runs:
            print(f"  {name:45s} {human(size):>10s}")
        return

    os.makedirs(destination, exist_ok=True)
    for index, (name, path, size) in enumerate(runs, start=1):
        target = os.path.join(destination, name)
        if os.path.exists(target):
            print(f"[{index}/{len(runs)}] {name}: já existe no destino, pulando")
            continue
        print(f"[{index}/{len(runs)}] {name} ({human(size)})…", flush=True)
        shutil.move(path, target)

    print(f"pronto: {len(runs)} execução(ões) em {destination}")


if __name__ == '__main__':
    main()
