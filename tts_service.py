"""Text-to-speech helpers using Google TTS (gTTS)."""

import io
import re

from gtts import gTTS

MAX_TTS_CHARS = 500


def sanitize_tts_text(text: str) -> str:
    """Normalize whitespace and cap length for gTTS."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    return cleaned[:MAX_TTS_CHARS]


def synthesize_speech(text: str, lang: str = "en") -> bytes:
    """Return MP3 bytes for the given text."""
    safe = sanitize_tts_text(text)
    if not safe:
        raise ValueError("No text to speak")

    lang_code = (lang or "en").strip()[:5]
    buf = io.BytesIO()
    gTTS(text=safe, lang=lang_code).write_to_fp(buf)
    return buf.getvalue()
