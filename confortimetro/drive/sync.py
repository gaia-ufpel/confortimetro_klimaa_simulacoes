"""Espelho das execuções na pasta "Ambiens" do Google Drive, e compartilhamento.

Cada execução vira uma subpasta com o nome da pasta local e um id único
(`.drive_id` na pasta local, `appProperties` na remota): só a pasta remota de
mesmo id é a da execução, e um nome já usado por outra ganha sufixo
("run_001 (2)"). O estado em `app_data_path()/drive.json` guarda execução →
pasta e arquivo → (id, tamanho, mtime): reenviar só o que mudou é comparar a
assinatura local com a gravada. Execução que falha (sem rede, erro da API)
entra em `pending` e é tentada de novo na próxima abertura ou simulação; token
revogado ou ausente marca `reconnect`.

Tudo aqui faz rede e pode levar minutos: chame fora da thread da interface.
As funções recebem o serviço do Drive pronto (`auth.service()`), o que deixa
os testes trocá-lo por um falso.
"""

import json
import logging
import os
import re
import shutil
import threading
import uuid

from ..assistant.store import _write_json
from ..paths import app_data_path
from . import auth

STATE_FILE = "drive.json"
ROOT_NAME = "Ambiens"
FOLDER_MIME = "application/vnd.google-apps.folder"
FOLDER_URL = "https://drive.google.com/drive/folders/{}"
# Mesmos marcadores de `compare.RUN_MARKERS`; repetidos para não importar o
# pandas só para saber o nome de dois arquivos.
RUN_MARKERS = ("configs.json", "parameters.txt")
# Só o que a interface lê de uma execução vai para o Drive: configuração
# (listagem, duplicar), planilhas (zonas, estatísticas, séries, comparação),
# `modelo.idf` e `eplustbl.csv` (assistente), o relatório HTML e imagens.
# O resto do EnergyPlus (`eplusout.eso/.err/.csv/.sql`…) chega a GB.
MIRRORED_FILES = {"configs.json", "parameters.txt", "modelo.idf", "eplustbl.csv"}
MIRRORED_SUFFIXES = (".xlsx", ".htm", ".html", ".png", ".jpg", ".jpeg", ".svg")
MAX_FILE_BYTES = 50 * 1024 * 1024
ID_FILE = ".drive_id"
APP_KEY = "ambiens_run_id"
EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")

SYNCED, SENDING, PENDING, ERROR = "sincronizado", "enviando", "pendente", "erro"

# ponytail: um lock global serializa toda operação com o Drive (envio, pull,
# compartilhar); um envio longo faz o compartilhar esperar. Lock por execução
# se isso incomodar.
_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


# --- Estado ----------------------------------------------------------------

def state_path() -> str:
    return os.path.join(app_data_path(), STATE_FILE)


def load_state() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (OSError, ValueError):
        state = {}
    state.setdefault("runs", {})
    state.setdefault("pending", [])
    return state


def save_state(state: dict):
    """Grava o estado; falha (mesmo depois das novas tentativas) vira DriveError."""
    try:
        _write_json(state_path(), state)
    except OSError as error:
        raise auth.DriveError(f"Não foi possível gravar o estado do Drive "
                              f"({state_path()}): {error}") from error


def is_connected(state: dict = None) -> bool:
    """Há cliente OAuth e uma conta conectada (o token mora no keyring)."""
    return bool(auth.client_path() and (state or load_state()).get("account"))


def run_status(name: str, state: dict = None):
    """sincronizado / enviando / pendente / erro, ou `None` se nunca enviada."""
    entry = (state or load_state())["runs"].get(name)
    return entry.get("status") if entry else None


# --- Conta -----------------------------------------------------------------

def connect() -> str:
    """Login no navegador; grava a conta no estado e devolve o e-mail.

    Não envia nada: quem chama dispara `sync_all` (backfill + pull) depois.
    """
    service = auth.connect()
    about = service.about().get(fields="user(emailAddress)").execute()
    email = about.get("user", {}).get("emailAddress") or "conta Google"
    with _LOCK:
        state = load_state()
        state["account"] = email
        state["reconnect"] = False
        save_state(state)
    return email


