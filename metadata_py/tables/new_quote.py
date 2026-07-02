"""CPQ 报价单 (new_quote) — framework_power table definition.

卖方正式报价头（带价/效期/条款）。1 询价 → N 报价；中标转客户PO(new_sparepartscustomerpo)。
所有 lookup 指向环境已存在实体；金额字段(Money)自动带交易币种(transactioncurrency 自动 provision)。
只新建本表，不改任何已有表。
Regenerate: python -m framework_power reverse new_quote --env dev
"""

from framework_power import Column, LookupColumn, Relationship, Table
from framework_power.models import AttributeType, Label, Option, RequiredLevel

TABLE: Table = Table(
    schema_name="new_quote",
    display_name=Label.bilingual("报价单", "Quote"),
    description=Label.bilingual("CPQ 售前正式报价单", "CPQ pre-sales formal quote"),
    ownership_type="UserOwned",
    columns=[
        Column("new_name", AttributeType.String, display_name=Label.bilingual("报价单号", "Quote Number"),
               required=RequiredLevel.ApplicationRequired, max_length=100, is_primary_name=True),
        Column("new_quotedate", AttributeType.DateTime, display_name=Label.bilingual("报价日期", "Quote Date"),
               required=RequiredLevel.ApplicationRequired, format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_validuntil", AttributeType.DateTime, display_name=Label.bilingual("报价效期", "Valid Until"),
               required=RequiredLevel.ApplicationRequired, format="DateOnly", date_time_behavior="DateOnly"),
        Column("new_status", AttributeType.Picklist, display_name=Label.bilingual("状态", "Status"),
               required=RequiredLevel.ApplicationRequired, default_value=1, options=[
                   Option(1, Label.bilingual("草稿", "Draft")),
                   Option(2, Label.bilingual("已提交", "Submitted")),
                   Option(3, Label.bilingual("已批准", "Approved")),
                   Option(4, Label.bilingual("已接受", "Accepted")),
                   Option(5, Label.bilingual("已拒绝", "Rejected")),
                   Option(6, Label.bilingual("已过期", "Expired")),
                   Option(7, Label.bilingual("已转单", "Converted")),
               ]),
        Column("new_totalamount", AttributeType.Money, display_name=Label.bilingual("整单汇总", "Total Amount"),
               precision=2),
        Column("new_totaldiscount", AttributeType.Money, display_name=Label.bilingual("整单折扣", "Total Discount"),
               precision=2),
        Column("new_approvalstatus", AttributeType.Picklist, display_name=Label.bilingual("审批状态", "Approval Status"),
               default_value=1, options=[
                   Option(1, Label.bilingual("草稿", "Draft")),
                   Option(2, Label.bilingual("待审核", "Pending Review")),
                   Option(3, Label.bilingual("已审核", "Approved")),
                   Option(4, Label.bilingual("已拒绝", "Rejected")),
               ]),
        Column("new_paymentterms", AttributeType.Picklist, display_name=Label.bilingual("付款条款", "Payment Terms"),
               options=[
                   Option(1, Label.bilingual("预付100%", "100% Advance")),
                   Option(2, Label.bilingual("货到付款", "Cash on Delivery")),
                   Option(3, Label.bilingual("月结30天", "Net 30")),
                   Option(4, Label.bilingual("月结60天", "Net 60")),
                   Option(5, Label.bilingual("信用证", "Letter of Credit")),
               ]),
        Column("new_remarks", AttributeType.Memo, display_name=Label.bilingual("备注", "Remarks"), max_length=2000),
    ],
    relationships=[
        Relationship(schema_name="new_quote_new_inquiry_id_new_inquiry", referenced_entity="new_inquiry",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_inquiry_id", display_name=Label.bilingual("来源询价", "Source Inquiry"),
                                         target_entity="new_inquiry")),
        Relationship(schema_name="new_quote_new_account_id_account", referenced_entity="account",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_account_id", display_name=Label.bilingual("客户", "Customer"),
                                         target_entity="account", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_quote_new_contact_id_contact", referenced_entity="contact",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_contact_id", display_name=Label.bilingual("联系人", "Contact"),
                                         target_entity="contact")),
        Relationship(schema_name="new_quote_new_pricelist_id_new_pricelist", referenced_entity="new_pricelist",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_pricelist_id", display_name=Label.bilingual("价目表", "Price List"),
                                         target_entity="new_pricelist", required=RequiredLevel.ApplicationRequired)),
        Relationship(schema_name="new_quote_new_shippingterm_id_new_shippingterm",
                     referenced_entity="new_shippingterm", referencing_entity="new_quote",
                     lookup=LookupColumn("new_shippingterm_id", display_name=Label.bilingual("贸易条款", "Shipping Term"),
                                         target_entity="new_shippingterm")),
        Relationship(schema_name="new_quote_new_targetcountry_id_new_country", referenced_entity="new_country",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_targetcountry_id", display_name=Label.bilingual("目的国", "Target Country"),
                                         target_entity="new_country")),
        Relationship(schema_name="new_quote_new_salesperson_id_systemuser", referenced_entity="systemuser",
                     referencing_entity="new_quote",
                     lookup=LookupColumn("new_salesperson_id", display_name=Label.bilingual("销售员", "Salesperson"),
                                         target_entity="systemuser")),
        Relationship(schema_name="new_quote_new_convertedpo_id_new_sparepartscustomerpo",
                     referenced_entity="new_sparepartscustomerpo", referencing_entity="new_quote",
                     lookup=LookupColumn("new_convertedpo_id", display_name=Label.bilingual("转出PO", "Converted PO"),
                                         target_entity="new_sparepartscustomerpo")),
    ],
)
