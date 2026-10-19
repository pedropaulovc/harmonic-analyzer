"""Four-view purchased-part reference sheets for stock that is not a catalogued fastener.

This builder reads the part's own Material Specification / Finish /
Manufacturing Notes, as the spring builder does, and lays it out in the
fastener cells, with the part's note printed as its footer note.  The
Isometric scales on its own, so a compact loop's tall pictorial never shrinks
the orthographic views.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from _check import check
from _com import _early_bound
from _drawing_common import read_required_properties
from _drawing_registry import DrawingSpec
from _purchased_fastener_drawing import (
    _PROPERTIES,
    SupplierDimensions,
    _build_reference_sheet,
)


async def build_purchased_part_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str,
    cut_to_suit: bool = False,
    supplier_dimensions: SupplierDimensions | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    supplier_data: Sequence[str] = (),
) -> dict[str, str]:
    """Front/Top/Right plus Isometric of a purchased part, its note in the footer.

    ``item`` is the catalogue designation on the ITEM row; ``cut_to_suit``
    marks stock its note cuts at assembly.
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
        item=item,
        material_property="Material Specification",
        notes=properties["Manufacturing Notes"],
        cut_to_suit=cut_to_suit,
        supplier_dimensions=supplier_dimensions,
        settled_checks=settled_checks,
        supplier_data=supplier_data,
    )
