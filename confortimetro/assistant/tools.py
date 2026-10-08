"""Ferramentas que o modelo chama para ler as execuções — só de leitura.

A exceção é `propor_simulacao`, que também não roda nada: monta e valida uma
proposta que fica pendente até o usuário confirmar na interface
(`simulacao.py`).

Rodam na máquina do usuário sobre `results/`; ao modelo vai só o recorte
pedido, nunca a planilha. Toda saída passa por `_limit`, para que uma série
anual não estoure o contexto.
"""

import ast
import json
import math
import os

import pandas

from .. import control
from ..control import MODULES_MAPPER, motivos
from ..idf.processor import _iter_objects, _read_text
from ..results import compare, series, tabular
from ..results.database import is_failed, is_interrupted
from ..versao import code_version
from . import normas, simulacao

MAX_ROWS = 200
MAX_BYTES = 20_000

OPERATORS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">": lambda s, v: s > v,
    ">=": lambda s, v: s >= v,
    "<": lambda s, v: s < v,
    "<=": lambda s, v: s <= v,
}

# A coluna de data não entra em agregação nem filtro.
VARIABLES = [name for name in (*series.COLUMNS, *series.COMPUTED) if name != "data"]

FREQUENCIES = {"hora": "h", "dia": "D", "mes": "MS"}

# O que o controlador lê e decide a cada timestep.
CONTROL_VARIABLES = [
    "ocupacao", "temp_externa", "temp_ar", "temp_operativa", "temp_radiante",
    "pmv", "pmv_controle", "clo", "clo_controle", "temp_neutra", "adap_min", "adap_max",
    "temp_op_max_adap", "janela", "ventilador", "velocidade_ar", "ac",
    "setpoint_aquecimento", "setpoint_resfriamento", "aquecimento", "resfriamento",
    "doas", "vazao_doas", "co2", "em_conforto",
]

# J por timestep nas planilhas; as colunas `*_w` já são W médios.
# Arquivo de cada módulo de controle. No executável do Windows os .py vão
# como dados ao lado dos .pyc (datas do .spec), então o caminho vale lá também.
CODE_FILES = {
    **{str(module): cls.__module__.rsplit(".", 1)[-1]
       for module, cls in MODULES_MAPPER.items()},
    "base": "base",
    "motivos": "motivos",
}

ENERGY_VARIABLES = ("aquecimento", "resfriamento", "janelas_ganho", "janelas_perda")

# Seleção aceita por `sinais_controle(colunas=...)`.
CONTROL_COLUMNS = CONTROL_VARIABLES + ["motivo"]
# Uma mudança numa destas abre uma linha em `apenas_mudancas`.
CHANGE_COLUMNS = ("janela", "ventilador", "ac", "doas", "setpoint_aquecimento",
                  "setpoint_resfriamento", "motivo")

# Componentes do balanço do ar da zona (W; positivo = calor entrando no ar).
BALANCE_COLUMNS = [name for name in series.COLUMNS if name.startswith("balanco_")]

_RUN_ZONE = {"execucao": {"type": "string"}, "zona": {"type": "string"}}

_PERIOD = {
    "inicio": {"type": "string", "description": "Início, AAAA-MM-DD ou MM-DD (inclusive)."},
    "fim": {"type": "string", "description": "Fim, AAAA-MM-DD ou MM-DD (inclusive)."},
}

