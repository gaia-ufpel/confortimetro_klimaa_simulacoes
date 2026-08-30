"""Os gráficos saem desenhados a partir dos agregados e das séries."""

import matplotlib
matplotlib.use('Agg')

import pytest

from confortimetro.results import charts
from confortimetro.results.compare import compare_runs, recompute_run
from tests.test_compare import _make_run
from tests.test_stats import ROOM


@pytest.fixture
def duas_execucoes(tmp_path):
    paths = [_make_run(tmp_path, 'CENARIO_COM_JANELA', 'COMPLETE', heating_kwh=10.0),
             _make_run(tmp_path, 'CENARIO_FECHADO', 'CLOSED_WINDOW', heating_kwh=4.0)]
    for path in paths:
        recompute_run(str(path))
    df = compare_runs([str(path) for path in paths], room=ROOM)
    runs = [(path.name, str(path)) for path in paths]
    return df, runs


def test_prefixo_comum_sai_dos_rotulos():
    assert charts.trim_common_prefix(['FAURB_A_1', 'FAURB_A_2']) == ['1', '2']
    assert charts.trim_common_prefix(['unico']) == ['unico']
    # Sem prefixo comum terminado em '_', os nomes ficam como estão.
    assert charts.trim_common_prefix(['abc', 'xyz']) == ['abc', 'xyz']


@pytest.mark.parametrize('name', [name for name, (_, series, _o) in charts.CHARTS.items()
                                  if not series])
def test_graficos_agregados(duas_execucoes, name):
    df, _ = duas_execucoes
    function = charts.CHARTS[name][0]

    figure = function(df)

    assert figure.axes  # desenhou em algum eixo
    assert figure.get_size_inches()[0] > 0


@pytest.mark.parametrize('name', [name for name, (_, series, _o) in charts.CHARTS.items()
                                  if series])
def test_graficos_de_serie(duas_execucoes, name):
    _, runs = duas_execucoes
    function = charts.CHARTS[name][0]

    figure = function(runs, ROOM)

    assert figure.axes


def test_delta_exige_referencia_valida(duas_execucoes):
    df, _ = duas_execucoes

    with pytest.raises(ValueError):
        charts.delta_vs_baseline(df, baseline='NAO_EXISTE')
