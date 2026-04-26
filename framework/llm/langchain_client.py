"""
LangChain LLM Client - 统一的 LLM 客户端

支持多个 LLM 提供商：Anthropic、智谱、通义千问等

环境配置加载顺序（优先级从高到低）：
1. 直接传入的参数 (api_key, model, etc.)
2. 环境变量
3. .env 文件
4. 配置文件 (config/hermes_profile.yaml)
5. 默认值
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from enum import Enum


# 尝试加载 python-dotenv（可选依赖）
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


class LLMProvider(Enum):
    """LLM 提供商"""
    ANTHROPIC = "anthropic"
    ZHIPU = "zhipu"
    QWEN = "qwen"
    OPENAI = "openai"
    DOUBAO = "doubao"


# 默认环境变量名映射
DEFAULT_ENV_MAPPING = {
    "provider": "LLM_PROVIDER",
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
        "model": "ANTHROPIC_MODEL",
    },
    "zhipu": {
        "api_key": "ZHIPUAI_API_KEY",
        "model": "ZHIPU_MODEL",
    },
    "qwen": {
        "api_key": "DASHSCOPE_API_KEY",
        "model": "QWEN_MODEL",
    },
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "model": "OPENAI_MODEL",
    },
    "doubao": {
        "api_key": "DOUBAO_API_KEY",
        "model": "DOUBAO_MODEL",
    },
}

# 默认模型配置
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "zhipu": "glm-4-flash",
    "qwen": "qwen-plus",
    "openai": "gpt-4o-mini",
    "doubao": "doubao-pro-32k",
}

# 默认 base URL 配置
DEFAULT_BASE_URLS = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
}


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    provider: str
    tokens_used: int | None = None
    finish_reason: str | None = None
    raw_response: dict[str, Any] | None = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """是否成功"""
        return bool(self.content)


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "anthropic"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4000

    # 环境配置
    env_file: str | None = None
    config_file: str | None = None
    env_prefix: str = ""

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "LLMConfig":
        """从字典创建配置"""
        return cls(**{k: v for k, v in config.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_env(cls, **kwargs) -> "LLMConfig":
        """从环境变量创建配置"""
        config = cls()

        # 加载 .env 文件
        if DOTENV_AVAILABLE:
            env_file = kwargs.get("env_file")
            if env_file:
                load_dotenv(env_file)
            else:
                # 尝试自动查找 .env 文件
                for path in [".env", ".env.local", "../.env"]:
                    if Path(path).exists():
                        load_dotenv(path)
                        break

        # 从环境变量读取
        config.provider = os.getenv(
            f"{kwargs.get('env_prefix', '')}LLM_PROVIDER",
            kwargs.get("provider", "anthropic")
        )

        # 根据提供商读取特定配置
        provider_config = DEFAULT_ENV_MAPPING.get(config.provider, {})

        if isinstance(provider_config, dict):
            config.api_key = kwargs.get("api_key") or os.getenv(
                f"{kwargs.get('env_prefix', '')}{provider_config.get('api_key', '')}"
            )
            config.model = kwargs.get("model") or os.getenv(
                f"{kwargs.get('env_prefix', '')}{provider_config.get('model', '')}",
                DEFAULT_MODELS.get(config.provider)
            )
        else:
            config.api_key = kwargs.get("api_key")
            config.model = kwargs.get("model", DEFAULT_MODELS.get(config.provider))

        config.base_url = kwargs.get("base_url") or os.getenv(
            f"{kwargs.get('env_prefix', '')}{config.provider.upper()}_BASE_URL",
            DEFAULT_BASE_URLS.get(config.provider)
        )

        config.temperature = kwargs.get("temperature", 0.3)
        config.max_tokens = kwargs.get("max_tokens", 4000)

        return config

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "LLMConfig":
        """从 YAML 配置文件读取"""
        import yaml

        config_file = Path(yaml_path)
        if not config_file.exists():
            return cls()

        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 从配置文件中提取 LLM 相关配置
        llm_config = data.get("llm", {})

        config = cls(
            provider=llm_config.get("provider", os.getenv("LLM_PROVIDER", "anthropic")),
            model=llm_config.get("model"),
            api_key=os.getenv(llm_config.get("api_key_env", ""), None),
            base_url=llm_config.get("base_url"),
            temperature=llm_config.get("temperature", 0.3),
            max_tokens=llm_config.get("max_tokens", 4000),
        )

        # 如果配置文件中有提供商特定配置
        provider_config = llm_config.get("提供商配置", {}).get(config.provider, {})
        if provider_config:
            config.model = provider_config.get("model") or config.model
            config.api_key = os.getenv(provider_config.get("api_key_env", "")) or config.api_key
            config.base_url = provider_config.get("base_url") or config.base_url

        return config


class LangChainLLMClient:
    """
    统一的 LLM 客户端

    使用策略模式，支持多个 LLM 提供商

    使用方式：
        # 方式1：使用默认配置
        client = LangChainLLMClient()

        # 方式2：从环境变量加载
        client = LangChainLLMClient.from_env()

        # 方式3：手动指定
        client = LangChainLLMClient(
            provider="zhipu",
            api_key="your-key",
            model="glm-4-flash"
        )

        # 方式4：从配置文件加载
        client = LangChainLLMClient.from_yaml("config/hermes_profile.yaml")
    """

    # 类级别的配置缓存
    _config_cache: LLMConfig | None = None

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        api_key: str | None = None,
        base_url: str | None = None,
        _config: LLMConfig | None = None
    ):
        """
        初始化 LLM 客户端

        Args:
            provider: 提供商名称 (默认从环境变量 LLM_PROVIDER 读取)
            model: 模型名称 (默认从环境变量读取)
            temperature: 温度参数
            max_tokens: 最大 token 数
            api_key: API 密钥 (默认从环境变量读取)
            base_url: API 基础 URL
            _config: 内部使用的配置对象
        """
        # 使用传入的配置或创建新配置
        if _config:
            self.config = _config
        else:
            self.config = LLMConfig.from_env(
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens
            )

        self.provider = self.config.provider
        self.model = self.config.model or self._get_default_model(self.provider)
        self.temperature = self.config.temperature
        self.max_tokens = self.config.max_tokens
        self.api_key = self.config.api_key or self._get_api_key(self.provider)
        self.base_url = self.config.base_url

        # 验证必要配置
        if not self.api_key:
            raise ValueError(
                f"API key not found for provider '{self.provider}'. "
                f"Please set {self._get_api_key_env_var(self.provider)} environment variable."
            )

        # 客户端实例
        self._client = None
        self._setup_client()

    @classmethod
    def from_env(cls, **kwargs) -> "LangChainLLMClient":
        """从环境变量创建客户端"""
        config = LLMConfig.from_env(**kwargs)
        return cls(_config=config)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "LangChainLLMClient":
        """从 YAML 配置文件创建客户端"""
        config = LLMConfig.from_yaml(yaml_path)
        return cls(_config=config)

    @classmethod
    def from_config(cls, config: LLMConfig) -> "LangChainLLMClient":
        """从配置对象创建客户端"""
        return cls(_config=config)

    def _get_api_key_env_var(self, provider: str) -> str:
        """获取 API key 的环境变量名"""
        provider_config = DEFAULT_ENV_MAPPING.get(provider, {})
        if isinstance(provider_config, dict):
            return provider_config.get("api_key", "")
        return ""

    def _get_default_model(self, provider: str) -> str:
        """获取默认模型"""
        return DEFAULT_MODELS.get(provider, "claude-sonnet-4-20250514")

    def _get_api_key(self, provider: str) -> str | None:
        """获取 API 密钥"""
        # 如果在初始化时已经提供，直接返回
        if self.config.api_key:
            return self.config.api_key

        # 从环境变量获取
        provider_config = DEFAULT_ENV_MAPPING.get(provider, {})
        if isinstance(provider_config, dict):
            env_var = provider_config.get("api_key", "")
            if env_var:
                return os.getenv(env_var)
        return None

    def _setup_client(self):
        """设置客户端"""
        if self.provider == "anthropic":
            self._setup_anthropic()
        elif self.provider == "zhipu":
            self._setup_zhipu()
        elif self.provider == "qwen":
            self._setup_qwen()
        elif self.provider == "openai":
            self._setup_openai()
        elif self.provider == "doubao":
            self._setup_doubao()
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _setup_anthropic(self):
        """设置 Anthropic 客户端"""
        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "anthropic package is required for Anthropic provider. "
                "Install it with: pip install anthropic"
            )

    def _setup_zhipu(self):
        """设置智谱 AI 客户端"""
        try:
            from zhipuai import ZhipuAI
            self._client = ZhipuAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "zhipuai package is required for Zhipu provider. "
                "Install it with: pip install zhipuai"
            )

    def _setup_qwen(self):
        """设置通义千问客户端"""
        try:
            from openai import OpenAI
            base_url = self.base_url or DEFAULT_BASE_URLS.get(
                "qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url  # type: ignore[arg-type]
            )
        except ImportError:
            raise ImportError(
                "openai package is required for Qwen provider. "
                "Install it with: pip install openai"
            )

    def _setup_openai(self):
        """设置 OpenAI 客户端"""
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI provider. "
                "Install it with: pip install openai"
            )

    def _setup_doubao(self):
        """设置豆包客户端"""
        try:
            from openai import OpenAI
            base_url = self.base_url or DEFAULT_BASE_URLS.get("doubao", "https://ark.cn-beijing.volces.com/api/v3")
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=base_url  # type: ignore[arg-type]
            )
        except ImportError:
            raise ImportError(
                "openai package is required for Doubao provider. "
                "Install it with: pip install openai"
            )

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            max_tokens: 最大 token 数
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLM 响应
        """
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        if self.provider == "anthropic":
            return self._generate_anthropic(
                prompt, system_prompt, max_tokens, temperature, **kwargs
            )
        elif self.provider == "zhipu":
            return self._generate_zhipu(
                prompt, system_prompt, max_tokens, temperature, **kwargs
            )
        elif self.provider in ("qwen", "openai", "doubao"):
            return self._generate_openai_compat(
                prompt, system_prompt, max_tokens, temperature, **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """使用 Anthropic API 生成"""
        messages = [{"role": "user", "content": prompt}]

        params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            params["system"] = system_prompt

        response = self._client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            provider="anthropic",
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason,
            raw_response={"model": response.model, "id": response.id}
        )

    def _generate_zhipu(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """使用智谱 AI API 生成"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="zhipu",
            tokens_used=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason,
        )

    def _generate_openai_compat(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        **kwargs
    ) -> LLMResponse:
        """使用 OpenAI 兼容 API 生成"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=self.provider,
            tokens_used=response.usage.total_tokens,
            finish_reason=response.choices[0].finish_reason,
        )

    def count_tokens(self, text: str) -> int:
        """
        估算 token 数量

        Args:
            text: 文本

        Returns:
            估算的 token 数量
        """
        # 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ):
        """
        流式生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数

        Yields:
            文本片段
        """
        if self.provider == "anthropic":
            yield from self._stream_anthropic(prompt, system_prompt, **kwargs)
        elif self.provider == "zhipu":
            yield from self._stream_zhipu(prompt, system_prompt, **kwargs)
        elif self.provider in ("qwen", "openai", "doubao"):
            yield from self._stream_openai_compat(prompt, system_prompt, **kwargs)
        else:
            raise ValueError(f"Streaming not supported for provider: {self.provider}")

    def _stream_anthropic(self, prompt: str, system_prompt: str | None, **kwargs):
        """Anthropic 流式生成"""
        messages = [{"role": "user", "content": prompt}]
        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
        }
        if system_prompt:
            params["system"] = system_prompt

        with self._client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield text

    def _stream_zhipu(self, prompt: str, system_prompt: str | None, **kwargs):
        """智谱 AI 流式生成"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _stream_openai_compat(self, prompt: str, system_prompt: str | None, **kwargs):
        """OpenAI 兼容流式生成"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stream=True,
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def create_llm_client(
    provider: str | None = None,
    **kwargs
) -> LangChainLLMClient:
    """
    创建 LLM 客户端的工厂函数

    Args:
        provider: 提供商名称
        **kwargs: 其他参数

    Returns:
        LLM 客户端实例

    Examples:
        # 使用默认配置
        client = create_llm_client()

        # 指定提供商
        client = create_llm_client(provider="zhipu")

        # 从环境变量加载
        client = create_llm_client.from_env()

        # 从配置文件加载
        client = create_llm_client.from_yaml("config/hermes_profile.yaml")
    """
    return LangChainLLMClient(provider=provider, **kwargs)
