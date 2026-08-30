import subprocess
import sys
import os
import platform
from queue import Queue
from importlib import import_module
import shutil
import logging
from typing import Optional

from confortimetro.control import MODULES_MAPPER
from confortimetro.control.base import request_stop
from confortimetro.results import (
    summary_rooms_results_from_eso,
    get_stats_from_simulation,
    split_target_period_excel,
)
from confortimetro.config import SimulationConfig
from confortimetro.module_type import ModuleType
from confortimetro.idf import IDFProcessor, read_run_period, read_timesteps_per_hour

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
            
            # Etapa 2: Preparar o diretório da execução e copiar o IDF para lá
            q.put("Preparando diretórios de saída...")
            self._prepare_output_directories()

            # Etapa 3: Processar o IDF (a cópia da execução, não o original)
            q.put("Processando arquivo IDF...")
            self._process_idf()

            # Etapa 4: Expandir objetos EnergyPlus
            q.put("Expandindo objetos EnergyPlus...")
            self._expand_objects()

            self.configs.to_json(os.path.join(self.configs.output_path, "configs.json"))
            
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
        """Expandir objetos EnergyPlus dentro do diretório da execução."""
        try:
            # ExpandObjects lê in.idf e escreve expanded.idf no diretório em que
            # roda; rodar no diretório da execução é o que mantém os artefatos
            # dela juntos e permite execuções paralelas sobre o mesmo modelo.
            shutil.copy(self.configs.idf_path,
                        os.path.join(self.configs.output_path, "in.idf"))

            expand_cmd = [os.path.join(self.configs.energy_path, EXPAND_OBJECTS_APP)]
            result = subprocess.run(expand_cmd, cwd=self.configs.output_path,
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
        """Criar o diretório da execução e trazer o modelo para dentro dele."""
        try:
            os.makedirs(self.configs.output_path, exist_ok=True)
            # output_path pode ter sido trocado depois da configuração ser criada.
            self.configs.expanded_idf_path = os.path.join(
                self.configs.output_path, "expanded.idf")

            # O IDFProcessor grava as alterações no lugar. Processar uma cópia
            # dentro da execução preserva o modelo original e deixa registrado
            # exatamente o IDF que foi simulado.
            if self.configs.source_idf_path is None:
                self.configs.source_idf_path = self.configs.idf_path
            model_path = os.path.join(self.configs.output_path, "modelo.idf")
            shutil.copy(self.configs.source_idf_path, model_path)
            self.configs.idf_path = model_path

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
            
            exit_code = self.ep_api.runtime.run_energyplus(self.state, cmd_args)
            self.ep_api.state_manager.reset_state(self.state)

            # Exceções do condicionador são engolidas pelo ctypes durante o run;
            # o condicionador guarda a primeira e ela é relançada aqui.
            if self.conditioner.error is not None:
                raise RuntimeError(
                    f"Condicionador falhou durante a simulação: {self.conditioner.error}"
                ) from self.conditioner.error

            if exit_code != 0 and not self.stop_requested:
                raise RuntimeError(
                    f"EnergyPlus terminou com código {exit_code}. "
                    f"Veja {os.path.join(self.configs.output_path, 'eplusout.err')}"
                )

            self._check_energyplus_errors()

            self.logger.info("Simulação EnergyPlus executada com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro na simulação EnergyPlus: {e}")
            raise

    def _check_energyplus_errors(self):
        """Abortar se o EnergyPlus não tiver terminado com sucesso.

        O eplusout.end é a linha de status canônica do EnergyPlus; sem esta
        checagem um erro fatal passava como "simulação concluída com sucesso".
        """
        if self.stop_requested:
            return

        end_path = os.path.join(self.configs.output_path, "eplusout.end")
        err_path = os.path.join(self.configs.output_path, "eplusout.err")
        if not os.path.exists(end_path):
            raise RuntimeError(
                f"EnergyPlus não gerou {end_path} (execução abortada). Veja {err_path}"
            )

        with open(end_path, "r", errors="replace") as end_file:
            status = end_file.read().strip()

        if "Completed Successfully" not in status:
            raise RuntimeError(f"EnergyPlus não concluiu: {status}. Veja {err_path}")

        self.logger.info(status)

    def stop(self):
        """Solicitar que o EnergyPlus encerre a execução atual."""
        self.stop_requested = True
        request_stop(self.ep_api, self.state)
    
    def _process_results(self, q: Queue):
        """Processar resultados da simulação."""
        try:
            q.put("Simulação finalizada!")
            print("Simulação finalizada!")
            
            q.put("Extraindo resultados...")
            print("Extraindo resultados...")
            # O período e o passo vêm do IDF simulado: com valores fixos, um
            # modelo de outro ano ou outro timestep sairia com datas erradas.
            start, end = read_run_period(self.configs.idf_path)
            summary_rooms_results_from_eso(
                self.configs.output_path, self.configs.rooms,
                timesteps_per_hour=read_timesteps_per_hour(self.configs.idf_path),
                start_date=start, end_date=end)
            q.put("Resultados extraidos com sucesso!")
            print("Resultados extraidos com sucesso!")
            
            q.put("Extraindo estatísticas...")
            print("Extraindo estatísticas...")
            get_stats_from_simulation(self.configs.output_path, self.configs.rooms)
            q.put("Estatísticas extraidas com sucesso!")
            print("Estatísticas extraidas com sucesso!")
            
            q.put("Dividindo resultados por período...")
            print("Dividindo resultados por período...")
            for room in self.configs.rooms:
                split_target_period_excel(
                    os.path.join(self.configs.output_path, f"{room}.xlsx"), room)
            q.put("Resultados divididos com sucesso!")
            print("Resultados divididos com sucesso!")
            
            q.put("EXIT")
            
        except Exception as e:
            error_msg = f"Erro no processamento de resultados: {str(e)}"
            self.logger.error(error_msg)
            q.put(error_msg)
            raise
