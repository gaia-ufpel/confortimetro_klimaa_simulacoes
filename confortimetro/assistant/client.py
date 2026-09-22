"""Conversa com o Gemini e o laço de function calling sobre as ferramentas locais.

O laço é manual (e não o `automatic_function_calling` do SDK) para poder
cancelar entre chamadas, mostrar no painel qual ferramenta está rodando e
guardar no histórico cada chamada e resultado.
"""

import os

from . import store
from .tools import DECLARATIONS, Toolbox

SYSTEM_PROMPT = """\
Você é o assistente de análise do Confortímetro Klimaa, software do grupo GAIA que \
simula conforto térmico com EnergyPlus. A cada timestep, com a sala ocupada, o \
controlador de cada zona: (1) escolhe o clo (vestimenta) com PMV mais próximo de zero \
na faixa clo_min…clo_max (se clo_priority); (2) se já há conforto, desliga ventilador \
e AC; (3) abre a janela quando o clima externo permite (abaixo do máximo adaptativo e \
com AC desligado); (4) com janela fechada e sem conforto, ajusta a velocidade do \
ventilador e, esgotada a faixa, liga o AC (PTHP) buscando setpoints por PMV; (5) liga \
o DOAS quando o CO2 passa de co2_limit com a janela fechada. Desocupada, tudo desliga \
e a janela pode abrir para purgar CO2. Conforto: PMV (Fanger) na faixa \
pmv_lowerbound…pmv_upperbound e banda adaptativa da ASHRAE 55 (ADAP_MIN/ADAP_MAX).

Módulos (`module_type`): COMPLETE (janela adaptativa, ventilador, AC e DOAS), \
CLOSED_WINDOW (janela sempre fechada), WITHOUT_FAN (sem ventilador) e \
FIXED_AC_WITHOUT_FAN (sem ventilador, setpoints fixos do IDF).

Regras:
- Responda em português, em tom técnico e objetivo, em Markdown (tabelas quando \
comparar).
- Todo número vem das ferramentas ou do histórico desta conversa. Cite sempre a \
execução, a zona e o período de cada número. Se o dado não existe, diga que não tem — \
nunca estime nem invente.
- Consulte as ferramentas antes de responder; prefira agregações (dia/mês) a séries \
horárias longas.
- Ao comparar execuções com períodos diferentes, avise que os totais não são \
comparáveis.
- Você só analisa: não altera configurações nem dispara simulações. Se pedirem, \
explique o que o resultado sugere e deixe a decisão ao usuário.
"""

SUMMARY_PROMPT = """\
Resuma a conversa abaixo para continuar a análise depois. Guarde todos os números \
já obtidos com execução, zona e período, as conclusões e as perguntas em aberto. \
Seja denso; não invente nada."""


class AssistantError(Exception):
    """Falha que o painel mostra ao usuário como está."""


class Cancelled(Exception):
    """O usuário cancelou a pergunta."""


def friendly_error(error: Exception) -> str:
    """Mensagem em português para os erros da API e de rede."""
    from google.genai import errors

    if isinstance(error, errors.APIError):
        text = f"{error.status or ''} {error.message or ''}".lower()
        if error.code == 429 or "resource_exhausted" in text:
            return ("Limite de uso da chave atingido (429). Espere um pouco ou "
                    "verifique a cota no Google AI Studio.")
        if error.code in (401, 403) or "api key" in text or "api_key" in text:
            return "Chave da API Gemini inválida ou sem permissão. Confira nas Configurações."
        if error.code == 404:
            return ("Modelo não encontrado. Confira o nome do modelo nas Configurações "
                    "do assistente.")
        if error.code and error.code >= 500:
            return f"O serviço do Gemini falhou ({error.code}). Tente de novo em instantes."
        return f"Erro da API Gemini ({error.code}): {error.message}"

    name = type(error).__name__.lower()
    if "timeout" in name:
        return "A chamada ao Gemini passou do tempo limite. Tente de novo ou aumente o timeout."
    if "connect" in name or "network" in name or isinstance(error, OSError):
        return "Sem conexão com o Gemini. Verifique a internet."
    return f"{type(error).__name__}: {error}"


def make_client(api_key: str, timeout_s: int):
    from google import genai
    from google.genai import types

    return genai.Client(api_key=api_key,
                        http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))


