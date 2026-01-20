"""
Processador para arquivos IDF do EnergyPlus.

Este módulo é responsável por todas as modificações e manipulações
de arquivos IDF necessárias para as simulações.
"""

import os
import platform
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from eppy.modeleditor import IDF

from ..utils.simulation_config import SimulationConfig
from ..utils.module_type import ModuleType


class IDFProcessor:
    """Processador para modificar arquivos IDF do EnergyPlus."""
    
    # Constantes para nomes de schedules
    OUTDOOR_CO2_SCHEDULE_NAME = "Outdoor CO2 Schedule"
    PEOPLE_OBJECT_NAME = "PEOPLE_{}"
    JANELA_SCHEDULE_NAME = "JANELA_{}"
    VENT_SCHEDULE_NAME = "VENT_{}"
    VEL_SCHEDULE_NAME = "VEL_{}"
    AC_SCHEDULE_NAME = "AC_{}"
    DOAS_SCHEDULE_NAME = "DOAS_STATUS_{}"
    TEMP_COOL_AC_SCHEDULE_NAME = "TEMP_COOL_AC_{}"
    TEMP_HEAT_AC_SCHEDULE_NAME = "TEMP_HEAT_AC_{}"
    PMV_SCHEDULE_NAME = "PMV_{}"
    TEMP_OP_SCHEDULE_NAME = "TEMP_OP_{}"
    ADAP_MIN_SCHEDULE_NAME = "ADAP_MIN_{}"
    ADAP_MAX_SCHEDULE_NAME = "ADAP_MAX_{}"
    EM_CONFORTO_SCHEDULE_NAME = "EM_CONFORTO_{}"
    MET_SCHEDULE_NAME = "METABOLISMO"
    WME_SCHEDULE_NAME = "WORK_EF"
    
    # Separador de caminho
    PATH_SEP = "/"
    
    def __init__(self, configs: SimulationConfig):
        """
        Inicializar o processador de IDF.
        
        Args:
            configs: Configurações da simulação
        """
        self.configs = configs
        self.logger = logging.getLogger("idf_processor")
        
        # Configurar eppy com o caminho do IDD
        self._setup_eppy()
    
    def _setup_eppy(self):
        """Configurar o eppy com o arquivo IDD do EnergyPlus."""
        try:
            idd_path = self.PATH_SEP.join([self.configs.energy_path, "Energy+.idd"])
            if not os.path.exists(idd_path):
                raise FileNotFoundError(f"IDD file not found: {idd_path}")
            
            IDF.setiddname(idd_path)
            self.logger.info(f"Eppy configured with IDD: {idd_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup eppy: {e}")
            raise
    
    def process_idf(self) -> bool:
        """
        Processar arquivo IDF completo aplicando todas as modificações necessárias.
        
        Returns:
            bool: True se processamento foi bem-sucedido
        """
        try:
            self.logger.info(f"Starting IDF processing: {self.configs.idf_path}")
            
            # Carregar arquivo IDF
            idf = IDF(self.configs.idf_path)
            
            # Aplicar modificações em sequência
            idf = self._modify_simulation_name(idf)
            idf = self._modify_existing_schedules(idf)
            idf = self._add_new_schedules(idf)
            idf = self._configure_people_objects(idf)
            idf = self._add_output_variables(idf)
            
            # Salvar arquivo modificado
            idf.save(self.configs.idf_path)
            
            self.logger.info("IDF processing completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"IDF processing failed: {e}")
            raise
    
    def _modify_simulation_name(self, idf: IDF) -> IDF:
        """
        Modificar nome da simulação baseado no diretório de saída.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            if idf.idfobjects.get("RunPeriod"):
                run_period = idf.idfobjects["RunPeriod"][0]
                simulation_name = self.configs.output_path.split(self.PATH_SEP)[-1]
                run_period.Name = simulation_name
                self.logger.debug(f"Simulation name set to: {simulation_name}")
            
            return idf
            
        except Exception as e:
            self.logger.warning(f"Failed to modify simulation name: {e}")
            return idf
    
    def _modify_existing_schedules(self, idf: IDF) -> IDF:
        """
        Modificar schedules existentes no arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            schedules_modified = 0
            
            for schedule in idf.idfobjects.get("Schedule:Constant", []):
                schedule_name = schedule.Name
                
                # Modificar schedule de metabolismo
                if schedule_name == self.MET_SCHEDULE_NAME:
                    schedule.Schedule_Type_Limits_Name = "Any Number"
                    schedule.Hourly_Value = self.configs.met_as_watts
                    schedules_modified += 1
                    self.logger.debug(f"Modified MET schedule: {self.configs.met_as_watts}")
                
                # Modificar schedule de work efficiency
                elif schedule_name == self.WME_SCHEDULE_NAME:
                    schedule.Schedule_Type_Limits_Name = "Any Number"
                    schedule.Hourly_Value = self.configs.wme
                    schedules_modified += 1
                    self.logger.debug(f"Modified WME schedule: {self.configs.wme}")
                
                # Modificações específicas para módulo FIXED_AC_WITHOUT_FAN
                elif self.configs.module_type == ModuleType.FIXED_AC_WITHOUT_FAN:
                    if self.TEMP_COOL_AC_SCHEDULE_NAME.format("") in schedule_name:
                        schedule.Hourly_Value = self.configs.temp_ac_max
                        schedules_modified += 1
                        self.logger.debug(f"Modified cooling schedule {schedule_name}: {self.configs.temp_ac_max}")
                    
                    elif self.TEMP_HEAT_AC_SCHEDULE_NAME.format("") in schedule_name:
                        schedule.Hourly_Value = self.configs.temp_ac_min
                        schedules_modified += 1
                        self.logger.debug(f"Modified heating schedule {schedule_name}: {self.configs.temp_ac_min}")
            
            self.logger.info(f"Modified {schedules_modified} existing schedules")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to modify existing schedules: {e}")
            return idf
    
    def _add_new_schedules(self, idf: IDF) -> IDF:
        """
        Adicionar novos schedules ao arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            # Adicionar tipos de limite de schedule se não existirem
            self._ensure_schedule_type_limits(idf)
            
            # Schedule de CO2 externo
            idf.newidfobject(
                "Schedule:Constant",
                Name=self.OUTDOOR_CO2_SCHEDULE_NAME,
                Schedule_Type_Limits_Name="Any Number",
                Hourly_Value=400
            )
            
            schedules_added = 1  # CO2 schedule
            
            # Schedules específicos por sala
            for room in self.configs.rooms:
                room_schedules = [
                    (self.JANELA_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.VENT_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.VEL_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.AC_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.DOAS_SCHEDULE_NAME.format(room), "On/Off", 0),
                    (self.TEMP_COOL_AC_SCHEDULE_NAME.format(room), "Any Number", self.configs.temp_ac_max),
                    (self.TEMP_HEAT_AC_SCHEDULE_NAME.format(room), "Any Number", self.configs.temp_ac_min),
                    (self.PMV_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.TEMP_OP_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.ADAP_MIN_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.ADAP_MAX_SCHEDULE_NAME.format(room), "Any Number", 0),
                    (self.EM_CONFORTO_SCHEDULE_NAME.format(room), "On/Off", 0)
                ]
                
                for schedule_name, schedule_type, value in room_schedules:
                    idf.newidfobject(
                        "Schedule:Constant",
                        Name=schedule_name,
                        Schedule_Type_Limits_Name=schedule_type,
                        Hourly_Value=value
                    )
                    schedules_added += 1
            
            # Schedules globais
            global_schedules = [
                (self.MET_SCHEDULE_NAME, "Any Number", self.configs.met_as_watts),
                (self.WME_SCHEDULE_NAME, "Any Number", self.configs.wme)
            ]
            
            for schedule_name, schedule_type, value in global_schedules:
                idf.newidfobject(
                    "Schedule:Constant",
                    Name=schedule_name,
                    Schedule_Type_Limits_Name=schedule_type,
                    Hourly_Value=value
                )
                schedules_added += 1
            
            self.logger.info(f"Added {schedules_added} new schedules")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to add new schedules: {e}")
            return idf
    
    def _ensure_schedule_type_limits(self, idf: IDF):
        """
        Garantir que os tipos de limite de schedule necessários existam.
        
        Args:
            idf: Objeto IDF do eppy
        """
        try:
            # Verificar tipos existentes
            existing_types = {obj.Name for obj in idf.idfobjects.get("ScheduleTypeLimits", [])}
            
            # Tipos necessários
            required_types = [
                ("On/Off", {
                    "Lower_Limit_Value": 0,
                    "Upper_Limit_Value": 1,
                    "Numeric_Type": "DISCRETE",
                    "Unit_Type": "Dimensionless"
                }),
                ("Any Number", {})
            ]
            
            # Adicionar tipos que não existem
            for type_name, params in required_types:
                if type_name not in existing_types:
                    idf.newidfobject("ScheduleTypeLimits", Name=type_name, **params)
                    self.logger.debug(f"Added schedule type limit: {type_name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to ensure schedule type limits: {e}")
    
    def _configure_people_objects(self, idf: IDF) -> IDF:
        """
        Configurar objetos de pessoas no arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            people_configured = 0
            
            for people in idf.idfobjects.get("People", []):
                people.Activity_Level_Schedule_Name = self.MET_SCHEDULE_NAME
                people.Work_Efficiency_Schedule_Name = self.WME_SCHEDULE_NAME
                people.Air_Velocity_Schedule_Name = self.VEL_SCHEDULE_NAME.format(people.Name)
                people_configured += 1
                
                self.logger.debug(f"Configured people object: {people.Name}")
            
            self.logger.info(f"Configured {people_configured} people objects")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to configure people objects: {e}")
            return idf
    
    def _add_output_variables(self, idf: IDF) -> IDF:
        """
        Adicionar variáveis de saída ao arquivo IDF.
        
        Args:
            idf: Objeto IDF do eppy
            
        Returns:
            IDF: Objeto IDF modificado
        """
        try:
            # Definir variáveis de saída desejadas
            desired_output_variables = [
                "People Occupant Count",
                "Site Outdoor Air Drybulb Temperature",
                "Zone Mean Radiante Temperature",
                "Zone Operative Temperature",
                "Zone Air Temperature",
                "Zone Air Relative Humidity",
                "Zone Thermal Comfort ASHRAE 55 Adaptative Model Temperature",
                "Zone Thermal Comfort Fanger Model PMV",
                "Zone Thermal Comfort Clothing Value",
                "Zone Air CO2 Concentration",
                "Schedule Value",
                "Zone Packaged Terminal Heat Pump Total Heating Energy",
                "Zone Packaged Terminal Heat Pump Total Cooling Energy",
                "Zone Infiltration Air Change Rate"
            ]
            
            # Verificar variáveis já existentes
            existing_variables = {
                output_var.Variable_Name 
                for output_var in idf.idfobjects.get("Output:Variable", [])
            }
            
            # Adicionar variáveis que não existem
            variables_added = 0
            for variable_name in desired_output_variables:
                if variable_name not in existing_variables:
                    idf.newidfobject(
                        "Output:Variable",
                        Key_Value="*",
                        Variable_Name=variable_name,
                        Reporting_Frequency="Timestep"
                    )
                    variables_added += 1
                    self.logger.debug(f"Added output variable: {variable_name}")
            
            # Adicionar variáveis específicas por sala
            for room in self.configs.rooms:
                idf.newidfobject(
                    "Output:Variable",
                    Key_Value=f"DOAS_{room.upper()} OUTDOOR AIR INLET",
                    Variable_Name="System Node Mass Flow Rate",
                    Reporting_Frequency="Timestep"
                )
                variables_added += 1
                self.logger.debug(f"Added room-specific output variable for: {room}")
            
            self.logger.info(f"Added {variables_added} output variables")
            return idf
            
        except Exception as e:
            self.logger.error(f"Failed to add output variables: {e}")
            return idf
    
    def validate_idf(self) -> List[str]:
        """
        Validar arquivo IDF antes do processamento.
        
        Returns:
            List[str]: Lista de erros encontrados
        """
        errors = []
        
        try:
            # Verificar se arquivo existe
            if not os.path.exists(self.configs.idf_path):
                errors.append(f"IDF file not found: {self.configs.idf_path}")
                return errors
            
            # Verificar se arquivo IDD existe
            idd_path = self.PATH_SEP.join([self.configs.energy_path, "Energy+.idd"])
            if not os.path.exists(idd_path):
                errors.append(f"IDD file not found: {idd_path}")
                return errors
            
            # Tentar carregar o arquivo IDF
            try:
                idf = IDF(self.configs.idf_path)
                
                # Verificar se tem objetos essenciais
                if not idf.idfobjects.get("Building"):
                    errors.append("No Building object found in IDF")
                
                if not idf.idfobjects.get("Zone"):
                    errors.append("No Zone objects found in IDF")
                
            except Exception as e:
                errors.append(f"Failed to parse IDF file: {e}")
            
        except Exception as e:
            errors.append(f"Validation error: {e}")
        
        return errors
    
    def get_idf_summary(self) -> Dict[str, Any]:
        """
        Obter resumo do arquivo IDF.
        
        Returns:
            Dict[str, Any]: Informações sobre o arquivo IDF
        """
        try:
            idf = IDF(self.configs.idf_path)
            
            summary = {
                "file_path": self.configs.idf_path,
                "building_count": len(idf.idfobjects.get("Building", [])),
                "zone_count": len(idf.idfobjects.get("Zone", [])),
                "people_count": len(idf.idfobjects.get("People", [])),
                "schedule_constant_count": len(idf.idfobjects.get("Schedule:Constant", [])),
                "output_variable_count": len(idf.idfobjects.get("Output:Variable", [])),
                "schedule_type_limits_count": len(idf.idfobjects.get("ScheduleTypeLimits", []))
            }
            
            # Adicionar informações sobre salas configuradas
            summary["configured_rooms"] = self.configs.rooms
            summary["room_count"] = len(self.configs.rooms)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to get IDF summary: {e}")
            return {"error": str(e)}
