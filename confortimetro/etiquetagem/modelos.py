"""Modelos real e de referência da INI-C a partir do IDF do usuário.

Edição textual, como o resto de `confortimetro/idf`: o IDF de origem nunca é
tocado e os objetos que não mudam saem com as linhas originais. Os três
papéis (Anexo C.I):

- `real` — o projeto com ocupação, cargas internas e operação da norma, carga
  térmica pelo sistema ideal e janelas fechadas;
- `real_vn` — o mesmo modelo sem condicionamento, com as janelas das APP
  abrindo pela regra da norma (modo ventilado do edifício híbrido);
- `referencia` — o `real` com paredes, cobertura, piso, vidro e PAF da
  condição de referência e sem o sombreamento do próprio edifício.

As APP são as zonas escolhidas na execução; as demais são APT.
"""

import math

from confortimetro.etiquetagem import norma
from confortimetro.idf.processor import _iter_objects, _read_text, _serialize_object

PAPEIS = {"real": "Real", "real_vn": "Real ventilado", "referencia": "Referência"}

# Geometria que este módulo sabe ler: superfícies e aberturas por vértices.
SUPERFICIE = "buildingsurface:detailed"
ABERTURA = "fenestrationsurface:detailed"
GEOMETRIA_NAO_SUPORTADA = (
    "wall:detailed", "roofceiling:detailed", "floor:detailed", "wall:exterior",
    "wall:adiabatic", "wall:underground", "wall:interzone", "roof",
    "ceiling:adiabatic", "ceiling:interzone", "floor:groundcontact",
    "floor:adiabatic", "floor:interzone", "window", "door", "glazeddoor",
    "window:interzone", "door:interzone", "glazeddoor:interzone")
# HVAC fora dos templates: não há como trocar por um sistema ideal sem
# desmontar laços e nós.
HVAC_NAO_SUPORTADO = ("zonehvac:equipmentconnections", "airloophvac", "plantloop")
# Sombreamento do próprio edifício, que a referência não tem (C.I.4). O de
# `Shading:Building`/`Shading:Site` é o entorno e fica nos dois modelos.
SOMBREAMENTO_PROPRIO = (
    "shading:zone:detailed", "shading:overhang", "shading:overhang:projection",
    "shading:fin", "shading:fin:projection", "windowshadingcontrol")
SOMBREAMENTO_ENTORNO = ("shading:building:detailed", "shading:site:detailed",
                        "shading:building", "shading:site")

VARIAVEIS = (
    "Zone Ideal Loads Supply Air Total Cooling Energy",
    "Zone Ideal Loads Supply Air Total Heating Energy",
    "Zone Operative Temperature",
    "Zone Thermal Comfort ASHRAE 55 Adaptive Model Running Average Outdoor Air Temperature",
)

OCUPACAO = "INIC_OCUPACAO"
DESLIGADO = "INIC_DESLIGADO"
ABERTURA_JANELA = "INIC_ABERTURA"
TERMOSTATO = "INIC_TERMOSTATO"
PAREDE, COBERTURA, PISO, JANELA = "INIC_PAREDE", "INIC_COBERTURA", "INIC_PISO", "INIC_JANELA"

# Folga entre a janela ampliada e a borda da parede, em metros.
FOLGA_BORDA = 0.02


class _Idf:
    """Objetos do IDF que podem ser trocados, removidos ou acrescentados."""

    def __init__(self, texto: str):
        self.linhas = texto.splitlines()
        self.objetos = [{"tipo": tipo, "campos": campos, "ini": ini, "fim": fim,
                         "mudou": False, "removido": False}
                        for tipo, campos, ini, fim in _iter_objects(texto)]
        self.novos = []

    def todos(self, *tipos):
        tipos = {tipo.lower() for tipo in tipos}
        return [obj for obj in self.objetos
                if not obj["removido"] and obj["tipo"].lower() in tipos]

    def tipos(self):
        return {obj["tipo"].lower() for obj in self.objetos if not obj["removido"]}

    def campo(self, obj, posicao, valor):
        campos = obj["campos"]
        while len(campos) <= posicao:
            campos.append("")
        if campos[posicao] != str(valor):
            campos[posicao] = str(valor)
            obj["mudou"] = True

    def remover(self, obj):
        obj["removido"] = True

    def novo(self, tipo, campos):
        self.novos.append((tipo, [str(campo) for campo in campos]))

    def texto(self, cabecalho: str) -> str:
        por_inicio = {obj["ini"]: obj for obj in self.objetos}
        saida, indice = [], 0
        while indice < len(self.linhas):
            obj = por_inicio.get(indice)
            if obj is None:
                saida.append(self.linhas[indice])
                indice += 1
                continue
            if obj["mudou"] and not obj["removido"]:
                saida.extend(_serialize_object(obj["tipo"], obj["campos"]))
            elif not obj["removido"]:
                saida.extend(self.linhas[obj["ini"]:obj["fim"] + 1])
            indice = obj["fim"] + 1
        saida += ["", f"! {cabecalho}"]
        for tipo, campos in self.novos:
            saida.extend(_serialize_object(tipo, campos))
        return "\n".join(saida) + "\n"


