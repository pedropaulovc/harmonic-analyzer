from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from _drawing_contract import (
    drawing_fleet_specification_violations,
    drawing_specification_violations,
    model_toleranced_dimensions,
)


def _rules(source: str) -> list[str]:
    return [item.rule for item in drawing_specification_violations(source)]


def _tolerance_violations(source: str) -> list[object]:
    """Every finding except the separate places rule, which any ``{x:.2f}`` trips."""
    return [
        item
        for item in drawing_specification_violations(source)
        if item.rule != "drawing-owned-precision"
    ]


@pytest.mark.parametrize(
    "value",
    (
        '"+0.00/-0.02"',
        '"+0.10/0"',
        '"+0.10/+0.00"',
        '"-0.02/-0.04"',
        '"+0.04/+0.02"',
        '"-0.02/+0.04"',
        '"+ 0.04 / + 0.02"',
        '"0/-0.10"',
        '"+0.00/-0.10"',
        '"±0.05"',
        '"Ra 1.6"',
        '"R0.10 MAX"',
        '"3.00 MIN"',
        '"6.375 MAX / 6.360 MIN"',
        'f"{upper:.3f} MAX / {lower:.3f} MIN"',
        'f"{upper:+.2f}/{lower:+.2f}"',
        'f"{upper:>+.3f} / {lower:*>+8.3f}"',
        'f"{upper:-.2f}/{lower:-.2f}"',
        'f"Ra {local_grade}"',
    ),
)
def test_detector_finds_frozen_manufacturing_string_fragments(value: str) -> None:
    assert "drawing-spec-string" in _rules(f"CALLOUT = {value}\n")


def test_detector_preserves_f_string_signs_in_violation_evidence() -> None:
    violations = _tolerance_violations('CALLOUT = f"{upper:+.2f}/{lower:+.2f}"\n')
    assert len(violations) == 1
    assert violations[0].rule == "drawing-spec-string"
    assert violations[0].evidence == "'+{...}/+{...}'"


@pytest.mark.parametrize(
    "value",
    (
        'f"{numerator:.2f}/{denominator:.2f}"',
        'f"{month:02d}/{day:02d}"',
        'f"{value:+.2f}"',
        'f"{width:+.2f} BY {height:+.2f}"',
    ),
)
def test_detector_does_not_treat_unbanded_f_strings_as_tolerances(value: str) -> None:
    assert _tolerance_violations(f"LABEL = {value}\n") == []


def test_detector_finds_fit_renderers_through_import_aliases() -> None:
    source = """
from _fit_limits import fit_limits as limits
import _fit_limits as bands

FIRST = limits(6.0, (-0.1, 0.1))
SECOND = bands.band_text((-0.1, 0.1))
"""
    assert _rules(source) == [
        "drawing-tolerance-renderer",
        "drawing-tolerance-renderer",
    ]


def test_detector_rejects_literal_and_local_surface_finish_grades() -> None:
    source = """
from _drawing_common import add_surface_finish as finish

LOCAL_GRADE = "1.6"
finish(adapter, view, symbol_xy=(0.1, 0.2), roughness_ra="0.8", label="first")
finish(adapter, view, symbol_xy=(0.2, 0.2), roughness_ra=LOCAL_GRADE, label="second")
"""
    assert _rules(source).count("drawing-roughness-provenance") == 2


def test_detector_allows_catalog_surface_finish_grades_and_local_aliases() -> None:
    source = """
from _drawing_common import add_surface_finish
from _surface_finish import MACHINED as CATALOG_GRADE
import _surface_finish as finish_catalog

LOCAL_ALIAS = CATALOG_GRADE
PLACEMENT = (0.125, 0.240, 2.0)
PROPERTY = '$PRPSHEET:"SurfaceFinish"'
PROSE = "REPORT MAX-MIN RADIAL WALL THICKNESS"
TEXT = f"Ra {CATALOG_GRADE}"

add_surface_finish(
    adapter,
    view,
    symbol_xy=PLACEMENT[:2],
    roughness_ra=LOCAL_ALIAS,
    label="catalog direct",
)
add_surface_finish(
    adapter,
    view,
    symbol_xy=PLACEMENT[:2],
    roughness_ra=finish_catalog.GROUND,
    label="catalog module",
)
"""
    assert drawing_specification_violations(source) == ()


