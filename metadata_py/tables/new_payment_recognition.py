"""Migrated from metadata/tables/payment_recognition.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='new_payment_recognition',
    display_name=Label.zh('认款单'),
    description=Label.zh('记录客户认款信息，关联订单、发票和客户，支持审批流程'),
    ownership_type='UserOwned',
    has_activities=True,
    has_notes=True,
    is_audit_enabled=True,
    columns=[
        Column('new_payment_number', AttributeType.String, display_name=Label.zh('认款单号'), description=Label.zh('认款单唯一编号'), required=RequiredLevel.ApplicationRequired, is_primary_name=True, max_length=50),
        Column('new_payment_date', AttributeType.DateTime, display_name=Label.zh('认款日期'), description=Label.zh('认款单创建日期'), required=RequiredLevel.ApplicationRequired, date_time_behavior="DateOnly", format="DateOnly"),
        Column('new_payment_amount', AttributeType.Money, display_name=Label.zh('认款金额'), description=Label.zh('本次认款金额'), required=RequiredLevel.ApplicationRequired, precision=2, precision_source=2, min_value=0),
        Column('new_remaining_amount', AttributeType.Money, display_name=Label.zh('剩余金额'), description=Label.zh('剩余未认款金额'), required=RequiredLevel.None_, precision=2, precision_source=2, min_value=0),
        Column('new_payment_type', AttributeType.Picklist, display_name=Label.zh('认款类型'), description=Label.zh('认款分类类型'), required=RequiredLevel.ApplicationRequired, options=[Option(100000000, Label.zh('预收款认款')), Option(100000001, Label.zh('发货认款')), Option(100000002, Label.zh('验收认款')), Option(100000003, Label.zh('尾款认款')), Option(100000004, Label.zh('其他认款'))]),
        Column('new_approval_status', AttributeType.Picklist, display_name=Label.zh('审批状态'), description=Label.zh('认款单审批状态'), required=RequiredLevel.ApplicationRequired, options=[Option(100000000, Label.zh('草稿')), Option(100000001, Label.zh('待审核')), Option(100000002, Label.zh('已审核')), Option(100000003, Label.zh('已拒绝')), Option(100000004, Label.zh('已撤回'))], default_value=100000000),
        Column('new_sales_order_number', AttributeType.String, display_name=Label.zh('销售订单号'), description=Label.zh('关联的销售订单编号'), required=RequiredLevel.None_, max_length=100),
        Column('new_invoice_number', AttributeType.String, display_name=Label.zh('发票号码'), description=Label.zh('关联的发票号码'), required=RequiredLevel.None_, max_length=100),
        Column('new_contract_number', AttributeType.String, display_name=Label.zh('合同编号'), description=Label.zh('关联的合同编号'), required=RequiredLevel.None_, max_length=100),
        Column('new_payment_method', AttributeType.Picklist, display_name=Label.zh('收款方式'), description=Label.zh('款项收款方式'), required=RequiredLevel.None_, options=[Option(100000000, Label.zh('银行转账')), Option(100000001, Label.zh('现金')), Option(100000002, Label.zh('支票')), Option(100000003, Label.zh('承兑汇票')), Option(100000004, Label.zh('其他'))]),
        Column('new_bank_account', AttributeType.String, display_name=Label.zh('收款银行'), description=Label.zh('收款银行账户'), required=RequiredLevel.None_, max_length=100),
        Column('new_payment_voucher', AttributeType.String, display_name=Label.zh('付款凭证号'), description=Label.zh('付款凭证编号'), required=RequiredLevel.None_, max_length=100),
        Column('new_approved_date', AttributeType.DateTime, display_name=Label.zh('审批日期'), description=Label.zh('审批通过日期'), required=RequiredLevel.None_, date_time_behavior="DateOnly", format="DateOnly"),
        Column('new_approval_comments', AttributeType.Memo, display_name=Label.zh('审批意见'), description=Label.zh('审批人意见'), required=RequiredLevel.None_, max_length=2000),
        Column('new_remarks', AttributeType.Memo, display_name=Label.zh('备注'), description=Label.zh('认款单备注信息'), required=RequiredLevel.None_, max_length=2000),
        Column('new_attachment_url', AttributeType.String, display_name=Label.zh('附件地址'), description=Label.zh('相关附件URL'), required=RequiredLevel.None_, max_length=500),
    ],
    relationships=[
        Relationship(schema_name='account_new_payment_recognition', referenced_entity='account', referencing_entity='new_payment_recognition', lookup=LookupColumn('new_customerid', display_name=Label.zh('客户'), target_entity='account', description=Label.zh('关联的客户'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.Cascade_, delete=Cascade.RemoveLink, reparent=Cascade.Cascade_, share=Cascade.Cascade_, unshare=Cascade.Cascade_)),
        Relationship(schema_name='new_systemuser_payment_recognition_handledby', referenced_entity='systemuser', referencing_entity='new_payment_recognition', lookup=LookupColumn('new_handledby', display_name=Label.zh('经办人'), target_entity='systemuser', description=Label.zh('认款单经办人'), required=RequiredLevel.ApplicationRequired), cascade=CascadeConfig(assign=Cascade.Cascade_, delete=Cascade.RemoveLink, reparent=Cascade.Cascade_, share=Cascade.Cascade_, unshare=Cascade.Cascade_)),
        Relationship(schema_name='new_systemuser_payment_recognition_approvedby', referenced_entity='systemuser', referencing_entity='new_payment_recognition', lookup=LookupColumn('new_approvedby', display_name=Label.zh('审批人'), target_entity='systemuser', description=Label.zh('认款单审批人'), required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.Cascade_, unshare=Cascade.Cascade_)),
    ],
)
