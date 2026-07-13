"""Appointment table — custom engagement fields (HKL CCRM Page 21 "Engagements" tab).

Extends the STANDARD ``appointment`` activity entity with the columns the Figma Engagements
grid needs (that aren't OOB appointment fields): Engagement ID / Engagement Type /
Engagement Channel / HKL PIC. OOB fields reused by the view: ``subject`` (Subject) and
``scheduledstart`` (Engagement Date). Only custom (``new_*``) fields are deployed.
"""

from framework_power import (
    AttributeType,
    Column,
    Label,
    LookupColumn,
    Option,
    Relationship,
    Table,
)

TABLE = Table(
    schema_name="appointment",
    display_name=Label.bilingual("Appointment", "Appointment"),
    columns=[
        Column(
            "new_EngagementId",
            AttributeType.String,
            display_name=Label.bilingual("Engagement ID", "Engagement ID"),
            max_length=50,
        ),
        Column(
            "new_EngagementType",
            AttributeType.Picklist,
            display_name=Label.bilingual("Engagement Type", "Engagement Type"),
            options=[
                Option(100000000, Label.bilingual("Casual Chat", "Casual Chat")),
                Option(100000001, Label.bilingual("Meeting", "Meeting")),
                Option(100000002, Label.bilingual("Festive Event", "Festive Event")),
            ],
        ),
        Column(
            "new_EngagementChannel",
            AttributeType.Picklist,
            display_name=Label.bilingual("Engagement Channel", "Engagement Channel"),
            options=[
                Option(100000000, Label.bilingual("Phone Call", "Phone Call")),
                Option(100000001, Label.bilingual("Virtual Meeting", "Virtual Meeting")),
                Option(100000002, Label.bilingual("In-person Meeting", "In-person Meeting")),
            ],
        ),
    ],
    relationships=[
        # HKL PIC (person responsible) — lookup from appointment to systemuser.
        Relationship(
            schema_name="new_Appointment_HklPic",
            type="OneToMany",
            referenced_entity="systemuser",
            referencing_entity="appointment",
            lookup=LookupColumn(
                "new_HklPic",
                display_name=Label.bilingual("HKL PIC", "HKL PIC"),
                target_entity="systemuser",
            ),
        ),
    ],
)
