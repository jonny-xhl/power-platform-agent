"""
Slim Dataverse Web API client (self-contained copy for framework_power).

Only the transport + metadata endpoints needed by the table deployer are kept.
The create/update methods accept *already-serialized* Dataverse Web API JSON
(built by ``framework_power.serializer``); there is NO YAML conversion layer here.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .retry_helper import retry_on_metadata_error, retry_on_404

logger = logging.getLogger(__name__)


class DataverseClient:
    """Thin Dataverse Web API client used by the metadata deployer."""

    def __init__(
        self,
        environment: str = "dev",
        config_path: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        """Initialize the client.

        Args:
            environment: Environment name (dev/test/production).
            config_path: Path to ``config/environments.yaml``.
            access_token: Optional bearer token applied to the session.
        """
        self.environment = environment
        self.config_path = config_path or "config/environments.yaml"
        self.access_token = access_token
        self._config: dict[str, Any] | None = None
        self._session: requests.Session | None = None
        self._base_url: str | None = None
        self._api_version = "9.2"

    # ------------------------------------------------------------------ config

    @property
    def config(self) -> dict[str, Any]:
        if self._config is None:
            self._load_config()
        return self._config  # type: ignore[return-value]

    @property
    def base_url(self) -> str:
        if self._base_url is None:
            env_config = self.config.get("environments", {}).get(self.environment, {})
            self._base_url = env_config.get("url", "")
        return self._base_url  # type: ignore[return-value]

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._create_session()
        assert self._session is not None
        return self._session

    def _load_config(self) -> None:
        import yaml

        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        else:
            self._config = {"environments": {}}

    def _create_session(self) -> None:
        self._session = requests.Session()
        retry_strategy = Retry(
            total=self.config.get("environments", {})
            .get(self.environment, {})
            .get("settings", {})
            .get("retry_count", 3),
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._session.headers.update(
            {
                "OData-Version": "4.0",
                "OData-MaxVersion": "4.0",
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "Prefer": "odata.include-annotations=*",
            }
        )
        if self.access_token:
            self._session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def set_token(self, access_token: str) -> None:
        """Set (or replace) the bearer token on the session."""
        self.access_token = access_token
        if self._session:
            self._session.headers.update({"Authorization": f"Bearer {access_token}"})

    def get_api_url(self, endpoint: str) -> str:
        """Build a full Web API URL for ``endpoint``."""
        base = self.base_url.rstrip("/")
        endpoint = endpoint.lstrip("/")
        return f"{base}/api/data/v{self._api_version}/{endpoint}"

    # -------------------------------------------------------------- metadata

    def entity_exists(self, entity_name: str) -> bool:
        """Return ``True`` if the entity exists (fast, no retry)."""
        try:
            url = self.get_api_url(f"EntityDefinitions(LogicalName='{entity_name}')")
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    @retry_on_404(max_retries=5, initial_delay=2.0)
    def get_entity_metadata(self, entity_name: str) -> dict[str, Any]:
        """Get the full entity metadata (retries on transient 404)."""
        url = self.get_api_url(f"EntityDefinitions(LogicalName='{entity_name}')")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_attributes(self, entity_name: str) -> list[dict[str, Any]]:
        """List all attribute metadata for ``entity_name``."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")
        url = self.get_api_url(f"EntityDefinitions({metadata_id})/Attributes")
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get("value", [])

    def get_relationships(self, entity_name: str) -> list[dict[str, Any]]:
        """List all (1:N, N:1, N:N) relationships for ``entity_name``."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        relationships: list[dict[str, Any]] = []
        for nav in ("OneToManyRelationships", "ManyToOneRelationships", "ManyToManyRelationships"):
            url = self.get_api_url(f"EntityDefinitions({metadata_id})/{nav}")
            response = self.session.get(url)
            response.raise_for_status()
            relationships.extend(response.json().get("value", []))
        return relationships

    # --------------------------------------------------------------- deploys

    def create_entity(self, entity_definition: dict[str, Any]) -> dict[str, Any]:
        """POST a fully-serialized EntityDefinitions payload (entity + inline Attributes).

        Args:
            entity_definition: Dataverse Web API EntityMetadata JSON (already serialized).

        Returns:
            A small dict with the new entity's ``MetadataId`` when available.
        """
        url = self.get_api_url("EntityDefinitions")
        response = self.session.post(url, json=entity_definition)
        if not response.ok:
            self._raise_with_detail(response, "create entity")

        entity_id = response.headers.get("OData-EntityId", "")
        if entity_id:
            entity_id = entity_id.split("(")[-1].rstrip(")")
            return {"MetadataId": entity_id, "status": "created"}
        return {"status": "created"}

    def update_entity(self, entity_name: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH updatable entity properties (keyed by LogicalName)."""
        url = self.get_api_url(f"EntityDefinitions(LogicalName='{entity_name}')")
        response = self.session.patch(url, json=patch)
        if not response.ok:
            self._raise_with_detail(response, f"update entity '{entity_name}'")
        return {"status": "updated"}

    @retry_on_metadata_error(
        max_retries=5,
        initial_delay=3.0,
        error_patterns=[
            "not found",
            "cannot be found",
            "does not exist",
            "invalid entity",
            "another",
            "running",
            "customization operation",
            "metadatacache",
            "0x80040216",
            "0x80060891",
        ],
    )
    def create_attribute(
        self,
        entity_name: str,
        attribute_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """POST a fully-serialized attribute to ``EntityDefinitions(id)/Attributes``."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        url = self.get_api_url(f"EntityDefinitions({metadata_id})/Attributes")
        response = self.session.post(url, json=attribute_metadata)
        if not response.ok:
            self._raise_with_detail(response, f"create attribute on '{entity_name}'")

        if not response.text or response.status_code == 204:
            return {"status": "already_exists"}
        try:
            return response.json()
        except Exception:  # noqa: BLE001
            return {"status": "created"}

    @retry_on_metadata_error(
        max_retries=5,
        initial_delay=3.0,
        error_patterns=[
            "not found",
            "cannot be found",
            "does not exist",
            "invalid entity",
            "another",
            "running",
            "customization operation",
            "metadatacache",
            "0x80040216",
            "0x80060891",
        ],
    )
    def update_attribute_by_logical_name(
        self,
        entity_name: str,
        attr_logical_name: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        """PATCH an attribute by single-valued navigation (LogicalName, not MetadataId)."""
        url = self.get_api_url(
            f"EntityDefinitions(LogicalName='{entity_name}')/Attributes(LogicalName='{attr_logical_name}')"
        )
        response = self.session.patch(url, json=patch)
        if not response.ok:
            self._raise_with_detail(
                response, f"update attribute '{attr_logical_name}' on '{entity_name}'"
            )
        return {"status": "updated"}

    @retry_on_metadata_error(
        max_retries=5,
        initial_delay=3.0,
        error_patterns=[
            "not found",
            "cannot be found",
            "does not exist",
            "another",
            "running",
            "customization operation",
            "metadatacache",
            "0x80040216",
            "0x80060891",
        ],
    )
    def create_relationship_from_json(self, relationship_json: dict[str, Any]) -> dict[str, Any]:
        """POST a fully-serialized relationship (Deep Insert) to RelationshipDefinitions."""
        url = self.get_api_url("RelationshipDefinitions")
        response = self.session.post(url, json=relationship_json)
        if not response.ok:
            self._raise_with_detail(response, "create relationship")
        return {"status": "created"}

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _raise_with_detail(response: requests.Response, action: str) -> None:
        """Raise an Exception carrying the Dataverse error message for ``response``."""
        try:
            error_detail = response.json()
            error_msg = (
                error_detail.get("error", {}).get("message", {}).get("value", str(error_detail))
            )
        except Exception:  # noqa: BLE001
            error_msg = response.text
        raise Exception(
            f"Failed to {action}. Status: {response.status_code}. Error: {error_msg}"
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"DataverseClient(environment={self.environment!r}, base_url={self.base_url!r})"
