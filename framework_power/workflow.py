"""
Cross-phase development workflow (framework_power Phase 9).

A thin orchestration layer that runs the full Dataverse development chain end-to-end across
**two solutions**, driven by a single explicit project manifest
(``metadata_py/project.py``)::

    Global Optionset -> Entity (+ Relationship) -> webresource -> plugin -> form -> view -> [roles] -> ribbon
    |<----------------------- main solution ----------------------->|                |<-- ribbon soln -->|

Every stage **self-manages its solution membership** (each deploy/sync function takes ``solution=``),
so this orchestrator does NO manual ``add_solution_component`` — it only sequences the stages in
dependency order, ensures the two solution shells exist, and runs a final org-wide publish (which
covers optionset/table metadata going live).

Two solutions (user-confirmed): a **main** solution holds everything except ribbon; a **dedicated
ribbon** solution holds the ribbon customizations (ribbon has no Web API write path — it deploys via
``sync_ribbons``' Export/Import round-trip, so it cannot share the main solution's AddSolutionComponent
flow).

Flows:
- ``load_project``   — load a ``Project`` from a module exporting ``PROJECT``.
- ``lint_workflow``  — offline manifest checks (no client).
- ``plan_workflow``  — read-only dry run (all ``would_*``; no writes, no solution ensure).
- ``deploy_workflow`` — run the chain: ensure solutions -> stages in order -> final PublishAllXml.

Non-destructive throughout (create/update/add only; standard components skipped).
"""

from __future__ import annotations

import importlib.util
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .components.models import Publisher, Solution
from .components.serializer import serialize_publisher, serialize_solution
from .deployer import deploy_table, plan_table
from .form_sync import load_form, plan_forms, sync_forms
from .lint import ERROR, WARNING, Issue
from .optionset_sync import load_optionset, plan_optionsets, sync_optionsets
from .plugin_sync import deploy_plugin
from .registry import DEFAULT_DEFINITIONS_DIR, deploy_order, get_definition
from .ribbon_sync import load_ribbon, plan_ribbons, sync_ribbons
from .role_deployer import deploy_role, plan_role
from .role_registry import DEFAULT_ROLES_DIR, get_role_definition
from .solution_deployer import SolutionDeployConfig, _validate_version
from .view_sync import load_view, plan_views, sync_views
from .webresource_sync import plan_webresources, sync_webresources

logger = logging.getLogger(__name__)

DEFAULT_OPTIONSETS_DIR = "metadata_py/optionsets"
DEFAULT_FORMS_DIR = "metadata_py/forms"
DEFAULT_VIEWS_DIR = "metadata_py/views"
DEFAULT_RIBBONS_DIR = "metadata_py/ribbons"
DEFAULT_WEBRESOURCES_ROOT = "webresources"
DEFAULT_PROJECT_PATH = "metadata_py/project.py"

# Canonical development chain order (user-confirmed). `roles` is opt-in (include_roles).
WORKFLOW_STAGE_ORDER: tuple[str, ...] = (
    "optionsets",
    "tables",
    "webresources",
    "plugins",
    "forms",
    "views",
    "roles",
    "ribbon",
)


# ----------------------------------------------------------------- manifest


@dataclass
class Project:
    """Explicit project manifest: the two solutions + every component by name/path.

    Component lists are **stems** resolved against their type's default dir
    (``<dir>/<stem>.py``), except ``plugins`` (project dirs) and ``webresources`` (bool: sync the
    whole ``webresources_root`` dir). ``tables``/``roles`` are name refs resolved via their
    registries (``get_definition`` / ``get_role_definition``).
    """

    main_solution: str
    ribbon_solution: str
    publisher: Optional[Publisher] = None
    version: str = "1.0.0.0"
    friendly_name: Optional[str] = None
    description: Optional[str] = None
    optionsets: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    webresources: bool = False
    plugins: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    ribbons: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    # dirs (overridable; mirror the per-phase CLIs)
    optionsets_dir: str = DEFAULT_OPTIONSETS_DIR
    tables_dir: str = DEFAULT_DEFINITIONS_DIR
    forms_dir: str = DEFAULT_FORMS_DIR
    views_dir: str = DEFAULT_VIEWS_DIR
    ribbons_dir: str = DEFAULT_RIBBONS_DIR
    roles_dir: str = DEFAULT_ROLES_DIR
    webresources_root: str = DEFAULT_WEBRESOURCES_ROOT


