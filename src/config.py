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

openai_api_base = os.getenv("OPENAI_API_BASE")
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_api_model = os.getenv("OPENAI_API_MODEL")

# i18n
bot_language = os.environ.get("BOT_LANGUAGE", "en")
bot_port = os.environ.get("BOT_PORT", 9998)
bot_host = os.environ.get("BOT_HOST", "0.0.0.0")

# gitlab connector
bot_gitlab_username = os.environ["BOT_GITLAB_USERNAME"]
bot_gitlab_url = os.environ["BOT_GITLAB_URL"]
bot_gitlab_token = os.environ["BOT_GITLAB_TOKEN"]

# git config username & email
bot_git_email_domain = os.getenv("BOT_GIT_EMAIL_DOMAIN", None)

# git commits
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