# --------------------------------------------------------------- geometria

def _vertices(campos, inicio):
    numeros = []
    for campo in campos[inicio:]:
        try:
            numeros.append(float(campo))
        except ValueError:
            break
    return [tuple(numeros[i:i + 3]) for i in range(0, len(numeros) - 2, 3)]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vetor_area(pontos):
    """Normal de Newell com módulo igual à área (para fora, no anti-horário)."""
    soma = (0.0, 0.0, 0.0)
    for indice, ponto in enumerate(pontos):
        proximo = pontos[(indice + 1) % len(pontos)]
        termo = _cross(ponto, proximo)
        soma = (soma[0] + termo[0], soma[1] + termo[1], soma[2] + termo[2])
    return (soma[0] / 2, soma[1] / 2, soma[2] / 2)


def _area(pontos):
    return math.sqrt(_dot(*(_vetor_area(pontos),) * 2)) if len(pontos) >= 3 else 0.0


def _centroide(pontos):
    n = len(pontos)
    return tuple(sum(ponto[eixo] for ponto in pontos) / n for eixo in range(3))


def _plano(pontos):
    """Origem e base (u, w) do plano do polígono, para trabalhar em 2D."""
    normal = _vetor_area(pontos)
    modulo = math.sqrt(_dot(normal, normal)) or 1.0
    normal = tuple(c / modulo for c in normal)
    u = _sub(pontos[1], pontos[0])
    tamanho = math.sqrt(_dot(u, u)) or 1.0
    u = tuple(c / tamanho for c in u)
    return pontos[0], u, _cross(normal, u)


def _em_2d(pontos, plano):
    origem, u, w = plano
    return [(_dot(_sub(p, origem), u), _dot(_sub(p, origem), w)) for p in pontos]


def _dentro(ponto, poligono):
    x, y = ponto
    dentro = False
    for indice, (x1, y1) in enumerate(poligono):
        x2, y2 = poligono[(indice + 1) % len(poligono)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def _distancia_borda(ponto, poligono):
    menor = math.inf
    for indice, (x1, y1) in enumerate(poligono):
        x2, y2 = poligono[(indice + 1) % len(poligono)]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((ponto[0] - x1) * dx + (ponto[1] - y1) * dy)
                         / ((dx * dx + dy * dy) or 1.0)))
        menor = min(menor, math.hypot(ponto[0] - x1 - t * dx, ponto[1] - y1 - t * dy))
    return menor


def _escalar(pontos, centro, fator):
    return [tuple(c + fator * (p - c) for p, c in zip(ponto, centro)) for ponto in pontos]


def _cabe(janela, centro, fator, parede_2d, plano):
    """A janela escalada fica dentro da parede, com folga da borda?"""
    for ponto in _em_2d(_escalar(janela, centro, fator), plano):
        if not _dentro(ponto, parede_2d) or _distancia_borda(ponto, parede_2d) < FOLGA_BORDA:
            return False
    return True


def _fator_maximo(janela, parede):
    """Maior escala linear que mantém a janela dentro da parede (bisseção)."""
    plano = _plano(parede)
    parede_2d = _em_2d(parede, plano)
    centro = _centroide(janela)
    baixo, alto = 0.0, 1.0
    while _cabe(janela, centro, alto, parede_2d, plano) and alto < 64:
        baixo, alto = alto, alto * 2
    for _ in range(40):
        meio = (baixo + alto) / 2
        if _cabe(janela, centro, meio, parede_2d, plano):
            baixo = meio
        else:
            alto = meio
    return baixo


def _caixa(pontos):
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    return min(xs), min(ys), max(xs), max(ys)


def _multiplicador(campo):
    try:
        return float(campo) if campo else 1.0
    except ValueError:
        return 1.0


def _superficies(idf):
    """`{nome: (objeto, vértices)}` das superfícies de edificação."""
    return {obj["campos"][0].upper(): (obj, _vertices(obj["campos"], 10))
            for obj in idf.todos(SUPERFICIE)}


def _zona_da_abertura(abertura, superficies):
    pai = superficies.get(abertura["campos"][3].upper())
    return pai[0]["campos"][3].upper() if pai else ""


