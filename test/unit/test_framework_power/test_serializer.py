"""Unit tests for framework_power.serializer (pure, no client/network)."""

import pytest

from framework_power.models import (
    AlternateKey,
    AttributeType,
    BooleanLabels,
    Cascade,
    CascadeConfig,
    Column,
    Label,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)
from framework_power.serializer import (
    build_attribute_patch,
    build_picklist_option_diff,
    serialize_alternate_key,
    serialize_boolean_optionset,
    serialize_column,
    serialize_entity_patch,
    serialize_label,
    serialize_relationship,
    serialize_table_for_create,
    serialize_updatable,
)

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------- labels


def test_serialize_label_multilang():
    label = serialize_label(Label.bilingual("项目预算", "Project Budget"))
    assert label["@odata.type"] == "Microsoft.Dynamics.CRM.Label"
    codes = {(ll["LanguageCode"], ll["Label"]) for ll in label["LocalizedLabels"]}
    assert codes == {(2052, "项目预算"), (1033, "Project Budget")}


def test_serialize_label_str_passthrough():
    label = serialize_label("名称")
    assert [(ll["LanguageCode"], ll["Label"]) for ll in label["LocalizedLabels"]] == [(2052, "名称")]


def test_serialize_label_none():
    assert serialize_label(None) is None


# ----------------------------------------------------------------- columns


def test_serialize_string_primary():
    col = Column(
        "new_Name", AttributeType.String,
        display_name=Label.bilingual("名称", "Name"),
        is_primary_name=True, max_length=200,
    )
    out = serialize_column(col, is_primary_name=True)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.StringAttributeMetadata"
    assert out["SchemaName"] == "new_Name"
    assert out["FormatName"] == {"Value": "Text"}
    assert out["MaxLength"] == 200
    assert out["IsPrimaryName"] is True
    assert out["RequiredLevel"]["Value"] == "None"


def test_serialize_column_audit_and_search_flags():
    out = serialize_column(Column(
        "new_BusinessKey",
        AttributeType.String,
        display_name=Label.bilingual("业务唯一键", "Business Key"),
        is_audit_enabled=True,
        is_searchable=True,
    ))
    assert out["IsAuditEnabled"] == {"Value": True}
    assert out["IsValidForAdvancedFind"] == {"Value": True}


def test_serialize_alternate_key():
    out = serialize_alternate_key(AlternateKey(
        schema_name="new_RollingForecast_BusinessKey",
        columns=["new_BusinessKey"],
        display_name=Label.bilingual("业务唯一键", "Business Key"),
    ))
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.EntityKeyMetadata"
    assert out["SchemaName"] == "new_RollingForecast_BusinessKey"
    assert out["KeyAttributes"] == ["new_BusinessKey"]
    assert "DisplayName" in out


def test_serialize_money():
    col = Column(
        "new_Amount", AttributeType.Money,
        display_name=Label.bilingual("金额", "Amount"),
        precision=2, precision_source=2, min_value=0, max_value=100,
    )
    out = serialize_column(col)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.MoneyAttributeMetadata"
    assert out["Precision"] == 2
    assert out["PrecisionSource"] == 2
    assert out["MinValue"] == 0
    assert out["MaxValue"] == 100


def test_serialize_decimal_and_double():
    dec = serialize_column(Column("new_Rate", AttributeType.Decimal, display_name=Label.zh("率"), precision=4))
    assert dec["@odata.type"] == "Microsoft.Dynamics.CRM.DecimalAttributeMetadata"
    assert dec["Precision"] == 4
    dbl = serialize_column(Column("new_Score", AttributeType.Double, display_name=Label.zh("分")))
    assert dbl["@odata.type"] == "Microsoft.Dynamics.CRM.DoubleAttributeMetadata"


def test_serialize_integer_bigint():
    int_ = serialize_column(Column("new_Count", AttributeType.Integer, display_name=Label.zh("数"), min_value=0, max_value=999))
    assert int_["@odata.type"] == "Microsoft.Dynamics.CRM.IntegerAttributeMetadata"
    assert int_["MinValue"] == 0 and int_["MaxValue"] == 999
    big = serialize_column(Column("new_Big", AttributeType.BigInt, display_name=Label.zh("大数")))
    assert big["@odata.type"] == "Microsoft.Dynamics.CRM.BigIntAttributeMetadata"


def test_serialize_picklist():
    col = Column(
        "new_Status", AttributeType.Picklist,
        display_name=Label.bilingual("状态", "Status"),
        options=[Option(1, Label.bilingual("草稿", "Draft")), Option(2, Label.bilingual("已批准", "Approved"))],
    )
    out = serialize_column(col)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
    assert out["OptionSet"]["IsGlobal"] is False
    assert [o["Value"] for o in out["OptionSet"]["Options"]] == [1, 2]
    first = out["OptionSet"]["Options"][0]["Label"]["LocalizedLabels"]
    assert (1033, "Draft") in {(ll["LanguageCode"], ll["Label"]) for ll in first}


