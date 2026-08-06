"""
Data dictionary generator for framework_power (Gen 2 Python-first path).

Converts :class:`Table` objects discovered from ``metadata_py/tables/`` into
human-readable Markdown docs under ``docs/data_dictionary/``.

This module is the workspace-aware successor to ``scripts/generate_data_dictionary.py``
(Gen 1, YAML-based). It reads from the same typed model that ``deploy`` uses,
guaranteeing the data dictionary reflects what is actually deployed.

Public API:
    - :func:`table_to_markdown` — single table → Markdown string
    - :func:`generate_index` — table list → ``index.md`` content
    - :func:`generate_all_tables_summary` — table list → ``all_tables.md`` content
    - :func:`generate_table_docs` — discover + write all docs to a directory

CLI integration:
    pp reverse --dictionary <name> --env dev   # from Dataverse
    python -m framework_power.dictionary        # from local metadata_py/
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    AttributeType,
    BooleanLabels,
    CascadeConfig,
    Column,
    Label,
    LookupColumn,
    Relationship,
    RequiredLevel,
    Table,
)
from .registry import Definition, DEFAULT_DEFINITIONS_DIR

logger = logging.getLogger(__name__)

# Default output directory (relative to workspace root)
DEFAULT_DICTIONARY_DIR = "docs/data_dictionary"

# Language codes for label extraction
LANGUAGE_ZH_CN = 2052
LANGUAGE_EN_US = 1033


# ----------------------------------------------------------------- label helpers


def _label_text(label: Optional[Label], lang_code: int = LANGUAGE_ZH_CN) -> str:
    """Extract a single-language string from a multi-language Label."""
    if label is None:
        return ""
    for loc in label.localized:
        if loc.language_code == lang_code:
            return loc.text
    # Fallback: return the first available
    if label.localized:
        return label.localized[0].text
    return ""


def _label_both(label: Optional[Label]) -> str:
    """Return 'zh / en' for display in data dictionary tables."""
    zh = _label_text(label, LANGUAGE_ZH_CN)
    en = _label_text(label, LANGUAGE_EN_US)
    if zh and en and zh != en:
        return f"{zh} / {en}"
    return zh or en or ""


def _label_zh_en_split(label: Optional[Label]) -> tuple[str, str]:
    """Return (zh, en) as separate strings for column-based display."""
    return (
        _label_text(label, LANGUAGE_ZH_CN),
        _label_text(label, LANGUAGE_EN_US),
    )


# ----------------------------------------------------------------- type formatting


def _format_type(col: Column) -> str:
    """Human-readable type string with type-specific constraints."""
    t = col.type
    parts: list[str] = [str(t.value)]

    if t == AttributeType.String and col.max_length:
        parts.append(f" (max {col.max_length})")
    elif t == AttributeType.Memo and col.max_length:
        parts.append(f" (max {col.max_length})")
    elif t in (AttributeType.Integer, AttributeType.BigInt):
        if col.min_value is not None or col.max_value is not None:
            parts.append(f" ({col.min_value or ''}~{col.max_value or ''})")
    elif t in (AttributeType.Money, AttributeType.Decimal, AttributeType.Double):
        if col.precision is not None:
            parts.append(f" (precision {col.precision})")
    elif t == AttributeType.DateTime:
        if col.format:
            parts.append(f" ({col.format})")
    elif t == AttributeType.File and col.max_size_in_kb:
        parts.append(f" (max {col.max_size_in_kb}KB)")

    return "".join(parts)


def _format_required(col: Column) -> str:
    """Map RequiredLevel enum to display string."""
    if col.required == RequiredLevel.ApplicationRequired:
        return "必填"
    if col.required == RequiredLevel.Recommended:
        return "推荐"
    return "否"


def _format_options(col: Column) -> str:
    """Format Picklist options or Boolean labels as inline text."""
    if col.type == AttributeType.Picklist and col.options:
        items = ", ".join(
            f"{_label_text(opt.label)}({opt.value})" for opt in col.options[:5]
        )
        if len(col.options) > 5:
            items += f", ... ({len(col.options)} total)"
        return items
    if col.type == AttributeType.Boolean and col.boolean_labels:
        bl: BooleanLabels = col.boolean_labels
        true_text = _label_text(bl.true_label)
        false_text = _label_text(bl.false_label)
        return f"True={true_text}, False={false_text}"
    return ""


def _format_cascade(cascade: CascadeConfig) -> str:
    """Compact cascade string showing non-default behaviors."""
    parts: list[str] = []
    defaults = CascadeConfig()  # all defaults
    for field_name in ("assign", "delete", "merge", "reparent", "share", "unshare"):
        actual = getattr(cascade, field_name)
        default = getattr(defaults, field_name)
        if actual != default:
            parts.append(f"{field_name}={actual.value}")
    return ", ".join(parts) if parts else "defaults"


# ----------------------------------------------------------------- Markdown generation


def table_to_markdown(
    table: Table,
    *,
    source_name: Optional[str] = None,
    source_dir: str = "metadata_py/tables",
) -> str:
    """Convert a single :class:`Table` into a data dictionary Markdown string.

    Args:
        table: The table definition to document.
        source_name: File stem of the source ``.py`` file (e.g. ``new_projectbudget``).
        source_dir: Directory path for the source link (relative to project root).

    Returns:
        Markdown string for ``docs/data_dictionary/tables/<schema>.md``.
    """
    schema_name = table.schema_name
    display = _label_both(table.display_name)
    description = _label_both(table.description)

    lines: list[str] = [
        f"# {display} (`{schema_name}`)",
        "",
    ]

    if description:
        lines.append(f"**说明**: {description}")
        lines.append("")

    zh_col, en_col = _label_zh_en_split(table.display_collection_name)
    if zh_col or en_col:
        lines.append(f"**集合名称**: {_label_both(table.display_collection_name)}")
        lines.append("")

    lines.append(f"**所有权类型**: `{table.ownership_type}`")
    lines.append("")

    if table.has_activities:
        lines.append("> ✅ 启用了 Activities")
    if table.has_notes:
        lines.append("> ✅ 启用了 Notes")
    if table.is_audit_enabled:
        lines.append("> ✅ 启用了 Audit")
    if table.is_quick_create_enabled:
        lines.append("> ✅ 启用了 Quick Create")

    if any([table.has_activities, table.has_notes, table.is_audit_enabled, table.is_quick_create_enabled]):
        lines.append("")

    lines.extend(["---", "", "## 字段列表", ""])
    lines.append("| Schema Name | 显示名称 | 类型 | 必填 | 默认值 | 选项集 / 布尔值 | 说明 |")
    lines.append("|-------------|----------|------|------|--------|----------------|------|")

    for col in table.columns:
        name = col.schema_name
        col_display = _label_both(col.display_name)
        col_type = _format_type(col)
        required = _format_required(col)
        default = ""
        if col.default_value is not None:
            default = str(col.default_value)
        options = _format_options(col)
        col_desc = _label_both(col.description)

        lines.append(
            f"| `{name}` | {col_display} | `{col_type}` | {required} | {default} | {options} | {col_desc} |"
        )

    # Relationships (extract lookup columns from 1:N relationships)
    one_to_many = [r for r in table.relationships if r.type == "OneToMany"]
    many_to_many = [r for r in table.relationships if r.type == "ManyToMany"]

    if one_to_many:
        lines.extend(["", "## 查找关系 (1:N)", ""])
        lines.append("| Lookup 字段 | 显示名称 | 目标实体 | 必填 | 关系名称 | 级联 |")
        lines.append("|-------------|----------|----------|------|----------|------|")
        for rel in one_to_many:
            if rel.lookup:
                lk: LookupColumn = rel.lookup
                lk_display = _label_both(lk.display_name)
                lk_required = _format_required(lk)
                target = rel.referenced_entity or lk.target_entity or "?"
                cascade = _format_cascade(rel.cascade)
                lines.append(
                    f"| `{lk.schema_name}` | {lk_display} | `{target}` | {lk_required} | `{rel.schema_name}` | {cascade} |"
                )

    if many_to_many:
        lines.extend(["", "## 多对多关系 (N:N)", ""])
        lines.append("| 关系名称 | 交集实体 | 目标实体 |")
        lines.append("|----------|----------|----------|")
        for rel in many_to_many:
            intersect = rel.intersect_entity_name or "?"
            target = rel.referenced_entity or "?"
            lines.append(f"| `{rel.schema_name}` | `{intersect}` | `{target}` |")

    # Metadata footer
    lines.extend(["", "---", "", "## 元数据", ""])
    lines.append(f"- **Schema Name**: `{schema_name}`")
    lines.append(f"- **Logical Name**: `{table.logical_name}`")

    if source_name:
        # Normalize source_dir to a relative path for clean links
        rel_source = source_dir.replace("\\", "/")
        lines.append(f"- **源文件**: [`{source_name}.py`](../../{rel_source}/{source_name}.py)")
    else:
        lines.append(f"- **生成方式**: 从 Dataverse 环境逆向导出")

    lines.append(f"- **生成时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- **字段数**: {len(table.columns)}")
    lines.append(f"- **关系数**: {len(table.relationships)}")
    lines.append("")

    return "\n".join(lines)


def generate_all_tables_summary(definitions: dict[str, Definition]) -> str:
    """Generate the ``all_tables.md`` summary page content.

    Args:
        definitions: Discovered table definitions from :func:`discover_definitions`.
    """
    lines: list[str] = [
        "# 所有表结构定义",
        "",
        f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "> 基于 `metadata_py/tables/` Python 定义（Gen 2 / framework_power）",
        "",
        "---",
        "",
    ]

    for name in sorted(definitions):
        defn = definitions[name]
        table = defn.table
        display = _label_both(table.display_name)
        description = _label_both(table.description)

        lines.extend([
            f"## {display} (`{table.schema_name}`)",
            "",
            description or "",
            "",
            f"**字段数**: {len(table.columns)} | **关系数**: {len(table.relationships)}",
            "",
            f"[查看详情](tables/{table.schema_name}.md)",
            "",
        ])

    return "\n".join(lines)


def generate_index(definitions: dict[str, Definition]) -> str:
    """Generate the ``index.md`` content from discovered definitions.

    Unlike the Gen 1 version (which re-scans the output directory), this version
    reads directly from the ``Table`` objects, guaranteeing accuracy.
    """
    lines: list[str] = [
        "# 数据字典索引",
        "",
        f"*自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "> 基于 `metadata_py/tables/` Python 定义（Gen 2 / framework_power）",
        "",
        "---",
        "",
        "## 表 (Tables)",
        "",
        "| 表名 | Schema Name | 字段数 | 关系数 | 说明 |",
        "|------|-------------|--------|--------|------|",
    ]

    for name in sorted(definitions):
        defn = definitions[name]
        table = defn.table
        display = _label_both(table.display_name)
        description = _label_both(table.description)
        lines.append(
            f"| [{display}](tables/{table.schema_name}.md) | `{table.schema_name}` | "
            f"{len(table.columns)} | {len(table.relationships)} | {description} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 快速导航",
        "",
        "- [所有表结构](all_tables.md) — 完整的表结构列表",
        "",
    ])

    return "\n".join(lines)


# ----------------------------------------------------------------- batch generation


def generate_table_docs(
    definitions: dict[str, Definition],
    output_dir: str | Path = DEFAULT_DICTIONARY_DIR,
    *,
    source_dir: str = DEFAULT_DEFINITIONS_DIR,
) -> list[Path]:
    """Write all table docs + index + summary to ``output_dir``.

    Args:
        definitions: Discovered table definitions.
        output_dir: Output directory (default ``docs/data_dictionary``).
        source_dir: Source directory path for relative links (should be relative
            to the project/workspace root, e.g. ``metadata_py/tables``).

    Returns:
        List of file paths written.
    """
    out = Path(output_dir)
    tables_out = out / "tables"
    tables_out.mkdir(parents=True, exist_ok=True)

    # Normalize source_dir to a relative path for clean Markdown links
    from pathlib import PurePosixPath
    try:
        rel_source = str(PurePosixPath(Path(source_dir)))
        # If source_dir is absolute, try to make it relative
        src_path = Path(source_dir)
        out_path = Path(output_dir)
        if src_path.is_absolute():
            try:
                rel_source = str(src_path.relative_to(src_path.anchor))
                rel_source = rel_source.replace("\\", "/")
            except Exception:
                rel_source = source_dir
    except Exception:
        rel_source = source_dir

    written: list[Path] = []

    for name, defn in definitions.items():
        md = table_to_markdown(defn.table, source_name=name, source_dir=rel_source)
        file_path = tables_out / f"{defn.table.schema_name}.md"
        file_path.write_text(md, encoding="utf-8")
        written.append(file_path)

    # Summary + index
    all_tables_path = out / "all_tables.md"
    all_tables_path.write_text(generate_all_tables_summary(definitions), encoding="utf-8")
    written.append(all_tables_path)

    index_path = out / "index.md"
    index_path.write_text(generate_index(definitions), encoding="utf-8")
    written.append(index_path)

    return written


# ----------------------------------------------------------------- reverse-path support
#
# The ``pp reverse --all --dictionary`` path writes one ``tables/<schema>.md`` per
# table but historically never produced an ``index.md`` (the local ``cmd_dictionary``
# path did, via ``generate_table_docs`` above). The helpers below close that gap by
# deriving the index directly from the already-written table Markdown files, and add
# global-optionset documentation (``optionsets/*.md``) which was never implemented.
#
# They depend only on the on-disk Markdown / raw Dataverse dicts — no Table models,
# no client import — so this module stays a leaf renderer.


# H1 format produced by table_to_markdown: "# {display} (`{schema}`)" — note the
# literal parentheses around the backticked schema name.
_TABLE_H1_RE = re.compile(r"^# (.+) \(`([^`]+)`\)$")
_DESC_RE = re.compile(r"^\*\*说明\*\*:\s*(.*)$")
_FIELDS_RE = re.compile(r"^- \*\*字段数\*\*:\s*(\d+)")
_RELS_RE = re.compile(r"^- \*\*关系数\*\*:\s*(\d+)")


def _parse_table_markdown(path: Path) -> dict:
    """Extract {schema, display, description, fields, rels} from a table doc.

    Best-effort regex parse against the format produced by :func:`table_to_markdown`.
    Missing fields degrade gracefully (empty string / 0) so a partially-written file
    never breaks index generation.
    """
    info: dict = {"schema": path.stem, "display": path.stem, "description": "", "fields": 0, "rels": 0}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return info
    for line in text.splitlines():
        m = _TABLE_H1_RE.match(line)
        if m:
            info["display"] = m.group(1).strip()
            info["schema"] = m.group(2).strip()
            continue
        m = _DESC_RE.match(line)
        if m:
            info["description"] = m.group(1).strip()
            continue
        m = _FIELDS_RE.match(line)
        if m:
            info["fields"] = int(m.group(1))
            continue
        m = _RELS_RE.match(line)
        if m:
            info["rels"] = int(m.group(1))
    return info


def _schema_prefix(schema: str) -> str:
    """Return the publisher prefix of a custom schema name, or '' if none.

    Dataverse convention: custom entities are ``<prefix>_<suffix>`` (publisher prefix
    is 2-8 chars), while standard entities are single tokens with no underscore.
    """
    m = re.match(r"^([^_]+)_", schema)
    return m.group(1) if m else ""


def generate_index_from_dir(dict_dir: str | Path, *, prefix: str = "new") -> Path:
    """Scan ``<dict_dir>/tables/*.md`` and write a grouped ``index.md``.

    This is the reverse-path counterpart to :func:`generate_index`: it derives the
    index from the Markdown files that ``pp reverse --all --dictionary`` already
    wrote, so the index reflects exactly what is on disk. Tables are grouped into
    standard vs. custom with a statistics header.

    Custom vs. standard classification keys off the Dataverse convention that custom
    entity names contain ``_`` (publisher prefix + ``_`` + suffix), while standard
    entities are single tokens (account, contact, systemuser, ...). This is
    publisher-agnostic, so multiple prefixes (``new_``, ``eden_``, ...) coexist
    correctly. ``prefix`` is retained for backward-compat callers but no longer
    drives classification; the distinct prefixes found are listed in the stats.

    Args:
        dict_dir: Data dictionary root (containing ``tables/``).
        prefix: Deprecated — kept so existing callers keep working. Classification
            now auto-detects every publisher prefix present.

    Returns:
        Path to the written ``index.md``.
    """
    out = Path(dict_dir)
    tables_dir = out / "tables"
    rows: list[dict] = []
    if tables_dir.is_dir():
        for md_path in sorted(tables_dir.glob("*.md")):
            rows.append(_parse_table_markdown(md_path))

    def _is_custom(schema: str) -> bool:
        return "_" in schema.lower()

    custom = [r for r in rows if _is_custom(r["schema"])]
    standard = [r for r in rows if not _is_custom(r["schema"])]
    custom.sort(key=lambda r: r["schema"].lower())
    standard.sort(key=lambda r: r["schema"].lower())

    # Lowercase so the same publisher's casing variants (New_ / new_) collapse.
    custom_prefixes = sorted(
        {_schema_prefix(r["schema"]).lower() for r in custom if _schema_prefix(r["schema"])},
        key=str.lower,
    )
    if custom_prefixes:
        prefixes_label = ", ".join(f"`{p}_`" for p in custom_prefixes)
    else:
        prefixes_label = "无"

    lines: list[str] = [
        "# 数据字典索引",
        "",
        f"*自动生成于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "> 从 `docs/data_dictionary/tables/` 反向导出的表文档汇总（Gen 2 / framework_power）",
        "",
        "---",
        "",
        "## 统计",
        "",
        f"- 表总数: {len(rows)}",
        f"- 自定义表: {len(custom)}（前缀: {prefixes_label}）",
        f"- 标准表: {len(standard)}",
        "",
        "---",
        "",
    ]

    def _emit_group(title: str, group: list[dict]) -> None:
        lines.extend([f"## {title}", ""])
        lines.append("| 表名 | Schema Name | 字段数 | 关系数 | 说明 |")
        lines.append("|------|-------------|--------|--------|------|")
        for r in group:
            lines.append(
                f"| [{r['display']}](tables/{r['schema']}.md) | `{r['schema']}` | "
                f"{r['fields']} | {r['rels']} | {r['description']} |"
            )
        lines.extend(["", "---", ""])

    _emit_group("标准表", standard)
    _emit_group("自定义表", custom)

    optionsets_dir = out / "optionsets"
    if optionsets_dir.is_dir() and any(optionsets_dir.glob("*.md")):
        count = len(list(optionsets_dir.glob("*.md")))
        lines.extend([
            "## 全局选项集",
            "",
            f"见 [optionsets/](optionsets/) 目录（{count} 个）。",
            "",
        ])

    lines.extend([
        "## 快速导航",
        "",
        "- 单表数据字典: `tables/<schema>.md`",
        "- 全局选项集: `optionsets/<name>.md`",
        "",
    ])

    index_path = out / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


# ----------------------------------------------------------------- global optionset docs


def _raw_label_text(label_obj: Optional[dict], lang_code: int) -> str:
    """Extract a single-language string from a raw Dataverse Label object."""
    if not label_obj:
        return ""
    for loc in label_obj.get("LocalizedLabels") or []:
        if loc.get("LanguageCode") == lang_code and loc.get("Label"):
            return loc["Label"]
    ull = label_obj.get("UserLocalizedLabel")
    if ull and ull.get("Label"):
        return ull["Label"]
    locs = label_obj.get("LocalizedLabels") or []
    return locs[0].get("Label", "") if locs else ""


def optionset_to_markdown(raw: dict) -> str:
    """Render a raw global-optionset Dataverse dict into ``optionsets/<name>.md``.

    ``raw`` is the JSON returned by ``GlobalOptionSetDefinitions``: ``Name``,
    ``DisplayName``, optional ``Description``, and ``Options`` (each ``Value`` /
    ``Label`` / ``Color``).
    """
    name = raw.get("Name") or ""
    display_zh = _raw_label_text(raw.get("DisplayName"), LANGUAGE_ZH_CN)
    display_en = _raw_label_text(raw.get("DisplayName"), LANGUAGE_EN_US)
    if display_zh and display_en and display_zh != display_en:
        display = f"{display_zh} / {display_en}"
    else:
        display = display_zh or display_en or name
    description_zh = _raw_label_text(raw.get("Description"), LANGUAGE_ZH_CN)
    description_en = _raw_label_text(raw.get("Description"), LANGUAGE_EN_US)
    description = description_zh or description_en

    lines: list[str] = [
        f"# {display} (`{name}`)",
        "",
    ]
    if description:
        lines.append(f"**说明**: {description}")
        lines.append("")

    lines.extend(["---", "", "## 选项列表", ""])
    lines.append("| 值 | 中文标签 | 英文标签 | 颜色 |")
    lines.append("|----|----------|----------|------|")

    options = raw.get("Options") or []
    for opt in options:
        value = opt.get("Value")
        zh = _raw_label_text(opt.get("Label"), LANGUAGE_ZH_CN)
        en = _raw_label_text(opt.get("Label"), LANGUAGE_EN_US)
        color = opt.get("Color") or ""
        lines.append(f"| {value} | {zh} | {en} | {color} |")

    lines.extend(["", "---", "", "## 元数据", ""])
    lines.append(f"- **Schema Name**: `{name}`")
    lines.append("- **生成方式**: 从 Dataverse 环境逆向导出")
    lines.append(f"- **生成时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- **选项数**: {len(options)}")
    lines.append("")

    return "\n".join(lines)


def write_optionset_docs(optionsets_raw: list[dict], dict_dir: str | Path) -> list[Path]:
    """Write ``optionsets/<name>.md`` for each raw global-optionset dict.

    Args:
        optionsets_raw: Raw Dataverse dicts (e.g. from a client list call).
        dict_dir: Data dictionary root (``optionsets/`` is created under it).

    Returns:
        List of file paths written.
    """
    out = Path(dict_dir)
    optionsets_out = out / "optionsets"
    optionsets_out.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for raw in optionsets_raw:
        name = raw.get("Name") or ""
        if not name:
            continue
        md = optionset_to_markdown(raw)
        file_path = optionsets_out / f"{name}.md"
        file_path.write_text(md, encoding="utf-8")
        written.append(file_path)
    return written
