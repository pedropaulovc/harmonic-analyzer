"""Offline contracts for the pinion-lift-rod drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config

import build_dt_pinion_lift_rod as part
import draw_dt_pinion_lift_rod as drawing
import dt_pinion_lever_geometry as lever
import dt_pinion_lift_rod_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-lift-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-lift-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-lift-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_pinion_lift_rod"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_pinion_lift_rod.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP) | set(drawing.DETAIL_KEEP) | set(drawing.FLATS_KEEP)
    assert kept == marked
    assert set(drawing.DETAIL_KEEP) == {"PinHoleDia", "PinHoleZ"}
    assert set(drawing.FLATS_KEEP) == dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS["FlatProfile"]


def test_bearing_is_the_only_band_and_finish() -> None:
    # drawing-guidelines.md rule 2 (the title block is the general specification) and drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the rod turns in the blocks, so its diameter carries the shaft
    # band and its flank the one roughness symbol; everything else rides the
    # title block at the part-authored places.
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "RodDia"): "*deviations(ROD_DIA_BAND)"
    }
    (control,) = dt_pinion_lift_rod_spec.SURFACE_FINISHES
    assert control.key == "bearing" and control.roughness_um == 1.6
    assert control.face.diameter_mm == dt_pinion_lift_rod_spec.ROD_DIA
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["RodDia"] == 4
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["PinHoleZ"] == 2


def test_pin_hole_sits_at_the_lever_mid_engagement() -> None:
    # U36: the pin crosses the rod where it crosses the lever hub -- half the
    # hub's bore depth in from the front end, which seats on the bore floor.
    assert lever.ROD_PIN_HOLE_FROM_END == lever.BORE_DEPTH / 2.0
    assert lever.ROD_PIN_HOLE_FROM_END == pytest.approx(0.16 * 25.4)
    assert dt_pinion_lift_rod_spec.LEVER_NUMBER in dt_pinion_lift_rod_spec.PIN_HOLE_CALLOUT


def test_the_lathe_sizes_live_on_the_side_view_plane() -> None:
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): one
    # Right-Plane half-profile carries the diameter, body, crown and overall,
    # so they all import into the side view; the pin hole shares that plane.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count('adapter.create_sketch("Right")') == 2
    assert 'create_sketch("Front")' not in source
    assert "create_revolve" in source
    assert 'set_dimension_prefix(adapter, "RodProfile", "CapR", "SR")' in source
    assert set(dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS["RodProfile"]) == set(
        drawing.RIGHT_KEEP
    )
    assert '"*Front"' not in Path(drawing.__file__).read_text(encoding="utf-8")


def test_the_overall_is_a_reference_and_the_body_length_controls() -> None:
    # Rule 10: the overall to the crown apex is real and conspicuous, printed
    # in parentheses; the body length carries the .XX band the rig stack reads.
    assert dt_pinion_lift_rod_spec.DRAWING_REFERENCE_DIMENSIONS == {"RodOverall"}
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION["RodProfile"]["RodBody"] == 2
    # Below the rod, the overall outermost.
    assert drawing.RIGHT_KEEP["RodOverall"][1] < drawing.RIGHT_KEEP["RodBody"][1]
    assert drawing.RIGHT_KEEP["RodBody"][1] < drawing.RIGHT_CENTER[1]


def test_the_body_length_exception_names_the_rig_stacks() -> None:
    # Owner ruling 2026-10-19 (RV-01): the rim-flush rig stacks read the body
    # length, so the review's "tolerance the overall" fix is declared away.
    import pinion_rig_layout
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "dt_pinion_lift_rod", "part")
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    spec = dt_pinion_lift_rod_spec
    assert "body length" in entry.where and "reference overall" in entry.where
    assert spec.CAP_R == pytest.approx(0.19 * 25.4)
    assert "SR.19" in entry.where
    for stack in ("lift_rod_seat_stack", "lever_north_travel_stack"):
        assert stack in entry.reason
        assert callable(getattr(pinion_rig_layout, stack))


def test_the_bearing_band_names_its_mate() -> None:
    # drawing-guidelines.md rule 4 (tighten only for function, and name the
    # mate): the h band and Ra ride the bore the rod runs in.
    block = _config.parts("dt-pinion-pivot-block")
    assert dt_pinion_lift_rod_spec.PIVOT_BLOCK_NUMBER == block["number"]
    callout = dt_pinion_lift_rod_spec.ROD_DIA_CALLOUT
    assert f"RUNNING FIT IN {block['number']} LIFT BORES" in callout
    assert "GROUND STOCK OK" in callout
    assert drawing.DIMENSION_CALLOUTS["RodDia"] == callout
    assert "\n" in callout  # multi-line: below the value, where it prints


def test_the_sheet_has_no_general_notes() -> None:
    # Machinist review r1: the crown note floated far from the feature it
    # governs; the SR on the side view defines the crown.
    assert not hasattr(dt_pinion_lift_rod_spec, "DRAWING_NOTES")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in source
    assert "add_feature_control_frame" not in source
    assert "add_native_axis_datum" not in source
    assert "SetPrecision3" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.DETAIL_SCALE == (5, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # side view true scale
    assert dt_pinion_lift_rod_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


_IN = 25.4
spec = dt_pinion_lift_rod_spec


def test_each_flat_covers_its_cams_feeler_set_range() -> None:
    # Rule-23 retention, owner ruling 2026-11-07 (owner question 2, option
    # A): each flat is twice its screw's half range plus the #2-56 major, up
    # to .01, and sits on the nominal tap station (owner_q2_rule23_sketch.py,
    # panel 2).
    assert spec.SCREW_FROM_RIM["front"] == pytest.approx(6.6563 * _IN, abs=1e-3)
    assert spec.SCREW_FROM_RIM["back"] == pytest.approx(0.66835 * _IN, abs=1e-3)
    assert spec.SCREW_HALF_RANGE["front"] == pytest.approx(0.06575 * _IN, abs=1e-3)
    assert spec.SCREW_HALF_RANGE["back"] == pytest.approx(0.03787 * _IN, abs=1e-3)
    for key, length in (("front", spec.FRONT_FLAT_LEN), ("back", spec.BACK_FLAT_LEN)):
        need = 2.0 * spec.SCREW_HALF_RANGE[key] + spec.CAM_SET_SCREW_MAJOR_MAX
        assert need <= length < need + 0.01 * _IN
    assert spec.FRONT_FLAT_LEN == pytest.approx(0.22 * _IN)
    assert spec.BACK_FLAT_LEN == pytest.approx(0.17 * _IN)
    # The printed rim-side edges, on the .XXX grid round the tap stations.
    assert spec.FRONT_FLAT_EDGE_FROM_RIM == pytest.approx(6.546 * _IN)
    assert spec.BACK_FLAT_EDGE_FROM_RIM == pytest.approx(0.583 * _IN)
    assert spec.FRONT_FLAT_FROM_RIM == pytest.approx(6.656 * _IN)
    assert spec.BACK_FLAT_FROM_RIM == pytest.approx(0.668 * _IN)
    for key in ("front", "back"):
        assert abs(spec.FLAT_FROM_RIM[key] - spec.SCREW_FROM_RIM[key]) <= 0.0005 * _IN


def test_the_screw_point_lands_on_its_flat_at_the_worst_case() -> None:
    # Every rig band and set error, plus the flats' own printed stations and
    # lengths: the point (one pitch off the major each side) stays on its
    # flat, and the shallowest flat is still wider than the point.
    assert spec.SET_SCREW_POINT_DIA == pytest.approx(
        spec.CAM_SET_SCREW_MAJOR_MAX - 2.0 * spec.CAM_SET_SCREW_PITCH
    )
    assert spec.SCREW_POINT_ON_FLAT_MARGIN_MM == pytest.approx(0.0038 * _IN, abs=0.0002 * _IN)
    assert spec.FLAT_CHORD_MIN > spec.SET_SCREW_POINT_DIA
    # For the record (owner sketch: the front flat can show past its hub):
    # with the flats' own bands it shows .019 and reaches .005 under the
    # front block's bore mouth; the back flat stays inside on both counts.
    assert spec.FLAT_HUB_COVER_MM["front"] == pytest.approx(-0.0190 * _IN, abs=0.0002 * _IN)
    assert spec.FLAT_HUB_COVER_MM["back"] > 0.0
    assert spec.FLAT_TO_BLOCK_MM["front"] == pytest.approx(-0.0053 * _IN, abs=0.0002 * _IN)
    assert spec.FLAT_TO_BLOCK_MM["back"] > 0.0


def test_the_flats_take_the_fulcrum_shafts_depth_and_name_their_mate() -> None:
    import pinion_rig_fitup

    assert spec.FLAT_DEPTH == pytest.approx(0.012 * _IN)
    assert spec.ACROSS_FLAT == pytest.approx(0.238 * _IN)
    assert pinion_rig_fitup.FRONT_COLLAR_LEAF == pytest.approx(
        spec._CAM_FRONT_FACE_Z["front"] - spec._rig.FRONT_BLOCK_Z0 - spec._rig.BLOCK_DEPTH
    )
    assert spec.CAM_NUMBER == _config.parts("dt-pinion-cam")["number"]
    assert f"2X {spec.CAM_NUMBER}" in spec.ACROSS_FLAT_CALLOUT
    assert "IN LINE, ONE SIDE" in spec.ACROSS_FLAT_CALLOUT
    assert drawing.DIMENSION_CALLOUTS["AcrossFlat"] == spec.ACROSS_FLAT_CALLOUT
    for name in ("FrontFlatFromRim", "BackFlatFromRim"):
        assert drawing.DIMENSION_CALLOUTS[name] == "FROM CROWN RIM"
    assert spec.DRAWING_PRECISION["FlatProfile"] == {
        "FrontFlatLen": 2,
        "BackFlatLen": 2,
        "FrontFlatFromRim": 3,
        "BackFlatFromRim": 3,
        "AcrossFlat": 3,
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'set_dimension_prefix(adapter, "FlatProfile", "AcrossFlat", "2X ")' in source
    assert "create_sketch(FLAT_PLANE)" in source
    assert 'name_last_feature(adapter, "SetScrewFlats")' in source
    assert part.V_FLATS > 0.0


def test_the_restated_cam_values_match_the_cam_spec() -> None:
    # The rod spec cannot import the cam spec (which reads the rod's
    # diameter); the drawing proves the restatement at import.
    import dt_pinion_cam_spec as cam

    assert drawing._CAM_DRIFT == {}
    assert spec.CAM_UNIT == cam.UNIT
    assert spec.CAM_SET_SCREW_MAJOR_MAX == pytest.approx(cam.SET_SCREW_MAJOR_MAX_MM)


def test_the_flat_normal_is_the_cams_screw_axis_in_the_rod_frame() -> None:
    # Transform2 rows: world = local @ rows.  The cam's tap enters its heavy
    # side from cam-local -Y; taken to the world through the cam's rows and
    # back into the rod through the rod's, it is the flats' outward normal.
    import build_dt_drive_train_assembly as drive
    import build_dt_pinion_cam as cam_build

    assert cam_build._TAP_PLANE_Y < 0.0
    assert spec.CAM_SET_SCREW_AXIS_LOCAL == (0.0, -1.0, 0.0)
    assert spec.ROD_PHASE_DEG == drive.LEVER_TILT_DEG
    world = [
        sum(spec.CAM_SET_SCREW_AXIS_LOCAL[i] * drive.PINION_CAM_ROWS[i][j] for i in range(3))
        for j in range(3)
    ]
    local = [
        sum(drive.LIFT_ROD_ROWS[i][j] * world[j] for j in range(3)) for i in range(3)
    ]
    assert spec.FLAT_NORMAL_LOCAL == pytest.approx(tuple(local), abs=1e-9)
    assert spec.FLAT_NORMAL_LOCAL == pytest.approx(
        (-math.sin(math.radians(10.0)), -math.cos(math.radians(10.0)), 0.0)
    )
    # Measured about the rod's +Z from the pin hole's axis (local X).
    assert spec.FLAT_NORMAL_FROM_PIN_AXIS_DEG == pytest.approx(-100.0)


def test_the_flats_are_the_angular_datum_the_pin_hole_follows() -> None:
    # The cams are staked on the flats before the pin hole is match-drilled
    # through the lever hub, so the sheet prints no clocking between them.
    import dt_drive_train_steps as steps

    assert steps.step_number("cam-collars-set") < steps.step_number("lever-pin-set")
    assert "VIEW B" in drawing.FLATS_LABEL
    assert "DEG" not in drawing.FLATS_LABEL


def test_view_b_looks_square_at_the_flats() -> None:
    rows = part.flats_view_rows()
    x, y, z = rows[0:3], rows[3:6], rows[6:9]
    for a, b, want in ((x, x, 1.0), (y, y, 1.0), (z, z, 1.0), (x, y, 0.0), (y, z, 0.0), (x, z, 0.0)):
        assert sum(p * q for p, q in zip(a, b)) == pytest.approx(want, abs=1e-12)
    # Right-handed, the crown end screen-left as on the side view, flats up,
    # and the line of sight normal to the plane holding the axis and normal.
    assert tuple(z) == pytest.approx(
        (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    )
    assert tuple(x) == (0.0, 0.0, -1.0)
    assert tuple(y) == spec.FLAT_NORMAL_LOCAL
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "place_view(adapter, str(SOURCE), FLATS_VIEW" in source
    assert drawing.FLATS_VIEW == spec.FLATS_VIEW
    # All of VIEW B's sizes above the rod, the across-flat off the crown end.
    top = drawing.FLATS_CENTER[1] + spec.ROD_DIA / 2000.0
    for name, (_, y_sheet) in drawing.FLATS_KEEP.items():
        if name != "AcrossFlat":
            assert y_sheet > top
    assert drawing.FLATS_KEEP["AcrossFlat"][0] < drawing.FLATS_CENTER[0] - drawing.HALF_SPAN
