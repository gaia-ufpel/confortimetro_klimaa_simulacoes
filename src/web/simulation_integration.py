"""Bridge between the Flask UI and the desktop simulation pipeline."""

import copy
import logging
import os
from pathlib import Path
from queue import Queue
import shutil
import tempfile
import threading
import uuid
import zipfile
from typing import Any, Dict, Optional

from src.utils.module_type import ModuleType
from src.utils.simulation_config import SimulationConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FIELDS = (
    "epw_path", "energy_path", "rooms", "pmv_upperbound", "pmv_lowerbound",
    "co2_limit", "max_vel", "adaptative_bound", "temp_ac_min", "temp_ac_max",
    "wme", "clo_max", "clo_min", "clo_delta", "temp_open_window_bound",
    "air_speed_delta", "pmv_comfort_bound", "module_type",
)


class WebSimulationManager:
    """Runs the existing EnergyPlus pipeline and forwards its queue to Socket.IO."""

    def __init__(self, socketio=None):
        self.socketio = socketio
        self.running_simulations: Dict[str, Dict[str, Any]] = {}
        self.simulation_configs: Dict[str, SimulationConfig] = {}
        self.session_dirs: Dict[str, Path] = {}
        self.logger = logging.getLogger(__name__)

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.session_dirs[session_id] = Path(tempfile.mkdtemp(prefix=f"confortimetro_{session_id}_"))
        return session_id

    def update_config(self, session_id: str, config_data: Dict[str, Any]) -> bool:
        try:
            module_type = ModuleType(config_data.get("module_type", ModuleType.COMPLETE))
            config = SimulationConfig(
                met_as_watts=0,
                _idf_path=str(config_data.get("idf_path", "")),
                _met=float(config_data.get("met", 1.0)),
                epw_path=str(config_data.get("epw_path", "")),
                energy_path=str(config_data.get("energy_path", "")),
                output_path="",
                rooms=[room for room in config_data.get("rooms", []) if room],
                pmv_upperbound=float(config_data.get("pmv_upperbound", 0.5)),
                pmv_lowerbound=float(config_data.get("pmv_lowerbound", -0.5)),
                temp_ac_min=float(config_data.get("temp_ac_min", 18.0)),
                temp_ac_max=float(config_data.get("temp_ac_max", 26.0)),
                wme=float(config_data.get("wme", 0.0)),
                module_type=module_type,
                **{field: config_data[field] for field in CONFIG_FIELDS
                   if field in config_data and field not in {"epw_path", "energy_path", "rooms", "pmv_upperbound", "pmv_lowerbound", "temp_ac_min", "temp_ac_max", "wme", "module_type"}},
            )
            self.simulation_configs[session_id] = config
            self.emit_message(session_id, "Configuração atualizada", "success")
            return True
        except (TypeError, ValueError) as error:
            self.emit_message(session_id, f"Erro na configuração: {error}", "error")
            return False

    def get_config(self, session_id: str) -> Optional[Dict[str, Any]]:
        config = self.simulation_configs.get(session_id)
        if not config:
            return None
        result = {"idf_path": config.idf_path, "met": config.met}
        result.update({field: getattr(config, field) for field in CONFIG_FIELDS})
        result["module_type"] = str(config.module_type)
        return result

    def start_simulation(self, session_id: str) -> bool:
        current = self.running_simulations.get(session_id)
        if current and current["status"] in {"starting", "running", "stopping"}:
            self.emit_message(session_id, "Simulação já está em execução", "warning")
            return False

        config = self.simulation_configs.get(session_id)
        if not config or not self._validate_config(config, session_id):
            return False

        run_config = self._prepare_run_config(session_id, config)
        if not run_config:
            return False

        thread = threading.Thread(target=self._run_simulation, args=(session_id, run_config), daemon=True)
        self.running_simulations[session_id] = {"thread": thread, "simulation": None, "status": "starting"}
        thread.start()
        self.emit_message(session_id, "Simulação iniciada", "info")
        return True

    def stop_simulation(self, session_id: str) -> bool:
        run = self.running_simulations.get(session_id)
        if not run or run["status"] not in {"starting", "running"}:
            self.emit_message(session_id, "Nenhuma simulação em execução", "warning")
            return False
        run["status"] = "stopping"
        simulation = run["simulation"]
        if simulation is not None:
            try:
                simulation.stop()
            except Exception as error:
                self.logger.exception("Could not stop simulation")
                self.emit_message(session_id, f"Não foi possível parar a simulação: {error}", "error")
                return False
        self.emit_message(session_id, "Parada solicitada", "warning")
        return True

    def get_simulation_status(self, session_id: str) -> str:
        run = self.running_simulations.get(session_id)
        return run["status"] if run else "stopped"

    def get_output_path(self, session_id: str) -> Optional[Path]:
        config = self.simulation_configs.get(session_id)
        return Path(config.output_path) if config and config.output_path else None

    def zip_outputs(self, session_id: str) -> Dict[str, Any]:
        output_path = self.get_output_path(session_id)
        if not output_path or not output_path.is_dir() or not any(output_path.iterdir()):
            return {"status": "error", "error": "Ainda não há resultados para baixar"}
        try:
            archive = tempfile.NamedTemporaryFile(prefix=f"sim_{session_id}_", suffix=".zip", delete=False)
            archive.close()
            with zipfile.ZipFile(archive.name, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for path in output_path.rglob("*"):
                    if path.is_file():
                        zip_file.write(path, path.relative_to(output_path))
            return {"status": "success", "zip_path": archive.name}
        except OSError as error:
            self.logger.exception("Could not create output archive")
            return {"status": "error", "error": str(error)}

    def _prepare_run_config(self, session_id: str, config: SimulationConfig) -> Optional[SimulationConfig]:
        try:
            run_dir = self.session_dirs.setdefault(session_id, Path(tempfile.mkdtemp(prefix=f"confortimetro_{session_id}_"))) / uuid.uuid4().hex
            input_dir = run_dir / "input"
            output_dir = run_dir / "output"
            input_dir.mkdir(parents=True)
            idf_path = input_dir / Path(config.idf_path).name
            shutil.copy2(config.idf_path, idf_path)

            run_config = copy.deepcopy(config)
            run_config.idf_path = str(idf_path)
            run_config.output_path = str(output_dir)
            self.simulation_configs[session_id] = run_config
            return run_config
        except OSError as error:
            self.logger.exception("Could not prepare simulation files")
            self.emit_message(session_id, f"Erro ao preparar arquivos da simulação: {error}", "error")
            return None

    def _validate_config(self, config: SimulationConfig, session_id: str) -> bool:
        errors = []
        for label, path in (("Arquivo IDF", config.idf_path), ("Arquivo EPW", config.epw_path), ("Caminho do EnergyPlus", config.energy_path)):
            if not path:
                errors.append(f"{label} é obrigatório")
            elif not Path(path).exists():
                errors.append(f"{label} não encontrado")
        if config.energy_path and not (Path(config.energy_path) / ("ExpandObjects.exe" if os.name == "nt" else "ExpandObjects")).is_file():
            errors.append("ExpandObjects não encontrado na instalação do EnergyPlus")
        if not config.rooms:
            errors.append("Informe ao menos um ambiente")
        if config.pmv_lowerbound >= config.pmv_upperbound:
            errors.append("PMV inferior deve ser menor que PMV superior")
        if config.temp_ac_min >= config.temp_ac_max:
            errors.append("Temperatura mínima deve ser menor que temperatura máxima")
        for error in errors:
            self.emit_message(session_id, error, "error")
        return not errors

    def _run_simulation(self, session_id: str, config: SimulationConfig) -> None:
        queue: Queue = Queue()
        failure = []
        run = self.running_simulations[session_id]

        def execute() -> None:
            try:
                simulation = self._new_simulation(config)
                run["simulation"] = simulation
                if run["status"] == "stopping":
                    simulation.stop()
                else:
                    run["status"] = "running"
                simulation.run(queue)
            except Exception as error:
                failure.append(error)
            finally:
                queue.put(None)

        worker = threading.Thread(target=execute, daemon=True)
        worker.start()
        while True:
            message = queue.get()
            if message is None:
                break
            self.emit_message(session_id, str(message), "error" if str(message).startswith("Erro") else "info")
        worker.join()

        if failure:
            run["status"] = "error"
            self.emit_message(session_id, f"Erro na simulação: {failure[0]}", "error")
        elif run["status"] == "stopping":
            run["status"] = "stopped"
            self.emit_message(session_id, "Simulação interrompida", "warning")
        else:
            run["status"] = "completed"
            self.emit_message(session_id, "Simulação concluída com sucesso!", "success")

        if self.socketio:
            self.socketio.emit("simulation_finished", {"session_id": session_id, "status": run["status"]}, to=session_id)

    def emit_message(self, session_id: str, message: str, msg_type: str = "info") -> None:
        payload = {"message": message, "type": msg_type, "session_id": session_id}
        if self.socketio:
            self.socketio.emit("simulation_message", payload, to=session_id)
        else:
            self.logger.info("[%s] %s", session_id, message)

    @staticmethod
    def _new_simulation(config: SimulationConfig):
        """Delay core imports until a simulation is actually requested."""
        from src.simulation import Simulation
        return Simulation(config)


class FileUploadManager:
    """Stores IDF and EPW uploads outside the static web tree."""

    allowed_extensions = {"idf": ".idf", "epw": ".epw"}

    def __init__(self, upload_dir: Optional[str] = None):
        self.upload_dir = Path(upload_dir) if upload_dir else PROJECT_ROOT / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def save_uploaded_file(self, file, file_type: str) -> Dict[str, Any]:
        extension = self.allowed_extensions.get(file_type)
        if not extension:
            return {"status": "error", "error": f"Tipo de arquivo não suportado: {file_type}"}
        if not file.filename or Path(file.filename).suffix.lower() != extension:
            return {"status": "error", "error": f"Extensão inválida para {file_type}"}
        try:
            path = self.upload_dir / f"{file_type}_{uuid.uuid4().hex}{extension}"
            file.save(path)
            return {"status": "success", "path": str(path.resolve()), "filename": file.filename, "unique_name": path.name}
        except OSError as error:
            self.logger.exception("Upload failed")
            return {"status": "error", "error": f"Erro no upload: {error}"}
