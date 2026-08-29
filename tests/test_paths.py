"""Pasta de dados da aplicação e o caminho de cada execução."""

import os

import pytest

from confortimetro import paths
from confortimetro.config import SimulationConfig

IDF = os.path.join('examples', 'idf', 'FAURB', 'FAURB_PTHP_ENTORNO.idf')


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.DATA_DIR_VARIABLE, str(tmp_path))
    return tmp_path


def test_variavel_de_ambiente_manda_na_raiz(data_dir):
    assert paths.app_data_path() == str(data_dir)
    assert paths.runs_root() == os.path.join(str(data_dir), paths.RUNS_DIRECTORY)


def test_raiz_por_plataforma(monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_VARIABLE, raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', '/tmp/dados')
    monkeypatch.setattr(paths.platform, 'system', lambda: 'Linux')

    assert paths.app_data_path() == os.path.join('/tmp/dados', paths.APP_NAME)

    monkeypatch.setattr(paths.platform, 'system', lambda: 'Windows')
    monkeypatch.setenv('LOCALAPPDATA', r'C:\Users\a\AppData\Local')
    assert paths.app_data_path().endswith(paths.APP_NAME)


def test_execucao_nova_nao_sobrescreve_existente(data_dir):
    primeiro = paths.new_run_path('teste')
    os.makedirs(primeiro)

    segundo = paths.new_run_path('teste')

    assert segundo != primeiro and segundo.endswith('teste_2')


def test_config_sem_saida_cai_na_pasta_da_aplicacao(data_dir):
    config = SimulationConfig(met_as_watts=0, _idf_path=IDF, _met=1.2)

    assert config.output_path.startswith(paths.runs_root())
    # O IDF expandido é artefato da execução, não do diretório do modelo.
    assert config.expanded_idf_path == os.path.join(config.output_path, 'expanded.idf')


def test_config_respeita_saida_escolhida(data_dir, tmp_path):
    escolhido = str(tmp_path / 'minha_saida')

    config = SimulationConfig(met_as_watts=0, _idf_path=IDF, _met=1.2,
                              output_path=escolhido)

    assert config.output_path == escolhido
    assert config.expanded_idf_path == os.path.join(escolhido, 'expanded.idf')
