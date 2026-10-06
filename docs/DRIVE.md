# Google Drive — cliente OAuth

O Ambiens sincroniza as execuções com o Google Drive de quem usa o app
(pasta `Ambiens`, uma subpasta por execução). Para isso o app precisa de um
**cliente OAuth** do projeto GCP do dono. Sem ele, a seção "Google Drive" das
Configurações aparece desabilitada e o resto funciona igual.

Funcionamento e código: seção 8 de [`PROJETO.md`](PROJETO.md#google-drive).

## Criar o cliente (uma vez)

No [Google Cloud Console](https://console.cloud.google.com/), com o projeto
do Ambiens selecionado (ou um novo):

1. **Ativar a API.** *APIs e serviços → Biblioteca* → "Google Drive API" →
   **Ativar**.
2. **Tela de consentimento.** *APIs e serviços → Tela de consentimento OAuth*
   (no console novo: *Google Auth Platform → Branding/Público*):
   - tipo de usuário **Externo**;
   - nome do app "Ambiens", e-mail de suporte e e-mail do desenvolvedor;
   - em *Escopos* (*Acesso a dados*), adicione **somente**
     `https://www.googleapis.com/auth/drive.file` ("Ver, editar, criar e
     excluir apenas os arquivos do Google Drive que você usa com este app").
     Ele não é sensível nem restrito: não pede verificação do Google;
   - em *Público*, clique **Publicar app** para passar de "Em teste" para
     **Em produção**. Em teste o refresh token expira em 7 dias e o usuário
     teria de reconectar toda semana; com `drive.file` publicar não exige
     verificação.
3. **Credencial.** *APIs e serviços → Credenciais → Criar credenciais → ID do
   cliente OAuth* → tipo **App para computador** → nome "Ambiens desktop" →
   **Criar**.
4. **Baixar o JSON** (botão de download na credencial criada). O arquivo tem a
   forma `{"installed": {"client_id": ..., "client_secret": ..., ...}}`.

O `client_secret` de um app para computador não é segredo de verdade (vai
dentro de todo instalador), mas não o versione: o `.gitignore` já ignora o
caminho abaixo.

## Onde pôr o JSON

O app procura, nesta ordem:

1. o caminho da variável de ambiente `AMBIENS_GOOGLE_CLIENT`;
2. `confortimetro/drive/client_secret.json` (junto do pacote).

- **Desenvolvimento**: copie o JSON para
  `confortimetro/drive/client_secret.json`, ou exporte
  `AMBIENS_GOOGLE_CLIENT=/caminho/client.json`.
- **Instalador Windows**: crie no GitHub o secret de repositório
  `GOOGLE_OAUTH_CLIENT` com o **conteúdo** do JSON. O workflow
  `windows-build.yml` grava o arquivo antes do PyInstaller e o
  `packaging/confortimetro.spec` o inclui no bundle se existir. Sem o secret o
  build passa e o Drive fica desabilitado nesse instalador.

## Conferir

Abra o app → **Configurações** → card "Google Drive" → **Conectar Google
Drive**. O navegador abre a tela de consentimento; ao terminar, o card mostra
"Conectado como <e-mail>" e as execuções existentes começam a subir.
