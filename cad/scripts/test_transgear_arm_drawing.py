"""Offline contracts for the transgear arm (MHA-164) drawing."""

from __future__ import annotations

import ast
import itertools
import math
from fractions import Fraction
from pathlib import Path

import pytest

import _config
import build_transgear_arm as part
import draw_transgear_arm as drawing
import latch_hook_bracket_geometry as bracket
import latch_hook_bracket_spec as bracket_spec
import latch_hook_geometry as hook
import support_bar_spec as bar
import transgear_arm_geometry as geometry
import transgear_arm_spec as spec
import transgear_hanger_joints as joints
import transgear_latch_pin_spec as pin
import transgear_pivot_screw_spec as pivot_screw
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-arm.pdf")
    assert DRAWINGS_BY_NAME["transgear_arm"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.FRONT_KEEP, drawing.SECTION_KEEP, drawing.END_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_walls_were_judged_at_no_less_than_the_printed_title_block_band() -> None:
    """The geometry module's wall and fit arithmetic uses rounded bands; each
    must cover the title-block row the printed places actually invoke."""
    for places, band in spec.BAND_BY_PLACES.items():
        assert band >= _band(places)
    precision = spec.DRAWING_PRECISION_BY_NAME
    for name, judged in (
        ("TipStation", geometry.TIP_STATION_BAND),
        ("PivotBoreDia", geometry.PIVOT_BORE_DIA_BAND),
        ("PinHoleDepth", geometry.PIN_HOLE_DEPTH_BAND),
    ):
        assert judged >= _band(precision[name]), name


def test_the_thickness_prints_as_the_ground_stock_reference() -> None:
    """The stock's band governs the thickness, so its dimension prints in
    parentheses after the stock's own size, which is the modelled one."""
    prefix, suffix = spec.STOCK_TEXT_PREFIX, spec.STOCK_TEXT_SUFFIX
    assert prefix.endswith("(") and suffix.startswith(")")
    stock_in = Fraction(prefix.rstrip("( "))
    assert float(stock_in) * 25.4 == pytest.approx(geometry.THICKNESS)
    assert "Depth" in drawing.END_KEEP


# The latched arm's angular play about the pivot (IntegratorE's coupled
# stack), rad.
_ARM_ANGLE_PLAY = 0.00305


# The dowel family's length grade, +/-0.010 in (the 98381A catalogue rows).
_PIN_LENGTH_GRADE = 0.010 * 25.4


def _printed_proud_range(pin_length: float, hole_depth: float) -> tuple[float, float]:
    """The pin pressed to the hole floor: its length at either end of the
    family's grade less the depth at either end of its printed row."""
    depth_band = _band(spec.DRAWING_PRECISION_BY_NAME["PinHoleDepth"])
    return (
        pin_length - _PIN_LENGTH_GRADE - (hole_depth + depth_band),
        pin_length + _PIN_LENGTH_GRADE - (hole_depth - depth_band),
    )


def _worst_far_face_margin(
    tip_band: float,
    proud_range: tuple[float, float] | None = None,
    bend_deg: float | None = None,
) -> float:
    """Least axial distance by which the latch pin's full diameter passes
    the hook strip's far face, over every corner of the coupled stack: the
    MHA-170 flap bent to either end of the title block's angular row (its
    BEND 90 DEG note), leaning the strip's far face about the base."""
    if proud_range is None:
        proud_range = _printed_proud_range(pin.LENGTH, geometry.PIN_HOLE_DEPTH)
    if bend_deg is None:
        bend_deg = _config.title_block("angular")["value_deg"]
    pivot = (bar.PIVOT_TAP_X, bracket.BAR_CENTRE_Y + bar.HANGER_TAP_Y)
    hole = (sum(hook.PLANE_X) / 2.0, hook.PIN_HOLE_YZ[0])
    theta0 = math.atan2(hole[1] - pivot[1], hole[0] - pivot[0])
    flap_shift = (
        bar.HOLE_POSITION_BAND + bracket_spec.POSITION_TOL + bracket_spec.HEAD_FLOAT_MAX
    )
    bore_float = (
        geometry.PIVOT_BORE_DIA
        + geometry.PIVOT_BORE_DIA_BAND
        - pivot_screw.SHOULDER_DIA
        - min(pivot_screw.SHOULDER_DIA_LIMITS)
    ) / 2.0
    # The flap's X is held at the base; the strip's face at the pin's height
    # above the base's underside leans by that height times tan(bend error).
    lever = geometry.PIN_MACHINE_Z - bracket.BAR_BACK_FACE_Z
    radii = [(pin.DIA + band) / 2.0 for band in pin.DIA_BAND]
    signs = (-1.0, 1.0)
    margins = []
    corners = itertools.product(
        signs,
        proud_range,
        radii,
        signs,
        (-bracket.SHEET_T_MINUS, bracket.SHEET_T_PLUS),
        signs,
        signs,
        signs,
        signs,
        (-math.radians(bend_deg), math.radians(bend_deg)),
    )
    for tip, proud, r, flap, sheet, tap, float_, lateral, angle, bend in corners:
        theta = theta0 + angle * _ARM_ANGLE_PLAY
        ux, uy = math.cos(theta), math.sin(theta)
        px = pivot[0] + tap * bar.HOLE_POSITION_BAND + float_ * bore_float
        # The crowned end's full-diameter circle, the pin off the arm's
        # centreline by its position band.
        full = geometry.TIP_STATION + tip * tip_band + proud - pin.CROWN_R
        centre_x = px + full * ux - uy * lateral * geometry.HOLE_POSITION_BAND
        far_face = hook.PLANE_X[1] + flap * flap_shift + sheet + lever * math.tan(bend)
        # Distance along the pin until the end circle (spanning the pin's
        # horizontal normal and machine Z) clears the leaning plane.
        c, s = math.cos(bend), math.sin(bend)
        reach = r * math.hypot(uy * c, s)
        margins.append(((centre_x - far_face) * c - reach) / (ux * c))
    return min(margins)


def test_the_latch_pin_full_diameter_passes_the_hook_at_the_printed_tip_band() -> None:
    """R9-23 / R9-50: the hook is set in y/z only, so the tip station's band,
    the pin's length grade, the hole depth's row and the flap's bend all
    reach the pin's grip on the strip; the 7/8 pin in the 8.50 hole keeps the
    full diameter through the strip at every corner of the printed rows."""
    printed = _band(spec.DRAWING_PRECISION_BY_NAME["TipStation"])  # 0.508
    margin = _worst_far_face_margin(printed)
    assert margin == pytest.approx(0.310, abs=1e-3)
    # The spec judges the rounder 0.51 rows, so its worst is a hair smaller.
    assert 0.0 < joints.LATCH_PIN_FAR_FACE_MARGIN_WORST <= margin
    assert joints.LATCH_PIN_FAR_FACE_MARGIN_WORST == pytest.approx(margin, abs=0.01)
    # The spec judges the bend at the title block's angular row or wider.
    assert joints.FLAP_BEND_TOL_DEG >= _config.title_block("angular")["value_deg"]
    # Negative control: the 3/4 pin in the 6.05 hole stops 0.42 short of the
    # far face with the bend and the grade; without either it cleared.
    old = _printed_proud_range(0.75 * 25.4, 6.05)
    assert _worst_far_face_margin(printed, old) < -0.4
    depth_only = (old[0] + _PIN_LENGTH_GRADE, old[1] - _PIN_LENGTH_GRADE)
    assert _worst_far_face_margin(printed, depth_only, bend_deg=0.0) > 0.0


def test_the_explicit_bands_are_the_spot_face_pin_ream_and_hole_positions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("SpotFaceProfile", "SpotFaceDia"): "*deviations(SPOT_FACE_DIA_BAND)",
        ("SpotFaceProfile", "FloorDepth"): "SPOT_FACE_FLOOR_TOLERANCE",
        ("StationReference", "StudStation"): "HOLE_POSITION_TOLERANCE",
        ("StationReference", "PlateTapStation1"): "HOLE_POSITION_TOLERANCE",
        ("StationReference", "PlateTapStation2"): "HOLE_POSITION_TOLERANCE",
        ("PinHoleProfile", "PinHoleZ"): "HOLE_POSITION_TOLERANCE",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_DIA_BAND)",
    }
    # The piloted counterbore only cuts oversize; the pin's press hole must
    # never end up larger than nominal.
    assert min(spec.SPOT_FACE_DIA_BAND) == 0.0 < max(spec.SPOT_FACE_DIA_BAND)
    assert max(geometry.PIN_HOLE_DIA_BAND) == 0.0 > min(geometry.PIN_HOLE_DIA_BAND)


def test_the_section_cuts_through_the_pivot_and_the_square_end() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.FRONT_CENTER[1]
    assert x0 < drawing._front_x(-geometry.PIVOT_END_R)
    assert x1 > drawing._front_x(geometry.TIP_STATION)


def test_the_countersink_lines_ride_the_tap_thread_compartment() -> None:
    definitions = {
        5: "",
        6: "<MOD-DIAM><hw-tapdrilldia> THRU\n<hw-tapsize> - <hw-threadclass> THRU",
        7: "",
        8: "",
    }
    updated = drawing.tap_callout_definitions(definitions, spec.STUD_TAP_CSK_CALLOUT)
    assert "<hw-threadclass>" not in updated[6].lower()
    assert updated[6].endswith(f"\n{spec.STUD_TAP_CSK_CALLOUT}")
    assert {part: updated[part] for part in (5, 7, 8)} == {5: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""}, "X")


def test_registry_row_is_the_made_steel_mha_164() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-164"
    assert int(row["quantity"]) == 1
    assert "ASTM A108" in row["material_specification"]
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = eval(ast.unparse(stamp.args[2]), vars(part)) if len(stamp.args) > 2 else {}
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)