def test_serialize_picklist_global_optionset_reference():
    col = Column(
        "new_BusinessGroupId", AttributeType.Picklist,
        display_name=Label.bilingual("商务组", "Business Group"),
        optionset_name="new_salesgroup",
        options=[],
    )
    out = serialize_column(col)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
    assert out["OptionSet"]["IsGlobal"] is True
    assert out["OptionSet"]["Name"] == "new_salesgroup"
    assert "Options" not in out["OptionSet"]


def test_serialize_picklist_global_optionset_bind():
    """ADR-014: with a resolved MetadataId the attribute-create payload binds the
    global optionset; an inline OptionSet reference block is rejected (0x80048403)."""
    col = Column(
        "new_BusinessGroupId", AttributeType.Picklist,
        display_name=Label.bilingual("商务组", "Business Group"),
        optionset_name="new_salesgroup",
        options=[],
    )
    out = serialize_column(
        col, global_optionset_ids={"new_salesgroup": "11111111-2222-3333-4444-555555555555"}
    )
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
    assert (
        out["GlobalOptionSet@odata.bind"]
        == "/GlobalOptionSetDefinitions(11111111-2222-3333-4444-555555555555)"
    )
    assert "OptionSet" not in out


def test_serialize_table_for_create_binds_global_optionsets():
    """ADR-014: entity-create Attributes bind referenced global optionsets too."""
    table = Table(
        schema_name="new_Demo",
        display_name=Label.bilingual("演示", "Demo"),
        columns=[
            Column(
                "new_Name", AttributeType.String,
                display_name=Label.bilingual("名称", "Name"),
                is_primary_name=True,
            ),
            Column(
                "new_BusinessGroupId", AttributeType.Picklist,
                display_name=Label.bilingual("商务组", "Business Group"),
                optionset_name="new_salesgroup",
            ),
        ],
    )
    out = serialize_table_for_create(table, global_optionset_ids={"new_salesgroup": "osid-1"})
    picklist = next(a for a in out["Attributes"] if a["SchemaName"] == "new_BusinessGroupId")
    assert picklist["GlobalOptionSet@odata.bind"] == "/GlobalOptionSetDefinitions(osid-1)"
    assert "OptionSet" not in picklist


def test_serialize_boolean():
    col = Column(
        "new_Active", AttributeType.Boolean,
        display_name=Label.bilingual("是否有效", "Is Active"),
        default_value=True,
        boolean_labels=BooleanLabels(Label.bilingual("是", "Yes"), Label.bilingual("否", "No")),
    )
    out = serialize_column(col)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.BooleanAttributeMetadata"
    assert out["DefaultValue"] is True
    os_ = out["OptionSet"]
    assert os_["@odata.type"] == "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata"
    assert os_["TrueOption"]["Value"] == 1 and os_["FalseOption"]["Value"] == 0


def test_serialize_boolean_optionset_multilang():
    os_ = serialize_boolean_optionset(BooleanLabels(Label.bilingual("是", "Yes"), Label.bilingual("否", "No")))
    true_codes = {(ll["LanguageCode"], ll["Label"]) for ll in os_["TrueOption"]["Label"]["LocalizedLabels"]}
    assert true_codes == {(2052, "是"), (1033, "Yes")}


def test_serialize_datetime():
    col = Column(
        "new_Start", AttributeType.DateTime,
        display_name=Label.bilingual("开始", "Start"),
        date_time_behavior="DateOnly",
    )
    out = serialize_column(col)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata"
    assert out["Format"] == "DateOnly"
    assert out["DateTimeBehavior"] == {"Value": "DateOnly"}


def test_serialize_memo_and_file():
    memo = serialize_column(Column("new_Notes", AttributeType.Memo, display_name=Label.zh("备注"), max_length=2000))
    assert memo["@odata.type"] == "Microsoft.Dynamics.CRM.MemoAttributeMetadata"
    assert memo["MaxLength"] == 2000
    file_ = serialize_column(Column("new_Doc", AttributeType.File, display_name=Label.zh("文件"), max_size_in_kb=512))
    assert file_["@odata.type"] == "Microsoft.Dynamics.CRM.FileAttributeMetadata"
    assert file_["MaxSizeInKB"] == 512


# ----------------------------------------------------------------- table


