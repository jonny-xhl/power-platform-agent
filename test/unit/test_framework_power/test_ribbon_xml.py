"""Unit tests for framework_power.ribbon_xml (parse/serialize/builders, Phase 7)."""

import pytest

from framework_power import ribbon_xml as rx
from framework_power import RibbonDefinition, RibbonScope

pytestmark = pytest.mark.unit


def _ribbon() -> RibbonDefinition:
    r = rx.new_ribbon("new_test")
    r = rx.add_button(
        r, "new_test.Send",
        scope=RibbonScope.Form,
        label={"1033": "Send", "2052": "发送"},
        tooltip={"1033": "Send this record", "2052": "发送此记录"},
        library="new_/js/test/ribbon.js",
        on_click_fn="onSendClick",
        show_fn="shouldShowSend",
        enable_fn="shouldEnableSend",
    )
    r = rx.hide_oob(r, "Mscrm.Form.new_test.Deactivate")  # default command_override
    return r


# ----------------------------------------------------------------- round-trip


def test_round_trip_lossless_and_idempotent():
    r = _ribbon()
    xml = rx.to_ribbondiff(r)
    back = rx.parse_ribbondiff(xml)
    xml2 = rx.to_ribbondiff(back)
    assert xml == xml2  # idempotent (Location preserved via attrs-first)


def test_serialize_structure():
    xml = rx.to_ribbondiff(_ribbon())
    # Real group (MainTab.Save) + .Controls._children suffix — not an invented group
    assert 'Location="Mscrm.Form.new_test.MainTab.Save.Controls._children"' in xml
    assert 'Command="new_test.Send.Command"' in xml
    assert 'Library="$webresource:new_/js/test/ribbon.js"' in xml
    assert "FunctionName=\"onSendClick\"" in xml
    assert 'CustomRule FunctionName="shouldShowSend"' in xml
    assert 'CustomRule FunctionName="shouldEnableSend"' in xml
    assert '<Title languagecode="2052" description="发送"' in xml
    # hide-OOB override emits a CommandDefinition override with the mutually-exclusive rules
    assert '<CommandDefinition Id="Mscrm.Form.new_test.Deactivate">' in xml
    assert 'DisplayRule Id="Mscrm.HideOnModern"' in xml and 'DisplayRule Id="Mscrm.ShowOnlyOnModern"' in xml


def test_parse_captures_wiring():
    back = rx.parse_ribbondiff(rx.to_ribbondiff(_ribbon()))
    cmd = back.commands[0]
    assert cmd.function_name == "onSendClick"
    assert cmd.library == "new_/js/test/ribbon.js"
    # show_fn + enable_fn BOTH produce EnableRules (CustomRule is EnableRule-only per MS Learn)
    assert "new_test.Send.ShowRule" in cmd.enable_rules
    assert "new_test.Send.EnableRule" in cmd.enable_rules
    assert cmd.display_rules == []
    show_rule = next(r for r in back.enable_rules if r.id == "new_test.Send.ShowRule")
    assert show_rule.custom_rule.function_name == "shouldShowSend"
    assert any(h.method == "command_override" and h.oob_command_id == "Mscrm.Form.new_test.Deactivate"
               for h in back.hide_oobs)


# ----------------------------------------------------------------- builders


def test_add_button_auto_creates_command():
    r = rx.new_ribbon("new_test")
    r = rx.add_button(r, "new_test.X", scope=RibbonScope.HomepageGrid, label="Go",
                      library="new_/js/x.js", on_click_fn="onGo")
    assert any(c.id == "new_test.X.Command" and c.function_name == "onGo" for c in r.commands)


def test_add_button_uses_existing_command():
    r = rx.new_ribbon("new_test")
    r = rx.add_command(r, "my.cmd", function_name="fn", library="new_/js/x.js")
    r = rx.add_button(r, "new_test.X", scope=RibbonScope.SubGrid, label="Go", command="my.cmd",
                      library="new_/js/x.js")
    assert len(r.commands) == 1 and r.buttons[0].command == "my.cmd"


def test_hide_custom_action_method():
    r = rx.hide_oob(rx.new_ribbon("new_test"), "Mscrm.Form.new_test.Delete", method="hide_custom_action")
    xml = rx.to_ribbondiff(r)
    assert '<HideCustomAction' in xml and 'Location="Mscrm.Form.new_test.Delete"' in xml


def test_application_scope_location():
    # Application default area is GlobalTab.New; .Controls._children appended
    r = rx.add_button(rx.new_ribbon(None), "global.Btn", scope=RibbonScope.Application,
                      label="G", library="new_/js/x.js", on_click_fn="fn")
    xml = rx.to_ribbondiff(r)
    assert 'Location="Mscrm.GlobalTab.New.Controls._children"' in xml


def test_scope_aware_default_area():
    # Each scope picks a real existing group so the button renders (no invented groups)
    cases = {
        RibbonScope.Form: "MainTab.Save",
        RibbonScope.HomepageGrid: "MainTab.Management",
        RibbonScope.SubGrid: "MainTab.Management",
    }
    for scope, group in cases.items():
        r = rx.add_button(rx.new_ribbon("new_test"), "new_test.B", scope=scope, label="L",
                          library="new_/js/x.js", on_click_fn="fn")
        assert rx.to_ribbondiff(r).count(f"Mscrm.{scope.value}.new_test.{group}.Controls._children") == 1


def test_area_override():
    r = rx.add_button(rx.new_ribbon("new_test"), "new_test.B", scope=RibbonScope.Form, label="L",
                      library="new_/js/x.js", on_click_fn="fn", area="MainTab.Actions")
    assert 'Location="Mscrm.Form.new_test.MainTab.Actions.Controls._children"' in rx.to_ribbondiff(r)


