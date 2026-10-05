"""O IDFProcessor não pode seguir com um IDF processado pela metade."""

from types import SimpleNamespace

import pytest

import eppy.modeleditor
from confortimetro.idf.processor import IDFProcessor
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
