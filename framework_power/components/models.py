"""
Typed models for solution components (framework_power Phase 2).

These extend the Phase-1 table model family (``framework_power.models``) with the
container + non-table component types a Dataverse Solution can hold. The same
"model as single source of truth" principle applies: ``components.serializer`` and
the per-type modules convert these to/from Dataverse Web API JSON.

Design notes:
- ``Publisher`` field names mirror ``config/publishers.yaml`` (name/display_name/
  prefix/description) so a config entry maps directly to a Publisher.
- ``Form`` is a STRUCTURED typed model (Phase 5): ``framework_power.form_xml`` parses
  FormXml into the nodes below and serializes them back. Layout nodes carry a full
  ``attrs`` dict (FormXml is attribute-heavy) so reverse->forward is lossless; only
  ``FetchXml``/``LayoutXml`` on ``View`` remain opaque.
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

# Text control classid (verified live on the account Main form). Used as the
# fallback when a control's field type has no known classid mapping.
DEFAULT_CONTROL_CLASSID = "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}"


class FormType(IntEnum):
    """Dataverse SystemForm ``type`` codes.

    Integer values VERIFIED LIVE on env dev account forms (Phase 5 verify-live):
    Main=2, QuickView=6 (帐户层次结构磁贴窗体 / 引用面板 / 卡), QuickCreate=7
    (帐户快速创建), Card=11. The pre-Phase-5 enum had QuickCreate/QuickView swapped —
    the environment is authoritative.
    """

    Dashboard = 0
    Main = 2
    Mobile = 5
    QuickView = 6
    QuickCreate = 7
    Card = 11


# Form types this tool will author/edit (user-confirmed Phase-5 scope). Enforced by
# ``components/form.lint``. Dashboard/Mobile/Card are reversed/skipped, not authored.
EDITABLE_FORM_TYPES: frozenset[FormType] = frozenset({FormType.Main, FormType.QuickCreate, FormType.QuickView})


@dataclass
class FormLabel:
    """A ``<label>`` (description + languagecode). languagecode is a FormXml str attr."""

    description: str
    languagecode: str = "2052"  # 2052 zh-CN (matches the org), 1033 en-US


@dataclass
class FormColumn:
    """A ``<column>`` inside a tab's ``<columns>``.

    In real FormXml, sections live INSIDE columns (``tab/columns/column/sections/section``),
    so each column owns its sections — preserving this nesting is what lets multi-column
    tabs round-trip losslessly. ``attrs`` preserves the width and any extra attributes.
    """

    width: str = "100%"
    sections: list["FormSection"] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class FormControl:
    """A ``<control>`` — binds a field (``datafieldname``) to a UI control.

    By Dataverse convention (verified live) the control ``id`` equals the field's
    logical name. ``classid`` selects the control type (text/lookup/optionset/...);
    ``parameters`` holds any ``<parameters>`` children; ``attrs`` preserves the full
    attribute set so reverse->forward is lossless.
    """

    datafieldname: str
    classid: str = DEFAULT_CONTROL_CLASSID
    id: str = ""  # defaults to datafieldname when serialized
    disabled: bool = False
    attrs: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class FormCell:
    """A ``<cell>`` (holds one ``control`` + its label). ``attrs`` carries colspan/
    rowspan/locklevel/labelid/visible and any other FormXml attributes verbatim."""

    control: Optional[FormControl] = None
    id: str = ""
    showlabel: bool = True
    visible: bool = True
    labels: list[FormLabel] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class FormRow:
    """A ``<row>`` (one or more ``<cell>`` laid out by the section's column count)."""

    cells: list[FormCell] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class FormSection:
    """A ``<section>``. ``columns`` is the FormXml ``columns`` attribute (e.g. 11 = 2
    equal columns, 1 = 1 column); ``attrs`` preserves showbar/layout/labelwidth/
    celllabelposition/celllabelalignment/locklevel/labelid/IsUserDefined verbatim."""

    name: str
    id: str = ""
    columns: int = 1
    labels: list[FormLabel] = field(default_factory=list)
    rows: list[FormRow] = field(default_factory=list)
    showlabel: bool = True
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class FormTab:
    """A ``<tab>``. Sections live inside the tab's ``columns`` (see :class:`FormColumn`).
    ``attrs`` preserves IsUserDefined/locklevel/labelid/showlabel/expanded verbatim."""

    name: str
    id: str = ""
    labels: list[FormLabel] = field(default_factory=list)
    columns: list[FormColumn] = field(default_factory=lambda: [FormColumn("100%")])
    showlabel: bool = True
    expanded: bool = True
    attrs: dict[str, str] = field(default_factory=dict)

    @property
    def sections(self) -> list["FormSection"]:
        """Flattened view of all sections across this tab's columns (read/edit helper)."""
        out: list[FormSection] = []
        for col in self.columns:
            out.extend(col.sections)
        return out


@dataclass
class FormLibrary:
    """A ``<Library>`` — a JS web resource loaded by the form.

    ``name`` is the webresource name (e.g. ``new_/js/common/XRM.com.js``); the
    dependency therefore requires the webresource to exist first. ``library_unique_id``
    is a brace-wrapped GUID (e.g. ``{...}``) — generated on serialize if empty.
    Verified live: NO ``libraryUniqueIdRaw`` attribute is used in this org's forms.
    """

    name: str
    library_unique_id: str = ""


@dataclass
class FormEventHandler:
    """A ``<Handler>`` — a JS function invoked by an event.

    ``library_name`` is the webresource name (== a :class:`FormLibrary.name`).
    ``internal`` marks ``<InternalHandlers>`` (system handlers — read-only, preserved
    on reverse, never authored here); custom bindings live in ``<Handlers>``
    (``internal=False``). ``handler_unique_id`` is a brace-wrapped GUID, generated on
    serialize if empty. ``parameters``/``pass_execution_context`` are OPTIONAL in
    FormXml (a system handler may omit them), so ``attrs`` is the source of truth for
    which attributes are present (verified live on the account onload handler).
    """

    function_name: str
    library_name: str
    handler_unique_id: str = ""
    enabled: bool = True
    parameters: str = ""
    pass_execution_context: bool = False
    internal: bool = False
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class FormEvent:
    """A ``<event>`` (onload/onsave/tabstatechange, or a control's onchange).

    For a control-level event (e.g. onchange), set ``control_id`` to the control id;
    form-level events (onload/onsave) leave it ``None``. ``attrs`` preserves the full
    attribute set (name/application/active/control/...) verbatim.
    """

    name: str
    active: bool = False
    application: bool = False
    handlers: list[FormEventHandler] = field(default_factory=list)
    control_id: Optional[str] = None
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class Form:
    """A SystemForm as a STRUCTURED typed model (Phase 5).

    ``form_xml`` is no longer an opaque string: ``framework_power.form_xml`` parses
    FormXml into ``tabs``/``libraries``/``events`` and serializes them back. ``entity``
    is the objecttypecode (logical name). ``root_attrs`` + ``extras_xml`` preserve
    unmodeled ``<form>`` attributes (showImage, headerdensity, ...) and children
    (ancestor, hiddencontrols, ...) verbatim so a reverse snapshot round-trips lossless.
    """

    name: str
    entity: str  # objecttypecode (logical name)
    form_type: FormType = FormType.Main
    description: Optional[str] = None
    tabs: list[FormTab] = field(default_factory=list)
    libraries: list[FormLibrary] = field(default_factory=list)
    events: list[FormEvent] = field(default_factory=list)
    root_attrs: dict[str, str] = field(default_factory=dict)
    # Unmodeled <form> children, captured verbatim, split by position so re-serialization
    # does not reorder them: pre (ancestor/hiddencontrols, before <tabs>) and post
    # (formParameters/DisplayConditions/..., after <events>).
    extras_pre_xml: str = ""
    extras_post_xml: str = ""


# ============================================================ view

# View types this tool will CREATE (only Public list views are creatable) and reverse+update in place
# (the 4 system views are one-per-table, update-only). Defined after QueryType below.


class QueryType(IntEnum):
    """Dataverse SavedQuery ``querytype`` codes (verified live on env dev new_fpformsmoke)."""

    Public = 0           # creatable list view
    AdvancedFind = 1     # one-per-table, update-only
    Associated = 2       # one-per-table, update-only
    QuickFind = 4        # one-per-table, update-only
    Lookup = 64          # one-per-table, update-only


AUTHORABLE_VIEW_TYPES = frozenset({QueryType.Public})
UPDATABLE_VIEW_TYPES = frozenset({QueryType.Public, QueryType.AdvancedFind, QueryType.Associated,
                                  QueryType.QuickFind, QueryType.Lookup})


@dataclass
class ViewColumn:
    """A displayed column — drives BOTH a fetch ``<attribute>`` (when ``name`` has no dot) and
    a layout ``<cell>`` (1:1, in display order). ``name`` may be ``alias.attr`` for a joined
    column (then the attribute lives on the matching :class:`ViewLinkEntity`). ``attrs`` preserves
    the full cell attribute set (width/disableSorting/imageprovider.../ishidden) for fidelity.
    """

    name: str
    width: int = 150
    disable_sorting: bool = False
    hidden: bool = False
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ViewOrder:
    """A fetch ``<order>`` (sort). ``attrs`` preserves extra attributes verbatim."""

    attribute: str
    descending: bool = False
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ViewCondition:
    """A fetch ``<condition>``. ``operator`` is any FetchXml operator (eq/ne/gt/like/in/null/
    eq-userid/last-x-days/...) passed through as a string. ``value`` for single-value operators;
    ``values`` for ``in``/``between``. Some operators (null, eq-userid, date-relative) take neither.
    """

    attribute: str
    operator: str
    value: Optional[str] = None
    values: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ViewFilter:
    """A fetch ``<filter>`` (AND/OR group). ``filters`` holds nested :class:`ViewFilter` so arbitrary
    trees ((A AND (B OR C))) are representable. ``attrs`` preserves extra attributes (e.g.
    ``isquickfindfields="1"`` on a QuickFind filter) verbatim.
    """

    filter_type: str = "and"  # "and" | "or"
    conditions: list[ViewCondition] = field(default_factory=list)
    filters: list["ViewFilter"] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ViewLinkEntity:
    """A fetch ``<link-entity>`` (join). ``from_attr``/``to_attr`` are the related/parent columns;
    ``attributes`` are the joined columns (referenced by ``alias.attr`` column names in the layout)."""

    name: str
    from_attr: str = ""
    to_attr: str = ""
    link_type: str = "inner"  # inner | outer | in | exists | ...
    alias: str = ""
    attributes: list[str] = field(default_factory=list)
    filter: Optional[ViewFilter] = None
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class View:
    """A SavedQuery as a STRUCTURED typed model (Phase 6).

    ``fetch_xml``/``layout_xml`` are no longer opaque: ``framework_power.view_xml`` parses them into
    ``columns``/``filter``/``orders``/``link_entities`` and serializes them back. ``primary_id`` is the
    layout ``<row id>`` attribute (always present as a fetch ``<attribute>`` too). ``object_type_code``
    is the INTEGER ObjectTypeCode the LayoutXml ``<grid object=>`` requires (verified live: looked up
    via ``get_entity_metadata.ObjectTypeCode``). ``fetch_attrs``/``grid_attrs``/``row_attrs`` preserve
    the remaining root-attribute sets verbatim (version/mapping/savedqueryid; name/jump/select/icon/
    preview; row name) so a reverse snapshot round-trips lossless.
    """

    name: str
    entity: str  # returnedtypecode (logical name)
    primary_id: str = ""
    object_type_code: int = 0
    query_type: QueryType = QueryType.Public
    description: Optional[str] = None
    is_default: bool = False
    columns: list[ViewColumn] = field(default_factory=list)
    filters: list[ViewFilter] = field(default_factory=list)  # sibling <filter>s are implicitly ANDed
    orders: list[ViewOrder] = field(default_factory=list)
    link_entities: list[ViewLinkEntity] = field(default_factory=list)
    extra_attributes: list[str] = field(default_factory=list)  # fetch <attribute>s with no layout cell
    fetch_attrs: dict[str, str] = field(default_factory=dict)
    grid_attrs: dict[str, str] = field(default_factory=dict)
    row_attrs: dict[str, str] = field(default_factory=dict)


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


# ============================================================ security role


class AccessRight(IntEnum):
    """The right a privilege grants (verified live from ``privilege.accessright``)."""

    READ = 1
    WRITE = 2
    APPEND = 4
    APPEND_TO = 16
    CREATE = 32
    DELETE = 65536
    SHARE = 262144
    ASSIGN = 524288


class PrivilegeDepth(IntEnum):
    """Privilege depth/scope — a bitmask stored as ``privilegedepthmask``.

    Verified live (Basic User's account privileges carry mask 1 = User-level).
    ``USER`` = Basic, ``BUSINESS_UNIT`` = Local, ``PARENT_CHILD`` = Deep, ``GLOBAL`` =
    Organization. "No access" is represented by the absence of a roleprivilege record.
    """

    USER = 1
    BUSINESS_UNIT = 2
    PARENT_CHILD = 4
    GLOBAL = 8


@dataclass(frozen=True)
class TablePrivilege:
    """The rights (at depths) a role should hold on one table."""

    table: str  # logical name, e.g. "new_fpsmokea"
    rights: dict[AccessRight, PrivilegeDepth] = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityRole:
    """A reference to an EXISTING Dataverse security role + its desired table privileges.

    The role is NOT created here — it must already exist in the environment (looked up
    by name). ``deploy_role`` upserts the listed privileges (non-destructive; unlisted
    rights are left untouched).
    """

    name: str
    table_privileges: list[TablePrivilege] = field(default_factory=list)


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
    roles: list[str] = field(default_factory=list)  # name refs -> metadata_py/roles/
    optionsets: list[GlobalOptionSet] = field(default_factory=list)
    webresources: list[WebResource] = field(default_factory=list)
    forms: list[Form] = field(default_factory=list)
    views: list[View] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)
    refs: list[ComponentRef] = field(default_factory=list)
