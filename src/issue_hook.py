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
import datetime
import re

from src.i18n import _


async def parse_milestone_release_note(event, gl):
    project_id = event.project_id
    if event.data["event_type"] == "note":
        idd = event.data["issue"]["iid"]
    else:
        idd = event.data["issue"]["iid"]
    note = event.data["object_attributes"]["note"]
    if "/bot-release-note" in note:
        try:
            pattern = r"/bot-release-note\s(\d+\.\d+\.\d+)"
            match = re.search(pattern, note)
            if match:
                milestone_name = match.group(1)
                milestones_query_url = (
                    f"/projects/{project_id}/milestones?title={milestone_name}"
                )
                milestones = await gl.getitem(milestones_query_url)
                if len(milestones) == 1:
                    milestone_id = milestones[0]["id"]
                    query_merge_requests_by_milestone_url = f"/projects/{project_id}/milestones/{milestone_id}/merge_requests"
                    merge_requests = await gl.getitem(
                        query_merge_requests_by_milestone_url
                    )
                    notes = []
                    for merge_request in merge_requests:
                        notes.append(
                            f"* [{merge_request['title']}]({merge_request['web_url']})\n"
                        )
                    message = _("milestone_release_note").format(
                        milestone=milestone_name, notes="".join(notes)
                    )
                else:
                    message = _("milestone_not_found").format(milestone=milestone_name)
            else:
                raise Exception(
                    _("invalid_bot_action").format(action="/bot-release-note 1.0.0")
                )
        except Exception as e:
            message = str(e)

        url = f"/projects/{project_id}/issues/{idd}/notes"
        await gl.post(url, data={"body": message})


async def automatically_mark_and_later_remove_stale_issues(event, gl):
    project_id = event.project_id
    # username = event.data["user"]["username"]
    issues = await gl.getitem(
        f"/projects/{project_id}/issues?state=opened&per_page=100"
    )
    for issue in issues:
        updated_at = datetime.fromisoformat(issue["updated_at"]).replace(tzinfo=None)
        current_time = datetime.now()
        diff = current_time - updated_at
        if diff.days > 30:
            print(
                f"{diff.days} {issue['author']['name']}: {issue['created_at']} - {issue['updated_at']} {issue['title']}"
            )
            # message = "此问题已经超过 30 天无任何反馈，如已解决请关闭或者联系相关处理人员跟踪此问题"
            # commits_data = await gl.getitem(
            #     f"/projects/{project_id}/issues/{issue['iid']}/notes"
            # )
            # history_commits = [commit["body"] for commit in commits_data]
            # if message not in history_commits:
            #     url = f"/projects/{project_id}/issues/{issue['iid']}/notes"
            #     await gl.post(url, data={"body": message})
            #     print(message)


class IssueHooks:
    async def issue_opened_event(self, event, gl, *args, **kwargs):
        pass
        # automatically_mark_and_later_remove_stale_issues(event, gl)

    async def issue_closed_event(self, event, gl, *args, **kwargs):
        pass

    async def issue_updated_event(self, event, gl, *args, **kwargs):
        pass

    async def note_issue_event(self, event, gl, *args, **kwargs):
        await parse_milestone_release_note(event, gl)
