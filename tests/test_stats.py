"""Estatísticas agregadas: energia em kWh e linhas fora do período simulado."""

import json
from types import SimpleNamespace

import numpy
import pandas
import pytest

from confortimetro.control.base import Conditioner
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
        f"{ROOM} PTHP:Zone Packaged Terminal Heat Pump Electricity Energy": [JOULES_PER_KWH] * rows,
        f"{ROOM} PTHP HEATING COIL:Heating Coil Electricity Energy": [JOULES_PER_KWH / 2] * rows,
        f"{ROOM} PTHP SUPP HEATING COIL:Heating Coil Electricity Energy": [JOULES_PER_KWH / 2] * rows,
        f"{ROOM} PTHP COOLING COIL:Cooling Coil Electricity Energy": [0.0] * rows,
        f"VENT_{ROOM}:Schedule Value": [0.0] * rows,
        f"JANELA_{ROOM}:Schedule Value": [0.0] * rows,
        f"DOAS_STATUS_{ROOM}:Schedule Value": [0.0] * rows,
        f"{ROOM}:Zone Air CO2 Concentration": [500.0] * rows,
        f"EM_CONFORTO_{ROOM}:Schedule Value": [1.0] * rows,
        f"PEOPLE_{ROOM}:Zone Thermal Comfort Fanger Model PMV": [0.1] * rows,
        # Entradas do PMV do controlador (ar parado a 25 °C: PMV ≈ 0,12).
        f"{ROOM}:Zone Air Temperature": [25.0] * rows,
        f"{ROOM}:Zone Mean Radiant Temperature": [25.0] * rows,
        f"{ROOM}:Zone Air Relative Humidity": [50.0] * rows,
        f"VEL_{ROOM}:Schedule Value": [0.0] * rows,
        f"CLO_{ROOM}:Schedule Value": [0.5] * rows,
        f"{ROOM}:Zone Operative Temperature": [24.0] * rows,
        f"ADAP_MIN_{ROOM}:Schedule Value": [21.0] * rows,
        f"ADAP_MAX_{ROOM}:Schedule Value": [26.0] * rows,
    })
    return pandas.concat([df, pandas.DataFrame(numpy.nan, index=range(nan_rows), columns=df.columns)])


def _write_config(run_path, met=1.2, wme=0.0):
    """O met/wme do controlador saem do configs.json da execução."""
    (run_path / "configs.json").write_text(json.dumps({"_met": met, "wme": wme}))


def test_ignora_linhas_fora_do_periodo_e_soma_energia(tmp_path):
    _room_dataframe().to_excel(tmp_path / f"{ROOM}.xlsx", index=False)
    _write_config(tmp_path)

    get_stats_from_simulation(str(tmp_path), [ROOM])
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    # As 5 linhas NaN não podem entrar na ocupação (NaN != 0 é True em pandas).
    assert stats["Número ocupação"] == 10
    assert stats["Aquecimento (%)"] == 1.0
    assert stats["Resfriamento (%)"] == 0.0
    assert stats["Aquecimento (kWh)"] == pytest.approx(10.0)
    assert stats["Energia total (kWh)"] == pytest.approx(10.0)
    assert stats["PMV fora da faixa (%)"] == 0.0
    assert stats["Fora da banda adaptativa (%)"] == 0.0


def test_get_stats_com_frames(tmp_path):
    df = _room_dataframe()
    # Não cria o arquivo {ROOM}.xlsx em disco para garantir que usa o frames em memória
    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: df})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert stats["Número ocupação"] == 10
    assert stats["Aquecimento (kWh)"] == pytest.approx(10.0)



def test_energia_eletrica_inclui_ventilador_de_teto(tmp_path):
    df = _room_dataframe()
    df[f"VENTILADOR_{ROOM}:Electric Equipment Electricity Energy"] = JOULES_PER_KWH / 10
    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: df})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert stats["Ventilador (kWh)"] == pytest.approx(1.0)
    assert stats["Resfriamento (kWh)"] == pytest.approx(1.0)
    assert stats["Energia total (kWh)"] == pytest.approx(11.0)


def test_energia_total_prefere_total_temporal_com_iluminacao_e_equipamentos(tmp_path):
    df = _room_dataframe(rows=10, nan_rows=0)
    df['Energia elétrica total'] = JOULES_PER_KWH * 2
    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: df})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert stats["Energia total (kWh)"] == pytest.approx(20.0)


def test_planilha_sem_consumo_eletrico_fica_sem_kwh(tmp_path):
    df = _room_dataframe()
    df = df[[c for c in df.columns if "Electricity" not in c]]
    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: df})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert numpy.isnan(stats["Energia total (kWh)"])
    assert numpy.isnan(stats["Ventilador (kWh)"])


def test_pmv_das_estatisticas_e_o_do_controlador(tmp_path):
    """Mesma função e mesmas entradas: igual ao PMV do controle até o
    arredondamento de ponto flutuante (tolerância 1e-9). O Fanger do EnergyPlus,
    0,36 acima, não entra."""
    df = _room_dataframe(rows=6, nan_rows=0)
    # Metade com ventilador a 0,6 m/s num ar a 28,5 °C (sem ele, PMV ≈ 1,3).
    df[f"{ROOM}:Zone Air Temperature"] = [25.0, 28.5, 28.5, 26.0, 28.5, 24.0]
    df[f"{ROOM}:Zone Mean Radiant Temperature"] = df[f"{ROOM}:Zone Air Temperature"]
    df[f"VEL_{ROOM}:Schedule Value"] = [0.0, 0.6, 0.0, 0.0, 0.6, 0.0]
    df[f"CLO_{ROOM}:Schedule Value"] = [0.5, 0.5, 0.5, 0.7, 0.5, 1.0]
    df[f"PEOPLE_{ROOM}:People Occupant Count"] = [1, 2, 1, 1, 1, 0]
    _write_config(tmp_path, met=1.2, wme=0.0)

    control = Conditioner(None, SimpleNamespace(rooms=[ROOM], met=1.2, wme=0.0))
    occupied = df[df[f"PEOPLE_{ROOM}:People Occupant Count"] > 0]
    expected = numpy.array([
        control.get_pmv(row[f"{ROOM}:Zone Air Temperature"],
                        row[f"{ROOM}:Zone Mean Radiant Temperature"],
                        row[f"VEL_{ROOM}:Schedule Value"],
                        row[f"{ROOM}:Zone Air Relative Humidity"],
                        row[f"CLO_{ROOM}:Schedule Value"])
        for _, row in occupied.iterrows()])
    df[f"PEOPLE_{ROOM}:Zone Thermal Comfort Fanger Model PMV"] = 0.36

    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: df})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert stats["PMV médio"] == pytest.approx(expected.mean(), abs=1e-9)
    assert stats["PMV fora da faixa (%)"] == pytest.approx(
        (numpy.abs(expected) > 0.5).sum() / len(expected), abs=1e-9)
    assert (numpy.abs(expected) > 0.5).sum() == 2  # 28,5 °C sem ventilador; 26 °C com 0,7 clo


def test_sem_met_na_configuracao_pmv_fica_sem_valor(tmp_path):
    get_stats_from_simulation(str(tmp_path), [ROOM], frames={ROOM: _room_dataframe()})
    stats = pandas.read_excel(tmp_path / "ESTATISTICAS.xlsx").iloc[0]

    assert numpy.isnan(stats["PMV médio"]) and numpy.isnan(stats["PMV fora da faixa (%)"])
