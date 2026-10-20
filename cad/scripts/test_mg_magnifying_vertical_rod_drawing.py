"""Offline contracts for the magnifying-vertical-rod drawing (#1559)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_mg_magnifying_vertical_rod as part
import draw_mg_magnifying_vertical_rod as drawing
import mg_magnifying_vertical_rod_geom as geom
import mg_magnifying_vertical_rod_spec as spec
import mg_rod_clamp_joint as joint
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm

_MARKED = {
    "RodDia",
    "BodyLength",
    "OverallLength",
    "DomeR",
    "ThreadLength",
    "ReliefWidth",
    "ReliefDia",
    "ReliefRootR",
}


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-vertical-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-vertical-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-vertical-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_vertical_rod"].script
        == Path(drawing.__file__).resolve()
    )


def test_rod_is_the_threaded_bar_of_the_joint_contract() -> None:
    assert (spec.ROD_DIA, spec.ROD_LENGTH) == (5.0, 132.5)
    assert spec.BODY_LENGTH == 125.0
    assert spec.SHOULDER_X == spec.ROD_THREAD_LEN == joint.ROD_THREAD_LEN == 7.50
    assert spec.ROD_THREAD_LEN_BAND == joint.ROD_THREAD_LEN_BAND == (0.25, -0.25)
    # The relief mates with nothing (r1): its width at the title block's .XX
    # band, its Ø as the single limit MAX (the model value is the limit).
    assert (spec.RELIEF_WIDTH, joint.RELIEF_WIDTH_PLACES) == (1.50, 2)
    assert joint.PRINTED_XX_BAND == printed_band_mm(joint.RELIEF_WIDTH_PLACES)
    assert (joint.RELIEF_WIDTH_MIN, joint.RELIEF_WIDTH_MAX) == pytest.approx((0.99, 2.01))
    assert spec.RELIEF_DIA == joint.RELIEF_DIA_MAX == 1.85
    assert spec.RELIEF_DIA_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert spec.THREAD == "#4-40" and spec.THREAD_CALLOUT == "#4-40 UNC"
    assert spec.THREAD_MAJOR == pytest.approx(2.845, abs=1e-3)
    assert spec.TIP_CHAMFER == pytest.approx(
        (spec.THREAD_MAJOR - spec.THREAD_BASIC_MINOR) / 2.0
    )
    assert spec.RELIEF_START_X == pytest.approx(7.50 - 1.50)
    # Full thread only (rule 18): one pitch at the tip, the run-out in the
    # relief; the worst-case engagement holds 1.5D.
    assert spec.FULL_THREAD_START_X == pytest.approx(0.635)
    assert spec.FULL_THREAD_END_X == pytest.approx(spec.RELIEF_START_X)
    assert joint.ENGAGEMENT_WORST == pytest.approx(7.25 - 2.01 - 0.635)
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN == pytest.approx(4.2675)
    assert joint.RELIEF_WIDTH_MIN >= joint.DIE_RUNOUT
    assert joint.RELIEF_DIA_MAX <= joint.THREAD_ROOT_2A_MIN
    assert geom.SEAT_LAND_WORST >= geom.SEAT_LAND_MIN
    # Both relief roots "R0.2 MAX" (r2): the model at the printed limit.
    assert spec.RELIEF_ROOT_R == joint.RELIEF_ROOT_R == 0.2
    assert spec.RELIEF_ROOT_R_TOL_TYPE == 6  # swTolType_e.swTolMAX


def test_relief_roots_are_one_fillet_over_both_corners() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("add_fillet(") == 1
    assert 'name_last_feature(adapter, "ReliefRoots")' in source
    # The shoulder's pick FIRST: the drawing's radius lands on its edge.
    assert (
        "[[SHOULDER_X, RELIEF_R, 0.0], [RELIEF_START_X, RELIEF_R, 0.0]]" in source
    )
    assert "propagate=False" in source
    assert '("ReliefRootR", RELIEF_ROOT_R)' in source
    assert '["ReliefRootR"])[0], \'"ReliefRootR"\')' in source
    # Each root fills a (1 - pi/4) R^2 spandrel turned about the axis at its
    # centroid (Pappus): ~0.1 mm^3, far inside the 0.5 % volume gate.
    rr, q = spec.RELIEF_ROOT_R, spec.RELIEF_DIA / 2.0
    centroid = q + rr * (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)
    roots = 2.0 * 2.0 * math.pi * centroid * (1.0 - math.pi / 4.0) * rr * rr
    assert part.V_TOTAL - part.V_PROFILE == pytest.approx(roots)
    assert 0.0 < roots < 0.005 * part.V_PROFILE


def test_rod_is_one_front_plane_revolve() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("create_revolve(") == 1
    assert 'create_sketch("Front")' in source
    assert 'name_last_feature(adapter, "RodProfile")' in source
    assert 'name_last_feature(adapter, "Rod")' in source
    assert "create_extrusion(" not in source
    for name in spec.DRAWING_DIMENSIONS["RodProfile"]:
        assert re.search(rf'profile\.record\(\s*"{name}"', source), name
    assert "add_thread(" in source
    r, t, m, q = (
        spec.ROD_DIA / 2.0,
        spec.THREAD_MAJOR / 2.0,
        spec.THREAD_BASIC_MINOR / 2.0,
        spec.RELIEF_DIA / 2.0,
    )
    c = spec.TIP_CHAMFER
    v = (
        math.pi * c / 3.0 * (m * m + m * t + t * t)
        + math.pi * t * t * (spec.RELIEF_START_X - c)
        + math.pi * q * q * spec.RELIEF_WIDTH
        + math.pi * r * r * (spec.BODY_LENGTH - r)
        + 2.0 / 3.0 * math.pi * r**3
    )
    assert part.V_PROFILE == pytest.approx(v)


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == _MARKED
    assert set(drawing.SIDE_KEEP).isdisjoint(drawing.DETAIL_KEEP)
    assert set(drawing.SIDE_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert set(drawing.DETAIL_KEEP) == {
        "ThreadLength",
        "ReliefWidth",
        "ReliefDia",
        "ReliefRootR",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= marked
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        **spec.DRAWING_PRECISION["RodProfile"],
        **spec.DRAWING_PRECISION["ReliefRoots"],
    }


def test_tolerances_are_native_on_the_model() -> None:
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "ThreadLength"): "*deviations(ROD_THREAD_LEN_BAND)",
    }
    assert set(spec.DRAWING_BANDS) == {("RodProfile", "ThreadLength")}
    assert spec.SINGLE_LIMITS == {
        ("RodProfile", "ReliefDia"): (1.85, 6),
        ("ReliefRoots", "ReliefRootR"): (0.2, 6),
    }
    precision = spec.DRAWING_PRECISION["RodProfile"]
    assert (precision["ThreadLength"], precision["ReliefWidth"], precision["ReliefDia"]) == (
        2,
        2,
        2,
    )
    assert spec.DRAWING_PRECISION["ReliefRoots"] == {"ReliefRootR": 1}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "_single_limits(adapter)" in source
    # Both lengths read from the shoulder, the seating face (rule 10); the
    # banded thread length names the seat it guards at its callout.
    assert drawing.ORIGIN_DIMENSIONS == ("BodyLength", "ThreadLength")
    assert drawing.DIMENSION_CALLOUTS == {
        "BodyLength": "FROM SHOULDER",
        "ThreadLength": "FROM SHOULDER\nSEATS ON MHA-MG-02;\nTIP CLEARS ITS TAP",
        "DomeR": "TANGENT HEMISPHERE",
    }
    # Owner ruling 2026-10-17: the Ø prints plain at the title block's band.
    assert "RodDia" not in drawing.DIMENSION_CALLOUTS
    assert "STOCK OK" not in Path(drawing.__file__).read_text(encoding="utf-8")
    # One radius stands for both roots: its count rides above the value.
    assert drawing.DIMENSION_CALLOUTS_ABOVE == {"ReliefRootR": "2X"}
    assert 'DIMENSION_CALLOUTS_ABOVE, location="above"' in Path(
        drawing.__file__
    ).read_text(encoding="utf-8")
    for callout in drawing.DIMENSION_CALLOUTS.values():
        lines = callout.splitlines()
        assert len(lines) <= 4 and all(len(line) <= 20 for line in lines), callout
        assert not any(ch.isdigit() for ch in callout.replace("MHA-MG-02", ""))


def test_relief_root_radius_reads_clear_in_detail_a() -> None:
    """The "2X R0.2 MAX" stands under the thread, opposite the shoulder's
    lower root arc; its leader toward the root centre passes under the Ø's
    lower arrow stub and the Ø's line stays off the thread-side root."""
    x_mm, y_mm = drawing.RELIEF_ROOT_CENTRE_MM
    assert (x_mm, y_mm) == pytest.approx(
        (spec.SHOULDER_X - spec.RELIEF_ROOT_R, -(spec.RELIEF_DIA / 2.0 + spec.RELIEF_ROOT_R))
    )
    cx, cy = drawing._detail_xy(x_mm, y_mm)
    tx, ty = drawing.DETAIL_KEEP["ReliefRootR"]
    # Down-left of the centre: opposite the arc's up-right quarter, so the
    # arrow lands on the arc's extension, the circle's down-left side.
    assert tx < cx and ty < cy
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "display.ArcExtensionLineOrOppositeSide = True" in source
    assert "_dress_relief_roots(adapter, detail, annotations)" in source
    # Under the thread's lower silhouette, over the thread length's block and
    # right of its tip extension line.
    thread_bottom = drawing._detail_xy(0.0, -spec.THREAD_MAJOR / 2.0)[1]
    assert thread_bottom - ty >= 0.015
    assert ty - drawing.DETAIL_KEEP["ThreadLength"][1] >= 0.020
    assert tx - 0.012 > drawing._detail_xy(0.0, 0.0)[0]
    # The leader from the text's right end (~10 mm from its centre) passes
    # >= 8 mm under the relief's lower silhouette at the Ø's line.
    dia_x = drawing.DETAIL_KEEP["ReliefDia"][0]
    end_x = tx + 0.010
    leader_y = cy + (cy - ty) / (cx - end_x) * (dia_x - cx)
    relief_bottom = drawing._detail_xy(0.0, -spec.RELIEF_DIA / 2.0)[1]
    assert end_x < dia_x < cx
    assert relief_bottom - leader_y >= 0.008
    # The Ø's line meets the floor >= 2 mm (sheet) clear of the thread-side
    # root's tangent.
    tangent_x = drawing._detail_xy(spec.RELIEF_START_X + spec.RELIEF_ROOT_R, 0.0)[0]
    assert dia_x - tangent_x >= 0.002
    # The root's far edge (its tangent on the shoulder face) stays inside the
    # fence, so the crop keeps it.
    fx, fy = drawing.DETAIL_FOCUS_MM
    assert math.hypot(spec.SHOULDER_X - fx, y_mm - fy) < drawing.DETAIL_RADIUS_MM


