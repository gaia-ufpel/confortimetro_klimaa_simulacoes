"""Classificação da envoltória a partir das execuções real e de referência.

Lê os ESO dos modelos gerados por `modelos.gerar_modelo` e aplica o item 8.2.1
da INI-C: carga térmica total anual das APP (CgTT), redução em relação à
referência (RedCgTT) e a classe pelos limites do coeficiente CRCgTT. No modo
híbrido, a carga de refrigeração de cada APP é ponderada pela fração de
horas em que a ventilação natural não dá conta (FHdesc, a partir do PHOCT),
e PHOCT ≥ 90 % dá A direto (nota do C.I.7).
"""

import json
import os

import esoreader

from confortimetro.etiquetagem import modelos, norma

ARQUIVO = "ETIQUETAGEM.json"
SUFIXO_IDEAL = " IDEAL LOADS AIR SYSTEM"
J_POR_KWH = 3.6e6


def _series(eso, variavel):
    """`{chave: valores horários}` de uma variável do ESO."""
    return {chave.upper(): eso.data[eso.dd.index[(frequencia, chave, nome)]]
            for frequencia, chave, nome in eso.dd.index
            if nome == variavel and frequencia == "Hourly"}


def cargas(caminho_eso: str, zonas_app) -> dict:
    """`{zona: {"resfriamento", "aquecimento", "total"}}` em kWh/ano."""
    eso = esoreader.read_from_path(caminho_eso)
    frio = _series(eso, modelos.VARIAVEIS[0])
    calor = _series(eso, modelos.VARIAVEIS[1])
    resultado = {}
    for zona in sorted(zonas_app):
        chave = zona.upper() + SUFIXO_IDEAL
        if chave not in frio:
            raise ValueError(f"A saída não tem a carga do sistema ideal da zona {zona}.")
        resfriamento = sum(frio[chave]) / J_POR_KWH
        aquecimento = sum(calor.get(chave, [])) / J_POR_KWH
        resultado[zona.upper()] = {"resfriamento": resfriamento,
                                   "aquecimento": aquecimento,
                                   "total": resfriamento + aquecimento}
    return resultado


def phoct(caminho_eso: str, zonas_app) -> dict:
    """`{zona: % de horas ocupadas em conforto}` pelo modelo adaptativo (C.I.6)."""
    eso = esoreader.read_from_path(caminho_eso)
    ocupacao = _series(eso, "Schedule Value").get(modelos.OCUPACAO)
    medias = list(_series(eso, modelos.VARIAVEIS[3]).values())
    operativas = _series(eso, modelos.VARIAVEIS[2])
    if ocupacao is None or not medias:
        raise ValueError("A saída do modelo ventilado não tem a rotina de ocupação "
                         "ou a média externa do modelo adaptativo.")
    # A média móvel externa é do clima: igual em todo People.
    media = medias[0]
    resultado = {}
    for zona in sorted(zonas_app):
        temperaturas = operativas.get(zona.upper())
        if temperaturas is None:
            raise ValueError(f"A saída não tem a temperatura operativa da zona {zona}.")
        horas = [hora for hora, valor in enumerate(ocupacao) if valor > 0.5]
        conforto = sum(norma.conforto_adaptativo(temperaturas[hora], media[hora])
                       for hora in horas)
        resultado[zona.upper()] = 100.0 * conforto / len(horas) if horas else 0.0
    return resultado


def avaliar(execucoes: dict, zonas_app, tipologia: str, zb: int, idf_original: str,
            avisos=()) -> dict:
    """Resultado da etiquetagem da envoltória.

    `execucoes` é `{papel: pasta da execução}`; o modo é híbrido quando há
    `real_vn`. O fator de forma vem da geometria do IDF original.
    """
    with open(idf_original, encoding="latin-1") as arquivo:
        geometria = modelos.geometria(arquivo.read())
    limites = norma.limites_envoltoria(tipologia, zb, geometria["ff"])

    real = cargas(os.path.join(execucoes["real"], "eplusout.eso"), zonas_app)
    referencia = cargas(os.path.join(execucoes["referencia"], "eplusout.eso"), zonas_app)
    hibrido = "real_vn" in execucoes
    conforto = (phoct(os.path.join(execucoes["real_vn"], "eplusout.eso"), zonas_app)
                if hibrido else {})

    zonas, cgtt_real, cgtt_ref = [], 0.0, 0.0
    for zona in sorted(real):
        fhdesc = (100.0 - conforto[zona]) / 100.0 if hibrido else 1.0
        # O FHdesc desconta só a refrigeração (Equação C.I.6).
        carga_real = real[zona]["resfriamento"] * fhdesc + real[zona]["aquecimento"]
        cgtt_real += carga_real
        cgtt_ref += referencia[zona]["total"]
        zonas.append({"zona": zona, "area": geometria["areas_piso"].get(zona, 0.0),
                      "real": real[zona], "referencia": referencia[zona],
                      "phoct": conforto.get(zona), "fhdesc": fhdesc if hibrido else None,
                      "cgtt_real": carga_real})

    red_cgtt = (cgtt_ref - cgtt_real) / cgtt_ref * 100 if cgtt_ref else 0.0
    classe = norma.classe_envoltoria(red_cgtt, limites)
    phoct_edificio = None
    if hibrido:
        area_total = sum(zona["area"] for zona in zonas)
        phoct_edificio = (sum(zona["phoct"] * zona["area"] for zona in zonas) / area_total
                          if area_total else sum(zona["phoct"] for zona in zonas) / len(zonas))
        if phoct_edificio >= norma.PHOCT_A:
            classe = "A"

    return {
        "classe": classe,
        "red_cgtt": red_cgtt,
        "cgtt_real": cgtt_real,
        "cgtt_ref": cgtt_ref,
        "limites": limites,
        "modo": "hibrido" if hibrido else "condicionado",
        "phoct": phoct_edificio,
        "tipologia": tipologia,
        "zb": zb,
        "ff": geometria["ff"],
        "area_envoltoria": geometria["area_envoltoria"],
        "volume": geometria["volume"],
        "zonas": zonas,
        "execucoes": {papel: os.path.basename(os.path.normpath(caminho))
                      for papel, caminho in execucoes.items()},
        "avisos": list(avisos),
        "aviso_estimativa": norma.AVISO_ESTIMATIVA,
    }


def gravar(resultado: dict, pastas) -> None:
    """Grava o resultado em cada execução do grupo."""
    for pasta in pastas:
        with open(os.path.join(pasta, ARQUIVO), "w", encoding="utf-8") as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=2)


def ler(pasta: str):
    """Resultado gravado numa execução, ou `None`."""
    try:
        with open(os.path.join(pasta, ARQUIVO), encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        return None
