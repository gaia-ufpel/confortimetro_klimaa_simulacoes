# Execução no Windows

Há dois caminhos: o **instalador** (para o usuário final) e a **instalação a
partir do código** (para quem vai mexer no projeto).

## A. Instalador (recomendado para o usuário final)

1. Instale o **EnergyPlus 9.4.0** —
   <https://github.com/NREL/EnergyPlus/releases/tag/v9.4.0> (instalador
   `Windows-x86_64.exe`), aceitando o diretório padrão `C:\EnergyPlusV9-4-0`.
   A versão **tem que ser a 9.4**: o programa usa o `pyenergyplus` que vem
   dentro da instalação, e as demais versões mudam essa API.
2. Baixe `ConfortimetroKlimaa-<versão>-setup.exe` na página de *Releases* do
   repositório e execute. Não pede senha de administrador (instala em
   `%LOCALAPPDATA%\ConfortimetroKlimaa`) e cria atalho no menu Iniciar.
3. Abra pelo atalho **Confortimetro Klimaa**. Python não é necessário: já vem
   embutido no executável. O caminho do EnergyPlus é detectado sozinho — se
   você instalou fora do padrão, use o botão **🔍 Detectar** ou **📂 Procurar**
   no campo "Caminho do EnergyPlus".

Onde ficam as coisas depois de instalado:

| O quê | Onde |
|---|---|
| Configuração da interface | `%LOCALAPPDATA%\ConfortimetroKlimaa\config.json` |
| IDF e EPW de exemplo | pasta `_internal\examples` dentro da instalação |
| Saída padrão das simulações | `Documentos\ConfortimetroKlimaa\run_001` |

Para desinstalar: *Configurações → Aplicativos → Confortimetro Klimaa*.

### Como o instalador é gerado

O build roda no GitHub Actions (`.github/workflows/windows-build.yml`), em
`windows-latest`, disparado por uma tag `v*` ou manualmente. Localmente, em um
Windows com Python e [Inno Setup 6](https://jrsoftware.org/isdl.php):

```bat
pip install -r requirements.txt pyinstaller
pyinstaller packaging\confortimetro.spec --noconfirm
iscc packaging\installer.iss
```

O `.exe` do instalador sai em `dist\`. O EnergyPlus **não** é embutido — o
`pyenergyplus` é carregado em tempo de execução da instalação da máquina.

### Armadilhas do empacotamento

Erros que já quebraram o build e o que os resolve:

| Erro | Causa |
|---|---|
| `script 'packaging/main.py' not found` | Caminhos dentro do `.spec` são resolvidos **em relação ao próprio `.spec`**, não ao diretório de onde o `pyinstaller` foi chamado. Por isso o spec ancora tudo em `SPECPATH`. |
| `Unknown preprocessor directive` (Inno) | Uma linha do `.iss` começando com `#13#10` é lida como diretiva do pré-processador. Quebras de linha só no **fim** da linha. |
| `Unknown identifier 'SLineBreak'` (Inno) | O Pascal Script do Inno não tem `SLineBreak`; use `#13#10`. |
| `collect_data_files - skipping ... not a package` | `esoreader` é um módulo solto, não um pacote — não passe pelo `collect_all`. |

### Versão

A versão é uma só, a do `version` no `pyproject.toml`. O workflow a lê de lá e
passa para o Inno Setup (`iscc /DAppVersion=...`), então o número no
instalador, em *Aplicativos e Recursos* e no nome do arquivo nunca divergem.

- **Release**: crie a tag `v<version>` — `v0.1.0` para `version = "0.1.0"`. Se a
  tag não bater com o `pyproject.toml`, o build falha de propósito, antes de
  publicar nada.
- **Build de teste** (`workflow_dispatch`, sem tag): a versão sai como
  `0.1.0-dev+<sha curto>`, para não se confundir com uma release.

Publicar uma versão nova: altere o `version` no `pyproject.toml`, commite, e
crie a tag `v` correspondente.

## B. Instalação a partir do código

### 1. Instalar os dois pré-requisitos

| Programa | Onde | Observação |
|---|---|---|
| **Python 3.10 ou superior** | <https://www.python.org/downloads/windows/> | Na primeira tela do instalador, marque **"Add python.exe to PATH"**. |
| **EnergyPlus 9.4.0** | <https://github.com/NREL/EnergyPlus/releases/tag/v9.4.0> (instalador `Windows-x86_64.exe`) | Aceite o diretório padrão `C:\EnergyPlusV9-4-0`. |

A versão do EnergyPlus **tem que ser a 9.4**: o programa usa o `pyenergyplus`
que vem dentro da instalação, e as demais versões mudam essa API.

### 2. Baixar o projeto

Baixe o repositório como ZIP e extraia para uma pasta sem acentos nem espaços,
por exemplo `C:\confortimetro`.

### 3. Instalar as dependências

Duplo-clique em **`bin\install.bat`**. Ele cria o ambiente virtual `.venv` dentro da
pasta do projeto e instala as bibliotecas Python. Leva alguns minutos na
primeira vez. A janela mostra `[OK] Instalacao concluida` ao terminar.

### 4. Executar

Duplo-clique em **`bin\executar.bat`**. A interface abre.

Na aba de caminhos, confira:

- **Caminho do EnergyPlus**: `C:\EnergyPlusV9-4-0` (preenchido automaticamente
  se a instalação estiver no lugar padrão).
- **Arquivo IDF** e **Arquivo EPW**: os exemplos ficam em `examples\idf` e `examples\epw`.
- **Diretório de saída**: uma pasta nova por execução, ex.: `outputs\run_001`.

## Diferenças em relação ao Linux

O código já trata o que muda entre os sistemas:

- `ExpandObjects.exe` e `ReadVarsESO.exe` no lugar dos binários sem extensão.
- Caminhos montados com `os.path.join`, não com `/` fixo.
- `energy_path` cai no padrão da plataforma (`C:\EnergyPlusV9-4-0`) quando o
  caminho gravado no `resources\config.json` não existe na máquina.

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `[ERRO] Python nao encontrado` no `bin\install.bat` | Python instalado sem marcar "Add python.exe to PATH". Reinstale marcando a opção. |
| `No module named 'pyenergyplus'` | Caminho do EnergyPlus errado na interface, ou EnergyPlus não instalado. Clique em **🔍 Detectar**. |
| `IDD file not found` | O **Caminho do EnergyPlus** precisa apontar para a raiz da instalação (a pasta que contém `Energy+.idd`), não para uma subpasta. O status do campo avisa antes de simular. |
| A janela fecha na hora | Rode pelo `bin\executar.bat` (ele mantém a janela aberta e mostra o erro), não por `python main.py` no Explorer. |
| Simulação parece travada | Uma simulação anual leva de dezenas de minutos a horas. O progresso do EnergyPlus sai na janela preta do `bin\executar.bat`. |

## Uma execução por pasta

`in.idf` e `expanded.idf` são gravados na pasta do IDF de entrada, e o IDF de
entrada é modificado no lugar. Não rode duas simulações ao mesmo tempo sobre o
mesmo IDF — copie o modelo para uma pasta por execução.
