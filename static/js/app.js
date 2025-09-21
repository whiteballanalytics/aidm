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
        
        this.init();
    }

    async init() {
        await this.loadWorlds();
        this.setupEventListeners();
        this.showTab('campaigns');
        await this.refreshCampaigns();
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
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            this.showAlert('Error: ' + error.message, 'error');
            throw error;
        }
    }

    async loadWorlds() {
        try {
            const data = await this.apiRequest('/api/worlds');
            this.worlds = data.worlds;
            this.populateWorldSelect();
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

        // Chat input enter key
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
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
            
            return `
                <div class="card">
                    <h3>${campaign.campaign_name || campaign.name || 'Untitled Campaign'}</h3>
                    <p><strong>World:</strong> ${campaign.world_collection}</p>
                    <p><strong>Description:</strong> ${campaign.user_description || campaign.description || 'No description'}</p>
                    <p><strong>Created:</strong> ${new Date(createdDate).toLocaleDateString()}</p>
                    ${lastPlayed}
                    <div class="item-actions">
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

    renderSessions() {
        const container = document.getElementById('sessions-list');
        const campaignInfo = document.getElementById('current-campaign-info');
        
        if (!container || !this.currentCampaign) return;
        
        // Update campaign info
        if (campaignInfo) {
            campaignInfo.innerHTML = `
                <h3>${this.currentCampaign.campaign_name || 'Untitled Campaign'}</h3>
                <p><strong>World:</strong> ${this.currentCampaign.world_collection}</p>
                <p><strong>Description:</strong> ${this.currentCampaign.user_description || 'No description'}</p>
            `;
        }

        if (this.sessions.length === 0) {
            container.innerHTML = `
                <div class="text-center mt-20">
                    <p>No sessions created yet for this campaign.</p>
                    <button class="btn" onclick="app.createSession()">Create First Session</button>
                </div>
            `;
            return;
        }

        container.innerHTML = this.sessions.map(session => {
            const statusClass = session.status === 'open' ? 'status-active' : 'status-complete';
            const statusText = session.status === 'open' ? 'Active' : 'Complete';
            
            return `
                <div class="card">
                    <div class="flex" style="justify-content: space-between; align-items: center;">
                        <div>
                            <h4>Session ${session.turn_number || 0}</h4>
                            <p><strong>Status:</strong> <span class="status-badge ${statusClass}">${statusText}</span></p>
                            <p><strong>Started:</strong> ${new Date(session.creation_time).toLocaleDateString()}</p>
                        </div>
                        <div class="item-actions">
                            ${session.status === 'open' ? 
                                `<button class="btn" onclick="app.playSession('${session.session_id}')">Continue</button>` :
                                `<button class="btn btn-secondary" onclick="app.viewSession('${session.session_id}')">View</button>`
                            }
                            ${session.status === 'open' ? 
                                `<button class="btn btn-danger" onclick="app.closeSession('${session.session_id}')">Close</button>` :
                                ''
                            }
                        </div>
                    </div>
                </div>
            `;
        }).join('');
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

    async closeSession(sessionId) {
        if (!confirm('Are you sure you want to close this session? It cannot be reopened.')) {
            return;
        }
        
        try {
            await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${sessionId}/close`, {
                method: 'POST'
            });
            
            this.showAlert('Session closed successfully!', 'success');
            await this.refreshSessions();
        } catch (error) {
            console.error('Failed to close session:', error);
        }
    }

    // Chat/Play Interface
    initializeChat() {
        if (!this.currentSession || !this.currentCampaign) return;
        
        // Update play interface info
        const playInfo = document.getElementById('current-play-info');
        if (playInfo) {
            playInfo.innerHTML = `
                <h3>${this.currentCampaign.campaign_name || 'Untitled Campaign'}</h3>
                <p><strong>Session:</strong> ${this.currentSession.turn_number || 0} turns</p>
                <p><strong>Status:</strong> ${this.currentSession.status}</p>
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
            this.currentSession.chat_history.forEach(message => {
                this.addChatMessage(message.role, message.content);
            });
        } else {
            this.addChatMessage('system', 'Welcome to your D&D session! What would you like to do?');
        }
        
        this.scrollChatToBottom();
    }

    addChatMessage(role, content) {
        const container = document.getElementById('chat-messages');
        if (!container) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        messageDiv.textContent = content;
        
        container.appendChild(messageDiv);
        this.scrollChatToBottom();
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
            this.addChatMessage('system', 'Connected to game session');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'dm_response') {
                this.addChatMessage('dm', data.dm_response);
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
            this.addChatMessage('system', 'Disconnected from game session');
        };
    }

    sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input || !input.value.trim()) return;
        
        const message = input.value.trim();
        
        // Add user message to chat
        this.addChatMessage('user', message);
        
        // Send via WebSocket if connected
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'play_turn',
                input: message,
                user_id: 'web_user'
            }));
        } else {
            // Fallback to REST API
            this.sendMessageREST(message);
        }
        
        input.value = '';
    }

    async sendMessageREST(message) {
        try {
            const result = await this.apiRequest(`/api/campaigns/${this.currentCampaign.campaign_id}/sessions/${this.currentSession.session_id}/turn`, {
                method: 'POST',
                body: JSON.stringify({
                    input: message,
                    user_id: 'web_user'
                })
            });
            
            this.addChatMessage('dm', result.dm_response);
            
            if (result.turn_number) {
                this.currentSession.turn_number = result.turn_number;
            }
        } catch (error) {
            this.addChatMessage('system', 'Failed to send message. Please try again.');
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

        let markdown = '';
        
        // Handle core_themes as the main overview (visible by default)
        if (outlineData.core_themes && Array.isArray(outlineData.core_themes)) {
            markdown += '# Campaign Themes\n\n';
            outlineData.core_themes.forEach(theme => {
                if (theme.label && theme.description) {
                    markdown += `**${theme.label}:** ${theme.description}\n\n`;
                }
            });
        }
        
        // Handle initial_draft as story overview
        if (outlineData.initial_draft && Array.isArray(outlineData.initial_draft)) {
            markdown += '## Story Overview\n\n';
            outlineData.initial_draft.forEach((paragraph, index) => {
                if (typeof paragraph === 'string') {
                    markdown += `${paragraph}\n\n`;
                }
            });
        }
        
        // Handle other sections dynamically
        Object.keys(outlineData).forEach(key => {
            if (key === 'core_themes' || key === 'initial_draft' || key === 'lore_call_checklist') {
                return; // Already handled or skip checklist
            }
            
            const value = outlineData[key];
            const heading = `## ${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`;
            
            markdown += `${heading}\n\n`;
            
            if (typeof value === 'object') {
                if (Array.isArray(value)) {
                    value.forEach((item, index) => {
                        if (typeof item === 'object') {
                            const itemTitle = item.name || item.title || item.label || `Item ${index + 1}`;
                            markdown += `### ${itemTitle}\n\n`;
                            Object.keys(item).forEach(subKey => {
                                if (subKey !== 'name' && subKey !== 'title' && subKey !== 'label') {
                                    markdown += `**${subKey.replace(/_/g, ' ')}:** ${item[subKey]}\n\n`;
                                }
                            });
                        } else {
                            markdown += `- ${item}\n`;
                        }
                    });
                } else {
                    Object.keys(value).forEach(subKey => {
                        markdown += `**${subKey.replace(/_/g, ' ')}:** ${value[subKey]}\n\n`;
                    });
                }
            } else {
                markdown += `${value}\n\n`;
            }
        });

        return markdown;
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
        
        // Convert JSON to markdown
        const markdown = this.convertJSONToMarkdown(outlineData);
        
        // Convert markdown to HTML using marked.js
        const htmlContent = marked.parse(markdown);
        
        // Make sections collapsible (except h1)
        const collapsibleContent = this.makeCollapsible(htmlContent);
        
        return `<div class="markdown-content">${collapsibleContent}</div>`;
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