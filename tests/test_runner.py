import unittest

import app


class JudgeTest(unittest.TestCase):
    def test_correct_solution_passes(self):
        code = """class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for index, value in enumerate(nums):
            if target - value in seen:
                return [seen[target - value], index]
            seen[value] = index
"""

        result = app.run_judge(app.PROBLEMS["two-sum"], code)

        self.assertTrue(result["results"])
        self.assertTrue(all(case["ok"] for case in result["results"]))

    def test_base_exception_becomes_case_error(self):
        code = """class Solution:
    def twoSum(self, nums, target):
        raise SystemExit('stop')
"""

        result = app.run_judge(app.PROBLEMS["two-sum"], code)

        self.assertIn("SystemExit: stop", result["results"][0]["error"])

    def test_solution_instance_is_fresh_for_each_case(self):
        problem = {
            "entry": "value",
            "tests": [
                {"args": [], "expected": 1},
                {"args": [], "expected": 1},
            ],
        }
        code = """class Solution:
    def __init__(self):
        self.calls = 0

    def value(self):
        self.calls += 1
        return self.calls
"""

        result = app.run_judge(problem, code)

        self.assertTrue(all(case["ok"] for case in result["results"]))

    def test_print_output_is_capped(self):
        code = """class Solution:
    def twoSum(self, nums, target):
        print('x' * 50000)
        seen = {}
        for index, value in enumerate(nums):
            if target - value in seen:
                return [seen[target - value], index]
            seen[value] = index
"""

        result = app.run_judge(app.PROBLEMS["two-sum"], code)

        self.assertTrue(result["prints"].startswith("[前方输出已截断]"))
        self.assertLess(len(result["prints"]), 17_000)

    def test_oversized_code_is_rejected(self):
        result = app.run_judge(app.PROBLEMS["two-sum"], "x" * (app.MAX_CODE_CHARS + 1))
        self.assertIn("代码过长", result["fatal"])

    def test_timeout_is_reported(self):
        original_timeout = app.RUN_TIMEOUT
        app.RUN_TIMEOUT = 0.2
        try:
            code = """class Solution:
    def twoSum(self, nums, target):
        while True:
            pass
"""
            result = app.run_judge(app.PROBLEMS["two-sum"], code)
        finally:
            app.RUN_TIMEOUT = original_timeout

        self.assertIn("运行超时", result["fatal"])


if __name__ == "__main__":
    unittest.main()
