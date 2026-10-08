# Pesquisa de usabilidade — Ambiens desktop

Rodada de 07/10/2026. Cinco personas simuladas encontraram cerca de 100
problemas na interface Tkinter; 6 são prioridade máxima, e um deles é erro de
cálculo nas estatísticas, não só de usabilidade.

Quatro temas apareceram em 3 ou mais personas:

- progresso opaco: barra de 2 px sem porcentagem nem tempo restante, numa
  simulação anual de cerca de 100 min;
- janela de 1200×900 fixa, que não cabe em notebook de 768 ou 720 px de altura;
- "Parar simulação" sem confirmação, inclusive quando acionado por duplo
  clique em Executar;
- parâmetros técnicos (PMV, Wme, clo, margem adaptativa) sem explicação, e
  execuções sem nome na lista.

## Método

Cinco agentes de IA, cada um no papel de uma persona do público-alvo, operaram
a interface real em paralelo.

- **Ambiente:** cada agente abriu `main.py` num display Xvfb próprio, na
  resolução da persona (1280×720 a 1920×1080), com dados isolados por
  `AMBIENS_DATA_DIR`.
- **Interação:** cliques e teclado com `xdotool`, capturas com ImageMagick
  (`import -window root`). O julgamento vem do que aparece na tela; o código só
  foi lido para achar widgets ou confirmar a causa de um defeito.
- **Cenário comum:** `examples/idf/FAURB/FAURB_PTHP_ENTORNO.idf`, clima
  `BRA_RS_Camaqua.869890_INMET.epw`, EnergyPlus 9.4.0.
- **Simulações:** as anuais foram canceladas após 2 a 4 min. Ricardo concluiu
  3 simulações de 1 semana para usar a comparação; Fernanda copiou 4 execuções
  existentes (2 no formato antigo) para ver resultados.
- **Severidade:** crítico, alto, médio, baixo — consolidados aqui em P0, P1 e P2
  e agrupados pela tela onde aparecem.

Limitações:

- Personas simuladas não substituem teste com pessoas; servem de triagem antes
  de uma rodada com usuários reais.
- Sem gerenciador de janelas no Xvfb, tooltips e foco em diálogos nem sempre
  funcionaram; esses pontos ficaram sem avaliação conclusiva.
- Só Linux. O Windows, plataforma do usuário final, não foi testado.
- As instâncias paralelas compartilharam `examples/config.json`, o que misturou
  execuções entre agentes (virou achado, ver Execução).

## Personas

| Persona | Perfil | Foco do teste | Tela | Tarefas concluídas |
|---|---|---|---|---|
| Juliana, 27 | Mestranda em Arquitetura; sabe a teoria, nunca editou IDF nem usou terminal | Primeiro uso, onboarding, entender parâmetros, achar resultados | 1366×768 | Parcial: configurou e executou, não achou onde ficam as planilhas |
| Prof. Ricardo, 55 | Orientador, 15 anos de EnergyPlus, impaciente | Rapidez, o que muda no IDF, comparar cenários, rastrear execuções | 1920×1080 | Parcial: comparou 3 cenários, não viu pela interface o que muda no IDF |
| Lucas, 20 | Bolsista de IC há 2 semanas; erra muito, não lê textos | Erros comuns e mensagens de erro | 1366×768 | 3 de 5; nenhum crash |
| Fernanda, 38 | Consultora de eficiência energética, notebook Windows | Layout em tela pequena, resultados apresentáveis a cliente | 1280×720, 100% e 125% | 3 de 5; Configurações inacessível |
| Marcos, 45 | Técnico do laboratório; baixa visão, tendinite, deuteranopia | Só teclado, foco, contraste, dependência de cor | 1600×900 | 1 de 5, e com mouse |

## Achados por tela

Cada achado leva a prioridade entre colchetes e as personas que o viram.
**P0** = resultado errado, perda de controle ou bloqueio de um grupo de
usuários; **P1** = alto; **P2** = médio ou baixo. Os nomes de tela seguem o
título exibido no app (`_page_nav` em `confortimetro/gui/main_window.py`).

