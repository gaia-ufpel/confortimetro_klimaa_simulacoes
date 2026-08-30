from confortimetro.control.base import Conditioner

class ConditionerComplete(Conditioner):
    def room_conditioner(self, state, room):
        (people_count, temp_neutra_adaptativo, temp_max_adaptativo,
         temp_min_adaptativo, co2, temp_op, temp_ar, tdb) = self.read_room(state, room)

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
            temp_cool_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_cool_ac_handler[room])
            temp_heat_ac = self.ep_api.exchange.get_actuator_value(state, self.temp_heat_ac_handler[room])

            clo, comfort_achieved = self.get_best_clo_for_comfort(temp_ar, mrt, vel, hum_rel, clo)
            if comfort_achieved:
                vel = 0.0
                status_ac = 0
                self.ac_on_counter[room] = 0

            if self.ac_timed_out(room):
                # Desligando o ar condicionado se passar do limite de tempo
                status_janela = 0
                vel = 0.0
                status_ac = 0

            if self.can_open_window(tdb, temp_ar, temp_max_adaptativo, status_ac):
                # Abrindo a janela se a temperatura externa estiver entre os limites e o ar condicionado estiver desligado
                if temp_max_adaptativo >= temp_op >= temp_min_adaptativo:
                    # Se a temperatura operativa estiver entre os limites, a janela é aberta
                    status_janela = 1
                    vel = 0.0
                elif temp_op > temp_max_adaptativo and 25.0 <= temp_op <= 27.2:
                    # Se a temperatura operativa estiver acima de 25 graus e a temperatura externa estiver entre os limites, a janela é aberta
                    if comfort_achieved:
                        status_janela = 1
                        vel = 0.0
                    else:
                        vel, status_janela = self.get_best_velocity_with_adaptative(temp_op)
                    temp_op_max = self.get_temp_max_op(vel)
                else:
                    # Se a temperatura operativa estiver abaixo de 25 graus, a janela é fechada
                    status_janela = 0
            else:
                # Fechando a janela se a temperatura externa estiver fora dos limites
                status_janela = 0

            if status_janela == 0 and not comfort_achieved:
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

            self.write_room(
                state, room, clo=clo, vel=vel, status_ac=status_ac,
                status_doas=status_doas, temp_cool_ac=temp_cool_ac,
                temp_heat_ac=temp_heat_ac, status_janela=status_janela,
                temp_op_max=temp_op_max, pmv=pmv,
                em_conforto=self.is_comfortable(temp_op, temp_neutra_adaptativo,
                                                temp_op_max, pmv, status_janela, vel),
            )
        else:
            # Caso não haja pessoas na sala: eliminando CO2 e desligando tudo
            status_janela = self.window_without_people(
                state, room, tdb, temp_ar, temp_op, temp_neutra_adaptativo,
                temp_min_adaptativo, temp_max_adaptativo)
            self.ac_on_counter[room] = 0
            self.write_room(state, room, status_janela=status_janela, status_ac=0,
                            status_doas=0, pmv=0, em_conforto=1)

        self.write_adaptative(state, room, temp_min_adaptativo, temp_max_adaptativo)
