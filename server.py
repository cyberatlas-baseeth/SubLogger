"""
SubLogger - WebSocket Server
Receives subtitle data from the Chrome extension in real-time.
"""

import asyncio
import json
import websockets

import config
from pipeline import Pipeline


class SubtitleServer:
    """
    Async WebSocket server that receives subtitle data from browser extensions.
    Messages are expected as JSON: {"text": "...", "timestamp": "...", "url": "..."}
    """

    def __init__(self, pipeline: Pipeline):
        self._pipeline = pipeline
        self._clients: set = set()
        self._server = None

    async def _handler(self, websocket):
        """Handle a single WebSocket connection."""
        self._clients.add(websocket)
        remote = websocket.remote_address
        print(f"[INFO] Extension connected: {remote}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    text = data.get("text", "")
                    url = data.get("url", "")
                    ts = data.get("timestamp", "")

                    if text:
                        result = self._pipeline.process_subtitle(text)
                        if result:
                            print(
                                f"[SUB] {result['original_text']}"
                                + (f" → {result['final_text']}" if result["translated"] else "")
                            )

                            # Send acknowledgment back to extension
                            ack = json.dumps({
                                "type": "ack",
                                "processed": True,
                                "translated": result["translated"],
                            })
                            await websocket.send(ack)

                except json.JSONDecodeError:
                    print(f"[WARN] Invalid JSON from extension: {message[:100]}")
                except Exception as e:
                    print(f"[ERROR] Processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[INFO] Extension disconnected: {remote}")

    async def start(self):
        """Start the WebSocket server."""
        self._server = await websockets.serve(
            self._handler,
            config.WS_HOST,
            config.WS_PORT,
        )
        print(f"[INFO] WebSocket server running on ws://{config.WS_HOST}:{config.WS_PORT}")
        return self._server

    async def stop(self):
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            print("[INFO] WebSocket server stopped")

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def has_clients(self) -> bool:
        return len(self._clients) > 0
