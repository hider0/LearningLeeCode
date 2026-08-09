#!/usr/bin/env python3
"""LeetCode 刷题训练器 —— 本地 Web 服务（仅依赖 Python 标准库）。

用法:
    python app.py [端口]        # 默认 8000
然后浏览器打开 http://127.0.0.1:8000

功能:
    - 按章节浏览题目、在线提交 Python 代码并运行测试判题
    - 提交后展示题解讲解，可就不明之处追问（配置大模型 API 后由 AI 回答，
      未配置时回退为本地讲解并记录问题笔记）
    - 自动记录错题，通过后自动移出错题本
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PROBLEMS_DIR = ROOT / "problems"
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
PROGRESS_FILE = DATA_DIR / "progress.json"
CONFIG_FILE = ROOT / "config.json"
RUNNER = ROOT / "runner.py"
RUN_TIMEOUT = 15   # 单次判题最长秒数
LLM_TIMEOUT = 60   # 大模型请求最长秒数


# ---------------------------------------------------------------- 题库

def load_problems():
    """加载 problems/ 下全部章节 JSON，按文件名排序。"""
    chapters, index = [], {}
    for path in sorted(PROBLEMS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = {"chapter": data["chapter"], "problems": []}
        for p in data["problems"]:
            p["chapter"] = data["chapter"]
            index[p["id"]] = p
            entry["problems"].append(p)
        chapters.append(entry)
    return chapters, index


CHAPTERS, PROBLEMS = load_problems()

# ---------------------------------------------------------------- 进度存储


def load_progress():
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"solved": {}, "wrong": {}, "notes": {}}


def save_progress(progress):
    DATA_DIR.mkdir(exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- 配置


def load_config():
    """大模型配置：config.json 优先，其次环境变量。"""
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "api_key": cfg.get("api_key") or os.environ.get("OPENAI_API_KEY", ""),
        "base_url": (cfg.get("base_url") or os.environ.get("OPENAI_BASE_URL")
                     or "https://api.openai.com/v1").rstrip("/"),
        "model": cfg.get("model") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
    }

# ---------------------------------------------------------------- 判题


def run_judge(problem, code):
    payload = {
        "code": code,
        "entry": problem["entry"],
        "tests": problem["tests"],
        "codec": problem.get("codec"),
        "compare": problem.get("compare", "exact"),
    }
    try:
        proc = subprocess.run(
            [sys.executable, str(RUNNER)],
            input=json.dumps(payload),
            capture_output=True, text=True,
            timeout=RUN_TIMEOUT, cwd=str(ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"fatal": f"运行超时（超过 {RUN_TIMEOUT} 秒），请检查是否存在死循环"}
    if not proc.stdout.strip():
        detail = proc.stderr.strip()[-500:] or "未知错误"
        return {"fatal": "判题进程异常退出：" + detail}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"fatal": "判题输出解析失败", "raw": proc.stdout[-500:]}

# ---------------------------------------------------------------- 追问


def local_answer(problem, question):
    """未配置大模型时的本地回退：返回预置讲解与提示，并记录问题。"""
    parts = [
        f"（未配置大模型 API Key，无法针对「{question}」实时作答；"
        "你的问题已记入笔记。以下为本地预置讲解，配置 Key 后可获得针对性回答。）",
        "【题目讲解】\n" + (problem.get("explanation") or "暂无讲解"),
    ]
    hints = problem.get("hints") or []
    if hints:
        parts.append("【提示】\n" + "\n".join(f"{i + 1}. {h}" for i, h in enumerate(hints)))
    return "\n\n".join(parts)


def call_llm(cfg, messages):
    """调用 OpenAI 兼容接口。

    安全约定：api_key 只出现在请求头中；抛出的异常信息经过清洗，
    保证不包含 Key 等敏感内容。
    """
    body = json.dumps({
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + cfg["api_key"]})
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"大模型接口返回 HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误: {exc.reason}") from None
    return data["choices"][0]["message"]["content"].strip()


def ask_llm(cfg, problem, code, question, history):
    """就用户的追问调用大模型。"""
    system = ("你是一位算法教练，正在辅导用户解答 LeetCode 题目。"
              "请用中文回答，结合题目描述和用户的代码，讲解清晰、具体、简洁，"
              "可以适当给出小例子，但不要直接替用户写完整答案，除非用户明确要求。")
    context = (
        f"题目：{problem['title']}\n\n{problem['description']}\n\n"
        f"参考讲解：\n{problem.get('explanation', '')}\n\n"
        f"用户当前代码：\n```python\n{code}\n```"
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": context}]
    for item in history[-6:]:
        messages.append({"role": "user", "content": item["q"]})
        messages.append({"role": "assistant", "content": item["a"]})
    messages.append({"role": "user", "content": question})
    return call_llm(cfg, messages)


def summarize_judge(judge_result):
    """把判题结果压缩成给大模型看的文本摘要。"""
    if "fatal" in judge_result:
        return "判题失败：" + judge_result["fatal"]
    if "compile_error" in judge_result:
        return "代码无法运行：" + judge_result["compile_error"]
    lines = []
    for i, r in enumerate(judge_result.get("results", []), 1):
        if r["ok"]:
            lines.append(f"用例{i}: 通过")
        elif "error" in r:
            lines.append(f"用例{i}: 运行报错 {r['error']}（输入 {r['args']}）")
        else:
            lines.append(f"用例{i}: 答案错误，输入 {r['args']}，"
                         f"期望 {r['expected']}，实际 {r.get('got')}")
    return "\n".join(lines)[:2000]


def diagnose_llm(cfg, problem, code, judge_result):
    """思路诊断：判定思路是否正确，定位 bug，给出修改方向（不给完整答案）。"""
    system = (
        "你是一位算法教练。用户提交了一段 LeetCode 题解代码但未通过判题。"
        "请阅读代码并判断用户的【解题思路】是否正确，区分「思路错误」和「思路正确但实现有 bug」。"
        "严格按以下三段格式用中文输出，每段 1~3 句话，简洁具体：\n"
        "【思路判定】思路正确 / 思路基本正确但有偏差 / 思路方向错误，并给出一句依据；\n"
        "【Bug 定位】指出出错的行或语句，说明为什么错；\n"
        "【修改提示】只给修改方向和关键思路，不要给出完整正确代码。"
    )
    context = (
        f"题目：{problem['title']}\n\n{problem['description']}\n\n"
        f"用户代码：\n```python\n{code}\n```\n\n"
        f"判题结果：\n{summarize_judge(judge_result)}"
    )
    return call_llm(cfg, [{"role": "system", "content": system},
                          {"role": "user", "content": context}])


def local_diagnose(judge_result, with_prefix=True):
    """本地启发式诊断（只看判题结果的统计特征）。"""
    prefix = ("（未配置大模型 API Key，以下为基于判题结果的粗略判断，"
              "配置 Key 后可获得思路级诊断。）\n\n") if with_prefix else ""
    if "fatal" in judge_result:
        return prefix + "【Bug 定位】\n" + judge_result["fatal"]
    if "compile_error" in judge_result:
        return (prefix + "【Bug 定位】\n代码存在语法或运行期错误：\n"
                + judge_result["compile_error"]
                + "\n\n【修改提示】\n先修复报错让代码能跑起来，再观察对拍结果。")
    results = judge_result.get("results", [])
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    if total and passed == 0:
        verdict = "所有用例均未通过，思路方向可能有问题，建议先对照「提示」和「讲解」检查算法选择。"
    elif passed < total:
        verdict = (f"{passed}/{total} 用例通过：思路大概率是正确的，"
                   "重点检查未通过用例的边界情况（空输入、单元素、重复元素、负数等）。")
    else:
        verdict = "全部用例通过。"
    failed = next((r for r in results if not r["ok"]), None)
    detail = ""
    if failed:
        detail = ("\n\n【首个失败用例】\n输入：" + json.dumps(failed["args"], ensure_ascii=False)
                  + "\n期望：" + json.dumps(failed["expected"], ensure_ascii=False)
                  + "\n" + ("实际：" + json.dumps(failed.get("got"), ensure_ascii=False)
                            if "got" in failed else "报错：" + failed.get("error", "")))
    return prefix + "【思路判定】\n" + verdict + detail


def mask_key(key):
    """Key 脱敏：只保留前 4 位和后 4 位。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def llm_status():
    """返回给前端的 LLM 配置状态——绝不包含完整 Key。"""
    cfg = load_config()
    host = ""
    if cfg["base_url"]:
        host = urlparse(cfg["base_url"]).netloc
    return {
        "configured": bool(cfg["api_key"]),
        "key_hint": mask_key(cfg["api_key"]),
        "model": cfg["model"] if cfg["api_key"] else "",
        "endpoint_host": host if cfg["api_key"] else "",
        "https": cfg["base_url"].startswith("https://"),
    }

