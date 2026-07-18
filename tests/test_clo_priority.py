import sys
from types import ModuleType, SimpleNamespace


pythermalcomfort = ModuleType("pythermalcomfort")
pythermalcomfort.utilities = SimpleNamespace()
ladybug_comfort = ModuleType("ladybug_comfort")
ladybug_pmv = ModuleType("ladybug_comfort.pmv")
ladybug_pmv.predicted_mean_vote = lambda **_kwargs: {"pmv": 0}
sys.modules.setdefault("pythermalcomfort", pythermalcomfort)
sys.modules.setdefault("ladybug_comfort", ladybug_comfort)
sys.modules.setdefault("ladybug_comfort.pmv", ladybug_pmv)

from src.modules.conditioner import Conditioner
from src.modules.conditioner_closed_window import ConditionerClosedWindow


def make_conditioner(pmv_by_clo):
    conditioner = Conditioner.__new__(Conditioner)
    conditioner.configs = SimpleNamespace(
        clo_min=0.5,
        clo_max=1.0,
        clo_delta=0.25,
        pmv_lowerbound=-0.5,
        pmv_upperbound=0.5,
    )
    conditioner.get_pmv = lambda *_args: pmv_by_clo[_args[-1]]
    return conditioner


def test_best_clo_is_the_most_neutral_value_in_the_full_range():
    conditioner = make_conditioner({0.5: 0.3, 0.75: 0.05, 1.0: -0.2})

    clo, comfortable = conditioner.get_best_clo_for_comfort(25, 25, 0, 50, 0.5)

    assert (clo, comfortable) == (0.75, True)


def test_best_clo_returns_the_nearest_value_when_comfort_is_impossible():
    conditioner = make_conditioner({0.5: 0.9, 0.75: 0.6, 1.0: -0.8})

    clo, comfortable = conditioner.get_best_clo_for_comfort(25, 25, 0, 50, 0.5)

    assert (clo, comfortable) == (0.75, False)


def test_comfortable_clo_turns_off_fan_and_ac_but_keeps_doas_control():
    class Exchange:
        variables = {"people": 1, "adaptive": 24, "air": 25, "mrt": 25, "rh": 50, "co2": 1200}
        actuators = {"clo": 0.5, "vel": 0.6, "ac": 1, "cool": 20, "heat": 24}

        def get_variable_value(self, _state, handler):
            return self.variables[handler]

        def get_actuator_value(self, _state, handler):
            return self.actuators[handler]

        def set_actuator_value(self, _state, handler, value):
            self.actuators[handler] = value

    exchange = Exchange()
    conditioner = ConditionerClosedWindow.__new__(ConditionerClosedWindow)
    conditioner.ep_api = SimpleNamespace(exchange=exchange)
    conditioner.configs = SimpleNamespace(
        clo_min=0.5, clo_max=1.0, clo_delta=0.25,
        pmv_lowerbound=-0.5, pmv_upperbound=0.5, pmv_comfort_bound=0.2,
        co2_limit=1000, adaptative_bound=2.5,
    )
    conditioner.ac_on_counter = {"room": 3}
    conditioner.ac_on_max_timesteps = 12
    for name, handler in {
        "people_count_handler": "people", "adaptativo_handler": "adaptive",
        "temp_ar_handler": "air", "mrt_handler": "mrt", "hum_rel_handler": "rh",
        "co2_handler": "co2", "clo_handler": "clo", "vel_handler": "vel",
        "status_ac_handler": "ac", "temp_cool_ac_handler": "cool",
        "temp_heat_ac_handler": "heat", "status_doas_handler": "doas",
        "status_vent_handler": "vent", "status_janela_handler": "window",
        "temp_op_max_handler": "temp_op_max", "pmv_handler": "pmv",
        "em_conforto_handler": "comfort", "adaptativo_max_handler": "adaptive_max",
        "adaptativo_min_handler": "adaptive_min",
    }.items():
        setattr(conditioner, name, {"room": handler})
    conditioner.get_pmv = lambda *_args: {0.5: 0.3, 0.75: 0.0, 1.0: -0.2}[_args[-1]]

    conditioner.room_conditioner(None, "room")

    assert exchange.actuators["clo"] == 0.75
    assert exchange.actuators["vel"] == exchange.actuators["ac"] == 0
    assert exchange.actuators["doas"] == 1
    assert conditioner.ac_on_counter["room"] == 0
