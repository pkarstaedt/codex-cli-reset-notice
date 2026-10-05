import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import codex_reset as hook


class NoticeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 4, 14, tzinfo=timezone.utc)
        self.data = {"updated_at": self.now.isoformat(), "official_signal": None,
                     "last_reset_at": "2026-10-02T21:18:48Z"}

    def message(self):
        return hook.notice(self.data, self.now).removesuffix(hook.SOURCE)

    def signal(self, **changes):
        signal = {"at": "2026-10-04T01:00:00Z", "window": {
            "start_at": "2026-10-05T08:00:00Z", "end_at": "2026-10-05T10:00:00Z",
            "target_at": "2026-10-05T10:00:00Z", "label": "tomorrow"}}
        signal.update(changes)
        self.data["official_signal"] = signal
        return signal

    def test_recent_reset(self):
        self.assertEqual(self.message(), "Last reset was on 02-10.")

    def test_exact_72_hours(self):
        self.data["last_reset_at"] = (self.now - timedelta(hours=72)).isoformat()
        self.assertTrue(self.message().startswith("Last reset"))
        self.data["last_reset_at"] = (self.now - timedelta(hours=72, seconds=1)).isoformat()
        self.assertEqual(self.message(), "No reset planned.")

    def test_no_reset(self):
        self.data["last_reset_at"] = None
        self.assertEqual(self.message(), "No reset planned.")

    def test_upcoming_wins(self):
        self.signal()
        self.assertEqual(self.message(), "Global reset announced for 05-10 on 04-10.")

    def test_expired_is_not_completion(self):
        s = self.signal()
        s["window"]["end_at"] = self.now.isoformat()
        self.assertEqual(self.message(), "Last reset was on 02-10.")

    def test_completed_supersedes_signal(self):
        self.signal(at="2026-10-01T12:00:00Z")
        self.assertEqual(self.message(), "Last reset was on 02-10.")

    def test_unspecified_timing(self):
        self.signal(window=None)
        self.assertEqual(self.message(), "Global reset announced on 04-10; timing unspecified.")
        self.signal()["window"]["label"] = "official hint — timing unspecified"
        self.assertEqual(self.message(), "Global reset announced on 04-10; timing unspecified.")

    def test_inactive(self):
        self.signal(active=False)
        self.assertEqual(self.message(), "Last reset was on 02-10.")

    def test_range(self):
        s = self.signal()
        s["window"].pop("target_at")
        s["window"]["start_at"] = "2026-10-04T21:00:00Z"
        self.assertEqual(self.message(), "Global reset announced for 04-10 to 05-10 on 04-10.")

    def test_berlin_midnight_and_dst(self):
        for raw, expected in [("2026-10-02T23:00:00Z", "03-10"),
                              ("2026-10-25T00:30:00Z", "25-10"),
                              ("2026-10-25T01:30:00Z", "25-10"),
                              ("2026-12-31T23:30:00Z", "01-01")]:
            self.assertEqual(hook.day(hook.timestamp(raw)), expected)

    def test_timezone_override(self):
        with patch.dict("os.environ", {"CODEX_RESET_TIMEZONE": "America/New_York"}):
            self.assertEqual(hook.day(hook.timestamp("2026-10-03T01:00:00Z")), "02-10")
            s = self.signal()
            s["window"].pop("target_at")
            s["window"]["start_at"] = "2026-10-05T02:00:00Z"
            s["window"]["end_at"] = "2026-10-05T05:00:00Z"
            self.assertEqual(self.message(), "Global reset announced for 04-10 to 05-10 on 03-10.")

    def test_banked_and_probability_ignored(self):
        self.data.update(probabilities={"rounded_24h": 99}, banked_state="available")
        self.assertEqual(self.message(), "Last reset was on 02-10.")

    def test_stale_and_unsupported(self):
        for data in [{}, [], {**self.data, "official_signal": "unknown"},
                     {**self.data, "last_reset_at": "2026-10-05T00:00:00Z"},
                     {**self.data, "updated_at": (self.now-timedelta(minutes=6)).isoformat()}]:
            with self.assertRaises(ValueError):
                hook.notice(data, self.now)


class RuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("codex"), "Codex CLI is required for hook discovery verification")
    def test_native_plugin_hook_discovery(self):
        from verify_plugin import verify
        verify(str(Path(__file__).resolve().parent))

    def test_fetch_stale_malformed_and_rate_limited(self):
        now = datetime.now(timezone.utc)
        class Response:
            headers = {}
            body = b"invalid JSON"
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return self.body
        response = Response()
        with patch.object(hook, "urlopen", return_value=response):
            with self.assertRaises(ValueError):
                hook.fetch(now)
            response.body = json.dumps({"updated_at": now.isoformat(),
                "last_reset_at": None, "official_signal": None}).encode()
            response.headers = {"x-published-expires-at": (now-timedelta(seconds=1)).isoformat()}
            with self.assertRaises(ValueError):
                hook.fetch(now)
        error = HTTPError(hook.API, 429, "limited", {"Retry-After": "120"}, None)
        with patch.object(hook, "urlopen", side_effect=error):
            entry = hook.fetch(now)
            self.assertIsNone(entry["data"])
            self.assertEqual(entry["retry_at"] - entry["fetched_at"], 120)

    def test_concurrent_fetch_only_once(self):
        import time
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as root:
            now = datetime.now(timezone.utc)
            entry = {"data": {"updated_at": now.isoformat(), "official_signal": None,
                "last_reset_at": None}, "fetched_at": now.timestamp(), "retry_at": 0}
            def slow_fetch(_):
                time.sleep(0.1)
                return entry
            with patch.object(hook, "fetch", side_effect=slow_fetch) as fetch:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    messages = list(pool.map(lambda _: hook.get_notice(Path(root)), range(3)))
                self.assertTrue(all("No reset planned" in message for message in messages))
                self.assertEqual(fetch.call_count, 1)

    def test_cache_and_failure_cooldown(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            now = datetime.now(timezone.utc)
            entry = {"data": {"updated_at": now.isoformat(), "official_signal": None,
                              "last_reset_at": None}, "fetched_at": now.timestamp(), "retry_at": 0}
            with patch.object(hook, "fetch", return_value=entry) as fetch:
                self.assertIn("No reset planned", hook.get_notice(folder))
                self.assertIn("No reset planned", hook.get_notice(folder))
                self.assertEqual(fetch.call_count, 1)
            (folder / "forecast.json").unlink()
            with patch.object(hook, "fetch", side_effect=TimeoutError) as fetch:
                with self.assertRaises(TimeoutError):
                    hook.get_notice(folder)
                self.assertEqual(hook.get_notice(folder), hook.UNAVAILABLE)
                self.assertEqual(fetch.call_count, 1)

    def test_retry_after(self):
        self.assertEqual(hook.retry_seconds("120", 0), 120)
        self.assertEqual(hook.retry_seconds("Sun, 04 Oct 2026 14:02:00 GMT", 1791122400), 120)
        self.assertEqual(hook.retry_seconds("nonsense", 0), 60)

    def test_rate_limit_cache(self):
        with tempfile.TemporaryDirectory() as root:
            entry = {"data": None, "fetched_at": 0,
                     "retry_at": datetime.now(timezone.utc).timestamp() + 120}
            hook.write_json(Path(root) / "forecast.json", entry)
            with patch.object(hook, "fetch") as fetch:
                self.assertEqual(hook.get_notice(Path(root)), hook.UNAVAILABLE)
                fetch.assert_not_called()

    def test_hook_output_and_skipped_events(self):
        for source in ["startup", "resume", "clear", "compact"]:
            with patch("sys.stdin", io.StringIO(json.dumps({"hook_event_name": "SessionStart", "source": source}))), patch.object(hook, "get_notice", return_value="example"), contextlib.redirect_stdout(io.StringIO()) as out:
                hook.main()
                self.assertEqual(out.getvalue().strip(), json.dumps({"systemMessage": "example"}) if source != "compact" else "")
        for raw in ["bad json", '{"hook_event_name":"SessionStart","source":"startup"}']:
            with patch("sys.stdin", io.StringIO(raw)), patch.object(hook, "get_notice", side_effect=TimeoutError), contextlib.redirect_stdout(io.StringIO()) as out:
                hook.main()
                self.assertEqual(json.loads(out.getvalue())["systemMessage"], hook.UNAVAILABLE)

    def test_install_twice_and_remove_preserves_existing(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "hooks.json"
            original = {"description": "existing", "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "original"}]}], "Stop": []}}
            hook.write_json(config, original)
            import os
            env = {**os.environ, "CODEX_HOME": root}
            for _ in range(2):
                subprocess.run(["python3", "install.py"], check=True, env=env, capture_output=True)
            self.assertEqual(len(json.loads(config.read_text())["hooks"]["SessionStart"]), 2)
            subprocess.run(["python3", "install.py", "--remove"], check=True, env=env, capture_output=True)
            self.assertEqual(json.loads(config.read_text()), original)
            self.assertEqual(len(list(Path(root).glob("hooks.json.backup-*"))), 2)


if __name__ == "__main__":
    unittest.main()
