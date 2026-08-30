from confortimetro.control.base import Conditioner

class ConditionerClosedWindow(Conditioner):
    def room_conditioner(self, state, room):
        (people_count, _, temp_max_adaptativo, temp_min_adaptativo,
         co2, _, temp_ar, _) = self.read_room(state, room, outdoor=False)

        if people_count > 0.0:
            mrt = self.ep_api.exchange.get_variable_value(state, self.mrt_handler[room])
            hum_rel = self.ep_api.exchange.get_variable_value(state, self.hum_rel_handler[room]) # Umidade relativa
            clo = self.ep_api.exchange.get_actuator_value(state, self.clo_handler[room]) # Roupagem

            # Valores iniciais
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
                vel = 0.0
                status_ac = 0

            if not comfort_achieved and status_ac == 0:
                vel, status_ac, clo = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
            elif not comfort_achieved:
                vel, _, clo = self.get_best_velocity_with_pmv(temp_ar, mrt, vel, hum_rel, clo)

            if status_ac == 1:
                # Executar com o modelo PMV
                temp_cool_ac, temp_heat_ac, clo = self.get_best_temperatures_with_pmv(temp_ar, mrt, vel, hum_rel, clo)
                self.ac_on_counter[room] += 1

            status_doas = 0
            if co2 >= self.configs.co2_limit:
                status_doas = 1

            pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)

            # A janela nunca abre neste módulo.
            self.write_room(
                state, room, clo=clo, vel=vel, status_ac=status_ac,
                status_doas=status_doas, temp_cool_ac=temp_cool_ac,
                temp_heat_ac=temp_heat_ac, status_janela=0, temp_op_max=0.0,
                pmv=pmv,
                em_conforto=self.is_comfortable(0.0, 0.0, 0.0, pmv, 0, vel),
            )
        else:
            self.ac_on_counter[room] = 0
            # Desligando tudo se não há ocupação
            self.write_room(state, room, status_janela=0, status_ac=0,
                            status_doas=0, pmv=0, em_conforto=1)

        self.write_adaptative(state, room, temp_min_adaptativo, temp_max_adaptativo)
