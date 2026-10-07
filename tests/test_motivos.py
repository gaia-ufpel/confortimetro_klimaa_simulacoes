from types import SimpleNamespace

from confortimetro.control.closed_window import ConditionerClosedWindow
from confortimetro.control.complete import ConditionerComplete
from confortimetro.control.fixed_ac_without_fan import ConditionerFixedAcWithoutFan
from confortimetro.control.motivos import Motivo, decode
from confortimetro.control.without_fan import ConditionerWithoutFan

M = Motivo
ROOM = "SALA"


class FakeExchange:
    """Imita o `ep_api.exchange`: handles inteiros, valores por handle e o log
    de cada set_actuator_value por nome de schedule."""

    def __init__(self, with_motivo=True):
        self.names = {}
        self.values = {}
        self.writes = {}
        self.mes = 1
        self.with_motivo = with_motivo

    def _handle(self, name):
        return self.names.setdefault(name, len(self.names) + 1)

    def get_variable_handle(self, _state, var, key):
        return self._handle((var, key.upper()))

    def get_actuator_handle(self, _state, _comp, _ctrl, key):
        if key.startswith("MOTIVO_") and not self.with_motivo:
            return -1
        return self._handle(key.upper())

    def get_variable_value(self, _state, handle):
        return self.values[handle]

    def get_actuator_value(self, _state, handle):
        return self.values[handle]

    def set_actuator_value(self, _state, handle, value):
        self.values[handle] = value
        name = next(k for k, v in self.names.items() if v == handle)
        self.writes[name] = value

    def month(self, _state):
        return self.mes

    def warmup_flag(self, _state):
        return False

    def api_data_fully_ready(self, _state):
        return True


def configs(**over):
    base = dict(
        rooms=[ROOM], pmv_upperbound=0.5, pmv_lowerbound=-0.5, co2_limit=1000,
        max_vel=1.2, adaptative_bound=2.5, temp_ac_min=16.0, temp_ac_max=30.0,
        met=1.2, wme=0.0, clo_max=1.0, clo_min=0.5, clo_delta=0.1,
        clo_priority=True, temp_open_window_bound=5.0, air_speed_delta=0.15,
        pmv_comfort_bound=0.2,
    )
    base.update(over)
    return SimpleNamespace(**base)


def make(cls, *, people=1, neutra=22.0, tdb=20.0, temp_ar=22.0, temp_op=22.0,
         co2=500.0, mes=1, ac=0, janela=0, vel=0.0, clo=0.5, cool=26.0,
         heat=20.0, temp_op_max=0.0, counter=0, pmv=None, with_motivo=True, **cfg):
    """Condicionador pronto para um timestep, com os valores de entrada."""
    exchange = FakeExchange(with_motivo)
    exchange.mes = mes
    conditioner = cls(SimpleNamespace(exchange=exchange), configs(**cfg))
    conditioner.acquire_handlers(None)
    conditioner.handlers_acquired = True
    conditioner.ac_on_counter[ROOM] = counter
    variables = {
        ("People Occupant Count", "PEOPLE_SALA"): people,
        ("Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature", "PEOPLE_SALA"): neutra,
        ("Site Outdoor Air Drybulb Temperature", "ENVIRONMENT"): tdb,
        ("Zone Air Temperature", ROOM): temp_ar,
        ("Zone Operative Temperature", ROOM): temp_op,
        ("Zone Mean Radiant Temperature", ROOM): temp_ar,
        ("Zone Air Relative Humidity", ROOM): 50.0,
        ("Zone Air CO2 Concentration", ROOM): co2,
        "CLO_SALA": clo, "JANELA_SALA": janela, "VEL_SALA": vel, "AC_SALA": ac,
        "TEMP_COOL_AC_SALA": cool, "TEMP_HEAT_AC_SALA": heat,
        "TEMP_OP_MAX_ADAP_SALA": temp_op_max,
    }
    for name, value in variables.items():
        exchange.values[exchange._handle(name)] = value
    if pmv is not None:
        conditioner.get_pmv = pmv
    return conditioner, exchange


def step(conditioner, exchange):
    conditioner._step(None)
    writes = dict(exchange.writes)
    motivo = writes.pop("MOTIVO_SALA", None)
    return (None if motivo is None else Motivo(int(motivo))), writes


