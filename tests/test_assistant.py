"""Assistente de análise: ferramentas, laço de function calling e histórico.

Sem rede: o cliente Gemini é trocado por um falso que devolve respostas
roteirizadas. O teste com a API de verdade só roda com GEMINI_API_KEY.
"""

import os
import threading

import pytest

pytest.importorskip("google.genai")
from google.genai import types  # noqa: E402

from confortimetro.assistant import store  # noqa: E402
from confortimetro.assistant.client import Assistant, AssistantError, Cancelled  # noqa: E402
from confortimetro.assistant.tools import MAX_ROWS, Toolbox  # noqa: E402
from confortimetro.results.compare import recompute_run  # noqa: E402
from tests.test_compare import _make_run  # noqa: E402
from tests.test_stats import ROOM  # noqa: E402

# Lida antes da fixture que limpa o ambiente de cada teste.
REAL_KEY = os.environ.get("GEMINI_API_KEY")


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Configurações, chave e conversas numa pasta descartável."""
    monkeypatch.setenv("CONFORTIMETRO_DATA_DIR", str(tmp_path / "dados"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return tmp_path / "dados"


@pytest.fixture
def root(tmp_path):
    outputs = tmp_path / "execucoes"
    outputs.mkdir()
    for name, module, heating in (("COM_JANELA", "COMPLETE", 10.0),
                                  ("FECHADA", "CLOSED_WINDOW", 4.0)):
        recompute_run(str(_make_run(outputs, name, module, heating_kwh=heating)))
    return str(outputs)


# --- Ferramentas ---------------------------------------------------------

def test_listar_e_indicadores(root):
    tools = Toolbox(root)
    names = [row["execucao"] for row in tools.call("listar_execucoes", {})["linhas"]]
    assert sorted(names) == ["COM_JANELA", "FECHADA"]

    rows = tools.call("indicadores", {"execucao": "COM_JANELA", "zona": ROOM})["linhas"]
    assert rows[0]["Energia total (kWh)"] == pytest.approx(10.0)


def test_comparar(root):
    result = Toolbox(root).call("comparar", {"execucoes": ["COM_JANELA", "FECHADA"]})
    assert [row["Energia total (kWh)"] for row in result["linhas"]] == pytest.approx([10.0, 4.0])


def test_nome_de_execucao_nao_sai_da_raiz(root):
    tools = Toolbox(root)
    for name in ("../COM_JANELA", "..", os.path.join("x", "y"), "NAO_EXISTE"):
        assert "erro" in tools.call("configuracao", {"execucao": name})


def test_serie_agregada_soma_energia_em_kwh(root):
    result = Toolbox(root).call("serie_agregada", {
        "execucao": "COM_JANELA", "zona": ROOM, "variaveis": ["pmv", "aquecimento"],
        "agregacao": "dia"})
    (row,) = result["linhas"]
    assert row["data"] == "2015-01-01"
    assert row["pmv_media"] == pytest.approx(0.1)
    assert row["aquecimento_kwh"] == pytest.approx(10.0)  # 10 timesteps × 1 kWh


def test_horas_em_condicao_filtro_estruturado(root):
    tools = Toolbox(root)
    result = tools.call("horas_em_condicao", {
        "execucao": "COM_JANELA", "zona": ROOM,
        "condicoes": [{"coluna": "ac", "operador": "==", "valor": 1},
                      {"coluna": "ocupacao", "operador": ">", "valor": 0}]})
    # 10 timesteps de 10 min com AC ligado.
    assert result["horas"] == pytest.approx(10 / 6, abs=0.01)
    assert result["linhas"][0]["mes"] == "2015-01"

    # Nada de expressão livre: operador fora da lista é recusado.
    bad = tools.call("horas_em_condicao", {
        "execucao": "COM_JANELA", "zona": ROOM,
        "condicoes": [{"coluna": "ac", "operador": "__import__('os')", "valor": 1}]})
    assert "erro" in bad


def test_periodo_mm_dd_usa_o_ano_da_serie(root):
    result = Toolbox(root).call("horas_em_condicao", {
        "execucao": "COM_JANELA", "zona": ROOM, "inicio": "01-02", "fim": "01-03",
        "condicoes": [{"coluna": "ac", "operador": "==", "valor": 1}]})
    assert "erro" in result  # a série só tem 01/01


def test_resultado_grande_e_cortado(root, monkeypatch):
    tools = Toolbox(root)
    monkeypatch.setattr(tools, "listar_execucoes",
                        lambda: {"linhas": [{"i": i} for i in range(1000)]})
    result = tools.call("listar_execucoes", {})
    assert len(result["linhas"]) == MAX_ROWS and "aviso" in result


# --- Laço de function calling ---------------------------------------------

def _chunk(*parts, prompt_tokens=100):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens))


class FakeModels:
    """Devolve, a cada chamada, a próxima lista de chunks do roteiro."""

    def __init__(self, script, summary="resumo"):
        self.script = list(script)
        self.requests = []
        self.summary = summary

    def generate_content_stream(self, model, contents, config):
        self.requests.append((contents, config))
        return iter(self.script.pop(0))

    def generate_content(self, model, contents, config):
        return types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text=self.summary)]))])


class FakeClient:
    def __init__(self, script, **kwargs):
        self.models = FakeModels(script, **kwargs)


def _call(name, **args):
    return types.Part(function_call=types.FunctionCall(name=name, args=args),
                      thought_signature=b"sig")


def test_chama_ferramenta_e_responde_em_streaming(root):
    client = FakeClient([
        [_chunk(_call("indicadores", execucao="COM_JANELA"))],
        [_chunk(types.Part(text="Consumo de ")),
         _chunk(types.Part(text="10 kWh.", thought_signature=b"fim"))],
    ])
    conversation = store.new_conversation(["COM_JANELA"])
    events = []
    answer = Assistant(conversation, root, client=client).ask(
        "Quanto consumiu?", on_event=lambda kind, data: events.append((kind, data)))

    assert answer == "Consumo de 10 kWh."
    assert ("text", "10 kWh.") in events
    assert any(kind == "status" and "indicadores" in data for kind, data in events)

    # A segunda chamada leva o resultado da ferramenta e a assinatura da chamada.
    contents, _ = client.models.requests[1]
    assert contents[1].parts[0].thought_signature == b"sig"
    result = contents[2].parts[0].function_response.response["resultado"]
    assert result["linhas"][0]["Energia total (kWh)"] == pytest.approx(10.0)

    # Tudo salvo em disco, com título e a versão dos resultados usados.
    saved = store.load_conversation(conversation["id"])
    assert saved["title"] == "Quanto consumiu?"
    assert len(saved["contents"]) == 4
    assert "COM_JANELA" in saved["run_mtimes"]
    assert store.visible_messages(saved) == [("user", "Quanto consumiu?"),
                                             ("model", "Consumo de 10 kWh.")]
    assert "10 kWh" in store.export_markdown(saved)


def test_limite_de_chamadas_forca_resposta(root):
    loop = [[_chunk(_call("listar_execucoes"))] for _ in range(3)]
    client = FakeClient(loop + [[_chunk(types.Part(text="fim"))]])
    settings = dict(store.DEFAULT_SETTINGS, max_tool_calls=2)

    Assistant(store.new_conversation(), root, settings, client=client).ask("oi")

    configs = [config for _, config in client.models.requests]
    assert configs[0].tool_config is None
    # Atingido o limite, a chamada seguinte proíbe ferramentas.
    assert configs[2].tool_config.function_calling_config.mode == "NONE"


def test_cancelar_nao_altera_a_conversa(root):
    cancel = threading.Event()
    cancel.set()
    client = FakeClient([[_chunk(types.Part(text="x"))]])
    conversation = store.new_conversation()
    with pytest.raises(Cancelled):
        Assistant(conversation, root, client=client).ask("oi", cancel=cancel)
    assert conversation["contents"] == []


def test_resposta_vazia_vira_erro(root):
    client = FakeClient([[types.GenerateContentResponse(candidates=[])]])
    with pytest.raises(AssistantError):
        Assistant(store.new_conversation(), root, client=client).ask("oi")


def test_resumo_substitui_historico_so_na_api(root):
    client = FakeClient([
        [_chunk(types.Part(text="primeira"), prompt_tokens=10)],
        [_chunk(types.Part(text="segunda"), prompt_tokens=900_000)],
        [_chunk(types.Part(text="terceira"))],
    ])
    conversation = store.new_conversation()
    assistant = Assistant(conversation, root, client=client)
    assistant.ask("um")
    assistant.ask("dois")  # passa de 700 mil tokens: resume o que veio antes

    assert conversation["summary"] == "resumo"
    assert conversation["summary_upto"] == 2
    assistant.ask("três")
    contents, _ = client.models.requests[2]
    assert "resumo" in contents[0].parts[0].text
    assert [c.parts[0].text for c in contents[2:]] == ["dois", "segunda", "três"]
    assert len(conversation["contents"]) == 6  # o disco guarda tudo


def test_execucao_recalculada_gera_aviso(root):
    conversation = store.new_conversation(["COM_JANELA"])
    conversation["run_mtimes"] = {"COM_JANELA": 1.0, "SUMIU": 1.0}
    stale = store.stale_runs(conversation, root)
    assert stale == {"COM_JANELA": "recalculada", "SUMIU": "apagada"}
    assert "recalculada" in Assistant(conversation, root, client=object())._system_prompt()


# --- Configurações e chave -----------------------------------------------

def test_configuracoes_e_chave_em_arquivo(monkeypatch, data_dir):
    monkeypatch.setattr(store, "_keyring", lambda: None)
    assert store.get_api_key() == ""
    store.set_api_key("abc")
    assert store.get_api_key() == "abc"
    monkeypatch.setenv("GEMINI_API_KEY", "do-ambiente")
    assert store.get_api_key() == "do-ambiente"
    monkeypatch.delenv("GEMINI_API_KEY")
    store.set_api_key("")
    assert store.get_api_key() == ""

    store.save_settings(dict(store.DEFAULT_SETTINGS, max_tool_calls=5))
    assert store.load_settings()["max_tool_calls"] == 5
    assert not (data_dir / "assistente.json").read_text().count("abc")


def test_listar_conversas_por_execucao():
    first = store.new_conversation(["A"])
    store.save_conversation(first)
    store.save_conversation(store.new_conversation(["B"]))
    assert [c["id"] for c in store.list_conversations("A")] == [first["id"]]
    assert len(store.list_conversations()) == 2
    store.delete_conversation(first["id"])
    assert len(store.list_conversations()) == 1
    with pytest.raises(ValueError):
        store.load_conversation("../x")


@pytest.mark.skipif(not REAL_KEY, reason="teste real só com GEMINI_API_KEY")
def test_api_real(root, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", REAL_KEY)
    answer = Assistant(store.new_conversation(["COM_JANELA"]), root).ask(
        "Qual a energia total da execução COM_JANELA?")
    assert "10" in answer
