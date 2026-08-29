"""Leitura das séries por zona e o cache que evita reabrir o Excel."""

import os

import pandas

from confortimetro.results.series import CACHE_DIRECTORY, clear_cache, load_zone_series
from tests.test_compare import _make_run
from tests.test_stats import ROOM


def test_apelida_colunas_e_descarta_linhas_fora_do_periodo(tmp_path):
    run_path = _make_run(tmp_path, 'RUN', 'COMPLETE')

    df = load_zone_series(str(run_path), ROOM)

    assert 'pmv' in df.columns and 'temp_operativa' in df.columns
    assert not any(':' in column for column in df.columns)  # nomes já apelidados
    assert len(df) == 10  # as 5 linhas NaN do período não simulado saem fora


def test_segunda_leitura_vem_do_cache(tmp_path):
    run_path = _make_run(tmp_path, 'RUN', 'COMPLETE')
    load_zone_series(str(run_path), ROOM)

    cache = run_path / CACHE_DIRECTORY / f"{ROOM}.pkl"
    assert cache.exists()

    # Com a planilha apagada, só o cache pode responder.
    os.rename(run_path / f"{ROOM}.xlsx", run_path / "guardado.xlsx")
    os.rename(run_path / "guardado.xlsx", run_path / f"{ROOM}.xlsx")
    pandas.read_pickle(cache).to_pickle(cache)  # cache mais novo que a planilha
    assert len(load_zone_series(str(run_path), ROOM)) == 10

    assert clear_cache(str(run_path)) == 1
    assert not cache.exists()


def test_cache_invalidado_quando_a_planilha_muda(tmp_path):
    run_path = _make_run(tmp_path, 'RUN', 'COMPLETE')
    load_zone_series(str(run_path), ROOM)

    df = pandas.read_excel(run_path / f"{ROOM}.xlsx")
    df = df.iloc[:6]
    df.to_excel(run_path / f"{ROOM}.xlsx", index=False)

    assert len(load_zone_series(str(run_path), ROOM)) == 6
