"""Contact Tag table (HKL CCRM Page 21) — tags applied to a contact.

Each row = one tag on a contact (e.g. "Pet owner" / "Sport Lover"), shown in the Contact
form Summary tab's "Contact Tag" custom HTML pane (colored-circle rows). 1:N from ``contact``
(via ``new_ContactId`` lookup). Fields mirror the Figma tag row: name + abbreviation +
color (for the circle), sub-label (remark), source.
"""

from framework_power import (
    AttributeType,
    Column,
    Label,
    LookupColumn,
    Option,
    Relationship,
    RequiredLevel,
    Table,
)

TABLE = Table(
    schema_name="new_ContactTag",
    display_name=Label.bilingual("Contact Tag", "Contact Tag"),
    is_quick_create_enabled=True,
    columns=[
        Column(
            "new_Name",
            AttributeType.String,
            display_name=Label.bilingual("Tag Name", "Tag Name"),
            is_primary_name=True,
            required=RequiredLevel.ApplicationRequired,
            max_length=200,
        ),
        Column(
            "new_Abbreviation",
            AttributeType.String,
            display_name=Label.bilingual("Abbreviation", "Abbreviation"),
            max_length=2,
        ),
        Column(
            "new_Color",
            AttributeType.Picklist,
            display_name=Label.bilingual("Color", "Color"),
            options=[
                Option(100000000, Label.bilingual("Red", "Red")),
                Option(100000001, Label.bilingual("Orange", "Orange")),
                Option(100000002, Label.bilingual("Yellow", "Yellow")),
                Option(100000003, Label.bilingual("Green", "Green")),
                Option(100000004, Label.bilingual("Blue", "Blue")),
                Option(100000005, Label.bilingual("Purple", "Purple")),
            ],
        ),
        Column(
            "new_SubLabel",
            AttributeType.String,
            display_name=Label.bilingual("Sub Label", "Sub Label"),
            max_length=200,
        ),
        Column(
            "new_Source",
            AttributeType.String,
            display_name=Label.bilingual("Source", "Source")),
    ],
    relationships=[
        # contact (1) -> new_ContactTag (N): each tag belongs to one contact.
        Relationship(
            schema_name="new_ContactTag_Contact",
            type="OneToMany",
            referenced_entity="contact",
            referencing_entity="new_contacttag",
            lookup=LookupColumn(
                "new_ContactId",
                display_name=Label.bilingual("Contact", "Contact"),
                target_entity="contact",
                required=RequiredLevel.ApplicationRequired,
            ),
        ),
    ],
)
