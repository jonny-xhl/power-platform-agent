"""Contact form — "Summary and Engagements" (HKL CCRM Page 21).

Summary tab (per Figma Image #2): left = "Contact Information" as a SINGLE-column stacked
list (one field per row: First Name → Remarks); right = "Tenant" pane (parentcustomerid
lookup) + "Contact Tag" pane (embeds new_/html/contact_tags.html, PassParameters=true so the
page receives the contact id).
Engagements tab: sub-grid of related appointments via the custom "Engagements" view
(columns: Engagement ID / Subject / Engagement Type / Engagement Channel / Engagement Date /
HKL PIC) + Contact_Appointments relationship.
"""

from framework_power import (
    Form,
    FormCell,
    FormControl,
    FormColumn,
    FormLabel,
    FormRow,
    FormSection,
    FormTab,
    FormType,
)
from framework_power.form_xml import SUBGRID_CLASSID, WEBRESOURCE_CLASSID

_TEXT = "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}"
_LOOKUP = "{270BD3DB-D9AF-4782-9025-509E298DEC0A}"
_DATETIME = "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}"
_MEMO = "{B0C872A3-3FA8-4D39-87D3-B3DCDA23B145}"

# Custom appointment "Engagements" view (deployed separately) — id captured live.
_ENGAGEMENTS_VIEW_ID = "{b725fb27-ac7b-f111-ab0e-7ced8de4ab8a}"


def _field(logical: str, label: str, classid: str = _TEXT) -> FormCell:
    return FormCell(
        control=FormControl(datafieldname=logical, classid=classid, id=logical),
        labels=[FormLabel(label)],
        showlabel=True,
        visible=True,
    )


def _row(cell: FormCell) -> FormRow:
    return FormRow(cells=[cell])


_CONTACT_TAG_CELL = FormCell(
    control=FormControl(
        datafieldname="",
        classid=WEBRESOURCE_CLASSID,
        id="contact_tag_ctrl",
        attrs={"id": "contact_tag_ctrl", "classid": WEBRESOURCE_CLASSID},
        parameters={
            "Url": "new_/html/contact_tags.html",
            "PassParameters": "true",
            "Scrolling": "auto",
            "Border": "false",
        },
    ),
    showlabel=False,
    visible=True,
    # rowspan gives the embedded iframe visible height (without it the web-resource collapses).
    attrs={"rowspan": "8"},
)

_ENGAGEMENTS_SUBGRID = FormCell(
    control=FormControl(
        datafieldname="",
        classid=SUBGRID_CLASSID,
        id="engagements_subgrid",
        attrs={"id": "engagements_subgrid", "classid": SUBGRID_CLASSID},
        parameters={
            "TargetEntityType": "appointment",
            "ViewId": _ENGAGEMENTS_VIEW_ID,
            "IsUserView": "false",
            "RelationshipName": "Contact_Appointments",
            "AutoExpand": "Fixed",
            "EnableQuickFind": "false",
            "EnableViewPicker": "false",
            "EnableJumpBar": "false",
            "ChartGridMode": "Grid",
            "VisualizationId": "",
            "IsUserChart": "false",
            "EnableChartPicker": "false",
            "RecordsPerPage": "5",
            "EnableContextualActions": "false",
        },
    ),
    showlabel=False,
    visible=True,
)

FORM: Form = Form(
    name="Summary and Engagements",
    entity="contact",
    form_type=FormType.Main,
    description="Contact form — Summary + Engagements tabs (HKL CCRM Page 21).",
    tabs=[
        FormTab(
            name="SUMMARY_TAB",
            labels=[FormLabel("Summary")],
            columns=[
                # Left: Contact Information — single column, one field per row (Figma layout).
                FormColumn(
                    "60%",
                    sections=[
                        FormSection(
                            name="Contact_Information",
                            labels=[FormLabel("Contact Information")],
                            columns=1,
                            rows=[
                                _row(_field("firstname", "First Name")),
                                _row(_field("lastname", "Last Name")),
                                _row(_field("jobtitle", "Title")),
                                _row(_field("salutation", "Salutation")),
                                _row(_field("mobilephone", "Mobile Phone")),
                                _row(_field("emailaddress1", "Email")),
                                _row(_field("new_ContactCode", "Contact ID")),
                                _row(_field("new_TenantCode", "Tenant ID")),
                                _row(_field("new_HklPic", "HKL PIC", _LOOKUP)),
                                _row(_field("new_LastEngagementDate", "Last Engagement Date", _DATETIME)),
                                _row(_field("description", "Remarks", _MEMO)),
                            ],
                        )
                    ],
                ),
                # Right: Tenant pane + Contact Tag pane.
                FormColumn(
                    "40%",
                    sections=[
                        FormSection(
                            name="Tenant",
                            labels=[FormLabel("Tenant")],
                            columns=1,
                            rows=[_row(_field("parentcustomerid", "Tenant", _LOOKUP))],
                        ),
                        FormSection(
                            name="Contact_Tag",
                            labels=[FormLabel("Contact Tag")],
                            columns=1,
                            rows=[_row(_CONTACT_TAG_CELL)],
                        ),
                    ],
                ),
            ],
        ),
        FormTab(
            name="ENGAGEMENTS_TAB",
            labels=[FormLabel("Engagements")],
            columns=[
                FormColumn(
                    "100%",
                    sections=[
                        FormSection(
                            name="Engagements_Section",
                            labels=[FormLabel("Engagements")],
                            columns=1,
                            rows=[_row(_ENGAGEMENTS_SUBGRID)],
                        )
                    ],
                )
            ],
        ),
    ],
)