def load_project(path: Any) -> Project:
    """Load a :class:`Project` from a Python module file that exports ``PROJECT``."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(
        f"_project_{path.stem}_{uuid.uuid4().hex[:8]}", str(path)
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load project manifest: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    project = getattr(mod, "PROJECT", None)
    if not isinstance(project, Project):
        raise ValueError(f"{path} does not export a Project as `PROJECT`")
    return project


# ----------------------------------------------------------------- stage selection


def _content_stages(project: Project) -> list[str]:
    """Stages that have something configured, ordered by :data:`WORKFLOW_STAGE_ORDER`."""
    present: set[str] = set()
    if project.optionsets:
        present.add("optionsets")
    if project.tables:
        present.add("tables")
    if project.webresources:
        present.add("webresources")
    if project.plugins:
        present.add("plugins")
    if project.forms:
        present.add("forms")
    if project.views:
        present.add("views")
    if project.roles:
        present.add("roles")
    if project.ribbons:
        present.add("ribbon")
    return [s for s in WORKFLOW_STAGE_ORDER if s in present]


def _active_stages(
    project: Project,
    *,
    include_roles: bool,
    skip: Optional[set[str]] = None,
    only: Optional[set[str]] = None,
) -> list[str]:
    stages = _content_stages(project)
    if not include_roles:
        stages = [s for s in stages if s != "roles"]
    if skip:
        stages = [s for s in stages if s not in skip]
    if only:
        stages = [s for s in stages if s in only]
    return stages


def _load_models(
    stems: list[str], directory: str, loader: Any
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Load one model per ``<directory>/<stem>.py``. Returns (models, load_errors)."""
    models: list[Any] = []
    errors: list[dict[str, Any]] = []
    for stem in stems:
        path = Path(directory) / f"{stem}.py"
        try:
            models.append(loader(path))
        except Exception as e:  # noqa: BLE001
            errors.append({"stem": stem, "path": str(path), "error": str(e)})
    return models, errors


def _with_errors(result: dict[str, Any], errors: list[dict[str, Any]]) -> dict[str, Any]:
    if errors:
        result["load_errors"] = errors
    return result


# ----------------------------------------------------------------- solution shells


def _ensure_solutions(
    client: Any, project: Project, *, prefix: str, cfg: SolutionDeployConfig
) -> dict[str, Any]:
    """Ensure the publisher + both solution shells exist (create if missing, bump version if stale)."""
    publisher = project.publisher or Publisher(name=prefix, display_name=prefix, prefix=prefix)
    try:
        pub_result = client.ensure_publisher_exists(serialize_publisher(publisher))
        pub_info = {"uniquename": publisher.name, **(pub_result if isinstance(pub_result, dict) else {})}
        if pub_result.get("created") if isinstance(pub_result, dict) else False:
            cfg.sleep(cfg.after_publisher_create_delay)
    except Exception as e:  # noqa: BLE001
        pub_info = {"uniquename": publisher.name, "action": "failed", "error": str(e)}
        logger.warning(f"Publisher ensure failed for '{publisher.name}': {e}")
    publisher_id = pub_info.get("publisherid")

    shells: dict[str, Any] = {}
    for key, name in (("main", project.main_solution), ("ribbon", project.ribbon_solution)):
        shells[key] = _ensure_one_solution(client, name, project, publisher_id, cfg)
    return {"publisher": pub_info, **shells}


def _ensure_one_solution(
    client: Any, name: str, project: Project, publisher_id: Optional[str], cfg: SolutionDeployConfig
) -> dict[str, Any]:
    existing = client.get_solution_by_name(name)
    if existing is None:
        shell = Solution(
            unique_name=name,
            friendly_name=project.friendly_name or name,
            version=project.version,
            description=project.description,
        )
        try:
            client.create_solution(serialize_solution(shell, publisher_id=publisher_id))
            cfg.sleep(cfg.after_solution_create_delay)
            return {"name": name, "action": "created"}
        except Exception as e:  # noqa: BLE001
            return {"name": name, "action": "failed", "error": str(e)}
    if project.version and existing.get("version") != project.version:
        try:
            client.update_solution_version(name, project.version)
            return {"name": name, "action": "updated", "version": project.version}
        except Exception as e:  # noqa: BLE001
            return {"name": name, "action": "update_failed", "error": str(e)}
    return {"name": name, "action": "exists"}


# ----------------------------------------------------------------- deploy


