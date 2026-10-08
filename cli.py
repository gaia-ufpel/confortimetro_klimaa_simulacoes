"""
Execução de simulações por linha de comando (sem interface gráfica).

Uso:
    python cli.py --config examples/config.json \
        --set output_path=./outputs/teste --set module_type=COMPLETE

Etiquetagem da envoltória pela INI-C (modelos real e de referência; as APP
são as `rooms` da configuração):
    python cli.py --config examples/config.json --inic condicionado \
        --tipologia educacional --uso "Ensino superior" --zb 2
"""

import argparse
import copy
import json
import logging
import sys
from queue import Queue

from confortimetro.assistant import simulacao
from confortimetro.simulation import Simulation
from confortimetro.config import SimulationConfig
from confortimetro.etiquetagem import norma
from confortimetro.module_type import ModuleType


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Ambiens - simulação via CLI")
    parser.add_argument("--config", default="examples/config.json",
                        help="JSON de configuração (padrão: examples/config.json)")
    parser.add_argument("--set", action="append", default=[], metavar="CHAVE=VALOR",
                        help="Sobrescreve um campo da configuração; repetível. "
                             "O valor é lido como JSON quando possível "
                             '(ex.: --set \'rooms=["ATELIE1"]\').')
    parser.add_argument("--print-config", action="store_true",
                        help="Mostra a configuração final e sai sem simular.")
    parser.add_argument("--quiet", action="store_true", help="Não imprime o progresso.")
    parser.add_argument("--inic", choices=("condicionado", "hibrido"),
                        help="Etiquetagem da envoltória pela INI-C, no modo dado.")
    parser.add_argument("--tipologia", choices=sorted(norma.TIPOLOGIAS), default="educacional",
                        help="Tipologia da INI-C (padrão: educacional).")
    parser.add_argument("--uso", help="Uso dentro da tipologia, que dá a densidade de "
                                      "ocupação (padrão: o primeiro da tipologia).")
    parser.add_argument("--zb", type=int, choices=range(1, 9),
                        help="Zona bioclimática (padrão: a do local do EPW).")
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
        current = getattr(config, key)
        # `--set air_speed_delta=` chegava como "" e só quebrava no meio da validação.
        if (isinstance(current, (int, float)) and not isinstance(current, bool)
                and not isinstance(value, (int, float))):
            raise SystemExit(f"--set {key}: {raw!r} não é um número")
        setattr(config, key, value)
    return config


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = apply_overrides(SimulationConfig.from_json(args.config), args.set)

    if args.print_config:
        print(json.dumps(config.__dict__, indent=4, default=str))
        return 0

    checked = config
    if args.inic:
        # Cada modelo da etiquetagem roda no módulo somente EnergyPlus.
        checked = copy.deepcopy(config)
        checked.module_type = ModuleType.ENERGYPLUS_ONLY
    problems, _ = simulacao.validate(checked, remote=False)
    if problems:
        print("Configuração inválida:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    q = Queue()
    try:
        simulation = _etiquetagem(config, args) if args.inic else Simulation(config)
        simulation.run(q)
    except Exception as e:
        print(f"Simulação falhou: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        while not q.empty():
            message = q.get()
            if message != "EXIT":
                print(message)

    if args.inic:
        print("Resultados em: " + ", ".join(simulation.execucoes.values()))
        for path in simulation.execucoes.values():
            _push_to_drive(path)
        return 0
    print(f"Resultados em: {config.output_path}")
    _push_to_drive(config.output_path)
    return 0


def _etiquetagem(config, args):
    from confortimetro.etiquetagem.execucao import EtiquetagemRun, zona_sugerida

    usos = norma.TIPOLOGIAS[args.tipologia]["ocupacao"]
    uso = args.uso or next(iter(usos))
    if uso not in usos:
        raise ValueError(f"Uso '{uso}' não existe na tipologia {args.tipologia}: "
                         + ", ".join(usos))
    zb = args.zb
    if zb is None:
        zb, cidade = zona_sugerida(config.epw_path, config.source_idf_path or config.idf_path)
        if zb is None:
            raise ValueError("Nem o EPW nem o IDF dizem o local; informe --zb.")
        print(f"Zona bioclimática {zb} ({cidade}, pelo local do clima)")
    return EtiquetagemRun(config, {"tipologia": args.tipologia, "uso": uso,
                                   "modo": args.inic, "zb": zb}, config.output_path)


def _push_to_drive(run_path):
    """Envia a execução ao Google Drive se a conta já foi conectada pela GUI.

    Sem conta não faz nada; falha nunca muda o código de saída — a execução
    fica pendente e a próxima abertura do app tenta de novo.
    """
    try:
        from confortimetro.drive.sync import push_after_run
        status = push_after_run(run_path)
    except Exception as error:
        status = f"falhou ({error})"
    if status:
        print(f"Google Drive: {status}")


if __name__ == "__main__":
    sys.exit(main())
