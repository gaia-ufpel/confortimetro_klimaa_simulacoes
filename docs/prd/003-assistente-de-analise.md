# PRD — Assistente conversacional para analisar resultados
Status: rascunho · Autor: Gabriel Leite Bessa · Data: 22/09/2026 · RFC relacionado: —

## 1. Problema

Uma simulação gera o `ESTATISTICAS.xlsx`, uma planilha por zona com 52 mil linhas e
gráficos. Tirar conclusão disso ("por que o AC ligou tanto em janeiro?", "o módulo
completo compensa sobre o sem ventilador?") exige cruzar indicadores, séries e
configurações à mão, e boa parte do público do GAIA não sabe onde olhar.

## 2. Usuários e contexto

Pesquisadores e estudantes do GAIA, pela GUI, depois que a simulação terminou: na tela de
detalhes de uma execução ou na tela de comparação.

## 3. Solução proposta

Um painel de chat na GUI. O usuário pergunta em português e o assistente responde com
números tirados das execuções. O modelo não recebe as planilhas: recebe um resumo curto
e chama **ferramentas** (tool use) que rodam **localmente** sobre `results/` e devolvem
só o recorte pedido.

Acesso só por **chave própria (BYOK)**: o usuário cola a própria chave da API Gemini
(Google AI Studio) e a GUI fala direto com o Google, sem servidor intermediário. Modelo
padrão: **Gemini 3.8 Flash**, via SDK `google-genai`.

## 4. Escopo

**Dentro:**
- Aba **Assistente** nos detalhes da execução (a página vira abas: Resumo | Série
  temporal | Assistente — a série vem do PRD 002).
- Botão **Perguntar ao assistente** na tela de Execuções, com as execuções selecionadas
  como contexto; sem seleção, o modelo descobre as execuções com `listar_execucoes`.
- Ferramentas de leitura (seção 6) sobre qualquer execução da raiz, priorizando as do
  contexto.
- Histórico persistido: um JSON por conversa, seletor com Nova / Renomear / Excluir,
  título automático pela primeira pergunta e **Exportar** para `.md`.
- Seção "Assistente" nas Configurações: chave (mascarada, com "Testar chave"), modelo e
  bloco "Avançado" com os limites.

**Fora (por enquanto):**
- Sugerir ou alterar configurações, IDF ou disparar simulações. O assistente só analisa.
- Roteador/servidor próprio com chave compartilhada (descartado).
- Outros provedores e modelo local (Ollama).
- Gerar gráficos pelo chat.

## 5. Requisitos

1. O painel abre com o contexto da execução selecionada (ou das selecionadas) já
   carregado.
2. Toda afirmação numérica vem de ferramenta ou do resumo e cita execução, zona e
   período; sem dado, o assistente diz que não tem. Português técnico.
3. Ferramentas são só de leitura, limitadas às execuções da raiz de saídas; o nome da
   execução não pode conter separador de caminho.
4. Resultado de ferramenta tem teto de tamanho (200 linhas / 20 KB); séries longas
   saem agregadas por hora, dia ou mês.
5. O filtro de `horas_em_condicao` é estruturado (`[{coluna, operador, valor}]`,
   combinados com E, colunas de `series.COLUMNS`, operadores `== != > >= < <=`); nada de
   `eval`/`DataFrame.query`.
6. A chamada ao modelo roda fora da thread do Tkinter, com botão de cancelar. O texto
   final chega em streaming; durante as ferramentas o painel mostra o status.
7. Chave no `keyring` (no Windows, Gerenciador de Credenciais); sem backend, arquivo em
   `app_data_path()`. `GEMINI_API_KEY` no ambiente tem precedência. Nunca no
   `configs.json` nem em log. Sem chave, "Perguntar" abre um diálogo com link para o AI
   Studio.
8. Configurações em `app_data_path()/assistente.json` (fora do `SimulationConfig`, que é
   copiado para cada execução): modelo (padrão `gemini-3.8-flash`), até 20 chamadas de
   ferramenta por pergunta, resumo do histórico acima de 700 mil tokens de prompt
   (`usage_metadata.prompt_token_count`) e timeout de 90 s por chamada.
9. Conversas em `app_data_path()/assistente/conversas/<id>.json` com tudo: perguntas,
   respostas, chamadas e resultados de ferramenta e resumos. O resumo substitui as
   mensagens antigas só no que vai para a API; o arquivo e o painel mantêm tudo.
10. Ao retomar, execução citada que foi recalculada ou apagada gera aviso no painel e no
    prompt. Excluir uma execução não mexe nas conversas.
11. Resposta em Markdown renderizada como HTML (`markdown` + `tkinterweb`), com tabelas.
12. Texto fixo de privacidade no rodapé do painel (os recortes vão ao Google; no plano
    gratuito podem ser usados para treino).
13. Erros de rede, chave inválida, 429 e cota esgotada viram mensagem clara no painel.
14. Funciona no instalador Windows: `tkinterweb`, `tkinterweb_tkhtml` e `keyring` no
    `collect_all` do `.spec`.

## 6. Abordagem técnica (alto nível)

**Cliente** — `confortimetro/assistant/`:
- `client.py`: monta o `genai.Client(api_key=...)` e roda o laço de function calling
  (`generate_content_stream` → executa `function_call` → devolve `function_response` →
  repete até vir só texto). O laço é manual, não o automático do SDK, para cancelar,
  mostrar progresso e guardar tudo. As partes do modelo são guardadas inteiras (com
  `thought_signature`, exigida pelo Gemini 3 nas chamadas de função).
- `store.py`: configurações, chave e conversas em disco.
- `tools.py`: definições e implementação das ferramentas, reaproveitando o que existe:

| Ferramenta | Base existente | Devolve |
|---|---|---|
| `listar_execucoes` | `compare.list_runs` | nome, data, módulo, IDF, EPW |
| `configuracao` | `compare.read_config` | campos do config de uma execução |
| `indicadores` | `ESTATISTICAS.xlsx` / `stats` | estatísticas por zona |
| `comparar` | `compare.compare_runs` | tabela comparativa |
| `serie_agregada` | `series.load_zone_series` | variável de `series.COLUMNS` agregada por hora/dia/mês num período |
| `horas_em_condicao` | `series.load_zone_series` | horas em que um filtro estruturado vale (ex.: AC ligado e sala ocupada) |

- `prompt.py`: prompt de sistema com o domínio (conforto adaptativo ASHRAE 55, PMV, lógica
  do controlador janela → ventilador → AC/DOAS) e a regra de citar números das
  ferramentas.
- GUI: `components/assistant_panel.py`, usado na aba dos detalhes e na página própria
  aberta pela tela de Execuções; seção nas Configurações.
- Testes sem rede: execuções de fixture (sem EnergyPlus) e um cliente Gemini falso com
  `function_call` roteirizadas; teste real só com `GEMINI_API_KEY`.

## 7. Métricas de sucesso

- Perguntas de um roteiro de teste (ex.: 15 perguntas sobre execuções de `examples/`)
  respondidas com número correto em ≥ 90% dos casos.
- Resposta típica em < 20 s.
- Custo médio por conversa (tokens de `usage_metadata`) baixo o bastante para uso com
  chave gratuita/pessoal.

## 8. Riscos, suposições e questões em aberto

- **Barreira de entrada:** cada usuário precisa criar a própria chave no Google AI
  Studio. Mitigação: passo a passo no painel e link direto.
- **Nome do modelo:** o identificador exato do Gemini 3.8 Flash na API precisa ser
  confirmado; fica como campo editável para trocar sem nova versão.
- **Alucinação de número:** mitigada pelo requisito 2 e pelo roteiro de teste.
- **Privacidade:** resumos e recortes das simulações saem da máquina (requisito 12).
- **Leitura lenta das séries:** a primeira leitura de uma zona leva ~22 s; o cache de
  `series` resolve as seguintes. Mostrar "lendo séries…" no painel.

## 9. Rollout

1. Ferramentas + laço de function calling testados pela CLI/testes.
2. Painel na GUI e configuração da chave.
3. Roteiro de avaliação e ajuste do prompt.
