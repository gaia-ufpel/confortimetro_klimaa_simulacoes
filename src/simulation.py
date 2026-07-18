import subprocess
import sys
import os
import platform
from ctypes import c_void_p
from queue import Queue
from importlib import import_module
import shutil
import logging
from typing import Optional

from src.modules import MODULES_MAPPER
from src.utils import summary_one_room_results_from_csv, summary_rooms_results_from_eso, get_stats_from_simulation, split_target_period_excel
from src.utils.simulation_config import SimulationConfig
from src.utils.module_type import ModuleType
from src.processors import IDFProcessor

EnergyPlusAPI = None

EXPAND_OBJECTS_APP = "ExpandObjects"
TO_CSV_APP = "runreadvars"

if platform.system() == "Windows":
    EXPAND_OBJECTS_APP = "ExpandObjects.exe"
    TO_CSV_APP = "PostProcess/ReadVarsESO.exe"

class Simulation:
    """Classe principal para execução de simulações EnergyPlus."""
    
    def __init__(self, configs: SimulationConfig):
        self.conditioner = None  # type: Optional[object]
        self.stop_requested = False
        self.configs = configs
        self.logger = logging.getLogger("simulation")

        # Configurar EnergyPlus API
        sys.path.append(self.configs.energy_path)
        EnergyPlusAPI = import_module("pyenergyplus.api").EnergyPlusAPI

        self.ep_api = EnergyPlusAPI()
        self.state = self.ep_api.state_manager.new_state()
        
        # Inicializar processador de IDF
        self.idf_processor = IDFProcessor(self.configs)

    def run(self, q: Queue):
        """
        Executar simulação completa.
        
        Args:
            q: Queue para comunicação com interface gráfica
        """
        try:
            self.logger.info("Iniciando simulação")
            q.put("Iniciando simulação...")
            
            # Etapa 1: Definir módulo condicionador
            q.put("Configurando módulo condicionador...")
            self.conditioner = MODULES_MAPPER[self.configs.module_type](
                ep_api=self.ep_api, 
                configs=self.configs
            )
            
            # Etapa 2: Processar arquivo IDF
            q.put("Processando arquivo IDF...")
            self._process_idf()
            
            # Etapa 3: Expandir objetos EnergyPlus
            q.put("Expandindo objetos EnergyPlus...")
            self._expand_objects()
            
            # Etapa 4: Preparar diretórios de saída
            q.put("Preparando diretórios de saída...")
            self._prepare_output_directories()
            
            # Etapa 5: Executar simulação EnergyPlus
            q.put("Executando simulação EnergyPlus...")
            self._run_energyplus()

            if self.stop_requested:
                q.put("Simulação interrompida")
                return
            
            # Etapa 6: Processar resultados
            q.put("Processando resultados...")
            self._process_results(q)
            
            self.logger.info("Simulação concluída com sucesso")
            
        except Exception as e:
            error_msg = f"Erro durante simulação: {str(e)}"
            self.logger.error(error_msg)
            q.put(error_msg)
            raise
    
    def _process_idf(self):
        """Processar arquivo IDF usando o IDFProcessor."""
        try:
            # Validar IDF antes do processamento
            validation_errors = self.idf_processor.validate_idf()
            if validation_errors:
                raise ValueError(f"Erros de validação do IDF: {validation_errors}")
            
            # Processar arquivo IDF
            success = self.idf_processor.process_idf()
            if not success:
                raise RuntimeError("Falha no processamento do arquivo IDF")
            
            self.logger.info("Arquivo IDF processado com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro no processamento do IDF: {e}")
            raise
    
    def _expand_objects(self):
        """Expandir objetos EnergyPlus."""
        try:
            # Copiar arquivo IDF para diretório de entrada
            shutil.copy(self.configs.idf_path, os.path.join(self.configs.input_path, "in.idf"))
            
            # Executar ExpandObjects
            expand_cmd = [os.path.join(self.configs.energy_path, EXPAND_OBJECTS_APP)]
            result = subprocess.run(expand_cmd, cwd=self.configs.input_path, 
                                  capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                raise RuntimeError(f"ExpandObjects falhou: {result.stderr}")
            
            self.logger.info("Objetos expandidos com sucesso")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout ao expandir objetos")
        except Exception as e:
            self.logger.error(f"Erro ao expandir objetos: {e}")
            raise
    
    def _prepare_output_directories(self):
        """Preparar diretórios de saída."""
        try:
            os.makedirs(self.configs.output_path, exist_ok=True)
            self.configs.to_json(os.path.join(self.configs.output_path, "configs.json"))
            
            self.logger.info("Diretórios de saída preparados")
            
        except Exception as e:
            self.logger.error(f"Erro ao preparar diretórios: {e}")
            raise
    
    def _run_energyplus(self):
        """Executar simulação EnergyPlus."""
        try:
            if self.stop_requested:
                self.logger.info("Simulação cancelada antes de iniciar o EnergyPlus")
                return
            # Registrar callback do condicionador
            self.ep_api.runtime.callback_begin_zone_timestep_after_init_heat_balance(
                self.state, self.conditioner
            )
            
            # Executar simulação
            cmd_args = [
                '--weather', self.configs.epw_path,
                '--output-directory', self.configs.output_path,
                self.configs.expanded_idf_path
            ]
            
            self.ep_api.runtime.run_energyplus(self.state, cmd_args)
            self.ep_api.state_manager.reset_state(self.state)
            
            self.logger.info("Simulação EnergyPlus executada com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro na simulação EnergyPlus: {e}")
            raise

    def stop(self):
        """Solicitar que o EnergyPlus encerre a execução atual."""
        self.stop_requested = True
        runtime = self.ep_api.runtime
        stop = getattr(runtime, "stop_simulation", None)
        if stop:
            stop(self.state)
            return

        # EnergyPlus 9.4 exports stopSimulation but omits its Python wrapper.
        stop = runtime.api.stopSimulation
        stop.argtypes = [c_void_p]
        stop.restype = None
        stop(self.state)
    
    def _process_results(self, q: Queue):
        """Processar resultados da simulação."""
        try:
            q.put("Simulação finalizada!")
            print("Simulação finalizada!")
            
            q.put("Extraindo resultados...")
            print("Extraindo resultados...")
            summary_rooms_results_from_eso(self.configs.output_path, self.configs.rooms)
            q.put("Resultados extraidos com sucesso!")
            print("Resultados extraidos com sucesso!")
            
            q.put("Extraindo estatísticas...")
            print("Extraindo estatísticas...")
            get_stats_from_simulation(self.configs.output_path, self.configs.rooms)
            q.put("Estatísticas extraidas com sucesso!")
            print("Estatísticas extraidas com sucesso!")
            
            q.put("Dividindo resultados por período...")
            print("Dividindo resultados por período...")
            split_target_period_excel(os.path.join(self.configs.output_path, "ATELIE1.xlsx"))
            q.put("Resultados divididos com sucesso!")
            print("Resultados divididos com sucesso!")
            
            q.put("EXIT")
            
        except Exception as e:
            error_msg = f"Erro no processamento de resultados: {str(e)}"
            self.logger.error(error_msg)
            q.put(error_msg)
            raise
    
    def get_idf_summary(self):
        """Obter resumo do arquivo IDF processado."""
        return self.idf_processor.get_idf_summary()
        
