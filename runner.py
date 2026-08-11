#!/usr/bin/env python3
"""判题运行器：在子进程中执行用户代码并对拍测试用例。

从 stdin 读取 JSON:
    {
        "code":    用户提交的代码（需定义 Solution 类）,
        "entry":   入口方法名,
        "tests":   [{"args": [...], "expected": ...}, ...],
        "codec":   {"args": ["linked"|"tree"|null, ...], "result": "linked"|"tree"|null},
        "compare": "exact" | "sorted" | "sorted_deep"
    }
向 stdout 输出 JSON:
    {"results": [{"ok": bool, "args": ..., "expected": ..., "got": ...}, ...], "prints": "..."}
    或 {"compile_error": "..."}
"""
import contextlib
import json
import os
import sys
from itertools import zip_longest

REAL_STDOUT = sys.stdout
JSON_DUMPS = json.dumps

MAX_CAPTURE_CHARS = 16_000
CPU_LIMIT_SECONDS = 6
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
FILE_LIMIT_BYTES = 1 * 1024 * 1024
OPEN_FILE_LIMIT = 64
PROCESS_LIMIT = 32


class CappedTextBuffer:
    """只保留末尾固定数量字符，避免 print 输出无限占用内存。"""

    def __init__(self, limit=MAX_CAPTURE_CHARS):
        self.limit = limit
        self.value = ""
        self.truncated = False

    def write(self, text):
        text = str(text)
        combined = self.value + text[-self.limit:]
        if len(combined) > self.limit or len(text) > self.limit:
            self.truncated = True
        self.value = combined[-self.limit:]
        return len(text)

    def flush(self):
        return None

    def getvalue(self):
        if self.truncated:
            return "[前方输出已截断]\n" + self.value
        return self.value


def apply_resource_limits():
    """在支持 resource 的系统上收紧判题进程资源上限。"""
    if os.name != "posix":
        return
    try:
        import resource
    except ImportError:
        return

    limits = [
        (resource.RLIMIT_CPU, CPU_LIMIT_SECONDS),
        (resource.RLIMIT_FSIZE, FILE_LIMIT_BYTES),
        (resource.RLIMIT_NOFILE, OPEN_FILE_LIMIT),
    ]
    if hasattr(resource, "RLIMIT_AS"):
        limits.append((resource.RLIMIT_AS, MEMORY_LIMIT_BYTES))
    if hasattr(resource, "RLIMIT_NPROC"):
        limits.append((resource.RLIMIT_NPROC, PROCESS_LIMIT))
    if hasattr(resource, "RLIMIT_CORE"):
        limits.append((resource.RLIMIT_CORE, 0))

    for kind, value in limits:
        try:
            resource.setrlimit(kind, (value, value))
        except (OSError, ValueError):
            continue


def emit(payload):
    REAL_STDOUT.write(JSON_DUMPS(payload, ensure_ascii=False))
    REAL_STDOUT.flush()


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right


def build_linked(values):
    dummy = ListNode()
    cur = dummy
    for v in values:
        cur.next = ListNode(v)
        cur = cur.next
    return dummy.next


def linked_to_list(node, limit=1000):
    out = []
    while node is not None and len(out) < limit:
        out.append(node.val)
        node = node.next
    return out


def build_tree(values):
    """按层序数组构造二叉树，None 表示空节点。"""
    if not values:
        return None
    root = TreeNode(values[0])
    queue = [root]
    i = 1
    while queue and i < len(values):
        node = queue.pop(0)
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            queue.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            queue.append(node.right)
        i += 1
    return root


def tree_to_list(root, limit=1000):
    """把二叉树序列化为层序数组（去掉末尾的 None）。"""
    if root is None:
        return []
    out, queue = [], [root]
    while queue and len(out) < limit:
        node = queue.pop(0)
        if node is None:
            out.append(None)
        else:
            out.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
    while out and out[-1] is None:
        out.pop()
    return out


DECODERS = {"linked": build_linked, "tree": build_tree}
ENCODERS = {"linked": linked_to_list, "tree": tree_to_list}


def decode(value, kind):
    if kind in DECODERS and value is not None:
        return DECODERS[kind](value)
    return value


def encode(value, kind):
    if kind in ENCODERS:
        return ENCODERS[kind](value)
    return value


def _key(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)


def matches(got, expected, mode):
    """比较实际输出与期望输出。

    exact:       完全相等
    sorted:      顶层排序后相等（适用于答案顺序无关的一维结果，如两数之和的下标）
    sorted_deep: 内层、外层都排序后相等（适用于字母异位词分组这类二维结果）
    """
    try:
        if mode == "sorted":
            return sorted(got, key=_key) == sorted(expected, key=_key)
        if mode == "sorted_deep":
            def norm(v):
                inner = (sorted(i, key=_key) if isinstance(i, list) else i for i in v)
                return sorted(inner, key=_key)
            return norm(got) == norm(expected)
        return got == expected
    except TypeError:
        return False


def main():
    payload = json.load(sys.stdin)
    apply_resource_limits()
    codec = payload.get("codec") or {}
    arg_kinds = codec.get("args") or []
    result_kind = codec.get("result")
    compare = payload.get("compare") or "exact"

    namespace = {"ListNode": ListNode, "TreeNode": TreeNode}
    buf = CappedTextBuffer()
    try:
        with contextlib.redirect_stdout(buf):
            exec(payload["code"], namespace)
    except BaseException as exc:
        emit({
            "compile_error": f"{type(exc).__name__}: {exc}",
            "prints": buf.getvalue(),
        })
        return

    solution_cls = namespace.get("Solution")
    if solution_cls is None:
        emit({"compile_error": "未找到 Solution 类，请按模板作答",
              "prints": buf.getvalue()})
        return
    if not hasattr(solution_cls, payload["entry"]):
        emit({"compile_error": f"Solution 类中未找到方法 {payload['entry']}",
              "prints": buf.getvalue()})
        return

    results = []
    for case in payload["tests"]:
        args = [decode(a, k) for a, k in zip_longest(case["args"], arg_kinds)]
        try:
            fn = getattr(solution_cls(), payload["entry"])
            with contextlib.redirect_stdout(buf):
                out = fn(*args)
            got = encode(out, result_kind)
            JSON_DUMPS(got, ensure_ascii=False)
            results.append({
                "ok": bool(matches(got, case["expected"], compare)),
                "args": case["args"],
                "expected": case["expected"],
                "got": got,
            })
        except BaseException as exc:
            results.append({
                "ok": False,
                "args": case["args"],
                "expected": case["expected"],
                "error": f"{type(exc).__name__}: {exc}",
            })
    emit({"results": results, "prints": buf.getvalue()})


if __name__ == "__main__":
    main()
