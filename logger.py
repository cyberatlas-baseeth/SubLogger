"""
SubLogger - Dual-format Logger
Writes to both logs.txt (human-readable) and logs.json (structured).
Thread-safe.
"""

import json
import os
import threading
from datetime import datetime, timezone

import config


class SubLogger:
    """Thread-safe dual-format logger for subtitle/audio transcription entries."""

    def __init__(self):
        os.makedirs(config.LOG_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: list[dict] = []

        # Load existing JSON entries if file exists
        if os.path.exists(config.LOG_JSON_FILE):
            try:
                with open(config.LOG_JSON_FILE, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._entries = []

    def log(
        self,
        source: str,
        original_text: str,
        final_text: str,
        language: str = "",
        translated: bool = False,
        confidence: float = 0.0,
    ) -> dict:
        """
        Log an entry to both txt and json files.

        Args:
            source: "subtitle" or "audio"
            original_text: The raw captured text
            final_text: The text after translation (or same as original)
            language: Detected language code (e.g. "tr", "en")
            translated: Whether translation was applied
            confidence: Language detection confidence score

        Returns:
            The logged entry dict
        """
        now = datetime.now(timezone.utc)
        timestamp_display = now.strftime("%H:%M:%S")
        timestamp_iso = now.isoformat()

        entry = {
            "timestamp": timestamp_iso,
            "timestamp_display": timestamp_display,
            "source": source,
            "original_text": original_text,
            "final_text": final_text,
            "language": language,
            "translated": translated,
            "confidence": round(confidence, 3),
        }

        with self._lock:
            self._entries.append(entry)
            self._write_txt(entry)
            self._write_json()

        return entry

    def _write_txt(self, entry: dict):
        """Append a single line to logs.txt."""
        arrow = " → " if entry["translated"] else ""
        final = entry["final_text"] if entry["translated"] else ""
        line = (
            f"[{entry['timestamp_display']}] "
            f"({entry['source']}) "
            f"{entry['original_text']}{arrow}{final}\n"
        )
        try:
            with open(config.LOG_TXT_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except IOError as e:
            print(f"[ERROR] Failed to write logs.txt: {e}")

    def _write_json(self):
        """Rewrite the entire JSON log file."""
        try:
            with open(config.LOG_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[ERROR] Failed to write logs.json: {e}")

    def get_entries(self, last_n: int = 0) -> list[dict]:
        """Get log entries. If last_n > 0, return only the last N entries."""
        with self._lock:
            if last_n > 0:
                return list(self._entries[-last_n:])
            return list(self._entries)

    def get_recent_texts(self, n: int = None) -> set[str]:
        """Get set of recent final texts for deduplication."""
        if n is None:
            n = config.DEDUP_HISTORY_SIZE
        with self._lock:
            recent = self._entries[-n:] if len(self._entries) >= n else self._entries
            return {e["final_text"] for e in recent}
