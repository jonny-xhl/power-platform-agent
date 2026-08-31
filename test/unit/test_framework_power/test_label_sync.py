# -*- coding: utf-8 -*-
"""Unit tests for framework_power.label_sync (fake client, no network)."""

import pytest

from framework_power import Label, Table
from framework_power.label_sync import (
    plan_auto_component_labels,
    sync_auto_component_labels,
)

pytestmark = pytest.mark.unit

NO_SLEEP = lambda seconds: None  # noqa: E731


def make_table():
    return Table(
        schema_name="new_x",
        display_name=Label.bilingual("明细", "X"),
        display_collection_name=Label.bilingual("明细集", "Xes"),
    )


def sys_views(localized=False):
    """The 7 platform views; ``localized`` = 2052 labels already healed."""
    rows = [
        (0, True, "Active Xes", "活动明细集"),
        (0, False, "Inactive Xes", "停用明细集"),
        (8192, False, "My Xes", "我的明细集"),
        (4, False, "Quick Find Active Xes", "快速查找活动明细集"),
        (2, False, "X Associated View", "明细关联视图"),
        (64, False, "X Lookup View", "明细查找视图"),
        (1, False, "X Advanced Find View", "明细高级查找视图"),
    ]
    out = []
    for i, (qt, isdef, en, zh) in enumerate(rows):
        out.append({
            "savedqueryid": f"v{i}",
            # caller language is 2052: name reflects the (un)healed 2052 label
            "name": zh if localized else en,
            "querytype": qt,
            "isdefault": isdef,
        })
    # a custom public view must never be touched
    out.append({"savedqueryid": "v99", "name": "我的自定义视图", "querytype": 0,
                "isdefault": False, "custom": True})
    return out


def sys_forms(localized=False):
    return [{
        "formid": f"f{i}",
        "name": "信息" if localized else "Information",
        "type": t,
    } for i, t in enumerate((2, 6, 11))]


class FakeClient:
    """Writes land in a pending layer; publish_entity promotes them (live quirk)."""

    promote_on_attempt = 1  # publish call index that promotes pending labels

    def __init__(self, *, localized=False, exists=True):
        self.exists = exists
        self._views = sys_views(localized)
        self._forms = sys_forms(localized)
        self.view_labels = {v["savedqueryid"]: {1033: _init_label(v), 2052: _init_label(v)}
                            for v in self._views}
        self.form_labels = {f["formid"]: {1033: "Information", 2052: f["name"]}
                            for f in self._forms}
        self.pending = []
        self.publish_calls = 0
        self.form_patches = []

    def entity_exists(self, logical):
        return self.exists

    def list_views_by_entity(self, entity, select=""):
        return self._views

    def list_forms_by_entity(self, entity, select=""):
        return self._forms

    def retrieve_loc_labels(self, entity_set, pk, attribute):
        store = self.view_labels if entity_set == "savedqueries" else self.form_labels
        return dict(store.get(pk) or {})

    def set_loc_labels(self, entity_set, pk, attribute, labels):
        self.pending.append((entity_set, pk, dict(labels)))

    def update_form(self, form_id, patch):
        self.form_patches.append((form_id, patch))

    def publish_entity(self, entity):
        self.publish_calls += 1
        if self.publish_calls >= self.promote_on_attempt:
            for entity_set, pk, labels in self.pending:
                store = self.view_labels if entity_set == "savedqueries" else self.form_labels
                store[pk] = dict(labels)
            self.pending = []
        return {"published": True, "entity": entity}


def _en_name(view):
    """The English template name for a fake view row."""
    import framework_power.label_sync as ls

    qt = view["querytype"]
    if qt == 0:
        tpl = ls._PUBLIC_TEMPLATES[bool(view["isdefault"])][1033]
    else:
        tpl = ls._VIEW_TEMPLATES[qt][1033]
    return tpl.format(s="X", c="Xes")


def _init_label(view):
    """Label text for the fake's initial state: custom views keep their own name."""
    return view["name"] if view.get("custom") else _en_name(view)


# --------------------------------------------------------------------- sync


