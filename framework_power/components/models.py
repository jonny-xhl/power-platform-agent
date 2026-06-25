"""
Typed models for solution components (framework_power Phase 2).

These extend the Phase-1 table model family (``framework_power.models``) with the
container + non-table component types a Dataverse Solution can hold. The same
"model as single source of truth" principle applies: ``components.serializer`` and
the per-type modules convert these to/from Dataverse Web API JSON.

Design notes:
- ``Publisher`` field names mirror ``config/publishers.yaml`` (name/display_name/
  prefix/description) so a config entry maps directly to a Publisher.
- ``FormXml`` / ``FetchXml`` / ``LayoutXml`` are OPAQUE string fields — the library
  never generates or parses them; reverse captures them verbatim.
- DLL bytes and WebResource content are base64 strings (opaque, same rationale).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from ..models import Label, Option


# ============================================================ publisher


@dataclass(frozen=True)
class Publisher:
    """A Dataverse publisher. Field names mirror ``config/publishers.yaml``."""

    name: str  # uniquename in Web API
    display_name: str  # friendlyname
    prefix: str  # customizationprefix (e.g. "new")
    description: Optional[str] = None


# ============================================================ catch-all ref


@dataclass(frozen=True)
class ComponentRef:
    """An add-only / unresolvable component reference inside a Solution.

    Used to add components by explicit id or by name+entity that framework_power
    does not deploy itself, and as the reverse fallback for component types it
    cannot reconstruct as a typed model.
    """

    type: str
    name: Optional[str] = None
    object_id: Optional[str] = None
    entity: Optional[str] = None
    note: Optional[str] = None


# ============================================================ optionset (global)


@dataclass(frozen=True)
class GlobalOptionSet:
    """A global OptionSet (picklist)."""

    name: str
    display_name: Label
    options: list[Option] = field(default_factory=list)
    description: Optional[Label] = None
    is_global: bool = True


# ============================================================ webresource


class WebResourceType(IntEnum):
    """Dataverse WebResource type codes (webresourcetype option set)."""

    WebPage = 1
    Css = 2
    JScript = 3  # JavaScript
    Xml = 4
    Png = 5
    Jpg = 6
    Gif = 7
    Silverlight = 8  # XAP
    Xsl = 9
    Ico = 10
    Svg = 11


@dataclass(frozen=True)
class WebResource:
    """A Web Resource. ``content`` is base64-encoded bytes (opaque)."""

    name: str
    display_name: str
    content: str  # base64
    webresource_type: WebResourceType
    description: Optional[str] = None


# ============================================================ form


class FormType(IntEnum):
    """Dataverse SystemForm type codes."""

    Dashboard = 0
    Main = 2
    Mobile = 5
    QuickCreate = 6
    QuickView = 7
    Card = 11


@dataclass(frozen=True)
class Form:
    """A SystemForm. ``form_xml`` is an OPAQUE FormXml string."""

    name: str
    entity: str  # objecttypecode (logical name)
    form_xml: str
    form_type: FormType = FormType.Main
    description: Optional[str] = None


# ============================================================ view


class QueryType(IntEnum):
    """Dataverse SavedQuery querytype codes."""

    Public = 0
    AdvancedFind = 1
    Associated = 2
    QuickFind = 4
    Lookup = 64


@dataclass(frozen=True)
class View:
    """A SavedQuery (view). ``fetch_xml`` and ``layout_xml`` are OPAQUE strings."""

    name: str
    entity: str  # returnedtypecode (logical name)
    fetch_xml: str
    layout_xml: str
    query_type: QueryType = QueryType.Public
    is_default: bool = False
    description: Optional[str] = None


# ============================================================ plugin


class IsolationMode(IntEnum):
    """Plugin assembly isolation mode."""

    None_ = 1
    Sandbox = 2
    External = 3


class SourceType(IntEnum):
    """Plugin assembly source type."""

    Database = 0
    FileContent = 1


@dataclass(frozen=True)
class PluginStep:
    """A SDK message processing step."""

    name: str
    message: str  # Create/Update/Delete/...
    entity: str  # primary entity logical name
    stage: int = 40  # 10 pre-validation, 20 pre-op, 40 post-op
    mode: int = 0  # 0 sync, 1 async
    deployment: int = 0  # 0 server, 1 client, 2 both
    filtering_attributes: str = ""
    description: str = ""
    rank: int = 1


@dataclass(frozen=True)
class CustomAction:
    """A custom action (SDK message / global)."""

    schema_name: str
    display_name: Label
    entity: Optional[str] = None  # None = global action
    description: Optional[Label] = None
    parameters: list[dict[str, Any]] = field(default_factory=list)
    return_type: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class Plugin:
    """A plugin assembly + its steps + custom actions. ``content`` is base64 DLL."""

    name: str
    content: str  # base64 DLL
    version: str = "1.0.0.0"
    isolation_mode: IsolationMode = IsolationMode.Sandbox
    source_type: SourceType = SourceType.Database
    steps: list[PluginStep] = field(default_factory=list)
    custom_actions: list[CustomAction] = field(default_factory=list)


# ============================================================ solution


@dataclass
class Solution:
    """A Power Platform Solution (container of components).

    ``tables`` are NAME REFS into ``metadata_py/tables/<name>.py`` (resolved by the
    table registry at deploy time). Non-table components are inlined. A reverse
    snapshot populates the same fields; forward deploy skips standard (non-prefixed)
    items, so a full snapshot is safe to re-deploy.
    """

    unique_name: str
    friendly_name: str
    version: str = "1.0.0.0"
    description: Optional[str] = None
    publisher: Optional[Publisher] = None
    publisher_key: Optional[str] = None  # config/publishers.yaml key
    tables: list[str] = field(default_factory=list)
    optionsets: list[GlobalOptionSet] = field(default_factory=list)
    webresources: list[WebResource] = field(default_factory=list)
    forms: list[Form] = field(default_factory=list)
    views: list[View] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)
    refs: list[ComponentRef] = field(default_factory=list)
