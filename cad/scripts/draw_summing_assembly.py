r"""Create the native four-sheet summing assembly drawing package.

The released ``summing.SLDASM`` stays authoritative and byte-for-byte
unchanged. This recipe consumes the builder-owned ``SUMMING_EXPLODED``
presentation and adds drawing-native associative fit measurements; it never
authors or saves source-assembly presentation or construction features.
"""

from __future__ import annotations

import argparse
import math
import hashlib
import sys
from pathlib import Path
from typing import Any, Callable, Literal

import _telemetry
from _common import _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_component_bom_balloons,
    check_drawing_layout,
    create_blank_drawing_sheets,
    create_section_view,
    finalize_drawing,
    import_cosmetic_threads,
    insert_bom_table,
    isolate_drawing_view_components,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from solidworks_mcp.adapters.com_variant import dispatch_array, double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from summing_assembly_spec import (
    BOM_COMPONENTS,
    BOM_DESCRIPTIONS,
    BOM_IDENTITY_ALIASES,
    BOM_NORMALIZED_ALIASES,
    BOM_PART_NUMBERS,
    BOM_QUANTITIES,
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
)
from build_knife_hanger_stud import THREAD_TIP_ROOT_RADIUS_MM
from build_knife_mount import STUD_TAP_DIA
from build_summing_assembly import (
    DRAWING_NUMBER,
    HANGER_COMPLETE_MALE_START_DEPTH_MM,
    HANGER_ENGAGEMENT_GENERAL_TOLERANCE_MM,
    HANGER_ENGAGEMENT_MAX_MM,
    HANGER_ENGAGEMENT_MIN_MM,
    HANGER_ENGAGEMENT_PRECISION,
    HANGER_ENGAGEMENT_TARGET_MM,
    HANGER_TAP_DRILL_SHOULDER_MIN_MM,
    HANGER_TAP_FULL_THREAD_MIN_MM,
    HEX_Z_MID,
    KNIFE,
    KNIFE_MOUNT_TOP_Y,
)
from cone_pivot_post_installation import SUMMING_Z


SPEC = DRAWINGS_BY_NAME["summing_assembly"]
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

# Sheet 4 keeps its position: the MHA-119 stud note cites "SHEET 4". Checks,
# setup and interfaces moved to an appended sheet 5 (Main, 2026-09-22) because
# 60 note lines at the 3.5 mm ASME Y14.2 height cannot share sheet 3.
SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY SEQUENCE",
    "HANGER FIT + INSPECTION",
    "CHECKS + SETUP",
)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the summing package primary sheet must remain landscape")

ASSEMBLED_SCALE = (1.0, 4.0)
EXPLODED_SCALE = (1.0, 4.0)
INSTRUCTION_SCALE = (1.0, 6.0)
HANGER_FIT_SHEET_SCALE = (1.0, 1.0)
HANGER_PARENT_SCALE = (1.0, 2.0)
HANGER_SECTION_SCALE = (1.0, 2.0)
HANGER_DETAIL_SCALE = (4.0, 1.0)
NOTES_SHEET_SCALE = (1.0, 1.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: EXPLODED_SCALE,
    SHEET_NAMES[2]: INSTRUCTION_SCALE,
    SHEET_NAMES[3]: HANGER_FIT_SHEET_SCALE,
    SHEET_NAMES[4]: NOTES_SHEET_SCALE,
}

