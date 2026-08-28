"""Leitura dos nomes de zona direto do texto do IDF (sem eppy/IDD)."""

from confortimetro.idf import read_zone_names


def write(tmp_path, text):
    path = tmp_path / "modelo.idf"
    path.write_text(text, encoding="latin-1")
    return str(path)


def test_le_zonas_em_varias_linhas(tmp_path):
    idf = write(tmp_path, """
Zone,
    COPA,                     !- Name
    0,                        !- Direction of Relative North
    0;                        !- X Origin

Zone,
    ATELIE1,                  !- Name
    0;                        !- Direction of Relative North
""")
    assert read_zone_names(idf) == ["COPA", "ATELIE1"]


def test_ignora_objetos_que_apenas_comecam_com_zone(tmp_path):
    idf = write(tmp_path, """
ZoneHVAC:EquipmentList,
    LISTA_1,                  !- Name
    ZoneHVAC:IdealLoadsAirSystem;

ZoneInfiltration:DesignFlowRate,
    INFIL_1;                  !- Name

Zone,
    SALA_AULA;                !- Name
""")
    assert read_zone_names(idf) == ["SALA_AULA"]


def test_zona_em_linha_unica_e_sem_repeticao(tmp_path):
    idf = write(tmp_path, "Zone, WC, 0, 0;\nZone, WC, 0, 0;\n")
    assert read_zone_names(idf) == ["WC"]


def test_arquivo_inexistente_nao_quebra_a_interface():
    assert read_zone_names("/caminho/que/nao/existe.idf") == []
