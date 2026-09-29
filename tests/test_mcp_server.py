"""Cliente MCP real via stdio e disparo isolado (sem EnergyPlus demorado)."""

import json
import os
import sys

import anyio
import pandas
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from confortimetro import mcp_server


def _payload(result):
    assert not result.isError, result.content
    return result.structuredContent or json.loads(result.content[0].text)


def test_stdio_listar_resumo_validar_e_recusar_traversal(tmp_path):
    root = tmp_path / "dados" / "execucoes"
    root.mkdir(parents=True)
    fixture = root / "fixture"
    fixture.mkdir()
    (fixture / "configs.json").write_text(json.dumps({"rooms": ["SALA"], "module_type": "COMPLETE"}))
    pandas.DataFrame([{"Nome da sala": "SALA", "Energia total (kWh)": 12.5,
                       "Desconforto (%)": 0.1}]).to_excel(fixture / "ESTATISTICAS.xlsx", index=False)
    outside = tmp_path / "fora"
    outside.mkdir()
    (outside / "configs.json").write_text("{}")
    (root / "link").symlink_to(outside, target_is_directory=True)

    async def check():
        env = {**os.environ, "CONFORTIMETRO_DATA_DIR": str(tmp_path / "dados")}
        env.pop("AMBIENS_DATA_DIR", None)
        env["PYTHONPATH"] = os.path.dirname(os.path.dirname(__file__))
        params = StdioServerParameters(command=sys.executable,
                                       args=["-m", "confortimetro.mcp_server"], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "listar_execucoes", "ler_execucao", "validar_configuracao",
                    "iniciar_simulacao", "estado_simulacao"}
                listed = _payload(await session.call_tool("listar_execucoes"))
                assert [run["id"] for run in listed["execucoes"]] == ["fixture"]
                summary = _payload(await session.call_tool("ler_execucao", {"id": "fixture"}))
                assert summary["configuracao"]["module_type"] == "COMPLETE"
                assert summary["indicadores"] == [{"Nome da sala": "SALA",
                    "Energia total (kWh)": 12.5, "Desconforto (%)": 0.1}]
                invalid = _payload(await session.call_tool("validar_configuracao", {
                    "configuracao": {"idf_path": str(outside / "nao-existe.idf")}}))
                assert invalid["valida"] is False
                repo = os.path.dirname(os.path.dirname(__file__))
                if os.path.isfile("/usr/local/EnergyPlus-9-4-0/Energy+.idd"):
                    valid = _payload(await session.call_tool("validar_configuracao", {
                        "configuracao": {
                            "idf_path": os.path.join(repo, "examples", "idf", "SALA", "SALA_PTHP.idf"),
                            "epw_path": os.path.join(repo, "examples", "epw", "BRA_RS_Camaqua.869890_INMET.epw"),
                            "rooms": ["SALA"], "module_type": "CLOSED_WINDOW",
                            "energy_path": "/usr/local/EnergyPlus-9-4-0",
                        }}))
                    assert valid == {"valida": True, "erros": []}
                for name in ("../fora", "link"):
                    refused = await session.call_tool("ler_execucao", {"id": name})
                    assert refused.isError

    anyio.run(check)


def test_disparo_fake_runner_persiste_estado(tmp_path, monkeypatch):
    """Fake só na fronteira Popen; não dispara simulação anual de verdade."""
    monkeypatch.setenv("CONFORTIMETRO_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("AMBIENS_DATA_DIR", raising=False)
    idf = tmp_path / "entrada.idf"
    idf.write_text("Zone, SALA;", encoding="utf-8")
    epw = tmp_path / "clima.epw"
    epw.write_text("epw", encoding="utf-8")
    energy = tmp_path / "EnergyPlus"
    (energy / "pyenergyplus").mkdir(parents=True)
    (energy / "Energy+.idd").touch()
    (energy / "pyenergyplus" / "api.py").touch()
    monkeypatch.setattr(mcp_server, "validar_configuracao", lambda args: {"valida": True, "erros": []})
    called = []
    monkeypatch.setattr(mcp_server.subprocess, "Popen", lambda *args, **kwargs: called.append((args, kwargs)))

    started = mcp_server.iniciar_simulacao({"idf_path": str(idf), "epw_path": str(epw),
                                            "energy_path": str(energy), "rooms": ["SALA"]})
    assert started["estado"] == "na_fila" and started["id"].startswith("mcp_")
    assert len(called) == 1
    assert called[0][0][0][:3] == [sys.executable, "-m", "confortimetro.mcp_runner"]
    assert mcp_server.estado_simulacao(started["id"])["estado"] == "na_fila"
    from confortimetro.mcp_runner import write_status
    write_status(started["pasta"], "concluida")
    assert mcp_server.estado_simulacao(started["id"])["estado"] == "concluida"
    saved = json.loads((tmp_path / "execucoes" / started["id"] / "entrada_mcp.json").read_text())
    assert saved["output_path"] == started["pasta"]
    with pytest.raises(ValueError, match="zonas"):
        mcp_server._config({"idf_path": str(idf), "epw_path": str(epw),
            "energy_path": str(energy), "rooms": ["../fora"]}, started["pasta"])
