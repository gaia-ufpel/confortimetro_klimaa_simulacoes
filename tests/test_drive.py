"""Sincronização e compartilhamento com o Google Drive, contra um Drive falso.

Nada aqui faz rede: `FakeDrive` imita a parte da API v3 que `drive.sync` usa
(files.list/create/update, permissions.create/delete, about.get).
"""

import json
import os
import re

import pytest

from confortimetro.drive import auth, sync

FOLDER = sync.FOLDER_MIME


class _Request:
    def __init__(self, drive, action):
        self.drive, self.action = drive, action

    def execute(self):
        if self.drive.fail is not None:
            raise self.drive.fail
        return self.action()


class HttpError(Exception):
    """Imita o `googleapiclient.errors.HttpError`: o status vem em `resp`."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class FakeDrive:
    def __init__(self):
        self.items = {}
        self.grants = {}
        self.writes = []  # (operação, nome) de cada create/update de arquivo
        self.fail = None
        self._next = 0

    # files() e permissions() devolvem o próprio falso, como a API devolve recursos.
    def files(self):
        return self

    def permissions(self):
        return _Permissions(self)

    def about(self):
        return self

    def get(self, fields=None):
        return _Request(self, lambda: {"user": {"emailAddress": "dono@exemplo.com"}})

    def add(self, name, parent, mime=None, content=b""):
        self._next += 1
        item_id = f"id{self._next}"
        self.items[item_id] = {"id": item_id, "name": name, "parents": [parent],
                               "mimeType": mime or "application/octet-stream",
                               "content": content, "size": str(len(content))}
        return item_id

    def list(self, q, **_kwargs):
        name = re.search(r"name='((?:[^'\\]|\\.)*)'", q)
        parent = re.search(r"'([^']+)' in parents", q).group(1)

        def match(item):
            if parent not in item["parents"]:
                return False
            if name and item["name"] != name.group(1):
                return False
            if f"mimeType='{FOLDER}'" in q and item["mimeType"] != FOLDER:
                return False
            if f"mimeType!='{FOLDER}'" in q and item["mimeType"] == FOLDER:
                return False
            return True

        return _Request(self, lambda: {"files": [dict(item) for item in self.items.values()
                                                 if match(item)]})

    def create(self, body, media_body=None, fields=None):
        def action():
            content = media_body.getbytes(0, media_body.size()) if media_body else b""
            item_id = self.add(body["name"], body["parents"][0], body.get("mimeType"), content)
            if media_body:
                self.writes.append(("create", body["name"]))
            return {"id": item_id}
        return _Request(self, action)

    def update(self, fileId, media_body=None, fields=None):
        def action():
            if fileId not in self.items:
                raise HttpError(404)
            item = self.items[fileId]
            item["content"] = media_body.getbytes(0, media_body.size())
            item["size"] = str(len(item["content"]))
            self.writes.append(("update", item["name"]))
            return {"id": fileId}
        return _Request(self, action)

    def tree(self, parent="root"):
        """{nome: conteúdo ou subárvore} a partir de `parent`."""
        return {item["name"]: (self.tree(item["id"]) if item["mimeType"] == FOLDER
                               else item["content"])
                for item in self.items.values() if parent in item["parents"]}

    def folder_id(self, name):
        return next(item["id"] for item in self.items.values()
                    if item["name"] == name and item["mimeType"] == FOLDER)


class _Permissions:
    def __init__(self, drive):
        self.drive = drive

    def create(self, fileId, body, sendNotificationEmail=None, fields=None):
        def action():
            permission_id = ("anyoneWithLink" if body["type"] == "anyone"
                             else f"perm-{body['emailAddress']}")
            self.drive.grants.setdefault(fileId, {})[permission_id] = dict(
                body, notify=sendNotificationEmail)
            return {"id": permission_id}
        return _Request(self.drive, action)

    def delete(self, fileId, permissionId):
        return _Request(self.drive,
                        lambda: self.drive.grants.get(fileId, {}).pop(permissionId))


@pytest.fixture
def drive(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENS_DATA_DIR", str(tmp_path / "dados"))
    client = tmp_path / "client_secret.json"
    client.write_text(json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}))
    monkeypatch.setenv(auth.CLIENT_VARIABLE, str(client))
    fake = FakeDrive()
    monkeypatch.setattr(auth, "service", lambda: fake)
    monkeypatch.setattr(sync, "_download", lambda service, file_id, path: open(
        path, "wb").write(service.items[file_id]["content"]))
    state = sync.load_state()
    state["account"] = "dono@exemplo.com"
    sync.save_state(state)
    return fake


def _run(root, name, extra=None):
    path = root / name
    path.mkdir(parents=True)
    (path / "configs.json").write_text('{"rooms": ["SALA"]}')
    (path / "SALA.xlsx").write_bytes(b"planilha " + name.encode())
    (path / "ESTATISTICAS.xlsx").write_bytes(b"stats")
    # Fora do espelho: ESO gigante, IDFs derivados e caches ocultos.
    (path / "eplusout.eso").write_bytes(b"x" * 100)
    (path / "in.idf").write_text("derivado")
    (path / ".series_cache").mkdir()
    for file_name, content in (extra or {}).items():
        (path / file_name).write_bytes(content)
    return path


def test_backfill_e_idempotencia(drive, tmp_path):
    outputs = tmp_path / "saidas"
    _run(outputs, "run_a")
    _run(outputs, "run_b")

    result = sync.sync_all(drive, str(outputs))

    assert result == {"pushed": 2, "failed": [], "pulled": []}
    assert drive.tree() == {"Ambiens": {
        "run_a": {"configs.json": b'{"rooms": ["SALA"]}', "SALA.xlsx": b"planilha run_a",
                  "ESTATISTICAS.xlsx": b"stats"},
        "run_b": {"configs.json": b'{"rooms": ["SALA"]}', "SALA.xlsx": b"planilha run_b",
                  "ESTATISTICAS.xlsx": b"stats"}}}
    assert sync.run_status("run_a") == sync.SYNCED

    drive.writes.clear()
    count = len(drive.items)
    sync.sync_all(drive, str(outputs))
    assert drive.writes == []
    assert len(drive.items) == count


def test_arquivo_alterado_reenvia_so_ele(drive, tmp_path):
    outputs = tmp_path / "saidas"
    run = _run(outputs, "run_a")
    sync.sync_all(drive, str(outputs))
    drive.writes.clear()

    (run / "ESTATISTICAS.xlsx").write_bytes(b"stats regeradas")
    sync.sync_all(drive, str(outputs))

    assert drive.writes == [("update", "ESTATISTICAS.xlsx")]
    assert drive.tree()["Ambiens"]["run_a"]["ESTATISTICAS.xlsx"] == b"stats regeradas"


def test_pull_baixa_execucao_ausente(drive, tmp_path):
    root = drive.add("Ambiens", "root", FOLDER)
    remote = drive.add("run_outra_maquina", root, FOLDER)
    drive.add("configs.json", remote, content=b"{}")
    drive.add("SALA.xlsx", remote, content=b"de la")
    # Pasta sem marcador de execução e nome perigoso: ignoradas.
    drive.add("lixo", root, FOLDER)
    drive.add("..", root, FOLDER)
    outputs = tmp_path / "saidas"
    outputs.mkdir()

    result = sync.sync_all(drive, str(outputs))

    assert result["pulled"] == ["run_outra_maquina"]
    local = outputs / "run_outra_maquina"
    assert (local / "SALA.xlsx").read_bytes() == b"de la"
    assert sorted(os.listdir(outputs)) == ["run_outra_maquina"]
    # Baixada não volta a subir, e o pull seguinte não baixa de novo.
    drive.writes.clear()
    assert sync.sync_all(drive, str(outputs)) == {"pushed": 1, "failed": [], "pulled": []}
    assert drive.writes == []


def test_falha_de_rede_deixa_pendente_e_retoma(drive, tmp_path):
    outputs = tmp_path / "saidas"
    run = _run(outputs, "run_a")
    drive.fail = OSError("rede caiu")

    assert sync.push_after_run(str(run)) == sync.PENDING
    state = sync.load_state()
    assert state["pending"] == [str(run)]
    assert "rede caiu" in state["runs"]["run_a"]["error"]

    # Próxima abertura: a pendente vai mesmo que esteja fora da pasta listada.
    drive.fail = None
    result = sync.sync_all(drive, str(tmp_path / "outra_raiz"))
    assert result["pushed"] == 1
    assert sync.load_state()["pending"] == []
    assert sync.run_status("run_a") == sync.SYNCED
    assert set(drive.tree()["Ambiens"]["run_a"]) == {"configs.json", "SALA.xlsx",
                                                     "ESTATISTICAS.xlsx"}


def test_token_revogado_pede_reconexao(drive, tmp_path):
    run = _run(tmp_path / "saidas", "run_a")
    drive.fail = HttpError(401)
    assert not sync.push_run(drive, str(run))
    state = sync.load_state()
    assert state["reconnect"] is True
    assert state["runs"]["run_a"]["status"] == sync.PENDING


def test_pasta_apagada_no_drive_e_recriada(drive, tmp_path):
    outputs = tmp_path / "saidas"
    run = _run(outputs, "run_a")
    sync.sync_all(drive, str(outputs))
    drive.items.clear()

    (run / "SALA.xlsx").write_bytes(b"nova")
    assert sync.push_run(drive, str(run))
    assert drive.tree()["Ambiens"]["run_a"]["SALA.xlsx"] == b"nova"


def test_compartilhar_link_e_convite(drive, tmp_path):
    run = _run(tmp_path / "saidas", "run_a")

    url = sync.share_link(drive, str(run))
    folder = drive.folder_id("run_a")
    assert url == f"https://drive.google.com/drive/folders/{folder}"
    assert drive.grants[folder]["anyoneWithLink"]["role"] == "reader"
    assert sync.is_link_shared(str(run))

    sync.invite(drive, str(run), sync.parse_emails("a@x.com, b@y.org;"))
    assert drive.grants[folder]["perm-a@x.com"] == {
        "type": "user", "role": "reader", "emailAddress": "a@x.com", "notify": True}
    assert "perm-b@y.org" in drive.grants[folder]
    with pytest.raises(auth.DriveError):
        sync.invite(drive, str(run), ["sem-arroba"])

    sync.unshare_link(drive, str(run))
    assert "anyoneWithLink" not in drive.grants[folder]
    assert "perm-a@x.com" in drive.grants[folder]
    assert not sync.is_link_shared(str(run))


def test_desconectar_apaga_estado(drive, monkeypatch):
    forgot = []
    monkeypatch.setattr(auth, "forget_token", lambda: forgot.append(True))
    sync.disconnect()
    assert forgot == [True]
    assert not sync.is_connected()
    assert not os.path.exists(sync.state_path())


def test_sem_cliente_desabilita_sem_quebrar(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AMBIENS_DATA_DIR", str(tmp_path / "dados"))
    monkeypatch.delenv(auth.CLIENT_VARIABLE, raising=False)
    monkeypatch.setattr(auth, "CLIENT_FILE", str(tmp_path / "nao_existe.json"))
    # Mesmo com uma conta no estado, sem cliente nada toca o keyring nem a rede.
    sync.save_state({"account": "dono@exemplo.com", "runs": {}, "pending": []})
    monkeypatch.setattr(auth, "refresh_token", lambda: pytest.fail("keyring consultado"))

    assert auth.client_path() is None
    assert auth.service() is None
    assert not sync.is_connected()
    assert sync.push_after_run(str(tmp_path)) is None
    with pytest.raises(auth.DriveError):
        auth.connect()

    import cli
    cli._push_to_drive(str(tmp_path))
    assert capsys.readouterr().out == ""
