# Copyright 2026 Lei Zhang
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

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


@dataclass
class MergeRequestNotification:
    """Normalized, channel-independent information about an MR action."""

    source: str
    event_type: str
    action: str
    webhook_action: str
    message: str
    project: Dict[str, Any]
    merge_request: Dict[str, Any]
    actor: Dict[str, Any]
    occurred_at: Optional[str]
    raw_payload: Optional[Mapping[str, Any]] = None
    triggered_by: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
