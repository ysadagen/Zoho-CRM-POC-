"""Pydantic schemas for the RAW-item subtype detail.

``RawItemDetailIn`` is used for **both** create and patch: every field is
optional, so the service applies only what the client sent
(``model_dump(exclude_unset=True)``). ``is_hazardous`` is typed ``bool``
(not ``bool | None``) so an explicit ``null`` is rejected rather than
violating the NOT NULL column; omitting it simply leaves it unset.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.raw_item_detail import MaterialClassification, Pharmacopoeia

__all__ = ["RawItemDetailIn", "RawItemDetailRead"]


class RawItemDetailIn(BaseModel):
    """Create/patch payload for a RAW item's detail block."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    material_classification: MaterialClassification | None = None
    pharmacopoeia: Pharmacopoeia | None = None
    is_hazardous: bool = False


class RawItemDetailRead(BaseModel):
    """RAW detail as returned inside ``ItemRead``."""

    model_config = ConfigDict(from_attributes=True)

    material_classification: MaterialClassification | None
    pharmacopoeia: Pharmacopoeia | None
    is_hazardous: bool
