#!/usr/bin/env python3
"""Install or remove the single user hook without changing other hooks or trust."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil

from codex_reset import write_json

parser = argparse.ArgumentParser()
parser.add_argument("--remove", action="store_true")
args = parser.parse_args()
home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
target = home / "hooks" / "codex_reset.py"
config = home / "hooks.json"
command = "python3 " + shlex.quote(str(target))
handler = {"type": "command", "command": command, "timeout": 5,
           "statusMessage": "Checking global reset status"}
group = {"matcher": "^(startup|resume|clear)$", "hooks": [handler]}
home.mkdir(parents=True, exist_ok=True)
data = json.loads(config.read_text()) if config.exists() else {"hooks": {}}
groups = data.setdefault("hooks", {}).setdefault("SessionStart", [])
changed = False
if args.remove:
    for item in groups[:]:
        remaining = [h for h in item.get("hooks", []) if h.get("command") != command]
        if len(remaining) != len(item.get("hooks", [])):
            changed = True
            if remaining:
                item["hooks"] = remaining
            else:
                groups.remove(item)
else:
    target.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("codex_reset.py")
    if not target.exists() or target.read_bytes() != source.read_bytes():
        shutil.copy2(source, target)
    if group not in groups:
        if any(h.get("command") == command for item in groups for h in item.get("hooks", [])):
            raise SystemExit("Existing reset hook differs; remove it before reinstalling.")
        groups.append(group)
        changed = True
if changed:
    if config.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = config.with_name("hooks.json.backup-" + stamp)
        shutil.copy2(config, backup)
        print("Backup:", backup)
    write_json(config, data)
if args.remove:
    target.unlink(missing_ok=True)
    print("Removed reset hook; other hooks preserved.")
else:
    print("Installed:", target)
    print("Review and trust this hook using /hooks in Codex.")
