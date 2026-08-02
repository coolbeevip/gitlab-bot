import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from gidgetlab.sansio import Event

import gitlab_bot
from src.channels.log import LogChannel
from src.hooks.approval_notification import ApprovalNotificationHooks, build_notification
from tests.fixtures.approval_webhook import copy_webhook


class RecordingChannel:
    def __init__(self):
        self.notifications = []

    async def send(self, notification):
        self.notifications.append(notification)


class FailingChannel:
    async def send(self, notification):
        raise RuntimeError("channel unavailable")


def make_event(action="approval", username="reviewer"):
    return SimpleNamespace(data=copy_webhook(action=action, username=username))


def test_build_notification_contains_human_readable_message_and_links():
    notification = build_notification(copy_webhook())

    assert notification.action == "approval"
    assert "reviewer" in notification.message
    assert "Add feature" in notification.message
    assert "!12" in notification.message
    assert "https://gitlab.example.com/group/project/-/merge_requests/12" in notification.message
    assert notification.project["id"] == 76
    assert notification.merge_request["iid"] == 12
    assert notification.actor["username"] == "reviewer"


def test_build_unapproval_notification_uses_human_readable_action():
    notification = build_notification(copy_webhook(action="unapproval"))

    assert notification.action == "unapproval"
    assert "取消" in notification.message or "unapproval" in notification.message
    assert "Add feature" in notification.message


def test_log_channel_emits_structured_json_with_readable_message(caplog):
    logger = logging.getLogger("test.approval_notification")
    channel = LogChannel(logger)
    notification = build_notification(copy_webhook())
    caplog.set_level(logging.INFO, logger="test.approval_notification")

    asyncio.run(channel.send(notification))

    payload = json.loads(caplog.records[-1].message)
    assert payload["message"] == notification.message
    assert payload["action"] == "approval"
    assert payload["merge_request"]["url"].endswith("/merge_requests/12")


@pytest.mark.parametrize(
    ("action", "expected_action"),
    [("approval", "approval"), ("approved", "approval"), ("unapproval", "unapproval"), ("unapproved", "unapproval")],
)
@pytest.mark.parametrize("username", ["reviewer", "review-bot"])
def test_router_sends_user_and_bot_approval_events_without_global_filter(
    monkeypatch, action, expected_action, username
):
    channel = RecordingChannel()
    monkeypatch.setattr(gitlab_bot, "approval_notification_hooks", ApprovalNotificationHooks(channel))
    monkeypatch.setattr(gitlab_bot, "bot_gitlab_username", "review-bot")
    event_data = copy_webhook(action=action, username=username)
    event = Event(event_data, event="Merge Request Hook")

    asyncio.run(gitlab_bot.bot.router.dispatch(event, None))

    assert len(channel.notifications) == 1
    assert channel.notifications[0].action == expected_action
    assert channel.notifications[0].webhook_action == action


def test_noncritical_fields_are_null_and_notification_is_still_sent():
    payload = copy_webhook()
    payload["project"].pop("path_with_namespace")
    payload["project"].pop("name")
    payload["project"].pop("web_url")
    payload["object_attributes"].pop("title")
    payload["object_attributes"].pop("url")
    payload["user"].pop("id")
    payload["user"].pop("name")
    payload["object_attributes"].pop("updated_at")
    channel = RecordingChannel()

    asyncio.run(ApprovalNotificationHooks(channel).handle(SimpleNamespace(data=payload)))

    notification = channel.notifications[0]
    assert notification.project["path"] is None
    assert notification.project["url"] is None
    assert notification.merge_request["title"] is None
    assert notification.merge_request["url"] is None
    assert notification.actor["id"] is None
    assert notification.actor["name"] is None
    assert notification.occurred_at is None


def test_approval_notification_does_not_call_gitlab_api():
    channel = RecordingChannel()
    hooks = ApprovalNotificationHooks(channel)
    api = SimpleNamespace(
        getitem=lambda *_args, **_kwargs: pytest.fail("approval notification must not call GitLab API"),
        post=lambda *_args, **_kwargs: pytest.fail("approval notification must not call GitLab API"),
    )

    asyncio.run(hooks.handle(make_event(), api))

    assert len(channel.notifications) == 1


def test_channel_failure_is_logged_and_does_not_escape(caplog):
    logger = logging.getLogger("test.approval_notification.failure")
    hooks = ApprovalNotificationHooks(FailingChannel(), logger=logger)
    caplog.set_level(logging.ERROR, logger="test.approval_notification.failure")

    asyncio.run(hooks.handle(make_event()))

    assert "channel unavailable" in caplog.text


def test_invalid_payload_is_logged_and_skipped(caplog):
    logger = logging.getLogger("test.approval_notification.invalid")
    channel = RecordingChannel()
    hooks = ApprovalNotificationHooks(channel, logger=logger)
    caplog.set_level(logging.ERROR, logger="test.approval_notification.invalid")
    invalid_event = SimpleNamespace(data={"object_attributes": {"action": "approval"}})

    asyncio.run(hooks.handle(invalid_event))

    assert channel.notifications == []
    assert "invalid approval webhook" in caplog.text


def test_non_target_action_is_skipped():
    channel = RecordingChannel()
    hooks = ApprovalNotificationHooks(channel)

    asyncio.run(hooks.handle(make_event(action="open")))

    assert channel.notifications == []


def test_duplicate_delivery_is_attempted_each_time():
    channel = RecordingChannel()
    hooks = ApprovalNotificationHooks(channel)
    event = make_event()

    asyncio.run(hooks.handle(event))
    asyncio.run(hooks.handle(event))

    assert len(channel.notifications) == 2
