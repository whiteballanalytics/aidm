// D&D AI Dungeon Master - Frontend Application

class DnDApp {
    constructor() {
        this.currentTab = 'campaigns';
        this.worlds = {};
        this.campaigns = [];
        this.currentCampaign = null;
        this.sessions = [];
        this.currentSession = null;
        this.websocket = null;
        this.voiceClient = null;
        this.partyPanelOpen = false;
        
        // Characters loaded from database
        this.characters = [];
        
        // Action mode: 'party', 'character', or 'ask_dm'
        this.actionMode = 'party';
        this.actionCharacterId = null;
        
        this.init();
    }

    async init() {
        await this.loadWorlds();
        this.setupEventListeners();
        this.initVoice();
        this.initParty();
        this.showTab('campaigns');
        await this.refreshCampaigns();
    }
    
    async initParty() {
        // Load characters from database
        await this.loadCharacters();
        this.updateLivePartyDisplay();
    }
    
    async loadCharacters() {
        try {
            const response = await this.apiRequest('/api/characters');
            this.characters = (response.characters || []).map(char => ({
                ...char,
                isLive: false
            }));
        } catch (error) {
            console.warn('Failed to load characters:', error);
            this.characters = [];
        }
    }
    
    initVoice() {
        if (typeof VoiceClient !== 'undefined') {
            this.voiceClient = new VoiceClient(this);
            
            const micButton = document.getElementById('voice-mic-button');
            if (micButton && !this.voiceClient.isAvailable()) {
                micButton.disabled = true;
                micButton.title = 'Voice input not supported in this browser';
            }
        }
    }
    
    toggleVoice() {
        if (!this.voiceClient) {
            this.showAlert('Voice features are not available', 'error');
            return;
        }
        
        if (!this.voiceClient.isAvailable()) {
            this.showAlert('Voice input is not supported in your browser. Try Chrome or Edge.', 'error');
            return;
        }
        
        this.voiceClient.toggleListening();
    }

    // Party Management Methods
    togglePartyPanel() {
        this.partyPanelOpen = !this.partyPanelOpen;
        const panel = document.getElementById('party-panel');
        const overlay = document.getElementById('party-overlay');
        
        if (this.partyPanelOpen) {
            panel.classList.add('active');
            overlay.classList.add('active');
            this.renderCharacters();
        } else {
            panel.classList.remove('active');
            overlay.classList.remove('active');
        }
    }
    
    renderCharacters() {
        const container = document.getElementById('character-list');
        if (!container) return;
        
        if (this.characters.length === 0) {
            container.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted);">No characters yet. Add one to get started!</p>';
            return;
        }
        