ASSEMBLED_FRONT_CENTER = (0.065, 0.158)
ASSEMBLED_RIGHT_CENTER = (0.185, 0.158)
ASSEMBLED_ISO_CENTER = (0.330, 0.158)
EXPLODED_ISO_CENTER = (0.105, 0.158)
INSTRUCTION_ISO_CENTER = (0.345, 0.190)
HANGER_PARENT_CENTER = (0.060, 0.205)
HANGER_SECTION_CENTER = (0.300, 0.205)
# Where the knife-mount top on the hanger axis lands on sheet 4. The views
# carry the whole (mostly hidden) assembly box, so they are placed by this
# model point, not by their outline.
HANGER_PARENT_ANCHOR_XY = (0.040, 0.200)
HANGER_SECTION_ANCHOR_XY = (0.140, 0.200)
HANGER_DETAIL_CENTER = (0.095, 0.085)
# The native detail label letter. The sheet heading and the MHA-119 stud note
# reference it; test_summing_assembly_drawing.py pins the cross-reference.
HANGER_DETAIL_LABEL = "B"
HANGER_DETAIL_LABEL_XY = (0.070, 0.142)
# Built-solid readback tolerances: circle y/r agreement, and how far a circle
# centre may sit off the nominal hanger axis and still belong to that station.
BUILT_GEOMETRY_TOLERANCE_MM = 1e-4
BUILT_STATION_TOLERANCE_MM = 0.01
# The BOM sits bottom-right, just above the title block, so the exploded view
# and its balloon ring own the upper-left of the sheet. DESCRIPTION is wide
# enough for the longest description on one line (r9: 70 chars wrapped at
# 145 mm; the rendered pitch is about 2.63 mm per character).
BOM_COLUMN_WIDTHS = {
    "item": 0.018,
    "part": 0.030,
    "description": 0.190,
    "quantity": 0.014,
}
BOM_ANCHOR = (0.414 - sum(BOM_COLUMN_WIDTHS.values()), 0.130)
# Requested row height. SolidWorks raises any row to the minimum that fits its
# text, so a row may persist taller (the header, legitimately); never shorter.
BOM_ROW_HEIGHT = 0.006
BOM_HEIGHT_TOLERANCE = 1e-6
# Paper clearance kept between the table and the sheet edge / title block.
BOM_SHEET_CLEARANCE = 0.003
# Sheet-space note fields (x0, top, x1, bottom), in metres. Blocks stack top
# down inside a field and each block's measured extent is gated against it.
NOTE_FIELD_LEFT = (0.018, 0.263, 0.212, 0.035)
NOTE_FIELD_RIGHT = (0.222, 0.263, 0.415, 0.072)
# Notes aim this far inside their field, so an imperfect move stays contained;
# the gate is containment, never the anchor residual (summing-asm-r11).
NOTE_FIELD_INSET = 0.0005
NOTE_ANCHOR_PASSES = 3
NOTE_ANCHOR_SETTLE = 0.00005
NOTE_BLOCK_GAP = 0.006
# Region the exploded view's balloon ring must fit: left of the BOM, below the
# heading, above the caption. The ring is the view outline grown by the
# balloon margin plus one rendered balloon diameter.
EXPLODED_RING_REGION = (0.020, 0.040, 0.160, 0.252)
EXPLODED_BALLOON_MARGIN = 0.012
BALLOON_DIAMETER = 0.010
# Only assembly-level requirements live here. Part drawings own component
# manufacture, and calculated native placements remain evidence rather than
# fitter tolerances. Keeping these drawing notes out of the assembly spec also
# keeps wording-only changes out of the native assembly rebuild closure.
ASSEMBLY_STEPS = "\n".join(
    (
        "MATCH-DRILL AND ASSEMBLY SEQUENCE",
        "1. OFF THE FRAME, FIT MHA-073 BETWEEN THE ACTUAL MHA-037 PAIR.",
        "   SEAT BOTH KNIFE CONTACTS, CENTER THE LEVER AXIALLY, AND VERIFY",
        "   FREE ROCK WITHOUT AXIAL RUB. RETAIN THIS FITTED PAIR AS A SET.",
        "2. OFFER THE FITTED SET TO THE MHA-077 UNDERSIDE. CENTER THE",
        "   KNIFE LINE ON THE CROSSBAR WIDTH. ALIGN THE ACTUAL MHA-073",
        "   COUNTER-BOSS TAP AXIS AND MHA-077 GUIDE-BORE AXIS IN ONE PLANE",
        "   NORMAL TO THE KNIFE AXIS; CLAMP WITHOUT DISTURBING THE FIT.",
        "3. MHA-077 MUST HAVE NO FINISHED HANGER-HOLE LOCATIONS. TRANSFER",
        "   FROM THE ACTUAL MHA-037 TAP AXES, THEN REMOVE THE FITTED SET.",
        "   PILOT AND MATCH-DRILL 2X MHA-077 FINAL CLEARANCE HOLES AT THE",
        "   TRANSFERRED CENTERS; NEVER ENTER THE MHA-037 TAPS. DO NOT",
        "   RECENTER TO CAD COORDINATES OR PRE-DRILLED MARKS. DEBURR;",
        "   RETAIN PAIR, FRONT/REAR, AND ORIENTATION MATCH MARKS.",
        "4. KEEP EACH MHA-119/MHA-131 WITH ITS IDENTIFIED SIDE. MEASURE,",
        "   TRIM, AND INSPECT EACH ACTUAL STACK PER SHEET 4; THEN ASSEMBLE",
        "   FROM ABOVE WITH WASHER ON CROSSBAR AND HEAD FULLY ON WASHER.",
        "5. THREAD MHA-005 DIRECTLY INTO THE MHA-073 COUNTER BOSS; NO NUT.",
        "   CLOCK THE OPEN EYE TO THE PULL PLANE AND APPLY REMOVABLE",
        "   MEDIUM-STRENGTH THREADLOCKER.",
        "6. LOOSEN THE MHA-032 SPRING-RETAINER SCREW ONLY AS NEEDED",
        "   FOR ACCESS. HOOK MHA-019 BETWEEN MHA-005 AND MHA-032, THEN",
        "   TIGHTEN THE SCREW TO CLAMP THE UPPER EYE AGAINST THE ARM END.",
        "   DO NOT APPLY THREADLOCKER TO THE MHA-032 RETAINER SCREW.",
        "7. WITH EXTERNAL MHA-118 BACKED CLEAR, SLIDE MHA-032 IN THE",
        "   MHA-077 GUIDE BORE. LEAVE THE POST FREE FOR FINAL BALANCE.",
        "8. AT FINAL MACHINE ASSEMBLY, THREAD 20 MHA-090 DIRECTLY INTO",
        "   THE 20 MHA-073 TAPPED SEATS; OMIT SUPPLIED NUTS. CLOCK EACH EYE",
        "   TO ITS MHA-011 SPRING PULL PLANE AND APPLY REMOVABLE",
        "   MEDIUM-STRENGTH THREADLOCKER. KEEP EACH CUT END RECESSED;",
        "   BACK OUT NO MORE THAN ONE TURN.",
        "9. AT CRANK HOME WITH ALL CHANNELS AT NEUTRAL, SLIDE MHA-032 UNTIL",
        "   MHA-073 IS LEVEL AND FREE-BALANCED; THEN TIGHTEN MHA-118.",
    )
)

ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. MHA-077/MHA-037 PAIR AND FRONT/REAR MATCH MARKS ALIGN.",
        "   BOTH MHA-119 PASS FREELY; HEADS AND MHA-131 WASHERS BEAR FULLY.",
        "   EACH AS-BUILT FIT MEETS SHEET 4; NEITHER STUD FORCES OR BOTTOMS.",
        "2. MHA-073 COUNTER-BOSS TAP AND MHA-077 GUIDE-BORE AXES SHARE",
        "   ONE PLANE NORMAL TO THE KNIFE AXIS. BOTH KNIFE CONTACTS ARE",
        "   SEATED; MHA-073 IS CENTERED AND ROCKS FREELY WITHOUT AXIAL RUB,",
        "   CLAMPING, OR A LOCKING CONSTRAINT.",
        "3. MHA-005 IS DIRECTLY THREADED, HAS NO NUT, AND ITS EYE FOLLOWS",
        "   THE COUNTER-SPRING PULL PLANE.",
        "4. THE MHA-019 UPPER EYE IS CLAMPED BETWEEN THE MHA-032 SCREW",
        "   HEAD AND ARM END AND CANNOT ESCAPE; NO THREADLOCKER IS PRESENT.",
        "   THE LOWER LOOP STAYS ON MHA-005; THE TENSIONED COIL CLEARS",
        "   MHA-032 AND MHA-073.",
        "5. MHA-032 SLIDES FREELY BEFORE SETTING AND IS HELD BY MHA-118",
        "   AFTER THE NEUTRAL BALANCE IS ESTABLISHED.",
        "6. ALL 20 MHA-090 EYES FOLLOW THEIR MHA-011 SPRING PULL PLANES;",
        "   NO NUTS ARE FITTED. CUT ENDS STAY RECESSED ABOVE THE MHA-073",
        "   UNDERSIDE AND RETAIN AT LEAST TWO FULL THREADS.",
        "7. AT CRANK HOME / NEUTRAL CHANNEL SETTING, MHA-073 IS LEVEL AND",
        "   RETURNS THROUGH ITS INTENDED FREE ROCK WITHOUT BINDING.",
    )
)

SETUP_NOTES = "\n".join(
    (
        "NEUTRAL / FREE-ROCKING SETUP",
        "SAVED DEFAULT IS THE NEUTRAL REFERENCE POSE.",
        "LEVER_ROCK IS THE ONE INTENTIONAL FREE DOF; DO NOT LOCK IT.",
        "NO PARKED OR ENGAGED CONFIGURATION IS DEFINED IN THIS SUBASSEMBLY.",
        "SET FINAL BALANCE WITH INSTALLED SPRINGS, NOT A CAD SPRING LENGTH.",
    )
)

INTERFACE_NOTES = "\n".join(
    (
        "EXTERNAL INSTALLATION INTERFACES - NOT BOM ITEMS",
        "MHA-077 / ACTUAL MHA-037 PAIR IS A NON-INTERCHANGEABLE SET.",
        "MHA-077 SUPPORTS THE HANGERS AND GUIDES MHA-032.",
        "MHA-118 LOCKS MHA-032 AFTER THE NEUTRAL SETUP.",
        "20X MHA-090 AND 20X MHA-011 BELONG TO THE CHANNEL ASSEMBLY.",
    )
)

HANGER_FIT_CONSTRUCTION = "\n".join(
    (
        "HANGER STUD CONSTRUCTION - MEASURE EACH IDENTIFIED SIDE",
        "T = MHA-077 THICKNESS FROM TOP WASHER SEAT TO LOWER FRAME FACE",
        "AT THE TRANSFERRED HANGER HOLE.",
        "W = ASSIGNED MHA-131 THICKNESS BETWEEN ITS TWO SEATING FACES.",
        "G = POSITIVE CLEARANCE FROM MHA-077 LOWER FRAME FACE TO THE",
        "MHA-037 TOP FACE IN THE FREE, FULLY SEATED POSITION.",
        "L = MHA-119 UNDER-HEAD SEAT TO FINISHED THREADED-END TIP.",
        "E = MHA-037 TAP MOUTH/TOP FACE TO FINISHED TIP; SEE DETAIL B.",
        "CUT L = T + W + G + E. MHA-119 UNDER-HEAD LENGTH IS REFERENCE.",
        "CHAMFER EACH CUT TO THE EXISTING THREAD ROOT PER MHA-119.",
        "MARK EACH BOLT FRONT/REAR; KEEP IT WITH ITS MHA-037/MHA-131 STATION.",
    )
)

HANGER_FIT_INSPECTION = "\n".join(
    (
        "AS-BUILT HANGER FIT - INSPECT EACH IDENTIFIED SIDE",
        "E MUST MEET DETAIL B'S NATIVE GENERAL .XX BAND.",
        "FINISHED TIP MUST NOT PASS THE ACTUAL MHA-037 COMPLETE-THREAD DEPTH.",
        "REQUIRE POSITIVE AXIAL OVERLAP BETWEEN COMPLETE MHA-119 MALE THREAD",
        "AND COMPLETE MHA-037 FEMALE THREAD.",
        "VERIFY FULL HEAD/WASHER SEATING AND POSITIVE MOUNT-TO-FRAME",
        "CLEARANCE.",
        "VERIFY BOTH KNIFE CONTACTS AND FREE ROCK WITHOUT AXIAL RUB.",
        "NO FORCING OR BOTTOMING.",
    )
)


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
    adapter: Any,
    text: str,
    xy: tuple[float, float],
    *,
    label: str,
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


