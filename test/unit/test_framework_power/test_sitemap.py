# -*- coding: utf-8 -*-
"""Offline tests for the sitemap component (framework_power Phase 10, ADR-015)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from framework_power.components import sitemap as sc

FIXTURE = (
    '<SiteMap Version="10.0.0.0">'
    "<Area Id='area_pricing' ShowGroup='true'>"
    "<Titles><Title LCID='1033' Title='Pricing' /><Title LCID='2052' Title='核价报价管理' /></Titles>"
    "<Group Id='group_quote' ResourceId='SitemapDesigner.NewGroup'>"
    "<Titles><Title LCID='1033' Title='报价管理' /></Titles>"
    "<SubArea Id='subarea_quote' Entity='new_quote' Client='All' AvailableOffline='true' "
    "PassParams='false' Sku='All'><Titles><Title LCID='1033' Title='报价单' /></Titles></SubArea>"
    "</Group>"
    "</Area>"
    "<Area Id='area_sales'>"
    "<Titles><Title LCID='2052' Title='销售管理' /></Titles>"
    "<Group Id='group_inv'>"
    "<Titles><Title LCID='2052' Title='发票管理' /></Titles>"
    "<SubArea Id='sub_inv' Entity='new_ci_invoice' Client='All' />"
    "</Group>"
    "</Area>"
    "</SiteMap>"
)


@pytest.fixture()
def model():
    return sc.parse_sitemap(FIXTURE, sitemapid="00000000-0000-0000-0000-000000000001",
                            sitemapnameunique="new_CustomerService")


def test_parse_structure(model):
    assert [a.id for a in model.areas] == ["area_pricing", "area_sales"]
    assert model.root_attrs["Version"] == "10.0.0.0"
    group = model.areas[0].groups[0]
    assert group.id == "group_quote"
    assert group.subareas[0].attrs["Entity"] == "new_quote"
    assert group.subareas[0].titles[0].title == "报价单"


def test_roundtrip_semantics(model):
    again = sc.parse_sitemap(sc.to_sitemapxml(model))
    assert [(a.id, [g.id for g in a.groups]) for a in again.areas] == \
        [(a.id, [g.id for g in a.groups]) for a in model.areas]
    assert [(a, g, s.attrs.get("Entity")) for a, g, s in again.entity_subareas()] == \
        [(a, g, s.attrs.get("Entity")) for a, g, s in model.entity_subareas()]
    assert sc.to_sitemapxml(again) == sc.to_sitemapxml(model)  # stable serialization


def test_find_by_title_zh_and_en(model):
    assert sc.find_area(model, "核价报价管理").id == "area_pricing"
    assert sc.find_area(model, "Pricing").id == "area_pricing"
    assert sc.find_area(model, "area_sales").id == "area_sales"
    assert sc.find_group(model.areas[0], "报价管理").id == "group_quote"
    assert sc.find_area(model, "不存在") is None


def test_add_entity_idempotent(model):
    m1, changed1 = sc.add_entity_subarea(
        model, "new_internal_quotation", area_ref="核价报价管理", group_ref="报价管理",
        titles=[sc.SitemapTitle("1033", "内部报价单"), sc.SitemapTitle("2052", "内部报价单")],
    )
    assert changed1 is True
    assert sc.has_entity(m1, "new_internal_quotation")
    # style cloned from existing subarea in the group
    sub = [s for _, _, s in m1.entity_subareas() if s.attrs["Entity"] == "new_internal_quotation"][0]
    assert sub.attrs["Client"] == "All"
    assert sub.attrs["Sku"] == "All"
    # second add anywhere → idempotent skip (no duplicate menu entries)
    m2, changed2 = sc.add_entity_subarea(
        m1, "new_internal_quotation", area_ref="销售管理", group_ref="发票管理")
    assert changed2 is False
    assert len([1 for _, _, s in m2.entity_subareas()
                if s.attrs["Entity"] == "new_internal_quotation"]) == 1


def test_add_missing_area_raises(model):
    with pytest.raises(KeyError):
        sc.add_entity_subarea(model, "new_x", area_ref="nope", group_ref="报价管理")


def test_remove_entity(model):
    m1, changed1 = sc.add_entity_subarea(
        model, "new_internal_quotation", area_ref="Pricing", group_ref="报价管理")
    assert changed1
    m2, removed = sc.remove_entity_subarea(m1, "new_internal_quotation")
    assert removed == 1
    assert not sc.has_entity(m2, "new_internal_quotation")
    m3, removed2 = sc.remove_entity_subarea(m2, "new_internal_quotation")
    assert removed2 == 0  # idempotent


def test_lint_flags_duplicate_entity(model):
    import copy

    dup = copy.deepcopy(model)
    sub = sc.SubArea(id="sub_dup", attrs={"Entity": "new_quote", "Id": "sub_dup"},
                     titles=[sc.SitemapTitle("1033", "dup")])
    dup.areas[1].groups[0].subareas.append(sub)
    issues = sc.lint(dup)
    assert any(i.is_error and "multiple SubAreas" in i.message for i in issues)


def test_codegen_roundtrip(model):
    import dataclasses as dc

    ns = {name: getattr(sc, name) for name in sc.CODEGEN_IMPORTS}
    clone = eval(sc.codegen(model), ns)  # noqa: S307 - trusted generated source
    assert sc.to_sitemapxml(clone) == sc.to_sitemapxml(model)
    assert dc.is_dataclass(clone)
