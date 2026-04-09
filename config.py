"""
SubLogger Configuration
Central configuration for all modules.
"""

import os

# ─── WebSocket Server ────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 8765

# ─── Whisper ─────────────────────────────────────────────────────────
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large
WHISPER_LANGUAGE = None  # None = auto-detect, or set e.g. "tr", "en"

# ─── Audio Capture ───────────────────────────────────────────────────
AUDIO_CHUNK_DURATION = 3        # seconds per chunk
AUDIO_SAMPLE_RATE = 16000       # Whisper expects 16kHz
AUDIO_CHANNELS = 1              # mono

# ─── Subtitle Processing ────────────────────────────────────────────
SUBTITLE_DEBOUNCE_MS = 300      # debounce interval in milliseconds
SUBTITLE_TIMEOUT_S = 10         # seconds without subtitle before audio fallback
DEDUP_HISTORY_SIZE = 20         # number of recent entries to check for duplicates

# ─── Language Detection ──────────────────────────────────────────────
LANG_CONFIDENCE_THRESHOLD = 0.5 # minimum confidence for language detection
TARGET_LANGUAGE = "tr"          # language to translate FROM
OUTPUT_LANGUAGE = "en"          # language to translate TO

# ─── Logging ─────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_TXT_FILE = os.path.join(LOG_DIR, "logs.txt")
LOG_JSON_FILE = os.path.join(LOG_DIR, "logs.json")

# ─── Mode ────────────────────────────────────────────────────────────
# Options: "hybrid", "subtitle", "audio"
MODE = "hybrid"
