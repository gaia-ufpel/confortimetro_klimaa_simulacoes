import math
import logging
from ctypes import c_void_p
from functools import lru_cache

import pythermalcomfort
from ladybug_comfort.pmv import predicted_mean_vote_no_set

from typing import Optional

from confortimetro.config import SimulationConfig


# predicted_mean_vote_no_set dá o mesmo PMV de predicted_mean_vote, mas só roda o
# modelo Pierce SET quando vel > 0.1 m/s (~500x mais rápido em ar parado).
# O cache existe porque o controlador repete as mesmas combinações várias vezes
# por timestep (varredura de CLO, de velocidade e o PMV final).
@lru_cache(maxsize=100_000)
def _pmv(temp_ar, mrt, vel, rh, met, clo, wme):
    return predicted_mean_vote_no_set(
        ta=temp_ar,
        tr=mrt,
        vel=_v_relative(vel, met),
        rh=rh,
        met=met,
        clo=_clo_dynamic(clo, met),
        wme=wme,
    )['pmv']


@lru_cache(maxsize=1024)
def _v_relative(vel, met):
    return pythermalcomfort.utilities.v_relative(vel, met=met)


@lru_cache(maxsize=1024)
def _clo_dynamic(clo, met):
    return pythermalcomfort.utilities.clo_dynamic(clo, met=met)

def request_stop(ep_api, state):
    """Pede ao EnergyPlus que encerre a execução atual."""
    stop = getattr(ep_api.runtime, "stop_simulation", None)
    if stop:
        stop(state)
        return

    # EnergyPlus 9.4 exporta stopSimulation mas não gera o wrapper Python.
    stop = ep_api.runtime.api.stopSimulation
    stop.argtypes = [c_void_p]
    stop.restype = None
    stop(state)


