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

FROM python:3.9-buster AS builder

WORKDIR /usr/app

# Create and activate virtual environment
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"

# Install dependencies
COPY poetry.lock pyproject.toml ./
# Install dependencies only (no dev dependencies)
RUN poetry export -f requirements.txt | pip install -r /dev/stdin

# Install project
COPY . .
RUN pip install -e .

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

# Copy only necessary files from builder
COPY --from=builder /usr/app/venv ./venv
COPY src src
COPY gitlab_bot.py gitlab_bot.py

ENV PATH="/usr/app/venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${BOT_PORT}/ || exit 1

CMD [ "python", "gitlab_bot.py" ]
