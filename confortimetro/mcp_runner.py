"""Processo independente do servidor MCP: executa o CLI e registra o término."""

import json
import os
import sys
import time


def write_status(run: str, state: str, error: str = "", pid: int = None) -> None:
    """Grava o estado; `pid` é o do runner, para detectar se morreu sem avisar."""
    path = os.path.join(run, "mcp_status.json")
    temporary = os.path.join(run, "mcp_status.tmp")
    # Remove e cria com O_EXCL: um symlink plantado no .tmp nunca é seguido.
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"estado": state, "erro": error[:500], "pid": pid,
                   "inicio": time.time() if pid else None}, handle)
    os.replace(temporary, path)


def main() -> int:
    config_path = sys.argv[1]
    run = os.path.dirname(os.path.realpath(config_path))
    write_status(run, "executando", pid=os.getpid())
    try:
        from cli import main as cli_main
        code = cli_main(["--config", config_path, "--quiet"])
        write_status(run, "concluida" if code == 0 else "falhou",
                     "" if code == 0 else "Consulte mcp.log na pasta da execução")
        return code
    except Exception as error:
        write_status(run, "falhou", str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
