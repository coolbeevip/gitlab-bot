import asyncio
from types import SimpleNamespace

import src.merge_request_hook as merge_request_hook
from tests.fixtures.approval_contract import (
    APPROVALS_EMPTY_GET,
    APPROVALS_OTHER_USER_GET,
    APPROVALS_ROBOT_GET,
    UNAPPROVE_RESPONSE,
    ApprovalApiFake,
)

PROJECT_ID = 76
MR_IID = 1
COMMITS_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/commits"
APPROVALS_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/approvals"
APPROVE_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/approve"
UNAPPROVE_URL = f"/projects/{PROJECT_ID}/merge_requests/{MR_IID}/unapprove"
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


class FailingGetApprovalApiFake(ApprovalApiFake):
    def __init__(self, responses, failing_url, error):
        super().__init__(responses)
        self.failing_url = failing_url
        self.error = error

    async def getitem(self, url):
        if url == self.failing_url:
            self.calls.append(("GET", url, None))
            raise self.error
        return self._respond("GET", url, None)


class FailingPostApprovalApiFake(ApprovalApiFake):
    def __init__(self, responses, failing_url, error):
        super().__init__(responses)
        self.failing_url = failing_url
        self.error = error

    async def post(self, url, data=None):
        if url == self.failing_url:
            self.calls.append(("POST", url, data))
            raise self.error
        return self._respond("POST", url, data)


def failure_note(key, error_message):
    return (
        "POST",
        NOTES_URL,
        {"body": merge_request_hook._(key).format(error_message=error_message)},
    )


def fail_validation(message="validation failed"):
    def check_commit_message(_):
        raise RuntimeError(message)

    return check_commit_message


def configure_failure_path(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", True)
    monkeypatch.setattr(merge_request_hook, "check_commit_message", fail_validation())


def test_check_commit_unapproves_only_robot_approval_on_validation_failure(monkeypatch):
    configure_failure_path(monkeypatch)
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_ROBOT_GET],
            ("POST", UNAPPROVE_URL): [UNAPPROVE_RESPONSE],
            ("POST", NOTES_URL): [{}],
        }
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", UNAPPROVE_URL, None),
        failure_note("bot_review_fails_approval_revoked", "validation failed"),
    ]


def test_check_commit_preserves_other_users_approval_on_validation_failure(monkeypatch):
    configure_failure_path(monkeypatch)
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_OTHER_USER_GET],
            ("POST", NOTES_URL): [{}],
        }
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        failure_note("bot_review_fails_approval_not_present", "validation failed"),
    ]


def test_check_commit_reports_unapprove_failure_without_claiming_revoked(monkeypatch):
    configure_failure_path(monkeypatch)
    client = FailingPostApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_ROBOT_GET],
            ("POST", NOTES_URL): [{}],
        },
        UNAPPROVE_URL,
        RuntimeError("unapprove failed"),
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", UNAPPROVE_URL, None),
        failure_note(
            "bot_review_fails_approval_not_revoked",
            "validation failed; unapprove error: unapprove failed",
        ),
    ]


def test_check_commit_reports_approval_query_failure_without_claiming_revoked(monkeypatch):
    configure_failure_path(monkeypatch)
    client = FailingGetApprovalApiFake(
        {("POST", NOTES_URL): [{}]},
        APPROVALS_URL,
        RuntimeError("approvals unavailable"),
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        failure_note(
            "bot_review_fails_approval_not_revoked",
            "validation failed; unapprove error: approvals unavailable",
        ),
    ]


def test_check_commit_reports_approve_failure_without_attempting_unapprove(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", True)
    client = FailingPostApprovalApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("GET", APPROVALS_URL): [APPROVALS_EMPTY_GET],
            ("POST", NOTES_URL): [{}],
        },
        APPROVE_URL,
        RuntimeError("approve failed"),
    )

    asyncio.run(merge_request_hook.check_commit(make_merge_request_event(), client))

    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
        failure_note("bot_review_fails_approval_unknown", "approve failed"),
    ]
