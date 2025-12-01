"""
OpenAI Text-to-Speech provider implementation.
"""

import os
import logging
from typing import AsyncGenerator, Optional, List, Literal

from openai import AsyncOpenAI

from .base import TTSProvider, TTSOptions, VoiceInfo

AudioFormat = Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm']

logger = logging.getLogger(__name__)

OPENAI_VOICES = [
    VoiceInfo(
        voice_id="alloy",
        name="Alloy",
        provider="openai",
        gender="neutral",
        description="Neutral, balanced voice"
    ),
    VoiceInfo(
        voice_id="echo",
        name="Echo",
        provider="openai",
        gender="male",
        description="Male, warm voice"
    ),
    VoiceInfo(
        voice_id="fable",
        name="Fable",
        provider="openai",
        gender="neutral",
        description="British accent, expressive - great for fantasy/storytelling"
    ),
    VoiceInfo(
        voice_id="onyx",
        name="Onyx",
        provider="openai",
        gender="male",
        description="Deep, authoritative voice"
    ),
    VoiceInfo(
        voice_id="nova",
        name="Nova",
        provider="openai",
        gender="female",
        description="Female, friendly voice"
    ),
    VoiceInfo(
        voice_id="shimmer",
        name="Shimmer",
        provider="openai",
        gender="female",
        description="Female, soft voice"
    ),
]


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS implementation using the Audio API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "tts-1"
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY_AGENT") or os.getenv("OPENAI_API_KEY")
        self._model = model
        self._client: Optional[AsyncOpenAI] = None
    
    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self._api_key:
                raise ValueError("OpenAI API key not configured")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def get_available_voices(self) -> List[VoiceInfo]:
        return OPENAI_VOICES.copy()
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        options: Optional[TTSOptions] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech with streaming.
        
        Note: OpenAI TTS API doesn't support true streaming in the same way
        as some other APIs. We fetch the full audio and yield it in chunks.
        """
        opts = options or TTSOptions()
        
        try:
            client = self._get_client()
            
            output_format: AudioFormat = "mp3"
            if opts.output_format in ('mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'):
                output_format = opts.output_format  # type: ignore
            
            response = await client.audio.speech.create(
                model=self._model,
                voice=voice_id,
                input=text,
                response_format=output_format,
                speed=opts.speed
            )
            
            audio_data = response.content
            
            chunk_size = 8192
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]
                
        except Exception as e:
            logger.error(f"OpenAI TTS synthesis error: {e}")
            raise
    
    async def synthesize_full(
        self,
        text: str,
        voice_id: str,
        options: Optional[TTSOptions] = None
    ) -> bytes:
        """Synthesize text to speech, returning complete audio."""
        opts = options or TTSOptions()
        
        try:
            client = self._get_client()
            
            output_format: AudioFormat = "mp3"
            if opts.output_format in ('mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'):
                output_format = opts.output_format  # type: ignore
            
            response = await client.audio.speech.create(
                model=self._model,
                voice=voice_id,
                input=text,
                response_format=output_format,
                speed=opts.speed
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"OpenAI TTS synthesis error: {e}")
            raise
