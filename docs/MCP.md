# Servidor MCP local

O servidor usa o SDK oficial Python e somente **stdio**. Não abre porta de rede,
não faz parte do instalador Windows e deve ser executado a partir do código-fonte
com as dependências de `requirements.txt` instaladas. Use Python 3.10+ e instale
o EnergyPlus 9.4 para disparar simulações. Execute sempre com a raiz do projeto
como diretório de trabalho.

## Claude Desktop

Edite `claude_desktop_config.json` em
`~/.config/Claude/claude_desktop_config.json` (Linux) ou
`%APPDATA%\Claude\claude_desktop_config.json` (Windows). Troque os caminhos
absolutos nos exemplos pela sua instalação e reinicie o Claude Desktop.

Linux:

```json
{
  "mcpServers": {
    "confortimetro": {
      "command": "/caminho/projeto/.venv/bin/python",
      "args": ["-m", "confortimetro.mcp_server"],
      "env": {"PYTHONPATH": "/caminho/projeto"}
    }
  }
}
```

Windows (código-fonte; não use o executável do instalador):

```json
{
  "mcpServers": {
    "confortimetro": {
      "command": "C:\\caminho\\projeto\\.venv\\Scripts\\python.exe",
      "args": ["-m", "confortimetro.mcp_server"],
      "env": {"PYTHONPATH": "C:\\caminho\\projeto"}
    }
  }
}
```

## Claude Code

No diretório do projeto, registre no escopo do usuário (adapte os caminhos):

```bash
claude mcp add --scope user --transport stdio confortimetro --env PYTHONPATH=/caminho/projeto -- /caminho/projeto/.venv/bin/python -m confortimetro.mcp_server
```

No Windows, use `claude mcp add --scope user --transport stdio confortimetro --env PYTHONPATH=C:\caminho\projeto -- C:\caminho\projeto\.venv\Scripts\python.exe -m confortimetro.mcp_server` no terminal. Confirme com `claude mcp list`.

## Ferramentas e limites

- `listar_execucoes`: até 30 pastas em `paths.runs_root()`; reconhece também
  `parameters.txt` de execuções antigas.
- `ler_execucao(id)`: configuração (sem caminhos locais) e até 30 linhas de
  métricas agregadas de `ESTATISTICAS.xlsx`, nunca a série inteira.
- `validar_configuracao(configuracao)`: valida IDF, EPW, EnergyPlus, zonas e
  equipamentos antes do disparo. Recebe `idf_path`, `epw_path`, `rooms` e,
  opcionalmente, `energy_path` e parâmetros de conforto (`module_type`, `met`,
  `clo_min` etc.). Não recebe `output_path`: é sempre reservado pelo servidor.
- `iniciar_simulacao(configuracao)`: valida, cria uma pasta exclusiva na raiz e
  retorna `{id, pasta, estado}` sem aguardar o EnergyPlus. Não reduz o período
  automaticamente: ajuste o `RunPeriod` no IDF indicado antes de disparar.
- `estado_simulacao(id)`: lê `mcp_status.json` na pasta da execução (`na_fila`,
  `executando`, `concluida`, `falhou`). Para falhas, consulte `mcp.log` e
  `eplusout.err` localmente. O processo de simulação continua se o cliente
  MCP fechar; o estado permanece consultável após reiniciar o servidor.

A raiz padrão pode ser trocada com `CONFORTIMETRO_DATA_DIR` (ou
`AMBIENS_DATA_DIR`, que tem precedência). As ferramentas não aceitam caminhos
de saída nem comandos arbitrários; identificadores com traversal e symlinks
que levem os arquivos de uma execução para fora da raiz são recusados. O IDF
e o EPW são arquivos de entrada explicitamente indicados pelo usuário;
EnergyPlus é lido da instalação configurada. Use uma pasta de dados com espaço
suficiente: uma execução anual pode superar 1 GB e durar horas.
