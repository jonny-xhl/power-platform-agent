"""Account form — "Contact View" (HKL CCRM Page 21).

A new Main form on the standard ``account`` entity with two tabs:
- **Summary**: minimal (account name).
- **Contact**: embeds the custom HTML web-resource ``new_/html/contact_list.html`` (the
  Contact List page) with ``PassParams=1`` so the page receives the current account ``id``
  and can query that account's contacts.
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
from framework_power.form_xml import WEBRESOURCE_CLASSID

_TEXT = "{4273EDBD-AC1D-40D3-9FB2-095C621B552D}"


def _field(logical: str, label: str) -> FormCell:
    return FormCell(
        control=FormControl(datafieldname=logical, classid=_TEXT, id=logical),
        labels=[FormLabel(label)],
        showlabel=True,
        visible=True,
    )


_CONTACT_LIST_CELL = FormCell(
    control=FormControl(
        datafieldname="",
        classid=WEBRESOURCE_CLASSID,
        id="contact_list_ctrl",
        attrs={
            "id": "contact_list_ctrl",
            "classid": WEBRESOURCE_CLASSID,
        },
        parameters={
            "Url": "new_/html/contact_list.html",
            "PassParameters": "true",
            "Scrolling": "auto",
            "Border": "false",
        },
    ),
    showlabel=False,
    visible=True,
)

FORM: Form = Form(
    name="Contact View",
    entity="account",
    form_type=FormType.Main,
    description="Account form with an embedded Contact list (HKL CCRM Page 21).",
    tabs=[
        FormTab(
            name="SUMMARY_TAB",
            labels=[FormLabel("Summary")],
            columns=[
                FormColumn(
                    "100%",
                    sections=[
                        FormSection(
                            name="Summary_Section",
                            labels=[FormLabel("Summary")],
                            columns=2,
                            rows=[FormRow(cells=[_field("name", "Account Name")])],
                        )
                    ],
                )
            ],
        ),
        FormTab(
            name="CONTACT_TAB",
            labels=[FormLabel("Contact")],
            columns=[
                FormColumn(
                    "100%",
                    sections=[
                        FormSection(
                            name="Contact_List_Section",
                            labels=[FormLabel("Contact List")],
                            columns=1,
                            rows=[FormRow(cells=[_CONTACT_LIST_CELL])],
                        )
                    ],
                )
            ],
        ),
    ],
)
