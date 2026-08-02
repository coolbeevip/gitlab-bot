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

import logging
from typing import Any, Dict, Mapping, Optional

from ..channels.base import Channel
from ..notifications.model import MergeRequestNotification

MERGE_WEBHOOK_ACTION = "merge"
MERGED_NOTIFICATION_ACTION = "merged"
MERGE_NOTIFICATION_EVENT_TYPE = "merge_request_lifecycle"
AUTO_MERGE_ACTOR = {
    "id": None,
    "username": "gitlab-auto-merge",
    "name": "GitLab 自动合并",
    "is_system": True,
}

__all__ = [
    "MERGE_WEBHOOK_ACTION",
    "MERGED_NOTIFICATION_ACTION",
    "MERGE_NOTIFICATION_EVENT_TYPE",
    "AUTO_MERGE_ACTOR",
    "MergeRequestNotification",
    "Channel",
    "build_merged_notification",
    "MergeRequestNotificationHooks",
]


def _first_value(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return None


def _require_mapping(data: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must be an object")
    return data


def _require_value(data: Mapping[str, Any], name: str) -> Any:
    value = data.get(name)
    if value is None or value == "":
        raise ValueError(f"{name} is required")
    return value


def _mapping_value(data: Mapping[str, Any], *keys: str) -> Optional[Mapping[str, Any]]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _normalize_actor(data: Mapping[str, Any]) -> Dict[str, Any]:
    username = _first_value(data, "username", "user_name")
    name = _first_value(data, "name", "user_name")
    if name is None:
        name = username
    return {
        "id": data.get("id"),
        "username": username,
        "name": name,
    }


def _merge_actor(payload: Mapping[str, Any], attributes: Mapping[str, Any]) -> Dict[str, Any]:
    merge_user = _mapping_value(attributes, "merge_user", "merged_by")
    if merge_user is None:
        merge_user = _mapping_value(payload, "merge_user", "merged_by")
    if merge_user is not None:
        actor = _normalize_actor(merge_user)
        if any(actor.get(key) is not None and actor.get(key) != "" for key in ("id", "username", "name")):
            return actor

    merge_user_id = _first_value(attributes, "merge_user_id", "merged_by_id")
    if merge_user_id is None:
        merge_user_id = _first_value(payload, "merge_user_id", "merged_by_id")
    merge_user_name = _first_value(attributes, "merge_user_name", "merged_by_name")
    if merge_user_name is None:
        merge_user_name = _first_value(payload, "merge_user_name", "merged_by_name")
    merge_user_username = _first_value(attributes, "merge_user_username", "merged_by_username")
    if merge_user_username is None:
        merge_user_username = _first_value(payload, "merge_user_username", "merged_by_username")
    if any(value is not None for value in (merge_user_id, merge_user_name, merge_user_username)):
        return {
            "id": merge_user_id,
            "username": merge_user_username,
            "name": merge_user_name or merge_user_username or str(merge_user_id),
        }

    return dict(AUTO_MERGE_ACTOR)


def _actor_display_name(actor: Mapping[str, Any]) -> str:
    name = actor.get("name") or actor.get("username") or actor.get("id")
    if name is None or name == "":
        return str(AUTO_MERGE_ACTOR["name"])
    username = actor.get("username")
    if username and str(username) != str(name) and not actor.get("is_system"):
        return f"{name} (@{username})"
    return str(name)


def _merge_idempotency_key(
    payload: Mapping[str, Any],
    attributes: Mapping[str, Any],
    project_id: Any,
    iid: Any,
    occurred_at: Optional[str],
) -> str:
    event_marker = occurred_at
    if event_marker is None:
        event_marker = _first_value(payload, "webhook_id", "id")
    if event_marker is None:
        event_marker = _first_value(attributes, "webhook_id", "id")
    if event_marker is None:
        event_marker = "unknown"
    return f"gitlab:{MERGE_WEBHOOK_ACTION}:{project_id}:{iid}:{event_marker}"


def _event_idempotency_key(event) -> Optional[str]:
    """Prefer a transport id when an adapter makes webhook headers available."""

    for attribute in ("webhook_id", "idempotency_key"):
        value = getattr(event, attribute, None)
        if value is not None and value != "":
            return f"gitlab:merge:header:{value}"

    headers = getattr(event, "headers", None)
    if isinstance(headers, Mapping):
        normalized_headers = {str(key).lower(): value for key, value in headers.items()}
        for header in ("webhook-id", "idempotency-key", "x-gitlab-webhook-id"):
            value = normalized_headers.get(header)
            if value is not None and value != "":
                return f"gitlab:merge:header:{value}"

    data = getattr(event, "data", None)
    if isinstance(data, Mapping):
        for key in ("webhook_id", "idempotency_key"):
            value = data.get(key)
            if value is not None and value != "":
                return f"gitlab:merge:header:{value}"
    return None


def build_merged_notification(data: Mapping[str, Any]) -> MergeRequestNotification:
    """Convert a completed GitLab MR merge webhook into a notification."""

    payload = _require_mapping(data, "payload")
    attributes = _require_mapping(payload.get("object_attributes"), "object_attributes")
    project_data = _require_mapping(payload.get("project"), "project")

    webhook_action = _require_value(attributes, "action")
    if webhook_action != MERGE_WEBHOOK_ACTION:
        raise ValueError(f"unsupported merge action: {webhook_action}")
    if attributes.get("state") != "merged" and not _first_value(attributes, "merged_at"):
        raise ValueError("merge webhook does not describe a completed merge")

    project_id = _require_value(project_data, "id")
    iid = _require_value(attributes, "iid")
    project_path = _first_value(project_data, "path_with_namespace", "path", "name")
    project_url = _first_value(project_data, "web_url", "url")
    mr_url = _first_value(attributes, "url", "web_url")
    if mr_url is None and project_url is not None:
        mr_url = f"{str(project_url).rstrip('/')}/-/merge_requests/{iid}"

    title = attributes.get("title")
    occurred_at = _first_value(attributes, "merged_at", "actioned_at", "updated_at")
    actor = _merge_actor(payload, attributes)
    triggered_by_data = payload.get("user")
    triggered_by = _normalize_actor(triggered_by_data) if isinstance(triggered_by_data, Mapping) else None
    project_label = str(project_path) if project_path is not None else "项目不可用"
    title_text = str(title) if title is not None and title != "" else "标题不可用"
    mr_url_text = str(mr_url) if mr_url is not None else "MR 链接不可用"
    occurred_at_text = str(occurred_at) if occurred_at is not None else "时间不可用"
    actor_name = _actor_display_name(actor)

    message = (
        f"MR !{iid}「{title_text}」已合并: {actor_name} 合并了项目 {project_label}, "
        f"时间: {occurred_at_text}, 链接: {mr_url_text}"
    )
    return MergeRequestNotification(
        source="gitlab",
        event_type=MERGE_NOTIFICATION_EVENT_TYPE,
        action=MERGED_NOTIFICATION_ACTION,
        webhook_action=webhook_action,
        message=message,
        project={
            "id": project_id,
            "path": project_path,
            "url": project_url,
        },
        merge_request={
            "iid": iid,
            "title": title,
            "url": mr_url,
        },
        actor=actor,
        occurred_at=occurred_at,
        triggered_by=triggered_by,
        idempotency_key=_merge_idempotency_key(payload, attributes, project_id, iid, occurred_at),
    )


class MergeRequestNotificationHooks:
    """Handle completed MR merge webhooks without invoking the GitLab API."""

    def __init__(self, channel: Channel, logger: Optional[logging.Logger] = None, delivery=None):
        self.channel = channel
        self.logger = logger or logging.getLogger(__name__)
        self.delivery = delivery

    async def handle(self, event, *args, **kwargs) -> None:
        try:
            data = event.data
            if not isinstance(data, Mapping):
                raise ValueError("payload must be an object")
            attributes = data.get("object_attributes")
            if not isinstance(attributes, Mapping):
                raise ValueError("object_attributes must be an object")
            action = attributes.get("action")
            if action != MERGE_WEBHOOK_ACTION:
                self.logger.debug("Skip merged notification for action=%r", action)
                return
            notification = build_merged_notification(data)
            event_key = _event_idempotency_key(event)
            if event_key is not None:
                notification.idempotency_key = event_key
        except Exception as exc:
            self.logger.error("invalid merged webhook: %s", exc)
            return

        if self.delivery is not None:
            await self.delivery.deliver(notification)
            return

        try:
            await self.channel.send(notification)
        except Exception as exc:
            self.logger.error(
                "merged notification channel failed (project=%s, mr_iid=%s): %s",
                notification.project.get("path") or notification.project.get("id"),
                notification.merge_request.get("iid"),
                exc,
                exc_info=True,
            )

    async def recover(self) -> int:
        if self.delivery is None:
            return 0
        return await self.delivery.recover()

    async def replay_failed(self) -> int:
        if self.delivery is None:
            return 0
        return await self.delivery.replay_failed()
