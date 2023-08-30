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
