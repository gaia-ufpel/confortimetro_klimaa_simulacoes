# PRD — Adicionar equipamentos em qualquer zona
Status: rascunho · Autor: Gabriel Leite Bessa · Data: 22/09/2026 · RFC relacionado: —

## 1. Problema

O controlador escreve a cada timestep nos schedules `JANELA_<ZONA>`, `VENT_<ZONA>` e
`AC_<ZONA>`. Se nenhum objeto do IDF consome esses schedules, a zona simula inteira
"decidindo no vazio". Hoje o software só oferece correção quando o próprio IDF já tem um
molde: um AC em outra zona para copiar ou a zona já presente no `AirflowNetwork`. Fora
disso a falta vira pendência (`plan_equipment_fixes` em `confortimetro/idf/processor.py`),
e o usuário precisa abrir o modelo em outra ferramenta (OpenStudio, IDF Editor) e modelar
o equipamento à mão, ou então simular ignorando a falta.

O mesmo vale quando o usuário quer testar um cenário ("e se esta sala tivesse
ar-condicionado?"): não existe caminho no software para incluir equipamento em uma zona
que não pediu correção.

Custo de não fazer: cada cenário novo depende de edição manual do IDF, que é lenta e
sujeita a erro de nome de schedule. É o erro mais caro do projeto, porque só aparece
depois de uma simulação anual de horas.

## 2. Usuários e contexto

Pesquisadores e estudantes do GAIA que rodam cenários de conforto sobre IDFs prontos,
nem sempre com domínio de EnergyPlus. O ponto de entrada é a GUI: carregam o IDF, escolhem
zonas e módulo, simulam. Hoje contornam o problema editando o IDF à mão ou pedindo o
modelo a quem sabe modelar.

## 3. Solução proposta

Na tela de edição do IDF, uma aba **Equipamentos** lista cada zona do modelo com três
colunas: janela, ventilador e ar-condicionado. Cada célula mostra o estado:
**ligado** (algum objeto consome o schedule), **ausente** ou **a adicionar**.

O usuário marca o que quer incluir em cada zona e ajusta poucos parâmetros com valores
padrão preenchidos:

- **Ar-condicionado:** bomba de calor compacta (PTHP) com COP (padrão 3,24) e capacidade
  e vazões automáticas (autosize).
- **Janela:** em IDF com `AirflowNetwork`, as janelas que a zona já tem na geometria
  passam a ser aberturas da rede, com fator de abertura (padrão 0,5). Em IDF sem
  `AirflowNetwork`, abertura simplificada com área em m² (padrão: 10 % da área de piso).
- **Ventilador:** potência em W (padrão 27 W).

Quando o IDF já tem o mesmo equipamento em outra zona, o software oferece copiar o de lá,
como já faz hoje. Quando não tem, gera o equipamento do zero. Antes de gravar, mostra o
resumo do que vai entrar no modelo, objeto a objeto. Ao confirmar, grava uma cópia
`<nome>_equipamentos.idf` (o original nunca é alterado) e passa a usá-la na configuração.

A correção oferecida ao iniciar uma simulação continua existindo e passa a usar a mesma
geração, de modo que as faltas deixam de virar pendência.

Estados:
- **IDF sem zonas / não carregado:** a aba informa que é preciso carregar um IDF.
- **Tudo ligado:** a zona aparece sem ações pendentes.
- **Erro ao gravar:** mensagem com o motivo; nenhuma cópia parcial fica em uso.
- **Sucesso:** toast com o nome do arquivo gerado; a lista recarrega com os novos estados.
- **Não suportado:** zona sem nenhuma janela na geometria (subsuperfície externa) num IDF
  com `AirflowNetwork` fica com a janela desabilitada, com a explicação.

## 4. Escopo

### Entra (v1)
- Aba Equipamentos com estado por zona e ação de adicionar janela, ventilador e AC.
- AC gerado do zero como `HVACTemplate:Zone:PTHP` + `HVACTemplate:Thermostat`, ligado a
  `AC_<ZONA>`, `TEMP_COOL_AC_<ZONA>` e `TEMP_HEAT_AC_<ZONA>`.
- Janela em IDF com `AirflowNetwork`: inclui a zona na rede (`AirflowNetwork:MultiZone:Zone`
  com `JANELA_<ZONA>` como schedule de disponibilidade) e cada janela externa dela como
  `AirflowNetwork:MultiZone:Surface`, reaproveitando o componente de abertura do IDF ou
  criando um `SimpleOpening`.
- Janela em IDF sem `AirflowNetwork`: `ZoneVentilation:WindandStackOpenArea` com a fração
  de abertura em `JANELA_<ZONA>`.
- Ventilador como `ElectricEquipment` com potência editável.
- Correção pré-simulação passando a gerar do zero quando não há molde.
- Aviso quando o IDF não tem o que o autosize exige.

### Não entra
- **Outros tipos de AC** (split com VRF, fan coil, IdealLoads): as estatísticas de consumo
  (`results/stats.py`) leem só as colunas do PTHP. Reconsiderar quando os KPIs aceitarem
  outros sistemas.
- **Criar janela na geometria:** a subsuperfície (posição, tamanho, vidro) não dá para
  inferir. Zona sem janela continua exigindo edição do modelo.
- **Ativar `AirflowNetwork` num IDF que não tem:** muda a infiltração do modelo inteiro;
  o IDF sem rede usa a janela simplificada.
- **Remover ou editar equipamento já existente:** a v1 só adiciona. Reconsiderar se houver
  pedido.
- **DOAS por zona:** fica como hoje (copiado junto quando o molde tem).
- **Adição pela CLI:** a CLI continua recebendo um IDF pronto. Reconsiderar se aparecer
  uso em lote.

## 5. Requisitos

1. **Must** — A aba Equipamentos deve listar todas as zonas do IDF carregado com o estado
   de janela, ventilador e AC, pela mesma regra de `missing_equipment`.
2. **Must** — Quando o usuário confirmar a adição, o sistema deve gravar uma cópia nova do
   IDF e nunca alterar o arquivo de origem.
3. **Must** — Depois da adição, `missing_equipment` deve voltar vazio para cada
   equipamento adicionado.
4. **Must** — Quando o IDF não tiver AC em nenhuma zona, o sistema deve gerar um PTHP
   completo que passe pelo `ExpandObjects` e pela simulação sem erro severo.
5. **Must** — O consumo do AC gerado deve aparecer nas estatísticas e nos KPIs da
   execução, como acontece com o PTHP dos exemplos.
6. **Must** — Quando o `AirflowNetwork:SimulationControl` do IDF estiver em
   `MultiZoneWithDistribution` ou `MultiZoneWithoutDistribution`, o sistema nunca deve
   gerar `ZoneVentilation:*` (o EnergyPlus não simula esses objetos nesses modos); a janela
   entra pela rede, usando as janelas externas existentes da zona.
6a. **Must** — Ao incluir a zona na rede, o sistema deve incluir as janelas externas dela e
   as janelas internas cuja zona vizinha já está na rede; janela interna para zona fora da
   rede nunca entra (o EnergyPlus aborta, ver R1c).
6b. **Must** — Quando a zona não tiver nenhuma janela elegível, o sistema deve
   desabilitar a janela da zona e explicar por quê.
7. **Must** — Antes de gravar, o sistema deve mostrar a lista de objetos que vão entrar.
8. **Should** — Quando o IDF já tiver o equipamento em outra zona, o sistema deve oferecer
   copiar ou gerar do zero, com copiar como padrão.
9. **Must** — Quando o IDF não tiver nenhum `SizingPeriod:*`, o sistema não deve gravar um
   AC em autosize: deve pedir capacidade e vazões fixas ou explicar que o IDF precisa de
   dias de projeto (o EnergyPlus aborta antes de simular, ver R2).
10. **Should** — Parâmetros (COP, área de abertura, potência) devem ser validados: número
    positivo; área menor ou igual à área de piso. Valor inválido bloqueia a confirmação
    com a mensagem no campo.
11. **Could** — Adicionar o mesmo equipamento em várias zonas de uma vez.

## 6. Abordagem técnica (alto nível)

Estende o que já existe em `confortimetro/idf/processor.py`: `plan_equipment_fixes` ganha
geração do zero (hoje há isso só para o ventilador, com `DEFAULT_FAN_FIELDS`) e passa a
aceitar uma lista explícita de `(zona, equipamento)` além das faltas do módulo. O formato
das correções (`objects`, `updates`) não muda, então `apply_equipment_fixes` e o fluxo de
`MainWindow._resolve_missing_equipment` são reaproveitados. A aba nova entra no
`IDFEditorPanel` (`gui/components/idf_editor_panel.py`), ao lado de People e período. Não
precisa de RFC: não há trade-off de arquitetura, os riscos técnicos
foram validados por simulação (R1b, R1c, R2).

## 7. Métricas de sucesso

- **Primária:** um cenário "zona sem AC → zona com AC" feito só pela GUI, sem editar o IDF
  fora do software, em menos de 2 minutos `[suposição]`. Validar cronometrando com 2
  usuários do grupo sobre o `SALA_IDEAL.idf`.
- **Contra-métrica:** zero simulações anuais perdidas por erro de equipamento gerado.
  Medido pelo teste automatizado (req. 3–5) e pelos `eplusout.err` das primeiras execuções
  reais.
- **Instrumentação:** não há telemetria no produto; a avaliação é qualitativa com o grupo
  nas primeiras duas semanas de uso.

## 8. Riscos, suposições e questões em aberto

- **R1 — ZoneVentilation com AirflowNetwork ativo (resolvido).** A documentação do
  EnergyPlus 9.4 (`AirflowNetwork:SimulationControl`, campo *AirflowNetwork Control*)
  diz que nos modos `MultiZoneWithDistribution` e `MultiZoneWithoutDistribution`
  nenhum `ZoneInfiltration:*`, `ZoneVentilation:*`, `ZoneMixing` ou `ZoneCrossMixing` é
  simulado, no modelo inteiro e não só nas zonas da rede. Todos os exemplos usam
  `MultizoneWithoutDistribution`. Por isso a janela em IDF com AFN entra pela rede.
- **R1b — Zona nova na rede (validado em 22/09/2026).** No `FAURB`, a SALA_AULA foi
  tirada da rede e recolocada só com as 6 janelas externas. Rodou 3 dias com 0 erro
  severo e os mesmos 51 avisos do original. Com `JANELA_SALA_AULA` = 1, as 6 janelas
  abriram com fator 1 em todas as horas, e a infiltração da zona ficou 1,2 % acima do
  modelo original (628 607 contra 620 921 m³), que tinha também as 4 aberturas internas.
- **R1c — Janela interna para zona fora da rede (validado).** O EnergyPlus aborta na
  leitura dos dados, pelos dois lados: "Zone for inside surface must be defined in a
  AirflowNetwork:MultiZone:Zone object" (superfície da zona fora da rede) e "An adjacent
  zone = SALA_AULA is not described in AIRFLOWNETWORK:MULTIZONE:ZONE" (superfície da
  vizinha). Daí o req. 6a.