def test_key(api_key: str, model: str, timeout_s: int = 30):
    """Levanta `AssistantError` se a chave ou o modelo não funcionam."""
    if not api_key:
        raise AssistantError("Informe a chave.")
    try:
        make_client(api_key, timeout_s).models.get(model=model)
    except Exception as error:
        raise AssistantError(friendly_error(error)) from error


def _is_question(content) -> bool:
    """Mensagem do usuário com texto (e não resultado de ferramenta)."""
    return content.role == "user" and any(part.text for part in content.parts or [])


class Assistant:
    """Responde perguntas numa conversa, chamando as ferramentas sobre `root`."""

    def __init__(self, conversation: dict, root: str, settings: dict = None,
                 api_key: str = None, client=None):
        self.conversation = conversation
        self.root = root
        self.settings = settings or store.load_settings()
        self.toolbox = Toolbox(root)
        self._client = client
        self._api_key = api_key

    @property
    def client(self):
        if self._client is None:
            key = self._api_key or store.get_api_key()
            if not key:
                raise AssistantError("Nenhuma chave da API Gemini configurada.")
            self._client = make_client(key, self.settings["timeout_s"])
        return self._client

    # --- Histórico ---

    def _contents(self):
        from google.genai import types
        return [types.Content.model_validate(item)
                for item in self.conversation["contents"]]

    def _history(self, contents):
        """O que vai para a API: o resumo no lugar das mensagens que ele cobre."""
        from google.genai import types

        summary = self.conversation.get("summary")
        if not summary:
            return list(contents)
        return [
            types.Content(role="user", parts=[types.Part(
                text="Resumo da conversa até aqui:\n" + summary)]),
            types.Content(role="model", parts=[types.Part(text="Entendido.")]),
        ] + list(contents[self.conversation["summary_upto"]:])

    def _system_prompt(self) -> str:
        from ..results import compare

        lines = [SYSTEM_PROMPT]
        runs = self.conversation.get("runs") or []
        if runs:
            lines.append("Execuções em foco nesta conversa (use-as por padrão; outras "
                         "estão em listar_execucoes):")
            for run in runs:
                path = os.path.join(self.root, run)
                if compare.is_run(path):
                    info = compare.read_run(path)
                    lines.append(f"- {run}: módulo {info['module_type']}, IDF {info['idf']}, "
                                 f"EPW {info['epw']}, zonas "
                                 f"{', '.join(info['rooms_disponiveis']) or '—'}, "
                                 f"status {info['status']}")
                else:
                    lines.append(f"- {run}: não existe mais")
        else:
            lines.append("Nenhuma execução em foco: descubra-as com listar_execucoes.")

        stale = store.stale_runs(self.conversation, self.root)
        if stale:
            lines.append("ATENÇÃO: desde as respostas anteriores, estas execuções mudaram "
                         "e os números antigos podem não valer mais: "
                         + ", ".join(f"{run} ({why})" for run, why in stale.items())
                         + ". Consulte de novo antes de reaproveitar números.")
        return "\n".join(lines)

    def _config(self, tools_enabled=True):
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt(),
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(**declaration) for declaration in DECLARATIONS])],
        )
        if not tools_enabled:
            config.tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="NONE"))
        return config

    # --- Laço ---

    def _stream(self, contents, config, on_event, cancel):
        """Uma chamada em streaming; devolve o `Content` do modelo já montado."""
        from google.genai import types

        parts, usage, finish = [], None, None
        stream = self.client.models.generate_content_stream(
            model=self.settings["model"], contents=self._history(contents), config=config)
        for chunk in stream:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            usage = chunk.usage_metadata or usage
            candidate = chunk.candidates[0] if chunk.candidates else None
            if candidate is None:
                continue
            finish = candidate.finish_reason or finish
            for part in (candidate.content.parts if candidate.content else None) or []:
                is_text = part.text is not None and not part.function_call and not part.thought
                if is_text:
                    on_event("text", part.text)
                    last = parts[-1] if parts else None
                    # Texto em pedaços vira uma parte só; a assinatura, quando
                    # vem, chega no último pedaço e precisa ser preservada.
                    if (last is not None and last.text is not None and not last.thought
                            and not last.function_call):
                        last.text += part.text
                        if part.thought_signature:
                            last.thought_signature = part.thought_signature
                        continue
                parts.append(part)

        if usage and usage.prompt_token_count:
            self.conversation["prompt_tokens"] = usage.prompt_token_count
        if not parts:
            raise AssistantError(f"O modelo não respondeu (motivo: {finish or 'desconhecido'}).")
        return types.Content(role="model", parts=parts)

    def ask(self, question: str, on_event=None, cancel=None) -> str:
        """Responde `question`, chamando ferramentas quantas vezes o limite deixar.

        `on_event(tipo, dado)` recebe `("text", pedaço)` durante a resposta e
        `("status", texto)` enquanto as ferramentas rodam. Cancelada ou com
        erro, a conversa fica como estava antes da pergunta.
        """
        from google.genai import types

        on_event = on_event or (lambda kind, data: None)
        contents = self._contents()
        contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
        used_runs = set(self.conversation.get("runs") or [])
        max_calls = int(self.settings["max_tool_calls"])
        calls = 0

        try:
            while True:
                on_event("status", "Pensando…")
                reply = self._stream(contents, self._config(tools_enabled=calls < max_calls),
                                     on_event, cancel)
                contents.append(reply)
                function_calls = [part.function_call for part in reply.parts
                                  if part.function_call]
                if not function_calls:
                    break

                responses = []
                for call in function_calls:
                    if cancel is not None and cancel.is_set():
                        raise Cancelled()
                    calls += 1
                    args = dict(call.args or {})
                    on_event("status", f"Consultando {call.name.replace('_', ' ')}…")
                    if calls > max_calls:
                        result = {"erro": "Limite de chamadas de ferramenta atingido; "
                                          "responda com o que já tem."}
                    else:
                        result = self.toolbox.call(call.name, args)
                    used_runs.update(filter(None, [args.get("execucao")]))
                    used_runs.update(args.get("execucoes") or [])
                    responses.append(types.Part.from_function_response(
                        name=call.name, response={"resultado": result}))
                contents.append(types.Content(role="user", parts=responses))
        except (Cancelled, AssistantError):
            raise
        except Exception as error:
            raise AssistantError(friendly_error(error)) from error

        answer = "".join(part.text or "" for part in contents[-1].parts if not part.thought)
        self._commit(contents, question, used_runs)
        if self.conversation.get("prompt_tokens", 0) > int(self.settings["summarize_tokens"]):
            on_event("status", "Resumindo o histórico…")
            try:
                self.summarize()
            except Exception:
                pass  # o resumo é otimização; a resposta já foi salva
        on_event("status", "")
        return answer

    def _commit(self, contents, question, used_runs):
        conversation = self.conversation
        conversation["contents"] = [content.model_dump(mode="json", exclude_none=True)
                                    for content in contents]
        if conversation["title"] == "Nova conversa":
            conversation["title"] = question.strip().splitlines()[0][:80]
        # Execuções que a conversa usou, com a versão dos resultados de agora.
        for run in used_runs:
            mtime = (store.run_mtime(os.path.join(self.root, run))
                     if run and os.path.basename(run) == run else None)
            if mtime is None:
                continue  # nome errado do modelo: não é execução citada
            conversation["run_mtimes"][run] = mtime
            if run not in conversation["runs"]:
                conversation["runs"].append(run)
        store.save_conversation(conversation)

    def summarize(self):
        """Resume tudo antes da última pergunta; o disco guarda o original."""
        from google.genai import types

        contents = self._contents()
        questions = [i for i, content in enumerate(contents) if _is_question(content)]
        cut = questions[-1] if questions else 0
        if cut <= self.conversation["summary_upto"]:
            return
        transcript = []
        for content in contents[self.conversation["summary_upto"]:cut]:
            for part in content.parts or []:
                if part.text and not part.thought:
                    transcript.append(f"[{content.role}] {part.text}")
                elif part.function_call:
                    transcript.append(f"[ferramenta] {part.function_call.name}"
                                      f"({dict(part.function_call.args or {})})")
                elif part.function_response:
                    transcript.append(f"[resultado] {part.function_response.response}")
        previous = self.conversation.get("summary")
        text = (f"Resumo anterior:\n{previous}\n\n" if previous else "") + "\n".join(transcript)
        response = self.client.models.generate_content(
            model=self.settings["model"],
            contents=[types.Content(role="user", parts=[types.Part(text=text)])],
            config=types.GenerateContentConfig(system_instruction=SUMMARY_PROMPT))
        if response.text:
            self.conversation["summary"] = response.text
            self.conversation["summary_upto"] = cut
            store.save_conversation(self.conversation)
