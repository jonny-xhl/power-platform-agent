"""CPQ 询价明细 (new_inquirydetail) — framework_power table definition.

询价单的行项目（每个问价产品，不带价）。只新建本表，不改任何已有表。
Regenerate: python -m framework_power reverse new_inquirydetail --env dev
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import AttributeType, Label, RequiredLevel

TABLE: Table = Table(
    schema_name="new_inquirydetail",
    display_name=Label.bilingual("询价明细", "Inquiry Line"),
    description=Label.bilingual("CPQ 询价单行项目（问价产品，不带价）", "CPQ inquiry line (product asked, no price)"),
    ownership_type="UserOwned",
    columns=[
        Column("new_name", AttributeType.String, display_name=Label.bilingual("明细名", "Line Title"),
               required=RequiredLevel.ApplicationRequired, max_length=200, is_primary_name=True),
        Column("new_qty", AttributeType.Integer, display_name=Label.bilingual("数量", "Quantity"),
               required=RequiredLevel.ApplicationRequired, min_value=0),
        Column("new_requesteddelivery", AttributeType.DateTime,
               display_name=Label.bilingual("期望交期", "Requested Delivery"),
               format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_remarks", AttributeType.Memo, display_name=Label.bilingual("备注", "Remarks"),
               description=Label.bilingual("规格/颜色/配置说明", "Spec/color/config notes"), max_length=2000),
    ],
    relationships=[
        Relationship(schema_name="new_inquirydetail_new_inquiry_id_new_inquiry", referenced_entity="new_inquiry",
                     referencing_entity="new_inquirydetail",
                     lookup=LookupColumn("new_inquiry_id", display_name=Label.bilingual("询价单", "Inquiry"),
                                         target_entity="new_inquiry", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_inquirydetail_new_product_id_new_product", referenced_entity="new_product",
                     referencing_entity="new_inquirydetail",
                     lookup=LookupColumn("new_product_id", display_name=Label.bilingual("产品", "Product"),
                                         target_entity="new_product", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_inquirydetail_new_vehiclemodel_id_new_vehiclemodel",
                     referenced_entity="new_vehiclemodel", referencing_entity="new_inquirydetail",
                     lookup=LookupColumn("new_vehiclemodel_id", display_name=Label.bilingual("车型", "Vehicle Model"),
                                         target_entity="new_vehiclemodel")),
    ],
)
