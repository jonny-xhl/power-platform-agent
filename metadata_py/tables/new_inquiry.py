"""CPQ 询价单 (new_inquiry) — framework_power table definition.

客户问价头（售前）。中标后经报价单(new_quote)转客户PO(new_sparepartscustomerpo)。
所有 lookup 指向**环境已存在**的实体（account/contact/new_country/systemuser/new_channel/
new_salesorganization）——只新建本表，不改任何已有表。
Regenerate: python -m framework_power reverse new_inquiry --env dev
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import AttributeType, Label, Option, RequiredLevel

TABLE: Table = Table(
    schema_name="new_inquiry",
    display_name=Label.bilingual("询价单", "Inquiry"),
    description=Label.bilingual("CPQ 售前询价单（客户问价头）", "CPQ pre-sales inquiry header"),
    ownership_type="UserOwned",
    columns=[
        Column("new_name", AttributeType.String, display_name=Label.bilingual("询价单名", "Inquiry Title"),
               required=RequiredLevel.ApplicationRequired, max_length=200, is_primary_name=True),
        Column("new_inquirydate", AttributeType.DateTime, display_name=Label.bilingual("询价日期", "Inquiry Date"),
               required=RequiredLevel.ApplicationRequired, format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_status", AttributeType.Picklist, display_name=Label.bilingual("状态", "Status"),
               required=RequiredLevel.ApplicationRequired, default_value=1, options=[
                   Option(1, Label.bilingual("草稿", "Draft")),
                   Option(2, Label.bilingual("已提交", "Submitted")),
                   Option(3, Label.bilingual("已报价", "Quoted")),
                   Option(4, Label.bilingual("已关闭", "Closed")),
                   Option(5, Label.bilingual("已作废", "Void")),
               ]),
        Column("new_expecteddelivery", AttributeType.DateTime,
               display_name=Label.bilingual("期望交期", "Expected Delivery"),
               format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_validity", AttributeType.DateTime, display_name=Label.bilingual("询价效期", "Valid Until"),
               format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_remarks", AttributeType.Memo, display_name=Label.bilingual("备注", "Remarks"), max_length=2000),
    ],
    relationships=[
        Relationship(schema_name="new_inquiry_new_account_id_account", referenced_entity="account",
                     referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_account_id", display_name=Label.bilingual("客户", "Customer"),
                                         target_entity="account", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_inquiry_new_contact_id_contact", referenced_entity="contact",
                     referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_contact_id", display_name=Label.bilingual("联系人", "Contact"),
                                         target_entity="contact")),
        Relationship(schema_name="new_inquiry_new_targetcountry_id_new_country", referenced_entity="new_country",
                     referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_targetcountry_id", display_name=Label.bilingual("目的国", "Target Country"),
                                         target_entity="new_country")),
        Relationship(schema_name="new_inquiry_new_salesperson_id_systemuser", referenced_entity="systemuser",
                     referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_salesperson_id", display_name=Label.bilingual("销售员", "Salesperson"),
                                         target_entity="systemuser")),
        Relationship(schema_name="new_inquiry_new_channel_id_new_channel", referenced_entity="new_channel",
                     referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_channel_id", display_name=Label.bilingual("渠道", "Channel"),
                                         target_entity="new_channel")),
        Relationship(schema_name="new_inquiry_new_salesorg_id_new_salesorganization",
                     referenced_entity="new_salesorganization", referencing_entity="new_inquiry",
                     lookup=LookupColumn("new_salesorg_id", display_name=Label.bilingual("销售组织", "Sales Organization"),
                                         target_entity="new_salesorganization")),
    ],
)