def _envidracada(obj):
    return obj["campos"][1].lower() in ("window", "glassdoor")


def geometria(texto: str) -> dict:
    """Área da envoltória, volume, fator de forma (Equação 8.8) e piso por zona.

    Envoltória: superfícies em contato com o exterior (`Outdoors`), aberturas
    incluídas, sem as em contato com o solo (definição 4.48). Volume: soma
    das zonas, pelo teorema da divergência sobre as superfícies de cada uma,
    ou o volume declarado na `Zone`. As exclusões da definição 4.59 (casa de
    máquinas, reservatórios, garagens, subsolos) não são detectadas.
    """
    idf = _Idf(texto)
    multiplicadores, volumes_declarados = {}, {}
    for zona in idf.todos("Zone"):
        campos = zona["campos"]
        nome = campos[0].upper()
        multiplicadores[nome] = _multiplicador(campos[6] if len(campos) > 6 else "")
        try:
            volumes_declarados[nome] = float(campos[8]) if len(campos) > 8 else None
        except ValueError:
            volumes_declarados[nome] = None

    area, volumes, pisos = 0.0, {}, {}
    for obj, pontos in _superficies(idf).values():
        campos = obj["campos"]
        zona = campos[3].upper()
        vetor = _vetor_area(pontos)
        volumes[zona] = volumes.get(zona, 0.0) + _dot(_centroide(pontos), vetor) / 3
        if campos[4].lower() == "outdoors":
            area += _area(pontos) * multiplicadores.get(zona, 1.0)
        if campos[1].lower() == "floor":
            pisos[zona] = pisos.get(zona, 0.0) + _area(pontos) * multiplicadores.get(zona, 1.0)

    volume = sum((volumes_declarados.get(zona) or abs(valor)) * multiplicadores.get(zona, 1.0)
                 for zona, valor in volumes.items())
    return {"area_envoltoria": area, "volume": volume,
            "ff": area / volume if volume else 0.0, "areas_piso": pisos}


# ----------------------------------------------------------------- edições

def _verificar_suportado(idf):
    tipos = idf.tipos()
    geometria_ruim = sorted(tipo for tipo in tipos if tipo in GEOMETRIA_NAO_SUPORTADA)
    if geometria_ruim:
        raise ValueError("O IDF usa geometria simplificada que a etiquetagem não "
                         f"converte ({', '.join(geometria_ruim)}). Exporte o modelo "
                         "com BuildingSurface:Detailed e FenestrationSurface:Detailed.")
    hvac = sorted(tipo for tipo in tipos if tipo.startswith(HVAC_NAO_SUPORTADO))
    if hvac:
        raise ValueError("O IDF tem HVAC detalhado (" + ", ".join(hvac) + "); a "
                         "etiquetagem só troca sistemas HVACTemplate pelo sistema ideal.")


def _periodo_e_controle(idf):
    """Ano inteiro, sem chuva e sem períodos de dimensionamento (C.I.1–C.I.3)."""
    periodos = idf.todos("RunPeriod")
    if not periodos:
        raise ValueError("O IDF não tem RunPeriod.")
    periodo = periodos[0]
    for posicao, valor in ((1, 1), (2, 1), (4, 12), (5, 31), (11, "No"), (12, "No")):
        idf.campo(periodo, posicao, valor)
    ano = periodo["campos"][3]
    idf.campo(periodo, 6, ano)
    for extra in periodos[1:]:
        idf.remover(extra)

    controles = idf.todos("SimulationControl")
    if not controles:
        idf.novo("SimulationControl", ["No", "No", "No", "No", "Yes"])
    for controle in controles:
        for posicao, valor in enumerate(("No", "No", "No", "No", "Yes")):
            idf.campo(controle, posicao, valor)


def _agendas(idf, tipologia):
    inicio, fim = norma.ROTINAS[norma.TIPOLOGIAS[tipologia]["horas"]]
    idf.novo("ScheduleTypeLimits", ["INIC_FRACAO", 0, 1, "Continuous"])
    idf.novo("ScheduleTypeLimits", ["INIC_QUALQUER"])
    # Dias de semana ocupados; feriados e fins de semana, não (Tabela C.2).
    idf.novo("Schedule:Compact", [
        OCUPACAO, "INIC_FRACAO", "Through: 12/31",
        "For: Weekdays SummerDesignDay WinterDesignDay",
        f"Until: {inicio:02d}:00", 0, f"Until: {fim:02d}:00", 1, "Until: 24:00", 0,
        "For: AllOtherDays", "Until: 24:00", 0])
    idf.novo("Schedule:Constant", [DESLIGADO, "INIC_FRACAO", 0])
    idf.novo("Schedule:Constant", [ABERTURA_JANELA, "INIC_QUALQUER", norma.TEMPERATURA_ABERTURA])


