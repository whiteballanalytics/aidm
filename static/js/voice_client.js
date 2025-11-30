/**
 * Voice Client for D&D AI Dungeon Master
 * 
 * Handles voice input (STT) via Web Speech API and voice output (TTS) via audio playback.
 * See docs/VOICE_ARCHITECTURE.md for full architectural documentation.
 */

class VoiceClient {
    constructor(chatApp) {
        this.chatApp = chatApp;
        this.recognition = null;
        this.isListening = false;
        this.isSupported = this._checkSupport();
        this.audioContext = null;
        this.currentAudio = null;
        
        this._initializeRecognition();
    }
    
    /**
     * Check if Web Speech API is supported
     */
    _checkSupport() {
        return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    }
    
    /**
     * Check if voice features are available
     */
    isAvailable() {
        return this.isSupported;
    }
    
    /**
     * Initialize the speech recognition instance
     */
    _initializeRecognition() {
        if (!this.isSupported) {
            console.warn('Web Speech API not supported in this browser');
            return;
        }
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        this.recognition.maxAlternatives = 1;
        
        this.previousInputValue = '';
        
        this.recognition.onstart = () => {
            this.isListening = true;
            this.hasFinalResult = false;
            const input = document.getElementById('chat-input');
            if (input) {
                this.previousInputValue = input.value;
            }
            this._updateUI('listening');
            console.log('Voice recognition started');
        };
        
        this.recognition.onend = () => {
            this.isListening = false;
            const input = document.getElementById('chat-input');
            if (input && input.classList.contains('voice-interim') && !this.hasFinalResult) {
                input.value = this.previousInputValue;
                input.classList.remove('voice-interim');
            }
            this._updateUI('idle');
            console.log('Voice recognition ended');
        };
        
        this.recognition.onresult = (event) => {
            this._handleRecognitionResult(event);
        };
        
        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
            this._updateUI('error', event.error);
            
            const input = document.getElementById('chat-input');
            if (input && input.classList.contains('voice-interim')) {
                input.value = this.previousInputValue;
                input.classList.remove('voice-interim');
            }
            
            if (event.error === 'not-allowed') {
                this._showPermissionError();
            } else if (event.error === 'no-speech') {
                this._showNoSpeechError();
            }
        };
    }
    
    _showNoSpeechError() {
        if (this.chatApp && this.chatApp.showAlert) {
            this.chatApp.showAlert(
                'No speech detected. Click the microphone and speak clearly.',
                'warning'
            );
        }
    }
    
    /**
     * Handle speech recognition results
     */
    _handleRecognitionResult(event) {
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }
        
        if (interimTranscript) {
            this._updateInterimText(interimTranscript);
        }
        
        if (finalTranscript) {
            this._submitFinalText(finalTranscript.trim());
        }
    }
    
    /**
     * Update the chat input with interim (in-progress) transcription
     */
    _updateInterimText(text) {
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            input.classList.add('voice-interim');
        }
    }
    
    /**
     * Submit the final transcription as a message
     */
    _submitFinalText(text) {
        this.hasFinalResult = true;
        
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            input.classList.remove('voice-interim');
        }
        
        if (text && this.chatApp) {
            this.chatApp.sendMessageFromVoice(text);
        }
    }
    
    /**
     * Start listening for voice input
     */
    startListening() {
        if (!this.isSupported) {
            console.error('Voice input not supported');
            this._updateUI('error', 'not supported');
            return false;
        }
        
        if (this.isListening) {
            return true;
        }
        
        try {
            this.recognition.start();
            return true;
        } catch (error) {
            console.error('Failed to start voice recognition:', error);
            this._updateUI('error', error.message || 'start failed');
            if (this.chatApp && this.chatApp.showAlert) {
                this.chatApp.showAlert(
                    'Could not start voice recognition. Please try again.',
                    'error'
                );
            }
            return false;
        }
    }
    
    /**
     * Stop listening for voice input
     */
    stopListening() {
        if (!this.recognition || !this.isListening) {
            return;
        }
        
        try {
            this.recognition.stop();
        } catch (error) {
            console.error('Failed to stop voice recognition:', error);
        }
    }
    
    /**
     * Toggle listening state
     */
    toggleListening() {
        if (this.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
        return this.isListening;
    }
    
    /**
     * Play TTS audio for a DM response
     */
    async playResponse(audioUrl, options = {}) {
        if (!audioUrl) {
            console.warn('No audio URL provided');
            return;
        }
        
        this.stopPlayback();
        
        try {
            const audio = new Audio(audioUrl);
            this.currentAudio = audio;
            
            audio.volume = options.volume || 1.0;
            audio.playbackRate = options.speed || 1.0;
            
            audio.onplay = () => {
                this._updateUI('speaking');
            };
            
            audio.onended = () => {
                this.currentAudio = null;
                this._updateUI('idle');
            };
            
            audio.onerror = (error) => {
                console.error('Audio playback error:', error);
                this.currentAudio = null;
                this._updateUI('idle');
            };
            
            await audio.play();
        } catch (error) {
            console.error('Failed to play audio:', error);
            this._updateUI('idle');
        }
    }
    
    /**
     * Stop any current audio playback
     */
    stopPlayback() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
            this._updateUI('idle');
        }
    }
    
    /**
     * Update UI elements based on voice state
     */
    _updateUI(state, error = null) {
        const micButton = document.getElementById('voice-mic-button');
        const voiceStatus = document.getElementById('voice-status');
        
        if (micButton) {
            micButton.classList.remove('listening', 'speaking', 'error');
            
            switch (state) {
                case 'listening':
                    micButton.classList.add('listening');
                    micButton.title = 'Listening... (click to stop)';
                    break;
                case 'speaking':
                    micButton.classList.add('speaking');
                    micButton.title = 'DM is speaking...';
                    break;
                case 'error':
                    micButton.classList.add('error');
                    micButton.title = `Error: ${error}`;
                    break;
                default:
                    micButton.title = 'Click to speak';
            }
        }
        
        if (voiceStatus) {
            switch (state) {
                case 'listening':
                    voiceStatus.textContent = 'Listening...';
                    voiceStatus.className = 'voice-status listening';
                    break;
                case 'speaking':
                    voiceStatus.textContent = 'DM speaking...';
                    voiceStatus.className = 'voice-status speaking';
                    break;
                case 'error':
                    voiceStatus.textContent = `Error: ${error}`;
                    voiceStatus.className = 'voice-status error';
                    break;
                default:
                    voiceStatus.textContent = '';
                    voiceStatus.className = 'voice-status';
            }
        }
    }
    
    /**
     * Show permission error message
     */
    _showPermissionError() {
        if (this.chatApp && this.chatApp.showAlert) {
            this.chatApp.showAlert(
                'Microphone permission denied. Please enable microphone access in your browser settings.',
                'error'
            );
        }
    }
    
    /**
     * Handle voice directive from backend
     */
    handleVoiceDirective(directive) {
        if (!directive || !directive.enabled) {
            return;
        }
        
        if (directive.auto_play && directive.audio_url) {
            this.playResponse(directive.audio_url, {
                speed: directive.speed || 1.0
            });
        }
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        this.stopListening();
        this.stopPlayback();
        this.recognition = null;
    }
}

window.VoiceClient = VoiceClient;
