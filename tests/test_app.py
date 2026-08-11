import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import app


class ProgressStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = app.DATA_DIR
        self.original_progress_file = app.PROGRESS_FILE
        app.DATA_DIR = Path(self.temp_dir.name)
        app.PROGRESS_FILE = app.DATA_DIR / "progress.json"

    def tearDown(self):
        app.DATA_DIR = self.original_data_dir
        app.PROGRESS_FILE = self.original_progress_file
        self.temp_dir.cleanup()

    def test_atomic_round_trip(self):
        progress = app.empty_progress()
        progress["solved"]["two-sum"] = "2026-08-11 10:00:00"

        app.save_progress(progress)

        self.assertEqual(app.load_progress(), progress)
        self.assertEqual(list(app.DATA_DIR.glob("*.tmp")), [])
        json.loads(app.PROGRESS_FILE.read_text(encoding="utf-8"))

    def test_concurrent_updates_do_not_lose_data(self):
        thread_count = 40
        errors = []

        def worker(index):
            try:
                def mutate(progress):
                    progress["solved"][f"problem-{index}"] = str(index)

                app.update_progress(mutate)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(index,))
                   for index in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(app.load_progress()["solved"]), thread_count)

    def test_corrupt_progress_is_quarantined_before_update(self):
        app.PROGRESS_FILE.write_text("{broken json", encoding="utf-8")

        app.update_progress(lambda progress: progress["solved"].update({"two-sum": "now"}))

        self.assertEqual(app.load_progress()["solved"], {"two-sum": "now"})
        backups = list(app.DATA_DIR.glob("progress.corrupt-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "{broken json")

    def test_malformed_nested_progress_is_normalized(self):
        app.PROGRESS_FILE.write_text(json.dumps({
            "solved": {},
            "wrong": {"bad": "not-a-record"},
            "notes": {"bad": "not-a-list", "ok": [{"q": "q"}, "bad-item"]},
        }), encoding="utf-8")

        progress = app.load_progress()

        self.assertEqual(progress["wrong"], {})
        self.assertEqual(progress["notes"], {"ok": [{"q": "q"}]})


class RequestBodyTest(unittest.TestCase):
    def make_handler(self, raw, declared_length=None):
        class FakeHandler:
            pass

        handler = FakeHandler()
        length = len(raw) if declared_length is None else declared_length
        handler.headers = {"Content-Length": str(length)}
        handler.rfile = io.BytesIO(raw)
        return handler

    def test_reads_json_object(self):
        raw = b'{"id":"two-sum"}'
        handler = self.make_handler(raw)

        body = app.Handler._read_body(handler)

        self.assertEqual(body, {"id": "two-sum"})

    def test_rejects_invalid_json(self):
        handler = self.make_handler(b"not json")
        with self.assertRaises(ValueError):
            app.Handler._read_body(handler)

    def test_rejects_oversized_request(self):
        handler = self.make_handler(b"{}", app.MAX_REQUEST_BYTES + 1)
        with self.assertRaises(OverflowError):
            app.Handler._read_body(handler)

    def test_submit_rejects_non_string_fields(self):
        class FakeHandler:
            def __init__(self):
                self.response = None

            def _send_json(self, payload, status=200):
                self.response = (payload, status)

        handler = FakeHandler()
        app.Handler._handle_submit(handler, {"id": [], "code": {}})

        self.assertEqual(handler.response[1], 400)
        self.assertIn("必须是字符串", handler.response[0]["error"])


class LlmErrorTest(unittest.TestCase):
    def test_http_error_redacts_api_key(self):
        api_key = "sk-secret-value"
        error = HTTPError(
            "https://example.test/chat/completions",
            401,
            "unauthorized",
            {},
            io.BytesIO(f"invalid key: {api_key}".encode("utf-8")),
        )
        config = {
            "api_key": api_key,
            "base_url": "https://example.test",
            "model": "test-model",
        }

        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as context:
                app.call_llm(config, [{"role": "user", "content": "hello"}])

        self.assertNotIn(api_key, str(context.exception))
        self.assertIn("[REDACTED]", str(context.exception))


class FrontendContractTest(unittest.TestCase):
    def test_security_error_and_draft_contracts_are_present(self):
        html = Path("static/index.html").read_text(encoding="utf-8")

        self.assertIn('.replace(/"/g, "&quot;")', html)
        self.assertIn("if (!resp.ok) throw new Error", html)
        self.assertIn("localStorage.setItem(draftKey(state.problem.id), editor.value)", html)
        self.assertIn("p.saved_code || p.starter", html)

    def test_security_headers_are_defined(self):
        class FakeHandler:
            def __init__(self):
                self.headers = {}

            def send_header(self, name, value):
                self.headers[name] = value

        handler = FakeHandler()
        app.Handler._send_common_headers(handler)

        self.assertEqual(handler.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(handler.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", handler.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
