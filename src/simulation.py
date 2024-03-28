import sys
import os
import platform
from importlib import import_module
from eppy.modeleditor import IDF

from modules import MODULES_MAPPER
import utils
from utils.simulation_config import SimulationConfig

EnergyPlusAPI = None

PATH_SEP = "/"

MET_SCHEDULE_NAME = "METABOLISMO"
WME_SCHEDULE_NAME = "WORK_EF"

EXPAND_OBJECTS_APP = "ExpandObjects"
TO_CSV_APP = "runreadvars"

if platform.system() == "Windows":
    EXPAND_OBJECTS_APP = "ExpandObjects.exe"
    TO_CSV_APP = "PostProcess/ReadVarsESO.exe"

class Simulation:
    def __init__(self, configs: SimulationConfig):
        self.configs = configs

        sys.path.append(self.configs.energy_path)
        EnergyPlusAPI = import_module("pyenergyplus.api").EnergyPlusAPI

        self.ep_api = EnergyPlusAPI()
        self.state = self.ep_api.state_manager.new_state()

        self.conditioner = MODULES_MAPPER[self.configs.module_type](ep_api=self.ep_api, configs=SimulationConfig(**self.configs.__dict__))

    def run(self):
        # Modifying IDF file
        self._modify_idf()

        # Expanding objects and creating expanded.idf
        if platform.system() == "Windows":
            os.system(f'cd \"{self.configs.input_path}\" && cp \"{self.configs.idf_filename}\" in.idf && \"{os.path.join(self.configs.energy_path, EXPAND_OBJECTS_APP)}\"')
        else:
            os.system(f'cd \"{self.configs.input_path}\" ; cp \"{self.configs.idf_filename}\" in.idf ; \"{os.path.join(self.configs.energy_path, EXPAND_OBJECTS_APP)}\"')

        # Moving expanded.idf to output folder
        os.rename(PATH_SEP.join([self.configs.input_path, "expanded.idf"]), self.configs.expanded_idf_path)
        os.makedirs(self.configs.output_path, exist_ok=True)
        self.configs.to_json(PATH_SEP.join([self.configs.output_path, "configs.json"]))

        # Running simulation
        self.ep_api.runtime.callback_begin_zone_timestep_after_init_heat_balance(self.state, self.conditioner)
        self.ep_api.runtime.run_energyplus(self.state,
            ['--weather', self.configs.epw_path, '--output-directory', self.configs.output_path, self.configs.expanded_idf_path]
        )
        self.ep_api.state_manager.reset_state(self.state)

        # Parsing results to CSV
        if platform.system() == "Windows":
            os.system(f"cd \"{self.configs.output_path}\" && {PATH_SEP.join([self.configs.energy_path, TO_CSV_APP])}")
        else:
            os.system(f"cd \"{self.configs.output_path}\" ; {PATH_SEP.join([self.configs.energy_path, TO_CSV_APP])} eplusout.eso")

        utils.summary_rooms_results_from_eso(self.configs.output_path, self.configs.rooms)
        utils.get_stats_from_simulation(self.configs.output_path, self.configs.rooms)

    def _modify_idf(self):
        IDF.setiddname(os.path.join(self.configs.energy_path, "Energy+.idd"))
        idf = IDF(self.configs.idf_path)
        
        idf = self._modify_schedules_idf(idf)

        idf.save(self.configs.idf_path)

    def _modify_schedules_idf(self, idf: IDF):
        for schedule in idf.idfobjects["Schedule:Constant"]:
            if schedule.Name == MET_SCHEDULE_NAME:
                schedule.Schedule_Type_Limits_Name = "Any Number"
                schedule.Hourly_Value = self.configs.met_as_watts
            elif schedule.Name == WME_SCHEDULE_NAME:
                schedule.Schedule_Type_Limits_Name = "Any Number"
                schedule.Hourly_Value = self.configs.wme

        return idf

    def _add_schedules_idf(self, idf: IDF):
        idf.newidfobject("ScheduleTypeLimits", Name="Any Number", Lower_Limit_Value=-1000000, Upper_Limit_Value=1000000, Numeric_Type="CONTINUOUS", Unit_Type="Dimensionless")
        idf.newidfobject("Schedule:Constant", Name=MET_SCHEDULE_NAME, Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.met_as_watts)
        idf.newidfobject("Schedule:Constant", Name=WME_SCHEDULE_NAME, Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.wme)

        return idf

    def _configure_zones_idf(self, idf: IDF):
        for zone in idf.idfobjects["Zone"]:
            zone.People_Name = MET_SCHEDULE_NAME
            zone.Work_Eff_Name = WME_SCHEDULE_NAME

        return idf

    def _add_output_variables_idf(self, idf: IDF):
        pass