| Tela | P0 | P1 | P2 |
|---|---|---|---|
| Janela e abertura | — | 2 | — |
| Boas-vindas (onboarding) | — | — | 3 |
| Execuções | — | 4 | 4 |
| Execução (editor) | 4 | 12 | 4 |
| Detalhes da execução | — | 3 | 2 |
| Comparação de resultados | — | 2 | 2 |
| Configurações | — | 1 | 1 |
| Assistente de análise | — | 1 | — |
| Transversal (todas as telas) | 2 | 1 | 6 |

### Janela e abertura

- **[P1]** Abertura leva 45–50 s sem janela nem aviso de carregamento.
  *Juliana.*
- **[P1]** Janela abre com 1200×900 fixo em y = −90: barra de título e
  rodapé/log cortados em 768 e 720 px. *Todas.*

### Boas-vindas (onboarding)

- **[P2]** Último botão diz "Abrir o editor", o texto fala em "Nova execução".
  *Juliana.*
- **[P2]** "Tudo pronto" aparece ao lado de "Baixar o EnergyPlus". *Juliana.*
- **[P2]** Rodando do repositório, sem `AMBIENS_ONBOARDING=1`, não há onboarding
  e a tela inicial fica vazia. *Juliana.*

### Execuções

- **[P1]** Concluídas, todas as execuções aparecem como "modelo.idf"; o IDF de
  origem some. Execuções não têm nome. *Ricardo.*
- **[P1]** Execução interrompida aparece como "0 zonas / sem planilhas" e conta
  como erro, não como "interrompida". *Juliana, Lucas, Ricardo.*
- **[P1]** Abaixo de ~700 px de altura, "Comparar selecionadas" e "Regerar
  estatísticas" somem. *Fernanda.*
- **[P1]** Lista não seleciona com setas, Enter não abre detalhe. *Marcos.*
- **[P2]** "0 execuções" com uma linha na tabela; "1 execuções". *Juliana.*
- **[P2]** Módulo em inglês ("COMPLETE") enquanto o editor diz "Completo".
  *Juliana.*
- **[P2]** Cards cortados ("SCONFORTO TÉRMI"). *Fernanda.*
- **[P2]** Linha selecionada com contraste de 1,18:1. *Marcos.*

### Execução (editor)

Inclui as abas Arquivos, Período, Conforto, Equipamentos, Ocupação e Zonas, o
log e a barra de progresso.

**Arquivos**

- **[P0]** Arquivo que não é IDF é aceito: `.epw` e `.txt` mostram "✓ Arquivo
  encontrado"; o app oferece incluir equipamentos e grava
  `..._INMET_equipamentos.epw` com objetos de IDF colados; o erro final fala em
  "zonas inexistentes". *Lucas.*
- **[P1]** "Salvar" grava `examples/config.json` sem perguntar, ignorando
  `AMBIENS_DATA_DIR`; instâncias paralelas passaram a listar execuções alheias.
  *Marcos, Lucas.*
- **[P1]** "Salvar como novo IDF" grava `<nome>_editado.idf` em `examples/`, sem
  diálogo, sobrescrevendo o anterior. *Ricardo.*
- **[P2]** Diálogo de arquivo abre na raiz do repositório (`.git`, `.venv`,
  `node_modules`). *Juliana.*

**Período**

- **[P0]** Período editado é ignorado sem aviso: fim em 31/01 rodou o ano
  inteiro; `in.idf` ficou 01/01–31/12; só vale após "Salvar como novo IDF". A
  configuração duplicada voltou a 31/12. *Ricardo, Marcos.*
- **[P1]** "Editar IDF" só pula para esta aba; a interface não mostra o que o
  Ambiens altera no IDF (clo 0,7 → 0,5, setpoints do AC, nome do RunPeriod, +28
  Output:Variable). *Ricardo.*

