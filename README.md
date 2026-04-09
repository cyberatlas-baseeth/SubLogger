# SubLogger

Real-time subtitle capture & audio transcription system with Turkish→English translation.

## Architecture

```
┌─────────────────────┐       WebSocket       ┌──────────────────────┐
│   Chrome Extension   │ ──────────────────── → │   Python Backend     │
│                      │   ws://localhost:8765  │                      │
│  • MutationObserver  │ ← ─── ack ────────── │  • Language Detection │
│  • TextTrack API     │                       │  • Translation (TR→EN)│
│  • Heuristic detect  │                       │  • Audio Capture      │
└─────────────────────┘                        │  • Whisper STT        │
                                               │  • Logging            │
                                               └──────────┬───────────┘
                                                          │
                                                   ┌──────┴──────┐
                                                   │  logs.txt   │
                                                   │  logs.json  │
                                                   └─────────────┘
```

**Decision Pipeline:**
```
IF subtitle exists:
    IF language == Turkish → translate to English
    ELSE → use as-is
ELSE:
    capture system audio → transcribe with Whisper
    IF language == Turkish → translate
LOG result
```

---

## Setup

### 1. Python Backend

**Prerequisites:** Python 3.10+, pip

```bash
cd sublogger

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

> **Note:** First run will download the Whisper model (~140MB for `base`). PyTorch will also be installed (~2GB).

### 2. Start the Backend

```bash
# Default: hybrid mode, base model, port 8765
python main.py

# Subtitle-only mode
python main.py --mode subtitle

# Audio-only mode with smaller model
python main.py --mode audio --model tiny

# Custom port
python main.py --port 9000

# View recent logs
python main.py --tail
python main.py --tail --tail-n 50
```

### 3. Chrome Extension

1. Open Chrome → `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder
5. The SubLogger icon appears in the toolbar

---

## Modes

| Mode | Behavior |
|------|----------|
| `hybrid` | Uses subtitles when available, falls back to audio capture when no subtitles for 10s |
| `subtitle` | Only captures subtitles from the extension, no audio |
| `audio` | Only captures system audio and transcribes, no subtitles |

---

## Project Structure

```
sublogger/
├── main.py                 # Entry point + CLI
├── config.py               # Configuration
├── server.py               # WebSocket server
├── pipeline.py             # Decision logic
├── language_detector.py    # langdetect wrapper
├── translator.py           # Google Translate (free)
├── audio_capture.py        # WASAPI loopback capture
├── transcriber.py          # Whisper STT
├── logger.py               # Dual-format logging
├── requirements.txt        # Python dependencies
├── logs/                   # Output directory
│   ├── logs.txt            # Human-readable log
│   └── logs.json           # Structured log
└── extension/              # Chrome extension
    ├── manifest.json
    ├── content.js           # Subtitle detection
    ├── background.js        # WebSocket client
    ├── popup.html           # Settings popup
    ├── popup.js
    ├── popup.css
    └── icons/
        ├── icon16.png
        ├── icon48.png
        └── icon128.png
```

---

## Log Format

**logs.txt:**
```
[16:23:45] (subtitle) Merhaba dünya → Hello world
[16:23:48] (subtitle) This is already in English
[16:24:01] (audio) Nasılsınız → How are you
```

**logs.json:**
```json
[
  {
    "timestamp": "2026-04-09T13:23:45.123456+00:00",
    "timestamp_display": "16:23:45",
    "source": "subtitle",
    "original_text": "Merhaba dünya",
    "final_text": "Hello world",
    "language": "tr",
    "translated": true,
    "confidence": 0.95
  }
]
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `websockets` | WebSocket server for extension communication |
| `openai-whisper` | Local speech-to-text |
| `langdetect` | Language identification |
| `deep-translator` | Free Google Translate |
| `sounddevice` | WASAPI loopback audio capture |
| `numpy` | Audio data processing |
| `torch` | Whisper backend |

All dependencies are **free and open-source**. No API keys required.

---

## Performance Notes

- Subtitle debouncing at 300ms prevents duplicate processing
- Deduplication checks against last 20 log entries
- Audio silence detection skips quiet chunks (RMS < 0.001)
- Whisper model is lazy-loaded on first audio transcription
- Audio worker pauses when subtitles are actively received
