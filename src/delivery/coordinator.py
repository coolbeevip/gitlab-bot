# Copyright 2026 Lei Zhang
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
from collections import Counter
from typing import Any, List, Optional

from ..channels.base import Channel
from ..notifications.model import Notification
from .sqlite import DeliveryRecord, NotificationDeliveryStore


class NotificationDelivery:
    """Coordinate durable delivery state, recovery, and observability."""

    def __init__(
        self,
        channel: Channel,
        store: NotificationDeliveryStore,
        logger: Optional[logging.Logger] = None,
    ):
        self.channel = channel
        self.store = store
        self.logger = logger or logging.getLogger(__name__)
        self.counters = Counter()

    def _log(self, level: int, event: str, notification: Notification, **extra: Any) -> None:
        merge_request = notification.merge_request or {}
        pipeline = notification.pipeline if hasattr(notification, "pipeline") else {}
        payload = {
            "event": "merge_notification_delivery",
            "action": event,
            "idempotency_key": notification.idempotency_key,
            "project": notification.project.get("path") or notification.project.get("id"),
            "mr_iid": merge_request.get("iid"),
            "pipeline_id": pipeline.get("id"),
            "notification_type": type(notification).__name__,
        }
        payload.update(extra)
        self.logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
        self.counters[event] += 1

    async def deliver(self, notification: Notification, *, force: bool = False) -> bool:
        try:
            decision = self.store.begin_delivery(notification, force=force)
        except Exception as exc:
            self.counters["failed"] += 1
            self.logger.error("notification delivery state failed: %s", exc, exc_info=True)
            return False
        if not decision.should_send:
            self._log(logging.INFO, "duplicate", notification, reason=decision.reason)
            return False

        try:
            await self.channel.send(notification)
        except Exception as exc:
            self.store.mark_failed(notification.idempotency_key, str(exc))
            self._log(logging.ERROR, "failed", notification, error=str(exc))
            return False

        reconcile = getattr(self.channel, "reconcile", None)
        if callable(reconcile):
            reconcile(notification)
        self.store.mark_sent(notification.idempotency_key)
        self._log(logging.INFO, "sent", notification, reason=decision.reason)
        return True

    async def recover(self) -> int:
        recovered = 0
        for record in self.store.recoverable_deliveries():
            if await self.deliver(record.notification):
                recovered += 1
        if recovered:
            self.logger.info(
                json.dumps({"event": "merge_notification_recovery", "count": recovered}, sort_keys=True)
            )
        return recovered

    async def replay_failed(self) -> int:
        replayed = 0
        for record in self.store.failed_deliveries():
            if await self.deliver(record.notification, force=True):
                replayed += 1
        if replayed:
            self.logger.info(
                json.dumps({"event": "merge_notification_replay", "count": replayed}, sort_keys=True)
            )
        return replayed

    def failure_backlog(self) -> List[DeliveryRecord]:
        return self.store.failed_deliveries()
