"""Recorte e agregação da série para a aba Série temporal."""

import numpy
import pandas

from confortimetro.results.series import window_series


def _serie(n=1000):
    data = pandas.date_range('2015-01-01', periods=n, freq='10min')
    janela = numpy.zeros(n)
    janela[503] = 1  # acionamento de um único timestep
    conforto = numpy.ones(n)
    conforto[707] = 0
    return pandas.DataFrame({'data': data, 'temp_operativa': numpy.arange(n, dtype=float),
                             'janela': janela, 'em_conforto': conforto})


def test_janela_pequena_devolve_timesteps_brutos_com_folga():
    df = _serie()
    frame, aggregated = window_series(df, df['data'][100], df['data'][149], 100)

    assert not aggregated
    assert list(frame['temp_operativa']) == list(range(99, 151))


def test_janela_grande_agrega_min_media_max_por_bloco():
    df = _serie()
    frame, aggregated = window_series(df, df['data'][0], df['data'][999], 100)

    assert aggregated
    assert len(frame) == 100  # blocos de 10 timesteps
    assert frame['temp_operativa_min'][0] == 0
    assert frame['temp_operativa_max'][0] == 9
    assert frame['temp_operativa_mean'][0] == 4.5
    assert frame['data'][1] == df['data'][10]


def test_acionamento_e_desconforto_curtos_sobrevivem_a_agregacao():
    df = _serie()
    frame, _ = window_series(df, df['data'][0], df['data'][999], 100)

    assert frame['janela'].sum() == 1 and frame['janela'][50] == 1
    assert (frame['em_conforto'] == 0).sum() == 1 and frame['em_conforto'][70] == 0


def test_blocos_alinhados_ao_inicio_da_serie():
    df = _serie()
    frame, aggregated = window_series(df, df['data'][203], df['data'][602], 100)

    # Blocos de 4 timesteps (40 min) contados a partir do primeiro timestep,
    # não do início da janela: arrastar não muda as fronteiras.
    assert aggregated
    step = pandas.Timedelta('40min')
    assert all((stamp - df['data'][0]) % step == pandas.Timedelta(0)
               for stamp in frame['data'])


def test_coluna_ausente_e_janela_vazia():
    df = _serie().drop(columns='em_conforto')
    frame, _ = window_series(df, df['data'][0], df['data'][999], 100)
    assert 'em_conforto' not in frame

    fora, aggregated = window_series(df, '2020-01-01', '2020-01-02', 100)
    assert fora.empty and not aggregated
