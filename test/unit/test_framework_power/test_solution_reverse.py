"""Unit tests for framework_power.solution_reverse (fake client, no network)."""

from typing import Any, Optional

import pytest

from framework_power.solution_reverse import reverse_solution

pytestmark = pytest.mark.unit


class ReverseFakeClient:
    def __init__(
        self,
        solution_obj: Optional[dict[str, Any]],
        components: list[dict[str, Any]],
        publisher: Optional[dict[str, Any]] = None,
    ) -> None:
        self._sol = solution_obj
        self._components = components
        self._publisher = publisher

    def get_solution_by_name(self, unique_name: str) -> Optional[dict[str, Any]]:
        return self._sol

    def get_solution_components(self, unique_name: str) -> list[dict[str, Any]]:
        return list(self._components)

    def get_entity_metadata_by_id(self, oid: str) -> dict[str, Any]:
        return {"LogicalName": "new_budget", "SchemaName": "new_Budget"}

    def get_publisher_by_id(self, pid: str) -> dict[str, Any]:
        if self._publisher is None:
            raise Exception("not found")
        return self._publisher


_SOL = {
    "uniquename": "new_Core",
    "friendlyname": "Core",
    "version": "1.2.0.0",
    "description": "core",
    "_publisherid_value": "pub-1",
}
_PUB = {
    "uniquename": "DefaultPublishercrmdev",
    "friendlyname": "CrmDev",
    "customizationprefix": "new",
    "description": "default",
}


def test_reverse_table_component_becomes_name_ref():
    comps = [{"componenttype": 1, "objectid": "tbl-guid-1"}]
    client = ReverseFakeClient(_SOL, comps, publisher=_PUB)
    sol = reverse_solution(client, "new_Core")
    assert sol.unique_name == "new_Core"
    assert sol.version == "1.2.0.0"
    assert "new_budget" in sol.tables  # resolved from get_entity_metadata_by_id
    assert sol.publisher is not None
    assert sol.publisher.name == "DefaultPublishercrmdev"
    assert sol.publisher.prefix == "new"


def test_reverse_unknown_typecode_becomes_component_ref():
    comps = [{"componenttype": 999, "objectid": "x-guid"}]
    client = ReverseFakeClient(_SOL, comps, publisher=_PUB)
    sol = reverse_solution(client, "new_Core")
    assert len(sol.refs) == 1
    ref = sol.refs[0]
    assert ref.object_id == "x-guid"
    assert ref.note and "999" in ref.note


def test_reverse_missing_solution_raises():
    client = ReverseFakeClient(None, [])
    with pytest.raises(ValueError):
        reverse_solution(client, "nope")


def test_reverse_missing_publisher_is_tolerated():
    client = ReverseFakeClient(_SOL, [], publisher=None)
    sol = reverse_solution(client, "new_Core")
    assert sol.publisher is None  # no publisher, but no raise


def test_reverse_codegen_round_trip():
    from framework_power.solution_codegen import solution_to_python_source

    client = ReverseFakeClient(
        _SOL,
        [{"componenttype": 1, "objectid": "tbl-1"}, {"componenttype": 999, "objectid": "x"}],
        publisher=_PUB,
    )
    sol = reverse_solution(client, "new_Core")
    src = solution_to_python_source(sol)
    compile(src, "new_Core.py", "exec")
    ns: dict = {}
    exec(src, ns)
    sol2 = ns["SOLUTION"]
    assert sol2.tables == sol.tables
    assert sol2.publisher == sol.publisher
    assert len(sol2.refs) == len(sol.refs)
