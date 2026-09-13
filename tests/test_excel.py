"""Testes para extração de resultados de arquivos .eso e _match_room."""

import pytest
from confortimetro.results.excel import _match_room


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
