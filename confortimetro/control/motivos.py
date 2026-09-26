"""Motivos das decisões do controlador, gravados por timestep em `MOTIVO_<ZONA>`.

Cada motivo é um bit: vários valem no mesmo timestep (janela bloqueada pela
externa fria *e* AC ligado por PMV) e o valor gravado é a soma. O schedule é
float no EnergyPlus, exato para inteiros até 2**24 — sobra folga para 24 bits.

Os valores são o contrato com as planilhas já geradas: acrescente bits novos
no fim e nunca renumere um existente.
"""

from enum import IntFlag


class Motivo(IntFlag):
    OCUPADA = 1 << 0                     # sala com gente neste timestep
    CONFORTO_SO_COM_CLO = 1 << 1         # clo sozinho levou o PMV à faixa
    AC_TEMPO_MAXIMO = 1 << 2             # AC desligado por passar do tempo máximo
    JANELA_ABERTA_ADAPTATIVO = 1 << 3    # operativa dentro da banda adaptativa
    JANELA_ABERTA_COM_VENTILADOR = 1 << 4  # operativa 25–27,2 °C, ventilação + vento
    JANELA_BLOQUEADA_EXTERNA_QUENTE = 1 << 5  # externa acima do máximo adaptativo
    JANELA_BLOQUEADA_EXTERNA_FRIA = 1 << 6    # externa abaixo de temp_ar - temp_open_window_bound
    JANELA_BLOQUEADA_AC_LIGADO = 1 << 7
    JANELA_FECHADA_OPERATIVA_FORA = 1 << 8    # externa permitia, operativa fora da banda
    VENTILADOR_POR_PMV = 1 << 9
    AC_LIGADO_POR_PMV = 1 << 10          # ligou neste timestep
    AC_MANTIDO = 1 << 11                 # já estava ligado
    SETPOINT_AQUECIMENTO_NO_LIMITE = 1 << 12  # subiu até temp_ac_max sem alcançar o PMV
    SETPOINT_RESFRIAMENTO_NO_LIMITE = 1 << 13  # desceu até temp_ac_min sem alcançar o PMV
    DOAS_POR_CO2 = 1 << 14
    VAZIA_JANELA_PURGA_CO2 = 1 << 15     # sala vazia, janela aberta para CO2
    VAZIA_JANELA_TRAVADA_FRIO = 1 << 16  # trava de janela_sem_pessoas após esfriar
    VAZIA_JANELA_INVERNO = 1 << 17       # mês de inverno: não abre sala vazia
    JANELA_FECHADA_VENTILADOR_NO_LIMITE = 1 << 18  # operativa 25–27,2 °C, mas o vento adaptativo passaria de max_vel


def decode(value) -> list:
    """Nomes dos motivos ligados em `value` (float da planilha ou int)."""
    try:
        flags = Motivo(int(round(float(value))))
    except (TypeError, ValueError):
        return []
    return [motivo.name for motivo in Motivo if motivo in flags]


if __name__ == "__main__":
    value = float(Motivo.OCUPADA | Motivo.JANELA_BLOQUEADA_EXTERNA_FRIA | Motivo.AC_MANTIDO)
    assert decode(value) == ["OCUPADA", "JANELA_BLOQUEADA_EXTERNA_FRIA", "AC_MANTIDO"]
    assert decode(0) == [] and decode(float("nan")) == []
    print("ok")
