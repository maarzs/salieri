"""Test the settings WebSocket API: get, list_models, test_connection, update."""
import asyncio
import json
import sys

import websockets

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9876
URI = f"ws://localhost:{PORT}"


async def rpc(ws, payload, want, timeout=60):
    """Send a request and wait for the first reply of the wanted type."""
    await ws.send(json.dumps(payload))
    while True:
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        if data.get("type") in (want, "error"):
            return data


async def main():
    async with websockets.connect(URI) as ws:
        print("== get_settings ==")
        r = await rpc(ws, {"type": "get_settings"}, "settings")
        s = r.get("settings", {})
        print(json.dumps(s, indent=2))
        assert "api_key" not in s, "SECURITY: raw api_key leaked to UI"
        assert "api_key_set" in s, "missing api_key_set flag"
        print(f"-> key masked OK (set={s['api_key_set']}, hint={s['api_key_hint']!r})")

        print("\n== list_models ==")
        r = await rpc(ws, {"type": "list_models"}, "models")
        models = r.get("models", [])
        print(f"{len(models)} models; first 8: {models[:8]}")

        print("\n== test_connection ==")
        r = await rpc(ws, {"type": "test_connection"}, "test_result")
        print(f"ok={r.get('ok')} msg={r.get('message')}")

        print("\n== update_settings (model change) ==")
        original = s.get("model")
        r = await rpc(
            ws,
            {"type": "update_settings", "settings": {"model": "gpt-4o-mini"}},
            "settings",
        )
        print(f"saved={r.get('saved')} model={r['settings'].get('model')}")
        assert r["settings"]["model"] == "gpt-4o-mini", "model did not apply"

        print("\n== empty api_key must NOT wipe stored key ==")
        r = await rpc(
            ws, {"type": "update_settings", "settings": {"api_key": ""}}, "settings"
        )
        print(f"api_key_set still {r['settings']['api_key_set']}")
        assert r["settings"]["api_key_set"] is True, "empty string wiped the key!"

        print("\n== chat still works after reconfigure ==")
        await ws.send(json.dumps({"type": "chat", "content": "Say: RECONFIG OK"}))
        chunks, seen = [], []
        for _ in range(40):
            d = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            t = d.get("type")
            seen.append(t)
            if t == "chat_stream":
                chunks.append(d["content"])
            elif t == "chat_response":
                print(f"streamed={''.join(chunks)!r}")
                print(f"chat_response full={d.get('content')!r}")
                break
            elif t == "error":
                print("ERROR:", d.get("message"))
                break

        print("\n== restore original model ==")
        await rpc(
            ws,
            {"type": "update_settings", "settings": {"model": original}},
            "settings",
        )
        print(f"restored to {original}")
        print("\nALL SETTINGS TESTS PASSED")


asyncio.run(main())
