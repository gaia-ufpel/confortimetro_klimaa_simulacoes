"""Gráficos de comparação entre execuções.

Todas as funções devolvem uma `Figure` do matplotlib — quem chama decide se
mostra na interface, salva em PNG ou embute em um relatório. Nada de `pyplot`
aqui: o estado global dele briga com o laço de eventos do Tk.

São dois grupos. Os *agregados* recebem a tabela do comparador (uma linha por
execução) e desenham na hora. Os de *série* releem as planilhas por zona via
`series.load_zone_series` — caro na primeira vez, instantâneo depois.
"""

import os

import numpy
from matplotlib.figure import Figure

from .series import load_zone_series

# Verdes do design system, mais os neutros de apoio; ciclo pensado para
# distinguir de quatro a seis execuções sem virar arco-íris.
PALETTE = ['#3a5a40', '#a06b00', '#588157', '#b3261e', '#406346', '#7a6f9b']
GRID_COLOR = '#d5d8cf'
TEXT_COLOR = '#344e41'

FIGURE_SIZE = (11, 6)


def _figure(title, size=FIGURE_SIZE):
    figure = Figure(figsize=size, dpi=100, facecolor='white')
    figure.suptitle(title, color=TEXT_COLOR, fontsize=13, fontweight='bold')
    return figure


def _style(axes, xlabel='', ylabel=''):
    axes.set_facecolor('white')
    axes.grid(True, color=GRID_COLOR, linewidth=0.8, alpha=0.9)
    axes.set_axisbelow(True)
    for side in ('top', 'right'):
        axes.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        axes.spines[side].set_color(GRID_COLOR)
    axes.tick_params(colors=TEXT_COLOR, labelsize=9)
    axes.set_xlabel(xlabel, color=TEXT_COLOR, fontsize=10)
    axes.set_ylabel(ylabel, color=TEXT_COLOR, fontsize=10)
    return axes


def _labels(df):
    return trim_common_prefix(list(df['Execução']))


def trim_common_prefix(labels):
    """Tira o prefixo que todas as execuções compartilham.

    Nomes como `FAURB_ENTORNO_JANELA_FECHADA_6` só diferem no fim; sem isso a
    legenda vira quatro rótulos idênticos truncados.
    """
    if len(labels) < 2:
        return list(labels)
    prefix = os.path.commonprefix(list(labels))
    prefix = prefix[:prefix.rfind('_') + 1] if '_' in prefix else ''
    if not prefix or any(len(label) <= len(prefix) for label in labels):
        return list(labels)
    return [label[len(prefix):] for label in labels]


def _short(label, limit=22):
    return label if len(label) <= limit else label[:limit - 1] + '…'


# --------------------------------------------------------------- agregados

def energia_vs_desconforto(df, comfort_metric='Desconforto'):
    """Dispersão energia × desconforto: a fronteira de Pareto entre estratégias."""
    figure = _figure('Energia anual × desconforto')
    axes = _style(figure.add_subplot(111), 'Energia total (kWh/ano)',
                  f'{comfort_metric} (fração do tempo ocupado)')

    for index, (label, (_, row)) in enumerate(zip(_labels(df), df.iterrows())):
        color = PALETTE[index % len(PALETTE)]
        axes.scatter(row['Energia total (kWh)'], row[comfort_metric], s=160,
                     color=color, edgecolor='white', linewidth=1.5, zorder=3)
        axes.annotate(_short(label),
                      (row['Energia total (kWh)'], row[comfort_metric]),
                      textcoords='offset points', xytext=(10, 6),
                      color=TEXT_COLOR, fontsize=9)

    # Canto inferior esquerdo é o melhor dos dois mundos; dizer isso poupa a
    # legenda mental de quem lê o gráfico pela primeira vez.
    axes.text(0.01, 1.02, '↙ menos energia e menos desconforto', fontsize=9,
              color='#588157', transform=axes.transAxes)
    figure.tight_layout()
    return figure


def energia_por_execucao(df):
    """Barras empilhadas de aquecimento e resfriamento."""
    figure = _figure('Consumo anual por execução')
    axes = _style(figure.add_subplot(111), '', 'Energia (kWh/ano)')

    labels = [_short(label) for label in _labels(df)]  # prefixo comum já removido
    positions = numpy.arange(len(labels))
    heating = df['Aquecimento (kWh)'].to_numpy()
    cooling = df['Resfriamento (kWh)'].to_numpy()

    axes.bar(positions, heating, 0.6, label='Aquecimento', color=PALETTE[1])
    axes.bar(positions, cooling, 0.6, bottom=heating, label='Resfriamento',
             color=PALETTE[0])
    for position, total in zip(positions, heating + cooling):
        axes.text(position, total, f"{total:,.0f}".replace(',', '.'),
                  ha='center', va='bottom', fontsize=9, color=TEXT_COLOR)

    axes.set_xticks(positions)
    axes.set_xticklabels(labels, rotation=20, ha='right')
    axes.legend(frameon=False, labelcolor=TEXT_COLOR)
    figure.tight_layout()
    return figure


