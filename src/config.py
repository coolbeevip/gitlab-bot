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

import os

from dotenv import load_dotenv

load_dotenv()  # isort:skip
DEFAULT_BOT_GIT_COMMIT_SUBJECT_REGEX_VALUE = (
    "^(fix|feat|docs|style|refactor|test|chore|build|ci): .*$"
)
DEFAULT_BOT_GIT_COMMIT_SUBJECT_EXAMPLES_MARKDOWN_VALUE = """
* feat: Add authentication module   
* fix: Resolve issue with login not working
* docs: Update README with installation instructions
* style: Format code according to the coding guidelines
* refactor: Extract reusable function for file upload
* test: Add unit tests for payment processing module
* build: Upgrade to Node.js version 14.0
* ci: Update Travis CI configuration for better test coverage
* chore: Update .gitignore file
"""
DEFAULT_BOT_GIT_COMMIT_SUBJECT_MAX_LENGTH_VALUE = 100
DEFAULT_BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED_VALUE = "false"
DEFAULT_BOT_GITLAB_MERGE_REQUEST_ISSUE_REQUIRED_VALUE = "false"
DEFAULT_BOT_GIT_COMMIT_SUBJECT_REGEX_ENABLED = "true"
DEFAULT_BOT_GITLAB_MERGE_REQUEST_SUMMARY_ENABLED_VALUE = "true"
DEFAULT_BOT_GITLAB_MERGE_REQUEST_EMAIL_USERNAME_NOT_MATCH_ENABLED = "true"
DEFAULT_BOT_GITLAB_MERGE_REQUEST_APPROVAL_ENABLED = "true"
DEFAULT_BOT_GIT_COMMIT_MESSAGE_CHECK_ENABLED = "true"
DEFAULT_BOT_GITLAB_MERGE_REQUEST_AIREVIEW_LABEL_ENABLED = "true"

# openai api
openai_api_base = os.getenv("OPENAI_API_BASE")
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_api_model = os.getenv("OPENAI_API_MODEL")

# azure openai
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
azure_openai_model = os.getenv("AZURE_OPENAI_MODEL")
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

# google gemini api
google_api_key = os.getenv("GOOGLE_API_KEY")
google_api_model = os.getenv("GOOGLE_API_MODEL")

# ai backend (openai or gemini)
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")

model_name = {
    "openai": openai_api_model,
    "azure-openai": azure_openai_model,
    "google": google_api_model,
}.get(AI_PROVIDER, None)

# i18n
bot_language = os.environ.get("BOT_LANGUAGE", "en")
bot_port = os.environ.get("BOT_PORT", "9998")
bot_host = os.environ.get("BOT_HOST", "0.0.0.0")

# gitlab connector
bot_gitlab_username = os.getenv("BOT_GITLAB_USERNAME", None)
bot_gitlab_url = os.getenv("BOT_GITLAB_URL", None)
bot_gitlab_token = os.getenv("BOT_GITLAB_TOKEN", None)

# git config username & email
bot_git_email_domain = os.getenv("BOT_GIT_EMAIL_DOMAIN", None)

# git commits
bot_git_commit_message_check_enabled = (
    os.getenv(
        "BOT_GIT_COMMIT_MESSAGE_CHECK_ENABLED",
        DEFAULT_BOT_GIT_COMMIT_MESSAGE_CHECK_ENABLED,
    ).lower()
    == "true"
)

bot_git_commit_subject_regex_enabled = (
    os.getenv(
        "BOT_GIT_COMMIT_SUBJECT_REGEX_ENABLED",
        DEFAULT_BOT_GIT_COMMIT_SUBJECT_REGEX_ENABLED,
    ).lower()
    == "true"
)
bot_git_commit_subject_regex = os.getenv(
    "BOT_GIT_COMMIT_SUBJECT_REGEX", DEFAULT_BOT_GIT_COMMIT_SUBJECT_REGEX_VALUE
)
bot_git_commit_subject_example_markdown = os.getenv(
    "BOT_GIT_COMMIT_SUBJECT_EXAMPLES_MARKDOWN",
    DEFAULT_BOT_GIT_COMMIT_SUBJECT_EXAMPLES_MARKDOWN_VALUE,
).replace("\\n", "\n")
bot_git_commit_subject_max_length = int(
    os.getenv(
        "BOT_GIT_COMMIT_SUBJECT_MAX_LENGTH",
        DEFAULT_BOT_GIT_COMMIT_SUBJECT_MAX_LENGTH_VALUE,
    )
)

# gitlab merge request
bot_gitlab_merge_request_milestone_required = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED_VALUE,
    ).lower()
    == "true"
)
bot_gitlab_merge_request_issue_required = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_ISSUE_REQUIRED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_ISSUE_REQUIRED_VALUE,
    ).lower()
    == "true"
)
bot_gitlab_merge_request_summary_enabled = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_SUMMARY_ENABLED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_SUMMARY_ENABLED_VALUE,
    ).lower()
    == "true"
)
# gitlab merge request summary
bot_gitlab_merge_request_summary_language = os.getenv(
    "BOT_GITLAB_MERGE_REQUEST_SUMMARY_LANGUAGE", "English"
)

# gitlab merge request email username not match check
bot_gitlab_merge_request_email_username_not_match_enabled = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_EMAIL_USERNAME_NOT_MATCH_ENABLED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_EMAIL_USERNAME_NOT_MATCH_ENABLED,
    ).lower()
    == "true"
)

# gitlab merge request approval
bot_gitlab_merge_request_approval_enabled = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_APPROVAL_ENABLED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_APPROVAL_ENABLED,
    ).lower()
    == "true"
)

# gitlab merge request ai review label
bot_gitlab_merge_request_aireview_label_enabled = (
    os.getenv(
        "BOT_GITLAB_MERGE_REQUEST_AIREVIEW_LABEL_ENABLED",
        DEFAULT_BOT_GITLAB_MERGE_REQUEST_AIREVIEW_LABEL_ENABLED,
    ).lower()
    == "true"
)
