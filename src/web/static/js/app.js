/**
 * Confortímetro Klimaa Web Interface
 * JavaScript functionality for the web interface
 */

class ConfortimetroApp {
    constructor() {
        this.socket = null;
        this.sessionId = null;
        this.isConnected = false;
        this.isSimulationRunning = false;
        this.messages = [];
        this.messageFilter = 'all';
        
        this.init();
    }
    
    init() {
        // Initialize Socket.IO connection
        this.initSocket();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial configuration
        this.loadConfiguration();
        
        // Setup auto-save
        this.setupAutoSave();
    }

    // Helper to wrap fetch with timeout to avoid UI hanging
    async fetchWithTimeout(url, options = {}, timeout = 30000) {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        options.signal = controller.signal;
        try {
            const res = await fetch(url, options);
            return res;
        } finally {
            clearTimeout(id);
        }
    }

    // Helper to retry idempotent requests with exponential backoff
    async fetchWithRetry(url, options = {}, retries = 3, backoff = 500, timeout = 5000) {
        let attempt = 0;
        while (attempt < retries) {
            try {
                const res = await this.fetchWithTimeout(url, options, timeout);
                return res;
            } catch (err) {
                attempt++;
                const isAbort = err.name === 'AbortError';
                // For abort (timeout) or network error, retry until attempts exhausted
                if (attempt >= retries) {
                    throw err;
                }
                // Backoff delay
                await new Promise(r => setTimeout(r, backoff * Math.pow(2, attempt - 1)));
            }
        }
    }
    
    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.isConnected = true;
            this.updateConnectionStatus(true);
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.isConnected = false;
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('connected', (data) => {
            this.sessionId = data.session_id;
            this.updateSessionInfo();
            this.addMessage('Conectado ao servidor', 'success');
        });
        
        this.socket.on('simulation_message', (data) => {
            this.addMessage(data.message, data.type);
        });
        
        this.socket.on('simulation_finished', (data) => {
            this.onSimulationFinished();
            this.addMessage(data.message, 'success');
        });
        
