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
import io
import json
import sys
from itertools import zip_longest

REAL_STDOUT = sys.stdout


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
    codec = payload.get("codec") or {}
    arg_kinds = codec.get("args") or []
    result_kind = codec.get("result")
    compare = payload.get("compare") or "exact"

    namespace = {"ListNode": ListNode, "TreeNode": TreeNode}
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(payload["code"], namespace)
    except Exception as exc:
        json.dump({
            "compile_error": f"{type(exc).__name__}: {exc}",
            "prints": buf.getvalue()[-4000:],
        }, REAL_STDOUT)
        return

    solution_cls = namespace.get("Solution")
    if solution_cls is None:
        json.dump({"compile_error": "未找到 Solution 类，请按模板作答",
                   "prints": buf.getvalue()[-4000:]}, REAL_STDOUT)
        return
    try:
        fn = getattr(solution_cls(), payload["entry"])
    except AttributeError:
        json.dump({"compile_error": f"Solution 类中未找到方法 {payload['entry']}",
                   "prints": buf.getvalue()[-4000:]}, REAL_STDOUT)
        return

    results = []
    for case in payload["tests"]:
        args = [decode(a, k) for a, k in zip_longest(case["args"], arg_kinds)]
        try:
            with contextlib.redirect_stdout(buf):
                out = fn(*args)
            got = encode(out, result_kind)
            results.append({
                "ok": bool(matches(got, case["expected"], compare)),
                "args": case["args"],
                "expected": case["expected"],
                "got": got,
            })
        except Exception as exc:
            results.append({
                "ok": False,
                "args": case["args"],
                "expected": case["expected"],
                "error": f"{type(exc).__name__}: {exc}",
            })
    json.dump({"results": results, "prints": buf.getvalue()[-4000:]}, REAL_STDOUT)


if __name__ == "__main__":
    main()
