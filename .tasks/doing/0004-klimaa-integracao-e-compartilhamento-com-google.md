---
id: 0004-klimaa-integracao-e-compartilhamento-com-google
title: 'klimaa: integração e compartilhamento com Google Drive'
repo: 'gaia-ufpel/confortimetro_klimaa_simulacoes'
type: codigo
agent: 'claude'
priority: media
created: 2026-10-06T17:23:10Z
updated: 2026-10-06T17:47:46Z
briefing_hash: 9c919aef5290510ac0134b07649aaffcd7039cc2bd78dc9f974ea9c3abe9f6ac
approved: '2026-10-06T17:23:32Z'
panel: 'klimaa-drive-sync'
---

## Request

## Briefing

### 2026-10-06T17:23:30Z
Tarefa: integração e compartilhamento com Google Drive no Ambiens (confortimetro_klimaa_simulacoes).

Diretório: worktree /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.agents/worktrees/drive-sync (branch drive-sync). Trabalhe só aqui. Leia AGENTS.md/CLAUDE.md e docs/PROJETO.md do repo antes.

Decisões do dono (não reabrir):
- Sincronização TRANSPARENTE: o usuário conecta a conta Google uma vez e, a partir daí, tudo sincroniza sozinho, sem clique.
- Compartilhamento: link "qualquer pessoa com o link pode ver" (copiado para a área de transferência) + convite por e-mail como leitor.
- Cliente OAuth vem de projeto GCP do dono (ainda não entregue). Código lê o cliente de arquivo, nunca commitado.

Decisões técnicas (orquestrador):
1. Escopo OAuth: somente https://www.googleapis.com/auth/drive.file (não sensível; o app só enxerga o que ele criou). Nada de drive/drive.readonly.
2. Fluxo: OAuth "App para computador" com loopback (google-auth-oauthlib InstalledAppFlow.run_local_server) abrindo o navegador. Refresh token no keyring (mesmo serviço KEYRING_SERVICE="ConfortimetroKlimaa" usado em confortimetro/assistant/store.py, usuário "google-drive"). Nunca em arquivo de texto, nunca em log.
3. Cliente OAuth: carregado de, nesta ordem, env AMBIENS_GOOGLE_CLIENT (caminho do JSON) e depois arquivo client_secret.json junto ao pacote (confortimetro/drive/client_secret.json), que entra no .gitignore e é incluído pelo empacotamento Windows (packaging/) se existir. Sem cliente: a seção Drive aparece desabilitada com mensagem clara; o resto do app funciona igual.
4. Dependências novas permitidas: google-api-python-client, google-auth-oauthlib (fixar versão em requirements.txt e constraints se aplicável). Imports preguiçosos (como o google-genai do assistente) para não pesar a abertura do app.
5. Módulo novo confortimetro/drive/ (poucos arquivos: auth + sync; sem abstração extra). Pasta raiz "Ambiens" no Drive; cada execução vira subpasta com o nome da pasta da execução em output_path, espelhando os arquivos (xlsx, gráficos, configs.json etc.).
6. Sincronização:
   - Push automático ao terminar cada simulação com sucesso (GUI e CLI quando conectado), em thread de fundo; nunca bloqueia a UI nem a simulação.
   - Ao conectar pela primeira vez: envia as execuções já existentes (backfill).
   - Idempotente: estado local (app_data_path(), ex. drive.json) mapeia execução→folderId e arquivo→(fileId, tamanho, mtime); reenvia só o que mudou. Grava atômico como _write_json do assistente.
   - Pull: execuções presentes na pasta Ambiens do Drive (criadas pelo app em outra máquina) e ausentes localmente são baixadas para output_path, para aparecerem no histórico. Na abertura do app e após conectar.
   - Sem rede/erro: fila persiste e tenta de novo na próxima abertura/execução; erro 401/invalid_grant marca "reconectar" na UI.
7. UI (Tkinter, siga theme.py e o padrão do assistant_panel/simulations_panel): no lugar natural (configurações ou painel de simulações) "Conectar Google Drive" / conta conectada / "Desconectar" (apaga token do keyring e estado); indicador discreto de status por execução (sincronizado / enviando / pendente / erro). Na execução do histórico: ação "Compartilhar" → abre diálogo com "Copiar link" (cria permissão anyone/reader na pasta da execução) e campo de e-mails (permissão user/reader, sendNotificationEmail=true). Avisar no diálogo que o link dá acesso a qualquer pessoa que o tenha. "Parar de compartilhar link" remove a permissão anyone.
8. CLI/MCP: só o push automático pós-execução quando já houver token; nada de fluxo de login pela CLI (opcional: subcomando para status). Não mexa no servidor MCP além disso.
9. Docs: seção nova em docs/PROJETO.md + docs/DRIVE.md curto com o passo a passo para o dono criar o cliente OAuth no GCP: ativar Google Drive API, tela de consentimento (tipo Externo, escopo drive.file, publicar em Produção para o refresh token não expirar em 7 dias — drive.file não exige verificação), credencial "App para computador", baixar JSON e onde colocá-lo.

Testes (pytest, sem rede): mocks do serviço Drive cobrindo: backfill + idempotência (segunda sync não reenvia nada), arquivo alterado reenvia só ele, pull baixa execução ausente, falha de rede deixa pendente e retoma, compartilhar cria/remove permissão anyone e convida e-mail, ausência de cliente desabilita sem quebrar. Nada de teste batendo na API real.

Fora do escopo: escolher IDF/EPW pelo Drive, Google Picker, scopes amplos, conflito de edição simultânea (última versão local vence; registre como ponytail: no código).

Pronto quando:
- `.venv/bin/python -m pytest tests -q` passa na worktree (use o .venv do checkout principal: /mnt/sda1/gabriellb/Documentos/Faculdade/projetos/gaia/confortimetro_klimaa_simulacoes/.venv/bin/python; instale as deps novas nele).
- `python -c "import confortimetro.gui.main_window"` importa sem cliente OAuth presente.
- Commits na branch drive-sync com mensagem clara. Não faça merge nem push.
Devolva: comandos rodados + saída (pytest, import), lista de arquivos alterados e qualquer decisão que você tomou fora deste briefing.
Pare e relate se: precisar de credencial real ou de decisão de produto não coberta.

## History

- 2026-10-06T17:23:10Z — todo (created)

- 2026-10-06T17:23:14Z — briefing aprovado pelo dono (sha256 a80dbbd2bfe3)

- 2026-10-06T17:23:32Z — briefing aprovado pelo dono (sha256 9c919aef5290)

- 2026-10-06T17:23:38Z — doing
