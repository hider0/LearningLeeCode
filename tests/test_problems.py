import json
import re
import unittest
from pathlib import Path

import app


class ProblemBankTest(unittest.TestCase):
    def test_problem_schema_and_ids(self):
        required = {
            "id", "title", "difficulty", "description", "entry",
            "starter", "tests", "hints", "explanation",
        }
        problem_ids = set()
        chapter_count = 0
        test_count = 0

        for path in sorted(Path("problems").glob("*.json")):
            chapter = json.loads(path.read_text(encoding="utf-8"))
            chapter_count += 1
            self.assertTrue(chapter["chapter"])
            self.assertTrue(chapter["problems"])
            for problem in chapter["problems"]:
                self.assertEqual(required - problem.keys(), set(), problem.get("id"))
                self.assertNotIn(problem["id"], problem_ids)
                self.assertIn(problem["difficulty"], {"简单", "中等", "困难"})
                self.assertTrue(problem["tests"])
                problem_ids.add(problem["id"])
                test_count += len(problem["tests"])

        self.assertEqual(chapter_count, 7)
        self.assertEqual(len(problem_ids), 41)
        self.assertGreaterEqual(test_count, 120)

    def test_all_reference_solutions_pass(self):
        failures = []
        for problem in app.PROBLEMS.values():
            code = app.reference_implementation(problem)
            if not code:
                failures.append((problem["id"], "missing reference implementation"))
                continue
            result = app.run_judge(problem, code)
            if not (result.get("results") and all(case["ok"] for case in result["results"])):
                failures.append((problem["id"], result))

        self.assertEqual(failures, [])

    def test_detailed_guides_exist_for_every_chapter(self):
        guide_files = sorted(Path("guide").glob("[0-9][0-9]-*.md"))
        self.assertEqual(len(guide_files), 7)
        for path in guide_files:
            text = path.read_text(encoding="utf-8")
            self.assertIn("本章目标", text)
            self.assertIn("常见错误", text)
            self.assertIn("复习清单", text)


if __name__ == "__main__":
    unittest.main()