**Conforto, Equipamentos e Ocupação**

- **[P0]** Valores inválidos de PMV, clo e AC são trocados em silêncio: vazio
  vira −3, "abc" vira 2, 5 vira 3, mínimo maior que máximo é invertido. *Lucas.*
- **[P1]** Nenhum campo tem ajuda: "Banda de conforto" vs "Faixa de PMV", Wme,
  "Variação do Clo", "Margem do adaptativo 90 %", "Valor do método". Rótulos
  truncados. *Juliana, Ricardo, Lucas.*
- **[P1]** Com o log aberto em 1366×768, Met, Wme e Clo ficam escondidos, sem
  rolagem. *Lucas.*
- **[P1]** A 125% com 640 px de altura, "Vestimenta" e "Janela" ficam com
  altura zero. *Fernanda.*
- **[P1]** Diálogos de equipamento maiores que a tela. *Lucas.*
- **[P2]** Mensagens de erro com nomes internos (`met`, `clo_min`). *Lucas.*

**Zonas**

- **[P1]** O seletor de módulo, a escolha mais importante, fica nesta última
  aba, com opções cortadas e sem descrição. *Juliana, Ricardo.*
- **[P1]** Salas não são removíveis por teclado. *Marcos.*

**Execução, progresso e log**

- **[P0]** Fechar a janela durante a simulação some com a interface, mas o
  processo continua (~40% de CPU, `eplusout.eso` crescendo). `MainWindow` não
  trata `WM_DELETE_WINDOW`. *Lucas.*
- **[P1]** Barra de progresso de 2 px, sem porcentagem, data simulada ou tempo
  restante; log parado em "Executando simulação EnergyPlus…" e barra em ~1%.
  Anual ≈ 100 min, sem aviso. *Juliana, Ricardo, Lucas, Fernanda.*
- **[P1]** "Parar simulação" interrompe sem confirmação; no duplo clique em
  Executar, o segundo clique cai em Parar. *Lucas, Juliana, Fernanda.*
- **[P1]** Os 45 warnings do EnergyPlus não aparecem. *Ricardo.*
- **[P2]** Rodapé manda clicar em "Ver detalhes", mas o botão é "Ver em
  andamento". *Juliana.*
- **[P2]** Filtro do log em inglês ("all"); aviso do log com contraste de
  4,38:1. *Juliana, Marcos.*

### Detalhes da execução

- **[P1]** Não diz onde ficam as planilhas nem o formato; o caminho da pasta
  não aparece; os 6 ícones de ação não têm rótulo. *Juliana.*
- **[P1]** Regerar estatísticas leva 10–20 min sem progresso; Exportar ZIP fica
  inerte enquanto isso; falha vira `KeyError`/`ValueError` cru num toast de
  10 s; o resfriamento mudou de 96,87 para 143,52 kWh sem aviso. *Fernanda,
  Lucas.*
- **[P1]** Tabela da série temporal soma temperaturas ("941917,3 °C"); XLSX
  exportado traz frações cruas na aba "Sheet1"; não há horas em conforto, só %
  e timesteps. *Fernanda.*
- **[P2]** "Período: consulte o IDF"; "Margem 90 %" do formulário vira
  "2.5 °C" aqui. *Juliana, Ricardo.*
- **[P2]** Três métricas de desconforto diferentes, sem explicação. *Fernanda.*

O defeito do limiar de PMV aparece aqui e na comparação; está em Transversal.

### Comparação de resultados

- **[P1]** "Energia anual" e "kWh/ano" para simulação de 1 semana. *Ricardo.*
- **[P1]** "Energia × desconforto" diz "%" mas mostra fração (0,0375); eixo Y
  entre "%" e "fração". *Ricardo, Fernanda.*
- **[P2]** Gráficos identificam execuções só pelo número ("1824/1833").
  *Ricardo.*
- **[P2]** Paleta com três verdes; barra de diferença só em vermelho e verde
  (visto no código). *Marcos.*

