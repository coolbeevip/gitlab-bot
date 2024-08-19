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
import re

from src.config import (
    bot_git_commit_subject_example_markdown,
    bot_git_commit_subject_max_length,
    bot_git_commit_subject_regex,
    bot_git_email_domain,
    bot_gitlab_merge_request_issue_required,
    bot_gitlab_merge_request_milestone_required,
    bot_gitlab_merge_request_summary_enabled,
    bot_gitlab_username,
    bot_gitlab_merge_request_email_username_not_match_enabled,
    bot_git_commit_message_check_enabled,
    bot_gitlab_merge_request_approval_enabled
)
from src.i18n import _
from src.llm import AI, ai_diffs_summary


def check_changes(gl, project_id, iid):
    # url = f"/projects/{project_id}/merge_requests/{iid}/changes"
    # changes = await gl.getitem(url)
    # for change in changes:
    pass


def check_commit_message(commit_msg):
    if bot_git_commit_message_check_enabled == False:
        return
    if len(commit_msg) > bot_git_commit_subject_max_length:
        raise Exception(
            _("commit_subject_max_length").format(
                commit_subject_max_length=bot_git_commit_subject_max_length
            )
        )
    if commit_msg.startswith("Merge branch "):
        return
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
        if bot_gitlab_merge_request_email_username_not_match_enabled and username != commit_author_name:
            raise Exception(
                _("email_username_not_match").format(
                    commit_author_name=commit_author_name,
                    commit_author_email=commit_author_email,
                )
            )


async def generate_diff_description_summary(event, gl):
    if bot_gitlab_merge_request_summary_enabled and AI is not None:
        try:
            project_id = event.project_id
            description = event.data["object_attributes"]["description"]
            iid = event.data["object_attributes"]["iid"]
            if "AI Summary:" not in description:
                try:
                    # Support 15.7+
                    diff_url = f"/projects/{project_id}/merge_requests/{iid}/diffs"
                    diffs = await gl.getitem(diff_url)
                except Exception as e:
                    logging.warning(
                        "Calling API /diffs error, trying to call /changes", e
                    )
                    diff_url = f"/projects/{project_id}/merge_requests/{iid}/changes"
                    changes = await gl.getitem(diff_url)
                    diffs = changes["changes"]

                response_summary = ai_diffs_summary(diffs)

                merge_request_post_note_url = (
                    f"/projects/{project_id}/merge_requests/{iid}/notes"
                )
                await gl.post(
                    merge_request_post_note_url,
                    data={"body": response_summary},
                )
        except Exception as e:
            logging.error(e)


async def check_commit(event, gl):
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
        if bot_gitlab_merge_request_approval_enabled:
            message = _("bot_review_success")
            approval_merge_request(project_id, iid, gl)
            await gl.post(merge_request_post_note_url, data={"body": message})
    except Exception as e:
        message = _("bot_review_fails").format(error_message=str(e))
        await gl.post(merge_request_post_note_url, data={"body": message})

        # Only support GitLab Premium in 13.9
        # https://docs.gitlab.com/ee/api/merge_request_approvals.html#unapprove-merge-request
        # merge_request_post_unapproval_url = (
        #     f"/projects/{project_id}/merge_requests/{iid}/unapprove"
        # )
        # await gl.post(merge_request_post_unapproval_url, data=None)


async def approval_merge_request(project_id, iid, gl):
    query_approvals_url = f"/projects/{project_id}/merge_requests/{iid}/approvals"
    approvals = gl.getitem(query_approvals_url)
    bot_approved = False
    if approvals.approved:
        for approval in approvals.approved_by:
            if approval.user.username == bot_gitlab_username:
                bot_approved = True
                return
    if not bot_approved:
        await gl.post(f"/projects/{project_id}/merge_requests/{iid}/approve", data=None)


def is_opened_merge_request(event):
    if event.data["event_type"] == "merge_request":
        merge_request_state = event.data["object_attributes"]["state"]
    else:
        merge_request_state = event.data["merge_request"]["state"]
    return merge_request_state == "opened"


class MergeRequestHooks:
    async def merge_request_opened_event(self, event, gl, *args, **kwargs):
        await generate_diff_description_summary(event, gl)
        await check_commit(event, gl)

    async def merge_request_updated_event(self, event, gl, *args, **kwargs):
        if is_opened_merge_request(event):
            await generate_diff_description_summary(event, gl)
            await check_commit(event, gl)

    async def merge_request_reopen_event(self, event, gl, *args, **kwargs):
        await generate_diff_description_summary(event, gl)
        await check_commit(event, gl)

    async def note_merge_request_event(self, event, gl, *args, **kwargs):
        if is_opened_merge_request(event):
            if "/bot-review" in event.data["object_attributes"]["note"]:
                await check_commit(event, gl)
