from src.modules.conditioner import Conditioner
from src.utils.simulation_config import SimulationConfig

class ConditionerComplete(Conditioner):
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
            # Caso haja pessoas na sala
            mrt = self.ep_api.exchange.get_variable_value(state, self.mrt_handler[room])
            hum_rel = self.ep_api.exchange.get_variable_value(state, self.hum_rel_handler[room]) # Umidade relativa
            clo = self.ep_api.exchange.get_actuator_value(state, self.clo_handler[room]) # Roupagem

            temp_op_max = self.ep_api.exchange.get_actuator_value(state, self.temp_op_max_handler[room])

            # Valores iniciais
            status_janela = self.ep_api.exchange.get_actuator_value(state, self.status_janela_handler[room])
            vel = self.ep_api.exchange.get_actuator_value(state, self.vel_handler[room])
            status_ac = self.ep_api.exchange.get_actuator_value(state, self.status_ac_handler[room])
            status_doas = 0
            temp_cool_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_cool_ac_handler[room])
            temp_heat_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_heat_ac_handler[room])

            if self.ac_on_counter[room] >= self.ac_on_max_timesteps:
                # Desligando o ar condicionado se passar do limite de tempo
                status_janela = 0
                vel = 0.0
                status_ac = 0
                self.ac_on_counter[room] = 0

            if tdb <= temp_max_adaptativo and tdb >= temp_ar - self.configs.temp_open_window_bound and status_ac == 0:
                # Abrindo a janela se a temperatura externa estiver entre os limites e o ar condicionado estiver desligado
                if temp_max_adaptativo >= temp_op >= temp_min_adaptativo:
                    # Se a temperatura operativa estiver entre os limites, a janela é aberta
                    status_janela = 1
                    vel = 0.0
                elif temp_op > temp_max_adaptativo and 25.0 <= temp_op <= 27.2:
                    # Se a temperatura operativa estiver acima de 25 graus e a temperatura externa estiver entre os limites, a janela é aberta
                    vel, status_janela = self.get_best_velocity_with_adaptative(temp_op)
                    temp_op_max = self.get_temp_max_op(vel)
                else:
                    # Se a temperatura operativa estiver abaixo de 25 graus, a janela é fechada
                    status_janela = 0
            else:
                # Fechando a janela se a temperatura externa estiver fora dos limites
                status_janela = 0
            
            if status_janela == 0:
                # Se a janela estiver fechada, o ar condicionado é ligado
                if status_ac == 0:
                    # Se o ar condicionado estiver desligado, a velocidade é ajustada
                    vel, status_ac, clo = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
                else:
                    # Se o ar condicionado estiver ligado, a velocidade é ajustada sem alterar o status
                    vel, _, clo = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
            
            if status_ac == 1:
                # Se o ar condicionado estiver ligado, o modelo PMV é executado
                temp_cool_ac, temp_heat_ac, clo = self.get_best_temperatures_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
                self.ac_on_counter[room] += 1
                
            status_doas = 0
            if co2 >= self.configs.co2_limit and status_janela == 0:
                # Se o CO2 estiver acima do limite e a janela estiver fechada, o DOAS é ligado
                status_doas = 1

            pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)

            if room == 'RECEPCAO':
                print(f'room: {room} - data: {self.ep_api.exchange.day_of_month(state)} - temp_ar: {temp_ar} - mrt: {mrt} - vel: {vel} - ac_min: {temp_cool_ac} - ac_max: {temp_heat_ac} - rh: {hum_rel} - clo: {clo} - pmv: {pmv}')

            # Mandando para o Energy os valores atualizados
            self.ep_api.exchange.set_actuator_value(state, self.clo_handler[room], clo)
            self.ep_api.exchange.set_actuator_value(state, self.status_vent_handler[room], 1 if vel > 0 else 0)
            self.ep_api.exchange.set_actuator_value(state, self.vel_handler[room], vel)
            self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], status_ac)
            if self.status_doas_handler != -1:
                self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], status_doas)
            self.ep_api.exchange.set_actuator_value(state, self.temp_cool_ac_handler[room], temp_cool_ac)
            self.ep_api.exchange.set_actuator_value(state, self.temp_heat_ac_handler[room], temp_heat_ac)
            self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], status_janela)
            self.ep_api.exchange.set_actuator_value(state, self.temp_op_max_handler[room], temp_op_max)
            self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], pmv)
            em_conforto = self.is_comfortable(temp_op, temp_neutra_adaptativo, temp_op_max, pmv, status_janela, vel)
            self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], em_conforto)
        else:
            # Caso não haja pessoas na sala
            # Eliminando CO2 da sala
            status_janela = 0
            if temp_op <= temp_min_adaptativo:
                # Se a temperatura operativa estiver abaixo do limite mínimo, a janela é fechada
                self.janela_sem_pessoas_bloqueada = True

            if (tdb < temp_max_adaptativo and self.ep_api.exchange.month(state) not in self.periodo_inverno and tdb >= temp_ar - self.configs.temp_open_window_bound and temp_op > temp_min_adaptativo):
                # Abrindo a janela se a temperatura externa estiver entre os limites e a temperatura operativa estiver acima do mínimo
                if not self.janela_sem_pessoas_bloqueada:
                    # Se a janela não estiver bloqueada, ela é aberta
                    status_janela = 1
                elif temp_op >= temp_neutra_adaptativo:
                    # Se a janela estiver bloqueada e a temperatura operativa estiver acima da neutra, a janela é aberta
                    status_janela = 1
                    self.janela_sem_pessoas_bloqueada = False

            self.ac_on_counter[room] = 0

            if room == 'RECEPCAO':
                print(f'room: {room} - data: {self.ep_api.exchange.day_of_month(state)} - temp_ar: {temp_ar}')

            # Desligando tudo se não há ocupação
            self.ep_api.exchange.set_actuator_value(state, self.status_vent_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.vel_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.status_ac_handler[room], 0)
            if self.status_doas_handler != -1:
                self.ep_api.exchange.set_actuator_value(state, self.status_doas_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.temp_cool_ac_handler[room], self.configs.temp_ac_max)
            self.ep_api.exchange.set_actuator_value(state, self.temp_heat_ac_handler[room], self.configs.temp_ac_min)
            self.ep_api.exchange.set_actuator_value(state, self.pmv_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.status_janela_handler[room], status_janela)
            self.ep_api.exchange.set_actuator_value(state, self.temp_op_max_handler[room], 0)
            self.ep_api.exchange.set_actuator_value(state, self.em_conforto_handler[room], 1)

        self.ep_api.exchange.set_actuator_value(state, self.adaptativo_max_handler[room], temp_max_adaptativo)
        self.ep_api.exchange.set_actuator_value(state, self.adaptativo_min_handler[room], temp_min_adaptativo)