def test_detector_requires_surface_finish_controls_from_a_part_spec() -> None:
    local_control = """
from _drawing_common import add_surface_finish
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

add_surface_finish(
    adapter,
    view,
    symbol_xy=(0.1, 0.2),
    control=SurfaceFinishControl(
        "strap_bore", MACHINED_UM, CylinderFace(30.8)
    ),
    label="local control",
)
"""
    assert _rules(local_control) == ["drawing-surface-finish-provenance"]

    imported_controls = """
from _drawing_common import add_surface_finish
from _surface_finish import surface_finish_by_key
from connecting_rod_spec import SURFACE_FINISHES
import connecting_rod_spec as rod_spec
import _surface_finish as finish_catalog

CONTROL = surface_finish_by_key(SURFACE_FINISHES, "strap_bore")
add_surface_finish(
    adapter, view, symbol_xy=(0.1, 0.2), control=CONTROL, label="direct spec"
)
add_surface_finish(
    adapter,
    view,
    symbol_xy=(0.2, 0.2),
    control=finish_catalog.surface_finish_by_key(
        rod_spec.SURFACE_FINISHES, "strap_bore"
    ),
    label="module spec",
)
"""
    assert drawing_specification_violations(imported_controls) == ()


def test_detector_finds_drawing_owned_feature_control_frame_tolerances() -> None:
    source = """
from _drawing_common import add_feature_control_frame as fcf
import _drawing_common as drawing

LOCAL_TOLERANCE = "0.10"
fcf(adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance="0.05", label="literal")
drawing.add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="perpendicularity",
    tolerance=LOCAL_TOLERANCE, label="local alias")
"""
    violations = drawing_specification_violations(source)
    assert [item.rule for item in violations] == [
        "drawing-gdt-provenance",
        "drawing-gdt-provenance",
    ]
    assert [item.evidence for item in violations] == [
        "tolerance='0.05' is not part-spec-sourced",
        "tolerance=LOCAL_TOLERANCE is not part-spec-sourced",
    ]


def test_detector_allows_feature_control_frame_values_from_part_contracts() -> None:
    source = """
from _drawing_common import add_feature_control_frame
from pinion_lever_spec import GEOMETRIC_CONTROLS, HUB_RUNOUT_TOLERANCE
import pinion_lever_spec as lever_spec

FIRST_CONTROL = GEOMETRIC_CONTROLS[0]
SELECTED_CONTROL = next(
    control for control in GEOMETRIC_CONTROLS if control.key == "grip-flatness"
)
add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance=HUB_RUNOUT_TOLERANCE, label="direct")
add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance=lever_spec.FLAT_END_TOLERANCE, label="module")
add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance=FIRST_CONTROL.tolerance, label="indexed control")
add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance=SELECTED_CONTROL.tolerance, label="selected control")
"""
    assert drawing_specification_violations(source) == ()


def test_detector_does_not_let_spec_text_mask_a_local_fcf_number() -> None:
    source = """
from _drawing_common import add_feature_control_frame
from pinion_lever_spec import LABEL

add_feature_control_frame(
    adapter, view, frame_xy=(0.1, 0.2), characteristic="flatness",
    tolerance=f"0.0{LABEL}", label="mixed provenance")
"""
    assert _rules(source) == ["drawing-gdt-provenance"]


def test_detector_finds_bare_within_limits_only_in_attached_notes() -> None:
    source = """
from _drawing_common import add_attached_note as attached
import _drawing_common as drawing
from pinion_lever_spec import LABEL

NOTE = "TIP FACE FLAT WITHIN 0.05\\nPERPENDICULAR TO AXIS WITHIN 0.10"
LOCAL_LIMIT = 0.20
attached(adapter, view, text=NOTE, note_xy=(0.1, 0.2), label="literal")
drawing.add_attached_note(
    adapter, view, text=f"PROFILE WITHIN {LOCAL_LIMIT:.2f}",
    note_xy=(0.1, 0.2), label="local f-string")
attached(
    adapter, view, text=f"FLAT WITHIN 0.30 {LABEL}",
    note_xy=(0.1, 0.2), label="unrelated spec interpolation")
attached(
    adapter, view, text="INSPECT WITHIN ",
    note_xy=(0.1, 0.2), label="text-only fragment")

PROSE = "complete within 0.30 seconds"
unrelated(text="WITHIN 0.40")
"""
    violations = drawing_specification_violations(source)
    assert [item.rule for item in violations] == [
        "drawing-gdt-note",
        "drawing-gdt-note",
        "drawing-gdt-note",
        "drawing-gdt-note",
    ]
    assert [item.evidence for item in violations] == [
        "'WITHIN 0.05'",
        "'WITHIN 0.10'",
        "'WITHIN {...}'",
        "'WITHIN 0.30'",
    ]


