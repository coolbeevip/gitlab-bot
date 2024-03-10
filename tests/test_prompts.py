import unittest
from unittest import TestCase

from src.prompts.prompts import get_prompt_text


class TestPrompts(TestCase):

    def test_load_prompt(self):
        self.assertIn("你是一个精通多种编程语言的智能机器人", get_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "zh"))
        self.assertIn(
            "You are an intelligent robot proficient in multiple programming languages and good at reading git-dff reports",
            get_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "en"))


if __name__ == "__main__":
    unittest.main()
