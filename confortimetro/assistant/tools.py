"""Ferramentas que o modelo chama para ler as execuções — todas só de leitura.

Rodam na máquina do usuário sobre `results/`; ao modelo vai só o recorte
pedido, nunca a planilha. Toda saída passa por `_limit`, para que uma série
anual não estoure o contexto.
"""

import json
import math
import os

import pandas

from ..results import compare, series

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
VARIABLES = [name for name in series.COLUMNS if name != "data"]

FREQUENCIES = {"hora": "h", "dia": "D", "mes": "MS"}

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
                        "(média, mínimo, máximo). Energia em kWh somada no intervalo. "
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

    def __init__(self, root: str):
        self.root = root

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
            "execucao": run["run"], "status": run["status"],
            "modulo": run["module_type"], "idf": run["idf"], "epw": run["epw"],
            "zonas": run["rooms_disponiveis"],
            "modificado": run["modificado"].strftime("%Y-%m-%d %H:%M"),
        } for run in runs]}

    def configuracao(self, execucao: str) -> dict:
        return {"execucao": execucao,
                "configuracao": compare.read_config(self.run_path(execucao))}

    def indicadores(self, execucao: str, zona: str = None) -> dict:
        stats_path = os.path.join(self.run_path(execucao), "ESTATISTICAS.xlsx")
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
        unknown = [v for v in variaveis if v not in VARIABLES]
        if unknown:
            raise ToolError(f"Variáveis desconhecidas: {unknown}. Use {VARIABLES}.")
        present = [v for v in variaveis if v in df.columns]
        if not present:
            raise ToolError(f"Nenhuma das variáveis está na planilha de {zona}.")

        grouped = df[present].resample(FREQUENCIES[agregacao])
        energy = [v for v in present if v in ("aquecimento", "resfriamento")]
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
