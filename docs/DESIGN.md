# Design system da interface

Referência única para a aparência da GUI Tkinter. Todo token vive em
[`confortimetro/gui/theme.py`](../confortimetro/gui/theme.py); os painéis em
`confortimetro/gui/components/` consomem os nomes de estilo e os helpers dali e
**não** definem cor, fonte ou espaçamento próprios.

## Princípios

1. **Um lugar só.** Cor, fonte, raio e espaçamento saem de `theme.py`. Literal
   de cor em painel é bug, salvo as de estado (✅/⚠️/❌), que vêm de
   `COLORS["ok"|"warn"|"danger"]`.
2. **Cor tem função.** Verde escuro = ação primária e título. Sage = borda e
   estrutura. Vermelho/âmbar = estado, nunca decoração.
3. **Menos superfícies.** Um único componente de card, uma única forma de
   agrupar campos. Sem header colorido + separador + moldura na mesma caixa.
4. **Emoji é estado, não enfeite.** A pill de status e o feedback de validação
   têm emoji; títulos de card e botões, não — emoji renderiza diferente em cada
   SO e é o que mais amadorece a tela. No log ele nem aparece: a fonte
   monoespaçada não tem emoji e o glifo vira caixa, então lá os marcadores são
   `· ✓ ! ×`.

## Tokens

### Cor

Os widgets ttk usam o tema **Sun Valley** (`sv_ttk`, visual Windows 11):
`apply_theme` chama `sv_ttk.set_theme("light", root)` antes de configurar os
estilos nomeados. Os sprites do sv_ttk são imagens PNG — **a cor de entry,
combobox, checkbutton, progressbar, treeview e scrollbar não é configurável**,
então esses estilos não são mais tocados aqui e o chrome neutro dele define
`bg`, `surface_2`, `line` e `text`. O verde da marca sobrevive nos widgets
desenhados à mão (`Card`, `RoundedButton`, `RangeField`, `ChipSelect`) e nos
títulos.

Os nomes de estilo próprios não podem colidir com os do sv_ttk: `Card.TFrame`
é dele (sprite de moldura), então a superfície branca dos painéis chama-se
`Surface.TFrame`. E `Section.TLabelframe` não define `background`, senão o
fundo cobre a moldura desenhada pelo sprite.

| Token | Hex | Uso |
|---|---|---|
| `bg` | `#fafafa` | fundo da janela (chrome do sv_ttk) |
| `surface` | `#ffffff` | fundo de card |
| `surface_2` | `#f0f0f0` | campo de entrada, hover fantasma, trilho |
| `line` | `#e0e0e0` | borda de 1px, separador |
| `scroll` | `#c2c2c2` | polegar das scrollbars `tk` clássicas |
| `text` | `#1c1c1c` | texto principal |
| `text_mute` | `#406346` | legenda, unidade, rodapé |
| `primary` | `#3a5a40` | ação primária, título de card |
| `primary_h` | `#588157` | hover da ação primária |
| `primary_d` | `#344e41` | pressed da ação primária |
| `accent` | `#a3b18a` | detalhe estrutural, estado inativo |
| `ok` | `#4e7a4d` | sucesso |
| `warn` | `#a06b00` | aviso |
| `danger` | `#b3261e` | erro, ação destrutiva |

`warn` e `danger` estão fora da paleta de propósito: precisam se distinguir do
verde.

Contraste: os verdes ficaram só como acento sobre branco/`#fafafa`, onde
`primary` dá 8:1. Os verdes **de texto** são versões escurecidas dos da paleta: `#588157` como
texto dá 3.1:1 sobre a areia e 3.9:1 sobre `surface_2` — reprova em contraste.
`#406346` sobe para 4.7:1 e 5.9:1; `ok` foi de `#588157` para `#4e7a4d` porque
também serve de fundo de pill com texto branco (4.5:1). O `#588157` da paleta
continua vivo como `primary_h` e em fundos, não em texto.

### Espaçamento

