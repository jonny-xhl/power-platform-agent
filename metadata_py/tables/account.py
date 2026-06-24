"""Migrated from metadata/tables/account.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='account',
    display_name=Label.zh('客户账户'),
    description=Label.zh('存储客户账户信息，包括账户编号、余额和状态'),
    ownership_type='UserOwned',
    columns=[
        Column('new_account_number', AttributeType.String, display_name=Label.zh('账户编号'), description=Label.zh('唯一账户编号'), required=RequiredLevel.ApplicationRequired, is_primary_name=True, max_length=50),
        Column('new_account_name', AttributeType.String, display_name=Label.zh('账户名称'), description=Label.zh('账户名称'), required=RequiredLevel.ApplicationRequired, max_length=100),
        Column('new_balance', AttributeType.Money, display_name=Label.zh('账户余额'), description=Label.zh('当前账户余额'), required=RequiredLevel.None_, precision=2, min_value=0),
        Column('new_status', AttributeType.Picklist, display_name=Label.zh('状态'), description=Label.zh('账户状态'), required=RequiredLevel.ApplicationRequired, options=[Option(100000000, Label.zh('活跃')), Option(100000001, Label.zh('冻结')), Option(100000002, Label.zh('关闭'))]),
        Column('new_account_type', AttributeType.Picklist, display_name=Label.zh('账户类型'), description=Label.zh('客户账户类型'), required=RequiredLevel.None_, options=[Option(100000000, Label.zh('个人')), Option(100000001, Label.zh('企业')), Option(100000002, Label.zh('政府'))]),
        Column('new_credit_limit', AttributeType.Money, display_name=Label.zh('信用额度'), description=Label.zh('客户信用额度'), required=RequiredLevel.None_, precision=2, min_value=0),
        Column('new_opened_date', AttributeType.DateTime, display_name=Label.zh('开户日期'), description=Label.zh('账户开立日期'), required=RequiredLevel.None_),
        Column('new_notes', AttributeType.Memo, display_name=Label.zh('备注'), description=Label.zh('账户备注信息'), required=RequiredLevel.None_, max_length=2000),
    ],
    relationships=[
        # TODO: relationship 'new_account_contact' (1:N) has no lookup_attribute in YAML; define its LookupColumn manually,
        # TODO: relationship 'new_primary_contact' (1:N) has no lookup_attribute in YAML; define its LookupColumn manually,
        Relationship(schema_name='new_account_product', type="ManyToMany", referencing_entity='account', referenced_entity='product', display_name=Label.zh('账户产品')),
    ],
)
