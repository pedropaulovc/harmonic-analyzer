r"""Create the native multi-sheet frame assembly drawing package.

The released ``fr-frame.SLDASM`` stays authoritative and byte-for-byte unchanged.
This recipe consumes the builder-owned ``FRAME_EXPLODED Simplified``
presentation (the teeth/thread-free twin of ``FRAME_EXPLODED``) for one native
drawing view. It never creates, edits, deletes, or saves assembly
presentation definitions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import sys
from typing import Any, Callable, Sequence

from solidworks_mcp.adapters.com_variant import dispatch_array, double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    view_name,
    visible_component_entities,
)

import _config

from _check import check
from _com import _early_bound
from _drawing_balloon_display import rendered_balloon_circle
from _drawing_balloons import (
    _BALLOON_LANDING_TOLERANCE_M,
    BalloonLanding,
    _balloon_item_number,
    _spread_balloons,
    _view_component_leaves,
    add_component_bom_balloons,
    assert_balloon_landings,
    drawing_viewport_pixel_size,
    position_bom_balloon,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimensions import set_arc_endpoints_to_center, set_reference_dimension
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_edges import _edge_endpoint_key
from _drawing_leaders import distance_to_point, segments_cross
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_ray_pick import (
    _EDGE_HIT,
    _HIT_WIDTH,
    _ORIGIN_MARGIN_M,
    _RAY_OFFSET_M,
    _RAY_OPTIONS,
    _RAY_RADIUS_M,
    _SW_SOLID_BODY,
    _direction_to_part,
    _to_model,
    _to_part,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _drawing_scan import _zoomed_on
from _drawing_selection import _select_view_entity
from _drawing_sections import create_section_view
from _drawing_sheet_region import sheet_drawable_region
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _fr_frame_balloon_anchors import FRAME_BALLOON_ANCHORS
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _simplified_names import simplified_name
import _telemetry
from _assembly_contract import assembly_contract
from _title_block_units import render_number
from fr_frame_attachment_spec import (
    BASE_SCREW_Y,
    CAP_TOP_Y,
    CASTING_FULL_THREAD_DEPTH,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from fr_harmonic_base_spec import BOTTOM_WIDTH, DECK_HALF_X
from fr_nameplate_spec import MOUNT_POS as NAMEPLATE_MOUNT_POS
from fr_vn_frame_cross_screw_spec import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    SHANK_DIA as CROSS_SCREW_SHANK_DIA,
    SHANK_LEN as CROSS_SCREW_SHANK_LEN,
    THREAD as CROSS_SCREW_THREAD,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["fr_frame_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# Step 9 sets MHA-FR-04 before its base seats are spotted through it (#628):
# the plate's lower edge as lettered (plate y = 0) lies at machine x =
# MOUNT_POS[0], parallel to the deck's MHA-FR-04 end at DECK_HALF_X. Section
# B-B looks down on both edges and dimensions the inset between them; step 9
# points to that dimension instead of repeating its value.
NAMEPLATE_END_INSET = DECK_HALF_X - NAMEPLATE_MOUNT_POS[0]
# The fitter sheets print decimal inch (fr-frame.yaml ``drawing_unit``).
UNIT = assembly_contract("fr-frame").drawing_unit
# Places the sheet-made checked dimensions print: the overall reference
# follows the cap stack's .001 grid (41.134); the inset is .16.
HEIGHT_PLACES = 3
INSET_PLACES = 2
# The top cross-bore axis height prints four places, the model equal to the
# print (40.0755; fr-frame deviation). Step 3 sets all four corners' axes to
# this one absolute height from the base underside before step 5
# match-drills the tubes, so the frame's own .72 tap station off its rail top
# cannot carry it. MHA-FR-02's taps stand .72 below its rail top, and that
# rail top (world 1036.2057) lies off the inch grid until the frame plane is
# snapped (PR C), so at three places the height would be a rounding tie.
TOP_AXIS_HEIGHT_PLACES = 4
# The tube match holes' finished drill, as steps 2 and 5 print it (.197).
CROSS_HOLE_TEXT = render_number(TUBE_CROSS_HOLE_DIAMETER / 25.4, UNIT, 3)
# Machine z stations each inset edge's ray is cast at, in turn: on both
# edges, clear of the plate's corner screw heads (z +/-42) and the deck's
# centre line (z 0). The first station whose ray meets an edge chooses it; the
# dimension's pick points project from the first station.
NAMEPLATE_INSET_PICK_Z_M = (0.025, 0.020, 0.030, 0.015, 0.035)
# How far (model mm) the chosen edge's ends may read from the target machine
# x. r6 (run 20261015T051440407Z) dimensioned a line 1.334 mm off its target.
NAMEPLATE_INSET_PICK_TOLERANCE_MM = 0.05
# swSelectType_e.swSelEDGES
_SW_SEL_EDGES = 1
# Machine z of the inset text, which carries the dimension line with it: past
# the base's outer edge (BOTTOM_WIDTH / 2), so the text sits below the plan
# view off the part and the line clears the plate's lettering. 17 mm is ~5.7
# mm on the 1:3 sheet: the 3.5 mm text and the line ~1 mm below it clear the
# base outline, above the title block.
NAMEPLATE_INSET_TEXT_Z_M = (BOTTOM_WIDTH / 2.0 + 17.0) / 1000.0
# Sheet distance of the inset text beyond the deck end, along the dimension
# line: the 1:3 gap is too narrow to hold it between the edges.
NAMEPLATE_INSET_TEXT_OFFSET_M = 0.005

# The controlling setup height names itself on its own native dimension, not
# in a free note the reader must pair with it.
TOP_AXIS_HEIGHT_SUFFIX = " TOP CROSS-BORE AXIS HEIGHT FROM BASE UNDERSIDE"
_DIMENSION_TEXT_SUFFIX = 2  # swDimensionTextParts_e.swDimensionTextSuffix


# With a blank line between steps, the sequence fills sheet 3's note column,
# so the assembly-only checks take their own sheet after it.
SHEET_NAMES = (
    "ASSEMBLED + JOINT SECTIONS",
    "EXPLODED VIEW + BOM",
    "FITTING + ASSEMBLY",
    "ASSEMBLY CHECKS",
)
SHEET_LAYOUTS = {
    SHEET_NAMES[0]: DrawingLayout.LANDSCAPE,
    SHEET_NAMES[1]: DrawingLayout.PORTRAIT,
    SHEET_NAMES[2]: DrawingLayout.LANDSCAPE,
    SHEET_NAMES[3]: DrawingLayout.LANDSCAPE,
}
if SPEC.layout is not SHEET_LAYOUTS[SHEET_NAMES[0]]:
    raise AssertionError("the frame package primary sheet must remain landscape")
SHEET_SCALE = (1.0, 8.0)
WORKING_FRONT_CENTER = (0.053763, 0.163612)
# The two joint sections stand right of the 1:8 view's height dimensions,
# which stand right of the A/B cutting-plane arrows and letters. Those letters
# reach CUTTING_LETTER_REACH_M past the view's flange edge: on the r4 render
# (run 20261015T235155114Z) they ended at 92.9 mm against the flange's
# 82.3 mm, and the (41.134) line at 92.0 mm struck the right-hand "B". Each
# height line keeps HEIGHT_LINE_CLEARANCE_M from the letters, from its
# neighbour and from section A-A's flange edge. Between the overall line and
# A-A's flange edge there is VIEW_GAP_M or more, so the dimensions read as the
# front view's (PR #1468 r6 review: at 2.4 mm the lines pressed against A-A).
# Both sections move right for that gap, B-B's right edge 2.5 mm inside the
# border and the two sections still over 6 mm apart.
BASE_SECTION_CENTER = (0.181714, 0.1823453)
TOP_SECTION_CENTER = (0.340290, 0.1815266)
VIEW_GAP_M = 0.007
CUTTING_LETTER_REACH_M = 0.0106
HEIGHT_LINE_CLEARANCE_M = 0.002
# The height dimensions' lines stand at their texts' x: the top cross-bore
# axis innermost, the overall reference outside it.
TOP_AXIS_HEIGHT_TEXT_XY = (0.0950, 0.254)
OVERALL_HEIGHT_TEXT_XY = (0.0980, 0.244)
JOINT_SECTION_SCALE = (1.0, 3.0)
EXPLODED_ISO_CENTER = (0.140, 0.198)
# 1:8, not 1:7: at 1:7 the balloon ring's apex (outline + 12 mm margin) sat at
# y=328 mm, and a balloon near it (item 10 on af13c8ff8, item 6 on earlier runs)
# printed 1.2-1.4 mm INTO the BOM table, whose bottom rule is at 331.6 mm. The
# table already runs to 5 mm under the top border, so it cannot rise with any air
# left, and the caption and title block sit 7 mm under the lowest balloons, so
# the view cannot drop. 1:8 pulls the ring apex in by ~15 mm at both ends.
EXPLODED_ISO_SCALE = (1.0, 8.0)
ASSEMBLY_ISO_CENTER = (0.345, 0.172)
ASSEMBLY_ISO_SCALE = (1.0, 7.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: SHEET_SCALE,
    SHEET_NAMES[1]: EXPLODED_ISO_SCALE,
    SHEET_NAMES[2]: ASSEMBLY_ISO_SCALE,
    SHEET_NAMES[3]: ASSEMBLY_ISO_SCALE,
}
BOM_ANCHOR = (0.018, 0.414)
# Keep the complete set-screw balloon below the measured BOM, not its nominal
# row heights: shared-SKU descriptions can wrap and lower the bottom rule.
_BOM_BALLOON_CLEARANCE_M = 0.003

# Drawing-selection coordinate only. The manufacturing column pitch remains
# defined by the released source assembly and the part drawings.
_LEFT_COLUMN_X_M = -0.197

BOM_QUANTITIES = {
    "fr-harmonic-base": 1,
    "fr-tube-frame": 4,
    "fr-vn-tube-frame-cap": 4,
    "fr-rocker-arm-support": 1,
    "fr-vn-lag-screw": 4,
    "fr-top-frame": 1,
    "fr-nameplate": 1,
    "sh-vn-brass-fillister-screw": 4,
    "fr-vn-frame-cross-screw": 8,
    "fr-vn-gooseneck-set-screw": 1,
}
if sum(BOM_QUANTITIES.values()) != 29:
    raise AssertionError("the released frame assembly must contain 29 components")
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
BOM_DESCRIPTIONS = {
    "fr-harmonic-base": "TWO-PLATE FRAME BASE",
    "fr-tube-frame": "OPEN-END TUBULAR FRAME COLUMN",
    "fr-vn-tube-frame-cap": "STEEL PUSH-ON CAP FOR 1 IN OD TUBE",
    "fr-rocker-arm-support": "ROCKER-ARM SUPPORT CASTING",
    "fr-vn-lag-screw": "1/4-20 X 3/4 HEX-HEAD SCREW, 18-8 SS",
    "fr-top-frame": "TOP-FRAME CASTING",
    "fr-nameplate": "ENGRAVED BRASS MAKER'S NAMEPLATE",
    "sh-vn-brass-fillister-screw": "BRASS #4-40 X 1/4 FILLISTER-HEAD SLOTTED SCREW",
    "fr-vn-frame-cross-screw": (
        "ZINC-PLATED STEEL #10-32 X 1-3/4 NARROW FILLISTER-HEAD SLOTTED SCREW"
    ),
    "fr-vn-gooseneck-set-screw": "STEEL 1/4-20 X 3/4 SQUARE-HEAD CUP-POINT SET SCREW",
}
BOM_PART_NUMBERS = {
    "fr-harmonic-base": "MHA-FR-01",
    "fr-tube-frame": "MHA-FR-03",
    "fr-vn-tube-frame-cap": "MHA-FR-VN-54",
    "fr-rocker-arm-support": "MHA-FR-05",
    "fr-vn-lag-screw": "MHA-FR-VN-51",
    "fr-top-frame": "MHA-FR-02",
    "fr-nameplate": "MHA-FR-04",
    "sh-vn-brass-fillister-screw": str(_config.parts("sh-vn-brass-fillister-screw")["number"]),
    "fr-vn-frame-cross-screw": "MHA-FR-VN-53",
    "fr-vn-gooseneck-set-screw": "MHA-FR-VN-52",
}
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}

if CROSS_SCREW_THREAD != "#10-32":
    raise AssertionError("MHA-FR-VN-53 must remain the approved #10-32 stock screw")
if TUBE_CROSS_HOLE_DIAMETER <= CROSS_SCREW_SHANK_DIA:
    raise AssertionError("tube match holes must clear the stock screw shank")
if CROSS_SCREW_SHANK_LEN >= CASTING_FULL_THREAD_DEPTH:
    raise AssertionError("stock cross screw must seat before reaching the tap bottom")

EXPLODED_VIEW_NAME = "FRAME_EXPLODED"
# The builder authors the explode in both drawing configurations (Default's is
# FRAME_EXPLODED, Default Simplified's FRAME_EXPLODED Simplified): a view shows
# the explode of the configuration it references.
SOURCE_CONFIGURATION = ASSEMBLY_VIEW_CONFIGURATION
EXPLODED_VIEW_NAMES = {
    SOURCE_CONFIGURATION: EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(EXPLODED_VIEW_NAME),
}

# These instructions carry only requirements that exist at assembly: matched
# fits, the one-setup coaxial casting threads, transfer-drilled tube holes,
# fitted stock caps, and checks against the actual purchased components. Part
# drawings still define the other manufacturing features.
ASSEMBLY_STEPS = "\n".join(
    (
        "MATCH-FIT AND ASSEMBLY SEQUENCE",
        "1. ROUGH-CUT MHA-FR-03 OVERSIZE. DECK UP; FIT EACH MHA-FR-01 SOCKET",
        "   TO ITS ASSIGNED ACTUAL TUBE: CLOSE HAND-SLIP, NO PERCEPTIBLE ROCK,",
        "   FULL SHOULDER SEATING. RETAIN COLUMN/CORNER/ORIENTATION MATCH",
        "   MARKS.",
        "",
        "2. RESEAT EACH MATCHED COLUMN. THROUGH THE EXISTING CASTING BORES,",
        "   PILOT-TRANSFER THE LOWER AXIS THROUGH BOTH TUBE WALLS WITH A DRILL",
        "   BELOW THE #10-32 THREAD MINOR; PROTECT BOTH THREAD SEGMENTS. REMOVE",
        f"   COLUMN; ENLARGE BOTH WALLS TO DIA {CROSS_HOLE_TEXT} "
        "AND DEBURR. THE ACTUAL",
        "   MHA-FR-VN-53 SHANK MUST PASS FREELY WITHOUT THREAD CONTACT.",
        "",
        "3. RESEAT EACH MATCHED COLUMN IN ITS BASE SOCKET. FIT MHA-FR-02 OVER",
        "   THE COLUMNS, HUB OPPOSITE THE MHA-FR-04 END. FIT EACH TOP SOCKET",
        "   TO ITS ASSIGNED ACTUAL MHA-FR-03 TUBE: CLOSE HAND-SLIP WITH NO",
        "   PERCEPTIBLE ROCK. SET EVERY FRONT/REAR CROSS-BORE AXIS TO THE",
        "   CONTROLLING TOP-AXIS HEIGHT ON SHEET 1; COMPARE GAUGE-PIN CENTRES",
        "   FROM THE BASE UNDERSIDE. CLAMP; RETAIN EACH TOP CORNER/COLUMN",
        "   ORIENTATION MATCH MARK.",
        "",
        "4. AT THAT HEIGHT, FINAL MATCH-CUT EACH IDENTIFIED COLUMN TO THE",
        "   ACTUAL BASE/TOP/CAP STACK: MHA-FR-VN-54 FULLY ON ITS INSIDE SEAT,",
        "   SKIRT CLEAR OF THE RECESS FLOOR. DO NOT TRIM THE STOCK CAPS. FINISH",
        "   THE TOP CHAMFER; RESEAT COLUMNS AND RESET THE TOP-AXIS HEIGHT.",
        "",
        "5. THROUGH THE EXISTING MHA-FR-02 CASTING BORES, PILOT-TRANSFER EACH",
        "   TOP AXIS THROUGH BOTH TUBE WALLS AS STEP 2; PROTECT BOTH THREAD",
        "   SEGMENTS. REMOVE MHA-FR-02/COLUMNS; ENLARGE BOTH WALLS TO",
        f"   DIA {CROSS_HOLE_TEXT}, DEBURR, AND VERIFY FREE PASSAGE "
        "OF THE ACTUAL MHA-FR-VN-53",
        "   SHANK.",
        "",
        "6. REASSEMBLE MATCHED FRAME. INSTALL EIGHT MHA-FR-VN-53 FROM THE SIDES",
        "   USED FOR PILOT-DRILLING; TIGHTEN ONLY UNTIL EVERY HEAD SEATS.",
        "",
        "7. VERIFY EACH MHA-FR-02 CAP RECESS CLEARS ITS ACTUAL MHA-FR-VN-54",
        "   SKIRT. AFTER MATCH MARKS ALIGN AND MHA-FR-VN-53 HEADS SEAT, PUSH EACH",
        "   CAP OVER THE CHAMFERED OPEN END UNTIL THE TUBE REACHES THE CAP'S",
        "   INSIDE SEAT.",
        "",
        "8. SEAT MHA-FR-05 ON DECK, WINDOWS FACING THE SHORT ENDS; INSTALL FOUR",
        "   MHA-FR-VN-51 TOP-DOWN AND DRAW DOWN EVENLY UNTIL ALL HEADS SEAT.",
        "",
        # Owner-accepted fit-up, declared as fr-frame RV-01 (#1468).
        "9. SET MHA-FR-04 DECORATED FACE UP, CENTRED FRONT TO REAR, PARALLEL TO",
        "   AND INSET FROM THE NEAR DECK END PER SECTION B-B, SHEET 1; CLAMP.",
        "   SPOT MHA-FR-01 THROUGH ITS FOUR HOLES; DRILL AND TAP EACH PER ITS",
        "   MHA-FR-01 TRANSFER CALLOUT. SEAT ALL FOUR MHA-SH-VN-51 HEADS.",
        "",
        "10. START MHA-FR-VN-52 IN THE GOOSENECK HUB; LEAVE ITS CUP POINT CLEAR.",
    )
)
ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY CHECKS",
        "1. ALL BASE/TOP MATCH MARKS ALIGN; COLUMNS ARE FULLY SEATED.",
        "   EACH FRONT/REAR TOP AXIS MEETS THE HEIGHT FROM THE BASE UNDERSIDE.",
        "",
        "2. ALL EIGHT MHA-FR-VN-53 HEADS SEAT WITHOUT TIPS BOTTOMING. EACH SHANK",
        "   CLEARS BOTH TUBE WALLS AND HAS POSITIVE THREAD ENGAGEMENT IN BOTH",
        "   NEAR AND FAR CASTING THREAD SEGMENTS.",
        "",
        "3. ALL FOUR MHA-FR-VN-54 CAPS REACH THEIR INSIDE SEATS; SKIRTS CLEAR THE",
        "   MHA-FR-02 RECESSES AND TUBE ENDS ARE NOT DISTORTED.",
        "",
        "4. MHA-FR-05 AND MHA-FR-04 LIE FLAT; ALL EIGHT OF THEIR SCREW HEADS",
        "   BEAR.",
        "",
        "5. GOOSENECK BORE IS UNOBSTRUCTED WITH MHA-FR-VN-52 BACKED CLEAR.",
    )
)


def _as_tuple(value: Any, *, label: str) -> tuple[Any, ...]:
    if value is None or isinstance(value, str):
        raise RuntimeError(f"{label}: SolidWorks returned no object array")
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _source_fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if current is None:
        raise RuntimeError("drawing has no current sheet after activation")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")


def _add_note_block(
    adapter: Any, text: str, xy: tuple[float, float], *, label: str
) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    actual = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    expected = text.replace("\r\n", "\n").replace("\r", "\n")
    if actual != expected:
        raise RuntimeError(
            f"{label} text did not persist "
            f"(actual_length={len(actual)}, expected_length={len(expected)})"
        )
    return note


def _configure_view(
    adapter: Any,
    view: Any,
    *,
    exploded: bool,
    role: ViewRole = ViewRole.PLAIN,
    label: str,
) -> str:
    """Point a view at its policy configuration, then explode or collapse it
    there. Both are read back; returns the configuration."""
    configuration = apply_view_configuration(adapter, view, role=role, label=label)
    set_view_exploded_state(adapter, view, exploded, configuration=configuration, label=label)
    return configuration


def _checked_linear_dimension(
    adapter: Any, display: Any, *, expected_mm: float, places: int, label: str
) -> Any:
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    dangling, types = _dimension_attachment(display)
    if dangling:
        # A dangling dimension measures and prints (in the dangling colour)
        # without being attached to anything the sheet draws.
        raise RuntimeError(f"{label} is dangling (attached entity types {types})")
    if int(display.SetPrecision3(places, -1, -1, -1)) < 0:
        raise RuntimeError(f"failed to set {label} precision")
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(f"{label} did not retain {places}-place precision")
    adapter.currentModel.EditRebuild3()
    return display


def _set_dimension_suffix(
    adapter: Any, display: Any, suffix: str, *, label: str
) -> Any:
    """Write ``suffix`` after a dimension's value and read the native text back."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(_DIMENSION_TEXT_SUFFIX, suffix)
    actual = str(display.GetText(_DIMENSION_TEXT_SUFFIX) or "")
    if actual != suffix:
        raise RuntimeError(
            f"{label}: suffix {suffix!r} did not persist, read {actual!r}"
        )
    adapter.currentModel.EditRebuild3()
    return display