def test_frio_com_ac_mantido_e_setpoint_no_limite():
    # Externa fria bloqueia, AC herdado ligado bloqueia, aquecimento vai a 30 °C
    # e o PMV continua frio, CO2 alto: seis motivos no mesmo timestep.
    conditioner, exchange = make(
        ConditionerComplete, tdb=5.0, temp_ar=18.0, temp_op=18.0, co2=1200.0,
        ac=1, counter=3, temp_op_max=1.5, pmv=lambda *_a: -3.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.JANELA_BLOQUEADA_EXTERNA_FRIA
                      | M.JANELA_BLOQUEADA_AC_LIGADO | M.AC_MANTIDO
                      | M.SETPOINT_AQUECIMENTO_NO_LIMITE | M.DOAS_POR_CO2)
    assert writes == {
        "CLO_SALA": 0.5, "AC_SALA": 1, "DOAS_STATUS_SALA": 1, "JANELA_SALA": 0,
        "PMV_SALA": -3.0, "EM_CONFORTO_SALA": 0, "VENT_SALA": 0, "VEL_SALA": 0.0,
        "TEMP_COOL_AC_SALA": 30.0, "TEMP_HEAT_AC_SALA": 30.0,
        "TEMP_OP_MAX_ADAP_SALA": 1.5, "ADAP_MAX_SALA": 24.5, "ADAP_MIN_SALA": 19.5,
    }
    assert conditioner.ac_on_counter[ROOM] == 4


def test_setpoint_que_alcanca_o_pmv_no_limite_nao_marca_o_bit():
    # O laço para em 30 °C sem avaliar; lá o PMV já entra na faixa.
    conditioner, exchange = make(
        ConditionerComplete, tdb=5.0, temp_ar=18.0, temp_op=18.0, ac=1,
        pmv=lambda ta, *_a: 0.0 if ta >= 30 else -3.0)
    motivo, writes = step(conditioner, exchange)

    assert M.AC_MANTIDO in motivo
    assert M.SETPOINT_AQUECIMENTO_NO_LIMITE not in motivo
    assert writes["TEMP_HEAT_AC_SALA"] == 30.0


def test_quente_tempo_maximo_religa_ac_com_ventilador_no_maximo():
    conditioner, exchange = make(
        ConditionerComplete, tdb=35.0, temp_ar=28.0, temp_op=28.0, ac=1,
        counter=12, pmv=lambda *_a: 3.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.AC_TEMPO_MAXIMO
                      | M.JANELA_BLOQUEADA_EXTERNA_QUENTE | M.VENTILADOR_POR_PMV
                      | M.AC_LIGADO_POR_PMV | M.SETPOINT_RESFRIAMENTO_NO_LIMITE)
    assert (writes["AC_SALA"], writes["VEL_SALA"], writes["VENT_SALA"]) == (1, 1.2, 1)
    assert (writes["TEMP_COOL_AC_SALA"], writes["TEMP_HEAT_AC_SALA"]) == (16.0, 16.0)
    assert writes["JANELA_SALA"] == 0 and writes["DOAS_STATUS_SALA"] == 0
    assert conditioner.ac_on_counter[ROOM] == 1


def test_janela_aberta_pelo_adaptativo_com_conforto_so_de_clo():
    conditioner, exchange = make(
        ConditionerComplete, neutra=23.0, tdb=22.0, temp_ar=23.0, temp_op=23.0,
        cool=25.0, heat=21.0, pmv=lambda *_a: 0.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == M.OCUPADA | M.CONFORTO_SO_COM_CLO | M.JANELA_ABERTA_ADAPTATIVO
    assert (writes["JANELA_SALA"], writes["AC_SALA"], writes["VEL_SALA"]) == (1, 0, 0.0)
    assert (writes["TEMP_COOL_AC_SALA"], writes["TEMP_HEAT_AC_SALA"]) == (25.0, 21.0)


def test_vento_adaptativo_acima_do_maximo_fecha_e_cai_no_pmv():
    # temp_op 27,1 pediria 1,35 m/s (> max_vel): janela fecha, o ventilador
    # por PMV fica com a menor velocidade que dá conforto.
    conditioner, exchange = make(
        ConditionerComplete, neutra=23.0, tdb=25.0, temp_ar=27.0, temp_op=27.1,
        pmv=lambda _ta, _tr, vel, _rh, _clo: 2.0 - 3.0 * vel)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.JANELA_FECHADA_OPERATIVA_FORA
                      | M.JANELA_FECHADA_VENTILADOR_NO_LIMITE | M.VENTILADOR_POR_PMV)
    assert (writes["JANELA_SALA"], writes["VEL_SALA"], writes["AC_SALA"]) == (0, 0.6, 0)
    assert writes["TEMP_OP_MAX_ADAP_SALA"] == conditioner.get_temp_max_op(1.2)


