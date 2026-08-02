# Copyright 2023 Lei Zhang
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
import warnings

from dotenv import load_dotenv

from src.channels.log import LogChannel
from src.config import (
    bot_gitlab_token,
    bot_gitlab_url,
    bot_gitlab_username,
    bot_host,
    bot_port,
    merge_notification_db_path,
    merge_notification_sending_timeout_seconds,
)
from src.delivery.coordinator import NotificationDelivery
from src.delivery.idempotent_channel import DurableIdempotentChannel
from src.delivery.sqlite import NotificationDeliveryStore
from src.hooks.approval_notification import ApprovalNotificationHooks
from src.hooks.issue import IssueHooks
from src.hooks.merge_notification import MergeRequestNotificationHooks
from src.hooks.merge_request import MergeRequestHooks
from src.hooks.note import NoteHooks
from src.hooks.pipeline_notification import PipelineNotificationHooks
from src.logs import print_event

load_dotenv()  # isort:skip


def _load_gitlab_bot():
    # gidgetlab 1.1.0 still imports the deprecated pkg_resources API.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            message=r"pkg_resources is deprecated as an API\.",
        )
        warnings.filterwarnings(
            "ignore",
            category=DeprecationWarning,
            message=r"Deprecated call to `pkg_resources\.declare_namespace",
        )
        from gidgetlab.aiohttp import GitLabBot

    return GitLabBot


GitLabBot = _load_gitlab_bot()

bot = GitLabBot(bot_gitlab_username, url=bot_gitlab_url, access_token=bot_gitlab_token)

issue_hooks = IssueHooks()
merge_request_hooks = MergeRequestHooks()
note_hooks = NoteHooks()
notification_channel = LogChannel()
approval_notification_hooks = ApprovalNotificationHooks(notification_channel)
pipeline_notification_hooks = PipelineNotificationHooks(notification_channel)
notification_delivery_store = NotificationDeliveryStore(
    merge_notification_db_path,
    sending_timeout_seconds=merge_notification_sending_timeout_seconds,
)
merge_notification_channel = DurableIdempotentChannel(notification_channel, notification_delivery_store)
merge_notification_delivery = NotificationDelivery(merge_notification_channel, notification_delivery_store)
merge_request_notification_hooks = MergeRequestNotificationHooks(
    merge_notification_channel,
    delivery=merge_notification_delivery,
)


async def recover_merge_notification_deliveries(_app):
    await merge_request_notification_hooks.recover()


bot.app.on_startup.append(recover_merge_notification_deliveries)


@bot.router.register("Issue Hook", action="open")
async def issue_opened_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await issue_hooks.issue_opened_event(event, gl, args, kwargs)


@bot.router.register("Issue Hook", action="close")
async def issue_closed_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await issue_hooks.issue_closed_event(event, gl, args, kwargs)


@bot.router.register("Issue Hook", action="update")
async def issue_updated_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await issue_hooks.issue_updated_event(event, gl, args, kwargs)


@bot.router.register("Note Hook", noteable_type="Issue")
async def note_issue_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await issue_hooks.note_issue_event(event, gl, args, kwargs)


@bot.router.register("Merge Request Hook", action="open")
async def merge_request_opened_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await merge_request_hooks.merge_request_opened_event(event, gl, args, kwargs)


@bot.router.register("Merge Request Hook", action="update")
async def merge_request_updated_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await merge_request_hooks.merge_request_updated_event(event, gl, args, kwargs)


@bot.router.register("Merge Request Hook", action="reopen")
async def merge_request_reopen_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await merge_request_hooks.merge_request_reopen_event(event, gl, args, kwargs)


@bot.router.register("Merge Request Hook", action="approved")
@bot.router.register("Merge Request Hook", action="approval")
async def merge_request_approval_event(event, gl, *args, **kwargs):
    await approval_notification_hooks.handle(event, gl, *args, **kwargs)


@bot.router.register("Merge Request Hook", action="unapproved")
@bot.router.register("Merge Request Hook", action="unapproval")
async def merge_request_unapproval_event(event, gl, *args, **kwargs):
    await approval_notification_hooks.handle(event, gl, *args, **kwargs)


@bot.router.register("Merge Request Hook", action="merge")
async def merge_request_merged_event(event, gl, *args, **kwargs):
    await merge_request_notification_hooks.handle(event, gl, *args, **kwargs)


@bot.router.register("Pipeline Hook")
async def pipeline_event(event, gl, *args, **kwargs):
    await pipeline_notification_hooks.handle(event, gl, *args, **kwargs)


@bot.router.register("Note Hook", noteable_type="MergeRequest")
async def note_merge_request_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await merge_request_hooks.note_merge_request_event(event, gl, args, kwargs)


@bot.router.register("Note Hook", noteable_type="Commit")
async def note_commit_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        note_hooks.note_commit_event(event, gl, args, kwargs)


@bot.router.register("Note Hook", noteable_type="Snippet")
async def note_snippet_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        note_hooks.note_snippet_event(event, gl, args, kwargs)


def ignore_event(event) -> bool:
    print_event(event)
    username = event.data["user"]["username"]
    if username != bot_gitlab_username:
        return False
    else:
        logging.info("Ignore event: %s triggered by admin", event.data["event_type"])
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(host=bot_host, port=int(bot_port))
