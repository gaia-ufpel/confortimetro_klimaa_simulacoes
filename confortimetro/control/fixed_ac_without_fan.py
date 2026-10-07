from confortimetro.control.base import Conditioner
from confortimetro.control.motivos import Motivo

class ConditionerFixedAcWithoutFan(Conditioner):
    def room_conditioner(self, state, room):
        (people_count, temp_neutra_adaptativo, temp_max_adaptativo,
         temp_min_adaptativo, co2, temp_op, temp_ar, tdb) = self.read_room(state, room)

        if people_count > 0.0:
            mrt = self.ep_api.exchange.get_variable_value(state, self.mrt_handler[room])
            hum_rel = self.ep_api.exchange.get_variable_value(state, self.hum_rel_handler[room]) # Umidade relativa
            clo = self.ep_api.exchange.get_actuator_value(state, self.clo_handler[room]) # Roupagem

            # Valores iniciais
            status_janela = self.ep_api.exchange.get_actuator_value(state, self.status_janela_handler[room])
            status_ac = self.ep_api.exchange.get_actuator_value(state, self.status_ac_handler[room])

            motivo = Motivo.OCUPADA

            clo, comfort_achieved = self.get_best_clo_for_comfort(temp_ar, mrt, 0.0, hum_rel, clo)
            if comfort_achieved:
                motivo |= Motivo.CONFORTO_SO_COM_CLO
                status_ac = 0
                self.ac_on_counter[room] = 0

            if self.ac_timed_out(room):
                motivo |= Motivo.AC_TEMPO_MAXIMO
                status_janela = 0
                status_ac = 0

            status_janela = self.window_by_adaptative(
                tdb, temp_ar, temp_op, temp_min_adaptativo, temp_max_adaptativo,
                status_ac)
            motivo |= self.window_by_adaptative_motivo(
                tdb, temp_ar, temp_op, temp_min_adaptativo, temp_max_adaptativo,
                status_ac, status_janela)

            pmv = self.get_pmv(temp_ar, mrt, 0.0, hum_rel, clo)

            ac_antes = status_ac
            if status_janela == 0:
                if not comfort_achieved and (pmv > self.configs.pmv_upperbound or pmv < self.configs.pmv_lowerbound):
                    status_ac = 1

            if status_ac == 1:
                self.ac_on_counter[room] += 1
                motivo |= Motivo.AC_MANTIDO if ac_antes == 1 else Motivo.AC_LIGADO_POR_PMV

            status_doas = 0
            if co2 >= self.configs.co2_limit and status_janela == 0:
                motivo |= Motivo.DOAS_POR_CO2
                status_doas = 1

            # O AC tem setpoint fixo no IDF: nada de vel/temperaturas aqui.
            self.write_room(
                state, room, clo=clo, status_ac=status_ac, status_doas=status_doas,
                status_janela=status_janela, pmv=pmv, equipment=False, motivo=motivo,
                em_conforto=self.is_comfortable(temp_op, temp_neutra_adaptativo,
                                                0.0, pmv, status_janela, 0.0),
            )
        else:
            # Eliminando CO2 da sala e desligando tudo
            status_janela = self.window_without_people(
                state, room, tdb, temp_ar, temp_op, temp_neutra_adaptativo,
                temp_min_adaptativo, temp_max_adaptativo)
            motivo = self.window_without_people_motivo(
                state, room, tdb, temp_ar, temp_op, temp_neutra_adaptativo,
                temp_max_adaptativo, status_janela)
            self.ac_on_counter[room] = 0
            self.write_room(state, room, status_janela=status_janela, status_ac=0,
                            status_doas=0, pmv=0, em_conforto=1, motivo=motivo, equipment=False)

        self.write_adaptative(state, room, temp_min_adaptativo, temp_max_adaptativo)