### Configurações

- **[P1]** A página não rola: cards "Servidor de simulações" e "Google Drive"
  ficam fora da tela em 720p, e o toast "Compartilhar" manda o usuário para lá.
  *Fernanda.*
- **[P2]** "Chave salva." sob campo de chave vazio. *Juliana.*

### Assistente de análise

- **[P1]** Recomenda "regerar estatísticas" numa execução interrompida, o que
  termina em `ValueError`. *Lucas.*

### Transversal (todas as telas)

- **[P0]** "PMV fora da faixa (%)" usa ±0,5 fixo e ignora
  `pmv_lowerbound`/`pmv_upperbound`; a faixa sombreada de "Distribuição do PMV"
  também. Afeta Detalhes, Comparação e as planilhas.
  `confortimetro/results/stats.py:174`. *Ricardo.*
- **[P0]** Nenhum botão responde a Enter ou Espaço, e o foco neles é
  invisível. `RoundedButton` em `confortimetro/gui/theme.py:568`; corrigir o
  componente resolve todos. *Marcos.*
- **[P1]** Nenhum atalho de teclado; Esc não volta de tela. *Marcos, Ricardo.*
- **[P2]** Contraste abaixo do WCAG (tabela abaixo).
- **[P2]** Sob deuteranopia, ok/aviso/erro viram o mesmo oliva (1,09 a 1,43:1
  entre si); ícone e texto salvam a informação, mas são pequenos. *Marcos.*
- **[P2]** Fontes fixas (8–10 pt), sem opção de tamanho; gráficos com ~8 px não
  escalam com o DPI. *Marcos, Fernanda.*
- **[P2]** Mistura PT/EN e formatos numéricos; meses em inglês nos gráficos.
  *Fernanda, Juliana.*
- **[P2]** Sem fila de execuções. *Ricardo.*
- **[P2]** Sem tema escuro. *Fernanda.*

#### Contraste (WCAG 2.x)

Cores de `confortimetro/gui/theme.py`. Mínimo 4,5:1 para texto, 3:1 para
componentes (1.4.11).

| Par | Frente | Fundo | Razão | Resultado |
|---|---|---|---|---|
| Texto principal | `#1c1c1c` | `#fafafa` | 16,33:1 | passa |
| text_mute | `#406346` | `#fafafa` | 6,51:1 | passa |
| Branco sobre primary | `#ffffff` | `#3a5a40` | 7,73:1 | passa |
| Branco sobre hover primary_h | `#ffffff` | `#588157` | 4,48:1 | **reprova** |
| Branco sobre selo warn | `#ffffff` | `#a06b00` | 4,57:1 | passa no limite |
| warn: log de aviso | `#a06b00` | `#fafafa` | 4,38:1 | **reprova** |
| danger: erro / campo inválido | `#b3261e` | `#fafafa` | 6,26:1 | passa |
| accent: link do rodapé | `#a3b18a` | `#f0f0f0` | 2,00:1 | **reprova** |
| Borda de campo/botão (`line`) | `#d8d8d8` | `#fafafa` | 1,37:1 | **reprova** |
| Linha selecionada na lista | `#e7e7e7` | `#fafafa` | 1,18:1 | **reprova** |
| Trilho do slider / scrollbar | `#c2c2c2` | `#fafafa` | 1,71:1 | **reprova** |
| Barra de progresso | `#176bba` | `#fafafa` | 5,23:1 | passa, mas tem 2 px |

## O que preservar

- Onboarding curto, com detecção automática do EnergyPlus; "Detectar" corrige
  caminho errado.
- Vírgula decimal aceita em todos os campos; erros claros nos campos simples.
- IDF, EPW e EnergyPlus vêm preenchidos; zonas aparecem como chips.
- Ao executar, botão, status e log mudam na hora; parar leva ~3 s e termina limpo.
- "Duplicar para nova execução" é ótimo para montar cenários.
- Detalhe denso, com o `configs.json` completo, versão e commit do código; cada
  execução guarda `modelo.idf`, `in.idf` e `expanded.idf`.
