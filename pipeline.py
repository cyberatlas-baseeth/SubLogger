"""
SubLogger - Decision Pipeline
Routes text through language detection → translation → logging.
Handles both subtitle and audio sources with deduplication.
"""

import time
import threading

import config
from language_detector import detect_language, is_turkish
from translator import translate_text
from logger import SubLogger


class Pipeline:
    """
    Core decision pipeline:
      IF subtitle exists:
          IF Turkish → translate to English
          ELSE → use as-is
      ELSE:
          capture audio → transcribe → same language logic
      LOG the result
    """

    def __init__(self, sub_logger: SubLogger):
        self._logger = sub_logger
        self._last_subtitle_time = 0.0
        self._lock = threading.Lock()
        self._debounce_cache: dict[str, float] = {}  # text → timestamp

    def process_subtitle(self, text: str) -> dict | None:
        """
        Process a subtitle text through the pipeline.

        Args:
            text: Raw subtitle text from the browser extension.

        Returns:
            Log entry dict or None if deduplicated/filtered.
        """
        if not text or not text.strip():
            return None

        text = text.strip()

        # Debounce: skip if same text was processed recently
        with self._lock:
            now = time.time()
            last_time = self._debounce_cache.get(text, 0)
            if now - last_time < (config.SUBTITLE_DEBOUNCE_MS / 1000.0):
                return None
            self._debounce_cache[text] = now
            self._last_subtitle_time = now

            # Trim cache to prevent memory growth
            if len(self._debounce_cache) > config.DEDUP_HISTORY_SIZE * 2:
                cutoff = now - 60  # Remove entries older than 60 seconds
                self._debounce_cache = {
                    k: v for k, v in self._debounce_cache.items() if v > cutoff
                }

        # Deduplication: skip if already in recent logs
        recent_texts = self._logger.get_recent_texts()
        if text in recent_texts:
            return None

        # Language detection and translation
        lang, confidence = detect_language(text)
        tr, tr_confidence = is_turkish(text)

        if tr:
            translated, success = translate_text(text)
            if success:
                return self._logger.log(
                    source="subtitle",
                    original_text=text,
                    final_text=translated,
                    language=lang,
                    translated=True,
                    confidence=tr_confidence,
                )
            else:
                # Translation failed, log original
                return self._logger.log(
                    source="subtitle",
                    original_text=text,
                    final_text=text,
                    language=lang,
                    translated=False,
                    confidence=tr_confidence,
                )
        else:
            # Not Turkish, use as-is
            return self._logger.log(
                source="subtitle",
                original_text=text,
                final_text=text,
                language=lang,
                translated=False,
                confidence=confidence,
            )

    def process_audio_transcription(self, result: dict) -> dict | None:
        """
        Process a Whisper transcription result.

        Args:
            result: Dict with keys: text, language, confidence

        Returns:
            Log entry dict or None if filtered.
        """
        text = result.get("text", "").strip()
        if not text:
            return None

        # Deduplication
        recent_texts = self._logger.get_recent_texts()
        if text in recent_texts:
            return None

        lang = result.get("language", "unknown")
        confidence = result.get("confidence", 0.0)

        # Check if Turkish
        is_tr = lang == config.TARGET_LANGUAGE

        if is_tr:
            translated, success = translate_text(text)
            if success:
                return self._logger.log(
                    source="audio",
                    original_text=text,
                    final_text=translated,
                    language=lang,
                    translated=True,
                    confidence=confidence,
                )
            else:
                return self._logger.log(
                    source="audio",
                    original_text=text,
                    final_text=text,
                    language=lang,
                    translated=False,
                    confidence=confidence,
                )
        else:
            return self._logger.log(
                source="audio",
                original_text=text,
                final_text=text,
                language=lang,
                translated=False,
                confidence=confidence,
            )

    def should_use_audio_fallback(self) -> bool:
        """
        Check if we should activate audio fallback.
        Returns True if no subtitle has been received within the timeout window.
        """
        if config.MODE == "audio":
            return True
        if config.MODE == "subtitle":
            return False

        # Hybrid mode: fallback if no recent subtitles
        with self._lock:
            elapsed = time.time() - self._last_subtitle_time
            return elapsed > config.SUBTITLE_TIMEOUT_S

    @property
    def last_subtitle_time(self) -> float:
        with self._lock:
            return self._last_subtitle_time
