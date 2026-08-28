"""Detecção da instalação do EnergyPlus."""

import os

import pytest

from confortimetro.config import (
    energy_path_version,
    find_energy_path,
    is_energy_path,
)


def make_install(root, name):
    """Cria uma instalação falsa do EnergyPlus e devolve o caminho."""
    path = root / name
    (path / "pyenergyplus").mkdir(parents=True)
    (path / "Energy+.idd").write_text("")
    (path / "pyenergyplus" / "api.py").write_text("")
    return path


def test_is_energy_path_exige_idd_e_api(tmp_path):
    completa = make_install(tmp_path, "EnergyPlus-9-4-0")
    assert is_energy_path(str(completa))

    # Subpasta da instalação: existe, mas não serve.
    assert not is_energy_path(str(completa / "pyenergyplus"))

    (completa / "Energy+.idd").unlink()
    assert not is_energy_path(str(completa))
    assert not is_energy_path("")


@pytest.mark.parametrize("nome,esperado", [
    ("EnergyPlusV9-4-0", "9.4"),
    ("EnergyPlus-9-4-0", "9.4"),
    ("EnergyPlus-23-2-0", "23.2"),
    ("qualquer-coisa", ""),
])
def test_energy_path_version(nome, esperado):
    assert energy_path_version(os.path.join("/opt", nome)) == esperado


def test_find_prefere_9_4_mesmo_com_versao_mais_nova(tmp_path, monkeypatch):
    make_install(tmp_path, "EnergyPlus-23-2-0")
    esperada = make_install(tmp_path, "EnergyPlus-9-4-0")

    monkeypatch.setattr(
        "confortimetro.config._platform_globs", lambda: [str(tmp_path / "EnergyPlus-*")]
    )
    monkeypatch.setattr("confortimetro.config.shutil.which", lambda _: None)
    monkeypatch.delenv("ENERGYPLUS_DIR", raising=False)

    assert find_energy_path() == str(esperada)


def test_find_usa_variavel_de_ambiente(tmp_path, monkeypatch):
    instalacao = make_install(tmp_path, "EnergyPlus-9-4-0")
    monkeypatch.setenv("ENERGYPLUS_DIR", str(instalacao))
    monkeypatch.setattr("confortimetro.config._platform_globs", lambda: [])
    monkeypatch.setattr("confortimetro.config.shutil.which", lambda _: None)

    assert find_energy_path() == str(instalacao)


def test_find_sem_instalacao_retorna_vazio(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "confortimetro.config._platform_globs", lambda: [str(tmp_path / "nada-*")]
    )
    monkeypatch.setattr("confortimetro.config.shutil.which", lambda _: None)
    monkeypatch.delenv("ENERGYPLUS_DIR", raising=False)

    assert find_energy_path() == ""
