"""Erros do pipeline precisam falhar alto, não passar em silêncio."""
import json
import sys

import pytest

from confortimetro.control.base import Conditioner
from confortimetro.results import get_stats_from_simulation
from confortimetro.config import SimulationConfig


class FakeExchange:
    def __init__(self, handle=1):
        self.handle = handle

    def warmup_flag(self, state):
        return False

    def api_data_fully_ready(self, state):
        return True

    def get_variable_handle(self, state, *args):
        return self.handle

    def get_actuator_handle(self, state, *args):
        return self.handle


class FakeRuntime:
    def __init__(self):
        self.stopped = False

    def stop_simulation(self, state):
        self.stopped = True


class FakeApi:
    def __init__(self, handle=1):
        self.exchange = FakeExchange(handle)
        self.runtime = FakeRuntime()


def _config(tmp_path):
    idf = tmp_path / "modelo.idf"
    idf.write_text("")
    config = SimulationConfig(met_as_watts=1.2 * 58.1 * 1.8, _idf_path=str(idf), _met=1.2)
    config.rooms = ["ATELIE1"]
    return config


def test_excecao_no_callback_guarda_erro_e_para_simulacao(tmp_path):
    api = FakeApi()
    conditioner = Conditioner(api, _config(tmp_path))
    conditioner.room_conditioner = lambda state, room: 1 / 0

    conditioner(state=None)  # não pode propagar: o ctypes engoliria

    assert isinstance(conditioner.error, ZeroDivisionError)
    assert api.runtime.stopped


def test_handler_invalido_aborta(tmp_path):
    api = FakeApi(handle=-1)
    conditioner = Conditioner(api, _config(tmp_path))

    conditioner(state=None)

    assert isinstance(conditioner.error, RuntimeError)
    assert "Handlers do EnergyPlus não encontrados" in str(conditioner.error)
    assert api.runtime.stopped


def test_estatisticas_sem_planilha_falham(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_stats_from_simulation(str(tmp_path), ["ATELIE1"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_config_cai_no_energyplus_da_plataforma_quando_o_caminho_nao_existe(tmp_path):
    """O config.json versionado tem caminhos de Linux; no Windows precisa cair no padrão."""
    from confortimetro.config import SimulationConfig, default_energy_path

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "met_as_watts": 125.496,
                "_idf_path": "./modelo.idf",
                "_met": 1.2,
                "energy_path": "/caminho/que/nao/existe",
            }
        )
    )

    config = SimulationConfig.from_json(str(config_path))

    assert config.energy_path == default_energy_path()
