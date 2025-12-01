"""
Voice module for D&D AI Dungeon Master.

This module provides voice input (STT) and output (TTS) capabilities,
separated from the core game engine logic.

See docs/VOICE_ARCHITECTURE.md for full architectural documentation.
"""

from .voice_controller import VoiceController, get_voice_controller
from .config import (
    VoiceConfig,
    VoiceSettings,
    get_voice_config,
    is_tts_enabled,
    is_intent_speakable,
    SPEAKABLE_INTENTS,
)
from .tts import OpenAITTSProvider

__all__ = [
    "VoiceController",
    "get_voice_controller",
    "VoiceConfig",
    "VoiceSettings",
    "get_voice_config",
    "is_tts_enabled",
    "is_intent_speakable",
    "SPEAKABLE_INTENTS",
    "OpenAITTSProvider",
]
