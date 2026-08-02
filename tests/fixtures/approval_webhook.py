"""Representative approval and unapproval webhook payloads.

These payloads follow the GitLab merge request webhook shape. Replace or
augment them with a redacted GitLab Community Edition 16.11 capture when the
target-instance smoke fixture is available.
"""

from copy import deepcopy


def make_approval_webhook(action="approval", username="reviewer"):
    return {
        "object_kind": "merge_request",
        "event_type": "merge_request",
        "user": {
            "id": 7,
            "name": "Reviewer",
            "username": username,
        },
        "project": {
            "id": 76,
            "name": "Project",
            "path_with_namespace": "group/project",
            "web_url": "https://gitlab.example.com/group/project",
        },
        "object_attributes": {
            "action": action,
            "iid": 12,
            "title": "Add feature",
            "url": "https://gitlab.example.com/group/project/-/merge_requests/12",
            "updated_at": "2026-08-02T10:00:00Z",
        },
    }


APPROVAL_WEBHOOK = make_approval_webhook()
UNAPPROVAL_WEBHOOK = make_approval_webhook(action="unapproval")


def copy_webhook(action="approval", username="reviewer"):
    if action == "approval" and username == "reviewer":
        return deepcopy(APPROVAL_WEBHOOK)
    if action == "unapproval" and username == "reviewer":
        return deepcopy(UNAPPROVAL_WEBHOOK)
    return make_approval_webhook(action=action, username=username)
