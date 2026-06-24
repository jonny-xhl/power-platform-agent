"""
Authentication cache + auto authenticator (self-contained copy for framework_power).

Uses MSAL ``ConfidentialClientApplication`` with the client-credentials flow against
the credentials stored in ``config/environments.yaml`` (expanded from ``.env``).
Tokens are persisted under ``.pp-local/state/tokens.json`` and refreshed when near
expiry.
"""

import json
import logging
import msal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AuthCache:
    """Persists access tokens per environment."""

    CACHE_DIR = Path(".pp-local/state")
    CACHE_FILE = CACHE_DIR / "tokens.json"

    def __init__(self) -> None:
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def save_token(self, environment: str, token_data: Dict[str, Any]) -> None:
        """Persist ``token_data`` (access_token + expires_on) for ``environment``."""
        cache: dict[str, Any] = {}
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, "r") as f:
                    cache = json.load(f)
            except Exception:  # noqa: BLE001 - corrupt cache -> start fresh
                cache = {}

        cache[environment] = {
            "access_token": token_data.get("access_token"),
            "expires_on": token_data.get("expires_on"),
            "cached_at": datetime.now().isoformat(),
        }

        with open(self.CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)

    def load_token(self, environment: str) -> Dict[str, Any] | None:
        """Return cached token data, or ``None`` if absent / about to expire."""
        if not self.CACHE_FILE.exists():
            return None

        try:
            with open(self.CACHE_FILE, "r") as f:
                cache = json.load(f)

            if environment not in cache:
                return None

            token_data = cache[environment]
            expires_on = token_data.get("expires_on")
            if expires_on:
                expire_time = datetime.fromisoformat(expires_on)
                # Refresh 5 minutes before actual expiry.
                if datetime.now() + timedelta(minutes=5) > expire_time:
                    return None
            return token_data
        except Exception:  # noqa: BLE001
            return None

    def remove_token(self, environment: str) -> None:
        """Remove the cached token for ``environment``."""
        if not self.CACHE_FILE.exists():
            return
        try:
            with open(self.CACHE_FILE, "r") as f:
                cache = json.load(f)
            if environment in cache:
                del cache[environment]
            with open(self.CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception:  # noqa: BLE001
            pass

    def clear_all(self) -> None:
        """Delete the entire token cache file."""
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()


class AutoAuthenticator:
    """Acquires Dataverse tokens via the client-credentials flow, with caching."""

    def __init__(self, config_path: str = "config/environments.yaml") -> None:
        self.config_path = config_path
        self.cache = AuthCache()

    def get_cached_or_refresh_token(
        self,
        environment: str,
        env_config: Dict[str, Any],
    ) -> str:
        """Return a valid access token: cached first, MSAL refresh as fallback.

        Args:
            environment: Environment name (dev/test/production).
            env_config: Resolved environment config (url, tenant_id, client_id, client_secret).

        Returns:
            A bearer access token.

        Raises:
            Exception: If credentials are missing or token acquisition fails.
        """
        cached = self.cache.load_token(environment)
        if cached:
            return cached["access_token"]
        return self._refresh_token(environment, env_config)

    def _refresh_token(self, environment: str, env_config: Dict[str, Any]) -> str:
        """Acquire a fresh token via MSAL client-credentials and cache it."""
        tenant_id = env_config.get("tenant_id")
        client_id = env_config.get("client_id")
        client_secret = env_config.get("client_secret")
        url = env_config.get("url")

        if not all([tenant_id, client_id, client_secret, url]):
            raise Exception(f"Missing credentials for environment {environment}")

        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential=client_secret,
        )

        scope = [f"{url}/.default"]
        result = app.acquire_token_for_client(scopes=scope)

        if "access_token" not in result:
            raise Exception(
                f"Failed to acquire token: {result.get('error_description', 'Unknown error')}"
            )

        expires_in = result.get("expires_in", 3600)
        expires_on = datetime.now() + timedelta(seconds=expires_in)
        self.cache.save_token(
            environment,
            {"access_token": result["access_token"], "expires_on": expires_on.isoformat()},
        )
        return result["access_token"]
