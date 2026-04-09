"""
SubLogger - Audio Capture Module
System audio loopback capture using soundcard library natively on Windows.
"""

import threading
import queue
import numpy as np
import soundcard as sc

import config


class AudioCapture:
    """
    Captures system audio via WASAPI loopback (Windows) using soundcard.
    Records audio in chunks and pushes them to a queue for processing.
    """

    def __init__(self):
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=50)
        self._running = False
        self._lock = threading.Lock()
        self._thread = None

    def _find_loopback_device(self):
        """Find a WASAPI loopback device using soundcard."""
        try:
            # First look for default speaker's loopback
            default_speaker = sc.default_speaker()
            loopback_mics = sc.all_microphones(include_loopback=True)
            
            # Find the loopback mic matching the default speaker's name
            for mic in loopback_mics:
                if mic.isloopback and default_speaker.name in mic.name:
                    return mic

            # Fallback: return the first loopback device found
            for mic in loopback_mics:
                if mic.isloopback:
                    return mic

            # Absolute fallback: use default microphone (not loopback)
            return sc.default_microphone()

        except Exception as e:
            print(f"[WARN] Error finding loopback device: {e}")
            return None

    def start(self):
        """Start capturing system audio."""
        with self._lock:
            if self._running:
                return

            self._running = True
            
            self._thread = threading.Thread(target=self._capture_thread, daemon=True)
            self._thread.start()
            print("[INFO] Audio capture started")

    def _capture_thread(self):
        """Background thread to poll soundcard blocking read."""
        device = self._find_loopback_device()
        if device is None:
            print("[ERROR] No audio device available for capture.")
            self._running = False
            return

        print(f"[INFO] Using audio device: {device.name}")

        num_frames = int(config.AUDIO_SAMPLE_RATE * config.AUDIO_CHUNK_DURATION)
        
        try:
            # Note: soundcard will automatically resample and downmix to mono if we request channels=1.
            with device.recorder(samplerate=config.AUDIO_SAMPLE_RATE, channels=1) as mic:
                while self._running:
                    # Blocking read
                    data = mic.record(numframes=num_frames)
                    
                    if not self._running:
                        break

                    # data is (frames, channels), we want a flat mono array
                    audio = data.flatten().astype(np.float32)

                    try:
                        self._queue.put_nowait(audio)
                    except queue.Full:
                        pass  # Drop oldest if queue is full

        except Exception as e:
            print(f"[ERROR] Audio capture thread crashed: {e}")
            self._running = False

    def stop(self):
        """Stop capturing audio."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            print("[INFO] Audio capture stopped")

    def get_chunk(self, timeout: float = None) -> np.ndarray | None:
        """
        Get the next audio chunk from the queue.

        Args:
            timeout: Seconds to wait. None = block forever. 0 = non-blocking.

        Returns:
            NumPy array of audio samples, or None if timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_running(self) -> bool:
        return self._running
