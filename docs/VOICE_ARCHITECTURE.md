# Voice Architecture

This document describes the architectural decisions and module structure for the voice input/output system in the D&D AI Dungeon Master application.

## Implementation Status

**Phase 1 (Complete):** Architecture scaffolding
- Abstract provider interfaces (STT/TTS)
- Voice configuration system
- Voice controller facade
- Frontend VoiceClient with Web Speech API STT
- Microphone button UI

**Phase 2 (Complete):** Provider implementations
- OpenAI TTS concrete provider (using `tts-1` model, `fable` voice)
- `/api/tts` endpoint for text-to-speech requests
- Speakable intents: narrative_short, narrative_long, qa_situation, travel
- Frontend audio playback with speaking state UI
- Provider registration/wiring in backend

**Phase 3 (Not Started):** Advanced features
- ElevenLabs TTS provider (for character voices)
- OpenAI Realtime STT fallback provider
- NPC-specific voice selection
- Voice hints integration with play_turn response

To enable TTS, set `VOICE_TTS_ENABLED=true` environment variable.

### Future Upgrade: gpt-4o-mini-tts

OpenAI's newer `gpt-4o-mini-tts` model supports **instructable speech** - the ability to control
*how* the text is spoken, not just what is spoken. This enables:

- Emotional modulation: "Speak dramatically for tense moments"
- Pacing control: "Speak slowly and ominously"
- Character voices: "Speak with a gruff, dwarven accent"

**Upgrade path:**
1. Update `OpenAITTSProvider` to accept model as constructor parameter (already done)
2. Add emotion/style hints to `VoiceHints` dataclass
3. Modify `synthesize()` to include instruction prompts when using gpt-4o-mini-tts
4. Update voice config to specify per-intent speaking instructions

Example future config:
```python
VOICE_CONFIG = {
    "intents": {
        "narrative_long": {
            "voice_id": "fable",
            "model": "gpt-4o-mini-tts",
            "instruction": "Speak with dramatic emphasis, pause for effect"
        },
        "travel": {
            "voice_id": "fable", 
            "model": "gpt-4o-mini-tts",
            "instruction": "Speak calmly and reflectively, as if describing a peaceful journey"
        }
    }
}
```

## Design Goals

1. **Low Latency Experience** - Voice interactions should feel natural and responsive
2. **Separation of Concerns** - Voice layer is isolated from game engine logic
3. **Provider Flexibility** - Support multiple TTS providers (OpenAI, ElevenLabs) with easy extension
4. **Intent-Aware Voice** - DM voice can vary based on intent (narrative, NPC dialogue, rules)
5. **Graceful Degradation** - Fallback to text when voice is unavailable

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ Chat UI      │◄──►│ VoiceClient  │◄──►│ Audio Playback       │  │
│  │ (app.js)     │    │ (voice.js)   │    │ (Web Audio API)      │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                   │                                        │
│         │                   │ Web Speech API (STT)                   │
│         │                   │ or OpenAI Realtime (fallback)          │
└─────────┼───────────────────┼───────────────────────────────────────┘
          │                   │
          │ WebSocket         │ /ws/voice (audio stream)
          │ /ws/{campaign}/{session}
          ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           Backend                                    │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐  │
│  │ Game Engine  │───►│ Voice Controller                         │  │
│  │              │    │ (voice_controller.py)                    │  │
│  │ Returns:     │    │                                          │  │
│  │ - dm_response│    │ Receives:                                │  │
│  │ - intent_used│    │ - text, intent, speaker_profile          │  │
│  │ - voice_hints│    │                                          │  │
│  └──────────────┘    │ Delegates to:                            │  │
│                      │ - TTSProvider (abstract)                 │  │
│                      │   ├── OpenAITTS                          │  │
│                      │   └── ElevenLabsTTS                      │  │
│                      └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## STT (Speech-to-Text) Strategy

### Primary: Web Speech API (Browser-Native)
- **Latency**: Sub-300ms streaming transcripts
- **Cost**: Free (no API calls)
- **Browser Support**: Chrome, Edge, Safari (partial)
- **Implementation**: `static/js/voice_client.js`

### Fallback: OpenAI Realtime API
- **When**: Browser doesn't support Web Speech API, or accuracy is insufficient
- **Latency**: ~500ms (requires server roundtrip)
- **Cost**: Per-minute pricing
- **Implementation**: `src/voice/stt/openai_realtime.py`

### Decision Logic
```javascript
if (window.SpeechRecognition || window.webkitSpeechRecognition) {
    // Use browser-native Web Speech API
} else {
    // Fall back to OpenAI Realtime via WebSocket
}
```

## TTS (Text-to-Speech) Strategy

