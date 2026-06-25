"""
Serializers for solution-container models (framework_power Phase 2).

Model -> Dataverse Web API JSON for the container types (publisher + solution).
Per-type component serializers (optionset, webresource, form, view, plugin) live
alongside their deployer/reverse/codegen modules and are added in later waves.
"""

from __future__ import annotations

from typing import Any, Optional

from .models import Publisher, Solution


def serialize_publisher(pub: Publisher) -> dict[str, Any]:
    """Publisher -> Web API payload (``uniquename``/``friendlyname``/...)."""
    payload: dict[str, Any] = {
        "uniquename": pub.name,
        "friendlyname": pub.display_name,
        "customizationprefix": pub.prefix,
    }
    if pub.description:
        payload["description"] = pub.description
    return payload


def serialize_solution(
    sol: Solution,
    publisher_id: Optional[str] = None,
) -> dict[str, Any]:
    """Solution -> Web API create payload (incl. ``publisherid@odata.bind``).

    Args:
        sol: The solution model.
        publisher_id: Resolved publisher GUID (from ``ensure_publisher_exists``);
            when provided, the solution is bound to it via OData navigation.
    """
    payload: dict[str, Any] = {
        "uniquename": sol.unique_name,
        "friendlyname": sol.friendly_name,
        "version": sol.version,
        "ismanaged": False,
        "isvisible": True,
        "description": sol.description or f"Solution: {sol.friendly_name}",
    }
    if publisher_id:
        payload["publisherid@odata.bind"] = f"/publishers({publisher_id})"
    return payload
