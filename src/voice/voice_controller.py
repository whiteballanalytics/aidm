"""
Voice Controller - Main facade for voice operations.

This controller receives text and metadata from the game engine
and coordinates with STT/TTS providers to handle voice I/O.
"""

import os
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from .config import get_voice_config, is_tts_enabled
from .tts.base import TTSProvider, TTSOptions

logger = logging.getLogger(__name__)


@dataclass
class VoiceHints:
    """Voice hints passed from game engine."""
    speaker: Optional[str] = None
    emotion: Optional[str] = None
    priority: str = "normal"
    auto_play: bool = False
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "VoiceHints":
        if not data:
            return cls()
        return cls(
            speaker=data.get("speaker"),
            emotion=data.get("emotion"),
            priority=data.get("priority", "normal"),
            auto_play=data.get("auto_play", False)
        )


@dataclass
class VoiceDirective:
    """Directive sent to frontend for voice handling."""
    enabled: bool = False
    provider: Optional[str] = None
    voice_id: Optional[str] = None
    speed: float = 1.0
    auto_play: bool = False
    audio_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "auto_play": self.auto_play,
            "audio_url": self.audio_url
        }


class VoiceController:
    """
    Main controller for voice operations.
    
    Responsibilities:
    - Determine voice settings based on intent and speaker
    - Coordinate with TTS providers for audio generation
    - Generate voice directives for frontend
    """
    
    def __init__(self):
        self._tts_providers: Dict[str, TTSProvider] = {}
        self._config = get_voice_config()
    
    def register_tts_provider(self, name: str, provider: TTSProvider):
        """Register a TTS provider."""
        self._tts_providers[name] = provider
        logger.info(f"Registered TTS provider: {name}")
    
    def get_tts_provider(self, name: str) -> Optional[TTSProvider]:
        """Get a registered TTS provider by name."""
        return self._tts_providers.get(name)
    
    def create_voice_directive(
        self,
        intent: Optional[str] = None,
        voice_hints: Optional[Dict[str, Any]] = None,
        response_id: Optional[str] = None
    ) -> VoiceDirective:
        """
        Create a voice directive based on intent and hints.
        
        Args:
            intent: The intent_used from the game engine
            voice_hints: Optional voice hints from the response
            response_id: Optional ID for generating audio URL
            
        Returns:
            VoiceDirective for the frontend
        """
        if not is_tts_enabled():
            return VoiceDirective(enabled=False)
        
        hints = VoiceHints.from_dict(voice_hints)
        voice_settings = self._config.get_voice(intent=intent, speaker=hints.speaker)
        
        directive = VoiceDirective(
            enabled=True,
            provider=voice_settings.provider,
            voice_id=voice_settings.voice_id,
            speed=voice_settings.speed,
            auto_play=hints.auto_play or hints.priority == "high"
        )
        
        if response_id:
            directive.audio_url = f"/api/voice/tts/{response_id}"
        
        return directive
    
    async def synthesize_speech(
        self,
        text: str,
        intent: Optional[str] = None,
        voice_hints: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize speech for the given text.
        
        Args:
            text: Text to synthesize
            intent: Intent for voice selection
            voice_hints: Optional voice hints
            
        Yields:
            Audio data chunks
            
        Note: This is a scaffold - no providers registered by default.
        Callers should check is_tts_enabled() before calling.
        """
        if not is_tts_enabled():
            logger.warning("TTS is not enabled, skipping synthesis")
            return
            yield  # Make this a proper generator even when returning early
        
        hints = VoiceHints.from_dict(voice_hints)
        voice_settings = self._config.get_voice(intent=intent, speaker=hints.speaker)
        
        provider = self._tts_providers.get(voice_settings.provider)
        if not provider:
            logger.error(f"TTS provider not found: {voice_settings.provider}")
            return
        
        if not provider.is_available():
            logger.error(f"TTS provider not available: {voice_settings.provider}")
            return
        
        options = TTSOptions(speed=voice_settings.speed)
        
        try:
            async for chunk in provider.synthesize(
                text=text,
                voice_id=voice_settings.voice_id,
                options=options
            ):
                yield chunk
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            raise
    
    async def synthesize_full(
        self,
        text: str,
        intent: Optional[str] = None,
        voice_hints: Optional[Dict[str, Any]] = None
    ) -> Optional[bytes]:
        """
        Synthesize complete audio for the given text.
        
        Args:
            text: Text to synthesize
            intent: Intent for voice selection
            voice_hints: Optional voice hints
            
        Returns:
            Complete audio data or None if unavailable
        """
        if not is_tts_enabled():
            return None
        
        hints = VoiceHints.from_dict(voice_hints)
        voice_settings = self._config.get_voice(intent=intent, speaker=hints.speaker)
        
        provider = self._tts_providers.get(voice_settings.provider)
        if not provider or not provider.is_available():
            return None
        
        options = TTSOptions(speed=voice_settings.speed)
        
        try:
            return await provider.synthesize_full(
                text=text,
                voice_id=voice_settings.voice_id,
                options=options
            )
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None


_voice_controller: Optional[VoiceController] = None


def get_voice_controller() -> VoiceController:
    """Get the global voice controller instance."""
    global _voice_controller
    if _voice_controller is None:
        _voice_controller = VoiceController()
    return _voice_controller
