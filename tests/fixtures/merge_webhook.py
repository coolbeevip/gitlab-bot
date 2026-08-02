"""Representative redacted GitLab merge request webhook payload."""

from copy import deepcopy


def make_merge_webhook(
    *,
    action="merge",
    state="merged",
    merged_at="2026-08-02T10:05:00Z",
    username="webhook-trigger",
    include_merge_user=True,
):
    attributes = {
        "action": action,
        "state": state,
        "merged_at": merged_at,
        "merge_user_id": 42 if include_merge_user else None,
        "id": 9001,
        "iid": 12,
        "title": "Add feature",
        "url": "https://gitlab.example.com/group/project/-/merge_requests/12",
        "updated_at": "2026-08-02T10:05:00Z",
    }
    if include_merge_user:
        attributes["merge_user"] = {"id": 42, "name": "Merger", "username": "merger"}

    return {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "id": "merge-event-9001",
        "user": {"id": 7, "name": "Webhook Trigger", "username": username},
        'project': {
            "id": 76,
            "name": "Project",
            "path_with_namespace": "group/project",
            "web_url": "https://gitlab.example.com/group/project",
        },
        "object_attributes": attributes,
    }


MERGE_WEBHOOK = make_merge_webhook()


def copy_merge_webhook(**kwargs):
    if not kwargs:
        return deepcopy(MERGE_WEBHOOK)
    return make_merge_webhook(**kwargs)
