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

from langchain.chat_models import ChatOpenAI

from src.config import openai_api_base, openai_api_key, openai_api_model

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
    )
