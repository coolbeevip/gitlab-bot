import ast
import asyncio
from pathlib import Path

from gidgetlab.sansio import Event

import gitlab_bot
from src.hooks.approval_notification import ApprovalNotificationHooks
from src.hooks.merge_notification import MergeRequestNotificationHooks
from tests.fixtures.approval_webhook import copy_webhook
from tests.fixtures.merge_webhook import copy_merge_webhook

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _import_modules(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            yield prefix + (node.module or "")


def test_channels_do_not_depend_on_hooks_or_delivery():
    for path in (SRC_ROOT / "channels").glob("*.py"):
        imports = tuple(_import_modules(path))
        assert not any("hooks" in name or "delivery" in name for name in imports), path


def test_notification_hooks_only_depend_on_notification_model_and_channel_contract():
    notification_hook_paths = (
        SRC_ROOT / "hooks" / "approval_notification.py",
        SRC_ROOT / "hooks" / "merge_notification.py",
    )
    for path in notification_hook_paths:
        imports = tuple(_import_modules(path))
        assert not any("channels.log" in name or "delivery" in name or "gitlab_bot" in name for name in imports), path


def test_delivery_does_not_depend_on_approval_notification_or_hooks():
    for path in (SRC_ROOT / "delivery").glob("*.py"):
        imports = tuple(_import_modules(path))
        assert not any("approval_notification" in name or "hooks" in name for name in imports), path


def test_legacy_facades_are_removed():
    legacy_paths = (
        SRC_ROOT / "approval_notification.py",
        SRC_ROOT / "notification_delivery.py",
        SRC_ROOT / "issue_hook.py",
        SRC_ROOT / "merge_request_hook.py",
        SRC_ROOT / "note_hook.py",
    )
    for path in legacy_paths:
        assert not path.exists(), path


def test_legacy_module_imports_are_removed_from_source_and_tests():
    legacy_modules = {
        "src.approval_notification",
        "src.notification_delivery",
        "src.issue_hook",
        "src.merge_request_hook",
        "src.note_hook",
    }
    python_paths = tuple(SRC_ROOT.rglob("*.py")) + tuple((PROJECT_ROOT / "tests").rglob("*.py"))
    for path in python_paths:
        imports = tuple(_import_modules(path))
        assert not any(name in legacy_modules for name in imports), path


def test_startup_recovery_and_notification_routes_are_registered_once(monkeypatch):
    assert gitlab_bot.bot.app.on_startup.count(gitlab_bot.recover_merge_notification_deliveries) == 1

    class RecordingChannel:
        def __init__(self):
            self.notifications = []

        async def send(self, notification):
            self.notifications.append(notification)

    approval_channel = RecordingChannel()
    monkeypatch.setattr(gitlab_bot, "approval_notification_hooks", ApprovalNotificationHooks(approval_channel))
    monkeypatch.setattr(gitlab_bot, "bot_gitlab_username", "review-bot")
    asyncio.run(
        gitlab_bot.bot.router.dispatch(
            Event(copy_webhook(username="reviewer"), event="Merge Request Hook"),
            None,
        )
    )
    assert len(approval_channel.notifications) == 1

    merge_channel = RecordingChannel()
    monkeypatch.setattr(gitlab_bot, "merge_request_notification_hooks", MergeRequestNotificationHooks(merge_channel))
    asyncio.run(
        gitlab_bot.bot.router.dispatch(
            Event(copy_merge_webhook(username="merger"), event="Merge Request Hook"),
            None,
        )
    )
    assert len(merge_channel.notifications) == 1
