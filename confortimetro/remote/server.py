"""Servidor HTTP do Ambiens: recebe simulações, executa em fila e devolve o espelho.

    python -m confortimetro.remote.server usuario NOME [--admin]   # cria/reemite o token
    python -m confortimetro.remote.server servir --porta 8765

Um processo só (nada de `--workers`): o agendador vive dentro dele. Cada
execução é uma pasta em `runs_root()/<usuário>/<id>` e roda num processo
próprio (`executar`), como as do MCP — o estado fica no `mcp_status.json` e
sobrevive a um reinício do servidor. TLS é do proxy reverso (Traefik, Caddy).
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime

from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from confortimetro import mcp_server as runs
from confortimetro.mcp_runner import write_status
from confortimetro.paths import app_data_path
from confortimetro.versao import code_version

logger = logging.getLogger("ambiens.servidor")

TOKENS_FILE = "servidor_tokens.json"
CONFIG_FILE = "entrada_servidor.json"
LOG_FILE = "progresso.log"
PROCESS_LOG = "servidor.log"
INPUT_DIR = "entrada"
MIRROR = "espelho.zip"
WAITING = "aguardando"
CANCELLED = "cancelada"
QUOTA_ENV = "AMBIENS_COTA_GB"
MAX_UPLOAD = 200 * 1024 * 1024
TICK_S = 5
QUOTA_INTERVAL_S = 600
USER_RE = re.compile(r"[a-z0-9_-]{1,32}")
ID_RE = re.compile(r"\d{8}_\d{4}_[0-9a-f]{12}")
# Arquivos internos do servidor: nunca vão para o cliente.
INTERNAL = r"mcp_.*|servidor\.log|entrada_servidor\.json|espelho\.zip.*|completo\..*"
# O espelho também deixa de fora os brutos do EnergyPlus: o app não os lê, e o
# eplusout.eso sozinho passa de 1 GB numa simulação anual.
MIRROR_SKIP = re.compile(r"eplusout\..*|in\.idf|expanded\.idf|sqlite\.err|" + INTERNAL)
FULL_SKIP = re.compile(INTERNAL)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_children = []  # Popen dos runners: `poll()` no tick evita processos zumbis
_quota = {}
_eppy_lock = threading.Lock()  # o eppy guarda o IDD em estado global da classe


# --- Usuários ---------------------------------------------------------------

def _tokens_path() -> str:
    return os.path.join(app_data_path(), TOKENS_FILE)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _load_tokens() -> dict:
    try:
        with open(_tokens_path(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def add_user(name: str, admin: bool = False) -> str:
    """Cria o usuário ou troca o token dele; devolve o token, mostrado uma vez só."""
    if not USER_RE.fullmatch(name):
        raise ValueError("Nome de usuário: 1 a 32 de a-z, 0-9, _ ou -")
    token = secrets.token_urlsafe(32)
    tokens = {key: user for key, user in _load_tokens().items() if user["usuario"] != name}
    tokens[_hash(token)] = {"usuario": name, "admin": admin}
    path = _tokens_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w",
              encoding="utf-8") as handle:
        json.dump(tokens, handle, indent=2)
    os.replace(temporary, path)
    return token


def _auth(request) -> dict:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    user = _load_tokens().get(_hash(token.strip())) if scheme.lower() == "bearer" else None
    if not user:
        raise HTTPException(401, "Token inválido")
    return user


# --- Execuções --------------------------------------------------------------

def _user_runs(base: str):
    """Pastas de execução de todos os usuários."""
    for user in os.scandir(base):
        if user.is_dir(follow_symlinks=False) and USER_RE.fullmatch(user.name):
            for run in os.scandir(user.path):
                if run.is_dir(follow_symlinks=False) and os.path.isfile(
                        os.path.join(run.path, runs.STATUS_FILE)):
                    yield run.path


def _run(user: dict, run_id: str) -> str:
    """Pasta da execução, se ela existe e o usuário pode vê-la (admin vê todas)."""
    if ID_RE.fullmatch(run_id):
        base = runs._root()
        owners = os.listdir(base) if user["admin"] and os.path.isdir(base) else [user["usuario"]]
        for owner in owners:
            path = os.path.join(base, owner, run_id)
            if USER_RE.fullmatch(owner) and os.path.isfile(os.path.join(path, runs.STATUS_FILE)):
                return path
    raise HTTPException(404, "Execução não encontrada")


def _safe_name(filename: str, extension: str) -> str:
    name = re.sub(r"[^\w.-]", "_", os.path.basename((filename or "").replace("\\", "/")))
    return name if name.lower().endswith(extension) and name != extension else f"arquivo{extension}"


def _launch(run: str):
    write_status(run, "na_fila")
    try:
        with open(os.path.join(run, PROCESS_LOG), "w", encoding="utf-8") as log:
            process, _ = runs._spawn(
                [sys.executable, "-m", "confortimetro.remote.server", "executar",
                 os.path.join(run, CONFIG_FILE)],
                cwd=REPO_ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, close_fds=True)
        _children.append(process)
        with open(os.path.join(run, runs.PID_FILE), "w", encoding="utf-8") as handle:
            json.dump({"pid": process.pid, "inicio": time.time()}, handle)
    except OSError as error:
        write_status(run, "falhou", str(error))


def tick():
    """Dispara as execuções em espera, mais antigas primeiro, até o limite."""
    _children[:] = [child for child in _children if child.poll() is None]
    base = runs._root()
    os.makedirs(base, exist_ok=True)
    with runs._launch_lock(base):
        waiting, active = [], 0
        for run in _user_runs(base):
            try:
                state = runs._status(run)["estado"]
            except (OSError, ValueError, KeyError):
                continue
            if state in runs.ACTIVE_STATES:
                active += 1
            elif state == WAITING:
                waiting.append(run)
        waiting.sort(key=lambda run: os.path.getmtime(os.path.join(run, CONFIG_FILE)))
        for run in waiting[:max(0, runs._active_limit() - active)]:
            _launch(run)


def check_quota():
    """Uso do disco contra `AMBIENS_COTA_GB`; avisa no log ao passar do limite."""
    limit = float(os.environ.get(QUOTA_ENV) or 0)
    if limit <= 0:
        _quota.clear()
        return
    used = sum(os.path.getsize(os.path.join(root, name))
               for root, _, files in os.walk(runs._root()) for name in files
               if not os.path.islink(os.path.join(root, name))) / 1024 ** 3
    exceeded = used > limit
    if exceeded:
        # ponytail: só no log (e no /api/eu do admin); e-mail/Telegram via sidecar lendo o log.
        logger.warning("COTA EXCEDIDA: %.1f GB usados de %.1f GB", used, limit)
    _quota.update(usado_gb=round(used, 1), limite_gb=limit, excedida=exceeded)


def _build_zip(run: str, path: str, skip=MIRROR_SKIP):
    """Zip da execução menos `skip`; `configs.json` por último marca o download completo."""
    temporary = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for root, dirs, files in os.walk(run):
            dirs[:] = [name for name in dirs if name != ".series_cache"]
            for name in files:
                full = os.path.join(root, name)
                relative = os.path.relpath(full, run).replace(os.sep, "/")
                if relative != "configs.json" and not skip.fullmatch(name) \
                        and not os.path.islink(full):
                    archive.write(full, relative)
        if os.path.isfile(os.path.join(run, "configs.json")):
            archive.write(os.path.join(run, "configs.json"), "configs.json")
    os.replace(temporary, path)


# --- Rotas ------------------------------------------------------------------

def me(request):
    user = _auth(request)
    body = {"usuario": user["usuario"], "admin": user["admin"], "versao": code_version()}
    if user["admin"] and _quota:
        body["cota"] = dict(_quota)
    return JSONResponse(body)


def list_runs(request):
    user = _auth(request)
    base = runs._root()
    every = user["admin"] and request.query_params.get("todas") == "1"
    rows = []
    for run in (_user_runs(base) if os.path.isdir(base) else ()):
        owner = os.path.basename(os.path.dirname(run))
        if every or owner == user["usuario"]:
            status = runs._status(run)
            rows.append({"id": os.path.basename(run), "usuario": owner,
                         "estado": status["estado"], "erro": status.get("erro", "")})
    rows.sort(key=lambda row: row["id"], reverse=True)
    return JSONResponse({"execucoes": rows})


async def submit(request):
    user = _auth(request)
    if int(request.headers.get("content-length") or 0) > MAX_UPLOAD:
        raise HTTPException(413, "Arquivos grandes demais")
    form = await request.form(max_files=2, max_fields=1)
    try:
        args = json.loads(form["configuracao"])
        uploads = {"idf_path": (form["idf"], ".idf"), "epw_path": (form["epw"], ".epw")}
    except (KeyError, ValueError):
        raise HTTPException(400, "Envie configuracao (JSON), idf e epw") from None
    if not isinstance(args, dict):
        raise HTTPException(400, "configuracao deve ser um objeto")
    # O cliente manda a configuração inteira; caminhos e campos internos ficam aqui.
    args = {key: value for key, value in args.items()
            if key in runs.CONFIG_FIELDS | {"rooms", "met"}}

    run_id = f"{datetime.now():%Y%m%d_%H%M}_{uuid.uuid4().hex[:12]}"
    run = os.path.join(runs._root(), user["usuario"], run_id)
    os.makedirs(os.path.join(run, INPUT_DIR))
    try:
        for key, (upload, extension) in uploads.items():
            args[key] = os.path.join(run, INPUT_DIR, _safe_name(upload.filename, extension))
            with open(args[key], "wb") as handle:
                await run_in_threadpool(shutil.copyfileobj, upload.file, handle)

        def validate():
            with _eppy_lock:
                return runs.validar_configuracao(args)

        result = await run_in_threadpool(validate)
        if not result["valida"]:
            raise HTTPException(400, "; ".join(result["erros"]))
        runs._config(args, run).to_json(os.path.join(run, CONFIG_FILE))
        write_status(run, WAITING)
    except BaseException:
        shutil.rmtree(run, ignore_errors=True)
        raise
    await run_in_threadpool(tick)
    return JSONResponse({"id": run_id, "estado": runs._status(run)["estado"]}, status_code=201)


def status(request):
    run = _run(_auth(request), request.path_params["id"])
    return JSONResponse({"id": request.path_params["id"], **runs._status(run)})


def log(request):
    """Linhas completas do progresso a partir do byte `desde`."""
    run = _run(_auth(request), request.path_params["id"])
    try:
        offset = max(0, int(request.query_params.get("desde", "0")))
    except ValueError:
        raise HTTPException(400, "desde deve ser inteiro") from None
    try:
        with open(os.path.join(run, LOG_FILE), "rb") as handle:
            handle.seek(offset)
            chunk = handle.read(1024 * 1024)
    except FileNotFoundError:
        chunk = b""
    chunk = chunk[:chunk.rfind(b"\n") + 1]
    return JSONResponse({"texto": chunk.decode("utf-8", "replace"), "proximo": offset + len(chunk)})


def cancel(request):
    run = _run(_auth(request), request.path_params["id"])
    with runs._launch_lock(runs._root()):
        current = runs._status(run)
        if current["estado"] in runs.ACTIVE_STATES:
            pid = current.get("pid")
            if not pid:
                with open(os.path.join(run, runs.PID_FILE), encoding="utf-8") as handle:
                    pid = json.load(handle)["pid"]
            # O runner abre sessão própria (pgid == pid): leva junto o ExpandObjects.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pid, signal.SIGKILL)
        elif current["estado"] != WAITING:
            raise HTTPException(409, f"Execução já {current['estado']}")
        write_status(run, CANCELLED, "Cancelada pelo usuário")
    return JSONResponse({"id": request.path_params["id"], "estado": CANCELLED})


def mirror(request):
    """Espelho leve (guardado para os próximos downloads) ou, com `completo=1`,
    a execução inteira com os brutos, num zip apagado depois do envio."""
    run = _run(_auth(request), request.path_params["id"])
    if runs._status(run)["estado"] != "concluida":
        raise HTTPException(409, "Execução não concluída")
    filename = f"{request.path_params['id']}.zip"
    if request.query_params.get("completo") == "1":
        path = os.path.join(run, f"completo.{uuid.uuid4().hex}.zip")
        _build_zip(run, path, FULL_SKIP)
        return FileResponse(path, filename=filename, background=BackgroundTask(os.remove, path))
    path = os.path.join(run, MIRROR)
    if not os.path.isfile(path):
        _build_zip(run, path)
    return FileResponse(path, filename=filename)


async def _error(request, exc):
    return JSONResponse({"erro": exc.detail}, status_code=exc.status_code)


async def _scheduler():
    last_quota = 0.0
    while True:
        try:
            await asyncio.to_thread(tick)
            if time.monotonic() - last_quota > QUOTA_INTERVAL_S:
                last_quota = time.monotonic()
                await asyncio.to_thread(check_quota)
        except Exception:
            logger.exception("Falha no agendador")
        await asyncio.sleep(TICK_S)


@contextlib.asynccontextmanager
async def _lifespan(app):
    task = asyncio.create_task(_scheduler())
    yield
    task.cancel()


def create_app(scheduler: bool = True) -> Starlette:
    return Starlette(
        routes=[
            Route("/api/eu", me),
            Route("/api/execucoes", list_runs),
            Route("/api/execucoes", submit, methods=["POST"]),
            Route("/api/execucoes/{id}", status),
            Route("/api/execucoes/{id}/log", log),
            Route("/api/execucoes/{id}/cancelar", cancel, methods=["POST"]),
            Route("/api/execucoes/{id}/espelho", mirror),
        ],
        exception_handlers={HTTPException: _error},
        lifespan=_lifespan if scheduler else None,
    )


# --- Processo de uma execução -----------------------------------------------

class _LogQueue:
    """A `Queue` que a `Simulation` espera, gravando cada mensagem no progresso.log."""

    def __init__(self, path: str):
        self.path = path

    def put(self, message):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(f"{str(message).rstrip()}\n")


def execute(config_path: str) -> int:
    from confortimetro.config import SimulationConfig
    from confortimetro.simulation import Simulation

    run = os.path.dirname(os.path.realpath(config_path))
    write_status(run, "executando", pid=os.getpid())
    try:
        Simulation(SimulationConfig.from_json(config_path)).run(_LogQueue(os.path.join(run, LOG_FILE)))
    except Exception as error:
        write_status(run, "falhou", str(error))
        return 1
    write_status(run, "concluida")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Servidor de simulações do Ambiens")
    commands = parser.add_subparsers(dest="comando", required=True)
    serve = commands.add_parser("servir")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--porta", type=int, default=8765)
    user = commands.add_parser("usuario")
    user.add_argument("nome")
    user.add_argument("--admin", action="store_true")
    run = commands.add_parser("executar")
    run.add_argument("config")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    if args.comando == "usuario":
        print(add_user(args.nome, args.admin))
        return 0
    if args.comando == "executar":
        return execute(args.config)
    import uvicorn
    uvicorn.run(create_app(), host=args.host, port=args.porta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