def _component_transform(component: Any) -> tuple[float, ...]:
    """One component's native ``Transform2`` ArrayData (16 values).

    Two round trips plus a wrapped object; the edge loops below read it once
    per component instead of twice per visible edge."""
    values = tuple(
        float(value)
        for value in _early_bound(
            _early_bound(component, "IComponent2").Transform2, "IMathTransform"
        ).ArrayData
    )
    if len(values) != 16:
        raise RuntimeError("frame drawing component transform is incomplete")
    return values


def _transform_point(
    values: Sequence[float], point: Sequence[float]
) -> tuple[float, float, float]:
    """Apply :func:`_component_transform` values to one component-local point."""
    if len(point) != 3:
        raise RuntimeError("frame drawing component transform is incomplete")
    x, y, z = (float(value) for value in point)
    scale = values[12]
    return (
        scale * (x * values[0] + y * values[3] + z * values[6]) + values[9],
        scale * (x * values[1] + y * values[4] + z * values[7]) + values[10],
        scale * (x * values[2] + y * values[5] + z * values[8]) + values[11],
    )


def _component_point_in_assembly(
    component: Any, point: Sequence[float]
) -> tuple[float, float, float]:
    """Transform one component-local point through its exact native transform."""
    return _transform_point(_component_transform(component), point)


