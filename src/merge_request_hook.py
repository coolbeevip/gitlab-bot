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

import re

from src.config import (
    bot_git_commit_subject_example_markdown,
    bot_git_commit_subject_max_length,
    bot_git_commit_subject_regex,
    bot_git_email_domain,
    bot_gitlab_merge_request_milestone_required, bot_gitlab_merge_request_issue_required,
)
from src.i18n import _
from src.logs import print_event


def check_changes(gl, project_id, iid):
    # url = f"/projects/{project_id}/merge_requests/{iid}/changes"
    # changes = await gl.getitem(url)
    # for change in changes:
    pass


def check_commit_message(commit_msg):
    if len(commit_msg) > bot_git_commit_subject_max_length:
        raise Exception(
            _("commit_subject_max_length").format(commit_subject_max_length=bot_git_commit_subject_max_length))

    regex = re.compile(bot_git_commit_subject_regex)
    if re.search(regex, commit_msg) is None:
        raise Exception(
            _("invalid_commit_message").format(
                commit_msg=commit_msg,
                git_commit_subject_example_markdown=bot_git_commit_subject_example_markdown,
            )
        )


def check_description(description):
    if bot_gitlab_merge_request_issue_required:
        issue_num_pattern = r"(#\d+)"
        if not re.search(issue_num_pattern, description):
            raise Exception(_("issue_num_is_required"))


def check_milestone(milestone_id):
    if bot_gitlab_merge_request_milestone_required and milestone_id is None:
        raise Exception(_("milestone_is_required"))


def check_email(commit_author_name, commit_author_email):
    if bot_git_email_domain is not None:
        username, domain = commit_author_email.split("@")
        if domain != bot_git_email_domain:
            raise Exception(
                _("invalid_email_address").format(
                    commit_author_email=commit_author_email,
                    gitlab_email_domain=bot_git_email_domain,
                )
            )
        if username != commit_author_name:
            raise Exception(
                _("email_username_not_match").format(
                    commit_author_name=commit_author_name,
                    commit_author_email=commit_author_email,
                )
            )


async def check_commit(event, gl):
    print_event(event)
    project_id = event.project_id
    if event.data["event_type"] == "note":
        commit_title = event.data["merge_request"]["last_commit"]["title"]
        commit_author_name = event.data["merge_request"]["last_commit"]["author"][
            "name"
        ]
        commit_author_email = event.data["merge_request"]["last_commit"]["author"][
            "email"
        ]
        iid = event.data["merge_request"]["iid"]
        milestone_id = event.data["merge_request"]["milestone_id"]
        # source_branch = event.data["merge_request"]["source_branch"]
        description = event.data["merge_request"]["description"]
    elif event.data["event_type"] == "merge_request":
        commit_title = event.data["object_attributes"]["last_commit"]["title"]
        commit_author_name = event.data["object_attributes"]["last_commit"]["author"][
            "name"
        ]
        commit_author_email = event.data["object_attributes"]["last_commit"]["author"][
            "email"
        ]
        iid = event.data["object_attributes"]["iid"]
        milestone_id = event.data["object_attributes"]["milestone_id"]
        # source_branch = event.data["object_attributes"]["source_branch"]
        description = event.data["object_attributes"]["description"]

    merge_request_post_note_url = f"/projects/{project_id}/merge_requests/{iid}/notes"
    try:
        check_email(commit_author_name, commit_author_email)
        check_commit_message(commit_title)
        check_milestone(milestone_id)
        check_description(description)
        check_changes(gl, project_id, iid)
        url = f"/projects/{project_id}/merge_requests/{iid}/commits"
        commits = await gl.getitem(url)
        for commit in commits:
            commit_title = commit["title"]
            commit_author_name = commit["author_name"]
            commit_author_email = commit["author_email"]
            check_email(commit_author_name, commit_author_email)
            check_commit_message(commit_title)
        message = _("bot_review_success")
        merge_request_post_approval_url = (
            f"/projects/{project_id}/merge_requests/{iid}/approve"
        )

    except Exception as e:
        message = _("bot_review_fails").format(error_message=str(e))
        merge_request_post_approval_url = (
            f"/projects/{project_id}/merge_requests/{iid}/unapprove"
        )

    await gl.post(merge_request_post_note_url, data={"body": message})
    await gl.post(merge_request_post_approval_url, data=None)


class MergeRequestHooks:
    async def merge_request_opened_event(self, event, gl, *args, **kwargs):
        await check_commit(event, gl)

    async def merge_request_updated_event(self, event, gl, *args, **kwargs):
        await check_commit(event, gl)

    async def merge_request_reopen_event(self, event, gl, *args, **kwargs):
        await check_commit(event, gl)

    async def note_merge_request_event(self, event, gl, *args, **kwargs):
        note = event.data["object_attributes"]["note"]
        # username = event.data["user"]["username"]
        # merge_request_title = event.data["merge_request"]["title"]
        merge_request_state = event.data["merge_request"]["state"]  # opened
        if merge_request_state == "opened":
            if "/bot-review" in note:
                await check_commit(event, gl)