def test_detector_allows_attached_note_limits_from_part_contracts() -> None:
    source = """
from _drawing_common import add_attached_note
from pinion_lever_spec import (
    GEOMETRIC_TOLERANCES_MM,
    GRIP_FLATNESS,
    GRIP_REQUIREMENT_NOTE,
)
import pinion_lever_spec as lever_spec

LOCAL_ALIAS = GRIP_FLATNESS
add_attached_note(
    adapter, view, text=f"TIP FACE FLAT WITHIN {LOCAL_ALIAS:.2f}",
    note_xy=(0.1, 0.2), label="direct value")
add_attached_note(
    adapter, view, text=GRIP_REQUIREMENT_NOTE,
    note_xy=(0.1, 0.2), label="direct note")
add_attached_note(
    adapter, view, text=lever_spec.GRIP_REQUIREMENT_NOTE,
    note_xy=(0.1, 0.2), label="module note")
add_attached_note(
    adapter,
    view,
    text=(
        "TIP FACE FLAT WITHIN "
        f"{GEOMETRIC_TOLERANCES_MM['grip tip face flatness']}\\n"
        "PERPENDICULAR TO GRIP AXIS\\n"
        f"WITHIN {GEOMETRIC_TOLERANCES_MM['grip tip face perpendicularity']}"
    ),
    note_xy=(0.1, 0.2),
    label="split text and spec values",
)
"""
    assert drawing_specification_violations(source) == ()


def test_detector_finds_direct_drawing_com_tolerance_mutation() -> None:
    source = """
model_dimension.SetToleranceType(2)
tolerance = _early_bound(model_dimension.Tolerance, "IDimensionTolerance")
tolerance.Type = 2
tolerance.SetValues(-0.00005, 0.00005)
set_dimension_symmetric_angular_tolerance(adapter, "Chamfer", "Angle", 0.5)
series.SetValues(1.0, 2.0)
"""
    assert _rules(source) == [
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
        "drawing-tolerance-mutation",
    ]


def test_model_tolerance_analysis_includes_symmetric_angular_setter(
    tmp_path: Path,
) -> None:
    source = tmp_path / "build_sample.py"
    source.write_text(
        "set_dimension_symmetric_angular_tolerance("
        'adapter, "Chamfer", "Angle", ANGULAR_TOLERANCE_MM)\n',
        encoding="utf-8",
    )
    module = SimpleNamespace(__file__=source)
    assert model_toleranced_dimensions(module) == {
        ("Chamfer", "Angle"): "ANGULAR_TOLERANCE_MM"
    }


def test_detector_ignores_docstrings_property_links_placement_and_prose() -> None:
    source = '''
"""Examples such as Ra 1.6 and +0.00/-0.02 are documentation only."""

VIEW_XY = (0.130, 0.170)
SCALE = (2, 1)
PROPERTY = '$PRPSHEET:"ToleranceCallout"'
NOTE = "KEEP MAX-MIN RESULTS WITH THE INSPECTION REPORT"
RATIO = "12/24"
THREAD = "1/4-20 UNC"
'''
    assert drawing_specification_violations(source) == ()


# Render-time places that predate the f-string and hole-callout detections.
# Each entry is a known violation with an owner; the fleet test fails on any
# NEW finding and on any entry that no longer fires, so this list only shrinks.
# Keyed by (script, evidence), not line, so an unrelated edit cannot shift it.
_HOLE_CALLOUT = (
    "set_hole_callout_precision(...) rewrites display precision at render time"
)
KNOWN_PRECISION_DEBT = Counter(
    {
        # harmonic-base package: stamped-ID height typed into the serial note.
        (
            "draw_harmonic_base.py",
            "f-string {SERIAL_HEIGHT_MM:.1f} types drawing-chosen decimal places "
            "into sheet text",
        ): 1,
        # harmonic-base package: tapped-hole depth places set on the callout.
        ("draw_harmonic_base.py", _HOLE_CALLOUT): 1,
        # top-frame package: tapped-hole depth places set on two callouts.
        ("draw_top_frame.py", _HOLE_CALLOUT): 2,
    }
)


