import asyncio
import json
import logging
from types import SimpleNamespace

from src.delivery.coordinator import NotificationDelivery
from src.delivery.idempotent_channel import DurableIdempotentChannel
from src.delivery.sqlite import NotificationDeliveryStore
from src.hooks.merge_notification import MergeRequestNotificationHooks, build_merged_notification
from tests.fixtures.merge_webhook import copy_merge_webhook


class RecordingChannel:
    def __init__(self):
        self.notifications = []
        self.calls = 0

    async def send(self, notification):
        self.calls += 1
        self.notifications.append(notification)


class YieldingChannel(RecordingChannel):
    async def send(self, notification):
        self.calls += 1
        await asyncio.sleep(0.01)
        self.notifications.append(notification)


class FailingOnceChannel(RecordingChannel):
    def __init__(self):
        super().__init__()
        self.failed = False

    async def send(self, notification):
        self.calls += 1
        if not self.failed:
            self.failed = True
            raise RuntimeError("temporary channel failure")
        self.notifications.append(notification)


class CrashAfterChannel:
    def __init__(self, channel):
        self.channel = channel

    async def send(self, notification):
        await self.channel.send(notification)
        raise KeyboardInterrupt


def make_notification():
    return build_merged_notification(copy_merge_webhook())


def make_delivery(tmp_path, channel, *, timeout=300):
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"), sending_timeout_seconds=timeout)
    durable_channel = DurableIdempotentChannel(channel, store)
    return store, NotificationDelivery(durable_channel, store)


def test_duplicate_delivery_has_one_channel_effect(tmp_path):
    channel = RecordingChannel()
    store, delivery = make_delivery(tmp_path, channel)
    notification = make_notification()

    async def run():
        first = await delivery.deliver(notification)
        second = await delivery.deliver(notification)
        return first, second

    first, second = asyncio.run(run())

    assert first is True
    assert second is False
    assert channel.calls == 1
    assert store.get_delivery(notification.idempotency_key).status == "sent"
    assert store.get_channel_effect(notification.idempotency_key)["status"] == "accepted"


def test_concurrent_delivery_has_one_channel_effect(tmp_path):
    channel = YieldingChannel()
    store, delivery = make_delivery(tmp_path, channel)
    notification = make_notification()

    async def run():
        return await asyncio.gather(
            delivery.deliver(notification),
            delivery.deliver(notification),
        )

    results = asyncio.run(run())

    assert sorted(results) == [False, True]
    assert channel.calls == 1
    assert store.get_delivery(notification.idempotency_key).status == "sent"


def test_channel_failure_is_retryable_and_reuses_key(tmp_path):
    channel = FailingOnceChannel()
    store, delivery = make_delivery(tmp_path, channel)
    notification = make_notification()

    async def run():
        first = await delivery.deliver(notification)
        failed = store.get_delivery(notification.idempotency_key)
        second = await delivery.deliver(notification)
        return first, failed, second

    first, failed, second = asyncio.run(run())

    assert first is False
    assert failed.status == "failed"
    assert second is True
    assert channel.calls == 2
    assert store.get_delivery(notification.idempotency_key).status == "sent"
    assert store.get_delivery(notification.idempotency_key).attempts == 2


def test_retry_backoff_defers_automatic_retry_until_due(tmp_path):
    channel = FailingOnceChannel()
    now = [1000.0]
    store = NotificationDeliveryStore(
        str(tmp_path / "delivery.sqlite3"),
        retry_backoff_seconds=10,
        clock=lambda: now[0],
    )
    delivery = NotificationDelivery(DurableIdempotentChannel(channel, store), store)
    notification = make_notification()

    assert asyncio.run(delivery.deliver(notification)) is False
    assert asyncio.run(delivery.deliver(notification)) is False
    assert channel.calls == 1

    now[0] += 10
    assert asyncio.run(delivery.deliver(notification)) is True
    assert channel.calls == 2


def test_retry_attempts_are_bounded_but_manual_replay_can_continue(tmp_path):
    channel = FailingOnceChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"), max_attempts=1)
    delivery = NotificationDelivery(DurableIdempotentChannel(channel, store), store)
    notification = make_notification()

    assert asyncio.run(delivery.deliver(notification)) is False
    assert asyncio.run(delivery.deliver(notification)) is False
    assert channel.calls == 1
    assert asyncio.run(delivery.replay_failed()) == 1
    assert channel.calls == 2


def test_restart_recovers_failed_delivery_and_manual_replay(tmp_path):
    first_channel = FailingOnceChannel()
    store, first_delivery = make_delivery(tmp_path, first_channel)
    notification = make_notification()
    asyncio.run(first_delivery.deliver(notification))

    second_channel = RecordingChannel()
    second_store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"))
    second_durable_channel = DurableIdempotentChannel(second_channel, second_store)
    second_delivery = NotificationDelivery(second_durable_channel, second_store)

    replayed = asyncio.run(second_delivery.replay_failed())

    assert replayed == 1
    assert second_channel.calls == 1
    assert second_store.get_delivery(notification.idempotency_key).status == "sent"


def test_restart_recovers_stale_sending_delivery(tmp_path):
    channel = RecordingChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"), sending_timeout_seconds=0)
    notification = make_notification()
    store.begin_delivery(notification)

    delivery = NotificationDelivery(DurableIdempotentChannel(channel, store), store)
    recovered = asyncio.run(delivery.recover())

    assert recovered == 1
    assert channel.calls == 1
    assert store.get_delivery(notification.idempotency_key).status == "sent"


def test_crash_after_channel_acceptance_does_not_duplicate_effect(tmp_path):
    channel = RecordingChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"), sending_timeout_seconds=0)
    crashing_delivery = NotificationDelivery(
        DurableIdempotentChannel(CrashAfterChannel(channel), store),
        store,
    )
    notification = make_notification()

    try:
        asyncio.run(crashing_delivery.deliver(notification))
    except KeyboardInterrupt:
        pass

    assert channel.calls == 1
    assert store.get_delivery(notification.idempotency_key).status == "sending"
    assert store.get_channel_effect(notification.idempotency_key)["status"] == "reserved"

    recovered = NotificationDelivery(
        DurableIdempotentChannel(channel, store),
        store,
    )
    assert asyncio.run(recovered.recover()) == 1
    assert channel.calls == 1
    assert store.get_delivery(notification.idempotency_key).status == "sent"
    assert store.get_channel_effect(notification.idempotency_key)["status"] == "accepted"


def test_transport_idempotency_header_overrides_fallback_key(tmp_path):
    channel = RecordingChannel()
    store, delivery = make_delivery(tmp_path, channel)
    hooks = MergeRequestNotificationHooks(
        DurableIdempotentChannel(channel, store),
        delivery=delivery,
    )
    event = SimpleNamespace(data=copy_merge_webhook(), headers={"webhook-id": "hook-123"})

    asyncio.run(hooks.handle(event))

    notification = channel.notifications[0]
    assert notification.idempotency_key == "gitlab:merge:header:hook-123"
    assert store.get_delivery(notification.idempotency_key).status == "sent"


def test_delivery_emits_structured_observability(caplog, tmp_path):
    logger = logging.getLogger("test.notification_delivery")
    caplog.set_level(logging.INFO, logger=logger.name)
    channel = RecordingChannel()
    store = NotificationDeliveryStore(str(tmp_path / "delivery.sqlite3"))
    delivery = NotificationDelivery(DurableIdempotentChannel(channel, store), store, logger=logger)

    asyncio.run(delivery.deliver(make_notification()))

    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "merge_notification_delivery"
    assert payload["action"] == "sent"
    assert delivery.counters["sent"] == 1