class Conditioner:
    # Grade de CLO, calculada uma vez no primeiro uso.
    _clo_values = None

    def __init__(self, ep_api, configs: SimulationConfig, ac_on_max_timesteps: int=12):
        self.logger = logging.getLogger(__name__)

        self.ep_api = ep_api
        self.configs = configs

        self.handlers_acquired = False

        self.tdb_handler = None
        self.people_count_handler = {}
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

        self.ac_on_counter: dict[str, int] = {room : 0 for room in self.configs.rooms}
        self.ac_on_max_timesteps: int = ac_on_max_timesteps
        
        self.janela_sem_pessoas_bloqueada = False

        self.periodo_inverno = range(6, 10)

        # Exceções levantadas dentro do callback são engolidas pelo ctypes
        # (o EnergyPlus seguiria com os atuadores congelados). Guardamos a
        # primeira aqui e o Simulation a relança depois do run.
        self.error: Optional[BaseException] = None

    def __call__(self, state):
        if self.error is not None:
            return
        try:
            self._step(state)
        except BaseException as error:
            # Sem este except a exceção morre no ctypes e a simulação continua
            # em silêncio com os atuadores parados no último valor.
            self.error = error
            self.logger.exception("Erro no condicionador; abortando a simulação")
            request_stop(self.ep_api, state)

    def _step(self, state):
        if self.ep_api.exchange.warmup_flag(state):
            return
        if not self.ep_api.exchange.api_data_fully_ready(state):
            return
        
        # Pegando todos os handlers
        if not self.handlers_acquired:
            self.acquire_handlers(state)
            self.handlers_acquired = True

        for room in self.configs.rooms:
            self.room_conditioner(state, room)
    
    def room_conditioner(self, state, room):
        raise NotImplementedError("Method room_conditioner must be implemented!")

    def read_room(self, state, room, outdoor=True):
        """Leitura de início de timestep, comum a todos os módulos.

        Devolve `(people_count, temp_neutra, temp_max, temp_min, co2, temp_op,
        temp_ar, tdb)` — o adaptativo já somado/subtraído da banda.
        `outdoor=False` para quem decide sem operativa nem externa (janela
        sempre fechada): esses dois voltam `None` e nem são lidos."""
        get = self.ep_api.exchange.get_variable_value
        temp_neutra = get(state, self.adaptativo_handler[room])
        return (
            get(state, self.people_count_handler[room]),
            temp_neutra,
            temp_neutra + self.configs.adaptative_bound,
            temp_neutra - self.configs.adaptative_bound,
            get(state, self.co2_handler[room]),
            get(state, self.temp_op_handler[room]) if outdoor else None,
            get(state, self.temp_ar_handler[room]),
            get(state, self.tdb_handler) if outdoor else None,
        )

    def ac_timed_out(self, room) -> bool:
        """Verdadeiro (e zera o contador) se o AC passou do tempo máximo ligado."""
        if self.ac_on_counter[room] < self.ac_on_max_timesteps:
            return False
        self.ac_on_counter[room] = 0
        return True

    def can_open_window(self, tdb, temp_ar, temp_max_adaptativo, status_ac) -> bool:
        """Externa dentro da faixa e AC desligado — pré-requisito para abrir."""
        return (tdb <= temp_max_adaptativo
                and tdb >= temp_ar - self.configs.temp_open_window_bound
                and status_ac == 0)

    def window_by_adaptative(self, tdb, temp_ar, temp_op, temp_min_adaptativo,
                             temp_max_adaptativo, status_ac) -> int:
        """Janela aberta só quando a operativa também está dentro do adaptativo."""
        if not self.can_open_window(tdb, temp_ar, temp_max_adaptativo, status_ac):
            return 0
        return 1 if temp_min_adaptativo <= temp_op <= temp_max_adaptativo else 0

    def window_without_people(self, state, room, tdb, temp_ar, temp_op,
                              temp_neutra_adaptativo, temp_min_adaptativo,
                              temp_max_adaptativo) -> int:
        """Janela na sala vazia: abre para eliminar CO2, mas trava depois de
        esfriar demais e só destrava quando a operativa volta à neutra."""
        if temp_op <= temp_min_adaptativo:
            self.janela_sem_pessoas_bloqueada = True

        if not (tdb < temp_max_adaptativo
                and self.ep_api.exchange.month(state) not in self.periodo_inverno
                and tdb >= temp_ar - self.configs.temp_open_window_bound
                and temp_op > temp_min_adaptativo):
            return 0

        if not self.janela_sem_pessoas_bloqueada:
            return 1
        if temp_op >= temp_neutra_adaptativo:
            self.janela_sem_pessoas_bloqueada = False
            return 1
        return 0

    def write_room(self, state, room, *, status_janela, status_ac, status_doas,
                   pmv, em_conforto, clo=None, vel=0.0, temp_cool_ac=None,
                   temp_heat_ac=None, temp_op_max=0.0, equipment=True):
        """Devolve ao EnergyPlus o estado decidido no timestep.

        `equipment=False` para os módulos sem ventilador e com AC de setpoint
        fixo: escrever vel/temperaturas do AC ali sobrescreveria o que o IDF
        já fixou. `clo=None` deixa a roupagem como está (sala vazia)."""
        set_value = self.ep_api.exchange.set_actuator_value
        if clo is not None:
            set_value(state, self.clo_handler[room], clo)
        set_value(state, self.status_ac_handler[room], status_ac)
        set_value(state, self.status_doas_handler[room], status_doas)
        set_value(state, self.status_janela_handler[room], status_janela)
        set_value(state, self.pmv_handler[room], pmv)
        set_value(state, self.em_conforto_handler[room], em_conforto)
        if equipment:
            set_value(state, self.status_vent_handler[room], 1 if vel > 0 else 0)
            set_value(state, self.vel_handler[room], vel)
            set_value(state, self.temp_cool_ac_handler[room],
                      self.configs.temp_ac_max if temp_cool_ac is None else temp_cool_ac)
            set_value(state, self.temp_heat_ac_handler[room],
                      self.configs.temp_ac_min if temp_heat_ac is None else temp_heat_ac)
            set_value(state, self.temp_op_max_handler[room], temp_op_max)

    def write_adaptative(self, state, room, temp_min_adaptativo, temp_max_adaptativo):
        """Limites do adaptativo, escritos no fim de todo timestep."""
        self.ep_api.exchange.set_actuator_value(
            state, self.adaptativo_max_handler[room], temp_max_adaptativo)
        self.ep_api.exchange.set_actuator_value(
            state, self.adaptativo_min_handler[room], temp_min_adaptativo)

    def get_best_velocity_with_adaptative(self, temp_op) -> tuple[float, int]:
        status_janela = 1
        nova_vel = math.ceil(self.get_vel_adap(temp_op) / self.configs.air_speed_delta) * self.configs.air_speed_delta

        if nova_vel > self.configs.max_vel:
            nova_vel = self.configs.max_vel
            status_janela = 0

        return nova_vel, status_janela
    
    def _clo_priority(self) -> bool:
        return getattr(self.configs, "clo_priority", True)

    def _step_clo(self, temp_ar, mrt, vel, hum_rel, clo) -> float:
        """Ajuste antigo do CLO: um passo na direção do conforto, sem varredura."""
        pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, clo)
        if pmv > self.configs.pmv_upperbound:
            return max(round(clo - self.configs.clo_delta, 2), self.configs.clo_min)
        if pmv < self.configs.pmv_lowerbound:
            return min(round(clo + self.configs.clo_delta, 2), self.configs.clo_max)
        return clo

    def get_best_clo_for_comfort(self, temp_ar, mrt, vel, hum_rel, clo) -> tuple[float, bool]:
        """Escolhe o CLO configurado cujo PMV fica mais próximo de zero."""
        if not self._clo_priority():
            # Modo antigo: o CLO só é ajustado junto com os equipamentos.
            return clo, False
        if self.configs.clo_delta <= 0:
            raise ValueError("clo_delta deve ser maior que zero")
        if self.configs.clo_min > self.configs.clo_max:
            raise ValueError("clo_min não pode ser maior que clo_max")

        if self._clo_values is None:
            values = []
            test_clo = self.configs.clo_min
            while test_clo < self.configs.clo_max:
                values.append(round(test_clo, 2))
                test_clo += self.configs.clo_delta
            values.append(self.configs.clo_max)
            self._clo_values = values

        best_pmv = None
        best_clo = None
        for value in self._clo_values:
            pmv = self.get_pmv(temp_ar, mrt, vel, hum_rel, value)
            if best_pmv is None or abs(pmv) < abs(best_pmv):
                best_pmv, best_clo = pmv, value
        return best_clo, self.configs.pmv_lowerbound <= best_pmv <= self.configs.pmv_upperbound
        
    def get_best_velocity_with_pmv(self, temp_ar, mrt, vel, hum_rel, clo) -> tuple[float, int, float]:
        status_ac = 0

        if not self._clo_priority():
            clo = self._step_clo(temp_ar, mrt, vel, hum_rel, clo)

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

        return vel, status_ac, clo

    def get_best_temperatures_with_pmv(self, temp_ar, mrt, vel, hum_rel, clo):
        best_cool_temp = self.configs.temp_ac_max
        best_heat_temp = self.configs.temp_ac_min

        if not self._clo_priority():
            clo = self._step_clo(temp_ar, mrt, vel, hum_rel, clo)

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

        if best_cool_temp < best_heat_temp:
            best_cool_temp = best_heat_temp + 1.0
            if best_cool_temp < self.configs.temp_ac_min:
                best_cool_temp = self.configs.temp_ac_min
                best_heat_temp -= 1.0

        return best_cool_temp, best_heat_temp, clo

    """
    def get_best_temperatures_with_pmv(self, mrt, vel, hum_rel, clo) -> tuple[float, float, float]:
        best_cool_temp = self.configs.temp_ac_max
        best_heat_temp = self.configs.temp_ac_min
        
        pmv = self.get_pmv(best_cool_temp, mrt, vel, hum_rel, clo)
        while pmv > self.configs.pmv_upperbound:
            if clo < self.configs.clo_max:
                clo = round(clo + self.configs.clo_delta, 2)
                if clo > self.configs.clo_max:
                    clo = self.configs.clo_max
                pmv = self.get_pmv(best_cool_temp, mrt, vel, hum_rel, clo)
            else:
                best_cool_temp -= 1.0
                if best_cool_temp <= self.configs.temp_ac_min:
                    best_cool_temp = self.configs.temp_ac_min
                    break
                pmv = self.get_pmv(best_cool_temp, mrt, vel, hum_rel, clo)

        pmv = self.get_pmv(best_heat_temp, mrt, vel, hum_rel, clo)
        while pmv < self.configs.pmv_lowerbound:
            if clo > self.configs.clo_min:
                clo = round(clo - self.configs.clo_delta, 2)
                if clo < self.configs.clo_min:
                    clo = self.configs.clo_min
                pmv = self.get_pmv(best_heat_temp, mrt, vel, hum_rel, clo)
            else:
                best_heat_temp += 1.0
                if best_heat_temp >= self.configs.temp_ac_max:
                    best_heat_temp = self.configs.temp_ac_max
                    break
                pmv = self.get_pmv(best_heat_temp, mrt, vel, hum_rel, clo)

        return best_cool_temp, best_heat_temp, clo
    """

    def get_pmv(self, temp_ar, mrt, vel, rh, clo):
        return _pmv(temp_ar, mrt, vel, rh, self.configs.met, clo, self.configs.wme)

    def is_comfortable(self, temp_op:float, adaptativo:float, temp_op_max:float, pmv:float, status_janela:int, vel:float):
        if temp_op - self.configs.adaptative_bound <= adaptativo <= temp_op + self.configs.adaptative_bound and status_janela == 1 and vel == 0.0:
            return 1
        elif temp_op <= temp_op_max and vel > 0.0 and status_janela == 1:
            return 1
        elif self.configs.pmv_upperbound + self.configs.pmv_comfort_bound >= pmv >= self.configs.pmv_lowerbound - self.configs.pmv_comfort_bound and status_janela == 0:
            return 1
        return 0
    
    def acquire_handlers(self, state):
        missing = []

        self.tdb_handler = self.ep_api.exchange.get_variable_handle(state, "Site Outdoor Air Drybulb Temperature", "Environment")
        if self.tdb_handler <= 0:
            missing.append("Site Outdoor Air Drybulb Temperature (Environment)")

        for room in self.configs.rooms:
            handler = self.ep_api.exchange.get_variable_handle(state, "People Occupant Count", f"PEOPLE_{room.upper()}")
            if handler <= 0:
                missing.append(f"People Occupant Count ({room})")
            self.people_count_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air Temperature", room)
            if handler <= 0:
                missing.append(f"Zone Air Temperature ({room})")
            self.temp_ar_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Mean Radiant Temperature", room)
            if handler <= 0:
                missing.append(f"Zone Mean Radiant Temperature ({room})")
            self.mrt_handler.update({ room : handler })

            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air Relative Humidity", room)
            if handler <= 0:
                missing.append(f"Zone Air Relative Humidity ({room})")
            self.hum_rel_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Operative Temperature", room)
            if handler <= 0:
                missing.append(f"Zone Operative Temperature ({room})")
            self.temp_op_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature", f"PEOPLE_{room.upper()}")
            if handler <= 0:
                missing.append(f"Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature ({room})")
            self.adaptativo_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_variable_handle(state, "Zone Air CO2 Concentration", f"{room.upper()}")
            if handler <= 0:
                missing.append(f"Zone Air CO2 Concentration ({room})")
            self.co2_handler.update({ room : handler })
            
            #handler = self.ep_api.exchange.get_variable_handle(state, "Zone Thermal Comfort Clothing Value", f"PEOPLE_{room.upper()}")
            #if handler <= 0:
            #    missing.append(f"Zone Thermal Comfort Clothing Value ({room})")
            #self.clo_handler.update({ room : handler })

            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"CLO_{room.upper()}")
            if handler <= 0:
                missing.append(f"CLO ({room})")
            self.clo_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"JANELA_{room.upper()}")
            if handler <= 0:
                missing.append(f"JANELA ({room})")
            self.status_janela_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"VENT_{room.upper()}")
            if handler <= 0:
                missing.append(f"VENT ({room})")
            self.status_vent_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"VEL_{room.upper()}")
            if handler <= 0:
                missing.append(f"VEL ({room})")
            self.vel_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"AC_{room.upper()}")
            if handler <= 0:
                missing.append(f"AC ({room})")
            self.status_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_COOL_AC_{room.upper()}")
            if handler <= 0:
                missing.append(f"TEMP_COOL_AC ({room})")
            self.temp_cool_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_HEAT_AC_{room.upper()}")
            if handler <= 0:
                missing.append(f"TEMP_HEAT_AC ({room})")
            self.temp_heat_ac_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"PMV_{room.upper()}")
            if handler <= 0:
                missing.append(f"PMV ({room})")
            self.pmv_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"TEMP_OP_MAX_ADAP_{room.upper()}")
            if handler <= 0:
                missing.append(f"TEMP_OP_MAX_ADAP ({room})")
            self.temp_op_max_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"ADAP_MIN_{room.upper()}")
            if handler <= 0:
                missing.append(f"ADAP_MIN ({room})")
            self.adaptativo_min_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"ADAP_MAX_{room.upper()}")
            if handler <= 0:
                missing.append(f"ADAP_MAX ({room})")
            self.adaptativo_max_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"EM_CONFORTO_{room.upper()}")
            if handler <= 0:
                missing.append(f"EM_CONFORTO ({room})")
            self.em_conforto_handler.update({ room : handler })
            
            handler = self.ep_api.exchange.get_actuator_handle(state, "Schedule:Constant", "Schedule Value", f"DOAS_STATUS_{room.upper()}")
            if handler <= 0:
                missing.append(f"DOAS_STATUS ({room})")
            self.status_doas_handler.update({ room : handler})

        if missing:
            raise RuntimeError(
                "Handlers do EnergyPlus não encontrados (verifique o IDF e a lista "
                f"de rooms): {missing}"
            )
    
    @staticmethod
    def get_temp_max_op(vel):
        return -0.3535 * vel ** 2 + 2.2758 * vel + 24.995
    
    @staticmethod
    def get_vel_adap(temp_op):
        return 0.055 * temp_op ** 2 - 2.331 * temp_op + 23.935 + 0.1
