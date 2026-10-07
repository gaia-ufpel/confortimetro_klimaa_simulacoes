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
- **Severidade:** crítico, alto, médio, baixo — consolidados aqui em P0, P1 e P2.

Limitações:

- Personas simuladas não substituem teste com pessoas; servem de triagem antes
  de uma rodada com usuários reais.
- Sem gerenciador de janelas no Xvfb, tooltips e foco em diálogos nem sempre
  funcionaram; esses pontos ficaram sem avaliação conclusiva.
- Só Linux. O Windows, plataforma do usuário final, não foi testado.
- As instâncias paralelas compartilharam `examples/config.json`, o que misturou
  execuções entre agentes (virou achado, ver P1).

## Personas

| Persona | Perfil | Foco do teste | Tela | Tarefas concluídas |
|---|---|---|---|---|
| Juliana, 27 | Mestranda em Arquitetura; sabe a teoria, nunca editou IDF nem usou terminal | Primeiro uso, onboarding, entender parâmetros, achar resultados | 1366×768 | Parcial: configurou e executou, não achou onde ficam as planilhas |
| Prof. Ricardo, 55 | Orientador, 15 anos de EnergyPlus, impaciente | Rapidez, o que muda no IDF, comparar cenários, rastrear execuções | 1920×1080 | Parcial: comparou 3 cenários, não viu pela interface o que muda no IDF |
| Lucas, 20 | Bolsista de IC há 2 semanas; erra muito, não lê textos | Erros comuns e mensagens de erro | 1366×768 | 3 de 5; nenhum crash |
| Fernanda, 38 | Consultora de eficiência energética, notebook Windows | Layout em tela pequena, resultados apresentáveis a cliente | 1280×720, 100% e 125% | 3 de 5; Configurações inacessível |
| Marcos, 45 | Técnico do laboratório; baixa visão, tendinite, deuteranopia | Só teclado, foco, contraste, dependência de cor | 1600×900 | 1 de 5, e com mouse |

## P0 — corrigir primeiro

Resultado errado, perda de controle sobre a simulação ou bloqueio de um grupo
inteiro de usuários.

| # | Problema | Evidência | Personas | Onde |
|---|---|---|---|---|
| 1 | "PMV fora da faixa (%)" usa ±0,5 fixo e ignora `pmv_lowerbound`/`pmv_upperbound` | Execução configurada para ±0,7 reporta o percentual com ±0,5; a faixa sombreada do gráfico "Distribuição do PMV" também | Ricardo | `confortimetro/results/stats.py:174` (`pmv.abs() > 0.5`) |
| 2 | Fechar a janela durante a simulação some com a interface, mas o processo continua | `main.py` seguiu com ~40% de CPU e `eplusout.eso` crescendo, sem janela | Lucas | `MainWindow` não trata `WM_DELETE_WINDOW` |
| 3 | Período editado no formulário é ignorado sem aviso | Fim em 31/01 rodou o ano inteiro; `in.idf` ficou 01/01–31/12; só vale após "Salvar como novo IDF". A configuração duplicada voltou a 31/12 | Ricardo, Marcos | Aba Período |
| 4 | Valores inválidos de PMV, clo e AC são trocados em silêncio | Vazio vira −3, "abc" vira 2, 5 vira 3, mínimo maior que máximo é invertido; a simulação roda com valores que o usuário não escolheu | Lucas | Abas Conforto e Equipamentos |
| 5 | Arquivo que não é IDF é aceito como IDF | `.epw` e `.txt` mostram "✓ Arquivo encontrado"; o app oferece incluir equipamentos e grava `..._INMET_equipamentos.epw` com objetos de IDF colados; o erro final fala em "zonas inexistentes" | Lucas | Seletor de IDF |
| 6 | Nenhum botão responde a Enter ou Espaço, e o foco neles é invisível | Nova execução, Validar e executar, Parar, Salvar, Carregar, Procurar e Voltar só funcionam com mouse | Marcos | `RoundedButton` em `confortimetro/gui/theme.py:568`; corrigir o componente resolve todos |

## P1 — alto

### Execução e progresso

- Barra de progresso de 2 px, sem porcentagem, data simulada ou tempo restante;
  o log fica parado em "Executando simulação EnergyPlus…" por minutos e a barra
  em ~1%. Anual ≈ 100 min, e a tela não avisa. *Juliana, Ricardo, Lucas, Fernanda.*
- "Parar simulação" interrompe sem confirmação; no duplo clique em Executar, o
  segundo clique cai em Parar. *Lucas, Juliana, Fernanda.*
- Execução interrompida aparece como "modelo.idf / 0 zonas / sem planilhas" e
  conta como erro, não como "interrompida". *Juliana, Lucas, Ricardo.*
- Abertura leva 45–50 s sem janela nem aviso de carregamento. *Juliana.*

### Layout e tela pequena

- Janela abre com 1200×900 fixo em y = −90: barra de título e rodapé/log
  cortados em 768 e 720 px. *Todas.*
- Com o log aberto em 1366×768, os campos Met, Wme e Clo ficam escondidos, sem
  rolagem. *Lucas.*
