"""Executa configurações independentes em processos separados.

Uso: .venv/bin/python scripts/lote.py --workers 2 run1.json run2.json
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def run_one(config_path, output_path):
    log_path = os.path.join(output_path, "lote.log")
    with open(log_path, "w", encoding="utf-8") as log:
        result = subprocess.run(
            [sys.executable, str(ROOT / "cli.py"), "--config", str(config_path), "--quiet"],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False,
        )
    return result.returncode, log_path


def main(argv=None):
    from confortimetro.config import SimulationConfig

    parser = argparse.ArgumentParser(description="Simulações paralelas em pastas separadas")
    parser.add_argument("configs", nargs="+", type=Path, help="JSON de cada execução")
    parser.add_argument("--workers", type=int, default=2, help="Máximo de simulações simultâneas (padrão: 2)")
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers deve ser maior que zero")

    runs = []
    seen = set()
    for path in args.configs:
        config_path = path.resolve()
        with open(config_path, encoding="utf-8") as handle:
            if not json.load(handle).get("output_path"):
                parser.error(f"Defina output_path explícito para o lote: {config_path}")
        config = SimulationConfig.from_json(str(config_path))
        output = os.path.abspath(config.output_path)
        if output in seen:
            parser.error(f"Diretório de saída repetido: {output}")
        if os.path.exists(output) and os.listdir(output):
            parser.error(f"Diretório de saída não está vazio: {output}")
        seen.add(output)
        runs.append((config_path, output))

    for _, output in runs:
        os.makedirs(output, exist_ok=True)

    failed = False
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, *run): run for run in runs}
        for future in as_completed(futures):
            path, _ = futures[future]
            try:
                code, log = future.result()
            except OSError as error:
                print(f"FALHOU {path}: {error}", flush=True)
                failed = True
                continue
            print(f"{'OK' if code == 0 else 'FALHOU'} {path} -> {log}", flush=True)
            failed |= code != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
