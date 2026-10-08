"""Valores da INI-C (Anexo I da Portaria Inmetro 309/2022, retificada pela NT 02).

Só o que a classificação da envoltória pelo método de simulação usa. As
referências de tabela apontam para o texto em
`docs/material/Normas PBE Edifica/Portaria_309_2022_retificada_NT02.pdf`.
"""

import csv
import math
import os

# Tabelas A.1, A.2 e A.8: o que muda de uma tipologia para outra. O resto da
# condição de referência (paredes, cobertura, piso, vidro) é igual em todas.
# `ocupacao` é m²/pessoa por uso; `horas` escolhe a rotina da Tabela C.2.
TIPOLOGIAS = {
    "educacional": {
        "nome": "Educacional",
        "paf": 0.40,
        "horas": 8,
        "ocupacao": {"Educação infantil": 2.5,
                     "Ensino fundamental e médio": 1.5,
                     "Ensino superior": 1.5},
    },
    "escritorio": {
        "nome": "Escritório",
        "paf": 0.50,
        "horas": 10,
        "ocupacao": {"Escritório": 10.0},
    },
    "outra": {
        "nome": "Tipologia não descrita",
        "paf": 0.60,
        "horas": 12,
        "ocupacao": {"Não descrita": 10.0},
    },
}

# Coeficiente de redução da carga térmica total anual de D para A (CRCgTT),
# por zona bioclimática e faixa de fator de forma:
# FF ≤ 0,20 | 0,20 < FF ≤ 0,30 | 0,30 < FF ≤ 0,40 | FF > 0,40.
CRCGTT = {
    # Tabela 8.12
    "escritorio": {1: (0.38, 0.39, 0.43, 0.46), 2: (0.34, 0.34, 0.38, 0.41),
                   3: (0.31, 0.32, 0.35, 0.37), 4: (0.35, 0.36, 0.40, 0.43),
                   5: (0.30, 0.30, 0.33, 0.36), 6: (0.32, 0.32, 0.35, 0.38),
                   7: (0.25, 0.25, 0.28, 0.30), 8: (0.24, 0.24, 0.27, 0.29)},
    # Tabela 8.13
    "educacional": {1: (0.22, 0.23, 0.28, 0.38), 2: (0.20, 0.20, 0.24, 0.29),
                    3: (0.16, 0.17, 0.20, 0.25), 4: (0.21, 0.21, 0.26, 0.31),
                    5: (0.15, 0.16, 0.19, 0.23), 6: (0.17, 0.18, 0.21, 0.25),
                    7: (0.13, 0.13, 0.16, 0.19), 8: (0.11, 0.11, 0.14, 0.17)},
    # Tabela 8.19
    "outra": {1: (0.23, 0.23, 0.27, 0.31), 2: (0.25, 0.26, 0.30, 0.34),
              3: (0.22, 0.22, 0.25, 0.29), 4: (0.30, 0.30, 0.35, 0.39),
              5: (0.22, 0.22, 0.26, 0.30), 6: (0.28, 0.28, 0.32, 0.36),
              7: (0.22, 0.23, 0.26, 0.30), 8: (0.19, 0.19, 0.22, 0.26)},
}

# Tabela C.2: horário ocupado nos dias de semana, como (início, fim) em horas.
ROTINAS = {8: (9, 17), 10: (7, 17), 12: (7, 19)}

# C.I.6: setpoints do sistema ideal. O aquecimento é 21 °C no texto do anexo
# de simulação; as tabelas do Anexo A dizem 20 °C. Vale o anexo do método.
SETPOINT_RESFRIAMENTO = 24.0
SETPOINT_AQUECIMENTO = 21.0
# C.I.3: a carga de aquecimento entra nas ZB 1 e 2 e, nas demais, quando o
# projeto prevê aquecimento.
ZB_COM_AQUECIMENTO = (1, 2)

# C.I.6: janelas abrem com a zona ocupada, temperatura interna ≥ 19 °C e
# acima da externa.
TEMPERATURA_ABERTURA = 19.0

# Tabela C.3, frestas com a abertura fechada: (coeficiente kg/(s·m), expoente).
# O expoente das portas sai como "0,0024" no texto, erro de digitação; 0,59 é
# o da NBR 15575, de onde a tabela vem.
FRESTAS_JANELA = (0.00063, 0.63)
FRESTAS_PORTA = (0.0024, 0.59)
COEFICIENTE_DESCARGA = 0.60