- Comparação com 8 gráficos; série temporal com inspetor de timestep;
  exportação em PNG.
- Texto principal com 16:1 de contraste; status com ícone + texto; abas trocam
  com setas; diálogo de arquivo funciona por teclado.
- O assistente explica PMV e clo de forma didática e mostra aviso de privacidade.

## Próximos passos

1. Corrigir o limiar de PMV em `stats.py` e regerar as estatísticas das
   execuções já entregues — afeta números usados em trabalhos.
2. Tratar `WM_DELETE_WINDOW` (confirmar e encerrar o EnergyPlus) e pedir
   confirmação em "Parar"; desabilitar Executar por ~1 s após o clique.
3. Validar entradas: IDF pela extensão e conteúdo, faixas numéricas com erro
   visível em vez de troca silenciosa, período aplicado ou bloqueado com aviso.
4. Dar ao `RoundedButton` foco visível e ativação por Enter/Espaço; depois,
   setas e Enter na lista de execuções e Esc para voltar.
5. Gravar configuração e IDF editado em `paths.app_data_path()`, nunca no
   repositório.
6. Janela com tamanho relativo à tela e área de formulário rolável; Configurações
   rolável.
7. Progresso com data simulada, porcentagem e tempo restante.
8. Tooltips e descrição dos módulos; mover o módulo para a primeira aba.
9. Corrigir unidades e rótulos dos resultados (kWh no período, % vs fração,
   não somar temperaturas).
10. Ajustar as cores que reprovam no WCAG e trocar a paleta dos gráficos por uma
    segura para daltonismo.
11. Repetir a rodada com 3 a 5 usuários reais, incluindo uma no Windows.

---

# 2ª rodada — versão 0.8.0 (`8966f72`)

Rodada de 07/10/2026, à noite, depois das correções de `cf13421`. Mesmas cinco
personas, mesmo método e cenário; desta vez cada agente usou Xvfb e
`AMBIENS_DATA_DIR` próprios, e ninguém gravou em `examples/` (`git status`
limpo nas cinco). Ricardo e Fernanda concluíram simulações de 1 semana
(5 no total); Lucas rodou e parou várias.

Dos achados da 1ª rodada, quase todos os P0 e a maior parte dos P1 ficaram
corrigidos. A rodada achou 3 P0 novos — um deles regressão do próprio
`cf13421` — e repetiu alguns P1 em várias personas.

| Persona | Tarefas | Antes → agora |
|---|---|---|
| Juliana | 8 de 9, 1 parcial | 18 achados: 11 corrigidos, 5 parciais, 1 persiste, 1 não verificável |
| Ricardo | 7 de 7 | comparou 3 cenários; números batem com a configuração |
| Lucas | 11 de 18, 6 parciais | nenhum arquivo errado passou; 1 crash novo |
| Fernanda | 4 de 8, 3 parciais | janela cabe em 720p e 125%; Regerar travou |
| Marcos | 4 de 5 só com teclado | era 1 de 5, e com mouse |

## Corrigido nesta rodada

- **[P0] Toda simulação bem-sucedida terminava como "Simulação falhou".** O
  resumo novo "N warnings e 0 severe errors" caía no teste `"error" in lower`
  de `_handle_simulation_message`; o selo ficava vermelho e a execução não ia
  ao Drive nem abria os detalhes. Agora o resumo sai com o prefixo `WARNING `,
  como o `PROGRESS `, e entra no log como aviso. *Todas.*
- **[P0] Zona sem `PEOPLE_<ZONA>` derrubava o app (segfault, exit 139).** O
  controlador parava no primeiro timestep e o EnergyPlus 9.4 caía ao gravar a
  saída; reproduzido pela CLI. `rooms_without_people` barra a zona antes de
  simular, na GUI e em `validate_idf`, sem passar pelo "Rodar mesmo assim" do
  equipamento. No FAURB, 9 das 16 zonas não têm People. *Lucas.*