def test_overall_is_a_driven_reference_dimension() -> None:
    assert spec.REFERENCE_DIMENSIONS == (("RodProfile", "OverallLength"),)
    assert spec.DRAWING_PRECISION["RodProfile"]["OverallLength"] == 1
    assert "OverallLength" in drawing.SIDE_KEEP
    source = Path(part.__file__).read_text(encoding="utf-8")
    # Made before the body length (never over-defining), then driven at once.
    made = source.index('"overall length",')
    assert made < source.index('_make_driven(adapter, overall, "overall length")')
    assert made < source.index('"body length",')
    assert re.search(r'profile\.record\("OverallLength"\)\n', source)
    assert "_author_reference_dimensions(adapter)" in source


def test_no_general_notes() -> None:
    assert not hasattr(spec, "DRAWING_NOTES")
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source, module.__name__
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "NOTES_XY =" not in source
    assert drawing.THREAD_NOTE_TEXT.startswith("#4-40 UNC")
    assert source.count("add_attached_note(") == 1


def _fixture_screw_reach() -> tuple[float, float]:
    """Rod stations (from the thread tip) the MHA-MG-06 thumb screw can bear
    on: its axis rides the fixture's hex axis, the hex reaches a corner radius
    along the rod each way (its top corner stops on MHA-MG-02's bottom face,
    at the shoulder; its bore stays on the body down to the dome tangent), and
    the tip widens the band by its radius."""
    import mg_output_fixture_geom as fixture
    from _mcmaster_91882a221 import SHANK_DIA

    half = fixture.HEX_CORNER_RADIUS
    tip = SHANK_DIA / 2.0
    return (
        spec.SHOULDER_X + half - tip,
        spec.ROD_LENGTH - spec.DOME_R - half + tip,
    )


