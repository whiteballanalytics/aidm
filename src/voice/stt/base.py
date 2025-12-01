"""
Abstract base class for Speech-to-Text providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """Result from STT transcription."""
    text: str
    is_final: bool
    confidence: Optional[float] = None
    language: Optional[str] = None


class STTProvider(ABC):
    """Abstract base class for STT providers."""
    
    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "en"
    ) -> AsyncGenerator[TranscriptionResult, None]:
        """
        Transcribe streaming audio input.
        
        Args:
            audio_stream: Async generator yielding audio chunks
            language: Language code for transcription
            
        Yields:
            TranscriptionResult with interim and final transcriptions
        """
        pass
    
    @abstractmethod
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en"
    ) -> TranscriptionResult:
        """
        Transcribe a complete audio buffer.
        
        Args:
            audio_data: Complete audio data
            language: Language code for transcription
            
        Returns:
            TranscriptionResult with final transcription
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass
