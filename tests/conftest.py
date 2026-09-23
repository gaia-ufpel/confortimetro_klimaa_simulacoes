import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Permite rodar `pytest tests` da raiz sem exportar PYTHONPATH.
sys.path.append(str(Path(__file__).resolve().parents[1]))


def pytest_sessionstart(session):
    """Dá aos testes Tk um display isolado no Linux.

    O ``conftest`` é carregado antes dos módulos de teste, portanto o Tk já vê
    o display virtual quando as janelas são criadas. Não se aproveita um
    ``$DISPLAY`` existente para nunca abrir janelas no display do usuário.
    """
    if sys.platform != "linux" or not shutil.which("Xvfb"):
        return

    for number in range(99, 200):
        display = f":{number}"
        socket = Path(f"/tmp/.X11-unix/X{number}")
        if socket.exists():
            continue
        process = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x800x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if socket.exists():
                os.environ["DISPLAY"] = display
                session.config._confortimetro_xvfb = process
                return
            if process.poll() is not None:
                break
            time.sleep(0.1)
        process.terminate()
        process.wait()


def pytest_sessionfinish(session, exitstatus):
    process = getattr(session.config, "_confortimetro_xvfb", None)
    if process is None:
        return
    process.terminate()
    process.wait()
