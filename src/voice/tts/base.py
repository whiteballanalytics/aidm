"""
Abstract base class for Text-to-Speech providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, List
from dataclasses import dataclass


@dataclass
class VoiceInfo:
    """Information about an available voice."""
    voice_id: str
    name: str
    provider: str
    language: str = "en"
    gender: Optional[str] = None
    description: Optional[str] = None
    preview_url: Optional[str] = None


@dataclass
class TTSOptions:
    """Options for TTS synthesis."""
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    output_format: str = "mp3"


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: str,
        options: Optional[TTSOptions] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech, streaming audio chunks.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier for this provider
            options: Optional synthesis options
            
        Yields:
            Audio data chunks (format depends on options.output_format)
        """
        pass
    
    @abstractmethod
    async def synthesize_full(
        self,
        text: str,
        voice_id: str,
        options: Optional[TTSOptions] = None
    ) -> bytes:
        """
        Synthesize text to speech, returning complete audio.
        
        Args:
            text: Text to synthesize
            voice_id: Voice identifier for this provider
            options: Optional synthesis options
            
        Returns:
            Complete audio data
        """
        pass
    
    @abstractmethod
    def get_available_voices(self) -> List[VoiceInfo]:
        """
        Get list of available voices for this provider.
        
        Returns:
            List of VoiceInfo objects
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'elevenlabs')."""
        pass
