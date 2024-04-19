from modules.conditioner import Conditioner
from utils.simulation_config import SimulationConfig

class ConditionerClosedWindow(Conditioner):
    def __init__(self, ep_api, configs: SimulationConfig):
        super().__init__(ep_api, configs)

    def __call__(self, state):
        if self.ep_api.exchange.warmup_flag(state):
            return
        if not self.ep_api.exchange.api_data_fully_ready(state):
            return
        
        # Pegando todos os handlers
        if not self.handlers_acquired:
            self.acquire_handlers(state)
            self.handlers_acquired = True
            
        for room in self.configs.rooms:
            # Pegando todos os valores que são realmente necessários antes
            people_count = self.ep_api.exchange.get_variable_value(state, self.people_count_handler[room]) # Contagem de pessoas na sala
            temp_neutra_adaptativo = self.ep_api.exchange.get_variable_value(state, self.adaptativo_handler[room])
            temp_max_adaptativo = temp_neutra_adaptativo + self.configs.adaptative_bound
            temp_min_adaptativo = temp_neutra_adaptativo - self.configs.adaptative_bound
            co2 = self.ep_api.exchange.get_variable_value(state, self.co2_handler[room])
            temp_ar = self.ep_api.exchange.get_variable_value(state, self.temp_ar_handler[room])

            if people_count > 0.0:
                mrt = self.ep_api.exchange.get_variable_value(state, self.mrt_handler[room])
                hum_rel = self.ep_api.exchange.get_variable_value(state, self.hum_rel_handler[room]) # Umidade relativa
                clo = self.ep_api.exchange.get_variable_value(state, self.clo_handler[room]) # Roupagem

                # Valores iniciais
                vel = self.ep_api.exchange.get_actuator_value(state, self.vel_handler[room])
                status_ac = self.ep_api.exchange.get_actuator_value(state, self.status_ac_handler[room])
                status_doas = 0
                temp_cool_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_cool_ac_handler[room])
                temp_heat_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_heat_ac_handler[room])

                if self.ac_on_counter >= self.ac_on_max_timesteps:
                    status_ac = 0
                    self.ac_on_counter = 0

                if status_ac == 0:
                    vel, status_ac = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
                else:
                    vel, _ = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
                
                if status_ac == 1:
                    # Executar com o modelo PMV
                    temp_cool_ac, temp_heat_ac = self.get_best_temperatures_with_pmv(mrt, vel, hum_rel, clo)
                    self.ac_on_counter += 1
                    
                status_doas = 0
                if co2 >= self.configs.co2_limit:
                    status_doas = 1

                pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)

                #logging.info(f'data: {self.ep_api.exchange.day_of_month(state)} - temp_ar: {temp_ar} - mrt: {mrt} - vel: {vel} - rh: {hum_rel} - met: {self.met} - clo: {clo} - pmv: {self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)}')

                # Mandando para o Energy os valores atualizados
                self.ep_api.exchange.set_actuator_value(state, self.status_vent_handler[room], 1 if vel > 0 else 0)
                self.ep_api.exchange.set_actuator_value(state, self.vel_handler[room], vel)
                self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], status_ac)
                if self.status_doas_handler != -1:
                    self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], status_doas)
                self.ep_api.exchange.set_actuator_value(state, self.temp_cool_ac_handler[room], temp_cool_ac)
                self.ep_api.exchange.set_actuator_value(state, self.temp_heat_ac_handler[room], temp_heat_ac)
                self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.temp_op_max_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], pmv)
                em_conforto = self.is_comfortable(pmv)
                self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], em_conforto)
            else:
                self.ac_on_counter = 0

                # Desligando tudo se não há ocupação
                self.ep_api.exchange.set_actuator_value(state, self.status_vent_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.vel_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], 0)
                if self.status_doas_handler != -1:
                    self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.temp_cool_ac_handler[room], self.configs.temp_ac_max)
                self.ep_api.exchange.set_actuator_value(state, self.temp_heat_ac_handler[room], self.configs.temp_ac_min)
                self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.temp_op_max_handler[room], 0)
                self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], 1)

            self.ep_api.exchange.set_actuator_value(state, self.adaptativo_max_handler[room], temp_max_adaptativo)
            self.ep_api.exchange.set_actuator_value(state, self.adaptativo_min_handler[room], temp_min_adaptativo)