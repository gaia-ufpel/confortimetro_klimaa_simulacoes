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

    def add(self, name, parent, mime=None, content=b"", app=None):
        self._next += 1
        item_id = f"id{self._next}"
        self.items[item_id] = {"id": item_id, "name": name, "parents": [parent],
                               "mimeType": mime or "application/octet-stream",
                               "content": content, "size": str(len(content)),
                               "appProperties": dict(app or {})}
        return item_id

    def list(self, q, **_kwargs):
        name = re.search(r"\bname='((?:[^'\\]|\\.)*)'", q)
        parent = re.search(r"'([^']+)' in parents", q).group(1)
        prop = re.search(r"appProperties has \{ key='([^']+)' and value='([^']+)' \}", q)

        def match(item):
            if parent not in item["parents"]:
                return False
            if name and item["name"] != name.group(1):
                return False
            if prop and item["appProperties"].get(prop.group(1)) != prop.group(2):
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
            item_id = self.add(body["name"], body["parents"][0], body.get("mimeType"), content,
                               body.get("appProperties"))
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

    def run_ids(self):
        """{nome da pasta: id da execução} das pastas de execução."""
        return {item["name"]: item["appProperties"].get(sync.APP_KEY)
                for item in self.items.values()
                if item["mimeType"] == FOLDER and item["appProperties"]}

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
    remote = drive.add("run_outra_maquina", root, FOLDER, app={sync.APP_KEY: "outra"})
    drive.add("configs.json", remote, content=b"{}")
    drive.add("SALA.xlsx", remote, content=b"de la")
    # Pasta sem marcador de execução, nome perigoso e sem id: ignoradas.
    drive.add("lixo", root, FOLDER, app={sync.APP_KEY: "lixo"})
    drive.add("..", root, FOLDER, app={sync.APP_KEY: "perigo"})
    sem_id = drive.add("sem_id", root, FOLDER)
    drive.add("configs.json", sem_id, content=b"{}")
    outputs = tmp_path / "saidas"
    outputs.mkdir()

    result = sync.sync_all(drive, str(outputs))

    assert result["pulled"] == ["run_outra_maquina"]
    local = outputs / "run_outra_maquina"
    assert (local / "SALA.xlsx").read_bytes() == b"de la"
    assert (local / sync.ID_FILE).read_text() == "outra"
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


