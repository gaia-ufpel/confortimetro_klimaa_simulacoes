"""Gráficos de comparação entre execuções.

Todas as funções devolvem uma `Figure` do matplotlib — quem chama decide se
mostra na interface, salva em PNG ou embute em um relatório. Nada de `pyplot`
aqui: o estado global dele briga com o laço de eventos do Tk.

São dois grupos. Os *agregados* recebem a tabela do comparador (uma linha por
execução) e desenham na hora. Os de *série* releem as planilhas por zona via
`series.load_zone_series` — caro na primeira vez, instantâneo depois.
"""

import os
import re

import matplotlib.dates as mdates
import numpy
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

from .compare import PERCENTAGE_COLUMNS, read_config
from . import series
from .series import load_zone_series

# Paleta Okabe-Ito (segura para daltonismo): azul, laranja, verde, vermelhão,
# rosa e azul-claro. Azul/laranja também servem de "melhor/pior" nas diferenças.
PALETTE = ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '#56B4E9']
GRID_COLOR = '#d5d8cf'
TEXT_COLOR = '#344e41'
# Mesmo fundo dos cards da interface (COLORS["surface"] em gui/theme.py): a
# figura é embutida num deles e um branco puro vira um retângulo destacado.
# Duplicado de propósito — `results/` não importa a GUI, roda no CLI headless.
BACKGROUND = '#fafafa'

FIGURE_SIZE = (11, 6)


def _figure(title, size=FIGURE_SIZE):
    # `constrained` em vez de tight_layout: a figura é embutida no painel e
    # precisa recompor as margens a cada redimensionamento, não só uma vez.
    figure = Figure(figsize=size, dpi=100, facecolor=BACKGROUND, layout='constrained')
    figure.suptitle(title, color=TEXT_COLOR, fontsize=13, fontweight='bold')
    return figure


def _style(axes, xlabel='', ylabel=''):
    axes.set_facecolor(BACKGROUND)
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


def _with_idf(labels, idfs):
    """Acrescenta o nome do IDF de origem ao número/nome curto da execução."""
    result = []
    for label, idf in zip(labels, idfs):
        stem = os.path.splitext(os.path.basename(str(idf)))[0] if idf and str(idf) != 'nan' else ''
        result.append(f"{label} · {stem}" if stem else label)
    return result


def _labels(df):
    labels = trim_common_prefix(list(df['Execução']))
    return _with_idf(labels, df['idf'] if 'idf' in df.columns else [None] * len(labels))


def _run_labels(runs):
    """Rótulos das execuções `(nome, caminho)` das séries: nome curto + IDF."""
    labels = trim_common_prefix([r[0] for r in runs])
    return _with_idf(labels, [os.path.basename(read_config(r[1]).get('_idf_path') or '')
                              for r in runs])


_MESES = {'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr', 'May': 'Mai',
          'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago', 'Sep': 'Set', 'Oct': 'Out',
          'Nov': 'Nov', 'Dec': 'Dez'}


def _pt(text):
    return re.sub(r'\b(%s)\b' % '|'.join(_MESES), lambda m: _MESES[m.group(1)], text)


class DateFormatterPT(mdates.ConciseDateFormatter):
    """ConciseDateFormatter com os meses em português (o `%b` segue o idioma do C)."""

    def format_ticks(self, values):
        return [_pt(label) for label in super().format_ticks(values)]

    def get_offset(self):
        return _pt(super().get_offset())


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


def _number(value):
    """Número no formato brasileiro, com 1 casa abaixo de 10 (0,6 não vira 1)."""
    digits = 1 if abs(value) < 10 else 0
    return (f"{value:,.{digits}f}".replace(',', '\0').replace('.', ',')
            .replace('\0', '.'))


def _short(label, limit=30):
    return label if len(label) <= limit else label[:limit - 1] + '…'


# --------------------------------------------------------------- agregados

def energia_vs_desconforto(df, comfort_metric=None):
    """Dispersão energia × desconforto: a fronteira de Pareto entre estratégias."""
    figure = _figure('Energia × desconforto')
    if comfort_metric is None:
        comfort_metric = 'Desconforto (%)' if 'Desconforto (%)' in df.columns else 'Desconforto'
    axes = _style(figure.add_subplot(111), 'Energia total no período (kWh)',
                  'Desconforto (% do tempo ocupado)')
    axes.yaxis.set_major_formatter(PercentFormatter(1.0))

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
    # Verde escurecido: o #009E73 da paleta dá 3,3:1 sobre branco como texto.
    axes.text(0.01, 1.02, '↙ menos energia e menos desconforto', fontsize=9,
              color='#00704f', transform=axes.transAxes)
    return figure


