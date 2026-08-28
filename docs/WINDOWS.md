# Execução no Windows

Guia para o usuário final rodar a interface gráfica do Confortímetro Klimaa em
um Windows, sem linha de comando além de dois duplos-cliques.

## 1. Instalar os dois pré-requisitos

| Programa | Onde | Observação |
|---|---|---|
| **Python 3.10 ou superior** | <https://www.python.org/downloads/windows/> | Na primeira tela do instalador, marque **"Add python.exe to PATH"**. |
| **EnergyPlus 9.4.0** | <https://github.com/NREL/EnergyPlus/releases/tag/v9.4.0> (instalador `Windows-x86_64.exe`) | Aceite o diretório padrão `C:\EnergyPlusV9-4-0`. |

A versão do EnergyPlus **tem que ser a 9.4**: o programa usa o `pyenergyplus`
que vem dentro da instalação, e as demais versões mudam essa API.

## 2. Baixar o projeto

Baixe o repositório como ZIP e extraia para uma pasta sem acentos nem espaços,
por exemplo `C:\confortimetro`.

## 3. Instalar as dependências

Duplo-clique em **`bin\install.bat`**. Ele cria o ambiente virtual `.venv` dentro da
pasta do projeto e instala as bibliotecas Python. Leva alguns minutos na
primeira vez. A janela mostra `[OK] Instalacao concluida` ao terminar.

## 4. Executar

Duplo-clique em **`bin\executar.bat`**. A interface abre.

Na aba de caminhos, confira:

- **Caminho do EnergyPlus**: `C:\EnergyPlusV9-4-0` (preenchido automaticamente
  se a instalação estiver no lugar padrão).
- **Arquivo IDF** e **Arquivo EPW**: os exemplos ficam em `examples\idf` e `examples\epw`.
- **Diretório de saída**: uma pasta nova por execução, ex.: `outputs\run_001`.

## 5. Diferenças em relação ao Linux

O código já trata o que muda entre os sistemas:

- `ExpandObjects.exe` e `ReadVarsESO.exe` no lugar dos binários sem extensão.
- Caminhos montados com `os.path.join`, não com `/` fixo.
- `energy_path` cai no padrão da plataforma (`C:\EnergyPlusV9-4-0`) quando o
  caminho gravado no `resources\config.json` não existe na máquina.

## 6. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `[ERRO] Python nao encontrado` no `bin\install.bat` | Python instalado sem marcar "Add python.exe to PATH". Reinstale marcando a opção. |
| `No module named 'pyenergyplus'` | Caminho do EnergyPlus errado na interface, ou EnergyPlus não instalado. |
| `IDD file not found` | O **Caminho do EnergyPlus** precisa apontar para a raiz da instalação (a pasta que contém `Energy+.idd`), não para uma subpasta. |
| A janela fecha na hora | Rode pelo `bin\executar.bat` (ele mantém a janela aberta e mostra o erro), não por `python main.py` no Explorer. |
| Simulação parece travada | Uma simulação anual leva de dezenas de minutos a horas. O progresso do EnergyPlus sai na janela preta do `bin\executar.bat`. |

## 7. Uma execução por pasta

`in.idf` e `expanded.idf` são gravados na pasta do IDF de entrada, e o IDF de
entrada é modificado no lugar. Não rode duas simulações ao mesmo tempo sobre o
mesmo IDF — copie o modelo para uma pasta por execução.
