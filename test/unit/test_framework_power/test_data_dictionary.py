"""
Unit tests for framework_power.data_dictionary module.

Tests the Gen 2 Python-first data dictionary generation:
- table_to_markdown() — single table → Markdown
- generate_index() — table list → index.md content
- generate_all_tables_summary() — table list → all_tables.md content
- generate_table_docs() — batch write to directory
"""

import tempfile
from pathlib import Path

import pytest

from framework_power.data_dictionary import (
    DEFAULT_DICTIONARY_DIR,
    generate_all_tables_summary,
    generate_index,
    generate_index_from_dir,
    generate_table_docs,
    optionset_to_markdown,
    table_to_markdown,
    write_optionset_docs,
)
from framework_power.models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Column,
    Label,
    LocalizedLabel,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)
from framework_power.registry import Definition


# ----------------------------------------------------------------- fixtures


def _make_simple_table() -> Table:
    """A minimal table for testing."""
    return Table(
        schema_name="new_Test",
        display_name=Label.bilingual("测试表", "Test Table"),
        description=Label.bilingual("测试用表", "A test table"),
        columns=[
            Column(
                "new_Name", AttributeType.String,
                display_name=Label.bilingual("名称", "Name"),
                is_primary_name=True,
                required=RequiredLevel.ApplicationRequired,
                max_length=200,
            ),
            Column(
                "new_Amount", AttributeType.Money,
                display_name=Label.bilingual("金额", "Amount"),
                precision=2, precision_source=2,
            ),
        ],
    )


def _make_full_table() -> Table:
    """A table with all column types, options, relationships, and features."""
    return Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        display_collection_name=Label.bilingual("项目预算", "Project Budgets"),
        description=Label.bilingual("项目预算主表", "Project budget header"),
        ownership_type="UserOwned",
        has_activities=True,
        has_notes=True,
        is_audit_enabled=True,
        is_quick_create_enabled=True,
        columns=[
            Column(
                "new_Name", AttributeType.String,
                display_name=Label.bilingual("预算名称", "Budget Name"),
                is_primary_name=True,
                required=RequiredLevel.ApplicationRequired,
                max_length=200,
            ),
            Column(
                "new_Amount", AttributeType.Money,
                display_name=Label.bilingual("预算金额", "Amount"),
                precision=2, precision_source=2, min_value=0, max_value=1e12,
                required=RequiredLevel.ApplicationRequired,
            ),
            Column(
                "new_Status", AttributeType.Picklist,
                display_name=Label.bilingual("状态", "Status"),
                default_value=1,
                options=[
                    Option(1, Label.bilingual("草稿", "Draft")),
                    Option(2, Label.bilingual("已批准", "Approved")),
                    Option(3, Label.bilingual("已关闭", "Closed")),
                ],
            ),
            Column(
                "new_IsActive", AttributeType.Boolean,
                display_name=Label.bilingual("是否有效", "Is Active"),
                default_value=True,
                boolean_labels=BooleanLabels(
                    true_label=Label.bilingual("是", "Yes"),
                    false_label=Label.bilingual("否", "No"),
                ),
            ),
            Column(
                "new_Count", AttributeType.Integer,
                display_name=Label.bilingual("数量", "Count"),
                min_value=0, max_value=999,
                required=RequiredLevel.Recommended,
            ),
            Column(
                "new_StartDate", AttributeType.DateTime,
                display_name=Label.bilingual("开始日期", "Start Date"),
                date_time_behavior="DateOnly", format="DateOnly",
            ),
            Column(
                "new_Notes", AttributeType.Memo,
                display_name=Label.bilingual("备注", "Notes"),
                max_length=2000,
            ),
        ],
        relationships=[
            Relationship(
                schema_name="new_ProjectBudget_Account",
                referenced_entity="account",
                referencing_entity="new_projectbudget",
                lookup=LookupColumn(
                    "new_AccountId",
                    display_name=Label.bilingual("客户", "Account"),
                    target_entity="account",
                    required=RequiredLevel.ApplicationRequired,
                ),
                cascade=CascadeConfig(delete=Cascade.RemoveLink, assign=Cascade.NoCascade),
            ),
        ],
    )


