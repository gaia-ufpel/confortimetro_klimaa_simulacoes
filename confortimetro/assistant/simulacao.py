"""Proposta de simulação feita pelo assistente — nunca a execução.

O modelo monta uma proposta (configuração base + alterações), que é resolvida
e validada aqui como o `--print-config` do CLI faria, e mais o que a GUI
confere antes de rodar (arquivos, zonas, equipamento). Quem dispara a
simulação é a interface, depois que o usuário confirma — e pelo mesmo caminho
do botão **Executar** (`MainWindow.start_simulation`).
"""

import datetime
import json
import math
import os
import uuid

from ..config import PORCENT2ADAPTATIVE, SimulationConfig, is_energy_path
from ..idf.processor import (read_run_period, read_timesteps_per_hour,
                             read_zone_names, unwired_equipment)
from ..module_type import ModuleType

# Campos que o assistente pode alterar, com o tipo esperado. Caminhos de saída,
# EnergyPlus e os derivados ficam de fora: são da máquina ou da própria execução.
# O IDF também: é o que o usuário escolheu (ou o da execução base), e o modelo
# não troca por outro arquivo do disco.
EDITABLE_FIELDS = {
    "epw_path": str,
    "module_type": str,
    "rooms": list,
    "met": float,
    "wme": float,
    "clo_min": float,
    "clo_max": float,
    "clo_delta": float,
    "clo_priority": bool,
    "pmv_lowerbound": float,
    "pmv_upperbound": float,
    "pmv_comfort_bound": float,
    "adaptative_bound": float,
    "temp_ac_min": float,
    "temp_ac_max": float,
    "temp_open_window_bound": float,
    "max_vel": float,
    "air_speed_delta": float,
    "co2_limit": float,
}

# Faixas fechadas da tela de execução (`simulation_config_panel`) e da validade
# do PMV (ISO 7730 / ASHRAE 55); ver PRD 005. `wme` vai de 0 até abaixo de `met`.
FIELD_RANGES = {
    "met": (0.8, 4.0),
    "pmv_lowerbound": (-3.0, 3.0),
    "pmv_upperbound": (-3.0, 3.0),
    "clo_min": (0.0, 2.0),
    "clo_max": (0.0, 2.0),
    "temp_ac_min": (10.0, 35.0),
    "temp_ac_max": (10.0, 35.0),
    "co2_limit": (400.0, 5000.0),
}
# Faixas abertas em zero: (0, máximo].
POSITIVE_RANGES = {
    "pmv_comfort_bound": 3.0,
    "temp_open_window_bound": 15.0,
    "max_vel": 2.0,
}

# Parâmetros efetivos da confirmação, inclusive os herdados da configuração base.
# Não listar saída/arquivos derivados: só são definidos quando a execução começa.
SUMMARY_FIELDS = ("idf_path", "epw_path", "module_type", "rooms", "met", "wme",
                  "clo_min", "clo_max", "clo_delta", "clo_priority", "pmv_lowerbound",
                  "pmv_upperbound", "pmv_comfort_bound", "adaptative_bound",
                  "temp_ac_min", "temp_ac_max", "temp_open_window_bound", "max_vel",
                  "air_speed_delta", "co2_limit", "energy_path", "runs_root_path",
                  "ignore_missing_equipment")

# Acima disto a simulação deixa de ser "rápida": avisar do tempo e do disco.
LONG_RUN_DAYS = 31


class ProposalError(Exception):
    """Pedido que não vira proposta; a mensagem vai ao modelo."""


