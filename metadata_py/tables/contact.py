"""Contact table — custom fields for HKL CCRM Page 21 (Figma "2.3 View Tenant Contact").

Extends the STANDARD ``contact`` entity with four custom fields shown on the Contact form
Summary tab: Contact Code, Tenant Code, HKL PIC (lookup → systemuser), Last Engagement Date.
OOB fields (firstname / lastname / jobtitle / emailaddress1 / etc.) are intentionally NOT
listed — they already exist; ``deploy_table`` only creates custom (``new_*``) columns and
skips standard ones (reference-only).
"""

from framework_power import (
    AttributeType,
    Column,
    Label,
    LookupColumn,
    Relationship,
    Table,
)

TABLE = Table(
    schema_name="contact",
    display_name=Label.bilingual("Contact", "Contact"),
    columns=[
        Column(
            "new_ContactCode",
            AttributeType.String,
            display_name=Label.bilingual("Contact ID", "Contact ID"),
            max_length=50,
        ),
        Column(
            "new_TenantCode",
            AttributeType.String,
            display_name=Label.bilingual("Tenant ID", "Tenant ID"),
            max_length=50,
        ),
        Column(
            "new_LastEngagementDate",
            AttributeType.DateTime,
            display_name=Label.bilingual("Last Engagement Date", "Last Engagement Date"),
            format="DateOnly",
            date_time_behavior="DateOnly",
        ),
    ],
    relationships=[
        # HKL PIC = "Person In Charge" — a lookup from contact to systemuser.
        Relationship(
            schema_name="new_Contact_HklPic",
            type="OneToMany",
            referenced_entity="systemuser",
            referencing_entity="contact",
            lookup=LookupColumn(
                "new_HklPic",
                display_name=Label.bilingual("HKL PIC", "HKL PIC"),
                target_entity="systemuser",
            ),
        ),
    ],
)
