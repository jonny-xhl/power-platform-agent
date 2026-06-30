"""Unit tests for framework_power.solution_zip (customizations.xml inject/extract, Phase 7)."""

import io
import zipfile

import pytest

from framework_power import solution_zip as sz

pytestmark = pytest.mark.unit

# Real-shape customizations.xml: <Name> carries LocalizedName/OriginalName ATTRIBUTES (pinned gotcha),
# and the Entity has FormXml/SavedQueries to confirm they're preserved on inject.
CUST = (
    '<ImportExportXml><Entities><Entity>'
    '<Name LocalizedName="X" OriginalName="X">new_Test</Name>'
    '<EntityInfo />'
    '<FormXml><form>KEEP_ME</form></FormXml>'
    '<SavedQueries />'
    '<RibbonDiffXml><CustomActions /><Templates><RibbonTemplates Id="Mscrm.Templates" /></Templates>'
    '<CommandDefinitions /><RuleDefinitions><TabDisplayRules /><DisplayRules /><EnableRules /></RuleDefinitions>'
    '<LocLabels /></RibbonDiffXml>'
    '</Entity></Entities></ImportExportXml>'
)
NEW_DIFF = '<RibbonDiffXml><CustomActions /><Templates><RibbonTemplates Id="Mscrm.Templates" /></Templates>' \
           '<CommandDefinitions /><RuleDefinitions><TabDisplayRules /><DisplayRules /><EnableRules />' \
           '</RuleDefinitions><LocLabels /><Marker>injected</Marker></RibbonDiffXml>'


def _zip(cust_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("customizations.xml", cust_xml)
        zf.writestr("solution.xml", "<solution/>")
    return buf.getvalue()


def test_name_with_attributes_is_matched():
    # <Name> has attributes (pinned) — extract must still find the entity's ribbon diff
    frag = sz.extract_ribbondiff(CUST, "new_Test")
    assert frag and "<RibbonDiffXml" in frag


def test_inject_replaces_ribbondiff_preserves_rest():
    new = sz.inject_entity_ribbondiff(CUST, "new_Test", NEW_DIFF)
    assert "<Marker>injected</Marker>" in new
    assert "KEEP_ME" in new  # FormXml preserved byte-for-byte
    assert "<SavedQueries" in new  # other Entity children preserved


def test_inject_then_extract_round_trips():
    new = sz.inject_entity_ribbondiff(CUST, "new_Test", NEW_DIFF)
    back = sz.extract_ribbondiff(new, "new_Test")
    assert "<Marker>injected</Marker>" in back


def test_inject_unknown_entity_raises():
    with pytest.raises(ValueError):
        sz.inject_entity_ribbondiff(CUST, "nope", NEW_DIFF)


def test_inject_inserts_when_entity_has_no_ribbondiff():
    # Shell-only entity export (DoNotIncludeSubcomponents=True) may omit <RibbonDiffXml> entirely.
    # Inject must INSERT before </Entity>, not silently drop the diff.
    shell = (
        '<ImportExportXml><Entities><Entity>'
        '<Name>new_Shell</Name>'
        '<EntityInfo />'
        '</Entity></Entities></ImportExportXml>'
    )
    new = sz.inject_entity_ribbondiff(shell, "new_Shell", NEW_DIFF)
    assert "<Marker>injected</Marker>" in new
    # and extractable right back
    assert "<Marker>injected</Marker>" in sz.extract_ribbondiff(new, "new_Shell")


def test_zip_round_trip():
    zb = _zip(CUST)
    assert sz.read_customizations_xml(zb) == CUST
    new_zb = sz.write_customizations_xml(zb, CUST.replace("KEEP_ME", "EDITED"))
    cust2 = sz.read_customizations_xml(new_zb)
    assert "EDITED" in cust2 and "KEEP_ME" not in cust2
    # other entries preserved
    with zipfile.ZipFile(io.BytesIO(new_zb)) as zf:
        assert "solution.xml" in zf.namelist()


def test_application_ribbon_inject_inserts_when_absent():
    # no root-level RibbonDiffXml -> inject inserts one after </Entities>
    new = sz.inject_application_ribbondiff(CUST, NEW_DIFF)
    assert "<Marker>injected</Marker>" in new
    # entity ribbon diff still present and untouched
    assert sz.extract_ribbondiff(new, "new_Test")  # entity block intact
