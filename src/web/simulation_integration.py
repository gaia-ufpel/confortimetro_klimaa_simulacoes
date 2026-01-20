"""
Integration layer between Flask web app and existing simulation modules
"""
import os
import sys
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import shutil
import tempfile
import zipfile

# Add parent directory to path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from simulation import ConfortimetroSimulation
    from simulation_config import SimulationConfig
    from utils import setup_logging
except ImportError as e:
    logging.warning(f"Could not import simulation modules: {e}")
    # Fallback classes for development
    class ConfortimetroSimulation:
        def __init__(self, config):
            self.config = config
        
        def run(self):
            pass
    
    class SimulationConfig:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    def setup_logging(level):
        logging.basicConfig(level=level)


class WebSimulationManager:
    """Manages simulation runs for the web interface"""
    
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.running_simulations: Dict[str, Any] = {}
        self.simulation_configs: Dict[str, SimulationConfig] = {}
        self.logger = logging.getLogger(__name__)
        
    def create_session(self) -> str:
        """Create a new session ID"""
        session_id = str(uuid.uuid4())
        # Create a temporary output directory for this session immediately
        try:
            tmpdir = tempfile.mkdtemp(prefix=f"sim_{session_id}_")
            config = SimulationConfig(output_path=str(Path(tmpdir)))
            self.simulation_configs[session_id] = config
            self.logger.info(f"Created session {session_id} with temp output {tmpdir}")
        except Exception as e:
            # Fallback to None if temp creation fails
            self.logger.error(f"Failed to create temp dir for session {session_id}: {e}")
            self.simulation_configs[session_id] = None

        return session_id
        
    def update_config(self, session_id: str, config_data: Dict[str, Any]) -> bool:
        """Update configuration for a session"""
        try:
            # Validate paths (output_path is handled by the server as a temp folder)
            required_paths = ['idf_path', 'epw_path', 'energy_path']
            for path_key in required_paths:
                if path_key in config_data and config_data[path_key]:
                    path = Path(config_data[path_key])
                    if path_key.endswith('_path') and path_key != 'output_path':
                        if not path.exists():
                            self.emit_message(session_id, f"Caminho não encontrado: {path}", "error")
                            return False
            
            # Create simulation config
            config = SimulationConfig(
                idf_path=config_data.get('idf_path', ''),
                epw_path=config_data.get('epw_path', ''),
                output_path=config_data.get('output_path', ''),
                energy_path=config_data.get('energy_path', ''),
                pmv_lowerbound=config_data.get('pmv_lowerbound', -0.5),
                pmv_upperbound=config_data.get('pmv_upperbound', 0.5),
                temp_ac_min=config_data.get('temp_ac_min', 18.0),
                temp_ac_max=config_data.get('temp_ac_max', 26.0),
                met=config_data.get('met', 1.0),
                wme=config_data.get('wme', 0.0),
                module_type=config_data.get('module_type', 'COMPLETE'),
                rooms=config_data.get('rooms', ['ATELIE1'])
            )
            
            self.simulation_configs[session_id] = config
            self.emit_message(session_id, "Configuração atualizada", "success")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
            self.emit_message(session_id, f"Erro na configuração: {str(e)}", "error")
            return False
    
    def get_config(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a session"""
        config = self.simulation_configs.get(session_id)
        if not config:
            return None
        return {
            'idf_path': getattr(config, 'idf_path', ''),
            'epw_path': getattr(config, 'epw_path', ''),
            'energy_path': getattr(config, 'energy_path', ''),
            'pmv_lowerbound': getattr(config, 'pmv_lowerbound', -0.5),
            'pmv_upperbound': getattr(config, 'pmv_upperbound', 0.5),
            'temp_ac_min': getattr(config, 'temp_ac_min', 18.0),
            'temp_ac_max': getattr(config, 'temp_ac_max', 26.0),
            'met': getattr(config, 'met', 1.0),
            'wme': getattr(config, 'wme', 0.0),
            'module_type': getattr(config, 'module_type', 'COMPLETE'),
            'rooms': getattr(config, 'rooms', ['ATELIE1'])
        }
    
    def start_simulation(self, session_id: str) -> bool:
        """Start a simulation for the given session"""
        if session_id in self.running_simulations:
            self.emit_message(session_id, "Simulação já está em execução", "warning")
            return False
            
        config = self.simulation_configs.get(session_id)
        if not config:
            self.emit_message(session_id, "Configuração não encontrada", "error")
            return False
            
        try:
            # Validate configuration
            if not self._validate_config(config, session_id):
                return False
                
            # Ensure a session-specific output directory exists
            # Create a system temporary directory for this session's outputs
            try:
                tmpdir = tempfile.mkdtemp(prefix=f"sim_{session_id}_")
                session_out = Path(tmpdir)
                config.output_path = str(session_out)
                self.logger.info(f"Using temp output dir for session {session_id}: {session_out}")
            except Exception as e:
                self.logger.error(f"Error creating temp output directory: {e}")
                self.emit_message(session_id, f"Erro ao preparar diretório temporário: {e}", "error")
                return False

            # Create simulation instance
            simulation = ConfortimetroSimulation(config)
            
            # Create and start simulation thread
            thread = threading.Thread(
                target=self._run_simulation,
                args=(session_id, simulation),
                daemon=True
            )
            
            self.running_simulations[session_id] = {
                'thread': thread,
                'simulation': simulation,
                'status': 'starting'
            }
            
            thread.start()
            self.emit_message(session_id, "Simulação iniciada", "info")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting simulation: {e}")
            self.emit_message(session_id, f"Erro ao iniciar simulação: {str(e)}", "error")
            return False
    
    def stop_simulation(self, session_id: str) -> bool:
        """Stop a running simulation"""
        if session_id not in self.running_simulations:
            self.emit_message(session_id, "Nenhuma simulação em execução", "warning")
            return False
            
        try:
            sim_info = self.running_simulations[session_id]
            sim_info['status'] = 'stopping'
            
            # In a real implementation, you'd have a way to stop the simulation
            # For now, we'll just mark it as stopped
            self.emit_message(session_id, "Parada solicitada", "warning")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping simulation: {e}")
            self.emit_message(session_id, f"Erro ao parar simulação: {str(e)}", "error")
            return False
    
    def get_simulation_status(self, session_id: str) -> str:
        """Get the status of a simulation"""
        if session_id not in self.running_simulations:
            return "stopped"
        return self.running_simulations[session_id]['status']

    def get_output_path(self, session_id: str) -> Optional[Path]:
        """Return configured output path for a session as a Path or None"""
        config = self.simulation_configs.get(session_id)
        if not config:
            return None

        out = getattr(config, 'output_path', None)
        if not out:
            return None
        return Path(out)

    def zip_outputs(self, session_id: str, max_bytes: Optional[int] = None) -> Dict[str, Any]:
        """Create a temporary zip of the simulation output folder for the session.

        Returns dict with status and path or error.
        """
        try:
            out_path = self.get_output_path(session_id)
            if not out_path:
                return {'status': 'error', 'error': 'Caminho de saída não configurado'}

            if not out_path.exists():
                return {'status': 'error', 'error': f'Caminho de saída não encontrado: {out_path}'}

            # Create a temporary zip file
            tmp_zip = tempfile.NamedTemporaryFile(prefix=f'sim_{session_id}_', suffix='.zip', delete=False)
            tmp_zip.close()

            with zipfile.ZipFile(tmp_zip.name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                if out_path.is_file():
                    # Single file
                    zf.write(out_path, arcname=out_path.name)
                else:
                    # Directory: walk and add files
                    for root, dirs, files in os.walk(out_path):
                        for f in files:
                            full = Path(root) / f
                            # Optionally enforce a max size
                            if max_bytes and full.stat().st_size > max_bytes:
                                self.logger.warning(f"Skipping large file in zip: {full}")
                                continue
                            try:
                                rel = full.relative_to(out_path)
                            except Exception:
                                rel = Path(full.name)
                            zf.write(full, arcname=str(rel))

            return {'status': 'success', 'zip_path': tmp_zip.name}

        except Exception as e:
            self.logger.error(f"Error creating zip for session {session_id}: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _validate_config(self, config: SimulationConfig, session_id: str) -> bool:
        """Validate simulation configuration"""
        errors = []
        
        # Check required paths
        if not config.idf_path:
            errors.append("Arquivo IDF é obrigatório")
        elif not Path(config.idf_path).exists():
            errors.append("Arquivo IDF não encontrado")
            
        if not config.epw_path:
            errors.append("Arquivo EPW é obrigatório")
        elif not Path(config.epw_path).exists():
            errors.append("Arquivo EPW não encontrado")
            
        if not config.output_path:
            errors.append("Diretório de saída é obrigatório")
            
        if not config.energy_path:
            errors.append("Caminho do EnergyPlus é obrigatório")
        elif not Path(config.energy_path).exists():
            errors.append("Caminho do EnergyPlus não encontrado")
            
        # Validate numeric ranges
        if config.pmv_lowerbound >= config.pmv_upperbound:
            errors.append("PMV inferior deve ser menor que PMV superior")
            
        if config.temp_ac_min >= config.temp_ac_max:
            errors.append("Temperatura mínima deve ser menor que temperatura máxima")
            
        if errors:
            for error in errors:
                self.emit_message(session_id, error, "error")
            return False
            
        return True
    
    def _run_simulation(self, session_id: str, simulation: ConfortimetroSimulation):
        """Run simulation in a separate thread"""
        try:
            self.running_simulations[session_id]['status'] = 'running'
            self.emit_message(session_id, "Executando simulação...", "info")
            
            # Run the simulation
            simulation.run()
            
            # Simulation completed
            self.running_simulations[session_id]['status'] = 'completed'
            self.emit_message(session_id, "Simulação concluída com sucesso!", "success")
            
            # Emit completion event
            if self.socketio:
                self.socketio.emit('simulation_finished', {
                    'message': 'Simulação concluída',
                    'session_id': session_id
                })
                
        except Exception as e:
            self.logger.error(f"Simulation error: {e}")
            self.running_simulations[session_id]['status'] = 'error'
            self.emit_message(session_id, f"Erro na simulação: {str(e)}", "error")
            
        finally:
            # Clean up
            if session_id in self.running_simulations:
                del self.running_simulations[session_id]
    
    def emit_message(self, session_id: str, message: str, msg_type: str = "info"):
        """Emit a message to the client"""
        if self.socketio:
            self.socketio.emit('simulation_message', {
                'message': message,
                'type': msg_type,
                'session_id': session_id
            })
        else:
            # Fallback to logging
            self.logger.info(f"[{session_id}] [{msg_type}] {message}")


class FileUploadManager:
    """Manages file uploads for the web interface"""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Allowed file extensions
        self.allowed_extensions = {
            'idf': ['.idf'],
            'epw': ['.epw']
        }
    
    def save_uploaded_file(self, file, file_type: str) -> Dict[str, Any]:
        """Save uploaded file and return result"""
        try:
            # Validate file type
            if file_type not in self.allowed_extensions:
                return {
                    'status': 'error',
                    'error': f'Tipo de arquivo não suportado: {file_type}'
                }
            
            # Check file extension
            filename = file.filename
            if not filename:
                return {
                    'status': 'error',
                    'error': 'Nome do arquivo não fornecido'
                }
                
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.allowed_extensions[file_type]:
                return {
                    'status': 'error',
                    'error': f'Extensão inválida para {file_type}: {file_ext}'
                }
            
            # Generate unique filename
            unique_filename = f"{file_type}_{uuid.uuid4().hex[:8]}{file_ext}"
            file_path = self.upload_dir / unique_filename
            
            # Save file
            file.save(str(file_path))
            
            self.logger.info(f"File uploaded: {filename} -> {file_path}")
            
            return {
                'status': 'success',
                'path': str(file_path.absolute()),
                'filename': filename,
                'unique_name': unique_filename
            }
            
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            return {
                'status': 'error',
                'error': f'Erro no upload: {str(e)}'
            }
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old uploaded files"""
        import time
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for file_path in self.upload_dir.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    self.logger.info(f"Cleaned up old file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up {file_path}: {e}")
