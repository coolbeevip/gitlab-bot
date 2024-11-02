import json
import unittest
from unittest import TestCase

from src.llm import ai_diffs_summary


class TestLLM(TestCase):
    def test_ai_diffs_summary(self):
        with open("git_diff.json", "r") as f:
            git_diff_json = json.loads(f.read())
            summary_report = ai_diffs_summary(git_diff_json)
            self.assertIn("AI 摘要(实验)", summary_report)
            self.assertIn("AI 模型", summary_report)
            print(summary_report)


if __name__ == "__main__":
    unittest.main()