def _make_definition(table: Table, name: str = "test_table") -> Definition:
    """Wrap a Table into a Definition for batch tests."""
    return Definition(name=name, table=table, source=Path(f"metadata_py/tables/{name}.py"))


# ----------------------------------------------------------------- label helpers


class TestLabelHelpers:
    """Test the internal label extraction functions."""

    def test_label_zh_extraction(self):
        from framework_power.data_dictionary import _label_text, LANGUAGE_ZH_CN
        label = Label.bilingual("中文", "English")
        assert _label_text(label, LANGUAGE_ZH_CN) == "中文"

    def test_label_en_extraction(self):
        from framework_power.data_dictionary import _label_text, LANGUAGE_EN_US
        label = Label.bilingual("中文", "English")
        assert _label_text(label, LANGUAGE_EN_US) == "English"

    def test_label_none(self):
        from framework_power.data_dictionary import _label_text
        assert _label_text(None) == ""

    def test_label_both_different(self):
        from framework_power.data_dictionary import _label_both
        label = Label.bilingual("中文", "English")
        assert _label_both(label) == "中文 / English"

    def test_label_both_same(self):
        from framework_power.data_dictionary import _label_both
        label = Label.zh("Same")
        assert _label_both(label) == "Same"


# ----------------------------------------------------------------- type formatting


class TestTypeFormatting:
    """Test the internal type/required/options/cascade formatters."""

    def test_format_type_string_with_max_length(self):
        from framework_power.data_dictionary import _format_type
        col = Column("new_Name", AttributeType.String, display_name=Label.zh("x"), max_length=200)
        assert "200" in _format_type(col)
        assert "String" in _format_type(col)

    def test_format_type_money_with_precision(self):
        from framework_power.data_dictionary import _format_type
        col = Column("new_Amt", AttributeType.Money, display_name=Label.zh("x"), precision=2)
        result = _format_type(col)
        assert "precision" in result

    def test_format_type_datetime_with_format(self):
        from framework_power.data_dictionary import _format_type
        col = Column("new_Date", AttributeType.DateTime, display_name=Label.zh("x"), format="DateOnly")
        assert "DateOnly" in _format_type(col)

    def test_format_required_application(self):
        from framework_power.data_dictionary import _format_required
        col = Column("x", AttributeType.String, display_name=Label.zh("x"),
                     required=RequiredLevel.ApplicationRequired)
        assert _format_required(col) == "必填"

    def test_format_required_recommended(self):
        from framework_power.data_dictionary import _format_required
        col = Column("x", AttributeType.String, display_name=Label.zh("x"),
                     required=RequiredLevel.Recommended)
        assert _format_required(col) == "推荐"

    def test_format_required_none(self):
        from framework_power.data_dictionary import _format_required
        col = Column("x", AttributeType.String, display_name=Label.zh("x"))
        assert _format_required(col) == "否"

    def test_format_options_picklist(self):
        from framework_power.data_dictionary import _format_options
        col = Column("x", AttributeType.Picklist, display_name=Label.zh("x"),
                     options=[
                         Option(1, Label.bilingual("草稿", "Draft")),
                         Option(2, Label.bilingual("已批准", "Approved")),
                     ])
        result = _format_options(col)
        assert "草稿" in result
        assert "1" in result

    def test_format_options_boolean(self):
        from framework_power.data_dictionary import _format_options
        col = Column("x", AttributeType.Boolean, display_name=Label.zh("x"),
                     boolean_labels=BooleanLabels(
                         true_label=Label.bilingual("是", "Yes"),
                         false_label=Label.bilingual("否", "No"),
                     ))
        result = _format_options(col)
        assert "True=" in result
        assert "是" in result

    def test_format_cascade_defaults(self):
        from framework_power.data_dictionary import _format_cascade
        cascade = CascadeConfig()  # all defaults
        assert _format_cascade(cascade) == "defaults"

    def test_format_cascade_custom(self):
        from framework_power.data_dictionary import _format_cascade
        # delete=Restrict is NOT the default (default is RemoveLink)
        cascade = CascadeConfig(delete=Cascade.Restrict)
        result = _format_cascade(cascade)
        assert "delete=Restrict" in result


