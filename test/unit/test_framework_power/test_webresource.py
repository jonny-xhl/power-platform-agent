"""Unit tests for framework_power.components.webresource (fake client)."""

import pytest

import framework_power.components.webresource as wr_mod
from framework_power import WebResource, WebResourceType

pytestmark = pytest.mark.unit


def _model() -> WebResource:
    return WebResource(
        name="new_/js/x.js",
        display_name="X",
        content="YmFzZTY0",
        webresource_type=WebResourceType.JScript,
    )


class FakeClient:
    def __init__(self, existing=None) -> None:
        self._existing = existing
        self.created = []
        self.updated = []

    def get_webresource_by_name(self, name):
        return dict(self._existing) if self._existing else None

    def create_webresource(self, payload):
        self.created.append(payload)
        return {"webresourceid": "wr-id", "name": payload["name"]}

    def update_webresource(self, webresourceid, patch):
        self.updated.append((webresourceid, patch))
        return {"updated": True, "webresourceid": webresourceid}


def test_serialize_keys():
    p = wr_mod.serialize(_model())
    assert p["name"] == "new_/js/x.js"
    assert p["displayname"] == "X"
    assert p["content"] == "YmFzZTY0"
    assert p["webresourcetype"] == 3


def test_deploy_creates_when_absent():
    c = FakeClient(existing=None)
    assert wr_mod.deploy(c, _model(), prefix="new")["action"] == "created"
    assert c.created


def test_deploy_updates_when_present():
    c = FakeClient(existing={"webresourceid": "wr-id"})
    assert wr_mod.deploy(c, _model(), prefix="new")["action"] == "updated"
    assert c.updated and c.updated[0][0] == "wr-id"


def test_deploy_skips_standard():
    m = WebResource(name="main.js", display_name="m", content="x", webresource_type=WebResourceType.JScript)
    assert wr_mod.deploy(FakeClient(), m, prefix="new")["action"] == "skipped_standard"


def test_resolve_id():
    c = FakeClient(existing={"webresourceid": "wr-id"})
    assert wr_mod.resolve_id(c, _model()) == "wr-id"


def test_plan_would_create_or_update():
    assert wr_mod.plan(FakeClient(existing=None), _model(), prefix="new")["action"] == "would_create"
    assert wr_mod.plan(FakeClient(existing={"webresourceid": "wr-id"}), _model(), prefix="new")["action"] == "would_update"


def test_reverse():
    class C:
        def get_webresource_by_id(self, oid):
            return {
                "name": "new_/js/x.js", "displayname": "X", "content": "YmFzZTY0",
                "webresourcetype": 3, "description": "d",
            }

    m = wr_mod.reverse(C(), "wr-id")
    assert m.name == "new_/js/x.js"
    assert m.content == "YmFzZTY0"
    assert m.webresource_type == WebResourceType.JScript


def test_codegen_round_trip():
    m = _model()
    src = wr_mod.codegen(m)
    compile(src, "w", "eval")
    ns = {"WebResource": WebResource, "WebResourceType": WebResourceType}
    assert eval(src, ns) == m


def test_lint_flags_empty_content():
    m = WebResource(name="new_/empty.js", display_name="e", content="", webresource_type=WebResourceType.JScript)
    issues = wr_mod.lint(m, prefix="new")
    assert any("empty" in i.message.lower() for i in issues)