def _parse_value(raw):
    """Como o `--set` do CLI: JSON quando der, senão o texto."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _coerce(field, value):
    kind = EDITABLE_FIELDS[field]
    value = _parse_value(value)
    if kind is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProposalError(f"{field} precisa ser número (recebido {value!r}).")
        if not math.isfinite(value):
            raise ProposalError(f"{field} precisa ser um número finito (recebido {value!r}).")
        return float(value)
    if kind is bool:
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        if not isinstance(value, bool):
            raise ProposalError(f"{field} precisa ser true ou false (recebido {value!r}).")
        return value
    if kind is list:
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ProposalError(f"{field} precisa ser uma lista de nomes de zona.")
        return value
    if field == "module_type":
        names = [module.value for module in ModuleType]
        if str(value).upper() not in names:
            raise ProposalError(f"module_type inválido: {value!r}. Use um de {names}.")
        return str(value).upper()
    return str(value)


def config_to_dict(config: SimulationConfig) -> dict:
    """Configuração em JSON puro, para guardar na conversa."""
    return json.loads(json.dumps(config.__dict__, default=str))


def config_from_dict(data: dict) -> SimulationConfig:
    return SimulationConfig(**data)


def base_from_run(run_path: str) -> SimulationConfig:
    """Configuração de uma execução, como o **Duplicar** faz: o IDF escolhido
    pelo usuário (e não a cópia da execução) e sem pasta de saída."""
    config = SimulationConfig.from_json(os.path.join(run_path, "configs.json"))
    if config.source_idf_path:
        config.idf_path = config.source_idf_path
    return config


def validate(config: SimulationConfig, remote: bool = None):
    """(problemas que impedem rodar, avisos que o usuário precisa ver).

    `remote` (padrão: o modo escolhido nas configurações) dispensa o
    EnergyPlus local: quem simula é o servidor.
    """
    if remote is None:
        from confortimetro.remote.client import enabled
        remote = enabled()
    problems, warnings = [], []
    if not config.idf_path or not os.path.isfile(config.idf_path):
        problems.append(f"Arquivo IDF não encontrado: {config.idf_path}")
    if not config.epw_path or not os.path.isfile(config.epw_path):
        problems.append(f"Arquivo EPW não encontrado: {config.epw_path}")
    if not remote and not is_energy_path(config.energy_path):
        problems.append(f"Instalação do EnergyPlus inválida: {config.energy_path}")
    rooms = list(config.rooms or [])
    if not rooms:
        problems.append("Nenhuma zona escolhida em rooms.")
    for low, high in (("clo_min", "clo_max"), ("pmv_lowerbound", "pmv_upperbound"),
                      ("temp_ac_min", "temp_ac_max")):
        if getattr(config, low) > getattr(config, high):
            problems.append(f"{low} ({getattr(config, low)}) maior que "
                            f"{high} ({getattr(config, high)}).")
    for field, (low, high) in FIELD_RANGES.items():
        value = getattr(config, field)
        if not low <= value <= high:
            problems.append(f"{field} ({value}) fora da faixa {low} a {high}.")
    for field, high in POSITIVE_RANGES.items():
        value = getattr(config, field)
        if not 0 < value <= high:
            problems.append(f"{field} ({value}) precisa ser maior que 0 e até {high}.")
    if not 0 <= config.wme < config.met:
        problems.append(f"wme ({config.wme}) precisa ser >= 0 e menor que met ({config.met}).")
    if config.adaptative_bound not in PORCENT2ADAPTATIVE.values():
        problems.append(f"adaptative_bound ({config.adaptative_bound}) precisa ser um de "
                        f"{sorted(PORCENT2ADAPTATIVE.values())}.")
    if config.clo_delta <= 0 or config.air_speed_delta <= 0:
        problems.append("clo_delta e air_speed_delta precisam ser positivos.")

    if os.path.isfile(config.idf_path or ""):
        zones = read_zone_names(config.idf_path)
        # IDF sem Zone não tem onde aplicar o controle: toda zona é desconhecida.
        unknown = [room for room in rooms if room.upper() not in
                   {zone.upper() for zone in zones}]
        if unknown:
            problems.append(f"Zonas que não existem no IDF: {', '.join(unknown)}. "
                            f"Disponíveis: {', '.join(zones) or 'nenhuma'}.")
        elif rooms:
            warnings += unwired_equipment(config.idf_path, rooms, config.module_type)
    return problems, warnings


def period_of(idf_path: str) -> dict:
    start, end = read_run_period(idf_path)
    days = (end - start).days
    return {"inicio": start.strftime("%d/%m/%Y"),
            "fim": (end - datetime.timedelta(days=1)).strftime("%d/%m/%Y"),
            "dias": days, "passos_por_hora": read_timesteps_per_hour(idf_path)}


def build_proposal(base: SimulationConfig, changes, runs_root: str, reason: str = "",
                   base_label: str = "configuração atual da tela de execução") -> dict:
    """Aplica `changes` (`[{campo, valor}]`) sobre `base` e valida.

    Levanta `ProposalError` se algo impede a simulação; devolve a proposta,
    ainda pendente de confirmação, caso contrário.
    """
    config = config_from_dict(config_to_dict(base))
    applied = {}
    for item in changes or []:
        if not isinstance(item, dict) or "campo" not in item:
            raise ProposalError("Cada alteração é {campo, valor}.")
        field = str(item["campo"]).strip()
        if field not in EDITABLE_FIELDS:
            raise ProposalError(f"Campo {field!r} não pode ser alterado pelo assistente. "
                                f"Permitidos: {', '.join(EDITABLE_FIELDS)}.")
        value = _coerce(field, item.get("valor"))
        setattr(config, field, value)
        applied[field] = value

    # A pasta de saída só é criada quando a simulação começa, na raiz que a
    # listagem lê — é lá que a execução aparece.
    config.runs_root_path = runs_root
    config.output_path = None
    config.source_idf_path = None
    config.code_version = None
    config.ignore_missing_equipment = False

    problems, warnings = validate(config)
    if problems:
        raise ProposalError("Configuração inválida: " + " ".join(problems))

    period = period_of(config.idf_path)
    if period["dias"] > LONG_RUN_DAYS:
        warnings.append(f"Período de {period['dias']} dias: a simulação pode levar de "
                        "dezenas de minutos a horas e ocupar mais de 1 GB.")
    if any("não tem" in warning for warning in warnings):
        # O usuário vê o aviso na confirmação; confirmar é aceitar rodar assim,
        # como no "Rodar mesmo assim?" da tela de execução.
        config.ignore_missing_equipment = True

    return {
        "id": uuid.uuid4().hex[:12],
        "status": "pendente",
        "criada": datetime.datetime.now().isoformat(timespec="seconds"),
        "base": base_label,
        "motivo": reason or "",
        "alteracoes": applied,
        "avisos": warnings,
        "periodo": period,
        "config": config_to_dict(config),
    }


def summary(proposal: dict) -> list:
    """(rótulo, valor) dos parâmetros efetivos, destacando os alterados."""
    config = proposal["config"]
    period = proposal["periodo"]
    rows = [("período (RunPeriod do IDF)",
             f"{period['inicio']} a {period['fim']} — {period['dias']} dia(s), "
             f"{period['passos_por_hora']} passo(s)/h")]
    changed = list(proposal["alteracoes"])
    for field in changed + [f for f in SUMMARY_FIELDS if f not in changed]:
        key = {"idf_path": "_idf_path", "met": "_met"}.get(field, field)
        value = config.get(key)
        if isinstance(value, list):
            value = ", ".join(value)
        mark = " (alterado)" if field in changed else ""
        rows.append((field + mark, "" if value is None else str(value)))
    return rows


def for_model(proposal: dict) -> dict:
    """O que volta ao modelo: sem os caminhos derivados."""
    return {
        "proposta_id": proposal["id"],
        "status": "aguardando confirmação do usuário na interface — ainda não está rodando",
        "alteracoes": proposal["alteracoes"],
        "periodo": proposal["periodo"],
        "avisos": proposal["avisos"],
        "configuracao": dict(summary(proposal)),
    }
