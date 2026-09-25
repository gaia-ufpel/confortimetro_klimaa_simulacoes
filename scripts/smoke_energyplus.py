"""Teste curto do pipeline real com EnergyPlus, sem tocar no IDF de exemplo."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from confortimetro.idf.processor import write_idf_fields  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true",
                        help="Prepara e valida a configuração sem rodar o EnergyPlus")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="confortimetro-smoke-"))
    source = ROOT / "examples" / "idf" / "FAURB" / "FAURB_PTHP_ENTORNO.idf"
    model = work / "smoke.idf"
    output = work / "run"
    # Uma semana com dias úteis; os dois primeiros dias são descartados na extração.
    write_idf_fields(str(source), str(model), {
        ("RunPeriod", 0): {1: "1", 2: "5", 3: "2015", 4: "1", 5: "11", 6: "2015", 7: "Monday"},
    })
    command = [sys.executable, str(ROOT / "cli.py"),
               "--set", f"idf_path={model}",
               "--set", f"output_path={output}",
               "--set", 'rooms=["ATELIE1"]']
    print(f"Arquivos do smoke test: {work}", flush=True)
    subprocess.run(command + ["--print-config"], cwd=ROOT, check=True)
    if args.prepare_only:
        return 0

    subprocess.run(command, cwd=ROOT, check=True)
    required = ["configs.json", "eplusout.end", "eplusout.err", "ATELIE1.xlsx", "ESTATISTICAS.xlsx"]
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        raise RuntimeError(f"Arquivos ausentes em {output}: {', '.join(missing)}")
    end = (output / "eplusout.end").read_text(errors="replace")
    errors = (output / "eplusout.err").read_text(errors="replace")
    if "Completed Successfully" not in end or "**  Fatal  **" in errors:
        raise RuntimeError(f"EnergyPlus não concluiu sem erros; veja {output / 'eplusout.err'}")
    config = json.loads((output / "configs.json").read_text(encoding="utf-8"))
    if config["rooms"] != ["ATELIE1"]:
        raise RuntimeError("A execução não usou a zona esperada")
    print(f"Smoke test concluído: {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"Smoke test falhou: {exc}", file=sys.stderr)
        sys.exit(1)
