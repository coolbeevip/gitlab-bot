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

# ruff: noqa: RUF001

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

import aiohttp

from ..notifications.model import MergeRequestNotification, Notification, PipelineNotification
from .base import Channel

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"


class FeishuError(RuntimeError):
    """Base error for a failed Feishu notification operation."""


class FeishuConfigError(FeishuError):
    """Raised when Feishu configuration is incomplete or invalid."""


class FeishuTransportError(FeishuError):
    """Raised when a Feishu request cannot reach the service."""


class FeishuHTTPError(FeishuError):
    """Raised when Feishu returns an unsuccessful HTTP status."""


class FeishuResponseError(FeishuError):
    """Raised when a Feishu response is malformed or reports a business error."""


class FeishuAuthenticationError(FeishuResponseError):
    """Raised when tenant access token acquisition fails."""


@dataclass(frozen=True)
class FeishuConfig:
    app_id: str
    app_secret: str
    chat_id: str
    bot_open_id: Optional[str] = None
    timeout_seconds: float = 10.0


def _display(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _project_label(notification: Notification) -> str:
    project = notification.project
    return _display(
        project.get("path")
        or project.get("path_with_namespace")
        or project.get("name")
        or project.get("id")
    )


def _format_duration(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number)}s"
    return f"{number:g}s"


def _actor_label(actor: Mapping[str, Any]) -> str:
    name = actor.get("name") or actor.get("username") or actor.get("id")
    username = actor.get("username")
    if name is None:
        return "—"
    if username and str(username) != str(name):
        return f"{name} (@{username})"
    return str(name)


def format_notification(notification: Notification) -> str:
    """Format a normalized notification without reading a GitLab webhook payload."""

    if isinstance(notification, MergeRequestNotification):
        action_labels = {
            "approval": ("✅", "已批准"),
            "unapproval": ("↩️", "撤销批准"),
            "merged": ("🔀", "已合并"),
        }
        emoji, action = action_labels.get(notification.action, ("ℹ️", notification.action or "变更"))
        merge_request = notification.merge_request
        return "\n".join(
            (
                f"{emoji} [{_project_label(notification)}] MR {action}",
                f"编号：!{_display(merge_request.get('iid'))}",
                f"标题：{_display(merge_request.get('title'))}",
                f"操作人：{_actor_label(notification.actor)}",
                f"链接：{_display(merge_request.get('url'))}",
            )
        )

    if isinstance(notification, PipelineNotification):
        pipeline = notification.pipeline
        status = notification.status or pipeline.get("status") or "unknown"
        emoji = {"success": "✅", "failed": "❌"}.get(status, "ℹ️")
        lines = [
            f"{emoji} [{_project_label(notification)}] Pipeline {status}",
            f"分支：{_display(pipeline.get('ref'))}",
            f"耗时：{_format_duration(pipeline.get('duration'))}",
        ]
        merge_request = notification.merge_request
        if merge_request:
            lines.append(f"关联 MR：!{_display(merge_request.get('iid'))} {_display(merge_request.get('title'))}")
        lines.append(f"链接：{_display(pipeline.get('url'))}")
        return "\n".join(lines)

    raise TypeError(f"unsupported notification type: {type(notification).__name__}")