def test_serialize_table_create_auto_primary_name():
    table = Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        columns=[
            Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"), max_length=200),
            Column("new_Amount", AttributeType.Money, display_name=Label.bilingual("金额", "Amount")),
        ],
    )
    out = serialize_table_for_create(table)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.EntityMetadata"
    assert out["SchemaName"] == "new_ProjectBudget"
    # Multi-language entity labels.
    dn = {(ll["LanguageCode"], ll["Label"]) for ll in out["DisplayName"]["LocalizedLabels"]}
    assert (2052, "项目预算") in dn and (1033, "Project Budget") in dn
    # Auto-picked the first String column as primary name.
    primaries = [a for a in out["Attributes"] if a.get("IsPrimaryName") is True]
    assert len(primaries) == 1
    assert primaries[0]["SchemaName"] == "new_Name"


def test_serialize_table_no_string_raises():
    table = Table(
        schema_name="new_X",
        display_name=Label.zh("X"),
        columns=[Column("new_Amount", AttributeType.Money, display_name=Label.zh("金额"))],
    )
    with pytest.raises(ValueError):
        serialize_table_for_create(table)


def test_serialize_entity_patch():
    table = Table(
        schema_name="new_ProjectBudget",
        display_name=Label.bilingual("项目预算", "Project Budget"),
        has_notes=True, is_audit_enabled=True,
    )
    patch = serialize_entity_patch(table)
    assert patch["HasNotes"] is True
    assert patch["IsAuditEnabled"] == {"Value": True}
    assert "DisplayName" in patch


# ----------------------------------------------------------------- relationships


def test_serialize_relationship_onetomany_deep_insert():
    rel = Relationship(
        schema_name="new_ProjectBudget_Account",
        referenced_entity="account",
        referencing_entity="new_projectbudget",
        lookup=LookupColumn("new_AccountId", display_name=Label.bilingual("客户", "Account"), target_entity="account"),
        cascade=CascadeConfig(delete=Cascade.RemoveLink),
    )
    out = serialize_relationship(rel, referenced_attribute="accountid")
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata"
    assert out["ReferencedEntity"] == "account"
    assert out["ReferencingEntity"] == "new_projectbudget"
    assert out["ReferencedAttribute"] == "accountid"
    assert out["CascadeConfiguration"]["Delete"] == "RemoveLink"
    assert out["Lookup"]["Targets"] == ["account"]
    assert out["Lookup"]["SchemaName"] == "new_AccountId"


def test_serialize_relationship_manytomany():
    rel = Relationship(
        schema_name="new_employee_project",
        type="ManyToMany",
        referencing_entity="new_employee",
        referenced_entity="new_project",
    )
    out = serialize_relationship(rel)
    assert out["@odata.type"] == "Microsoft.Dynamics.CRM.ManyToManyRelationshipMetadata"
    assert out["Entity1LogicalName"] == "new_employee"
    assert out["Entity2LogicalName"] == "new_project"
    assert out["IntersectEntityName"] == "new_employee_project"


# ----------------------------------------------------------------- updatable / patch


def test_serialize_updatable_whitelist_excludes_readonly():
    col = Column("new_Status", AttributeType.Picklist, display_name=Label.zh("状态"),
                 options=[Option(1, Label.zh("一"))])
    up = serialize_updatable(col)
    assert "@odata.type" not in up
    assert "SchemaName" not in up
    assert "OptionSet" not in up
    assert "DisplayName" in up and "RequiredLevel" in up


def test_build_attribute_patch_detects_scalar_change():
    col = Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"), max_length=300)
    existing = {
        "LogicalName": "new_name",
        "MaxLength": 100,
        "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"},
        "DisplayName": serialize_label(Label.bilingual("名称", "Name")),
    }
    patch = build_attribute_patch(col, existing)
    assert patch is not None
    assert patch.get("MaxLength") == 300


def test_build_picklist_option_diff_is_non_destructive_and_language_scoped():
    col = Column(
        "new_Status",
        AttributeType.Picklist,
        display_name=Label.bilingual("状态", "Status"),
        options=[
            Option(1, Label.bilingual("草稿", "Draft")),
            Option(2, Label.bilingual("已批准", "Approved")),
            Option(3, Label.bilingual("已关闭", "Closed")),
        ],
    )
    existing = {
        "OptionSet": {
            "Options": [
                {
                    "Value": 1,
                    "Label": {
                        "LocalizedLabels": [
                            {"LanguageCode": 2052, "Label": "草案"},
                            {"LanguageCode": 1033, "Label": "Draft"},
                            {"LanguageCode": 1041, "Label": "ドラフト"},
                        ]
                    },
                },
                {"Value": 2, "Label": serialize_label(Label.bilingual("已批准", "Approved"))},
                {"Value": 9, "Label": serialize_label(Label.bilingual("远端保留", "Remote"))},
            ]
        }
    }

    diff = build_picklist_option_diff(col, existing)

    assert [item["value"] for item in diff["insert"]] == [3]
    assert diff["update"] == [{
        "value": 1,
        "label": serialize_label(Label.bilingual("草稿", "Draft")),
        "languages": [2052],
    }]
    assert diff["unchanged"] == [2]
    assert diff["remote_only"] == [9]


