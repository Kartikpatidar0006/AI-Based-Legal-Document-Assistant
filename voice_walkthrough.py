"""
voice_walkthrough.py
AI-Based Legal Document Assistant for Small Businesses

Voice walkthrough module:
Re-exports _clean_text_for_speech, generate_audio_summary, and AUDIO_CACHE_DIR
from document_processor for backwards compatibility.
"""

from document_processor import (
    _clean_text_for_speech,
    generate_audio_summary,
    AUDIO_CACHE_DIR,
)

__all__ = [
    "_clean_text_for_speech",
    "generate_audio_summary",
    "AUDIO_CACHE_DIR",
]
