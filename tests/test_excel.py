"""Testes para extração de resultados de arquivos .eso e _match_room."""

import pandas
from confortimetro.results.excel import (
    ELECTRICITY_AC,
    ELECTRICITY_FAN,
    ELECTRICITY_LIGHTS,
    ELECTRICITY_OTHER,
    ELECTRICITY_TOTAL,
    _add_electricity_columns,
    _match_room,
)


def test_match_room_prefix_suffix_and_sorting():
    rooms = ["LINSE", "SEC_LINSE", "ATELIE1"]

    # SEC_LINSE deve casar antes de LINSE por ser mais longo
    var_sec = ("TimeStep", "PEOPLE_SEC_LINSE", "People Occupant Count")
    assert _match_room(var_sec, rooms) == "SEC_LINSE"

    var_linse = ("TimeStep", "PEOPLE_LINSE", "People Occupant Count")
    assert _match_room(var_linse, rooms) == "LINSE"

    # Prefixo de equipamento com espaço
    var_pthp = ("TimeStep", "ATELIE1 PTHP", "Zone Packaged Terminal Heat Pump Total Heating Energy")
    assert _match_room(var_pthp, rooms) == "ATELIE1"

    # DOAS inlet com prefixo e sufixo
    var_doas = ("TimeStep", "DOAS_ATELIE1 OUTDOOR AIR INLET", "System Node Mass Flow Rate")
    assert _match_room(var_doas, rooms) == "ATELIE1"

    # Sem key (key é None), room no name
    var_name_colon = ("TimeStep", None, "Zone Operative Temperature:ATELIE1")
    assert _match_room(var_name_colon, rooms) == "ATELIE1"

    var_name_underscore = ("TimeStep", None, "Zone Operative Temperature_ATELIE1")
    assert _match_room(var_name_underscore, rooms) == "ATELIE1"

    # Variável externa/não relacionada não deve casar com nenhuma sala
    var_env = ("TimeStep", "Environment", "Site Outdoor Air Drybulb Temperature")
    assert _match_room(var_env, rooms) is None


def test_soma_eletricidade_por_zona_inclui_ac_ventilador_e_iluminacao():
    room = "ATELIE1"
    df = pandas.DataFrame({
        f"{room} PTHP:Zone Packaged Terminal Heat Pump Electricity Energy": [100.0, 200.0],
        f"VENTILADOR_{room}:Electric Equipment Electricity Energy": [10.0, 20.0],
        f"{room}:Zone Electric Equipment Electricity Energy": [30.0, 50.0],
        f"{room}:Zone Lights Electricity Energy": [40.0, 60.0],
    })

    _add_electricity_columns(df, room)

    assert df[ELECTRICITY_AC].tolist() == [100.0, 200.0]
    assert df[ELECTRICITY_FAN].tolist() == [10.0, 20.0]
    assert df[ELECTRICITY_OTHER].tolist() == [20.0, 30.0]
    assert df[ELECTRICITY_LIGHTS].tolist() == [40.0, 60.0]
    assert df[ELECTRICITY_TOTAL].tolist() == [170.0, 310.0]