DECLARATIONS = [
    {
        "name": "listar_execucoes",
        "description": "Lista as execuções disponíveis com status, módulo, IDF, EPW e zonas.",
        "parameters_json_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "configuracao",
        "description": "Configuração completa (configs.json) de uma execução.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {"execucao": {"type": "string"}},
            "required": ["execucao"],
        },
    },
    {
        "name": "indicadores",
        "description": ("Estatísticas por zona do ESTATISTICAS.xlsx: energia (kWh), "
                        "desconforto, PMV, horas fora da banda adaptativa, uso de janela, "
                        "ventilador, DOAS, CO2 e timesteps simulados."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {"execucao": {"type": "string"},
                           "zona": {"type": "string", "description": "Opcional."}},
            "required": ["execucao"],
        },
    },
    {
        "name": "comparar",
        "description": ("Tabela comparativa de várias execuções: indicadores por zona e "
                        "os parâmetros de cada cenário. Avisa se os períodos diferem."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {"execucoes": {"type": "array", "items": {"type": "string"}},
                           "zona": {"type": "string", "description": "Opcional."}},
            "required": ["execucoes"],
        },
    },
    {
        "name": "serie_agregada",
        "description": ("Série temporal de uma zona agregada por hora, dia ou mês "
                        "(média, mínimo, máximo). aquecimento, resfriamento e janelas_ganho/perda "
                        "saem em kWh somados no intervalo; as colunas *_w já são W. "
                        "Variáveis: " + ", ".join(VARIABLES) + "."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "execucao": {"type": "string"},
                "zona": {"type": "string"},
                "variaveis": {"type": "array", "items": {"type": "string", "enum": VARIABLES}},
                "agregacao": {"type": "string", "enum": list(FREQUENCIES)},
                "somente_ocupado": {"type": "boolean",
                                    "description": "Só timesteps com ocupação > 0."},
                **_PERIOD,
            },
            "required": ["execucao", "zona", "variaveis", "agregacao"],
        },
    },
    {
        "name": "horas_em_condicao",
        "description": ("Horas de uma zona em que todas as condições valem (E), no total "
                        "e por mês. Ex.: AC ligado com sala ocupada = "
                        "[{coluna: ac, operador: ==, valor: 1}, "
                        "{coluna: ocupacao, operador: >, valor: 0}]."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "execucao": {"type": "string"},
                "zona": {"type": "string"},
                "condicoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "coluna": {"type": "string", "enum": VARIABLES},
                            "operador": {"type": "string", "enum": list(OPERATORS)},
                            "valor": {"type": "number"},
                        },
                        "required": ["coluna", "operador", "valor"],
                    },
                },
                **_PERIOD,
            },
            "required": ["execucao", "zona", "condicoes"],
        },
    },
    {
        "name": "inspecionar_zona",
        "description": ("Características físicas da zona (relatórios do EnergyPlus e IDF): "
                        "área, volume, pé-direito, cargas internas nominais (W/m², m²/pessoa), "
                        "superfícies externas com U, área, azimute e orientação, janelas "
                        "(área, U, SHGC), WWR por orientação e superfícies de infiltração "
                        "do AirflowNetwork."),
        "parameters_json_schema": {"type": "object", "properties": _RUN_ZONE,
                                   "required": ["execucao", "zona"]},
    },
    {
        "name": "balanco_termico",
        "description": ("Balanço de calor da zona. Pela série (execuções novas), no "
                        "período pedido: kWh de ganho e de perda de cada componente do "
                        "balanço do ar (ganhos internos, superfícies, entre zonas, ar "
                        "externo/infiltração/janela, sistema, armazenamento) e ganho/perda "
                        "pelas janelas. Pelo relatório anual do EnergyPlus (Sensible Heat "
                        "Gain Summary): kWh por mecanismo no período simulado todo e W nos "
                        "picos. Execuções antigas só têm o relatório anual (sem recorte)."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {**_RUN_ZONE, **_PERIOD,
                           "somente_ocupado": {"type": "boolean",
                                               "description": "Só timesteps ocupados."}},
            "required": ["execucao", "zona"]},
    },
    {
        "name": "inspecionar_hvac",
        "description": ("PTHP e DOAS da zona: capacidades nominais das serpentinas (W), "
                        "vazão dos ventiladores (m³/s), carga de projeto, horas de setpoint "
                        "não atendido do EnergyPlus e, pela série, potência entregue a cada "
                        "timestep comparada à capacidade (pico, horas acima de 90%). "
                        "Execuções novas: demanda × entrega × capacidade com AC ligado "
                        "(horas com demanda acima da capacidade, entrega < 90% da demanda, "
                        "resistência de apoio ligada, pico de demanda)."),
        "parameters_json_schema": {"type": "object", "properties": {**_RUN_ZONE, **_PERIOD},
                                   "required": ["execucao", "zona"]},
    },
    {
        "name": "sinais_controle",
        "description": ("Sinais do controlador timestep a timestep num período curto: "
                        "PMV calculado, clo escolhido, velocidade do ar, setpoints de "
                        "aquecimento/resfriamento do AC, banda adaptativa, estados de "
                        "janela/ventilador/AC/DOAS, temperaturas e potência do PTHP (W). "
                        "Execuções novas trazem motivo (bits) e motivos (nomes decodificados "
                        "de cada decisão); nas antigas deduza das colunas. Resumo: horas com "
                        "AC ligado abaixo/acima do setpoint, faixa dos setpoints e horas por "
                        "motivo. Para períodos longos use apenas_mudancas e colunas."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {**_RUN_ZONE, **_PERIOD,
                           "somente_ocupado": {"type": "boolean"},
                           "apenas_mudancas": {
                               "type": "boolean",
                               "description": ("Só timesteps em que janela, ventilador, AC, "
                                               "DOAS, setpoints ou motivo mudaram, com "
                                               "duracao_h até a próxima mudança. Com "
                                               "colunas, só as mudanças dessas contam.")},
                           "colunas": {"type": "array",
                                       "items": {"type": "string", "enum": CONTROL_COLUMNS},
                                       "description": "Subconjunto das colunas devolvidas."}},
            "required": ["execucao", "zona", "inicio"],
        },
    },
    {
        "name": "serie_timestep",
        "description": ("Série sem agregação, um valor por timestep (ex.: 10 min), para "
                        "ver dinâmica curta como a partida a frio. Use períodos de poucos "
                        "dias. aquecimento, resfriamento e janelas_ganho/perda saem em W "
                        "médios no timestep; motivo vem também decodificado em motivos. "
                        "Variáveis: " + ", ".join(VARIABLES) + "."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                **_RUN_ZONE,
                "variaveis": {"type": "array", "items": {"type": "string", "enum": VARIABLES}},
                "somente_ocupado": {"type": "boolean"},
                **_PERIOD,
            },
            "required": ["execucao", "zona", "variaveis", "inicio"],
        },
    },
    {
        "name": "codigo_controle",
        "description": ("Código-fonte do controlador, com números de linha, para conferir "
                        "se o comportamento observado (sinais_controle, motivos) bate com "
                        "o implementado ou revela erro. arquivo = um módulo (COMPLETE, …), "
                        "'base' (funções comuns: PMV, janela, setpoints, escrita) ou "
                        "'motivos' (bits). Sem `funcoes`, módulo e motivos vêm inteiros e "
                        "a base vem como índice de funções; peça as da base pelo nome. "
                        "É o código da versão instalada (versao_instalada); compare com o "
                        "code_version da configuracao da execução."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "arquivo": {"type": "string", "enum": [*CODE_FILES]},
                "funcoes": {"type": "array", "items": {"type": "string"},
                            "description": "Nomes de funções/métodos daquele arquivo."},
            },
            "required": ["arquivo"],
        },
    },
    {
        "name": "guia_norma",
        "description": ("Guia (skill) do PBE Edifica: mapa da Portaria Inmetro 309/2022 "
                        "(INI-C, INI-R, RAC) com páginas, siglas, como a envoltória é "
                        "classificada e o que a etiquetagem do Ambiens implementa e "
                        "simplifica, com as tabelas por tipologia que ele usa. Leia antes "
                        "de responder sobre norma, etiquetagem, ENCE ou classe."),
        "parameters_json_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "buscar_norma",
        "description": ("Busca no texto integral das normas (sem acento nem caixa) e devolve "
                        "as páginas que mais casam, com trechos. Termos separados por "
                        "espaço; frase exata entre aspas (\"Tabela 8.16\", \"fator de "
                        "forma\")."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "termos": {"type": "string"},
                "documento": {"type": "string", "enum": list(normas.DOCUMENTOS)},
                "limite": {"type": "integer", "description": "Páginas (padrão 6)."},
            },
            "required": ["termos"],
        },
    },
    {
        "name": "ler_norma",
        "description": ("Texto de páginas inteiras de uma norma (até 4), para tabelas, "
                        "equações e o contexto de um trecho de buscar_norma."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "documento": {"type": "string", "enum": list(normas.DOCUMENTOS)},
                "pagina": {"type": "integer"},
                "ate": {"type": "integer", "description": "Última página (opcional)."},
            },
            "required": ["documento", "pagina"],
        },
    },
    {
        "name": "etiquetagem",
        "description": ("Resultado da etiquetagem INI-C de uma execução do grupo (classe, "
                        "RedCgTT, limites, CgTT real e de referência por zona, PHOCT, "
                        "avisos dos modelos) e as opções usadas (tipologia, uso, modo, ZB, "
                        "fachada)."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {"execucao": {"type": "string"}},
            "required": ["execucao"],
        },
    },
    {
        "name": "propor_simulacao",
        "description": ("Propõe uma simulação nova ao usuário — NÃO a executa. Parte da "
                        "configuração atual da tela de execução ou, com base_execucao, da "
                        "configuração de uma execução existente (como o Duplicar), aplica "
                        "as alterações e valida (arquivos, EnergyPlus, zonas do IDF, "
                        "equipamento). Válida, a interface mostra a configuração e só roda "
                        "se o usuário confirmar; inválida, devolve o erro para corrigir. "
                        "O período vem do RunPeriod do IDF e não é alterável aqui. Use só "
                        "quando o usuário pedir para rodar/simular; depois diga que a "
                        "confirmação está na tela, nunca que a simulação começou."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "base_execucao": {"type": "string",
                                  "description": "Execução cuja configuração é a base."},
                "alteracoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "campo": {"type": "string",
                                      "enum": list(simulacao.EDITABLE_FIELDS)},
                            "valor": {"type": "string",
                                      "description": "Como no --set do CLI: JSON quando "
                                                     "der (1.3, true, [\"SALA1\"])."},
                        },
                        "required": ["campo", "valor"],
                    },
                },
                "motivo": {"type": "string",
                           "description": "Uma frase: o que o usuário quer testar."},
            },
        },
    },
]


