import asyncio
import logging
from types import SimpleNamespace

import pytest
from gidgetlab.sansio import Event

import gitlab_bot
from src.hooks.merge_notification import MergeRequestNotificationHooks, build_merged_notification
from tests.fixtures.merge_webhook import copy_merge_webhook


class RecordingChannel:
    def __init__(self):
        self.notifications = []

    async def send(self, notification):
        self.notifications.append(notification)


def make_event(payload=None):
    return SimpleNamespace(data=payload or copy_merge_webhook())


def test_build_merged_notification_normalizes_fields_and_message():
    notification = build_merged_notification(copy_merge_webhook())

    assert notification.source == "gitlab"
    assert notification.event_type == "merge_request_lifecycle"
    assert notification.action == "merged"
    assert notification.webhook_action == "merge"
    assert notification.actor["username"] == "merger"
    assert notification.triggered_by["username"] == "webhook-trigger"
    assert notification.occurred_at == "2026-08-02T10:05:00Z"
    assert notification.idempotency_key == "gitlab:merge:76:12:2026-08-02T10:05:00Z"
    assert "MR !12" in notification.message
    assert "Add feature" in notification.message
    assert "group/project" in notification.message
    assert "Merger" in notification.message
    assert "已合并" in notification.message
    assert "https://gitlab.example.com/group/project/-/merge_requests/12" in notification.message


@pytest.mark.parametrize(
    ("action", "state", "merged_at"),
    [("open", "merged", "2026-08-02T10:05:00Z"), ("merge", "opened", None), ("merged", "merged", None)],
)
def test_non_merge_or_uncompleted_events_are_skipped(action, state, merged_at):
    channel = RecordingChannel()
    hooks = MergeRequestNotificationHooks(channel)

    asyncio.run(
        hooks.handle(
            make_event(copy_merge_webhook(action=action, state=state, merged_at=merged_at))
        )
    )

    assert channel.notifications == []


@pytest.mark.parametrize(
    "username",
    ["webhook-trigger", "review-bot"],
)
def test_merge_route_sends_user_and_bot_events_without_global_filter(monkeypatch, username):
    channel = RecordingChannel()
    monkeypatch.setattr(gitlab_bot, "merge_request_notification_hooks", MergeRequestNotificationHooks(channel))
    monkeypatch.setattr(gitlab_bot, "bot_gitlab_username", "review-bot")
    event = Event(copy_merge_webhook(username=username), event="Merge Request Hook")

    asyncio.run(gitlab_bot.bot.router.dispatch(event, None))

    assert len(channel.notifications) == 1
    assert channel.notifications[0].action == "merged"
    assert channel.notifications[0].webhook_action == "merge"


def test_auto_merge_falls_back_without_using_webhook_trigger_user():
    payload = copy_merge_webhook(include_merge_user=False)
    channel = RecordingChannel()

    asyncio.run(MergeRequestNotificationHooks(channel).handle(make_event(payload)))

    notification = channel.notifications[0]
    assert notification.actor["name"] == "GitLab 自动合并"
    assert notification.actor["username"] == "gitlab-auto-merge"
    assert notification.triggered_by["username"] == "webhook-trigger"
    assert "GitLab 自动合并" in notification.message
    assert "webhook-trigger" not in notification.message


def test_noncritical_fields_use_placeholders_and_are_still_sent():
    payload = copy_merge_webhook()
    payload["project"].pop("path_with_namespace")
    payload["project"].pop("name")
    payload["project"].pop("web_url")
    payload["object_attributes"]["title"] = None
    payload["object_attributes"].pop("url")
    payload["object_attributes"].pop("updated_at")
    payload["object_attributes"]["merged_at"] = None
    channel = RecordingChannel()

    asyncio.run(MergeRequestNotificationHooks(channel).handle(make_event(payload)))

    notification = channel.notifications[0]
    assert "项目不可用" in notification.message
    assert "标题不可用" in notification.message
    assert "MR 链接不可用" in notification.message
    assert "时间不可用" in notification.message


def test_missing_critical_fields_are_logged_and_skipped(caplog):
    payload = copy_merge_webhook()
    payload["project"].pop("id")
    channel = RecordingChannel()
    logger = logging.getLogger("test.merge_notification.invalid")
    caplog.set_level(logging.ERROR, logger=logger.name)

    asyncio.run(MergeRequestNotificationHooks(channel, logger=logger).handle(make_event(payload)))

    assert channel.notifications == []
    assert "invalid merged webhook" in caplog.text


def test_merge_notification_does_not_call_gitlab_api():
    channel = RecordingChannel()
    api = SimpleNamespace(
        getitem=lambda *_args, **_kwargs: pytest.fail("merge notification must not call GitLab API"),
        post=lambda *_args, **_kwargs: pytest.fail("merge notification must not call GitLab API"),
    )

    asyncio.run(MergeRequestNotificationHooks(channel).handle(make_event(), api))

    assert len(channel.notifications) == 1