Escala de 4 px — `SPACE = (0, 4, 8, 12, 16, 24, 32)`. Só esses valores.

- Janela: 24 de padding.
- Entre cards: 16 — inclusive na janela de simulações.
- Dentro do card: 16 (`Card(pad=SPACE[4])`, o padrão). Barra de ações só com
  botões e combos usa 12 (`pad=SPACE[3]`): a linha é baixa e 16 sobraria.
- Entre linhas dentro de um mesmo card: 12.
- Entre rótulo e campo: 4. Entre campos: 8.
- Linha de status de um campo (`✅ Arquivo encontrado`) só ocupa espaço quando
  tem texto: fica em `grid_remove` enquanto vazia, senão o ritmo entre os
  campos varia sem motivo visível.
- Numa barra horizontal: 8 entre botões vizinhos, 12 ao trocar de grupo
  (campo → botão, fim de um par rótulo+campo → o próximo).

### Raio

`RADIUS = {"card": 12, "control": 8, "pill": 999}`.

Tk/ttk **não** tem `border-radius`. Toda forma arredondada é desenhada num
`tk.Canvas` por `rounded_rect()`, um `create_polygon(..., smooth=True)`. Só o
`Card`, o `RoundedButton`, a pill de status e o trilho do `RangeField` pagam
esse custo; o resto continua sendo ttk plano.

### Tipografia

Cinco papéis, não uma coleção de tamanhos ad-hoc.

| Papel | Tamanho | Peso | Uso |
|---|---|---|---|
| `h1` | 18 | bold | título do app, uma vez por tela |
| `h2` | 13 | bold | título de card |
| `label` | 10 | bold | rótulo de campo, título de seção |
| `body` | 10 | normal | valores, botões, texto corrente |
| `caption` | 9 | normal | hint, unidade, rodapé, contador |
| `mono` | 9 | normal | área de log |

Família resolvida em tempo de execução por `_pick_family()`: a primeira de
`Segoe UI → Inter → DejaVu Sans → TkDefaultFont` que existir na máquina.
Pedir `Segoe UI` direto (como o código fazia) cai num fallback aleatório no
Linux.

## Componentes

### Card — `theme.Card`

Único container visual. Retângulo branco de raio 12 com borda de 1 px `line`,
título opcional em `h2`/`primary` no topo à esquerda, padding interno 16.

Sem header verde, sem separador. O fundo é um `Canvas` em `place()` atrás do
corpo; o corpo (`card.body`) é um `ttk.Frame` branco recuado pelo padding, então
nunca invade os cantos arredondados. A altura acompanha o conteúdo empacotado.

```python
card = Card(parent, "Configuração de caminhos")
card.pack(fill="x", pady=(0, SPACE[4]))
MeuPainel(card.body).pack(fill="both", expand=True)
```

### Botão — `theme.RoundedButton`

Quatro variantes. Altura 34, raio 8, fonte `body`.

| Variante | Fundo | Texto | Uso |
|---|---|---|---|
| `primary` | `primary` | branco | ação principal da tela; uma por card |
| `ghost` | `surface`, hover `surface_2` | `primary` | ações secundárias num card |
| `bar` | `bg`, hover `surface_2` | `primary` | ações sobre o fundo da janela |
| `danger` | `danger` | branco | parar simulação, ações destrutivas |

`Secondary.TButton` e `Outline.TButton` foram fundidos em `ghost` — eram
visualmente quase idênticos.

API: `configure(text=…, variant=…, state=…)`, compatível com o uso do
`ControlPanel`.

### Campo de entrada

`Field.TEntry` / `Field.TCombobox`: fundo `surface_2`, borda 1 px `line`,
foco troca a borda para `primary`. Rótulo em `label` **acima** do campo, nunca
ao lado — resolve o alinhamento irregular do layout antigo.

Feedback de validação vai numa `caption` sob o campo, colorida por
`ok`/`warn`/`danger`, prefixada pelo emoji de estado.

### Seção de campos

