"""
Global OptionSet sync standalone flow (framework_power Phase 9).

The solution-aware wrapper that global optionset — unlike form/view/webresource/ribbon — previously
lacked (it only had the registry handler in ``components/optionset.py``). Treats authored
``GlobalOptionSet`` models as the source of truth and reconciles them against Dataverse. Global
optionsets are create-only: option values cannot be PATCHed, so a differing existing optionset
reports ``manual_update_required``.

Flows:
- ``load_optionset``  — load a ``GlobalOptionSet`` from a module exporting ``OPTIONSET``.
- ``plan_optionsets`` — read-only: per-optionset ``would_create`` / ``would_skip`` /
  ``manual_update_required`` / ``would_skip_standard``.
- ``sync_optionsets`` — create/exists each (reuses the Phase-2 ``components.optionset`` handler),
  optional add to a solution (code 9; idempotent).

Non-destructive: ``sync`` only creates (never deletes, never PATCHes options). Optionsets publish
org-wide via the caller's ``PublishAllXml`` (there is no targeted per-optionset publish), so this
flow does not publish individually — the workflow's final publish covers it.
"""

from __future__ import annotations

import importlib.util
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .components import optionset as optionset_component
from .components.models import GlobalOptionSet
from .deployer import _is_already_exists

logger = logging.getLogger(__name__)

# Actions that yield no addable id (standard/manual/fail) — skip the solution add for these.
_NO_ID_ACTIONS = frozenset({"skipped_standard", "manual_update_required", "failed"})


def load_optionset(path: Any) -> GlobalOptionSet:
    """Load a ``GlobalOptionSet`` from a Python module file that exports ``OPTIONSET``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"_optionset_def_{path.stem}", str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load optionset definition file: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    optionset = getattr(mod, "OPTIONSET", None)
    if not isinstance(optionset, GlobalOptionSet):
        raise ValueError(f"{path} does not export a GlobalOptionSet as `OPTIONSET`")
    return optionset


@dataclass
class OptionSetSyncConfig:
    """Tunables for inter-operation sleeps (metadata propagation)."""

    after_create_delay: float = 0.5
    between_adds_delay: float = 0.3
    sleep: Callable[[float], None] = time.sleep


# ----------------------------------------------------------------- plan


def plan_optionsets(client: Any, optionsets: list[GlobalOptionSet], *, prefix: str = "new") -> dict[str, Any]:
    """Read-only dry run over authored optionsets (no writes)."""
    entries: list[dict[str, Any]] = []
    for optionset in optionsets:
        try:
            entry = optionset_component.plan(client, optionset, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            entry = {"action": "failed", "error": str(e)}
        entries.append({"name": optionset.name, "plan": entry})
    return {"optionsets": entries}


# ----------------------------------------------------------------- sync


def sync_optionsets(
    client: Any,
    optionsets: list[GlobalOptionSet],
    *,
    prefix: str = "new",
    solution: Optional[str] = None,
    config: Optional[OptionSetSyncConfig] = None,
) -> dict[str, Any]:
    """Sync authored global optionsets to Dataverse (non-destructive, idempotent).

    Deploys each (create-only via the Phase-2 handler). When ``solution`` is given, adds every
    created/existing optionset to that solution (code 9; idempotent). Optionsets publish org-wide
    via the caller's ``PublishAllXml`` — this flow does not publish individually.
    """
    cfg = config or OptionSetSyncConfig()
    result: dict[str, Any] = {"synced": [], "added": []}

    ids: list[str] = []
    for optionset in optionsets:
        try:
            deploy_entry = optionset_component.deploy(client, optionset, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": optionset.name, "deploy": {"action": "failed", "error": str(e)}})
            continue
        result["synced"].append({"name": optionset.name, "deploy": deploy_entry})
        if isinstance(deploy_entry, dict) and deploy_entry.get("action") not in _NO_ID_ACTIONS:
            oid = deploy_entry.get("id")
            if oid:
                ids.append(str(oid))
        cfg.sleep(cfg.after_create_delay)

    if solution and ids:
        for oid in ids:
            try:
                client.add_solution_component(solution, optionset_component.SOLUTION_CODE, oid)
                result["added"].append({"name": solution, "object_id": oid, "action": "added"})
            except Exception as e:  # noqa: BLE001
                if _is_already_exists(e):
                    result["added"].append(
                        {"name": solution, "object_id": oid, "action": "already_in_solution"}
                    )
                else:
                    result["added"].append(
                        {"name": solution, "object_id": oid, "action": "failed", "error": str(e)}
                    )
            cfg.sleep(cfg.between_adds_delay)

    return result


__all__ = ["OptionSetSyncConfig", "load_optionset", "plan_optionsets", "sync_optionsets"]
