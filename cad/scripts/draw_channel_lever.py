r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  This recipe supplies only the channel-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The lever is a long thin third-class lever (~186 mm nose-to-tip, 9.5 mm tall,
3.0 mm thick).  The sheet runs at 1:1 with a small 1:4 isometric; the 3.0 x 9.5
section is dimensioned on a right end view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_channel_lever.py channel-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from channel_lever_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_entity_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    auto_arrange_view_dimensions,
    retain_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_entities import CircleEdge, LineEdge, ModelEntities
from _gtol_spec import PlanarFace
from channel_lever_spec import (
    BAR_PIN_X,
    BAR_TALL,
    HUB_LENGTH,
    LEVER_SPRING_X,
    LEVER_THICKNESS,
    PIVOT_HOLE_DIA,
    TIP_END_X,
    TIP_ARC_CX,
    TIP_RADIUS,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["channel_lever"]
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

SHEET_SCALE = (1.0, 1.0)  # 1:1

_NOSE_R = BAR_TALL / 2.0  # 4.75
_BBOX_CX = (-_NOSE_R + TIP_END_X) / 2.0  # front-view X centre
_SPRING_HOLE_DIA = 4.039  # #21 drill
_BAR_PIN_DIA = 1.994  # #47 drill

FRONT_CENTER = (0.150, 0.155)
RIGHT_CENTER = (0.295, 0.155)
TOP_CENTER = (0.150, 0.205)  # above the profile: plate thickness + datum A live here
ISO_CENTER = (0.360, 0.210)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + (mx - _BBOX_CX) / 1000.0,
        FRONT_CENTER[1] + my / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (x, z) point in the top view (1:1, x aligned
    with the front view, centred on the plate's mid-thickness)."""
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) / 1000.0,
        TOP_CENTER[1] + mz / 1000.0,
    )


