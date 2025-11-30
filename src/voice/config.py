"""
Voice configuration for mapping intents and NPCs to voice settings.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class VoiceSettings:
    """Settings for a specific voice configuration."""
    provider: str = "openai"
    voice_id: str = "onyx"
    speed: float = 1.0
    pitch: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch
        }


@dataclass
class VoiceConfig:
    """Complete voice configuration."""
    
    default: VoiceSettings = field(default_factory=lambda: VoiceSettings())
    
    intents: Dict[str, VoiceSettings] = field(default_factory=lambda: {
        "narrative_short": VoiceSettings(voice_id="onyx"),
        "narrative_long": VoiceSettings(voice_id="onyx"),
        "npc_dialogue": VoiceSettings(provider="openai", voice_id="fable"),
        "qa_rules": VoiceSettings(voice_id="nova", speed=1.1),
        "qa_situation": VoiceSettings(voice_id="onyx"),
        "travel": VoiceSettings(voice_id="onyx"),
        "gameplay": VoiceSettings(voice_id="echo")
    })
    
    npcs: Dict[str, VoiceSettings] = field(default_factory=dict)
    
    def get_voice_for_intent(self, intent: str) -> VoiceSettings:
        """Get voice settings for a given intent."""
        return self.intents.get(intent, self.default)
    
    def get_voice_for_npc(self, npc_id: str) -> Optional[VoiceSettings]:
        """Get voice settings for a specific NPC."""
        return self.npcs.get(npc_id)
    
    def get_voice(
        self,
        intent: Optional[str] = None,
        speaker: Optional[str] = None
    ) -> VoiceSettings:
        """
        Get appropriate voice settings based on intent and speaker.
        
        Priority:
        1. Specific NPC voice (if speaker is provided and configured)
        2. Intent-based voice (if intent is provided)
        3. Default voice
        """
        if speaker:
            npc_voice = self.get_voice_for_npc(speaker)
            if npc_voice:
                return npc_voice
        
        if intent:
            return self.get_voice_for_intent(intent)
        
        return self.default
    
    def register_npc_voice(self, npc_id: str, settings: VoiceSettings):
        """Register a voice configuration for an NPC."""
        self.npcs[npc_id] = settings


_voice_config: Optional[VoiceConfig] = None


def get_voice_config() -> VoiceConfig:
    """Get the global voice configuration instance."""
    global _voice_config
    if _voice_config is None:
        _voice_config = VoiceConfig()
        _load_npc_voices(_voice_config)
    return _voice_config


def _load_npc_voices(config: VoiceConfig):
    """Load NPC-specific voice configurations."""
    config.register_npc_voice(
        "tavern_keeper",
        VoiceSettings(provider="openai", voice_id="onyx", pitch=0.9)
    )
    config.register_npc_voice(
        "elven_mage",
        VoiceSettings(provider="openai", voice_id="nova", speed=0.95)
    )
    config.register_npc_voice(
        "ancient_dragon",
        VoiceSettings(provider="openai", voice_id="echo", pitch=0.7, speed=0.85)
    )


def is_tts_enabled() -> bool:
    """Check if TTS is enabled via environment variable."""
    return os.getenv("VOICE_TTS_ENABLED", "false").lower() == "true"


def get_tts_provider() -> str:
    """Get the configured TTS provider."""
    return os.getenv("VOICE_TTS_PROVIDER", "openai")


def get_stt_fallback() -> str:
    """Get the configured STT fallback provider."""
    return os.getenv("VOICE_STT_FALLBACK", "openai_realtime")