def connected_service():
    """Serviço do Drive, ou `None`.

    Conta no estado sem token no keyring (cofre limpo, outro usuário do
    sistema) marca `reconnect`: o card de Configurações pede para conectar.
    """
    service = auth.service()
    if service is None and is_connected() and not auth.refresh_token():
        with _LOCK:
            state = load_state()
            if not state.get("reconnect"):
                state["reconnect"] = True
                save_state(state)
    return service


def disconnect():
    """Apaga o token do keyring e o estado; os arquivos no Drive ficam."""
    with _LOCK:
        auth.forget_token()
        if os.path.exists(state_path()):
            os.remove(state_path())


# --- Drive -----------------------------------------------------------------

def _quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def _list(service, query: str, fields: str = "id,name"):
    items, token = [], None
    while True:
        response = service.files().list(q=query, spaces="drive", pageToken=token,
                                         fields=f"nextPageToken,files({fields})").execute()
        items += response.get("files", [])
        token = response.get("nextPageToken")
        if not token:
            return items


def _folder(service, name: str, parent: str):
    """Id da pasta `name` em `parent`; cria se não existir. (id, criada?)."""
    found = _list(service, f"name='{_quote(name)}' and '{parent}' in parents and "
                           f"mimeType='{FOLDER_MIME}' and trashed=false")
    if found:
        return found[0]["id"], False
    body = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}
    return service.files().create(body=body, fields="id").execute()["id"], True


def _root(service, state: dict) -> str:
    if not state.get("root_id"):
        state["root_id"], _ = _folder(service, ROOT_NAME, "root")
        save_state(state)
    return state["root_id"]


def _media(path: str):
    from googleapiclient.http import MediaFileUpload

    return MediaFileUpload(path, resumable=True)


