# Confortímetro Klimaa - Interface Web

Interface web moderna para o sistema de simulação Confortímetro Klimaa, construída com Flask e Bootstrap.

## 🚀 Características

### Interface Moderna
- **Design Responsivo**: Interface adaptável para desktop, tablet e mobile
- **Tema Moderno**: Paleta de cores profissional com cards e componentes estilizados
- **Feedback Visual**: Validação em tempo real, indicadores de status e notificações

### Funcionalidades Principais
- **Configuração Interativa**: Interface intuitiva para configurar simulações
- **Upload de Arquivos**: Drag & drop para arquivos IDF e EPW
- **Monitoramento em Tempo Real**: Acompanhamento do progresso das simulações
- **Log Centralizado**: Visualização de mensagens e eventos em tempo real
- **Controle de Sessão**: Gerenciamento automático de sessões de usuário

### Tecnologias
- **Backend**: Flask + Flask-SocketIO
- **Frontend**: Bootstrap 5, JavaScript ES6, Socket.IO
- **Comunicação**: REST APIs + WebSockets para tempo real
- **Styling**: CSS customizado com variáveis e componentes modulares

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Dependências do projeto principal (eppy, numpy, etc.)
- Navegador moderno com suporte a WebSockets

## 🛠️ Instalação e Execução

### Método 1: Script Automático (Recomendado)

```bash
# Instalar e executar em um comando
./run_web.sh

# Ou apenas instalar as dependências
./run_web.sh install

# Depois executar
./run_web.sh start
```

### Método 2: Manual

```bash
# 1. Criar ambiente virtual
python3 -m venv venv_web
source venv_web/bin/activate

# 2. Instalar dependências
pip install -r src/web/requirements.txt

# 3. Configurar PYTHONPATH
export PYTHONPATH="$PWD:$PYTHONPATH"

# 4. Executar servidor
cd src/web
python app.py
```

### Acesso
Abra seu navegador e acesse: **http://localhost:5000**

## 📁 Estrutura da Interface Web

```
src/web/
├── app.py                    # Aplicação Flask principal
├── simulation_integration.py # Integração com módulos de simulação
├── requirements.txt          # Dependências específicas da web
├── templates/
│   └── index.html           # Template principal
└── static/
    ├── css/
    │   └── style.css        # Estilos customizados
    └── js/
        └── app.js           # Lógica JavaScript
```

## 🎨 Interface do Usuário

### Painel de Configuração
- **Caminhos de Arquivos**: Configuração de arquivos IDF, EPW e diretórios
- **Parâmetros PMV**: Controles para limites de conforto térmico
- **Configurações do AC**: Temperaturas mínima e máxima
- **Parâmetros Pessoais**: Taxa metabólica (MET) e trabalho mecânico (WME)
- **Tipo de Módulo**: Seleção do tipo de simulação
- **Salas**: Lista de ambientes para simulação

### Painel de Controle
- **Botão Executar**: Inicia a simulação com validação automática
- **Botão Parar**: Interrompe simulação em execução
- **Status em Tempo Real**: Indicadores visuais do estado da simulação
- **Barra de Progresso**: Acompanhamento visual do progresso

### Painel de Resultados
- **Log em Tempo Real**: Mensagens categorizadas (info, sucesso, warning, erro)
- **Filtros**: Filtragem por tipo de mensagem
- **Exportação**: Download do log completo
- **Limpeza**: Opção para limpar o histórico

### Indicadores de Status
- **Conexão**: Status da conexão WebSocket
- **Sessão**: Identificador único da sessão
- **Última Atualização**: Timestamp da última atividade

## 🔧 Funcionalidades Técnicas

### Upload de Arquivos
- **Validação Automática**: Verificação de extensões (.idf, .epw)
- **Feedback Visual**: Indicadores de progresso e status
- **Armazenamento Seguro**: Nomes únicos e validação de conteúdo
- **Limite de Tamanho**: Máximo de 50MB por arquivo

### Comunicação em Tempo Real
- **WebSockets**: Comunicação bidirecional para atualizações instantâneas
- **Auto-reconexão**: Reconexão automática em caso de perda de conexão
- **Keepalive**: Sistema de ping/pong para manter conexão ativa

### Validação e Feedback
- **Validação Cliente**: Verificação instantânea de campos obrigatórios
- **Validação Servidor**: Verificação de arquivos e configurações
- **Feedback Visual**: Classes CSS para indicar status (válido/inválido)
- **Mensagens Contextuais**: Tooltips e mensagens de ajuda

### Gerenciamento de Sessão
- **Sessões Únicas**: UUID para cada sessão de usuário
- **Persistência**: Manutenção do estado durante a navegação
- **Isolamento**: Configurações independentes por sessão

## 🚀 Recursos Avançados

### Atalhos de Teclado
- **Ctrl+S**: Salvar configuração
- **Ctrl+R**: Executar simulação (se não estiver rodando)

### Auto-save
- **Salvamento Automático**: Configurações salvas a cada 30 segundos
- **Detecção de Mudanças**: Apenas salva quando há alterações

### Notificações
- **Toasts**: Notificações temporárias para ações importantes
- **Persistência**: Mensagens importantes mantidas no log

### Responsividade
- **Design Mobile-First**: Interface otimizada para dispositivos móveis
- **Breakpoints**: Adaptação automática para diferentes tamanhos de tela
- **Touch-Friendly**: Botões e controles otimizados para touch

## 🔍 Debugging e Logs

### Logs do Servidor
```bash
# Ver logs em tempo real
tail -f logs/web_app.log

# Logs de simulação
tail -f logs/simulation_*.log
```

### Console do Navegador
Abra as ferramentas de desenvolvedor (F12) para ver logs detalhados da comunicação WebSocket e eventos JavaScript.

### Modo Debug
O servidor Flask roda em modo debug por padrão, permitindo:
- Reload automático em mudanças de código
- Stack traces detalhados
- Debug toolbar (se instalado)

## 🛠️ Customização

### Temas e Cores
Edite `src/web/static/css/style.css` para personalizar:
- Paleta de cores (variáveis CSS no início do arquivo)
- Tipografia e espaçamentos
- Animações e transições

### Funcionalidades
Adicione novas funcionalidades editando:
- `app.py`: Novos endpoints e lógica de servidor
- `app.js`: Lógica de frontend e interações
- `index.html`: Novos componentes de interface

## 📊 Monitoramento

### Métricas Disponíveis
- Sessões ativas
- Simulações em execução
- Uploads realizados
- Tempo de resposta das operações

### Health Check
Acesse `/health` para verificar o status do servidor (endpoint a ser implementado).

## 🚧 Desenvolvimento Futuro

### Melhorias Planejadas
- [ ] Dashboard com métricas
- [ ] Histórico de simulações
- [ ] Export de configurações
- [ ] Templates de configuração
- [ ] Visualizações gráficas dos resultados
- [ ] Sistema de usuários e autenticação
- [ ] API REST completa
- [ ] Testes automatizados

### Contribuições
Para contribuir com o desenvolvimento:
1. Fork do repositório
2. Crie uma branch para sua feature
3. Implemente com testes
4. Submit pull request

## 📄 Licença

Este projeto segue a mesma licença do projeto principal Confortímetro Klimaa.