        container.innerHTML = this.characters.map(char => `
            <div class="character-card" onclick="app.toggleCharacterLive('${char.id}')">
                <div class="character-card-actions">
                    <button class="char-action-btn" onclick="event.stopPropagation(); app.showUpdateCharacterModal('${char.id}')" title="Update">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3Z"/>
                        </svg>
                    </button>
                    <button class="char-action-btn char-action-delete" onclick="event.stopPropagation(); app.confirmDeleteCharacter('${char.id}', '${char.name.replace(/'/g, "\\'")}')" title="Delete">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
                <input type="checkbox" class="character-card-radio" 
                       ${char.isLive ? 'checked' : ''} 
                       onclick="event.stopPropagation(); app.toggleCharacterLive('${char.id}')">
                <div class="character-card-name">${char.name}</div>
                <div class="character-card-stat">
                    <span class="character-card-stat-label">Class</span>
                    <span class="character-card-stat-value">${char.class}</span>
                </div>
                <div class="character-card-stat">
                    <span class="character-card-stat-label">Level</span>
                    <span class="character-card-stat-value">${char.level}</span>
                </div>
                <div class="character-card-stat">
                    <span class="character-card-stat-label">Race</span>
                    <span class="character-card-stat-value">${char.race}</span>
                </div>
                <div class="character-card-stat">
                    <span class="character-card-stat-label">HP</span>
                    <span class="character-card-stat-value">${char.currentHp}/${char.maxHp}</span>
                </div>
            </div>
        `).join('');
    }
    
    toggleCharacterLive(charId) {
        const char = this.characters.find(c => c.id === charId);
        if (char) {
            char.isLive = !char.isLive;
            this.renderCharacters();
            this.updateLivePartyDisplay();
        }
    }
    
    updateLivePartyDisplay() {
        const container = document.getElementById('live-party-display');
        if (!container) return;
        
        const liveChars = this.characters.filter(c => c.isLive);
        
        if (liveChars.length === 0) {
            container.innerHTML = '';
        } else {
            container.innerHTML = liveChars.map(char => `
                <div class="live-character-card">
                    <div class="live-character-info">
                        <div class="live-character-name">${char.name}</div>
                        <div class="live-character-class">${char.race} ${char.class} Level ${char.level}</div>
                    </div>
                    <div class="live-stat-box">
                        <div class="live-stat-label">HP</div>
                        <div class="live-stat-value">${char.currentHp}/${char.maxHp}</div>
                    </div>
                </div>
            `).join('');
        }
        
        // Also update the action character selector
        this.updateActionCharacterSelect();
    }
    
    // Action Mode Methods
    setActionMode(mode) {
        this.actionMode = mode;
        
        // Update button states
        document.querySelectorAll('.action-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        
        // Show/hide character selector
        const selector = document.getElementById('character-selector');
        if (selector) {
            selector.style.display = mode === 'character' ? 'flex' : 'none';
        }
        
        // Update placeholder text based on mode
        const input = document.getElementById('chat-input');
        if (input) {
            const placeholders = {
                'party': 'Describe your party\'s action...',
                'character': 'Describe your character\'s action...',
                'ask_dm': 'Ask the DM a question...'
            };
            input.placeholder = placeholders[mode] || 'Describe your action...';
        }
        
        // Reset character selection when switching away from character mode
        if (mode !== 'character') {
            this.actionCharacterId = null;
        }
    }
    
    updateActionCharacterSelect() {
        const select = document.getElementById('action-character-select');
        if (!select) return;
        
        const liveChars = this.characters.filter(c => c.isLive);
        
        select.innerHTML = '<option value="">Select character...</option>';
        liveChars.forEach(char => {
            const option = document.createElement('option');
            option.value = char.id;
            option.textContent = `${char.name} (${char.class})`;
            select.appendChild(option);
        });
        
        // Reset selection if current character is no longer live
        if (this.actionCharacterId && !liveChars.find(c => c.id === this.actionCharacterId)) {
            this.actionCharacterId = null;
            select.value = '';
        }
    }
    
    getActionContext() {
        return {
            action_mode: this.actionMode,
            character_id: this.actionMode === 'character' ? this.actionCharacterId : null,
            character_name: this.actionMode === 'character' && this.actionCharacterId 
                ? this.characters.find(c => c.id === this.actionCharacterId)?.name 
                : null
        };
    }
    
    confirmDeleteCharacter(charId, charName) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 400px; width: 100%;" onclick="event.stopPropagation()">
                    <h3 style="color: var(--danger-color);">Delete Character</h3>
                    <p style="margin-bottom: 20px;">Are you sure you want to delete <strong>${charName}</strong>? This cannot be undone.</p>
                    
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                        <button class="btn" style="background: var(--danger-color);" onclick="app.deleteCharacter('${charId}'); this.closest('[style*=fixed]').remove()">Delete</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    async deleteCharacter(charId) {
        try {
            await this.apiRequest(`/api/characters/${charId}`, { method: 'DELETE' });
            this.characters = this.characters.filter(c => c.id !== charId);
            this.renderCharacters();
            this.updateLivePartyDisplay();
            this.showAlert('Character deleted', 'success');
        } catch (error) {
            console.error('Failed to delete character:', error);
            this.showAlert(error.message || 'Failed to delete character', 'error');
        }
    }
    
    showUpdateCharacterModal(charId) {
        const char = this.characters.find(c => c.id === charId);
        if (!char) return;
        
        const hasDDBSource = char.source === 'dndbeyond' && char.dndbeyond_id;
        
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 450px; width: 100%;" onclick="event.stopPropagation()">
                    <h3>Update ${char.name}</h3>
                    <p style="margin-bottom: 20px; color: var(--text-muted);">Choose how to update this character:</p>
                    
                    <div style="display: flex; flex-direction: column; gap: 15px;">
                        ${hasDDBSource ? `
                        <div class="card" style="cursor: pointer; margin-bottom: 0;" onclick="app.refreshCharacterFromDDB('${charId}'); this.closest('[style*=fixed]').remove();">
                            <h4 style="color: var(--primary-accent); margin-bottom: 8px;">🔄 Refresh from D&D Beyond</h4>
                            <p style="font-size: 0.9em;">Pull the latest data from your D&D Beyond character sheet (ID: ${char.dndbeyond_id}).</p>
                        </div>
                        ` : `
                        <div class="card" style="margin-bottom: 0; opacity: 0.5;">
                            <h4 style="color: var(--text-muted); margin-bottom: 8px;">🔄 Refresh from D&D Beyond</h4>
                            <p style="font-size: 0.9em;">Not available - this character wasn't imported from D&D Beyond.</p>
                        </div>
                        `}
                        
                        <div class="card" style="cursor: pointer; margin-bottom: 0;" onclick="app.showUpdatePDFForm('${charId}'); this.closest('[style*=fixed]').remove();">
                            <h4 style="color: var(--primary-accent); margin-bottom: 8px;">📄 Upload New PDF</h4>
                            <p style="font-size: 0.9em;">Replace this character's data with a new PDF character sheet.</p>
                        </div>
                    </div>
                    
                    <div class="text-center mt-20">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    showUpdatePDFForm(charId) {
        const char = this.characters.find(c => c.id === charId);
        if (!char) return;
        
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 450px; width: 100%;" onclick="event.stopPropagation()">
                    <h3>Update ${char.name} from PDF</h3>
                    <p style="margin-bottom: 20px; color: var(--text-muted);">Select a new PDF character sheet:</p>
                    
                    <div class="form-group">
                        <input type="file" id="pdf-upload-input" class="form-input" accept=".pdf"
                               style="padding: 10px;">
                    </div>
                    
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                        <button class="btn" onclick="app.uploadPDF('${charId}')">Update Character</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    async refreshCharacterFromDDB(charId) {
        try {
            this.showLoading('Refreshing character from D&D Beyond...');
            
            const updatedChar = await this.apiRequest(`/api/characters/${charId}/refresh`, { method: 'POST' });
            
            const index = this.characters.findIndex(c => c.id === charId);
            if (index !== -1) {
                const wasLive = this.characters[index].isLive;
                this.characters[index] = { ...updatedChar, isLive: wasLive };
            }
            
            this.renderCharacters();
            this.updateLivePartyDisplay();
            this.showAlert(`${updatedChar.name} updated successfully!`, 'success');
            
        } catch (error) {
            console.error('Failed to refresh character:', error);
            this.showAlert(error.message || 'Failed to refresh character', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    showAddCharacterMenu() {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 450px; width: 100%;" onclick="event.stopPropagation()">
                    <h3>Add Character</h3>
                    <p style="margin-bottom: 20px; color: var(--text-muted);">Choose how to add your character:</p>
                    
                    <div style="display: flex; flex-direction: column; gap: 15px;">
                        <div class="card" style="cursor: pointer; margin-bottom: 0;" onclick="app.showDDBImportForm(); this.closest('[style*=fixed]').remove();">
                            <h4 style="color: var(--primary-accent); margin-bottom: 8px;">🔗 Import from D&D Beyond</h4>
                            <p style="font-size: 0.9em;">Paste a D&D Beyond character URL or ID to import your character sheet automatically.</p>
                        </div>
                        
                        <div class="card" style="cursor: pointer; margin-bottom: 0;" onclick="app.showPDFUploadForm(); this.closest('[style*=fixed]').remove();">
                            <h4 style="color: var(--primary-accent); margin-bottom: 8px;">📄 Upload Character PDF</h4>
                            <p style="font-size: 0.9em;">Upload a PDF character sheet to extract your character's stats.</p>
                        </div>
                    </div>
                    
                    <div class="text-center mt-20">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    showDDBImportForm() {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 450px; width: 100%;" onclick="event.stopPropagation()">
                    <h3>Import from D&D Beyond</h3>
                    <p style="margin-bottom: 20px; color: var(--text-muted);">Enter your character URL or ID:</p>
                    
                    <div class="form-group">
                        <input type="text" id="ddb-import-input" class="form-input" 
                               placeholder="https://dndbeyond.com/characters/115183470 or just 115183470">
                    </div>
                    
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                        <button class="btn" onclick="app.importFromDDB()">Import Character</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        document.getElementById('ddb-import-input').focus();
    }
    
    async importFromDDB() {
        const input = document.getElementById('ddb-import-input');
        const value = input?.value?.trim();
        
        if (!value) {
            this.showAlert('Please enter a D&D Beyond character URL or ID', 'error');
            return;
        }
        
        // Extract character ID from URL or use directly if numeric
        let charId = value;
        const urlMatch = value.match(/characters\/(\d+)/);
        if (urlMatch) {
            charId = urlMatch[1];
        }
        
        // Validate that we have a numeric ID
        if (!/^\d+$/.test(charId)) {
            this.showAlert('Invalid character ID. Please enter a numeric ID or a valid D&D Beyond URL.', 'error');
            return;
        }
        
        // Close modal first
        document.querySelector('[style*="z-index: 1100"]')?.remove();
        
        try {
            this.showLoading('Importing character from D&D Beyond...');
            
            const response = await this.apiRequest('/api/characters/import/dndbeyond', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    dndbeyond_id: charId,
                    campaign_id: this.currentCampaign?.campaign_id || null
                })
            });
            
            // Add the imported character to our list
            this.characters.push({
                ...response,
                isLive: false
            });
            
            // Refresh the character display
            if (this.partyPanelOpen) {
                this.renderCharacters();
            }
            
            this.showAlert(`Successfully imported ${response.name}!`, 'success');
            
        } catch (error) {
            console.error('Failed to import character:', error);
            this.showAlert(error.message || 'Failed to import character. Make sure the character is public on D&D Beyond.', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    showPDFUploadForm() {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 1100; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card" style="max-width: 450px; width: 100%;" onclick="event.stopPropagation()">
                    <h3>Upload Character PDF</h3>
                    <p style="margin-bottom: 20px; color: var(--text-muted);">Select a PDF character sheet to upload:</p>
                    
                    <div class="form-group">
                        <input type="file" id="pdf-upload-input" class="form-input" accept=".pdf"
                               style="padding: 10px;">
                    </div>
                    
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Cancel</button>
                        <button class="btn" onclick="app.uploadPDF()">Upload & Extract</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    async uploadPDF(charIdToUpdate = null) {
        const input = document.getElementById('pdf-upload-input');
        const file = input?.files?.[0];
        
        if (!file) {
            this.showAlert('Please select a PDF file', 'error');
            return;
        }
        
        document.querySelector('[style*="z-index: 1100"]')?.remove();
        
        try {
            this.showLoading(charIdToUpdate ? 'Updating character from PDF...' : 'Importing character from PDF...');
            
            const formData = new FormData();
            formData.append('pdf_file', file);
            if (this.currentCampaign?.campaign_id) {
                formData.append('campaign_id', this.currentCampaign.campaign_id);
            }
            
            let url = '/api/characters/import/pdf';
            if (charIdToUpdate) {
                url = `/api/characters/${charIdToUpdate}/update-pdf`;
            }
            
            const response = await fetch(url, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    if (errorData.error) {
                        errorMessage = errorData.error;
                    }
                } catch (e) {}
                throw new Error(errorMessage);
            }
            
            const character = await response.json();
            
            if (charIdToUpdate) {
                const index = this.characters.findIndex(c => c.id === charIdToUpdate);
                if (index !== -1) {
                    const wasLive = this.characters[index].isLive;
                    this.characters[index] = { ...character, isLive: wasLive };
                }
            } else {
                this.characters.push({
                    ...character,
                    isLive: false
                });
            }
            
            if (this.partyPanelOpen) {
                this.renderCharacters();
            }
            this.updateLivePartyDisplay();
            
            this.showAlert(`Successfully ${charIdToUpdate ? 'updated' : 'imported'} ${character.name}!`, 'success');
            
        } catch (error) {
            console.error('Failed to upload PDF:', error);
            this.showAlert(error.message || 'Failed to process PDF file.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    // API Methods
    async apiRequest(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                // Try to get the error message from the response body
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    if (errorData.error) {
                        errorMessage = errorData.error;
                    }
                } catch (e) {
                    // Response wasn't JSON, use default message
                }
                throw new Error(errorMessage);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    async loadWorlds() {
        try {
            const data = await this.apiRequest('/api/worlds');
            this.worlds = data.worlds;
            this.populateWorldSelect();
            this.populateWorldPreview();
        } catch (error) {
            console.error('Failed to load worlds:', error);
        }
    }

    async refreshCampaigns() {
        try {
            const data = await this.apiRequest('/api/campaigns');
            this.campaigns = [];
            
            // Load full campaign details for each ID
            for (const campaignId of data.campaign_ids) {
                try {
                    const campaign = await this.apiRequest(`/api/campaigns/${campaignId}`);
                    this.campaigns.push(campaign);
                } catch (error) {
                    console.error(`Failed to load campaign ${campaignId}:`, error);
                }
            }
            
            this.renderCampaigns();
        } catch (error) {
            console.error('Failed to refresh campaigns:', error);
        }
    }

    async refreshSessions() {
        if (!this.currentCampaign) return;
        
        try {
            const data = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions`);
            this.sessions = [];
            
            // Load full session details for each ID
            for (const sessionId of data.session_ids) {
                try {
                    const session = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${sessionId}`);
                    this.sessions.push(session);
                } catch (error) {
                    console.error(`Failed to load session ${sessionId}:`, error);
                }
            }
            
            this.renderSessions();
        } catch (error) {
            console.error('Failed to refresh sessions:', error);
        }
    }

    // UI Methods
    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                this.showTab(tabName);
            });
        });

        // Campaign creation form
        const createForm = document.getElementById('create-campaign-form');
        if (createForm) {
            createForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.createCampaign();
            });
        }

        // Chat form
        const chatForm = document.getElementById('chat-form');
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }

        // Chat input: Enter to send, Shift+Enter for newline, auto-expand
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-expand textarea as user types
            chatInput.addEventListener('input', () => {
                this.autoExpandTextarea(chatInput);
            });
        }
        
        // Party panel button
        const partyButton = document.getElementById('party-button');
        if (partyButton) {
            partyButton.addEventListener('click', () => this.togglePartyPanel());
        }
        
        // Party overlay click to close
        const partyOverlay = document.getElementById('party-overlay');
        if (partyOverlay) {
            partyOverlay.addEventListener('click', () => this.togglePartyPanel());
        }
        
        // Action mode buttons
        document.querySelectorAll('.action-mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.currentTarget.dataset.mode;
                this.setActionMode(mode);
            });
        });
        
        // Character selector for character mode
        const characterSelect = document.getElementById('action-character-select');
        if (characterSelect) {
            characterSelect.addEventListener('change', (e) => {
                this.actionCharacterId = e.target.value || null;
            });
        }
    }

    showTab(tabName) {
        this.currentTab = tabName;
        
        // Update tab buttons
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        // Load data for specific tabs
        if (tabName === 'campaigns') {
            this.refreshCampaigns();
        } else if (tabName === 'sessions' && this.currentCampaign) {
            this.refreshSessions();
        }
    }

    populateWorldSelect() {
        const select = document.getElementById('world-select');
        if (!select) return;
        
        select.innerHTML = '<option value="">Choose a world...</option>';
        
        Object.keys(this.worlds).forEach(worldName => {
            const option = document.createElement('option');
            option.value = worldName;
            option.textContent = worldName;
            select.appendChild(option);
        });
    }

    populateWorldPreview() {
        const select = document.getElementById('world-preview-select');
        if (!select) return;
        
        select.innerHTML = '<option value="">Select a world to preview...</option>';
        
        Object.keys(this.worlds).forEach(worldName => {
            const option = document.createElement('option');
            option.value = worldName;
            option.textContent = worldName;
            select.appendChild(option);
        });

        // Add event listener for world selection changes
        select.addEventListener('change', (e) => this.onWorldPreviewChange(e.target.value));
    }

    onWorldPreviewChange(worldName) {
        const panel = document.getElementById('world-description-panel');
        if (!panel) return;
        
        if (!worldName) {
            panel.innerHTML = '<p class="world-preview-empty">Select a world above to see its description</p>';
            return;
        }

        // Get world data from loaded worlds (now includes descriptions and features from API)
        const world = this.worlds[worldName];
        if (world && world.description) {
            panel.innerHTML = `
                <div class="world-preview-content">
                    <h4 class="world-preview-title">${worldName}</h4>
                    <p class="world-preview-description">${world.description}</p>
                    <div class="world-preview-features">
                        <strong>Key Features:</strong>
                        <ul>
                            ${world.features ? world.features.map(feature => `<li>${feature}</li>`).join('') : '<li>No features available</li>'}
                        </ul>
                    </div>
                </div>
            `;
        } else {
            panel.innerHTML = '<p class="world-preview-empty">World description not available</p>';
        }
    }

    renderCampaigns() {
        const container = document.getElementById('campaigns-list');
        if (!container) return;
        
        if (this.campaigns.length === 0) {
            container.innerHTML = `
                <div class="text-center mt-20">
                    <p>No campaigns created yet. Create your first campaign to get started!</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.campaigns.map(campaign => {
            const createdDate = campaign.creation_time || campaign.created_at;
            const lastPlayed = campaign.last_played ? 
                `<p><strong>Last Played:</strong> ${new Date(campaign.last_played).toLocaleDateString()}</p>` : 
                '<p><strong>Last Played:</strong> Never</p>';
            
            // Get session count for this campaign
            const sessionCount = campaign.session_count || 0;
            const sessionText = sessionCount === 0 ? 'No sessions yet' : 
                               sessionCount === 1 ? '1 session' : 
                               `${sessionCount} sessions`;
            
            // Truncate text fields with specified character limits
            const campaignName = campaign.campaign_name || campaign.name || 'Untitled Campaign';
            const truncatedName = campaignName.length > 40 ? campaignName.substring(0, 40) + '...' : campaignName;
            
            const world = campaign.world_collection || '';
            const truncatedWorld = world.length > 15 ? world.substring(0, 15) + '...' : world;
            
            const description = campaign.user_description || campaign.description || 'No description';
            const truncatedDescription = description.length > 60 ? description.substring(0, 60) + '...' : description;
            
            return `
                <div class="card">
                    <h3>${truncatedName}</h3>
                    <div class="campaign-info-compact">
                        <div class="campaign-info-row">
                            <b>WORLD:</b> ${truncatedWorld} &nbsp;&nbsp;&nbsp; <b>DESCRIPTION:</b> ${truncatedDescription}
                        </div>
                        <div class="campaign-info-row">
                            <b>CREATED:</b> ${new Date(createdDate).toLocaleDateString()} &nbsp;&nbsp;&nbsp; <b>LAST PLAYED:</b> ${campaign.last_played ? new Date(campaign.last_played).toLocaleDateString() : 'Never'} &nbsp;&nbsp;&nbsp; <b>SESSIONS:</b> ${sessionText}
                        </div>
                    </div>
                    <div class="campaign-actions">
                        <button class="btn" onclick="app.selectCampaign('${campaign.campaign_id}')">
                            Manage Sessions
                        </button>
                        <button class="btn btn-secondary" onclick="app.viewCampaign('${campaign.campaign_id}')">
                            View Details (DM only)
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Helper methods for session numbering
    sessionTimestamp(session) {
        if (session.created_at) {
            return new Date(session.created_at).getTime();
        }
        // Fallback: parse numeric portion of session_id
        const match = session.session_id.match(/\d+/);
        return match ? parseInt(match[0]) : 0;
    }

    computeSessionNumberMap() {
        // Sort sessions by creation time (oldest first) and assign sequential numbers
        const sortedSessions = [...this.sessions].sort((a, b) => 
            this.sessionTimestamp(a) - this.sessionTimestamp(b)
        );
        
        const numberMap = new Map();
        sortedSessions.forEach((session, index) => {
            numberMap.set(session.session_id, index + 1);
        });
        
        return numberMap;
    }

    // ============ UNIFIED JSON-TO-MARKDOWN RENDERER ============
    
    /**
     * Unified JSON-to-Markdown renderer that can handle any JSON structure
     * @param {any} value - The value to render
     * @param {Object} options - Rendering options
     * @param {Array} path - Current path in the JSON structure
     * @returns {string} Markdown string
     */
    renderJSONToMarkdown(value, options = {}, path = []) {
        const defaults = {
            maxDepth: 4,
            arrayItemLimit: 20,
            headingBaseLevel: 1,
            showCounts: true,
            linkify: true,
            rawFenceLanguage: 'json'
        };
        const opts = { ...defaults, ...options };
        const currentDepth = path.length;
        
        // If we've exceeded max depth, show raw JSON
        if (currentDepth >= opts.maxDepth) {
            return this.renderRawJSON(value, opts.rawFenceLanguage);
        }
        
        if (value === null) return '*(null)*';
        if (value === undefined) return '*(undefined)*';
        
        const type = Array.isArray(value) ? 'array' : typeof value;
        
        switch (type) {
            case 'object':
                return this.renderObjectToMarkdown(value, opts, path);
            case 'array':
                return this.renderArrayToMarkdown(value, opts, path);
            case 'string':
                return this.renderStringToMarkdown(value, opts);
            case 'number':
            case 'boolean':
                return `${value}`;
            default:
                return this.escapeMarkdown(String(value));
        }
    }
    
    /**
     * Render object to markdown
     */
    renderObjectToMarkdown(obj, opts, path) {
        if (!obj || Object.keys(obj).length === 0) {
            return '*(empty object)*\n\n';
        }
        
        let markdown = '';
        const currentDepth = path.length;
        
        Object.keys(obj).forEach(key => {
            const value = obj[key];
            const keyPath = [...path, key];
            const headingLevel = Math.min(opts.headingBaseLevel + currentDepth, 6);
            const heading = '#'.repeat(headingLevel);
            const displayKey = this.formatKeyName(key);
            
            if (typeof value === 'object' && value !== null) {
                // Complex value - create a section
                markdown += `${heading} ${displayKey}\n\n`;
                markdown += this.renderJSONToMarkdown(value, opts, keyPath);
                markdown += '\n';
            } else {
                // Simple value - show as key-value pair
                const renderedValue = this.renderJSONToMarkdown(value, opts, keyPath);
                markdown += `**${displayKey}:** ${renderedValue}\n\n`;
            }
        });
        
        return markdown;
    }
    
    /**
     * Render array to markdown
     */
    renderArrayToMarkdown(arr, opts, path) {
        if (!arr || arr.length === 0) {
            return '*(empty array)*\n\n';
        }
        
        let markdown = '';
        const currentDepth = path.length;
        const showCount = opts.showCounts && arr.length > opts.arrayItemLimit;
        
        // Check if array contains homogeneous objects
        const isObjectArray = arr.every(item => typeof item === 'object' && item !== null && !Array.isArray(item));
        const isSimpleArray = arr.every(item => typeof item !== 'object' || item === null);
        
        if (isSimpleArray) {
            // Simple array - render as bullet list
            const itemsToShow = arr.slice(0, opts.arrayItemLimit);
            itemsToShow.forEach(item => {
                const renderedItem = this.renderJSONToMarkdown(item, opts, [...path, 'item']);
                markdown += `- ${renderedItem}\n`;
            });
            
            if (showCount) {
                const remaining = arr.length - opts.arrayItemLimit;
                const expandId = 'expand_' + Math.random().toString(36).substr(2, 9);
                markdown += `- **[Show ${remaining} more items...]** {data-expand="${expandId}" data-items="${this.encodeForAttribute(JSON.stringify(arr.slice(opts.arrayItemLimit)))}" data-opts="${this.encodeForAttribute(JSON.stringify(opts))}" data-path="${this.encodeForAttribute(JSON.stringify([...path, 'remaining']))}"}\n`;
                markdown += `\n{expand-placeholder-${expandId}}\n`;
            }
            markdown += '\n';
        } else if (isObjectArray) {
            // Object array - render each with index
            const itemsToShow = arr.slice(0, opts.arrayItemLimit);
            itemsToShow.forEach((item, index) => {
                const itemPath = [...path, index];
                const headingLevel = Math.min(opts.headingBaseLevel + currentDepth + 1, 6);
                const heading = '#'.repeat(headingLevel);
                
                // Try to find a good title for the item
                const title = this.getItemTitle(item, index);
                markdown += `${heading} ${title}\n\n`;
                markdown += this.renderJSONToMarkdown(item, opts, itemPath);
                markdown += '\n';
            });
            
            if (showCount) {
                const remaining = arr.length - opts.arrayItemLimit;
                const expandId = 'expand_' + Math.random().toString(36).substr(2, 9);
                markdown += `**[Show ${remaining} more items...]** {data-expand="${expandId}" data-items="${this.encodeForAttribute(JSON.stringify(arr.slice(opts.arrayItemLimit)))}" data-opts="${this.encodeForAttribute(JSON.stringify(opts))}" data-path="${this.encodeForAttribute(JSON.stringify([...path, 'remaining']))}"}\n\n`;
                markdown += `{expand-placeholder-${expandId}}\n\n`;
            }
        } else {
            // Mixed array - render each item separately
            const itemsToShow = arr.slice(0, opts.arrayItemLimit);
            itemsToShow.forEach((item, index) => {
                const itemPath = [...path, index];
                markdown += `**Item ${index + 1}:** ${this.renderJSONToMarkdown(item, opts, itemPath)}\n\n`;
            });
            
            if (showCount) {
                const remaining = arr.length - opts.arrayItemLimit;
                const expandId = 'expand_' + Math.random().toString(36).substr(2, 9);
                markdown += `**[Show ${remaining} more items...]** {data-expand="${expandId}" data-items="${this.encodeForAttribute(JSON.stringify(arr.slice(opts.arrayItemLimit)))}" data-opts="${this.encodeForAttribute(JSON.stringify(opts))}" data-path="${this.encodeForAttribute(JSON.stringify([...path, 'remaining']))}"}\n\n`;
                markdown += `{expand-placeholder-${expandId}}\n\n`;
            }
        }
        
        return markdown;
    }
    
    /**
     * Render string with smart formatting
     */
    renderStringToMarkdown(str, opts) {
        if (!str) return '*(empty)*';
        
        // Escape the string for markdown safety
        let escaped = this.escapeMarkdown(str);
        
        // Optionally linkify URLs
        if (opts.linkify) {
            escaped = this.linkifyText(escaped);
        }
        
        // Preserve line breaks
        escaped = escaped.replace(/\n/g, '  \n');
        
        return escaped;
    }
    
    /**
     * Render raw JSON when depth limit exceeded
     */
    renderRawJSON(value, language = 'json') {
        try {
            const jsonString = JSON.stringify(value, null, 2);
            return `\`\`\`${language}\n${jsonString}\n\`\`\`\n\n`;
        } catch (e) {
            return `\`\`\`\n${String(value)}\n\`\`\`\n\n`;
        }
    }
    
    /**
     * Helper functions for the renderer
     */
    formatKeyName(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    getItemTitle(item, index) {
        if (typeof item !== 'object' || item === null) {
            return `Item ${index + 1}`;
        }
        
        // Try common title fields
        const titleFields = ['name', 'title', 'label', 'id'];
        for (const field of titleFields) {
            if (item[field] && typeof item[field] === 'string') {
                return this.escapeMarkdown(item[field]);
            }
        }
        
        return `Item ${index + 1}`;
    }
    
    escapeMarkdown(text) {
        if (typeof text !== 'string') return text;
        return text
            .replace(/\\/g, '\\\\')
            .replace(/\*/g, '\\*')
            .replace(/_/g, '\\_')
            .replace(/\[/g, '\\[')
            .replace(/\]/g, '\\]')
            .replace(/\(/g, '\\(')
            .replace(/\)/g, '\\)')
            .replace(/~/g, '\\~')
            .replace(/`/g, '\\`')
            .replace(/>/g, '\\>')
            .replace(/#/g, '\\#')
            .replace(/\+/g, '\\+')
            .replace(/-/g, '\\-')
            .replace(/\./g, '\\.')
            .replace(/!/g, '\\!')
            .replace(/\|/g, '\\|');
    }
    
    linkifyText(text) {
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.replace(urlRegex, '[$1]($1)');
    }
    
    /**
     * Extract structured data from various formats
     */
    extractStructuredData(input) {
        if (!input) return null;
        
        // If already an object, return it
        if (typeof input === 'object' && input !== null) {
            return input;
        }
        
        if (typeof input !== 'string') return null;
        
        // Try direct JSON parse
        try {
            return JSON.parse(input);
        } catch (e) {
            // Continue to other methods
        }
        
        // Try RunResult format extraction
        const runResultData = this.extractJSONFromRunResult(input);
        if (runResultData) return runResultData;
        
        // Try to find JSON in fenced code blocks
        const fencedMatch = input.match(/```(?:json)?\s*\n([\s\S]*?)\n```/i);
        if (fencedMatch) {
            try {
                return JSON.parse(fencedMatch[1]);
            } catch (e) {
                // Continue
            }
        }
        
        return null;
    }
    
    /**
     * Safe markdown to HTML conversion with proper sanitization
     */
    safeMarkdownToHTML(markdown) {
        try {
            // Configure marked with safe options
            const renderer = new marked.Renderer();
            
            // Override dangerous features
            renderer.html = () => '';  // Block raw HTML
            renderer.link = (href, title, text) => {
                // Sanitize links
                if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
                    return `<a href="${this.escapeHTML(href)}" title="${this.escapeHTML(title || '')}" target="_blank" rel="noopener noreferrer">${text}</a>`;
                }
                return text;
            };
            
            // Convert markdown to HTML with safe renderer
            let htmlContent = marked.parse(markdown, { renderer });
            
            // Additional safety layer - allowlist approach
            htmlContent = this.sanitizeHTML(htmlContent);
            
            return htmlContent;
        } catch (e) {
            console.warn('Failed to parse markdown:', e);
            return `<pre>${this.escapeHTML(markdown)}</pre>`;
        }
    }
    
    /**
     * Sanitize HTML using allowlist approach
     */
    sanitizeHTML(html) {
        // Create a temporary DOM for parsing
        const temp = document.createElement('div');
        temp.innerHTML = html;
        
        // Allowlisted tags and attributes
        const allowedTags = ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote', 'details', 'summary', 'button', 'div'];
        const allowedAttrs = ['href', 'title', 'class', 'id', 'onclick', 'target', 'rel'];
        
        this.sanitizeElement(temp, allowedTags, allowedAttrs);
        return temp.innerHTML;
    }
    
    /**
     * Recursively sanitize DOM elements
     */
    sanitizeElement(element, allowedTags, allowedAttrs) {
        const children = Array.from(element.children);
        
        children.forEach(child => {
            if (!allowedTags.includes(child.tagName.toLowerCase())) {
                // Replace with text content
                const textNode = document.createTextNode(child.textContent);
                child.parentNode.replaceChild(textNode, child);
            } else {
                // Clean attributes
                const attrs = Array.from(child.attributes);
                attrs.forEach(attr => {
                    if (!allowedAttrs.includes(attr.name.toLowerCase())) {
                        child.removeAttribute(attr.name);
                    }
                });
                
                // Recursively clean children
                this.sanitizeElement(child, allowedTags, allowedAttrs);
            }
        });
    }
    
    /**
     * Encode data for safe attribute embedding
     */
    encodeForAttribute(data) {
        return btoa(encodeURIComponent(data));
    }
    
    /**
     * Decode data from attribute
     */
    decodeFromAttribute(encoded) {
        return decodeURIComponent(atob(encoded));
    }
    
    /**
     * Process show-more placeholders after safe HTML rendering
     */
    processShowMorePlaceholders(container) {
        // Find all show-more triggers and placeholders
        const triggers = container.querySelectorAll('strong');
        
        triggers.forEach(trigger => {
            const text = trigger.textContent;
            if (text.includes('[Show') && text.includes('more items...]')) {
                // Extract data attributes from parent element text
                const parentText = trigger.parentElement.textContent;
                const match = parentText.match(/\{data-expand="([^"]+)" data-items="([^"]+)" data-opts="([^"]+)" data-path="([^"]+)"\}/);
                if (match) {
                    const [, expandId, encodedItems, encodedOpts, encodedPath] = match;
                    
                    // Create button element
                    const button = document.createElement('button');
                    button.className = 'show-more-btn';
                    button.textContent = text.replace(/^\[|\]$/g, '');
                    button.setAttribute('data-expand-id', expandId);
                    button.setAttribute('data-items', encodedItems);
                    button.setAttribute('data-opts', encodedOpts);
                    button.setAttribute('data-path', encodedPath);
                    
                    // Create placeholder div
                    const placeholder = document.createElement('div');
                    placeholder.id = expandId;
                    placeholder.className = 'hidden-content';
                    
                    // Replace the trigger text with button
                    trigger.parentElement.replaceChild(button, trigger);
                    
                    // Find and replace placeholder text using TreeWalker
                    const walker = document.createTreeWalker(
                        container,
                        NodeFilter.SHOW_TEXT,
                        {
                            acceptNode: function(node) {
                                return node.textContent.includes(`{expand-placeholder-${expandId}}`) ? 
                                    NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                            }
                        }
                    );
                    
                    let node;
                    while (node = walker.nextNode()) {
                        if (node.textContent.includes(`{expand-placeholder-${expandId}}`)) {
                            node.parentNode.replaceChild(placeholder, node);
                            break;
                        }
                    }
                    
                    // Fallback: insert after button if placeholder not found
                    if (!placeholder.parentNode) {
                        button.parentNode.insertBefore(placeholder, button.nextSibling);
                    }
                }
            }
        });
        
        // Add event delegation for show-more buttons
        container.addEventListener('click', (e) => {
            if (e.target.classList.contains('show-more-btn')) {
                this.handleShowMoreClick(e.target);
            }
        });
    }
    
    /**
     * Handle show-more button clicks
     */
    handleShowMoreClick(button) {
        const expandId = button.getAttribute('data-expand-id');
        const encodedItems = button.getAttribute('data-items');
        const encodedOpts = button.getAttribute('data-opts');
        const encodedPath = button.getAttribute('data-path');
        
        try {
            const items = JSON.parse(this.decodeFromAttribute(encodedItems));
            const options = JSON.parse(this.decodeFromAttribute(encodedOpts));
            const path = JSON.parse(this.decodeFromAttribute(encodedPath));
            
            this.expandArraySection(expandId, items, options, path);
            button.style.display = 'none';
        } catch (e) {
            console.error('Failed to expand section:', e);
            button.textContent = 'Error loading items';
            button.disabled = true;
        }
    }
    
    /**
     * Expand array section for "show more" functionality (updated)
     */
    expandArraySection(expandId, remainingItems, opts, path) {
        const container = document.getElementById(expandId);
        if (!container) return;
        
        try {
            let markdown = '';
            remainingItems.forEach((item, index) => {
                const actualIndex = opts.arrayItemLimit + index;
                if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
                    const title = this.getItemTitle(item, actualIndex);
                    markdown += `### ${title}\n\n`;
                    markdown += this.renderJSONToMarkdown(item, opts, [...path, actualIndex]);
                } else {
                    markdown += `- ${this.renderJSONToMarkdown(item, opts, [...path, actualIndex])}\n`;
                }
            });
            
            const htmlContent = this.safeMarkdownToHTML(markdown);
            container.innerHTML = htmlContent;
            container.style.display = 'block';
        } catch (e) {
            console.error('Failed to expand array section:', e);
            container.innerHTML = '<p><em>Error loading additional items</em></p>';
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHTML(text) {
        if (typeof text !== 'string') return text;
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    renderSessions() {
        const container = document.getElementById('sessions-list');
        const buttonContainer = document.getElementById('session-button-container');
        const campaignInfo = document.getElementById('current-campaign-info');
        
        if (!container || !this.currentCampaign) return;
        
        // Update campaign info
        if (campaignInfo) {
            // Character limits matching Campaign Builder format (manual truncation like Campaign Builder)
            const campaignName = this.currentCampaign.campaign_name || 'Untitled Campaign';
            const worldName = this.currentCampaign.world_collection || 'Unknown';
            const description = this.currentCampaign.user_description || 'No description';
            
            const truncatedName = campaignName.length > 40 ? campaignName.slice(0, 40) + '...' : campaignName;
            const truncatedWorld = worldName.length > 15 ? worldName.slice(0, 15) + '...' : worldName;
            const truncatedDescription = description.length > 60 ? description.slice(0, 60) + '...' : description;
            
            // Get session count for this campaign
            const sessionCount = this.sessions.length || 0;
            const sessionText = sessionCount === 0 ? 'No sessions yet' : 
                               sessionCount === 1 ? '1 session' : 
                               `${sessionCount} sessions`;
            
            // Format dates
            const createdDate = this.currentCampaign.creation_time || this.currentCampaign.created_at;
            const lastPlayed = this.currentCampaign.last_played ? 
                new Date(this.currentCampaign.last_played).toLocaleDateString() : 'Never';
            
            campaignInfo.innerHTML = `
                <h3>${truncatedName}</h3>
                <div class="campaign-info-compact">
                    <div class="campaign-info-row">
                        <b>WORLD:</b> ${truncatedWorld} &nbsp;&nbsp;&nbsp; <b>DESCRIPTION:</b> ${truncatedDescription}
                    </div>
                    <div class="campaign-info-row">
                        <b>CREATED:</b> ${new Date(createdDate).toLocaleDateString()} &nbsp;&nbsp;&nbsp; <b>LAST PLAYED:</b> ${lastPlayed} &nbsp;&nbsp;&nbsp; <b>SESSIONS:</b> ${sessionText}
                    </div>
                </div>
            `;
        }

        // Handle button rendering in the separate container above "Game Sessions" header
        if (buttonContainer) {
            if (this.sessions.length === 0) {
                buttonContainer.innerHTML = `<button class="btn" onclick="app.createSession()">Create First Session</button>`;
            } else {
                // Check if there's an active (open) session
                const hasActiveSession = this.sessions.some(session => session.status === 'open');
                buttonContainer.innerHTML = !hasActiveSession ? 
                    `<button class="btn" onclick="app.createSession()">Create New Session</button>` : '';
            }
        }

        if (this.sessions.length === 0) {
            container.innerHTML = `
                <div class="text-center mt-20">
                    <p>No sessions created yet for this campaign.</p>
                </div>
            `;
            return;
        }

        // Compute session numbering map based on creation order
        const sessionNumberMap = this.computeSessionNumberMap();

        const sessionsHTML = this.sessions.map((session) => {
            const statusClass = session.status === 'open' ? 'status-active' : 'status-complete';
            const statusText = session.status === 'open' ? 'Active' : 'Complete';
            
            // Session numbering: sequential based on creation order (oldest = 1, newest = highest)
            const sessionNumber = sessionNumberMap.get(session.session_id);
            
            // Format dates and message count
            const createdDate = session.created_at ? new Date(session.created_at).toLocaleDateString() : 'Unknown';
            const lastPlayed = session.last_activity ? new Date(session.last_activity).toLocaleDateString() : 'Never';
            const messageCount = session.turn_count || 0;
            const messageText = messageCount === 0 ? 'No messages yet' : 
                               messageCount === 1 ? '1 message' : 
                               `${messageCount} messages`;
            
            return `
                <div class="card">
                    <h3>Session ${sessionNumber}</h3>
                    <div class="campaign-info-compact">
                        <div class="campaign-info-row">
                            <b>STATUS:</b> <span class="status-badge ${statusClass}">${statusText}</span> &nbsp;&nbsp;&nbsp; <b>MESSAGES:</b> ${messageText}
                        </div>
                        <div class="campaign-info-row">
                            <b>CREATED:</b> ${createdDate} &nbsp;&nbsp;&nbsp; <b>LAST PLAYED:</b> ${lastPlayed}
                        </div>
                    </div>
                    <div class="campaign-actions">
                        ${session.status === 'open' ? 
                            `<button class="btn" onclick="app.playSession('${session.session_id}')">Continue</button>` :
                            `<button class="btn btn-secondary" onclick="app.playSession('${session.session_id}')">Recap</button>`
                        }
                        ${session.status === 'open' ? 
                            `<button class="btn btn-warning" onclick="app.closeSession('${session.session_id}')">Close Session</button>` :
                            ''
                        }
                        <button class="btn btn-secondary" onclick="app.viewSession('${session.session_id}')">View Details (DM Only)</button>
                    </div>
                </div>
            `;
        }).join('');
        
        container.innerHTML = sessionsHTML;
    }

    // Campaign Management
    async createCampaign() {
        const form = document.getElementById('create-campaign-form');
        const formData = new FormData(form);
        
        const data = {
            name: formData.get('name'),
            description: formData.get('description'),
            world_collection: formData.get('world')
        };

        if (!data.world_collection) {
            this.showAlert('Please select a world', 'warning');
            return;
        }

        try {
            this.showLoading('Creating campaign... this can take a few minutes');
            await this.apiRequest('/api/campaigns', {
                method: 'POST',
                body: JSON.stringify(data)
            });
            
            this.showAlert('Campaign created successfully!', 'success');
            form.reset();
            await this.refreshCampaigns();
        } catch (error) {
            console.error('Failed to create campaign:', error);
        } finally {
            this.hideLoading();
        }
    }

    async selectCampaign(campaignId) {
        try {
            this.currentCampaign = await this.apiRequest(`/api/campaigns/${campaignId}`);
            this.showTab('sessions');
        } catch (error) {
            console.error('Failed to select campaign:', error);
        }
    }

    async viewCampaign(campaignId) {
        try {
            const campaign = await this.apiRequest(`/api/campaigns/${campaignId}`);
            this.showCampaignModal(campaign);
        } catch (error) {
            console.error('Failed to load campaign details:', error);
        }
    }

    // Session Management
    async createSession() {
        if (!this.currentCampaign) return;
        
        try {
            this.showLoading('Creating session... this can take a few minutes');
            await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions`, {
                method: 'POST'
            });
            
            this.showAlert('Session created successfully!', 'success');
            await this.refreshSessions();
        } catch (error) {
            console.error('Failed to create session:', error);
        } finally {
            this.hideLoading();
        }
    }

    async playSession(sessionId) {
        try {
            this.currentSession = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${sessionId}`);
            
            // Clear character selections when loading a new session
            this.characters.forEach(c => c.isLive = false);
            this.updateLivePartyDisplay();
            if (this.partyPanelOpen) {
                this.renderCharacters();
            }
            
            // Update last_played timestamp
            try {
                await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/last_played`, {
                    method: 'PUT'
                });
            } catch (error) {
                console.warn('Failed to update last played timestamp:', error);
            }
            
            this.showTab('play');
            this.initializeChat();
        } catch (error) {
            console.error('Failed to load session:', error);
        }
    }

    async viewSession(sessionId) {
        try {
            const session = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${sessionId}`);
            this.showSessionModal(session);
        } catch (error) {
            console.error('Failed to load session details:', error);
            this.showAlert('Failed to load session details', 'error');
        }
    }

    convertSessionToMarkdown(session) {
        if (!session) {
            return '# Session Details\n\nNo session data available.';
        }

        // Create a highlights section for key information
        let highlights = '# Session Highlights\n\n';
        highlights += `**Turn Count:** ${session.turn_count || 0}\n\n`;
        highlights += `**Status:** ${session.status || 'Unknown'}\n\n`;
        highlights += `**Last Activity:** ${session.last_activity ? new Date(session.last_activity).toLocaleString() : 'Never'}\n\n`;
        
        if (session.summary) {
            highlights += `**Summary:** ${this.escapeMarkdown(session.summary)}\n\n`;
        }

        // Use unified renderer for complete data
        const completeData = '# Complete Session Data\n\n' + this.renderJSONToMarkdown(session, {
            maxDepth: 4,
            arrayItemLimit: 10,
            headingBaseLevel: 2
        });

        return highlights + '\n' + completeData;
    }

    showSessionModal(session) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card campaign-modal" onclick="event.stopPropagation()">
                    <h3>📜 Session Details (DM Only)</h3>
                    
                    <div class="campaign-metadata">
                        <h4>Session ${this.computeSessionNumberMap().get(session.session_id) || 0}</h4>
                        <p><strong>Campaign:</strong> ${this.currentCampaign.campaign_name || 'Untitled Campaign'}</p>
                        <p><strong>Created:</strong> ${new Date(session.created_at).toLocaleDateString()}</p>
                        <p><strong>Status:</strong> ${session.status || 'Unknown'}</p>
                    </div>
                    
                    <h4>📖 Session Plan & Details:</h4>
                    <div class="campaign-outline markdown-container">
                        ${this.formatSessionContent(session)}
                    </div>
                    
                    <div class="text-center mt-20">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Close</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    formatSessionContent(session) {
        // Convert session data to markdown using unified renderer
        const markdown = this.convertSessionToMarkdown(session);
        
        // Convert markdown to HTML using safe parser
        const htmlContent = this.safeMarkdownToHTML(markdown);
        
        // Make sections collapsible (except h1)
        const collapsibleContent = this.makeCollapsible(htmlContent);
        
        // Create container and process show-more placeholders
        const container = document.createElement('div');
        container.className = 'markdown-content';
        container.innerHTML = collapsibleContent;
        
        // Process placeholders for interactive functionality
        this.processShowMorePlaceholders(container);
        
        return container.outerHTML;
    }

    showThemedConfirm(message, onConfirm, onCancel = null) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; justify-content: center; align-items: center; padding: 20px;">
                <div class="card" style="max-width: 400px; text-align: center;" onclick="event.stopPropagation()">
                    <h3>⚠️ Confirm Action</h3>
                    <p style="margin: 20px 0; font-size: 1.1em;">${message}</p>
                    
                    <div style="display: flex; gap: 15px; justify-content: center; margin-top: 25px;">
                        <button class="btn btn-secondary">Cancel</button>
                        <button class="btn btn-danger">Confirm</button>
                    </div>
                </div>
            </div>
        `;
        
        // Add event listeners
        const buttons = modal.querySelectorAll('button');
        buttons[1].addEventListener('click', (e) => {
            modal.remove();
            onConfirm();
        });
        buttons[0].addEventListener('click', (e) => {
            modal.remove();
            if (onCancel) onCancel();
        });
        
        document.body.appendChild(modal);
    }

    async closeSession(sessionId) {
        this.showThemedConfirm(
            'Are you sure you want to close this session? It cannot be reopened.',
            async () => {
                this.showLoading('Generating post-session analysis... this can take a few minutes');
                try {
                    await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${sessionId}/close`, {
                        method: 'POST'
                    });
                    
                    this.hideLoading();
                    this.showAlert('Session closed successfully!', 'success');
                    await this.refreshSessions();
                } catch (error) {
                    this.hideLoading();
                    console.error('Failed to close session:', error);
                    this.showAlert('Failed to close session', 'error');
                }
            }
        );
    }

    // Chat/Play Interface
    initializeChat() {
        if (!this.currentSession || !this.currentCampaign) return;
        
        // Update play interface info
        const playInfo = document.getElementById('current-play-info');
        if (playInfo) {
            // Get campaign information
            const campaignName = this.currentCampaign.campaign_name || 'Untitled Campaign';
            const truncatedName = campaignName.length > 40 ? campaignName.slice(0, 40) + '...' : campaignName;
            
            // Get session information
            const sessionTitle = this.currentSession.session_plan?.session_title || 'Untitled Session';
            const truncatedSessionTitle = sessionTitle.length > 50 ? sessionTitle.slice(0, 50) + '...' : sessionTitle;
            
            const turnCount = this.currentSession.turn_count || 0;
            const isOpen = this.currentSession.status === 'open';
            let turnText;
            if (turnCount === 0) {
                turnText = 'No turns yet';
            } else if (turnCount === 1) {
                turnText = isOpen ? '1 turn before current session' : '1 turn';
            } else {
                turnText = isOpen ? `${turnCount} turns before current session` : `${turnCount} turns`;
            }
            
            const statusClass = isOpen ? 'status-active' : 'status-complete';
            const statusText = isOpen ? 'Active' : 'Complete';
            
            // Use same styling structure as Session Manager tab
            playInfo.innerHTML = `
                <h3>${truncatedName}</h3>
                <div class="campaign-info-compact">
                    <div class="campaign-info-row">
                        <b>SESSION:</b> ${truncatedSessionTitle} &nbsp;&nbsp;&nbsp; <b>TURNS:</b> ${turnText}
                    </div>
                    <div class="campaign-info-row">
                        <b>STATUS:</b> <span class="status-badge ${statusClass}">${statusText}</span>
                    </div>
                </div>
            `;
        }

        // Load chat history
        this.renderChatHistory();
        
        // Setup WebSocket connection
        this.connectWebSocket();
    }

    renderChatHistory() {
        const container = document.getElementById('chat-messages');
        if (!container || !this.currentSession) return;
        
        container.innerHTML = '';
        
        if (this.currentSession.chat_history && this.currentSession.chat_history.length > 0) {
            // Convert backend turn records to chat messages
            this.currentSession.chat_history.forEach(turn => {
                // Add user message
                if (turn.user_input) {
                    this.addChatMessage('user', turn.user_input);
                }
                // Add DM response with intent if available
                if (turn.dm_response) {
                    this.addChatMessage('dm', turn.dm_response, turn.intent_used);
                }
            });
        } else {
            // No chat history yet - display opening read-aloud from first beat
            const firstBeat = this.currentSession.session_plan?.beats?.[0];
            const readAloud = firstBeat?.read_aloud_open;
            if (readAloud) {
                this.addChatMessage('dm', readAloud);
            } else {
                this.addChatMessage('system', 'Welcome to your D&D session! What would you like to do?');
            }
        }
        
        this.scrollChatToBottom();
    }

    addChatMessage(role, content, intent = null) {
        const container = document.getElementById('chat-messages');
        if (!container) return;
        
        // Purge old "thinking" system messages only - preserve welcome/error messages
        if (role === 'system' && content.includes('Dungeon Master is considering')) {
            const existingThinkingMessages = Array.from(container.querySelectorAll('.chat-message.system'))
                .filter(msg => msg.textContent.includes('Dungeon Master is considering'));
            existingThinkingMessages.forEach(msg => msg.remove());
        }
        
        const messageDiv = document.createElement('div');
        let className = `chat-message ${role}`;
        
        // Add intent-specific styling for DM messages
        if (role === 'dm' && intent) {
            if (intent === 'npc_dialogue') {
                className += ' dm-npc';
            } else if (intent === 'qa_rules' || intent === 'qa_situation') {
                className += ' dm-meta';
            } else {
                className += ' dm-narrative';
            }
            
            // Add agent badge (with show-badges toggle class on container)
            const badge = document.createElement('span');
            badge.className = 'agent-badge';
            badge.textContent = this.getAgentLabel(intent);
            messageDiv.appendChild(badge);
        } else if (role === 'dm') {
            // Default to narrative styling for DM messages without intent
            className += ' dm-narrative';
        }
        
        // Apply the className to the element
        messageDiv.className = className;
        
        const textNode = document.createTextNode(content);
        messageDiv.appendChild(textNode);
        
        // Add play button for DM messages with speakable intents
        if (role === 'dm' && this.voiceClient && this.voiceClient.shouldSpeak(intent)) {
            const playBtn = document.createElement('button');
            playBtn.className = 'dm-play-btn';
            playBtn.title = 'Listen to DM';
            playBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
            playBtn.onclick = (e) => {
                e.stopPropagation();
                this.playDMMessage(content, intent, playBtn);
            };
            messageDiv.appendChild(playBtn);
        }
        
        container.appendChild(messageDiv);
        this.scrollChatToBottom();
    }
    
    playDMMessage(text, intent, button) {
        if (!this.voiceClient) return;
        
        const playIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
        const pauseIcon = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
        
        // If already playing, stop
        if (button.classList.contains('playing')) {
            this.voiceClient.stopPlayback();
            return;
        }
        
        // Stop any other playing audio and reset their buttons
        document.querySelectorAll('.dm-play-btn.playing').forEach(btn => {
            btn.classList.remove('playing');
            btn.innerHTML = playIcon;
        });
        this.voiceClient.stopPlayback();
        
        // Mark as playing
        button.classList.add('playing');
        button.innerHTML = pauseIcon;
        
        // Callback resets button when playback completes or stops
        const resetButton = () => {
            button.classList.remove('playing');
            button.innerHTML = playIcon;
        };
        
        this.voiceClient.speakDMResponse(text, intent, resetButton);
    }
    
    getAgentLabel(intent) {
        const labels = {
            'narrative_short': 'Narrative',
            'narrative_long': 'Narrative',
            'qa_situation': 'Situation',
            'qa_rules': 'Rules',
            'npc_dialogue': 'NPC',
            'combat_designer': 'Combat',
            'travel': 'Travel',
            'gameplay': 'Gameplay'
        };
        return labels[intent] || 'DM';
    }

    scrollChatToBottom() {
        const container = document.getElementById('chat-messages');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    connectWebSocket() {
        if (!this.currentSession || !this.currentCampaign) return;
        
        // Close existing connection
        if (this.websocket) {
            this.websocket.close();
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.currentCampaign.campaign_id}/${this.currentSession.session_id}`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'dm_response') {
                this.addChatMessage('dm', data.dm_response, data.intent_used);
                // Update session info
                if (data.turn_number) {
                    this.currentSession.turn_number = data.turn_number;
                }
            } else if (data.type === 'dm_thinking') {
                this.addChatMessage('system', data.message);
            } else if (data.type === 'error') {
                this.addChatMessage('system', 'Error: ' + data.message);
            }
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addChatMessage('system', 'Connection error occurred');
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
        };
    }

    sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input || !input.value.trim()) return;
        
        const message = input.value.trim();
        input.value = '';
        this.resetTextareaHeight();
        
        this._sendMessageInternal(message);
    }
    
    sendMessageFromVoice(text) {
        if (!text || !text.trim()) return;
        
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = '';
            this.resetTextareaHeight();
        }
        
        this._sendMessageInternal(text.trim());
    }
    
    _sendMessageInternal(message) {
        // Get action context (mode and optional character)
        const actionContext = this.getActionContext();
        
        // Add user message to chat
        this.addChatMessage('user', message);
        
        // Send via WebSocket if connected
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'play_turn',
                input: message,
                user_id: 'web_user',
                ...actionContext
            }));
        } else {
            // Fallback to REST API
            this.sendMessageREST(message, actionContext);
        }
    }

    async sendMessageREST(message, actionContext = null) {
        try {
            const payload = {
                input: message,
                user_id: 'web_user',
                ...(actionContext || this.getActionContext())
            };
            
            const result = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${this.currentSession.session_id}/turn`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            
            this.addChatMessage('dm', result.dm_response, result.intent_used);
            
            if (result.turn_number) {
                this.currentSession.turn_number = result.turn_number;
            }
        } catch (error) {
            this.addChatMessage('system', 'Failed to send message. Please try again.');
        }
    }

    autoExpandTextarea(textarea) {
        // Reset height to auto to get the correct scrollHeight
        textarea.style.height = 'auto';
        // Set height to scrollHeight, but cap at max-height (handled by CSS)
        const newHeight = Math.min(textarea.scrollHeight, 150);
        textarea.style.height = newHeight + 'px';
    }
    
    resetTextareaHeight() {
        const input = document.getElementById('chat-input');
        if (input) {
            input.style.height = 'auto';
        }
    }

    // UI Utilities
    showAlert(message, type = 'success') {
        // Remove existing alerts
        const existing = document.querySelector('.alert');
        if (existing) {
            existing.remove();
        }
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        
        const content = document.querySelector('.main-content');
        content.insertBefore(alert, content.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }

    showLoading(message = 'Loading...') {
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <span>${message}</span>
            </div>
        `;
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000;
            color: white;
            font-size: 1.2em;
        `;
        
        document.body.appendChild(overlay);
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    convertJSONToMarkdown(outlineData) {
        if (!outlineData || typeof outlineData !== 'object') {
            return '# Campaign Outline\n\nNo structured outline available.';
        }

        // Create highlights section for key campaign themes
        let highlights = '';
        
        // Handle core_themes as highlights (visible by default)
        if (outlineData.core_themes && Array.isArray(outlineData.core_themes)) {
            highlights += '# Campaign Themes\n\n';
            outlineData.core_themes.forEach(theme => {
                if (theme.label && theme.description) {
                    highlights += `**${this.escapeMarkdown(theme.label)}:** ${this.escapeMarkdown(theme.description)}\n\n`;
                }
            });
        }
        
        // Story overview from initial_draft
        if (outlineData.initial_draft && Array.isArray(outlineData.initial_draft)) {
            highlights += '## Story Overview\n\n';
            outlineData.initial_draft.forEach((paragraph, index) => {
                if (typeof paragraph === 'string') {
                    highlights += `${this.escapeMarkdown(paragraph)}\n\n`;
                }
            });
        }

        // Use unified renderer for complete data
        const completeData = '# Complete Campaign Data\n\n' + this.renderJSONToMarkdown(outlineData, {
            maxDepth: 4,
            arrayItemLimit: 15,
            headingBaseLevel: 2
        });

        return highlights + '\n' + completeData;
    }

    makeCollapsible(htmlContent) {
        // Create a temporary div to parse HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent;
        
        // Find all h2, h3, h4 headings (keep h1 visible)
        const headings = tempDiv.querySelectorAll('h2, h3, h4');
        
        headings.forEach(heading => {
            // Collect content until next heading of same or higher level
            const headingLevel = parseInt(heading.tagName.charAt(1));
            const content = [];
            let nextElement = heading.nextElementSibling;
            
            while (nextElement) {
                const nextLevel = nextElement.tagName.startsWith('H') ? parseInt(nextElement.tagName.charAt(1)) : null;
                if (nextLevel && nextLevel <= headingLevel) {
                    break;
                }
                content.push(nextElement);
                const temp = nextElement;
                nextElement = nextElement.nextElementSibling;
                temp.remove();
            }
            
            // Create collapsible structure
            const details = document.createElement('details');
            const summary = document.createElement('summary');
            summary.innerHTML = heading.innerHTML;
            summary.className = 'markdown-heading-summary';
            
            details.appendChild(summary);
            content.forEach(el => details.appendChild(el));
            
            // Replace heading with details
            heading.parentNode.replaceChild(details, heading);
        });
        
        return tempDiv.innerHTML;
    }

    extractJSONFromRunResult(runResultString) {
        if (!runResultString || typeof runResultString !== 'string') {
            return null;
        }
        
        // Look for the pattern "Final output (str):" followed by JSON
        const finalOutputMatch = runResultString.match(/Final output \(str\):\s*(\{[\s\S]*)/);
        if (!finalOutputMatch) {
            return null;
        }
        
        let jsonString = finalOutputMatch[1].trim();
        
        // The JSON might be incomplete due to truncation, so we need to find the actual end
        // Try to find the last complete JSON object
        let bracketCount = 0;
        let lastValidIndex = -1;
        
        for (let i = 0; i < jsonString.length; i++) {
            if (jsonString[i] === '{') {
                bracketCount++;
            } else if (jsonString[i] === '}') {
                bracketCount--;
                if (bracketCount === 0) {
                    lastValidIndex = i;
                    break;
                }
            }
        }
        
        if (lastValidIndex > -1) {
            jsonString = jsonString.substring(0, lastValidIndex + 1);
        }
        
        try {
            return JSON.parse(jsonString);
        } catch (e) {
            console.warn('Failed to parse extracted JSON:', e);
            return null;
        }
    }

    formatCampaignOutline(outline) {
        if (!outline) return '<p>No outline available</p>';
        
        let outlineData;
        
        // First, try to extract JSON from RunResult format
        if (typeof outline === 'string' && outline.includes('RunResult:')) {
            outlineData = this.extractJSONFromRunResult(outline);
        } else {
            // Try to parse as direct JSON
            try {
                outlineData = typeof outline === 'string' ? JSON.parse(outline) : outline;
            } catch (e) {
                outlineData = null;
            }
        }
        
        // If we couldn't extract structured data, display as markdown text
        if (!outlineData) {
            return `<div class="markdown-content">${marked.parse(outline || 'No outline available')}</div>`;
        }
        
        // Convert JSON to markdown using unified renderer
        const markdown = this.convertJSONToMarkdown(outlineData);
        
        // Convert markdown to HTML using safe parser
        const htmlContent = this.safeMarkdownToHTML(markdown);
        
        // Make sections collapsible (except h1)
        const collapsibleContent = this.makeCollapsible(htmlContent);
        
        // Create container and process show-more placeholders
        const container = document.createElement('div');
        container.className = 'markdown-content';
        container.innerHTML = collapsibleContent;
        
        // Process placeholders for interactive functionality
        this.processShowMorePlaceholders(container);
        
        return container.outerHTML;
    }

    showCampaignModal(campaign) {
        const createdDate = campaign.creation_time || campaign.created_at;
        const lastPlayed = campaign.last_played ? 
            `<p><strong>Last Played:</strong> ${new Date(campaign.last_played).toLocaleDateString()}</p>` : 
            '<p><strong>Last Played:</strong> Never</p>';
        
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; justify-content: center; align-items: center; padding: 20px;" onclick="this.remove()">
                <div class="card campaign-modal" onclick="event.stopPropagation()">
                    <h3>📜 Campaign Details (DM Only)</h3>
                    
                    <div class="campaign-metadata">
                        <h4>${campaign.campaign_name || campaign.name || 'Untitled Campaign'}</h4>
                        <p><strong>World:</strong> ${campaign.world_collection}</p>
                        <p><strong>Description:</strong> ${campaign.user_description || campaign.description || 'No description'}</p>
                        <p><strong>Created:</strong> ${new Date(createdDate).toLocaleDateString()}</p>
                        ${lastPlayed}
                    </div>
                    
                    <h4>📖 AI-Generated Campaign Outline:</h4>
                    <div class="campaign-outline markdown-container">
                        ${this.formatCampaignOutline(campaign.outline)}
                    </div>
                    
                    <div class="text-center mt-20">
                        <button class="btn btn-secondary" onclick="this.closest('[style*=fixed]').remove()">Close</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DnDApp();
});