def note_field_violations(
    extent: tuple[float, float, float, float],
    field: tuple[float, float, float, float],
) -> list[str]:
    """Name every edge of a note box (x0, y0, x1, y1) that leaves its field."""
    x0, y0, x1, y1 = extent
    left, top, right, bottom = field
    violations = []
    if x0 < left - 1e-6:
        violations.append(f"left {x0 * 1000:.2f} mm < field {left * 1000:.2f}")
    if x1 > right + 1e-6:
        violations.append(f"right {x1 * 1000:.2f} mm > field {right * 1000:.2f}")
    if y1 > top + 1e-6:
        violations.append(f"top {y1 * 1000:.2f} mm > field {top * 1000:.2f}")
    if y0 < bottom - 1e-6:
        violations.append(f"bottom {y0 * 1000:.2f} mm < field {bottom * 1000:.2f}")
    return violations


def _note_extent(adapter: Any, note: Any, *, label: str) -> tuple[float, ...]:
    """The rendered sheet-space box (x0, y0, x1, y1) of a free note."""
    adapter.currentModel.GraphicsRedraw2()
    extent = tuple(float(value) for value in (_early_bound(note, "INote").GetExtent() or ()))
    if len(extent) != 6 or extent[3] <= extent[0] or extent[4] <= extent[1]:
        raise RuntimeError(f"{label}: note has no rendered extent: {extent!r}")
    return (extent[0], extent[1], extent[3], extent[4])


def _anchor_note(
    adapter: Any,
    note: Any,
    corner: tuple[float, float],
    *,
    label: str,
) -> tuple[float, ...]:
    """Steer a note's RENDERED top-left corner toward ``corner``.

    The text box neither sits on the insertion point (summing-asm-r10: 0.28 mm
    right, 0.34 mm down) nor follows it 1:1 (r11: 0.162 mm residual after one
    exact move), so this iterates move -> re-measure -> correct up to
    NOTE_ANCHOR_PASSES times and never gates on the residual. The caller aims
    NOTE_FIELD_INSET inside its field and gates on containment.
    """
    target_x, target_y = corner
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation is None:
        raise RuntimeError(f"{label}: note has no annotation to move")
    extent = _note_extent(adapter, note, label=label)
    moves = 0
    for _pass in range(NOTE_ANCHOR_PASSES):
        shift = (target_x - extent[0], target_y - extent[3])
        if max(abs(shift[0]), abs(shift[1])) <= NOTE_ANCHOR_SETTLE:
            break
        position = tuple(float(value) for value in (annotation.GetPosition() or ()))
        if len(position) != 3:
            raise RuntimeError(f"{label}: note position is unreadable: {position!r}")
        if not annotation.SetPosition(
            position[0] + shift[0], position[1] + shift[1], position[2]
        ):
            raise RuntimeError(f"{label}: note SetPosition failed")
        extent = _note_extent(adapter, note, label=label)
        moves += 1
    _telemetry.event(
        "drawing.note_anchor",
        block=label,
        moves=moves,
        target_mm=(target_x * 1000.0, target_y * 1000.0),
        residual_mm=(
            (extent[0] - target_x) * 1000.0,
            (extent[3] - target_y) * 1000.0,
        ),
        extent_mm=tuple(value * 1000.0 for value in extent),
    )
    return extent


def _stack_note_field(
    adapter: Any,
    blocks: tuple[tuple[str, str], ...],
    field: tuple[float, float, float, float],
    *,
    label: str,
) -> list[str]:
    """Stack note blocks top-down in one field by their rendered extents.

    Returns every block's field violations instead of raising on the first, so
    one farm round reports every field; ``_check_package_layout`` fails on them.
    """
    left, top, _right, _bottom = field
    y = top
    findings = []
    for block_label, text in blocks:
        note = _add_note_block(adapter, text, (left, y), label=block_label)
        extent = _anchor_note(
            adapter,
            note,
            (left + NOTE_FIELD_INSET, y - NOTE_FIELD_INSET),
            label=block_label,
        )
        violations = note_field_violations(extent, field)
        _telemetry.event(
            "drawing.note_field",
            field=label,
            block=block_label,
            extent_mm=tuple(value * 1000.0 for value in extent),
            violations=tuple(violations),
        )
        if violations:
            findings.append(
                f"{label}: {block_label} leaves its note field: "
                + "; ".join(violations)
            )
        y = extent[1] - NOTE_BLOCK_GAP
    return findings


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"view has an invalid outline {outline!r}")
    return outline


def _shift_view(adapter: Any, view: Any, delta: tuple[float, float], *, label: str) -> None:
    """Move a drawing view by a sheet-space delta and read the move back."""
    view = _early_bound(view, "IView")
    before = tuple(float(value) for value in view.Position)
    target = (before[0] + delta[0], before[1] + delta[1])
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if math.dist(after, target) > 1e-6:
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")


def _place_view_by_model_point(
    adapter: Any,
    view: Any,
    model_point_mm: tuple[float, float, float],
    target_xy: tuple[float, float],
    *,
    label: str,
) -> None:
    """Land one model point of a view on a sheet target (views of an isolated
    assembly keep the whole assembly's box, so their outline is no guide)."""
    current = model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in model_point_mm),
        label=label,
    )
    _shift_view(
        adapter,
        view,
        (target_xy[0] - current[0], target_xy[1] - current[1]),
        label=label,
    )
    landed = model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in model_point_mm),
        label=label,
    )
    if math.dist(landed[:2], target_xy) > 1e-6:
        raise RuntimeError(f"{label}: model point landed at {landed!r}, not {target_xy!r}")


def ring_fit_shift(
    outline: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
    *,
    grow: float,
) -> tuple[tuple[float, float], list[str]]:
    """Shift that centres an outline's balloon ring in a region, plus overflows.

    The ring is estimated from the view OUTLINE, which SolidWorks pads beyond
    the ink, so an overflow is reported rather than raised: the end-of-build
    layout audit on the real balloons is the hard gate.
    """
    ring = (
        outline[0] - grow,
        outline[1] - grow,
        outline[2] + grow,
        outline[3] + grow,
    )
    x0, y0, x1, y1 = region
    ring_w, ring_h = ring[2] - ring[0], ring[3] - ring[1]
    overflows = [
        f"{axis} {size * 1000:.1f} mm > {room * 1000:.1f} mm"
        for axis, size, room in (
            ("width", ring_w, x1 - x0),
            ("height", ring_h, y1 - y0),
        )
        if size > room
    ]
    shift = (
        (x0 + x1) / 2.0 - (ring[0] + ring[2]) / 2.0,
        (y0 + y1) / 2.0 - (ring[1] + ring[3]) / 2.0,
    )
    return shift, overflows


def _check_package_layout(adapter: Any, field_findings: list[str]) -> None:
    """Run the layout audit on every sheet and fail on any finding at all,
    including the note-field findings collected while the sheets were placed.
    """
    failures = list(field_findings)
    for number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        try:
            check_drawing_layout(
                adapter,
                layout=SHEET_LAYOUTS[sheet_name],
                stem=f"{ARTIFACT_STEM} sheet {number}",
            )
        except RuntimeError as exc:
            failures.append(f"sheet {number} {sheet_name}: {exc}")
    if failures:
        raise RuntimeError(
            "summing package layout audit failed:\n" + "\n".join(failures)
        )


