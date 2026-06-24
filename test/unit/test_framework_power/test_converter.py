"""Unit tests for scripts/yaml_to_python_metadata.py (YAML -> framework_power migration)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import yaml_to_python_metadata as conv  # noqa: E402

pytestmark = pytest.mark.unit


def test_gen_column_string_primary():
    s = conv.gen_column({"schema_name": "new_name", "type": "String", "display_name": "名",
                         "required": True, "is_primary_name": True, "max_length": 100})
    assert "AttributeType.String" in s and "is_primary_name=True" in s and "max_length=100" in s


def test_gen_column_money_precision_source_currency():
    s = conv.gen_column({"schema_name": "new_amt", "type": "Money", "display_name": "金额",
                         "precision": 2, "precision_source": "transactioncurrency", "min_value": 0})
    assert "AttributeType.Money" in s and "precision_source=2" in s and "min_value=0" in s


def test_gen_column_datetime_date_only():
    s = conv.gen_column({"schema_name": "new_date", "type": "DateTime", "display_name": "日", "date_only": True})
    assert 'date_time_behavior="DateOnly"' in s and 'format="DateOnly"' in s


def test_gen_column_picklist_options():
    s = conv.gen_column({"schema_name": "new_status", "type": "Picklist", "display_name": "状态",
                         "options": [{"value": 1, "label": "草稿"}, {"value": 2, "label": "已批准"}]})
    assert "AttributeType.Picklist" in s and "Option(1, Label.zh('草稿'))" in s


def test_gen_column_skips_lookup():
    assert conv.gen_column({"schema_name": "new_x", "type": "Lookup", "display_name": "x"}) is None


def test_gen_relationship_manytoone_with_lookup():
    lookups = {"new_customerid": {"schema_name": "new_customerid", "display_name": "客户", "target": "account"}}
    rel = {"schema_name": "new_account_x", "related_entity": "account", "relationship_type": "ManyToOne",
           "display_name": "客户", "referencing_attribute": "new_customerid",
           "cascade_delete": "RemoveLink", "cascade_assign": "Cascade"}
    s = conv.gen_relationship(rel, lookups, "new_x")
    assert "referenced_entity='account'" in s
    assert "referencing_entity='new_x'" in s
    assert "LookupColumn(" in s and "target_entity='account'" in s
    assert "Cascade.Cascade_" in s and "Cascade.RemoveLink" in s


def test_gen_relationship_manytomany():
    rel = {"schema_name": "new_a_b", "related_entity": "new_b", "relationship_type": "ManyToMany",
           "display_name": "AB"}
    s = conv.gen_relationship(rel, {}, "new_a")
    assert 'type="ManyToMany"' in s and "referencing_entity='new_a'" in s


def test_gen_relationship_no_lookup_is_comment():
    rel = {"schema_name": "new_x_y", "related_entity": "new_y", "relationship_type": "ManyToOne",
           "referencing_attribute": "missing"}
    s = conv.gen_relationship(rel, {}, "new_x")
    assert s.startswith("# TODO")


def test_gen_table_source_compiles():
    data = {
        "schema": {"schema_name": "new_Thing", "display_name": "事物", "description": "d", "ownership_type": "UserOwned"},
        "attributes": [
            {"schema_name": "new_name", "type": "String", "display_name": "名", "is_primary_name": True},
            {"schema_name": "new_amt", "type": "Money", "display_name": "额", "precision_source": "transactioncurrency"},
        ],
        "relationships": [],
    }
    source = conv.gen_table_source(data, "thing.yaml")
    # Must be syntactically valid Python.
    compile(source, "thing.py", "exec")
    assert "TABLE: Table = Table(" in source


def test_convert_file_skips_no_string_column(tmp_path):
    yaml_path = tmp_path / "stub.yaml"
    yaml_path.write_text(
        "schema:\n  schema_name: new_stub\n  display_name: x\nattributes: []\nrelationships: []\n",
        encoding="utf-8",
    )
    assert conv.convert_file(yaml_path, tmp_path / "out") is None