def energia_por_execucao(df):
    """Barras empilhadas de aquecimento, resfriamento e ventilador de teto."""
    figure = _figure('Consumo no período por execução')
    axes = _style(figure.add_subplot(111), '', 'Energia no período (kWh)')

    labels = [_short(label) for label in _labels(df)]  # prefixo comum já removido
    positions = numpy.arange(len(labels))
    heating = df['Aquecimento (kWh)'].to_numpy()
    cooling_total = df['Resfriamento (kWh)'].to_numpy()
    fan = (df['Ventilador (kWh)'].fillna(0).to_numpy() if 'Ventilador (kWh)' in df
           else numpy.zeros(len(df)))
    # Como Resfriamento (kWh) agora inclui o ventilador, subtraímos para
    # manter a barra de resfriamento (AC) segmentada da do ventilador sem duplicar.
    cooling_ac = numpy.clip(cooling_total - fan, 0, None)

    axes.bar(positions, heating, 0.6, label='Aquecimento', color=PALETTE[1])
    axes.bar(positions, cooling_ac, 0.6, bottom=heating, label='Resfriamento (AC)',
             color=PALETTE[0])
    axes.bar(positions, fan, 0.6, bottom=heating + cooling_ac, label='Ventilador',
             color=PALETTE[2])
    for position, total in zip(positions, heating + cooling_total):
        axes.text(position, total, _number(total),
                  ha='center', va='bottom', fontsize=9, color=TEXT_COLOR)

    axes.set_xticks(positions)
    axes.set_xticklabels(labels, rotation=20, ha='right')
    axes.legend(frameon=False, labelcolor=TEXT_COLOR)
    return figure


ACTUATION_COLUMNS = [
    'Janela aberta (%)', 'Janela aberta',
    'Ventilador ligado (%)', 'Ventilador ligado',
    'Ar condicionado ligado (%)', 'Ar condicionado ligado',
    'DOAS ligado (%)', 'DOAS ligado',
    'Desconforto (%)', 'Desconforto',
]


def acionamentos(df):
    """Barras agrupadas com a fração do tempo ocupado de cada acionamento."""
    figure = _figure('Acionamentos (% do tempo ocupado)')
    axes = _style(figure.add_subplot(111), '', '% do tempo ocupado')
    axes.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))

    # Prioriza as colunas com (%) se presentes, senão legadas sem duplicar
    desired_order = [
        ('Janela aberta (%)', 'Janela aberta'),
        ('Ventilador ligado (%)', 'Ventilador ligado'),
        ('Ar condicionado ligado (%)', 'Ar condicionado ligado'),
        ('DOAS ligado (%)', 'DOAS ligado'),
        ('Desconforto (%)', 'Desconforto'),
    ]
    columns = []
    for new_col, old_col in desired_order:
        if new_col in df.columns:
            columns.append(new_col)
        elif old_col in df.columns:
            columns.append(old_col)

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
    return figure


def delta_vs_baseline(df, baseline=None, metrics=None):
    """Diferença de cada execução contra uma de referência, métrica a métrica."""
    if metrics is None:
        disc_col = 'Desconforto (%)' if 'Desconforto (%)' in df.columns else 'Desconforto'
        metrics = ('Energia total (kWh)', disc_col)
    else:
        # Resolve métricas passadas explicitamente que podem estar no formato legado
        resolved = []
        for m in metrics:
            if m == 'Desconforto' and 'Desconforto (%)' in df.columns and 'Desconforto' not in df.columns:
                resolved.append('Desconforto (%)')
            else:
                resolved.append(m)
        metrics = tuple(resolved)

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
        # Laranja para pior (subiu) e azul para melhor (caiu): nas duas
        # métricas menos é melhor (par seguro para daltonismo).
        colors = [PALETTE[1] if delta > 0 else PALETTE[0] for delta in deltas]
        if metric in PERCENTAGE_COLUMNS:
            axes.xaxis.set_major_formatter(PercentFormatter(1.0))
        axes.barh(positions, deltas, 0.6, color=colors)
        axes.axvline(0, color=TEXT_COLOR, linewidth=1)
        axes.set_yticks(positions)
        axes.set_yticklabels(
            [_short(label, 26) for label in _labels(others)],
            fontsize=9)

    return figure


# ------------------------------------------------------------------ séries

def _occupied(run_path, room):
    series = load_zone_series(run_path, room)
    return series[series['ocupacao'] > 0]