def _cargas_internas(idf, zonas_app, densidade, avisos):
    """Mesma ocupação e rotina nos dois modelos (C.I.4 h–m, C.I.5)."""
    listas = {obj["campos"][0].upper(): {z.upper() for z in obj["campos"][1:]}
              for obj in idf.todos("ZoneList")}
    for pessoas in idf.todos("People"):
        campos = pessoas["campos"]
        alvo = campos[1].upper()
        zonas = listas.get(alvo, {alvo})
        idf.campo(pessoas, 2, OCUPACAO)
        if zonas <= zonas_app:
            for posicao, valor in ((3, "Area/Person"), (4, ""), (5, ""), (6, densidade)):
                idf.campo(pessoas, posicao, valor)
        elif zonas & zonas_app:
            avisos.append(f"People '{campos[0]}' cobre APP e APT ({alvo}); a "
                          "densidade de ocupação da norma não foi aplicada a ele.")
        # Só o adaptativo: o PHOCT sai dele, e o Fanger exigiria os schedules
        # de vestimenta e velocidade do ar que o controlador do Ambiens escreve.
        del campos[19:]
        idf.campo(pessoas, 19, "AdaptiveASH55")
        pessoas["mudou"] = True

    # APP sem ninguém dentro não tem como ter PHOCT nem a carga da ocupação.
    com_pessoas = set()
    for pessoas in idf.todos("People"):
        alvo = pessoas["campos"][1].upper()
        com_pessoas |= listas.get(alvo, {alvo})
    modelo = next(iter(idf.todos("People")), None)
    nomes = {obj["campos"][0].upper(): obj["campos"][0] for obj in idf.todos("Zone")}
    for zona in sorted(zonas_app - com_pessoas):
        if modelo is None:
            raise ValueError("O IDF não tem nenhum objeto People para servir de "
                             "base à ocupação da norma.")
        campos = ["INIC_PESSOAS_" + nomes[zona], nomes[zona], OCUPACAO, "Area/Person",
                  "", "", densidade] + (modelo["campos"][7:19] + [""] * 12)[:12] + ["AdaptiveASH55"]
        idf.novo("People", campos)
        avisos.append(f"Zona {zona}: não tinha People; recebeu a ocupação da norma "
                      f"(atividade e vestimenta de '{modelo['campos'][0]}').")

    for carga in idf.todos("Lights", "ElectricEquipment"):
        # O ventilador de teto do Ambiens: na norma não há quem o ligue.
        if carga["tipo"].lower() == "electricequipment" and \
                carga["campos"][2].upper().startswith("VENT_"):
            idf.remover(carga)
            continue
        idf.campo(carga, 2, OCUPACAO)


def _tem_aquecimento(idf):
    for obj in idf.todos("HVACTemplate:Zone:PTHP", "HVACTemplate:Zone:PTAC",
                         "HVACTemplate:Zone:Unitary", "HVACTemplate:Zone:VRF",
                         "HVACTemplate:Zone:IdealLoadsAirSystem"):
        if obj["tipo"].lower() != "hvactemplate:zone:ptac" or \
                any(campo.lower() in ("electric", "gas", "hotwater")
                    for campo in obj["campos"]):
            return True
    return False


def _hvac(idf, zonas_app, papel, aquecimento):
    """Troca o condicionamento do projeto pelo sistema ideal, só nas horas ocupadas."""
    for obj in list(idf.objetos):
        tipo = obj["tipo"].lower()
        if tipo.startswith(("hvactemplate:", "zonecontrol:thermostat", "thermostatsetpoint:")):
            idf.remover(obj)
    if papel == "real_vn":
        return
    idf.novo("HVACTemplate:Thermostat", [TERMOSTATO, "", norma.SETPOINT_AQUECIMENTO,
                                         "", norma.SETPOINT_RESFRIAMENTO])
    nomes = {obj["campos"][0].upper(): obj["campos"][0] for obj in idf.todos("Zone")}
    for zona in sorted(zonas_app):
        idf.novo("HVACTemplate:Zone:IdealLoadsAirSystem", [
            nomes.get(zona, zona), TERMOSTATO, OCUPACAO, 50, 13, 0.0156, 0.0077,
            "NoLimit", "", "", "NoLimit", "", "",
            "" if aquecimento else DESLIGADO, "",
            "ConstantSensibleHeatRatio", 0.7, 60, "None", 30,
            "Sum", norma.AR_EXTERNO_PESSOA, norma.AR_EXTERNO_AREA, 0, "",
            "None", "NoEconomizer", "None", 0.7, 0.65])


