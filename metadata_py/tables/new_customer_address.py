"""Migrated from metadata/tables/new_customer_address.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='new_customer_address',
    display_name=Label.zh('客户地址'),
    description=Label.zh('记录客户的地址信息，支持审批流程和多级区域管理'),
    ownership_type='UserOwned',
    is_audit_enabled=True,
    columns=[
        Column('new_name', AttributeType.Memo, display_name=Label.zh('地址全称'), description=Label.zh('地址完整名称'), required=RequiredLevel.None_, is_primary_name=True, max_length=300),
        Column('new_address', AttributeType.Memo, display_name=Label.zh('详细地址'), description=Label.zh('详细地址信息'), required=RequiredLevel.None_, max_length=500),
        Column('new_contact', AttributeType.String, display_name=Label.zh('联系人'), description=Label.zh('地址联系人'), required=RequiredLevel.None_, max_length=100),
        Column('new_contactphone', AttributeType.String, display_name=Label.zh('联系电话'), description=Label.zh('联系人电话'), required=RequiredLevel.None_, max_length=100),
        Column('new_type', AttributeType.Picklist, display_name=Label.zh('地址类型'), description=Label.zh('地址分类类型'), required=RequiredLevel.None_, options=[Option(1, Label.zh('我的地址')), Option(2, Label.zh('门店地址')), Option(3, Label.zh('短交通订单收货地址'))]),
        Column('new_appro_process', AttributeType.Picklist, display_name=Label.zh('审批流程'), description=Label.zh('当前审批流程状态'), required=RequiredLevel.None_, options=[Option(1, Label.zh('未知'))]),
        Column('new_approvalstatus', AttributeType.Picklist, display_name=Label.zh('审核状态'), description=Label.zh('地址审核状态'), required=RequiredLevel.None_, options=[Option(1, Label.zh('已创建')), Option(2, Label.zh('审核中')), Option(3, Label.zh('审核通过')), Option(4, Label.zh('审核不通过'))]),
        Column('new_approved_time', AttributeType.DateTime, display_name=Label.zh('审核时间'), description=Label.zh('审核通过的时间'), required=RequiredLevel.None_),
        Column('new_submit_time', AttributeType.DateTime, display_name=Label.zh('提交时间'), description=Label.zh('提交审核的时间'), required=RequiredLevel.None_),
        Column('new_last_approve_time', AttributeType.DateTime, display_name=Label.zh('上一次审批时间'), description=Label.zh('最近一次审批的时间'), required=RequiredLevel.None_),
        Column('new_curr_approvestep_name', AttributeType.String, display_name=Label.zh('当前审批步骤'), description=Label.zh('当前审批步骤名称'), required=RequiredLevel.None_, max_length=100),
        Column('new_curr_approvestep_user', AttributeType.String, display_name=Label.zh('当前审批人'), description=Label.zh('当前审批人姓名'), required=RequiredLevel.None_, max_length=100),
        Column('new_last_approvestep_name', AttributeType.String, display_name=Label.zh('上一个审批步骤'), description=Label.zh('上一个审批步骤名称'), required=RequiredLevel.None_, max_length=100),
        Column('new_last_approvestep_user', AttributeType.String, display_name=Label.zh('上一个审批人'), description=Label.zh('上一个审批人姓名'), required=RequiredLevel.None_, max_length=100),
    ],
    relationships=[
        Relationship(schema_name='new_account_new_customer_address', referenced_entity='account', referencing_entity='new_customer_address', lookup=LookupColumn('new_account_id', display_name=Label.zh('客户'), target_entity='account', description=Label.zh('关联的客户'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_businessunit_new_customer_address_approvaldept', referenced_entity='businessunit', referencing_entity='new_customer_address', lookup=LookupColumn('new_approvaldept_id', display_name=Label.zh('签核部门'), target_entity='businessunit', description=Label.zh('签核审批部门'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_salesorganization_new_customer_address', referenced_entity='new_salesorganization', referencing_entity='new_customer_address', lookup=LookupColumn('new_businessunit_id', display_name=Label.zh('销售组织'), target_entity='new_salesorganization', description=Label.zh('所属销售组织'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_city_new_customer_address', referenced_entity='new_city', referencing_entity='new_customer_address', lookup=LookupColumn('new_city_id', display_name=Label.zh('所属城市'), target_entity='new_city', description=Label.zh('所属城市'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_country_new_customer_address', referenced_entity='new_country', referencing_entity='new_customer_address', lookup=LookupColumn('new_country_id', display_name=Label.zh('所属国家'), target_entity='new_country', description=Label.zh('所属国家'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_county_new_customer_address', referenced_entity='new_county', referencing_entity='new_customer_address', lookup=LookupColumn('new_county_id', display_name=Label.zh('所属区县'), target_entity='new_county', description=Label.zh('所属区县'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_province_new_customer_address', referenced_entity='new_province', referencing_entity='new_customer_address', lookup=LookupColumn('new_province_id', display_name=Label.zh('所属省份'), target_entity='new_province', description=Label.zh('所属省份'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_businessunit_new_customer_address_head', referenced_entity='businessunit', referencing_entity='new_customer_address', lookup=LookupColumn('new_headbusinessunit_id', display_name=Label.zh('负责人业务部门'), target_entity='businessunit', description=Label.zh('负责人所属业务部门'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_businessunit_new_customer_address_second', referenced_entity='businessunit', referencing_entity='new_customer_address', lookup=LookupColumn('new_secondbusinessunit_id', display_name=Label.zh('二级业务部门'), target_entity='businessunit', description=Label.zh('二级业务部门'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
    ],
)
