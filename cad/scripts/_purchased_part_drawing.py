"""Four-view purchased-part reference sheets for stock that is not a catalogued fastener.

This builder reads the part's own Material Specification / Finish /
Manufacturing Notes, as the spring builder does, and lays it out in the
fastener cells, with the part's note printed as its footer note.  The
Isometric scales on its own, so a compact loop's tall pictorial never shrinks
the orthographic views.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_common import read_required_properties
from _drawing_registry import DrawingSpec
from _purchased_fastener_drawing import _PROPERTIES, _build_reference_sheet


class HiddenLineDisplay(Enum):
    """How Front/Top/Right draw the edges hidden behind the part.

    The Isometric always has hidden lines removed.
    """

    # Dashed hidden edges, for a part whose bores and pins they explain.
    VISIBLE = "visible"
    # No hidden edges: on an undimensioned reference view a dashed edge names
    # no feature (rule 9).
    REMOVED = "removed"


async def build_purchased_part_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str | None = None,
    cut_to_suit: bool = False,
    hidden_lines: HiddenLineDisplay = HiddenLineDisplay.REMOVED,
) -> dict[str, str]:
    """Front/Top/Right plus Isometric of a purchased part, its note in the footer.

    ``item`` is the catalogue designation on the ITEM row; without one the row
    prints the part's Stock Name (the chain links, owned by the part-coverage
    stack, until both stacks are on main).  ``cut_to_suit`` marks stock its
    note cuts at assembly.
    """
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")
    check(f"open {spec.artifact_stem} source", await adapter.open_model(str(source)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != source.resolve():
        raise RuntimeError(f"opened purchased part is not {source}")
    names = (*_PROPERTIES, "Material Specification", "Finish", "Manufacturing Notes")
    properties = read_required_properties(model, names, required=names)
    return await _build_reference_sheet(
        adapter,
        spec,
        properties=properties,
        finish=properties["Finish"],
        item=item if item is not None else properties["Stock Name"].upper(),
        material_property="Material Specification",
        notes=properties["Manufacturing Notes"],
        cut_to_suit=cut_to_suit,
        hidden_lines_removed=hidden_lines is HiddenLineDisplay.REMOVED,
    )