def test_espelho_so_com_permitidos_e_teto_de_tamanho(drive, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(sync, "MAX_FILE_BYTES", 50)
    run = _run(tmp_path / "saidas", "run_a", {
        "eplusout.err": b"e", "eplusout.csv": b"c", "eplusout.sql": b"s", "eplusout.mtr": b"m",
        "eplustbl.csv": b"tabela", "eplustbl.htm": b"<html>", "grafico.png": b"png",
        "modelo.idf": b"idf", "~$SALA.xlsx": b"trava", "GRANDE.xlsx": b"x" * 51})

    with caplog.at_level("WARNING", logger=sync.logger.name):
        assert sync.push_run(drive, str(run))

    assert set(drive.tree()["Ambiens"]["run_a"]) == {
        "configs.json", "SALA.xlsx", "ESTATISTICAS.xlsx", "eplustbl.csv", "eplustbl.htm",
        "grafico.png", "modelo.idf"}
    assert "GRANDE.xlsx" in caplog.text


def test_push_sem_mudanca_nao_grava_estado(drive, tmp_path, monkeypatch):
    run = _run(tmp_path / "saidas", "run_a")
    assert sync.push_run(drive, str(run))
    saves, changes = [], []
    monkeypatch.setattr(sync, "save_state", lambda state: saves.append(dict(state)))

    assert sync.push_run(drive, str(run), lambda: changes.append(True))
    assert saves == [] and changes == []


def test_fim_da_simulacao_envia_tambem_pendentes(drive, tmp_path):
    outputs = tmp_path / "saidas"
    old = _run(outputs, "run_a")
    drive.fail = OSError("rede caiu")
    assert sync.push_after_run(str(old)) == sync.PENDING

    drive.fail = None
    new = _run(outputs, "run_b")
    assert sync.push_after_run(str(new)) == sync.SYNCED

    assert sync.load_state()["pending"] == []
    assert sync.run_status("run_a") == sync.SYNCED
    assert set(drive.tree()["Ambiens"]) == {"run_a", "run_b"}


def test_conta_sem_token_no_keyring_pede_reconexao(drive, tmp_path, monkeypatch):
    run = _run(tmp_path / "saidas", "run_a")
    monkeypatch.setattr(auth, "service", lambda: None)
    monkeypatch.setattr(auth, "refresh_token", lambda: "")

    assert sync.push_after_run(str(run)) == sync.PENDING
    assert sync.load_state()["reconnect"] is True


def test_envio_bem_sucedido_limpa_reconexao(drive, tmp_path):
    run = _run(tmp_path / "saidas", "run_a")
    drive.fail = HttpError(401)
    assert not sync.push_run(drive, str(run))
    assert sync.load_state()["reconnect"] is True

    drive.fail = None
    assert sync.push_run(drive, str(run))
    assert sync.load_state()["reconnect"] is False


def test_execucoes_homonimas_de_maquinas_diferentes_nao_colidem(drive, tmp_path):
    root = drive.add("Ambiens", "root", FOLDER)
    other = drive.add("run_a", root, FOLDER, app={sync.APP_KEY: "da-outra-maquina"})
    drive.add("configs.json", other, content=b'{"outra": 1}')
    drive.add("SALA.xlsx", other, content=b"planilha da outra")
    outputs = tmp_path / "saidas"
    mine = _run(outputs, "run_a")

    result = sync.sync_all(drive, str(outputs))

    # A minha foi para "run_a (2)"; a da outra máquina ficou intocada no
    # Drive e desceu para "run_a (2)" local, sem sobrescrever a minha.
    my_id = (mine / sync.ID_FILE).read_text()
    assert drive.run_ids() == {"run_a": "da-outra-maquina", "run_a (2)": my_id}
    assert drive.tree()["Ambiens"]["run_a"] == {"configs.json": b'{"outra": 1}',
                                                "SALA.xlsx": b"planilha da outra"}
    assert drive.tree()["Ambiens"]["run_a (2)"]["SALA.xlsx"] == b"planilha run_a"
    assert result["pulled"] == ["run_a (2)"]
    assert (mine / "SALA.xlsx").read_bytes() == b"planilha run_a"
    assert (outputs / "run_a (2)" / "SALA.xlsx").read_bytes() == b"planilha da outra"

    # Estado perdido: a pasta remota de mesmo id é adotada, sem duplicar nada.
    os.remove(sync.state_path())
    sync.save_state({"account": "dono@exemplo.com", "runs": {}, "pending": []})
    drive.writes.clear()
    count = len(drive.items)
    assert sync.sync_all(drive, str(outputs))["pulled"] == []
    assert drive.writes == [] and len(drive.items) == count


def test_gravacao_do_estado_tenta_de_novo_e_falha_visivel(drive, tmp_path, monkeypatch):
    from confortimetro.assistant import store

    monkeypatch.setattr(store, "REPLACE_WAIT_S", 0)
    real_replace, calls = os.replace, []

    def flaky(source, target):
        calls.append(target)
        if len(calls) <= 2:
            raise PermissionError("em uso")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", flaky)
    sync.save_state({"account": "a", "runs": {}, "pending": []})
    assert len(calls) == 3 and sync.load_state()["account"] == "a"

    def locked(source, target):
        raise PermissionError("em uso")

    monkeypatch.setattr(os, "replace", locked)
    run = _run(tmp_path / "saidas", "run_a")
    with pytest.raises(auth.DriveError, match="estado do Drive"):
        sync.push_after_run(str(run))


def test_login_expirado_vira_drive_error(drive, monkeypatch):
    from google_auth_oauthlib.flow import InstalledAppFlow

    class Flow:
        def run_local_server(self, **_kwargs):
            raise AttributeError("'NoneType' object has no attribute 'replace'")

    monkeypatch.setattr(auth, "_vault", lambda: object())
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file",
                        classmethod(lambda cls, *args, **kwargs: Flow()))
    with pytest.raises(auth.DriveError, match="5 minutos"):
        auth.connect()