def distribuicao_pmv(runs, room, bounds=None):
    """Distribuição do PMV nas horas ocupadas, uma curva por execução.

    A faixa sombreada vem da configuração da primeira execução (±0,5 se ausente).
    """
    bounds = bounds or series.pmv_bounds(runs[0][1])
    figure = _figure(f'Distribuição do PMV ocupado — {room}')
    axes = _style(figure.add_subplot(111), 'PMV', 'Fração das horas ocupadas')

    axes.axvspan(bounds[0], bounds[1], color=PALETTE[2], alpha=0.12,
                 label=f'faixa {bounds[0]} a {bounds[1]}')

    edges = numpy.linspace(-3, 3, 61)
    for index, (label, run_path) in enumerate(zip(_run_labels(runs),
                                                  [r[1] for r in runs])):
        pmv = _occupied(run_path, room)['pmv'].dropna()
        weights = numpy.ones(len(pmv)) / max(len(pmv), 1)
        axes.hist(pmv, bins=edges, weights=weights, histtype='step', linewidth=2,
                  color=PALETTE[index % len(PALETTE)], label=_short(label))

    axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=9)
    return figure


def adaptativo(runs, room, sample=2000):
    """Temperatura externa × operativa contra a banda adaptativa da ASHRAE 55."""
    figure = _figure(f'Modelo adaptativo — {room}')
    axes = _style(figure.add_subplot(111), 'Temperatura externa (°C)',
                  'Temperatura operativa (°C)')

    for index, (label, run_path) in enumerate(zip(_run_labels(runs),
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
    return figure


# Primeiro dia de cada mês no ano (não bissexto), para os ticks da carpete.
_MONTH_STARTS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]


def carpete(runs, room, variable='temp_operativa'):
    """Mapa dia × hora da variável, um painel por execução na mesma escala.

    O eixo cobre só os dias simulados: uma semana não é esticada sobre o ano.
    """
    titles = {'temp_operativa': 'Temperatura operativa (°C)', 'pmv': 'PMV',
              'co2': 'CO₂ (ppm)'}
    figure = _figure(f'{titles.get(variable, variable)} ao longo do período — {room}',
                     (12, 2.4 * len(runs) + 1.2))
    axes_list = figure.subplots(len(runs), 1, squeeze=False)[:, 0]

    grids, year = [], None
    for _, run_path in runs:
        series = load_zone_series(run_path, room)
        data = series[['data', variable]].dropna()
        stamps = data['data']
        if year is None and len(stamps):
            year = int(stamps.iloc[0].year)
        # Uma coluna por dia, uma linha por timestep do dia.
        day = stamps.dt.dayofyear
        slot = stamps.dt.hour * 60 + stamps.dt.minute
        grid = data.assign(dia=day, slot=slot).pivot_table(
            index='slot', columns='dia', values=variable, aggfunc='mean')
        grids.append(grid)

    low = min(float(numpy.nanmin(grid.to_numpy())) for grid in grids)
    high = max(float(numpy.nanmax(grid.to_numpy())) for grid in grids)
    first = min(int(grid.columns.min()) for grid in grids)
    last = max(int(grid.columns.max()) for grid in grids)

    months = [day for day in _MONTH_STARTS if first <= day <= last]
    if len(months) >= 2:
        ticks, tick_labels = months, [list(_MESES.values())[_MONTH_STARTS.index(day)]
                                      for day in months]
    else:
        # Período curto: um tick por dia (ou a cada poucos dias), em dd/mm.
        step = max(1, (last - first + 1) // 10)
        ticks = list(range(first, last + 1, step))
        origin = numpy.datetime64(f'{year or 2015}-01-01')
        tick_labels = [str(origin + numpy.timedelta64(day - 1, 'D'))[8:10] + '/'
                       + str(origin + numpy.timedelta64(day - 1, 'D'))[5:7]
                       for day in ticks]

    for axes, label, grid in zip(axes_list, _run_labels(runs), grids):
        image = axes.imshow(grid.to_numpy(), aspect='auto', origin='lower',
                            cmap='RdYlGn_r' if variable != 'co2' else 'YlOrBr',
                            vmin=low, vmax=high,
                            extent=[grid.columns.min() - 0.5,
                                    grid.columns.max() + 0.5, 0, 24])
        axes.set_xlim(first - 0.5, last + 0.5)
        axes.set_title(_short(label, 40), color=TEXT_COLOR, fontsize=10, loc='left')
        axes.set_ylabel('Hora', color=TEXT_COLOR, fontsize=9)
        axes.set_yticks([0, 6, 12, 18, 24])
        axes.set_xticks(ticks)
        axes.set_xticklabels(tick_labels)
        axes.tick_params(colors=TEXT_COLOR, labelsize=8)
        figure.colorbar(image, ax=axes, pad=0.01)

    axes_list[-1].set_xlabel('Dia', color=TEXT_COLOR, fontsize=9)
    return figure


def _parse_start(text):
    """`dd/mm/aaaa` (como no editor) ou `aaaa-mm-dd`; vazio devolve `None`."""
    text = (text or '').strip()
    if not text:
        return None
    match = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if match:
        day, month, year = match.groups()
        text = f'{year}-{int(month):02d}-{int(day):02d}'
    try:
        return numpy.datetime64(text, 'D')
    except ValueError:
        raise ValueError(f'Início “{text}” não é uma data dd/mm/aaaa.') from None


def periodo(runs, room, start=None, days=7):
    """Recorte de alguns dias: externa, operativa, banda adaptativa e estados.

    Sem `start`, começa no primeiro dia simulado; fora do período simulado, o
    painel diz qual é o período em vez de sair vazio.
    """
    zones = [load_zone_series(run_path, room) for _, run_path in runs]
    begin = _parse_start(start)
    if begin is None:
        begin = min(zone['data'].min() for zone in zones).to_datetime64().astype('datetime64[D]')
    end = begin + numpy.timedelta64(days, 'D')
    shown = str(begin)
    figure = _figure(f'{days} dias a partir de {shown[8:10]}/{shown[5:7]}/{shown[:4]} — {room}',
                     (12, 2.6 * len(runs) + 1.2))
    axes_list = figure.subplots(len(runs), 1, sharex=True, squeeze=False)[:, 0]

    for axes, label, zone in zip(axes_list, _run_labels(runs), zones):
        window = zone[(zone['data'] >= begin) & (zone['data'] < end)]
        _style(axes, '', '°C')
        if window.empty:
            first, last = zone['data'].min(), zone['data'].max()
            axes.text(0.5, 0.5, f"Sem dados nesse intervalo. Período simulado: "
                      f"{first:%d/%m/%Y} a {last:%d/%m/%Y}.",
                      transform=axes.transAxes, ha='center', va='center',
                      color=TEXT_COLOR, fontsize=10)
            axes.set_title(_short(label, 40), color=TEXT_COLOR, fontsize=10, loc='left')
            continue

        axes.plot(window['data'], window['temp_externa'], color=PALETTE[1],
                  linewidth=1.2, label='Externa')
        axes.plot(window['data'], window['temp_operativa'], color=PALETTE[0],
                  linewidth=1.8, label='Operativa')
        axes.fill_between(window['data'], window['adap_min'], window['adap_max'],
                          color=PALETTE[2], alpha=0.15, label='Banda adaptativa')

        # Faixas de estado no rodapé: o que o controlador fez em cada instante.
        bottom = axes.get_ylim()[0]
        for offset, (state, color) in enumerate(
                (('janela', PALETTE[2]), ('ventilador', PALETTE[1]), ('ac', PALETTE[3]))):
            if state not in window:
                continue
            axes.fill_between(window['data'], bottom + offset * 0.4,
                              bottom + (offset + 1) * 0.4,
                              where=window[state] > 0, color=color, alpha=0.55,
                              step='post', linewidth=0,
                              label=f"{state.capitalize()} (faixa)")

        axes.set_title(_short(label, 40), color=TEXT_COLOR, fontsize=10, loc='left')
        axes.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=8, ncol=6)

    axes_list[-1].xaxis.set_major_formatter(
        DateFormatterPT(axes_list[-1].xaxis.get_major_locator()))
    return figure


CARPET_VARIABLES = {'Temperatura operativa': 'temp_operativa', 'PMV': 'pmv',
                    'CO₂': 'co2'}

# Catálogo consumido pela interface: rótulo -> (função, precisa das séries?,
# opções que a função aceita além dos dados). As opções viram campos na janela.
CHARTS = {
    'Energia × desconforto': (energia_vs_desconforto, False, ()),
    'Consumo por execução': (energia_por_execucao, False, ()),
    'Acionamentos': (acionamentos, False, ()),
    'Diferença contra a referência': (delta_vs_baseline, False, ('baseline',)),
    'Distribuição do PMV': (distribuicao_pmv, True, ()),
    'Modelo adaptativo': (adaptativo, True, ()),
    'Carpete anual': (carpete, True, ('variable',)),
    'Semana típica': (periodo, True, ('start', 'days')),
}