def _component_point_in_assembly(
    component: Any,
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Transform one component-local point through its native assembly transform."""
    values = tuple(
        float(value)
        for value in _early_bound(
            _early_bound(component, "IComponent2").Transform2,
            "IMathTransform",
        ).ArrayData
    )
    if len(values) != 16:
        raise RuntimeError("summing drawing component transform is incomplete")
    x, y, z = point
    scale = values[12]
    return (
        scale * (x * values[0] + y * values[3] + z * values[6]) + values[9],
        scale * (x * values[1] + y * values[4] + z * values[7]) + values[10],
        scale * (x * values[2] + y * values[5] + z * values[8]) + values[11],
    )


def _visible_component_circle(
    view: Any,
    *,
    component_stem: str,
    height_mm: float,
    radius_mm: float,
    target_z_mm: float,
    label: str,
) -> Any:
    """Resolve one actual component edge by identity and native circle geometry."""
    view = _early_bound(view, "IView")
    full_components: dict[str, Any] = {}
    for raw_drawing_component in tuple(view.GetVisibleDrawingComponents() or ()):
        drawing_component = _early_bound(raw_drawing_component, "IDrawingComponent")
        component = _early_bound(drawing_component.Component, "IComponent2")
        name = str(component.Name2 or "").rsplit("/", 1)[-1]
        if name in full_components:
            raise RuntimeError(f"{label}: duplicate visible component {name!r}")
        full_components[name] = component

    candidates: list[tuple[tuple[float, ...], Any]] = []
    # Every circle this stem shows in the view, (component, y, r, z) in mm, so
    # a miss names what the view actually offered instead of just "none".
    seen_circles: list[tuple[str, float, float, float]] = []
    edge_counts: dict[str, int] = {}
    for raw_component in tuple(view.GetVisibleComponents() or ()):
        visible_component = _early_bound(raw_component, "IComponent2")
        if _component_stem(visible_component) != component_stem:
            continue
        name = str(visible_component.Name2 or "").rsplit("/", 1)[-1]
        edge_counts[name] = 0
        full_component = full_components.get(name)
        if full_component is None:
            raise RuntimeError(f"{label}: component {name!r} has no full peer")
        transform_values = tuple(
            float(value)
            for value in _early_bound(
                full_component.Transform2,
                "IMathTransform",
            ).ArrayData
        )
        component_scale = transform_values[12]
        for raw_edge in tuple(view.GetVisibleEntities2(visible_component, 1) or ()):
            edge_counts[name] += 1
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve is None or not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if len(parameters) < 7:
                raise RuntimeError(f"{label}: circular edge parameters are incomplete")
            center = _component_point_in_assembly(
                full_component,
                (parameters[0], parameters[1], parameters[2]),
            )
            actual_height_mm = center[1] * 1000.0
            actual_radius_mm = parameters[6] * component_scale * 1000.0
            seen_circles.append(
                (name, actual_height_mm, actual_radius_mm, center[2] * 1000.0)
            )
            if abs(actual_height_mm - height_mm) > 1e-5:
                continue
            if abs(actual_radius_mm - radius_mm) > 1e-5:
                continue
            candidates.append(
                (
                    (
                        abs(center[2] * 1000.0 - target_z_mm),
                        abs(center[0] * 1000.0 - KNIFE[0]),
                        center[2],
                        *parameters[:3],
                    ),
                    edge,
                )
            )
    nearest = sorted(
        seen_circles,
        key=lambda circle: abs(circle[1] - height_mm) + abs(circle[2] - radius_mm),
    )[:8]
    _telemetry.event(
        "drawing.visible_circle_search",
        label=label,
        view=str(view.GetName2() or ""),
        component_stem=component_stem,
        target_y_mm=height_mm,
        target_radius_mm=radius_mm,
        edge_counts=tuple(sorted(edge_counts.items())),
        circle_count=len(seen_circles),
        matches=len(candidates),
        nearest=tuple(
            f"{name} y={y:.5f} r={r:.5f} z={z:.3f}" for name, y, r, z in nearest
        ),
    )
    if not candidates:
        raise RuntimeError(
            f"{label}: no {component_stem!r} circle at y={height_mm:g} mm, "
            f"radius={radius_mm:g} mm in view {view.GetName2()!r}; visible "
            f"edges per component {edge_counts!r}, {len(seen_circles)} circles; "
            "nearest (component, y, r, z mm): "
            + "; ".join(
                f"{name} {y:.5f} {r:.5f} {z:.3f}" for name, y, r, z in nearest
            )
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def hanger_engagement_violations(
    mouth_y_mm: float,
    tip_y_mm: float,
) -> list[str]:
    """Judge a BUILT tap-mouth/finished-tip pair against the receiver band.

    The assembly's stack gate proves the constants agree; this proves the
    solids the drawing dimensions do.
    """
    engagement = mouth_y_mm - tip_y_mm
    violations = []
    if abs(mouth_y_mm - KNIFE_MOUNT_TOP_Y) > BUILT_GEOMETRY_TOLERANCE_MM:
        violations.append(
            f"tap mouth y {mouth_y_mm:.5f} mm is not the knife-mount top "
            f"{KNIFE_MOUNT_TOP_Y:.5f} mm"
        )
    if abs(engagement - HANGER_ENGAGEMENT_TARGET_MM) > BUILT_GEOMETRY_TOLERANCE_MM:
        violations.append(
            f"built engagement {engagement:.5f} mm is not the stack target "
            f"{HANGER_ENGAGEMENT_TARGET_MM:.5f} mm"
        )
    if not HANGER_ENGAGEMENT_MIN_MM <= engagement <= HANGER_ENGAGEMENT_MAX_MM:
        violations.append(
            f"built engagement {engagement:.5f} mm is outside the printed band "
            f"{HANGER_ENGAGEMENT_MIN_MM:.2f}..{HANGER_ENGAGEMENT_MAX_MM:.2f} mm"
        )
    if engagement > HANGER_TAP_FULL_THREAD_MIN_MM:
        violations.append(
            f"finished tip {engagement:.5f} mm deep passes the minimum complete "
            f"female thread {HANGER_TAP_FULL_THREAD_MIN_MM:.4f} mm"
        )
    if engagement >= HANGER_TAP_DRILL_SHOULDER_MIN_MM:
        violations.append(
            f"finished tip {engagement:.5f} mm deep reaches the tap-drill "
            f"shoulder {HANGER_TAP_DRILL_SHOULDER_MIN_MM:.4f} mm"
        )
    if engagement <= max(0.0, HANGER_COMPLETE_MALE_START_DEPTH_MM):
        violations.append(
            f"finished tip {engagement:.5f} mm deep leaves no complete male "
            "thread inside the receiver"
        )
    return violations


def _brep_circles(component: Any) -> list[tuple[float, float, float, float]]:
    """Every circular B-rep edge of one instance as (x, y, z, r) assembly mm."""
    scale = float(
        _early_bound(
            _early_bound(component, "IComponent2").Transform2, "IMathTransform"
        ).ArrayData[12]
    )
    circles = []
    for raw_body in tuple(_early_bound(component, "IComponent2").GetBodies2(0) or ()):
        for raw_edge in tuple(_early_bound(raw_body, "IBody2").GetEdges() or ()):
            raw_curve = _early_bound(raw_edge, "IEdge").GetCurve()
            if raw_curve is None:
                continue
            curve = _early_bound(raw_curve, "ICurve")
            if not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            x, y, z = _component_point_in_assembly(component, parameters[:3])
            circles.append(
                (x * 1000.0, y * 1000.0, z * 1000.0, parameters[6] * scale * 1000.0)
            )
    return circles


def _station_circle(
    view: Any,
    *,
    component_stem: str,
    radius_mm: float,
    station_z_mm: float,
    pick: Literal["highest", "lowest"],
    label: str,
) -> tuple[str, tuple[float, float, float, float]]:
    """The B-rep circle of ``radius_mm`` on the stem instance at the station."""
    matches = []
    for raw_drawing_component in tuple(
        _early_bound(view, "IView").GetVisibleDrawingComponents() or ()
    ):
        component = _early_bound(
            _early_bound(raw_drawing_component, "IDrawingComponent").Component,
            "IComponent2",
        )
        if _component_stem(component) != component_stem:
            continue
        name = str(component.Name2 or "").rsplit("/", 1)[-1]
        for circle in _brep_circles(component):
            on_station = abs(circle[2] - station_z_mm) <= BUILT_STATION_TOLERANCE_MM
            on_axis = abs(circle[0] - KNIFE[0]) <= BUILT_STATION_TOLERANCE_MM
            if not (on_station and on_axis):
                continue
            if abs(circle[3] - radius_mm) > BUILT_GEOMETRY_TOLERANCE_MM:
                continue
            matches.append((name, circle))
    if not matches:
        raise RuntimeError(
            f"{label}: no {component_stem!r} B-rep circle r={radius_mm:g} mm on "
            f"the x={KNIFE[0]:g}, z={station_z_mm:g} mm hanger axis"
        )
    matches.sort(key=lambda match: match[1][1], reverse=pick == "highest")
    return matches[0]


def _assert_built_hanger_engagement(section: Any, *, station_z_mm: float) -> None:
    """Measure E between the built mount and stud solids before dimensioning it."""
    mount_name, mouth = _station_circle(
        section,
        component_stem="knife-mount",
        radius_mm=STUD_TAP_DIA / 2.0,
        station_z_mm=station_z_mm,
        pick="highest",
        label="built MHA-037 tap mouth",
    )
    stud_name, tip = _station_circle(
        section,
        component_stem="knife-hanger-stud",
        radius_mm=THREAD_TIP_ROOT_RADIUS_MM,
        station_z_mm=station_z_mm,
        pick="lowest",
        label="built MHA-119 finished tip",
    )
    violations = hanger_engagement_violations(mouth[1], tip[1])
    facts = {
        "mount": mount_name,
        "stud": stud_name,
        "mouth_y_mm": mouth[1],
        "tip_y_mm": tip[1],
        "engagement_mm": mouth[1] - tip[1],
        "violations": tuple(violations),
    }
    _telemetry.event("drawing.built_hanger_engagement", **facts)
    summary = (
        f"built hanger engagement {stud_name} in {mount_name}: mouth "
        f"{mouth[1]:.5f}, tip {tip[1]:.5f}, E {mouth[1] - tip[1]:.5f} mm"
    )
    if violations:
        raise RuntimeError(f"{summary}: " + "; ".join(violations))
    _telemetry.success(summary)


def _exclude_fasteners_from_section(
    adapter: Any,
    section: Any,
    *,
    component_stems: tuple[str, ...],
    label: str,
) -> None:
    """Draw the hanger studs unsectioned in the cut (ASME Y14.3 bolt rule).

    A sectioned stud exposes only cut/intersection edges near its tip, so the
    detail derived from the section never offers the finished-tip rim as a
    circle (r7 census: 0 circles of 66 visible stud edges in Detail B while
    the B-rep carries the rim exactly at the expected y and r). Excluded, the
    stud shows whole inside the cut tap with its real edges.
    """
    section = _early_bound(section, "IView")
    components: dict[str, Any] = {}
    for raw_drawing_component in tuple(section.GetVisibleDrawingComponents() or ()):
        component = _early_bound(
            _early_bound(raw_drawing_component, "IDrawingComponent").Component,
            "IComponent2",
        )
        if _component_stem(component) in component_stems:
            components[str(component.Name2 or "").rsplit("/", 1)[-1]] = component
    expected = sum(BOM_QUANTITIES[stem] for stem in component_stems)
    if len(components) != expected:
        raise RuntimeError(
            f"{label}: section shows {sorted(components)!r}, expected "
            f"{expected} instances of {component_stems!r} to exclude"
        )
    dr_section = _early_bound(section.GetSection(), "IDrSection")
    if not dr_section.SetExcludedComponents(dispatch_array(list(components.values()))):
        raise RuntimeError(f"{label}: SetExcludedComponents returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: rebuild after section exclusion failed")
    excluded = sorted(
        str(_early_bound(raw, "IComponent2").Name2 or "").rsplit("/", 1)[-1]
        for raw in tuple(dr_section.GetExcludedComponents() or ())
    )
    _telemetry.event(
        "drawing.section_excluded_components",
        label=label,
        requested=tuple(sorted(components)),
        excluded=tuple(excluded),
    )
    if excluded != sorted(components):
        raise RuntimeError(
            f"{label}: section excludes {excluded!r}, expected {sorted(components)!r}"
        )
    _telemetry.success(f"{label}: drawn unsectioned {', '.join(excluded)}")


def _create_hanger_detail(adapter: Any, section: Any) -> Any:
    """Create a native enlarged detail around one real hanger/receiver interface."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    section = _early_bound(section, "IView")
    if not drawing.ActivateView(str(section.GetName2() or "")):
        raise RuntimeError("failed to activate hanger section for detail")
    draw.ClearSelection2(True)
    tip_y = KNIFE_MOUNT_TOP_Y - HANGER_ENGAGEMENT_TARGET_MM
    detail_point_mm = (
        KNIFE[0],
        (KNIFE_MOUNT_TOP_Y + tip_y) / 2.0,
        SUMMING_Z + HEX_Z_MID,
    )
    center = model_point_in_view(
        adapter,
        section,
        tuple(value / 1000.0 for value in detail_point_mm),
        label="hanger engagement detail center",
    )
    radius = 0.012 * HANGER_SECTION_SCALE[0] / HANGER_SECTION_SCALE[1]
    sketch = _early_bound(section.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create native hanger detail fence")
    detail = drawing.CreateDetailViewAt4(
        *HANGER_DETAIL_CENTER,
        0.0,
        0,
        *HANGER_DETAIL_SCALE,
        HANGER_DETAIL_LABEL,
        1,
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native hanger fit detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(HANGER_DETAIL_SCALE))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("hanger detail has invalid bounds")
    target = [
        position[index]
        + HANGER_DETAIL_CENTER[index]
        - (outline[index] + outline[index + 2]) / 2.0
        for index in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position hanger fit detail")
    draw.EditRebuild3()
    if tuple(float(value) for value in detail.ScaleRatio) != HANGER_DETAIL_SCALE:
        raise RuntimeError("hanger detail scale did not persist")

    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"hanger detail has {len(notes)} native labels")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    if not annotation.SetPosition2(*HANGER_DETAIL_LABEL_XY, 0.0):
        raise RuntimeError("failed to position hanger detail label")
    circles = tuple(_read_member(section, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"hanger section has {len(circles)} detail fences")
    detail_circle = _early_bound(circles[0], "IDetailCircle")
    parent_label = (center[0] + 0.014, center[1] + 0.010)
    detail_circle.SetLabelPosition(*parent_label)
    draw.EditRebuild3()
    if math.dist(
        tuple(float(value) for value in detail_circle.GetLabelPosition()),
        parent_label,
    ) > 1e-8:
        raise RuntimeError("hanger detail parent label position did not persist")
    return detail


def _add_hanger_engagement_dimension(adapter: Any, detail: Any) -> Any:
    """Add and verify the associative tap-mouth-to-finished-tip measurement."""
    tip_y = KNIFE_MOUNT_TOP_Y - HANGER_ENGAGEMENT_TARGET_MM
    station_z = SUMMING_Z + HEX_Z_MID
    mouth = _visible_component_circle(
        detail,
        component_stem="knife-mount",
        height_mm=KNIFE_MOUNT_TOP_Y,
        radius_mm=STUD_TAP_DIA / 2.0,
        target_z_mm=station_z,
        label="actual MHA-037 tap mouth",
    )
    tip = _visible_component_circle(
        detail,
        component_stem="knife-hanger-stud",
        height_mm=tip_y,
        radius_mm=THREAD_TIP_ROOT_RADIUS_MM,
        target_z_mm=station_z,
        label="actual MHA-119 finished tip",
    )
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    detail = _early_bound(detail, "IView")
    if not drawing.ActivateView(str(detail.GetName2() or "")):
        raise RuntimeError("failed to activate hanger fit detail")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, mouth), (True, tip)):
        selection_data = _early_bound(
            selection_manager.CreateSelectData(),
            "ISelectData",
        )
        selection_data.View = detail
        if not _early_bound(raw_entity, "IEntity").Select4(append, selection_data):
            raise RuntimeError("failed to select actual hanger fit edge")
    display = draw.AddVerticalDimension2(0.150, 0.082, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to add native hanger engagement measurement")
    # Both circles lie normal to the view (edge-on), so the dimension is
    # plane-to-plane: SolidWorks gives it no arc endpoints to re-anchor
    # (r8: GetArcEndCondition 0 on both). The value check below proves it
    # measures E.
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    arc_end_conditions = tuple(
        int(dimension.GetArcEndCondition(index)) for index in (1, 2)
    )
    _telemetry.event(
        "drawing.hanger_engagement_dimension",
        arc_end_conditions=arc_end_conditions,
        system_value_mm=float(dimension.SystemValue) * 1000.0,
    )
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - HANGER_ENGAGEMENT_TARGET_MM) > 1e-5:
        raise RuntimeError(
            "hanger engagement actual-edge measurement is "
            f"{measured_mm:g} mm, expected {HANGER_ENGAGEMENT_TARGET_MM:g} mm"
        )
    if int(
        display.SetPrecision3(HANGER_ENGAGEMENT_PRECISION, -1, -1, -1)
    ) < 0:
        raise RuntimeError("failed to set hanger engagement precision")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = HANGER_ENGAGEMENT_GENERAL_TOLERANCE_MM / 1000.0
    tolerance.Type = 11
    if not tolerance.SetValues(-band, band):
        raise RuntimeError("hanger engagement general tolerance was rejected")
    draw.EditRebuild3()
    if int(display.GetPrimaryPrecision2()) != HANGER_ENGAGEMENT_PRECISION:
        raise RuntimeError("hanger engagement precision did not persist")
    if (
        int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError("hanger engagement general tolerance did not persist")
    return display


def _place_hanger_fit_sheet(adapter: Any) -> list[str]:
    """Place the real assembly section/detail and its as-built fit instructions."""
    _add_note_block(
        adapter,
        f"{DRAWING_NUMBER} - {SHEET_NAMES[3]}\n"
        "MHA-119 / MHA-131 / MHA-037 MATCHED TO MHA-077",
        (0.018, 0.263),
        label="hanger fit sheet identity",
    )
    hanger_axis_mm = (KNIFE[0], KNIFE_MOUNT_TOP_Y, SUMMING_Z)
    parent = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *HANGER_PARENT_CENTER,
        scale=HANGER_PARENT_SCALE,
    )
    _set_exploded_state(adapter, parent, False, label="hanger fit parent")
    set_hidden_lines_removed(adapter, parent)
    visible_stems = frozenset(
        {"knife-mount", "knife-hanger-washer", "knife-hanger-stud"}
    )
    isolate_drawing_view_components(
        adapter,
        parent,
        visible_stems=visible_stems,
        label="hanger fit parent",
    )
    _place_view_by_model_point(
        adapter,
        parent,
        hanger_axis_mm,
        HANGER_PARENT_ANCHOR_XY,
        label="hanger fit parent placement",
    )
    parent = _early_bound(parent, "IView")
    cut_x = model_point_in_view(
        adapter,
        parent,
        tuple(value / 1000.0 for value in hanger_axis_mm),
        label="hanger-axis section station",
    )[0]
    # Span the parent's whole outline, as r9 did: a line short of the cut
    # bodies leaves a full section open ("olive, unhatched").
    outline = _view_outline(parent)
    section = create_section_view(
        adapter,
        parent,
        line_start=(cut_x, outline[1] - 0.002),
        line_end=(cut_x, outline[3] + 0.002),
        view_xy=HANGER_SECTION_CENTER,
        section_label="A",
        scale=HANGER_SECTION_SCALE,
        label="hanger-axis assembly section",
    )
    set_hidden_lines_removed(adapter, section)
    isolate_drawing_view_components(
        adapter,
        section,
        visible_stems=visible_stems,
        label="hanger-axis assembly section",
    )
    _place_view_by_model_point(
        adapter,
        section,
        hanger_axis_mm,
        HANGER_SECTION_ANCHOR_XY,
        label="hanger-axis section placement",
    )
    # ASME Y14.3: bolts and washers in a cut are drawn unsectioned.
    _exclude_fasteners_from_section(
        adapter,
        section,
        component_stems=("knife-hanger-stud", "knife-hanger-washer"),
        label="hanger-axis assembly section",
    )
    _assert_built_hanger_engagement(section, station_z_mm=SUMMING_Z + HEX_Z_MID)
    _record_cosmetic_threads(adapter, section, label="hanger-axis assembly section")
    detail = _create_hanger_detail(adapter, section)
    set_hidden_lines_removed(adapter, detail)
    _record_cosmetic_threads(adapter, detail, label="hanger fit detail")
    _add_hanger_engagement_dimension(adapter, detail)
    return _stack_note_field(
        adapter,
        (
            (
                "hanger engagement detail heading",
                f"DETAIL {HANGER_DETAIL_LABEL}: E IS ACTUAL TAP MOUTH TO FINISHED "
                "BOLT TIP",
            ),
            ("hanger fit construction", HANGER_FIT_CONSTRUCTION),
            ("hanger fit inspection", HANGER_FIT_INSPECTION),
        ),
        NOTE_FIELD_RIGHT,
        label="sheet 4 note field",
    )


def _record_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> None:
    """Import the view's cosmetic threads and record what SolidWorks shows.

    Investigation for Main (S4-5): the MHA-037 tap is modelled at tap-drill
    size with a cosmetic thread, so the modelled MHA-119 crests overlap the
    hatched wall. The counts say whether the internal thread can be drawn.
    """
    seeds, instances = import_cosmetic_threads(adapter, view)
    _telemetry.event(
        "drawing.cosmetic_threads",
        label=label,
        seed_count=seeds,
        instance_count=instances,
    )
    _telemetry.info(
        f"{label}: {seeds} cosmetic-thread seed(s), {instances} instance(s)"
    )


def _set_exploded_state(
    adapter: Any,
    view: Any,
    show: bool,
    *,
    label: str,
) -> None:
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"{label}: view must reference {SOURCE_CONFIGURATION!r}"
        )
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(
            f"{label}: exploded-state readback is {actual}, expected {show}"
        )
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_persisted_explode(source_model: Any) -> None:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(
        source_model.ConfigurationManager,
        "IConfigurationManager",
    )
    configuration = _early_bound(
        manager.ActiveConfiguration,
        "IConfiguration",
    )
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"summing source must open in {SOURCE_CONFIGURATION!r}"
        )
    names = tuple(
        assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
    )
    if names != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"summing source exploded views {names!r} != "
            f"{(EXPLODED_VIEW_NAME,)!r}"
        )

    groups = {stem: 0 for stem in BOM_COMPONENTS}
    components = tuple(assembly.GetComponents(True) or ())
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        stem = _component_stem(component)
        if stem not in groups:
            raise RuntimeError(
                f"summing source contains unexpected component "
                f"{component.Name2!r}: {stem!r}"
            )
        groups[stem] += 1
        total = _early_bound(
            component.GetTotalTransform(True),
            "IMathTransform",
        )
        base = _early_bound(
            component.GetTotalTransform(False),
            "IMathTransform",
        )
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(
                total.ArrayData,
                base.ArrayData,
                strict=True,
            )
        ):
            raise RuntimeError(
                f"summing source must open collapsed: "
                f"{component.Name2!r} is displaced"
            )
    if groups != BOM_QUANTITIES:
        raise RuntimeError(
            f"summing source component counts {groups!r} != "
            f"{BOM_QUANTITIES!r}"
        )