ACTUATION_COLUMNS = ['Janela aberta', 'Ventilador ligado', 'Ar condicionado ligado',
                     'DOAS ligado', 'Desconforto']


def acionamentos(df):
    """Barras agrupadas com a fração do tempo ocupado de cada acionamento."""
    figure = _figure('Acionamentos (fração do tempo ocupado)')
    axes = _style(figure.add_subplot(111), '', 'Fração do tempo ocupado')

    columns = [column for column in ACTUATION_COLUMNS if column in df.columns]
    labels = _labels(df)
    positions = numpy.arange(len(columns))
    width = 0.8 / max(len(labels), 1)

    for index, (label, (_, row)) in enumerate(zip(labels, df.iterrows())):
        offset = (index - (len(labels) - 1) / 2) * width
        axes.bar(positions + offset, [row[column] for column in columns], width,
                 label=_short(label), color=PALETTE[index % len(PALETTE)])

    axes.set_xticks(positions)
    axes.set_xticklabels(columns, rotation=12, ha='right')
    axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=9)
    figure.tight_layout()
    return figure


def delta_vs_baseline(df, baseline=None,
                      metrics=('Energia total (kWh)', 'Desconforto')):
    """Diferença de cada execução contra uma de referência, métrica a métrica."""
    # A referência é procurada pelo nome real da execução; o encurtamento vale
    # só para os rótulos desenhados.
    labels = list(df['Execução'])
    baseline = baseline or labels[0]
    if baseline not in labels:
        raise ValueError(f"execução de referência {baseline} não está na tabela")

    reference = df[df['Execução'] == baseline].iloc[0]
    others = df[df['Execução'] != baseline]
    if others.empty:
        raise ValueError('a comparação precisa de ao menos duas execuções')

    figure = _figure(f'Diferença contra {_short(baseline)}')
    axes_list = figure.subplots(1, len(metrics), squeeze=False)[0]

    for axes, metric in zip(axes_list, metrics):
        _style(axes, '', f'Δ {metric}')
        deltas = others[metric].to_numpy() - reference[metric]
        positions = numpy.arange(len(deltas))
        # Vermelho para pior (subiu) e verde para melhor (caiu): nas duas
        # métricas menos é melhor.
        colors = [PALETTE[3] if delta > 0 else PALETTE[0] for delta in deltas]
        axes.barh(positions, deltas, 0.6, color=colors)
        axes.axvline(0, color=TEXT_COLOR, linewidth=1)
        axes.set_yticks(positions)
        axes.set_yticklabels(
            [_short(label, 18) for label in trim_common_prefix(list(others['Execução']))],
            fontsize=9)

    figure.tight_layout()
    return figure


# ------------------------------------------------------------------ séries

def _occupied(run_path, room):
    series = load_zone_series(run_path, room)
    return series[series['ocupacao'] > 0]


def distribuicao_pmv(runs, room, bounds=(-0.5, 0.5)):
    """Distribuição do PMV nas horas ocupadas, uma curva por execução."""
    figure = _figure(f'Distribuição do PMV ocupado — {room}')
    axes = _style(figure.add_subplot(111), 'PMV', 'Fração das horas ocupadas')

    axes.axvspan(bounds[0], bounds[1], color='#588157', alpha=0.12,
                 label=f'faixa {bounds[0]} a {bounds[1]}')

    edges = numpy.linspace(-3, 3, 61)
    for index, (label, run_path) in enumerate(zip(trim_common_prefix([r[0] for r in runs]),
                                                  [r[1] for r in runs])):
        pmv = _occupied(run_path, room)['pmv'].dropna()
        weights = numpy.ones(len(pmv)) / max(len(pmv), 1)
        axes.hist(pmv, bins=edges, weights=weights, histtype='step', linewidth=2,
                  color=PALETTE[index % len(PALETTE)], label=_short(label))

    axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=9)
    figure.tight_layout()
    return figure


def adaptativo(runs, room, sample=2000):
    """Temperatura externa × operativa contra a banda adaptativa da ASHRAE 55."""
    figure = _figure(f'Modelo adaptativo — {room}')
    axes = _style(figure.add_subplot(111), 'Temperatura externa (°C)',
                  'Temperatura operativa (°C)')

    for index, (label, run_path) in enumerate(zip(trim_common_prefix([r[0] for r in runs]),
                                                  [r[1] for r in runs])):
        occupied = _occupied(run_path, room)
        # Dezenas de milhares de pontos viram uma mancha sólida e travam o
        # canvas; uma amostra regular preserva a nuvem.
        step = max(len(occupied) // sample, 1)
        sampled = occupied.iloc[::step]
        axes.scatter(sampled['temp_externa'], sampled['temp_operativa'], s=8,
                     alpha=0.45, color=PALETTE[index % len(PALETTE)],
                     label=_short(label), edgecolors='none')

    # A banda vem da média móvel da externa, não da externa instantânea: ligar
    # os pontos na ordem bruta desenha um zigue-zague que cobre o gráfico.
    # A média por faixa de 1 °C recupera a linha que o modelo descreve.
    reference = _occupied(runs[0][1], room)
    bins = numpy.arange(numpy.floor(reference['temp_externa'].min()),
                        numpy.ceil(reference['temp_externa'].max()) + 1, 1.0)
    grouped = reference.groupby(numpy.digitize(reference['temp_externa'], bins))
    centers = grouped['temp_externa'].mean()
    axes.plot(centers, grouped['adap_min'].mean(), color=TEXT_COLOR, linewidth=2,
              linestyle='--', label='banda adaptativa', zorder=4)
    axes.plot(centers, grouped['adap_max'].mean(), color=TEXT_COLOR, linewidth=2,
              linestyle='--', zorder=4)

    axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=9, markerscale=2)
    figure.tight_layout()
    return figure


