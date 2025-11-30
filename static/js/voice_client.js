/**
 * Voice Client for D&D AI Dungeon Master
 * 
 * Handles voice input (STT) via Web Speech API and voice output (TTS) via audio playback.
 * See docs/VOICE_ARCHITECTURE.md for full architectural documentation.
 */

const SPEAKABLE_INTENTS = new Set([
    'narrative_short',
    'narrative_long',
    'qa_situation',
    'travel',
]);

class VoiceClient {
    constructor(chatApp) {
        this.chatApp = chatApp;
        this.recognition = null;
        this.isListening = false;
        this.isSupported = this._checkSupport();
        this.audioContext = null;
        this.currentAudio = null;
        this.ttsEnabled = true;
        this.currentAbortController = null;
        this.currentOnComplete = null;
        
        this._initializeRecognition();
    }
    
    /**
     * Check if TTS should play for a given intent
     */
    shouldSpeak(intent) {
        return this.ttsEnabled && intent && SPEAKABLE_INTENTS.has(intent);
    }
    
    /**
     * Enable or disable TTS playback
     */
    setTTSEnabled(enabled) {
        this.ttsEnabled = enabled;
        if (!enabled) {
            this.stopPlayback();
        }
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
     * Place the final transcription in the input field for user review
     * User can then edit and submit manually when ready
     */
    _submitFinalText(text) {
        this.hasFinalResult = true;
        
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            input.classList.remove('voice-interim');
            input.focus();
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
     * Speak a DM response using TTS
     * Requests audio from backend and plays it
     * @param {string} text - Text to speak
     * @param {string} intent - Intent type
     * @param {Function} onComplete - Optional callback when playback completes
     * @returns {Promise} Resolves when playback completes
     */
    async speakDMResponse(text, intent, onComplete = null) {
        if (!this.shouldSpeak(intent)) {
            if (onComplete) onComplete();
            return;
        }
        
        if (!text || text.trim().length === 0) {
            if (onComplete) onComplete();
            return;
        }
        
        this.stopPlayback();
        
        // Create abort controller for this request
        const abortController = new AbortController();
        this.currentAbortController = abortController;
        this.currentOnComplete = onComplete;
        
        try {
            console.log(`Requesting TTS for intent: ${intent}`);
            
            const response = await fetch('/api/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    intent: intent
                }),
                signal: abortController.signal
            });
            
            // Check if we were cancelled during the fetch
            if (abortController.signal.aborted) {
                return;
            }
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.warn('TTS request failed:', errorData.error || response.statusText);
                if (onComplete) onComplete();
                return;
            }
            
            const audioBlob = await response.blob();
            
            // Check if we were cancelled during blob reading
            if (abortController.signal.aborted) {
                return;
            }
            
            const audioUrl = URL.createObjectURL(audioBlob);
            
            await this.playResponse(audioUrl, { cleanup: true, onComplete });
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('TTS request was cancelled');
                // onComplete already called by stopPlayback
                return;
            }
            console.error('Failed to get TTS audio:', error);
            if (onComplete) onComplete();
        } finally {
            if (this.currentAbortController === abortController) {
                this.currentAbortController = null;
                this.currentOnComplete = null;
            }
        }
    }
    
    /**
     * Play TTS audio for a DM response
     * Note: This does NOT call stopPlayback() - caller is responsible for cleanup
     * @returns {Promise} Resolves when playback completes
     */
    async playResponse(audioUrl, options = {}) {
        if (!audioUrl) {
            console.warn('No audio URL provided');
            if (options.onComplete) options.onComplete();
            return;
        }
        
        // Stop any currently playing audio (but don't abort controllers - handled by caller)
        if (this.currentAudio) {
            const oldAudio = this.currentAudio;
            this.currentAudio = null;
            oldAudio.pause();
            // Note: don't trigger old onended - the new playback takes over
        }
        
        return new Promise((resolve) => {
            try {
                const audio = new Audio(audioUrl);
                this.currentAudio = audio;
                
                audio.volume = options.volume || 1.0;
                audio.playbackRate = options.speed || 1.0;
                
                const cleanupUrl = options.cleanup ? audioUrl : null;
                
                const cleanup = () => {
                    this.currentAudio = null;
                    this._updateUI('idle');
                    if (cleanupUrl) {
                        URL.revokeObjectURL(cleanupUrl);
                    }
                    if (options.onComplete) options.onComplete();
                    resolve();
                };
                
                audio.onplay = () => {
                    this._updateUI('speaking');
                };
                
                audio.onended = cleanup;
                
                audio.onerror = (error) => {
                    console.error('Audio playback error:', error);
                    cleanup();
                };
                
                audio.play().catch((error) => {
                    console.error('Failed to play audio:', error);
                    cleanup();
                });
            } catch (error) {
                console.error('Failed to play audio:', error);
                this._updateUI('idle');
                if (options.onComplete) options.onComplete();
                resolve();
            }
        });
    }
    
    /**
     * Stop any current audio playback or pending TTS request
     */
    stopPlayback() {
        // Cancel any pending TTS request
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            // Call the onComplete callback since we're cancelling
            if (this.currentOnComplete) {
                this.currentOnComplete();
                this.currentOnComplete = null;
            }
            this.currentAbortController = null;
        }
        
        // Stop any playing audio
        if (this.currentAudio) {
            const audio = this.currentAudio;
            this.currentAudio = null;
            audio.pause();
            // Trigger onended to run cleanup callbacks
            if (audio.onended) {
                audio.onended();
            }
        }
    }
    
    /**
     * Update UI elements based on voice state
     * Note: 'speaking' state is handled by the play button on each message, not the mic button
     */
    _updateUI(state, error = null) {
        const micButton = document.getElementById('voice-mic-button');
        const voiceStatus = document.getElementById('voice-status');
        
        if (micButton) {
            micButton.classList.remove('listening', 'error');
            
            switch (state) {
                case 'listening':
                    micButton.classList.add('listening');
                    micButton.title = 'Listening... (click to stop)';
                    break;
                case 'error':
                    micButton.classList.add('error');
                    micButton.title = `Error: ${error}`;
                    break;
                case 'speaking':
                    // Don't change mic button for speaking - handled by play button
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
                    // Don't show status for speaking - the play button indicates this
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
