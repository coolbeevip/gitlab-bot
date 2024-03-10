import os


def get_prompt_text(name: str, lang: str) -> str:
    current_directory = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(current_directory, f"{name}_{lang}.txt")
    with open(path, "r", encoding="UTF-8") as file:
        return file.read()
