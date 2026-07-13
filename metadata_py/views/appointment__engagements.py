"""Appointment Public view "Engagements" (HKL CCRM Page 21).

Columns match the Figma Engagements grid exactly: Engagement ID / Subject / Engagement Type /
Engagement Channel / Engagement Date (→ scheduledstart) / HKL PIC. Used by the Contact form
Engagements tab sub-grid (``Contact_Appointments`` relationship scopes rows to the contact).
``object_type_code`` is auto-filled by ``sync_views`` from the env.
"""

from framework_power import QueryType, View, ViewColumn, ViewOrder

VIEW: View = View(
    name="Engagements",
    entity="appointment",
    primary_id="activityid",
    query_type=QueryType.Public,
    columns=[
        ViewColumn("new_engagementid", width=120),
        ViewColumn("subject", width=220),
        ViewColumn("new_engagementtype", width=140),
        ViewColumn("new_engagementchannel", width=150),
        ViewColumn("scheduledstart", width=140),
        ViewColumn("new_hklpic", width=140),
    ],
    orders=[ViewOrder("scheduledstart", descending=True)],
    grid_attrs={"name": "resultset", "jump": "subject", "select": "1", "icon": "1", "preview": "1"},
    row_attrs={"name": "result"},
)
