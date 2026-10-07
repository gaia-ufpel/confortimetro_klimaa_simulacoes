# por que o desconforto em SEC_LINSE ficou tão alto?

Execuções: 20260926_1420

## Pergunta

por que o desconforto em SEC_LINSE ficou tão alto?

## Assistente

Na execução **`20260926_1420`**, a sala **`SEC_LINSE`** apresentou um índice de **Desconforto de 0,0932 (9,32%)**, sendo o maior entre todas as zonas do edifício (por comparação: `RECEPCAO` teve 7,02%, `ATELIE2` 4,71%, `SALA_AULA` 4,20%, `ATELIE1` 3,74%, `ATELIE3` 3,70% e `LINSE` 1,33%).

A análise dos dados revela os seguintes motivos:

---

### 1. O desconforto é exclusivamente por frio
* **Zero desconforto no verão:** Nos meses mais quentes (janeiro a março, novembro e dezembro), o desconforto ocupado foi de **0 horas** (`em_conforto = 1,0` em 100% dos timesteps ocupados). O resfriamento artificial sequer precisou ser acionado no ano (0% do tempo).
* **Concentração no inverno/meia-estação:** Todas as **257,33 horas de desconforto** ocorrem entre abril e outubro, com concentração crítica nos meses mais frios:
  * **Junho:** 78,00 h de desconforto (PMV médio ocupado de -0,64; mínima operativa de 9,69 °C; PMV mínimo de -2,64)
  * **Agosto:** 55,00 h de desconforto (PMV médio ocupado de -0,54; mínima operativa de 10,34 °C)
  * **Julho:** 43,33 h de desconforto (PMV médio ocupado de -0,44)
  * **Setembro:** 38,33 h de desconforto (PMV médio ocupado de -0,43)
  * **Maio:** 24,50 h de desconforto
  * **Abril e Outubro:** 10,67 h e 7,50 h, respectivamente

---

### 2. O aquecimento opera, mas não vence a carga térmica / inércia
* **AC ligado quase todo o tempo em desconforto:** Das 257,33 horas em que a sala esteve ocupada e em desconforto, em **256,67 horas o ar-condicionado já estava ligado em modo aquecimento**.
* **Maior uso de aquecimento do edifício:** O aquecimento em `SEC_LINSE` foi acionado durante **19,12% dos timesteps anuais** (o maior percentual de aquecimento entre todas as salas), consumindo **349,36 kWh**.
* **Perda de calor entre turnos (partidas a frio):** Como o sistema desliga nos períodos desocupados (à noite e no intervalo das 12h às 14h), a temperatura operativa da sala despenca para 10 °C a 12 °C nos dias frios de inverno.
* **Recuperação térmica lenta:** Ao início de cada turno de ocupação (às 08h, 14h e 19h), o equipamento entra em capacidade de aquecimento, mas a sala demora vários timesteps para atingir temperaturas operativas suficientes para elevar o PMV acima de -0,50. Mesmo após horas ligado, em dias rigorosos a temperatura operativa estabiliza próxima a 18 °C–19 °C, insuficiente para trazer o PMV para a faixa neutra com a atividade e vestimenta consideradas.

---

### 3. Baixo ganho interno
Diferente das salas de aula e ateliês, que concentram grande número de ocupantes e equipamentos elétricos (gerando calor interno que atenua o frio), a `SEC_LINSE` tem menor densidade de carga interna. Como resultado, o ambiente perde calor rapidamente pelas superfícies e depende quase que exclusivamente do sistema de aquecimento para não resfriar.

---

### Síntese dos Indicadores (`SEC_LINSE` vs. Média das demais)

| Métrica | SEC_LINSE | Média das outras 6 zonas |
| :--- | :---: | :---: |
| **Desconforto total** | **0,0932 (9,32%)** | 0,0412 (4,12%) |
| **PMV médio ocupado** | **-0,1242** | -0,0145 |
| **Fora da banda adaptativa** | **0,4919 (49,19%)** | 0,4146 (41,46%) |
| **Tempo com aquecimento ligado** | **0,1912 (19,12%)** | 0,1118 (11,18%) |
| **Tempo com resfriamento ligado** | **0,0000 (0,00%)** | 0,0079 (0,79%) |

