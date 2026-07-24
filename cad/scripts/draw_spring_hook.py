r"""Create the curated machinist drawing for the channel-spring plate hook.

A small formed-wire open J-hook.  The print shows a 5:1 front (profile) view, a
5:1 top view for the wire diameter, and a 5:1 isometric; the form is described
in the notes.  Shared behavior lives in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_spring_hook.py spring-hook
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _early_bound,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from spring_hook_spec import (
    ARM_HEIGHT,
    SHANK_RISE,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["spring_hook"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (5.0, 1.0)  # 5:1
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (5.0)

# Front-view model bbox: X 0..arm-tip, Y 0..arm-height.
_BBOX_CX = 2.0
_BBOX_CY = ARM_HEIGHT / 2.0

FRONT_CENTER = (0.110, 0.150)
TOP_CENTER = (0.210, 0.150)
ISO_CENTER = (0.300, 0.150)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (5:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


@_telemetry.traced("drawing.pick_shank_silhouette")
def _shank_silhouette(adapter: Any, view: Any) -> Any:
    """Return the longest visible straight silhouette of the shank.

    Spanned, and sweeping through the shared ``visible_view_entities``
    chokepoint rather than re-walking GetVisibleComponents/GetVisibleEntities2
    itself. Both matter for the same reason: this was the ONLY untraced COM work
    between ``curate_dimensions`` and ``surface_finish``, so on a run where every
    named span was fast (surface_finish 1.3 s, finalize 8.8 s) 693 s of a 724 s
    build had nothing to attribute it to. The same drawing has also run 65 s,
    71 s and 74 s -- a 10x spread living entirely in unspanned code, which is a
    reliability signal, not just a slow drawing. Counts go on the span's own
    attributes so the cost is readable off the span line.
    """
    name = view_name(adapter, view)
    drawing_doc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing_doc.ActivateView(name):
        raise RuntimeError(f"failed to activate spring-hook drawing view {name!r}")
    raw_silhouettes = visible_view_entities(view, 4, label="spring-hook shank")
    candidates: list[tuple[float, float, Any]] = []
    endpoint_count = 0
    for raw_silhouette in raw_silhouettes:
        silhouette = _early_bound(raw_silhouette, "ISilhouetteEdge")
        start = adapter._attempt(lambda s=silhouette: s.GetStartPoint())
        end = adapter._attempt(lambda s=silhouette: s.GetEndPoint())
        if start is None or end is None:
            continue
        endpoint_count += 1
        start_xyz = adapter._get_attr_or_call(start, "ArrayData")
        end_xyz = adapter._get_attr_or_call(end, "ArrayData")
        if not start_xyz or not end_xyz:
            continue
        length = sum(
            (float(a) - float(b)) ** 2 for a, b in zip(start_xyz, end_xyz)
        ) ** 0.5
        midpoint_x = (float(start_xyz[0]) + float(end_xyz[0])) / 2.0
        candidates.append((length, midpoint_x, silhouette))
    span = _telemetry.trace.get_current_span()
    span.set_attribute("silhouettes", len(raw_silhouettes))
    span.set_attribute("endpoint_pairs", endpoint_count)
    span.set_attribute("candidates", len(candidates))
    if not candidates:
        raise RuntimeError(
            "front view exposes no usable spring-hook silhouette edges: "
            f"silhouettes={len(raw_silhouettes)} "
            f"endpoint pairs={endpoint_count}"
        )
    length, _midpoint_x, silhouette = max(candidates, key=lambda item: item[:2])
    if length < SHANK_RISE / 2000.0:
        raise RuntimeError(
            "could not identify the straight shank silhouette: "
            f"longest visible silhouette is only {length * 1000:g} mm"
        )
    return silhouette


FRONT_KEEP = {
    "Rise": (0.075, FRONT_CENTER[1]),
    "ArmRun": (0.130, 0.205),
}
TOP_KEEP = {
    "RodDia": (0.210, 0.110),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open spring-hook source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Spring Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "spring hook; formed wire; plate hook",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(5, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(5, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(5, 1))

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    # Attach Ra to the longest front-view cylindrical outline: the straight
    # seating shank.  Swept wire exposes this as a drawing-native silhouette,
    # not a model edge, so select the returned entity rather than guessing a pick.
    shank_edge = _shank_silhouette(adapter, front)
    add_surface_finish(
        adapter,
        front,
        edge_entity=shank_edge,
        symbol_xy=(0.140, 0.120),
        roughness_ra="1.6",
        label="shank seating finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.280, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Spring Hook Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
