"""
Execução de simulações por linha de comando (sem interface gráfica).

Uso:
    python cli.py --config examples/config.json \
        --set output_path=./outputs/teste --set module_type=COMPLETE
"""

import argparse
import json
import logging
import sys
from queue import Queue

from confortimetro.simulation import Simulation
from confortimetro.config import SimulationConfig


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Confortímetro Klimaa - simulação via CLI")
    parser.add_argument("--config", default="examples/config.json",
                        help="JSON de configuração (padrão: examples/config.json)")
    parser.add_argument("--set", action="append", default=[], metavar="CHAVE=VALOR",
                        help="Sobrescreve um campo da configuração; repetível. "
                             "O valor é lido como JSON quando possível "
                             '(ex.: --set \'rooms=["ATELIE1"]\').')
    parser.add_argument("--print-config", action="store_true",
                        help="Mostra a configuração final e sai sem simular.")
    parser.add_argument("--quiet", action="store_true", help="Não imprime o progresso.")
    return parser.parse_args(argv)


def apply_overrides(config: SimulationConfig, overrides):
    for item in overrides:
        if "=" not in item:
            raise SystemExit(f"--set inválido (esperado CHAVE=VALOR): {item}")
        key, _, raw = item.partition("=")
        key = key.strip()
        if not hasattr(config, key):
            raise SystemExit(f"Campo desconhecido em --set: {key}")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        setattr(config, key, value)
    return config


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = apply_overrides(SimulationConfig.from_json(args.config), args.set)

    if args.print_config:
        print(json.dumps(config.__dict__, indent=4, default=str))
        return 0

    q = Queue()
    simulation = Simulation(config)
    try:
        simulation.run(q)
    except Exception as e:
        print(f"Simulação falhou: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        while not q.empty():
            message = q.get()
            if message != "EXIT":
                print(message)

    print(f"Resultados em: {config.output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
