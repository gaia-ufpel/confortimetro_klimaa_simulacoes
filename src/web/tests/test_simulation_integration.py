from pathlib import Path
from threading import Event
import time

from src.web.simulation_integration import WebSimulationManager


class FakeSimulation:
    def __init__(self, config):
        self.config = config

    def run(self, queue):
        assert Path(self.config.idf_path).is_file()
        assert Path(self.config.output_path).parent.name
        queue.put("Executando simulação EnergyPlus...")
        Path(self.config.output_path).mkdir()
        (Path(self.config.output_path) / "result.txt").write_text("ok")


def test_manager_runs_the_desktop_pipeline_contract(tmp_path):
    idf_path = tmp_path / "source.idf"
    epw_path = tmp_path / "weather.epw"
    energy_path = tmp_path / "EnergyPlus"
    idf_path.write_text("idf")
    epw_path.write_text("epw")
    energy_path.mkdir()
    (energy_path / "ExpandObjects").write_text("")

    manager = WebSimulationManager()
    session_id = manager.create_session()
    manager._new_simulation = FakeSimulation
    assert manager.update_config(session_id, {
        "idf_path": str(idf_path), "epw_path": str(epw_path), "energy_path": str(energy_path),
        "rooms": ["ATELIE1"], "module_type": "COMPLETE",
    })

    assert manager.start_simulation(session_id)
    manager.running_simulations[session_id]["thread"].join(timeout=2)
    assert manager.get_simulation_status(session_id) == "completed"
    assert manager.get_output_path(session_id).joinpath("result.txt").read_text() == "ok"
    assert idf_path.read_text() == "idf"


def test_manager_stops_a_running_simulation(tmp_path):
    idf_path = tmp_path / "source.idf"
    epw_path = tmp_path / "weather.epw"
    energy_path = tmp_path / "EnergyPlus"
    idf_path.write_text("idf")
    epw_path.write_text("epw")
    energy_path.mkdir()
    (energy_path / "ExpandObjects").write_text("")

    class StoppableSimulation:
        started = Event()
        stopped = Event()

        def __init__(self, config):
            self.config = config

        def run(self, queue):
            self.started.set()
            self.stopped.wait(1)

        def stop(self):
            self.stopped.set()

    manager = WebSimulationManager()
    session_id = manager.create_session()
    manager._new_simulation = StoppableSimulation
    assert manager.update_config(session_id, {
        "idf_path": str(idf_path), "epw_path": str(epw_path), "energy_path": str(energy_path),
        "rooms": ["ATELIE1"], "module_type": "COMPLETE",
    })
    assert manager.start_simulation(session_id)
    while not StoppableSimulation.started.is_set():
        time.sleep(0.01)
    assert manager.stop_simulation(session_id)
    manager.running_simulations[session_id]["thread"].join(timeout=2)
    assert manager.get_simulation_status(session_id) == "stopped"