def _airflow(idf, zonas_app, papel, avisos):
    """Frestas da Tabela C.3 e a regra de abertura do modo ventilado (C.I.6)."""
    zonas_afn = idf.todos("AirflowNetwork:MultiZone:Zone")
    if not zonas_afn:
        if papel == "real_vn":
            raise ValueError("O modo híbrido precisa de AirflowNetwork no IDF para "
                             "abrir as janelas; use o modo condicionado.")
        avisos.append("Sem AirflowNetwork: a infiltração do IDF foi mantida, e "
                      "não a das frestas da Tabela C.3.")
        return

    superficies = _superficies(idf)
    aberturas = {obj["campos"][0].upper(): obj for obj in idf.todos(ABERTURA)}
    uso = {}
    for superficie in idf.todos("AirflowNetwork:MultiZone:Surface"):
        idf.campo(superficie, 4, "ZoneLevel")
        abertura = aberturas.get(superficie["campos"][0].upper())
        if abertura is not None:
            porta = abertura["campos"][1].lower() == "door"
            uso.setdefault(superficie["campos"][1].upper(), set()).add(porta)

    for componente in idf.todos("AirflowNetwork:MultiZone:Component:SimpleOpening",
                                "AirflowNetwork:MultiZone:Component:DetailedOpening",
                                "AirflowNetwork:MultiZone:Component:HorizontalOpening"):
        quem = uso.get(componente["campos"][0].upper())
        if not quem:
            continue
        coeficiente, expoente = norma.FRESTAS_PORTA if quem == {True} else norma.FRESTAS_JANELA
        idf.campo(componente, 1, coeficiente)
        idf.campo(componente, 2, expoente)
        if componente["tipo"].lower().endswith("detailedopening"):
            try:
                conjuntos = int(float(componente["campos"][5]))
            except (IndexError, ValueError):
                conjuntos = 2
            for conjunto in range(conjuntos):
                idf.campo(componente, 7 + 5 * conjunto, norma.COEFICIENTE_DESCARGA)
        else:
            idf.campo(componente, 4, norma.COEFICIENTE_DESCARGA)

    com_afn = set()
    for zona in zonas_afn:
        nome = zona["campos"][0].upper()
        com_afn.add(nome)
        if papel == "real_vn" and nome in zonas_app:
            for posicao, valor in ((1, "Temperature"), (2, ABERTURA_JANELA), (3, 1),
                                   (8, OCUPACAO)):
                idf.campo(zona, posicao, valor)
        else:
            idf.campo(zona, 1, "NoVent")
    if papel == "real_vn":
        for zona in sorted(zonas_app - com_afn):
            avisos.append(f"Zona {zona}: sem AirflowNetwork, as janelas não abrem "
                          "no modo ventilado.")
    del superficies


def _saidas(idf):
    for obj in list(idf.objetos):
        if obj["tipo"].lower() in ("output:variable", "output:meter",
                                   "output:meter:meterfileonly",
                                   "output:meter:cumulative"):
            idf.remover(obj)
    for variavel in VARIAVEIS:
        idf.novo("Output:Variable", ["*", variavel, "Hourly"])
    # Horas ocupadas, para o PHOCT: a rotina da norma, igual em todas as zonas.
    idf.novo("Output:Variable", [OCUPACAO, "Schedule Value", "Hourly"])


def _materiais(idf):
    def material(nome, camada, absortancia=0.7):
        espessura, condutividade, densidade, calor = camada
        idf.novo("Material", [nome, "MediumRough", espessura, condutividade,
                              densidade, calor, 0.9, absortancia, absortancia])

    material("INIC_ARGAMASSA_PAREDE", norma.ARGAMASSA, norma.ABSORTANCIA_PAREDE)
    material("INIC_CERAMICA", norma.CERAMICA)
    material("INIC_CONCRETO", norma.CONCRETO, norma.ABSORTANCIA_PISO)
    material("INIC_FIBROCIMENTO", norma.FIBROCIMENTO, norma.ABSORTANCIA_COBERTURA)
    idf.novo("Material:AirGap", ["INIC_CAMARA_PAREDE", norma.CAMARA_PAREDE])
    idf.novo("Material:AirGap", ["INIC_CAMARA_COBERTURA", norma.CAMARA_COBERTURA])
    idf.novo("WindowMaterial:SimpleGlazingSystem",
             ["INIC_VIDRO", norma.VIDRO_U, norma.VIDRO_FS, norma.VIDRO_TV])
    # Camadas simétricas: a mesma construção serve aos dois lados de uma
    # superfície entre zonas. A absortância interna fica a da referência, e
    # não a do modelo real, como a norma pede (C.I.4.1).
    idf.novo("Construction", [PAREDE, "INIC_ARGAMASSA_PAREDE", "INIC_CERAMICA",
                              "INIC_CAMARA_PAREDE", "INIC_CERAMICA", "INIC_ARGAMASSA_PAREDE"])
    idf.novo("Construction", [PISO, "INIC_CONCRETO"])
    idf.novo("Construction", [COBERTURA, "INIC_FIBROCIMENTO", "INIC_CAMARA_COBERTURA",
                              "INIC_CONCRETO"])
    idf.novo("Construction", [JANELA, "INIC_VIDRO"])