def _visible_circle_at_height(
    view: Any,
    *,
    component_stem: str,
    height_mm: float,
    target_x_m: float,
    label: str,
    radius_mm: float | None = None,
) -> Any:
    """Resolve a visible circular edge by component identity and native geometry."""
    view = _early_bound(view, "IView")
    full_components: dict[str, Any] = {}
    for raw_drawing_component in _as_tuple(
        view.GetVisibleDrawingComponents(),
        label=f"{label} visible drawing components",
    ):
        drawing_component = _early_bound(raw_drawing_component, "IDrawingComponent")
        component = _early_bound(drawing_component.Component, "IComponent2")
        name = str(component.Name2 or "").rsplit("/", 1)[-1]
        if name in full_components:
            raise RuntimeError(f"{label}: duplicate visible component {name!r}")
        full_components[name] = component

    candidates: list[tuple[tuple[float, ...], Any]] = []
    for visible_component in _as_tuple(
        view.GetVisibleComponents(), label=f"{label} visible components"
    ):
        visible_component = _early_bound(visible_component, "IComponent2")
        if _component_stem(visible_component) != component_stem:
            continue
        name = str(visible_component.Name2 or "").rsplit("/", 1)[-1]
        full_component = full_components.get(name)
        if full_component is None:
            raise RuntimeError(f"{label}: component {name!r} has no full peer")
        for raw_edge in tuple(visible_component_entities(view, visible_component, 1)):
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve is None or not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if len(parameters) < 7:
                raise RuntimeError(f"{label}: circular edge has incomplete parameters")
            center = _component_point_in_assembly(full_component, parameters[:3])
            actual_height_mm = center[1] * 1000.0
            actual_radius_mm = parameters[6] * 1000.0
            if abs(actual_height_mm - height_mm) > 1e-5:
                continue
            if radius_mm is not None and abs(actual_radius_mm - radius_mm) > 1e-5:
                continue
            geometry_key = (
                abs(center[0] - target_x_m),
                center[0],
                center[2],
                actual_radius_mm,
                *parameters[:3],
            )
            candidates.append((geometry_key, edge))
    if not candidates:
        radius_detail = "" if radius_mm is None else f", radius {radius_mm:g} mm"
        raise RuntimeError(
            f"{label}: no {component_stem!r} circle at {height_mm:g} mm{radius_detail}"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _add_entity_height_dimension(
    adapter: Any,
    view: Any,
    entity0: Any,
    entity1: Any,
    *,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    if not drawing.ActivateView(str(view.GetName2() or "")):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, entity0), (True, entity1)):
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.View = view
        if not _early_bound(raw_entity, "IEntity").Select4(append, selection_data):
            raise RuntimeError(f"failed to select exact entity for {label}")
    display = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if display is None:
        raise RuntimeError(f"failed to create {label}")
    return display


def _add_frame_height_dimensions(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Add native overall and top-cross-screw setup heights."""
    base_bottom = _visible_circle_at_height(
        front,
        component_stem="fr-harmonic-base",
        height_mm=0.0,
        target_x_m=-_LEFT_COLUMN_X_M,
        label="frame base underside",
    )
    cap_top = _visible_circle_at_height(
        front,
        component_stem="fr-vn-tube-frame-cap",
        height_mm=CAP_TOP_Y,
        target_x_m=-_LEFT_COLUMN_X_M,
        label="finished cap top",
    )
    overall = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        cap_top,
        text_xy=OVERALL_HEIGHT_TEXT_XY,
        label="finished frame overall height",
    )
    overall = _checked_linear_dimension(
        adapter,
        overall,
        expected_mm=CAP_TOP_Y,
        places=HEIGHT_PLACES,
        label="finished frame overall height",
    )
    overall = set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="finished frame overall height reference",
    )

    screw_head = _visible_circle_at_height(
        front,
        component_stem="fr-vn-frame-cross-screw",
        height_mm=TOP_SCREW_Y,
        target_x_m=-_LEFT_COLUMN_X_M,
        radius_mm=CROSS_SCREW_HEAD_DIA / 2.0,
        label="installed top cross-screw head",
    )
    screw_axis = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        screw_head,
        text_xy=TOP_AXIS_HEIGHT_TEXT_XY,
        label="installed top cross-screw axis height",
    )
    screw_axis = set_arc_endpoints_to_center(
        adapter, screw_axis, label="installed top cross-screw axis height"
    )
    screw_axis = _checked_linear_dimension(
        adapter,
        screw_axis,
        expected_mm=TOP_SCREW_Y,
        places=TOP_AXIS_HEIGHT_PLACES,
        label="installed top cross-screw axis height",
    )
    screw_axis = _set_dimension_suffix(
        adapter,
        screw_axis,
        TOP_AXIS_HEIGHT_SUFFIX,
        label="installed top cross-screw axis height",
    )

    # An outside dimension can put its text to either side of the requested
    # anchor. Inspect the native shoulder/witness ink, not that anchor alone.
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    for label, display in (("overall reference", overall), ("top axis", screw_axis)):
        display = _early_bound(display, "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        text_count = int(data.GetTextCount())
        points = []
        for index in range(int(data.GetLineCount())):
            line = tuple(float(value) for value in data.GetLineAtIndex2(index))
            if len(line) < 10:
                raise RuntimeError(f"{label}: incomplete native dimension line")
            points.extend(((line[4], line[5]), (line[7], line[8])))
        if not points or text_count < 1:
            raise RuntimeError(f"{label}: missing native dimension display data")
        bounds = (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )
        _telemetry.event(
            "drawing.frame_height_ink",
            label=label,
            annotation_position=tuple(annotation.GetPosition()),
            line_bounds=bounds,
            text=tuple(str(data.GetTextAtIndex(index)) for index in range(text_count)),
            text_positions=tuple(
                float(value)
                for index in range(text_count)
                for value in data.GetTextPositionAtIndex(index)
            ),
            text_heights=tuple(
                float(data.GetTextHeightAtIndex(index)) for index in range(text_count)
            ),
        )
        if (
            bounds[0] < region.xmin - 1e-6
            or bounds[1] < region.ymin - 1e-6
            or bounds[2] > region.xmax + 1e-6
            or bounds[3] > region.ymax + 1e-6
        ):
            raise RuntimeError(
                f"{label}: native dimension ink {bounds!r} crosses {region!r}"
            )
    return overall, screw_axis


def _create_joint_sections(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Cut plan sections through the lower and upper cross-screw axes."""
    bound_front = _early_bound(front, "IView")
    outline = tuple(float(value) for value in bound_front.GetOutline())
    if len(outline) != 4 or outline[0] >= outline[2]:
        raise RuntimeError(f"working front view has invalid outline {outline!r}")
    line_x = (outline[0] - 0.002, outline[2] + 0.002)
    sections = []
    for axis_y_mm, center, section_label, label in (
        (BASE_SCREW_Y, BASE_SECTION_CENTER, "A", "base socket joint"),
        (TOP_SCREW_Y, TOP_SECTION_CENTER, "B", "top socket joint"),
    ):
        cut_y = model_point_in_view(
            adapter,
            front,
            (0.0, axis_y_mm / 1000.0, 0.0),
            label=f"{label} cutting-plane station",
        )[1]
        section = create_section_view(
            adapter,
            front,
            line_start=(line_x[0], cut_y),
            line_end=(line_x[1], cut_y),
            view_xy=center,
            section_label=section_label,
            scale=JOINT_SECTION_SCALE,
            label=label,
        )
        # A section shows its cut in solid lines only; the working front
        # view keeps its hidden lines.
        set_hidden_lines_removed(adapter, section)
        apply_view_configuration(adapter, section, label=f"joint section {cut_y:.3f}")
        sections.append(section)
    return sections[0], sections[1]


@_telemetry.traced("drawing.inset_edge_rays")
def _inset_edge_rays(
    adapter: Any,
    view: Any,
    *,
    leaves: Sequence[Any],
    stem: str,
    target_mm: float,
    stations_m: Sequence[float],
) -> tuple[str, Any, list[tuple[Any, float] | None]]:
    """Find the highest model edge at each machine-x/z station by ray.

    One ``IModelDocExtension::RayIntersections`` call per solid body of the
    stem's one shown drawing component avoids walking the engraved plate's
    thousands of edges (783 s on run 20261022T162906839Z; the ray path took
    about 21 s). The returned edges still need mapping into drawing-view
    context. Their ``IEntity.GetComponent`` returned null in the bounded
    native diagnostic, before AND after ``GetSafeEntity``; return the explicit
    drawing component separately rather than trying to recover it from an edge.
    ``IView.GetCorrespondingEntity`` supplies the actual section-owned edge.

    Each ray points down machine -y through ``(target x, z)`` from above the
    body. Return the instance name, its component and, per station, the
    highest edge hit as ``(component edge, machine y)`` or ``None``. Section views need this path:
    ``GetVisibleComponents`` and ``GetVisibleEntities2`` returned no entities
    in runs 20261015T024651004Z and 20261015T042140629Z.
    """
    model = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    shown = [
        leaf for leaf in leaves
        if leaf.visible and leaf.component is not None and stem in leaf.identities
    ]
    if len(shown) != 1:
        raise RuntimeError(
            f"nameplate inset: {len(shown)} shown {stem} instances, expected one"
        )
    component = _early_bound(shown[0].component, "IComponent2")
    name = shown[0].path or str(component.Name2)
    result = adapter._attempt(
        lambda: component.GetBodies3(_SW_SOLID_BODY), default=None
    )
    bodies = (
        tuple(result[0] or ()) if isinstance(result, tuple) and len(result) == 2 else ()
    )
    if not bodies:
        raise RuntimeError(f"nameplate inset: {name!r} resolves no solid body")
    values = _component_transform(component)
    down = _direction_to_part(values, (0.0, -1.0, 0.0))
    extension = _early_bound(model.Extension, "IModelDocExtension")
    found: list[tuple[float, Any] | None] = [None] * len(stations_m)
    for body in bodies:
        bound = _early_bound(body, "IBody2")
        # Start above the body: its extreme point along machine +y, plus margin.
        extreme = tuple(bound.GetExtremePoint(*_direction_to_part(values, (0.0, 1.0, 0.0))) or ())
        if len(extreme) != 4 or not extreme[0]:
            raise RuntimeError(f"nameplate inset: {name!r} body has no extreme point")
        top_m = _to_model(values, extreme[1:4])[1] + _ORIGIN_MARGIN_M
        starts: list[float] = []
        vectors: list[float] = []
        for z_m in stations_m:
            starts.extend(_to_part(values, (target_mm / 1000.0, top_m, z_m)))
            vectors.extend(down)
        extension.RayIntersections(
            dispatch_array([body]),
            double_array(starts),
            double_array(vectors),
            _RAY_OPTIONS,
            _RAY_RADIUS_M,
            _RAY_OFFSET_M,
            True,
        )
        raw = tuple(model.GetRayIntersectionsPoints() or ())
        topology = tuple(model.GetRayIntersectionsTopology() or ())
        if len(raw) % _HIT_WIDTH or len(topology) != len(raw) // _HIT_WIDTH:
            raise RuntimeError(
                f"nameplate inset: ray readback on {name} is malformed: "
                f"{len(raw)} doubles, {len(topology)} entities"
            )
        for k in range(0, len(raw), _HIT_WIDTH):
            ray = int(raw[k + 1])
            if not int(raw[k + 2]) & _EDGE_HIT:
                continue
            hit_y = _to_model(values, raw[k + 3 : k + 6])[1]
            if found[ray] is not None and found[ray][0] >= hit_y:
                continue
            edge = adapter._attempt(
                lambda e=topology[k // _HIT_WIDTH]: component.GetCorrespondingEntity(e),
                default=None,
            )
            if edge is not None:
                found[ray] = (hit_y, edge)
    return name, component, [None if row is None else (row[1], row[0]) for row in found]


def _read_selected_inset_edge(
    adapter: Any,
) -> tuple[Any, str, tuple[float, float] | None]:
    """Read the current selection back: edge, owner and its ends' machine x (mm).

    Edge and x are ``None`` when the selection is not a readable component
    edge; the owner string then says why.
    """
    draw = adapter.currentModel
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    index = int(manager.GetSelectedObjectCount2(-1))
    kind = int(manager.GetSelectedObjectType3(index, -1))
    edge = manager.GetSelectedObject6(index, -1)
    draw.ClearSelection2(True)
    if kind != _SW_SEL_EDGES or edge is None:
        return None, f"selection type {kind}", None
    component = adapter._attempt(
        lambda: _early_bound(edge, "IEntity").GetComponent(), default=None
    )
    if component is None:
        return None, "edge without a component", None
    owner = str(_early_bound(component, "IComponent2").Name2)
    key = _edge_endpoint_key(adapter, edge)
    if key is None:
        return None, f"{owner} edge without curve params", None
    transform = _component_transform(component)
    start, end = (_transform_point(transform, key[i : i + 3]) for i in (0, 3))
    return edge, owner, (start[0] * 1000.0, end[0] * 1000.0)


@dataclass(frozen=True)
class _InsetEdgeReference:
    """Keep safe model topology and explicit occurrence ownership across rebuilds."""

    label: str
    model_edge: Any
    view_edge: Any
    instance: str
    component: Any


@dataclass(frozen=True)
class _InsetDimensionProof:
    view: Any
    display: Any
    references: tuple[_InsetEdgeReference, _InsetEdgeReference]


@_telemetry.traced("drawing.inset_correspondence", label_param="label")
def _inset_section_edge(
    adapter: Any, view: Any, model_edge: Any, *, component: Any, label: str
) -> Any:
    """Map model topology into the section, and prove its source identity.

    ``IComponent2.GetCorrespondingEntity`` only provides component context.
    The separate ``IView.GetCorrespondingEntity`` mapping is what gives the
    drawing a view-owned reference, not a currently selectable model edge.
    Reverse both objects into the same source part before comparing them.
    """
    model_entity = _early_bound(model_edge, "IEntity")
    if not bool(model_entity.IsSafe):
        _telemetry.event(
            "drawing.inset_correspondence", label=label, model_safe=False,
            expected_view=view_name(adapter, view),
        )
        raise RuntimeError(f"nameplate inset {label}: retained model edge is not safe across rebuilds")
    section_edge = _early_bound(view, "IView").GetCorrespondingEntity(model_edge)
    source = (
        None if component is None
        else _early_bound(component, "IComponent2").GetModelDoc2()
    )
    canonical = returned = None
    if section_edge is not None and source is not None:
        extension = _early_bound(
            _early_bound(source, "IModelDoc2").Extension, "IModelDocExtension"
        )
        canonical = extension.GetCorrespondingEntity2(model_edge)
        returned = extension.GetCorrespondingEntity2(section_edge)
    same = (
        -1 if canonical is None or returned is None
        else int(adapter.swApp.IsSame(canonical, returned))
    )
    _telemetry.event(
        "drawing.inset_correspondence",
        label=label,
        mapped=section_edge is not None,
        source_available=source is not None,
        source_identity=same,
        canonical_available=canonical is not None,
        returned_available=returned is not None,
        model_safe=True,
        expected_view=view_name(adapter, view),
        expected_instance="" if component is None else str(component.Name2),
    )
    if section_edge is None or same != 1:  # swObjectSame; unknown also refuses.
        raise RuntimeError(
            f"nameplate inset {label}: no source-verified section edge "
            f"(mapped={section_edge is not None}, source identity={same})"
        )
    return section_edge


@_telemetry.traced("drawing.inset_edge", label_param="label")
def _pick_inset_edge(
    adapter: Any,
    view: Any,
    *,
    leaves: Sequence[Any],
    label: str,
    stem: str,
    target_mm: float,
    stations_m: Sequence[float],
) -> _InsetEdgeReference:
    """Find the edge geometrically, map it into the section, and prove the pick.

    The first ray-hit station chooses the model edge. Its corresponding
    section entity must select as that exact edge in that exact view, and
    both read-back endpoints must have the intended machine x. No screen
    coordinate or engraved-body edge enumeration participates.
    """
    name, component, rays = _inset_edge_rays(
        adapter, view, leaves=leaves, stem=stem, target_mm=target_mm, stations_m=stations_m
    )
    chosen = next(
        ((z_m, row) for z_m, row in zip(stations_m, rays) if row is not None), None
    )
    if chosen is None:
        raise RuntimeError(
            f"nameplate inset {label}: no ray down machine -y through x "
            f"{target_mm:g} mm at z {tuple(z * 1000.0 for z in stations_m)} mm "
            f"meets an edge of {name}"
        )
    z_m, (edge, y_m) = chosen
    # Retain safe topology across rebuilds and the explicit component alongside
    # it: neither the original model edge nor its safe handle supplies GetComponent.
    edge = _early_bound(edge, "IEntity").GetSafeEntity()
    if edge is None:
        raise RuntimeError(f"nameplate inset {label}: failed to retain a safe model edge")
    section_edge = _inset_section_edge(
        adapter, view, edge, component=component, label=label,
    )
    _select_view_entity(adapter, view, "EDGE", None, label=label, entity=section_edge)
    manager = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
    picked_view = manager.GetSelectedObjectsDrawingView2(1, -1)
    selected, owner, xs = _read_selected_inset_edge(adapter)
    same_entity = selected is not None and int(adapter.swApp.IsSame(selected, section_edge)) == 1
    same_view = picked_view is not None and int(adapter.swApp.IsSame(picked_view, view)) == 1
    same_owner = owner.rsplit("/", 1)[-1] == name.rsplit("/", 1)[-1]
    hit = same_entity and same_view and same_owner and xs is not None and all(
        abs(x - target_mm) <= NAMEPLATE_INSET_PICK_TOLERANCE_MM for x in xs
    )
    reading = (
        f"{name} y {y_m * 1000.0:.3f} z {z_m * 1000.0:g} mm: {owner}"
        + ("" if xs is None else f" at machine x {xs[0]:.3f}/{xs[1]:.3f} mm")
    )
    _telemetry.info(
        f"nameplate inset edge {label} {reading} "
        f"(target x {target_mm:g} mm) -> {'hit' if hit else 'miss'}"
    )
    _telemetry.event(
        "drawing.inset_edge",
        label=label,
        instance=name,
        owner=owner,
        expected_view=view_name(adapter, view),
        selected_view="" if picked_view is None else view_name(adapter, picked_view),
        machine_y_mm=y_m * 1000.0,
        station_z_mm=z_m * 1000.0,
        rays=len(rays),
        machine_x_mm=xs,
        hit=hit,
        same_entity=same_entity,
        same_view=same_view,
        same_owner=same_owner,
    )
    if not hit:
        raise RuntimeError(
            f"nameplate inset {label}: selected edge reads {reading}, not the section's "
            f"named edge at machine x {target_mm:g} mm "
            f"(entity={same_entity}, view={same_view}, owner={same_owner})"
        )
    return _InsetEdgeReference(label, edge, selected, name, component)


@_telemetry.traced("drawing.nameplate_inset")
def _add_nameplate_inset_dimension(adapter: Any, section: Any) -> _InsetDimensionProof:
    """Dimension step 9's inset with source-verified, section-owned edges.

    The model rays identify the two real edges without screen hit-testing.
    Their section correspondences, native dimension attachments and measured
    value are proved after the creation rebuild and again after finalization.
    """
    targets = (
        ("nameplate lower edge", "fr-nameplate", NAMEPLATE_MOUNT_POS[0]),
        ("deck end", "fr-harmonic-base", DECK_HALF_X),
    )
    y_mm = NAMEPLATE_MOUNT_POS[1]
    plate_line, deck_line = model_points_in_view(
        adapter,
        section,
        [
            (x_mm / 1000.0, y_mm / 1000.0, NAMEPLATE_INSET_TEXT_Z_M)
            for _, _, x_mm in targets
        ],
        label="nameplate inset text line",
        names=[f"{name} text line" for name, _, _ in targets],
    )
    gap = math.hypot(deck_line[0] - plate_line[0], deck_line[1] - plate_line[1])
    if gap <= 0.0:
        raise RuntimeError("nameplate inset edges coincide on the sheet")
    leaves = _view_component_leaves(adapter, section, label="nameplate inset")
    references = tuple(
        _pick_inset_edge(
            adapter,
            section,
            leaves=leaves,
            label=name,
            stem=stem,
            target_mm=target_mm,
            stations_m=NAMEPLATE_INSET_PICK_Z_M,
        )
        for name, stem, target_mm in targets
    )
    text_xy = tuple(
        deck + (deck - plate) / gap * NAMEPLATE_INSET_TEXT_OFFSET_M
        for plate, deck in zip(plate_line, deck_line)
    )
    display = _add_inset_dimension(
        adapter, section, tuple(ref.view_edge for ref in references),
        text_xy=(text_xy[0], text_xy[1]), label="nameplate end inset",
    )
    display = _checked_linear_dimension(
        adapter,
        display,
        expected_mm=NAMEPLATE_END_INSET,
        places=INSET_PLACES,
        label="nameplate end inset",
    )
    proof = _InsetDimensionProof(section, display, references)
    _assert_inset_dimension_settled(adapter, proof, phase="creation rebuild")
    return proof


def _dimension_attachment(display: Any) -> tuple[bool, tuple[int, ...]]:
    """``(dangling, attached entity types)`` of a display dimension."""
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    return (
        bool(annotation.IsDangling()),
        tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ())),
    )


@_telemetry.traced("drawing.add_inset_dimension", label_param="label")
def _add_inset_dimension(
    adapter: Any, view: Any, edges: Sequence[Any], *, text_xy: tuple[float, float], label: str
) -> Any:
    """Create one native dimension from the two already mapped section edges.

    Selection-API retries cannot repair a missing drawing correspondence.
    Only section-owned entities enter this path; the caller checks the actual
    attachments after rebuilding, not the transient initial ``IsDangling``.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not _early_bound(draw, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, edge in enumerate(edges):
        selection_data = manager.CreateSelectData()
        selection_data.View = view
        if not _early_bound(edge, "IEntity").Select4(index > 0, selection_data):
            raise RuntimeError(f"{label}: failed to select section edge {index}")
        count = int(manager.GetSelectedObjectCount2(-1))
        selected = manager.GetSelectedObject6(index + 1, -1)
        picked_view = manager.GetSelectedObjectsDrawingView2(index + 1, -1)
        if (
            count != index + 1 or selected is None or picked_view is None
            or int(adapter.swApp.IsSame(selected, edge)) != 1
            or int(adapter.swApp.IsSame(picked_view, view)) != 1
        ):
            raise RuntimeError(f"{label}: section edge {index} selection changed identity or view")
    display = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: added no native dimension")
    return display


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_persisted_explode(source_model: Any) -> None:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError("frame source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"frame source {owner} exploded views {names!r} != {(wanted,)!r}"
            )
    components = tuple(assembly.GetComponents(True) or ())
    if len(components) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError("frame source must contain exactly 29 components")
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"frame source must open collapsed: {component.Name2!r} is displaced"
            )


def _normalized_bom_identity(text: str) -> str:
    normalized = text.strip().casefold()
    return BOM_NORMALIZED_ALIASES.get(normalized, normalized)


def _validate_frame_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"frame BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    contents = tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(columns)
        )
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(f"frame BOM has no unique {label} column: {header!r}")
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    # Use the portrait sheet width rather than wrapping descriptions into a
    # narrow table over the exploded view. Native minimum heights retain text.
    for column, width in (
        (item_column, 0.022),
        (part_column, 0.038),
        (description_column, 0.162),
        (quantity_column, 0.022),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(f"frame BOM column width did not persist: {column}")
    for row in range(rows):
        table.SetRowHeight(row, 0.006, 0)

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        stem = _normalized_bom_identity(row[part_column])
        if stem in actual:
            raise RuntimeError(f"frame BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"frame BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    expected_items = {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}
    actual_items = {values[1] for values in actual.values()}
    if actual_items != expected_items:
        raise RuntimeError(
            f"frame BOM item numbers {sorted(actual_items)!r} != "
            f"{sorted(expected_items)!r}"
        )

    for stem, (row_index, _item, description, quantity) in actual.items():
        expected_part_number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != expected_part_number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"frame BOM part-number cell for {stem!r} is not editable"
                )
            table.SetText2(row_index, part_column, False, expected_part_number)
            applied = str(
                table.DisplayedText2(row_index, part_column, False) or ""
            ).strip()
            if applied != expected_part_number:
                raise RuntimeError(
                    f"frame BOM part number for {stem!r} did not persist"
                )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"frame BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"frame BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )
    adapter.currentModel.EditRebuild3()
    for stem, (row_index, _item, _description, _quantity) in actual.items():
        applied = str(table.DisplayedText(row_index, part_column) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"frame BOM part number for {stem!r} reverted to {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _copy_selected_sheet(draw: Any, sheet_name: str, *, label: str) -> None:
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        sheet_name,
        "SHEET",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"{label}: failed to select sheet {sheet_name!r}")
    draw.EditCopy()


def _paste_blank_sheet(
    adapter: Any, drawing: Any, *, new_name: str, label: str
) -> None:
    drawing = _early_bound(drawing, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    before = tuple(ddoc.GetSheetNames() or ())
    returned = bool(ddoc.PasteSheet(2, 2))  # move to end; preserve view names
    after = tuple(ddoc.GetSheetNames() or ())
    added = tuple(name for name in after if name not in before)
    if len(after) != len(before) + 1 or len(added) != 1:
        raise RuntimeError(
            f"{label}: sheet paste failed (returned={returned!r}, "
            f"before={before!r}, after={after!r})"
        )
    if not returned:
        _telemetry.warn(f"{label}: PasteSheet returned false but created {added[0]!r}")
    if not ddoc.ActivateSheet(added[0]):
        raise RuntimeError(f"{label}: failed to activate pasted sheet {added[0]!r}")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    sheet.SetName(new_name)
    if str(sheet.GetName() or "") != new_name:
        raise RuntimeError(f"{label}: failed to rename pasted sheet {new_name!r}")


def _activate_frame_package(adapter: Any, target: Any) -> Any:
    target_title = str(target.GetTitle() or "")
    if not target_title:
        raise RuntimeError("frame package drawing has no title")
    activation = adapter.swApp.ActivateDoc3(target_title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate frame package drawing")
    activated, errors = activation
    if int(errors) != 0:
        raise RuntimeError(
            f"failed to reactivate frame package drawing (errors={errors})"
        )
    if activated is None:
        activated = adapter.swApp.ActiveDoc
    if activated is None:
        raise RuntimeError("frame package drawing did not become active")
    activated = _early_bound(activated, "IModelDoc2")
    if int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the frame package drawing")
    adapter.currentModel = activated
    return activated


def _append_template_sheet(
    adapter: Any,
    target: Any,
    *,
    layout: DrawingLayout,
    new_name: str,
    label: str,
) -> None:
    donor_title = ""
    try:
        donor, donor_sheet = new_project_drawing(
            adapter, layout=layout, scale=SHEET_SCALES[new_name], unit=UNIT
        )
        donor = _early_bound(donor, "IModelDoc2")
        donor_sheet = _early_bound(donor_sheet, "ISheet")
        donor_title = str(donor.GetTitle() or "")
        donor_name = str(donor_sheet.GetName() or "")
        if not donor_title or not donor_name:
            raise RuntimeError(f"{label}: donor drawing is incomplete")
        _copy_selected_sheet(donor, donor_name, label=label)
        _activate_frame_package(adapter, target)
        _paste_blank_sheet(
            adapter,
            target,
            new_name=new_name,
            label=label,
        )
    finally:
        primary_error = sys.exception()
        cleanup_error: Exception | None = None
        if donor_title:
            try:
                adapter.swApp.CloseDoc(donor_title)
                _activate_frame_package(adapter, target)
            except Exception as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            if primary_error is None:
                raise cleanup_error
            _telemetry.warn(f"{label}: donor cleanup failed: {cleanup_error}")


def _create_mixed_package_sheets(adapter: Any) -> None:
    """Create landscape/portrait/landscape/landscape sheets from the project templates."""
    target, initial = new_project_drawing(
        adapter,
        layout=SHEET_LAYOUTS[SHEET_NAMES[0]],
        scale=SHEET_SCALES[SHEET_NAMES[0]],
        unit=UNIT,
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name the frame package primary sheet")

    for sheet_name in SHEET_NAMES[1:]:
        _append_template_sheet(
            adapter,
            target,
            layout=SHEET_LAYOUTS[sheet_name],
            new_name=sheet_name,
            label=f"{sheet_name} frame sheet",
        )

    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"frame package sheet order mismatch: {actual!r}")


def _frame_visible_components(view: Any) -> dict[str, list[tuple[Any, Any]]]:
    full = {}
    for raw in view.GetVisibleDrawingComponents() or ():
        component = _early_bound(
            _early_bound(raw, "IDrawingComponent").Component, "IComponent2"
        )
        full[str(component.Name2).rsplit("/", 1)[-1]] = component
    families: dict[str, list[tuple[Any, Any]]] = {}
    for raw in view.GetVisibleComponents() or ():
        component = _early_bound(raw, "IComponent2")
        name = str(component.Name2).rsplit("/", 1)[-1]
        families.setdefault(_component_stem(component), []).append(
            (component, full[name])
        )
    return families


def _upper_frame_balloon_edges(
    adapter: Any, view: Any, families: dict[str, list[tuple[Any, Any]]]
) -> dict[str, Any]:
    """Choose exposed support-body and screw-head edges, not feet or shanks."""
    winners = {}
    for stem in ("fr-rocker-arm-support", "fr-vn-lag-screw"):
        for component, full in families[stem]:
            name = str(component.Name2)
            transform = None  # read at the first usable edge, as before batching
            for edge in visible_component_entities(view, component, 1):
                key = _edge_endpoint_key(adapter, edge)
                if key is None:
                    continue
                if transform is None:
                    transform = _component_transform(full)
                p0 = _transform_point(transform, key[:3])
                p1 = _transform_point(transform, key[3:6])
                score = (min(p0[1], p1[1]), -abs(p0[1] - p1[1]), name, *key)
                if stem not in winners or score > winners[stem][0]:
                    winners[stem] = (score, edge)
    if set(winners) != {"fr-rocker-arm-support", "fr-vn-lag-screw"}:
        raise RuntimeError("missing visible upper support-body or screw-head edge")
    return {stem: row[1] for stem, row in winners.items()}


def _bind_left_column_balloon(
    adapter: Any, view: Any, note: Any, item: str,
    components: Sequence[tuple[Any, Any]],
) -> tuple[Any, Any, Any]:
    """Bind to an actual outer tube rim on the open left side of the view."""
    candidates = []
    for component, _full in components:
        rims = []
        for raw_edge in visible_component_entities(view, component, 1):
            curve = _early_bound(
                _early_bound(raw_edge, "IEdge").GetCurve(), "ICurve"
            )
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(abs(circle[4]) - 1.0) < 1e-9:
                rims.append((circle[6], circle[1], raw_edge))
        if not rims:
            continue
        radius = max(row[0] for row in rims)
        rim = max(
            (row for row in rims if abs(row[0] - radius) < 1e-7),
            key=lambda row: row[1],
        )[2]
        note, _annotation, point = _bind_frame_balloon(adapter, view, note, rim, item)
        candidates.append((point[:2], rim))
    if not candidates:
        raise RuntimeError("no visible outer column rim for the BOM balloon")
    rim = min(candidates, key=lambda row: row[0])[1]
    note, annotation, _point = _bind_frame_balloon(adapter, view, note, rim, item)
    return note, annotation, rim


def _exposed_top_casting_edge(
    adapter: Any, view: Any, components: Sequence[tuple[Any, Any]]
) -> Any:
    # Every linear edge's two ends go through ONE projection call: the view
    # does not move while its edges are ranked (~210 edges, 420 points).
    lines = []
    points = []
    names = []
    for component, full in components:
        # Read at the first usable edge: a component with none neither pays
        # for the transform nor can abort the pick with an unreadable one.
        transform = None
        for edge_index, edge in enumerate(visible_component_entities(view, component, 1)):
            curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            key = _edge_endpoint_key(adapter, edge)
            if key is None:
                continue
            if transform is None:
                transform = _component_transform(full)
                component_name = str(component.Name2)
            lines.append((key, edge))
            points.append(_transform_point(transform, key[:3]))
            points.append(_transform_point(transform, key[3:6]))
            edge_name = f"{component_name} edge {edge_index}"
            names += [f"{edge_name} start", f"{edge_name} end"]
    projected = model_points_in_view(
        adapter, view, points, label="top casting edge ends", names=names
    )
    candidates = []
    for index, (key, edge) in enumerate(lines):
        p0, p1 = projected[2 * index], projected[2 * index + 1]
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if length >= 0.003:
            candidates.append(((min(p0[0], p1[0]), length, *key), edge))
    if not candidates:
        raise RuntimeError("top casting has no exposed right-side linear edge")
    return max(candidates, key=lambda row: row[0])[1]


def _frame_balloon_binding_readback(
    adapter: Any, annotation: Any, entity: Any, item: str,
) -> dict[str, Any]:
    """Keep entity, BOM, and leader failures distinct in native diagnostics."""
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    points = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
    same = [int(adapter.swApp.IsSame(actual, entity)) for actual in attached]
    actual_item = str(note.GetBomBalloonText(True) or "").strip()
    dangling = bool(annotation.IsDangling())
    failures = []
    if len(attached) != 1:
        failures.append("entity_count")
    if same != [1]:
        failures.append("entity_identity")
    if actual_item != item:
        failures.append("bom_item")
    if dangling:
        failures.append("dangling")
    if len(points) < 6:
        failures.append("leader_points")
    position = tuple(annotation.GetPosition() or ())
    circle = rendered_balloon_circle(note, label=f"frame balloon {item}")
    return {
        "expected_item": item,
        "actual_item": actual_item,
        "expected_entity_type": type(entity).__name__,
        "actual_entity_types": [type(actual).__name__ for actual in attached],
        "entity_is_same": same,
        "dangling": dangling,
        "actual_leader_points": points,
        "annotation_position": position,
        "rendered_circle": circle,
        "viewport_pixel_bounds_m": tuple(
            max(1e-6, value) for value in drawing_viewport_pixel_size(adapter)
        ),
        "anchor_to_circle_xy": (
            (circle[0] - position[0], circle[1] - position[1])
            if len(position) >= 2 else None
        ),
        "failed_checks": failures,
    }


def _bind_frame_balloon(
    adapter: Any, view: Any, note: Any, entity: Any, item: str
) -> tuple[Any, Any, tuple[float, float, float]]:
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetAttachedEntities(dispatch_array([entity])):
        raise RuntimeError(f"frame balloon {item} rejected its native target")
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    state = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    if state["failed_checks"]:
        raise RuntimeError(f"frame balloon reattachment failed: {state!r}")
    points = state["actual_leader_points"]
    return note, annotation, points[-3:]


# Half the sheet square the short-leader placement runs zoomed onto: a
# balloon ring (9.5 mm) and its leader's start. Fit to the sheet, the ring
# GetDisplayData reports is the one the seat's window rendered, at 0.68 mm a
# pixel on an 820-high window and 0.94 on a 640-high one. Placing from it,
# item 5's anchor sat at (154.4, 283.6) mm on swmaker000004/6 and up to
# (156.2, 283.8) on swmaker000005/7/8 for the same target, and only builds on
# the small windows printed a short leader through its own ring (399c05283,
# 8bd440ca7). Zoomed, a pixel is under 0.06 mm on every seat, and the zoomed
# read is the ring the PDF prints: on swmaker000008 (run 20260928T141421973Z)
# items 2, 5 and 9 read (93.61, 249.03), (159.11, 282.43), (91.71, 270.84)
# zoomed and printed at (93.52, 249.06), (158.93, 282.50), (91.50, 270.74),
# 0.10, 0.19 and 0.23 mm apart. On swmaker000005 (run 20260928T142458776Z)
# the same SetPosition for item 2, (89.32, 250.85), read at fit after the
# rebuild put the ring at (92.85, 249.98), 1.14 mm off that print, so a fit
# read is no check of where the ring prints.
#
# Zoomed, GetDisplayData snaps the ring's centre to the window's pixel rows.
# position_bom_balloon takes the anchor-to-ring offset from the read before
# SetPosition; read inside the window, that offset differs from the placed
# ring's only by which of the two rows bracketing the target it snaps to,
# under a pixel. Items 2 and 5 start some 50 mm above the window, where the
# offset read up to two rows off: item 5 landed 1.59 px high twice
# (swmaker00000F/A, 2026-10-01) and 1.89 px high once (swmaker00000F, run
# 20261010T073339590Z, its start moved 1.7 mm by the raised base deck).
# Placed at fit first, every ring starts inside the zoom: items 2, 5 and 9
# then landed 0.89, -0.11 and -0.11 px from target on swmaker00000a and
# swmaker000004; all 168 placements made at fit, both reads inside the
# window, stayed under a pixel.
_SHORT_BALLOON_ZOOM_HALF = 0.012
# How far the rebuild may move the balloon's SetPosition anchor: a model
# value, not a rendered one, so any move is the rebuild's.
_SHORT_BALLOON_POSITION_TOL_M = 1e-7


def _short_balloon_failures(
    state: dict[str, Any], target: tuple[float, float]
) -> list[str]:
    """What one read of a short-leader balloon's ring and length breaks,
    within that read's pixel."""
    failures = list(state["failed_checks"])
    leader = state["actual_leader_points"]
    length = sum(
        math.hypot(
            leader[index + 3] - leader[index], leader[index + 4] - leader[index + 1]
        )
        for index in range(0, len(leader) - 3, 3)
    )
    state["length_m"] = length
    if length > 0.030:
        failures.append("leader_length")
    circle = state["rendered_circle"]
    pixel = state["viewport_pixel_bounds_m"]
    if any(abs(circle[index] - target[index]) > pixel[index] for index in range(2)):
        failures.append("circle_position")
    return failures


def _leader_start_failures(state: dict[str, Any]) -> list[str]:
    """The leader leaves the ring: no point of it lies inside the ring by more
    than a pixel. Meaningful only on the read right after SetPosition."""
    leader = state["actual_leader_points"]
    circle = state["rendered_circle"]
    pixel = state["viewport_pixel_bounds_m"]
    if len(leader) >= 6 and any(
        math.hypot(leader[index] - circle[0], leader[index + 1] - circle[1])
        < circle[2] - max(pixel)
        for index in range(0, len(leader), 3)
    ):
        return ["leader_inside_ring"]
    return []


def _rebuilt_balloon_failures(
    after: dict[str, Any], placed: dict[str, Any], target: tuple[float, float]
) -> list[str]:
    """The re-zoomed read after the rebuild: ring on target, the same radius
    and arrowtip as placed, each within that read's pixel. Its leader start
    is not checked: the rebuild leaves it where the fit render put it, which
    is not where the PDF draws the leader (see :func:`_short_frame_balloon`)."""
    failures = _short_balloon_failures(after, target)
    pixel = max(after["viewport_pixel_bounds_m"])
    if abs(after["rendered_circle"][2] - placed["rendered_circle"][2]) > pixel:
        failures.append("ring_radius")
    tip, placed_tip = after["actual_leader_points"][-3:-1], placed["actual_leader_points"][-3:-1]
    if len(tip) != 2 or math.dist(tip, placed_tip) > pixel:
        failures.append("arrowtip_moved")
    return failures


@dataclass(frozen=True)
class _ShortBalloonProof:
    """What a short-leader balloon passed: its binding, target ring and the
    zoomed read right after placement, for :func:`_settled_short_balloon_failures`."""

    item: str
    annotation: Any
    entity: Any
    target: tuple[float, float]
    placed: dict[str, Any]


def _position_moved(state: dict[str, Any], placed: dict[str, Any]) -> bool:
    moved = [
        abs(a - b)
        for a, b in zip(state["annotation_position"][:2], placed["annotation_position"][:2])
    ]
    return len(moved) != 2 or max(moved) > _SHORT_BALLOON_POSITION_TOL_M


