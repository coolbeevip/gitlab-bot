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

from ..channels.base import Channel
from ..notifications.model import Notification
from .sqlite import NotificationDeliveryStore


class DurableIdempotentChannel(Channel):
    """Add a durable idempotency ledger around an existing Channel."""

    def __init__(self, channel: Channel, store: NotificationDeliveryStore, delivery_target: str = "log"):
        self.channel = channel
        self.store = store
        self.delivery_target = delivery_target

    async def send(self, notification: Notification) -> None:
        if not self.store.claim_channel_effect(notification, delivery_target=self.delivery_target):
            return
        try:
            await self.channel.send(notification)
        except Exception as exc:
            self.store.release_channel_effect(
                notification.idempotency_key,
                str(exc),
                delivery_target=self.delivery_target,
            )
            raise
        self.store.mark_channel_accepted(
            notification.idempotency_key,
            delivery_target=self.delivery_target,
            message_id=getattr(self.channel, "last_message_id", None),
        )

    def reconcile(self, notification: Notification) -> None:
        self.store.mark_channel_accepted(
            notification.idempotency_key,
            delivery_target=self.delivery_target,
            message_id=getattr(self.channel, "last_message_id", None),
        )