class ToolError(Exception):
    """Erro de uso da ferramenta: volta ao modelo como texto para ele corrigir."""


def _clean(value):
    """Valor serializável em JSON, com floats arredondados."""
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, 4)
    if isinstance(value, pandas.Timestamp):
        return value.isoformat(sep=" ")
    if hasattr(value, "item"):  # numpy
        return _clean(value.item())
    return value


def _records(df: pandas.DataFrame) -> list:
    return [{key: _clean(value) for key, value in row.items()}
            for row in df.to_dict(orient="records")]


def _limit(result: dict) -> dict:
    """Corta `linhas` até caber em MAX_ROWS e MAX_BYTES, avisando o modelo."""
    rows = result.get("linhas")
    if isinstance(rows, list):
        total = len(rows)
        rows = rows[:MAX_ROWS]
        while rows and len(json.dumps(rows, ensure_ascii=False, default=str)) > MAX_BYTES:
            rows = rows[:len(rows) // 2]
        if len(rows) < total:
            result["linhas"] = rows
            result["aviso"] = (f"Resultado cortado: {len(rows)} de {total} linhas. "
                               "Use agregação maior ou um período menor.")
    return result


class Toolbox:
    """Ferramentas sobre as execuções de uma pasta raiz."""

    def __init__(self, root: str, base_config=None):
        self.root = root
        # Configuração da tela de execução no momento da pergunta — lida na
        # thread do Tk, nunca daqui.
        self.base_config = base_config
        # Propostas criadas nesta pergunta; a conversa as guarda ao terminar.
        self.proposals = []

    def run_path(self, name: str) -> str:
        """Pasta da execução, recusando nomes que saiam da raiz."""
        if not name or os.path.basename(name) != name or name in (".", ".."):
            raise ToolError(f"Nome de execução inválido: {name!r}.")
        path = os.path.join(self.root, name)
        if not compare.is_run(path):
            raise ToolError(f"Execução {name!r} não encontrada. Use listar_execucoes.")
        return path

    def call(self, name: str, args: dict) -> dict:
        """Executa a ferramenta; erros viram `{"erro": ...}` para o modelo."""
        method = getattr(self, name, None)
        if name not in {d["name"] for d in DECLARATIONS} or method is None:
            return {"erro": f"Ferramenta desconhecida: {name}."}
        try:
            return _limit(method(**(args or {})))
        except ToolError as error:
            return {"erro": str(error)}
        except TypeError as error:
            return {"erro": f"Argumentos inválidos: {error}"}
        except Exception as error:  # planilha corrompida, formato antigo…
            return {"erro": f"{type(error).__name__}: {error}"}

    # --- Ferramentas ---

    def listar_execucoes(self) -> dict:
        runs = compare.list_runs(self.root)
        return {"linhas": [{
            "execucao": run["run"],
            "status": ("interrompida" if is_interrupted(run)
                       else "falhou" if is_failed(run) else run["status"]),
            "modulo": run["module_type"], "idf": run["idf"], "epw": run["epw"],
            "zonas": run["rooms_disponiveis"],
            "modificado": run["modificado"].strftime("%Y-%m-%d %H:%M"),
        } for run in runs]}

    def configuracao(self, execucao: str) -> dict:
        return {"execucao": execucao,
                "configuracao": compare.read_config(self.run_path(execucao))}

    def indicadores(self, execucao: str, zona: str = None) -> dict:
        path = self.run_path(execucao)
        stats_path = os.path.join(path, "ESTATISTICAS.xlsx")
        if is_interrupted(compare.read_run(path)):
            raise ToolError(f"{execucao} foi interrompida antes de gerar resultados; "
                            "não há o que regerar. Rode a simulação de novo.")
        if not os.path.exists(stats_path):
            raise ToolError(f"{execucao} não tem ESTATISTICAS.xlsx; é preciso regerar "
                            "as estatísticas na tela de Execuções.")
        df = pandas.read_excel(stats_path)
        if zona:
            df = df[df["Nome da sala"] == zona]
            if df.empty:
                raise ToolError(f"Zona {zona!r} não está em {execucao}.")
        return {"execucao": execucao, "linhas": _records(df)}

    def comparar(self, execucoes: list, zona: str = None) -> dict:
        paths = [self.run_path(name) for name in execucoes]
        df = compare.compare_runs(paths, room=zona)
        if df.empty:
            raise ToolError("Nenhuma execução com estatísticas completas para comparar.")
        missing = sorted(set(execucoes) - set(df["Execução"]))
        result = {"linhas": _records(df)}
        if missing:
            result["sem_estatisticas"] = missing
        mismatched = compare.mismatched_periods(df)
        if mismatched:
            result["periodo_diferente"] = mismatched
        return result

    def _series(self, execucao, zona, inicio=None, fim=None, somente_ocupado=False):
        path = self.run_path(execucao)
        info = compare.read_run(path)
        if zona not in info["rooms_disponiveis"]:
            raise ToolError(f"Zona {zona!r} sem planilha em {execucao}. "
                            f"Zonas: {', '.join(info['rooms_disponiveis']) or 'nenhuma'}.")
        df = series.load_zone_series(path, zona).copy()
        df["data"] = pandas.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"]).set_index("data").sort_index()
        df = _filter_period(df, inicio, fim)
        if somente_ocupado:
            df = df[df["ocupacao"] > 0]
        if df.empty:
            raise ToolError("Nenhum timestep no período/filtro pedido.")
        return df

    def serie_agregada(self, execucao, zona, variaveis, agregacao,
                       inicio=None, fim=None, somente_ocupado=False) -> dict:
        if agregacao not in FREQUENCIES:
            raise ToolError(f"agregacao deve ser uma de {list(FREQUENCIES)}.")
        df = self._series(execucao, zona, inicio, fim, somente_ocupado)
        if "motivo" in variaveis:
            raise ToolError("motivo é soma de bits e não se agrega; use horas_por_motivo "
                            "do sinais_controle.")
        present = _present(df, variaveis, zona)
        grouped = df[present].resample(FREQUENCIES[agregacao])
        energy = [v for v in present if v in ENERGY_VARIABLES]
        others = [v for v in present if v not in energy]
        parts = []
        if others:
            stats = grouped[others].agg(["mean", "min", "max"])
            labels = {"mean": "media", "min": "min", "max": "max"}
            stats.columns = [f"{name}_{labels[stat]}" for name, stat in stats.columns]
            parts.append(stats)
        if energy:
            # As planilhas guardam energia em J por timestep.
            parts.append((grouped[energy].sum() / 3.6e6).add_suffix("_kwh"))
        out = pandas.concat(parts, axis=1).dropna(how="all").reset_index()
        out["data"] = out["data"].dt.strftime(
            {"hora": "%Y-%m-%d %H:00", "dia": "%Y-%m-%d", "mes": "%Y-%m"}[agregacao])
        return {"execucao": execucao, "zona": zona, "agregacao": agregacao,
                "periodo": _period_label(df), "linhas": _records(out)}

    def horas_em_condicao(self, execucao, zona, condicoes, inicio=None, fim=None) -> dict:
        if not condicoes:
            raise ToolError("Informe ao menos uma condição.")
        df = self._series(execucao, zona, inicio, fim)
        mask = pandas.Series(True, index=df.index)
        for condition in condicoes:
            column = condition.get("coluna")
            operator = OPERATORS.get(condition.get("operador"))
            if column not in VARIABLES or operator is None:
                raise ToolError(f"Condição inválida: {condition}. Colunas: {VARIABLES}; "
                                f"operadores: {list(OPERATORS)}.")
            if column not in df.columns:
                raise ToolError(f"A planilha de {zona} não tem a coluna {column}.")
            mask &= operator(df[column], float(condition.get("valor")))

        step_hours = _step_hours(df.index)
        monthly = mask.groupby(df.index.to_period("M")).agg(["sum", "size"])
        return {
            "execucao": execucao, "zona": zona, "periodo": _period_label(df),
            "condicoes": condicoes,
            "horas": round(float(mask.sum()) * step_hours, 2),
            "horas_no_periodo": round(len(mask) * step_hours, 2),
            "linhas": [{"mes": str(month), "horas": round(float(row["sum"]) * step_hours, 2),
                        "horas_no_mes": round(float(row["size"]) * step_hours, 2)}
                       for month, row in monthly.iterrows()],
        }

    def serie_timestep(self, execucao, zona, variaveis, inicio, fim=None,
                       somente_ocupado=False) -> dict:
        df = self._series(execucao, zona, inicio, fim or inicio, somente_ocupado)
        return {"execucao": execucao, "zona": zona, "periodo": _period_label(df),
                "linhas": _timestep_rows(df[_present(df, variaveis, zona)])}

    def sinais_controle(self, execucao, zona, inicio, fim=None, somente_ocupado=False,
                        apenas_mudancas=False, colunas=None) -> dict:
        df = self._series(execucao, zona, inicio, fim or inicio, somente_ocupado)
        unknown = [c for c in colunas or [] if c not in CONTROL_COLUMNS]
        if unknown:
            raise ToolError(f"Colunas desconhecidas: {unknown}. Use {CONTROL_COLUMNS}.")
        wanted = colunas or CONTROL_COLUMNS
        columns = [c for c in wanted if c in df.columns]
        if not columns:
            raise ToolError(f"Nenhuma das colunas está na planilha de {zona}.")
        avisos = []
        missing = [c for c in colunas or [] if c not in df.columns]
        if missing:
            avisos.append(f"A planilha não tem {', '.join(missing)}.")
        if "motivo" not in df:
            avisos.append("Execução anterior ao registro do motivo: deduza das colunas.")

        rows = df[columns]
        if apenas_mudancas:
            # Mudança de estado ou buraco na série (somente_ocupado) abre um trecho.
            # Com `colunas`, só os estados pedidos contam: o AC liga e desliga
            # quase a cada timestep e esconderia as trocas de janela.
            watched = [c for c in CHANGE_COLUMNS if c in df and c in columns] or \
                [c for c in CHANGE_COLUMNS if c in df]
            watched = df[watched].fillna(-1)
            gap = df.index.to_series().diff() > pandas.Timedelta(hours=_step_hours(df.index))
            start = (watched.ne(watched.shift()).any(axis=1) | gap).to_numpy(copy=True)
            start[0] = True
            durations = pandas.Series(start.cumsum()).value_counts(sort=False).sort_index()
            rows = rows[start]
        result = {"execucao": execucao, "zona": zona, "periodo": _period_label(df),
                  "linhas": _timestep_rows(rows)}
        if apenas_mudancas:
            hours = _step_hours(df.index)
            for row, count in zip(result["linhas"], durations):
                row["duracao_h"] = round(count * hours, 2)
        result["resumo"] = _control_summary(df)
        if avisos:
            result["avisos"] = avisos
        return result

    def _zone_tables(self, execucao, zona):
        path = self.run_path(execucao)
        try:
            tables = tabular.read_tables(path)
        except FileNotFoundError as error:
            raise ToolError(f"{error}; a execução não guardou os relatórios do "
                            "EnergyPlus.") from error
        zones = [row["nome"] for row in tabular.table(
            tables, "Input Verification and Results Summary", "Zone Summary")]
        if zona.upper() not in zones:
            raise ToolError(f"Zona {zona!r} não está nos relatórios de {execucao}. "
                            f"Zonas: {', '.join(zones)}.")
        return path, tables, zona.upper()

    def inspecionar_zona(self, execucao, zona) -> dict:
        path, tables, zone = self._zone_tables(execucao, zona)
        (summary,) = [row for row in tabular.table(
            tables, "Input Verification and Results Summary", "Zone Summary")
            if row["nome"] == zone]
        area, volume = summary.get("Area [m2]"), summary.get("Volume [m3]")
        per_person = summary.get("People [m2 per person]")
        summary = {**summary,
                   "pe_direito_m": _ratio(volume, area),
                   "pessoas_por_m2": _ratio(1, per_person)}

        surfaces, afn = _zone_surfaces(path, zone)
        opaque = [row for row in tabular.table(tables, "Envelope Summary", "Opaque Exterior")
                  if row["nome"] in surfaces]
        doors = [row for row in tabular.table(tables, "Envelope Summary", "Exterior Door")
                 if row["nome"] in surfaces]
        windows = [row for row in tabular.table(tables, "Envelope Summary",
                                                "Exterior Fenestration")
                   if row.get("Parent Surface") in surfaces]

        by_direction = {}
        for row in opaque:
            if row.get("Tilt [deg]") == 90.0:  # só paredes entram no WWR
                entry = by_direction.setdefault(row["Cardinal Direction"],
                                                {"parede_bruta_m2": 0.0, "vidro_m2": 0.0})
                entry["parede_bruta_m2"] += row.get("Gross Area [m2]") or 0.0
        for row in windows:
            entry = by_direction.setdefault(row["Cardinal Direction"],
                                            {"parede_bruta_m2": 0.0, "vidro_m2": 0.0})
            entry["vidro_m2"] += row.get("Glass Area [m2]") or 0.0
        wwr = [{"direcao": key, **{k: round(v, 2) for k, v in value.items()},
                "wwr": _ratio(value["vidro_m2"], value["parede_bruta_m2"])}
               for key, value in sorted(by_direction.items())]

        return {"execucao": execucao, "zona": zone, "zona_resumo": summary,
                "superficies_externas": opaque, "portas_externas": doors,
                "janelas": windows, "wwr_por_direcao": wwr,
                "airflownetwork_superficies": [
                    {"superficie": fields[0], "componente": fields[1]}
                    for fields in afn]}

    def balanco_termico(self, execucao, zona, inicio=None, fim=None,
                        somente_ocupado=False) -> dict:
        result, avisos = {"execucao": execucao, "zona": zona}, []
        try:
            df = self._series(execucao, zona, inicio, fim, somente_ocupado)
        except (ToolError, ValueError, FileNotFoundError) as error:
            df = None
            avisos.append(f"Série indisponível: {error}")
        if df is not None and any(c in df for c in BALANCE_COLUMNS):
            hours = _step_hours(df.index)
            def kwh(values):
                return round(float(values.sum()) * hours / 1000, 3)
            air = {}
            for name in BALANCE_COLUMNS:
                if name in df:
                    values = df[name].fillna(0)
                    air[name.removeprefix("balanco_").removesuffix("_w")] = {
                        "ganho": kwh(values.clip(lower=0)),
                        "perda": kwh(values.clip(upper=0)),
                        "liquido": kwh(values)}
            result["serie"] = {"periodo": _period_label(df),
                               "somente_ocupado": bool(somente_ocupado),
                               "ar_da_zona_kwh": air}
            windows = [c for c in ("janelas_ganho", "janelas_perda") if c in df]
            if windows:
                # J por timestep; a perda vem positiva do EnergyPlus.
                result["serie"]["janelas_kwh"] = {
                    c.removeprefix("janelas_"): round(float(df[c].sum()) / 3.6e6, 3)
                    for c in windows}
        elif df is not None:
            avisos.append("Execução anterior às colunas de balanço por timestep: só o "
                          "relatório anual, que ignora inicio, fim e somente_ocupado.")

        try:
            _, tables, zone = self._zone_tables(execucao, zona)
        except ToolError as error:
            tables = None
            avisos.append(str(error))
        report = "Sensible Heat Gain Summary"
        if tables is not None:
            def pick(title):
                return next((row for row in tabular.table(tables, report, title)
                             if row["nome"] == zone), None)
            annual = pick("Annual Building Sensible Heat Gain Components")
            if annual is None:
                avisos.append(f"{execucao} não tem o relatório {report}.")
            else:
                result["relatorio_anual"] = {
                    "periodo": "todo o período simulado (sem os dias de aquecimento)",
                    "total_kwh": annual,
                    "pico_aquecimento_w": pick("Peak Heating Sensible Heat Gain Components"),
                    "pico_resfriamento_w": pick("Peak Cooling Sensible Heat Gain Components")}
        if "serie" not in result and "relatorio_anual" not in result:
            raise ToolError(" ".join(avisos))
        if avisos:
            result["avisos"] = avisos
        return result

    def inspecionar_hvac(self, execucao, zona, inicio=None, fim=None) -> dict:
        _, tables, zone = self._zone_tables(execucao, zona)
        def own(name):
            return str(name).split(" ")[0] in (zone, f"DOAS_{zone}")
        def pick(report, title):
            return [row for row in tabular.table(tables, report, title)
                    if own(row["nome"])]
        equipment = {title: pick("Equipment Summary", title)
                     for title in ("Cooling Coils", "Heating Coils", "DX Heating Coils",
                                   "Fans")}
        result = {
            "execucao": execucao, "zona": zone,
            "equipamentos": equipment,
            "carga_projeto": {title: pick("HVAC Sizing Summary", title)
                              for title in ("Zone Sensible Heating", "Zone Sensible Cooling")},
            "doas": pick("System Summary", "Economizer"),
            "setpoint_nao_atendido_h": pick("System Summary", "Time Setpoint Not Met"),
        }
        capacity = {
            "aquecimento": sum(row.get("Nominal Total Capacity [W]") or 0
                               for row in equipment["Heating Coils"]),
            "resfriamento": sum(row.get("Nominal Total Capacity [W]") or 0
                                for row in equipment["Cooling Coils"]),
        }
        try:
            df = self._series(execucao, zona, inicio, fim)
        except (ToolError, ValueError, FileNotFoundError) as error:
            result["desempenho"] = f"Série indisponível: {error}"
            return result
        step_hours = _step_hours(df.index)
        power = _as_power(df)
        result["desempenho"] = {"periodo": _period_label(df)}
        result["demanda_x_entrega"] = _demand_vs_delivery(df, capacity)
        for name in ("aquecimento", "resfriamento"):
            column = f"{name}_w"
            if column not in power:
                continue
            nominal = capacity[name]
            delivered = power[column]
            result["desempenho"][name] = {
                "capacidade_nominal_w": round(nominal, 1),
                "pico_entregue_w": _clean(delivered.max()),
                "horas_em_operacao": round(float((delivered > 0).sum()) * step_hours, 2),
                "horas_acima_90pct_capacidade": (
                    round(float((delivered >= 0.9 * nominal).sum()) * step_hours, 2)
                    if nominal else None),
            }
        return result

    def propor_simulacao(self, alteracoes=None, base_execucao=None, motivo="") -> dict:
        if base_execucao:
            path = self.run_path(base_execucao)
            try:
                base = simulacao.base_from_run(path)
            except (OSError, ValueError, TypeError) as error:
                raise ToolError(f"Não foi possível ler a configuração de {base_execucao}: "
                                f"{error}") from error
            label = f"execução {base_execucao}"
        elif self.base_config is not None:
            base, label = self.base_config, "configuração atual da tela de execução"
        else:
            raise ToolError("Sem configuração base nesta tela; informe base_execucao.")
        if self.proposals:
            # A tela confirma uma proposta por vez; a extra voltaria como
            # pendente escondida atrás da primeira.
            raise ToolError("Já há uma proposta nesta resposta aguardando o usuário; "
                            "proponha uma simulação por vez.")
        try:
            proposal = simulacao.build_proposal(base, alteracoes, self.root, motivo, label)
        except simulacao.ProposalError as error:
            raise ToolError(str(error)) from error
        self.proposals.append(proposal)
        return simulacao.for_model(proposal)

    def guia_norma(self) -> dict:
        from ..etiquetagem import norma

        tipologias = [{
            "tipologia": chave, "nome": dados["nome"],
            "paf": (dict(zip(("principal", "demais"), dados["paf"]))
                    if isinstance(dados["paf"], tuple) else dados["paf"]),
            "rotina_horas": dados["horas"], "m2_por_pessoa": dados["ocupacao"],
            "crcgtt_por_zb": {zb: list(valores) for zb, valores in norma.CRCGTT[chave].items()},
        } for chave, dados in norma.TIPOLOGIAS.items()]
        return {"guia": normas.guia(), "tipologias_do_ambiens": tipologias,
                "faixas_ff_do_crcgtt": ["FF ≤ 0,20", "0,20 < FF ≤ 0,30",
                                        "0,30 < FF ≤ 0,40", "FF > 0,40"]}

    def buscar_norma(self, termos, documento=None, limite=6) -> dict:
        if documento and documento not in normas.DOCUMENTOS:
            raise ToolError(f"documento deve ser um de {list(normas.DOCUMENTOS)}.")
        try:
            achados = normas.buscar(termos, documento, max(1, min(int(limite), 10)))
        except ValueError as error:
            raise ToolError(str(error)) from error
        if not achados:
            raise ToolError("Nada encontrado. Tente sinônimos, a sigla ou menos termos.")
        return {"paginas": achados}

    def ler_norma(self, documento, pagina, ate=None) -> dict:
        if documento not in normas.DOCUMENTOS:
            raise ToolError(f"documento deve ser um de {list(normas.DOCUMENTOS)}.")
        try:
            return {"documento": documento,
                    "paginas": normas.ler(documento, int(pagina), ate and int(ate))}
        except ValueError as error:
            raise ToolError(str(error)) from error

    def etiquetagem(self, execucao) -> dict:
        from ..etiquetagem import avaliacao

        path = self.run_path(execucao)
        resultado = avaliacao.ler(path)
        opcoes = compare.read_config(path).get("etiquetagem")
        if resultado is None:
            raise ToolError(f"{execucao} não tem resultado de etiquetagem"
                            + (" (o grupo não terminou)." if opcoes else "."))
        return {"execucao": execucao, "opcoes": opcoes, "resultado": resultado}

    def codigo_controle(self, arquivo, funcoes=None) -> dict:
        if arquivo not in CODE_FILES:
            raise ToolError(f"arquivo deve ser um de {list(CODE_FILES)}.")
        path = os.path.join(os.path.dirname(control.__file__), f"{CODE_FILES[arquivo]}.py")
        try:
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
        except OSError as error:
            raise ToolError(f"Código de {arquivo} indisponível nesta instalação.") from error
        lines = source.splitlines()

        def numbered(first, last):
            return "\n".join(f"{number:4}| {lines[number - 1]}"
                             for number in range(first, last + 1))

        functions = {}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                functions.setdefault(node.name, (start, node.end_lineno, node))
        result = {"arquivo": f"confortimetro/control/{CODE_FILES[arquivo]}.py",
                  "versao_instalada": code_version()}
        if funcoes:
            missing = [name for name in funcoes if name not in functions]
            if missing:
                raise ToolError(f"Funções inexistentes em {arquivo}: {missing}. "
                                f"Disponíveis: {sorted(functions)}.")
            result["funcoes"] = {name: numbered(*functions[name][:2]) for name in funcoes}
        elif arquivo == "base":
            # Inteira passaria de 20 kB; o índice basta para escolher o que ler.
            result["indice"] = [
                {"funcao": name, "linhas": f"{start}-{end}",
                 "doc": (ast.get_docstring(node) or "").split("\n")[0]}
                for name, (start, end, node) in sorted(functions.items(),
                                                        key=lambda item: item[1][0])]
        else:
            result["codigo"] = numbered(1, len(lines))
        return result


def _present(df, variaveis, zona) -> list:
    """Variáveis pedidas que a planilha tem; recusa nomes fora de VARIABLES."""
    unknown = [v for v in variaveis if v not in VARIABLES]
    if unknown:
        raise ToolError(f"Variáveis desconhecidas: {unknown}. Use {VARIABLES}.")
    present = [v for v in variaveis if v in df.columns]
    if not present:
        raise ToolError(f"Nenhuma das variáveis está na planilha de {zona}.")
    return present


def _as_power(df):
    """Energia por timestep (J) vira potência média (W), com sufixo `_w`."""
    seconds = _step_hours(df.index) * 3600
    energy = [v for v in ENERGY_VARIABLES if v in df.columns]
    return df.assign(**{f"{v}_w": df[v] / seconds for v in energy}).drop(columns=energy)


def _timestep_rows(df) -> list:
    """Linhas por timestep, energia em W e o motivo também decodificado."""
    out = _as_power(df).reset_index()
    out["data"] = out["data"].dt.strftime("%Y-%m-%d %H:%M")
    rows = _records(out)
    if "motivo" in df:
        for row in rows:
            row["motivos"] = motivos.decode(row["motivo"])
    return rows


def _demand_vs_delivery(df, capacity):
    """Demanda até o setpoint × entrega das serpentinas × capacidade nominal,
    só com AC ligado — desligado, a demanda existe mas ninguém a atende."""
    if "demanda_aquecimento_w" not in df and "demanda_resfriamento_w" not in df:
        return ("Execução anterior às colunas de demanda e serpentinas: resimule para "
                "comparar demanda × capacidade.")
    hours = _step_hours(df.index)
    def count(mask):
        return round(float(mask.sum()) * hours, 2)
    on = df["ac"] > 0 if "ac" in df else pandas.Series(True, index=df.index)
    result = {"horas_ac_ligado": count(on)}
    # A demanda de resfriamento do EnergyPlus é negativa.
    for name, column, sign, coils in (
            ("aquecimento", "demanda_aquecimento_w", 1,
             ("serpentina_aquecimento_w", "serpentina_apoio_w")),
            ("resfriamento", "demanda_resfriamento_w", -1, ("serpentina_resfriamento_w",))):
        if column not in df:
            continue
        demand = (df[column].fillna(0) * sign).clip(lower=0)
        nominal = capacity[name]
        entry = {"capacidade_nominal_w": round(nominal, 1),
                 "pico_demanda_w": _clean(demand[on].max()),
                 "horas_com_demanda": count(on & (demand > 0)),
                 "horas_demanda_acima_capacidade": (
                     count(on & (demand > nominal)) if nominal else None)}
        present = [c for c in coils if c in df]
        if present:
            delivered = df[present].fillna(0).sum(axis=1)
            entry["horas_entrega_abaixo_90pct_demanda"] = count(
                on & (demand > 0) & (delivered < 0.9 * demand))
        if "serpentina_apoio_w" in df and name == "aquecimento":
            entry["horas_resistencia_apoio"] = count(df["serpentina_apoio_w"] > 0)
        result[name] = entry
    return result


def _control_summary(df) -> dict:
    """Horas em que o AC ligado não segurou o setpoint pedido pelo controlador."""
    hours = _step_hours(df.index)
    def count(mask):
        return round(float(mask.sum()) * hours, 2)
    occupied = df["ocupacao"] > 0
    summary = {"horas_ocupado": count(occupied)}
    if "motivo" in df:
        summary["horas_por_motivo"] = _motive_hours(df)
    if "ac" not in df:
        return summary
    ac_on = df["ac"] > 0
    summary["horas_ac_ligado"] = count(ac_on)
    for setpoint, above in (("setpoint_aquecimento", False), ("setpoint_resfriamento", True)):
        if setpoint not in df or "temp_ar" not in df:
            continue
        used = df.loc[ac_on, setpoint]
        missed = df["temp_ar"] > df[setpoint] + 0.5 if above else \
            df["temp_ar"] < df[setpoint] - 0.5
        summary[setpoint] = {
            "min": _clean(used.min()), "mediana": _clean(used.median()),
            "max": _clean(used.max()),
            "horas_ac_ligado_fora_por_0_5C": count(ac_on & missed),
        }
    return summary


def _motive_hours(df) -> dict:
    """Horas com cada bit de motivo ligado, só os que aparecem."""
    hours = _step_hours(df.index)
    values = df["motivo"].fillna(0).round().astype(int)
    result = {}
    for motivo in motivos.Motivo:
        on = int(((values & int(motivo)) != 0).sum())
        if on:
            result[motivo.name] = round(on * hours, 2)
    return result


def _zone_surfaces(run_path, zone):
    """Superfícies da zona no IDF da execução e as entradas do AirflowNetwork
    que as usam. Nomes em maiúsculas, como nos relatórios."""
    text = ""
    for name in ("modelo.idf", "in.idf"):
        text = _read_text(os.path.join(run_path, name))
        if text:
            break
    objects = [(kind.lower(), [field.upper() for field in fields])
               for kind, fields, _, _ in _iter_objects(text)]
    surfaces = {fields[0] for kind, fields in objects
                if kind == "buildingsurface:detailed" and len(fields) > 3
                and fields[3] == zone}
    surfaces |= {fields[0] for kind, fields in objects
                 if kind == "fenestrationsurface:detailed" and len(fields) > 3
                 and fields[3] in surfaces}
    afn = [fields for kind, fields in objects
           if kind == "airflownetwork:multizone:surface" and len(fields) > 1
           and fields[0] in surfaces]
    return surfaces, afn


def _ratio(num, den):
    try:
        return round(float(num) / float(den), 4) if float(den) else None
    except (TypeError, ValueError):
        return None


def _step_hours(index) -> float:
    """Duração de um timestep em horas, pela diferença mais comum entre linhas."""
    if len(index) < 2:
        return 1.0
    delta = pandas.Series(index).diff().dropna().mode()
    return delta.iloc[0].total_seconds() / 3600 if not delta.empty else 1.0


def _parse_day(text, year, end=False):
    """AAAA-MM-DD ou MM-DD; o fim inclui o dia inteiro."""
    text = (text or "").strip()
    try:
        day = pandas.Timestamp(text if len(text) > 5 else f"{year}-{text}")
    except ValueError as error:
        raise ToolError(f"Data inválida: {text!r} (use AAAA-MM-DD ou MM-DD).") from error
    return day + pandas.Timedelta(days=1) - pandas.Timedelta(seconds=1) if end else day


def _filter_period(df, inicio, fim):
    if df.empty or not (inicio or fim):
        return df
    # MM-DD usa o ano da própria série: as planilhas carimbam um ano fixo.
    year = df.index[0].year
    if inicio:
        df = df[df.index >= _parse_day(inicio, year)]
    if fim:
        df = df[df.index <= _parse_day(fim, year, end=True)]
    return df


def _period_label(df) -> str:
    return f"{df.index[0]:%Y-%m-%d %H:%M} a {df.index[-1]:%Y-%m-%d %H:%M}"
