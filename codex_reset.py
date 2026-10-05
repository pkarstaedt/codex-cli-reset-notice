#!/usr/bin/env python3
"""One visible Codex SessionStart notice, using the public reset forecast."""

import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = "https://codex-reset.com/api/forecast"
USER_AGENT = "codex-reset-session-hook/1.0 (personal CLI integration; source https://codex-reset.com/)"
ZONE = ZoneInfo("UTC")
UNAVAILABLE = "Cannot get usage reset news from https://codex-reset.com"
SOURCE = " Source: https://codex-reset.com/"


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Expected an ISO timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def display_zone():
    zone_name = os.environ.get("CODEX_RESET_TIMEZONE")
    return ZoneInfo(zone_name) if zone_name else ZONE


def day(value):
    return value.astimezone(display_zone()).strftime("%d-%m")


def date_time(value):
    return value.astimezone(display_zone()).strftime("%d-%m %H:%M %Z")


def notice(data, now):
    """Pure message selection; unknown or stale data raises ValueError."""
    if not isinstance(data, dict) or not {"updated_at", "official_signal", "last_reset_at"} <= data.keys():
        raise ValueError("Unsupported forecast")
    age = now - timestamp(data["updated_at"])
    if not -timedelta(seconds=60) <= age <= timedelta(minutes=5):
        raise ValueError("Stale forecast")
    last = timestamp(data["last_reset_at"]) if data["last_reset_at"] is not None else None
    if last and last > now:
        raise ValueError("Future completed reset")
    signal = data["official_signal"]
    if signal is not None:
        if not isinstance(signal, dict):
            raise ValueError("Unsupported official signal")
        announced = timestamp(signal.get("at"))
        if announced > now:
            raise ValueError("Future announcement")
        if signal.get("active") is not False and (last is None or announced > last):
            window = signal.get("window")
            if window is None:
                return f"Global Codex usage reset announced on {day(announced)}; timing unspecified." + SOURCE
            if not isinstance(window, dict):
                raise ValueError("Unsupported announcement window")
            end = timestamp(window.get("end_at"))
            if end > now:
                label = str(window.get("label", ""))
                if "timing unspecified" in label.lower():
                    return f"Global Codex usage reset announced on {day(announced)}; timing unspecified." + SOURCE
                target = timestamp(window.get("target_at") or window["end_at"])
                if window.get("target_at"):
                    if window.get("target_kind") == "deadline":
                        return f"Global Codex usage reset announced to arrive by {date_time(target)}; announced on {day(announced)}." + SOURCE
                    target_info = date_time(target)
                else:
                    start = timestamp(window.get("start_at"))
                    if start > end:
                        raise ValueError("Inverted window")
                    if label.strip().lower() in {"today", "tomorrow", "later today", "later tomorrow", "next week"}:
                        target_info = day(end) if start.astimezone(display_zone()).date() == end.astimezone(display_zone()).date() else f"{day(start)} to {day(end)}"
                    else:
                        target_info = f"{date_time(start)} to {date_time(end)}"
                return f"Global Codex usage reset announced for {target_info}; announced on {day(announced)}." + SOURCE
    if last and now - last <= timedelta(hours=72):
        return f"Last Codex usage reset was on {day(last)}."
    return "No Codex usage reset planned."


def write_json(path, data):
    """Atomic replacement, including when several Codex sessions open together."""
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def retry_seconds(value, now):
    try:
        return max(60, int(value))
    except (TypeError, ValueError):
        try:
            return max(60, (parsedate_to_datetime(value).timestamp() - now))
        except (TypeError, ValueError, OverflowError):
            return 60


def fetch(now):
    request = Request(API, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=3) as response:
            payload = response.read(262145)
            if len(payload) > 262144:
                raise ValueError("Oversized forecast")
            data = json.loads(payload)
            checked = response.headers.get("x-published-checked-at")
            expires = response.headers.get("x-published-expires-at")
            if checked and now - timestamp(checked) > timedelta(minutes=5):
                raise ValueError("Stale published copy")
            if expires and timestamp(expires) <= now:
                raise ValueError("Expired published copy")
            notice(data, now)  # Validate before retaining it.
            return {"data": data, "fetched_at": time.time(), "retry_at": 0}
    except HTTPError as exc:
        if exc.code != 429:
            raise
        current = time.time()
        return {"data": None, "fetched_at": current,
                "retry_at": current + retry_seconds(exc.headers.get("Retry-After"), current)}


def get_notice(cache_dir=None):
    cache_dir = cache_dir or Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "codex-reset-session-hook"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / "forecast.json"
    with (cache_dir / "forecast.lock").open("a") as lock:
        deadline = time.monotonic() + 0.4
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return UNAVAILABLE
                time.sleep(0.02)
        now = datetime.now(timezone.utc)
        try:
            entry = json.loads(cache.read_text())
        except (OSError, ValueError):
            entry = {}
        recent = 0 <= now.timestamp() - entry.get("fetched_at", 0) < 60
        if entry.get("retry_at", 0) > now.timestamp():
            return UNAVAILABLE
        if not recent:
            # Persist failure cooldown before networking so failures cannot cause rapid polling.
            write_json(cache, {"data": None, "fetched_at": now.timestamp(), "retry_at": 0})
            entry = fetch(now)
            write_json(cache, entry)
        return notice(entry["data"], now) if entry.get("data") is not None else UNAVAILABLE


def main():
    try:
        event = json.load(sys.stdin)
        if event.get("hook_event_name") != "SessionStart" or event.get("source") not in {"startup", "resume", "clear"}:
            return
        message = get_notice()
    except Exception:
        message = UNAVAILABLE
    print(json.dumps({"systemMessage": message}))


if __name__ == "__main__":
    main()
