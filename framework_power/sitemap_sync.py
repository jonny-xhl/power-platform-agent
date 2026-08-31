"""App sitemap entity-menu sync (framework_power Phase 10, ADR-015).

High-level flow used by the ``sitemap`` CLI subcommand: resolve an app's
app-aware sitemap, plan/deploy adding or removing an entity SubArea under an
area/group, with ADR-013-style local backup before every write and a publish
step (targeted ``PublishXml`` first, ``PublishAllXml`` fallback — the targeted
form returned 400 live for app-aware sitemaps).

Live-verified keying (2026-08-26): ``sitemap.sitemapnameunique == appmodule.uniquename``
(e.g. app ``new_CustomerService`` → sitemap ``new_CustomerService``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .components import sitemap as sitemap_component
from .components.sitemap import AppSitemap, SitemapTitle, parse_sitemap, to_sitemapxml

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- app / sitemap resolve


def list_appmodules(client: Any) -> list[dict[str, Any]]:
    rec = client.session.get(
        client.get_api_url("appmodules") + "?$select=name,uniquename,appmoduleid&$top=100",
        timeout=60,
    )
    return rec.json().get("value", [])


def resolve_app(client: Any, app: str) -> dict[str, Any]:
    """``app`` = appmodule uniquename or display name → {appmoduleid, uniquename, name}."""
    for flt in (f"uniquename eq '{app}'", f"name eq '{app}'"):
        rec = client.session.get(
            client.get_api_url("appmodules") + f"?$filter={flt}&$top=1&$select=name,uniquename,appmoduleid",
            timeout=60,
        )
        value = rec.json().get("value") or []
        if value:
            return value[0]
    raise KeyError(f"appmodule not found: {app!r} (uniquename or display name)")


def resolve_app_sitemap(client: Any, app: str) -> dict[str, Any]:
    """App → its app-aware sitemap record (sitemapid, sitemapnameunique, sitemapxml)."""
    app_rec = resolve_app(client, app)
    unique = app_rec["uniquename"]
    rec = client.session.get(
        client.get_api_url("sitemaps") + f"?$filter=sitemapnameunique eq '{unique}'&$top=1"
        + "&$select=sitemapid,sitemapnameunique,sitemapxml",
        timeout=60,
    )
    value = rec.json().get("value") or []
    if value:
        return value[0]
    # fallback: sitemap display name == app display name
    rec = client.session.get(
        client.get_api_url("sitemaps") + f"?$filter=sitemapname eq '{app_rec['name']}'&$top=1"
        + "&$select=sitemapid,sitemapnameunique,sitemapxml",
        timeout=60,
    )
    value = rec.json().get("value") or []
    if value:
        return value[0]
    raise KeyError(f"no app-aware sitemap found for app {unique!r} — app may use the classic main sitemap")


# ----------------------------------------------------------------- entity default title


def _entity_display(client: Any, entity: str) -> str:
    try:
        meta = client.get_entity_metadata(entity)
        dn = meta.get("DisplayName") or {}
        labels = dn.get("LocalizedLabels") or []
        if labels:
            return labels[0].get("Label", entity)
    except Exception:  # noqa: BLE001 - title is best-effort
        pass
    return entity


# ----------------------------------------------------------------- plan / deploy


def plan_entity(
    client: Any, app: str, entity: str, *, area: str, group: str
) -> dict[str, Any]:
    """Read-only: would the entity SubArea be added or skipped."""
    rec = resolve_app_sitemap(client, app)
    model = parse_sitemap(
        rec["sitemapxml"],
        sitemapid=rec["sitemapid"],
        sitemapnameunique=rec.get("sitemapnameunique", ""),
    )
    area_node = sitemap_component.find_area(model, area)
    if area_node is None:
        return {"action": "error", "error": f"area not found: {area!r}",
                "areas": [(a.id, [t.title for t in a.titles]) for a in model.areas]}
    group_node = sitemap_component.find_group(area_node, group)
    if group_node is None:
        return {"action": "error", "error": f"group not found: {group!r} under area {area!r}",
                "groups": [(g.id, [t.title for t in g.titles]) for g in area_node.groups]}
    return {
        "action": "would_skip" if sitemap_component.has_entity(model, entity) else "would_add",
        "app": app,
        "sitemap": rec.get("sitemapnameunique"),
        "sitemapid": rec["sitemapid"],
        "area": {"id": area_node.id, "titles": [t.title for t in area_node.titles]},
        "group": {"id": group_node.id, "titles": [t.title for t in group_node.titles]},
        "entity": entity,
    }


def _backup_sitemap_xml(backup_dir: Path, unique: str, xml: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"sitemap_{unique}.{stamp}.bak.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def _publish_sitemap(client: Any, sitemapnameunique: str) -> dict[str, Any]:
    """Targeted PublishXml first; fall back to PublishAllXml (live: 400 → fallback)."""
    body = {
        "ParameterXml": (
            "<importexportxml><sitemaps>"
            f"<sitemap>{sitemapnameunique}</sitemap>"
            "</sitemaps></importexportxml>"
        )
    }
    try:
        r = client.session.post(client.get_api_url("PublishXml"), json=body, timeout=300)
        if r.status_code < 300:
            return {"publish": "targeted", "status": r.status_code}
    except Exception as exc:  # noqa: BLE001
        logger.debug("targeted PublishXml failed: %s", exc)
    r = client.session.post(client.get_api_url("PublishAllXml"), json={}, timeout=600)
    return {"publish": "all", "status": r.status_code}


def _deploy_op(
    client: Any,
    app: str,
    entity: str,
    *,
    op: str,
    area: Optional[str] = None,
    group: Optional[str] = None,
    title: Optional[str] = None,
    publish: bool = True,
    backup_dir: Optional[Any] = None,
    note: str = "",
) -> dict[str, Any]:
    rec = resolve_app_sitemap(client, app)
    original = rec["sitemapxml"]
    model = parse_sitemap(
        original,
        sitemapid=rec["sitemapid"],
        sitemapnameunique=rec.get("sitemapnameunique", ""),
    )
    if op == "add":
        area = area or ""
        group = group or ""
        zh = title or _entity_display(client, entity)
        titles = [SitemapTitle("1033", zh), SitemapTitle("2052", zh)]
        model, changed = sitemap_component.add_entity_subarea(
            model, entity, area_ref=area, group_ref=group, titles=titles
        )
    else:
        model, removed_count = sitemap_component.remove_entity_subarea(
            model, entity, area_ref=area, group_ref=group
        )
        changed = removed_count > 0
    if not changed:
        return {"action": "skipped_unchanged", "entity": entity, "app": app}

    backup_path = None
    if backup_dir is not None:
        backup_path = _backup_sitemap_xml(
            Path(backup_dir), rec.get("sitemapnameunique", app), original
        )
    new_xml = to_sitemapxml(model)
    r = client.session.patch(
        client.get_api_url(f"sitemaps({rec['sitemapid']})"),
        json={"sitemapxml": new_xml},
        headers={"If-Match": "*"},
        timeout=120,
    )
    if r.status_code >= 300:
        return {"action": "error", "status": r.status_code, "detail": r.text[:500]}

    published: Any = None
    if publish:
        published = _publish_sitemap(client, rec.get("sitemapnameunique", ""))

    # verify
    back = client.session.get(
        client.get_api_url(f"sitemaps({rec['sitemapid']})") + "?$select=sitemapxml", timeout=60
    ).json().get("sitemapxml", "")
    back_model = parse_sitemap(back)
    present = sitemap_component.has_entity(back_model, entity)
    ok = present if op == "add" else not present
    return {
        "action": "added" if op == "add" else "removed",
        "entity": entity,
        "app": app,
        "area": area,
        "group": group,
        "backup": str(backup_path) if backup_path else None,
        "published": published,
        "verified": ok,
        "note": note,
    }


def add_entity(
    client: Any, app: str, entity: str, *, area: str, group: str,
    title: Optional[str] = None, publish: bool = True,
    backup_dir: Optional[Any] = None, note: str = "",
) -> dict[str, Any]:
    """Add the entity to the app menu under area/group (idempotent, backed up, published)."""
    return _deploy_op(client, app, entity, op="add", area=area, group=group,
                      title=title, publish=publish, backup_dir=backup_dir, note=note)


def remove_entity(
    client: Any, app: str, entity: str, *, area: Optional[str] = None,
    group: Optional[str] = None, publish: bool = True,
    backup_dir: Optional[Any] = None, note: str = "",
) -> dict[str, Any]:
    """Remove the entity's menu entry (idempotent, backed up, published)."""
    return _deploy_op(client, app, entity, op="remove", area=area, group=group,
                      publish=publish, backup_dir=backup_dir, note=note)
