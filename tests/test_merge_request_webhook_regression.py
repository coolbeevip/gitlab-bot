import asyncio
from types import SimpleNamespace

import pytest

import src.merge_request_hook as merge_request_hook
from tests.fixtures.approval_contract import (
    APPROVALS_EMPTY_GET,
    APPROVALS_ROBOT_GET,
    APPROVE_RESPONSE,
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


def make_event(event_type="merge_request", state="opened"):
    last_commit = {
        "title": "[feat]:[][Test commit]",
        "author": {
            "name": "reviewer",
            "email": "reviewer@asiainfo.com",
        },
    }
    if event_type == "note":
        return SimpleNamespace(
            project_id=PROJECT_ID,
            data={
                "event_type": "note",
                "object_attributes": {"note": "/bot-review"},
                "merge_request": {
                    "state": state,
                    "last_commit": last_commit,
                    "iid": MR_IID,
                    "milestone_id": 1,
                    "description": "#123 test merge request",
                },
            },
        )

    return SimpleNamespace(
        project_id=PROJECT_ID,
        data={
            "event_type": "merge_request",
            "object_attributes": {
                "state": state,
                "last_commit": last_commit,
                "iid": MR_IID,
                "milestone_id": 1,
                "description": "#123 test merge request",
            },
        },
    )


def success_note_call():
    return ("POST", NOTES_URL, {"body": merge_request_hook._("bot_review_success")})


def failure_note_call(key, error_message):
    return (
        "POST",
        NOTES_URL,
        {"body": merge_request_hook._(key).format(error_message=error_message)},
    )


def make_success_client(approvals=APPROVALS_EMPTY_GET):
    return ApprovalApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("GET", APPROVALS_URL): [approvals],
            ("POST", APPROVE_URL): [APPROVE_RESPONSE],
            ("POST", NOTES_URL): [{}],
        }
    )


class FailingPostApiFake(ApprovalApiFake):
    def __init__(self, responses, failing_url, error):
        super().__init__(responses)
        self.failing_url = failing_url
        self.error = error

    async def post(self, url, data=None):
        if url == self.failing_url:
            self.calls.append(("POST", url, data))
            raise self.error
        return self._respond("POST", url, data)


class FailingGetApiFake(ApprovalApiFake):
    def __init__(self, responses, failing_url, error):
        super().__init__(responses)
        self.failing_url = failing_url
        self.error = error

    async def getitem(self, url):
        if url == self.failing_url:
            self.calls.append(("GET", url, None))
            raise self.error
        return self._respond("GET", url, None)


def configure_hooks(monkeypatch):
    async def skip_summary(event, gl):
        return None

    monkeypatch.setattr(merge_request_hook, "generate_diff_description_summary", skip_summary)
    monkeypatch.setattr(merge_request_hook, "has_required_reviewer", lambda event_data: True)
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", True)


@pytest.mark.parametrize(
    "method_name,event_type",
    [
        ("merge_request_opened_event", "merge_request"),
        ("merge_request_updated_event", "merge_request"),
        ("merge_request_reopen_event", "merge_request"),
        ("note_merge_request_event", "note"),
    ],
)
def test_merge_request_hooks_entrypoints_preserve_approval_order(monkeypatch, method_name, event_type):
    configure_hooks(monkeypatch)
    client = make_success_client()
    hooks = merge_request_hook.MergeRequestHooks()

    result = asyncio.run(getattr(hooks, method_name)(make_event(event_type), client))

    assert result is None
    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
        success_note_call(),
    ]


def test_merge_request_hook_failure_returns_once_after_bot_unapproval(monkeypatch):
    configure_hooks(monkeypatch)

    def fail_validation(_):
        raise RuntimeError("validation failed")

    monkeypatch.setattr(merge_request_hook, "check_commit_message", fail_validation)
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_ROBOT_GET],
            ("POST", UNAPPROVE_URL): [UNAPPROVE_RESPONSE],
            ("POST", NOTES_URL): [{}],
        }
    )
    hooks = merge_request_hook.MergeRequestHooks()

    result = asyncio.run(hooks.merge_request_opened_event(make_event(), client))

    assert result is None
    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", UNAPPROVE_URL, None),
        failure_note_call("bot_review_fails_approval_revoked", "validation failed"),
    ]
    assert sum(call[0:2] == ("POST", NOTES_URL) for call in client.calls) == 1


def test_merge_request_hook_approval_failure_returns_once_without_retry(monkeypatch):
    configure_hooks(monkeypatch)
    client = FailingPostApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("GET", APPROVALS_URL): [APPROVALS_EMPTY_GET],
            ("POST", NOTES_URL): [{}],
        },
        APPROVE_URL,
        RuntimeError("approve failed"),
    )
    hooks = merge_request_hook.MergeRequestHooks()

    result = asyncio.run(hooks.merge_request_updated_event(make_event(), client))

    assert result is None
    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
        failure_note_call("bot_review_fails_approval_unknown", "approve failed"),
    ]
    assert sum(call[0:2] == ("POST", NOTES_URL) for call in client.calls) == 1


def test_merge_request_hook_approval_query_failure_returns_once_without_retry(monkeypatch):
    configure_hooks(monkeypatch)
    client = FailingGetApiFake(
        {
            ("GET", COMMITS_URL): [[]],
            ("POST", NOTES_URL): [{}],
        },
        APPROVALS_URL,
        RuntimeError("approvals unavailable"),
    )
    hooks = merge_request_hook.MergeRequestHooks()

    result = asyncio.run(hooks.merge_request_updated_event(make_event(), client))

    assert result is None
    assert client.calls == [
        ("GET", COMMITS_URL, None),
        ("GET", APPROVALS_URL, None),
        failure_note_call("bot_review_fails_approval_unknown", "approvals unavailable"),
    ]
    assert sum(call[0:2] == ("POST", NOTES_URL) for call in client.calls) == 1


def test_merge_request_hook_flag_disabled_skips_approval_endpoints(monkeypatch):
    configure_hooks(monkeypatch)
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_merge_request_approval_enabled", False)
    client = ApprovalApiFake({("GET", COMMITS_URL): [[]]})
    hooks = merge_request_hook.MergeRequestHooks()

    result = asyncio.run(hooks.merge_request_updated_event(make_event(), client))

    assert result is None
    assert client.calls == [("GET", COMMITS_URL, None)]
