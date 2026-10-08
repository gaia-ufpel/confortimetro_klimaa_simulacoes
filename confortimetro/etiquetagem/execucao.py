"""Grupo de execuções da etiquetagem: gera os modelos, simula em sequência e dá a nota.

Cada modelo é uma execução comum do Ambiens no módulo somente EnergyPlus
(pasta própria, listada e comparável como as outras), marcada com
`config.etiquetagem`. A nota é gravada em `ETIQUETAGEM.json` em todas elas.
"""

import copy
import os
from queue import Queue

from confortimetro.etiquetagem import avaliacao, modelos, norma
from confortimetro.module_type import ModuleType
from confortimetro.paths import new_run_path

MODOS = {"condicionado": ("real", "referencia"),
         "hibrido": ("real", "real_vn", "referencia")}
MODELO = "modelo_inic.idf"


def aquecimento(zb: int, idf_path: str) -> bool:
    """A carga de aquecimento entra (C.I.3)?"""
    return int(zb) in norma.ZB_COM_AQUECIMENTO or modelos.tem_aquecimento(idf_path)


def _local_epw(epw_path: str):
    """`(latitude, longitude)` da linha LOCATION do EPW, ou `None`."""
    try:
        with open(epw_path, encoding="latin-1") as arquivo:
            campos = arquivo.readline().split(",")
        return float(campos[6]), float(campos[7])
    except (OSError, IndexError, ValueError):
        return None


def zona_sugerida(epw_path: str, idf_path: str = None):
    """`(ZB, "Cidade/UF")` pelo local do EPW (o clima simulado) ou, sem ele,
    pelo `Site:Location` do IDF; `(None, "")` se nenhum disser."""
    local = _local_epw(epw_path) if epw_path else None
    if local is None and idf_path:
        local = modelos.localizacao(idf_path)
    return norma.zona_bioclimatica(*local) if local else (None, "")


class EtiquetagemRun:
    """Mesma interface de `Simulation` (`run(q)`, `stop()`, `stop_requested`).

    `opcoes` = `{"tipologia", "uso", "modo", "zb"}`. Os modelos são gerados no
    construtor, para um IDF que a etiquetagem não suporta falhar antes de
    qualquer simulação; `self.execucoes` diz onde cada papel vai rodar.
    """

    def __init__(self, config, opcoes: dict, primeira: str = None):
        self.stop_requested = False
        self.simulation = None
        origem = config.source_idf_path or config.idf_path
        zonas = list(config.rooms or [])
        papeis = MODOS[opcoes["modo"]]
        com_aquecimento = aquecimento(opcoes["zb"], origem)

        primeira = primeira or new_run_path(root=config.runs_root_path)
        grupo = os.path.basename(primeira)
        self.execucoes, self.configs, self.avisos = {}, {}, []
        for papel in papeis:
            pasta = new_run_path(f"{grupo}_inic_{papel}", root=os.path.dirname(primeira)) \
                if papel != papeis[0] else primeira
            os.makedirs(pasta, exist_ok=True)
            idf = os.path.join(pasta, MODELO)
            avisos = modelos.gerar_modelo(origem, idf, papel, zonas, opcoes["tipologia"],
                                          opcoes["uso"], com_aquecimento)
            self.avisos += [aviso for aviso in avisos if aviso not in self.avisos]
            cfg = copy.deepcopy(config)
            cfg.module_type = ModuleType.ENERGYPLUS_ONLY
            cfg.source_idf_path = idf
            cfg.idf_path = idf
            cfg.output_path = pasta
            cfg.expanded_idf_path = os.path.join(pasta, "expanded.idf")
            # O período e o passo da tela não valem: a norma pede o ano inteiro.
            cfg.run_period_start = cfg.run_period_end = None
            cfg.nome = f"{config.nome or os.path.splitext(os.path.basename(origem))[0]}" \
                       f" · INI-C {modelos.PAPEIS[papel].lower()}"
            cfg.etiquetagem = {"grupo": grupo, "papel": papel, "zonas": zonas,
                               "aquecimento": com_aquecimento,
                               "idf_original": origem, **opcoes}
            self.execucoes[papel] = pasta
            self.configs[papel] = cfg
        self.primeira = primeira

    def run(self, q: Queue):
        from confortimetro.simulation import Simulation

        total = len(self.configs)
        for aviso in self.avisos:
            q.put(f"WARNING INI-C: {aviso}")
        for indice, (papel, cfg) in enumerate(self.configs.items()):
            if self.stop_requested:
                q.put("Simulação interrompida")
                return
            q.put(f"INI-C: modelo {modelos.PAPEIS[papel].lower()} "
                  f"({indice + 1} de {total})")
            interna = _Repasse(q, indice, total)
            self.simulation = Simulation(cfg)
            self.simulation.run(interna)
            if self.stop_requested:
                return

        q.put("INI-C: calculando a classificação da envoltória...")
        primeira = next(iter(self.configs.values()))
        resultado = avaliacao.avaliar(self.execucoes, primeira.rooms, primeira.etiquetagem["tipologia"],
                                      primeira.etiquetagem["zb"],
                                      primeira.etiquetagem["idf_original"], self.avisos)
        avaliacao.gravar(resultado, self.execucoes.values())
        q.put(resumo(resultado))
        q.put("EXIT")

    def stop(self):
        self.stop_requested = True
        if self.simulation is not None:
            self.simulation.stop()


class _Repasse:
    """Fila que repassa as mensagens de uma simulação do grupo à da GUI.

    O progresso vira o do grupo inteiro e o `EXIT` de cada uma fica retido:
    só o fim do grupo encerra.
    """

    def __init__(self, destino, indice, total):
        self.destino, self.indice, self.total = destino, indice, total

    def put(self, mensagem):
        if mensagem == "EXIT":
            return
        if isinstance(mensagem, str) and mensagem.startswith("PROGRESS "):
            parcial = float(mensagem.split()[1])
            mensagem = f"PROGRESS {(self.indice + parcial / 100) / self.total * 100:.1f}"
        self.destino.put(mensagem)


def resumo(resultado: dict) -> str:
    """Uma linha com a nota, para o log e a CLI."""
    texto = (f"INI-C: envoltória classe {resultado['classe']} — RedCgTT "
             f"{resultado['red_cgtt']:.1f} % (A > {resultado['limites']['A']:.1f} %, "
             f"B > {resultado['limites']['B']:.1f} %, C > {resultado['limites']['C']:.1f} %); "
             f"CgTT real {resultado['cgtt_real']:.0f} kWh/ano, referência "
             f"{resultado['cgtt_ref']:.0f} kWh/ano")
    if resultado.get("phoct") is not None:
        texto += f"; PHOCT {resultado['phoct']:.1f} %"
    return texto + "."
