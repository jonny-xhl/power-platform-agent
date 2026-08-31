"""
Slim Dataverse Web API client (self-contained copy for framework_power).

Only the transport + metadata endpoints needed by the table deployer are kept.
The create/update methods accept *already-serialized* Dataverse Web API JSON
(built by ``framework_power.serializer``); there is NO YAML conversion layer here.
"""

import base64
import copy
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .retry_helper import retry_on_metadata_error, retry_on_404

logger = logging.getLogger(__name__)


_ATTRIBUTE_ODATA_TYPES: dict[str, str] = {
    "String": "StringAttributeMetadata",
    "Memo": "MemoAttributeMetadata",
    "Integer": "IntegerAttributeMetadata",
    "BigInt": "BigIntAttributeMetadata",
    "Money": "MoneyAttributeMetadata",
    "Decimal": "DecimalAttributeMetadata",
    "Double": "DoubleAttributeMetadata",
    "Picklist": "PicklistAttributeMetadata",
    "Boolean": "BooleanAttributeMetadata",
    "DateTime": "DateTimeAttributeMetadata",
    "File": "FileAttributeMetadata",
    # Lookup-family attribute types share LookupAttributeMetadata
    "Lookup": "LookupAttributeMetadata",
    "Owner": "LookupAttributeMetadata",
    "Customer": "LookupAttributeMetadata",
    "PartyList": "LookupAttributeMetadata",
    "State": "StateAttributeMetadata",
    "Status": "StatusAttributeMetadata",
    "EntityName": "EntityNameAttributeMetadata",
    "Uniqueidentifier": "UniqueIdentifierAttributeMetadata",
    "Image": "ImageAttributeMetadata",
}

# Properties returned by the full metadata GET that Microsoft's update sample does
# not send back in the PUT definition.  These are response annotations, change
# tracking values, or server-maintained fields rather than part of the writable
# attribute definition.
_ATTRIBUTE_RESPONSE_ONLY_FIELDS = {
    "@odata.context",
    "HasChanged",
    "AttributeOf",
    "DeprecatedVersion",
    "IsValidODataAttribute",
    "LinkedAttributeId",
    "ExternalName",
    "InheritsFrom",
    "CreatedOn",
    "ModifiedOn",
    "MinSupportedValue",
    "MaxSupportedValue",
    "MinSupportedPrecision",
    "MaxSupportedPrecision",
}


def _odata_quote(value: str) -> str:
    """URL-encode a string for safe use inside an OData quoted literal."""
    from urllib.parse import quote

    return quote(value, safe="")


# Properties returned by the full EntityDefinitions GET that must not be sent back
# in an update PUT: OData annotations, server-maintained GUIDs/names, capability
# flags, and system-managed booleans.  Only writable entity properties remain.
_ENTITY_RESPONSE_ONLY_FIELDS = {
    "@odata.context",
    "MetadataId",
    "EntitySetName",
    "LogicalName",
    "PrimaryIdAttribute",
    "PrimaryNameAttribute",
    "ActivityTypeMask",
    "ObjectTypeCode",
    "OwnershipType",
    "IsIntersect",
    "IsPrivate",
    "IsManaged",
    "IsActivity",
    "IsCustomEntity",
    "IsBusinessProcessEnabled",
    "IsBPFEntity",
    "IsDocumentManagementEnabled",
    "IsDocumentRecommendationsEnabled",
    "IsKnowledgeManagementEnabled",
    "IsDataEncryptionEnabled",
    "IsAirplaneModeEnabled",
    "IsOneNoteIntegrationEnabled",
    "IsEnabledForCharts",
    "IsEnabledForExternalChannels",
    "IsEnabledForTrace",
    "IsExportToExcelEnabled",
    "IsImportable",
    "IsOptimisticConcurrencyEnabled",
    "IsOfflineInMobileClient",
    "IsReadyForDataMigration",
    "IsSecurityDisabled",
    "IsSLAEnabled",
    "IsSharedActivities",
    "IsStateControl",
    "IsVisibleInMobile",
    "IsVisibleInMobileClient",
    "CanEnableAttributes",
    "CanChangeHierarchicalRelationship",
    "CanChangeTrackingBeEnabled",
    "CanModifyAdditionalSettings",
    "CanTriggerWorkflow",
    "WorksWithDataLake",
    "CreatedOn",
    "ModifiedOn",
    "IntroducedVersion",
    "SolutionId",
    "SolutionIdUnique",
    "BaseSolutionId",
    "IsRenameable",
    "IsValidForAdvancedFind",
    "IsQuickCreateEnabled",
    "IsReadingPaneEnabled",
    "IsMappable",
    "IsDuplicateDetectionEnabled",
    "IsMailMergeEnabled",
    "IsAutoRouteEnabled",
    "IsExternalActivity",
    "IsInteractionCentric",
    "IsExternalActivity",
    "IsEnabledForCharts",
    "HasActivities",
    "HasNotes",
    "IsCustomizable",
}


