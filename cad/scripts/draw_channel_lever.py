r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  This recipe supplies only the channel-lever
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The lever is a long thin third-class lever (~186 mm nose-to-tip, 9.5 mm tall,
3.0 mm thick). The sheet runs at 1:2 with a small 1:4 isometric. Separate
front-orientation views carry the true profile and the hole pattern so their
diameter and radius leaders do not compete for the same drawing space. The
3.0 mm thickness is dimensioned in Top; the hub masks it in the end view.

Run with SolidWorks open::

    uv run python -m doit drawing:channel_lever
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Callable

from channel_lever_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check
from _drawing_build import ProjectDrawingFactory, TemplateSpec, run_drawing_build
from _basic_dimensions import require_basic_dimension
from _drawing_project_layout import DatumLeaderPolicy, repair_project_drawing_layout
from _drawing_parallel_dimensions import align_channel_lever_basic_pairs
from _drawing_leader_clearance import validate_dimension_leader_clearance
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
    SOURCE_BASIC_DIMENSIONS,
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

SHEET_SCALE = (1.0, 2.0)  # 1:2; leave room for the measured annotation envelopes.
TEMPLATE_SPEC = TemplateSpec(scale=SHEET_SCALE, decimals=2)

_NOSE_R = BAR_TALL / 2.0  # 4.75
_BBOX_CX = (-_NOSE_R + TIP_END_X) / 2.0  # front-view X centre
_SPRING_HOLE_DIA = 4.039  # #21 drill
_BAR_PIN_DIA = 1.994  # #47 drill

FRONT_CENTER = (0.150, 0.135)
HOLES_CENTER = (0.150, 0.235)
RIGHT_CENTER = (0.295, 0.135)
TOP_CENTER = (0.150, 0.185)
ISO_CENTER = (0.360, 0.210)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Project model millimetres to front-view text seeds at the declared scale."""
    ratio = SHEET_SCALE[0] / SHEET_SCALE[1]
    return (
        FRONT_CENTER[0] + ratio * (mx - _BBOX_CX) / 1000.0,
        FRONT_CENTER[1] + ratio * my / 1000.0,
    )


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Project model (x, z) millimetres to top-view text seeds at sheet scale.

    X aligns with the front view; Z is centred on the plate's mid-thickness.
    """
    ratio = SHEET_SCALE[0] / SHEET_SCALE[1]
    return (
        TOP_CENTER[0] + ratio * (mx - _BBOX_CX) / 1000.0,
        TOP_CENTER[1] + ratio * mz / 1000.0,
    )


def _holes_xy(mx: float, my: float) -> tuple[float, float]:
    """Project model millimetres to hole-view text seeds, never feature picks."""
    x, y = _sheet_xy(mx, my)
    return x + HOLES_CENTER[0] - FRONT_CENTER[0], y + HOLES_CENTER[1] - FRONT_CENTER[1]


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


FRONT_KEEP = (
    "BarLength",
    "TipCentreX",
    "NoseRadius",
    "TipRadius",
)
HOLES_KEEP = ("FulcrumDia",)
RIGHT_KEEP: tuple[str, ...] = ()
TOP_KEEP: tuple[str, ...] = ()


def _model_entities(model: Any) -> dict[str, Any]:
    half_z = LEVER_THICKNESS / 2.0
    return ModelEntities(model).resolve(
        {
            "fulcrum": CircleEdge(
                PIVOT_HOLE_DIA / 2.0, (0, 0, -HUB_LENGTH / 2.0), (0, 0, 1)
            ),
            "bar_pin": CircleEdge(
                _BAR_PIN_DIA / 2.0, (BAR_PIN_X, 0, -half_z), (0, 0, 1)
            ),
            "spring": CircleEdge(
                _SPRING_HOLE_DIA / 2.0, (LEVER_SPRING_X, 0, -half_z), (0, 0, 1)
            ),
            "tip": CircleEdge(TIP_RADIUS, (TIP_ARC_CX, 0, -half_z), (0, 0, 1)),
            "top_front": LineEdge((80, BAR_TALL / 2.0, -half_z), (1, 0, 0)),
            "top_back": LineEdge((80, BAR_TALL / 2.0, half_z), (1, 0, 0)),
            "bottom_front": LineEdge((80, -BAR_TALL / 2.0, -half_z), (1, 0, 0)),
            "broad_a": PlanarFace((0, 0, 1), half_z),
            "broad_opposite": PlanarFace((0, 0, -1), half_z),
        }
    )


