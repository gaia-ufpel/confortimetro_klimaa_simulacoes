"""Módulo ENERGYPLUS_ONLY: só executa o EnergyPlus, sem tocar no modelo."""

import hashlib
import os
import sys
import types
from queue import Queue

from confortimetro.config import SimulationConfig
from confortimetro.module_type import ModuleType
from confortimetro import simulation as sim_module

IDF_TEXT = "Version,9.4;\nBuilding,\n  Predio;\nZone,\n  SALA;\n"


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class FakeRuntime:
    def __init__(self):
        self.registered = []
        self.seen_idf_hash = None
        self.idf_arg = None

    def __getattr__(self, name):
        # Qualquer callback_* registrado fica anotado; o resto do run é o teste.
        if name.startswith("callback_"):
            return lambda *args: self.registered.append(name)
        raise AttributeError(name)

    def run_energyplus(self, state, args):
        self.idf_arg = args[-1]
        self.seen_idf_hash = sha(self.idf_arg)
        out = args[args.index("--output-directory") + 1]
        with open(os.path.join(out, "eplusout.end"), "w") as handle:
            handle.write("EnergyPlus Completed Successfully")
        return 0


def test_energyplus_only_nao_registra_callback_nem_altera_idf(tmp_path, monkeypatch):
    idf = tmp_path / "modelo_original.idf"
    idf.write_text(IDF_TEXT)
    original = sha(idf)
    runtime = FakeRuntime()
    fake_api = types.SimpleNamespace(
        runtime=runtime,
        state_manager=types.SimpleNamespace(new_state=lambda: object(),
                                            reset_state=lambda state: None))
    monkeypatch.setitem(sys.modules, "pyenergyplus.api", types.SimpleNamespace(
        EnergyPlusAPI=lambda: fake_api))
    class NoEditProcessor:
        def __init__(self, configs):
            pass

        def process_idf(self):
            raise AssertionError("o IDF não pode ser processado")

    monkeypatch.setattr(sim_module, "IDFProcessor", NoEditProcessor)
    # ExpandObjects: sem HVACTemplate ele só reescreve o in.idf como expanded.idf.
    def fake_expand(self):
        import shutil
        shutil.copy(self.configs.idf_path,
                    os.path.join(self.configs.output_path, "in.idf"))
        shutil.copy(self.configs.idf_path, self.configs.expanded_idf_path)
    monkeypatch.setattr(sim_module.Simulation, "_expand_objects", fake_expand)

    out = tmp_path / "run"
    configs = SimulationConfig(met_as_watts=0, _idf_path=str(idf), _met=1.0, epw_path=str(tmp_path / "x.epw"),
                               output_path=str(out), energy_path=str(tmp_path),
                               rooms=["SALA"], module_type=ModuleType.ENERGYPLUS_ONLY)
    simulation = sim_module.Simulation(configs)
    simulation.run(Queue())

    assert simulation.conditioner is None
    # callback_progress só alimenta a barra da GUI; nenhum callback de controle.
    assert [c for c in runtime.registered if c != "callback_progress"] == []
    assert runtime.seen_idf_hash == original   # IDF entregue ao EnergyPlus = original
    assert sha(idf) == original                # e o arquivo do usuário intacto
    assert sha(out / "modelo.idf") == original