- **[P0] "Regerar estatísticas" travava para sempre no Linux.** O
  `ProcessPoolExecutor` usava `fork` com as threads da GUI vivas e os workers
  ficavam em `futex_wait`. Agora usa `spawn`, como no Windows; com Tk ativo,
  regerou 2 execuções em 69 s. *Fernanda.*

## Pendente

**P1**

- Aviso falso "Período de 365 dias… 1–2 h" com período editado:
  `_warn_long_run` (`main_window.py`) lê o IDF original e ignora
  `run_period_start/end`. *Juliana, Ricardo, Lucas, Marcos, Fernanda.*
- "Editar IDF" depois de Duplicar recarrega o IDF e volta o Fim para 31/12 sem
  aviso (`IDFEditorPanel.load`); Ricardo rodou um ano sem querer. *Ricardo.*
- Selo e log da execução anterior não são limpos; o contador soma erros
  antigos. *Juliana, Ricardo, Marcos, Lucas, Fernanda.*
- "Passos por hora" aceita valor que não divide 60; o pós-processamento falha
  ~3 min depois. *Lucas.*
- Falha no pós-processamento aparece como "Interrompida", e o Assistente diz
  que não há dados brutos. *Lucas.*
- Comparação: "Carpete anual" estica 1 semana sobre o ano (`extent=[1, 365]`);
  "Semana típica" abre vazia em 1970; "Exportar CSV" some ao trocar de gráfico;
  rótulos arredondam 0,6 kWh para "1". *Fernanda.*
- Seleção múltipla na lista só com Ctrl+clique: Comparação inalcançável por
  teclado. *Marcos.*
- Botões desabilitados recebem Tab sem anel (`theme.py`); Configurações não
  rola atrás do foco. *Marcos.*
- A 125%, Detalhes fica com a tabela por zona em altura zero. *Fernanda.*

**P2**

- Execuções indistinguíveis na lista ("FAURB_PTHP_ENTORNO · 07/…"), sem nome;
  lista usa a hora de modificação e a comparação a de início. *Juliana,
  Ricardo, Marcos, Fernanda.*
- Desconforto 0 %, PMV fora 20–31 % e fora da banda adaptativa 24 % lado a
  lado, sem explicação; a tela não diz que o PMV é o do controlador, não o
  Fanger do EnergyPlus. *Juliana, Ricardo, Fernanda.*
- Ctrl+A não seleciona o campo, e o que se digita é colado ao valor antigo;
  campos de PMV/clo às vezes recebem foco sem seleção. *Juliana, Lucas, Marcos,
  Fernanda.*
- Validação incompleta: velocidade −2 e Met vazio sem borda vermelha; um erro
  por vez; slider desenha −3 ou faixa invertida. *Lucas.*
- Resto de inglês: filtro "all", "COMPLETE" na comparação, "True", números com
  ponto. *Todas.*
- Cards e rótulos cortados ("ESCONFORT", "Ajustar Clo antes dos equipame…").
- Contraste: `#f67a24` em texto (2,60:1), anotação `#009e73` (3,28:1); aviso e
  erro oliva sob deuteranopia (1,50:1). *Marcos.*
- Abertura ainda leva ~26–45 s até a tela utilizável, agora com splash.
  *Juliana, Ricardo.*

## O que melhorou

- Os números: "PMV fora" respeita a faixa de cada execução, energia no
  período, período editado chega ao `in.idf` e passa pelo Duplicar.
- Arquivo errado barrado na hora; valor inválido fica vermelho e não é trocado.
- Parar e fechar a janela pedem confirmação, e fechar encerra o EnergyPlus.
- Progresso com % e tempo restante; Esc, F5 e Ctrl+Enter; anel de foco nos
  botões; setas e Enter na lista.
- Janela proporcional à tela; Configurações e abas rolam.
- Configuração e IDF editado na pasta de dados do app.