def test_drawing_fleet_owns_placement_not_manufacturing_values() -> None:
    scripts = Path(__file__).parent.glob("draw_*.py")
    violations = drawing_fleet_specification_violations(scripts)
    found = Counter((Path(item.filename).name, item.evidence) for item in violations)
    new = [
        item
        for item in violations
        if found[(Path(item.filename).name, item.evidence)]
        > KNOWN_PRECISION_DEBT[(Path(item.filename).name, item.evidence)]
    ]
    assert not new, "drawing-owned manufacturing specifications:\n" + "\n".join(
        str(item) for item in new
    )
    retired = +(KNOWN_PRECISION_DEBT - found)
    assert not retired, (
        "fixed precision debt is still listed; delete it from KNOWN_PRECISION_DEBT: "
        f"{sorted(retired)}"
    )


def test_detector_flags_render_time_precision_but_not_tolerance_places() -> None:
    source = """
from _drawing_common import set_dimension_precision

set_dimension_precision(adapter, dims, {"HubDia": 1})
display.SetPrecision3(1, -1, -1, -1)
display.SetPrecision3(-1, -1, 3, -1)
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule) for item in violations] == [
        (4, "drawing-owned-precision"),
        (5, "drawing-owned-precision"),
    ]


def test_precision_exception_is_the_spec_reference_precision_only() -> None:
    """Only DRAWING_REFERENCE_PRECISION (direct, aliased, module attribute, or an
    item of it) may reach SetPrecision3; any other *_spec value is spec data,
    not a places statement, and still writes a drawing-owned precision."""
    source = """
import top_frame_spec
from harmonic_base_spec import DRAWING_REFERENCE_PRECISION as REF
from tube_frame_spec import DRAWING_REFERENCE_PRECISION, SHANK_DIA

display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
display.SetPrecision3(DRAWING_REFERENCE_PRECISION["Height"], -1, -1, -1)
display.SetPrecision3(REF, -1, -1, -1)
display.SetPrecision3(top_frame_spec.DRAWING_REFERENCE_PRECISION["Web"], -1, -1, -1)
display.SetPrecision3(SHANK_DIA, -1, -1, -1)
display.SetPrecision3(top_frame_spec.WEB_WIDTH, -1, -1, -1)
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule) for item in violations] == [
        (10, "drawing-owned-precision"),
        (11, "drawing-owned-precision"),
    ]


def test_precision_rule_is_scoped_to_migrated_drawings(tmp_path: Path) -> None:
    legacy = tmp_path / "draw_legacy.py"
    migrated = tmp_path / "draw_harmonic_base.py"
    body = "display.SetPrecision3(1, -1, -1, -1)\n"
    legacy.write_text(body, encoding="utf-8")
    migrated.write_text(body, encoding="utf-8")
    violations = drawing_fleet_specification_violations([legacy, migrated])
    assert [Path(item.filename).name for item in violations] == [
        "draw_harmonic_base.py"
    ]


def test_detector_flags_precision_typed_into_sheet_text() -> None:
    """Policy rule 2's own example, ``f"{DEPTH:.1f} DEEP"``, in every sheet sink."""
    source = """
from _drawing_common import add_attached_note
from pinion_arbor_spec import BACK_CAP_R, DEPTH

CALLOUTS = {"BackCapSagDim": f"SR{BACK_CAP_R:.1f} BACK CROWN"}
add_attached_note(adapter, view, text=f"{DEPTH:.1f} DEEP", label="depth")
STEPS = "; ".join(f"{index}. SHIM {gap:.2f}" for index, gap in enumerate(gaps))
PERCENT = f"{fill:.0%} FULL"
GENERAL = f"{value:.3g}"
PLACES = f"{value:.{places}f}"
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule) for item in violations] == [
        (5, "drawing-owned-precision"),
        (6, "drawing-owned-precision"),
        (7, "drawing-owned-precision"),
        (8, "drawing-owned-precision"),
        (9, "drawing-owned-precision"),
        (10, "drawing-owned-precision"),
    ]
    assert violations[0].evidence == (
        "f-string {BACK_CAP_R:.1f} types drawing-chosen decimal places into sheet text"
    )
    assert violations[-1].evidence == (
        "f-string {value:.{...}f} types drawing-chosen decimal places into sheet text"
    )


def test_detector_ignores_diagnostic_and_unplaced_f_strings() -> None:
    source = """