def test_crm_param_default_is_scope_aware():
    # Form button -> PrimaryControl (formContext); Grid button -> SelectedControl (gridContext)
    form = rx.add_button(rx.new_ribbon("new_test"), "new_test.F", scope=RibbonScope.Form, label="L",
                         library="new_/js/x.js", on_click_fn="onClickF", show_fn="onShowF")
    grid = rx.add_button(rx.new_ribbon("new_test"), "new_test.G", scope=RibbonScope.HomepageGrid, label="L",
                         library="new_/js/x.js", on_click_fn="onClickG", show_fn="onShowG")
    fxml, gxml = rx.to_ribbondiff(form), rx.to_ribbondiff(grid)
    assert fxml.count('<CrmParameter Value="PrimaryControl" />') == 2     # click + show rule
    assert "SelectedControl" not in fxml
    assert gxml.count('<CrmParameter Value="SelectedControl" />') == 2    # click + show rule
    assert "PrimaryControl" not in gxml


def test_crm_param_override():
    r = rx.add_button(rx.new_ribbon("new_test"), "new_test.B", scope=RibbonScope.Form, label="L",
                      library="new_/js/x.js", on_click_fn="onClick", show_fn="onShow",
                      params=["PrimaryControl", "CommandProperties"],
                      rule_params=["PrimaryControl", "SelectedControlSelectedItemIds"])
    xml = rx.to_ribbondiff(r)
    # click handler params
    assert '<CrmParameter Value="PrimaryControl" /><CrmParameter Value="CommandProperties" />' in xml or \
           ('Value="PrimaryControl"' in xml and 'Value="CommandProperties"' in xml)
    assert 'Value="SelectedControlSelectedItemIds"' in xml  # rule param override


# ----------------------------------------------------------------- customise_command (OOB)


def _customise_ribbon():
    # Deactivate: preserve its OOB rules (seeded) + add a conditional-hide CustomRule + paste Actions
    return rx.customise_command(
        rx.new_ribbon("new_test"), "Mscrm.Form.new_test.Deactivate",
        library="new_/js/test/ribbon.js",
        show_fn="shouldShowDeactivate",
        actions_xml="<Actions><JavaScriptFunction Library=\"$webresource:sysapi\" FunctionName=\"deactivate\" /></Actions>",
    )


def test_customise_command_preserves_rules_and_adds_customrule():
    xml = rx.to_ribbondiff(_customise_ribbon())
    assert '<CommandDefinition Id="Mscrm.Form.new_test.Deactivate">' in xml
    # OOB DISPLAY rules preserved (seeded for Deactivate) -> stay in <DisplayRules>
    assert '<DisplayRule Id="Mscrm.CanWritePrimary" />' in xml
    assert '<DisplayRule Id="Mscrm.PrimaryIsActive" />' in xml
    assert '<DisplayRule Id="Mscrm.PrimaryEntityHasStatecode" />' in xml
    # added CustomRule is an ENABLE rule (CustomRule is EnableRule-only per MS Learn), fail-OPEN for OOB
    assert '<EnableRule Id="new_test.Deactivate.ShowRule" />' in xml
    assert 'CustomRule FunctionName="shouldShowDeactivate"' in xml
    assert 'Default="true"' in xml
    # actions preserved verbatim (click still works)
    assert 'FunctionName="deactivate"' in xml


def test_customise_command_round_trip():
    r = _customise_ribbon()
    xml = rx.to_ribbondiff(r)
    back = rx.parse_ribbondiff(xml)
    assert xml == rx.to_ribbondiff(back)  # idempotent
    ov = back.command_overrides
    assert len(ov) == 1
    assert ov[0].oob_command_id == "Mscrm.Form.new_test.Deactivate"
    assert ov[0].preserve_display_rules == [
        "Mscrm.CanWritePrimary", "Mscrm.PrimaryIsActive", "Mscrm.PrimaryEntityHasStatecode"]
    assert ov[0].added_rule_ids == ["new_test.Deactivate.ShowRule"]
    assert "FunctionName=\"deactivate\"" in ov[0].actions_xml


def test_customise_command_explicit_rules_for_unseeded():
    # Activate isn't seeded -> preserve_* must be passed explicitly
    r = rx.customise_command(
        rx.new_ribbon("new_test"), "Mscrm.Form.new_test.Assign",
        library="new_/js/x.js", show_fn="fn",
        preserve_display_rules=["Mscrm.CanWritePrimary", "Mscrm.CanAssignObject"],
    )
    xml = rx.to_ribbondiff(r)
    assert '<DisplayRule Id="Mscrm.CanAssignObject" />' in xml


# ----------------------------------------------------------------- lint


def test_lint_flags_missing_command_and_library():
    from framework_power.ribbon_sync import lint_ribbon

    # button references a command that doesn't exist; command has no library
    r = RibbonDefinition(entity="new_test")
    from framework_power import RibbonButton
    r.buttons.append(RibbonButton(id="b", scope=RibbonScope.Form, command="ghost"))
    issues = lint_ribbon(r, prefix="new")
    msgs = " ".join(i.message for i in issues)
    assert "unknown command 'ghost'" in msgs


def test_lint_flags_customise_command_caveats():
    from framework_power.ribbon_sync import lint_ribbon

    # no actions_xml + no preserved rules -> two warnings (click may break + gating lost)
    r = rx.customise_command(rx.new_ribbon("new_test"), "Mscrm.Form.new_test.Delete",
                             library="new_/js/x.js", show_fn="fn",
                             preserve_display_rules=[], preserve_enable_rules=[])
    msgs = " ".join(i.message for i in lint_ribbon(r, prefix="new"))
    assert "no actions_xml" in msgs
    assert "preserves no OOB rules" in msgs