# ---------------------------------------------------------------- HTTP 处理


class Handler(BaseHTTPRequestHandler):
    server_version = "LeetCodeTrainer/1.0"

    # ---- 工具 ----

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    # ---- GET ----

    def do_GET(self):
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            self._send_html(STATIC_DIR / "index.html")
        elif route == "/api/chapters":
            self._send_json(self._chapters_payload())
        elif route == "/api/problem":
            self._handle_get_problem(query)
        elif route == "/api/wrong":
            self._handle_get_wrong()
        elif route == "/api/notes":
            pid = (query.get("problem_id") or [""])[0]
            notes = load_progress()["notes"].get(pid, [])
            self._send_json({"notes": notes})
        elif route == "/api/llm-status":
            self._send_json(llm_status())
        else:
            self._send_json({"error": "not found"}, status=404)

    def _chapters_payload(self):
        progress = load_progress()
        out = []
        for ch in CHAPTERS:
            items = []
            for p in ch["problems"]:
                if p["id"] in progress["solved"]:
                    status = "solved"
                elif p["id"] in progress["wrong"]:
                    status = "wrong"
                else:
                    status = "todo"
                items.append({"id": p["id"], "title": p["title"],
                              "difficulty": p["difficulty"], "status": status})
            out.append({"chapter": ch["chapter"], "problems": items})
        return out

    def _handle_get_problem(self, query):
        pid = (query.get("id") or [""])[0]
        p = PROBLEMS.get(pid)
        if not p:
            self._send_json({"error": "题目不存在"}, status=404)
            return
        self._send_json({
            "id": p["id"], "title": p["title"], "chapter": p["chapter"],
            "difficulty": p["difficulty"], "description": p["description"],
            "examples": p.get("examples", []), "starter": p["starter"],
            "hints": p.get("hints", []), "explanation": p.get("explanation", ""),
        })

    def _handle_get_wrong(self):
        progress = load_progress()
        items = []
        for pid, rec in progress["wrong"].items():
            p = PROBLEMS.get(pid)
            if not p:
                continue
            items.append({
                "id": pid, "title": p["title"], "chapter": p["chapter"],
                "difficulty": p["difficulty"], "attempts": rec.get("attempts", 0),
                "time": rec.get("time", ""), "last_error": rec.get("last_error", ""),
            })
        items.sort(key=lambda x: x["time"], reverse=True)
        self._send_json({"wrong": items, "count": len(items)})

    # ---- POST ----

    def do_POST(self):
        route = urlparse(self.path).path
        body = self._read_body()
        if route == "/api/submit":
            self._handle_submit(body)
        elif route == "/api/ask":
            self._handle_ask(body)
        elif route == "/api/diagnose":
            self._handle_diagnose(body)
        else:
            self._send_json({"error": "not found"}, status=404)

    def _handle_diagnose(self, body):
        pid, code = body.get("id", ""), body.get("code", "")
        problem = PROBLEMS.get(pid)
        if not problem:
            self._send_json({"error": "题目不存在"}, status=404)
            return
        if not code.strip():
            self._send_json({"error": "代码不能为空"}, status=400)
            return

        judge_result = run_judge(problem, code)
        cfg = load_config()
        if cfg["api_key"]:
            try:
                diagnosis = diagnose_llm(cfg, problem, code, judge_result)
                source = "ai"
            except Exception as exc:
                diagnosis = (f"（调用大模型失败：{exc}，已回退为本地粗略诊断。）\n\n"
                             + local_diagnose(judge_result, with_prefix=False))
                source = "local"
        else:
            diagnosis = local_diagnose(judge_result)
            source = "local"

        progress = load_progress()
        history = progress["notes"].setdefault(pid, [])
        history.append({"q": "[思路诊断]", "a": diagnosis, "source": source,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        save_progress(progress)
        self._send_json({"diagnosis": diagnosis, "source": source})

    def _handle_submit(self, body):
        pid, code = body.get("id", ""), body.get("code", "")
        problem = PROBLEMS.get(pid)
        if not problem:
            self._send_json({"error": "题目不存在"}, status=404)
            return
        if not code.strip():
            self._send_json({"error": "代码不能为空"}, status=400)
            return

        result = run_judge(problem, code)
        if "fatal" in result or "compile_error" in result:
            passed = False
            summary = result.get("fatal") or result.get("compile_error")
        else:
            passed = all(r["ok"] for r in result["results"])
            failed = next((r for r in result["results"] if not r["ok"]), None)
            summary = "" if passed else (
                failed.get("error")
                or f"用例 {failed['args']} 期望 {failed['expected']}，实际 {failed.get('got')}")

        progress = load_progress()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if passed:
            progress["solved"][pid] = now
            progress["wrong"].pop(pid, None)
        else:
            rec = progress["wrong"].get(pid, {"attempts": 0})
            rec["attempts"] = rec.get("attempts", 0) + 1
            rec["last_code"] = code[-4000:]
            rec["last_error"] = summary
            rec["time"] = now
            progress["wrong"][pid] = rec
        save_progress(progress)

        result["passed"] = passed
        self._send_json(result)

    def _handle_ask(self, body):
        pid = body.get("id", "")
        question = (body.get("question") or "").strip()
        code = body.get("code", "")
        problem = PROBLEMS.get(pid)
        if not problem:
            self._send_json({"error": "题目不存在"}, status=404)
            return
        if not question:
            self._send_json({"error": "问题不能为空"}, status=400)
            return

        progress = load_progress()
        history = progress["notes"].setdefault(pid, [])
        cfg = load_config()
        if cfg["api_key"]:
            try:
                answer = ask_llm(cfg, problem, code, question, history)
                source = "ai"
            except Exception as exc:
                answer = (f"（调用大模型失败：{exc}，已回退为本地讲解。）\n\n"
                          + local_answer(problem, question))
                source = "local"
        else:
            answer = local_answer(problem, question)
            source = "local"

        history.append({"q": question, "a": answer, "source": source,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        save_progress(progress)
        self._send_json({"answer": answer, "source": source})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"已加载 {sum(len(c['problems']) for c in CHAPTERS)} 道题目 / "
          f"{len(CHAPTERS)} 个章节")
    print(f"请用浏览器打开: http://127.0.0.1:{port}  (Ctrl+C 退出)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
