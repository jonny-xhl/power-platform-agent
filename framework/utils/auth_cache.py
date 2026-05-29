"""
认证缓存管理器

提供 token 的持久化存储和自动刷新功能
"""
import json
import os
import msal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict


class AuthCache:
    """认证缓存管理器"""

    CACHE_DIR = Path(".pp-local/state")
    CACHE_FILE = CACHE_DIR / "tokens.json"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def save_token(self, environment: str, token_data: Dict[str, Any]) -> None:
        """
        保存 token 到缓存文件

        Args:
            environment: 环境名称
            token_data: token 数据，包含 access_token, expires_on 等
        """
        # 读取现有缓存
        cache = {}
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    cache = json.load(f)
            except:
                cache = {}

        # 更新指定环境的 token
        cache[environment] = {
            "access_token": token_data.get("access_token"),
            "expires_on": token_data.get("expires_on"),
            "cached_at": datetime.now().isoformat()
        }

        # 保存到文件
        with open(self.CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)

    def load_token(self, environment: str) -> Dict[str, Any] | None:
        """
        从缓存加载 token

        Args:
            environment: 环境名称

        Returns:
            token 数据，如果不存在或已过期返回 None
        """
        if not self.CACHE_FILE.exists():
            return None

        try:
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)

            if environment not in cache:
                return None

            token_data = cache[environment]

            # 检查是否过期（提前5分钟刷新）
            expires_on = token_data.get("expires_on")
            if expires_on:
                expire_time = datetime.fromisoformat(expires_on)
                if datetime.now() + timedelta(minutes=5) > expire_time:
                    return None  # 即将过期，返回 None 让调用者刷新

            return token_data
        except:
            return None

    def remove_token(self, environment: str) -> None:
        """移除指定环境的 token"""
        if not self.CACHE_FILE.exists():
            return

        try:
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)

            if environment in cache:
                del cache[environment]

            with open(self.CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
        except:
            pass

    def clear_all(self) -> None:
        """清除所有缓存的 token"""
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()


class AutoAuthenticator:
    """自动认证器 - 使用 .env 中的凭据自动获取 token"""

    def __init__(self, config_path: str = "config/environments.yaml"):
        self.config_path = config_path
        self.cache = AuthCache()

    def get_cached_or_refresh_token(
        self,
        environment: str,
        env_config: Dict[str, Any]
    ) -> str:
        """
        获取缓存的 token，如果不存在或过期则自动刷新

        Args:
            environment: 环境名称
            env_config: 环境配置

        Returns:
            access_token

        Raises:
            Exception: 如果认证失败
        """
        # 尝试从缓存加载
        cached = self.cache.load_token(environment)
        if cached:
            return cached["access_token"]

        # 缓存中没有或已过期，使用凭据刷新
        return self._refresh_token(environment, env_config)

    def _refresh_token(self, environment: str, env_config: Dict[str, Any]) -> str:
        """使用凭据获取新的 token"""
        tenant_id = env_config.get("tenant_id")
        client_id = env_config.get("client_id")
        client_secret = env_config.get("client_secret")
        url = env_config.get("url")

        if not all([tenant_id, client_id, client_secret, url]):
            raise Exception(f"Missing credentials for environment {environment}")

        # 使用 MSAL 获取 token
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential=client_secret
        )

        scope = [f"{url}/.default"]
        result = app.acquire_token_for_client(scopes=scope)

        if "access_token" not in result:
            raise Exception(f"Failed to acquire token: {result.get('error_description', 'Unknown error')}")

        # 计算过期时间（默认 1 小时）
        expires_in = result.get("expires_in", 3600)
        expires_on = datetime.now() + timedelta(seconds=expires_in)

        # 保存到缓存
        self.cache.save_token(environment, {
            "access_token": result["access_token"],
            "expires_on": expires_on.isoformat()
        })

        return result["access_token"]
