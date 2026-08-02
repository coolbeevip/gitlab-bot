import asyncio
import json
import sqlite3
from dataclasses import asdict
from types import SimpleNamespace

from src.channels.dispatcher import NotificationDispatcher
from src.delivery.coordinator import NotificationDelivery
from src.delivery.idempotent_channel import DurableIdempotentChannel
from src.delivery.sqlite import NotificationDeliveryStore
from src.hooks.merge_notification import build_merged_notification
from src.hooks.pipeline_notification import PipelineNotificationHooks, build_pipeline_notification
from src.notifications.model import PipelineNotification
from tests.fixtures.merge_webhook import copy_merge_webhook
from tests.fixtures.pipeline_webhook import copy_pipeline_webhook


def test_feishu_is_not_constructed_when_disabled(monkeypatch):
    import gitlab_bot

    monkeypatch.setattr(gitlab_bot, "feishu_enabled", False)

    targets = gitlab_bot._build_notification_targets()

    assert tuple(targets) == ("log",)


class RecordingChannel:
    def __init__(self):
        self.calls = 0
        self.notifications = []

    async def send(self, notification):
        self.calls += 1
        self.notifications.append(notification)


class FailingOnceChannel(RecordingChannel):
    def __init__(self):
        super().__init__()
        self.failed = False

    async def send(self, notification):
        self.calls += 1
        if not self.failed:
            self.failed = True
            raise RuntimeError("temporary Feishu failure")
        self.notifications.append(notification)


def make_durable_dispatcher(store, log_channel, feishu_channel):
    return NotificationDispatcher(
        {
            "log": DurableIdempotentChannel(log_channel, store, delivery_target="log"),
            "feishu": DurableIdempotentChannel(feishu_channel, store, delivery_target="feishu"),
        }
    )


def test_pipeline_delivery_keeps_log_success_when_feishu_retries(tmp_path):
    log_channel = RecordingChannel()
    feishu_channel = FailingOnceChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"))
    dispatcher = make_durable_dispatcher(store, log_channel, feishu_channel)
    delivery = NotificationDelivery(dispatcher, store)
    notification = build_pipeline_notification(copy_pipeline_webhook(status="failed"))

    first = asyncio.run(delivery.deliver(notification))
    first_record = store.get_delivery(notification.idempotency_key)
    first_log_effect = store.get_channel_effect(notification.idempotency_key, "log")
    first_feishu_effect = store.get_channel_effect(notification.idempotency_key, "feishu")
    second = asyncio.run(delivery.deliver(notification))

    assert first is False
    assert second is True
    assert first_record.status == "failed"
    assert first_log_effect["status"] == "accepted"
    assert first_feishu_effect["status"] == "failed"
    assert log_channel.calls == 1
    assert feishu_channel.calls == 2
    assert store.get_channel_effect(notification.idempotency_key, "feishu")["status"] == "accepted"
    assert store.get_delivery(notification.idempotency_key).status == "sent"


def test_pipeline_hook_uses_durable_delivery_and_serializes_pipeline_notification(tmp_path):
    log_channel = RecordingChannel()
    feishu_channel = RecordingChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"))
    dispatcher = make_durable_dispatcher(store, log_channel, feishu_channel)
    delivery = NotificationDelivery(dispatcher, store)
    hooks = PipelineNotificationHooks(dispatcher, delivery=delivery)
    event = SimpleNamespace(data=copy_pipeline_webhook(status="success"))

    asyncio.run(hooks.handle(event))

    notification = log_channel.notifications[0]
    record = store.get_delivery(notification.idempotency_key)
    assert isinstance(record.notification, PipelineNotification)
    assert record.notification.status == "success"
    assert log_channel.calls == 1
    assert feishu_channel.calls == 1


def test_pipeline_hook_without_delivery_keeps_direct_channel_contract():
    channel = RecordingChannel()
    hooks = PipelineNotificationHooks(channel)

    asyncio.run(hooks.handle(SimpleNamespace(data=copy_pipeline_webhook(status="success"))))

    assert channel.calls == 1


def test_legacy_single_target_effects_are_migrated_as_log(tmp_path):
    notification = build_merged_notification(copy_merge_webhook())
    database_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE channel_effects (
            idempotency_key TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK(status IN ('reserved', 'accepted', 'failed')),
            notification_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_error TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO channel_effects VALUES (?, 'accepted', ?, 1, 1, NULL)",
        (notification.idempotency_key, json.dumps(asdict(notification))),
    )
    connection.commit()
    connection.close()

    store = NotificationDeliveryStore(str(database_path))
    effect = store.get_channel_effect(notification.idempotency_key, "log")

    assert effect["delivery_target"] == "log"
    assert effect["status"] == "accepted"
    assert store.get_channel_effect(notification.idempotency_key, "feishu") is None