async def build(
    adapter: Any,
    *,
    drawing_factory: ProjectDrawingFactory,
    source: Path = SOURCE,
    outputs: DrawingOutputs = OUTPUTS,
    layout: Callable = repair_project_drawing_layout,
) -> dict[str, str]:
    """Build the real recipe; explicit inputs also permit isolated diagnostics."""
    if not source.is_file():
        raise FileNotFoundError(f"source part is missing: {source}")

    check("open channel-lever source", await adapter.open_model(str(source)))
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
    drawing_model, _sheet = drawing_factory(
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

    front = place_view(adapter, str(source), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    holes = place_view(adapter, str(source), "*Front", *HOLES_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(source), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    # Top view (2026-09-02): the integral O12 x 7.06 fulcrum hub hides the whole
    # 3 x 9.5 plate section in the end view, so the plate thickness is read
    # here, along the length clear of the hub. Datum C uses the same top-front
    # model edge as before, now in this separate orthogonal view.
    top = place_view(adapter, str(source), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(source), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)
    set_hidden_lines_visible(adapter, holes)

    front_annotations = retain_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="profile"
    )
    profile_dimensions = set().union(*SOURCE_BASIC_DIMENSIONS.values())
    profile_linear = {}
    for annotation in front_annotations:
        name = dimension_name(adapter, annotation)
        if name in {"BarLength", "TipCentreX"}:
            if name in profile_linear:
                raise RuntimeError(f"duplicate profile linear dimension {name!r}")
            profile_linear[name] = annotation
        if name not in profile_dimensions:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"profile dimension {name!r} has no display annotation")
        require_basic_dimension(display, label=f"profile {name}")
    retain_view_dimensions(adapter, holes, keep=HOLES_KEEP, view_label="holes")
    retain_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    retain_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")

    if not auto_center_marks(adapter, holes, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to hole-pattern view")
    entities = _model_entities(front.ReferencedDocument)
    _add_tip_arc_center_mark(adapter, front, entities["tip"])

    # Fulcrum -> bar-pin (127) and fulcrum -> spring-eye (177.8) centre distances
    # (bore edge to bore edge; SolidWorks dimensions circle edges centre-to-centre).
    bar_pin_c2c = add_entity_dimension(
        adapter,
        holes,
        entities=(entities["fulcrum"], entities["bar_pin"]),
        text_xy=(HOLES_CENTER[0] - 0.020, HOLES_CENTER[1] - 0.027),
        label="fulcrum-to-bar-pin c2c",
    )
    set_basic_dimension(adapter, bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    _force_dimension_black(bar_pin_c2c, label="fulcrum-to-bar-pin c2c")
    spring_c2c = add_entity_dimension(
        adapter,
        holes,
        entities=(entities["fulcrum"], entities["spring"]),
        text_xy=(HOLES_CENTER[0], HOLES_CENTER[1] - 0.037),
        label="fulcrum-to-spring c2c",
    )
    set_basic_dimension(adapter, spring_c2c, label="fulcrum-to-spring c2c")
    _force_dimension_black(spring_c2c, label="fulcrum-to-spring c2c")

    # Section thickness (3.0) in the top view at mid-length (clear of the hub);
    # bar height (9.5) on the front profile at the same station.
    _mid_x = (
        BAR_PIN_X + LEVER_SPRING_X
    ) / 2.0 - 60.0  # ~92: between the hub and the tab
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

    # Hole identities come from the model roles. These projected text seeds
    # precede the single native arrangement pass; they never select features.
    bar_pin_edge = _holes_xy(BAR_PIN_X, _BAR_PIN_DIA / 2.0)
    spring_edge = _holes_xy(LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0, 0.0)
    add_native_hole_callout(
        adapter,
        holes,
        edge=entities["bar_pin"],
        callout_xy=(bar_pin_edge[0] - 0.010, HOLES_CENTER[1] + 0.030),
        label="bar-pin hole",
    )
    add_native_hole_callout(
        adapter,
        holes,
        edge=entities["spring"],
        callout_xy=(spring_edge[0] + 0.005, HOLES_CENTER[1] + 0.030),
        label="spring-eye hole",
    )

    # Let the native dimension bank settle BEFORE authoring symbol/GTol bodies.
    # The retained single-view control's 1 mm spacing produced 6 mm anchor
    # steps whose actual BASIC frames overlapped adjacent extension lines.
    # This is one documented native spacing request, not a placement retry.
    auto_arrange_view_dimensions(
        adapter, (front, holes, right, top, iso), spacing_m=0.003
    )

    # Complete datum reference frame: A is a broad machined face (primary), B
    # is the functional fulcrum-bore axis (secondary), and C is the top narrow
    # face (tertiary clocking).  The two BASIC hole locations reference A|B|C.
    add_datum_feature(
        adapter,
        right,
        entity=entities["broad_a"],
        entity_type="FACE",
        datum="A",
        label="broad machined face",
    )
    add_datum_feature(
        adapter,
        holes,
        entity=entities["fulcrum"],
        datum="B",
        label="fulcrum bore axis",
    )
    # Keep the exact long-edge identity; separate the clocking datum from the
    # profile's R3 leader instead of searching for another coordinate pick.
    add_datum_feature(
        adapter,
        top,
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
        holes,
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
        holes,
        entity=entities["bar_pin"],
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["bar-pin hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="bar-pin hole position",
    )
    add_feature_control_frame(
        adapter,
        holes,
        entity=entities["spring"],
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-eye hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="spring-eye hole position",
    )

    manufacturing = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.075
    )
    caption = add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.175)

    from _drawing_native_layout import AxisLink, LayoutNote
    from _drawing_view_packing import Axis, AxisOrder

    # Exact retained/created handles, one native parallel pass per BASIC pair.
    # The measured lever calibration is limited to these scale-0.5 view classes.
    if profile_linear.keys() != {"BarLength", "TipCentreX"}:
        raise RuntimeError("missing exact profile BASIC pair")
    # AddDimension2 returns a raw dispatch. Bind its method before calling it;
    # late binding can evaluate GetAnnotation then invoke the returned object's
    # nonexistent default member (native receipt datum-policy-gyx30dw5).
    bar_pin_c2c = _early_bound(bar_pin_c2c, "IDisplayDimension")
    spring_c2c = _early_bound(spring_c2c, "IDisplayDimension")
    align_channel_lever_basic_pairs(
        adapter,
        front=front,
        bar_length=profile_linear["BarLength"],
        tip_centre_x=profile_linear["TipCentreX"],
        holes=holes,
        bar_pin_c2c=bar_pin_c2c.GetAnnotation(),
        spring_c2c=spring_c2c.GetAnnotation(),
    )
    layout(
        adapter,
        datum_leader_policy=DatumLeaderPolicy.BENT_DOCUMENT,
        additional_annotation_validation=validate_dimension_leader_clearance,
        views={"front": front, "holes": holes, "right": right, "top": top, "iso": iso},
        alignments=(
            AxisLink(Axis.X, "front", "top"),
            AxisLink(Axis.Y, "front", "right"),
        ),
        orderings=(
            AxisOrder(Axis.Y, "front", "top"),
            AxisOrder(Axis.X, "front", "right"),
        ),
        notes=(
            LayoutNote("manufacturing", manufacturing.GetAnnotation()),
            LayoutNote("iso-caption", caption.GetAnnotation(), "iso"),
        ),
    )
    return await finalize_drawing(
        adapter,
        outputs,
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
    sys.exit(run_drawing_build(build, spec=TEMPLATE_SPEC))
