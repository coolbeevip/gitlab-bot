import unittest
from unittest import TestCase

from src.prompts.prompts import get_summary_prompt_text


class TestPrompts(TestCase):
    def test_load_default_prompt(self):
        self.assertIn(
            "你是一个精通多种编程语言的智能机器人",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "zh"),
        )
        self.assertIn(
            "You are an intelligent robot proficient in multiple programming languages and good at reading git-dff reports",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "en"),
        )
        self.assertNotIn(
            "<RULES>",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "en"),
        )
        self.assertNotIn(
            "</RULES>",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "zh"),
        )

    def test_load_custom_prompt(self):
        custom_rules = "1. RULE1\n2. RULE2"
        self.assertIn(
            "1. RULE1\n2. RULE2",
            get_summary_prompt_text(
                "DIFFS_SUMMARY_PROMPTS_TEMPLATE", "zh", custom_rules
            ),
        )
        self.assertIn(
            "1. RULE1\n2. RULE2",
            get_summary_prompt_text(
                "DIFFS_SUMMARY_PROMPTS_TEMPLATE", "en", custom_rules
            ),
        )
        self.assertNotIn(
            "<RULES>",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "en"),
        )
        self.assertNotIn(
            "</RULES>",
            get_summary_prompt_text("DIFFS_SUMMARY_PROMPTS_TEMPLATE", "zh"),
        )


if __name__ == "__main__":
    unittest.main()