import _telemetry
from _common import check
from arbor_spec import DRAWING_REFERENCE_PRECISION

raise RuntimeError(f"measured {measured:.3f} mm")
assert abs(error) < 1e-6, f"off by {error:.6f}"
_telemetry.debug(f"pick at {x:.4f}, {y:.4f}")
check(f"volume {volume:.2f}", ok)
seen = "; ".join(f"dev={item:.3g}" for item in nearest)
raise RuntimeError(f"no line; nearest: {seen}")
WIDTH = f"{name:>8}"
COUNT = f"{count:d} HOLES"
GROUPED = f"{total:,}"
REPR = f"{label!r}"
REFERENCE = f"({height:.{DRAWING_REFERENCE_PRECISION}f})"


def _layout_problems(box):
    problems = []
    if box[0] < 0.0:
        problems.append(f"left {box[0] * 1000:.2f} mm is off the sheet")
    return problems


def _format_box(box):
    return f"[{box[0] * 1000.0:.1f},{box[1] * 1000.0:.1f}]mm"


def _pick(adapter, view, radial_mm):
    where = f"at radius {radial_mm:.4f} mm"
    where += f", station {radial_mm:.4f} mm"
    point = model_point_in_view(adapter, view, (0, 0, 0), label=f"r {radial_mm:.3f}")
    if point is None:
        raise RuntimeError(f"no edge {where}")
    return point
"""
    assert drawing_specification_violations(source) == ()


def test_detector_follows_callout_tables_into_the_sheet() -> None:
    source = """
from _drawing_common import set_dimension_callouts
from crank_arm_spec import SHAFT_CLEARANCE_MAX, SHAFT_CLEARANCE_MIN

DIMENSION_CALLOUTS = {
    "HubBore": f"{SHAFT_CLEARANCE_MIN:.2f}-{SHAFT_CLEARANCE_MAX:.2f} CLEARANCE",
}
set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
CALLOUTS["Dimple"] = f"{DEPTH:.1f} DEEP"
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule) for item in violations] == [
        (6, "drawing-owned-precision"),
        (6, "drawing-owned-precision"),
        (9, "drawing-owned-precision"),
    ]


def test_diagnostic_name_that_also_reaches_the_sheet_is_still_flagged() -> None:
    source = """
from _drawing_common import add_note

text = f"{DEPTH:.1f} DEEP"
add_note(adapter, text, 0.1, 0.2)
raise RuntimeError(text)
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule) for item in violations] == [
        (4, "drawing-owned-precision")
    ]


def test_detector_flags_hole_callout_precision_through_aliases() -> None:
    source = """
import _drawing_common as drawing
from _drawing_common import set_hole_callout_precision
from _drawing_common import set_hole_callout_precision as callout_places

set_hole_callout_precision(display, {"hw-tapdrldepth": 1}, label="tap")
callout_places(display, {"hw-threaddepth": 1}, label="thread")
drawing.set_hole_callout_precision(display, {"hw-tapdrldepth": 1}, label="module")
"""
    violations = drawing_specification_violations(source)
    assert [(item.line, item.rule, item.evidence) for item in violations] == [
        (
            line,
            "drawing-owned-precision",
            "set_hole_callout_precision(...) rewrites display precision at render time",
        )
        for line in (6, 7, 8)
    ]


def test_new_precision_rules_are_scoped_to_migrated_drawings(tmp_path: Path) -> None:
    body = (
        'NOTE = f"{DEPTH:.1f} DEEP"\n'
        'set_hole_callout_precision(display, {"hw-tapdrldepth": 1}, label="tap")\n'
    )
    legacy = tmp_path / "draw_legacy.py"
    migrated = tmp_path / "draw_top_frame.py"
    legacy.write_text(body, encoding="utf-8")
    migrated.write_text(body, encoding="utf-8")
    violations = drawing_fleet_specification_violations([legacy, migrated])
    assert [(Path(item.filename).name, item.line) for item in violations] == [
        ("draw_top_frame.py", 1),
        ("draw_top_frame.py", 2),
    ]
