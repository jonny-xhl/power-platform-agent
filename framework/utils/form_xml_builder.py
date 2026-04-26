"""
FormXml builder - generates Dataverse FormXml from YAML form design.
Generates COMPLETE formxml suitable for both POST (new form) and PATCH (update).
"""

import uuid
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET


CONTROL_CLASSIDS = {
    "String": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",
    "Lookup": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "Customer": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "Owner": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "DateTime": "{5B773807-9FB2-42DB-97C3-7A91EFF8ADFF}",
    "Money": "{F1F39E30-FC9C-4342-8E51-05344D42E92E}",
    "Picklist": "{3AA39999-F31A-4F60-B95A-7C58AC2BDF8A}",
    "Memo": "{E0DECE4B-6FC8-4A8F-A065-5A5FDE2CB3C1}",
    "Boolean": "{67FAC785-CD58-4A9F-A7D3-532D57D3B8B0}",
    "Integer": "{24C9C335-2A4A-4EBF-9A1C-39EB71DC1852}",
    "Double": "{24C9C335-2A4A-4EBF-9A1C-39EB71DC1852}",
    "Decimal": "{24C9C335-2A4A-4EBF-9A1C-39EB71DC1852}",
    "Virtual": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",
}


class FormXmlBuilder:
    """Builds complete Dataverse FormXml from YAML form design."""

    def __init__(self, entity_fields: Dict[str, str]):
        self.entity_fields = entity_fields
        self._id_map: Dict[str, str] = {}

    def build(self, form_design: Dict[str, Any]) -> str:
        """Build COMPLETE FormXml string from form YAML design."""
        form_el = ET.Element("form")

        tabs_el = ET.SubElement(form_el, "tabs")
        tabs = form_design.get("tabs", [])
        for i, tab_def in enumerate(tabs):
            tab_el = self._build_tab(tab_def, i)
            tabs_el.append(tab_el)

        return ET.tostring(form_el, encoding="unicode")

    def _build_tab(self, tab_def: Dict[str, Any], index: int) -> ET.Element:
        name = tab_def.get("name", f"tab_{index}")
        display_name = tab_def.get("display_name", f"Tab {index + 1}")

        tab_el = ET.Element("tab")
        tab_el.set("name", name)
        tab_el.set("id", self._guid())
        tab_el.set("showlabel", "true")
        tab_el.set("expanded", "true" if tab_def.get("expand_by_default", True) else "false")
        tab_el.set("visible", "true" if tab_def.get("visible", True) else "false")
        tab_el.set("verticallayout", "true")
        tab_el.set("IsUserDefined", "1")

        labels_el = ET.SubElement(tab_el, "labels")
        self._add_label(labels_el, display_name)

        columns_el = ET.SubElement(tab_el, "columns")
        column_el = ET.SubElement(columns_el, "column")
        column_el.set("width", "100%")

        sections_el = ET.SubElement(column_el, "sections")
        for sec_def in tab_def.get("sections", []):
            section_el = self._build_section(sec_def)
            sections_el.append(section_el)

        return tab_el

    def _build_section(self, sec_def: Dict[str, Any]) -> ET.Element:
        name = sec_def.get("name", "")
        display_name = sec_def.get("display_name", "Section")

        section_el = ET.Element("section")
        section_el.set("name", name)
        section_el.set("id", self._guid())
        section_el.set("showlabel", "true")
        section_el.set("showbar", "false")
        section_el.set("visible", "true" if sec_def.get("visible", True) else "false")
        section_el.set("IsUserDefined", "1")

        labels_el = ET.SubElement(section_el, "labels")
        self._add_label(labels_el, display_name)

        rows_el = ET.SubElement(section_el, "rows")
        for row_def in sec_def.get("rows", []):
            row_el = ET.SubElement(rows_el, "row")
            for cell_def in row_def.get("cells", []):
                cell_el = self._build_cell(cell_def)
                row_el.append(cell_el)

        return section_el

    def _build_cell(self, cell_def: Dict[str, Any]) -> ET.Element:
        attr_name = cell_def.get("attribute", "")
        field_type = self.entity_fields.get(attr_name, "String")
        classid = CONTROL_CLASSIDS.get(field_type, CONTROL_CLASSIDS["String"])

        cell_el = ET.Element("cell")
        cell_el.set("id", self._guid())

        control_el = ET.SubElement(cell_el, "control")
        control_el.set("id", attr_name)
        control_el.set("classid", classid)
        control_el.set("datafieldname", attr_name)

        if cell_def.get("disabled"):
            control_el.set("disabled", "true")

        return cell_el

    @staticmethod
    def _add_label(parent: ET.Element, text: str, _labelid: str = "") -> None:
        label_en = ET.SubElement(parent, "label")
        label_en.set("languagecode", "1033")
        label_en.set("description", text)

        label_zh = ET.SubElement(parent, "label")
        label_zh.set("languagecode", "2052")
        label_zh.set("description", text)

    @staticmethod
    def _guid() -> str:
        return "{" + str(uuid.uuid4()).upper() + "}"
