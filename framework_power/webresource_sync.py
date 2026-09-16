"""
Web resource directory sync (framework_power Phase 4).

A standalone flow that treats a **local directory** of web assets (JS/CSS/HTML/...) as the
source of truth and reconciles it against Dataverse web resources — the real-world workflow
for assets that change constantly (especially JS).

Naming convention (user-confirmed): the web resource name is ``{prefix}_/{relpath}`` where
``relpath`` is the file's path under the sync root (forward slashes) — e.g.
``js/order/test.js`` -> ``new_/js/order/test.js``. The Dataverse ``webresourcetype`` code is
derived independently from the file extension.

Resources created *before* that convention was adopted keep their original names, which the
convention cannot reproduce — syncing them would create duplicates under the conventional
name while every existing caller still loads the old one. Those few names are declared
explicitly in ``{root}/webresources.aliases.json`` (see :func:`load_aliases`); everything
else, including every newly added file, follows the convention with no bookkeeping.

Flows:
- ``scan_webresources``  — dir -> ``[WebResource]`` (offline; name/type/base64 content).
- ``plan_webresources``  — read-only (would_create / would_update per file).
- ``sync_webresources``  — create/update each (reuses the Phase-2 component handler) +
  optional add to a solution (code 61) + optional **targeted** ``PublishXml``.
- ``reverse_webresources`` — env -> local: decode base64 ``content``, write bytes back to
  ``<root>/{relpath}``, scoped by name prefix (default the publisher prefix).

Non-destructive: ``sync`` only creates/updates (never deletes); delete is an explicit client
method for teardown.
"""

from __future__ import annotations

import base64
import fnmatch
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .components import webresource as wr_component
from .components._common import is_custom
from .components.models import WebResource, WebResourceType
from .deployer import _is_already_exists
from .workspace import WEBRESOURCE_ALIASES_FILENAME as ALIASES_FILENAME

logger = logging.getLogger(__name__)


def _matches_include(relpath: str, include: Optional[list[str]]) -> bool:
    """True if ``relpath`` matches any include glob (fnmatch — ``*`` spans ``/``).

    ``None``/empty ``include`` means "all files" (no filtering).
    """
    if not include:
        return True
    return any(fnmatch.fnmatch(relpath, pat) for pat in include)


# File extension -> Dataverse web resource type (forward scan).
EXT_TO_TYPE: dict[str, WebResourceType] = {
    ".js": WebResourceType.JScript,
    ".css": WebResourceType.Css,
    ".htm": WebResourceType.WebPage,
    ".html": WebResourceType.WebPage,
    ".xml": WebResourceType.Xml,
    ".png": WebResourceType.Png,
    ".jpg": WebResourceType.Jpg,
    ".jpeg": WebResourceType.Jpg,
    ".gif": WebResourceType.Gif,
    ".xap": WebResourceType.Silverlight,
    ".xsl": WebResourceType.Xsl,
    ".xslt": WebResourceType.Xsl,
    ".ico": WebResourceType.Ico,
    ".svg": WebResourceType.Svg,
}

# Advisory: the conventional type-folder segment (first path part) per type.
TYPE_TO_FOLDER: dict[WebResourceType, str] = {
    WebResourceType.JScript: "js",
    WebResourceType.Css: "css",
    WebResourceType.WebPage: "html",
    WebResourceType.Xml: "xml",
    WebResourceType.Png: "png",
    WebResourceType.Jpg: "jpg",
    WebResourceType.Gif: "gif",
    WebResourceType.Silverlight: "xap",
    WebResourceType.Xsl: "xsl",
    WebResourceType.Ico: "ico",
    WebResourceType.Svg: "svg",
}


@dataclass
class WebResourceSyncConfig:
    """Tunables for inter-operation sleeps (metadata propagation)."""

    after_create_delay: float = 0.5
    between_adds_delay: float = 0.3
    sleep: Callable[[float], None] = time.sleep


# ----------------------------------------------------------------- naming


def webresource_name(relpath: str, prefix: str) -> str:
    """Build the Dataverse web resource name: ``{prefix}_/{relpath}``.

    ``relpath`` is normalized to forward slashes (e.g. ``js/order/test.js``).
    """
    return f"{prefix}_/{relpath.replace(chr(92), '/')}"