- **R2 — Autosize sem dias de projeto (validado).** O `FAURB` sem os 2
  `SizingPeriod:DesignDay` aborta antes de simular: "Sizing for Zones has been requested
  but there are no design environments specified". Daí o req. 9 como Must.
- **R3 — Valores padrão (aceito provisoriamente em 22/09/2026).** COP 3,24 e fator de
  abertura 0,5 vêm do `SALA_PTHP.idf` e do `SALA_IDEAL.idf`. O autor os aceitou como padrão
  da v1, sujeitos à confirmação da orientação do projeto; como são editáveis na aba,
  trocar depois não exige mudança de código.
- **R4 — Janela simplificada muda o resultado.** A ventilação por `ZoneVentilation` é bem
  mais simples que o AFN, e resultados de zonas com janelas diferentes não são
  comparáveis. Mitigação: a nota gravada no IDF e o resumo antes de gravar dizem qual
  modelo de janela foi usado.

## 9. Rollout

Sem flag: a aba é aditiva, e o arquivo de origem nunca é tocado. Sai numa versão menor
(0.5.0) com nota no `README` e em `docs/CLI.md` (requisitos do IDF). Rollback: voltar a
versão anterior; os IDFs `_equipamentos.idf` já gerados continuam válidos, porque são IDF
comum. Não há migração de dados.
