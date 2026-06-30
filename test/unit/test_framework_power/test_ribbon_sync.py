"""Unit tests for framework_power.ribbon_sync (fake client, no network, Phase 7)."""

import io
import zipfile

import pytest

from framework_power import ribbon_xml as rx
from framework_power import ribbon_sync as rs
from framework_power import RibbonDefinition, RibbonScope

pytestmark = pytest.mark.unit

CUST = (
    '<ImportExportXml><Entities><Entity>'
    '<Name LocalizedName="X" OriginalName="X">new_Test</Name>'
    '<EntityInfo /><FormXml><form>KEEP</form></FormXml><SavedQueries />'
    '<RibbonDiffXml><CustomActions /><Templates><RibbonTemplates Id="Mscrm.Templates" /></Templates>'
    '<CommandDefinitions /><RuleDefinitions><TabDisplayRules /><DisplayRules /><EnableRules /></RuleDefinitions>'
    '<LocLabels /></RibbonDiffXml>'
    '</Entity></Entities></ImportExportXml>'
)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class RibbonFakeClient:
    def __init__(self):
        self.solution_exists = False
        self.imported_zip = None
        self.published = []
        self.added = []

    def get_api_url(self, path):
        return path

    @property
    def session(self):
        outer = self

        class S:
            def get(self_inner, url):
                if "publishers" in url:
                    return _Resp({"value": [{"uniquename": "new", "publisherid": "pid",
                                             "customizationprefix": "new"}]})
                return _Resp({"value": []})

        return S()

    def get_solution_by_name(self, name):
        return {"solutionid": "s"} if self.solution_exists else None

    def create_solution(self, payload):
        self.solution_exists = True
        return {"solutionid": "s"}

    def get_entity_metadata(self, entity):
        return {"LogicalName": entity, "SchemaName": "new_Test", "MetadataId": "mid"}

    def add_solution_component(self, sol, code, oid, **kwargs):
        self.added.append((sol, code, oid, kwargs))
        return {"added": True}

    def export_solution(self, name):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("customizations.xml", CUST)
            zf.writestr("solution.xml", "<solution/>")
        return buf.getvalue()

    def import_solution(self, zip_bytes, **kwargs):
        self.imported_zip = zip_bytes
        return {"ImportJobId": "job"}

    def publish_entity(self, entity):
        self.published.append(("entity", entity))
        return {}

    def publish_application_ribbon(self):
        self.published.append(("application", None))
        return {}


def _ribbon() -> RibbonDefinition:
    r = rx.new_ribbon("new_test")
    r = rx.add_button(r, "new_test.Send", scope=RibbonScope.Form, label="Send",
                      library="new_/js/test/ribbon.js", on_click_fn="onSendClick", show_fn="shouldShow")
    r = rx.customise_command(r, "Mscrm.Form.new_test.Deactivate", library="new_/js/test/ribbon.js",
                             show_fn="shouldShowDeactivate",
                             actions_xml="<Actions><JavaScriptFunction FunctionName=\"x\" /></Actions>")
    return r


# ----------------------------------------------------------------- plan


def test_plan_reports_targets():
    fake = RibbonFakeClient()
    res = rs.plan_ribbons(fake, [_ribbon()], prefix="new", solution="new_RibbonSoln")
    entry = res["ribbons"][0]
    assert entry["plan"]["action"] == "would_import"
    assert entry["plan"]["buttons"] == 1
    assert entry["plan"]["schema"] == "new_Test"


# ----------------------------------------------------------------- sync


def test_sync_imports_and_publishes_entity_scope():
    fake = RibbonFakeClient()
    res = rs.sync_ribbons(fake, [_ribbon()], prefix="new", solution="new_RibbonSoln", publish=True)
    assert res["synced"][0]["action"] == "imported"
    assert fake.solution_exists  # created
    assert fake.added and fake.added[0][1] == 1  # entity component added
    assert fake.added[0][3] == {"do_not_include_subcomponents": True}  # shell-only (Ribbon Workbench-loadable)
    assert fake.imported_zip is not None
    # the ribbon diff was injected into the imported customizations.xml
    cust = rs.solution_zip.read_customizations_xml(fake.imported_zip)
    assert "onSendClick" in cust and "KEEP" in cust  # ribbon injected, FormXml preserved
    assert ("entity", "new_test") in fake.published


def test_sync_no_publish():
    fake = RibbonFakeClient()
    rs.sync_ribbons(fake, [_ribbon()], prefix="new", solution="new_RibbonSoln", publish=False)
    assert fake.published == []


def test_load_ribbon(tmp_path):
    f = tmp_path / "r.py"
    f.write_text(
        "from framework_power import RibbonDefinition, RibbonScope\n"
        "from framework_power.ribbon_xml import new_ribbon, add_button\n"
        "RIBBON = add_button(new_ribbon('new_test'), 'new_test.X', scope=RibbonScope.Form,\n"
        "                    label='X', library='new_/js/x.js', on_click_fn='fn')\n",
        encoding="utf-8",
    )
    ribbon = rs.load_ribbon(f)
    assert ribbon.entity == "new_test" and len(ribbon.buttons) == 1


def test_codegen_round_trip():
    r = _ribbon()
    src = rs.codegen_ribbon(r)
    compile(src, "r", "eval")
    ns = {
        "RibbonDefinition": RibbonDefinition, "RibbonScope": RibbonScope,
        "RibbonButton": __import__("framework_power", fromlist=["RibbonButton"]).RibbonButton,
        "RibbonCommand": __import__("framework_power", fromlist=["RibbonCommand"]).RibbonCommand,
        "RibbonCommandOverride": __import__("framework_power", fromlist=["RibbonCommandOverride"]).RibbonCommandOverride,
        "RibbonCustomRule": __import__("framework_power", fromlist=["RibbonCustomRule"]).RibbonCustomRule,
        "RibbonDisplayRule": __import__("framework_power", fromlist=["RibbonDisplayRule"]).RibbonDisplayRule,
        "RibbonEnableRule": __import__("framework_power", fromlist=["RibbonEnableRule"]).RibbonEnableRule,
        "RibbonHideOob": __import__("framework_power", fromlist=["RibbonHideOob"]).RibbonHideOob,
        "RibbonLocLabel": __import__("framework_power", fromlist=["RibbonLocLabel"]).RibbonLocLabel,
    }
    assert eval(src, ns) == r