def load_aliases(root: Path) -> dict[str, str]:
    """Read the optional ``{relpath: dataverseName}`` override table from ``root``.

    Resources created before the ``{prefix}_/{relpath}`` convention was adopted carry names
    the convention cannot reproduce: a file at ``html/orders.html`` whose Dataverse name is
    ``new_Orders.html`` would be derived as ``new_/html/orders.html``. Syncing it would
    therefore *create* a duplicate under the conventional name while every existing caller
    keeps loading the old one. Such names are declared explicitly in
    ``{root}/webresources.aliases.json``:

        {"html/orders.html": "new_Orders.html"}

    Keys are relpaths (forward slashes, same form ``include`` uses); values are the exact
    Dataverse name. Files absent from the table — including every newly added one — keep
    following the convention.

    Raises ``ValueError`` on malformed content rather than ignoring it: silently falling back
    to the convention name is exactly the duplicate-creating failure this table prevents.
    """
    path = Path(root) / ALIASES_FILENAME
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read web resource aliases {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object of {{relpath: name}}")

    aliases: dict[str, str] = {}
    for relpath, name in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: alias for {relpath!r} must be a non-empty string")
        aliases[str(relpath).replace("\\", "/")] = name.strip()
    return aliases


def relpath_from_name(name: str, prefix: str) -> str:
    """Inverse of :func:`webresource_name`: strip the ``{prefix}_/`` marker.

    Falls back to stripping a leading ``{prefix}_`` then any leading slash for names that do
    not follow the ``{prefix}_/`` convention exactly.
    """
    marker = f"{prefix}_/"
    if name.startswith(marker):
        return name[len(marker):]
    short = f"{prefix}_"
    if name.startswith(short):
        return name[len(short):].lstrip("/")
    return name.lstrip("/")


# ----------------------------------------------------------------- scan


def scan_webresources(
    root: Path,
    prefix: str,
    *,
    include: Optional[list[str]] = None,
    aliases: Optional[dict[str, str]] = None,
) -> tuple[list[WebResource], list[str]]:
    """Walk ``root`` and build a :class:`WebResource` per recognized file.

    Returns ``(models, warnings)``. Dotfiles/dot-dirs are skipped; unrecognized extensions
    are recorded as warnings (not fatal). ``content`` is the base64-encoded file bytes.

    ``include`` (optional) restricts the scan to files whose relpath (forward slashes)
    matches any fnmatch glob — e.g. ``["js/order/*.js"]`` syncs only those, not the whole
    tree. ``None``/empty scans everything.

    ``aliases`` overrides the Dataverse name per relpath (see :func:`load_aliases`); when
    omitted it is read from ``{root}/webresources.aliases.json``. Files without an entry use
    the ``{prefix}_/{relpath}`` convention, so newly added files need no bookkeeping.
    """
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"web resource root is not a directory: {root}")
    if aliases is None:
        aliases = load_aliases(root)

    models: list[WebResource] = []
    warnings: list[str] = []
    scanned: set[str] = set()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        # Skip dotfiles / dot-dirs (e.g. .git, .DS_Store).
        if any(part.startswith(".") for part in rel.parts):
            continue
        relpath = rel.as_posix()
        # The override table is configuration, not a web resource.
        if relpath == ALIASES_FILENAME:
            continue
        if not _matches_include(relpath, include):
            continue
        scanned.add(relpath)
        ext = path.suffix.lower()
        wrtype = EXT_TO_TYPE.get(ext)
        if wrtype is None:
            warnings.append(f"skipping unrecognized extension '{ext}': {path}")
            continue
        alias = aliases.get(relpath)
        if alias is not None and not is_custom(alias, prefix):
            warnings.append(
                f"alias '{alias}' for {relpath} lacks the '{prefix}_' publisher prefix; "
                f"deploy will skip it as a standard resource"
            )
        content = base64.b64encode(path.read_bytes()).decode("ascii")
        models.append(
            WebResource(
                name=alias or webresource_name(relpath, prefix),
                display_name=path.name,
                content=content,
                webresource_type=wrtype,
            )
        )

    # A key with no matching file is a typo: that file would silently fall back to the
    # convention name and be created as a duplicate. Only checked on a full scan, since
    # ``include`` legitimately hides files.
    if not include:
        for relpath in sorted(set(aliases) - scanned):
            warnings.append(
                f"alias key '{relpath}' matches no file under {root} — typo? "
                f"it falls back to the convention name"
            )
    return models, warnings


# ----------------------------------------------------------------- plan


