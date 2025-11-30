"""
Speech-to-Text (STT) providers.

Primary: Browser-native Web Speech API (handled in frontend)
Fallback: OpenAI Realtime API (server-side)
"""

from .base import STTProvider

__all__ = ["STTProvider"]
