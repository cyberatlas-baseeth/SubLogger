import sounddevice as sd
import numpy as np

device = 13  # WASAPI headphones
channels = 2

try:
    print(f"Opening WASAPI loopback on device {device} with {channels} channels...")
    settings = sd.WasapiSettings(loopback=True)
    with sd.InputStream(
        device=device,
        channels=channels,
        samplerate=44100,  # try 44100 first
        extra_settings=settings
    ) as stream:
        print("Success! Reading 10 frames...")
        data, overflow = stream.read(10)
        print("Data shape:", data.shape)
except Exception as e:
    print("FAILED:", e)
