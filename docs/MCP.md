# Servidor MCP local

O servidor usa o SDK oficial Python e somente **stdio**. Não abre porta de rede,
não faz parte do instalador Windows e deve ser executado a partir do código-fonte
com as dependências de `requirements.txt` instaladas. Use Python 3.10+ e instale
o EnergyPlus 9.4 para disparar simulações. O diretório de trabalho do cliente
não importa: o `PYTHONPATH` dos exemplos abaixo já aponta para o projeto.

## Claude Desktop

O Claude Desktop tem build oficial só para Windows e macOS; no Linux, use o
Claude Code (abaixo) ou um build não oficial por sua conta. Edite `claude_desktop_config.json` em
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
  opcionalmente, parâmetros de conforto (`module_type`, `met`, `clo_min` etc.).
  Informe `idf_path` e `epw_path` como caminhos **absolutos**: um caminho
  relativo seria resolvido contra o diretório de trabalho do cliente, que não é
  conhecido. Não recebe `output_path` (reservado pelo servidor) nem
  `energy_path`: o EnergyPlus é sempre o da instalação detectada
  (`ENERGYPLUS_DIR`, `energyplus` no PATH ou pasta padrão). Se a instalação
  mudar com o servidor aberto, reinicie o servidor MCP.
- `iniciar_simulacao(configuracao)`: valida, cria uma pasta exclusiva na raiz
  (`AAAAMMDD_HHMM_mcp_<hex>`, ordenada junto com as da GUI/CLI) e retorna
  `{id, pasta, estado}` sem aguardar o EnergyPlus. Não reduz o período
  automaticamente: ajuste o `RunPeriod` no IDF indicado antes de disparar.
  Recusa (`estado: recusada`) quando já há 2 simulações vivas (`na_fila` ou
  `executando`); o teto muda com a variável `CONFORTIMETRO_MCP_MAX_ACTIVE`.
- `estado_simulacao(id)`: lê `mcp_status.json` na pasta da execução (`na_fila`,
  `executando`, `concluida`, `falhou`, `interrompida`). O runner grava o
  próprio PID; se o processo não existir mais (morto, reinício da máquina), o
  estado passa a `interrompida`. Para falhas, consulte `mcp.log` e
  `eplusout.err` localmente. O estado permanece consultável após reiniciar o
  servidor.

### Se o cliente MCP fechar

- **Linux/macOS:** o runner abre em sessão própria (`start_new_session`), então
  continua mesmo quando o cliente encerra o servidor à força (`killpg`).
- **Windows:** o runner abre com `CREATE_BREAKAWAY_FROM_JOB`. Isso só funciona
  se o Job Object do cliente permitir (`JOB_OBJECT_LIMIT_BREAKAWAY_OK`); o
  `stdio_client` do SDK Python cria o job só com `KILL_ON_JOB_CLOSE`, sem essa
   permissão, e o servidor não tem como obtê-la. Nesse caso o disparo falha
   (`estado: falhou`) em vez de prometer uma simulação independente do cliente.

A raiz padrão pode ser trocada com `CONFORTIMETRO_DATA_DIR` (ou
`AMBIENS_DATA_DIR`, que tem precedência). As ferramentas não aceitam caminhos
de saída nem comandos arbitrários; identificadores com traversal e symlinks
que levem os arquivos de uma execução para fora da raiz são recusados. O IDF
e o EPW são arquivos de entrada explicitamente indicados pelo usuário;
EnergyPlus vem só da instalação detectada, nunca de um caminho enviado pela
ferramenta. Use uma pasta de dados com espaço
suficiente: uma execução anual pode superar 1 GB e durar horas.