def _clean_entity_update_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize retrieved entity metadata into a safe full ``PUT`` body.

    The Web API in some tenants rejects PATCH on ``EntityDefinitions`` (405 /
    0x80060888 "Operation not supported on EntityMetadata").  Microsoft's documented
    update path is a full definition PUT, mirroring the attribute contract: GET the
    typed current metadata, overlay the desired writable properties, drop response-only
    / capability fields, and PUT back by MetadataId.
    """

    def clean(value: Any, *, top_level: bool = False) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, nested in value.items():
                if key in {"@odata.context", "@odata.etag", "HasChanged"}:
                    continue
                if top_level and key in _ENTITY_RESPONSE_ONLY_FIELDS:
                    continue
                if nested is None:
                    continue
                cleaned = clean(nested)
                if key == "@odata.type" and isinstance(cleaned, str):
                    cleaned = cleaned.lstrip("#")
                result[key] = cleaned
            return result
        if isinstance(value, list):
            return [clean(item) for item in value if item is not None]
        return value

    return clean(copy.deepcopy(metadata), top_level=True)


def _entity_id(response: requests.Response) -> Optional[str]:
    """Parse the GUID out of an ``OData-EntityId`` create-response header."""
    entity_id = response.headers.get("OData-EntityId", "")
    if entity_id:
        return entity_id.split("(")[-1].rstrip(")")
    return None


def _clean_attribute_update_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    """Normalize retrieved attribute metadata into a safe full ``PUT`` body.

    Microsoft requires the complete concrete attribute definition for updates, but
    the GET response also contains OData annotations and server-maintained values.
    Remove only those response-only values, retain type-specific settings, and drop
    nulls that cannot contribute to the replacement definition.
    """

    def clean(value: Any, *, top_level: bool = False) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, nested in value.items():
                if key in {"@odata.context", "@odata.etag", "HasChanged"}:
                    continue
                if top_level and key in _ATTRIBUTE_RESPONSE_ONLY_FIELDS:
                    continue
                if nested is None:
                    continue
                cleaned = clean(nested)
                if key == "@odata.type" and isinstance(cleaned, str):
                    cleaned = cleaned.lstrip("#")
                result[key] = cleaned
            return result
        if isinstance(value, list):
            return [clean(item) for item in value if item is not None]
        return value

    return clean(copy.deepcopy(metadata), top_level=True)


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

    def list_entities(
        self, prefix: Optional[str] = None, include_system: bool = False
    ) -> list[dict[str, Any]]:
        """List all entities in the environment, optionally filtered by prefix.

        Args:
            prefix: Filter to logical names starting with this prefix (e.g. ``new_``).
                Filtering is done client-side (Dataverse ``startswith`` is not universally
                supported on EntityDefinitions).
            include_system: If False, only return custom entities (IsCustomEntity=true).
        """
        filter_clause = ""
        if not include_system:
            filter_clause = "?$filter=IsCustomEntity eq true"

        url = self.get_api_url(f"EntityDefinitions{filter_clause}")
        url += "&$select=LogicalName,SchemaName,DisplayName,IsCustomEntity,IsManaged,"
        url += "Description,OwnershipType,PrimaryNameAttribute"

        entities: list[dict[str, Any]] = []
        while url:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            batch = data.get("value", [])
            if prefix:
                batch = [e for e in batch if (e.get("LogicalName") or "").startswith(prefix)]
            entities.extend(batch)
            url = data.get("@odata.nextLink", "")
        return entities

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

    def get_attribute_metadata(
        self,
        entity_name: str,
        attr_logical_name: str,
        *,
        attribute_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Retrieve the complete concrete metadata definition for one attribute.

        Dataverse metadata is polymorphic.  Existing-column updates require a full
        type-specific definition followed by ``PUT``; the base ``Attributes`` item
        does not expose every derived property.  ``attribute_type`` may be either an
        ``AttributeType`` value (for example ``"Decimal"``) or an OData type name.
        When omitted, a base read is performed first to discover the concrete type.
        """
        base_path = (
            f"EntityDefinitions(LogicalName='{entity_name}')"
            f"/Attributes(LogicalName='{attr_logical_name}')"
        )
        discovered: dict[str, Any] | None = None
        type_name = attribute_type or ""
        if not type_name:
            response = self.session.get(
                self.get_api_url(base_path),
                headers={"Consistency": "Strong"},
            )
            response.raise_for_status()
            discovered = response.json()
            type_name = discovered.get("@odata.type") or discovered.get("AttributeType") or ""

        short_type = str(type_name).split(".")[-1].lstrip("#")
        if not short_type.endswith("AttributeMetadata"):
            short_type = _ATTRIBUTE_ODATA_TYPES.get(short_type, "")
        if not short_type:
            raise ValueError(
                f"Unsupported or unknown attribute type for "
                f"'{entity_name}.{attr_logical_name}': {type_name!r}"
            )

        url = self.get_api_url(
            f"{base_path}/Microsoft.Dynamics.CRM.{short_type}"
        )
        if short_type in {"PicklistAttributeMetadata", "BooleanAttributeMetadata"}:
            url += "?$expand=OptionSet"
        response = self.session.get(url, headers={"Consistency": "Strong"})
        response.raise_for_status()
        return response.json()

    def get_optionset_attributes(self, entity_name: str) -> dict[str, dict[str, Any]]:
        """Fetch OptionSet data for all Picklist and Boolean attributes.

        The polymorphic ``/Attributes`` endpoint does NOT include the ``OptionSet``
        navigation property. We query the typed derived-type collections with
        ``$expand=OptionSet`` to get the full option data in two batched calls.

        Returns:
            Dict keyed by attribute logical name -> ``{"OptionSet": {...}}``
            (Picklist) or ``{"OptionSet": {...}}`` (Boolean with True/False options).
        """
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")

        result: dict[str, dict[str, Any]] = {}
        for derived_type, odata_type in (
            ("PicklistAttributeMetadata", "#Microsoft.Dynamics.CRM.PicklistAttributeMetadata"),
            ("BooleanAttributeMetadata", "#Microsoft.Dynamics.CRM.BooleanAttributeMetadata"),
        ):
            url = self.get_api_url(
                f"EntityDefinitions({metadata_id})"
                f"/Attributes/Microsoft.Dynamics.CRM.{derived_type}"
            )
            url += "?$expand=OptionSet&$select=LogicalName,OptionSet"
            try:
                response = self.session.get(url)
                response.raise_for_status()
                for attr in response.json().get("value", []):
                    logical = attr.get("LogicalName")
                    if logical and attr.get("OptionSet"):
                        result[logical] = {"OptionSet": attr["OptionSet"]}
            except Exception:
                # Non-fatal: if typed query fails, attributes just lack OptionSet data
                pass
        return result

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

    def get_entity_keys(self, entity_name: str) -> list[dict[str, Any]]:
        """List alternate keys for ``entity_name``."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")
        response = self.session.get(self.get_api_url(f"EntityDefinitions({metadata_id})/Keys"))
        response.raise_for_status()
        return response.json().get("value", [])

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
        """PATCH updatable entity properties (keyed by MetadataId; LogicalName PATCH is 405).

        Some tenants reject ``PATCH EntityDefinitions`` outright (405 / 0x80060888
        "Operation not supported on EntityMetadata").  When that happens the method
        transparently falls back to the documented full-definition PUT contract:
        GET typed current metadata -> overlay ``patch`` -> clean response-only fields
        -> PUT by MetadataId.
        """
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")
        url = self.get_api_url(f"EntityDefinitions({metadata_id})")
        response = self.session.patch(url, json=patch)
        if response.ok:
            return {"status": "updated", "method": "patch"}

        message = response.text.lower()
        if response.status_code == 405 or "0x80060888" in message or "operation not supported on entitymetadata" in message:
            full = self.get_entity_metadata_by_id(metadata_id)
            full.update(copy.deepcopy(patch))
            put_response = self.session.put(
                url,
                json=_clean_entity_update_payload(full),
                headers={"Content-Type": "application/json"},
            )
            if not put_response.ok:
                self._raise_with_detail(put_response, f"update entity '{entity_name}' (PUT fallback)")
            return {"status": "updated", "method": "put"}
        self._raise_with_detail(response, f"update entity '{entity_name}'")
        return {"status": "updated", "method": "patch"}

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
            return {"status": "created"}
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
        changes: dict[str, Any],
        *,
        attribute_type: Optional[str] = None,
        solution: Optional[str] = None,
    ) -> dict[str, Any]:
        """Safely update an existing attribute with a full-definition ``PUT``.

        Dataverse does not support ``PATCH`` on the attribute metadata navigation
        endpoint.  Its documented contract is retrieve-modify-``PUT``: fetch the
        complete concrete metadata type, remove response-only properties, overlay
        the intended mutable changes, and send the full definition to the uncast
        logical-name URL.
        """
        current = self.get_attribute_metadata(
            entity_name,
            attr_logical_name,
            attribute_type=attribute_type,
        )
        payload = _clean_attribute_update_payload(current)
        type_name = attribute_type or current.get("@odata.type") or current.get("AttributeType")
        short_type = str(type_name or "").split(".")[-1].lstrip("#")
        if not short_type.endswith("AttributeMetadata"):
            short_type = _ATTRIBUTE_ODATA_TYPES.get(short_type, "")
        if not short_type:
            raise ValueError(
                f"Unsupported or unknown attribute type for "
                f"'{entity_name}.{attr_logical_name}': {type_name!r}"
            )
        # Typed GET responses don't consistently echo @odata.type.  The uncast PUT
        # endpoint needs the discriminator or it validates derived properties (such
        # as Decimal MaxValue) against the base AttributeMetadata type.
        payload["@odata.type"] = f"Microsoft.Dynamics.CRM.{short_type}"
        payload.update(copy.deepcopy(changes))

        url = self.get_api_url(
            f"EntityDefinitions(LogicalName='{entity_name}')"
            f"/Attributes(LogicalName='{attr_logical_name}')"
        )
        headers = {"MSCRM.MergeLabels": "true"}
        if solution:
            headers["MSCRM.SolutionUniqueName"] = solution
        response = self.session.put(url, json=payload, headers=headers)
        if not response.ok:
            self._raise_with_detail(
                response, f"update attribute '{attr_logical_name}' on '{entity_name}'"
            )
        return {
            "status": "updated",
            "method": "PUT",
            "fields": list(changes.keys()),
        }

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
    def insert_option_value(
        self,
        entity_name: str,
        attr_logical_name: str,
        value: int,
        label: dict[str, Any],
        *,
        solution: Optional[str] = None,
    ) -> dict[str, Any]:
        """Insert one value into an existing local Picklist.

        ``InsertOptionValue`` is the supported Dataverse action for changing an
        existing OptionSet. ``SolutionUniqueName`` belongs in the action body rather
        than the metadata-update header used by attribute ``PUT``.
        """
        payload: dict[str, Any] = {
            "EntityLogicalName": entity_name,
            "AttributeLogicalName": attr_logical_name,
            "Value": int(value),
            "Label": copy.deepcopy(label),
        }
        if solution:
            payload["SolutionUniqueName"] = solution
        response = self.session.post(self.get_api_url("InsertOptionValue"), json=payload)
        if not response.ok:
            self._raise_with_detail(
                response,
                f"insert option {value} into '{entity_name}.{attr_logical_name}'",
            )
        data = response.json() if response.text else {}
        return {
            "status": "inserted",
            "value": data.get("NewOptionValue", value),
        }

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
    def update_option_value(
        self,
        entity_name: str,
        attr_logical_name: str,
        value: int,
        label: dict[str, Any],
        *,
        solution: Optional[str] = None,
    ) -> dict[str, Any]:
        """Merge authored language labels for one existing local-Picklist value."""
        payload: dict[str, Any] = {
            "EntityLogicalName": entity_name,
            "AttributeLogicalName": attr_logical_name,
            "Value": int(value),
            "Label": copy.deepcopy(label),
            "MergeLabels": True,
        }
        if solution:
            payload["SolutionUniqueName"] = solution
        response = self.session.post(self.get_api_url("UpdateOptionValue"), json=payload)
        if not response.ok:
            self._raise_with_detail(
                response,
                f"update option {value} on '{entity_name}.{attr_logical_name}'",
            )
        return {"status": "updated", "value": value}

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

    def create_entity_key(
        self,
        entity_name: str,
        key_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Create an alternate key on an existing entity."""
        metadata_id = self.get_entity_metadata(entity_name).get("MetadataId")
        if not metadata_id:
            raise ValueError(f"Entity {entity_name} not found")
        url = self.get_api_url(f"EntityDefinitions({metadata_id})/Keys")
        response = self.session.post(url, json=key_metadata)
        if not response.ok:
            self._raise_with_detail(response, f"create alternate key on '{entity_name}'")
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

    def list_global_optionsets(self, prefix: Optional[str] = None) -> list[dict[str, Any]]:
        """List all global optionsets, optionally filtered by name prefix.

        ``GlobalOptionSetDefinitions`` is a metadata collection that does NOT support
        ``$filter`` (405), so publisher-prefix filtering is done client-side after
        pagination (mirrors :meth:`list_entities`). ``Options`` (value/label/color)
        are included in each item so callers can render docs without a second fetch.

        Args:
            prefix: If given, keep only optionsets whose ``Name`` starts with this
                string (case-insensitive). Pass the full prefix including the trailing
                underscore, e.g. ``"new_"``.
        """
        url = self.get_api_url("GlobalOptionSetDefinitions")
        items: list[dict[str, Any]] = []
        while url:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            batch = data.get("value", [])
            if prefix:
                pfx = prefix.lower()
                batch = [o for o in batch if (o.get("Name") or "").lower().startswith(pfx)]
            items.extend(batch)
            url = data.get("@odata.nextLink", "")
        return items

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

    def list_webresources_by_prefix(
        self,
        name_prefix: str,
        *,
        select: str = "name,webresourceid,webresourcetype,content",
    ) -> list[dict[str, Any]]:
        """List web resources whose ``name`` starts with ``name_prefix``.

        Used by the scoped reverse flow (defaults to the publisher prefix, e.g.
        ``new_/``). ``content`` is included via explicit ``$select`` (it is not returned
        for collection queries unless selected).
        """
        encoded = _odata_quote(name_prefix)
        response = self.session.get(
            self.get_api_url(
                f"webresourceset?$filter=startswith(name,'{encoded}')&$select={select}"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def delete_webresource(self, webresourceid: str) -> dict[str, Any]:
        """DELETE a web resource by id (teardown; not used by ``sync``)."""
        url = self.get_api_url(f"webresourceset({webresourceid})")
        response = self.session.delete(url)
        if not response.ok:
            self._raise_with_detail(response, f"delete webresource '{webresourceid}'")
        return {"status": "deleted", "webresourceid": webresourceid}

    # ---- forms / SystemForm (Wave 3) ----
    def get_form_by_name(
        self, entity: str, name: str, *, form_type: Optional[int] = None
    ) -> Optional[dict[str, Any]]:
        """Return the system form for ``entity`` named ``name``, or ``None``.

        When ``form_type`` is given, also filter by ``type`` — needed because Dataverse
        auto-creates several forms all named "Information" (Main/QuickView/Card), so a
        name-only lookup is ambiguous and may target the wrong one.
        """
        e = _odata_quote(entity)
        n = _odata_quote(name)
        flt = f"objecttypecode eq '{e}' and name eq '{n}'"
        if form_type is not None:
            flt += f" and type eq {int(form_type)}"
        response = self.session.get(
            self.get_api_url(f"systemforms?$filter={flt}&$top=1")
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

    def list_forms_by_entity(
        self,
        entity: str,
        *,
        select: str = "formid,name,type,objecttypecode,formxml,description,iscustomizable",
    ) -> list[dict[str, Any]]:
        """List all system forms for ``entity``.

        ``formxml`` is returned ONLY because it is in the explicit ``$select`` (collection
        queries do not return it by default — verified live). Used by form reverse.
        """
        e = _odata_quote(entity)
        response = self.session.get(
            self.get_api_url(
                f"systemforms?$filter=objecttypecode eq '{e}'&$select={select}"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    # ---- views / SavedQuery (Wave 3) ----
    def get_view_by_name(
        self, entity: str, name: str, *, query_type: Optional[int] = None
    ) -> Optional[dict[str, Any]]:
        """Return the saved query (view) for ``entity`` named ``name``, or ``None``.

        When ``query_type`` is given, also filter by ``querytype`` — needed because the auto-created
        views share generic names and ``querytype`` is the disambiguator (mirrors form ``form_type``).
        """
        e = _odata_quote(entity)
        n = _odata_quote(name)
        flt = f"returnedtypecode eq '{e}' and name eq '{n}'"
        if query_type is not None:
            flt += f" and querytype eq {int(query_type)}"
        response = self.session.get(self.get_api_url(f"savedqueries?$filter={flt}&$top=1"))
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    def list_views_by_entity(
        self,
        entity: str,
        *,
        select: str = "savedqueryid,name,querytype,returnedtypecode,fetchxml,layoutxml,description,"
        "isdefault,iscustomizable,statecode",
    ) -> list[dict[str, Any]]:
        """List all saved queries (views) for ``entity``.

        ``fetchxml``/``layoutxml`` are returned only because they are in the explicit ``$select``
        (collection queries don't return them by default — verified live). Used by view reverse.
        """
        e = _odata_quote(entity)
        response = self.session.get(
            self.get_api_url(f"savedqueries?$filter=returnedtypecode eq '{e}'&$select={select}")
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def get_object_type_code(self, entity: str) -> int:
        """Return the integer ObjectTypeCode for ``entity`` — needed for LayoutXml ``<grid object=>``."""
        meta = self.get_entity_metadata(entity)
        try:
            return int(meta.get("ObjectTypeCode"))
        except (TypeError, ValueError):
            return 0

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

    def get_plugintypes_by_assembly(self, pluginassemblyid: str) -> list[dict[str, Any]]:
        """List the PluginType records (one per IPlugin class) owned by an assembly.

        A ``sdkmessageprocessingstep`` references a PluginType (via ``eventhandler``), NOT the assembly —
        so step registration needs the plugintype id resolved from the assembly.
        """
        response = self.session.get(
            self.get_api_url(
                f"plugintypes?$filter=_pluginassemblyid_value eq {pluginassemblyid}"
                "&$select=plugintypeid,name,typename,assemblyname&$top=100"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_plugintype(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a ``plugintypes`` record for a type the assembly content update did NOT auto-register.

        Pinned live: replacing ``pluginassembly.content`` swaps the DLL bytes but does NOT re-enumerate
        plugintypes (a stale list silently misses newly added IPlugin classes). Creating the record
        manually registers the type so steps can bind to it.
        """
        response = self.session.post(self.get_api_url("plugintypes"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create plugintype")
        return {"plugintypeid": _entity_id(response), "typename": payload.get("typename")}

    def get_sdk_message_filter(self, sdkmessageid: str, entity: str) -> Optional[str]:
        """Resolve the sdkmessagefilter that scopes a message to an entity (e.g. Update+account)."""
        response = self.session.get(
            self.get_api_url(
                f"sdkmessagefilters?$filter=_sdkmessageid_value eq {sdkmessageid} "
                f"and primaryobjecttypecode eq '{_odata_quote(entity)}'&$top=1"
            )
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0].get("sdkmessagefilterid") if values else None

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_sdk_message_filter(self, sdkmessageid: str, entity: str) -> str:
        """Create an sdkmessagefilter scoping a message to an entity (for custom entities that lack one)."""
        payload = {
            "sdkmessageid@odata.bind": f"/sdkmessages({sdkmessageid})",
            "primaryobjecttypecode": entity,
        }
        response = self.session.post(self.get_api_url("sdkmessagefilters"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, f"create sdkmessagefilter ({sdkmessageid}, {entity})")
        return _entity_id(response) or ""

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_plugin_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a serialized SDK message processing step."""
        response = self.session.post(self.get_api_url("sdkmessageprocessingsteps"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create plugin step")
        return {"sdkmessageprocessingstepid": _entity_id(response), "name": payload.get("name")}

    def get_steps_by_assembly(self, pluginassemblyid: str) -> list[dict[str, Any]]:
        """List the SDK message processing steps owned by an assembly.

        A step references a PluginType (via ``eventhandler``), not the assembly directly (sdkmessageprocessingstep
        has no ``_pluginassemblyid_value``), so resolve the assembly's plugintypes first, then the steps whose
        ``eventhandler`` is one of them.
        """
        ptids = [p.get("plugintypeid") for p in self.get_plugintypes_by_assembly(pluginassemblyid)
                 if p.get("plugintypeid")]
        if not ptids:
            return []
        filt = " or ".join(f"_eventhandler_value eq {pid}" for pid in ptids)
        response = self.session.get(
            self.get_api_url(f"sdkmessageprocessingsteps?$filter={filt}")
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def list_sdk_messages(self, *, filter_name: Optional[str] = None) -> list[dict[str, Any]]:
        """List SDK messages (optionally filtered by name). Custom-action messages are auto-created
        alongside their workflow (category=3)."""
        q = "sdkmessages?$select=name,sdkmessageid&$top=1000"
        if filter_name:
            q = f"sdkmessages?$filter=name eq '{_odata_quote(filter_name)}'&$select=name,sdkmessageid&$top=1"
        response = self.session.get(self.get_api_url(q))
        response.raise_for_status()
        return response.json().get("value", [])

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_plugin_step(self, step_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing SDK message processing step."""
        response = self.session.patch(
            self.get_api_url(f"sdkmessageprocessingsteps({step_id})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update plugin step '{step_id}'")
        return {"updated": True, "sdkmessageprocessingstepid": step_id}

    def delete_plugin_step(self, step_id: str) -> dict[str, Any]:
        """DELETE a SDK message processing step (teardown; not used by deploy)."""
        response = self.session.delete(self.get_api_url(f"sdkmessageprocessingsteps({step_id})"))
        if not response.ok:
            self._raise_with_detail(response, f"delete plugin step '{step_id}'")
        return {"deleted": True, "sdkmessageprocessingstepid": step_id}

    def get_step_images(self, step_id: str) -> list[dict[str, Any]]:
        """List the Pre/Post images registered on an SDK message processing step.

        Images are addressed by ``_sdkmessageprocessingstepid_value`` (the collection has no
        direct navigation from the step usable with $expand here); filter by id instead.
        """
        response = self.session.get(
            self.get_api_url(
                f"sdkmessageprocessingstepimages?$filter=_sdkmessageprocessingstepid_value eq {step_id}"
                "&$select=sdkmessageprocessingstepimageid,name,entityalias,imagetype,attributes"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def get_step_images_bulk(self, step_ids: list[str]) -> list[dict[str, Any]]:
        """List images for MANY steps in one query (OR-filter on the step lookup).

        Caller chunks the id list (keep ≤ ~15 per request — long OR filters hit URL
        length limits). Each returned row carries ``_sdkmessageprocessingstepid_value``
        so the caller can group by step. Snapshot/backup code MUST prefer this over
        one ``get_step_images`` call per step (~100 custom steps → 8 requests vs 100).
        """
        if not step_ids:
            return []
        or_clause = " or ".join(
            f"_sdkmessageprocessingstepid_value eq {sid}" for sid in step_ids)
        response = self.session.get(
            self.get_api_url(
                f"sdkmessageprocessingstepimages?$filter={or_clause}"
                "&$select=sdkmessageprocessingstepimageid,name,entityalias,imagetype,"
                "attributes,_sdkmessageprocessingstepid_value"
            )
        )
        response.raise_for_status()
        return response.json().get("value", [])

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_step_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a ``sdkmessageprocessingstepimage`` (Pre/Post entity image bound to a step).

        ``imagetype``: 0=PreImage, 1=PostImage (pinned live). ``messagepropertyname`` is
        message-dependent: Create→``Id``, Update/Delete/others→``Target`` (0x8004416b rejects
        Target on Create). ``attributes`` is the comma-separated attribute list (the live field
        name — NOT the SDK-doc ``attributes1``); omit it to snapshot ALL attributes.
        """
        response = self.session.post(self.get_api_url("sdkmessageprocessingstepimages"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create step image")
        return {"sdkmessageprocessingstepimageid": _entity_id(response),
                "entityalias": payload.get("entityalias")}

    # ---- plugin packages (Phase 8; NuGet path) ----

    def list_plugin_packages(self) -> list[dict[str, Any]]:
        """List all plugin packages (NuGet)."""
        response = self.session.get(self.get_api_url("pluginpackages?$select=name,version&$top=100"))
        response.raise_for_status()
        return response.json().get("value", [])

    def get_plugin_package_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return the plugin package whose ``name == name``, or ``None``."""
        encoded = _odata_quote(name)
        response = self.session.get(
            self.get_api_url(f"pluginpackages?$filter=name eq '{encoded}'&$top=1")
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        return values[0] if values else None

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_plugin_package(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a plugin package (NuGet ``.nupkg``); ``content`` is base64. Dataverse discovers the IPlugin
        types in the package and auto-creates the ``pluginassembly``."""
        response = self.session.post(self.get_api_url("pluginpackages"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create plugin package")
        return {"pluginpackageid": _entity_id(response), "name": payload.get("name")}

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def update_plugin_package(self, pluginpackageid: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH an existing plugin package (e.g. replace base64 ``content`` / version)."""
        response = self.session.patch(
            self.get_api_url(f"pluginpackages({pluginpackageid})"), json=patch
        )
        if not response.ok:
            self._raise_with_detail(response, f"update plugin package '{pluginpackageid}'")
        return {"updated": True, "pluginpackageid": pluginpackageid}

    # ---- custom actions (Phase 8; best-effort) ----

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def create_custom_action(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Best-effort: POST a ``workflows`` record with ``category=3`` (Action) to create a custom-action
        definition. A functional/invokable Action typically also needs a definition (clientdata/XAML) +
        activation, which the Web API alone may not provision reliably — callers should treat this as
        best-effort and fall back to the manual flag (maker portal) on failure."""
        response = self.session.post(self.get_api_url("workflows"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "create custom action (workflow)")
        return {"workflowid": _entity_id(response), "uniquename": payload.get("uniquename")}

    def get_workflow_by_uniquename(self, uniquename: str) -> Optional[dict[str, Any]]:
        """Find a workflow record by ``uniquename`` (the workflow identity of a custom action).

        Note: ``$select=xaml`` on the collection is silently dropped by this env (returns rows with
        no xaml); fetch the single entity for XAML instead.
        """
        encoded = _odata_quote(uniquename)
        response = self.session.get(
            self.get_api_url(
                f"workflows?$filter=uniquename eq '{encoded}'"
                "&$select=workflowid,name,uniquename,statecode,statuscode,category,type&$top=5"
            )
        )
        response.raise_for_status()
        values = response.json().get("value", [])
        if not values:
            return None
        # An activated action can expose both the definition (type=1) and its activation copy
        # (type=2) under one uniquename — prefer the definition record.
        return next((v for v in values if v.get("type") == 1), values[0])

    def get_workflow_xaml(self, workflowid: str) -> Optional[str]:
        """Fetch a workflow's XAML via single-entity GET.

        Pinned live: the XAML lives in the ``xaml`` field (classic workflow definitions) — NOT
        ``clientdata`` (modern-flow field, always null here). Collection queries with
        ``$select=xaml`` silently drop it; the single-entity GET returns it.
        """
        response = self.session.get(self.get_api_url(f"workflows({workflowid})?$select=xaml"))
        response.raise_for_status()
        return response.json().get("xaml")

    @retry_on_metadata_error(max_retries=3, initial_delay=2.0)
    def activate_workflow(self, workflowid: str) -> dict[str, Any]:
        """Activate a workflow (draft→activated) — required for custom actions: activation provisions
        the ``type=2`` activation copy and the SDK message, without which the action is not callable."""
        payload = {"statecode": 1, "statuscode": 2}
        response = self.session.patch(self.get_api_url(f"workflows({workflowid})"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, f"activate workflow '{workflowid}'")
        return {"activated": True, "workflowid": workflowid}

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

    def delete_solution(self, unique_name: str) -> dict[str, Any]:
        """DELETE an unmanaged solution by unique name.

        Removes the solution container and its ``solutioncomponents`` associations;
        the components themselves (tables, roles, ...) remain in the default
        unmanaged layer (an unmanaged delete is a container-only teardown — it does
        NOT delete the components). Destructive — not used by ``deploy_solution``;
        exposed for explicit teardown (e.g. removing test solutions). Raises if the
        solution is not found (caller verifies existence first, as for ``delete_entity``).
        """
        sol = self.get_solution_by_name(unique_name)
        if not sol:
            raise ValueError(f"Solution not found: {unique_name}")
        solution_id = sol.get("solutionid")
        response = self.session.delete(self.get_api_url(f"solutions({solution_id})"))
        if not response.ok:
            self._raise_with_detail(response, f"delete solution '{unique_name}'")
        return {"status": "deleted", "uniquename": unique_name}

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
        do_not_include_subcomponents: bool = False,
    ) -> dict[str, Any]:
        """POST the ``AddSolutionComponent`` action (solutioncomponent has no Create).

        ``do_not_include_subcomponents=True`` adds the component SHELL only (e.g. an entity without its
        forms/views/attributes) — required so Ribbon Workbench will load a ribbon-only solution (it refuses
        solutions whose entities drag in all sub-components, for performance) and keeps the dedicated ribbon
        solution tiny/fast to export+import.
        """
        payload = {
            "SolutionUniqueName": unique_name,
            "ComponentType": component_type,
            "ComponentId": object_id,
            "AddRequiredComponents": bool(add_required),
            "DoNotIncludeSubcomponents": bool(do_not_include_subcomponents),
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
    def remove_solution_component(
        self,
        unique_name: str,
        component_type: int,
        object_id: str,
    ) -> dict[str, Any]:
        """POST the ``RemoveSolutionComponent`` action — remove a component from the solution
        CONTAINER only.

        Non-destructive: the component itself stays in the environment's default unmanaged layer.
        This is the correct way to prune solution membership (e.g. drop OOB sub-components dragged
        in by an entity add). Do NOT ``DELETE solutioncomponents(...)`` rows directly — that 400s;
        the bound action is the only supported path.

        Verified-live parameter form: ``RemoveSolutionComponent`` takes ``SolutionUniqueName``,
        ``ComponentType`` (int), and ``SolutionComponent`` — a nested ``mscrm.solutioncomponent``
        object. Action payloads reject ``@odata.bind`` and require the entity key, so the nested
        object is ``{@odata.type, solutioncomponentid: <COMPONENT objectid>}`` (the component's own
        object id, NOT the membership record's id — the action locates the membership by it).
        """
        sol = self.get_solution_by_name(unique_name)
        if not sol:
            raise ValueError(f"Solution not found: {unique_name}")
        sid = sol.get("solutionid")
        rows = self.session.get(
            self.get_api_url("solutioncomponents"),
            params={
                "$filter": f"_solutionid_value eq {sid} and objectid eq {object_id} "
                f"and componenttype eq {component_type}",
                "$select": "solutioncomponentid",
            },
        ).json().get("value", [])
        if not rows:
            return {
                "removed": False,
                "solution": unique_name,
                "object_id": object_id,
                "note": "not a member of this solution",
            }
        scid = rows[0].get("solutioncomponentid")
        payload = {
            # RemoveSolutionComponent's SolutionComponent param is a mscrm.solutioncomponent
            # entity reference (NOT a guid). Action parameter payloads reject @odata.bind
            # annotations, so pass it as a nested object. Dataverse locates the membership by
            # (solution, ComponentType, objectid) — verified live.
            "SolutionComponent": {
                "@odata.type": "#Microsoft.Dynamics.CRM.solutioncomponent",
                "solutioncomponentid": object_id,
            },
            "ComponentType": component_type,
            "SolutionUniqueName": unique_name,
        }
        response = self.session.post(self.get_api_url("RemoveSolutionComponent"), json=payload)
        if not response.ok:
            self._raise_with_detail(
                response,
                f"remove component type={component_type} id={object_id} from '{unique_name}'",
            )
        return {
            "removed": True,
            "solution": unique_name,
            "component_type": component_type,
            "object_id": object_id,
            "solutioncomponentid": scid,
        }

    @retry_on_metadata_error(max_retries=4, initial_delay=3.0)
    def publish_all_xml(self) -> dict[str, Any]:
        """POST ``PublishAllXml`` — publishes ALL unmanaged customizations in the org."""
        response = self.session.post(self.get_api_url("PublishAllXml"))
        if not response.ok:
            self._raise_with_detail(response, "publish all customizations")
        return {"published": True, "scope": "organization"}

    def publish_webresources(self, webresource_ids: list[str]) -> dict[str, Any]:
        """POST ``PublishXml`` — targeted publish of the given web resources only.

        Unlike ``publish_all_xml`` (org-wide), this publishes just the listed web
        resources (and refreshes the form/ribbon bindings that reference them), which is
        what makes frequent JS edits cheap. Empty input is a no-op.
        """
        ids = [i for i in (webresource_ids or []) if i]
        if not ids:
            return {"published": False, "count": 0, "ids": []}
        nodes = "".join(f"<webresource>{i}</webresource>" for i in ids)
        parameter_xml = (
            "<importexportxml><webresources>" + nodes + "</webresources></importexportxml>"
        )
        response = self.session.post(
            self.get_api_url("PublishXml"), json={"ParameterXml": parameter_xml}
        )
        if not response.ok:
            self._raise_with_detail(response, "publish webresources")
        return {"published": True, "count": len(ids), "ids": ids}

    def publish_entity(self, logical_name: str) -> dict[str, Any]:
        """POST ``PublishXml`` scoped to one entity — publishes that table's forms/views/ribbons.

        Form formxml edits do NOT take effect until published, and the publish scope for
        forms is the ENTITY (not a per-form id). Different inner tag from
        ``publish_webresources`` (``<entities><entity>`` vs ``<webresources>``).
        """
        parameter_xml = (
            "<importexportxml><entities><entity>"
            + logical_name
            + "</entity></entities></importexportxml>"
        )
        response = self.session.post(
            self.get_api_url("PublishXml"), json={"ParameterXml": parameter_xml}
        )
        if not response.ok:
            self._raise_with_detail(response, f"publish entity '{logical_name}'")
        return {"published": True, "scope": "entity", "entity": logical_name}

    def publish_application_ribbon(self) -> dict[str, Any]:
        """POST ``PublishXml`` for the application (global) ribbon.

        Uses ``<ribbons><ribbon></ribbon></ribbons>`` — an empty ``<ribbon>`` element publishes the
        application ribbon (distinct from per-entity ribbon, which is published via ``publish_entity``).
        """
        parameter_xml = "<importexportxml><ribbons><ribbon></ribbon></ribbons></importexportxml>"
        response = self.session.post(
            self.get_api_url("PublishXml"), json={"ParameterXml": parameter_xml}
        )
        if not response.ok:
            self._raise_with_detail(response, "publish application ribbon")
        return {"published": True, "scope": "application_ribbon"}

    # ------------------------------------------------ localized labels (ADR-016)
    # SetLocLabels/RetrieveLocLabels work on a limited set of DATA-record localizable
    # attributes (verified live: savedquery.name, systemform.name). Two org quirks,
    # both live-verified 2026-08-28:
    #   - the ACTION rejects "@odata.id" monikers -> typed {@odata.type, <pk>: id} form;
    #   - this org rejects the documented "PublishFlag" parameter -> publish separately.

    _LOC_LABEL_TYPES = {
        "savedqueries": ("Microsoft.Dynamics.CRM.savedquery", "savedqueryid"),
        "systemforms": ("Microsoft.Dynamics.CRM.systemform", "formid"),
    }

    def retrieve_loc_labels(
        self, entity_set: str, pk: str, attribute: str
    ) -> dict[int, str]:
        """GET ``RetrieveLocLabels`` -> ``{languagecode: label}`` (published labels).

        ``entity_set`` is the entity-set name ("savedqueries"/"systemforms"); the
        response labels live under ``Label.LocalizedLabels`` (not ``value``).
        """
        if entity_set not in self._LOC_LABEL_TYPES:
            raise ValueError(f"Unsupported entity set for loc labels: {entity_set!r}")
        url = self.get_api_url(
            "RetrieveLocLabels(EntityMoniker=@m,AttributeName=@a,IncludeUnpublished=@u)"
            f"?@m={{'@odata.id':'{entity_set}({pk})'}}&@a='{attribute}'&@u=false"
        )
        response = self.session.get(url)
        if not response.ok:
            self._raise_with_detail(response, f"retrieve loc labels for {entity_set}({pk})")
        labels = response.json().get("Label", {}).get("LocalizedLabels", [])
        return {
            int(lab["LanguageCode"]): lab["Label"]
            for lab in labels if lab.get("Label") is not None
        }

    def set_loc_labels(
        self, entity_set: str, pk: str, attribute: str, labels: dict[int, str]
    ) -> dict[str, Any]:
        """POST ``SetLocLabels`` — set the given language labels for a data attribute.

        Pass the FULL label set (unchanged languages included): the action may replace
        the attribute's label collection, so omitting a language could drop it.
        """
        odata_type, pk_field = self._LOC_LABEL_TYPES[entity_set]
        body = {
            "EntityMoniker": {"@odata.type": odata_type, pk_field: pk},
            "AttributeName": attribute,
            "Labels": [
                {"Label": text, "LanguageCode": lc} for lc, text in sorted(labels.items())
            ],
        }
        response = self.session.post(self.get_api_url("SetLocLabels"), json=body)
        if not response.ok:
            self._raise_with_detail(response, f"set loc labels for {entity_set}({pk})")
        return {"status": "updated", "labels": {str(k): v for k, v in sorted(labels.items())}}

    # -------------------------------------------------------- solution ZIP (Phase 7)

    def export_solution(self, solution_name: str, *, managed: bool = False) -> bytes:
        """POST ``ExportSolution`` and return the solution ZIP bytes (base64-decoded).

        Used by ribbon deploy/reverse: the ZIP's ``customizations.xml`` is edited
        (RibbonDiffXml) then re-imported. ``managed`` defaults False (unmanaged, editable).
        """
        response = self.session.post(
            self.get_api_url("ExportSolution"),
            json={"SolutionName": solution_name, "Managed": bool(managed)},
        )
        if not response.ok:
            self._raise_with_detail(response, f"export solution '{solution_name}'")
        b64 = (response.json() or {}).get("ExportSolutionFile")
        if not b64:
            raise RuntimeError(f"ExportSolution('{solution_name}') returned no ExportSolutionFile")
        return base64.b64decode(b64)

    def import_solution(
        self,
        zip_bytes: bytes,
        *,
        overwrite_unmanaged: bool = True,
        publish_workflows: bool = False,
        import_job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST ``ImportSolution`` with the (edited) solution ZIP and return the ImportJob result.

        ``OverwriteUnmanagedCustomizations=true`` so the edited RibbonDiffXml replaces the existing one.
        For a small dedicated solution this is fast and backup-free (unlike full-solution Ribbon Workbench
        re-imports). Returns ``{ImportJobId, ...}``.
        """
        payload: dict[str, Any] = {
            "CustomizationFile": base64.b64encode(zip_bytes).decode("ascii"),
            "OverwriteUnmanagedCustomizations": bool(overwrite_unmanaged),
            "PublishWorkflows": bool(publish_workflows),
            "ImportJobId": import_job_id or str(uuid.uuid4()),
        }
        response = self.session.post(self.get_api_url("ImportSolution"), json=payload)
        if not response.ok:
            self._raise_with_detail(response, "import solution")
        try:
            return response.json() or {}
        except ValueError:
            return {"status": "imported"}

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

    def get_role_by_id(self, role_id: str) -> dict[str, Any]:
        """Get a security role keyed by id (used by solution reverse)."""
        response = self.session.get(
            self.get_api_url(f"roles({role_id})?$select=roleid,name")
        )
        response.raise_for_status()
        return response.json()

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
    def add_privileges_to_role(
        self, role_id: str, privileges: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Invoke the bound ``AddPrivilegesRole`` action (the ONLY Web API way to write
        role privileges — the ``roleprivileges`` entity doesn't support Create).

        ``privileges`` is a list of ``{"PrivilegeId": <guid>, "Depth": "<name>"}`` where
        Depth is the bare PrivilegeDepth member name (``Basic``/``Local``/``Deep``/
        ``Global``). The action upserts: adding an already-present privilege updates its
        depth.
        """
        response = self.session.post(
            self.get_api_url(f"roles({role_id})/Microsoft.Dynamics.CRM.AddPrivilegesRole"),
            json={"Privileges": privileges},
        )
        if not response.ok:
            self._raise_with_detail(response, "add privileges to role")
        return {"synced": True, "count": len(privileges)}

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
