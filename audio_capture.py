"""
SubLogger - Audio Capture Module
System audio loopback capture using sounddevice with WASAPI on Windows.
"""

import threading
import queue
import numpy as np
import sounddevice as sd

import config


class AudioCapture:
    """
    Captures system audio via WASAPI loopback (Windows) or default input.
    Records audio in chunks and pushes them to a queue for processing.
    """

    def __init__(self):
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=50)
        self._stream: sd.InputStream | None = None
        self._running = False
        self._lock = threading.Lock()

    def _find_loopback_device(self) -> int | None:
        """Find a WASAPI loopback device on Windows."""
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()

            # Find WASAPI host API index
            wasapi_idx = None
            for i, api in enumerate(hostapis):
                if "WASAPI" in api["name"]:
                    wasapi_idx = i
                    break

            if wasapi_idx is None:
                return None

            # Find a loopback device in WASAPI
            for i, dev in enumerate(devices):
                if dev["hostapi"] == wasapi_idx and dev["max_input_channels"] > 0:
                    name = dev["name"].lower()
                    if "loopback" in name or "stereo mix" in name:
                        return i

            # Fallback: use default WASAPI output as loopback
            default_output = hostapis[wasapi_idx].get("default_output_device")
            if default_output is not None and default_output >= 0:
                return default_output

        except Exception as e:
            print(f"[WARN] Error finding loopback device: {e}")

        return None

    def start(self):
        """Start capturing system audio."""
        with self._lock:
            if self._running:
                return

            device = self._find_loopback_device()
            extra_settings = None

            if device is not None:
                try:
                    # Try to use WASAPI loopback
                    extra_settings = sd.WasapiSettings(exclusive=False)
                    print(f"[INFO] Using WASAPI loopback device: {sd.query_devices(device)['name']}")
                except Exception:
                    device = None
                    extra_settings = None
                    print("[WARN] WASAPI not available, using default input device")

            if device is None:
                print("[INFO] Using default audio input device")

            try:
                self._stream = sd.InputStream(
                    device=device,
                    samplerate=config.AUDIO_SAMPLE_RATE,
                    channels=config.AUDIO_CHANNELS,
                    dtype="float32",
                    blocksize=int(config.AUDIO_SAMPLE_RATE * config.AUDIO_CHUNK_DURATION),
                    callback=self._audio_callback,
                    extra_settings=extra_settings,
                )
                self._stream.start()
                self._running = True
                print("[INFO] Audio capture started")
            except Exception as e:
                print(f"[ERROR] Failed to start audio capture: {e}")
                self._running = False

    def stop(self):
        """Stop capturing audio."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            print("[INFO] Audio capture stopped")

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Callback invoked by sounddevice for each audio chunk."""
        if status:
            print(f"[WARN] Audio status: {status}")
        if self._running:
            # Copy to avoid buffer reuse issues
            try:
                self._queue.put_nowait(indata.copy().flatten())
            except queue.Full:
                pass  # Drop oldest if queue is full

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