## Pergunta

gostaria de ter alguma tool a mais que permita fazer analises mais precisas?

## Assistente

Sim, para aprofundar diagnósticos como o de `SEC_LINSE` e evitar a necessidade de inferências, algumas ferramentas adicionais trariam ganhos analíticos significativos:

---

### 1. Inspeção de Parâmetros do IDF e Envelope (`inspecionar_zona` ou `dados_geometricos`)
* **O que falta:** As ferramentas atuais não informam as características físicas da zona simulada.
* **Benefício:** Permitiria consultar diretamente:
  * Área de piso ($m^2$), volume ($m^3$) e pé-direito;
  * Área e orientação das fachadas externas e janelas (WWR);
  * Cargas internas nominais (densidade de ocupação $pessoas/m^2$, potência de iluminação e equipamentos em $W/m^2$).
* **Aplicação prática:** Confirmaria de imediato se o resfriamento excessivo de `SEC_LINSE` decorre de alta área de fachada externa voltada para quadrantes frios (ex.: Sul), maior taxa de infiltração ou ausência de equipamentos gerando calor interno.

---

### 2. Balanço Térmico da Zona (`balanco_termico`)
* **O que falta:** Não há acesso às componentes de ganho e perda de calor da zona (*Zone Heat Balance* do EnergyPlus).
* **Benefício:** Extrair as trocas térmicas integradas (kWh) por mecanismo:
  * Condução através de paredes, piso e cobertura;
  * Ganhos solares pelas aberturas;
  * Trocas por infiltração e ventilação natural;
  * Ganhos internos sensíveis (pessoas, luzes, equipamentos);
  * Calor adicionado/removido pelo sistema HVAC.
* **Aplicação prática:** Responderia com exatidão *por onde* a sala perde calor no inverno e qual parcela foi suprida pelo PTHP.

---

### 3. Dimensionamento e Desempenho do HVAC (`inspecionar_hvac`)
* **O que falta:** Não é possível verificar a capacidade nominal e o fator de sobrecarga do equipamento de climatização (PTHP).
* **Benefício:** Permitiria checar:
  * Capacidade de aquecimento e resfriamento dimensionada ($W$);
  * Vazão nominal de ar ($m^3/s$);
  * Horas de carga não atendida (*unmet load hours*);
  * Comparativo entre a potência demandada e a capacidade máxima entregue a cada timestep.
* **Aplicação prática:** Esclareceria se a dificuldade em atingir conforto em `SEC_LINSE` foi causada por subdimensionamento da serpentina de aquecimento ou por limitação da vazão de ar do sistema.

---

### 4. Setpoints Dinâmicos e Sinais do Controlador (`sinais_controle`)
* **O que falta:** Acompanhar as variáveis intermediárias geradas pelo algoritmo do Ambiens.
* **Benefício:** Monitorar:
  * O setpoint de temperatura calculado pelo algoritmo de PMV a cada instante;
  * A vestimenta efetiva escolhida (`clo`);
  * O estado de transição das regras de controle (ex.: por que a janela abriu ou fechou, se houve bloqueio por faixa adaptativa).
* **Aplicação prática:** Permitiria isolar se a temperatura não subiu por restrição de setpoint do controlador (ex.: teto em 20 °C) ou por limitação da máquina em alcançar o setpoint estipulado.

---

### 5. Série Temporal em Nível de Timestep (`serie_timestep`)
* **O que falta:** `serie_agregada` agrupa dados no mínimo em médias horárias.
* **Benefício:** Acesso aos timesteps individuais de simulação (ex.: 10 ou 15 minutos).
* **Aplicação prática:** Fundamental para avaliar a dinâmica dos primeiros 30 a 60 minutos após a chegada dos ocupantes (curva de aquecimento da sala na partida a frio).
