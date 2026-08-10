"""Test the full Salieri backend pipeline via WebSocket."""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import websockets


async def test():
    uri = "ws://localhost:9876"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected!")

            # Send chat
            msg = {"type": "chat", "content": "What do you think about consciousness? Can an AI truly be conscious?"}
            print(f"\nSending: {msg['content']}")
            await ws.send(json.dumps(msg))

            # Read all responses
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    data = json.loads(raw)
                    t = data.get("type", "")

                    if t == "chat_stream":
                        print(data.get("content", ""), end="", flush=True)
                    elif t == "stream_end":
                        print("\n\n--- Stream complete ---")
                    elif t == "chat_response":
                        print(f"\n[Emotion: {data.get('emotion')}]")
                    elif t == "tts_audio":
                        print(f"[TTS audio: {len(data.get('audio', ''))} chars]")
                    elif t == "tts_done":
                        print("[TTS done]")
                        return
                    elif t == "error":
                        print(f"\nERROR: {data.get('message')}")
                        return
                    else:
                        print(f"\n[{t}]")
                except asyncio.TimeoutError:
                    print("\nTimeout - no more messages")
                    break

    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure the backend is running: cd backend && python server.py")


if __name__ == "__main__":
    asyncio.run(test())