- A 125% com 640 px de altura, as seções "Vestimenta" e "Janela" ficam com
  altura zero. *Fernanda.*
- Página Configurações não rola: cards "Servidor de simulações" e "Google
  Drive" ficam fora da tela em 720p, e o toast "Compartilhar" manda o usuário
  para lá. *Fernanda.*
- Abaixo de ~700 px de altura, "Comparar selecionadas" e "Regerar estatísticas"
  somem. Diálogos de equipamento são maiores que a tela. *Fernanda, Lucas.*

### Estado gravado no repositório

- "Salvar" grava `examples/config.json` sem perguntar, ignorando
  `AMBIENS_DATA_DIR`; o arquivo leva o caminho da pasta de dados, e outra
  instância passou a listar as execuções alheias. *Marcos, Lucas.*
- "Salvar como novo IDF" grava `<nome>_editado.idf` em `examples/`, sem diálogo,
  sobrescrevendo o anterior. *Ricardo.*

### Transparência e rastreabilidade

- A interface não mostra o que o Ambiens altera no IDF: Schedule:Constant de
  clo (0,7 → 0,5), setpoints do AC, nome do RunPeriod e +28 Output:Variable. O
  botão "Editar IDF" só pula para a aba Período. *Ricardo.*
- Concluídas, todas as execuções aparecem como "modelo.idf"; o IDF de origem
  some da lista e do detalhe. Execuções não têm nome (gráficos mostram só
  "1824/1833"). *Ricardo.*

### Parâmetros e orientação

- Nenhum campo de Conforto, Equipamentos e Ocupação tem ajuda: "Banda de
  conforto" vs "Faixa de PMV", Wme, "Variação do Clo", "Margem do adaptativo
  90 %" (que vira "2.5 °C" no detalhe), "Valor do método". Rótulos truncados.
  *Juliana, Ricardo, Lucas.*
- O seletor de módulo, a escolha mais importante, fica na última aba (Zonas),
  com opções cortadas e sem descrição. *Juliana, Ricardo.*
- O app não diz onde ficam as planilhas nem o formato; o caminho não aparece no
  detalhe; os 6 ícones de ação não têm rótulo. *Juliana.*

### Resultados

- Comparação mostra "Energia anual" e "kWh/ano" para simulação de 1 semana.
  *Ricardo.*
- Gráfico "Energia × desconforto" diz "%" mas mostra fração (0,0375).
  *Ricardo, Fernanda.*
- Tabela da série temporal soma temperaturas ("941917,3 °C"). *Fernanda.*
- XLSX exportado traz frações cruas na aba "Sheet1". Não há horas em conforto,
  só % e timesteps. *Fernanda.*
- Regerar estatísticas leva 10–20 min sem progresso; Exportar ZIP fica inerte
  enquanto isso; falha vira `KeyError`/`ValueError` cru num toast de 10 s; o
  resfriamento mudou de 96,87 para 143,52 kWh sem aviso. *Fernanda, Lucas.*
- O assistente recomenda "regerar estatísticas" numa execução interrompida, o
  que termina em `ValueError`. *Lucas.*

### Teclado

- Lista de execuções não seleciona com setas, Enter não abre detalhe; salas da
  aba Zonas não são removíveis por teclado; nenhum atalho; Esc não volta.
  *Marcos, Ricardo.*

## P2 — médio e baixo

### Contraste (WCAG 2.x)

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

### Cor e tamanho

- Sob deuteranopia, ok/aviso/erro viram o mesmo oliva (1,09 a 1,43:1 entre si);
  ícone e texto salvam a informação, mas são pequenos.
- Paleta dos gráficos tem três verdes; barra de diferença usa só vermelho e
  verde (visto no código; a execução cancelada não gerou gráficos).
- Fontes fixas (8–10 pt), sem opção de tamanho; gráficos com ~8 px não escalam
  com o DPI.

### Texto e consistência

- Mistura PT/EN: "COMPLETE" na lista vs "Completo" no editor; filtro do log
  "all"; meses em inglês nos gráficos; números ora pt-BR, ora en.
- "0 execuções" com uma linha na tabela; "1 execuções".
- Rodapé manda clicar em "Ver detalhes", mas o botão é "Ver em andamento".
- "Período: consulte o IDF" no detalhe; "Chave salva." sob campo vazio.
- Mensagens de erro com nomes internos (`met`, `clo_min`).
- Cards da lista cortados ("SCONFORTO TÉRMI").

### Onboarding e diálogos

- Último botão diz "Abrir o editor", o texto fala em "Nova execução".
- "Tudo pronto" aparece ao lado de "Baixar o EnergyPlus".
- Rodando do repositório, sem `AMBIENS_ONBOARDING=1`, não há onboarding e a
  tela inicial fica vazia.
- Diálogo de arquivo abre na raiz do repositório (`.git`, `.venv`,
  `node_modules`).

### Outros

- Os 45 warnings do EnergyPlus não aparecem na interface.
- Sem fila de execuções.
- Três métricas de desconforto diferentes, sem explicação.
- Sem tema escuro.

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
