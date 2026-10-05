#!/usr/bin/env python3
"""Verify native Codex installation AND hook discovery in an isolated home."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading


def verify(source):
    with tempfile.TemporaryDirectory(prefix="codex-reset-verify-") as temporary:
        env = {**os.environ, "CODEX_HOME": temporary}
        for args in [("marketplace", "add", source),
                     ("add", "codex-cli-reset-notice@codex-cli-reset-notices")]:
            subprocess.run(["codex", "plugin", *args, "--json"], env=env,
                           check=True, capture_output=True, text=True, timeout=60)
        process = subprocess.Popen(["codex", "app-server", "--stdio"], env=env,
            cwd=temporary, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
        messages = queue.Queue()

        def read():
            for line in process.stdout:
                try:
                    messages.put(json.loads(line))
                except ValueError:
                    pass

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def rpc(identifier, method, params):
            process.stdin.write(json.dumps({"id": identifier, "method": method,
                                           "params": params}) + "\n")
            process.stdin.flush()
            while True:
                message = messages.get(timeout=20)
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message["result"]

        try:
            rpc(1, "initialize", {"clientInfo": {"name": "reset-hook-verification", "version": "1.0"},
                                  "capabilities": {"experimentalApi": True}})
            result = rpc(2, "hooks/list", {"cwds": [temporary]})
            entry = result["data"][0]
            assert not entry["errors"], entry["errors"]
            hooks = [h for h in entry["hooks"] if h.get("pluginId") ==
                     "codex-cli-reset-notice@codex-cli-reset-notices"]
            assert len(hooks) == 1, f"Expected one plugin hook, got {hooks}"
            hook = hooks[0]
            assert hook["eventName"] == "sessionStart" and hook["enabled"]
            assert hook["trustStatus"] == "untrusted"
            assert hook["matcher"] == "^(startup|resume|clear)$"
            assert "${PLUGIN_ROOT}" not in hook["command"]
            print("PASS: SessionStart hook discovered, enabled, and awaiting trust.")
        finally:
            process.terminate()
            process.wait(timeout=5)
            reader.join(timeout=1)
            process.stdin.close()
            process.stdout.close()
        subprocess.run(["codex", "plugin", "remove",
            "codex-cli-reset-notice@codex-cli-reset-notices"], env=env,
            check=True, capture_output=True, timeout=30)


if __name__ == "__main__":
    import sys
    verify(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent))