def deploy_workflow(
    client: Any,
    project: Project,
    *,
    prefix: str = "new",
    include_roles: bool = False,
    skip: Optional[set[str]] = None,
    only: Optional[set[str]] = None,
    publish: bool = True,
    config: Optional[SolutionDeployConfig] = None,
) -> dict[str, Any]:
    """Run the full development chain across the main + ribbon solutions.

    Every stage self-manages its solution membership (``solution=main`` or ``ribbon``); this
    orchestrator does no manual ``add_solution_component``. Non-destructive throughout.

    Args:
        client: Authenticated ``DataverseClient``.
        project: The resolved :class:`Project` manifest.
        prefix: Publisher prefix for the custom-component check.
        include_roles: Run the (opt-in) role-privilege-sync stage.
        skip: Stage names to skip (e.g. ``{"plugins"}`` to skip the .NET build).
        only: Restrict to these stage names (intersect with the content stages).
        publish: Final org-wide ``PublishAllXml`` (covers optionset/table metadata going live).
    """
    cfg = config or SolutionDeployConfig()
    main = project.main_solution
    ribbon = project.ribbon_solution
    result: dict[str, Any] = {
        "project": {
            "main_solution": main,
            "ribbon_solution": ribbon,
            "version": project.version,
        },
        "solutions": {},
        "stages": {},
        "publish": {},
    }

    # Step 0: ensure publisher + both solution shells.
    result["solutions"] = _ensure_solutions(client, project, prefix=prefix, cfg=cfg)

    # Steps 1..n: run each active stage (self-managing solution membership), in chain order.
    stages = _active_stages(
        project, include_roles=include_roles, skip=skip or set(), only=only
    )
    for stage in stages:
        try:
            result["stages"][stage] = _run_stage(
                client, stage, project, main=main, ribbon=ribbon, prefix=prefix, publish=publish, cfg=cfg
            )
        except Exception as e:  # noqa: BLE001
            result["stages"][stage] = {"action": "failed", "error": str(e)}
            logger.warning(f"Stage '{stage}' failed: {e}")

    # Final publish: optionset/table metadata need PublishAllXml to go live; other stages already
    # published granularly (webresource targeted, form/view per-entity, ribbon via import).
    if publish:
        try:
            result["publish"] = client.publish_all_xml()
        except Exception as e:  # noqa: BLE001
            result["publish"] = {"published": False, "error": str(e)}
            logger.warning(f"PublishAllXml failed: {e}")

    return result


def _run_stage(
    client: Any,
    stage: str,
    project: Project,
    *,
    main: str,
    ribbon: str,
    prefix: str,
    publish: bool,
    cfg: SolutionDeployConfig,
) -> dict[str, Any]:
    """Dispatch one stage to its self-managing deploy function (``solution=main`` / ``ribbon``)."""
    if stage == "optionsets":
        models, errs = _load_models(project.optionsets, project.optionsets_dir, load_optionset)
        return _with_errors(sync_optionsets(client, models, prefix=prefix, solution=main), errs)

    if stage == "tables":
        return _deploy_tables(client, project, main=main, prefix=prefix, cfg=cfg)

    if stage == "webresources":
        return sync_webresources(
            client, Path(project.webresources_root), prefix=prefix, solution=main, publish=publish
        )

    if stage == "plugins":
        return _deploy_plugins(client, project, main=main, prefix=prefix)

    if stage == "forms":
        models, errs = _load_models(project.forms, project.forms_dir, load_form)
        return _with_errors(sync_forms(client, models, prefix=prefix, solution=main, publish=publish), errs)

    if stage == "views":
        models, errs = _load_models(project.views, project.views_dir, load_view)
        return _with_errors(sync_views(client, models, prefix=prefix, solution=main, publish=publish), errs)

    if stage == "roles":
        return _deploy_roles(client, project, main=main, prefix=prefix)

    if stage == "ribbon":
        models, errs = _load_models(project.ribbons, project.ribbons_dir, load_ribbon)
        return _with_errors(
            sync_ribbons(client, models, prefix=prefix, solution=ribbon, publish=publish), errs
        )

    return {"action": "unknown_stage", "stage": stage}


