"""
SubLogger - Translation Module
Uses deep-translator (Google Translate) for Turkish → English.
Free, no API key required.
"""

from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    TranslationNotFound,
    RequestError,
    TooManyRequests,
)

import config


# Reusable translator instance
_translator = GoogleTranslator(
    source=config.TARGET_LANGUAGE,
    target=config.OUTPUT_LANGUAGE,
)


def translate_text(text: str) -> tuple[str, bool]:
    """
    Translate text from Turkish to English.

    Args:
        text: The Turkish text to translate.

    Returns:
        Tuple of (translated_text, success).
        On failure, returns (original_text, False).
    """
    if not text or not text.strip():
        return (text, False)

    try:
        result = _translator.translate(text.strip())
        if result:
            return (result, True)
        return (text, False)
    except (TranslationNotFound, RequestError, TooManyRequests) as e:
        print(f"[WARN] Translation failed: {e}")
        return (text, False)
    except Exception as e:
        print(f"[WARN] Unexpected translation error: {e}")
        return (text, False)
