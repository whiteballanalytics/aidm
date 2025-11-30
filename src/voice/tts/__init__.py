"""
Text-to-Speech (TTS) providers.

Available providers:
- OpenAI TTS (default)
- ElevenLabs TTS (for character voices)
"""

from .base import TTSProvider, VoiceInfo, TTSOptions

__all__ = ["TTSProvider", "VoiceInfo", "TTSOptions"]
