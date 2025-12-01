"""
Text-to-Speech (TTS) providers.

Available providers:
- OpenAI TTS (default)
- ElevenLabs TTS (for character voices)
"""

from .base import TTSProvider, VoiceInfo, TTSOptions
from .openai_tts import OpenAITTSProvider

__all__ = ["TTSProvider", "VoiceInfo", "TTSOptions", "OpenAITTSProvider"]
