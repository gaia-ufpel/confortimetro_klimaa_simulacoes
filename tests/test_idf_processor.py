"""O IDFProcessor não pode seguir com um IDF processado pela metade."""

from types import SimpleNamespace

import pytest

import eppy.modeleditor
from confortimetro.idf.processor import IDFProcessor, rooms_without_people
from confortimetro.module_type import ModuleType


class BrokenPeople:
    Name = "PEOPLE_SALA"
    Zone_or_ZoneList_Name = "SALA"

    def __setattr__(self, name, value):
        raise RuntimeError("campo do People rejeitado")


def test_falha_no_people_faz_process_idf_falhar(monkeypatch, tmp_path):
    saved = []

    class FakeIDF:
        def __init__(self, path):
            self.idfobjects = {"People": [BrokenPeople()]}

        def newidfobject(self, *args, **kwargs):
            pass

        def save(self, path):
            saved.append(path)

    monkeypatch.setattr(eppy.modeleditor, "IDF", FakeIDF)
    monkeypatch.setattr(IDFProcessor, "_setup_eppy", lambda self: None)
    configs = SimpleNamespace(
        idf_path=str(tmp_path / "modelo.idf"), output_path=str(tmp_path / "run"),
        rooms=["SALA"], module_type=ModuleType.COMPLETE, met_as_watts=125.0,
        wme=0.0, clo_min=0.5, temp_ac_max=30.0, temp_ac_min=18.0)

    with pytest.raises(RuntimeError, match="People"):
        IDFProcessor(configs).process_idf()
    assert saved == []  # o modelo pela metade não chega a ser gravado


def test_check_input_file_recusa_extensao_e_conteudo(tmp_path):
    from confortimetro.idf import check_input_file
    idf = tmp_path / "a.idf"
    idf.write_text("Version, 9.4;\nZone, SALA;\n")
    epw = tmp_path / "a.epw"
    epw.write_text("LOCATION,x\n")
    lixo = tmp_path / "b.idf"
    lixo.write_text("LOCATION,x\n")
    assert check_input_file(str(idf), "idf") is None
    assert check_input_file(str(epw), "epw") is None
    assert "extensão" in check_input_file(str(epw), "idf")
    assert "conteúdo" in check_input_file(str(lixo), "idf")
    assert "extensão" in check_input_file(str(idf), "epw")


def test_periodo_da_configuracao_vai_para_o_runperiod(monkeypatch, tmp_path):
    from confortimetro.idf.processor import describe_changes
    run_period = SimpleNamespace()
    timestep = SimpleNamespace()
    idf = SimpleNamespace(idfobjects={"RunPeriod": [run_period], "Timestep": [timestep]})
    monkeypatch.setattr(IDFProcessor, "_setup_eppy", lambda self: None)
    configs = SimpleNamespace(
        run_period_start="2015-01-01", run_period_end="2015-01-31",
        timesteps_per_hour=4, met=1.2, met_as_watts=125.0, wme=0.0, clo_min=0.5,
        temp_ac_max=30.0, temp_ac_min=18.0, module_type=ModuleType.COMPLETE)
    IDFProcessor(configs)._apply_run_period(idf)
    assert (run_period.End_Month, run_period.End_Day_of_Month) == (1, 31)
    assert (run_period.Begin_Month, run_period.Begin_Year) == (1, 2015)
    assert timestep.Number_of_Timesteps_per_Hour == 4
    texto = "\n".join(describe_changes(configs))
    assert "01/01/2015 a 31/01/2015" in texto and "Output:Variable" in texto


def test_zona_sem_people_e_barrada():
    # Sem PEOPLE_<ZONA> o EnergyPlus 9.4 caía em segfault no meio da simulação.
    idf = "examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf"
    problems = rooms_without_people(idf, ["ATELIE1", "COPA"])
    assert len(problems) == 1 and "PEOPLE_COPA" in problems[0]
