"""
Solution ZIP / customizations.xml helpers (framework_power Phase 7).

Ribbon (and any future component that lives in ``customizations.xml``) has no direct Web API write
path — it is deployed by ``ExportSolution`` → edit ``customizations.xml`` → ``ImportSolution``. This
module is the XML/ZIP layer over the solution round-trip; it un-defers Phase 2's deferred ZIP handling
for the ribbon use case. Uses ONLY stdlib (``zipfile`` + ``re`` + ``xml.etree.ElementTree``).

Pinned live facts (env dev, verified via ExportSolution of new_FpFormSmoke):
- ``customizations.xml`` root is ``<ImportExportXml>``; each ``<Entity><Name>{SCHEMA name}</Name>…
  <RibbonDiffXml>…</RibbonDiffXml></Entity>``. **The Entity ``<Name>`` is the SCHEMA name** (e.g.
  ``new_FpFormSmoke``), NOT the logical name — callers must look up the SchemaName.
- An empty ``<RibbonDiffXml>`` is ``<CustomActions /><Templates><RibbonTemplates Id="Mscrm.Templates"/>
  </Templates><CommandDefinitions /><RuleDefinitions><TabDisplayRules /><DisplayRules /><EnableRules />
  </RuleDefinitions><LocLabels />`` — so authored diffs must include the ``<Templates>`` element.
- Editing strategy: replace ONLY the target entity's ``<RibbonDiffXml>`` region (regex over ``<Entity>``
  blocks) and leave the rest of customizations.xml byte-for-byte intact, so the entity's forms/views are
  unchanged → ImportSolution is a no-op for them. (Parsing the whole doc with ElementTree would drop
  comments/CDATA/formatting and risk data loss elsewhere, so we splice instead.)
"""

from __future__ import annotations

import io
import re
import zipfile

ENTITY_BLOCK_RE = re.compile(r"<Entity\b[^>]*>.*?</Entity>", re.DOTALL)
NAME_RE = re.compile(r"<Name\b[^>]*>([^<]+)</Name>")
SELF_CLOSED_RIBBON_RE = re.compile(r"<RibbonDiffXml\b[^>]*?/>")
OPEN_RIBBON_RE = re.compile(r"<RibbonDiffXml\b[^>]*>.*?</RibbonDiffXml>", re.DOTALL)


# ----------------------------------------------------------------- ZIP read/write


def read_customizations_xml(zip_bytes: bytes) -> str:
    """Read ``customizations.xml`` from a solution ZIP (bytes) as UTF-8 text."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.read("customizations.xml").decode("utf-8")


def write_customizations_xml(zip_bytes: bytes, new_xml: str) -> bytes:
    """Write a modified ``customizations.xml`` back into the solution ZIP, preserving every other entry."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "customizations.xml":
                data = new_xml.encode("utf-8")
            zout.writestr(item, data)
    return out.getvalue()


# ----------------------------------------------------------------- RibbonDiffXml inject/extract


def _replace_first_ribbondiff(block: str, ribbondiff_xml: str) -> str:
    """Replace the first ``<RibbonDiffXml/>`` (self-closing) or ``<RibbonDiffXml>…</RibbonDiffXml>``
    (open/close) in ``block`` with ``ribbondiff_xml``. If neither exists (a shell-only entity export —
    ``DoNotIncludeSubcomponents=True`` — may omit the block entirely), insert it right before ``</Entity>``
    rather than silently dropping the diff. Returns the new block (unchanged only if the block is malformed)."""
    new_block, n = SELF_CLOSED_RIBBON_RE.subn(ribbondiff_xml, block, count=1)
    if n:
        return new_block
    new_block, n = OPEN_RIBBON_RE.subn(ribbondiff_xml, new_block, count=1)
    if n:
        return new_block
    close = block.rfind("</Entity>")
    if close < 0:
        return block
    return block[:close] + ribbondiff_xml + block[close:]


def inject_entity_ribbondiff(xml: str, entity_schema_name: str, ribbondiff_xml: str) -> str:
    """Replace the ``<RibbonDiffXml>`` of the ``<Entity>`` whose ``<Name>`` == ``entity_schema_name``.

    Every other part of customizations.xml is preserved byte-for-byte. Raises ``ValueError`` if the
    entity block is not found.
    """
    found = [False]

    def repl_entity(match: re.Match[str]) -> str:
        block = match.group(0)
        name_match = NAME_RE.search(block)
        if not (name_match and name_match.group(1) == entity_schema_name):
            return block  # not our entity — leave untouched
        found[0] = True
        return _replace_first_ribbondiff(block, ribbondiff_xml)

    result = ENTITY_BLOCK_RE.sub(repl_entity, xml)
    if not found[0]:
        raise ValueError(f"entity '{entity_schema_name}' not found in customizations.xml")
    return result


def inject_application_ribbondiff(xml: str, ribbondiff_xml: str) -> str:
    """Replace the root-level (Application Ribbon) ``<RibbonDiffXml>``.

    The Application Ribbon block is a direct child of ``<ImportExportXml>`` (it appears once the
    "Application Ribbons" solution component is present) — searched for in the region after ``</Entities>``
    so entity-level diffs are not touched. If none exists, the block is inserted right after ``</Entities>``.
    """
    split_idx = xml.find("</Entities>")
    head_end = split_idx + len("</Entities>") if split_idx >= 0 else 0
    head = xml[:head_end]
    tail = xml[head_end:]
    new_tail, n = SELF_CLOSED_RIBBON_RE.subn(ribbondiff_xml, tail, count=1)
    if not n:
        new_tail, n = OPEN_RIBBON_RE.subn(ribbondiff_xml, new_tail, count=1)
    if not n:
        # no existing application-ribbon block -> insert one immediately after </Entities>
        new_tail = ribbondiff_xml + tail
    return head + new_tail


def extract_ribbondiff(xml: str, entity_schema_name: str) -> str:
    """Return the ``<RibbonDiffXml>…</RibbonDiffXml>`` (or self-closing form) of the named entity.

    Returns ``""`` if the entity or its RibbonDiffXml is not present (used for reverse/diff)."""
    target_block = ""
    for m in ENTITY_BLOCK_RE.finditer(xml):
        block = m.group(0)
        name_match = NAME_RE.search(block)
        if name_match and name_match.group(1) == entity_schema_name:
            target_block = block
            break
    if not target_block:
        return ""
    match = SELF_CLOSED_RIBBON_RE.search(target_block) or OPEN_RIBBON_RE.search(target_block)
    return match.group(0) if match else ""


def entity_schema_name_in(xml: str, entity_schema_name: str) -> bool:
    """True if an ``<Entity><Name>{entity_schema_name}</Name>`` block is present in customizations.xml."""
    for m in ENTITY_BLOCK_RE.finditer(xml):
        name_match = NAME_RE.search(m.group(0))
        if name_match and name_match.group(1) == entity_schema_name:
            return True
    return False