def _deploy_tables(
    client: Any, project: Project, *, main: str, prefix: str, cfg: SolutionDeployConfig
) -> dict[str, Any]:
    """Deploy tables in dependency order; ``deploy_table(solution=main)`` self-adds each (code 1)."""
    defs: dict[str, Any] = {}
    missing: list[str] = []
    for name in project.tables:
        try:
            defs[name] = get_definition(name, project.tables_dir)
        except KeyError:
            missing.append(name)
    order = deploy_order(defs) if defs else []
    synced: list[dict[str, Any]] = []
    for name in order:
        try:
            entry = deploy_table(client, defs[name].table, prefix=prefix, solution=main)
        except Exception as e:  # noqa: BLE001
            entry = {"schema_name": name, "entity": {"action": "failed", "error": str(e)}}
        synced.append({"name": name, "deploy": entry})
        cfg.sleep(cfg.after_component_create_delay)
    result: dict[str, Any] = {"synced": synced, "solution": main}
    if missing:
        result["missing_definitions"] = missing
    return result


def _deploy_plugins(client: Any, project: Project, *, main: str, prefix: str) -> dict[str, Any]:
    """Build + deploy each plugin project; ``deploy_plugin(solution=main)`` self-adds (10030/+92)."""
    synced: list[dict[str, Any]] = []
    for pdir in project.plugins:
        try:
            entry = deploy_plugin(client, pdir, prefix=prefix, solution=main)
        except Exception as e:  # noqa: BLE001
            synced.append({"project": pdir, "action": "failed", "error": str(e)})
            continue
        synced.append({"project": pdir, "deploy": entry})
    return {"synced": synced, "solution": main}


def _deploy_roles(client: Any, project: Project, *, main: str, prefix: str) -> dict[str, Any]:
    """Sync each role's privileges; ``deploy_role(solution=main)`` self-adds the role (code 20)."""
    synced: list[dict[str, Any]] = []
    for name in project.roles:
        try:
            role = get_role_definition(name, project.roles_dir).role
        except Exception as e:  # noqa: BLE001
            synced.append({"role": name, "action": "failed", "error": str(e)})
            continue
        try:
            entry = deploy_role(client, role, prefix=prefix, solution=main)
        except Exception as e:  # noqa: BLE001
            synced.append({"role": name, "action": "failed", "error": str(e)})
            continue
        synced.append({"role": name, "deploy": entry})
    return {"synced": synced, "solution": main}


# ----------------------------------------------------------------- plan


