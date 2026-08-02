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
from typing import Any, Mapping, Optional

from ..channels.base import Channel
from ..notifications.model import MergeRequestNotification

APPROVAL_ACTIONS = frozenset(("approval", "approved", "unapproval", "unapproved"))
NORMALIZED_ACTIONS = {
    "approval": "approval",
    "approved": "approval",
    "unapproval": "unapproval",
    "unapproved": "unapproval",
}

__all__ = [
    "APPROVAL_ACTIONS",
    "NORMALIZED_ACTIONS",
    "MergeRequestNotification",
    "Channel",
    "build_notification",
    "ApprovalNotificationHooks",
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


def _build_message(
    action: str,
    actor_name: str,
    title: str,
    iid: Any,
    project_label: str,
    mr_url: Optional[str],
) -> str:
    if action == "approval":
        action_text = "approved"
    else:
        action_text = "canceled approval (unapproval) for"

    message = f"{actor_name} {action_text} MR !{iid}: {title} (project: {project_label})"
    if mr_url:
        message += f" {mr_url}"
    else:
        message += " (MR URL unavailable)"
    return message


def build_notification(data: Mapping[str, Any]) -> MergeRequestNotification:
    """Convert a GitLab merge request webhook payload into a notification."""

    payload = _require_mapping(data, "payload")
    attributes = _require_mapping(payload.get("object_attributes"), "object_attributes")
    project_data = _require_mapping(payload.get("project"), "project")
    actor_data = _require_mapping(payload.get("user"), "user")

    webhook_action = _require_value(attributes, "action")
    if not isinstance(webhook_action, str) or webhook_action not in APPROVAL_ACTIONS:
        raise ValueError(f"unsupported approval action: {webhook_action}")
    action = NORMALIZED_ACTIONS[webhook_action]

    project_id = _require_value(project_data, "id")
    iid = _require_value(attributes, "iid")
    username = _require_value(actor_data, "username")

    project_path = _first_value(project_data, "path_with_namespace", "path", "name")
    project_url = _first_value(project_data, "web_url", "url")
    mr_url = _first_value(attributes, "url", "web_url")
    if mr_url is None and project_url is not None:
        mr_url = f"{str(project_url).rstrip('/')}/-/merge_requests/{iid}"

    title = attributes.get("title")
    title_text = str(title) if title is not None and title != "" else "(untitled)"
    project_label = str(project_path) if project_path is not None else str(project_id)
    actor_name = str(_first_value(actor_data, "name", "username"))
    if actor_name != str(username):
        actor_name = f"{actor_name} (@{username})"

    return MergeRequestNotification(
        source="gitlab",
        event_type="merge_request_review",
        action=action,
        webhook_action=webhook_action,
        message=_build_message(
            action,
            actor_name,
            title_text,
            iid,
            project_label,
            str(mr_url) if mr_url is not None else None,
        ),
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
        actor={
            "id": actor_data.get("id"),
            "username": username,
            "name": actor_data.get("name"),
        },
        occurred_at=_first_value(attributes, "actioned_at", "updated_at"),
    )


class ApprovalNotificationHooks:
    """Handle approval webhooks without invoking any GitLab API."""

    def __init__(self, channel: Channel, logger: Optional[logging.Logger] = None):
        self.channel = channel
        self.logger = logger or logging.getLogger(__name__)

    async def handle(self, event, *args, **kwargs) -> None:
        try:
            data = event.data
            if not isinstance(data, Mapping):
                raise ValueError("payload must be an object")
            attributes = data.get("object_attributes")
            if not isinstance(attributes, Mapping):
                raise ValueError("object_attributes must be an object")
            action = attributes.get("action")
            if action is None or action == "":
                raise ValueError("object_attributes.action is required")
            if action not in APPROVAL_ACTIONS:
                self.logger.debug("Skip approval notification for action=%r", action)
                return
            notification = build_notification(data)
        except Exception as exc:
            self.logger.error("invalid approval webhook: %s", exc)
            return

        try:
            await self.channel.send(notification)
        except Exception as exc:
            self.logger.error(
                "approval notification channel failed (action=%s, project=%s, mr_iid=%s): %s",
                notification.action,
                notification.project.get("path") or notification.project.get("id"),
                notification.merge_request.get("iid"),
                exc,
                exc_info=True,
            )
