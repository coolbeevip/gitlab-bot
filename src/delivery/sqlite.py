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

from ..notifications.model import MergeRequestNotification, Notification, PipelineNotification

DELIVERY_STATES = frozenset(("pending", "sending", "sent", "failed"))
CHANNEL_EFFECT_STATES = frozenset(("reserved", "accepted", "failed", "unknown"))


@dataclass(frozen=True)
class DeliveryRecord:
    idempotency_key: str
    status: str
    notification: Notification
    attempts: int
    updated_at: float
    last_error: Optional[str]


@dataclass(frozen=True)
class DeliveryDecision:
    should_send: bool
    reason: str


def _serialize_notification(notification: Notification) -> str:
    data = asdict(notification)
    data["_notification_type"] = "pipeline" if isinstance(notification, PipelineNotification) else "merge_request"
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _deserialize_notification(payload: str) -> Notification:
    data = json.loads(payload)
    notification_type = data.pop("_notification_type", None)
    if notification_type == "pipeline" or (notification_type is None and "pipeline" in data):
        return PipelineNotification(
            source=data["source"],
            event_type=data["event_type"],
            action=data["action"],
            webhook_action=data["webhook_action"],
            status=data["status"],
            message=data["message"],
            project=data["project"],
            pipeline=data["pipeline"],
            actor=data["actor"],
            occurred_at=data.get("occurred_at"),
            merge_request=data.get("merge_request"),
            raw_payload=data.get("raw_payload"),
            idempotency_key=data.get("idempotency_key"),
        )
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
        max_attempts: int = 5,
        retry_backoff_seconds: float = 0.0,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.path = path
        self.sending_timeout_seconds = sending_timeout_seconds
        self.max_attempts = max(1, int(max_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
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
                idempotency_key TEXT NOT NULL,
                delivery_target TEXT NOT NULL DEFAULT 'log',
                status TEXT NOT NULL CHECK(status IN ('reserved', 'accepted', 'failed', 'unknown')),
                notification_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_error TEXT,
                message_id TEXT,
                PRIMARY KEY (idempotency_key, delivery_target)
            );
            CREATE INDEX IF NOT EXISTS idx_notification_deliveries_status
                ON notification_deliveries(status);
            """
        )
        delivery_columns = {row[1] for row in connection.execute("PRAGMA table_info(notification_deliveries)")}
        if "next_attempt_at" not in delivery_columns:
            connection.execute("ALTER TABLE notification_deliveries ADD COLUMN next_attempt_at REAL")
        self._migrate_legacy_channel_effects(connection)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_channel_effects_target_status "
            "ON channel_effects(delivery_target, status)"
        )
        return connection

    @staticmethod
    def _migrate_legacy_channel_effects(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(channel_effects)").fetchall()}
        if columns and "delivery_target" not in columns:
            legacy_table = "channel_effects_legacy"
            legacy_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (legacy_table,),
            ).fetchone()
            if legacy_exists is None:
                connection.execute("ALTER TABLE channel_effects RENAME TO channel_effects_legacy")
            else:
                connection.execute("ALTER TABLE channel_effects RENAME TO channel_effects_legacy_v1")
                legacy_table = "channel_effects_legacy_v1"
            connection.execute(
                """
                CREATE TABLE channel_effects (
                    idempotency_key TEXT NOT NULL,
                    delivery_target TEXT NOT NULL DEFAULT 'log',
                    status TEXT NOT NULL CHECK(status IN ('reserved', 'accepted', 'failed', 'unknown')),
                    notification_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_error TEXT,
                    message_id TEXT,
                    PRIMARY KEY (idempotency_key, delivery_target)
                )
                """
            )
            connection.execute(
                f"""
                INSERT OR IGNORE INTO channel_effects
                    (idempotency_key, delivery_target, status, notification_json,
                     created_at, updated_at, last_error, message_id)
                SELECT idempotency_key, 'log', status, notification_json,
                       created_at, updated_at, last_error, NULL
                FROM {legacy_table}
                """
            )

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

    def begin_delivery(self, notification: Notification, *, force: bool = False) -> DeliveryDecision:
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

            if row["status"] == "failed" and not force:
                if row["attempts"] >= self.max_attempts:
                    connection.commit()
                    return DeliveryDecision(False, "retry_exhausted")
                next_attempt_at = row["next_attempt_at"]
                if next_attempt_at is not None and now < next_attempt_at:
                    connection.commit()
                    return DeliveryDecision(False, "retry_not_due")

            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'sending', notification_json = ?, attempts = attempts + 1,
                    updated_at = ?, claimed_at = ?, last_error = NULL, next_attempt_at = NULL
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
                SET status = 'sent', updated_at = ?, claimed_at = NULL,
                    last_error = NULL, next_attempt_at = NULL
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
            row = connection.execute(
                "SELECT attempts FROM notification_deliveries WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            attempts = int(row["attempts"]) if row is not None else 1
            delay = min(self.retry_backoff_seconds * (2 ** max(attempts - 1, 0)), 300.0)
            connection.execute(
                """
                UPDATE notification_deliveries
                SET status = 'failed', updated_at = ?, claimed_at = NULL,
                    last_error = ?, next_attempt_at = ?
                WHERE idempotency_key = ? AND status != 'sent'
                """,
                (now, error, now + delay, idempotency_key),
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
                   AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                   OR (status = 'sending' AND (claimed_at IS NULL OR claimed_at <= ?))
                ORDER BY created_at ASC
                """,
                (self._clock(), threshold),
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

    def claim_channel_effect(self, notification: Notification, delivery_target: str = "log") -> bool:
        key = notification.idempotency_key
        if not key:
            raise ValueError("notification idempotency_key is required")
        if not delivery_target:
            raise ValueError("delivery_target is required")
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT status FROM channel_effects
                WHERE idempotency_key = ? AND delivery_target = ?
                """,
                (key, delivery_target),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO channel_effects
                        (idempotency_key, delivery_target, status, notification_json, created_at, updated_at)
                    VALUES (?, ?, 'reserved', ?, ?, ?)
                    """,
                    (key, delivery_target, _serialize_notification(notification), now, now),
                )
                connection.commit()
                return True
            if row["status"] == "failed":
                connection.execute(
                    """
                    UPDATE channel_effects
                    SET status = 'reserved', notification_json = ?, updated_at = ?, last_error = NULL
                    WHERE idempotency_key = ? AND delivery_target = ?
                    """,
                    (_serialize_notification(notification), now, key, delivery_target),
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

    def mark_channel_accepted(
        self,
        idempotency_key: str,
        delivery_target: str = "log",
        message_id: Optional[str] = None,
    ) -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE channel_effects
                SET status = 'accepted', updated_at = ?, last_error = NULL,
                    message_id = COALESCE(?, message_id)
                WHERE idempotency_key = ? AND delivery_target = ?
                  AND status IN ('reserved', 'accepted', 'unknown')
                """,
                (now, message_id, idempotency_key, delivery_target),
            )
        finally:
            connection.close()

    def release_channel_effect(self, idempotency_key: str, error: str, delivery_target: str = "log") -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE channel_effects
                SET status = 'failed', updated_at = ?, last_error = ?
                WHERE idempotency_key = ? AND delivery_target = ? AND status = 'reserved'
                """,
                (now, error, idempotency_key, delivery_target),
            )
        finally:
            connection.close()

    def mark_channel_unknown(self, idempotency_key: str, error: str, delivery_target: str = "feishu") -> None:
        now = self._clock()
        connection = self._connect()
        try:
            connection.execute(
                """
                UPDATE channel_effects
                SET status = 'unknown', updated_at = ?, last_error = ?
                WHERE idempotency_key = ? AND delivery_target = ? AND status = 'reserved'
                """,
                (now, error, idempotency_key, delivery_target),
            )
        finally:
            connection.close()

    def get_channel_effect(self, idempotency_key: str, delivery_target: str = "log") -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            row = connection.execute(
                """
                SELECT * FROM channel_effects
                WHERE idempotency_key = ? AND delivery_target = ?
                """,
                (idempotency_key, delivery_target),
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            connection.close()

    def get_channel_effects(self, idempotency_key: str) -> List[Dict[str, Any]]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM channel_effects WHERE idempotency_key = ? ORDER BY delivery_target",
                (idempotency_key,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()