def _envoltoria_referencia(idf, zonas_app, avisos):
    _materiais(idf)
    superficies = _superficies(idf)
    for obj, _ in superficies.values():
        campos = obj["campos"]
        tipo, contorno = campos[1].lower(), campos[4].lower()
        if tipo == "wall":
            idf.campo(obj, 2, PAREDE)
        elif tipo == "roof" and contorno == "outdoors":
            idf.campo(obj, 2, COBERTURA)
        else:
            idf.campo(obj, 2, PISO)

    # Ático modelado como zona: a cobertura de referência já traz câmara e laje.
    for zona in sorted({obj["campos"][3].upper() for obj, _ in superficies.values()
                        if obj["campos"][1].lower() == "roof"
                        and obj["campos"][4].lower() == "outdoors"} - zonas_app):
        sem_janela = not any(_zona_da_abertura(a, superficies) == zona
                             for a in idf.todos(ABERTURA))
        if sem_janela and any(o["campos"][3].upper() == zona and o["campos"][1].lower() == "floor"
                              and o["campos"][4].lower() == "surface"
                              for o, _ in superficies.values()):
            avisos.append(f"Zona {zona} parece um ático: recebeu a cobertura de "
                          "referência (telha, câmara e laje) por cima da laje do "
                          "modelo. Confira se é assim que o modelo real está.")

    for abertura in idf.todos(ABERTURA):
        pai = superficies.get(abertura["campos"][3].upper())
        if _envidracada(abertura) and pai and pai[0]["campos"][4].lower() == "outdoors" \
                and pai[0]["campos"][3].upper() in zonas_app:
            idf.campo(abertura, 2, JANELA)

    removidos = [obj for obj in idf.objetos if not obj["removido"]
                 and obj["tipo"].lower() in SOMBREAMENTO_PROPRIO]
    for obj in removidos:
        idf.remover(obj)
    if removidos:
        avisos.append(f"{len(removidos)} sombreamento(s) do próprio edifício removido(s) "
                      "na referência (brises, beirais, controles de sombreamento).")
    entorno = len(idf.todos(*SOMBREAMENTO_ENTORNO))
    if entorno:
        avisos.append(f"{entorno} superfície(s) de sombreamento mantida(s) como entorno "
                      "nos dois modelos. Se alguma for brise ou beiral do próprio "
                      "edifício, ela deveria sair da referência.")


