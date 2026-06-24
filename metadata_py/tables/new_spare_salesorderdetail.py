"""Migrated from metadata/tables/new_spare_salesorderdetail.yaml -> framework_power definition.

Schema names are preserved as-is (legacy lowercase). Add Label.bilingual +
English names where known. Regenerate via scripts/yaml_to_python_metadata.py.
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import (AttributeType, BooleanLabels, Cascade, CascadeConfig, Label, Option, RequiredLevel)

TABLE: Table = Table(
    schema_name='new_spare_salesorderdetail',
    display_name=Label.zh('备件销售订单明细'),
    description=Label.zh('备件销售订单明细表'),
    ownership_type='UserOwned',
    columns=[
        Column('new_budget_amount', AttributeType.Money, display_name=Label.zh('预算占用金额'), required=RequiredLevel.None_, precision=2),
        Column('new_credit_amount', AttributeType.Money, display_name=Label.zh('贷项总金额'), required=RequiredLevel.None_, precision=2),
        Column('new_total_loan', AttributeType.Money, display_name=Label.zh('行项目总额(借贷调整后)'), required=RequiredLevel.None_, precision=4),
        Column('new_total_payment', AttributeType.Money, display_name=Label.zh('销售总价'), required=RequiredLevel.None_, precision=4),
        Column('new_distributeqty', AttributeType.Decimal, display_name=Label.zh('今日分配数量'), required=RequiredLevel.None_, precision=2),
        Column('new_quota', AttributeType.Decimal, display_name=Label.zh('配货数量'), required=RequiredLevel.None_, precision=2, min_value=0, max_value=1000000000),
        Column('new_totaldistributeqty', AttributeType.Decimal, display_name=Label.zh('累计分配数量'), required=RequiredLevel.None_, precision=2),
        Column('new_undelivered_qty', AttributeType.Decimal, display_name=Label.zh('未交货数量'), required=RequiredLevel.None_, precision=2),
        Column('new_actual_qty', AttributeType.Decimal, display_name=Label.zh('实际出库数量'), required=RequiredLevel.None_, precision=2, min_value=0, max_value=1000000000),
        Column('new_sap_remaininventory', AttributeType.Decimal, display_name=Label.zh('SAP剩余数量'), required=RequiredLevel.None_, precision=0, min_value=0, max_value=100000000000),
        Column('new_sapprice', AttributeType.Money, display_name=Label.zh('sap成本金额'), required=RequiredLevel.None_, precision=4),
        Column('new_occupyinventory', AttributeType.Decimal, display_name=Label.zh('预打包占用库存数量'), required=RequiredLevel.None_, precision=0, min_value=0, max_value=100000000000),
        Column('new_material_sn', AttributeType.String, display_name=Label.zh('整车备件SN编码'), required=RequiredLevel.None_, max_length=100),
        Column('new_note', AttributeType.Memo, display_name=Label.zh('说明'), required=RequiredLevel.None_, max_length=2000),
        Column('new_commercialrobotprices_value', AttributeType.Money, display_name=Label.zh('商用机器人价格'), required=RequiredLevel.None_, precision=2),
        Column('new_denial_reason', AttributeType.String, display_name=Label.zh('拒绝原因'), required=RequiredLevel.None_, max_length=100),
        Column('new_discountedamount', AttributeType.Money, display_name=Label.zh('折后金额'), required=RequiredLevel.None_, precision=2),
        Column('new_dnstatus', AttributeType.Picklist, display_name=Label.zh('DN推单状态'), required=RequiredLevel.None_, options=[Option(1, Label.zh('待推单')), Option(2, Label.zh('部分推单')), Option(3, Label.zh('已推单'))], default_value=1),
        Column('new_erp_seq', AttributeType.String, display_name=Label.zh('ERP行项目号'), required=RequiredLevel.None_, max_length=100),
        Column('new_free_reason', AttributeType.String, display_name=Label.zh('免费原因'), required=RequiredLevel.None_, max_length=100),
        Column('new_ischangeqty', AttributeType.Boolean, display_name=Label.zh('交货明细是否变动'), description=Label.zh('标记交货明细是否发生变动'), required=RequiredLevel.None_, default_value=False, boolean_labels=BooleanLabels(Label.zh('是'), Label.zh('否'))),
        Column('new_ispresent', AttributeType.Boolean, display_name=Label.zh('是否为赠品'), description=Label.zh('标记是否为赠品'), required=RequiredLevel.None_, default_value=False, boolean_labels=BooleanLabels(Label.zh('是'), Label.zh('否'))),
        Column('new_lotno', AttributeType.String, display_name=Label.zh('批号'), required=RequiredLevel.None_, max_length=100),
        Column('new_oaorderlineno', AttributeType.String, display_name=Label.zh('OA订单行号'), required=RequiredLevel.None_, max_length=100),
        Column('new_ord_saleorderseq', AttributeType.String, display_name=Label.zh('原订单行'), required=RequiredLevel.None_, max_length=100),
        Column('new_ord_shipmentseq', AttributeType.String, display_name=Label.zh('发货单行号'), required=RequiredLevel.None_, max_length=100),
        Column('new_order_amount', AttributeType.Money, display_name=Label.zh('原订单额'), required=RequiredLevel.None_, precision=2),
        Column('new_originalorder_shippedqty', AttributeType.Decimal, display_name=Label.zh('原发货单行发货数量'), required=RequiredLevel.None_, precision=2),
        Column('new_originalqty', AttributeType.Decimal, display_name=Label.zh('原下单数量'), required=RequiredLevel.None_, precision=2),
        Column('new_remark', AttributeType.Memo, display_name=Label.zh('备注'), required=RequiredLevel.None_, max_length=500),
        Column('new_serial_number', AttributeType.String, display_name=Label.zh('VIN / SN'), required=RequiredLevel.None_, max_length=100),
        Column('new_vin', AttributeType.String, display_name=Label.zh('vin'), required=RequiredLevel.None_, max_length=100),
    ],
    relationships=[
        Relationship(schema_name='new_spare_salesorderdetail_new_account_id_account', referenced_entity='account', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_account_id', display_name=Label.zh('售达方'), target_entity='account', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_warehouse_id_new_warehouse', referenced_entity='new_warehouse', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_warehouse_id', display_name=Label.zh('仓库'), target_entity='new_warehouse', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_productgroup_id_new_productgroup', referenced_entity='new_productgroup', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_productgroup_id', display_name=Label.zh('产品系列'), target_entity='new_productgroup', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_producttype_id_new_producttype', referenced_entity='new_producttype', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_producttype_id', display_name=Label.zh('产品分类'), target_entity='new_producttype', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_factory_id_new_factory', referenced_entity='new_factory', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_factory_id', display_name=Label.zh('出货工厂'), target_entity='new_factory', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_ord_shipment_id_new_shipment', referenced_entity='new_shipment', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_ord_shipment_id', display_name=Label.zh('发货单'), target_entity='new_shipment', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_product_id_new_product', referenced_entity='new_product', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_product_id', display_name=Label.zh('产品名称'), target_entity='new_product', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
        Relationship(schema_name='new_spare_salesorderdetail_new_reseaon_id_new_ord_reason', referenced_entity='new_ord_reason', referencing_entity='new_spare_salesorderdetail', lookup=LookupColumn('new_reseaon_id', display_name=Label.zh('订单原因'), target_entity='new_ord_reason', required=RequiredLevel.None_), cascade=CascadeConfig(assign=Cascade.NoCascade, delete=Cascade.RemoveLink, reparent=Cascade.NoCascade, share=Cascade.NoCascade, unshare=Cascade.NoCascade)),
    ],
)
