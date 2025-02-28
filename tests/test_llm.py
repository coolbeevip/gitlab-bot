import json
import os
import unittest
from unittest import TestCase

from src.llm import ai_diffs_summary


class TestLLM(TestCase):
    def test_ai_diffs_summary(self):
        test_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(test_dir, "git_diff.json")

        with open(file_path, "r") as f:
            git_diff_json = json.loads(f.read())
            summary_report = ai_diffs_summary(git_diff_json)
            self.assertIn("AI Summary(experiment)", summary_report)
            self.assertIn("Powered by", summary_report)
            print(summary_report)


if __name__ == "__main__":
    unittest.main()
