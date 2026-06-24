"""Migrated from metadata/tables/new_ord_forecastorder.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='new_ord_forecastorder',
    display_name=Label.zh('代理商预测单'),
    description=Label.zh('代理商预测单'),
    ownership_type='UserOwned',
    columns=[
        Column('new_name', AttributeType.String, display_name=Label.zh('销售预测单号'), description=Label.zh('销售预测单号'), required=RequiredLevel.ApplicationRequired, is_primary_name=True, max_length=100),
        Column('new_status', AttributeType.Picklist, display_name=Label.zh('预测单状态'), description=Label.zh('预测单状态'), required=RequiredLevel.ApplicationRequired, options=[Option(1, Label.zh('草稿')), Option(2, Label.zh('生效')), Option(3, Label.zh('失效')), Option(4, Label.zh('已锁单'))], default_value=1),
        Column('new_submittime', AttributeType.DateTime, display_name=Label.zh('预测提交时间'), description=Label.zh('预测提交时间'), required=RequiredLevel.ApplicationRequired, date_time_behavior='UserLocal', format='DateAndTime'),
        Column('new_year', AttributeType.Integer, display_name=Label.zh('预测年份'), description=Label.zh('预测年份'), required=RequiredLevel.ApplicationRequired, min_value=-2147483648, max_value=2147483647),
        Column('new_month', AttributeType.Integer, display_name=Label.zh('预测月份'), description=Label.zh('预测月份'), required=RequiredLevel.ApplicationRequired, min_value=-2147483648, max_value=2147483647),
        Column('new_totalamount', AttributeType.Money, display_name=Label.zh('预测单总金额'), description=Label.zh('预测单总金额'), required=RequiredLevel.ApplicationRequired, precision=2, min_value=-922337203685477, max_value=922337203685477),
        Column('new_totalqty', AttributeType.Decimal, display_name=Label.zh('预测总数量'), description=Label.zh('预测总数量'), required=RequiredLevel.ApplicationRequired, precision=2, min_value=-100000000000, max_value=100000000000),
        Column('new_remark', AttributeType.Memo, display_name=Label.zh('备注'), description=Label.zh('备注'), required=RequiredLevel.ApplicationRequired, max_length=2000),
    ],
    relationships=[
        Relationship(schema_name='new_ord_forecastorder_businessunitid_businessunit', referenced_entity='businessunit', referencing_entity='new_ord_forecastorder', lookup=LookupColumn('new_businessunitid', display_name=Label.zh('销售组织'), target_entity='businessunit', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
    ],
)
