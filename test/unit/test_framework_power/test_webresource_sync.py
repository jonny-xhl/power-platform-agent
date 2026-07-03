"""Unit tests for framework_power.webresource_sync (fake client, no network)."""

import base64
from pathlib import Path
from typing import Any, Optional

import pytest

from framework_power import WebResourceType
from framework_power.webresource_sync import (
    EXT_TO_TYPE,
    relpath_from_name,
    scan_webresources,
    sync_webresources,
    plan_webresources,
    reverse_webresources,
    webresource_name,
)

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------- naming


def test_webresource_name_preserves_relpath():
    assert webresource_name("js/order/test.js", "new") == "new_/js/order/test.js"
    assert webresource_name("js/common/XRM.com.js", "new") == "new_/js/common/XRM.com.js"


def test_webresource_name_normalizes_backslashes():
    assert webresource_name("js\\order\\test.js", "new") == "new_/js/order/test.js"


def test_relpath_from_name_roundtrip():
    assert relpath_from_name("new_/js/order/test.js", "new") == "js/order/test.js"
    # fallback for names without the slash form
    assert relpath_from_name("new_foo.js", "new") == "foo.js"


def test_ext_to_type_map():
    assert EXT_TO_TYPE[".js"] == WebResourceType.JScript
    assert EXT_TO_TYPE[".css"] == WebResourceType.Css
    assert EXT_TO_TYPE[".svg"] == WebResourceType.Svg
    assert EXT_TO_TYPE[".html"] == WebResourceType.WebPage


# ----------------------------------------------------------------- scan


