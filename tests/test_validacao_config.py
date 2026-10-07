"""Configuração inválida é recusada antes de simular (GUI e CLI)."""

import pytest

import cli
from confortimetro.config import SimulationConfig
from confortimetro.gui.theme import parse_num
from tests import test_gui_pages

# Fixture da janela; atribuída (não importada) para o ruff não ver redefinição.
window = test_gui_pages.window


def _config(tmp_path, **over):
    """Configuração que passa em `simulacao.validate`, mais `over`."""
    idf = tmp_path / "modelo.idf"
    idf.write_text("Zone,\n  SALA1;\n")
    epw = tmp_path / "clima.epw"
    epw.write_text("LOCATION,Teste\n")
    energy = tmp_path / "EnergyPlus-9-4-0"
    (energy / "pyenergyplus").mkdir(parents=True, exist_ok=True)
    (energy / "Energy+.idd").write_text("")
    (energy / "pyenergyplus" / "api.py").write_text("")
    config = SimulationConfig(met_as_watts=125.496, _idf_path=str(idf), _met=1.2,
                              epw_path=str(epw), energy_path=str(energy), rooms=["SALA1"],
                              runs_root_path=str(tmp_path / "execucoes"),
                              output_path=str(tmp_path / "execucoes" / "run"))
    for key, value in over.items():
        setattr(config, key, value)
    return config


def test_parse_num_recusa_texto_invalido():
    assert parse_num("0,15") == 0.15
    for text in ("", "1.2 m/s", "abc"):
        with pytest.raises(ValueError):
            parse_num(text)


@pytest.fixture
def no_simulation(monkeypatch):
    class Forbidden:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("a simulação não podia ter começado")
    monkeypatch.setattr(cli, "Simulation", Forbidden)


def test_cli_recusa_air_speed_delta_zero(tmp_path, capsys, no_simulation):
    path = tmp_path / "config.json"
    _config(tmp_path).to_json(str(path))

    assert cli.main(["--config", str(path), "--set", "air_speed_delta=0"]) == 1
    assert "air_speed_delta" in capsys.readouterr().err


def test_cli_recusa_air_speed_delta_vazio(tmp_path, no_simulation):
    path = tmp_path / "config.json"
    _config(tmp_path).to_json(str(path))

    with pytest.raises(SystemExit, match="air_speed_delta"):
        cli.main(["--config", str(path), "--set", "air_speed_delta="])


def test_gui_start_simulation_recusa_air_speed_delta_zero(window, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(window, "_run_simulation_thread", lambda q, c: started.append(c))
    errors = []
    monkeypatch.setattr(window.results_panel, "append_error", errors.append)

    assert window.start_simulation(_config(tmp_path, air_speed_delta=0.0)) is None
    assert window.simulation_thread is None and started == []
    assert any("air_speed_delta" in error for error in errors)
    # A mesma configuração com o passo válido passa.
    assert window.start_simulation(_config(tmp_path, air_speed_delta=0.15))
    window.simulation_thread.join(5)
    assert len(started) == 1


def test_gui_campo_vazio_nao_vira_zero(window, monkeypatch):
    started = []
    monkeypatch.setattr(window, "start_simulation", started.append)
    errors = []
    monkeypatch.setattr(window.results_panel, "append_error", errors.append)
    window.simulation_panel.air_speed_delta_entry.delete(0, "end")

    with pytest.raises(ValueError, match="Variação da vel. de ventilação"):
        window.simulation_panel.get_configuration()
    window.on_run_simulation()
    assert started == [] and window.simulation_thread is None
    assert errors and "Variação da vel. de ventilação" in errors[0]
