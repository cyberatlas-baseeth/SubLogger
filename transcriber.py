"""
SubLogger - Whisper Transcription Module
Loads OpenAI Whisper locally and transcribes audio chunks.
"""

import threading
import numpy as np

import config

# Lazy-loaded model
_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazy-load the Whisper model (thread-safe)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import whisper
                print(f"[INFO] Loading Whisper model '{config.WHISPER_MODEL}'...")
                _model = whisper.load_model(config.WHISPER_MODEL)
                print(f"[INFO] Whisper model loaded successfully")
    return _model


def transcribe_audio(audio_data: np.ndarray) -> dict:
    """
    Transcribe an audio chunk using Whisper.

    Args:
        audio_data: NumPy array of float32 audio samples at 16kHz.

    Returns:
        Dict with keys: text, language, confidence
    """
    if audio_data is None or len(audio_data) == 0:
        return {"text": "", "language": "unknown", "confidence": 0.0}

    try:
        model = _get_model()

        # Ensure correct dtype
        audio = audio_data.astype(np.float32)

        # Pad/trim to 30 seconds as Whisper expects
        import whisper
        audio = whisper.pad_or_trim(audio)

        # Transcribe
        options = {}
        if config.WHISPER_LANGUAGE:
            options["language"] = config.WHISPER_LANGUAGE

        result = model.transcribe(
            audio,
            fp16=False,  # Use fp32 for CPU compatibility
            **options,
        )

        text = result.get("text", "").strip()
        language = result.get("language", "unknown")

        # Calculate average confidence from segments
        segments = result.get("segments", [])
        if segments:
            avg_conf = sum(
                seg.get("avg_logprob", -1.0) for seg in segments
            ) / len(segments)
            # Convert log probability to a 0-1 score (approximate)
            confidence = max(0.0, min(1.0, 1.0 + avg_conf))
        else:
            confidence = 0.0

        return {
            "text": text,
            "language": language,
            "confidence": round(confidence, 3),
        }

    except Exception as e:
        print(f"[ERROR] Whisper transcription failed: {e}")
        return {"text": "", "language": "unknown", "confidence": 0.0}


def transcribe_in_thread(audio_data: np.ndarray, callback):
    """
    Transcribe audio in a background thread.

    Args:
        audio_data: Audio samples.
        callback: Function called with the result dict when done.
    """
    def _run():
        result = transcribe_audio(audio_data)
        if callback:
            callback(result)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
