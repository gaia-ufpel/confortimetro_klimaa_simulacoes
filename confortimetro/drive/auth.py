"""Acesso à conta Google: cliente OAuth, refresh token no keyring e o serviço.

O escopo é só `drive.file`: o app enxerga apenas o que ele mesmo criou no
Drive do usuário. O refresh token mora no cofre de senhas do sistema — nunca em
arquivo nem em log; sem cofre, conectar falha com mensagem.

As bibliotecas do Google são importadas dentro das funções, como o
google-genai do assistente, para não pesar a abertura da janela.
"""

import json
import os

from ..assistant.store import KEYRING_SERVICE, _keyring

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
KEYRING_USER = "google-drive"
CLIENT_VARIABLE = "AMBIENS_GOOGLE_CLIENT"
CLIENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_secret.json")
# Segundos por requisição HTTP: sem isso o httplib2 espera para sempre numa
# rede que caiu no meio do envio.
HTTP_TIMEOUT_S = 120
# Quanto o servidor local espera o usuário terminar o login no navegador.
LOGIN_TIMEOUT_S = 300


class DriveError(Exception):
    """Falha com mensagem para o usuário (sem cliente, sem cofre, sem token)."""


def client_path():
    """JSON do cliente OAuth "App para computador", ou `None` se não houver.

    Ordem: `AMBIENS_GOOGLE_CLIENT` (caminho) e depois o `client_secret.json`
    junto do pacote, que fica fora do git e entra no instalador se existir.
    """
    for path in (os.environ.get(CLIENT_VARIABLE), CLIENT_FILE):
        if path and os.path.isfile(path):
            return path
    return None


def _client():
    path = client_path()
    if not path:
        raise DriveError("Cliente OAuth do Google não configurado (veja docs/DRIVE.md).")
    with open(path, encoding="utf-8-sig") as client_file:
        data = json.load(client_file)
    return data.get("installed") or data.get("web") or data


def _vault():
    keyring = _keyring()
    if keyring is None:
        raise DriveError("Sem cofre de senhas do sistema: o acesso ao Drive não "
                         "pode ser guardado com segurança nesta máquina.")
    return keyring


def refresh_token():
    """Refresh token guardado, ou '' se não houver."""
    keyring = _keyring()
    if keyring is None:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception:
        return ""


def credentials():
    """`Credentials` com o refresh token do keyring; `None` se não conectado."""
    token = refresh_token()
    if not token:
        return None
    from google.oauth2.credentials import Credentials

    client = _client()
    return Credentials(None, refresh_token=token,
                       token_uri=client.get("token_uri", "https://oauth2.googleapis.com/token"),
                       client_id=client["client_id"],
                       client_secret=client.get("client_secret"), scopes=SCOPES)


def build_service(creds):
    import google_auth_httplib2
    import httplib2
    from googleapiclient.discovery import build

    http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=HTTP_TIMEOUT_S))
    # O documento de descoberta do drive v3 vem dentro do pacote: nada de rede aqui.
    return build("drive", "v3", http=http, cache_discovery=False)


def service():
    """Serviço do Drive v3 autenticado; `None` sem cliente ou sem token."""
    if not client_path():
        return None
    creds = credentials()
    return build_service(creds) if creds else None


def connect():
    """Login no navegador (loopback) e guarda o refresh token. Devolve o serviço.

    Bloqueia até o usuário terminar no navegador ou `LOGIN_TIMEOUT_S`: chame
    fora da thread da interface.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    path = client_path()
    if not path:
        _client()  # levanta a mensagem de cliente ausente
    keyring = _vault()
    flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
    # `prompt=consent` garante o refresh token mesmo numa segunda autorização.
    creds = flow.run_local_server(port=0, open_browser=True, prompt="consent",
                                  access_type="offline", timeout_seconds=LOGIN_TIMEOUT_S)
    if not creds or not creds.refresh_token:
        raise DriveError("O Google não devolveu acesso permanente; tente conectar de novo.")
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, creds.refresh_token)
    return build_service(creds)


def forget_token():
    keyring = _keyring()
    if keyring is None:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass
