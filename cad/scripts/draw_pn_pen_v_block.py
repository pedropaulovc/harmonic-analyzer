r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative. This recipe supplies only the pen-v-block
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The repaired annotation lanes are measured again after the final rebuild:
stock-depth ink stays above the title band, and native callout text stays off
neighbouring views, witnesses, datums and dimension lines.

The sheet runs at 4:1 (the block is 32 mm end to end); the isometric carries an
explicit 2:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_v_block.py pen-v-block
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from pn_pen_v_block_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
)
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _surface_finish import surface_finish_by_key
from pn_pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BORE_X,
    CHAMFER,
    SCREW_HOLE_XY,
    GROOVE_Z0,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_v_block"]
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

SHEET_SCALE = (4.0, 1.0)

# Sheet layout (meters).  The front view's model bbox is 32 x 18 mm; at 4:1 the
# view is 128 x 72 mm.  Third angle: the top view (block seen from above,
# carrying the two pen bores) sits ABOVE the front view; the right view (16 x 18
# stock section) sits to its right.
FRONT_CENTER = (0.130, 0.135)
TOP_CENTER = (0.130, 0.225)
RIGHT_CENTER = (0.265, 0.135)
ISO_CENTER = (0.360, 0.225)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - BLOCK_LENGTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The linear chain stacks below the front view, smallest span nearest
# the geometry; the slit band dims sit left of the view; the screw-hole group
# sits right, between the front and right views.
FRONT_KEEP = {
    "Length": (_sheet_x(BLOCK_LENGTH / 2.0), 0.058),
    "Chamfer2dx": (
        _sheet_x(BLOCK_LENGTH - CHAMFER / 2.0),
        _front_y(BLOCK_HEIGHT) + 0.012,
    ),
    # The set-screw hole now sits ON the rod-bore axis (x 10), so its station
    # dim would overprint the top view's Bore0X (10.00) above the front view;
    # it goes in the free band under the front view instead (the old slit row).
    "ScrewHoleCx": (_sheet_x(SCREW_HOLE_XY[0] / 2.0), 0.070),
    # The text belongs between the endpoints, not on its own hole-centre
    # witness. Keep the native line in the corridor left of datum C.
    "ScrewHoleCz": (_sheet_x(BLOCK_LENGTH) + 0.012, _front_y(8.5)),
    "ScrewHoleDiaDim": (_sheet_x(BLOCK_LENGTH) + 0.015, _front_y(16.0)),
}
TOP_KEEP = {
    "Bore0X": (_sheet_x(BORE_X[0] / 2.0), 0.1885),
    "Bore1X": (_sheet_x(BORE_X[1] / 2.0), 0.181),
    "Bore0Dia": (0.030, 0.255),
    # Bottom groove band (a Top-plane sketch, so its Z dims project into the
    # top view). GrooveWidth's extension lines start at the groove edges' RIGHT
    # ends (x=0.202), so text LEFT of the view dragged them across the whole view
    # at y 0.198/0.232, walling both bores in (audit leader-crosses-line x4 for
    # the bore Ra/FCF leaders) and parking its "8.50" under datum B's leader
    # (leader-through-text). RIGHT of the view they shrink to 13 mm stubs; text
    # x 0.2106..0.2194 keeps 3 mm off the view outline and 3.7 mm above the FCF.
    "GrooveWidth": (_sheet_x(BLOCK_LENGTH) + 0.013, TOP_CENTER[1]),
    "GrooveZ0": (_sheet_x(0.0) - 0.032, TOP_CENTER[1] - 0.024),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.047),
    # Move the entire groove-depth display to the right-hand lane. Its model
    # witnesses extend below the stock; raising the aligned front/right group
    # keeps those native strokes, not merely its text, clear of the title band.
    "GrooveDepth": (RIGHT_CENTER[0] + 0.062, RIGHT_CENTER[1] - 0.028),
}

# Right-view half extents at 4:1: the 16 (Z) x 18 (Y) stock section.
RIGHT_HALF_Z = BLOCK_DEPTH / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = BLOCK_HEIGHT / 2.0 * SHEET_SCALE[0] / 1000.0
DIMENSION_CALLOUTS = {
    "Bore0Dia": "2X THRU",
    "ScrewHoleDiaDim": "THRU",
    "Chamfer2dx": "X 45 DEG, 2 PLACES",
}

# Chamfer text leaves its short dimension line through the existing native
# linear OffsetText path; no multiline suffix sits on a chamfer witness.
CHAMFER_TEXT_POSITION = (0.275, 0.196)
ANNOTATION_FIELDS = {
    "Chamfer2dx": (0.250, 0.185, 0.305, 0.203),
    "ScrewHoleCz": (0.205, 0.127, 0.226, 0.141),
    "ScrewHoleDiaDim": (0.207, 0.154, 0.228, 0.173),
    "Depth": (0.249, 0.079, 0.283, 0.096),
    "GrooveDepth": (0.314, 0.098, 0.339, 0.118),
    "datum C": (0.214, 0.108, 0.227, 0.123),
    "block-height overall": (0.300, 0.127, 0.329, 0.143),
    "block top-face parallelism": (0.296, 0.173, 0.332, 0.188),
    "Bore0X": (0.062, 0.184, 0.092, 0.194),
    "Bore1X": (0.095, 0.176, 0.128, 0.185),
    "Bore0Dia": (0.020, 0.243, 0.050, 0.265),
    "datum A": (0.171, 0.080, 0.185, 0.096),
    "pen bore finish 0": (0.150, 0.252, 0.176, 0.266),
    "pen bore finish 1": (0.180, 0.252, 0.206, 0.266),
}


def _assert_release_readability(
    adapter: Any, annotations: dict[str, Any], views: tuple[Any, ...],
    owners: dict[str, int],
) -> None:
    """Refuse actual text/line collisions or title intrusion after settling."""
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        ANNOTATION_FIELDS,
        text_heights={"pen bore finish 0": 0.0025, "pen bore finish 1": 0.0025},
        # BASIC station boxes intentionally enclose their own text. Their
        # witnesses still participate in all foreign row/line checks below.
        check_own_lines=("Chamfer2dx", "ScrewHoleCz", "Depth", "GrooveDepth"),
    )
    chamfer = _early_bound(annotations["Chamfer2dx"], "IAnnotation")
    display = _early_bound(chamfer.GetSpecificAnnotation(), "IDisplayDimension")
    if display.OffsetText is not True:
        raise RuntimeError("native chamfer text did not leave its dimension line")
    template = DRAWING_TEMPLATES[SPEC.layout]
    title = {
        "title-block": (
            template.title_block_left_m, 0.0,
            template.width_m, template.title_block_top_m,
        )
    }
    view_boxes = {
        index: tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
        for index, view in enumerate(views)
    }
    for label in ANNOTATION_FIELDS:
        ink = inks[label]
        # Like the native audit, exempt the owning view's padded outline:
        # a witness or on-view symbol is allowed to reference its own geometry.
        other_views = {
            f"view {index}": box
            for index, box in view_boxes.items()
            if index != owners[label]
        }
        require_clear(label, ink.text, {**title, **other_views})
        for line in ink.lines:
            box = line.box()
            require_clear(label, (box.xmin, box.ymin, box.xmax, box.ymax), title)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-v-block source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen V-Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen v-block; brass; marker groove; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # The front view carries the vertical pen bores as hidden lines; the top
    # view exposes the slit band and the screw hole crossing the depth.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    # Right view: the 16 x 18 stock section.  Depth is the model extrusion dim;
    # the 18 height is added as an explicit overall across the view's extremes.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    offset_dimension_text(
        adapter, front_annotations, {"Chamfer2dx": CHAMFER_TEXT_POSITION}
    )
    # The two bore stations from datum B are the nominal locations the A-B-C
    # position FCF controls, so they must be BASIC -- leaving them under the
    # general/title-block tolerance would double-tolerance the bore positions.
    # curate_view_dimensions yields IAnnotation; set_basic_dimension wants the
    # IDisplayDimension, so resolve it via GetSpecificAnnotation.
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    for station in ("Bore0X", "Bore1X"):
        annotation = top_by_name[station]
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{station} station has no display dimension to box")
        set_basic_dimension(adapter, display, label=f"{station} basic bore station")
    # Block height (18): dimension the right view's flat top/bottom silhouette
    # edges.  At 4:1 the 16 x 18 section spans +/-0.032 (Z) x +/-0.036 (Y)
    # around the view center. The bottom edge is interrupted by the marker
    # groove (GROOVE_Z0..GROOVE_Z0 + GROOVE_WIDTH across the depth), so pick
    # it on the remaining land beside the groove, not at mid-depth.
    _bottom_land_x = (
        RIGHT_CENTER[0] - RIGHT_HALF_Z + GROOVE_Z0 / 2.0 * SHEET_SCALE[0] / 1000.0
    )
    block_height = add_edge_dimension(
        adapter,
        right,
        p0=(_bottom_land_x, RIGHT_CENTER[1] - RIGHT_HALF_Y),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y),
        text_xy=(RIGHT_CENTER[0] + RIGHT_HALF_Z + 0.014, RIGHT_CENTER[1]),
        label="block-height overall",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Native datum/GD&T/surface annotations.  A = the bottom face the block
    # seats on; B = the left end the slit and both bore stations run from;
    # C = the broad front face.
    # Datum A hangs below the unchanged bottom face, between the native lower
    # dimension chain and the raised aligned view group.
    datum_a = add_datum_feature(
        adapter,
        front,
        edge_xy=(_sheet_x(30.0), _front_y(0.0)),
        symbol_xy=(_sheet_x(30.0), _front_y(0.0) - 0.008),
        datum="A",
        label="block bottom face",
    )
    datum_b = add_datum_feature(
        adapter,
        top,
        edge_xy=(_sheet_x(0.0), TOP_CENTER[1]),
        symbol_xy=(_sheet_x(0.0) - 0.018, TOP_CENTER[1]),
        datum="B",
        label="block left end",
    )
    datum_c = add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        symbol_xy=(RIGHT_CENTER[0] - RIGHT_HALF_Z - 0.010, RIGHT_CENTER[1] - 0.020),
        datum="C",
        label="block broad face",
    )
    # 45 deg points on the two Ø8 bore circles (16 mm sheet radius at 4:1): off
    # the right silhouette, which coincides with the chamfer line for bore 1, and
    # off the top point, which sat 1 mm under the groove edge line.
    bore_r45 = 0.0113
    bore_position = add_feature_control_frame(
        adapter,
        top,
        # Bore 1's lower-right point, not bore 0's right point (0.114, 0.215):
        # the leader to bore 0 crossed Bore1X's extension line (x=0.162) and the
        # groove band (audit leader-crosses-line x2). 2X covers both bores; the
        # new leader drops 18 mm from the frame, 7.4 mm off GrooveWidth's stub.
        edge_xy=(_sheet_x(BORE_X[1]) + bore_r45, TOP_CENTER[1] - bore_r45),
        frame_xy=(0.198, 0.196),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["pen bore position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2X",
        label="pen bore position",
    )
    top_parallelism = add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y),
        frame_xy=(0.300, RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.014),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["block top-face parallelism"],
        datums=("A",),
        label="block top-face parallelism",
    )
    # Ra 1.6 on BOTH pen bores (the 2X functional pair) -- add_surface_finish
    # attaches to one edge, so each bore carries its own symbol; a single symbol
    # would leave the other Ø8 bore without the finish requirement.
    # Retain the native 2.5 mm symbols above the raised top view. Each leader
    # stays on its own side of the bore-station witnesses; the bore-size callout
    # has its separate upper-left lane.
    bore_finish_0 = add_surface_finish(
        adapter,
        top,
        edge_xy=(_sheet_x(BORE_X[0]) + bore_r45, TOP_CENTER[1] + bore_r45),
        symbol_xy=(0.155, 0.2575),
        control=surface_finish_by_key(SURFACE_FINISHES, "pen_bore_0"),
        label="pen bore finish (bore 0)",
        char_height=0.0025,
    )
    bore_finish_1 = add_surface_finish(
        adapter,
        top,
        edge_xy=(_sheet_x(BORE_X[1]) + bore_r45, TOP_CENTER[1] + bore_r45),
        symbol_xy=(0.185, 0.2575),
        control=surface_finish_by_key(SURFACE_FINISHES, "pen_bore_1"),
        label="pen bore finish (bore 1)",
        char_height=0.0025,
    )

    manufacturing_note = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.046
    )
    iso_note = add_property_linked_note(
        adapter, "Isometric View Note", 0.330, 0.180
    )
    annotations = {
        dimension_name(adapter, annotation): annotation
        for annotation in (*front_annotations, *top_annotations, *right_annotations)
    }
    annotations.update({
        "block-height overall": _early_bound(block_height, "IDisplayDimension").GetAnnotation(),
        "datum A": _early_bound(datum_a, "IDatumTag").GetAnnotation(),
        "datum B": _early_bound(datum_b, "IDatumTag").GetAnnotation(),
        "datum C": _early_bound(datum_c, "IDatumTag").GetAnnotation(),
        "pen bore position": _early_bound(bore_position, "IGtol").GetAnnotation(),
        "block top-face parallelism": _early_bound(top_parallelism, "IGtol").GetAnnotation(),
        "pen bore finish 0": _early_bound(bore_finish_0, "ISFSymbol").GetAnnotation(),
        "pen bore finish 1": _early_bound(bore_finish_1, "ISFSymbol").GetAnnotation(),
        "Manufacturing Notes": _early_bound(manufacturing_note, "INote").GetAnnotation(),
        "Isometric View Note": _early_bound(iso_note, "INote").GetAnnotation(),
    })
    owners = {
        dimension_name(adapter, annotation): index
        for index, imported in enumerate(
            (front_annotations, top_annotations, right_annotations)
        )
        for annotation in imported
    }
    owners.update({
        "datum C": 2,
        "block-height overall": 2,
        "block top-face parallelism": 2,
        "datum A": 0,
        "pen bore finish 0": 1,
        "pen bore finish 1": 1,
    })
    for label, field in ANNOTATION_FIELDS.items():
        place_annotation_in_field(adapter, annotations[label], label=label, field=field)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Pen V-Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_release_readability(
                adapter, annotations, (front, top, right, iso), owners
            ),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
