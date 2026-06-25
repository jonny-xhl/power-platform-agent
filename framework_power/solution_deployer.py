"""
Idempotent solution deployer (framework_power Phase 2).

``deploy_solution`` reconciles a desired :class:`Solution` against the live
Dataverse environment using the documented 5-step flow:

    1. ensure publisher exists
    2. create/update the solution object
    3. deploy each component (in dependency order) via the component registry
    4. add every custom component to the solution
    5. publish all customizations

It is never destructive (no deletes). Standard (non-publisher-prefixed) components
are reference-only (e.g. from a reverse snapshot) and are NOT deployed or added —
so re-deploying a full snapshot is safe and idempotent. "already in solution" /
"duplicate" add errors are treated as benign skips.

``plan_solution`` is the read-only counterpart (all ``would_*`` actions, no writes).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .components import COMPONENT_DEPLOY_ORDER, COMPONENT_TYPES
from .components.models import Publisher, Solution
from .components.serializer import serialize_publisher, serialize_solution
from .deployer import _is_already_exists, _is_custom
from .lint import ERROR, WARNING, Issue
from .registry import DEFAULT_DEFINITIONS_DIR, deploy_order, get_definition

logger = logging.getLogger(__name__)

PUBLISHERS_CONFIG = "config/publishers.yaml"


@dataclass
class SolutionDeployConfig:
    """Tunables for metadata propagation waits and the sleep primitive."""

    after_publisher_create_delay: float = 3.0
    after_solution_create_delay: float = 5.0
    after_component_create_delay: float = 1.0
    between_adds_delay: float = 0.5
    sleep: Callable[[float], None] = time.sleep


# ----------------------------------------------------------------- publisher


def _load_publishers_config(config_path: str = PUBLISHERS_CONFIG) -> dict[str, Any]:
    try:
        import yaml

        if not Path(config_path).exists():
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        return {}


def resolve_publisher(
    solution: Solution, config_path: str = PUBLISHERS_CONFIG
) -> Publisher:
    """Resolve a solution's publisher: inline > config key > current default.

    Field names mirror ``config/publishers.yaml`` (name/display_name/prefix).
    """
    if solution.publisher is not None:
        return solution.publisher
    cfg = _load_publishers_config(config_path)
    publishers = cfg.get("publishers", {})
    key = solution.publisher_key or cfg.get("current") or "default"
    info = publishers.get(key)
    if info:
        return Publisher(
            name=info.get("name", key),
            display_name=info.get("display_name", info.get("name", key)),
            prefix=info.get("prefix", "new"),
            description=info.get("description"),
        )
    return Publisher(name=key, display_name=key, prefix="new")


def _validate_version(version: str) -> bool:
    """True if ``version`` matches Dataverse ``X.Y.Z.W``."""
    parts = (version or "").split(".")
    return len(parts) == 4 and all(p.isdigit() for p in parts)


def lint_solution(solution: Solution, *, prefix: str = "new") -> list[Issue]:
    """Offline convention checks for a Solution definition (no network)."""
    issues: list[Issue] = []
    if not solution.unique_name:
        issues.append(Issue(ERROR, "solution.unique_name is required."))
    if not _validate_version(solution.version):
        issues.append(
            Issue(ERROR, f"solution.version must be 'X.Y.Z.W', got: {solution.version!r}.")
        )
    seen_tables: set[str] = set()
    for name in solution.tables:
        if name in seen_tables:
            issues.append(Issue(WARNING, f"Duplicate table ref in solution: '{name}'."))
        seen_tables.add(name)
    if solution.publisher is None and solution.publisher_key is None:
        issues.append(
            Issue(WARNING, "Solution has no publisher/publisher_key; the config default will be used.")
        )
    return issues


# ----------------------------------------------------------------- helpers


def _model_identity_name(type_key: str, model: Any) -> str:
    """The schema/name used for the publisher-prefix (custom) check."""
    if type_key == "table":
        return getattr(model, "schema_name", "")
    return getattr(model, "name", "") or ""


def _is_model_custom(type_key: str, model: Any, prefix: str) -> bool:
    return _is_custom(_model_identity_name(type_key, model), prefix)


def _iter_solution_models(
    solution: Solution,
    type_key: str,
    definitions_dir: str,
    prefix: str,
    result: dict[str, Any],
) -> list[tuple[str, Any]]:
    """Yield ``(label, model)`` for one component type within the solution.

    Tables are resolved from name refs (``metadata_py/tables/<name>.py``) and
    returned in dependency order. A missing name ref is a hard failure only when it
    is custom (prefixed) — a standard/system name ref with no local definition is
    recorded as ``skipped_standard`` so a reverse snapshot re-deploys safely.
    """
    if type_key == "table":
        defs: dict[str, Any] = {}
        for name in solution.tables:
            try:
                defs[name] = get_definition(name, definitions_dir)
            except KeyError:
                if _is_custom(name, prefix):
                    result["components"].append(
                        {
                            "type": "table",
                            "name": name,
                            "deploy": {
                                "action": "failed",
                                "error": f"definition '{name}' not found in '{definitions_dir}'",
                            },
                        }
                    )
                else:
                    result["components"].append(
                        {
                            "type": "table",
                            "name": name,
                            "deploy": {
                                "action": "skipped_standard",
                                "note": "no local definition (standard/system component)",
                            },
                        }
                    )
        order = deploy_order(defs) if defs else []
        return [(name, defs[name].table) for name in order]
    return [
        (getattr(m, "name", type_key), m)
        for m in getattr(solution, type_key + "s", [])
    ]


def _ref_type_code(type_str: str) -> Any:
    """Resolve a ComponentRef ``type`` to an AddSolutionComponent code (or None)."""
    if not type_str:
        return None
    if type_str in COMPONENT_TYPES:
        return COMPONENT_TYPES[type_str].solution_component_type
    try:
        return int(type_str)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------- deploy


def deploy_solution(
    client: Any,
    solution: Solution,
    *,
    definitions_dir: str = DEFAULT_DEFINITIONS_DIR,
    prefix: str = "new",
    config: SolutionDeployConfig | None = None,
) -> dict[str, Any]:
    """Deploy (create/sync) a ``Solution`` to Dataverse (non-destructive, idempotent).

    Returns a result dict with ``publisher`` / ``solution_object`` / ``components`` /
    ``added`` / ``publish`` summaries.
    """
    cfg = config or SolutionDeployConfig()
    result: dict[str, Any] = {
        "solution": solution.unique_name,
        "publisher": {},
        "solution_object": {},
        "components": [],
        "added": [],
        "publish": {},
    }

    # ---- STEP 1: ensure publisher ----
    publisher = resolve_publisher(solution)
    try:
        pub_result = client.ensure_publisher_exists(serialize_publisher(publisher))
        result["publisher"] = {"uniquename": publisher.name, **pub_result}
        if pub_result.get("created"):
            cfg.sleep(cfg.after_publisher_create_delay)
    except Exception as e:  # noqa: BLE001
        result["publisher"] = {"uniquename": publisher.name, "action": "failed", "error": str(e)}
        logger.warning(f"Publisher ensure failed for '{publisher.name}': {e}")

    publisher_id = result["publisher"].get("publisherid")

    # ---- STEP 2: ensure solution object ----
    existing = client.get_solution_by_name(solution.unique_name)
    if existing is None:
        try:
            client.create_solution(serialize_solution(solution, publisher_id=publisher_id))
            result["solution_object"] = {"action": "created"}
            cfg.sleep(cfg.after_solution_create_delay)
        except Exception as e:  # noqa: BLE001
            result["solution_object"] = {"action": "failed", "error": str(e)}
    elif solution.version and existing.get("version") != solution.version:
        try:
            client.update_solution_version(solution.unique_name, solution.version)
            result["solution_object"] = {"action": "updated", "version": solution.version}
        except Exception as e:  # noqa: BLE001
            result["solution_object"] = {"action": "update_failed", "error": str(e)}
    else:
        result["solution_object"] = {"action": "exists"}

    # ---- STEP 3: deploy components (dependency order) ----
    add_targets: list[tuple[int, str, str]] = []  # (type_code, object_id, label)
    for type_key in COMPONENT_DEPLOY_ORDER:
        ctype = COMPONENT_TYPES.get(type_key)
        if ctype is None:
            continue
        for label, model in _iter_solution_models(solution, type_key, definitions_dir, prefix, result):
            if not _is_model_custom(type_key, model, prefix):
                result["components"].append(
                    {"type": type_key, "name": label, "deploy": {"action": "skipped_standard"}}
                )
                continue
            try:
                deploy_entry = ctype.deploy(client, model, prefix=prefix)
            except Exception as e:  # noqa: BLE001
                result["components"].append(
                    {"type": type_key, "name": label, "deploy": {"action": "failed", "error": str(e)}}
                )
                continue
            result["components"].append({"type": type_key, "name": label, "deploy": deploy_entry})
            cfg.sleep(cfg.after_component_create_delay)
            try:
                oid = ctype.resolve_id(client, model)
            except Exception:  # noqa: BLE001
                oid = None
            if oid:
                add_targets.append((ctype.solution_component_type, str(oid), label))

    # ---- STEP 4: add custom components (and explicit refs) to the solution ----
    for code, oid, label in add_targets:
        _add_one(client, solution.unique_name, code, oid, label, result, cfg)

    for ref in solution.refs:
        code = _ref_type_code(ref.type)
        oid = ref.object_id
        if not oid and ref.type == "table" and ref.name:
            try:
                oid = client.get_entity_metadata(ref.name.lower()).get("MetadataId")
            except Exception:  # noqa: BLE001
                oid = None
        if code and oid:
            _add_one(client, solution.unique_name, int(code), str(oid), ref.name or str(oid), result, cfg)
        else:
            result["added"].append(
                {"type": ref.type, "name": ref.name, "action": "skipped", "note": "unresolved ref"}
            )

    # ---- STEP 5: publish ----
    try:
        result["publish"] = client.publish_all_xml()
    except Exception as e:  # noqa: BLE001
        result["publish"] = {"published": False, "error": str(e)}
        logger.warning(f"Publish failed: {e}")

    return result


def _add_one(
    client: Any,
    unique_name: str,
    code: int,
    oid: str,
    label: str,
    result: dict[str, Any],
    cfg: SolutionDeployConfig,
) -> None:
    """Add one component to the solution; "already in solution" is a benign skip."""
    try:
        client.add_solution_component(unique_name, code, oid)
        result["added"].append(
            {"component_type": code, "object_id": oid, "name": label, "action": "added"}
        )
    except Exception as e:  # noqa: BLE001
        if _is_already_exists(e):
            result["added"].append(
                {"component_type": code, "object_id": oid, "name": label, "action": "already_in_solution"}
            )
        else:
            result["added"].append(
                {"component_type": code, "object_id": oid, "name": label, "action": "failed", "error": str(e)}
            )
    cfg.sleep(cfg.between_adds_delay)


# ----------------------------------------------------------------- plan


def plan_solution(
    client: Any,
    solution: Solution,
    *,
    definitions_dir: str = DEFAULT_DEFINITIONS_DIR,
    prefix: str = "new",
) -> dict[str, Any]:
    """Read-only dry run: compute what ``deploy_solution`` would do, with NO writes."""
    result: dict[str, Any] = {
        "solution": solution.unique_name,
        "publisher": {},
        "solution_object": {},
        "components": [],
        "added": [],
        "publish": {},
    }

    publisher = resolve_publisher(solution)
    existing_pub = client.get_publisher_by_name(publisher.name)
    result["publisher"] = {
        "uniquename": publisher.name,
        "action": "exists" if existing_pub else "would_create",
    }

    existing_sol = client.get_solution_by_name(solution.unique_name)
    if existing_sol is None:
        result["solution_object"] = {"action": "would_create"}
    elif solution.version and existing_sol.get("version") != solution.version:
        result["solution_object"] = {"action": "would_update_version", "version": solution.version}
    else:
        result["solution_object"] = {"action": "exists"}

    for type_key in COMPONENT_DEPLOY_ORDER:
        ctype = COMPONENT_TYPES.get(type_key)
        if ctype is None:
            continue
        for label, model in _iter_solution_models(solution, type_key, definitions_dir, prefix, result):
            if not _is_model_custom(type_key, model, prefix):
                result["components"].append(
                    {"type": type_key, "name": label, "plan": {"action": "would_skip_standard"}}
                )
                continue
            try:
                plan_entry = ctype.plan(client, model, prefix=prefix)
            except Exception as e:  # noqa: BLE001
                plan_entry = {"action": "failed", "error": str(e)}
            result["components"].append({"type": type_key, "name": label, "plan": plan_entry})
            result["added"].append({"type": type_key, "name": label, "action": "would_add"})

    for ref in solution.refs:
        result["added"].append(
            {"type": ref.type, "name": ref.name, "action": "would_add" if ref.object_id else "would_resolve"}
        )

    result["publish"] = {"action": "would_publish"}
    return result
