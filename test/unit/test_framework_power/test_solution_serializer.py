"""Unit tests for framework_power.components.serializer."""

import pytest

from framework_power.components.models import Publisher, Solution
from framework_power.components.serializer import serialize_publisher, serialize_solution

pytestmark = pytest.mark.unit


def test_serialize_publisher_keys():
    p = Publisher(name="Pub", display_name="Pub Display", prefix="new", description="d")
    out = serialize_publisher(p)
    assert out == {
        "uniquename": "Pub",
        "friendlyname": "Pub Display",
        "customizationprefix": "new",
        "description": "d",
    }


def test_serialize_publisher_omits_empty_description():
    out = serialize_publisher(Publisher(name="P", display_name="P", prefix="new"))
    assert "description" not in out


def test_serialize_solution_basic():
    out = serialize_solution(Solution(unique_name="new_Core", friendly_name="Core"))
    assert out["uniquename"] == "new_Core"
    assert out["friendlyname"] == "Core"
    assert out["version"] == "1.0.0.0"
    assert out["ismanaged"] is False
    assert out["isvisible"] is True
    assert "publisherid@odata.bind" not in out
    assert out["description"] == "Solution: Core"


def test_serialize_solution_with_publisher_binding():
    out = serialize_solution(
        Solution(unique_name="new_Core", friendly_name="Core"), publisher_id="GUID-1"
    )
    assert out["publisherid@odata.bind"] == "/publishers(GUID-1)"