def test_sync_localizes_all_default_named_views_and_forms():
    fake = FakeClient()
    res = sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    assert res["changed"] is True
    localized = [v for v in res["views"] if v["action"] == "localized"]
    assert len(localized) == 7
    assert {v["zh"] for v in localized} == {
        "活动明细集", "停用明细集", "我的明细集", "快速查找活动明细集",
        "明细关联视图", "明细查找视图", "明细高级查找视图",
    }
    assert all(f["action"] == "localized" and f["zh"] == "信息" for f in res["forms"])
    # each localized form is also PATCHed (name) to dirty it for the entity publish
    assert [pk for pk, _ in fake.form_patches] == ["f0", "f1", "f2"]
    assert all(p == {"name": "信息"} for _, p in fake.form_patches)
    # 7 views + 3 forms promoted on the single publish; nothing left pending
    assert fake.pending == [] and fake.publish_calls == 1
    assert res["publish"] == {"action": "published", "attempts": 1}
    # published layer carries the Chinese names (custom view untouched)
    zh_names = [fake.view_labels[f"v{i}"][2052] for i in range(7)]
    assert fake.view_labels["v99"][2052] == "我的自定义视图"
    assert all(n for n in zh_names)


def test_sync_keeps_english_label_and_custom_names():
    fake = FakeClient()
    sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    by_id = {v["savedqueryid"]: v for v in fake._views}
    for pk, labels in fake.view_labels.items():
        assert labels[1033] == _init_label(by_id[pk])


def test_sync_idempotent_when_already_localized():
    fake = FakeClient(localized=True)
    res = sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    assert res["changed"] is False
    assert fake.publish_calls == 0
    assert res["publish"] == {"action": "skipped_no_changes"}
    sys_actions = [v["action"] for v in res["views"]
                   if v["view"] != "我的自定义视图"]
    assert all(a == "skipped_localized" for a in sys_actions)
    assert all(f["action"] == "skipped_localized" for f in res["forms"])


def test_sync_skips_custom_named_public_view():
    fake = FakeClient(localized=True)
    fake._views.append({"savedqueryid": "v100", "name": "全部明细", "querytype": 0,
                        "isdefault": False})
    res = sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    actions = {v["view"]: v["action"] for v in res["views"]}
    assert actions["全部明细"] == "skipped_custom_name"


def test_sync_reports_failure_per_component():
    fake = FakeClient()

    def boom(entity_set, pk, attribute, labels=None):
        raise RuntimeError("api down")

    fake.set_loc_labels = lambda *a, **k: boom(*a, **k)
    res = sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    assert res["changed"] is False
    sys_actions = [v["action"] for v in res["views"]
                   if v["view"] != "我的自定义视图"]
    assert all(a == "failed" for a in sys_actions)
    # nothing written -> no publish attempted
    assert res["publish"] == {"action": "skipped_no_changes"}


def test_sync_republishes_when_labels_not_yet_visible():
    """Live quirk: first publish may miss fresh labels (propagation) -> retry."""
    fake = FakeClient()
    fake.promote_on_attempt = 2  # labels only visible after the 2nd publish
    res = sync_auto_component_labels(fake, make_table(), sleep=NO_SLEEP)
    assert fake.publish_calls == 2
    assert res["publish"] == {"action": "published", "attempts": 2}
    assert all(fake.view_labels[f"v{i}"][2052] for i in range(7))
    assert all(fake.form_labels[f"f{i}"][2052] == "信息" for i in range(3))


def test_sync_skips_without_bilingual_table_labels():
    table = Table(schema_name="new_x", display_name=Label.zh("明细"))
    fake = FakeClient()
    res = sync_auto_component_labels(fake, table, sleep=NO_SLEEP)
    assert res["changed"] is False
    assert "skipped" in res


# --------------------------------------------------------------------- plan


def test_plan_fresh_create_summary():
    fake = FakeClient(exists=False)
    res = plan_auto_component_labels(fake, make_table())
    assert res["action"] == "would_localize"
    assert res["views"] == 7 and res["forms"] == 3


def test_plan_existing_lists_per_component_actions():
    fake = FakeClient()
    res = plan_auto_component_labels(fake, make_table())
    assert all(v["action"] == "would_localize"
               for v in res["views"] if v["view"] != "我的自定义视图")
    assert next(v for v in res["views"]
                if v["view"] == "我的自定义视图")["action"] == "would_skip_custom_name"
    assert all(f["action"] == "would_localize" for f in res["forms"])
