"""Servidor MCP local: acesso limitado às execuções e disparo pelo CLI."""

import json
import contextlib
import math
import os
import subprocess
import sys
import time
import uuid
from dataclasses import fields
from datetime import datetime
from functools import lru_cache

import pandas
from eppy.modeleditor import IDDAlreadySetError
from mcp.server.fastmcp import FastMCP

from confortimetro.config import SimulationConfig, default_energy_path, find_energy_path, is_energy_path
from confortimetro.paths import runs_root
from confortimetro.results import compare

SERVER = FastMCP("Ambiens")
STATUS_FILE = "mcp_status.json"
MAX_RUNS = 30
MAX_ROOMS = 30
PID_FILE = "mcp_pid.json"
MAX_ACTIVE_ENV = "AMBIENS_MCP_MAX_ACTIVE"
LEGACY_MAX_ACTIVE_ENV = "CONFORTIMETRO_MCP_MAX_ACTIVE"
ACTIVE_STATES = ("na_fila", "executando")
QUEUE_TIMEOUT = 120
INTERRUPTED = "Processo da simulação não está mais ativo"
BREAKAWAY_WARNING = ("O cliente MCP não permite desvincular processos do Job Object: "
                     "a simulação será interrompida se o cliente fechar")
WINDOWS = os.name == "nt"
CONFIG_FIELDS = {field.name for field in fields(SimulationConfig)} - {
    "met_as_watts", "_idf_path", "_met", "output_path", "runs_root_path",
    "input_path", "expanded_idf_path", "source_idf_path", "idf_filename", "code_version",
}
CONFIG_FIELDS -= {"epw_path", "energy_path", "rooms"}
PATH_FIELDS = {"idf_path", "epw_path", "energy_path", "output_path", "runs_root_path",
               "source_idf_path", "_idf_path", "input_path", "expanded_idf_path"}


def _root():
    return os.path.realpath(runs_root())


def _run_path(name: str, existing: bool = True) -> str:
    if not isinstance(name, str) or not name or name in (".", "..") or os.path.basename(name) != name:
        raise ValueError("ID de execução inválido")
    root = _root()
    path = os.path.join(root, name)
    if os.path.commonpath((root, os.path.realpath(path))) != root or os.path.islink(path):
        raise ValueError("Execução fora da raiz")
    if existing and (not os.path.isdir(path) or not (compare.is_run(path) or os.path.isfile(os.path.join(path, STATUS_FILE)))):
        raise ValueError("Execução não encontrada")
    return path


def _file(run: str, name: str) -> str:
    path = os.path.join(run, name)
    if os.path.commonpath((run, os.path.realpath(path))) != run:
        raise ValueError("Arquivo fora da execução")
    return path


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _status(run: str) -> dict:
    path = _file(run, STATUS_FILE)
    if not os.path.isfile(path):
        return {"estado": "concluida" if os.path.isfile(_file(run, "ESTATISTICAS.xlsx"))
                else "desconhecido"}
    status = _read_json(path)
    if status.get("estado") not in ACTIVE_STATES:
        return status
    # O runner grava o próprio PID ao começar; antes disso vale o PID do Popen.
    pid, started = status.get("pid"), status.get("inicio")
    pid_file = _file(run, PID_FILE)
    if not pid and os.path.isfile(pid_file):
        spawned = _read_json(pid_file)
        pid, started = spawned.get("pid"), spawned.get("inicio")
    if pid:
        dead = not _pid_alive(pid, started)
    else:
        # Servidor morreu entre reservar a pasta e disparar o runner.
        dead = time.time() - os.path.getmtime(path) > QUEUE_TIMEOUT
    if not dead:
        return status
    from confortimetro.mcp_runner import write_status
    # Releitura: o runner pode ter gravado o resultado enquanto consultávamos o PID.
    if _read_json(path).get("estado") not in ACTIVE_STATES:
        return _read_json(path)
    write_status(run, "interrompida", INTERRUPTED)
    return {"estado": "interrompida", "erro": INTERRUPTED}