        // Keepalive
        setInterval(() => {
            if (this.isConnected) {
                this.socket.emit('ping');
            }
        }, 30000);
    }
    
    setupEventListeners() {
        // Configuration change listeners
        document.querySelectorAll('input, select').forEach(element => {
            element.addEventListener('change', () => {
                this.onConfigurationChange();
            });
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveConfiguration();
            }
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                if (!this.isSimulationRunning) {
                    this.startSimulation();
                }
            }
        });
    }
    
    setupAutoSave() {
        // Auto-save configuration every 30 seconds
        setInterval(() => {
            this.autoSaveConfiguration();
        }, 30000);
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connection-status');
        if (connected) {
            statusElement.className = 'badge bg-success';
            statusElement.innerHTML = '<i class="bi bi-wifi"></i> Conectado';
        } else {
            statusElement.className = 'badge bg-danger';
            statusElement.innerHTML = '<i class="bi bi-wifi-off"></i> Desconectado';
        }
    }
    
    updateSessionInfo() {
        const sessionElement = document.getElementById('session-info');
        if (this.sessionId) {
            sessionElement.textContent = `Sessão: ${this.sessionId.substring(0, 8)}...`;
        }
    }
    
    onConfigurationChange() {
        // Validate inputs and provide visual feedback
        this.validateConfiguration();
        
        // Update configuration on server
        this.updateConfiguration();
    }
    
    validateConfiguration() {
        const fields = {
            'idf-path': { required: true, type: 'file', extension: '.idf' },
            'epw-path': { required: true, type: 'file', extension: '.epw' },
            'energy-path': { required: true, type: 'directory' }
        };
        
        let isValid = true;
        
        Object.entries(fields).forEach(([fieldId, rules]) => {
            const field = document.getElementById(fieldId);
            const value = field.value.trim();
            
            field.classList.remove('is-valid', 'is-invalid');
            
            if (rules.required && !value) {
                field.classList.add('is-invalid');
                isValid = false;
            } else if (value) {
                field.classList.add('is-valid');
            }
        });
        
        return isValid;
    }
    
    async updateConfiguration() {
        const config = this.getConfiguration();
        
        try {
            const response = await this.fetchWithTimeout('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            }, 8000);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error updating configuration:', error);
        }
    }
    
    async autoSaveConfiguration() {
        if (this.hasUnsavedChanges()) {
            await this.updateConfiguration();
        }
    }
    
    getConfiguration() {
        return {
            idf_path: document.getElementById('idf-path').value,
            epw_path: document.getElementById('epw-path').value,
            energy_path: document.getElementById('energy-path').value,
            pmv_lowerbound: parseFloat(document.getElementById('pmv-lowerbound').value),
            pmv_upperbound: parseFloat(document.getElementById('pmv-upperbound').value),
            temp_ac_min: parseFloat(document.getElementById('temp-ac-min').value),
            temp_ac_max: parseFloat(document.getElementById('temp-ac-max').value),
            met: parseFloat(document.getElementById('met').value),
            wme: parseFloat(document.getElementById('wme').value),
            module_type: document.getElementById('module-type').value,
            rooms: document.getElementById('rooms').value.split(',').map(s => s.trim()).filter(s => s)
        };
    }
    
    setConfiguration(config) {
        document.getElementById('idf-path').value = config.idf_path || '';
        document.getElementById('epw-path').value = config.epw_path || '';
        document.getElementById('energy-path').value = config.energy_path || '';
        document.getElementById('pmv-lowerbound').value = config.pmv_lowerbound || -0.5;
        document.getElementById('pmv-upperbound').value = config.pmv_upperbound || 0.5;
        document.getElementById('temp-ac-min').value = config.temp_ac_min || 18.0;
        document.getElementById('temp-ac-max').value = config.temp_ac_max || 26.0;
        document.getElementById('met').value = config.met || 1.0;
        document.getElementById('wme').value = config.wme || 0.0;
        document.getElementById('module-type').value = config.module_type || 'COMPLETE';
        document.getElementById('rooms').value = (config.rooms || ['ATELIE1']).join(', ');
    }
    
    async loadConfiguration() {
        try {
            const response = await this.fetchWithRetry('/api/config', {}, 3, 400, 5000);
            if (response.ok) {
                const config = await response.json();
                this.setConfiguration(config);
                this.addMessage('Configuração carregada', 'success');
            } else {
                const err = await response.json().catch(() => ({}));
                this.addMessage(err.error || 'Erro ao carregar configuração', 'error');
            }
        } catch (error) {
            console.error('Error loading configuration:', error);
            const isTimeout = error.name === 'AbortError';
            this.addMessage(isTimeout ? 'Erro: tempo esgotado ao carregar configuração' : 'Erro ao carregar configuração (rede)', isTimeout ? 'warning' : 'error');
        }
    }
    
    async saveConfiguration() {
        this.showLoading('Salvando configuração...');
        
        try {
            await this.updateConfiguration();
            this.hideLoading();
            this.addMessage('Configuração salva com sucesso', 'success');
            this.showToast('Configuração salva!', 'success');
        } catch (error) {
            this.hideLoading();
            this.addMessage('Erro ao salvar configuração', 'error');
            this.showToast('Erro ao salvar configuração', 'error');
        }
    }
    
    async startSimulation() {
        if (this.isSimulationRunning) {
            return;
        }
        
        // Validate configuration first
        if (!this.validateConfiguration()) {
            this.showToast('Por favor, corrija os campos obrigatórios', 'warning');
            return;
        }
        
        this.showLoading('Iniciando simulação...');
        
        try {
            const response = await this.fetchWithTimeout('/api/simulation/start', { method: 'POST' }, 45000);
            
            if (response.ok) {
                this.onSimulationStarted();
                this.addMessage('Simulação iniciada', 'info');
            } else {
                const error = await response.json();
                throw new Error(error.error || 'Erro desconhecido');
            }
        } catch (error) {
            const isTimeout = error.name === 'AbortError';
            this.addMessage(`Erro ao iniciar simulação: ${isTimeout ? 'Timeout' : error.message}`, isTimeout ? 'warning' : 'error');
            this.showToast(isTimeout ? 'Tempo esgotado ao iniciar simulação' : 'Erro ao iniciar simulação', isTimeout ? 'warning' : 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    async stopSimulation() {
        if (!this.isSimulationRunning) {
            return;
        }
        
        try {
            const response = await this.fetchWithTimeout('/api/simulation/stop', { method: 'POST' }, 15000);
            
            if (response.ok) {
                this.onSimulationStopped();
                this.addMessage('Parada solicitada', 'warning');
            } else {
                const err = await response.json().catch(()=>({error:'unknown'}));
                this.addMessage(`Erro ao parar simulação: ${err.error || 'Erro'}`, 'error');
            }
        } catch (error) {
            const msg = error.name === 'AbortError' ? 'Timeout ao parar simulação' : error.message;
            this.addMessage(`Erro ao parar simulação: ${msg}`, 'error');
        }
    }
    
    onSimulationStarted() {
        this.isSimulationRunning = true;
        
        // Update UI
        document.getElementById('run-btn').style.display = 'none';
        document.getElementById('stop-btn').style.display = 'inline-block';
        document.getElementById('progress-container').style.display = 'block';
        
        this.updateSimulationStatus('Simulação em execução...', 'running');
        
        // Disable configuration inputs
        document.querySelectorAll('input, select').forEach(element => {
            element.disabled = true;
        });
    }
    
    onSimulationStopped() {
        this.isSimulationRunning = false;
        this.onSimulationFinished();
    }
    
    onSimulationFinished() {
        this.isSimulationRunning = false;
        
        // Update UI
        document.getElementById('run-btn').style.display = 'inline-block';
        document.getElementById('stop-btn').style.display = 'none';
        document.getElementById('progress-container').style.display = 'none';
        
        this.updateSimulationStatus('Pronto para executar', 'ready');
        
        // Re-enable configuration inputs
        document.querySelectorAll('input, select').forEach(element => {
            element.disabled = false;
        });
        
        this.showToast('Simulação concluída!', 'success');
    }
    
    updateSimulationStatus(message, type) {
        const statusElement = document.getElementById('simulation-status');
        const iconMap = {
            ready: 'bi-circle-fill',
            running: 'bi-arrow-clockwise',
            error: 'bi-exclamation-triangle-fill'
        };
        const classMap = {
            ready: 'bg-secondary',
            running: 'bg-warning',
            error: 'bg-danger'
        };
        
        statusElement.innerHTML = `
            <span class="badge ${classMap[type] || 'bg-secondary'}">
                <i class="bi ${iconMap[type] || 'bi-circle-fill'} me-1"></i>
                ${message}
            </span>
        `;
    }
    
    addMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const messageObj = { message, type, timestamp };
        
        this.messages.push(messageObj);
        
        // Keep only last 500 messages
        if (this.messages.length > 500) {
            this.messages = this.messages.slice(-500);
        }
        
        this.displayMessage(messageObj);
        this.updateMessageCount();
        this.updateLastUpdate();
    }
    
    displayMessage(messageObj) {
        if (this.messageFilter !== 'all' && this.messageFilter !== messageObj.type) {
            return;
        }
        
        const container = document.getElementById('messages-container');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-item ${messageObj.type} fade-in`;
        
        const iconMap = {
            info: 'bi-info-circle',
            success: 'bi-check-circle',
            warning: 'bi-exclamation-triangle',
            error: 'bi-x-circle'
        };
        
        messageDiv.innerHTML = `
            <div class="d-flex align-items-start">
                <i class="bi ${iconMap[messageObj.type] || 'bi-info-circle'} me-2 mt-1"></i>
                <div class="flex-grow-1">
                    <div class="message-content">${this.escapeHtml(messageObj.message)}</div>
                    <div class="message-timestamp">${messageObj.timestamp}</div>
                </div>
            </div>
        `;
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }
    
    filterMessages() {
        this.messageFilter = document.getElementById('message-filter').value;
        this.refreshMessages();
    }
    
    refreshMessages() {
        const container = document.getElementById('messages-container');
        container.innerHTML = '';
        
        this.messages
            .filter(msg => this.messageFilter === 'all' || msg.type === this.messageFilter)
            .forEach(msg => this.displayMessage(msg));
    }
    
    clearMessages() {
        if (confirm('Deseja realmente limpar todas as mensagens?')) {
            this.messages = [];
            document.getElementById('messages-container').innerHTML = `
                <div class="text-muted">
                    <i class="bi bi-info-circle me-2"></i>
                    Log limpo. Aguardando novas mensagens...
                </div>
            `;
            this.updateMessageCount();
        }
    }
    
    exportMessages() {
        const content = this.messages
            .map(msg => `[${msg.timestamp}] [${msg.type.toUpperCase()}] ${msg.message}`)
            .join('\n');
        
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `klimaa-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    updateMessageCount() {
        const total = this.messages.length;
        const filtered = this.messageFilter === 'all' ? 
            total : 
            this.messages.filter(msg => msg.type === this.messageFilter).length;
        
        document.getElementById('message-count').textContent = 
            this.messageFilter === 'all' ? 
            `${total} mensagens` : 
            `${filtered} de ${total} mensagens`;
    }
    
    updateLastUpdate() {
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    }
    
    showLoading(text = 'Carregando...') {
        document.getElementById('loading-text').textContent = text;
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }
    
    hideLoading() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('loadingModal'));
        if (modal) {
            modal.hide();
        }
    }
    
    showToast(message, type = 'info') {
        // Create toast element
        const toastContainer = document.querySelector('.toast-container') || (() => {
            const container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
            return container;
        })();
        
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'success' ? 'bg-success' : 
                       type === 'error' ? 'bg-danger' : 
                       type === 'warning' ? 'bg-warning' : 'bg-primary';
        
        const toastHTML = `
            <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
                <div class="toast-body d-flex align-items-center">
                    <i class="bi bi-${type === 'success' ? 'check-circle' : 
                                      type === 'error' ? 'x-circle' : 
                                      type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
                    ${message}
                    <button type="button" class="btn-close btn-close-white ms-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
        
        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }
    
    hasUnsavedChanges() {
        // Simple check - in a real app, you'd compare with last saved state
        return true;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// File upload functions
function handleFileUpload(input, type) {
    const file = input.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', type);
    
    app.showLoading(`Uploading ${type.toUpperCase()} file...`);
    
    app.showLoading(`Uploading ${type.toUpperCase()} file...`);
    app.fetchWithTimeout('/api/upload', { method: 'POST', body: formData }, 60000)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById(`${type}-path`).value = data.path;
            app.addMessage(`${data.filename} uploaded successfully`, 'success');
            app.onConfigurationChange();
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    })
    .catch(error => {
        const isTimeout = error.name === 'AbortError';
        const msg = isTimeout ? 'Timeout no upload' : error.message;
        app.addMessage(`Upload error: ${msg}`, isTimeout ? 'warning' : 'error');
        app.showToast(isTimeout ? 'Upload timeout' : 'Erro no upload', isTimeout ? 'warning' : 'error');
    })
    .finally(() => {
        app.hideLoading();
        input.value = ''; // Reset file input
    });
}

function openFileSelector(type) {
    document.getElementById(`${type}-file`).click();
}

// Global functions
function startSimulation() {
    app.startSimulation();
}

function stopSimulation() {
    app.stopSimulation();
}

function saveConfiguration() {
    app.saveConfiguration();
}

function loadConfiguration() {
    app.loadConfiguration();
}

function filterMessages() {
    app.filterMessages();
}

function clearMessages() {
    app.clearMessages();
}

function exportMessages() {
    app.exportMessages();
}

// Download simulation outputs as zip
async function downloadOutputs() {
    try {
        app.showLoading('Preparando download...');
    const res = await app.fetchWithTimeout('/api/simulation/download', {}, 60000);
        if (!res.ok) {
            const err = await res.json().catch(()=>({error:'unknown'}));
            throw new Error(err.error || 'Falha ao criar o zip');
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `simulation-outputs-${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        app.addMessage('Download iniciado', 'success');
    } catch (error) {
        console.error('Download error', error);
        app.addMessage(`Erro ao preparar download: ${error.message}`, 'error');
        app.showToast('Erro ao preparar download', 'error');
    } finally {
        app.hideLoading();
    }
}

// Initialize app when page loads
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new ConfortimetroApp();
});