### Provider Interface
All TTS providers implement a common interface:

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        options: dict = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream audio chunks for the given text."""
        pass
    
    @abstractmethod
    def get_available_voices(self) -> list[VoiceInfo]:
        """Return list of available voices for this provider."""
        pass
```

### OpenAI TTS
- **Voices**: alloy, echo, fable, onyx, nova, shimmer
- **Streaming**: Yes (chunked audio)
- **Latency**: ~500ms to first chunk
- **Use Case**: Default DM narrative voice

### ElevenLabs TTS
- **Voices**: Large library + custom voice cloning
- **Streaming**: Yes
- **Latency**: ~300-500ms to first chunk
- **Use Case**: Distinct NPC character voices

## Voice Configuration

### Intent-to-Voice Mapping
Located in `src/voice/config.py`:

```python
VOICE_CONFIG = {
    "default": {
        "provider": "openai",
        "voice_id": "onyx",
        "speed": 1.0
    },
    "intents": {
        "narrative_short": {"voice_id": "onyx"},
        "narrative_long": {"voice_id": "onyx"},
        "npc_dialogue": {"provider": "elevenlabs", "voice_id": "character_default"},
        "qa_rules": {"voice_id": "nova", "speed": 1.1},
        "qa_situation": {"voice_id": "onyx"},
        "travel": {"voice_id": "onyx"},
        "gameplay": {"voice_id": "echo"}
    },
    "npcs": {
        "tavern_keeper": {"provider": "elevenlabs", "voice_id": "gruff_male"},
        "elven_mage": {"provider": "elevenlabs", "voice_id": "ethereal_female"}
    }
}
```

### Voice Hints from Game Engine
The game engine can pass optional voice hints alongside responses:

```python
return {
    "dm_response": "The dragon roars...",
    "intent_used": "narrative_long",
    "voice_hints": {
        "speaker": "ancient_dragon",  # NPC speaking
        "emotion": "menacing",
        "priority": "high"  # Should auto-play
    }
}
```

## Module Structure

```
src/voice/
├── __init__.py              # Module exports
├── voice_controller.py      # Main facade - receives text + metadata, returns audio
├── config.py                # Voice configuration and intent mapping
├── stt/
│   ├── __init__.py
│   ├── base.py              # STTProvider abstract base class
│   └── openai_realtime.py   # OpenAI Realtime STT implementation
└── tts/
    ├── __init__.py
    ├── base.py              # TTSProvider abstract base class
    ├── openai_tts.py        # OpenAI TTS implementation
    └── elevenlabs_tts.py    # ElevenLabs TTS implementation

static/js/
├── app.js                   # Existing chat application
└── voice_client.js          # Voice UI and Web Speech API handling
```

## Frontend Voice Client

### Responsibilities
1. **Microphone Management** - Request permissions, handle stream
2. **STT Processing** - Web Speech API with interim results
3. **Audio Playback** - Stream and play TTS audio chunks
4. **UI State** - Show listening/speaking indicators

### API

```javascript
class VoiceClient {
    constructor(chatApp) { }
    
    // Start listening for voice input
    startListening()
    
    // Stop listening
    stopListening()
    
    // Play TTS audio for a DM response
    playResponse(audioUrl, options)
    
    // Check if voice features are available
    isAvailable()
}
```

## WebSocket Protocol Extension

### Voice Input (STT)
Not required for browser-native Web Speech API. For OpenAI Realtime fallback:

```json
{
    "type": "voice_input",
    "audio": "<base64 audio chunk>"
}
```

### Voice Output (TTS)
Response includes audio URL or streaming endpoint:

```json
{
    "type": "dm_response",
    "dm_response": "The ancient door creaks open...",
    "intent_used": "narrative_long",
    "voice_audio_url": "/api/voice/tts/{response_id}"
}
```

## Environment Variables

```bash
# TTS Provider Selection
VOICE_TTS_PROVIDER=openai          # or "elevenlabs"
VOICE_TTS_ENABLED=true             # Enable/disable TTS

# OpenAI TTS (uses existing OPENAI_API_KEY_AGENT)
OPENAI_TTS_MODEL=tts-1             # or "tts-1-hd"

# ElevenLabs (optional)
ELEVENLABS_API_KEY=xxx             # Required if using ElevenLabs
ELEVENLABS_MODEL_ID=eleven_turbo_v2

# STT Settings
VOICE_STT_FALLBACK=openai_realtime # Fallback when Web Speech unavailable
```

## Extension Points

### Adding a New TTS Provider

1. Create `src/voice/tts/new_provider.py`:
```python
from .base import TTSProvider, VoiceInfo

class NewProviderTTS(TTSProvider):
    async def synthesize(self, text, voice_id, options=None):
        # Implementation
        yield audio_chunk
    
    def get_available_voices(self):
        return [VoiceInfo(...)]
```

2. Register in `src/voice/tts/__init__.py`
3. Add configuration in `src/voice/config.py`

### Adding NPC-Specific Voices

1. Add entry to `VOICE_CONFIG["npcs"]` in config.py
2. Pass NPC identifier in `voice_hints.speaker` from game engine
3. Voice controller automatically selects appropriate voice

## Security Considerations

1. **API Keys** - Stored as secrets, never exposed to frontend
2. **Audio Streaming** - TTS audio served from backend, not direct API calls from browser
3. **Rate Limiting** - Voice endpoints should have appropriate rate limits
4. **Content Filtering** - OpenAI TTS includes content moderation

## Testing Strategy

### Unit Tests
- Mock TTS providers to test voice controller logic
- Test intent-to-voice mapping

### Integration Tests
- Test full voice pipeline with real API calls (rate-limited)
- Verify audio format compatibility

### Frontend Tests
- Web Speech API availability detection
- Audio playback across browsers
- Graceful degradation when voice unavailable

## Future Enhancements

1. **Voice Activity Detection** - Auto-detect when user stops speaking
2. **Conversation Mode** - Continuous back-and-forth without button presses
3. **Voice Cloning** - Custom DM/NPC voices using ElevenLabs
4. **Multi-language Support** - Detect and respond in user's language
5. **Ambient Audio** - Background music/sounds based on scene
