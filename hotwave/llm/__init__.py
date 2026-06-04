"""LLM 客户端封装"""

from openai import OpenAI


def create_llm(config: dict) -> OpenAI:
    """根据配置创建 LLM 客户端"""
    provider = config.get("provider", "deepseek")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)
