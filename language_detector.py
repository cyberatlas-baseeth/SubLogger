"""
SubLogger - Language Detection
Wraps langdetect for fast language identification.
"""

from langdetect import detect, detect_langs, LangDetectException

import config


def detect_language(text: str) -> tuple[str, float]:
    """
    Detect the language of the given text.

    Args:
        text: The text to detect language for.

    Returns:
        Tuple of (language_code, confidence).
        On failure, returns ("unknown", 0.0).
    """
    if not text or len(text.strip()) < 3:
        return ("unknown", 0.0)

    try:
        results = detect_langs(text)
        if results:
            best = results[0]
            return (best.lang, best.prob)
        return ("unknown", 0.0)
    except LangDetectException:
        return ("unknown", 0.0)


def is_turkish(text: str) -> tuple[bool, float]:
    """
    Check if the given text is Turkish with sufficient confidence.

    Returns:
        Tuple of (is_turkish, confidence).
    """
    lang, confidence = detect_language(text)
    is_tr = lang == config.TARGET_LANGUAGE and confidence >= config.LANG_CONFIDENCE_THRESHOLD
    return (is_tr, confidence)