def _force_dimension_black(dimension: Any, *, label: str) -> None:
    """Make an added basic dimension print at full black instead of driven gray."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetAnnotation"
    )
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label} has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "Color", "LayerOverride"
    )
    annotation.Color = 0  # COLORREF black; overrides the drawing layer color.
    if int(annotation.Color) != 0:
        raise RuntimeError(f"{label} did not retain black annotation color")
    if not int(annotation.LayerOverride) & 0x1:
        raise RuntimeError(f"{label} did not retain its color override")


def _add_tip_arc_center_mark(adapter: Any, view: Any, tip_arc: Any) -> None:
    """Center-mark the outer R3 arc so its boxed centre coordinate is explicit."""
    draw = adapter.currentModel
    drawing_doc = _sw_type_info.early_bound_or_flag(
        draw, "IDrawingDoc", "ActivateView", "InsertCenterMark3"
    )
    if not drawing_doc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate channel-lever front view")
    draw.ClearSelection2(True)
    selected = view.SelectEntity(tip_arc, False)
    if not selected:
        raise RuntimeError("failed to select channel-lever tip R3 arc")
    center_mark = drawing_doc.InsertCenterMark3(2, False, False)
    draw.ClearSelection2(True)
    if center_mark is None:
        raise RuntimeError("failed to add channel-lever tip R3 center mark")


FRONT_KEEP = ("BarLength", "TipCentreX", "NoseRadius", "TipRadius", "FulcrumDia",)
RIGHT_KEEP: tuple[str, ...] = ()
TOP_KEEP: tuple[str, ...] = ()


def _model_entities(model: Any) -> dict[str, Any]:
    half_z = LEVER_THICKNESS / 2.0
    return ModelEntities(model).resolve({
        "fulcrum": CircleEdge(PIVOT_HOLE_DIA / 2.0, (0, 0, -HUB_LENGTH / 2.0), (0, 0, 1)),
        "bar_pin": CircleEdge(_BAR_PIN_DIA / 2.0, (BAR_PIN_X, 0, -half_z), (0, 0, 1)),
        "spring": CircleEdge(_SPRING_HOLE_DIA / 2.0, (LEVER_SPRING_X, 0, -half_z), (0, 0, 1)),
        "tip": CircleEdge(TIP_RADIUS, (TIP_ARC_CX, 0, -half_z), (0, 0, 1)),
        "top_front": LineEdge((80, BAR_TALL / 2.0, -half_z), (1, 0, 0)),
        "top_back": LineEdge((80, BAR_TALL / 2.0, half_z), (1, 0, 0)),
        "bottom_front": LineEdge((80, -BAR_TALL / 2.0, -half_z), (1, 0, 0)),
        "broad_a": PlanarFace((0, 0, 1), half_z),
        "broad_opposite": PlanarFace((0, 0, -1), half_z),
    })


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open channel-lever source", await adapter.open_model(str(SOURCE)))
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
            0: "Channel Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "channel lever; cast iron; third-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    # Top view (2026-09-02): the integral O12 x 7.06 fulcrum hub hides the whole
    # 3 x 9.5 plate section in the end view, so the plate thickness and the
    # broad-face datum are read here, along the length clear of the hub.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    front_annotations = retain_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    profile_dimensions = {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"}
    for annotation in front_annotations:
        name = dimension_name(adapter, annotation)
        if name not in profile_dimensions:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"profile dimension {name!r} has no display annotation")
        set_basic_dimension(adapter, display, label=f"profile {name}")
    retain_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    retain_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    entities = _model_entities(front.ReferencedDocument)
    _add_tip_arc_center_mark(adapter, front, entities["tip"])

    # Fulcrum -> bar-pin (127) and fulcrum -> spring-eye (177.8) centre distances
    # (bore edge to bore edge; SolidWorks dimensions circle edges centre-to-centre).
    bar_pin_c2c = add_entity_dimension(
        adapter,
        front,
        entities=(entities["fulcrum"], entities["bar_pin"]),
        text_xy=(FRONT_CENTER[0] - 0.020, 0.128),
        label="fulcrum-to-bar-pin c2c",
    )
    set_basic_dimension(adapter, bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    _force_dimension_black(bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    spring_c2c = add_entity_dimension(
        adapter,
        front,
        entities=(entities["fulcrum"], entities["spring"]),
        text_xy=(FRONT_CENTER[0], 0.118),
        label="fulcrum-to-spring c2c",
    )
    set_basic_dimension(adapter, spring_c2c, label="fulcrum-to-spring c2c")
    _force_dimension_black(spring_c2c, label="fulcrum-to-spring c2c")

    # Section thickness (3.0) in the top view at mid-length (clear of the hub);
    # bar height (9.5) on the front profile at the same station.
    _mid_x = (BAR_PIN_X + LEVER_SPRING_X) / 2.0 - 60.0  # ~92: between the hub and the tab
    add_entity_dimension(
        adapter,
        top,
        entities=(entities["top_front"], entities["top_back"]),
        text_xy=(_top_xy(_mid_x, 0.0)[0], TOP_CENTER[1] + 0.020),
        label="lever thickness",
        orientation="vertical",
    )
    bar_height = add_entity_dimension(
        adapter,
        front,
        entities=(entities["bottom_front"], entities["top_front"]),
        text_xy=(_sheet_xy(_mid_x, 0.0)[0] + 0.022, FRONT_CENTER[1]),
        label="bar height",
        orientation="vertical",
    )
    set_basic_dimension(adapter, bar_height, label="bar height from datum C")

    # Hole identities come from the model roles. These projected positions only
    # keep the two native hole callouts in separate text lanes.
    bar_pin_edge = _sheet_xy(BAR_PIN_X, _BAR_PIN_DIA / 2.0)
    spring_edge = _sheet_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    add_native_hole_callout(
        adapter,
        front,
        edge=entities["bar_pin"],
        callout_xy=(bar_pin_edge[0] - 0.010, 0.185),
        label="bar-pin hole",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge=entities["spring"],
        callout_xy=(spring_edge[0] + 0.005, 0.185),
        label="spring-eye hole",
    )

    # Complete datum reference frame: A is a broad machined face (primary), B
    # is the functional fulcrum-bore axis (secondary), and C is the top narrow
    # face (tertiary clocking).  The two BASIC hole locations reference A|B|C.
    add_datum_feature(
        adapter,
        top,
        entity=entities["broad_a"],
        entity_type="FACE",
        datum="A",
        label="broad machined face",
    )
    add_datum_feature(
        adapter,
        front,
        entity=entities["fulcrum"],
        datum="B",
        label="fulcrum bore axis",
    )
    # The integral hub hides this face in the end view. Identify its visible
    # long edge in the front view so the clocking datum has a readable witness.
    add_datum_feature(
        adapter,
        front,
        entity=entities["top_front"],
        datum="C",
        label="top clocking face",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["top_front"],
        characteristic="profile_surface",
        tolerance=GEOMETRIC_TOLERANCES_MM["outer perimeter profile"],
        datums=("A", "B", "C"),
        all_around=True,
        label="outer perimeter profile",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["fulcrum"],
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["fulcrum bore perpendicularity"],
        datums=("A",),
        diameter=True,
        label="fulcrum bore perpendicularity",
    )
    add_feature_control_frame(
        adapter,
        right,
        entity=entities["broad_opposite"],
        entity_type="FACE",
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["opposite broad face parallelism"],
        datums=("A",),
        label="opposite broad face parallelism",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["bar_pin"],
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["bar-pin hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="bar-pin hole position",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["spring"],
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-eye hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="spring-eye hole position",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    auto_arrange_view_dimensions(adapter, (front, right, top, iso))
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Lever Manufacturing Drawing",
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