def _short_frame_balloon(
    adapter: Any, view: Any, note: Any, item: str, offset: tuple[float, float]
) -> _ShortBalloonProof:
    """Give frame balloon ``item`` a short leader ``offset`` from its arrowtip.

    The ring is placed at fit, then zoomed onto its target
    (:data:`_SHORT_BALLOON_ZOOM_HALF`), starting from inside that window, and
    read back there: on target, short, its leader leaving it. The window
    then goes back to fit and the drawing rebuilds, the state the export
    starts from: read there, the balloon must keep its attachment, item and
    SetPosition anchor. It is then read zoomed again, where the ring matches
    the print, and must keep its ring and arrowtip. Any failure fails the leaf.

    The rebuilt read's leader start is not checked. After the rebuild at fit,
    item 2's re-zoomed ring was the placed one to the micron, but its leader
    started 4.19 mm from the centre, the radius of the ring the fit render
    drew, inside the 4.89 mm zoomed ring: bit-identical on swmaker000008 and
    swmaker000005 (runs 20260928T144159300Z, 20260928T145256004Z), and
    UpdateViewDisplayGeometry zoomed did not move it. The PDF does not draw
    from it: from the same SetPosition, run 20260928T141421973Z printed the
    leader from the printed ring (0.001 mm), 0.45 mm from the start COM
    reported. The layout audit checks the printed leader.
    """
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1:
        raise RuntimeError(f"frame balloon {item} has no unique native attachment")
    entity = attached[0]
    before = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    if before["failed_checks"]:
        raise RuntimeError(f"frame balloon {item} has invalid placement input: {before!r}")
    leader = before["actual_leader_points"]
    # Native readback: the FIRST point meets the balloon; the LAST is the rim/
    # face arrowtip. Sheet XY determines placement and length; Z is view depth.
    target = (leader[-3] + offset[0], leader[-2] + offset[1])
    _telemetry.event("drawing.frame_short_balloon_before", item=item, target=target, **before)
    # To within a fit pixel, so the zoomed placement starts from a ring inside
    # its window (see _SHORT_BALLOON_ZOOM_HALF).
    position_bom_balloon(
        adapter, [note], item_number=item, position_xy=target,
        label="frame short-leader balloon at fit",
    )
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    with _zoomed_on(adapter, target, _SHORT_BALLOON_ZOOM_HALF):
        adapter.currentModel.GraphicsRedraw2()
        position_bom_balloon(
            adapter, [note], item_number=item, position_xy=target,
            label="frame short-leader balloon",
        )
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        view.UpdateViewDisplayGeometry()
        adapter.currentModel.GraphicsRedraw2()
        placed = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    fit = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    with _zoomed_on(adapter, target, _SHORT_BALLOON_ZOOM_HALF):
        adapter.currentModel.GraphicsRedraw2()
        after = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    failures = [
        f"zoomed:{name}"
        for name in _short_balloon_failures(placed, target) + _leader_start_failures(placed)
    ]
    failures += [f"fit:{name}" for name in fit["failed_checks"]]
    if _position_moved(fit, placed):
        failures.append("fit:position_moved")
    failures += [f"rebuilt:{name}" for name in _rebuilt_balloon_failures(after, placed, target)]
    state = {"before": before, "placed": placed, "fit": fit, "after": after,
             "target_circle": target, "failed_checks": failures}
    _telemetry.event("drawing.frame_short_balloon", item=item, **state)
    if failures:
        raise RuntimeError(f"frame balloon {item} short placement failed: {state!r}")
    return _ShortBalloonProof(
        item=item, annotation=annotation, entity=entity, target=target, placed=placed
    )


def _settled_short_balloon_failures(adapter: Any, proof: _ShortBalloonProof) -> list[str]:
    """Read a short-leader balloon zoomed onto its target again, as
    :func:`_short_frame_balloon` did after its own rebuild: every later
    rebuild (the next balloons', the finalizer's) re-solves it too. Ring,
    arrowtip and SetPosition anchor must still be the placed ones."""
    with _zoomed_on(adapter, proof.target, _SHORT_BALLOON_ZOOM_HALF):
        adapter.currentModel.GraphicsRedraw2()
        settled = _frame_balloon_binding_readback(
            adapter, proof.annotation, proof.entity, proof.item
        )
    failures = _rebuilt_balloon_failures(settled, proof.placed, proof.target)
    if _position_moved(settled, proof.placed):
        failures.append("position_moved")
    _telemetry.event(
        "drawing.frame_short_balloon_settled", item=proof.item, settled=settled,
        failed_checks=failures,
    )
    return failures


@dataclass(frozen=True)
class _BoundBalloonProof:
    """A rebound frame balloon without a short leader: its binding and the
    arrowtip read after :func:`_reattach_frame_balloons`' last rebuild."""

    item: str
    annotation: Any
    entity: Any
    tip: tuple[float, float]


@dataclass(frozen=True)
class _FrameBalloonProof:
    """What :func:`_reattach_frame_balloons` proved, for
    :func:`_assert_frame_balloons_settled`. ``rebound`` names the families
    whose component landing the rebind replaced."""

    rebound: frozenset[str]
    bound: tuple[_BoundBalloonProof, ...]
    short: tuple[_ShortBalloonProof, ...]


def _assert_frame_balloons_settled(
    adapter: Any, landings: Sequence[BalloonLanding], proof: _FrameBalloonProof
) -> None:
    """Prove every frame balloon again after the drawing's last rebuild.

    Each balloon was checked where it was placed, and every rebuild after
    that (the next balloons', the later sheets', the finalizer's) re-solves
    all of them. The component balloons keep their attachment and hit-tested
    landing (:func:`assert_balloon_landings`), the rebound ones their
    binding and arrowtip, the short-leader ones their ring, arrowtip and
    anchor (:func:`_settled_short_balloon_failures`). Every failure is named.
    """
    _activate_sheet(adapter, SHEET_NAMES[1])
    failures = []
    try:
        assert_balloon_landings(
            adapter, [landing for landing in landings if landing.stem not in proof.rebound]
        )
    except RuntimeError as error:
        failures.append(str(error))
    for bound in proof.bound:
        state = _frame_balloon_binding_readback(adapter, bound.annotation, bound.entity, bound.item)
        failed = list(state["failed_checks"])
        tip = state["actual_leader_points"][-3:-1]
        if len(tip) != 2 or math.dist(tip, bound.tip) > _BALLOON_LANDING_TOLERANCE_M:
            failed.append("arrowtip_moved")
        if failed:
            failures.append(f"frame balloon {bound.item}: {failed}")
    for short in proof.short:
        failed = _settled_short_balloon_failures(adapter, short)
        if failed:
            failures.append(f"frame balloon {short.item} short leader: {failed}")
    if failures:
        raise RuntimeError(
            "frame balloons changed after the final rebuild: " + "; ".join(failures)
        )


def _frame_bom_bottom(table: Any) -> float:
    """Read the unsplit, top-left-anchored BOM's actual lower rule."""
    table = _early_bound(table, "ITableAnnotation")
    position = tuple(_early_bound(table.GetAnnotation(), "IAnnotation").GetPosition() or ())
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    if (
        len(position) != 3 or not all(map(math.isfinite, position))
        or not heights or any(not math.isfinite(height) or height <= 0 for height in heights)
    ):
        raise RuntimeError("frame BOM has unreadable native extents")
    return position[1] - sum(heights)


def _frame_bom_balloon_failures(
    bottom: float, circle: Sequence[float], cap_circle: Sequence[float],
    leader: Sequence[float], cap_leader: Sequence[float],
) -> list[str]:
    """Keep item 10's complete ring below the BOM and clear of item 6's route."""
    failures = []
    if any(
        len(points) < 6 or len(points) % 3 or not all(map(math.isfinite, points))
        for points in (leader, cap_leader)
    ):
        return ["missing_leader"]
    if bottom - circle[1] - circle[2] < _BOM_BALLOON_CLEARANCE_M:
        failures.append("bom_rule_clearance")
    if math.dist(circle[:2], cap_circle[:2]) - circle[2] - cap_circle[2] < 0.002:
        failures.append("cap_balloon_clearance")
    routes = [
        [(tuple(points[i:i + 2]), tuple(points[i + 3:i + 5]))
         for i in range(0, len(points) - 3, 3)]
        for points in (leader, cap_leader)
    ]
    if not all(routes):
        failures.append("missing_leader")
    elif (
        any(segments_cross(a, b) for a in routes[0] for b in routes[1])
        or any(distance_to_point(segment, circle[:2]) < circle[2] + 0.001
               for segment in routes[1])
        or any(distance_to_point(segment, cap_circle[:2]) < cap_circle[2] + 0.001
               for segment in routes[0])
    ):
        failures.append("cap_leader_collision")
    return failures


