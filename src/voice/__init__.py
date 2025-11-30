"""
Voice module for D&D AI Dungeon Master.

This module provides voice input (STT) and output (TTS) capabilities,
separated from the core game engine logic.

See docs/VOICE_ARCHITECTURE.md for full architectural documentation.
"""

from .voice_controller import VoiceController
from .config import VoiceConfig, get_voice_config

__all__ = [
    "VoiceController",
    "VoiceConfig", 
    "get_voice_config"
]
