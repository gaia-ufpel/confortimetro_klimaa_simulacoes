"""Leitura das séries temporais por zona, com cache em disco.

Cada `<ZONA>.xlsx` tem 52 mil linhas e leva ~22 s para abrir; um gráfico que
compara quatro execuções esperaria um minuto e meio a cada clique. A primeira
leitura grava um pickle ao lado da planilha e as seguintes saem dele
(milissegundos), invalidado pelo `mtime` da planilha original.
"""

import math
import os

import numpy
import pandas

CACHE_DIRECTORY = '.series_cache'
# Sobe quando `COLUMNS` ganha apelidos: o pickle antigo não os tem.
CACHE_VERSION = 4

# Nomes das colunas do <ZONA>.xlsx, com a zona interpolada.
COLUMNS = {
    'data': 'Date/Time',
    'temp_externa': 'Site Outdoor Air Drybulb Temperature',
    'ocupacao': 'PEOPLE_{room}:People Occupant Count',
    'temp_operativa': '{room}:Zone Operative Temperature',
    'pmv': 'PEOPLE_{room}:Zone Thermal Comfort Fanger Model PMV',
    'clo': 'PEOPLE_{room}:Zone Thermal Comfort Clothing Value',
    'adap_min': 'ADAP_MIN_{room}:Schedule Value',
    'adap_max': 'ADAP_MAX_{room}:Schedule Value',
    'janela': 'JANELA_{room}:Schedule Value',
    'ventilador': 'VENT_{room}:Schedule Value',
    'ac': 'AC_{room}:Schedule Value',
    'doas': 'DOAS_STATUS_{room}:Schedule Value',
    'em_conforto': 'EM_CONFORTO_{room}:Schedule Value',
    'co2': '{room}:Zone Air CO2 Concentration',
    'aquecimento': '{room} PTHP:Zone Packaged Terminal Heat Pump Total Heating Energy',
    'resfriamento': '{room} PTHP:Zone Packaged Terminal Heat Pump Total Cooling Energy',
    'energia_ac': 'Energia elétrica AC',
    'energia_ventilador': 'Energia elétrica ventilador',
    'energia_outros': 'Energia elétrica outros equipamentos',
    'energia_iluminacao': 'Energia elétrica iluminação',
    'energia_total': 'Energia elétrica total',
    # Sinais do controlador e do ambiente, para ler a decisão timestep a timestep.
    'temp_ar': '{room}:Zone Air Temperature',
    'temp_radiante': '{room}:Zone Mean Radiant Temperature',
    'umidade': '{room}:Zone Air Relative Humidity',
    'temp_neutra': 'PEOPLE_{room}:Zone Thermal Comfort ASHRAE 55 Adaptive Model Temperature',
    'pmv_controle': 'PMV_{room}:Schedule Value',
    'clo_controle': 'CLO_{room}:Schedule Value',
    'velocidade_ar': 'VEL_{room}:Schedule Value',
    'setpoint_aquecimento': 'TEMP_HEAT_AC_{room}:Schedule Value',
    'setpoint_resfriamento': 'TEMP_COOL_AC_{room}:Schedule Value',
    'temp_op_max_adap': 'TEMP_OP_MAX_ADAP_{room}:Schedule Value',
    'vazao_doas': 'DOAS_{room} OUTDOOR AIR INLET:System Node Mass Flow Rate',
    # Bits de `control.motivos.Motivo` somados; decodifique com `motivos.decode`.
    'motivo': 'MOTIVO_{room}:Schedule Value',
    # Demanda × entrega do PTHP (W) e setpoint efetivo do termostato.
    'demanda_aquecimento_w': '{room}:Zone Predicted Sensible Load to Heating Setpoint Heat Transfer Rate',
    'demanda_resfriamento_w': '{room}:Zone Predicted Sensible Load to Cooling Setpoint Heat Transfer Rate',
    'serpentina_aquecimento_w': '{room} PTHP HEATING COIL:Heating Coil Heating Rate',
    'serpentina_apoio_w': '{room} PTHP SUPP HEATING COIL:Heating Coil Heating Rate',
    'serpentina_resfriamento_w': '{room} PTHP COOLING COIL:Cooling Coil Total Cooling Rate',
    'termostato_aquecimento': '{room}:Zone Thermostat Heating Setpoint Temperature',
    'termostato_resfriamento': '{room}:Zone Thermostat Cooling Setpoint Temperature',
    # Balanço de calor do ar da zona (W; positivo = entra calor no ar).
    'balanco_ganhos_internos_w': '{room}:Zone Air Heat Balance Internal Convective Heat Gain Rate',
    'balanco_superficies_w': '{room}:Zone Air Heat Balance Surface Convection Rate',
    'balanco_entre_zonas_w': '{room}:Zone Air Heat Balance Interzone Air Transfer Rate',
    'balanco_ar_externo_w': '{room}:Zone Air Heat Balance Outdoor Air Transfer Rate',
    'balanco_sistema_ar_w': '{room}:Zone Air Heat Balance System Air Transfer Rate',
    'balanco_sistema_conv_w': '{room}:Zone Air Heat Balance System Convective Heat Gain Rate',
    'balanco_armazenamento_w': '{room}:Zone Air Heat Balance Air Energy Storage Rate',
    'janelas_ganho': '{room}:Zone Windows Total Heat Gain Energy',
    'janelas_perda': '{room}:Zone Windows Total Heat Loss Energy',
}


