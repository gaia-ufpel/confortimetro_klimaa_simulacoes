"""Listagem e comparação de execuções já simuladas."""

import json

import pytest

from confortimetro.results.compare import (
    compare_runs,
    list_runs,
    needs_recompute,
    recompute_run,
)
from tests.test_stats import ROOM, _room_dataframe


def _make_run(outputs, name, module_type, heating_kwh=10.0):
    run_path = outputs / name
    run_path.mkdir()
    (run_path / 'configs.json').write_text(json.dumps({
        'rooms': [ROOM], 'module_type': module_type,
        '_idf_path': '/tmp/modelo/FAURB.idf', 'epw_path': '/tmp/clima/Camaqua.epw',
    }), encoding='utf-8')
    df = _room_dataframe()
    heating = f"{ROOM} PTHP:Zone Packaged Terminal Heat Pump Total Heating Energy"
    df[heating] = df[heating] * (heating_kwh / 10.0)
    df.to_excel(run_path / f"{ROOM}.xlsx", index=False)
    return run_path


def test_lista_execucoes_com_status(tmp_path):
    _make_run(tmp_path, 'COM_JANELA', 'COMPLETE')
    vazia = tmp_path / 'SEM_CONFIG'
    vazia.mkdir()

    runs = list_runs(str(tmp_path))

    assert [run['run'] for run in runs] == ['COM_JANELA']  # sem configs.json não é execução
    assert runs[0]['status'] == 'sem estatísticas'
    assert runs[0]['module_type'] == 'COMPLETE'
    assert runs[0]['idf'] == 'FAURB.idf' and runs[0]['epw'] == 'Camaqua.epw'
    assert runs[0]['rooms_disponiveis'] == [ROOM]


def test_recompute_marca_execucao_como_pronta(tmp_path):
    run_path = _make_run(tmp_path, 'COM_JANELA', 'COMPLETE')

    assert needs_recompute(str(run_path))
    assert recompute_run(str(run_path)) == (str(run_path), None)
    assert not needs_recompute(str(run_path))
    assert list_runs(str(tmp_path))[0]['status'] == 'pronta'


def test_compara_duas_execucoes(tmp_path):
    janela = _make_run(tmp_path, 'COM_JANELA', 'COMPLETE', heating_kwh=10.0)
    fechada = _make_run(tmp_path, 'JANELA_FECHADA', 'CLOSED_WINDOW', heating_kwh=4.0)
    for run_path in (janela, fechada):
        recompute_run(str(run_path))

    df = compare_runs([str(janela), str(fechada)], room=ROOM)

    assert list(df['Execução']) == ['COM_JANELA', 'JANELA_FECHADA']
    assert list(df['module_type']) == ['COMPLETE', 'CLOSED_WINDOW']
    assert df['Energia total (kWh)'].tolist() == pytest.approx([10.0, 4.0])


def test_marca_execucoes_de_periodos_diferentes(tmp_path):
    from confortimetro.results.compare import mismatched_periods
    from tests.test_stats import _room_dataframe

    anual = _make_run(tmp_path, 'ANUAL', 'COMPLETE')
    curta = _make_run(tmp_path, 'CURTA', 'COMPLETE')
    # A execução curta cobre metade dos timesteps: comparar totais não faz sentido.
    _room_dataframe(rows=5, nan_rows=0).to_excel(curta / f"{ROOM}.xlsx", index=False)
    for run_path in (anual, curta):
        recompute_run(str(run_path))

    df = compare_runs([str(anual), str(curta)], room=ROOM)

    assert df['Timesteps simulados'].tolist() == [10, 5]
    assert mismatched_periods(df) == ['CURTA']


def test_compara_ignora_execucao_sem_estatisticas(tmp_path):
    pronta = _make_run(tmp_path, 'PRONTA', 'COMPLETE')
    crua = _make_run(tmp_path, 'CRUA', 'COMPLETE')
    recompute_run(str(pronta))

    df = compare_runs([str(pronta), str(crua)], room=ROOM)

    assert list(df['Execução']) == ['PRONTA']


def test_execucao_antiga_com_parameters_txt_aparece(tmp_path):
    """Antes do configs.json a execução só tinha parameters.txt."""
    from confortimetro.results.compare import list_runs

    run_path = tmp_path / "FAURB_50_1"
    run_path.mkdir()
    (run_path / "parameters.txt").write_text("pmv_upperbound=0.5\nmet=1.2\n")

    runs = list_runs(str(tmp_path))
    assert [run['run'] for run in runs] == ["FAURB_50_1"]
    assert runs[0]['config']['met'] == "1.2"
