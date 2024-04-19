import math
import logging
from datetime import datetime
import pythermalcomfort
from ladybug_comfort.pmv import predicted_mean_vote

from utils.simulation_config import SimulationConfig

class Conditioner:
    def __init__(self, ep_api, configs: SimulationConfig, ac_on_max_timesteps: int=12):
        self.logger = self._setup_logging()

        self.ep_api = ep_api
        self.configs = configs

        self.handlers_acquired = False

        self.people_count_handler = {}
        self.tdb_handler = None
        self.temp_ar_handler = {}
        self.mrt_handler = {}
        self.hum_rel_handler = {}
        self.temp_op_handler = {}
        self.adaptativo_handler = {}
        self.co2_handler = {}
        self.clo_handler = {}
        self.status_janela_handler = {}
        self.status_vent_handler = {}
        self.vel_handler = {}
        self.status_ac_handler = {}
        self.temp_cool_ac_handler = {}
        self.temp_heat_ac_handler = {}
        self.pmv_handler = {}
        self.temp_op_max_handler = {}
        self.adaptativo_min_handler = {}
        self.adaptativo_max_handler = {}
        self.em_conforto_handler = {}
        self.status_doas_handler = {}

        self.ac_on_counter = 0
        self.ac_on_max_timesteps = ac_on_max_timesteps
        
        self.janela_sem_pessoas_bloqueada = False

        self.periodo_inverno = range(6, 10)

    def _setup_logging(self):
        logger = logging.getLogger(__name__)
        logging.basicConfig(
            filename = f'logs/simulation_{datetime.now().isoformat()}.log',
            format='%(asctime)s %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p'
        )
        return logger

    def __call__(self, state):
        raise NotImplementedError("Method __call__ must be implemented")
    
    def get_best_velocity_with_adaptative(self, temp_op):
        status_janela = 1
        nova_vel = math.ceil(self.get_vel_adap(temp_op) / self.configs.air_speed_delta) * self.configs.air_speed_delta

        if nova_vel > self.configs.max_vel:
            nova_vel = self.configs.max_vel
            status_janela = 0

        return nova_vel, status_janela
        
    def get_best_velocity_with_pmv(self, temp_ar, mrt, vel, hum_rel, clo):
        status_ac = 0
        pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)
        while pmv > self.configs.pmv_upperbound:
            vel = round(vel + self.configs.air_speed_delta, 2)
            if vel > self.configs.max_vel:
                vel = self.configs.max_vel
                status_ac = 1
                break
            pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)

        while pmv < self.configs.pmv_lowerbound:
            vel = round(vel - self.configs.air_speed_delta, 2)
            if vel < 0.0:
                vel = 0.0
                status_ac = 1
                break
            pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)

        return vel, status_ac

    def get_best_temperatures_with_pmv(self, mrt, vel, hum_rel, clo):
        best_cool_temp = self.configs.temp_ac_max
        best_heat_temp = self.configs.temp_ac_min
        
        pmv = self.get_pmv(best_cool_temp, mrt, vel, hum_rel, clo)
        while pmv > self.configs.pmv_upperbound:
            best_cool_temp -= 1.0
            if best_cool_temp <= self.configs.temp_ac_min:
                best_cool_temp = self.configs.temp_ac_min
                break
            pmv = self.get_pmv(best_cool_temp, mrt, vel, hum_rel, clo)

        pmv = self.get_pmv(best_heat_temp, mrt, vel, hum_rel, clo)
        while pmv < self.configs.pmv_lowerbound:
            best_heat_temp += 1.0
            if best_heat_temp >= self.configs.temp_ac_max:
                best_heat_temp = self.configs.temp_ac_max
                break
            pmv = self.get_pmv(best_heat_temp, mrt, vel, hum_rel, clo)

        return best_cool_temp, best_heat_temp

    def get_pmv(self, temp_ar, mrt, vel, rh, clo):
        return predicted_mean_vote(
            ta=temp_ar,
            tr=mrt,
            vel=pythermalcomfort.utilities.v_relative(vel, met=self.configs.met),
            rh=rh,
            met=self.configs.met,
            clo=pythermalcomfort.utilities.clo_dynamic(clo, met=self.configs.met),
            wme=self.configs.wme
        )['pmv']
    
    def is_comfortable(self, temp_op:float, adaptativo:float, temp_op_max:float, pmv:float, status_janela:int, vel:float):
        if adaptativo >= temp_op - self.configs.adaptative_bound and adaptativo <= temp_op + self.configs.adaptative_bound and status_janela == 1 and vel == 0.0:
            return 1
        elif temp_op <= temp_op_max and vel > 0.0 and status_janela == 1:
            return 1
        elif pmv <= self.configs.pmv_upperbound + self.configs.pmv_comfort_bound and pmv >= self.configs.pmv_lowerbound - self.configs.pmv_comfort_bound and status_janela == 0:
            return 1

        return 0
    
    def acquire_handlers(self, state):
        self.tdb_handler = self.ep_api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        if self.tdb_handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Site Outdoor Air Drybulb Temperature da sala {room}")

        for room in self.configs.rooms:
            handler = self.ep_api.exchange.get_variable_handle(state, "People Occupant Count", f"PEOPLE_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador People Occupant Count da sala {room}")
            self.people_count_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air Temperature", room)
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Air Temperature da sala {room}")
            self.temp_ar_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Mean Radiant Temperature", room)
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Mean Radiant Temperature da sala {room}")
            self.mrt_handler.update({ room : handler })

            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air Relative Humidity", room)
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Air Relative Humidity da sala {room}")
            self.hum_rel_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Operative Temperature", room)
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Operative Temperature da sala {room}")
            self.temp_op_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature", f"PEOPLE_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature da sala {room}")
            self.adaptativo_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air CO2 Concentration", f"{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Air CO2 Concentration da sala {room}")
            self.co2_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Thermal Comfort Clothing Value", f"PEOPLE_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador Zone Thermal Comfort Clothing Value da sala {room}")
            self.clo_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"JANELA_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador JANELA da sala {room}")
            self.status_janela_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"VENT_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador VENT da sala {room}")
            self.status_vent_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"VEL_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador VEL da sala {room}")
            self.vel_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"AC_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador AC da sala {room}")
            self.status_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_COOL_AC_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador TEMP_COOL_AC da sala {room}")
            self.temp_cool_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_HEAT_AC_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador TEMP_HEAT_AC da sala {room}")
            self.temp_heat_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"PMV_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador PMV da sala {room}")
            self.pmv_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_OP_MAX_ADAP_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador TEMP_OP_MAX_ADAP da sala {room}")
            self.temp_op_max_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"ADAP_MIN_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador ADAP_MIN da sala {room}")
            self.adaptativo_min_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"ADAP_MAX_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador ADAP_MAX da sala {room}")
            self.adaptativo_max_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"EM_CONFORTO_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador EM_CONFORTO da sala {room}")
            self.em_conforto_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"DOAS_STATUS_{room.upper()}")
            if handler <= 0:
                self.logger.error(f"Não foi possível pegar o tratador DOAS_STATUS da sala {room}")
            self.status_doas_handler.update({ room : handler})
    
    @staticmethod
    def get_temp_max_op(vel):
        return -0.3535 * vel ** 2 + 2.2758 * vel + 24.995
    
    @staticmethod
    def get_vel_adap(temp_op):
        return 0.055 * temp_op ** 2 - 2.331 * temp_op + 23.935 + 0.1