def ajustar_paf(idf, zonas_app, paf, avisos):
    """Redimensiona as janelas de cada APP para o PAF de referência (C.I.4.1).

    Cada janela é escalada em torno do próprio centro, todas na mesma
    proporção, mantendo a posição. A que bate na borda da parede para ali e as
    outras crescem mais para compensar; se nem assim couber, o PAF fica abaixo
    do alvo e o aviso diz quanto. Zona sem janela continua sem.
    """
    superficies = _superficies(idf)
    paredes = {}
    for nome, (obj, pontos) in superficies.items():
        campos = obj["campos"]
        if campos[1].lower() == "wall" and campos[4].lower() == "outdoors" \
                and campos[3].upper() in zonas_app:
            paredes[nome] = (campos[3].upper(), pontos)

    por_zona = {}
    for abertura in idf.todos(ABERTURA):
        pai = abertura["campos"][3].upper()
        if pai in paredes and _envidracada(abertura):
            por_zona.setdefault(paredes[pai][0], []).append(abertura)
        elif pai in superficies and _envidracada(abertura) \
                and superficies[pai][0]["campos"][1].lower() == "roof" \
                and superficies[pai][0]["campos"][3].upper() in zonas_app:
            avisos.append(f"Abertura zenital '{abertura['campos'][0]}' mantida como "
                          "no modelo real (a Tabela C.1 não foi aplicada).")

    for zona in sorted(zonas_app):
        fachada = sum(_area(pontos) for z, pontos in paredes.values() if z == zona)
        janelas = por_zona.get(zona, [])
        if not fachada or not janelas:
            continue
        dados = []
        for abertura in janelas:
            pontos = _vertices(abertura["campos"], 9)
            area = _area(pontos) * _multiplicador(abertura["campos"][7])
            parede = paredes[abertura["campos"][3].upper()][1]
            dados.append([abertura, pontos, area, _fator_maximo(pontos, parede)])
        _limitar_vizinhas(dados, paredes)
        atual = sum(area for _, _, area, _ in dados) / fachada
        alvo = paf * fachada

        def total(escala):
            return sum(area * min(escala, limite) ** 2 for _, _, area, limite in dados)

        baixo, alto = 0.0, max(limite for *_, limite in dados)
        if total(alto) < alvo:
            escala = alto
        else:
            for _ in range(60):
                meio = (baixo + alto) / 2
                baixo, alto = (meio, alto) if total(meio) < alvo else (baixo, meio)
            escala = alto
        novas = {}
        for abertura, pontos, area, limite in dados:
            fator = min(escala, limite)
            novas[abertura["campos"][0]] = (
                abertura, _escalar(pontos, _centroide(pontos), fator), area * fator ** 2)
        faixa = ""
        if total(escala) < alvo - 0.005 * fachada:
            faixa = _faixas(novas, paredes, alvo)

        for abertura, pontos, _ in novas.values():
            for posicao, ponto in enumerate(pontos):
                for eixo, valor in enumerate(ponto):
                    idf.campo(abertura, 9 + 3 * posicao + eixo, f"{valor:.4f}")
        obtido = sum(area for *_, area in novas.values()) / fachada
        mensagem = (f"Zona {zona}: PAF {atual * 100:.1f} % → {obtido * 100:.1f} % "
                    f"({len(dados)} janela(s) {'ampliada(s)' if obtido > atual else 'reduzida(s)'}"
                    f"{faixa})")
        if obtido < paf - 0.005:
            mensagem += f"; não coube {paf * 100:.0f} % nas paredes com janela"
        avisos.append(mensagem + ".")


def _retangulo_vertical(pontos):
    """`(origem, direita, normal, (a0, a1), (z0, z1))` de uma parede retangular vertical."""
    if len(pontos) != 4:
        return None
    normal = _vetor_area(pontos)
    if abs(normal[2]) > 1e-6 * (_area(pontos) or 1):
        return None
    direita = _cross((0.0, 0.0, 1.0), normal)
    modulo = math.sqrt(_dot(direita, direita)) or 1.0
    direita = tuple(c / modulo for c in direita)
    origem = pontos[0]
    largura = [_dot(_sub(p, origem), direita) for p in pontos]
    alturas = [p[2] for p in pontos]
    a, z = (min(largura), max(largura)), (min(alturas), max(alturas))
    if abs((a[1] - a[0]) * (z[1] - z[0]) - _area(pontos)) > 0.01 * _area(pontos):
        return None
    return origem, direita, normal, a, z


def _faixas(novas, paredes, alvo):
    """Refaz as janelas de cada parede retangular como faixa de painéis lado a lado.

    Usado quando escalar cada janela no lugar não alcança o PAF: a parede com
    `k` janelas ganha `k` painéis de mesma largura, ocupando a largura toda (com
    folga), na altura média das janelas originais. Nomes e superfície-mãe
    ficam, então as ligações do AirflowNetwork continuam valendo. A área que
    falta é dividida entre as paredes retangulares na proporção da área delas.
    """
    por_parede = {}
    for nome, (abertura, _, _) in novas.items():
        por_parede.setdefault(abertura["campos"][3].upper(), []).append(nome)
    retangulos = {pai: _retangulo_vertical(paredes[pai][1]) for pai in por_parede}
    retangulos = {pai: r for pai, r in retangulos.items() if r}
    if not retangulos:
        return ""
    fixa = sum(area for nome, (abertura, _, area) in novas.items()
               if abertura["campos"][3].upper() not in retangulos)
    falta = max(alvo - fixa, 0.0)
    soma_paredes = sum(_area(paredes[pai][1]) for pai in retangulos)

    for pai, (origem, direita, normal, (a0, a1), (z0, z1)) in retangulos.items():
        nomes = sorted(por_parede[pai],
                       key=lambda n: _dot(_sub(_centroide(novas[n][1]), origem), direita))
        k = len(nomes)
        largura = (a1 - a0 - (k + 1) * FOLGA_BORDA) / k
        if largura <= 0:
            continue
        meta = falta * _area(paredes[pai][1]) / soma_paredes
        altura = min(meta / (k * largura), z1 - z0 - 2 * FOLGA_BORDA)
        centro = sum(_centroide(novas[n][1])[2] for n in nomes) / k
        base = min(max(centro - altura / 2, z0 + FOLGA_BORDA), z1 - FOLGA_BORDA - altura)
        for indice, nome in enumerate(nomes):
            esquerda = a0 + FOLGA_BORDA + indice * (largura + FOLGA_BORDA)

            def ponto(a, z):
                return (origem[0] + a * direita[0], origem[1] + a * direita[1], z)

            # Canto superior esquerdo, anti-horário visto de fora.
            pontos = [ponto(esquerda, base + altura), ponto(esquerda, base),
                      ponto(esquerda + largura, base), ponto(esquerda + largura, base + altura)]
            if _dot(_vetor_area(pontos), normal) < 0:
                pontos.reverse()
            abertura = novas[nome][0]
            abertura["campos"][7] = "1"
            abertura["mudou"] = True
            novas[nome] = (abertura, pontos, largura * altura)
    return "; em faixa nas paredes retangulares"

