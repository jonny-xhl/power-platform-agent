"""Migrated from metadata/tables/contact.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='contact',
    display_name=Label.zh('联系人'),
    description=Label.zh('存储联系人信息'),
    ownership_type='UserOwned',
    has_activities=True,
    has_notes=True,
    is_audit_enabled=True,
    columns=[
        Column('new_first_name', AttributeType.String, display_name=Label.zh('名'), description=Label.zh('联系人的名字'), required=RequiredLevel.ApplicationRequired, max_length=50),
        Column('new_last_name', AttributeType.String, display_name=Label.zh('姓'), description=Label.zh('联系人的姓氏'), required=RequiredLevel.ApplicationRequired, is_primary_name=True, max_length=50),
        Column('new_email', AttributeType.String, display_name=Label.zh('电子邮件'), description=Label.zh('主要电子邮件地址'), required=RequiredLevel.ApplicationRequired, max_length=100),
        Column('new_phone', AttributeType.String, display_name=Label.zh('电话'), description=Label.zh('主要电话号码'), required=RequiredLevel.None_, max_length=50),
        Column('new_mobile', AttributeType.String, display_name=Label.zh('手机'), description=Label.zh('手机号码'), required=RequiredLevel.None_, max_length=50),
    ],
    relationships=[
        # TODO: relationship 'new_contact_account' (1:N) has no lookup_attribute in YAML; define its LookupColumn manually,
    ],
)
