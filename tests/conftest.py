"""Keep test configuration independent from a developer's local .env file."""

import os

os.environ.update(
    {
        "BOT_GIT_COMMIT_MESSAGE_CHECK_ENABLED": "true",
        "BOT_GIT_COMMIT_SUBJECT_REGEX_ENABLED": "true",
        "BOT_GIT_COMMIT_SUBJECT_REGEX": (
            r"^(\[(fix|feat)\]:\[.*]\[.*\]|"
            r"\[(docs|style|ref|test|chore|tag|revert|perf)\]:\[.*\])$"
        ),
        "BOT_GIT_EMAIL_DOMAIN": "asiainfo.com",
        "BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED": "false",
        "BOT_GITLAB_MERGE_REQUEST_ISSUE_REQUIRED": "false",
        "BOT_GITLAB_MERGE_REQUEST_APPROVAL_ENABLED": "true",
    }
)