def plan_webresources(
    client: Any,
    root: Path,
    *,
    prefix: str = "new",
    include: Optional[list[str]] = None,
    aliases: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Read-only dry run: per-file ``would_create`` / ``would_update`` / ``would_skip_standard``."""
    models, warnings = scan_webresources(root, prefix, include=include, aliases=aliases)
    files: list[dict[str, Any]] = []
    for model in models:
        try:
            entry = wr_component.plan(client, model, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            entry = {"action": "failed", "error": str(e)}
        files.append({"name": model.name, "type": model.webresource_type.name, "plan": entry})
    return {"root": str(root), "files": files, "warnings": warnings}


# ----------------------------------------------------------------- sync


def sync_webresources(
    client: Any,
    root: Path,
    *,
    prefix: str = "new",
    solution: Optional[str] = None,
    publish: bool = True,
    config: WebResourceSyncConfig | None = None,
    include: Optional[list[str]] = None,
    aliases: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Sync a local web-resource directory to Dataverse (non-destructive, idempotent).

    For each scanned file: create or update (PATCH base64 ``content``). When ``solution`` is
    given, add every synced resource to that solution (code 61; idempotent). When ``publish``
    is true, targeted-``PublishXml`` the synced resources so the new content goes live.
    ``include`` restricts the scan to matching relpath globs (see :func:`scan_webresources`);
    ``aliases`` keeps pre-convention Dataverse names (see :func:`load_aliases`).
    """
    cfg = config or WebResourceSyncConfig()
    models, warnings = scan_webresources(root, prefix, include=include, aliases=aliases)
    result: dict[str, Any] = {
        "root": str(root),
        "synced": [],
        "added": [],
        "publish": {},
        "warnings": warnings,
    }

    ids: list[str] = []
    for model in models:
        try:
            deploy_entry = wr_component.deploy(client, model, prefix=prefix)
        except Exception as e:  # noqa: BLE001
            result["synced"].append({"name": model.name, "action": "failed", "error": str(e)})
            continue
        result["synced"].append({"name": model.name, "deploy": deploy_entry})
        if isinstance(deploy_entry, dict) and deploy_entry.get("action") != "skipped_standard":
            oid = deploy_entry.get("id")
            if oid:
                ids.append(str(oid))
        cfg.sleep(cfg.after_create_delay)

    # Optional: add every synced resource to the solution (code 61; idempotent).
    if solution and ids:
        for oid in ids:
            try:
                client.add_solution_component(solution, wr_component.SOLUTION_CODE, oid)
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

    # Optional: targeted publish of just the synced resources.
    if publish and ids:
        try:
            result["publish"] = client.publish_webresources(ids)
        except Exception as e:  # noqa: BLE001
            result["publish"] = {"published": False, "error": str(e)}
            logger.warning(f"PublishXml failed: {e}")

    return result


# ----------------------------------------------------------------- reverse


def reverse_webresources(
    client: Any,
    root: Path,
    *,
    prefix: str = "new",
    name_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Pull web resources from the environment back to the local ``root`` directory.

    Scoped by ``name_prefix`` (default ``{prefix}_/`` — only this publisher's resources).
    Each resource's base64 ``content`` is decoded and written to ``<root>/{relpath}``.
    Aliased names map back to their declared relpath so a round trip is stable; note that
    legacy names outside the ``{prefix}_/`` scope need an explicit ``name_prefix`` to be
    listed at all.
    """
    root = Path(root)
    scope = name_prefix or f"{prefix}_/"
    relpath_by_name = {name: rel for rel, name in load_aliases(root).items()}
    resources = client.list_webresources_by_prefix(scope)
    result: dict[str, Any] = {"root": str(root), "name_prefix": scope, "written": [], "skipped": []}
    for res in resources:
        name = res.get("name") or ""
        content_b64 = res.get("content")
        if not content_b64:
            result["skipped"].append({"name": name, "reason": "empty content"})
            continue
        relpath = relpath_by_name.get(name) or relpath_from_name(name, prefix)
        if not relpath or relpath == name:
            result["skipped"].append({"name": name, "reason": "cannot map to relpath"})
            continue
        out_path = root / relpath
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(base64.b64decode(content_b64))
        except Exception as e:  # noqa: BLE001
            result["skipped"].append({"name": name, "reason": f"write failed: {e}"})
            continue
        result["written"].append({"name": name, "path": str(out_path)})
    return result
