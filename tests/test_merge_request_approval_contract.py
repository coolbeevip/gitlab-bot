import asyncio

import src.merge_request_hook as merge_request_hook
from tests.fixtures.approval_contract import (
    APPROVALS_EMPTY_GET,
    APPROVALS_OTHER_USER_GET,
    APPROVALS_ROBOT_GET,
    APPROVE_RESPONSE,
    UNAPPROVE_RESPONSE,
    ApprovalApiFake,
)

approval_merge_request = merge_request_hook.approval_merge_request

APPROVALS_URL = "/projects/76/merge_requests/1/approvals"
APPROVE_URL = "/projects/76/merge_requests/1/approve"
UNAPPROVE_URL = "/projects/76/merge_requests/1/unapprove"


def test_target_approvals_fixture_preserves_nullable_fields():
    client = ApprovalApiFake({("GET", APPROVALS_URL): [APPROVALS_EMPTY_GET]})

    response = asyncio.run(client.getitem(APPROVALS_URL))

    assert response == {
        "approved": False,
        "approvals_required": None,
        "approvals_left": None,
        "approved_by": [],
    }


def test_approval_fixtures_distinguish_robot_other_user_and_empty_state():
    assert APPROVALS_EMPTY_GET["approved_by"] == []
    assert APPROVALS_ROBOT_GET["approved_by"][0]["user"]["username"] == "review-bot"
    assert APPROVALS_OTHER_USER_GET["approved_by"][0]["user"]["username"] == "other-reviewer"


def test_async_fake_records_approval_api_order_and_payload():
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_EMPTY_GET],
            ("POST", APPROVE_URL): [APPROVE_RESPONSE],
            ("POST", UNAPPROVE_URL): [UNAPPROVE_RESPONSE],
        }
    )

    async def exercise_api():
        await client.getitem(APPROVALS_URL)
        await client.post(APPROVE_URL, data=None)
        await client.post(UNAPPROVE_URL, data=None)

    asyncio.run(exercise_api())

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
        ("POST", UNAPPROVE_URL, None),
    ]


def test_approve_and_unapprove_fixtures_capture_target_user_state():
    assert APPROVE_RESPONSE["user_has_approved"] is True
    assert APPROVE_RESPONSE["user_can_approve"] is False
    assert APPROVE_RESPONSE["approved_by"][0]["user"]["username"] == "review-bot"

    assert UNAPPROVE_RESPONSE["user_has_approved"] is False
    assert UNAPPROVE_RESPONSE["user_can_approve"] is True
    assert UNAPPROVE_RESPONSE["approved"] is False
    assert UNAPPROVE_RESPONSE["approved_by"] == []


def test_approval_merge_request_approves_when_robot_is_not_approved(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_EMPTY_GET],
            ("POST", APPROVE_URL): [APPROVE_RESPONSE],
        }
    )

    asyncio.run(approval_merge_request(76, 1, client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
    ]


def test_approval_merge_request_does_not_duplicate_robot_approval(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    client = ApprovalApiFake({("GET", APPROVALS_URL): [APPROVALS_ROBOT_GET]})

    asyncio.run(approval_merge_request(76, 1, client))

    assert client.calls == [("GET", APPROVALS_URL, None)]


def test_approval_merge_request_approves_when_only_other_user_is_approved(monkeypatch):
    monkeypatch.setattr(merge_request_hook, "bot_gitlab_username", "review-bot")
    client = ApprovalApiFake(
        {
            ("GET", APPROVALS_URL): [APPROVALS_OTHER_USER_GET],
            ("POST", APPROVE_URL): [APPROVE_RESPONSE],
        }
    )

    asyncio.run(approval_merge_request(76, 1, client))

    assert client.calls == [
        ("GET", APPROVALS_URL, None),
        ("POST", APPROVE_URL, None),
    ]
