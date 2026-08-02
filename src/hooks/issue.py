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
from datetime import datetime, timedelta

from src.i18n import _


async def bot_issue_help(event, gl):
    project_id = event.project_id
    idd = event.data["issue"]["iid"]
    await gl.post(
        f"/projects/{project_id}/issues/{idd}/notes",
        data={"body": _("bot_issue_help")},
    )


async def parse_milestone_release_note(event, gl):
    project_id = event.project_id
    if event.data["event_type"] == "note":
        idd = event.data["issue"]["iid"]
    else:
        idd = event.data["issue"]["iid"]
    note = event.data["object_attributes"]["note"]
    try:
        pattern = r"/bot-release-note\s(\d+\.\d+\.\d+)"
        match = re.search(pattern, note)
        if match:
            milestone_name = match.group(1)
            milestones_query_url = f"/projects/{project_id}/milestones?title={milestone_name}"
            milestones = await gl.getitem(milestones_query_url)
            if len(milestones) == 1:
                milestone_id = milestones[0]["id"]
                query_merge_requests_by_milestone_url = (
                    f"/projects/{project_id}/milestones/{milestone_id}/merge_requests"
                )
                merge_requests = await gl.getitem(query_merge_requests_by_milestone_url)
                notes = []
                for merge_request in merge_requests:
                    notes.append(f"* [{merge_request['title']}]({merge_request['web_url']})\n")
                message = _("milestone_release_note").format(milestone=milestone_name, notes="".join(notes))
            else:
                message = _("milestone_not_found").format(milestone=milestone_name)
        else:
            raise Exception(_("invalid_bot_action").format(action="/bot-release-note 1.0.0"))
    except Exception as e:
        message = str(e)

    url = f"/projects/{project_id}/issues/{idd}/notes"
    await gl.post(url, data={"body": message})


async def automatically_mark_label_outdated_issues(event, gl, days_ago=14):
    project_id = event.project_id
    idd = event.data["issue"]["iid"]
    # get all issues updated before N days ago
    date_days_ago = datetime.now() - timedelta(days=days_ago)
    updated_before = date_days_ago.strftime("%Y-%m-%d")
    old_issues = await gl.getitem(f"/projects/{project_id}/issues?state=opened&updated_before={updated_before}")
    outdated_issue_label = "Outdated"
    if len(old_issues) > 0:
        for issue in old_issues:
            issue_labels = issue["labels"]
            if outdated_issue_label not in issue_labels:
                # create label if not exist
                all_labels = await gl.getitem(f"/projects/{project_id}/labels")
                if any(d["name"] == outdated_issue_label for d in all_labels):
                    pass
                else:
                    # create label
                    await gl.post(
                        f"/projects/{project_id}/labels",
                        data={
                            "name": outdated_issue_label,
                            "color": "#6699cc",
                        },
                    )
                # add label to issue
                issue_labels.append(outdated_issue_label)
                await gl.put(
                    f"/projects/{project_id}/issues/{issue['iid']}?labels={','.join(issue_labels)}",
                    data=None,
                )
    await gl.post(
        f"/projects/{project_id}/issues/{idd}/notes",
        data={
            "body": _("marked_issue_outdated_summary").format(
                total=len(old_issues),
                days_ago=days_ago,
                label_name=outdated_issue_label,
            )
        },
    )


def is_opened_issue(event):
    return event.data["issue"]["state"] == "opened"


class IssueHooks:
    async def issue_opened_event(self, event, gl, *args, **kwargs):
        pass

    async def issue_closed_event(self, event, gl, *args, **kwargs):
        pass

    async def issue_updated_event(self, event, gl, *args, **kwargs):
        if is_opened_issue(event):
            pass

    async def note_issue_event(self, event, gl, *args, **kwargs):
        if is_opened_issue(event):
            note = event.data["object_attributes"]["note"]
            if "/bot-release-note" in note:
                await parse_milestone_release_note(event, gl)
            elif "/bot-issue-outdated" in note:
                await automatically_mark_label_outdated_issues(event, gl)
            elif "/bot" in note:
                await bot_issue_help(event, gl)
