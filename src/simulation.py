import sys
import os
import platform
from importlib import import_module
from eppy.modeleditor import IDF

from modules import MODULES_MAPPER
import utils
from utils.simulation_config import SimulationConfig
from utils.module_type import ModuleType

EnergyPlusAPI = None

PATH_SEP = "/"

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

        self.conditioner = MODULES_MAPPER[self.configs.module_type](ep_api=self.ep_api, configs=configs)

    def run(self):
        # Modifying IDF file
        self._modify_idf()

        # Expanding objects and creating expanded.idf
        if platform.system() == "Windows":
            os.system(f'cd \"{self.configs.input_path}\" && cp \"{self.configs.idf_filename}\" in.idf && \"{PATH_SEP.join([self.configs.energy_path, EXPAND_OBJECTS_APP])}\"')
        else:
            os.system(f'cd \"{self.configs.input_path}\" ; cp \"{self.configs.idf_filename}\" in.idf ; \"{PATH_SEP.join([self.configs.energy_path, EXPAND_OBJECTS_APP])}\"')

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

        print("Simulação finalizada!")
        utils.summary_rooms_results_from_eso(self.configs.output_path, self.configs.rooms)
        print("Resultados extraidos com sucesso!")
        utils.get_stats_from_simulation(self.configs.output_path, self.configs.rooms)
        print("Estatísticas extraidas com sucesso!")

    def _modify_idf(self):
        IDF.setiddname(PATH_SEP.join([self.configs.energy_path, "Energy+.idd"]))
        idf = IDF(self.configs.idf_path)
        
        idf = self._modify_schedules_idf(idf)
        #idf = self._add_output_variables_idf(idf)

        idf.save(self.configs.idf_path)

    def _modify_schedules_idf(self, idf: IDF):
        for schedule in idf.idfobjects["Schedule:Constant"]:
            if schedule.Name == MET_SCHEDULE_NAME:
                schedule.Schedule_Type_Limits_Name = "Any Number"
                schedule.Hourly_Value = self.configs.met_as_watts
            elif schedule.Name == WME_SCHEDULE_NAME:
                schedule.Schedule_Type_Limits_Name = "Any Number"
                schedule.Hourly_Value = self.configs.wme
            elif self.configs.module_type == ModuleType.FIXED_AC_WITHOUT_VENT:
                if TEMP_COOL_AC_SCHEDULE_NAME.format("") in schedule.Name:
                    schedule.Hourly_Value = self.configs.temp_ac_max
                elif TEMP_HEAT_AC_SCHEDULE_NAME.format("") in schedule.Name:
                    schedule.Hourly_Value = self.configs.temp_ac_min

        return idf

    def _add_schedules_idf(self, idf: IDF):
        idf.newidfobject("ScheduleTypeLimits", Name="On/Off", Lower_Limit_Value=0, Upper_Limit_Value=1, Numeric_Type="DISCRETE", Unit_Type="Dimensionless")
        idf.newidfobject("ScheduleTypeLimits", Name="Any Number")
        idf.newidfobject("Schedule:Constant", Name=OUTDOOR_CO2_SCHEDULE_NAME, Schedule_Type_Limits_Name="Any Number", Hourly_Value=400)

        for room in self.configs.rooms:
            idf.newidfobject("Schedule:Constant", Name=JANELA_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=VENT_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=VEL_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=AC_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=DOAS_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=TEMP_COOL_AC_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.temp_ac_max)
            idf.newidfobject("Schedule:Constant", Name=TEMP_HEAT_AC_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.temp_ac_min)
            idf.newidfobject("Schedule:Constant", Name=PMV_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=TEMP_OP_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=ADAP_MIN_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=ADAP_MAX_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="Any Number", Hourly_Value=0)
            idf.newidfobject("Schedule:Constant", Name=EM_CONFORTO_SCHEDULE_NAME.format(room), Schedule_Type_Limits_Name="On/Off", Hourly_Value=0)

        idf.newidfobject("Schedule:Constant", Name=MET_SCHEDULE_NAME, Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.met_as_watts)
        idf.newidfobject("Schedule:Constant", Name=WME_SCHEDULE_NAME, Schedule_Type_Limits_Name="Any Number", Hourly_Value=self.configs.wme)

        return idf

    def _configure_people_object_idf(self, idf: IDF):
        for people in idf.idfobjects["People"]:
            people.Activity_Level_Schedule_Name = MET_SCHEDULE_NAME
            people.Work_Eff_Name = WME_SCHEDULE_NAME
            people.Air_Velocity_Schedule_Name = VEL_SCHEDULE_NAME.format(people.Name)

        return idf

    def _add_output_variables_idf(self, idf: IDF):
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="People Occupant Count", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Site Outdoor Air Drybulb Temperature", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Mean Radiante Temperature", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Operative Temperature", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Air Temperature", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Air Relative Humidity", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Thermal Comfort ASHRAE 55 Adaptative Model Temperature", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Thermal Comfort Fanger Model PMV", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Thermal Comfort Clothing Value", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Air CO2 Concentration", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Schedule Value", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Packaged Terminal Heat Pump Total Heating Energy", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Packaged Terminal Heat Pump Total Cooling Energy", Reporting_Frequency="Timestep")
        idf.newidfobject("Output:Variable", Key_Value="*", Variable_Name="Zone Infiltration Air Change Rate", Reporting_Frequency="Timestep")

        for room in self.configs.rooms:
            idf.newidfobject("Output:Variable", Key_Value=f"DOAS_{room.upper()} OUTDOOR AIR INLET", Variable_Name="System Node Mass Flow Rate", Reporting_Frequency="Timestep")
            
        return idf
        
