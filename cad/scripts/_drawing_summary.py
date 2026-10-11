"""Drawing summary custom-property stamping.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from solidworks_mcp.adapters import sw_type_info as _sw_type_info


def stamp_drawing_summary(
    adapter: Any, drawing_model: Any, fields: dict[int, str]
) -> None:
    """Write and read-verify the drawing document summary metadata."""
    model_doc = _sw_type_info.early_bound_or_flag(drawing_model, "IModelDoc2")
    for field, value in fields.items():
        # SummaryInfo is a property: early binding splits it into a getter
        # (SummaryInfo(field)) and a setter (SetSummaryInfo(field, value)).
        # A 2-arg SummaryInfo(field, value) put only worked under late binding.
        model_doc.SetSummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")
