import asyncio
import json
from types import SimpleNamespace

import pytest

from src.channels.feishu import (
    MESSAGE_URL,
    TOKEN_URL,
    FeishuChannel,
    FeishuConfigError,
    FeishuResponseError,
    format_notification,
)
from src.hooks.approval_notification import build_notification
from src.hooks.merge_notification import build_merged_notification
from src.hooks.pipeline_notification import build_pipeline_notification
from tests.fixtures.approval_webhook import copy_webhook
from tests.fixtures.merge_webhook import copy_merge_webhook
from tests.fixtures.pipeline_webhook import copy_pipeline_webhook


class FakeResponse:
    def __init__(self, status, data):
        self.status = status
        self.data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, **_kwargs):
        return self.data


class FakeSession:
    def __init__(self, responses, calls):
        self.responses = responses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        status, data = self.responses.pop(0)
        return FakeResponse(status, data)


class FakeSessionFactory:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, **_kwargs):
        return FakeSession(self.responses, self.calls)


def make_channel(responses, **kwargs):
    factory = FakeSessionFactory(responses)
    return (
        FeishuChannel(
            "app-id",
            "app-secret",
            "chat-id",
            session_factory=factory,
            **kwargs,
        ),
        factory,
    )


def test_feishu_channel_sends_normalized_pipeline_text_and_caches_token():
    channel, factory = make_channel(
        [
            (200, {"code": 0, "tenant_access_token": "token-value", "expire": 7200}),
            (200, {"code": 0, "data": {"message_id": "message-1"}}),
            (200, {"code": 0, "data": {"message_id": "message-2"}}),
        ]
    )
    notification = build_pipeline_notification(copy_pipeline_webhook(status="failed"))

    async def run():
        await channel.send(notification)
        await channel.send(notification)

    asyncio.run(run())

    assert [call[0] for call in factory.calls] == [TOKEN_URL, MESSAGE_URL, MESSAGE_URL]
    message_payload = factory.calls[1][1]["json"]
    assert message_payload["receive_id"] == "chat-id"
    assert message_payload["msg_type"] == "text"
    message_text = json.loads(message_payload["content"])["text"]
    assert "❌" in message_text
    assert "Pipeline failed" in message_text
    assert "master" in message_text
    assert channel.last_message_id == "message-2"


def test_feishu_channel_refreshes_token_when_expiring():
    now = [1000.0]
    channel, factory = make_channel(
        [
            (200, {"code": 0, "tenant_access_token": "first-token", "expire": 61}),
            (200, {"code": 0, "data": {}}),
            (200, {"code": 0, "tenant_access_token": "second-token", "expire": 7200}),
            (200, {"code": 0, "data": {}}),
        ],
        clock=lambda: now[0],
    )
    notification = build_pipeline_notification(copy_pipeline_webhook(status="success"))

    async def run():
        await channel.send(notification)
        now[0] = 1001.0
        await channel.send(notification)

    asyncio.run(run())

    assert [call[0] for call in factory.calls] == [TOKEN_URL, MESSAGE_URL, TOKEN_URL, MESSAGE_URL]
    assert factory.calls[3][1]["headers"]["Authorization"] == "Bearer second-token"


def test_feishu_channel_supports_optional_at_and_mr_formatting():
    channel, factory = make_channel(
        [
            (200, {"code": 0, "tenant_access_token": "token-value", "expire": 7200}),
            (200, {"code": 0, "data": {}}),
        ],
        bot_open_id="ou_test-user",
    )
    notification = build_merged_notification(copy_merge_webhook())

    asyncio.run(channel.send(notification))

    message_text = json.loads(factory.calls[1][1]["json"]["content"])["text"]
    assert '<at user_id="ou_test-user"></at>' in message_text
    assert "MR" in message_text
    assert "!12" in message_text


def test_feishu_channel_rejects_business_error_without_logging_secret():
    channel, _factory = make_channel(
        [
            (200, {"code": 999, "msg": "permission denied"}),
        ]
    )

    with pytest.raises(FeishuResponseError, match="code=999"):
        asyncio.run(channel.send(build_pipeline_notification(copy_pipeline_webhook(status="failed"))))


def test_feishu_channel_requires_complete_configuration():
    with pytest.raises(FeishuConfigError, match="FEISHU_APP_SECRET"):
        FeishuChannel("app-id", "", "chat-id")


def test_format_notification_rejects_unknown_normalized_type():
    with pytest.raises(TypeError, match="unsupported notification type"):
        format_notification(SimpleNamespace(action="unknown"))


@pytest.mark.parametrize(
    ("webhook_action", "expected"),
    (("approval", "已批准"), ("unapproval", "撤销批准")),
)
def test_format_notification_supports_approval_and_unapproval(webhook_action, expected):
    notification = build_notification(copy_webhook(action=webhook_action))

    assert expected in format_notification(notification)
