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

import json
import logging

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from src.config import (
    bot_gitlab_merge_request_summary_language,
    openai_api_base,
    openai_api_key,
    openai_api_model,
)
from src.i18n import _

AI = None
if (
    openai_api_model is not None
    and openai_api_key is not None
    and openai_api_base is not None
):
    AI = ChatOpenAI(
        openai_api_base=openai_api_base,
        openai_api_key=openai_api_key,
        model_name=openai_api_model,
        temperature=0,
        request_timeout=300,
        max_retries=2,
    )


def ai_diffs_summary(git_diff) -> str:
    summary_descriptions = []
    prefix = _("merge_requests_description_summary_prefix")
    suffix = _("merge_requests_description_summary_suffix")
    for diff in git_diff:
        diff_string = json.dumps(diff, ensure_ascii=False, indent=4)
        logging.info(f"diffs_string: {diff_string}")
        messages = [
            SystemMessage(
                content=f"You are a professional git commit review assistant, \
                generating achieve {bot_gitlab_merge_request_summary_language} summaries based on the following git diff information.\n\n{diff_string}"
            ),
            HumanMessage(content="Please summarize briefly"),
        ]
        try:
            response = AI(messages)
            summary_description = response.content
            summary_descriptions.append(f"* {summary_description}")
        except Exception as e:
            logging.error(e)
            # if isinstance(e, OpenAIError):
            #     summary_description = f"{prefix}\n>{e.json_body['message']}"
    descriptions = "\n".join(summary_descriptions)
    return f"**{prefix}**\n\n{descriptions}\n\n**{suffix}** {openai_api_model}"
