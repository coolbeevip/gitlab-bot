import asyncio

import pytest

from src.channels.dispatcher import NotificationDispatcher, NotificationDispatchError
from src.hooks.pipeline_notification import build_pipeline_notification
from tests.fixtures.pipeline_webhook import copy_pipeline_webhook


class RecordingChannel:
    def __init__(self, error=None):
        self.notifications = []
        self.error = error

    async def send(self, notification):
        self.notifications.append(notification)
        if self.error:
            raise self.error


def test_dispatcher_runs_all_targets_and_preserves_partial_success():
    log_channel = RecordingChannel()
    feishu_channel = RecordingChannel(RuntimeError("feishu unavailable"))
    dispatcher = NotificationDispatcher({"log": log_channel, "feishu": feishu_channel})
    notification = build_pipeline_notification(copy_pipeline_webhook(status="failed"))

    with pytest.raises(NotificationDispatchError) as error:
        asyncio.run(dispatcher.send(notification))

    assert log_channel.notifications == [notification]
    assert feishu_channel.notifications == [notification]
    assert set(error.value.errors) == {"feishu"}


def test_dispatcher_with_one_target_keeps_log_only_mode():
    log_channel = RecordingChannel()
    dispatcher = NotificationDispatcher({"log": log_channel})
    notification = build_pipeline_notification(copy_pipeline_webhook(status="success"))

    asyncio.run(dispatcher.send(notification))

    assert log_channel.notifications == [notification]
