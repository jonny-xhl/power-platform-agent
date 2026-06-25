"""Unit tests for framework_power.components.models."""

import pytest

from framework_power.components.models import (
    ComponentRef,
    CustomAction,
    Form,
    FormType,
    GlobalOptionSet,
    IsolationMode,
    Plugin,
    PluginStep,
    Publisher,
    QueryType,
    Solution,
    View,
    WebResource,
    WebResourceType,
)
from framework_power.models import Label

pytestmark = pytest.mark.unit


def test_publisher_defaults():
    p = Publisher(name="DefaultPublishercrmdev", display_name="CrmDev", prefix="new")
    assert p.description is None


def test_solution_defaults():
    s = Solution(unique_name="new_Core", friendly_name="Core")
    assert s.version == "1.0.0.0"
    assert s.tables == [] and s.refs == []
    assert s.publisher is None and s.publisher_key is None
    for attr in ("optionsets", "webresources", "forms", "views", "plugins"):
        assert getattr(s, attr) == []


def test_component_ref_defaults():
    r = ComponentRef(type="webresource")
    assert r.name is None and r.object_id is None and r.entity is None


def test_enum_values():
    assert int(WebResourceType.JScript) == 3
    assert int(FormType.Main) == 2
    assert int(QueryType.Public) == 0
    assert int(IsolationMode.Sandbox) == 2


def test_plugin_defaults_and_steps():
    pl = Plugin(name="MyPlugin", content="base64==")
    assert pl.version == "1.0.0.0"
    assert pl.isolation_mode == IsolationMode.Sandbox
    assert pl.steps == [] and pl.custom_actions == []
    step = PluginStep(name="step1", message="Create", entity="new_budget")
    assert step.stage == 40 and step.mode == 0


def test_global_optionset_uses_label_and_option():
    from framework_power.models import Option

    os_ = GlobalOptionSet(
        name="new_Priority",
        display_name=Label.bilingual("优先级", "Priority"),
        options=[Option(1, Label.en("Low"))],
    )
    assert os_.is_global is True
    assert os_.options[0].value == 1


def test_custom_action_defaults():
    a = CustomAction(schema_name="new_Score", display_name=Label.en("Score"))
    assert a.entity is None and a.parameters == [] and a.return_type is None