def _download(service, file_id: str, path: str):
    from googleapiclient.http import MediaIoBaseDownload

    with open(path, "wb") as output:
        downloader = MediaIoBaseDownload(output, service.files().get_media(fileId=file_id),
                                         chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _status_code(error):
    return getattr(getattr(error, "resp", None), "status", None)


def _is_auth_error(error) -> bool:
    """Token revogado/expirado: só reconectar resolve."""
    return _status_code(error) == 401 or type(error).__name__ == "RefreshError"


def _safe_name(name: str) -> bool:
    """Nome vindo do Drive que pode virar caminho local sem sair da pasta."""
    return bool(name) and not name.startswith(".") and "/" not in name and "\\" not in name


def _free_name(name: str, taken) -> str:
    """`name`, ou "name (2)", "name (3)"… o primeiro fora de `taken`."""
    candidate, number = name, 1
    while candidate in taken:
        number += 1
        candidate = f"{name} ({number})"
    return candidate


def run_files(run_path: str) -> list:
    """Arquivos do espelho: os permitidos do primeiro nível, até `MAX_FILE_BYTES`."""
    names = []
    for name in sorted(os.listdir(run_path)):
        path = os.path.join(run_path, name)
        if (name.startswith((".", "~$")) or not os.path.isfile(path)
                or not (name in MIRRORED_FILES or name.lower().endswith(MIRRORED_SUFFIXES))):
            continue
        if os.path.getsize(path) > MAX_FILE_BYTES:
            logger.warning("Drive: %s fica fora do envio (%d MB, limite de %d MB).", path,
                           os.path.getsize(path) // 2**20, MAX_FILE_BYTES // 2**20)
            continue
        names.append(name)
    return names


def _run_id(run_path: str, entry: dict) -> str:
    """Id da execução, de `ID_FILE` na pasta (criado na primeira vez).

    Id diferente do registrado é outra execução numa pasta de mesmo nome:
    o registro anterior é descartado e ela ganha uma pasta remota própria.
    """
    path = os.path.join(run_path, ID_FILE)
    try:
        with open(path, encoding="utf-8") as id_file:
            run_id = id_file.read().strip()
    except OSError:
        run_id = ""
    if not run_id:
        run_id = uuid.uuid4().hex
        stat = os.stat(run_path)
        with open(path, "w", encoding="utf-8") as id_file:
            id_file.write(run_id)
        # A listagem ordena pelo mtime da pasta; o id não é uma modificação.
        os.utime(run_path, (stat.st_atime, stat.st_mtime))
    if entry.get("run_id") != run_id:
        entry.clear()
        entry.update(run_id=run_id, files={})
    return run_id


def _changed_files(run_path: str, entry: dict) -> list:
    """(nome, [tamanho, mtime]) dos arquivos diferentes do último envio."""
    changed = []
    for file_name in run_files(run_path):
        path = os.path.join(run_path, file_name)
        signature = [os.path.getsize(path), os.path.getmtime(path)]
        known = entry["files"].get(file_name)
        if not known or known[1:] != signature:
            changed.append((file_name, signature))
    return changed


# --- Envio -----------------------------------------------------------------

def _notify(on_change):
    if on_change:
        try:
            on_change()
        except Exception:
            pass


def _run_folder(service, state: dict, run_path: str, entry: dict):
    """Pasta remota com o id da execução; sem ela, cria uma com nome livre.

    Pasta de mesmo nome e outro id é de outra execução (outra máquina): fica
    intocada, e esta vai para "nome (2)". (id, criada?).
    """
    root = _root(service, state)
    folders = f"'{root}' in parents and mimeType='{FOLDER_MIME}' and trashed=false"
    found = _list(service, folders + f" and appProperties has {{ key='{APP_KEY}' and "
                                     f"value='{entry['run_id']}' }}")
    if found:
        return found[0]["id"], False
    taken = {folder["name"] for folder in _list(service, folders)}
    body = {"name": _free_name(os.path.basename(os.path.normpath(run_path)), taken),
            "mimeType": FOLDER_MIME, "parents": [root],
            "appProperties": {APP_KEY: entry["run_id"]}}
    return service.files().create(body=body, fields="id").execute()["id"], True


def _push(service, state: dict, run_path: str, entry: dict):
    if not entry.get("folder_id"):
        entry["folder_id"], created = _run_folder(service, state, run_path, entry)
        if not created:
            # A pasta desta execução já existia (estado perdido): adota os
            # arquivos de mesmo nome e tamanho em vez de reenviá-los.
            # ponytail: compara só o tamanho; mudança que não altera o tamanho
            # passa despercebida até o arquivo mudar de novo.
            for remote in _list(service, f"'{entry['folder_id']}' in parents and trashed=false",
                                "id,name,size"):
                local = os.path.join(run_path, remote["name"])
                if os.path.isfile(local) and str(os.path.getsize(local)) == str(remote.get("size")):
                    entry["files"][remote["name"]] = [remote["id"], os.path.getsize(local),
                                                      os.path.getmtime(local)]
                elif remote["name"] not in entry["files"]:
                    entry["files"][remote["name"]] = [remote["id"], None, None]
        save_state(state)

    # ponytail: sem detecção de conflito — a última versão local vence e
    # sobrescreve a do Drive. Arquivo apagado localmente continua no Drive.
    for file_name, signature in _changed_files(run_path, entry):
        path = os.path.join(run_path, file_name)
        known = entry["files"].get(file_name)
        if known:
            service.files().update(fileId=known[0], media_body=_media(path),
                                   fields="id").execute()
            file_id = known[0]
        else:
            file_id = service.files().create(
                body={"name": file_name, "parents": [entry["folder_id"]]},
                media_body=_media(path), fields="id").execute()["id"]
        entry["files"][file_name] = [file_id] + signature
        # Gravado a cada arquivo: uma queda no meio não reenvia o que já foi.
        save_state(state)


def push_run(service, run_path: str, on_change=None) -> bool:
    """Envia o que mudou na execução; em falha, deixa pendente. True se ok."""
    run_path = os.path.abspath(run_path)
    name = os.path.basename(os.path.normpath(run_path))
    with _LOCK:
        state = load_state()
        entry = state["runs"].setdefault(name, {"files": {}})
        _run_id(run_path, entry)
        send = not entry.get("folder_id") or bool(_changed_files(run_path, entry))
        if not send and entry.get("status") == SYNCED and run_path not in state["pending"]:
            return True  # nada mudou: nenhuma chamada, nenhuma gravação
        if send:
            entry["status"] = SENDING
            save_state(state)
            _notify(on_change)
            try:
                try:
                    _push(service, state, run_path, entry)
                except Exception as error:
                    if _status_code(error) != 404:
                        raise
                    # Pasta ou arquivo apagado no Drive: recomeça do zero, uma vez.
                    state.pop("root_id", None)
                    entry["folder_id"], entry["files"] = None, {}
                    _push(service, state, run_path, entry)
            except Exception as error:
                if _is_auth_error(error):
                    state["reconnect"] = True
                code = _status_code(error)
                # 4xx que não é de autenticação nem limite não melhora sozinho;
                # nem o estado que não pôde ser gravado.
                permanent = isinstance(error, auth.DriveError) or (
                    code is not None and 400 <= code < 500 and code not in (401, 408, 429))
                entry["status"] = ERROR if permanent else PENDING
                entry["error"] = str(error)[:300]
                if run_path not in state["pending"]:
                    state["pending"].append(run_path)
                save_state(state)
                _notify(on_change)
                if isinstance(error, auth.DriveError):
                    raise
                return False
            # O Drive aceitou o envio: o token voltou a valer.
            state["reconnect"] = False
        entry["status"] = SYNCED
        entry.pop("error", None)
        if run_path in state["pending"]:
            state["pending"].remove(run_path)
        save_state(state)
    _notify(on_change)
    return True


def pull(service, outputs_root: str, on_change=None) -> list:
    """Baixa as execuções que estão no Drive e nunca passaram por esta máquina.

    Execução que esta máquina já conhece (enviou ou baixou) não volta: apagar
    localmente não ressuscita a pasta. Devolve os nomes baixados.
    """
    pulled = []
    with _LOCK:
        state = load_state()
        known = {entry.get("run_id") for entry in state["runs"].values()}
        root = _root(service, state)
        for folder in _list(service, f"'{root}' in parents and mimeType='{FOLDER_MIME}' "
                                     "and trashed=false", "id,name,appProperties"):
            run_id = (folder.get("appProperties") or {}).get(APP_KEY)
            if not run_id or run_id in known or not _safe_name(folder["name"]):
                continue
            files = [item for item in _list(
                service, f"'{folder['id']}' in parents and mimeType!='{FOLDER_MIME}' "
                         "and trashed=false") if _safe_name(item["name"])]
            if not any(item["name"] in RUN_MARKERS for item in files):
                continue
            # Nome local de outra execução (ou de uma já conhecida e apagada):
            # baixa ao lado, com sufixo, sem tocar na existente.
            os.makedirs(outputs_root, exist_ok=True)
            name = _free_name(folder["name"], set(os.listdir(outputs_root)) | set(state["runs"]))
            target = os.path.join(outputs_root, name)
            # Baixa numa pasta oculta e só renomeia no fim: a listagem nunca vê
            # uma execução pela metade.
            partial = os.path.join(outputs_root, f".{name}.partial")
            shutil.rmtree(partial, ignore_errors=True)
            os.makedirs(partial)
            entry = {"run_id": run_id, "folder_id": folder["id"], "files": {}}
            for item in files:
                path = os.path.join(partial, item["name"])
                _download(service, item["id"], path)
                entry["files"][item["name"]] = [item["id"], os.path.getsize(path),
                                                os.path.getmtime(path)]
            with open(os.path.join(partial, ID_FILE), "w", encoding="utf-8") as id_file:
                id_file.write(run_id)
            os.replace(partial, target)
            entry["status"] = SYNCED
            state["runs"][name] = entry
            known.add(run_id)
            save_state(state)
            pulled.append(name)
            _notify(on_change)
    return pulled


def sync_all(service, outputs_root: str, on_change=None) -> dict:
    """Envia todas as execuções de `outputs_root` e as pendentes; depois, pull.

    É o backfill da primeira conexão e o que roda a cada abertura do app: o
    que não mudou não gera chamada nenhuma de envio.
    """
    from ..results.compare import is_run

    with _LOCK:
        paths = []
        if os.path.isdir(outputs_root):
            for name in sorted(os.listdir(outputs_root)):
                path = os.path.abspath(os.path.join(outputs_root, name))
                if not name.startswith(".") and os.path.isdir(path) and is_run(path):
                    paths.append(path)
        paths += [path for path in load_state()["pending"]
                  if path not in paths and os.path.isdir(path)]

        failed = [path for path in paths if not push_run(service, path, on_change)]
        state = load_state()
        if state.get("reconnect"):
            return {"pushed": len(paths) - len(failed), "failed": failed, "pulled": []}
        try:
            pulled = pull(service, outputs_root, on_change)
        except Exception as error:
            if _is_auth_error(error):
                state = load_state()
                state["reconnect"] = True
                save_state(state)
            pulled = []
        return {"pushed": len(paths) - len(failed), "failed": failed, "pulled": pulled}


def push_after_run(run_path: str, on_change=None):
    """Envio automático ao fim de uma simulação (GUI e CLI), e das pendentes.

    Sem conta conectada não faz nada e devolve `None`; senão, o status final
    da execução. Depois dela, na mesma thread, vão as execuções que ficaram em
    `pending` (falhas anteriores). Falha ao montar o serviço também vira
    pendente, para a próxima abertura.
    """
    if not is_connected():
        return None
    run_path = os.path.abspath(run_path)
    try:
        service = connected_service()
    except Exception:
        service = None
    if service is None:
        with _LOCK:
            state = load_state()
            if run_path not in state["pending"]:
                state["pending"].append(run_path)
            state["runs"].setdefault(os.path.basename(os.path.normpath(run_path)),
                                     {"files": {}})["status"] = PENDING
            save_state(state)
        return PENDING
    push_run(service, run_path, on_change)
    status = run_status(os.path.basename(os.path.normpath(run_path)))
    if not load_state().get("reconnect"):
        for path in load_state()["pending"]:
            if path != run_path and os.path.isdir(path):
                push_run(service, path, on_change)
    return status


# --- Compartilhamento ------------------------------------------------------

def _synced_folder(service, run_path: str) -> str:
    """Pasta da execução no Drive, enviando o que faltar antes."""
    if not push_run(service, run_path):
        entry = load_state()["runs"].get(os.path.basename(os.path.normpath(run_path)), {})
        raise auth.DriveError(f"Não foi possível enviar a execução: {entry.get('error', '')}")
    return load_state()["runs"][os.path.basename(os.path.normpath(run_path))]["folder_id"]


def _set_link(run_path: str, shared: bool):
    state = load_state()
    state["runs"][os.path.basename(os.path.normpath(run_path))]["link"] = shared
    save_state(state)


def is_link_shared(run_path: str) -> bool:
    entry = load_state()["runs"].get(os.path.basename(os.path.normpath(run_path)), {})
    return bool(entry.get("link"))


def share_link(service, run_path: str) -> str:
    """Qualquer pessoa com o link pode ver a pasta da execução. Devolve o link."""
    with _LOCK:
        folder = _synced_folder(service, run_path)
        service.permissions().create(fileId=folder, fields="id",
                                     body={"type": "anyone", "role": "reader"}).execute()
        _set_link(run_path, True)
    return FOLDER_URL.format(folder)


def unshare_link(service, run_path: str):
    """Remove a permissão "qualquer pessoa com o link"; convites ficam."""
    with _LOCK:
        entry = load_state()["runs"].get(os.path.basename(os.path.normpath(run_path)), {})
        if not entry.get("folder_id"):
            return
        try:
            # `anyoneWithLink` é o id fixo da permissão do tipo anyone.
            service.permissions().delete(fileId=entry["folder_id"],
                                         permissionId="anyoneWithLink").execute()
        except Exception as error:
            if _status_code(error) != 404:
                raise
        _set_link(run_path, False)


def parse_emails(text: str) -> list:
    """E-mails separados por vírgula, ponto e vírgula ou espaço."""
    return [item for item in re.split(r"[\s,;]+", text) if item]


def invite(service, run_path: str, emails: list):
    """Convida cada e-mail como leitor da pasta, com e-mail do Google."""
    invalid = [email for email in emails if not EMAIL.match(email)]
    if invalid:
        raise auth.DriveError("E-mail inválido: " + ", ".join(invalid))
    with _LOCK:
        folder = _synced_folder(service, run_path)
        for email in emails:
            service.permissions().create(
                fileId=folder, sendNotificationEmail=True, fields="id",
                body={"type": "user", "role": "reader", "emailAddress": email}).execute()
