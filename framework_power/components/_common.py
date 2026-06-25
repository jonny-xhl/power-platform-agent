"""Shared helpers for component modules (framework_power Phase 2)."""

from __future__ import annotations

from typing import Any, Optional

from ..models import Label, LocalizedLabel


def extract_label(label_obj: Optional[dict[str, Any]]) -> Optional[Label]:
    """Build a Label from a Dataverse Label object (LocalizedLabels / UserLocalizedLabel)."""
    if not label_obj:
        return None
    locs = label_obj.get("LocalizedLabels") or []
    pairs = [(loc.get("Label"), loc.get("LanguageCode")) for loc in locs if loc.get("Label")]
    if not pairs:
        ull = label_obj.get("UserLocalizedLabel")
        if ull and ull.get("Label"):
            pairs = [(ull.get("Label"), ull.get("LanguageCode") or 1033)]
    if not pairs:
        return None
    return Label([LocalizedLabel(text, code or 2052) for text, code in pairs])


def is_custom(name: Optional[str], prefix: str) -> bool:
    """True if ``name`` carries the publisher prefix (project-owned / deployable)."""
    return name is not None and name.lower().startswith(f"{prefix}_")
