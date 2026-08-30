"""Leitura do RunPeriod e do timestep direto do texto do IDF."""

from datetime import datetime

from confortimetro.idf import read_run_period, read_timesteps_per_hour

IDF = "examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf"


def test_le_do_modelo_de_referencia():
    assert read_timesteps_per_hour(IDF) == 6
    # O fim é exclusivo: 31/12 vira a meia-noite de 1º de janeiro seguinte.
    assert read_run_period(IDF) == (datetime(2015, 1, 1), datetime(2016, 1, 1))


def test_le_periodo_curto_e_outro_timestep(tmp_path):
    idf = tmp_path / "verao.idf"
    idf.write_text(
        "Timestep,\n    4;  !- Number of Timesteps per Hour\n\n"
        "RunPeriod,\n    verao,  !- Name\n    12,  !- Begin Month\n"
        "    1,  !- Begin Day\n    2019,  !- Begin Year\n"
        "    2,  !- End Month\n    28,  !- End Day\n    2020;  !- End Year\n",
        encoding="latin-1")

    assert read_timesteps_per_hour(str(idf)) == 4
    assert read_run_period(str(idf)) == (datetime(2019, 12, 1), datetime(2020, 2, 29))


def test_valores_padrao_quando_o_arquivo_nao_serve(tmp_path):
    vazio = tmp_path / "vazio.idf"
    vazio.write_text("Zone,\n    ATELIE1;\n", encoding="latin-1")

    assert read_timesteps_per_hour(str(vazio)) == 6
    assert read_run_period(str(vazio)) == (datetime(2015, 1, 1), datetime(2016, 1, 1))
