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

FROM ghcr.io/astral-sh/uv:0.10.11 AS uv

FROM python:3.9-buster AS builder

COPY --from=uv /uv /bin/uv

WORKDIR /usr/app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Preserve the Python 3.9 venv bootstrap packages used by gidgetlab 1.1.0.
RUN python -m venv .venv

# Install locked production dependencies before copying application code.
COPY pyproject.toml uv.lock ./
RUN uv lock --check && uv sync --frozen --no-dev --no-install-project --no-editable

# Install the project as a non-editable package for the production stage.
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.9-slim AS production

# Set environment variables in separate layers for better caching
ENV BOT_LANGUAGE="en" \
    BOT_HOST="0.0.0.0" \
    BOT_PORT=9998 \
    BOT_GIT_COMMIT_SUBJECT_MAX_LENGTH=100 \
    BOT_GIT_COMMIT_SUBJECT_REGEX="^(\[(fix|feat)\]:\[.*]\[.*\]|\[(docs|style|ref|test|chore|tag|revert|perf)\]:\[.*\])$" \
    BOT_GIT_COMMIT_SUBJECT_EXAMPLES="[feat]:[][Added xxx];[feat]:[][Added xxx];[fix]:[][Fixed xxx];[docs]:[][Added/Updated/Removed xxx];[style]:[Formatted xxx];[ref]:[Refactored xxx];[test]:[Added xxx];[chore]:[Updated xxx];[tag]:[Tag xxx];[revert]:[Reverted xxx];[perf]:[Optimized xxx]" \
    BOT_GITLAB_MERGE_REQUEST_MILESTONE_REQUIRED=false

WORKDIR /usr/app

# Copy only the production environment and application entry point.
COPY --from=builder /usr/app/.venv ./venv
COPY gitlab_bot.py gitlab_bot.py

ENV PATH="/usr/app/venv/bin:$PATH"

# Probe the existing gidgetlab health endpoint with the Python standard library.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=12 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('BOT_PORT', '9998') + '/health', timeout=2).read()"]

CMD [ "python", "gitlab_bot.py" ]
