"""
SubLogger - Main Entry Point
Starts the WebSocket server and audio capture engine.
CLI interface with mode selection.
"""

import asyncio
import argparse
import signal
import sys
import time
import threading

import config
from logger import SubLogger
from pipeline import Pipeline
from server import SubtitleServer
from audio_capture import AudioCapture
from transcriber import transcribe_audio


def parse_args():
    parser = argparse.ArgumentParser(
        description="SubLogger - Real-time subtitle capture and audio transcription",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Start in hybrid mode (default)
  python main.py --mode subtitle     # Subtitle-only mode
  python main.py --mode audio        # Audio-only mode
  python main.py --model small       # Use Whisper 'small' model
  python main.py --port 9000         # Custom WebSocket port
  python main.py --tail              # Show recent log entries
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["hybrid", "subtitle", "audio"],
        default="hybrid",
        help="Operating mode (default: hybrid)",
    )
    parser.add_argument(
        "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)",
    )
    parser.add_argument(
        "--tail",
        action="store_true",
        help="Show recent log entries and exit",
    )
    parser.add_argument(
        "--tail-n",
        type=int,
        default=20,
        help="Number of log entries to show with --tail (default: 20)",
    )
    return parser.parse_args()


def show_tail(n: int):
    """Show the last N log entries."""
    sub_logger = SubLogger()
    entries = sub_logger.get_entries(last_n=n)
    if not entries:
        print("No log entries found.")
        return
    print(f"\n{'='*60}")
    print(f" Last {len(entries)} log entries")
    print(f"{'='*60}\n")
    for entry in entries:
        arrow = " → " if entry["translated"] else ""
        final = entry["final_text"] if entry["translated"] else ""
        print(
            f"[{entry['timestamp_display']}] "
            f"({entry['source']}) "
            f"{entry['original_text']}{arrow}{final}"
        )
    print()


def audio_worker(pipeline: Pipeline, audio: AudioCapture, stop_event: threading.Event):
    """
    Background thread that captures audio and transcribes it.
    Only active when the pipeline decides audio fallback is needed.
    """
    print("[INFO] Audio worker thread started")

    while not stop_event.is_set():
        try:
            # Check if we should be capturing audio
            if not pipeline.should_use_audio_fallback():
                # Subtitles are active, pause audio
                if audio.is_running:
                    audio.stop()
                stop_event.wait(timeout=1.0)
                continue

            # Start audio capture if not already running
            if not audio.is_running:
                audio.start()

            # Get audio chunk
            chunk = audio.get_chunk(timeout=1.0)
            if chunk is None:
                continue

            # Skip very quiet audio (likely silence)
            rms = float((chunk ** 2).mean() ** 0.5)
            if rms < 0.001:
                continue

            # Transcribe
            result = transcribe_audio(chunk)
            if result["text"]:
                entry = pipeline.process_audio_transcription(result)
                if entry:
                    print(
                        f"[AUD] {entry['original_text']}"
                        + (f" → {entry['final_text']}" if entry["translated"] else "")
                    )

        except Exception as e:
            print(f"[ERROR] Audio worker error: {e}")
            stop_event.wait(timeout=2.0)

    # Cleanup
    if audio.is_running:
        audio.stop()
    print("[INFO] Audio worker thread stopped")


async def main_async(args):
    """Main async entry point."""
    # Apply config overrides from CLI
    config.MODE = args.mode
    config.WHISPER_MODEL = args.model
    config.WS_PORT = args.port

    # Initialize components
    sub_logger = SubLogger()
    pipeline = Pipeline(sub_logger)
    ws_server = SubtitleServer(pipeline)
    audio = AudioCapture()
    stop_event = threading.Event()

    # Print banner
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║             SubLogger MVP v1.0.0                ║")
    print("║  Real-time Subtitle & Audio Transcription       ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Mode:    {config.MODE:<39}║")
    print(f"║  Whisper: {config.WHISPER_MODEL:<39}║")
    print(f"║  Port:    {config.WS_PORT:<39}║")
    print(f"║  Logs:    {config.LOG_DIR:<39}║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # Start WebSocket server
    if config.MODE in ("hybrid", "subtitle"):
        await ws_server.start()

    # Start audio worker thread
    audio_thread = None
    if config.MODE in ("hybrid", "audio"):
        audio_thread = threading.Thread(
            target=audio_worker,
            args=(pipeline, audio, stop_event),
            daemon=True,
        )
        audio_thread.start()

    # Graceful shutdown handler
    shutdown_event = asyncio.Event()

    def _signal_handler():
        print("\n[INFO] Shutting down...")
        stop_event.set()
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    # Status printer
    async def status_printer():
        while not shutdown_event.is_set():
            await asyncio.sleep(30)
            if not shutdown_event.is_set():
                entries = sub_logger.get_entries()
                clients = ws_server.client_count if config.MODE != "audio" else 0
                audio_status = "running" if audio.is_running else "stopped"
                print(
                    f"[STATUS] Entries: {len(entries)} | "
                    f"Clients: {clients} | "
                    f"Audio: {audio_status}"
                )

    status_task = asyncio.create_task(status_printer())

    print("[INFO] SubLogger is running. Press Ctrl+C to stop.\n")

    # Wait for shutdown
    try:
        await shutdown_event.wait()
    except KeyboardInterrupt:
        _signal_handler()

    # Cleanup
    status_task.cancel()
    await ws_server.stop()
    stop_event.set()
    if audio_thread and audio_thread.is_alive():
        audio_thread.join(timeout=5)

    print("[INFO] SubLogger stopped. Goodbye!")


def main():
    args = parse_args()

    if args.tail:
        show_tail(args.tail_n)
        return

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted. Goodbye!")


if __name__ == "__main__":
    main()
