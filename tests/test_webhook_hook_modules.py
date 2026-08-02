import ast
from pathlib import Path

import gitlab_bot

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def test_webhook_implementations_live_in_hooks_package():
    assert gitlab_bot.issue_hooks.__class__.__module__ == "src.hooks.issue"
    assert gitlab_bot.merge_request_hooks.__class__.__module__ == "src.hooks.merge_request"
    assert gitlab_bot.note_hooks.__class__.__module__ == "src.hooks.note"


def test_legacy_webhook_modules_are_removed():
    for path in (
        SRC_ROOT / "issue_hook.py",
        SRC_ROOT / "merge_request_hook.py",
        SRC_ROOT / "note_hook.py",
    ):
        assert not path.exists(), path


def test_new_webhook_modules_do_not_import_legacy_paths():
    for path in (
        SRC_ROOT / "hooks" / "issue.py",
        SRC_ROOT / "hooks" / "merge_request.py",
        SRC_ROOT / "hooks" / "note.py",
    ):
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(("." * node.level) + (node.module or ""))
        assert not any(name in {"src.issue_hook", "src.merge_request_hook", "src.note_hook"} for name in imports), path
