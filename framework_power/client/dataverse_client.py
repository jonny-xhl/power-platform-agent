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


def _odata_quote(value: str) -> str:
    """URL-encode a string for safe use inside an OData quoted literal."""
    from urllib.parse import quote

    return quote(value, safe="")


def _entity_id(response: requests.Response) -> Optional[str]:
    """Parse the GUID out of an ``OData-EntityId`` create-response header."""
    entity_id = response.headers.get("OData-EntityId", "")
    if entity_id:
        return entity_id.split("(")[-1].rstrip(")")
    return None


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

    def get_entity_metadata_by_id(self, metadata_id: str) -> dict[str, Any]:
        """Get entity metadata keyed by MetadataId (used by solution reverse)."""
        url = self.get_api_url(f"EntityDefinitions({metadata_id})")
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
        """PATCH updatable entity properties (keyed by MetadataId; LogicalName PATCH is 405)."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")
        url = self.get_api_url(f"EntityDefinitions({metadata_id})")
        response = self.session.patch(url, json=patch)
        if not response.ok:
            self._raise_with_detail(response, f"update entity '{entity_name}'")
        return {"status": "updated"}

    def delete_entity(self, logical_name: str) -> dict[str, Any]:
        """DELETE an entity by logical name.

        Cascades to the entity's attributes and the relationships it owns (including its
        lookup columns). Destructive — not used by ``deploy_table``; exposed for explicit
        teardown (e.g. removing test tables).
        """
        metadata_id = self.get_entity_metadata(logical_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {logical_name} not found")
        url = self.get_api_url(f"EntityDefinitions({metadata_id})")
        response = self.session.delete(url)
        if not response.ok:
            self._raise_with_detail(response, f"delete entity '{logical_name}'")
        return {"status": "deleted", "logical_name": logical_name}

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

    # ----------------------------------------------------- per-type components
    # Endpoints for non-table component types, added per wave. Thin transport only;
    # payloads are built by the per-type serializers.

    # ---- global optionsets (Wave 2) ----
    def get_global_optionset_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the global optionset whose logical ``Name == name``, or ``None``.

        ``GlobalOptionSetDefinitions`` is a metadata collection that does NOT support
        ``$filter`` (405); address it by the ``Name`` alternate key instead. Dataverse
        stores the optionset Name lowercased, so the lookup must use the lowercased
        name regardless of the authored schema-name casing.
        """
        encoded = _odata_quote(name.lower())
        response = self.session.get(
            self.get_api_url(f"GlobalOptionSetDefinitions(Name='{encoded}')")
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def get_global_optionset_by_id(self, metadata_id: str) -> dict[str, Any]:
        """Get a global optionset keyed by MetadataId (used by reverse)."""
        response = self.session.get(self.get_api_url(f"GlobalOptionSetDefinitions({metadata_id})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_global_optionset(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized global-optionset payload to ``GlobalOptionSetDefinitions``."""
        response = self.session.post(self.get_api_url("GlobalOptionSetDefinitions"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create global optionset")
        return {"MetadataId": _entity_id(response), "Name": payload.get("Name")}

    # ---- web resources (Wave 2) ----
    def get_webresource_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the web resource whose ``name == name``, or ``None``."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(f"webresourceset?$filter=name eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_webresource_by_id(self, webresourceid: str) -> dict[str, Any]:
        """Get a web resource keyed by id (used by reverse)."""
        response = self.session.get(self.get_api_url(f"webresourceset({webresourceid})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_webresource(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized web-resource payload (``content`` is base64)."""
        response = self.session.post(self.get_api_url("webresourceset"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create webresource")
        return {"webresourceid": _entity_id(response), "name": payload.get("name")}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_webresource(self, webresourceid: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing web resource (e.g. replace ``content``)."""
        response = self.session.patch(
            self.get_api_url(f"webresourceset({webresourceid})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update webresource '{webresourceid}'")
        return {"updated": True, "webresourceid": webresourceid}

    # ---- forms / SystemForm (Wave 3) ----
    def get_form_by_name(self, entity: str, name: str) -> Optional[dict[str, Any]]:
        """Return the system form for ``entity`` named ``name``, or ``None``."""
        e = _odata_quote(entity)
        n = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(
                f"systemforms?$filter=objecttypecode eq '{e}' and name eq '{n}'&$top=1"
            )
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_form_by_id(self, form_id: str) -> dict[str, Any]:
        """Get a system form keyed by id (used by reverse)."""
        response = self.session.get(self.get_api_url(f"systemforms({form_id})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_form(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized SystemForm payload (``formxml`` is opaque)."""
        response = self.session.post(self.get_api_url("systemforms"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create form")
        return {"formid": _entity_id(response), "name": payload.get("name")}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_form(self, form_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing system form (e.g. replace ``formxml``)."""
        response = self.session.patch(self.get_api_url(f"systemforms({form_id})"), json=patch)
        if not response.ok:
            self._raise_with_detail(response, f"update form '{form_id}'")
        return {"updated": True, "formid": form_id}

    # ---- views / SavedQuery (Wave 3) ----
    def get_view_by_name(self, entity: str, name: str) -> Optional[dict[str, Any]]:
        """Return the saved query (view) for ``entity`` named ``name``, or ``None``."""
        e = _odata_quote(entity)
        n = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(
                f"savedqueries?$filter=returnedtypecode eq '{e}' and name eq '{n}'&$top=1"
            )
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_view_by_id(self, savedquery_id: str) -> dict[str, Any]:
        """Get a saved query keyed by id (used by reverse)."""
        response = self.session.get(self.get_api_url(f"savedqueries({savedquery_id})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_view(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized SavedQuery payload (``fetchxml``/``layoutxml`` opaque)."""
        response = self.session.post(self.get_api_url("savedqueries"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create view")
        return {"savedqueryid": _entity_id(response), "name": payload.get("name")}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_view(self, savedquery_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing saved query (e.g. replace ``fetchxml``/``layoutxml``)."""
        response = self.session.patch(
            self.get_api_url(f"savedqueries({savedquery_id})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update view '{savedquery_id}'")
        return {"updated": True, "savedqueryid": savedquery_id}

    # ---- plugins (Wave 4) ----
    def get_plugin_assemblies(self) -> list[dict[str, Any]]:
        """List all plugin assemblies."""
        response = self.session.get(self.get_api_url("pluginassemblies"))
        response.raise_for_status()
        return response.json().get("value", [])

    def get_plugin_assembly_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the plugin assembly whose ``name == name``, or ``None``."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(f"pluginassemblies?$filter=name eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_plugin_assembly_by_id(self, pluginassemblyid: str) -> dict[str, Any]:
        """Get a plugin assembly keyed by id (used by reverse)."""
        response = self.session.get(self.get_api_url(f"pluginassemblies({pluginassemblyid})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_plugin_assembly(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized plugin-assembly payload (``content`` is base64 DLL)."""
        response = self.session.post(self.get_api_url("pluginassemblies"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create plugin assembly")
        return {"pluginassemblyid": _entity_id(response), "name": payload.get("name")}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_plugin_assembly(self, pluginassemblyid: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing plugin assembly (e.g. replace base64 ``content``)."""
        response = self.session.patch(
            self.get_api_url(f"pluginassemblies({pluginassemblyid})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update plugin assembly '{pluginassemblyid}'")
        return {"updated": True, "pluginassemblyid": pluginassemblyid}

    def get_sdk_message_id(self, message_name: str) -> Optional[str]:
        """Resolve a global SDK message id by name (Create/Update/Delete/...)."""
        encoded = _odata_quote(message_name)
        response = self.session.get(
            self.get_api_url(f"sdkmessages?$filter=name eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0].get("sdkmessageid") if values else None

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_plugin_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized SDK message processing step."""
        response = self.session.post(self.get_api_url("sdkmessageprocessingsteps"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create plugin step")
        return {"sdkmessageprocessingstepid": _entity_id(response), "name": payload.get("name")}

    def get_steps_by_assembly(self, pluginassemblyid: str) -> list[dict[str, Any]]:
        """List the SDK message processing steps owned by an assembly."""
        response = self.session.get(
            self.get_api_url(
                f"sdkmessageprocessingsteps?$filter=_pluginassemblyid_value eq {pluginassemblyid}"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    # ----------------------------------------------------- solution / publisher
    # Thin transport methods over the Web API. Create payloads are built by
    # ``framework_power.components.serializer``; the client stays model-free.

    def get_publishers(self) -> list[dict[str, Any]]:
        """List all publishers."""
        response = self.session.get(self.get_api_url("publishers"))
        response.raise_for_status()
        return response.json().get("value", [])

    def get_publisher_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the publisher whose ``uniquename == name``, or ``None``."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(f"publishers?$filter=uniquename eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_publisher_by_id(self, publisher_id: str) -> dict[str, Any]:
        """Get a publisher keyed by its id (used by solution reverse)."""
        response = self.session.get(self.get_api_url(f"publishers({publisher_id})"))
        response.raise_for_status()
        return response.json()

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_publisher(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized publisher payload (``uniquename``/``friendlyname``/...)."""
        response = self.session.post(self.get_api_url("publishers"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create publisher")
        publisher_id = _entity_id(response)
        return {"publisherid": publisher_id, "uniquename": payload.get("uniquename")}

    def ensure_publisher_exists(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Idempotently ensure a publisher exists (looked up by ``uniquename``).

        ``payload`` is the serialized publisher (from ``serialize_publisher``).
        Returns ``{created, publisherid, uniquename}``.
        """
        name = payload.get("uniquename")
        if not name:
            raise ValueError("publisher payload missing 'uniquename'")
        existing = self.get_publisher_by_name(name)
        if existing:
            return {
                "created": False,
                "publisherid": existing.get("publisherid"),
                "uniquename": name,
                "publisher": existing,
            }
        created = self.create_publisher(payload)
        return {"created": True, **created}

    def get_solutions(self) -> list[dict[str, Any]]:
        """List all solutions."""
        response = self.session.get(self.get_api_url("solutions"))
        response.raise_for_status()
        return response.json().get("value", [])

    def get_solution_by_name(self, unique_name: str) -> Optional[dict[str, Any]]:
        """Return the solution whose ``uniquename == unique_name``, or ``None``."""
        encoded = _odata_quote(unique_name)
        response = self.session.get(
            self.get_api_url(f"solutions?$filter=uniquename eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_solution(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized solution payload (incl. ``publisherid@odata.bind``)."""
        response = self.session.post(self.get_api_url("solutions"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create solution")
        solution_id = _entity_id(response)
        return {"solutionid": solution_id, "uniquename": payload.get("uniquename")}

    def update_solution_version(self, unique_name: str, version: str) -> dict[str, Any]:
        """PATCH the version of an existing solution (looked up by unique name)."""
        sol = self.get_solution_by_name(unique_name)
        if not sol:
            raise ValueError(f"Solution not found: {unique_name}")
        solution_id = sol.get("solutionid")
        response = self.session.patch(
            self.get_api_url(f"solutions({solution_id})"), json={"version": version}
        )
        if not response.ok:
            self._raise_with_detail(response, f"update solution '{unique_name}' version")
        return {"updated": True, "uniquename": unique_name, "version": version}

    def get_solution_components(self, unique_name: str) -> list[dict[str, Any]]:
        """List a solution's components (``componenttype`` + ``objectid``).

        The collection-valued navigation properties (``solution_solutioncomponents`` /
        ``SolutionComponents``) are unavailable in some tenants (404/400), so query the
        ``solutioncomponents`` entity set filtered by the looked-up ``solutionid``.
        """
        sol = self.get_solution_by_name(unique_name)
        if not sol:
            return []
        solution_id = sol.get("solutionid")
        response = self.session.get(
            self.get_api_url(
                f"solutioncomponents?$filter=_solutionid_value eq {solution_id}"
                f"&$select=componenttype,objectid"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    @retry_on_metadata_error(max_retries=4, initial_delay=3.0)
    def add_solution_component(
        self,
        unique_name: str,
        component_type: int,
        object_id: str,
        add_required: bool = False,
    ) -> dict[str, Any]:
        """POST the ``AddSolutionComponent`` action (solutioncomponent has no Create)."""
        payload = {
            "SolutionUniqueName": unique_name,
            "ComponentType": component_type,
            "ComponentId": object_id,
            "AddRequiredComponents": bool(add_required),
            "DoNotIncludeSubcomponents": False,
        }
        response = self.session.post(self.get_api_url("AddSolutionComponent"), json=payload)
        if not response.ok:
            self._raise_with_detail(
                response,
                f"add component type={component_type} id={object_id} to '{unique_name}'",
            )
        return {
            "added": True,
            "solution": unique_name,
            "component_type": component_type,
            "object_id": object_id,
        }

    @retry_on_metadata_error(max_retries=4, initial_delay=3.0)
    def publish_all_xml(self) -> dict[str, Any]:
        """POST ``PublishAllXml`` — publishes ALL unmanaged customizations in the org."""
        response = self.session.post(self.get_api_url("PublishAllXml"))
        if not response.ok:
            self._raise_with_detail(response, "publish all customizations")
        return {"published": True, "scope": "organization"}

    # -------------------------------------------------------- roles / privileges
    # Security-role privilege management. Roles PRE-EXIST (never created here); we
    # only read a role and upsert its roleprivileges. The depth is the bitmask
    # ``privilegedepthmask`` on the ``roleprivilegescollection`` link (NOT ``depth``).

    def get_role_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the security role whose ``name == name``, or ``None``."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(f"roles?$filter=name eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_role_privileges(
        self, role_id: str, privilege_ids: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """List a role's roleprivileges, optionally scoped to a set of privilege ids.

        Scoping by ``privilegeid`` (server-side) is how reverse avoids pulling every
        table's privilege — pass the requested tables' privilege ids. Each record
        carries ``privilegedepthmask`` (the depth bitmask).
        """
        filt = f"roleid eq {role_id}"
        if privilege_ids:
            filt += " and (" + " or ".join(f"privilegeid eq {pid}" for pid in privilege_ids) + ")"
        response = self.session.get(
            self.get_api_url(
                f"roleprivilegescollection?$filter={filt}"
                f"&$select=roleprivilegeid,privilegeid,privilegedepthmask"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def get_privilege_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the privilege whose ``name == name`` (e.g. ``prvReadAccount``)."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(
                f"privileges?$filter=name eq '{encoded}'&$top=1"
                f"&$select=name,accessright,privilegeid"
            )
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def get_entity_schema_name(self, logical_name: str) -> str:
        """The entity SchemaName (privilege names use it: ``prvRead<SchemaName>``)."""
        meta = self.get_entity_metadata(logical_name)
        return meta.get("SchemaName") or logical_name

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_role_privilege(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a roleprivilege (``roleid@odata.bind`` + ``privilegeid@odata.bind`` +
        ``privilegedepthmask``)."""
        response = self.session.post(
            self.get_api_url("roleprivilegescollection"), json=payload
        )
        if not response.ok:
            self._raise_with_detail(response, "create role privilege")
        return {"roleprivilegeid": _entity_id(response)}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_role_privilege(
        self, roleprivilege_id: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """PATCH a roleprivilege (e.g. replace ``privilegedepthmask``)."""
        response = self.session.patch(
            self.get_api_url(f"roleprivilegescollection({roleprivilege_id})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update role privilege '{roleprivilege_id}'")
        return {"updated": True, "roleprivilegeid": roleprivilege_id}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def delete_role_privilege(self, roleprivilege_id: str) -> dict[str, Any]:
        """DELETE a roleprivilege (revokes that privilege from the role)."""
        response = self.session.delete(
            self.get_api_url(f"roleprivilegescollection({roleprivilege_id})")
        )
        if not response.ok:
            self._raise_with_detail(response, f"delete role privilege '{roleprivilege_id}'")
        return {"deleted": True, "roleprivilegeid": roleprivilege_id}

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
