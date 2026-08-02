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
from ..notifications.model import PipelineNotification

PIPELINE_STATUSES = frozenset(("success", "failed"))
PIPELINE_NOTIFICATION_EVENT_TYPE = "pipeline_lifecycle"
PIPELINE_WEBHOOK_ACTION = "status_changed"
STATUS_LABELS = {
    "success": "成功",
    "failed": "失败",
}

__all__ = [
    "PIPELINE_STATUSES",
    "PIPELINE_NOTIFICATION_EVENT_TYPE",
    "PIPELINE_WEBHOOK_ACTION",
    "PipelineNotification",
    "Channel",
    "build_pipeline_notification",
    "PipelineNotificationHooks",
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


def _normalize_actor(data: Any) -> Dict[str, Any]:
    if not isinstance(data, Mapping):
        return {"id": None, "username": None, "name": None}
    username = _first_value(data, "username", "user_name")
    name = _first_value(data, "name", "user_name") or username
    return {
        "id": data.get("id"),
        "username": username,
        "name": name,
    }


def _normalize_merge_request(data: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(data, Mapping):
        return None
    merge_request = {
        "iid": _first_value(data, "iid"),
        "title": _first_value(data, "title"),
        "url": _first_value(data, "url", "web_url"),
        "source_branch": _first_value(data, "source_branch"),
        "target_branch": _first_value(data, "target_branch"),
    }
    if not any(value is not None for value in merge_request.values()):
        return None
    return merge_request


def _pipeline_idempotency_key(
    payload: Mapping[str, Any],
    attributes: Mapping[str, Any],
    project_id: Any,
    pipeline_id: Any,
    status: str,
) -> str:
    event_marker = _first_value(payload, "webhook_id", "idempotency_key")
    if event_marker is None:
        event_marker = _first_value(attributes, "webhook_id", "idempotency_key")
    if event_marker is not None:
        return f"gitlab:pipeline:{project_id}:{pipeline_id}:{status}:{event_marker}"
    return f"gitlab:pipeline:{project_id}:{pipeline_id}:{status}"


def _event_idempotency_key(event) -> Optional[str]:
    for attribute in ("webhook_id", "idempotency_key"):
        value = getattr(event, attribute, None)
        if value is not None and value != "":
            return f"gitlab:pipeline:header:{value}"

    headers = getattr(event, "headers", None)
    if isinstance(headers, Mapping):
        normalized_headers = {str(key).lower(): value for key, value in headers.items()}
        for header in ("webhook-id", "idempotency-key", "x-gitlab-webhook-id"):
            value = normalized_headers.get(header)
            if value is not None and value != "":
                return f"gitlab:pipeline:header:{value}"
    return None


def build_pipeline_notification(data: Mapping[str, Any]) -> PipelineNotification:
    """Convert a GitLab Pipeline Hook payload into a notification."""

    payload = _require_mapping(data, "payload")
    attributes = _require_mapping(payload.get("object_attributes"), "object_attributes")
    project_data = _require_mapping(payload.get("project"), "project")

    status = _require_value(attributes, "status")
    if not isinstance(status, str) or status not in PIPELINE_STATUSES:
        raise ValueError(f"unsupported pipeline status: {status}")

    project_id = _require_value(project_data, "id")
    pipeline_id = _require_value(attributes, "id")
    pipeline_iid = _first_value(attributes, "iid")
    project_path = _first_value(project_data, "path_with_namespace", "path", "name")
    project_url = _first_value(project_data, "web_url", "url")
    pipeline_url = _first_value(attributes, "url", "web_url")
    if pipeline_url is None and project_url is not None:
        pipeline_url = f"{str(project_url).rstrip('/')}/-/pipelines/{pipeline_id}"

    merge_request = _normalize_merge_request(payload.get("merge_request"))
    actor = _normalize_actor(payload.get("user"))
    actor_name = actor.get("name") or actor.get("username")
    project_label = str(project_path) if project_path is not None else str(project_id)
    pipeline_label = f"Pipeline #{pipeline_id}"
    if pipeline_iid is not None and str(pipeline_iid) != str(pipeline_id):
        pipeline_label += f" (IID {pipeline_iid})"

    merge_request_label = ""
    if merge_request is not None:
        merge_request_iid = merge_request.get("iid")
        merge_request_title = merge_request.get("title") or "标题不可用"
        if merge_request_iid is not None:
            merge_request_label = f" for MR !{merge_request_iid}「{merge_request_title}」"

    status_label = STATUS_LABELS[status]
    details = [
        f"project: {project_label}",
        f"ref: {_first_value(attributes, 'ref') or 'ref unavailable'}",
    ]
    if actor_name:
        details.append(f"triggered by: {actor_name}")
    if attributes.get("duration") is not None:
        details.append(f"duration: {attributes['duration']}s")
    if pipeline_url:
        details.append(str(pipeline_url))
    else:
        details.append("(Pipeline URL unavailable)")

    return PipelineNotification(
        source="gitlab",
        event_type=PIPELINE_NOTIFICATION_EVENT_TYPE,
        action=status,
        webhook_action=PIPELINE_WEBHOOK_ACTION,
        status=status,
        message=f"{pipeline_label}{merge_request_label} {status_label} ({status}): " + ", ".join(details),
        project={
            "id": project_id,
            "path": project_path,
            "url": project_url,
        },
        pipeline={
            "id": pipeline_id,
            "iid": pipeline_iid,
            "name": attributes.get("name"),
            "status": status,
            "detailed_status": attributes.get("detailed_status"),
            "ref": attributes.get("ref"),
            "sha": attributes.get("sha"),
            "source": attributes.get("source"),
            "url": pipeline_url,
            "duration": attributes.get("duration"),
            "queued_duration": attributes.get("queued_duration"),
            "created_at": attributes.get("created_at"),
            "finished_at": attributes.get("finished_at"),
        },
        actor=actor,
        occurred_at=_first_value(attributes, "finished_at", "updated_at", "created_at"),
        merge_request=merge_request,
        idempotency_key=_pipeline_idempotency_key(payload, attributes, project_id, pipeline_id, status),
    )


class PipelineNotificationHooks:
    """Handle successful and failed GitLab Pipeline webhooks."""

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
            status = attributes.get("status")
            if status not in PIPELINE_STATUSES:
                self.logger.debug("Skip pipeline notification for status=%r", status)
                return
            notification = build_pipeline_notification(data)
            event_key = _event_idempotency_key(event)
            if event_key is not None:
                notification.idempotency_key = event_key
        except Exception as exc:
            self.logger.error("invalid pipeline webhook: %s", exc)
            return

        try:
            await self.channel.send(notification)
        except Exception as exc:
            self.logger.error(
                "pipeline notification channel failed (status=%s, project=%s, pipeline_id=%s): %s",
                notification.status,
                notification.project.get("path") or notification.project.get("id"),
                notification.pipeline.get("id"),
                exc,
                exc_info=True,
            )