def _place_frame_set_screw_balloon(
    adapter: Any, view: Any, table: Any, landings: Sequence[BalloonLanding],
) -> _ShortBalloonProof:
    landing = next(row for row in landings if row.stem == "fr-vn-gooseneck-set-screw")
    note = _early_bound(landing.note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    leader = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
    if len(leader) < 6:
        raise RuntimeError("frame set-screw balloon has no native leader")
    circle = rendered_balloon_circle(note, label="frame set-screw balloon")
    # Retain its right-hand lane beside the cap balloon. Lower it far enough
    # for both a full-ring BOM gap and a short leader, without changing the tip.
    target = (
        circle[0],
        min(_frame_bom_bottom(table) - circle[2] - 0.004, leader[-2] + 0.020),
    )
    return _short_frame_balloon(
        adapter, view, note,
        _balloon_item_number(adapter, note, label="frame set-screw balloon"),
        (target[0] - leader[-3], target[1] - leader[-2]),
    )


def _assert_frame_bom_balloon_clearance(
    adapter: Any, table: Any, landings: Sequence[BalloonLanding], proof: _ShortBalloonProof,
) -> None:
    """Check actual native circles and leader routes again after final rebuild."""
    cap = next(row for row in landings if row.stem == "fr-vn-tube-frame-cap")
    states = []
    for raw_note, target in ((proof.annotation.GetSpecificAnnotation(), proof.target),
                             (cap.note, None)):
        note = _early_bound(raw_note, "INote")
        if target is None:
            target = rendered_balloon_circle(note, label="frame cap balloon")[:2]
        with _zoomed_on(adapter, target, _SHORT_BALLOON_ZOOM_HALF):
            adapter.currentModel.GraphicsRedraw2()
            circle = rendered_balloon_circle(note, label="frame BOM balloon clearance")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            leader = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
            states.append((circle, leader))
    failures = _frame_bom_balloon_failures(
        _frame_bom_bottom(table), states[0][0], states[1][0], states[0][1], states[1][1],
    )
    if failures:
        raise RuntimeError(f"frame set-screw balloon clearance: {failures}")



def _reattach_frame_balloons(
    adapter: Any, view: Any, balloons: Sequence[Any], items: Sequence[tuple[str, str]]
) -> _FrameBalloonProof:
    families = _frame_visible_components(view)
    anchors = _upper_frame_balloon_edges(adapter, view, families)
    item_by_stem = dict(items)
    notes = {
        _balloon_item_number(adapter, note, label="frame balloon"): note
        for note in balloons
    }
    anchors["fr-top-frame"] = _exposed_top_casting_edge(
        adapter, view, families["fr-top-frame"]
    )
    bound = {}
    for stem, entity in anchors.items():
        item = item_by_stem[stem]
        notes[item], annotation, _point = _bind_frame_balloon(
            adapter, view, notes[item], entity, item
        )
        bound[item] = (annotation, entity)

    item = item_by_stem["fr-tube-frame"]
    notes[item], _annotation, _rim = _bind_left_column_balloon(
        adapter, view, notes[item], item, families["fr-tube-frame"]
    )

    item = item_by_stem["fr-vn-frame-cross-screw"]
    shanks = []
    for component, full in families["fr-vn-frame-cross-screw"]:
        if (
            abs(
                _component_point_in_assembly(full, (0.0, 0.0, 0.0))[1] * 1000.0
                - TOP_SCREW_Y
            )
            > 1e-5
        ):
            continue
        for raw_face in visible_component_entities(view, component, 3):
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if (
                not surface.IsCylinder()
                or abs(
                    float(surface.CylinderParams[6]) - CROSS_SCREW_SHANK_DIA / 2000.0
                )
                > 1e-7
            ):
                continue
            notes[item], _annotation, point = _bind_frame_balloon(
                adapter, view, notes[item], face, item
            )
            shanks.append(((point[0], point[1]), face))
    if not shanks:
        raise RuntimeError("no visibly exposed upper cross-screw shank")
    # The leftmost native attachment is outside the casting/column silhouettes.
    face = min(shanks, key=lambda row: row[0])[1]
    notes[item], _annotation, _point = _bind_frame_balloon(
        adapter, view, notes[item], face, item
    )

    # Offsets are sheet metres from each balloon's native attachment. Items 2
    # and 9 attach 7 mm apart on the upper-left column/casting corner: at
    # (-18, -12) and (-16, -8) mm their circles printed 1.50 mm apart, under the
    # audit's 0.5 x text-height clearance (1.74 mm); 9 now rises above the
    # screw instead. Item 5 at (+14, +10) mm printed onto the rear-right
    # MHA-FR-VN-54 cap; (+8, +16) mm clears it above the rear rail.
    short = {
        item_by_stem["fr-tube-frame"]: (-0.018, -0.012),
        item_by_stem["fr-top-frame"]: (0.008, 0.016),
        item_by_stem["fr-vn-frame-cross-screw"]: (-0.018, 0.004),
    }
    _spread_balloons(
        adapter,
        view,
        [note for item, note in notes.items() if item not in short],
        margin=0.012,
    )
    proofs = tuple(
        _short_frame_balloon(adapter, view, notes[item], item, offset)
        for item, offset in short.items()
    )
    adapter.currentModel.EditRebuild3()
    held = []
    for item, (annotation, entity) in bound.items():
        if item in short:
            continue
        state = _frame_balloon_binding_readback(adapter, annotation, entity, item)
        if state["failed_checks"]:
            raise RuntimeError(f"frame balloon {item} lost its binding: {state!r}")
        tip = state["actual_leader_points"][-3:-1]
        held.append(_BoundBalloonProof(item=item, annotation=annotation, entity=entity, tip=tip))
    return _FrameBalloonProof(
        rebound=frozenset((*anchors, "fr-tube-frame", "fr-vn-frame-cross-screw")),
        bound=tuple(held),
        short=proofs,
    )


def _place_package(adapter: Any) -> Callable[[], None]:
    """Place every sheet; return the check that proves every balloon again
    after the last rebuild (:func:`_assert_frame_balloons_settled`)."""
    _create_mixed_package_sheets(adapter)
    for sheet_name in SHEET_NAMES:
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(
            _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
        )
        sheet_scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(sheet_scale[0]), float(sheet_scale[1]), False, False):
            raise RuntimeError(f"failed to set native frame sheet scale: {sheet_name}")

    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *WORKING_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    set_hidden_lines_visible(adapter, front)
    # Before the dimensions and sections bind to it: the 1:8 view prints the
    # teeth/thread-free configuration, and the A-A/B-B sections follow it.
    _configure_view(adapter, front, exploded=False, label="working front")
    _add_frame_height_dimensions(adapter, front)
    _, top_section = _create_joint_sections(adapter, front)
    inset = _add_nameplate_inset_dimension(adapter, top_section)

    _add_note_block(
        adapter,
        "WORKING POSITION - A-A BASE JOINT / B-B TOP JOINT",
        (0.130, 0.263),
        label="working-view heading",
    )
    _add_note_block(
        adapter,
        "SCALE 1:8",
        (0.030, 0.065),
        label="working-view scale",
    )

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *EXPLODED_ISO_CENTER,
        scale=EXPLODED_ISO_SCALE,
    )
    set_high_quality_shaded_with_edges(
        adapter, exploded, label="frame exploded anchor visibility"
    )
    # Configuration, then its own explode, then the BOM and balloons bind.
    _configure_view(adapter, exploded, exploded=True, label="exploded isometric")
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="frame",
    )
    balloon_items = _validate_frame_bom(adapter, table)
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        anchors=FRAME_BALLOON_ANCHORS,
        label="frame exploded-view BOM coverage",
        margin=0.012,
    )
    proof = _reattach_frame_balloons(
        adapter, exploded, [landing.note for landing in landings], balloon_items
    )
    # The ring layout does not know the BOM's rebuilt row heights. Keep item 10
    # below its actual bottom rule without changing the native screw attachment.
    set_screw_proof = _place_frame_set_screw_balloon(adapter, exploded, table, landings)
    proof = _FrameBalloonProof(
        rebound=proof.rebound, bound=proof.bound,
        short=(*proof.short, set_screw_proof),
    )
    _assert_frame_bom_balloon_clearance(adapter, table, landings, set_screw_proof)
    _add_note_block(
        adapter,
        f"EXPLODED VIEW {EXPLODED_ISO_SCALE[0]:g}:{EXPLODED_ISO_SCALE[1]:g}"
        " - SEE SHEET 3 FOR INSTALLATION ORDER",
        (0.045, 0.075),
        label="exploded-view caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[2])
    instruction_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLY_ISO_CENTER,
        scale=ASSEMBLY_ISO_SCALE,
    )
    # The drawing's full-detail view: every modeled tooth and thread.
    _configure_view(
        adapter,
        instruction_iso,
        exploded=False,
        role=ViewRole.FULL_DETAIL,
        label="assembly instruction isometric",
    )
    assert_full_detail_view(adapter, label="frame assembly")
    # A blank line between steps gives the sequence 48 rows. At the ~4.5 mm
    # pitch measured on the printed sheet they end near y=46 mm, clear of the
    # bottom border and left of the title block; the checks cannot follow.
    _add_note_block(adapter, ASSEMBLY_STEPS, (0.018, 0.263), label="assembly sequence")
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:7",
        (0.300, 0.074),
        label="assembly isometric caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[3])
    checks_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLY_ISO_CENTER,
        scale=ASSEMBLY_ISO_SCALE,
    )
    _configure_view(
        adapter, checks_iso, exploded=False, label="assembly checks isometric"
    )
    _add_note_block(adapter, ASSEMBLY_CHECKS, (0.018, 0.263), label="assembly checks")
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:7",
        (0.300, 0.074),
        label="assembly checks isometric caption",
    )

    def settled() -> None:
        _assert_frame_balloons_settled(adapter, landings, proof)
        _assert_frame_bom_balloon_clearance(adapter, table, landings, set_screw_proof)
        _assert_inset_dimension_settled(adapter, inset)

    return settled


@_telemetry.traced("drawing.inset_dimension_settled")
def _assert_inset_dimension_settled(
    adapter: Any, proof: _InsetDimensionProof, *, phase: str = "final rebuild"
) -> None:
    """Prove the rebuilt section still owns the dimension and both real edges.

    Runs 20261022T194220151Z and 20261022T204612817Z initially read
    ``IsDangling=False`` and 4 mm, then lost every attached entity on rebuild.
    Reacquire each section edge from its session-safe model entity before
    comparing the annotation's native attachments. Ordinary cached topology
    pointers and the measured value alone cannot establish surviving references.
    """
    display = _early_bound(proof.display, "IDisplayDimension")
    view = _early_bound(proof.view, "IView")
    dangling, types = _dimension_attachment(display)
    expected_view = view_name(adapter, view)
    expected_instances = tuple(ref.instance for ref in proof.references)
    _telemetry.event(
        "drawing.inset_dimension_settled", phase=phase, dangling=dangling, types=types,
        expected_view=expected_view, expected_instances=expected_instances,
    )
    if dangling:
        raise RuntimeError(
            f"nameplate end inset dangles after the {phase} (attached entity types {types})"
        )
    try:
        edges = tuple(
            _inset_section_edge(
                adapter, view, ref.model_edge, component=ref.component, label=ref.label,
            )
            for ref in proof.references
        )
        measured_mm = assert_dimension_measures(
            adapter, display, expected_mm=NAMEPLATE_END_INSET,
            label=f"nameplate end inset after {phase}", entities=edges,
        )
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        # On the native screen positive control and both mapped variants,
        # GetAttachedEntityTypes was empty despite two exact live attachments.
        # Query the actual attached objects, not that legacy summary array.
        attached_types = tuple(
            int(_early_bound(entity, "IEntity").GetType())
            for entity in (annotation.GetAttachedEntities3() or ())
        )
        kind = int(display.Type2)
        # swLinearDimension / swHorLinearDimension / swVertLinearDimension.
        if attached_types != (_SW_SEL_EDGES, _SW_SEL_EDGES) or kind not in (2, 11, 12):
            raise RuntimeError(
                f"nameplate end inset lost its edge/linear type: {attached_types}, {kind}"
            )
        inventory = tuple(view.GetDisplayDimensions() or ())
        if sum(int(adapter.swApp.IsSame(item, display)) == 1 for item in inventory) != 1:
            raise RuntimeError("nameplate end inset is not owned by its section view")
    except RuntimeError as exc:
        _telemetry.event(
            "drawing.inset_dimension", phase=phase, dangling=dangling, types=types,
            expected_view=expected_view, expected_instances=expected_instances,
            reference_failure=str(exc),
        )
        raise
    _telemetry.event(
        "drawing.inset_dimension", phase=phase, dangling=dangling, types=types,
        expected_view=expected_view, expected_instances=expected_instances,
        attached_entity_types=attached_types,
        measured_mm=measured_mm, dimension_type=kind, section_owned=True,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open frame drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError(
            "frame source assembly is already dirty; refusing to discard user changes"
        )
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    source_title = str(source_model.GetTitle() or "")
    if not source_title:
        raise RuntimeError("frame source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        _validate_persisted_explode(source_model)
        settled = _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Frame Assembly Drawing Package",
            scale=SHEET_SCALE,
            expected_sheet_names=SHEET_NAMES,
            sheet_layouts=SHEET_LAYOUTS,
            sheet_scales=SHEET_SCALES,
            settled_checks=(settled,),
        )
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        # A failed placement leaves an unsaved drawing active. Its views retain
        # the source assembly, so release the drawing before discarding source.
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:  # swDocDRAWING
                        drawing_title = str(active_model.GetTitle() or "")
                        if not drawing_title:
                            cleanup_errors.append(
                                "generated frame drawing has no title for close"
                            )
                        else:
                            adapter.swApp.CloseDoc(drawing_title)
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"failed to close generated frame drawing: {exc}")

        try:
            adapter.swApp.CloseDoc(source_title)
            if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
                cleanup_errors.append(
                    f"frame source {source_title!r} remained open after discard"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to close frame source {source_title!r}: {exc}"
            )

        try:
            after_fingerprint = _source_fingerprint(SOURCE)
            if after_fingerprint != fingerprint:
                cleanup_errors.append(
                    "frame drawing generation changed the released source assembly "
                    f"(size, mtime_ns, SHA256): {fingerprint!r} -> "
                    f"{after_fingerprint!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to verify frame source fingerprint: {exc}")

        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(f"frame drawing cleanup after failure: {message}")
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("frame drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
