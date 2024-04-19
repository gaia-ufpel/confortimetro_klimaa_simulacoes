from modules.conditioner import Conditioner
from utils.simulation_config import SimulationConfig

class ConditionerFixedAcWithoutFan(Conditioner):
    def __init__(self, ep_api, configs: SimulationConfig):
        super().__init__(ep_api, configs)

    def room_conditioner(self, state, room):
        # Pegando todos os valores que são realmente necessários antes
        people_count = self.ep_api.exchange.get_variable_value(state, self.people_count_handler[room]) # Contagem de pessoas na sala
        temp_neutra_adaptativo = self.ep_api.exchange.get_variable_value(state, self.adaptativo_handler[room])
        temp_max_adaptativo = temp_neutra_adaptativo + self.configs.adaptative_bound
        temp_min_adaptativo = temp_neutra_adaptativo - self.configs.adaptative_bound
        co2 = self.ep_api.exchange.get_variable_value(state, self.co2_handler[room])
        temp_op = self.ep_api.exchange.get_variable_value(state, self.temp_op_handler[room])
        temp_ar = self.ep_api.exchange.get_variable_value(state, self.temp_ar_handler[room])
        tdb = self.ep_api.exchange.get_variable_value(state, self.tdb_handler)

        if people_count > 0.0:
            mrt = self.ep_api.exchange.get_variable_value(state, self.mrt_handler[room])
            hum_rel = self.ep_api.exchange.get_variable_value(state, self.hum_rel_handler[room]) # Umidade relativa
            clo = self.ep_api.exchange.get_variable_value(state, self.clo_handler[room]) # Roupagem

            # Valores iniciais
            status_janela = self.ep_api.exchange.get_actuator_value(state, self.status_janela_handler[room])
            status_ac = self.ep_api.exchange.get_actuator_value(state, self.status_ac_handler[room])
            status_doas = 0

            if self.ac_on_counter[room] >= self.ac_on_max_timesteps:
                status_janela = 0
                status_ac = 0
                self.ac_on_counter[room] = 0

            #logging.info(f'data: {self.ep_api.exchange.day_of_month(state)} - temp_ar: {temp_ar} - mrt: {mrt} - vel: {vel} - rh: {hum_rel} - met: {self.met} - clo: {clo} - pmv: {self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)}')

            if tdb <= temp_max_adaptativo and tdb >= temp_ar - self.configs.temp_open_window_bound and status_ac == 0:
                if temp_op <= temp_max_adaptativo and temp_op >= temp_min_adaptativo:
                    status_janela = 1
                else:
                    status_janela = 0
            else:
                status_janela = 0

            pmv = self.get_pmv(temp_ar, mrt, 0.0, hum_rel, clo)

            if status_janela == 0:
                if pmv > self.configs.pmv_upperbound or pmv < self.configs.pmv_lowerbound:
                    status_ac = 1

            if status_ac == 1:    
                self.ac_on_counter[room] += 1
                
            status_doas = 0
            if co2 >= self.configs.co2_limit and status_janela == 0:
                status_doas = 1

            # Mandando para o Energy os valores atualizados
            self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], status_ac)
            if self.status_doas_handler != -1:
                self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], status_doas)
            self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], status_janela)
            self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], pmv)
            em_conforto = self.is_comfortable(temp_op, temp_neutra_adaptativo, pmv, status_janela)
            self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], em_conforto)
        else:
            # Eliminando CO2 da sala
            status_janela = 0
            if temp_op <= temp_min_adaptativo:
                self.janela_sem_pessoas_bloqueada = True

            if (tdb < temp_max_adaptativo and self.ep_api.exchange.month(state) not in self.periodo_inverno and tdb >= temp_ar - self.configs.temp_open_window_bound and temp_op > temp_min_adaptativo):
                if not self.janela_sem_pessoas_bloqueada:
                    status_janela = 1
                elif temp_op >= (temp_min_adaptativo + temp_max_adaptativo) / 2:
                    status_janela = 1
                    self.janela_sem_pessoas_bloqueada = False

            self.ac_on_counter[room] = 0

            # Desligando tudo se não há ocupação
            self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], 0)
            if self.status_doas_handler != -1:
                self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], status_janela)
            self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], 1)

        self.ep_api.exchange.set_actuator_value(state, self.adaptativo_max_handler[room], temp_max_adaptativo)
        self.ep_api.exchange.set_actuator_value(state, self.adaptativo_min_handler[room], temp_min_adaptativo)