`ttk.LabelFrame` estilo `Section.TLabelframe`: sem moldura pesada, título em
`label`/`text_mute`, colunas com `weight=1, uniform="fields"` para todos os
campos terem a mesma largura.

### Pill de status — `theme.StatusPill`

Cápsula (raio `pill`) com emoji + texto, fundo derivado do estado
(`info`/`running` = `surface_2`, `success` = `ok`, `warning` = `warn`,
`error` = `danger`). Substitui o label solto do `ControlPanel`.

### Faixa mínimo–máximo — `theme.RangeField`

Um par min/max é um controle só: campo numérico em cada ponta e um trilho de
dois cursores no meio. Arrastar e digitar editam o mesmo valor.

Domínios (só afetam o trilho e o grampeamento; o passo é o incremento do
arrasto):

| Faixa | Domínio | Passo |
|---|---|---|
| PMV | −3 … 3 (escala ASHRAE) | 0.1 |
| Temperatura do AC | 10 … 35 °C | 0.5 |
| Clo | 0 … 2 | 0.05 |

`get()` devolve `(mínimo, máximo)` já ordenado e dentro do domínio — campo
vazio ou invertido não vira exceção nem valor inválido. `min_entry` e
`max_entry` são `ttk.Entry` de verdade, então continuam sendo o contrato de
leitura da configuração.

### Seleção múltipla — `theme.ChipSelect`

Combobox das opções + um chip removível por item escolhido. Usado nas salas:
as opções são as zonas do IDF selecionado, lidas por
`confortimetro.idf.read_zone_names` (parser de texto, sem eppy nem IDD — a GUI
não pode esperar segundos nem exigir o EnergyPlus só para listar zonas). Sem
IDF válido o campo vira texto livre em vez de travar.

### Painel inferior — `theme.BottomSheet`

Barra sempre visível + conteúdo colapsável, no espírito do painel do VS Code.
Abre sozinho quando a simulação começa. Substituiu as abas: a tela é uma só.

### Barra de progresso

`Modern.Horizontal.TProgressbar`: 6 px de altura, trilho `surface_2`, barra
`primary`, sem relevo.

### Log

`ScrolledText` em `mono`, fundo `surface`, texto `text`. Tags por tipo:
`info` → `primary`, `success` → `ok`, `warning` → `warn`, `error` → `danger`,
`timestamp` → `accent` em `caption`.

## Layout

- Janela 1200×900, mínimo 800×600, padding 24.
- Cabeçalho sobre o fundo `bg`: título `h1` em `primary` e subtítulo `caption`
  em `text_mute`.
- **Sem abas.** Uma tela só, em três faixas:
  1. **Topbar** (card raso): Executar / Salvar / Carregar à esquerda, pill de
     estado à direita, barra de progresso abaixo enquanto roda.
  2. **Parâmetros** (card único, com rolagem): caminhos e parâmetros de
     simulação separados por um `Separator` — caminho de arquivo também é
     parâmetro da simulação, não merecia card próprio.
  3. **Log** (`BottomSheet`), fechado por padrão.
- Rodapé em `caption`/`text_mute`.

## Ao mexer

- Depois de alterar layout, confirme que os painéis estão mapeados — widget não
  empacotado some em silêncio (ver `AGENTS.md`):

```bash
.venv/bin/python -c "
from confortimetro.gui.main_window import MainWindow
a = MainWindow(); a.update()
print(a.path_panel.winfo_ismapped(), a.simulation_panel.winfo_ismapped())
a.destroy()"
```

- `RangeField` e `ChipSelect` expõem `min_entry`/`max_entry` e
  `get_values()`/`set_values()`. Trocar esses nomes quebra
  `get_configuration`/`set_configuration` em silêncio.
- `theme.apply_theme(root)` precisa rodar antes de qualquer widget ttk ser
  criado; `MainWindow.__init__` já faz isso.
- Card e RoundedButton redesenham no evento `<Configure>`. Se um deles aparecer
  vazio, quase sempre o pai tem tamanho 0 porque falta `fill`/`expand`.
