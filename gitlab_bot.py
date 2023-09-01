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

from gidgetlab.aiohttp import GitLabBot

from src.config import bot_gitlab_username, bot_gitlab_url, bot_gitlab_token, bot_port, bot_host
from src.issue_hook import IssueHooks
from src.logs import print_event
from src.merge_request_hook import MergeRequestHooks
from src.note_hook import NoteHooks

bot = GitLabBot(bot_gitlab_username, url=bot_gitlab_url, access_token=bot_gitlab_token)

issue_hooks = IssueHooks()
merge_request_hooks = MergeRequestHooks()
note_hooks = NoteHooks()


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
async def merge_request_updated_event(event, gl, *args, **kwargs):
    if not ignore_event(event):
        await merge_request_hooks.merge_request_reopen_event(event, gl, args, kwargs)


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
    bot.run(host=bot_host, port=bot_port)
