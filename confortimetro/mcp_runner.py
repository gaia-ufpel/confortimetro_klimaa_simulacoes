"""Processo independente do servidor MCP: executa o CLI e registra o término."""

import json
import os
import sys


def write_status(run: str, state: str, error: str = "") -> None:
    path = os.path.join(run, "mcp_status.json")
    temporary = os.path.join(run, "mcp_status.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"estado": state, "erro": error[:500]}, handle)
    os.replace(temporary, path)


def main() -> int:
    from cli import main as cli_main

    config_path = sys.argv[1]
    run = os.path.dirname(os.path.realpath(config_path))
    write_status(run, "executando")
    try:
        code = cli_main(["--config", config_path, "--quiet"])
        write_status(run, "concluida" if code == 0 else "falhou",
                     "" if code == 0 else "Consulte mcp.log na pasta da execução")
        return code
    except Exception as error:
        write_status(run, "falhou", str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