# ----------------------------------------------------------------- table_to_markdown


class TestTableToMarkdown:

    def test_generates_markdown_string(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_schema_name(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "new_Test" in md

    def test_contains_display_name_bilingual(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "测试表" in md
        assert "Test Table" in md

    def test_contains_description(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "测试用表" in md

    def test_contains_ownership_type(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "UserOwned" in md

    def test_contains_column_names(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "new_Name" in md
        assert "new_Amount" in md
        assert "new_Status" in md
        assert "new_IsActive" in md

    def test_contains_type_constraints(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "200" in md  # max_length for String
        assert "precision" in md  # precision for Money

    def test_contains_picklist_options(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "草稿" in md
        assert "已批准" in md
        assert "已关闭" in md

    def test_contains_boolean_labels(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "True=" in md
        assert "False=" in md

    def test_contains_required_level(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "必填" in md
        assert "推荐" in md

    def test_contains_relationship_section(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "查找关系" in md
        assert "new_AccountId" in md
        assert "new_ProjectBudget_Account" in md
        assert "account" in md

    def test_contains_feature_flags(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "Activities" in md
        assert "Notes" in md
        assert "Audit" in md
        assert "Quick Create" in md

    def test_contains_source_file_link(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "test_table.py" in md

    def test_no_source_file_link(self):
        table = _make_simple_table()
        md = table_to_markdown(table, source_name=None)
        assert "Dataverse" in md  # "从 Dataverse 环境逆向导出"
        assert "test_table.py" not in md

    def test_contains_field_count(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "字段数" in md
        assert "7" in md  # 7 columns in _make_full_table

    def test_contains_relationship_count(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name="test_table")
        assert "关系数" in md
        assert "1" in md


# ----------------------------------------------------------------- generate_index


class TestGenerateIndex:

    def test_generates_index_string(self):
        defs = {"a": _make_definition(_make_simple_table(), "a")}
        md = generate_index(defs)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_header(self):
        defs = {"a": _make_definition(_make_simple_table(), "a")}
        md = generate_index(defs)
        assert "数据字典索引" in md

    def test_contains_table_entry(self):
        defs = {"a": _make_definition(_make_simple_table(), "a")}
        md = generate_index(defs)
        assert "new_Test" in md
        assert "测试表" in md

    def test_contains_field_count(self):
        defs = {"a": _make_definition(_make_full_table(), "a")}
        md = generate_index(defs)
        assert "7" in md  # _make_full_table has 7 columns

    def test_multiple_tables_sorted(self):
        defs = {
            "z_table": _make_definition(Table("new_Z", display_name=Label.zh("Z")), "z_table"),
            "a_table": _make_definition(Table("new_A", display_name=Label.zh("A")), "a_table"),
        }
        md = generate_index(defs)
        # a_table should appear before z_table
        assert md.index("new_A") < md.index("new_Z")

    def test_contains_gen2_note(self):
        defs = {"a": _make_definition(_make_simple_table(), "a")}
        md = generate_index(defs)
        assert "Gen 2" in md or "framework_power" in md


# ----------------------------------------------------------------- generate_all_tables_summary


class TestGenerateAllTablesSummary:

    def test_generates_summary_string(self):
        defs = {"a": _make_definition(_make_simple_table(), "a")}
        md = generate_all_tables_summary(defs)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_table_details(self):
        defs = {"pb": _make_definition(_make_full_table(), "pb")}
        md = generate_all_tables_summary(defs)
        assert "new_ProjectBudget" in md
        assert "项目预算" in md

    def test_contains_link(self):
        defs = {"pb": _make_definition(_make_full_table(), "pb")}
        md = generate_all_tables_summary(defs)
        assert "tables/new_ProjectBudget.md" in md


# ----------------------------------------------------------------- generate_table_docs


class TestGenerateTableDocs:

    def test_writes_files_to_directory(self):
        defs = {"pb": _make_definition(_make_full_table(), "pb")}
        with tempfile.TemporaryDirectory() as tmpdir:
            written = generate_table_docs(defs, output_dir=tmpdir)
            assert len(written) > 0
            # Check files exist
            tables_dir = Path(tmpdir) / "tables"
            assert tables_dir.exists()
            assert (tables_dir / "new_ProjectBudget.md").exists()
            assert (Path(tmpdir) / "index.md").exists()
            assert (Path(tmpdir) / "all_tables.md").exists()

    def test_file_content_is_valid_markdown(self):
        defs = {"pb": _make_definition(_make_full_table(), "pb")}
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_table_docs(defs, output_dir=tmpdir)
            content = (Path(tmpdir) / "tables" / "new_ProjectBudget.md").read_text(encoding="utf-8")
            assert content.startswith("# ")
            assert "## 字段列表" in content

    def test_source_link_is_relative(self):
        defs = {"pb": _make_definition(_make_full_table(), "pb")}
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_table_docs(defs, output_dir=tmpdir, source_dir="metadata_py/tables")
            content = (Path(tmpdir) / "tables" / "new_ProjectBudget.md").read_text(encoding="utf-8")
            assert "../../metadata_py/tables/pb.py" in content

    def test_multiple_tables(self):
        defs = {
            "a": _make_definition(_make_simple_table(), "a"),
            "b": _make_definition(_make_full_table(), "b"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            written = generate_table_docs(defs, output_dir=tmpdir)
            # 2 table docs + all_tables.md + index.md = 4 files
            assert len(written) == 4


# ----------------------------------------------------------------- edge cases


class TestEdgeCases:

    def test_table_with_no_columns(self):
        table = Table("new_Empty", display_name=Label.zh("空表"))
        md = table_to_markdown(table, source_name="empty")
        assert "new_Empty" in md
        assert "字段数" in md
        assert "0" in md  # 0 columns

    def test_table_with_zh_only_label(self):
        table = Table("new_Zh", display_name=Label.zh("纯中文"))
        md = table_to_markdown(table, source_name="zh")
        assert "纯中文" in md
        # Should not have " / " separator for single-language
        assert "纯中文 / " not in md

    def test_table_with_en_only_label(self):
        table = Table("new_En", display_name=Label.en("EnglishOnly"))
        md = table_to_markdown(table, source_name="en")
        assert "EnglishOnly" in md

    def test_many_to_many_relationship(self):
        table = Table(
            "new_Intersection",
            display_name=Label.zh("交集表"),
            relationships=[
                Relationship(
                    schema_name="new_Test_M2M",
                    type="ManyToMany",
                    referenced_entity="other",
                    intersect_entity_name="new_test_m2m",
                ),
            ],
        )
        md = table_to_markdown(table, source_name="m2m")
        assert "多对多关系" in md
        assert "new_test_m2m" in md


# ----------------------------------------------------------------- reverse-path: index from dir


def _make_raw_optionset(
    name: str = "new_status",
    zh: str = "状态",
    en: str = "Status",
    options=None,
) -> dict:
    """Build a raw Dataverse global-optionset dict for render/write tests."""
    def label(z: str, e: str) -> dict:
        return {"LocalizedLabels": [
            {"Label": z, "LanguageCode": 2052},
            {"Label": e, "LanguageCode": 1033},
        ]}
    if options is None:
        options = [
            {"Value": 1, "Label": label("草稿", "Draft"), "Color": "#FF0000"},
            {"Value": 2, "Label": label("已批准", "Approved"), "Color": ""},
        ]
    return {"Name": name, "DisplayName": label(zh, en), "Options": options}


class TestParseTableMarkdown:
    """Test the regex parser that derives index rows from table docs on disk."""

    def test_parses_generated_doc(self):
        table = _make_full_table()
        md = table_to_markdown(table, source_name=None)
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "tables" / "new_ProjectBudget.md"
            p.parent.mkdir(parents=True)
            p.write_text(md, encoding="utf-8")
            from framework_power.data_dictionary import _parse_table_markdown
            info = _parse_table_markdown(p)
            assert info["schema"] == "new_ProjectBudget"
            assert info["display"] == "项目预算 / Project Budget"
            assert info["fields"] == 7
            assert info["rels"] == 1
            assert "项目预算主表" in info["description"]

    def test_missing_file_degrades_gracefully(self):
        from framework_power.data_dictionary import _parse_table_markdown
        info = _parse_table_markdown(Path("nonexistent.md"))
        assert info["schema"] == "nonexistent"
        assert info["fields"] == 0


class TestGenerateIndexFromDir:
    """Test generate_index_from_dir — reverse-path index from on-disk table docs."""

    def test_writes_index_with_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tables_dir = Path(tmpdir) / "tables"
            tables_dir.mkdir()
            # one custom + one standard
            (tables_dir / "new_Alpha.md").write_text(
                "# 阿尔法 / Alpha (`new_Alpha`)\n\n**说明**: 自定义表\n\n---\n\n## 元数据\n\n- **字段数**: 3\n- **关系数**: 1\n",
                encoding="utf-8",
            )
            (tables_dir / "account.md").write_text(
                "# 客户 (`account`)\n\n---\n\n## 元数据\n\n- **字段数**: 50\n- **关系数**: 5\n",
                encoding="utf-8",
            )
            idx = generate_index_from_dir(tmpdir, prefix="new")
            content = idx.read_text(encoding="utf-8")
            assert "表总数: 2" in content
            assert "自定义表 (`new_`): 1" in content
            assert "标准表: 1" in content
            # custom and standard land in separate grouped sections
            assert "## 标准表" in content
            assert "## 自定义表 (`new_`)" in content
            assert "new_Alpha" in content
            assert "account" in content

    def test_includes_optionsets_section_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "tables").mkdir()
            opt_dir = Path(tmpdir) / "optionsets"
            opt_dir.mkdir()
            (opt_dir / "new_status.md").write_text("# x (`new_status`)", encoding="utf-8")
            (opt_dir / "new_type.md").write_text("# y (`new_type`)", encoding="utf-8")
            content = generate_index_from_dir(tmpdir, prefix="new").read_text(encoding="utf-8")
            assert "## 全局选项集" in content
            assert "2 个" in content

    def test_no_optionsets_section_when_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "tables").mkdir()
            content = generate_index_from_dir(tmpdir, prefix="new").read_text(encoding="utf-8")
            assert "## 全局选项集" not in content


# ----------------------------------------------------------------- global optionset docs


class TestOptionsetToMarkdown:

    def test_renders_name_and_options(self):
        md = optionset_to_markdown(_make_raw_optionset())
        assert "# 状态 / Status (`new_status`)" in md
        assert "| 值 | 中文标签 | 英文标签 | 颜色 |" in md
        assert "草稿" in md and "Draft" in md
        assert "#FF0000" in md  # color rendered
        assert "选项数" in md

    def test_single_language_display(self):
        raw = _make_raw_optionset(zh="状态", en="状态")
        md = optionset_to_markdown(raw)
        # zh == en → no " / " separator
        assert "状态 / 状态" not in md
        assert "`new_status`" in md

    def test_no_description_is_ok(self):
        raw = _make_raw_optionset()
        md = optionset_to_markdown(raw)
        assert "## 选项列表" in md


class TestWriteOptionsetDocs:

    def test_writes_one_file_per_optionset(self):
        raws = [
            _make_raw_optionset("new_a", "甲", "A"),
            _make_raw_optionset("new_b", "乙", "B"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_optionset_docs(raws, tmpdir)
            assert len(written) == 2
            opt_dir = Path(tmpdir) / "optionsets"
            assert (opt_dir / "new_a.md").exists()
            assert (opt_dir / "new_b.md").exists()
            content = (opt_dir / "new_a.md").read_text(encoding="utf-8")
            assert "`new_a`" in content

    def test_skips_nameless_optionset(self):
        raw = _make_raw_optionset()
        raw["Name"] = ""
        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_optionset_docs([raw], tmpdir)
            assert len(written) == 0
