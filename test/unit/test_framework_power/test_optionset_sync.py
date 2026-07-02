"""Unit tests for framework_power.optionset_sync (fake client, no network)."""

from typing import Any, Optional

import pytest

from framework_power import GlobalOptionSet, Label, Option
from framework_power.optionset_sync import OptionSetSyncConfig, plan_optionsets, sync_optionsets

pytestmark = pytest.mark.unit


_NO_DELAY = OptionSetSyncConfig(
    after_create_delay=0.0, between_adds_delay=0.0, sleep=lambda _s: None
)


class FakeClient:
    def __init__(self, existing: Optional[dict[str, dict[str, Any]]] = None) -> None:
        self.existing = existing or {}
        self.created: list[dict[str, Any]] = []
        self.solution_adds: list[tuple[str, int, str]] = []

    def get_global_optionset_by_name(self, name: str):
        return self.existing.get(name)

    def create_global_optionset(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.created.append(payload)
        return {"MetadataId": "osid:" + payload["Name"]}

    def add_solution_component(self, solution: str, code: int, oid: str) -> dict[str, Any]:
        self.solution_adds.append((solution, code, oid))
        return {"status": "added"}


def _optset() -> GlobalOptionSet:
    return GlobalOptionSet(
        name="new_Category",
        display_name=Label.bilingual("类别", "Category"),
        options=[Option(1, Label.en("A")), Option(2, Label.en("B"))],
    )


def test_sync_creates_and_adds_to_solution():
    client = FakeClient()
    res = sync_optionsets(client, [_optset()], prefix="new", solution="new_MainSoln", config=_NO_DELAY)
    assert res["synced"][0]["deploy"]["action"] == "created"
    # optionset self-adds to the solution (code 9) — Phase 9 uniformity.
    assert client.solution_adds == [("new_MainSoln", 9, "osid:new_Category")]


def test_sync_no_solution_no_add():
    client = FakeClient()
    res = sync_optionsets(client, [_optset()], prefix="new", config=_NO_DELAY)
    assert res["synced"][0]["deploy"]["action"] == "created"
    assert client.solution_adds == []


def test_sync_exists_is_idempotent_no_recreate():
    existing = {"new_Category": {"MetadataId": "osid:new_Category", "Options": [{"Value": 1}, {"Value": 2}]}}
    client = FakeClient(existing=existing)
    res = sync_optionsets(client, [_optset()], prefix="new", solution="new_MainSoln", config=_NO_DELAY)
    assert res["synced"][0]["deploy"]["action"] == "exists"
    assert client.created == []  # not re-created
    assert client.solution_adds == [("new_MainSoln", 9, "osid:new_Category")]


def test_plan_is_read_only():
    client = FakeClient()
    res = plan_optionsets(client, [_optset()], prefix="new")
    assert res["optionsets"][0]["plan"]["action"] == "would_create"
    assert client.created == []
    assert client.solution_adds == []
