"""
Typed, declarative model API for Dataverse table metadata (framework_power).

These dataclasses are the single source of truth that AI-authored deploy scripts
build. ``framework_power.serializer`` converts them to Dataverse Web API JSON.

Design notes:
- ``Label`` supports multiple languages (zh-CN 2052, en-US 1033, ...) and replaces
  the legacy single-language label helpers.
- ``Column`` carries type-specific optional fields; irrelevant fields are ignored
  by the serializer for a given ``AttributeType``.
- ``LookupColumn`` is separate from ``Column`` because lookup attributes are created
  via relationship Deep Insert, never POSTed standalone.
- ``SchemaName`` values are passed through verbatim (no case forcing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union


# ============================================================ labels

LANGUAGE_ZH_CN = 2052
LANGUAGE_EN_US = 1033


@dataclass(frozen=True)
class LocalizedLabel:
    """A single localized label string."""

    text: str
    language_code: int = LANGUAGE_ZH_CN


@dataclass(frozen=True)
class Label:
    """A multi-language label: a list of ``LocalizedLabel`` pairs."""

    localized: list[LocalizedLabel] = field(default_factory=list)

    @classmethod
    def zh(cls, text: str) -> "Label":
        """Chinese-only label (back-compat with the legacy default behavior)."""
        return cls([LocalizedLabel(text, LANGUAGE_ZH_CN)])

    @classmethod
    def en(cls, text: str) -> "Label":
        """English-only label."""
        return cls([LocalizedLabel(text, LANGUAGE_EN_US)])

    @classmethod
    def bilingual(cls, zh: str, en: str) -> "Label":
        """Chinese + English label."""
        return cls([LocalizedLabel(zh, LANGUAGE_ZH_CN), LocalizedLabel(en, LANGUAGE_EN_US)])

    @classmethod
    def parse(cls, value: "Label | LocalizedLabel | str | tuple | None") -> Optional["Label"]:
        """Coerce common inputs into a ``Label``.

        - ``Label``: passed through.
        - ``LocalizedLabel``: wrapped.
        - ``str``: treated as Chinese-only (legacy default).
        - ``(zh, en)`` tuple: bilingual.
        - ``None``: ``None``.
        """
        if value is None:
            return None
        if isinstance(value, Label):
            return value
        if isinstance(value, LocalizedLabel):
            return cls([value])
        if isinstance(value, str):
            return cls.zh(value)
        if isinstance(value, tuple) and len(value) == 2:
            return cls.bilingual(value[0], value[1])
        raise TypeError(f"Cannot coerce {type(value).__name__} into a Label")


# ============================================================ enums


class AttributeType(str, Enum):
    """Dataverse attribute types supported by the deployer."""

    String = "String"
    Integer = "Integer"
    BigInt = "BigInt"
    Money = "Money"
    Decimal = "Decimal"
    Double = "Double"
    Picklist = "Picklist"  # local option set
    Boolean = "Boolean"
    Memo = "Memo"
    DateTime = "DateTime"
    File = "File"


class RequiredLevel(str, Enum):
    """Field requirement level."""

    None_ = "None"
    ApplicationRequired = "ApplicationRequired"
    Recommended = "Recommended"


class Cascade(str, Enum):
    """Cascade behavior values for relationship configuration."""

    Active = "Active"  # Parental
    Cascade_ = "Cascade"
    NoCascade = "NoCascade"
    RemoveLink = "RemoveLink"
    Restrict = "Restrict"


# ============================================================ composites


@dataclass(frozen=True)
class Option:
    """A picklist option (value + multi-language label)."""

    value: int
    label: Label


@dataclass(frozen=True)
class BooleanLabels:
    """True/False labels for a Boolean attribute."""

    true_label: Label
    false_label: Label


@dataclass(frozen=True)
class CascadeConfig:
    """Cascade configuration for a relationship (defaults are conservative/Referential)."""

    assign: Cascade = Cascade.NoCascade
    delete: Cascade = Cascade.RemoveLink
    merge: Cascade = Cascade.Cascade_
    reparent: Cascade = Cascade.NoCascade
    share: Cascade = Cascade.NoCascade
    unshare: Cascade = Cascade.NoCascade


# ============================================================ attributes


@dataclass
class Column:
    """A non-lookup attribute. Lookup attributes use ``LookupColumn`` + ``Relationship``."""

    schema_name: str
    type: AttributeType
    display_name: Label
    description: Optional[Label] = None
    required: RequiredLevel = RequiredLevel.None_
    is_primary_name: bool = False
    ime_mode: Optional[str] = None

    # type-specific optional props (ignored by the serializer when N/A):
    max_length: Optional[int] = None  # String, Memo
    format_name: Optional[str] = None  # String: Text/Email/Url/Phone/TextArea/...
    format: Optional[str] = None  # DateTime: DateOnly/DateAndTime
    date_time_behavior: Optional[str] = None  # DateTime: UserLocal/DateOnly/TimeZoneIndependent
    precision: Optional[int] = None  # Money, Decimal, Double
    precision_source: Optional[int] = None  # Money: 0/1/2
    min_value: Optional[float] = None  # Integer, BigInt, Decimal, Double, Money
    max_value: Optional[float] = None
    default_value: Union[bool, int, str, None] = None  # Boolean->bool, Picklist/Integer->int
    options: list[Option] = field(default_factory=list)  # Picklist (local/inline options)
    optionset_name: Optional[str] = None  # Picklist: global optionset name (if referenced)
    boolean_labels: Optional[BooleanLabels] = None  # Boolean
    max_size_in_kb: Optional[int] = None  # File


@dataclass
class LookupColumn:
    """A lookup attribute. Always deployed via a Relationship (Deep Insert)."""

    schema_name: str
    display_name: Label
    target_entity: str  # logical name of the referenced entity
    description: Optional[Label] = None
    required: RequiredLevel = RequiredLevel.None_


# ============================================================ relationship


@dataclass
class Relationship:
    """A 1:N (creates the lookup column via Deep Insert) or N:N relationship."""

    schema_name: str
    type: str = "OneToMany"  # "OneToMany" | "ManyToMany"

    # 1:N
    referenced_entity: Optional[str] = None  # parent (1 side), logical name
    referencing_entity: Optional[str] = None  # child (N side) = owning table
    lookup: Optional[LookupColumn] = None  # required for 1:N
    cascade: CascadeConfig = field(default_factory=CascadeConfig)

    # N:N
    intersect_entity_name: Optional[str] = None
    display_name: Optional[Label] = None


# ============================================================ table


@dataclass
class Table:
    """A Dataverse table definition (the deployable source of truth)."""

    schema_name: str  # PascalCase, passed through verbatim
    display_name: Label
    display_collection_name: Optional[Label] = None
    description: Optional[Label] = None
    ownership_type: str = "UserOwned"  # "UserOwned" | "OrganizationOwned"
    has_activities: bool = False
    has_notes: bool = False
    is_quick_create_enabled: bool = False
    is_audit_enabled: bool = False
    primary_name_column: Optional[str] = None  # None -> serializer auto-picks
    columns: list[Column] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    @property
    def logical_name(self) -> str:
        """Dataverse lowercases SchemaName for the logical name."""
        return self.schema_name.lower()