def plan_workflow(
    client: Any,
    project: Project,
    *,
    prefix: str = "new",
    include_roles: bool = False,
    skip: Optional[set[str]] = None,
    only: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Read-only dry run of the whole chain (all ``would_*``; no writes, no solution ensure)."""
    result: dict[str, Any] = {
        "project": {
            "main_solution": project.main_solution,
            "ribbon_solution": project.ribbon_solution,
            "version": project.version,
        },
        "stages": {},
    }
    stages = _active_stages(
        project, include_roles=include_roles, skip=skip or set(), only=only
    )
    for stage in stages:
        try:
            result["stages"][stage] = _plan_stage(
                client, stage, project, ribbon=project.ribbon_solution, prefix=prefix
            )
        except Exception as e:  # noqa: BLE001
            result["stages"][stage] = {"action": "failed", "error": str(e)}
    return result


def _plan_stage(
    client: Any, stage: str, project: Project, *, ribbon: str, prefix: str
) -> dict[str, Any]:
    if stage == "optionsets":
        models, errs = _load_models(project.optionsets, project.optionsets_dir, load_optionset)
        return _with_errors(plan_optionsets(client, models, prefix=prefix), errs)
    if stage == "tables":
        return _plan_tables(client, project, prefix=prefix)
    if stage == "webresources":
        return plan_webresources(client, Path(project.webresources_root), prefix=prefix)
    if stage == "plugins":
        return _plan_plugins(project)
    if stage == "forms":
        models, errs = _load_models(project.forms, project.forms_dir, load_form)
        return _with_errors(plan_forms(client, models, prefix=prefix), errs)
    if stage == "views":
        models, errs = _load_models(project.views, project.views_dir, load_view)
        return _with_errors(plan_views(client, models, prefix=prefix), errs)
    if stage == "roles":
        return _plan_roles(client, project, prefix=prefix)
    if stage == "ribbon":
        models, errs = _load_models(project.ribbons, project.ribbons_dir, load_ribbon)
        return _with_errors(plan_ribbons(client, models, prefix=prefix, solution=ribbon), errs)
    return {"action": "unknown_stage", "stage": stage}


def _plan_tables(client: Any, project: Project, *, prefix: str) -> dict[str, Any]:
    defs: dict[str, Any] = {}
    for name in project.tables:
        try:
            defs[name] = get_definition(name, project.tables_dir)
        except KeyError:
            pass
    order = deploy_order(defs) if defs else []
    entries: list[dict[str, Any]] = []
    for name in order:
        try:
            entries.append({"name": name, "plan": plan_table(client, defs[name].table, prefix=prefix)})
        except Exception as e:  # noqa: BLE001
            entries.append({"name": name, "plan": {"action": "failed", "error": str(e)}})
    return {"tables": entries, "solution": project.main_solution}


def _plan_plugins(project: Project) -> dict[str, Any]:
    """Plan plugins WITHOUT building (no dotnet). Reports configured steps/targets only."""
    from .client.plugin_build import load_plugin_project

    entries: list[dict[str, Any]] = []
    for pdir in project.plugins:
        def_path = Path(pdir) / "plugin_def.py"
        try:
            pcfg = load_plugin_project(def_path)
            entries.append(
                {
                    "project": pdir,
                    "assembly": pcfg.assembly_name,
                    "plan": {"action": "would_build_and_deploy", "steps": len(pcfg.steps)},
                }
            )
        except Exception as e:  # noqa: BLE001
            entries.append({"project": pdir, "plan": {"action": "failed", "error": str(e)}})
    return {"plugins": entries, "solution": project.main_solution}


def _plan_roles(client: Any, project: Project, *, prefix: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for name in project.roles:
        try:
            role = get_role_definition(name, project.roles_dir).role
            entries.append({"role": name, "plan": plan_role(client, role, prefix=prefix)})
        except Exception as e:  # noqa: BLE001
            entries.append({"role": name, "plan": {"action": "failed", "error": str(e)}})
    return {"roles": entries, "solution": project.main_solution}


# ----------------------------------------------------------------- lint


def _check_file(
    issues: list[Issue], directory: str, stem: str, label: str
) -> None:
    path = Path(directory) / f"{stem}.py"
    if not path.exists():
        issues.append(Issue(ERROR, f"{label} definition not found: {path}"))


def lint_workflow(project: Project, *, prefix: str = "new") -> list[Issue]:
    """Offline manifest checks (no network): required fields, version, referenced files/dirs."""
    issues: list[Issue] = []
    if not project.main_solution:
        issues.append(Issue(ERROR, "project.main_solution is required."))
    if not project.ribbon_solution:
        issues.append(Issue(ERROR, "project.ribbon_solution is required."))
    if (
        project.main_solution
        and project.ribbon_solution
        and project.main_solution == project.ribbon_solution
    ):
        issues.append(
            Issue(ERROR, "main_solution and ribbon_solution must differ (ribbon is a dedicated solution).")
        )
    if not _validate_version(project.version):
        issues.append(Issue(ERROR, f"project.version must be 'X.Y.Z.W', got: {project.version!r}."))
    if project.publisher is None:
        issues.append(Issue(WARNING, "project.publisher is None; the prefix default publisher will be used."))

    for stem in project.optionsets:
        _check_file(issues, project.optionsets_dir, stem, "optionset")
    for name in project.tables:
        _check_file(issues, project.tables_dir, name, "table")
    for stem in project.forms:
        _check_file(issues, project.forms_dir, stem, "form")
    for stem in project.views:
        _check_file(issues, project.views_dir, stem, "view")
    for stem in project.ribbons:
        _check_file(issues, project.ribbons_dir, stem, "ribbon")
    for name in project.roles:
        _check_file(issues, project.roles_dir, name, "role")
    for pdir in project.plugins:
        p = Path(pdir)
        if not p.is_dir():
            issues.append(Issue(ERROR, f"plugin project dir not found: {pdir}"))
        elif not (p / "plugin_def.py").exists():
            issues.append(Issue(ERROR, f"plugin dir '{pdir}' has no plugin_def.py"))
    if project.webresources and not Path(project.webresources_root).is_dir():
        issues.append(Issue(WARNING, f"webresources root not found: {project.webresources_root}"))

    return issues


__all__ = [
    "Project",
    "load_project",
    "lint_workflow",
    "plan_workflow",
    "deploy_workflow",
    "WORKFLOW_STAGE_ORDER",
    "DEFAULT_PROJECT_PATH",
    "DEFAULT_OPTIONSETS_DIR",
]