# Renovação de ar igual nos dois modelos (C.I.6 remete à NBR 16401-3):
# 5 L/s por pessoa + 0,6 L/s por m², o nível 1 de sala de aula.
AR_EXTERNO_PESSOA = 0.005
AR_EXTERNO_AREA = 0.0006

# Tabela A.9: camadas (nome, espessura m, λ W/(m·K), ρ kg/m³, c J/(kg·K)) e
# resistência das câmaras de ar (m²·K/W). Absortâncias da Tabela A.2.
ABSORTANCIA_PAREDE = 0.5
ABSORTANCIA_COBERTURA = 0.8
ABSORTANCIA_PISO = 0.8
ARGAMASSA = (0.025, 1.15, 2000, 1000)
CERAMICA = (0.0134, 0.90, 1600, 920)
CONCRETO = (0.10, 1.75, 2200, 1000)
FIBROCIMENTO = (0.008, 0.95, 1900, 840)
CAMARA_PAREDE = 0.175
CAMARA_COBERTURA = 0.21
# Vidro simples incolor de 6 mm.
VIDRO_U = 5.7
VIDRO_FS = 0.82
VIDRO_TV = 0.88

# Item 8.2.1 / C.I.6: PHOCT a partir do qual a envoltória é A sem calcular a
# carga térmica.
PHOCT_A = 90.0

# Modelo adaptativo da ASHRAE 55 (80 % de aceitabilidade): faixa em torno da
# temperatura de conforto e limites de aplicação da média externa.
ADAPTATIVO_BANDA = 3.5
ADAPTATIVO_MEDIA = (10.0, 33.5)

CLASSES = ("A", "B", "C", "D", "E")

AVISO_ESTIMATIVA = ("Estimativa pelo método de simulação da INI-C. A ENCE "
                    "oficial exige inspeção de um organismo acreditado (OIA).")


def faixa_fator_forma(ff: float) -> int:
    """Coluna das Tabelas 8.12–8.19 para o fator de forma."""
    for index, limite in enumerate((0.20, 0.30, 0.40)):
        if ff <= limite:
            return index
    return 3


def limites_envoltoria(tipologia: str, zb: int, ff: float) -> dict:
    """`i` e o limite inferior de RedCgTT de cada classe (Equação 8.10)."""
    cr = CRCGTT[tipologia][int(zb)][faixa_fator_forma(ff)]
    i = cr * 100 / 3
    return {"cr": cr, "i": i, "A": 3 * i, "B": 2 * i, "C": i, "D": 0.0}


def classe_envoltoria(red_cgtt: float, limites: dict) -> str:
    """Tabela 8.11: A acima de 3i, B acima de 2i, C acima de i, D até 0, E abaixo."""
    if red_cgtt < 0:
        return "E"
    for classe in ("A", "B", "C"):
        if red_cgtt > limites[classe]:
            return classe
    return "D"


def conforto_adaptativo(temperatura_operativa: float, media_externa: float) -> bool:
    """A hora está em conforto pelo modelo adaptativo (80 %)?

    Fora da faixa de média externa em que o modelo vale, a hora não conta como
    conforto: a norma não dá outro critério e contar como conforto inflaria o
    PHOCT justamente no inverno de Pelotas.
    """
    if not ADAPTATIVO_MEDIA[0] <= media_externa <= ADAPTATIVO_MEDIA[1]:
        return False
    conforto = 0.31 * media_externa + 17.8
    return abs(temperatura_operativa - conforto) <= ADAPTATIVO_BANDA


_CSV_ZONAS = os.path.join(os.path.dirname(__file__), "zonas_bioclimaticas.csv")


def zona_bioclimatica(latitude: float, longitude: float):
    """`(ZB, "Cidade/UF")` do município mais próximo, pelo CSV oficial do PBE Edifica.

    A norma classifica por município; o IDF só tem coordenadas, então vale o
    mais próximo. A interface mostra a cidade para o usuário conferir.
    """
    melhor, distancia = None, math.inf
    with open(_CSV_ZONAS, encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            lat, lon = float(linha["Lat"]), float(linha["Lon"])
            d = (lat - latitude) ** 2 + ((lon - longitude) * math.cos(math.radians(lat))) ** 2
            if d < distancia:
                melhor, distancia = linha, d
    if melhor is None:
        return None, ""
    return int(melhor["ZB"]), f"{melhor['Cidade']}/{melhor['UF']}"
