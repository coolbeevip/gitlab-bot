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

from src.i18n import _
from src.logs import print_event


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
                    _("invalid_bot_action").format(action="/src-release-note 1.0.0")
                )
        except Exception as e:
            message = str(e)
            logging.error(e)

        url = f"/projects/{project_id}/issues/{idd}/notes"
        await gl.post(url, data={"body": message})


class IssueHooks:
    async def issue_opened_event(self, event, gl, *args, **kwargs):
        # """Whenever an issue is opened, greet the author and say thanks."""
        # url = f"/projects/{event.project_id}/issues/{event.object_attributes['iid']}/notes"
        # message = f"Thanks for the report @{event.data['user']['username']}! I will look into it ASAP! (I'm a src)."
        # await gl.post(url, data={"body": message})
        print_event(event)

    async def issue_closed_event(self, event, gl, *args, **kwargs):
        # url = f"/projects/{event.project_id}/issues/{event.object_attributes['iid']}/notes"
        # message = f"Bye @{event.data['user']['username']}! (I'm a src)."
        # await gl.post(url, data={"body": message})
        print_event(event)

    async def issue_updated_event(self, event, gl, *args, **kwargs):
        print_event(event)

    async def note_issue_event(self, event, gl, *args, **kwargs):
        print_event(event)
        await parse_milestone_release_note(event, gl)
