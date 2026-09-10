"""Unit tests for framework_power.codegen (Table -> Python source, round-trip)."""

import pytest

from framework_power import Column, LookupColumn, Relationship, Table, table_to_python_source
from framework_power.codegen import emit_column, emit_label
from framework_power.models import (
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Label,
    LocalizedLabel,
    Option,
    RequiredLevel,
)

pytestmark = pytest.mark.unit


def _sample_table() -> Table:
    return Table(
        schema_name="new_Thing",
        display_name=Label.bilingual("事物", "Thing"),
        description=Label.en("A thing"),
        has_notes=True,
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"),
                   is_primary_name=True, required=RequiredLevel.ApplicationRequired, max_length=200),
            Column("new_Status", AttributeType.Picklist, display_name=Label.zh("状态"),
                   options=[Option(1, Label.bilingual("草稿", "Draft")), Option(2, Label.zh("已批准"))]),
            Column("new_Active", AttributeType.Boolean, display_name=Label.zh("有效"),
                   default_value=True,
                   boolean_labels=BooleanLabels(Label.bilingual("是", "Yes"), Label.zh("否"))),
        ],
        relationships=[
            Relationship(schema_name="new_Thing_Account", referenced_entity="account",
                         referencing_entity="new_thing",
                         lookup=LookupColumn("new_AccountId", Label.bilingual("客户", "Account"), target_entity="account"),
                         cascade=CascadeConfig(delete=Cascade.RemoveLink)),
        ],
    )


def test_emit_label_variants():
    assert emit_label(Label.zh("名")) == "Label.zh('名')"
    assert emit_label(Label.en("Name")) == "Label.en('Name')"
    assert emit_label(Label.bilingual("名", "Name")) == "Label.bilingual('名', 'Name')"
    assert emit_label(None) == "None"
    explicit = emit_label(Label([LocalizedLabel("x", 1031)]))
    assert explicit.startswith("Label([") and "1031" in explicit


def test_table_to_python_source_round_trips():
    table = _sample_table()
    src = table_to_python_source(table)
    compile(src, "new_thing.py", "exec")  # syntactically valid
    ns: dict = {}
    exec(src, ns)
    t2 = ns["TABLE"]

    assert t2.schema_name == table.schema_name
    assert [c.schema_name for c in t2.columns] == [c.schema_name for c in table.columns]
    assert [c.type for c in t2.columns] == [c.type for c in table.columns]
    assert t2.columns[0].is_primary_name is True
    assert t2.columns[0].max_length == 200
    assert t2.columns[1].options[0].label.localized[0].text == "草稿"
    assert t2.columns[2].boolean_labels.true_label.localized[1].text == "Yes"
    # Bilingual label preserved on the entity.
    codes = {ll.language_code for ll in t2.display_name.localized}
    assert codes == {2052, 1033}
    # Relationship + cascade preserved.
    assert len(t2.relationships) == 1
    assert t2.relationships[0].cascade.delete == Cascade.RemoveLink
    assert t2.relationships[0].lookup.target_entity == "account"


def test_emit_column_preserves_global_optionset_name():
    """A Picklist bound to a global optionset must round-trip ``optionset_name``.

    Regression: ``emit_column`` used to emit only ``options=``, silently
    downgrading a global optionset to a local one on every reverse export —
    re-deploying to a fresh environment would then duplicate the optionset
    (ADR-009 / ADR-014 bind semantics lost).
    """
    col = Column(
        "new_SyncStatus",
        AttributeType.Picklist,
        display_name=Label.bilingual("同步状态", "Sync Status"),
        optionset_name="new_sync_status",
        options=[Option(279640000, Label.zh("未同步"))],
    )
    src = emit_column(col)

    assert "optionset_name='new_sync_status'" in src
    # Options snapshot is retained alongside the name (needed for doc generation).
    assert "options=[" in src


def test_emit_column_omits_optionset_name_for_local_picklist():
    """A local (entity-bound) Picklist has no ``optionset_name`` — inline only."""
    col = Column(
        "new_Status",
        AttributeType.Picklist,
        display_name=Label.bilingual("状态", "Status"),
        options=[Option(1, Label.bilingual("草稿", "Draft"))],
    )
    src = emit_column(col)

    assert "optionset_name" not in src
    assert "options=[" in src
