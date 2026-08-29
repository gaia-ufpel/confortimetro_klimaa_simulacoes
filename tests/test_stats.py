"""Estatísticas agregadas: energia em kWh e linhas fora do período simulado."""

import numpy
import pandas
import pytest

from confortimetro.results.stats import get_stats_from_simulation

ROOM = "ATELIE1"
JOULES_PER_KWH = 3.6e6


def _room_dataframe(rows=10, nan_rows=5):
    """Metade ocupada com aquecimento; `nan_rows` linhas fora do período (NaN)."""
    df = pandas.DataFrame({
        "Date/Time": pandas.date_range("2015-01-01 00:10", periods=rows, freq="10min"),
        "Site Outdoor Air Drybulb Temperature": [22.0] * rows,
        f"PEOPLE_{ROOM}:People Occupant Count": [1.0] * rows,
        f"AC_{ROOM}:Schedule Value": [1.0] * rows,
        f"{ROOM} PTHP:Zone Packaged Terminal Heat Pump Total Heating Energy": [JOULES_PER_KWH] * rows,
        f"{ROOM} PTHP:Zone Packaged Terminal Heat Pump Total Cooling Energy": [0.0] * rows,
        f"VENT_{ROOM}:Schedule Value": [0.0] * rows,
        f"JANELA_{ROOM}:Schedule Value": [0.0] * rows,
        f"DOAS_STATUS_{ROOM}:Schedule Value": [0.0] * rows,
        f"{ROOM}:Zone Air CO2 Concentration": [500.0] * rows,
        f"EM_CONFORTO_{ROOM}:Schedule Value": [1.0] * rows,
        f"PEOPLE_{ROOM}:Zone Thermal Comfort Fanger Model PMV": [0.1] * rows,
        f"{ROOM}:Zone Operative Temperature": [24.0] * rows,
        f"ADAP_MIN_{ROOM}:Schedule Value": [21.0] * rows,
        f"ADAP_MAX_{ROOM}:Schedule Value": [26.0] * rows,
    })
    return pandas.concat([df, pandas.DataFrame(numpy.nan, index=range(nan_rows), columns=df.columns)])


def test_ignora_linhas_fora_do_periodo_e_soma_energia(tmp_path):
    _room_dataframe().to_excel(tmp_path / f"{ROOM}.xlsx", index=False)

    get_stats_from_simulation(str(tmp_path), [ROOM])
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    # As 5 linhas NaN não podem entrar na ocupação (NaN != 0 é True em pandas).
    assert stats["Número ocupação"] == 10
    assert stats["Aquecimento"] == 1.0
    assert stats["Resfriamento"] == 0.0
    assert stats["Aquecimento (kWh)"] == pytest.approx(10.0)
    assert stats["Energia total (kWh)"] == pytest.approx(10.0)
    assert stats["PMV fora da faixa"] == 0.0
    assert stats["Fora da banda adaptativa"] == 0.0
