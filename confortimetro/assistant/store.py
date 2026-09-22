"""Configurações, chave e conversas do assistente, guardadas fora das execuções.

Nada disto vai para o `SimulationConfig`: ele é copiado para o `configs.json`
de cada execução, e a chave ou o modelo do chat não descrevem a simulação.
"""

import datetime
import json
import os
import uuid

from ..paths import app_data_path

SETTINGS_FILE = "assistente.json"
CONVERSATIONS_DIRECTORY = os.path.join("assistente", "conversas")
KEY_FILE = "assistente.key"
KEYRING_SERVICE = "ConfortimetroKlimaa"
KEYRING_USER = "gemini"
KEY_VARIABLE = "GEMINI_API_KEY"
AI_STUDIO_URL = "https://aistudio.google.com/apikey"

DEFAULT_SETTINGS = {
    "model": "gemini-3.8-flash",
    "max_tool_calls": 20,
    "summarize_tokens": 700_000,
    "timeout_s": 90,
}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _write_json(path, data):
    """Grava num temporário e troca: uma queda no meio não corrompe o arquivo."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=1)
    os.replace(temporary, path)


# --- Configurações ---------------------------------------------------------

def load_settings() -> dict:
    """Configurações salvas sobre os padrões; campos desconhecidos ficam de fora."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(os.path.join(app_data_path(), SETTINGS_FILE), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return settings
    for key, default in DEFAULT_SETTINGS.items():
        value = saved.get(key)
        if isinstance(value, type(default)) and value:
            settings[key] = value
    return settings


def save_settings(settings: dict):
    clean = {key: settings.get(key, default) for key, default in DEFAULT_SETTINGS.items()}
    _write_json(os.path.join(app_data_path(), SETTINGS_FILE), clean)


# --- Chave -----------------------------------------------------------------

def _keyring():
    """O módulo `keyring` com um backend de verdade, ou `None`.

    No Linux sem Secret Service (servidor, WSL, sessão sem GNOME/KDE) o backend
    é o `fail`, que só levanta erro; aí a chave vai para o arquivo.
    """
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    if isinstance(keyring.get_keyring(), fail.Keyring):
        return None
    return keyring


def _key_path():
    return os.path.join(app_data_path(), KEY_FILE)


def get_api_key() -> str:
    """Chave do ambiente, do keyring ou do arquivo, nessa ordem; '' se não houver."""
    if os.environ.get(KEY_VARIABLE):
        return os.environ[KEY_VARIABLE].strip()
    keyring = _keyring()
    if keyring:
        try:
            key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            if key:
                return key
        except Exception:
            pass
    try:
        with open(_key_path(), encoding="utf-8") as key_file:
            return key_file.read().strip()
    except OSError:
        return ""


def set_api_key(key: str):
    """Guarda a chave no keyring; sem ele, num arquivo só do usuário.

    Chave vazia apaga a guardada.
    """
    key = key.strip()
    keyring = _keyring()
    if keyring:
        try:
            if key:
                keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
            else:
                try:
                    keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
                except Exception:
                    pass
            # Uma chave antiga em arquivo não pode sobrepor a nova.
            if os.path.exists(_key_path()):
                os.remove(_key_path())
            return
        except Exception:
            pass

    if not key:
        if os.path.exists(_key_path()):
            os.remove(_key_path())
        return
    os.makedirs(app_data_path(), exist_ok=True)
    # No Windows o chmod só mexe no somente-leitura; a pasta em %LOCALAPPDATA%
    # já é do usuário. No Linux/macOS o arquivo nasce 600.
    descriptor = os.open(_key_path(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
        key_file.write(key)


# --- Conversas -------------------------------------------------------------

def conversations_path() -> str:
    return os.path.join(app_data_path(), CONVERSATIONS_DIRECTORY)


def _conversation_file(conversation_id: str) -> str:
    # O id vira nome de arquivo: só o que `new_conversation` gera passa.
    if not conversation_id or not conversation_id.replace("-", "").isalnum():
        raise ValueError(f"id de conversa inválido: {conversation_id!r}")
    return os.path.join(conversations_path(), f"{conversation_id}.json")


def new_conversation(runs=None) -> dict:
    """Conversa vazia; `runs` são os nomes das execuções do contexto."""
    now = _now()
    return {
        "id": uuid.uuid4().hex,
        "title": "Nova conversa",
        "created": now,
        "updated": now,
        "runs": list(runs or []),
        # Cada item é um `types.Content` do google-genai em JSON: pergunta,
        # resposta, chamada e resultado de ferramenta — o histórico completo.
        "contents": [],
        # Até onde `summary` cobre `contents`; a API recebe o resumo no lugar
        # dessas mensagens, o disco e o painel continuam com tudo.
        "summary": "",
        "summary_upto": 0,
        # `mtime` das estatísticas de cada execução citada, na última resposta:
        # se mudar, a conversa falava de números que não existem mais.
        "run_mtimes": {},
        "prompt_tokens": 0,
    }


def save_conversation(conversation: dict):
    conversation["updated"] = _now()
    _write_json(_conversation_file(conversation["id"]), conversation)


def load_conversation(conversation_id: str) -> dict:
    with open(_conversation_file(conversation_id), encoding="utf-8") as f:
        return json.load(f)


def delete_conversation(conversation_id: str):
    path = _conversation_file(conversation_id)
    if os.path.exists(path):
        os.remove(path)


def list_conversations(run: str = None) -> list:
    """Conversas mais recentes primeiro; com `run`, só as que citam a execução.

    Devolve só os metadados — as conversas longas não são carregadas inteiras
    para montar o seletor.
    """
    directory = conversations_path()
    if not os.path.isdir(directory):
        return []
    items = []
    for name in os.listdir(directory):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if run and run not in data.get("runs", []):
            continue
        items.append({key: data.get(key) for key in ("id", "title", "updated", "runs")})
    return sorted(items, key=lambda item: item["updated"] or "", reverse=True)


def run_mtime(run_path: str):
    """Marca de versão dos resultados de uma execução; `None` se ela sumiu."""
    stats = os.path.join(run_path, "ESTATISTICAS.xlsx")
    for path in (stats, run_path):
        if os.path.exists(path):
            return os.path.getmtime(path)
    return None


def stale_runs(conversation: dict, root: str) -> dict:
    """Execuções citadas que mudaram desde a última resposta: nome → motivo."""
    stale = {}
    for run, mtime in conversation.get("run_mtimes", {}).items():
        current = run_mtime(os.path.join(root, run))
        if current is None:
            stale[run] = "apagada"
        elif mtime is not None and current != mtime:
            stale[run] = "recalculada"
    return stale


def export_markdown(conversation: dict) -> str:
    """Só o que o usuário leu: perguntas e respostas, sem as ferramentas."""
    lines = [f"# {conversation['title']}", ""]
    if conversation.get("runs"):
        lines += [f"Execuções: {', '.join(conversation['runs'])}", ""]
    for role, text in visible_messages(conversation):
        lines += ["## " + ("Pergunta" if role == "user" else "Assistente"), "", text, ""]
    return "\n".join(lines)


def visible_messages(conversation: dict) -> list:
    """(papel, texto) das mensagens com texto; ferramentas e resumo ficam de fora."""
    messages = []
    for content in conversation.get("contents", []):
        text = "".join(part.get("text") or "" for part in content.get("parts", [])
                       if not part.get("thought"))
        if text.strip():
            messages.append((content.get("role"), text))
    return messages
