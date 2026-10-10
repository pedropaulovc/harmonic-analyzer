r"""Pure-data requirement features a part spec hands to ``export_features``.

A part whose ``<stem>_spec`` declares ``EXPORT_FEATURES: dict[str, ExportFeature]``
and whose stem is listed in ``export_features.SPEC_DRIVEN_PARTS`` gets its
``features.toml`` written from that declaration alone: no per-part branch in the
exporter. Values are the drawing's own numbers (bands as ``(low, high)`` limits,
nominals, positions in the part's model frame). Each field names the spec
declarations that carry it; a ``(module, NAME)`` pair cites another module, which
is how a fixture cites the parent-part fit its locating feature is held to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from _gtol_face import FaceSpec
from _printed_tolerance import printed_deviations

# A citation source: a declaration in the declaring spec, or (module, declaration).
Source = str | tuple[str, str]


def limits(model: float, places: int, band: tuple[float, float] | None = None) -> list[float]:
    """``[low, high]`` for a dimension: its explicit ``(upper, lower)`` native
    tolerance, else the general grade of its printed places."""
    # An explicit native tolerance qualifies the exact source dimension.
    # General grades qualify its printed nominal; use the source's Python
    # formatting convention without inventing a SolidWorks rounding mode.
    if band is not None:
        return [round(model + band[1], 12), round(model + band[0], 12)]
    low, high = printed_deviations(model, places)
    return [round(model + low, 12), round(model + high, 12)]


@dataclass(frozen=True)
class ExportFeature:
    kind: str
    faces: tuple[FaceSpec, ...]
    requirements: tuple[str, ...]
    # field -> (value, sources); tuples become TOML arrays.
    fields: dict[str, tuple[Any, tuple[Source, ...]]]
    precision: dict[str, int | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.faces:
            raise ValueError(f"{self.kind} requirement feature names no STEP face")
        missing = [name for name in self.requirements if name not in self.fields]
        if missing:
            raise ValueError(f"requirements without a field: {missing}")
        unsourced = [name for name, (_value, sources) in self.fields.items() if not sources]
        if unsourced:
            raise ValueError(f"fields without a source declaration: {unsourced}")