def _process_start(pid: int):
    """Hora (epoch) em que o processo começou; None se não der para saber."""
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            ticks = int(handle.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/stat", encoding="utf-8") as handle:
            boot = next(int(line.split()[1]) for line in handle if line.startswith("btime "))
        return boot + ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        return None


def _pid_alive(pid: int, started: float = None) -> bool:
    """Processo existe e não é outro que reaproveitou o PID depois de `started`."""
    if WINDOWS:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform == "linux":
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
                if handle.read().rsplit(")", 1)[1].split()[0] == "Z":
                    return False  # zombie não é execução viva
        except OSError:
            return False
        begun = _process_start(pid)
        if started and begun and begun > started + 2:
            return False
    return True


@contextlib.contextmanager
def _launch_lock(root: str):
    """Serializa a reserva de vagas também entre servidores MCP independentes."""
    with open(os.path.join(root, ".mcp_launch.lock"), "a+b") as handle:
        if WINDOWS:
            import msvcrt
            handle.seek(0)
            if not handle.read(1):
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if WINDOWS:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _active_limit() -> int:
    try:
        limit = int(os.environ.get(MAX_ACTIVE_ENV) or os.environ.get(LEGACY_MAX_ACTIVE_ENV) or "2")
        if limit < 1:
            raise ValueError
        return limit
    except ValueError as error:
        raise ValueError(f"{MAX_ACTIVE_ENV} deve ser inteiro positivo") from error


def _spawn(args: list, **kwargs):
    """Abre o runner fora da sessão/Job Object do cliente; devolve (processo, aviso)."""
    if not WINDOWS:
        return subprocess.Popen(args, start_new_session=True, **kwargs), ""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    try:
        return subprocess.Popen(args, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                                **kwargs), ""
    except PermissionError:
        # Job sem JOB_OBJECT_LIMIT_BREAKAWAY_OK (ex.: stdio_client do SDK Python).
        raise PermissionError(BREAKAWAY_WARNING) from None


@lru_cache(maxsize=1)
def _energy_installation() -> str:
    """Eppy fixa o IDD no processo; a instalação não deve mudar entre chamadas."""
    energy = find_energy_path() or default_energy_path()
    if not isinstance(energy, str) or not is_energy_path(energy):
        raise ValueError("Instalação do EnergyPlus inválida")
    return os.path.realpath(energy)


def _config(args: dict, output: str) -> SimulationConfig:
    if not isinstance(args, dict):
        raise ValueError("configuracao deve ser um objeto")
    allowed = CONFIG_FIELDS | {"idf_path", "epw_path", "rooms", "met"}
    unknown = set(args) - allowed
    if unknown:
        raise ValueError(f"Campos não permitidos: {sorted(unknown)}")
    idf = args.get("idf_path")
    epw = args.get("epw_path")
    if not isinstance(idf, str) or not os.path.isabs(idf) or not os.path.isfile(idf) or not idf.lower().endswith(".idf"):
        raise ValueError("Informe um arquivo IDF existente")
    if not isinstance(epw, str) or not os.path.isabs(epw) or not os.path.isfile(epw) or not epw.lower().endswith(".epw"):
        raise ValueError("Informe um arquivo EPW existente")
    rooms = args.get("rooms")
    if not isinstance(rooms, list) or not rooms or len(rooms) > MAX_ROOMS or not all(
        isinstance(room, str) and room and room not in (".", "..")
        and "/" not in room and "\\" not in room for room in rooms
    ):
        raise ValueError("Informe uma lista de 1 a 30 zonas")
    energy = _energy_installation()
    config = SimulationConfig(met_as_watts=0, _idf_path=os.path.realpath(idf),
                              _met=1.2, epw_path=os.path.realpath(epw),
                              output_path=output, runs_root_path=_root(),
                              energy_path=energy, rooms=rooms)
    for key, value in args.items():
        if key not in {"idf_path", "epw_path", "rooms"}:
            if key == "module_type" and value not in ("COMPLETE", "CLOSED_WINDOW", "WITHOUT_FAN", "FIXED_AC_WITHOUT_FAN", "ENERGYPLUS_ONLY"):
                raise ValueError("module_type inválido")
            if key in ("ignore_missing_equipment", "clo_priority") and not isinstance(value, bool):
                raise ValueError(f"{key} deve ser booleano")
            if key not in ("module_type", "ignore_missing_equipment", "clo_priority"):
                if isinstance(value, bool) or not isinstance(value, (float, int)):
                    raise ValueError(f"{key} deve ser numérico")
                if not math.isfinite(value):
                    raise ValueError(f"{key} deve ser finito")
            setattr(config, key, value)
    if config.clo_min > config.clo_max or config.clo_delta <= 0 or config.pmv_lowerbound >= config.pmv_upperbound or config.temp_ac_min >= config.temp_ac_max:
        raise ValueError("Faixas de parâmetros inválidas")
    return config


@SERVER.tool()
def listar_execucoes() -> dict:
    """Lista até 30 execuções da raiz local, com estado e zonas (sem séries)."""
    root = _root()
    if not os.path.isdir(root):
        return {"execucoes": [], "total": 0}
    names = sorted(os.listdir(root), reverse=True)
    rows = []
    for name in names:
        try:
            run = _run_path(name)
            # Evita que os leitores de compare sigam marcadores/planilhas externos.
            for filename in (*compare.RUN_MARKERS, "ESTATISTICAS.xlsx", STATUS_FILE):
                _file(run, filename)
            config = compare.read_config(run) if compare.is_run(run) else {}
            rooms = config.get("rooms") if isinstance(config.get("rooms"), list) else []
            rows.append({"id": name, "estado": _status(run)["estado"],
                         "resultado": "com estatísticas" if os.path.isfile(_file(run, "ESTATISTICAS.xlsx")) else "pendente",
                         "zonas": [room for room in rooms[:MAX_ROOMS] if isinstance(room, str)]})
        except (ValueError, OSError, KeyError):
            continue
        if len(rows) == MAX_RUNS:
            break
    return {"execucoes": rows, "limite": MAX_RUNS}


@SERVER.tool()
def ler_execucao(id: str) -> dict:
    """Lê a configuração e os indicadores agregados de uma execução (até 30 zonas)."""
    run = _run_path(id)
    if not compare.is_run(run):
        return {"id": id, "estado": _status(run), "configuracao": {}, "indicadores": []}
    for name in (*compare.RUN_MARKERS, "ESTATISTICAS.xlsx", STATUS_FILE):
        _file(run, name)
    config = compare.read_config(run)
    safe = {key: value for key, value in config.items()
            if key not in PATH_FIELDS and key in CONFIG_FIELDS | {"_met", "rooms", "module_type"}
            and isinstance(value, (str, int, float, bool)) and (not isinstance(value, str) or len(value) <= 200)}
    if isinstance(config.get("rooms"), list):
        safe["rooms"] = [room[:100] for room in config["rooms"][:MAX_ROOMS]
                         if isinstance(room, str)]
    stats = _file(run, "ESTATISTICAS.xlsx")
    indicators = []
    if os.path.isfile(stats):
        df = pandas.read_excel(stats, usecols=lambda column: column == "Nome da sala" or column in compare.COMPARISON_COLUMNS, nrows=MAX_ROOMS)
        indicators = json.loads(df.to_json(orient="records"))
    return {"id": id, "estado": _status(run), "configuracao": safe,
            "indicadores": indicators, "limite_zonas": MAX_ROOMS}


@SERVER.tool()
def validar_configuracao(configuracao: dict) -> dict:
    """Valida caminhos, parâmetros e IDF sem iniciar simulação nem criar execução."""
    try:
        config = _config(configuracao, os.path.join(_root(), "validacao"))
        from confortimetro.idf import IDFProcessor, read_zone_names
        zones = read_zone_names(config.idf_path)
        missing = [room for room in config.rooms if room not in zones]
        errors = [f"Zonas ausentes no IDF: {missing}"] if missing else []
        if not errors:
            errors = IDFProcessor(config).validate_idf()
        return {"valida": not errors, "erros": errors[:20]}
    except IDDAlreadySetError:
        # O eppy fixa um IDD por processo; a instalação mudou desde a 1ª validação.
        return {"valida": False, "erros": ["A instalação do EnergyPlus mudou; reinicie o servidor MCP"]}
    except (ValueError, OSError, TypeError) as error:
        return {"valida": False, "erros": [str(error)]}


@SERVER.tool()
def iniciar_simulacao(configuracao: dict) -> dict:
    """Valida e inicia uma simulação em processo separado; retorna imediatamente o ID."""
    validation = validar_configuracao(configuracao)
    if not validation["valida"]:
        return validation
    root = _root()
    os.makedirs(root, exist_ok=True)
    with _launch_lock(root):
        active = 0
        for entry in os.scandir(root):
            if entry.is_dir(follow_symlinks=False) and os.path.isfile(os.path.join(entry.path, STATUS_FILE)):
                try:
                    if _status(_run_path(entry.name))["estado"] in ACTIVE_STATES:
                        active += 1
                except (ValueError, OSError, KeyError, json.JSONDecodeError):
                    continue
        if active >= _active_limit():
            return {"estado": "recusada", "erro": "Limite de simulações simultâneas atingido"}
        while True:
            name = f"{datetime.now().strftime('%Y%m%d_%H%M')}_mcp_{uuid.uuid4().hex[:12]}"
            run = _run_path(name, existing=False)
            try:
                os.mkdir(run)
                break
            except FileExistsError:
                continue
        try:
            config = _config(configuracao, run)
        except Exception:
            os.rmdir(run)
            raise
        config_path = _file(run, "entrada_mcp.json")
        config.to_json(config_path)
        from confortimetro.mcp_runner import write_status
        write_status(run, "na_fila")
        try:
            with open(_file(run, "mcp.log"), "w", encoding="utf-8") as log:
                process, warning = _spawn(
                    [sys.executable, "-m", "confortimetro.mcp_runner", config_path],
                    cwd=os.path.dirname(os.path.dirname(__file__)),
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True)
            with open(_file(run, PID_FILE), "w", encoding="utf-8") as handle:
                json.dump({"pid": process.pid, "inicio": time.time()}, handle)
        except OSError as error:
            write_status(run, "falhou", str(error))
            return {"id": name, "pasta": run, "estado": "falhou", "erro": str(error)}
    started = {"id": name, "pasta": run, "estado": "na_fila"}
    return {**started, "aviso": warning} if warning else started


@SERVER.tool()
def estado_simulacao(id: str) -> dict:
    """Consulta o estado persistido da execução, inclusive após reiniciar o MCP."""
    return {"id": id, **_status(_run_path(id))}


def main():
    SERVER.run(transport="stdio")


if __name__ == "__main__":
    main()
