"""App SiteMap component handler (framework_power Phase 10, ADR-015).

Structured model over an app-aware SiteMap's ``sitemapxml`` (the navigation of a
model-driven app such as ``new_CustomerService``). Lossless round-trip: every
node keeps its full ``attrs`` dict and un-modeled children survive as raw XML
strings in ``extras`` — re-serializing a parsed sitemap reproduces the original
semantics (same contract as form/view components).

Live-verified findings baked in (ADR-015, 2026-08-26):
- ``appmodule`` has **no** ``sitemapxml`` column in app-aware orgs; the nav XML
  lives on the ``sitemap`` entity, keyed by ``sitemapnameunique == appmodule.uniquename``.
- Deploy = ``PATCH sitemaps({id}) {sitemapxml}`` + publish. Targeted
  ``PublishXml(<sitemaps><sitemap>{unique}</sitemap></sitemaps>)`` returns 400 →
  fall back to ``PublishAllXml`` (org-wide, same as PublishAllXml note in CLAUDE.md §9).
- New SubAreas clone the attribute style (Client/AvailableOffline/PassParams/Sku)
  of an existing entity SubArea in the same group for visual consistency.
- Sitemap is a solution component (code 62): a sitemap already inside a transport
  solution (e.g. ``new_entity930``) rides along on export — but it carries the
  WHOLE app nav (areas referencing entities outside the solution), so lint warns.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

from ..lint import ERROR, WARNING, Issue

KEY = "sitemap"
SOLUTION_CODE = 62
MODEL_CLS: Any = None  # set below (AppSitemap)
DEPENDS_ON: tuple[str, ...] = ()
CODEGEN_IMPORTS: tuple[str, ...] = (
    "AppSitemap",
    "SiteArea",
    "SiteGroup",
    "SubArea",
    "SitemapTitle",
)

# Attribute style cloned for brand-new SubAreas when the group has no example.
DEFAULT_SUBAREA_ATTRS: dict[str, str] = {
    "Client": "All,Outlook,OutlookLaptopClient,OutlookWorkstationClient,Web",
    "AvailableOffline": "true",
    "PassParams": "false",
    "Sku": "All,OnPremise,Live,SPLA",
}


# ----------------------------------------------------------------- model


@dataclass
class SitemapTitle:
    lcid: str = "1033"
    title: str = ""


@dataclass
class SubArea:
    id: str
    attrs: dict[str, str] = field(default_factory=dict)  # Entity / Client / ...
    titles: list[SitemapTitle] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)  # raw XML of un-modeled children


@dataclass
class SiteGroup:
    id: str
    attrs: dict[str, str] = field(default_factory=dict)
    titles: list[SitemapTitle] = field(default_factory=list)
    subareas: list[SubArea] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)


@dataclass
class SiteArea:
    id: str
    attrs: dict[str, str] = field(default_factory=dict)
    titles: list[SitemapTitle] = field(default_factory=list)
    groups: list[SiteGroup] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)


@dataclass
class AppSitemap:
    sitemapid: str = ""
    sitemapnameunique: str = ""
    root_attrs: dict[str, str] = field(default_factory=dict)
    areas: list[SiteArea] = field(default_factory=list)
    extras: list[str] = field(default_factory=list)  # <SiteMap> children other than <Area>

    def entity_subareas(self) -> list[tuple[SiteArea, SiteGroup, SubArea]]:
        """All SubAreas carrying ``Entity=`` (i.e. table menu entries)."""
        out = []
        for area in self.areas:
            for group in area.groups:
                for sub in group.subareas:
                    if sub.attrs.get("Entity"):
                        out.append((area, group, sub))
        return out


MODEL_CLS = AppSitemap


# ----------------------------------------------------------------- parse / serialize


def _titles_of(el: ET.Element) -> list[SitemapTitle]:
    out: list[SitemapTitle] = []
    titles_el = el.find("Titles")
    if titles_el is not None:
        for t in titles_el.findall("Title"):
            out.append(SitemapTitle(lcid=t.get("LCID", "1033"), title=t.get("Title", "")))
    return out


def _extras_of(el: ET.Element, modeled_tags: set[str]) -> list[str]:
    return [ET.tostring(ch, encoding="unicode") for ch in el if ch.tag not in modeled_tags]


def parse_sitemap(xml: str, *, sitemapid: str = "", sitemapnameunique: str = "") -> AppSitemap:
    """Parse ``sitemapxml`` into :class:`AppSitemap` (attrs + extras preserved)."""
    root = ET.fromstring(xml)
    model = AppSitemap(
        sitemapid=sitemapid,
        sitemapnameunique=sitemapnameunique,
        root_attrs=dict(root.attrib),
        extras=_extras_of(root, {"Area"}),
    )
    for area_el in root.findall("Area"):
        area = SiteArea(
            id=area_el.get("Id", ""),
            attrs=dict(area_el.attrib),
            titles=_titles_of(area_el),
            extras=_extras_of(area_el, {"Group", "Titles"}),
        )
        for group_el in area_el.findall("Group"):
            group = SiteGroup(
                id=group_el.get("Id", ""),
                attrs=dict(group_el.attrib),
                titles=_titles_of(group_el),
                extras=_extras_of(group_el, {"SubArea", "Titles"}),
            )
            for sub_el in group_el.findall("SubArea"):
                group.subareas.append(
                    SubArea(
                        id=sub_el.get("Id", ""),
                        attrs=dict(sub_el.attrib),
                        titles=_titles_of(sub_el),
                        extras=_extras_of(sub_el, {"Titles"}),
                    )
                )
            area.groups.append(group)
        model.areas.append(area)
    return model


def _el(name: str, attrs: dict[str, str]) -> ET.Element:
    el = ET.Element(name)
    for k, v in attrs.items():
        el.set(k, v)
    return el


def _append_extras(parent: ET.Element, extras: list[str]) -> None:
    for raw in extras:
        try:
            parent.append(ET.fromstring(raw))
        except ET.ParseError:  # pragma: no cover - defensive
            continue


def _append_titles(parent: ET.Element, titles: list[SitemapTitle]) -> None:
    if not titles:
        return
    titles_el = ET.SubElement(parent, "Titles")
    for t in titles:
        title_el = ET.SubElement(titles_el, "Title")
        title_el.set("LCID", str(t.lcid))
        title_el.set("Title", t.title)


def to_sitemapxml(model: AppSitemap) -> str:
    """Serialize :class:`AppSitemap` back to ``sitemapxml``."""
    root = _el("SiteMap", model.root_attrs)
    _append_extras(root, model.extras)
    for area in model.areas:
        area_el = _el("Area", area.attrs)
        _append_titles(area_el, area.titles)
        _append_extras(area_el, area.extras)
        for group in area.groups:
            group_el = _el("Group", group.attrs)
            _append_titles(group_el, group.titles)
            _append_extras(group_el, group.extras)
            for sub in group.subareas:
                sub_el = _el("SubArea", sub.attrs)
                _append_titles(sub_el, sub.titles)
                _append_extras(sub_el, sub.extras)
                group_el.append(sub_el)
            area_el.append(group_el)
        root.append(area_el)
    return ET.tostring(root, encoding="unicode")


# ----------------------------------------------------------------- ops


def _matches_ref(titles: list[SitemapTitle], node_id: str, ref: str) -> bool:
    """True if ``ref`` equals the node Id or any title text (case-insensitive)."""
    if ref == node_id:
        return True
    low = ref.strip().lower()
    return any(t.title.strip().lower() == low for t in titles)


def find_area(model: AppSitemap, ref: str) -> Optional[SiteArea]:
    for area in model.areas:
        if _matches_ref(area.titles, area.id, ref):
            return area
    return None


def find_group(area: SiteArea, ref: str) -> Optional[SiteGroup]:
    for group in area.groups:
        if _matches_ref(group.titles, group.id, ref):
            return group
    return None


def has_entity(model: AppSitemap, entity: str, *, area_ref: Optional[str] = None,
               group_ref: Optional[str] = None) -> bool:
    for area, group, sub in model.entity_subareas():
        if sub.attrs.get("Entity", "").lower() != entity.lower():
            continue
        if area_ref and area is not find_area(model, area_ref):
            continue
        if group_ref and group is not find_group(area, group_ref):
            continue
        return True
    return False


def add_entity_subarea(
    model: AppSitemap,
    entity: str,
    *,
    area_ref: str,
    group_ref: str,
    titles: Optional[list[SitemapTitle]] = None,
    subarea_id: Optional[str] = None,
    create_group_if_missing: bool = False,
    group_titles: Optional[list[SitemapTitle]] = None,
) -> tuple[AppSitemap, bool]:
    """Add an ``Entity=`` SubArea under ``area_ref``/``group_ref`` (idempotent).

    Returns ``(model, changed)``; ``changed=False`` when the entity already has a
    SubArea anywhere in the sitemap (idempotent skip, no duplicate menu entries).

    When ``create_group_if_missing=True`` and the group is not found, a new
    ``SiteGroup`` is created under the area with ``group_ref`` as its Id and
    ``group_titles`` (or a default derived from ``group_ref``) as labels.
    """
    if has_entity(model, entity):
        return model, False
    area = find_area(model, area_ref)
    if area is None:
        raise KeyError(f"area not found: {area_ref!r} (by id or title)")
    group = find_group(area, group_ref)
    if group is None:
        if not create_group_if_missing:
            raise KeyError(f"group not found: {group_ref!r} under area {area_ref!r}")
        # Generate a group id (sitemap XSD requires Id attr; use a hex suffix
        # to avoid collisions with existing group ids in the area).
        import uuid as _uuid
        gid = f"group_{_uuid.uuid4().hex[:8]}"
        gtitles = group_titles or [
            SitemapTitle("1033", group_ref),
            SitemapTitle("2052", group_ref),
        ]
        group = SiteGroup(id=gid, attrs={"Id": gid}, titles=gtitles)
        area.groups.append(group)

    style = {**DEFAULT_SUBAREA_ATTRS}
    for _, _, sub in model.entity_subareas():
        style = {k: v for k, v in sub.attrs.items() if k != "Id"}
        break
    style["Entity"] = entity
    sid = subarea_id or f"subarea_{entity.strip('_').replace('_', '')}"
    sub = SubArea(
        id=sid,
        attrs={**style, "Id": sid},
        titles=titles or [SitemapTitle("1033", entity), SitemapTitle("2052", entity)],
    )
    group.subareas.append(sub)
    return model, True


def remove_entity_subarea(
    model: AppSitemap,
    entity: str,
    *,
    area_ref: Optional[str] = None,
    group_ref: Optional[str] = None,
) -> tuple[AppSitemap, int]:
    """Remove every SubArea for ``entity`` (optionally scoped to area/group)."""
    removed = 0
    for area in model.areas:
        if area_ref and area is not find_area(model, area_ref):
            continue
        for group in area.groups:
            if group_ref and group is not find_group(area, group_ref):
                continue
            keep = []
            for sub in group.subareas:
                if sub.attrs.get("Entity", "").lower() == entity.lower():
                    removed += 1
                else:
                    keep.append(sub)
            group.subareas = keep
    return model, removed


# ----------------------------------------------------------------- registry interface


def serialize(model: AppSitemap) -> dict[str, Any]:
    return {"sitemapxml": to_sitemapxml(model)}


def exists(client: Any, model: AppSitemap) -> bool:
    rec = client.session.get(
        client.get_api_url(f"sitemaps({model.sitemapid})") + "?$select=sitemapid", timeout=30
    )
    return rec.status_code == 200


def resolve_id(client: Any, model: AppSitemap) -> Optional[str]:
    return model.sitemapid or None


def deploy(client: Any, model: AppSitemap, *, prefix: str = "new", config: Any = None) -> dict[str, Any]:
    payload = serialize(model)
    client.session.patch(
        client.get_api_url(f"sitemaps({model.sitemapid})"),
        json=payload,
        headers={"If-Match": "*"},
        timeout=120,
    )
    client.publish_all_xml()
    return {"action": "updated", "id": model.sitemapid}


def plan(client: Any, model: AppSitemap, *, prefix: str = "new") -> dict[str, Any]:
    rec = client.session.get(
        client.get_api_url(f"sitemaps({model.sitemapid})") + "?$select=sitemapxml", timeout=60
    ).json()
    live = rec.get("sitemapxml") or ""
    return {
        "action": "would_skip" if live == to_sitemapxml(model) else "would_update",
        "sitemap": model.sitemapnameunique,
    }


def reverse(client: Any, ident: str) -> AppSitemap:
    """``ident`` = sitemapid (GUID) or appmodule uniquename."""
    rec = _fetch_sitemap_record(client, ident)
    return parse_sitemap(
        rec.get("sitemapxml") or "",
        sitemapid=rec.get("sitemapid", ""),
        sitemapnameunique=rec.get("sitemapnameunique", ""),
    )


def _fetch_sitemap_record(client: Any, ident: str) -> dict[str, Any]:
    import re as _re

    if _re.fullmatch(r"[0-9a-fA-F-]{36}", ident or ""):
        rec = client.session.get(
            client.get_api_url(f"sitemaps({ident})")
            + "?$select=sitemapid,sitemapnameunique,sitemapxml",
            timeout=60,
        )
        if rec.status_code == 200:
            return rec.json()
    flt = f"sitemapnameunique eq '{ident}'"
    rec = client.session.get(
        client.get_api_url("sitemaps") + f"?$filter={flt}&$top=1"
        + "&$select=sitemapid,sitemapnameunique,sitemapxml",
        timeout=60,
    )
    value = rec.json().get("value") or []
    if value:
        return value[0]
    raise KeyError(f"sitemap not found for {ident!r} (tried id and sitemapnameunique)")


def lint(model: AppSitemap, *, prefix: str = "new") -> list[Issue]:
    issues: list[Issue] = []
    if not model.sitemapnameunique:
        issues.append(Issue(WARNING, "Sitemap has no sitemapnameunique (app linkage unclear)."))
    seen_entities: dict[str, str] = {}
    for area, group, sub in model.entity_subareas():
        entity = sub.attrs["Entity"]
        if entity in seen_entities:
            issues.append(
                Issue(ERROR, f"Entity {entity!r} appears in multiple SubAreas "
                             f"({seen_entities[entity]} and {area.id}/{group.id}/{sub.id}).")
            )
        else:
            seen_entities[entity] = f"{area.id}/{group.id}/{sub.id}"
        if not sub.titles:
            issues.append(Issue(WARNING, f"SubArea {sub.id} has no Titles (menu shows raw entity name)."))
    if len(model.areas) > 12:
        issues.append(Issue(WARNING, "Sitemap spans >12 areas — it is app-wide; "
                                     "transporting it drags nav for entities outside this solution."))
    return issues


# ----------------------------------------------------------------- codegen


def codegen(model: AppSitemap) -> str:
    return _to_py(model, 0)


def _to_py(value: Any, indent: int) -> str:  # same recursive emitter contract as form/view
    pad = "    " * indent
    inner = "    " * (indent + 1)
    import dataclasses as _dc

    if value is None or isinstance(value, (str, int, float, bool)):
        return repr(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        items = [inner + _to_py(v, indent + 1) for v in value]
        return "[\n" + ",\n".join(items) + ",\n" + pad + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [inner + repr(k) + ": " + _to_py(v, indent + 1) for k, v in value.items()]
        return "{\n" + ",\n".join(items) + ",\n" + pad + "}"
    if _dc.is_dataclass(value):
        parts = [
            inner + f.name + "=" + _to_py(getattr(value, f.name), indent + 1)
            for f in _dc.fields(value)
        ]
        return type(value).__name__ + "(\n" + ",\n".join(parts) + ",\n" + pad + ")"
    raise TypeError(f"cannot emit {type(value)!r}")