def carpete(runs, room, variable='temp_operativa'):
    """Mapa dia × hora da variável, um painel por execução na mesma escala."""
    titles = {'temp_operativa': 'Temperatura operativa (°C)', 'pmv': 'PMV',
              'co2': 'CO₂ (ppm)'}
    figure = _figure(f'{titles.get(variable, variable)} ao longo do ano — {room}',
                     (12, 3.2 * len(runs) + 1.4))
    axes_list = figure.subplots(len(runs), 1, squeeze=False)[:, 0]

    grids = []
    for _, run_path in runs:
        series = load_zone_series(run_path, room)
        data = series[['data', variable]].dropna()
        stamps = data['data']
        # Uma coluna por dia, uma linha por timestep do dia.
        day = stamps.dt.dayofyear
        slot = stamps.dt.hour * 60 + stamps.dt.minute
        grid = data.assign(dia=day, slot=slot).pivot_table(
            index='slot', columns='dia', values=variable, aggfunc='mean')
        grids.append(grid)

    low = min(float(numpy.nanmin(grid.to_numpy())) for grid in grids)
    high = max(float(numpy.nanmax(grid.to_numpy())) for grid in grids)

    for axes, (label, _), grid in zip(axes_list, runs, grids):
        image = axes.imshow(grid.to_numpy(), aspect='auto', origin='lower',
                            cmap='RdYlGn_r' if variable != 'co2' else 'YlOrBr',
                            vmin=low, vmax=high,
                            extent=[1, 365, 0, 24])
        axes.set_title(_short(label, 40), color=TEXT_COLOR, fontsize=10, loc='left')
        axes.set_ylabel('Hora', color=TEXT_COLOR, fontsize=9)
        axes.set_yticks([0, 6, 12, 18, 24])
        axes.tick_params(colors=TEXT_COLOR, labelsize=8)
        figure.colorbar(image, ax=axes, pad=0.01)

    axes_list[-1].set_xlabel('Dia do ano', color=TEXT_COLOR, fontsize=9)
    figure.tight_layout()
    return figure


def periodo(runs, room, start='2015-01-15', days=7):
    """Recorte de alguns dias: externa, operativa, banda adaptativa e estados."""
    figure = _figure(f'{days} dias a partir de {start} — {room}',
                     (12, 3.4 * len(runs) + 1.2))
    axes_list = figure.subplots(len(runs), 1, sharex=True, squeeze=False)[:, 0]

    begin = numpy.datetime64(start)
    end = begin + numpy.timedelta64(days, 'D')

    for axes, (label, run_path) in zip(axes_list, runs):
        series = load_zone_series(run_path, room)
        window = series[(series['data'] >= begin) & (series['data'] < end)]
        _style(axes, '', '°C')

        axes.plot(window['data'], window['temp_externa'], color=PALETTE[1],
                  linewidth=1.2, label='Externa')
        axes.plot(window['data'], window['temp_operativa'], color=PALETTE[0],
                  linewidth=1.8, label='Operativa')
        axes.fill_between(window['data'], window['adap_min'], window['adap_max'],
                          color='#588157', alpha=0.15, label='Banda adaptativa')

        # Faixas de estado no rodapé: o que o controlador fez em cada instante.
        bottom = axes.get_ylim()[0]
        for offset, (state, color) in enumerate(
                (('janela', '#588157'), ('ventilador', '#a06b00'), ('ac', '#b3261e'))):
            if state not in window:
                continue
            axes.fill_between(window['data'], bottom + offset * 0.4,
                              bottom + (offset + 1) * 0.4,
                              where=window[state] > 0, color=color, alpha=0.55,
                              step='post', linewidth=0,
                              label=f"{state.capitalize()} (faixa)")

        axes.set_title(_short(label, 40), color=TEXT_COLOR, fontsize=10, loc='left')
        axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=8, ncol=6)

    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


# Catálogo consumido pela interface: rótulo -> (função, precisa das séries?).
CHARTS = {
    'Energia × desconforto': (energia_vs_desconforto, False),
    'Consumo por execução': (energia_por_execucao, False),
    'Acionamentos': (acionamentos, False),
    'Diferença contra a referência': (delta_vs_baseline, False),
    'Distribuição do PMV': (distribuicao_pmv, True),
    'Modelo adaptativo': (adaptativo, True),
    'Carpete anual': (carpete, True),
    'Semana típica': (periodo, True),
}