def _limitar_vizinhas(dados, paredes):
    """Janelas da mesma parede crescem até encostar (com folga), sem se sobrepor.

    Pela caixa de cada uma no plano da parede: com as duas escaladas por `s`
    em torno do centro, ficam separadas num eixo enquanto
    `s · (meia1 + meia2) ≤ distância entre centros − folga`.
    """
    caixas = []
    for abertura, pontos, *_ in dados:
        plano = _plano(paredes[abertura["campos"][3].upper()][1])
        caixas.append((abertura["campos"][3].upper(), _caixa(_em_2d(pontos, plano))))
    for i, (pai_a, a) in enumerate(caixas):
        for j in range(i + 1, len(caixas)):
            pai_b, b = caixas[j]
            if pai_a != pai_b:
                continue
            limite = 0.0
            for eixo in (0, 1):
                distancia = abs((a[eixo] + a[eixo + 2]) - (b[eixo] + b[eixo + 2])) / 2
                meias = (a[eixo + 2] - a[eixo] + b[eixo + 2] - b[eixo]) / 2
                if meias:
                    limite = max(limite, (distancia - FOLGA_BORDA) / meias)
            dados[i][3] = min(dados[i][3], max(limite, 0.0))
            dados[j][3] = min(dados[j][3], max(limite, 0.0))


def gerar_modelo(origem: str, destino: str, papel: str, zonas_app,
                 tipologia: str, uso: str, aquecimento: bool) -> list:
    """Grava o modelo do `papel` em `destino` e devolve os avisos para o usuário."""
    texto = _read_text(origem)
    if not texto:
        raise OSError(f"IDF ilegível: {origem}")
    if papel not in PAPEIS:
        raise ValueError(f"Papel desconhecido: {papel}")
    idf = _Idf(texto)
    _verificar_suportado(idf)
    zonas_app = {zona.upper() for zona in zonas_app}
    if not zonas_app:
        raise ValueError("Escolha as zonas de permanência prolongada (APP) da avaliação.")
    faltando = zonas_app - {obj["campos"][0].upper() for obj in idf.todos("Zone")}
    if faltando:
        raise ValueError(f"Zona(s) {', '.join(sorted(faltando))} não existem no IDF.")

    avisos = []
    tipo = norma.TIPOLOGIAS[tipologia]
    _periodo_e_controle(idf)
    _agendas(idf, tipologia)
    _cargas_internas(idf, zonas_app, tipo["ocupacao"][uso], avisos)
    _hvac(idf, zonas_app, papel, aquecimento)
    _airflow(idf, zonas_app, papel, avisos)
    _saidas(idf)
    if papel == "referencia":
        _envoltoria_referencia(idf, zonas_app, avisos)
        ajustar_paf(idf, zonas_app, tipo["paf"], avisos)

    with open(destino, "w", encoding="latin-1") as arquivo:
        arquivo.write(idf.texto(f"Modelo {PAPEIS[papel].lower()} da INI-C gerado pelo Ambiens "
                                f"({tipo['nome']}, {uso})"))
    return avisos


def tem_aquecimento(origem: str) -> bool:
    """O projeto prevê aquecimento (o HVAC do IDF aquece)?"""
    return _tem_aquecimento(_Idf(_read_text(origem)))


def localizacao(origem: str):
    """`(latitude, longitude)` do `Site:Location`, ou `None`."""
    for obj in _Idf(_read_text(origem)).todos("Site:Location"):
        try:
            return float(obj["campos"][1]), float(obj["campos"][2])
        except (IndexError, ValueError):
            return None
    return None
