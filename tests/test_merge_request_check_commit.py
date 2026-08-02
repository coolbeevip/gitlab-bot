import asyncio
from types import SimpleNamespace

import src.hooks.merge_request as merge_request_hook
from tests.fixtures.approval_contract import (
    APPROVALS_ROBOT_GET,
    APPROVE_RESPONSE,
    ApprovalApiFake,
)

PROJECT_ID = 76
MR_IID = 1
COMMITS_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/commits"
APPROVALS_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/approvals"
APPROVE_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/approve"
NOTES_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/notes"


def make_merge_request_event():
    return SimpleNamespace(
        project_id=PROJECT_ID,
        data={
            "event_type": "merge_request",
            "object_attributes": {
                "last_commit": {
                    "title": "[feat]:[][Test commit]",
                    "author": {
                        "name": "reviewer",
                        "email": "reviewer@asiainfo.com",
                    },
                },
                "iid": MR_IID,
                "milestone_id": 1,
                "description": "#123 test merge request",
            },
        },
    )


def success_note_call():
    return ("POST", NOTES_URL, {"body": merge_request_hook._("bot_review_success")})


def test_check_commit_awaits_approval_before_success_note(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", True)
    client = ApprovalApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("GET", APPROVALS_URL): [
                {
                    "approved": False,
                    "approvals_required": None,
                    "approvals_left": None,
                    "approved_by": [],
                }
            ],
            ("POST", APPROVE_URL): [APPROVE_RESPONSE],
            ("POST", NOTES_URL): [{}],
        }
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
        success_note_call(),
    ]


def test_check_commit_skips_approve_when_robot_already_approved(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", True)
    client = ApprovalApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("GET", APPROVALS_URL): [APPROVALS_ROBOT_GET],
            ("POST", NOTES_URL): [{}],
        }
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        success_note_call(),
    ]


def test_check_commit_does_not_call_approval_api_when_feature_is_disabled(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", False)
    client = ApprovalApiFake({("GET", COMMITS_URL): [[]]})

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [("GET", COMMITS_URL, None)]