def column(name, room):
    """Nome real da coluna a partir do apelido e da zona."""
    return COLUMNS[name].format(room=room)


def _cache_path(run_path, room):
    return os.path.join(run_path, CACHE_DIRECTORY, f"{room}.v{CACHE_VERSION}.pkl")


def load_zone_series(run_path, room, refresh=False):
    """Série temporal de uma zona, com apelidos de coluna já aplicados.

    As colunas ganham os nomes curtos de `COLUMNS` (`pmv`, `temp_operativa`, …);
    as demais são descartadas. Linhas fora do período simulado — as planilhas
    antigas carimbam o ano inteiro e preenchem o resto com NaN — saem fora.
    """
    excel_path = os.path.join(run_path, f"{room}.xlsx")
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"{room}.xlsx não encontrado em {run_path}")

    cache_path = _cache_path(run_path, room)
    if not refresh and os.path.exists(cache_path):
        if os.path.getmtime(cache_path) >= os.path.getmtime(excel_path):
            return pandas.read_pickle(cache_path)

    raw = pandas.read_excel(excel_path)
    missing = [alias for alias in ('data', 'ocupacao')
               if column(alias, room) not in raw.columns]
    if missing:
        raise ValueError(
            f"{room}.xlsx em {run_path} não tem "
            f"{', '.join(column(alias, room) for alias in missing)}; a planilha "
            "não veio do pós-processamento desta versão")

    df = pandas.DataFrame({
        alias: raw[column(alias, room)]
        for alias in COLUMNS if column(alias, room) in raw.columns
    })
    df = df.dropna(subset=['ocupacao'])

    # Fallback para 'clo': se a variável do EnergyPlus não foi gravada ou resultou
    # em 0 em timesteps ocupados (ex.: IDF que não amarrou ClothingInsulationSchedule),
    # usa os valores controlados pelo schedule `CLO_{room}`.
    if 'clo_controle' in df:
        if 'clo' not in df or (df.loc[df['ocupacao'] > 0, 'clo'] == 0).all():
            df['clo'] = df['clo_controle']

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_pickle(cache_path)
    return df


def clear_cache(run_path):
    """Remove o cache de séries de uma execução."""
    directory = os.path.join(run_path, CACHE_DIRECTORY)
    if not os.path.isdir(directory):
        return 0
    removed = 0
    for name in os.listdir(directory):
        os.remove(os.path.join(directory, name))
        removed += 1
    os.rmdir(directory)
    return removed


# Estados liga/desliga: num bloco agregado vale o máximo — um acionamento curto
# não pode sumir ao afastar o zoom. `em_conforto` é o inverso: basta um timestep
# fora de conforto para o bloco inteiro contar como fora.
STATE_COLUMNS = ('janela', 'ventilador', 'ac', 'doas')
MIN_STATE_COLUMNS = ('em_conforto',)


def window_series(df, start, end, max_points):
    """Recorte da série para desenhar a janela [start, end] em `max_points` pontos.

    Devolve `(frame, aggregated)`. Com até `max_points` timesteps na janela, o
    frame traz os valores brutos. Acima disso, cada bloco de timesteps vira uma
    linha com `<var>_mean`, `<var>_min` e `<var>_max` para as variáveis
    contínuas e um único valor para os estados. O bloco é contado em timesteps,
    não em tempo, para descer até 1 ao aproximar, e alinhado ao início da série
    para não tremer ao arrastar. Um bloco de folga de cada lado evita que a
    linha termine antes da borda do gráfico.
    """
    stamps = df['data'].to_numpy()
    first = int(stamps.searchsorted(pandas.Timestamp(start).to_datetime64(), 'left'))
    last = int(stamps.searchsorted(pandas.Timestamp(end).to_datetime64(), 'right'))
    count = last - first

    if count == 0:
        return df.iloc[0:0], False
    if count <= max_points:
        window = df.iloc[max(first - 1, 0):last + 1]
        return window.reset_index(drop=True), False

    block = math.ceil(count / max_points)
    begin = max((first // block - 1) * block, 0)
    finish = min((math.ceil(last / block) + 1) * block, len(df))
    window = df.iloc[begin:finish]
    groups = window.groupby(numpy.arange(begin, finish) // block, sort=True)

    columns = {'data': groups['data'].first()}
    for name in window.columns:
        if name == 'data':
            continue
        if name in STATE_COLUMNS:
            columns[name] = groups[name].max()
        elif name in MIN_STATE_COLUMNS:
            columns[name] = groups[name].min()
        else:
            columns[f'{name}_mean'] = groups[name].mean()
            columns[f'{name}_min'] = groups[name].min()
            columns[f'{name}_max'] = groups[name].max()
    return pandas.DataFrame(columns).reset_index(drop=True), True