def test_janela_aberta_com_ventilador_adaptativo():
    conditioner, exchange = make(
        ConditionerComplete, neutra=22.0, tdb=24.0, temp_ar=26.0, temp_op=26.0,
        pmv=lambda *_a: 1.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == M.OCUPADA | M.JANELA_ABERTA_COM_VENTILADOR
    assert writes["JANELA_SALA"] == 1 and writes["VEL_SALA"] > 0


def test_sala_vazia_no_inverno_e_travada_pelo_frio():
    conditioner, exchange = make(
        ConditionerComplete, people=0, mes=7, tdb=15.0, temp_ar=19.0, temp_op=19.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == M.VAZIA_JANELA_INVERNO | M.VAZIA_JANELA_TRAVADA_FRIO
    assert writes["JANELA_SALA"] == 0 and conditioner.janela_sem_pessoas_bloqueada[ROOM]


def test_sala_vazia_destravada_purga_co2():
    conditioner, exchange = make(
        ConditionerWithoutFan, people=0, tdb=20.0, temp_ar=23.0, temp_op=23.0)
    conditioner.janela_sem_pessoas_bloqueada[ROOM] = True
    motivo, writes = step(conditioner, exchange)

    assert motivo == M.VAZIA_JANELA_PURGA_CO2
    assert writes["JANELA_SALA"] == 1 and not conditioner.janela_sem_pessoas_bloqueada[ROOM]


def test_sala_vazia_bloqueada_por_externa_fria_e_quente():
    conditioner, exchange = make(
        ConditionerFixedAcWithoutFan, people=0, tdb=30.0, temp_ar=22.0, temp_op=22.0)
    assert step(conditioner, exchange)[0] == M.JANELA_BLOQUEADA_EXTERNA_QUENTE
    conditioner, exchange = make(
        ConditionerFixedAcWithoutFan, people=0, tdb=10.0, temp_ar=22.0, temp_op=22.0)
    assert step(conditioner, exchange)[0] == M.JANELA_BLOQUEADA_EXTERNA_FRIA


def test_sem_ventilador_operativa_fora_liga_ac():
    # Externa permitia, operativa abaixo da banda: janela fecha e o AC liga.
    conditioner, exchange = make(
        ConditionerWithoutFan, tdb=18.0, temp_ar=19.0, temp_op=19.0, co2=1500.0,
        pmv=lambda ta, *_a: (ta - 21.0) * 0.5)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.JANELA_FECHADA_OPERATIVA_FORA
                      | M.AC_LIGADO_POR_PMV | M.DOAS_POR_CO2)
    assert (writes["AC_SALA"], writes["JANELA_SALA"], writes["DOAS_STATUS_SALA"]) == (1, 0, 1)
    assert writes["VEL_SALA"] == 0.0 and (writes["TEMP_COOL_AC_SALA"], writes["TEMP_HEAT_AC_SALA"]) == (22.0, 20.0)


def test_ac_fixo_mantido_sem_escrever_equipamento():
    conditioner, exchange = make(
        ConditionerFixedAcWithoutFan, tdb=35.0, temp_ar=28.0, temp_op=28.0, ac=1,
        pmv=lambda *_a: 2.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.JANELA_BLOQUEADA_EXTERNA_QUENTE
                      | M.JANELA_BLOQUEADA_AC_LIGADO | M.AC_MANTIDO)
    assert "VEL_SALA" not in writes and "TEMP_COOL_AC_SALA" not in writes
    assert writes["AC_SALA"] == 1


def test_janela_fechada_sem_bits_de_janela():
    conditioner, exchange = make(
        ConditionerClosedWindow, co2=1100.0, pmv=lambda *_a: 3.0)
    motivo, writes = step(conditioner, exchange)

    assert motivo == (M.OCUPADA | M.VENTILADOR_POR_PMV | M.AC_LIGADO_POR_PMV
                      | M.SETPOINT_RESFRIAMENTO_NO_LIMITE | M.DOAS_POR_CO2)
    assert writes["JANELA_SALA"] == 0 and writes["VEL_SALA"] == 1.2

    conditioner, exchange = make(ConditionerClosedWindow, people=0)
    assert step(conditioner, exchange)[0] == Motivo(0)


def test_idf_sem_motivo_simula_igual_sem_gravar():
    kwargs = dict(tdb=5.0, temp_ar=18.0, temp_op=18.0, ac=1, pmv=lambda *_a: -3.0)
    com, ex_com = make(ConditionerComplete, **kwargs)
    sem, ex_sem = make(ConditionerComplete, with_motivo=False, **kwargs)
    motivo, writes = step(com, ex_com)
    assert step(sem, ex_sem) == (None, writes)
    assert "SETPOINT_AQUECIMENTO_NO_LIMITE" in decode(float(motivo))


def test_trava_da_sala_vazia_e_por_sala():
    # A esfriou até o mínimo e trava; B (operativa entre o mínimo e a neutra,
    # nunca travada) abre para purgar CO2. Com uma trava só, B herdava a de A
    # e o resultado dependia da ordem das salas.
    operativa = {"A": 21.5, "B": 23.0}
    for order in (["A", "B"], ["B", "A"]):
        conditioner = ConditionerComplete(SimpleNamespace(exchange=FakeExchange()),
                                          configs(rooms=order))
        janela = {room: conditioner.window_without_people(
            None, room, tdb=20.0, temp_ar=23.0, temp_op=operativa[room],
            temp_neutra_adaptativo=24.0, temp_min_adaptativo=21.5,
            temp_max_adaptativo=26.5) for room in order}
        assert janela == {"A": 0, "B": 1}
        assert conditioner.janela_sem_pessoas_bloqueada == {"A": True, "B": False}
