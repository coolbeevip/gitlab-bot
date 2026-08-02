import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from gidgetlab.sansio import Event

import gitlab_bot
from src.channels.log import LogChannel
from src.hooks.pipeline_notification import PipelineNotificationHooks, build_pipeline_notification
from tests.fixtures.pipeline_webhook import copy_pipeline_webhook


class RecordingChannel:
    def __init__(self):
        self.notifications = []

    async def send(self, notification):
        self.notifications.append(notification)


def make_event(payload=None):
    return SimpleNamespace(data=payload or copy_pipeline_webhook())


@pytest.mark.parametrize("status", ["success", "failed"])
def test_build_pipeline_notification_contains_pipeline_and_merge_request_details(status):
    notification = build_pipeline_notification(copy_pipeline_webhook(status=status))

    assert notification.source == "gitlab"
    assert notification.event_type == "pipeline_lifecycle"
    assert notification.action == status
    assert notification.status == status
    assert notification.webhook_action == "status_changed"
    assert notification.project["id"] == 76
    assert notification.pipeline["id"] == 31
    assert notification.pipeline["status"] == status
    assert notification.merge_request["iid"] == 12
    assert "Pipeline #31" in notification.message
    assert "MR !12" in notification.message
    assert status in notification.message
    assert "group/project" in notification.message
    assert "https://gitlab.example.com/group/project/-/pipelines/31" in notification.message


def test_build_branch_pipeline_without_merge_request():
    notification = build_pipeline_notification(copy_pipeline_webhook(include_merge_request=False))

    assert notification.merge_request is None
    assert "MR !" not in notification.message


@pytest.mark.parametrize("status", ["created", "pending", "running", "canceled", "skipped"])
def test_non_terminal_pipeline_statuses_are_skipped(status):
    channel = RecordingChannel()

    asyncio.run(PipelineNotificationHooks(channel).handle(make_event(copy_pipeline_webhook(status=status))))

    assert channel.notifications == []


@pytest.mark.parametrize("status", ["success", "failed"])
def test_pipeline_route_sends_success_and_failure_notifications(monkeypatch, status):
    channel = RecordingChannel()
    monkeypatch.setattr(gitlab_bot, "pipeline_notification_hooks", PipelineNotificationHooks(channel))
    event = Event(copy_pipeline_webhook(status=status), event="Pipeline Hook")

    asyncio.run(gitlab_bot.bot.router.dispatch(event, None))

    assert len(channel.notifications) == 1
    assert channel.notifications[0].status == status


def test_pipeline_notification_uses_webhook_id_when_available():
    channel = RecordingChannel()
    event = SimpleNamespace(data=copy_pipeline_webhook(), headers={"webhook-id": "pipeline-hook-123"})

    asyncio.run(PipelineNotificationHooks(channel).handle(event))

    assert channel.notifications[0].idempotency_key == "gitlab:pipeline:header:pipeline-hook-123"


def test_log_channel_emits_structured_pipeline_json(caplog):
    logger = logging.getLogger("test.pipeline_notification")
    channel = LogChannel(logger)
    notification = build_pipeline_notification(copy_pipeline_webhook(status="failed"))
    caplog.set_level(logging.INFO, logger=logger.name)

    asyncio.run(channel.send(notification))

    payload = json.loads(caplog.records[-1].message)
    assert payload["status"] == "failed"
    assert payload["pipeline"]["id"] == 31
    assert payload["merge_request"]["iid"] == 12


def test_invalid_pipeline_payload_is_logged_and_skipped(caplog):
    logger = logging.getLogger("test.pipeline_notification.invalid")
    channel = RecordingChannel()
    hooks = PipelineNotificationHooks(channel, logger=logger)
    caplog.set_level(logging.ERROR, logger=logger.name)

    asyncio.run(hooks.handle(SimpleNamespace(data={"object_attributes": {"status": "success"}})))

    assert channel.notifications == []
    assert "invalid pipeline webhook" in caplog.text


def test_pipeline_notification_does_not_call_gitlab_api():
    channel = RecordingChannel()
    api = SimpleNamespace(
        getitem=lambda *_args, **_kwargs: pytest.fail("pipeline notification must not call GitLab API"),
        post=lambda *_args, **_kwargs: pytest.fail("pipeline notification must not call GitLab API"),
    )

    asyncio.run(PipelineNotificationHooks(channel).handle(make_event(), api))

    assert len(channel.notifications) == 1
