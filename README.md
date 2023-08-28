# Gitlab Bot 

This is a Gitlab bot based on webhooks to automate specific tasks:

* Generate Release Notes for a specified milestone in Issues using the /bot-release-note command.
* Check if the email domain and username of the submitter match during Merge requests.
* Check if a milestone has been specified during Merge requests.
* Check if the commit titles comply with the [Conventional Commits Specification](https://www.conventionalcommits.org/) during Merge requests.

## Quick Start

```shell
docker run --rm \
-e BOT_GITLAB_USERNAME="Your Gitlab Username" \
-e BOT_GITLAB_URL="Your Gitlab URL" \
-e BOT_GITLAB_TOKEN="Your Gitlab Access Token" \
-p 9998:9998 \
coolbeevip/gitlab-bot
```

## Environment Variables

**`BOT_GITLAB_USERNAME` / `BOT_GITLAB_URL` / `BOT_GITLAB_TOKEN`**

GitLab username, GitLab URL, and GitLab token to authenticate the bot with the GitLab API. E.g.:

```shell
BOT_GITLAB_USERNAME="coolbeevip"
BOT_GITLAB_URL="http://127.0.0.1:8081"
BOT_GITLAB_TOKEN="xxxxxx"
```

**`BOT_LANGUAGE`** 

Supports zh and en (default).

**`BOT_HOST` / `BOT_PORT`**

Host and port to run the bot. Default values are 0.0.0.0 and 9998, respectively.

**`BOT_GIT_EMAIL_DOMAIN`**

Domain to be used for email addresses when making Git commits. E.g.:

```shell
BOT_GIT_EMAIL_DOMAIN=gmail.com
```

**`BOT_GIT_COMMIT_SUBJECT_MAX_LENGTH`**

Maximum character length allowed for Git commit subjects. Default value is 100.

**`BOT_GIT_COMMIT_SUBJECT_REGEX` / `BOT_GIT_COMMIT_SUBJECT_EXAMPLES`**

Regular expression pattern and example commit subjects to validate and provide guidance for Git commit messages. E.g.: [Conventional Commits Specification](https://www.conventionalcommits.org/)

**`BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED`**

Milestone is required when creating a merge request in GitLab. Default value is false.

