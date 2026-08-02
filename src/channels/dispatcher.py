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

import asyncio
import json
import logging
from typing import Dict, Mapping, Optional

from ..notifications.model import Notification
from .base import Channel


class NotificationDispatchError(RuntimeError):
    """Raised after all notification targets have had a chance to process a notification."""

    def __init__(self, errors: Mapping[str, BaseException]):
        self.errors = dict(errors)
        summary = ", ".join(f"{target}: {type(error).__name__}" for target, error in self.errors.items())
        super().__init__(f"notification dispatch failed ({summary})")


class NotificationDispatcher(Channel):
    """Send one normalized notification to independent named targets."""

    def __init__(self, channels: Mapping[str, Channel], logger: Optional[logging.Logger] = None):
        if not channels:
            raise ValueError("NotificationDispatcher requires at least one target")
        self.channels = dict(channels)
        self.logger = logger or logging.getLogger(__name__)

    async def send(self, notification: Notification) -> None:
        target_names = tuple(self.channels)
        results = await asyncio.gather(
            *(self.channels[target].send(notification) for target in target_names),
            return_exceptions=True,
        )
        errors: Dict[str, BaseException] = {}
        for target, result in zip(target_names, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                errors[target] = result
                self.logger.error(
                    json.dumps(
                        {
                            "event": "notification_channel_failed",
                            "target": target,
                            "notification_action": notification.action,
                            "error_type": type(result).__name__,
                            "error": str(result),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
        if errors:
            raise NotificationDispatchError(errors)


__all__ = ["NotificationDispatchError", "NotificationDispatcher"]
