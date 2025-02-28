import os
import re


def get_summary_prompt_text(name: str, lang: str, custom_rule: str = None) -> str:
    current_directory = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(current_directory, f"{name}_{lang}.txt")
    with open(path, "r", encoding="UTF-8") as file:
        summary_prompt = file.read()
        if custom_rule:
            # replace summary_prompt_rule with the actual rule
            summary_prompt = re.sub(
                r"<RULES>.*?</RULES>", f"{custom_rule}", summary_prompt, flags=re.DOTALL
            )
        else:
            # Remove the tags
            summary_prompt = summary_prompt.replace("<RULES>\n", "").replace(
                "</RULES>\n", ""
            )
        return summary_prompt
