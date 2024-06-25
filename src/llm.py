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

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import bot_language, openai_api_base, openai_api_key, openai_api_model, google_api_key, google_api_model, AI_PROVIDER
from src.i18n import _
from src.prompts.prompts import get_prompt_text

AI = None

if (
    openai_api_model is not None
    and openai_api_key is not None
    and openai_api_base is not None
    and AI_PROVIDER == "openai"
):
    AI = ChatOpenAI(
        openai_api_base=openai_api_base,
        openai_api_key=openai_api_key,
        model_name=openai_api_model,
        temperature=0,
        request_timeout=300,
        max_retries=2,
    )

if (
    google_api_key is not None
    and google_api_model is not None
    and AI_PROVIDER == "google"
):
    AI = ChatGoogleGenerativeAI(model=google_api_model)


def ai_diffs_summary(git_diff) -> str:
    summary_descriptions = []
    prefix = _("merge_requests_description_summary_prefix")
    suffix = _("merge_requests_description_summary_suffix")
    diff_string = json.dumps(git_diff, ensure_ascii=False, indent=4)
    logging.info(f"diffs_string: {diff_string}")
    messages = [
        SystemMessage(
            content=get_prompt_text(
                name="DIFFS_SUMMARY_PROMPTS_TEMPLATE", lang=bot_language
            )
        ),
        HumanMessage(content=diff_string),
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
