# Confortímetro Klimaa — simulações personalizadas

Ferramenta acadêmica da UFPel para simular conforto térmico em edificações com
EnergyPlus. O núcleo Python modifica um arquivo IDF, registra um controlador
durante a simulação e transforma os resultados em planilhas Excel.

## Estado do projeto

As interfaces desktop e web executam o mesmo pipeline de simulação. A web
recebe IDF/EPW por upload, isola os arquivos de cada sessão e oferece o ZIP
dos resultados ao final.

## Início rápido (desktop)

1. Instale o EnergyPlus compatível e identifique a pasta que contém
   `Energy+.idd`, `ExpandObjects` e a API `pyenergyplus`.
2. Crie um ambiente Python e instale as dependências descritas em
   [`src/web/requirements.txt`](src/web/requirements.txt). O repositório não
   possui um `requirements.txt` na raiz.
3. Ajuste [`resources/config.json`](resources/config.json) para os caminhos da
   sua máquina e para as zonas do seu IDF.
4. Execute:

   ```bash
   python main.py
   ```

Na janela, valide os caminhos, escolha os parâmetros e clique em **Executar**.
Os resultados são gravados no diretório `output_path` configurado.

## Interface web

Com o EnergyPlus instalado e o caminho informado na página, execute:

```bash
./run_web.sh
```

Abra `http://localhost:5000`, envie o IDF e o EPW, informe o diretório do
EnergyPlus e clique em **Executar Simulação**. A aplicação usa cópias do IDF
em diretórios temporários por sessão; ao terminar, use **Baixar Resultados**.

## Documentação

O guia completo, baseado no código atualmente presente, está em
[`documentation/PROJETO.md`](documentation/PROJETO.md). Ele cobre:

- arquitetura e fluxo de dados;
- pré-requisitos, configuração e execução;
- módulos de condicionamento e resultados produzidos;
- API e operação da interface web;
- testes, limitações conhecidas e manutenção.

Os registros históricos de refatorações e melhorias ficam em
[`documentation/history/`](documentation/history/); podem citar arquivos que
já não existem.

## Estrutura essencial

```text
main.py                    entrada da interface desktop
src/simulation.py          orquestração EnergyPlus e pós-processamento
src/processors/            alterações no IDF via eppy
src/modules/               controladores de conforto por zona
src/gui/                   interface Tkinter
src/web/                   interface Flask/Socket.IO
src/utils/                 configuração e planilhas de resultados
resources/                 IDFs, EPWs e configuração de exemplo
scripts/                   utilitários de desenvolvimento
tests/legacy/              verificações manuais antigas
documentation/             documentação atual, histórica e ativos visuais
```

## Verificação atual

```bash
python -m compileall -q main.py src tests
python -m pytest src/web/tests -q
```

Os comandos verificam a sintaxe e as rotas, uploads, Socket.IO e o contrato
entre a interface web e o pipeline de simulação.
