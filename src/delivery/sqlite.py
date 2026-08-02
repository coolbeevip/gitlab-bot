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
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..notifications.model import MergeRequestNotification

DELIVERY_STATES = frozenset(("pending", "sending", "sent", "failed"))
CHANNEL_EFFECT_STATES = frozenset(("reserved", "accepted", "failed"))


@dataclass(frozen=True)
class DeliveryRecord:
    idempotency_key: str
    status: str
    notification: MergeRequestNotification
    attempts: int
    updated_at: float
    last_error: Optional[str]


@dataclass(frozen=True)
class DeliveryDecision:
    should_send: bool
    reason: str


def _serialize_notification(notification: MergeRequestNotification) -> str:
    return json.dumps(asdict(notification), ensure_ascii=False, sort_keys=True)


def _deserialize_notification(payload: str) -> MergeRequestNotification:
    data = json.loads(payload)
    return MergeRequestNotification(
        source=data["source"],
        event_type=data["event_type"],
        action=data["action"],
        webhook_action=data["webhook_action"],
        message=data["message"],
        project=data["project"],
        merge_request=data["merge_request"],
        actor=data["actor"],
        occurred_at=data.get("occurred_at"),
        raw_payload=data.get("raw_payload"),
        triggered_by=data.get("triggered_by"),
        idempotency_key=data.get("idempotency_key"),
    )


class NotificationDeliveryStore:
    """SQLite-backed state and Channel-effect ledger for notifications."""

    def __init__(
        self,
        path: str,
        *,
        sending_timeout_seconds: float = 300.0,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.path = path
        self.sending_timeout_seconds = sending_timeout_seconds
        self._clock = clock or time.time

    def _connect(self) -> sqlite3.Connection:
        if self.path != ":memory:":
            parent = Path(self.path).expanduser().parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        if self.path != ":memory:":
            connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notification_deliveries (
                idempotency_key TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('pending', 'sending', 'sent', 'failed')),
                notification_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                claimed_at REAL,
                last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS channel_effects (
                idempotency_key TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('reserved', 'accepted', 'failed')),
                notification_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_notification_deliveries_status
                ON notification_deliveries(status);
            """
        )
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> DeliveryRecord:
        return DeliveryRecord(
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            notification=_deserialize_notification(row["notification_json"]),
            attempts=row["attempts"],
            updated_at=row["updated_at"],
            last_error=row["last_error"],
        )

    def begin_delivery(self, notification: MergeRequestNotification) -> DeliveryDecision:
        key = notification.idempotency_key
        if not key:
            raise ValueError("notification idempotency_key is required")
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM notification_deliveries WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO notification_deliveries
                        (idempotency_key, status, notification_json, attempts, created_at, updated_at, claimed_at)
                    VALUES (?, 'sending', ?, 1, ?, ?, ?)
                    """,
                    (key, _serialize_notification(notification), now, now, now),
                )
                connection.commit()
                return DeliveryDecision(True, "new")

            if row["status"] == "sent":
                connection.commit()
                return DeliveryDecision(False, "already_sent")

            if row["status"] == "sending":
                claimed_at = row["claimed_at"]
                is_active = claimed_at is not None and now - claimed_at < self.sending_timeout_seconds
                if is_active:
                    connection.commit()
                    return DeliveryDecision(False, "in_flight")

            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'sending', notification_json = ?, attempts = attempts + 1,
                    updated_at = ?, claimed_at = ?, last_error = NULL
                WHERE idempotency_key = ?
                """,
                (_serialize_notification(notification), now, now, key),
            )
            connection.commit()
            return DeliveryDecision(True, "retry")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_sent(self, idempotency_key: str) -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'sent', updated_at = ?, claimed_at = NULL, last_error = NULL
                WHERE idempotency_key = ? AND status != 'sent'
                """,
                (now, idempotency_key),
            )
        finally:
            connection.close()

    def mark_failed(self, idempotency_key: str, error: str) -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'failed', updated_at = ?, claimed_at = NULL, last_error = ?
                WHERE idempotency_key = ? AND status != 'sent'
                """,
                (now, error, idempotency_key),
            )
        finally:
            connection.close()

    def get_delivery(self, idempotency_key: str) -> Optional[DeliveryRecord]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM notification_deliveries WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            return self._record(row) if row is not None else None
        finally:
            connection.close()

    def recoverable_deliveries(self) -> List[DeliveryRecord]:
        threshold = self._clock() - self.sending_timeout_seconds
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM notification_deliveries
                WHERE status IN ('pending', 'failed')
                   OR (status = 'sending' AND (claimed_at IS NULL OR claimed_at <= ?))
                ORDER BY created_at ASC
                """,
                (threshold,),
            ).fetchall()
            return [self._record(row) for row in rows]
        finally:
            connection.close()

    def failed_deliveries(self) -> List[DeliveryRecord]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM notification_deliveries WHERE status = 'failed' ORDER BY updated_at ASC"
            ).fetchall()
            return [self._record(row) for row in rows]
        finally:
            connection.close()

    def claim_channel_effect(self, notification: MergeRequestNotification) -> bool:
        key = notification.idempotency_key
        if not key:
            raise ValueError("notification idempotency_key is required")
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM channel_effects WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO channel_effects
                        (idempotency_key, status, notification_json, created_at, updated_at)
                    VALUES (?, 'reserved', ?, ?, ?)
                    """,
                    (key, _serialize_notification(notification), now, now),
                )
                connection.commit()
                return True
            if row["status"] == "failed":
                connection.execute(
                    """
                    UPDATE channel_effects
                    SET status = 'reserved', notification_json = ?, updated_at = ?, last_error = NULL
                    WHERE idempotency_key = ?
                    """,
                    (_serialize_notification(notification), now, key),
                )
                connection.commit()
                return True
            connection.commit()
            return False
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_channel_accepted(self, idempotency_key: str) -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE channel_effects
                SET status = 'accepted', updated_at = ?, last_error = NULL
                WHERE idempotency_key = ? AND status IN ('reserved', 'accepted')
                """,
                (now, idempotency_key),
            )
        finally:
            connection.close()

    def release_channel_effect(self, idempotency_key: str, error: str) -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE channel_effects
                SET status = 'failed', updated_at = ?, last_error = ?
                WHERE idempotency_key = ? AND status = 'reserved'
                """,
                (now, error, idempotency_key),
            )
        finally:
            connection.close()

    def get_channel_effect(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM channel_effects WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            connection.close()