def _write(root: Path, rel: str, data: bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_scan_naming_type_content(tmp_path):
    _write(tmp_path, "js/order/test.js", b"console.log(1);")
    models, warnings = scan_webresources(tmp_path, "new")
    assert len(models) == 1
    m = models[0]
    assert m.name == "new_/js/order/test.js"
    assert m.webresource_type == WebResourceType.JScript
    assert m.display_name == "test.js"
    assert m.content == base64.b64encode(b"console.log(1);").decode("ascii")
    assert warnings == []


def test_scan_multiple_types_and_dots_skipped(tmp_path):
    _write(tmp_path, "js/a.js", b"a")
    _write(tmp_path, "css/b.css", b"b")
    _write(tmp_path, "img/c.svg", b"c")
    _write(tmp_path, ".git/config", b"x")  # dot-dir -> skipped
    _write(tmp_path, ".hidden.js", b"y")  # dotfile -> skipped
    _write(tmp_path, "readme.md", b"z")  # unknown ext -> warning
    models, warnings = scan_webresources(tmp_path, "new")
    names = sorted(m.name for m in models)
    assert names == ["new_/css/b.css", "new_/img/c.svg", "new_/js/a.js"]
    assert any("readme.md" in w for w in warnings)
    assert all(".git" not in n and ".hidden" not in n for n in names)


def test_scan_requires_dir(tmp_path):
    f = tmp_path / "notadir.js"
    f.write_bytes(b"x")
    with pytest.raises(ValueError):
        scan_webresources(f, "new")


def test_scan_include_filters_to_matching_relpaths(tmp_path):
    _write(tmp_path, "js/order/a.js", b"a")
    _write(tmp_path, "js/order/b.js", b"b")
    _write(tmp_path, "css/c.css", b"c")
    # exact relpath
    models, _ = scan_webresources(tmp_path, "new", include=["js/order/a.js"])
    assert [m.name for m in models] == ["new_/js/order/a.js"]
    # glob within a subtree
    models, _ = scan_webresources(tmp_path, "new", include=["js/order/*.js"])
    assert sorted(m.name for m in models) == ["new_/js/order/a.js", "new_/js/order/b.js"]
    # multiple globs
    models, _ = scan_webresources(tmp_path, "new", include=["js/order/a.js", "css/*.css"])
    assert sorted(m.name for m in models) == ["new_/css/c.css", "new_/js/order/a.js"]


def test_scan_include_none_means_all(tmp_path):
    _write(tmp_path, "js/a.js", b"a")
    _write(tmp_path, "css/b.css", b"b")
    models, _ = scan_webresources(tmp_path, "new", include=None)
    assert len(models) == 2
    models, _ = scan_webresources(tmp_path, "new", include=[])
    assert len(models) == 2


# ----------------------------------------------------------------- fake client


class SyncFakeClient:
    def __init__(
        self,
        existing: Optional[dict[str, dict[str, Any]]] = None,
        by_prefix: Optional[list[dict[str, Any]]] = None,
        add_raises: Optional[Exception] = None,
    ) -> None:
        self._existing: dict[str, dict[str, Any]] = dict(existing or {})
        self._by_prefix = by_prefix or []
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []
        self.published: Optional[list[str]] = None
        self.added: list[tuple[str, int, str]] = []
        self.listed_prefix: Optional[str] = None
        self._add_raises = add_raises

    def get_webresource_by_name(self, name: str):
        return dict(self._existing[name]) if name in self._existing else None

    def create_webresource(self, payload: dict[str, Any]):
        wid = "wr-" + payload["name"].replace("/", "_")
        self._existing[payload["name"]] = {"webresourceid": wid}
        self.created.append(payload)
        return {"webresourceid": wid, "name": payload["name"]}

    def update_webresource(self, webresourceid: str, patch: dict[str, Any]):
        self.updated.append((webresourceid, patch))
        return {"updated": True, "webresourceid": webresourceid}

    def add_solution_component(self, unique_name: str, code: int, oid: str):
        if self._add_raises is not None:
            raise self._add_raises
        self.added.append((unique_name, code, oid))
        return {"added": True}

    def publish_webresources(self, ids: list[str]):
        self.published = list(ids)
        return {"published": True, "count": len(ids), "ids": list(ids)}

    def list_webresources_by_prefix(self, name_prefix: str, *, select: str = ""):
        # Server-side filtering is delegated to the client (real one applies
        # $filter=startswith). The fake records the prefix it was asked for.
        self.listed_prefix = name_prefix
        return list(self._by_prefix)


# ----------------------------------------------------------------- plan


def test_plan_read_only(tmp_path):
    _write(tmp_path, "js/a.js", b"a")
    _write(tmp_path, "js/b.js", b"b")
    client = SyncFakeClient(existing={"new_/js/b.js": {"webresourceid": "wr-b"}})
    res = plan_webresources(client, tmp_path, prefix="new")
    by_name = {f["name"]: f["plan"]["action"] for f in res["files"]}
    assert by_name == {"new_/js/a.js": "would_create", "new_/js/b.js": "would_update"}
    assert client.published is None  # plan never writes


# ----------------------------------------------------------------- sync


def test_sync_creates_and_publishes(tmp_path):
    _write(tmp_path, "js/order/test.js", b"v1")
    client = SyncFakeClient()
    res = sync_webresources(client, tmp_path, prefix="new", publish=True)
    assert client.created and client.created[0]["name"] == "new_/js/order/test.js"
    assert client.published and len(client.published) == 1  # targeted publish with the id
    synced = res["synced"]
    assert synced[0]["deploy"]["action"] == "created"


def test_sync_updates_when_present(tmp_path):
    _write(tmp_path, "js/a.js", b"v2")
    client = SyncFakeClient(existing={"new_/js/a.js": {"webresourceid": "wr-a"}})
    sync_webresources(client, tmp_path, prefix="new")
    assert not client.created
    assert client.updated and client.updated[0][0] == "wr-a"


def test_sync_no_publish(tmp_path):
    _write(tmp_path, "js/a.js", b"x")
    client = SyncFakeClient()
    sync_webresources(client, tmp_path, prefix="new", publish=False)
    assert client.published is None


def test_sync_solution_add(tmp_path):
    _write(tmp_path, "js/a.js", b"a")
    _write(tmp_path, "js/b.js", b"b")
    client = SyncFakeClient()
    sync_webresources(client, tmp_path, prefix="new", solution="new_Core", publish=False)
    assert len(client.added) == 2
    assert all(code == 61 for _, code, _ in client.added)


def test_sync_solution_already_in_is_benign(tmp_path):
    _write(tmp_path, "js/a.js", b"a")
    client = SyncFakeClient(add_raises=Exception("The solution component already exists"))
    res = sync_webresources(client, tmp_path, prefix="new", solution="new_Core", publish=False)
    assert res["added"][0]["action"] == "already_in_solution"


# ----------------------------------------------------------------- reverse


def test_reverse_decodes_and_writes(tmp_path):
    payload = base64.b64encode(b"hello world").decode("ascii")
    client = SyncFakeClient(
        by_prefix=[
            {"name": "new_/js/a.js", "webresourceid": "1", "content": payload},
            {"name": "new_/js/sub/b.js", "webresourceid": "2", "content": payload},
            {"name": "new_/js/empty.js", "webresourceid": "3", "content": None},
        ]
    )
    res = reverse_webresources(client, tmp_path, prefix="new")
    written = {w["name"] for w in res["written"]}
    assert written == {"new_/js/a.js", "new_/js/sub/b.js"}
    assert (tmp_path / "js" / "a.js").read_bytes() == b"hello world"
    assert (tmp_path / "js" / "sub" / "b.js").read_bytes() == b"hello world"
    assert any("empty.js" in s["name"] for s in res["skipped"])


def test_reverse_passes_default_prefix(tmp_path):
    client = SyncFakeClient()
    reverse_webresources(client, tmp_path, prefix="new")
    assert client.listed_prefix == "new_/"  # default scope = publisher prefix


def test_reverse_passes_custom_name_prefix(tmp_path):
    client = SyncFakeClient()
    res = reverse_webresources(client, tmp_path, prefix="new", name_prefix="new_/css/")
    assert client.listed_prefix == "new_/css/"  # custom scope passed through to client
    assert res["name_prefix"] == "new_/css/"
