import sounddevice as sd

with open("devices_utf8.txt", "w", encoding="utf-8") as f:
    f.write("--- Host APIs ---\n")
    for i, api in enumerate(sd.query_hostapis()):
        f.write(f"[{i}] {api['name']}\n")
    f.write("\n--- Devices ---\n")
    for i, dev in enumerate(sd.query_devices()):
        f.write(f"[{i}] {dev['name']} - IN: {dev['max_input_channels']}, OUT: {dev['max_output_channels']}, API: {dev['hostapi']}\n")
