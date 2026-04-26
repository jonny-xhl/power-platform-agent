"""
LLM Client - 统一的 LLM 客户端接口

支持多个 LLM 提供商
"""

from .langchain_client import LangChainLLMClient, LLMResponse

__all__ = ["LangChainLLMClient", "LLMResponse"]
