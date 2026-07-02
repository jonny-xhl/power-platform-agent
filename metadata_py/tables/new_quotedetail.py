"""CPQ 报价明细 (new_quotedetail) — framework_power table definition.

报价单的行项目（带价：单价取自价目表 + 折扣 + 行小计）。只新建本表，不改任何已有表。
Regenerate: python -m framework_power reverse new_quotedetail --env dev
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import AttributeType, Label, RequiredLevel

TABLE: Table = Table(
    schema_name="new_quotedetail",
    display_name=Label.bilingual("报价明细", "Quote Line"),
    description=Label.bilingual("CPQ 报价单行项目（带价）", "CPQ quote line (priced)"),
    ownership_type="UserOwned",
    columns=[
        Column("new_name", AttributeType.String, display_name=Label.bilingual("明细名", "Line Title"),
               required=RequiredLevel.ApplicationRequired, max_length=200, is_primary_name=True),
        Column("new_qty", AttributeType.Integer, display_name=Label.bilingual("数量", "Quantity"),
               required=RequiredLevel.ApplicationRequired, min_value=0),
        Column("new_unitprice", AttributeType.Money, display_name=Label.bilingual("单价", "Unit Price"),
               description=Label.bilingual("取自 new_pricelistdetails.new_salesprice", "From price list"),
               precision=2),
        Column("new_standardprice", AttributeType.Money, display_name=Label.bilingual("标准价", "Standard Price"),
               precision=2),
        Column("new_discount", AttributeType.Decimal, display_name=Label.bilingual("行折扣(%)", "Line Discount %"),
               precision=2, min_value=0, max_value=100),
        Column("new_linetotal", AttributeType.Money, display_name=Label.bilingual("行小计", "Line Total"),
               description=Label.bilingual("= qty × unitprice × (1 − 折扣)", "= qty × unitprice × (1 − discount)"),
               precision=2),
        Column("new_requesteddelivery", AttributeType.DateTime,
               display_name=Label.bilingual("期望交期", "Requested Delivery"),
               format="DateOnly", date_time_behavior="DateOnly"),
    ],
    relationships=[
        Relationship(schema_name="new_quotedetail_new_quote_id_new_quote", referenced_entity="new_quote",
                     referencing_entity="new_quotedetail",
                     lookup=LookupColumn("new_quote_id", display_name=Label.bilingual("报价单", "Quote"),
                                         target_entity="new_quote", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_quotedetail_new_product_id_new_product", referenced_entity="new_product",
                     referencing_entity="new_quotedetail",
                     lookup=LookupColumn("new_product_id", display_name=Label.bilingual("产品", "Product"),
                                         target_entity="new_product", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_quotedetail_new_vehiclemodel_id_new_vehiclemodel",
                     referenced_entity="new_vehiclemodel", referencing_entity="new_quotedetail",
                     lookup=LookupColumn("new_vehiclemodel_id", display_name=Label.bilingual("车型", "Vehicle Model"),
                                         target_entity="new_vehiclemodel")),
    ],
)
