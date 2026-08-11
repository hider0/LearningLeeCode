import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import app


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_config_file = app.CONFIG_FILE
        app.CONFIG_FILE = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        app.CONFIG_FILE = self.original_config_file
        self.temp_dir.cleanup()

    def test_timeout_is_loaded_from_config(self):
        app.CONFIG_FILE.write_text(json.dumps({
            "api_key": "secret",
            "base_url": "https://example.test/v1",
            "model": "test-model",
            "timeout_seconds": 120,
        }), encoding="utf-8")

        config = app.load_config()

        self.assertEqual(config["timeout_seconds"], 120)

    def test_timeout_can_come_from_environment_and_is_clamped(self):
        with patch.dict(os.environ, {"OPENAI_TIMEOUT_SECONDS": "9999"}, clear=False):
            config = app.load_config()

        self.assertEqual(config["timeout_seconds"], app.MAX_LLM_TIMEOUT)

    def test_invalid_timeout_uses_default(self):
        app.CONFIG_FILE.write_text('{"timeout_seconds":"invalid"}', encoding="utf-8")

        config = app.load_config()

        self.assertEqual(config["timeout_seconds"], app.DEFAULT_LLM_TIMEOUT)


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

    def test_request_sets_output_limit(self):
        response = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "OK"}}]
        }).encode("utf-8"))
        config = {
            "api_key": "secret",
            "base_url": "https://example.test",
            "model": "test-model",
            "timeout_seconds": 120,
        }

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            answer = app.call_llm(
                config, [{"role": "user", "content": "hello"}], max_tokens=123)

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(answer, "OK")
        self.assertEqual(payload["max_tokens"], 123)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)

    def test_timeout_has_clear_message(self):
        config = {
            "api_key": "secret",
            "base_url": "https://example.test",
            "model": "test-model",
        }
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(RuntimeError, "请求超过"):
                app.call_llm(config, [{"role": "user", "content": "hello"}])

    def test_failed_call_fallback_does_not_claim_key_is_missing(self):
        answer = app.local_answer(
            app.PROBLEMS["two-sum"], "什么是哈希表？", failure_reason="请求超时")

        self.assertIn("大模型调用失败", answer)
        self.assertNotIn("未配置大模型 API Key", answer)

    def test_ask_only_reuses_successful_ai_history(self):
        history = [
            {"q": "保留", "a": "保留回答", "source": "ai"},
            {"q": "本地回退", "a": "很长的本地内容", "source": "local"},
            {"q": "[思路诊断]", "a": "诊断内容", "source": "ai"},
        ]
        config = {"api_key": "secret", "base_url": "https://example.test", "model": "test"}

        with patch("app.call_llm", return_value="OK") as call:
            app.ask_llm(
                config, app.PROBLEMS["two-sum"], "class Solution: pass", "问题", history)

        messages = call.call_args.args[1]
        contents = [message["content"] for message in messages]
        self.assertIn("保留", contents)
        self.assertNotIn("本地回退", contents)
        self.assertNotIn("[思路诊断]", contents)

    def test_diagnosis_requires_complexity_comparison(self):
        brute_force = """class Solution:
    def twoSum(self, nums, target):
        for left in range(len(nums)):
            for right in range(left + 1, len(nums)):
                if nums[left] + nums[right] == target:
                    return [left, right]
"""
        judge_result = app.run_judge(app.PROBLEMS["two-sum"], brute_force)
        config = {"api_key": "secret", "base_url": "https://example.test", "model": "test"}

        with patch("app.call_llm", return_value="OK") as call:
            app.diagnose_llm(config, app.PROBLEMS["two-sum"], brute_force, judge_result)

        messages = call.call_args.args[1]
        prompt = "\n".join(message["content"] for message in messages)
        self.assertIn("正确但需优化", prompt)
        self.assertIn("时间 O(n)", prompt)
        self.assertIn("标准实现", prompt)
        self.assertIn("【实现对比】", prompt)
        self.assertIn(app.reference_implementation(app.PROBLEMS["two-sum"]), prompt)
        self.assertEqual(call.call_args.kwargs["max_tokens"], 520)

    def test_local_passed_diagnosis_mentions_complexity_limit(self):
        result = {"results": [{"ok": True}]}
        diagnosis = app.local_diagnose(result, with_prefix=False)

        self.assertIn("正确性已验证", diagnosis)
        self.assertIn("复杂度", diagnosis)


class FrontendContractTest(unittest.TestCase):
    def test_security_error_and_draft_contracts_are_present(self):
        html = Path("static/index.html").read_text(encoding="utf-8")

        self.assertIn('.replace(/"/g, "&quot;")', html)
        self.assertIn("if (!resp.ok) throw new Error", html)
        self.assertIn("localStorage.setItem(draftKey(state.problem.id), editor.value)", html)
        self.assertIn("p.saved_code || p.starter", html)
        self.assertIn("AI 评估复杂度与思路", html)
        self.assertIn("s.timeout_seconds", html)

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
