r"""Shared sheet assembly for the uniform PR 358 fastener drawings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from _common import check
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


@dataclass(frozen=True)
class FastenerSheet:
    title: str
    keywords: str
    scale: tuple[float, float]
    side_view: str
    end_view: str
    side_center: tuple[float, float]
    end_center: tuple[float, float]
    iso_center: tuple[float, float]
    end_keep: Mapping[str, tuple[float, float]]
    dimension_callouts: Mapping[str, str]
    side_keep: Mapping[str, tuple[float, float]] | None = None
    side_dimension_callouts: Mapping[str, str] | None = None
    note_xy: tuple[float, float] = (0.020, 0.115)
    end_note_xy: tuple[float, float] = (0.050, 0.220)
    side_centerline_face_xy: tuple[float, float] | None = None
    end_center_mark: Literal["required", "not_applicable"] = "not_applicable"


async def build_fastener_sheet(
    adapter: Any,
    *,
    source: Path,
    property_view: str,
    outputs: DrawingOutputs,
    recipe: FastenerSheet,
) -> dict[str, str]:
    """Build one profile + head-end + isometric fastener sheet."""
    if not source.is_file():
        raise FileNotFoundError(f"source part is missing: {source}")

    check(f"open {property_view} source", await adapter.open_model(str(source)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=property_view, scale=recipe.scale
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: recipe.title,
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: recipe.keywords,
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(
        adapter,
        str(source),
        recipe.side_view,
        *recipe.side_center,
        scale=recipe.scale,
    )
    end = place_view(
        adapter,
        str(source),
        recipe.end_view,
        *recipe.end_center,
        scale=recipe.scale,
    )
    iso = place_view(
        adapter,
        str(source),
        "*Isometric",
        *recipe.iso_center,
        scale=recipe.scale,
    )
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)
    # The shank is fully occluded in the driver/knob-face view.  Showing its
    # hidden circle reads like a counterbore or boss on these tiny sheets and
    # adds no manufacturing information; the thread callout owns that feature.
    set_hidden_lines_removed(adapter, end)

    if recipe.side_centerline_face_xy is not None:
        add_view_centerline(
            adapter,
            side,
            face_xy=recipe.side_centerline_face_xy,
            label=f"{property_view} side-view axis centerline",
        )
    if recipe.end_center_mark == "required" and not auto_center_marks(
        adapter, end, holes=True, size=0.0025
    ):
        raise RuntimeError(f"failed to add ASME center mark to {property_view} end view")

    end_annotations = curate_view_dimensions(
        adapter, end, keep=recipe.end_keep, view_label="head-end"
    )
    set_dimension_callouts(adapter, end_annotations, recipe.dimension_callouts)

    if recipe.side_keep:
        side_annotations = curate_view_dimensions(
            adapter, side, keep=dict(recipe.side_keep), view_label="side"
        )
        set_dimension_callouts(
            adapter,
            side_annotations,
            dict(recipe.side_dimension_callouts or {}),
        )

    add_property_linked_note(adapter, "Manufacturing Notes", *recipe.note_xy)
    add_property_linked_note(adapter, "End View Note", *recipe.end_note_xy)

    return await finalize_drawing(
        adapter,
        outputs,
        pdf_title=recipe.title,
        scale=recipe.scale,
    )