def _normalized_bom_identity(text: str) -> str:
    normalized = text.strip().casefold()
    return BOM_NORMALIZED_ALIASES.get(normalized, normalized)


def bom_row_fit(requested: float, actual: float) -> Literal["short", "exact", "grown"]:
    """Classify a persisted BOM row height against the requested height."""
    if actual < requested - BOM_HEIGHT_TOLERANCE:
        return "short"
    if actual <= requested + BOM_HEIGHT_TOLERANCE:
        return "exact"
    return "grown"


def bom_extent_violations(
    anchor: tuple[float, float],
    width: float,
    height: float,
) -> list[str]:
    """Name every way a top-left-anchored BOM box leaves its paper budget."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    left, top = anchor
    right = left + width
    bottom = top - height
    clearance = BOM_SHEET_CLEARANCE
    violations = []
    if left < clearance:
        violations.append(f"left edge {left * 1000:.3f} mm is off the sheet")
    if right > template.width_m - clearance:
        violations.append(
            f"right edge {right * 1000:.3f} mm passes "
            f"{(template.width_m - clearance) * 1000:.3f} mm"
        )
    if top > template.height_m - clearance:
        violations.append(
            f"top edge {top * 1000:.3f} mm passes "
            f"{(template.height_m - clearance) * 1000:.3f} mm"
        )
    title_block_floor = template.title_block_top_m + clearance
    over_title_block = right > template.title_block_left_m
    if over_title_block and bottom < title_block_floor:
        violations.append(
            f"bottom edge {bottom * 1000:.3f} mm enters the title block "
            f"(floor {title_block_floor * 1000:.3f} mm)"
        )
    if bottom < clearance:
        violations.append(f"bottom edge {bottom * 1000:.3f} mm is off the sheet")
    return violations


def _validate_summing_bom(
    adapter: Any,
    table: Any,
) -> tuple[tuple[str, str], ...]:
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"summing BOM is {rows}x{columns}; expected "
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

    def column_named(
        predicate: Callable[[str], bool],
        label: str,
    ) -> int:
        matches = [
            index for index, cell in enumerate(header) if predicate(cell)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"summing BOM has no unique {label} column: {header!r}"
            )
        return matches[0]

    item_column = column_named(
        lambda cell: cell.startswith("ITEM NO"),
        "ITEM NO.",
    )
    part_column = column_named(
        lambda cell: cell == "PART NUMBER",
        "PART NUMBER",
    )
    description_column = column_named(
        lambda cell: cell == "DESCRIPTION",
        "DESCRIPTION",
    )
    quantity_column = column_named(
        lambda cell: cell.startswith("QTY"),
        "QTY.",
    )
    for column, width in (
        (item_column, BOM_COLUMN_WIDTHS["item"]),
        (part_column, BOM_COLUMN_WIDTHS["part"]),
        (description_column, BOM_COLUMN_WIDTHS["description"]),
        (quantity_column, BOM_COLUMN_WIDTHS["quantity"]),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(
                f"summing BOM column {column} width did not persist: "
                f"requested {width * 1000:.3f} mm, "
                f"actual {actual_width * 1000:.3f} mm"
            )

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        stem = _normalized_bom_identity(row[part_column])
        if stem in actual:
            raise RuntimeError(
                f"summing BOM repeats component family {stem!r}"
            )
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"summing BOM identities {sorted(actual)!r} != "
            f"{sorted(BOM_COMPONENTS)!r}"
        )
    expected_items = {
        str(item) for item in range(1, len(BOM_COMPONENTS) + 1)
    }
    actual_items = {values[1] for values in actual.values()}
    if actual_items != expected_items:
        raise RuntimeError(
            f"summing BOM item numbers {sorted(actual_items)!r} != "
            f"{sorted(expected_items)!r}"
        )

    for stem, (row_index, _item, description, quantity) in actual.items():
        expected_part_number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != expected_part_number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"summing BOM part-number cell for {stem!r} "
                    "is not editable"
                )
            table.SetText2(
                row_index,
                part_column,
                False,
                expected_part_number,
            )
            applied = str(
                table.DisplayedText2(
                    row_index,
                    part_column,
                    False,
                )
                or ""
            ).strip()
            if applied != expected_part_number:
                raise RuntimeError(
                    f"summing BOM part number for {stem!r} did not persist"
                )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(
                f"summing BOM description mismatch for {stem!r}"
            )
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"summing BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )
    header_count = int(table.GetHeaderCount())
    # Rows are sized after the part-number rewrite, so the long component
    # stems SolidWorks displays first cannot leave a row wrapped-tall.
    # SetRowHeight returns the height SolidWorks applied: never less than the
    # minimum that fits the row's text, which the header can exceed. The
    # contract is enforced on the persisted height after the rebuild below.
    setter_heights = tuple(
        float(table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)) for row in range(rows)
    )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("summing BOM rebuild failed")
    for stem, (row_index, _item, _description, _quantity) in actual.items():
        applied = str(
            table.DisplayedText(row_index, part_column) or ""
        ).strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"summing BOM part number for {stem!r} "
                f"reverted to {applied!r}"
            )
    _check_bom_extents(
        adapter,
        table,
        contents=contents,
        header_count=header_count,
        setter_heights=setter_heights,
    )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _bom_row_text_heights(
    adapter: Any,
    table: Any,
    row: int,
    columns: int,
) -> tuple[float | None, ...]:
    """Character height per cell, for telemetry only (None when unreadable)."""
    return tuple(
        adapter._attempt(
            lambda column=column: float(
                _early_bound(
                    table.GetCellTextFormat(row, column),
                    "ITextFormat",
                ).CharHeight
            )
        )
        for column in range(columns)
    )


def _check_bom_extents(
    adapter: Any,
    table: Any,
    *,
    contents: tuple[tuple[str, ...], ...],
    header_count: int,
    setter_heights: tuple[float, ...],
) -> None:
    """Hold the persisted BOM rows to their floor and the table to the sheet.

    Row heights are read back after the rebuild -- the layout audit boxes the
    table from the same ``GetRowHeight`` values -- so nothing downstream rests
    on the requested 6 mm.
    """
    columns = int(table.ColumnCount)
    heights: list[float] = []
    for row, setter_height in enumerate(setter_heights):
        row_kind = "header" if row < header_count else "data"
        height = float(table.GetRowHeight(row))
        heights.append(height)
        fit = bom_row_fit(BOM_ROW_HEIGHT, height)
        gap = adapter._attempt(lambda row=row: float(table.GetRowVerticalGap(row)))
        text_heights = _bom_row_text_heights(adapter, table, row, columns)
        facts = {
            "row": row,
            "row_kind": row_kind,
            "fit": fit,
            "requested_mm": BOM_ROW_HEIGHT * 1000.0,
            "setter_mm": setter_height * 1000.0,
            "actual_mm": height * 1000.0,
            "vertical_gap_mm": None if gap is None else gap * 1000.0,
            "char_heights_mm": tuple(
                None if value is None else value * 1000.0 for value in text_heights
            ),
            "cells": contents[row],
        }
        _telemetry.event("drawing.bom_row_height", **facts)
        summary = (
            f"summing BOM {row_kind} row {row}: requested "
            f"{BOM_ROW_HEIGHT * 1000:.3f} mm, setter returned "
            f"{setter_height * 1000:.3f} mm, persisted {height * 1000:.3f} mm "
            f"(vertical gap {facts['vertical_gap_mm']}, "
            f"char heights {facts['char_heights_mm']}, cells {contents[row]!r})"
        )
        if fit == "short":
            raise RuntimeError(f"{summary} is below the requested height")
        if fit == "exact":
            _telemetry.debug(summary)
            continue
        if row_kind == "header":
            _telemetry.info(f"{summary} -- native header minimum")
            continue
        _telemetry.warn(f"{summary} -- data row grew; check for wrapped text")

    width = sum(float(table.GetColumnWidth(column)) for column in range(columns))
    height = sum(heights)
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    anchor = (position[0], position[1])
    violations = bom_extent_violations(anchor, width, height)
    _telemetry.event(
        "drawing.bom_extents",
        anchor_mm=tuple(value * 1000.0 for value in anchor),
        width_mm=width * 1000.0,
        height_mm=height * 1000.0,
        row_heights_mm=tuple(value * 1000.0 for value in heights),
        violations=tuple(violations),
    )
    if violations:
        raise RuntimeError(
            f"summing BOM at {anchor!r} ({width * 1000:.3f} x "
            f"{height * 1000:.3f} mm): " + "; ".join(violations)
        )
    _telemetry.info(
        f"summing BOM extents {width * 1000:.3f} x {height * 1000:.3f} mm "
        f"from top-left {anchor!r}; rows "
        f"{tuple(round(value * 1000, 3) for value in heights)} mm"
    )


def _create_package_sheets(adapter: Any) -> None:
    _drawing, _sheet = new_project_drawing(
        adapter,
        layout=SPEC.layout,
        scale=ASSEMBLED_SCALE,
    )
    create_blank_drawing_sheets(
        adapter,
        SHEET_NAMES,
        label="summing assembly package",
    )
    for sheet_number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(
            _early_bound(
                adapter.currentModel,
                "IDrawingDoc",
            ).GetCurrentSheet(),
            "ISheet",
        )
        sheet_scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(
            float(sheet_scale[0]),
            float(sheet_scale[1]),
            False,
            False,
        ):
            raise RuntimeError(
                f"failed to set native summing sheet scale: {sheet_name}"
            )
        _add_note_block(
            adapter,
            f"SHEET {sheet_number} OF {len(SHEET_NAMES)}",
            (0.018, 0.025),
            label="package sheet number",
        )


def _place_package(adapter: Any) -> None:
    _create_package_sheets(adapter)

    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *ASSEMBLED_FRONT_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    right = place_view(
        adapter,
        str(SOURCE),
        "*Right",
        *ASSEMBLED_RIGHT_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    assembled_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLED_ISO_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    for label, view in (
        ("assembled front", front),
        ("assembled right", right),
        ("assembled isometric", assembled_iso),
    ):
        _set_exploded_state(adapter, view, False, label=label)
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, right)
    set_high_quality_shaded_with_edges(
        adapter,
        assembled_iso,
        label="summing assembled isometric",
    )
    _add_note_block(
        adapter,
        "ASSEMBLED NEUTRAL REFERENCE - LEVER ROCK REMAINS FREE",
        (0.112, 0.263),
        label="assembled-view heading",
    )
    _add_note_block(
        adapter,
        "FRONT 1:4",
        (0.040, 0.080),
        label="front-view caption",
    )
    _add_note_block(
        adapter,
        "RIGHT 1:4",
        (0.160, 0.080),
        label="right-view caption",
    )
    _add_note_block(
        adapter,
        "ASSEMBLED ISOMETRIC 1:4",
        (0.290, 0.080),
        label="assembled-isometric caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *EXPLODED_ISO_CENTER,
        scale=EXPLODED_SCALE,
    )
    _set_exploded_state(
        adapter,
        exploded,
        True,
        label="exploded isometric",
    )
    set_high_quality_shaded_with_edges(
        adapter,
        exploded,
        label="summing exploded isometric",
    )
    # Centre the balloon ring (outline + margin + one balloon) in its region,
    # so no balloon lands on the heading, the caption, the BOM or the border.
    exploded_outline = _view_outline(exploded)
    ring_shift, ring_overflows = ring_fit_shift(
        exploded_outline,
        EXPLODED_RING_REGION,
        grow=EXPLODED_BALLOON_MARGIN + BALLOON_DIAMETER,
    )
    _telemetry.event(
        "drawing.exploded_ring_fit",
        outline_mm=tuple(value * 1000.0 for value in exploded_outline),
        shift_mm=tuple(value * 1000.0 for value in ring_shift),
        overflows=tuple(ring_overflows),
    )
    if ring_overflows:
        _telemetry.warn(
            "exploded balloon ring estimate overflows its region ("
            + "; ".join(ring_overflows)
            + "); the layout audit decides"
        )
    _shift_view(adapter, exploded, ring_shift, label="exploded isometric ring fit")
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="summing",
    )
    balloon_items = _validate_summing_bom(adapter, table)
    add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        label="summing exploded-view BOM coverage",
        margin=EXPLODED_BALLOON_MARGIN,
    )
    _add_note_block(
        adapter,
        "EXPLODED ISOMETRIC 1:4",
        (0.018, 0.263),
        label="exploded-view heading",
    )
    _add_note_block(
        adapter,
        "SEE SHEET 3 FOR ASSEMBLY, SHEET 4 FOR HANGER FIT, SHEET 5 FOR CHECKS",
        (0.018, 0.037),
        label="exploded-view caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[2])
    instruction_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *INSTRUCTION_ISO_CENTER,
        scale=INSTRUCTION_SCALE,
    )
    _set_exploded_state(
        adapter,
        instruction_iso,
        False,
        label="instruction isometric",
    )
    set_high_quality_shaded_with_edges(
        adapter,
        instruction_iso,
        label="summing instruction isometric",
    )
    field_findings = _stack_note_field(
        adapter,
        (("assembly sequence", ASSEMBLY_STEPS),),
        NOTE_FIELD_LEFT,
        label="sheet 3 note field",
    )
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:6",
        (0.315, 0.145),
        label="instruction-isometric caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[3])
    field_findings += _place_hanger_fit_sheet(adapter)

    _activate_sheet(adapter, SHEET_NAMES[4])
    field_findings += _stack_note_field(
        adapter,
        (("assembly functional checks", ASSEMBLY_CHECKS),),
        NOTE_FIELD_LEFT,
        label="sheet 5 left note field",
    )
    field_findings += _stack_note_field(
        adapter,
        (
            ("neutral setup", SETUP_NOTES),
            ("external interfaces", INTERFACE_NOTES),
        ),
        NOTE_FIELD_RIGHT,
        label="sheet 5 right note field",
    )
    _check_package_layout(adapter, field_findings)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open summing drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError(
            "summing source assembly is already dirty; "
            "refusing to discard user changes"
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
        raise RuntimeError("summing source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        _validate_persisted_explode(source_model)
        _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Summing Assembly Drawing Package",
            scale=ASSEMBLED_SCALE,
            expected_sheet_names=SHEET_NAMES,
            sheet_layouts=SHEET_LAYOUTS,
            sheet_scales=SHEET_SCALES,
        )
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:
                        drawing_title = str(active_model.GetTitle() or "")
                        if not drawing_title:
                            cleanup_errors.append(
                                "generated summing drawing has no title for close"
                            )
                        else:
                            adapter.swApp.CloseDoc(drawing_title)
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(
                    f"failed to close generated summing drawing: {exc}"
                )

        try:
            adapter.swApp.CloseDoc(source_title)
            if (
                adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve()))
                is not None
            ):
                cleanup_errors.append(
                    f"summing source {source_title!r} remained open after discard"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to close summing source {source_title!r}: {exc}"
            )

        try:
            after_fingerprint = _source_fingerprint(SOURCE)
            if after_fingerprint != fingerprint:
                cleanup_errors.append(
                    "summing drawing generation changed the released source "
                    "assembly (size, mtime_ns, SHA256): "
                    f"{fingerprint!r} -> {after_fingerprint!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to verify summing source fingerprint: {exc}"
            )

        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(
                    f"summing drawing cleanup after failure: {message}"
                )
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("summing drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