def test_body_cylinder_is_the_fixture_thumb_screw_seat() -> None:
    """Owner ruling 2026-10-17 (rule 6, a static seat, Ra 3.2): MHA-MG-06's
    axial thumb screw (MHA-MG-VN-50) locks the fixture wherever the operator
    sets it along the rod (ch. 20 p. 46). Its reach lies on the body's one Ø5
    cylinder and covers nearly all of it, so the control qualifies that whole
    face, with no zone lengths. No MHA-MG-02 screw bears on the rod."""
    import build_mg_magnifier_assembly as assembly
    import mg_magnifying_clamp_geom as clamp
    import mg_output_fixture_geom as fixture
    from _gtol_cylinder import CylinderFace
    from _surface_finish import SEAT, SEAT_UM, SurfaceFinishControl, surface_finish_by_key

    assert spec.SURFACE_FINISHES == (
        SurfaceFinishControl("screw_seat", SEAT_UM, CylinderFace(spec.ROD_DIA)),
    )
    control = surface_finish_by_key(spec.SURFACE_FINISHES, "screw_seat")
    assert control.roughness_ra == SEAT == "3.2"
    assert control.production_method == ""  # no method text
    assert drawing.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    # The Ø5 body, shoulder to dome tangent, is the part's only Ø5 cylinder.
    assert spec.RELIEF_DIA < spec.THREAD_MAJOR < spec.ROD_DIA
    body = (spec.SHOULDER_X, spec.ROD_LENGTH - spec.DOME_R)
    reach = _fixture_screw_reach()
    assert body[0] < reach[0] < reach[1] < body[1]
    assert reach[0] - spec.SHOULDER_X == pytest.approx(4.993, abs=1e-3)
    assert spec.ROD_LENGTH - reach[1] == pytest.approx(7.493, abs=1e-3)
    assert (reach[1] - reach[0]) / (body[1] - body[0]) > 0.9
    # The modelled installation lies inside the reach: the screw axis 47.85
    # under the thread tip, its tip tangent to the rod.
    station = assembly.VROD_TOP_Y - fixture.FIXTURE_AXIS_Y
    assert station == pytest.approx(47.85, abs=1e-9)
    half = fixture.HEX_CORNER_RADIUS
    assert body[0] + half <= station <= body[1] - half
    assert assembly.FIXTURE_SCREW_TIP_X == spec.ROD_DIA / 2.0
    # MHA-MG-02: its thumb screw enters the top face and stops on the lever
    # (the drill to the lever bore's axis); the rod's threaded end, screwed
    # into the bottom face, stops under that bore, so no clamp screw meets it.
    assert clamp.THUMB_TAP_DRILL_DEPTH == pytest.approx(
        clamp.BLOCK_HEIGHT - clamp.LEVER_BORE_Y
    )
    assert spec.SHOULDER_X < clamp.LEVER_BORE_Y - clamp.LEVER_BORE_DIA / 2.0

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_surface_finish(\n") == 1
    assert 'control=surface_finish_by_key(SURFACE_FINISHES, "screw_seat")' in source
    assert "leader_attach_xy=spt(*SEAT_FINISH_PICK)" in source
    assert "char_height=FINISH_CHAR_HEIGHT" in source
    # Picked before the mark circle goes on (no pick meets it).
    assert source.index("add_surface_finish(\n") < source.index(
        "_mark_detail_on_side(adapter, side)"
    )
    # The reason says what the face does, never how to make it; no digits.
    assert spec.SEAT_FINISH_REASON == "THUMB-SCREW SEAT"
    assert not any(ch.isdigit() for ch in spec.SEAT_FINISH_REASON)
    assert "SEAT_FINISH_REASON,\n        spt(*SEAT_REASON_XY)," in source
    for module in (part, drawing):
        module_source = Path(module.__file__).read_text(encoding="utf-8")
        for token in ("add_feature_control_frame(", "add_datum_feature("):
            assert token not in module_source, (module.__name__, token)


def test_seat_finish_reason_reads_at_its_symbol() -> None:
    """The symbol lands on the body's top silhouette inside the screw's reach;
    its reason reads on the symbol's own row, just right of its "Ra 3.2" (r4
    review: a label floating near detail A did not read as the symbol's),
    clear of detail A's stack and of the Ø value. Ink sizes are the r5 farm
    render's (20261017T070700133Z) measures against each anchor."""
    pick_x, pick_y = drawing.SEAT_FINISH_PICK
    assert pick_y == pytest.approx(
        drawing.SIDE_CENTER[1] + spec.ROD_DIA / 2.0 * drawing._S / 1000.0
    )
    model_x = (pick_x - drawing.SIDE_CENTER[0]) * 1000.0 / drawing._S + drawing._MID_X
    reach = _fixture_screw_reach()
    assert reach[0] < model_x < reach[1]
    symbol_x, symbol_y = drawing.SEAT_FINISH_SYMBOL
    reason_x, reason_y = drawing.SEAT_REASON_XY
    assert pick_y < symbol_y and abs(symbol_x - pick_x) < 0.005
    # The symbol's "Ra 3.2" ends 14.9 mm right of its anchor and spans 3.7..
    # 7.0 mm over it; the reason (a note: position = top-left) prints 3.9 mm
    # tall and 2.8 mm a character.
    ra_right = symbol_x + 0.0149
    ra_mid_y = symbol_y + (0.0037 + 0.0070) / 2.0
    reason_right = reason_x + 0.0028 * len(spec.SEAT_FINISH_REASON)
    reason_mid_y = reason_y - 0.0039 / 2.0
    assert 0.001 < reason_x - ra_right < 0.005  # beside it, not touching
    assert abs(reason_mid_y - ra_mid_y) < 0.001  # on its row
    # Clear of the Ø value's text (~12.5 mm left of its dimension line).
    assert reason_right < drawing.SIDE_KEEP["RodDia"][0] - 0.0125 - 0.010
    # The symbol's leader shoulder (~5 mm left of its anchor) stands right of
    # detail A's shoulder extension line, and its top (8 mm over the anchor)
    # under the detail's thread-length row (dimension line ~33 mm under the
    # crop's bottom).
    assert symbol_x - 0.005 > drawing.DETAIL_SHOULDER_X + 0.008
    assert symbol_y + 0.008 < drawing._DETAIL_BOTTOM - 0.030
    assert reason_y < drawing._DETAIL_BOTTOM - 0.030


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.VIEW_SCALE == (2, 1)
    assert drawing.DETAIL_SCALE == (8, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # The fence holds the tip face and the shoulder's outer corner.
    fx, fy = drawing.DETAIL_FOCUS_MM
    for x, y in ((0.0, 0.0), (spec.SHOULDER_X, spec.ROD_DIA / 2.0)):
        assert math.hypot(x - fx, y - fy) < drawing.DETAIL_RADIUS_MM


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-vertical-rod")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
