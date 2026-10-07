"""Servidor remoto + cliente ponta a ponta, com um runner falso no lugar do EnergyPlus."""

import json
import os
from queue import Queue

import pytest
from starlette.testclient import TestClient

from confortimetro import mcp_server
from confortimetro.config import SimulationConfig
from confortimetro.mcp_runner import write_status
from confortimetro.remote import client as remote
from confortimetro.remote import server


def _fake_launch(run):
    """O que o runner deixaria numa execução concluída."""
    with open(os.path.join(run, server.CONFIG_FILE), encoding="utf-8") as handle:
        config = json.load(handle)
    config["_idf_path"] = os.path.join(run, "modelo.idf")
    with open(os.path.join(run, "configs.json"), "w", encoding="utf-8") as handle:
        json.dump(config, handle)
    for name, content in (("modelo.idf", "Zone,SALA;"), ("ESTATISTICAS.xlsx", "x"),
                          ("eplusout.eso", "bruto"), ("eplustbl.csv", "tabela")):
        with open(os.path.join(run, name), "w", encoding="utf-8") as handle:
            handle.write(content)
    with open(os.path.join(run, server.LOG_FILE), "w", encoding="utf-8") as handle:
        handle.write("Executando simulação EnergyPlus...\nPROGRESS 50\nEXIT\nlinha incomplet")
    write_status(run, "concluida")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("AMBIENS_DATA_DIR", str(tmp_path / "servidor"))
    monkeypatch.setattr(mcp_server, "validar_configuracao", lambda args: {"valida": True})
    monkeypatch.setattr(mcp_server, "_energy_installation", lambda: str(tmp_path))
    monkeypatch.setattr(server, "_launch", _fake_launch)
    monkeypatch.setattr(remote, "POLL_S", 0)
    http = TestClient(server.create_app(scheduler=False))

    def client_for(name, admin=False):
        token = server.add_user(name, admin)
        client = remote.Client(url="http://testserver", token=token)
        client.http = TestClient(http.app, headers={"Authorization": f"Bearer {token}"})
        return client

    idf, epw = tmp_path / "meu modelo.idf", tmp_path / "clima.epw"
    idf.write_text("Zone,SALA;")
    epw.write_text("LOCATION")
    local = tmp_path / "local"
    config = SimulationConfig(met_as_watts=0, _idf_path=str(idf), _met=1.2, epw_path=str(epw),
                              rooms=["SALA"], runs_root_path=str(local),
                              output_path=str(local / "20261007_1500"))
    return http, client_for, config, tmp_path


def test_envia_acompanha_e_espelha_sem_brutos(setup):
    http, client_for, config, tmp_path = setup
    assert http.get("/api/execucoes").json() == {"erro": "Token inválido"}
    ana, beto = client_for("ana"), client_for("beto")

    q = Queue()
    simulation = remote.RemoteSimulation(config, ana)
    simulation.run(q)
    messages = [q.get() for _ in range(q.qsize())]
    assert "PROGRESS 50" in messages and "EXIT" not in messages
    assert not any("incomplet" in message for message in messages)
    assert messages[-1] == "Resultados baixados do servidor."

    dest = config.output_path
    assert sorted(os.listdir(dest)) == ["ESTATISTICAS.xlsx", "configs.json", "entrada",
                                        "eplustbl.csv", "modelo.idf", "progresso.log",
                                        "remoto.json"]
    assert sorted(os.listdir(os.path.join(dest, "entrada"))) == ["clima.epw", "meu_modelo.idf"]
    saved = json.load(open(os.path.join(dest, "configs.json"), encoding="utf-8"))
    assert saved["_idf_path"] == os.path.join(dest, "modelo.idf")
    assert saved["epw_path"] == os.path.join(dest, "entrada", "clima.epw")
    assert saved["output_path"] == dest and saved["energy_path"] == ""
    assert SimulationConfig.from_json(os.path.join(dest, "configs.json")).rooms == ["SALA"]

    # Outro usuário não enxerga; cancelar o que já terminou é recusado.
    with pytest.raises(remote.RemoteError, match="404"):
        beto.status(simulation.run_id)
    with pytest.raises(remote.RemoteError, match="409"):
        ana.cancel(simulation.run_id)
    assert beto.runs() == []

    # Sync: baixa o que falta numa raiz nova e ignora o que já tem espelho.
    other = tmp_path / "outra_maquina"
    assert remote.sync(str(other), ana) == 1
    assert os.path.isfile(other / simulation.run_id / "configs.json")
    assert remote.sync(str(other), ana) == 0
    assert remote.sync(os.path.dirname(dest), ana) == 0


def test_fila_respeita_limite_e_cancela_quem_espera(setup, monkeypatch):
    _, client_for, config, _ = setup
    monkeypatch.setattr(server, "_launch", lambda run: write_status(run, "executando", pid=os.getpid()))
    monkeypatch.setenv(mcp_server.MAX_ACTIVE_ENV, "1")
    ana = client_for("ana")
    first, second = ana.submit(config), ana.submit(config)
    assert ana.status(first)["estado"] == "executando"
    assert ana.status(second)["estado"] == server.WAITING
    assert ana.cancel(second)["estado"] == server.CANCELLED
    assert {run["id"]: run["estado"] for run in ana.runs()} == {
        first: "executando", second: server.CANCELLED}


def test_cota_avisa_admin(setup, monkeypatch):
    _, client_for, config, _ = setup
    admin = client_for("admin", admin=True)
    admin.submit(config)
    monkeypatch.setenv(server.QUOTA_ENV, "0.000000001")
    server.check_quota()
    assert admin.me()["cota"]["excedida"] is True
    assert "cota" not in client_for("ana").me()
