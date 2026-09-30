"""Four-view purchased-part reference sheets for stock that is not a catalogued fastener.

The spring builder's layout is shaped for long thin coils (a 30 mm-tall Front
cell), which shrinks a compact part to 1:4 on an empty sheet: the keeper
chain's first sheet did exactly that. This builder reads the part's own
Material Specification / Finish / Manufacturing Notes, as the spring builder
does, and lays it out in the fastener cells, with the part's note printed as
its installation line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _common import _early_bound, check
from _drawing_common import read_required_properties
from _drawing_registry import DrawingSpec
from _purchased_fastener_drawing import _PROPERTIES, _build_reference_sheet


async def build_purchased_part_drawing(adapter: Any, spec: DrawingSpec) -> dict[str, str]:
    """Front/Top/Right plus Isometric of a purchased part, its note as the install line."""
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
        material_property="Material Specification",
        installation_notes=properties["Manufacturing Notes"],
    )
