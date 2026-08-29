"""Banco SQLite dos agregados: ingestão incremental, consulta e histórico."""

import matplotlib
matplotlib.use('Agg')

import pytest

from confortimetro.results.compare import recompute_run
from confortimetro.results.database import (
    database_path,
    history,
    known_mtimes,
    load_comparison,
    sync,
)
from tests.test_compare import _make_run
from tests.test_stats import ROOM


def test_sync_ingere_so_o_que_esta_pronto(tmp_path):
    pronta = _make_run(tmp_path, 'PRONTA', 'COMPLETE')
    _make_run(tmp_path, 'CRUA', 'CLOSED_WINDOW')  # sem ESTATISTICAS.xlsx
    recompute_run(str(pronta))

    assert sync(str(tmp_path)) == (1, 0)
    assert sync(str(tmp_path)) == (0, 0)  # nada mudou: não relê

    df = load_comparison(database_path(str(tmp_path)))
    assert list(df['Execução']) == ['PRONTA']
    assert df['Energia total (kWh)'].tolist() == pytest.approx([10.0])
    assert df['module_type'].tolist() == ['COMPLETE']


def test_known_mtimes_serve_de_cache_de_status(tmp_path):
    pronta = _make_run(tmp_path, 'PRONTA', 'COMPLETE')
    recompute_run(str(pronta))
    sync(str(tmp_path))

    assert str(pronta) in known_mtimes(database_path(str(tmp_path)))


def test_historico_guarda_as_ingestoes_anteriores(tmp_path):
    run_path = _make_run(tmp_path, 'PRONTA', 'COMPLETE')
    recompute_run(str(run_path))
    sync(str(tmp_path))

    # Uma nova regeração com outro consumo não pode apagar o resultado anterior.
    outra = tmp_path / 'novo'
    outra.mkdir()
    nova = _make_run(outra, 'PRONTA', 'COMPLETE', heating_kwh=25.0)
    (nova / f"{ROOM}.xlsx").replace(run_path / f"{ROOM}.xlsx")
    recompute_run(str(run_path))
    sync(str(tmp_path))

    atual = load_comparison(database_path(str(tmp_path)))
    assert atual['Energia total (kWh)'].tolist() == pytest.approx([25.0])

    anterior = history(database_path(str(tmp_path)), str(run_path), ROOM)
    assert anterior['Energia total (kWh)'].tolist() == pytest.approx([10.0, 25.0])


def test_load_comparison_filtra_por_zona(tmp_path):
    run_path = _make_run(tmp_path, 'PRONTA', 'COMPLETE')
    recompute_run(str(run_path))
    sync(str(tmp_path))

    assert load_comparison(database_path(str(tmp_path)), room=ROOM).shape[0] == 1
    assert load_comparison(database_path(str(tmp_path)), room='OUTRA').empty