def test_build_picklist_option_diff_rejects_global_online_optionset():
    col = Column(
        "new_Status",
        AttributeType.Picklist,
        display_name=Label.zh("状态"),
        options=[Option(1, Label.zh("一"))],
    )
    with pytest.raises(ValueError, match="global online"):
        build_picklist_option_diff(
            col,
            {"OptionSet": {"IsGlobal": True, "Options": []}},
        )


def test_build_picklist_option_diff_rejects_duplicate_values():
    col = Column(
        "new_Status",
        AttributeType.Picklist,
        display_name=Label.zh("状态"),
        options=[Option(1, Label.zh("一")), Option(1, Label.zh("重复"))],
    )
    with pytest.raises(ValueError, match="duplicate option values"):
        build_picklist_option_diff(col, {"OptionSet": {"Options": []}})


def test_build_attribute_patch_ignores_label_metadataid_noise():
    col = Column("new_Name", AttributeType.String, display_name=Label.bilingual("名称", "Name"), max_length=100)
    desired_label = serialize_label(Label.bilingual("名称", "Name"))
    # Add MetadataId noise the API returns; the diff must treat labels as equal.
    for ll in desired_label["LocalizedLabels"]:
        ll["MetadataId"] = "some-guid"
    existing = {
        "LogicalName": "new_name",
        "MaxLength": 100,
        "FormatName": {"Value": "Text"},
        "RequiredLevel": {"Value": "None"},
        "DisplayName": desired_label,
    }
    assert build_attribute_patch(col, existing) is None


# ------------------------------------------------- picklist default value (ADR-017)


def _motorcycle_mark_col(*, default_value=2) -> Column:
    return Column(
        "new_MotorcycleMark", AttributeType.Picklist,
        display_name=Label.bilingual("电摩/非电摩标记", "Motorcycle Mark"),
        required=RequiredLevel.ApplicationRequired,
        default_value=default_value,
        options=[
            Option(1, Label.bilingual("电摩", "E-Motorcycle")),
            Option(2, Label.bilingual("非电摩", "Non E-Motorcycle")),
        ],
    )


def test_serialize_picklist_emits_default_form_value():
    """A picklist default is written as ``DefaultFormValue``.

    ``DefaultValue`` is a Boolean-only property: emitting that name instead made
    Dataverse ignore it, so every declared picklist default was silently dropped
    and the column was created with "no default".
    """
    out = serialize_column(_motorcycle_mark_col())
    assert out["DefaultFormValue"] == 2
    assert "DefaultValue" not in out


def test_serialize_picklist_global_bound_still_carries_default():
    """The default lives on the attribute, so a global-bound picklist keeps it too."""
    col = Column(
        "new_Flag", AttributeType.Picklist,
        display_name=Label.en("Flag"),
        default_value=1,
        optionset_name="new_isornotselect",
    )
    out = serialize_column(col, global_optionset_ids={"new_isornotselect": "osid-9"})
    assert out["GlobalOptionSet@odata.bind"] == "/GlobalOptionSetDefinitions(osid-9)"
    assert out["DefaultFormValue"] == 1


def test_serialize_picklist_no_default_omits_property():
    """``None`` means "no default" — the property must not be sent as -1 or 0."""
    col = _motorcycle_mark_col(default_value=None)
    assert "DefaultFormValue" not in serialize_column(col)


def test_serialize_picklist_boolean_default_is_ignored(caplog):
    """``default_value=False`` on a picklist is an authoring mistake.

    ``False`` coerces to option value 0, which is rarely a real option, so it is
    skipped with a warning rather than pushed to Dataverse.
    """
    col = _motorcycle_mark_col(default_value=False)
    with caplog.at_level("WARNING"):
        out = serialize_column(col)
    assert "DefaultFormValue" not in out
    assert any("boolean default_value" in r.getMessage() for r in caplog.records)


def test_serialize_updatable_picklist_includes_default_form_value():
    """The patch overlay must carry DefaultFormValue, or deploy can never fix a drift."""
    assert serialize_updatable(_motorcycle_mark_col())["DefaultFormValue"] == 2


def test_build_attribute_patch_detects_default_form_value_drift():
    """-1 (Dataverse's "no default") is a real drift; a matching value is not."""
    col = _motorcycle_mark_col()
    existing = {
        "LogicalName": "new_motorcyclemark",
        "DefaultFormValue": 2,
        "RequiredLevel": {"Value": "ApplicationRequired"},
        "DisplayName": serialize_label(col.display_name),
    }
    assert "DefaultFormValue" not in (build_attribute_patch(col, existing) or {})

    drifted = dict(existing, DefaultFormValue=-1)
    assert build_attribute_patch(col, drifted)["DefaultFormValue"] == 2
