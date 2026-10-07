"""Marca de instalação que decide se a apresentação abre sozinha."""

import sys

import pytest

pytest.importorskip("tkinter")

from confortimetro.gui import onboarding  # noqa: E402


@pytest.fixture
def instalado(tmp_path, monkeypatch):
    """Simula o executável instalado, com o `instalacao.ini` do Inno Setup."""
    monkeypatch.delenv(onboarding.FORCE_VARIABLE, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Ambiens.exe"))
    return tmp_path / onboarding.MARKER_FILE


def test_pendente_ate_marcar_feito(instalado):
    instalado.write_text("[Ambiens]\nonboarding=pendente\n")
    assert onboarding.pending()
    onboarding.mark_done()
    assert not onboarding.pending()
    # Reinstalar regrava a marca e a apresentação volta.
    instalado.write_text("[Ambiens]\nonboarding=pendente\n")
    assert onboarding.pending()


def test_sem_marca_nao_abre(instalado):
    assert not onboarding.pending()
    onboarding.mark_done()  # sem arquivo, não cria nem quebra
    assert not instalado.exists()


def test_repositorio_so_com_variavel(monkeypatch):
    monkeypatch.delenv(onboarding.FORCE_VARIABLE, raising=False)
    assert not onboarding.pending()
    monkeypatch.setenv(onboarding.FORCE_VARIABLE, "1")
    assert onboarding.pending()