class FeishuChannel(Channel):
    """Send normalized notifications to one Feishu chat as text messages."""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        chat_id: str,
        *,
        bot_open_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
        session_factory: Optional[Callable[..., aiohttp.ClientSession]] = None,
        clock: Optional[Callable[[], float]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        missing = [
            name
            for name, value in (
                ("FEISHU_APP_ID", app_id),
                ("FEISHU_APP_SECRET", app_secret),
                ("FEISHU_CHAT_ID", chat_id),
            )
            if not value
        ]
        if missing:
            raise FeishuConfigError(f"missing Feishu configuration: {', '.join(missing)}")
        if timeout_seconds <= 0:
            raise FeishuConfigError("FEISHU_REQUEST_TIMEOUT_SECONDS must be greater than zero")

        self.config = FeishuConfig(
            app_id=str(app_id),
            app_secret=str(app_secret),
            chat_id=str(chat_id),
            bot_open_id=str(bot_open_id) if bot_open_id else None,
            timeout_seconds=float(timeout_seconds),
        )
        self._session_factory = session_factory or aiohttp.ClientSession
        self._clock = clock or time.time
        self._logger = logger or logging.getLogger(__name__)
        self._token: Optional[str] = None
        self._token_expires_at = 0.0
        self._token_lock: Optional[asyncio.Lock] = None
        self.last_message_id: Optional[str] = None

    @classmethod
    def from_environment(
        cls,
        *,
        app_id: Optional[str],
        app_secret: Optional[str],
        chat_id: Optional[str],
        bot_open_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
        session_factory: Optional[Callable[..., aiohttp.ClientSession]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> "FeishuChannel":
        return cls(
            app_id or "",
            app_secret or "",
            chat_id or "",
            bot_open_id=bot_open_id,
            timeout_seconds=timeout_seconds,
            session_factory=session_factory,
            logger=logger,
        )

    async def _post_json(
        self,
        url: str,
        *,
        payload: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        try:
            async with self._session_factory(timeout=timeout) as session:
                async with session.post(url, json=dict(payload), headers=dict(headers or {})) as response:
                    try:
                        data = await response.json(content_type=None)
                    except (TypeError, ValueError) as exc:
                        raise FeishuResponseError("Feishu returned invalid JSON") from exc
                    if response.status < 200 or response.status >= 300:
                        raise FeishuHTTPError(f"Feishu HTTP request failed (status={response.status})")
                    if not isinstance(data, Mapping):
                        raise FeishuResponseError("Feishu returned an invalid response object")
                    return dict(data)
        except FeishuError:
            raise
        except asyncio.TimeoutError as exc:
            raise FeishuTransportError("Feishu request timed out") from exc
        except aiohttp.ClientError as exc:
            raise FeishuTransportError("Feishu request failed") from exc

    async def _get_tenant_access_token(self) -> str:
        now = self._clock()
        if self._token and self._token_expires_at > now + 60:
            return self._token

        if self._token_lock is None:
            self._token_lock = asyncio.Lock()
        async with self._token_lock:
            now = self._clock()
            if self._token and self._token_expires_at > now + 60:
                return self._token

            data = await self._post_json(
                TOKEN_URL,
                payload={"app_id": self.config.app_id, "app_secret": self.config.app_secret},
                headers={"Content-Type": "application/json"},
            )
            code = data.get("code")
            token = data.get("tenant_access_token")
            if code != 0 or not token:
                message = _display(data.get("msg") or data.get("message"), "unknown error")
                raise FeishuAuthenticationError(f"tenant access token request failed (code={code}, message={message})")
            try:
                expires_in = int(data.get("expire", data.get("expire_seconds", 7200)))
            except (TypeError, ValueError):
                expires_in = 7200
            self._token = str(token)
            self._token_expires_at = self._clock() + max(expires_in, 0)
            self._logger.info(json.dumps({"event": "feishu_token_refreshed"}, ensure_ascii=False))
            return self._token

    async def send(self, notification: Notification) -> None:
        message = format_notification(notification)
        if self.config.bot_open_id:
            message = f'<at user_id="{self.config.bot_open_id}"></at> {message}'

        token = await self._get_tenant_access_token()
        data = await self._post_json(
            MESSAGE_URL,
            payload={
                "receive_id": self.config.chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": message}, ensure_ascii=False),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        code = data.get("code")
        if code != 0:
            error_message = _display(data.get("msg") or data.get("message"), "unknown error")
            raise FeishuResponseError(f"Feishu message request failed (code={code}, message={error_message})")

        response_data = data.get("data")
        message_id = response_data.get("message_id") if isinstance(response_data, Mapping) else None
        self.last_message_id = str(message_id) if message_id else None
        self._logger.info(
            json.dumps(
                {
                    "event": "feishu_notification_sent",
                    "project": _project_label(notification),
                    "notification_action": notification.action,
                    "message_id": self.last_message_id,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )


__all__ = [
    "FeishuAuthenticationError",
    "FeishuChannel",
    "FeishuConfig",
    "FeishuConfigError",
    "FeishuError",
    "FeishuHTTPError",
    "FeishuResponseError",
    "FeishuTransportError",
    "MESSAGE_URL",
    "TOKEN_URL",
    "format_notification",
]
