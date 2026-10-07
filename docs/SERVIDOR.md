# Servidor de simulações

O processamento pesado (EnergyPlus e pós-processamento) roda num servidor, e o
desktop só envia a simulação e recebe os resultados. O modo local continua
existindo: quem escolhe é a caixa **Executar as simulações no servidor**, em
Configurações → Servidor de simulações.

## Como funciona

1. O desktop envia o IDF, o EPW e os parâmetros (`POST /api/execucoes`). O
   servidor valida a configuração como o MCP faz (`mcp_server.validar_configuracao`)
   e cria `execucoes/<usuário>/<id>/`, com os arquivos enviados em `entrada/`.
2. A execução fica `aguardando`. O agendador (um tick a cada 5 s dentro do
   servidor) dispara as mais antigas até o limite de `CONFORTIMETRO_MCP_MAX_ACTIVE`.
   Cada uma roda num processo próprio (`server.py executar`), com estado no
   `mcp_status.json` e o log no `progresso.log`.
3. O desktop lê estado e log a cada 2 s e mostra o andamento no mesmo painel de
   log e na mesma barra de progresso do modo local. Se a rede cair, ele tenta
   de novo a cada 10 s.
4. Quando a execução termina, o desktop baixa o **espelho** para a pasta local
   de execuções. O espelho é a pasta inteira menos os brutos do EnergyPlus
   (`eplusout.*`, `in.idf`, `expanded.idf`). O `configs.json` chega por último,
   com os caminhos trocados para os locais. Por isso a listagem, a comparação,
   os gráficos, o assistente e o Drive funcionam sem nenhuma mudança.

Se o app fechar no meio, a simulação continua no servidor. A pasta local fica
só com o `remoto.json` (o id da execução no servidor), e **Baixar execuções do
servidor** completa o espelho depois. O mesmo botão baixa, numa máquina nova,
todas as execuções concluídas daquele usuário.

Para ter os brutos de uma execução remota, use **Baixar arquivos completos**
nos detalhes dela. O botão só aparece em execuções com `remoto.json`, pede
confirmação (uma anual passa de 1 GB) e completa a mesma pasta local com
`eplusout.*`, `in.idf` e `expanded.idf`.

Parar a simulação no desktop cancela a execução no servidor, que mata o grupo
de processos dela (`SIGKILL`). A execução fica `cancelada`, sem resultado.

## Instalar o servidor

```bash
docker compose -f packaging/servidor/compose.yaml up -d --build
docker compose -f packaging/servidor/compose.yaml exec ambiens \
    python -m confortimetro.remote.server usuario ana          # imprime o token
docker compose -f packaging/servidor/compose.yaml exec ambiens \
    python -m confortimetro.remote.server usuario gabriel --admin
```

O token aparece uma vez só. Rodar o comando de novo para o mesmo nome reemite
o token e invalida o anterior. O servidor guarda apenas o hash, em
`/dados/servidor_tokens.json`, e não precisa reiniciar para ler um usuário
novo. Para remover um usuário, apague a entrada dele nesse arquivo.

A imagem traz o EnergyPlus 9.4 em `/opt/energyplus`. Todos os dados ficam no
volume `/dados`: `execucoes/<usuário>/<id>` e o arquivo de tokens.

**Exposição:** o compose publica a porta só em `127.0.0.1`. Para acesso
remoto, ponha um proxy reverso com TLS na frente (Traefik, Caddy) ou use uma
VPN (Tailscale). Por HTTP puro, o token trafega em claro.

| Variável | Padrão | Efeito |
|---|---|---|
| `CONFORTIMETRO_MCP_MAX_ACTIVE` | 2 | Simulações simultâneas. Cada uma ocupa cerca de um núcleo |
| `AMBIENS_COTA_GB` | (sem cota) | Acima desse uso de disco: `WARNING COTA EXCEDIDA` no log e aviso para o admin |
| `CONFORTIMETRO_DATA_DIR` | `/dados` | Raiz dos dados |

Os nomes `CONFORTIMETRO_*` valem antes e depois da troca para `AMBIENS_*`.

**Retenção:** nada é apagado automaticamente. A cada 10 min o servidor mede o
disco. Quando passa da cota, registra o aviso no log (um sidecar como o
`telegram-log-sidecar` pode encaminhá-lo) e o admin o vê em **Salvar e
testar**, no desktop.

Rode **um processo só** (sem `--workers`): o agendador vive dentro dele.

## API

Todas as rotas exigem `Authorization: Bearer <token>`. Cada usuário só vê as
próprias execuções; o admin vê todas.

| Rota | Uso |
|---|---|
| `GET /api/eu` | usuário, versão do código e, para o admin, a cota |
| `GET /api/execucoes` | execuções do usuário (`?todas=1` para o admin) |
| `POST /api/execucoes` | multipart: `configuracao` (JSON), `idf` e `epw` |
| `GET /api/execucoes/{id}` | estado: `aguardando`, `na_fila`, `executando`, `concluida`, `falhou`, `interrompida` ou `cancelada` |
| `GET /api/execucoes/{id}/log?desde=N` | linhas completas do progresso a partir do byte N |
| `POST /api/execucoes/{id}/cancelar` | cancela uma execução em espera ou em andamento |
| `GET /api/execucoes/{id}/espelho` | zip do espelho (gerado uma vez e guardado como `espelho.zip`) |
| `GET /api/execucoes/{id}/espelho?completo=1` | zip com tudo, brutos incluídos (temporário, apagado depois do envio) |

## Limites conhecidos

- O espelho do módulo `ENERGYPLUS_ONLY` chega quase vazio (só `eplustbl.csv`
  e afins): os resultados dele estão nos brutos, que vêm por **Baixar arquivos
  completos**.
- Execuções que falharam no servidor não têm download: o diagnóstico
  (`eplusout.err`) fica lá.
- Reabrir o app não retoma o log ao vivo de uma execução em andamento. Ela
  continua no servidor e é baixada por **Baixar execuções do servidor**.
- Não há rota para apagar execuções: a limpeza é do admin, direto no volume.
- O servidor só roda em Linux (`killpg` e `/proc`).
