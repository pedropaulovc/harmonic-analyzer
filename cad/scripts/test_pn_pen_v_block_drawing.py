"""Offline contracts for the pen v-block part and its drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

import pytest

import build_pn_pen_v_block as part
import draw_pn_pen_v_block as drawing
import pn_pen_v_block_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import TAP_DRILL_MM
from _printed_tolerance import printed_band_mm

_PART_SOURCE = Path(part.__file__).read_text(encoding="utf-8")
_DRAWING_SOURCE = Path(drawing.__file__).read_text(encoding="utf-8")
_SPEC_SOURCE = Path(spec.__file__).read_text(encoding="utf-8")
_VIEW_KEEPS = (
    drawing.FRONT_KEEP,
    drawing.RIGHT_KEEP,
    drawing.BOTTOM_KEEP,
    drawing.SECTION_KEEP,
)


def _string_constants(source: str) -> set[str]:
    return {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-v-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-v-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-v-block_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_v_block"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    # The part marks the spec's map and the drawing keeps exactly its union,
    # each dimension in one view only.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [name for keep in _VIEW_KEEPS for name in keep]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS_ABOVE is spec.DIMENSION_CALLOUTS_ABOVE
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert set(spec.DIMENSION_CALLOUTS_ABOVE) <= marked
    for feature, name in spec.DIMENSION_PREFIXES:
        assert name in spec.DRAWING_DIMENSIONS[feature]
    for feature, name in spec.DRAWING_BANDS:
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert name in spec.DIMENSION_CALLOUTS


def test_build_authors_every_marked_feature_and_dimension_name() -> None:
    strings = _string_constants(_PART_SOURCE)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert feature in strings, feature
        assert names <= strings, (feature, names - strings)
    tree_order = [
        "OutlineProfile",
        "Block",
        "VGrooveProfile",
        "VGroove",
        "ReliefProfile",
        "Relief",
        "PivotBoreProfile",
        "PivotBore",
        "PivotBoreChamfer",
        "SetScrewHole",
    ]
    # Within build(): the sketch helpers above it name their own sketches.
    build = _PART_SOURCE[_PART_SOURCE.index("async def build(adapter)") :]
    positions = [build.index(f'"{name}"') for name in tree_order]
    # The reference sketches come last, the section's after its cutting plane.
    positions.append(build.index("await _section_plane(adapter)"))
    positions += [
        build.index(f"drive_jobs += await _{helper}_reference(adapter)")
        for helper in ("relief", "pivot")
    ]
    # The tap is built after the bore, so its through_next stops at the bore.
    assert positions == sorted(positions)
    # Simplified E: no corner chamfers, no lightening bore (the pivot bore's
    # top chamfer stays).
    assert not any(name.startswith(("Chamfer", "Lightening")) for name in strings)


def test_every_feature_is_located_from_the_front_face() -> None:
    # drawing-guidelines.md rule 10: no feature across the depth by symmetry.
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {
        "NeckZ0",
        "NeckZ1",
        "Depth",
        "VMouthZ0",
        "VMouthZ1",
        "ReliefZ0",
        "ReliefZ1",
        "PivotZ",
    } <= marked
    # One datum: the body's front face.  Every depth-wise station the print
    # states is a baseline from it.
    assert spec.depth_station(spec.BODY_Z0) == 0.0
    assert spec.depth_station(0.0) == spec.BODY_SIDE_STEP
    assert spec.depth_station(spec.BODY_Z1) == spec.BODY_DEPTH
    # The paper-end view prints the whole depth-wise stack in one row: the V's
    # sketch carries the neck's and the body's faces as stubs from the datum.
    assert {"NeckZ0", "NeckZ1", "Depth"} <= spec.DRAWING_DIMENSIONS["VGrooveProfile"]
    assert spec.DRAWING_DIMENSIONS["OutlineProfile"] == {"Length"}
    v_groove = _PART_SOURCE[_PART_SOURCE.index("async def _v_groove(") :]
    v_groove = v_groove[: v_groove.index("\nasync def ")]
    for needle in (
        '(0.0, "NeckZ0", \'"NeckFrontZ"\', "VNeckFrontStub")',
        '(NECK_DEPTH, "NeckZ1", \'"NeckBackZ"\', "VNeckBackStub")',
        '(BODY_Z1, "Depth", \'"BlockDepth"\', "VBodyBackStub")',
        "depth_station(z)",
        '"horizontal_points"',
    ):
        assert needle in v_groove, needle
    assert '"VApexZ"' not in _PART_SOURCE
    assert set(spec.REFERENCE_SKETCHES) <= set(spec.DRAWING_DIMENSIONS)
    for feature in spec.REFERENCE_SKETCHES:
        assert f'"{feature}"' in _PART_SOURCE
    # Hidden only once marked, before the save that the drawing opens.
    marks = _PART_SOURCE.index("mark_dimensions_for_drawing(adapter, feature_name")
    hide = _PART_SOURCE.index("blank_reference_sketches(adapter, REFERENCE_SKETCHES)")
    assert marks < hide < _PART_SOURCE.index("save_part_and_images(adapter")
    assert "segment.ConstructionGeometry = True" in _PART_SOURCE
    # PivotZ's extension line lands on the section's bore-axis centreline.
    # Farm 2229cc4db: InsertCenterLine2 on a picked bore face returned None in
    # this section, so the axis is sketched between projected model points.
    # r13: sheet-owned after EditSheet it passed its colour readback and never
    # printed, so it is view-owned (draw_fr_top_frame's recipe): the section
    # active, the points mapped into its sketch, straight to the database (no
    # snapping), endpoints read back, black, CENTER font.
    assert "add_view_centerline" not in _DRAWING_SOURCE
    assert "_add_pivot_axis_centerline(adapter, section)" in _DRAWING_SOURCE
    body = _DRAWING_SOURCE[_DRAWING_SOURCE.index("def _add_pivot_axis_centerline(") :]
    body = body[: body.index("\ndef ")]
    for needle in (
        "model_point_in_view(",
        "PIVOT_BORE_X / 1000.0",
        "_CZ / 1000.0",
        "drawing.ActivateView(view_name(adapter, section))",
        "sketch.ModelToSketchTransform",
        "manager.AddToDB = True",
        "CreateCenterLine(",
        "_assert_centreline_placed(adapter, centerline, points)",
        "segment.Style = _SW_LINE_CENTER",
        "GetOutline()",
    ):
        assert needle in body, needle
    assert "EditSheet()" not in body
    # The database flag is restored whatever CreateCenterLine does.
    assert body.index("manager.AddToDB = True") < body.index("finally:")
    assert "manager.AddToDB = previous_add_to_db" in body
    # 3 mm past each end on paper.
    assert drawing._CENTERLINE_OVERSHOOT_MM * drawing._S == pytest.approx(0.003)
    # Drawn after the section is cut and curated.
    assert _DRAWING_SOURCE.index("keep=SECTION_KEEP") < _DRAWING_SOURCE.index(
        "_add_pivot_axis_centerline(adapter, section)"
    )


def test_hidden_reference_dimensions_reach_their_views() -> None:
    # Farm e7b8b6928: the plain targeted import delivered none of a hidden
    # sketch's dimensions (LighteningZ missing from the bottom view).  Every
    # view curates through _drawing_hidden_sketches, which shows a hidden
    # owner per view; the section, a derived view, is cut and curated while
    # the part shows its sketches, which lie in its cutting plane.
    assert (
        "from _drawing_hidden_sketches import curate_view_dimensions, "
        "part_sketches_shown" in _DRAWING_SOURCE
    )
    assert "from _drawing_dimension_import import curate_view_dimensions" not in (
        _DRAWING_SOURCE
    )
    assert set(spec.SECTION_REFERENCE_SKETCHES) <= set(spec.REFERENCE_SKETCHES)
    section_names = set().union(
        *(spec.DRAWING_DIMENSIONS[s] for s in spec.SECTION_REFERENCE_SKETCHES)
    )
    assert section_names <= set(drawing.SECTION_KEEP)
    for sketch in set(spec.REFERENCE_SKETCHES) - set(spec.SECTION_REFERENCE_SKETCHES):
        assert not spec.DRAWING_DIMENSIONS[sketch] & set(drawing.SECTION_KEEP)
    block = _DRAWING_SOURCE.index("with part_sketches_shown(")
    assert "SECTION_REFERENCE_SKETCHES" in _DRAWING_SOURCE[block : block + 200]
    assert "base_view=front" in _DRAWING_SOURCE[block : block + 250]
    cut = _DRAWING_SOURCE.index("section = create_section_view(")
    curate = _DRAWING_SOURCE.index("keep=SECTION_KEEP")
    iso = _DRAWING_SOURCE.index('"*Isometric"')
    assert block < cut < curate < iso
    # The cutting line and the sketches' plane are the same x.
    assert {point[0] for point in drawing.SECTION_LINE_MODEL_MM} == {spec.PIVOT_BORE_X}
    assert 'base_plane="Right Plane", offset=PIVOT_BORE_X' in _PART_SOURCE
    for helper in ("_relief_reference", "_pivot_reference"):
        body = _PART_SOURCE[_PART_SOURCE.index(f"async def {helper}(") :]
        body = body[: body.index("\nasync def ")]
        assert "create_sketch(SECTION_PLANE)" in body
    assert 'blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))' in (
        _PART_SOURCE
    )


def test_relief_corners_carry_the_largest_radius_the_grip_allows() -> None:
    assert spec.RELIEF_CORNER_R == 1.0
    assert spec._GRIP_GAP_AT_BOTTOM - spec.RELIEF_CORNER_R >= 0.25
    assert spec.DIMENSION_PREFIXES == {("ReliefProfile", "ReliefCornerR"): "2X R"}
    assert (
        "set_dimension_prefix(adapter, feature_name, dimension_name, prefix)"
        in _PART_SOURCE
    )
    assert '"tangent"' in _PART_SOURCE and '"radial"' in _PART_SOURCE


def test_pivot_bore_drops_wholly_into_the_slot_at_its_printed_limits() -> None:
    import pn_pen_carriage_geom as carriage
    import vn_pen_marker_spec as marker

    # Review final4: with the step at 10.0 the reamed bore's edge stood 0.5
    # off it, and at the printed limits (step 10.8, station 11.99, ream
    # radius 2.006) broke 0.8 into the step wall.  Both stations are .X / .XX
    # baselines from the paper end; the step moved to 9.0.
    assert spec.RELIEF_X0 == 9.0
    assert spec.DRAWING_PRECISION["ReliefProfile"]["ReliefX0"] == 1
    assert spec.DRAWING_PRECISION["PivotBoreProfile"]["PivotX"] == 2
    worst_edge = (
        spec.PIVOT_BORE_X
        - printed_band_mm(2)
        - (spec.PIVOT_BORE_DIA + spec.PIVOT_BORE_BAND[0]) / 2.0
    )
    worst_step = spec.RELIEF_X0 + printed_band_mm(1)
    assert spec.PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN == pytest.approx(
        worst_edge - worst_step
    )
    assert 0.15 < spec.PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN < 0.2
    # The grip still seats on 9 of its 14.5 (10 before: under 7% of the grip
    # lost), spans the whole V, and its body clears the corner arcs.
    grip_length = marker.BARREL_END_Y - marker.BARREL_START_Y
    start, end = carriage.MARKER_GRIP_LOCAL_X
    assert end - start == pytest.approx(grip_length)
    seat = min(end, spec.RELIEF_X0) - max(start, 0.0)
    assert seat == spec.RELIEF_X0
    assert (10.0 - seat) / grip_length < 0.07
    assert end > spec.RELIEF_X0 + spec.RELIEF_CORNER_R + 1.5
    assert carriage.plan_cg_residual_mm() <= 0.25


def test_pivot_chamfer_clears_the_rod_fillet_as_a_min_limit() -> None:
    import _config
    import pn_pen_rod_spec as rod

    fillet_reach = rod.SHOULDER_FILLET_R * (2.0 - math.sqrt(2.0))
    assert spec.PIVOT_BORE_TOP_CHAMFER - fillet_reach >= 0.1
    mouth_r = (spec.PIVOT_BORE_DIA + spec.PIVOT_BORE_BAND[0]) / 2.0
    largest = spec.PIVOT_BORE_TOP_CHAMFER + spec.PIVOT_CHAMFER_BAND[0]
    assert mouth_r + largest < (rod.ROD_SECTION + rod.SECTION_BAND[1]) / 2.0
    assert spec.PIVOT_CHAMFER_TOL_TYPE == 5  # swTolMIN
    assert "tolerance.Type = PIVOT_CHAMFER_TOL_TYPE" in _PART_SOURCE
    assert _PART_SOURCE.index("_pivot_chamfer_min_limit(adapter)\n") < (
        _PART_SOURCE.index("clear_dimensions_for_drawing(adapter)")
    )
    rod_number = _config.parts("pn-pen-rod")["number"]
    assert rod_number in spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"]
    for text in (
        spec.DIMENSION_CALLOUTS["PivotChamferSize"],
        spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"],
    ):
        assert not re.search(r"\d\.\d", text)


def test_title_block_bands_keep_walls_lands_and_clear_the_marker_body() -> None:
    import pn_pen_frame_spec as frame
    from _printed_tolerance import angular_band_deg

    places = spec.DRAWING_PRECISION_BY_NAME
    # Simplified E (2026-10 ruling, no named exception): every depth-wise
    # station prints the title block's .X as a baseline from the body's front
    # face; only the neck's two faces take the routine .XX, for the stirrup's
    # window.  Nothing prints .XXX but the reamed bore's banded diameter.
    stations = ("VMouthZ0", "VMouthZ1", "ReliefZ0", "ReliefZ1", "Depth")
    for name in stations:
        assert places[name] == 1, name
    assert places["NeckZ0"] == places["NeckZ1"] == 2
    assert places["VAngle"] == 0
    assert {name for name, n in places.items() if n >= 3} == {"PivotDia"}
    assert spec.V_MOUTH_Z0 == 3.0 and spec.V_MOUTH_Z1 == 15.0
    assert spec.RELIEF_Z0 == 1.0 and spec.RELIEF_Z1 == 17.0
    assert spec.NECK_DEPTH == 18.0 and spec.BODY_DEPTH == 22.2
    station = spec.depth_station
    # Linear bands; the V's angle prints whole degrees on the angular row.
    band = {name: printed_band_mm(n) for name, n in places.items() if name != "VAngle"}
    body_r = spec.marker.BODY_FRONT_DIA / 2.0
    grip_r = spec.marker.BARREL_DIA / 2.0

    def stack(b: dict[str, float]) -> dict[str, float]:
        # The seated body's widest chord over the V's printed corners: its
        # angle (the title block's +/-1 deg) and mouth (both edges' bands);
        # the flat's height is their reference and carries no band.  The V's
        # centre moves by the mean of its two edges' bands.
        mouth_band = b["VMouthZ0"] + b["VMouthZ1"]
        centre_band = mouth_band / 2.0
        chords = []
        for angle in (-angular_band_deg(), angular_band_deg()):
            for mouth in (-mouth_band, mouth_band):
                half = math.radians(spec.V_ANGLE_DEG + angle) / 2.0
                a = ((spec.V_MOUTH_WIDTH + mouth) / 2.0) / math.tan(half)
                axis_y = a - grip_r / math.sin(half)
                chords.append(math.sqrt(body_r**2 - axis_y**2))
        chord = max(chords)
        centre = station((spec.V_MOUTH_Z0 + spec.V_MOUTH_Z1) / 2.0)
        relief_z0 = station(spec.RELIEF_Z0)
        relief_z1 = station(spec.RELIEF_Z1)
        return {
            "chord": chord,
            "near": (centre - centre_band) - chord - (relief_z0 + b["ReliefZ0"]),
            "far": (relief_z1 - b["ReliefZ1"]) - (centre + centre_band) - chord,
            "near_wall": relief_z0 - b["ReliefZ0"],
            "far_wall": spec.BODY_DEPTH - b["Depth"] - (relief_z1 + b["ReliefZ1"]),
            "near_land": (station(spec.V_MOUTH_Z0) - b["VMouthZ0"])
            - (station(0.0) + b["NeckZ0"]),
            "far_land": (station(spec.NECK_DEPTH) - b["NeckZ1"])
            - (station(spec.V_MOUTH_Z1) + b["VMouthZ1"]),
            "neck": spec.NECK_DEPTH + b["NeckZ0"] + b["NeckZ1"],
        }

    worst = stack(band)
    assert spec.RELIEF_NEAR_WALL_PRINTED_MIN == pytest.approx(worst["near_wall"])
    assert spec.RELIEF_FAR_WALL_PRINTED_MIN == pytest.approx(worst["far_wall"])
    assert spec.V_NEAR_LAND_PRINTED_MIN == pytest.approx(worst["near_land"])
    assert spec.V_FAR_LAND_PRINTED_MIN == pytest.approx(worst["far_land"])
    assert worst["near_wall"] == pytest.approx(2.3)
    # The far wall stands at the 1.5 floor exactly (rule: 2.0 target, 1.5
    # floor at worst case).
    assert worst["far_wall"] == pytest.approx(1.5)
    assert worst["near_land"] == pytest.approx(1.69)
    assert worst["far_land"] == pytest.approx(1.69)
    for name in ("near_wall", "far_wall", "near_land", "far_land"):
        assert round(worst[name], 6) >= 1.5, name
    assert spec.BODY_HALF_CHORD_PRINTED_MAX == pytest.approx(worst["chord"])
    assert worst["chord"] == pytest.approx(6.116, abs=5e-4)
    assert spec.BODY_NEAR_CLEARANCE_PRINTED_MIN == pytest.approx(worst["near"])
    assert spec.BODY_FAR_CLEARANCE_PRINTED_MIN == pytest.approx(worst["far"])
    assert worst["near"] == pytest.approx(0.284, abs=5e-4)
    assert worst["far"] == pytest.approx(0.284, abs=5e-4)
    # The neck slides through the stirrup's window at its printed limits; the
    # neck faces' .XX is load-bearing: at .X the neck could print 19.6 wide.
    assert spec.NECK_WIDTH_PRINTED_MAX == pytest.approx(worst["neck"])
    assert worst["neck"] == pytest.approx(19.02)
    assert worst["neck"] < frame.WINDOW_WIDTH_PRINTED_MIN
    loose = stack(dict(band, NeckZ0=printed_band_mm(1), NeckZ1=printed_band_mm(1)))
    assert loose["neck"] > frame.WINDOW_WIDTH_PRINTED_MIN
    # No function text and no tolerance exception: the stations print bare.
    assert set(spec.DIMENSION_CALLOUTS) == {"PivotDia", "PivotChamferSize"}
    policy = (
        Path(__file__).resolve().parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert "pn-pen-v-block" not in policy
    assert "Named exception" not in _SPEC_SOURCE


def test_end_view_prints_the_depth_stack_in_one_baseline_row() -> None:
    # Rule 10: one datum (the body's front face, the end view's left edge),
    # every station a baseline from it, nested shortest-innermost: each
    # station right of and each row under the last, so an outer extension
    # line never crosses an inner dimension line.
    keep = drawing.RIGHT_KEEP
    order = ("NeckZ0", "VMouthZ0", "VMouthZ1", "NeckZ1", "Depth")
    stations = (0.0, spec.V_MOUTH_Z0, spec.V_MOUTH_Z1, spec.NECK_DEPTH, spec.BODY_Z1)
    xs = [drawing._rz(z) for z in stations]
    assert xs == sorted(xs)
    rows = [keep[name][1] for name in order]
    assert rows == sorted(rows, reverse=True)
    for upper, lower in zip(rows, rows[1:], strict=False):
        assert upper - lower == pytest.approx(drawing._END_ROW)
    assert rows[0] < drawing._ry(0.0) - 0.005
    # ~3 mm a character at the sheet's text height.  The neck front face's
    # "2.10" stands left of the datum's extension line, right of the front
    # view's SetScrewX "12.50"; the V's front edge's "5.1" inside its span.
    datum = drawing._rz(spec.BODY_Z0)
    neck_text = keep["NeckZ0"][0]
    assert neck_text + 0.006 < datum - 0.001
    assert neck_text - 0.006 > drawing.FRONT_KEEP["SetScrewX"][0] + 0.0075 + 0.005
    mouth_text = keep["VMouthZ0"][0]
    assert datum + 0.001 < mouth_text - 0.0045
    assert mouth_text + 0.0045 < drawing._rz(spec.V_MOUTH_Z0) - 0.001
    # The lowest row's line (~3.3 mm under its text) stays over the reamed
    # diameter's callout block (keep +0.009 at the top).
    assert (
        keep["Depth"][1] - 0.0033 > drawing.BOTTOM_KEEP["PivotDia"][1] + 0.009 + 0.003
    )


def test_section_looks_the_same_way_as_the_paper_end_view() -> None:
    # Review r3 (rule 10 clarity): A-A mirrored the end view, so the V and the
    # relief read as located from opposite faces.  Both now put the body's
    # front face left.
    assert drawing._rz(spec.BODY_Z0) < drawing._rz(spec.BODY_Z1)
    assert drawing._sz(spec.BODY_Z0) < drawing._sz(spec.BODY_Z1)
    assert drawing._sz(drawing._CZ) == pytest.approx(drawing.SECTION_CENTER[0])
    cut = _DRAWING_SOURCE.index("section = create_section_view(")
    orient = _DRAWING_SOURCE.index("_orient_section(adapter, section)")
    centre = _DRAWING_SOURCE.index("_centre_section(adapter, section)")
    curate = _DRAWING_SOURCE.index("keep=SECTION_KEEP")
    assert cut < orient < centre < curate
    body = _DRAWING_SOURCE[_DRAWING_SOURCE.index("def _orient_section(") :]
    body = body[: body.index("\ndef ")]
    assert "SetReversedCutDirection(" in body
    assert "GetReversedCutDirection()" in body
    # Both walls a baseline pair from the front face: the near wall's "3.1"
    # inside its span, the far wall's "19.1" between the near wall's
    # extension line and its own, the height right of the far wall.
    keep = drawing.SECTION_KEEP
    front = drawing._sz(spec.BODY_Z0)
    near_wall = drawing._sz(spec.RELIEF_Z0)
    far_wall = drawing._sz(spec.RELIEF_Z1)
    assert front + 0.001 < keep["ReliefZ0"][0] - 0.0045
    assert keep["ReliefZ0"][0] + 0.0045 < near_wall - 0.001
    assert near_wall + 0.003 < keep["ReliefZ1"][0] - 0.006
    assert keep["ReliefZ1"][0] + 0.006 < far_wall - 0.003
    assert keep["ReliefZ1"][1] < keep["ReliefZ0"][1]
    assert keep["ReliefHeight"][0] > drawing._sz(spec.BODY_Z1)
    assert keep["ReliefHeight"][0] + 0.006 < 0.4191 - 0.005
    assert front < keep["PivotZ"][0] < drawing._sz(drawing._CZ)
    rim = drawing._sz(
        drawing._CZ + spec.PIVOT_BORE_DIA / 2.0 + spec.PIVOT_BORE_TOP_CHAMFER
    )
    # Review r5: with its text right of the far rim the chamfer's line ran
    # under its whole text block to 1 mm off the border.  Text left: the
    # line runs out to the left end of its ~72 mm above-row, clear of the
    # tap callout (~71 mm centred on TAP_CALLOUT_XY), over PivotZ's text (top
    # ~1.7 mm over its keep) and its extension lines, the block 5 mm or more
    # under the top border (0.2667).
    chamfer_x, chamfer_y = keep["PivotChamferSize"]
    tap_right = drawing.TAP_CALLOUT_XY[0] + 0.0355
    assert chamfer_x + 0.012 < rim
    assert chamfer_x - 0.036 > tap_right + 0.005
    assert chamfer_y - 0.0084 > keep["PivotZ"][1] + 0.0017 + 0.004
    assert chamfer_y + 0.0075 < 0.2667 - 0.005
    assert chamfer_y > keep["PivotZ"][1] + 0.012
    # The printed ReliefHeight is the far wall's chord in the build; both walls
    # stand from the front face, neither chained from the other.
    assert '"ReliefZ0",\n            "ReliefNearWall",\n            "ReliefZ1",' in (
        _PART_SOURCE
    )
    assert '"ReliefWidth"' not in _PART_SOURCE
    # The caption drops under the far wall's line.
    assert "position_section_caption(" in _DRAWING_SOURCE
    assert drawing.SECTION_CAPTION_XY[1] < keep["ReliefZ1"][1] - 0.0033 - 0.003


def test_holes_are_native_wizard_features_with_native_callouts() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    assert _PART_SOURCE.count("wizard_holes(") == 1
    assert "SET_SCREW_TAP_SPEC,\n" in _PART_SOURCE
    # The reamed pivot bore is a sketched cut whose diameter carries the band.
    assert "define_circle(" in _PART_SOURCE
    assert spec.DRAWING_BANDS == {
        ("PivotBoreProfile", "PivotDia"): spec.PIVOT_BORE_BAND
    }
    assert _DRAWING_SOURCE.count("add_native_hole_callout(") == 1
    assert 'process="TAP"' in _DRAWING_SOURCE
    # The title block owns the thread class (rule 2); the reamed bore's
    # leader stops on the near rim (rule 14).
    assert (
        'omit_title_block_thread_class(tap_callout, label="rod set-screw tap")'
        in _DRAWING_SOURCE
    )
    assert 'set_near_side_diameter(pivot_dia[0], "reamed pivot-bore diameter")' in (
        _DRAWING_SOURCE
    )
    # The tap's mouth is on the body's front face, the depth datum.
    assert "(PIVOT_BORE_X, SET_SCREW_Y, BODY_Z0)" in _DRAWING_SOURCE
    assert "[[PIVOT_BORE_X, SET_SCREW_Y, BODY_Z0]]" in _PART_SOURCE


def test_pivot_callout_names_its_mate_and_says_ream() -> None:
    import _config

    rod_number = _config.parts("pn-pen-rod")["number"]
    callout = spec.DIMENSION_CALLOUTS["PivotDia"]
    assert callout.startswith("REAM THRU")
    assert rod_number in callout
    assert not re.search(r"\d\.\d", callout)


def test_tap_callout_says_drill_and_ends_in_the_pivot_bore() -> None:
    # Review r11 (rule 12): "TAP 4-40 UNC THRU" read as drilled through the
    # block, so both native rows end INTO PIVOT BORE; r13: "Ø 2.26 ..." had no
    # process word, so the drill row opens DRILL.  Only text around the
    # variables changes, so size and thread stay associative.
    original = {
        5: "TAP <hw-threaddesc> <hw-thru>",
        6: "",
        7: "<MOD-DIAM><hw-tapdrldia> <hw-thru>",
        8: "",
    }
    rewritten = drawing._tap_callout_definitions(original)
    assert rewritten == {
        5: "TAP <hw-threaddesc> INTO PIVOT BORE",
        6: "",
        7: "DRILL <MOD-DIAM><hw-tapdrldia> INTO PIVOT BORE",
        8: "",
    }
    # Both rows in one part: the drill row alone takes the word.
    joined = drawing._tap_callout_definitions(
        {
            5: "TAP <hw-threaddesc> <hw-thru>",
            6: "",
            7: "",
            8: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>\nCOAXIAL",
        }
    )
    assert joined[8] == "DRILL <MOD-DIAM><hw-thrutapdrldia> INTO PIVOT BORE\nCOAXIAL"
    for bad in (
        {5: "TAP <hw-threaddesc> <hw-thru>", 6: "", 7: "", 8: ""},
        {5: "<hw-thru>", 6: "", 7: "<hw-thru>", 8: ""},
        {5: "TAP <hw-threaddesc> <hw-thru>", 7: "<hw-thru>"},
        # No drill row, or one already worded, or sharing the thread's row.
        {5: "TAP <hw-threaddesc> <hw-thru>", 6: "", 7: "<hw-thru>", 8: ""},
        {
            5: "TAP <hw-threaddesc> <hw-thru>",
            6: "",
            7: "DRILL <MOD-DIAM><hw-tapdrldia> <hw-thru>",
            8: "",
        },
        {
            5: "TAP <hw-tapdrldia> <hw-threaddesc> <hw-thru> <hw-thru>",
            6: "",
            7: "",
            8: "",
        },
    ):
        with pytest.raises(RuntimeError):
            drawing._tap_callout_definitions(bad)
    assert not re.search(r"\d", drawing._TAP_END + drawing._DRILL_WORD)
    # The readback, on resolved text as the sheet prints it.
    assert drawing._tap_callout_resolved(
        "TAP 4-40 UNC INTO PIVOT BORE\n\nDRILL Ø2.26 INTO PIVOT BORE\n"
    )
    for printed in (
        "TAP 4-40 UNC INTO PIVOT BORE\n\nØ2.26 INTO PIVOT BORE\n",
        "DRILL TAP 4-40 UNC INTO PIVOT BORE\n\nØ2.26 INTO PIVOT BORE\n",
        "TAP 4-40 UNC THRU\n\nDRILL Ø2.26 INTO PIVOT BORE\n",
    ):
        assert not drawing._tap_callout_resolved(printed), printed
    # After the thread class leaves, on the tap's callout only.
    omit = _DRAWING_SOURCE.index(
        'omit_title_block_thread_class(tap_callout, label="rod set-screw tap")'
    )
    rewrite = _DRAWING_SOURCE.index("_set_tap_callout_text(tap_callout)")
    assert (
        omit
        < rewrite
        < _DRAWING_SOURCE.index(
            'rebuild_drawing(adapter, label="near-side diameter leaders")'
        )
    )
    assert _DRAWING_SOURCE.count("_set_tap_callout_text(") == 2  # def + call


def test_v_is_its_angle_mouth_and_apex_flat_with_a_reference_height() -> None:
    import pn_pen_carriage_geom as carriage
    from _printed_tolerance import angular_band_deg

    # Review r11 (rules 3/10): the V prints its included angle (driving, the
    # title block's +/-1 deg); final review: both mouth edges from the front
    # face.  Blind review (rule 16): the apex is a flat a cutter leaves, its
    # width driving at .X and its height a driven reference.
    assert spec.V_ANGLE_DEG == 90.0
    assert spec.V_MOUTH_WIDTH == 12.0
    assert (spec.V_MOUTH_Z0 + spec.V_MOUTH_Z1) / 2.0 == spec.DEPTH_MID_Z
    assert spec.RELIEF_WIDTH == 16.0
    assert (spec.RELIEF_Z0 + spec.RELIEF_Z1) / 2.0 == spec.DEPTH_MID_Z
    assert (spec.BODY_Z0 + spec.BODY_Z1) / 2.0 == spec.DEPTH_MID_Z
    # The theoretical apex still seats the grip; the flat stands 1.0 under it.
    assert spec.V_APEX_Y == 6.0
    assert spec.MARKER_AXIS_Y == pytest.approx(6.0 - 5.3 * math.sqrt(2.0))
    assert spec.V_FLAT_WIDTH == 2.0
    assert spec.V_FLAT_Y == 5.0
    assert spec.V_GROOVE_AREA == pytest.approx(35.0)
    assert carriage.BLOCK_BOTTOM_Y == pytest.approx(366.2)
    assert spec.REFERENCE_DIMENSIONS == (("VGrooveProfile", "VFlatY"),)
    assert {
        "VAngle",
        "VFlatWidth",
        "VFlatY",
        "VMouthZ0",
        "VMouthZ1",
        "NeckZ0",
        "NeckZ1",
        "Depth",
    } == spec.DRAWING_DIMENSIONS["VGrooveProfile"]
    assert spec.DRAWING_DIMENSIONS["ReliefReference"] == {
        "ReliefZ0",
        "ReliefZ1",
        "ReliefHeight",
    }
    assert spec.DRAWING_PRECISION["VGrooveProfile"]["VFlatY"] == 1
    assert spec.DRAWING_PRECISION["VGrooveProfile"]["VFlatWidth"] == 1
    # The grip seats on the flanks: at the widest printed flat and either
    # printed angle the flat stays clear over the grip's top, and at the
    # narrowest it is still a flat.
    grip_r = spec.marker.BARREL_DIA / 2.0
    widest = spec.V_FLAT_WIDTH + printed_band_mm(1)
    for angle in (-angular_band_deg(), angular_band_deg()):
        half = math.radians(spec.V_ANGLE_DEG + angle) / 2.0
        gap = grip_r / math.sin(half) - grip_r - (widest / 2.0) / math.tan(half)
        assert gap >= spec.V_FLAT_GRIP_CLEARANCE_PRINTED_MIN - 1e-9
    assert spec.V_FLAT_GRIP_CLEARANCE_PRINTED_MIN == pytest.approx(0.754, abs=1e-3)
    assert spec.V_FLAT_WIDTH - printed_band_mm(1) == pytest.approx(1.2)
    assert spec.V_CONTACT_Y < spec.V_FLAT_Y
    # The build: the flat's height is made driven before the angle drives, so
    # the sketch is never over-defined; the width and the angle follow
    # globals; the reference display (parentheses, no tolerance) is read back.
    body = _PART_SOURCE[_PART_SOURCE.index("async def _v_groove(") :]
    body = body[: body.index("\nasync def ")]
    assert "flank_a, flat, flank_b, mouth = await add_line_chain" in body
    assert 'add_sketch_constraint(flat, None, "horizontal")' in body
    driven = body.index('_make_driven(adapter, flat_height, "V apex flat height")')
    angle = body.index("_add_driving_v_angle(adapter, flank_a, flank_b)")
    assert driven < body.index('dims.record("VFlatWidth", \'"VFlatWidth"\')') < angle
    assert 'dims.record("VFlatY")\n' in body
    assert 'dims.record("VAngle", \'"VAngle"\')' in body
    assert 'dims.record("VMouthZ0", \'"VMouthFrontZ"\')' in body
    assert 'dims.record("VMouthZ1", \'"VMouthBackZ"\')' in body
    assert '"VMouth"' not in _PART_SOURCE
    assert '"vertical_distance"' in body and '"horizontal_distance"' in body
    assert 'set_global(adapter, "VAngle", f"{V_ANGLE_DEG}deg")' in _PART_SOURCE
    assert '("VFlatWidth", V_FLAT_WIDTH)' in _PART_SOURCE
    assert '("VFlatY", V_FLAT_Y)' not in _PART_SOURCE
    assert "dimension.DrivenState = 2" in _PART_SOURCE
    assert "dimension.DrivenState = 1" in _PART_SOURCE
    assert "_author_reference_dimensions(adapter)\n" in _PART_SOURCE
    assert _PART_SOURCE.index("_author_reference_dimensions(adapter)\n") < (
        _PART_SOURCE.index("clear_dimensions_for_drawing(adapter)")
    )
    # The angle's text point (which picks the wedge it measures) lies inside
    # the V: under the flat, over the mouth, between the flanks.
    u, v = part._v_angle_text_point()
    apex_u = -spec.DEPTH_MID_Z
    assert 0.0 < v < spec.V_FLAT_Y
    half_width = (spec.V_APEX_Y - v) * math.tan(math.radians(spec.V_ANGLE_DEG / 2))
    assert abs(u - apex_u) < half_width


def test_v_dimension_text_stays_off_the_part_in_the_end_view() -> None:
    # Blind review (rule 14): the angle's text sat in the V.  It now sits on
    # the V's axis under the bottom face (y 0.156), its arc wholly inside the
    # wedge's mouth so it meets neither mouth edge's extension line; the
    # flat's width prints over the top face and its height right of the body.
    keep = drawing.RIGHT_KEEP
    angle_x, angle_y = keep["VAngle"]
    assert angle_x == pytest.approx(drawing._rz(drawing._CZ))
    bottom = drawing._ry(0.0)
    assert angle_y + 0.0017 < bottom - 0.003
    # The arc runs through the text, about the theoretical apex: it ends on
    # the flanks over the mouth corners, and under the flat.
    radius_mm = (drawing._ry(spec.V_APEX_Y) - angle_y) / drawing._S
    flank_end_y = spec.V_APEX_Y - radius_mm * math.cos(math.radians(45.0))
    assert 0.5 < flank_end_y < spec.V_FLAT_Y
    # Its text clears the rows: the neck's front-face row ends at x 0.196,
    # the mouth edges' row text sits 4.5 mm under it.
    assert angle_x - 0.0045 > drawing._rz(0.0) + 0.02
    assert keep["VMouthZ0"][1] + 0.0017 < angle_y - 0.0018 - 0.002
    # The flat's width: its line over the top face, its text under the tap's
    # callout rows (~0.249 / 0.255, from ~0.247).
    width_x, width_y = keep["VFlatWidth"]
    assert width_x == pytest.approx(drawing._rz(drawing._CZ))
    assert width_y - 0.0033 > drawing._ry(spec.BLOCK_HEIGHT) + 0.004
    assert width_y + 0.0017 < drawing.TAP_CALLOUT_XY[1] - 0.003 - 0.005
    # The flat's height: right of the body's back face, inside the gap to
    # section A-A.
    height_x, height_y = keep["VFlatY"]
    assert height_x > drawing._rz(spec.BODY_Z1) + 0.008
    assert height_x + 0.006 < drawing._sz(spec.BODY_Z0) - 0.008
    assert drawing._ry(0.0) < height_y < drawing._ry(spec.V_FLAT_Y)


def test_v_runs_past_the_step_so_no_knife_edge_shows_in_the_end_view() -> None:
    # Review final2: a closed triangle at each V mouth lip in the paper-end
    # view, which hiding tangent edges did not remove.  It was brass: stopped
    # at the step, the V left a sliver under each flank where the corner arc
    # curved away from the step.  The simplified E's wider slot stands both
    # corner arcs outside the V's mouth, and the cut still runs on to where
    # they end: past the step the V lies wholly inside the slot.
    near_corner_z = spec.RELIEF_Z0 + spec.RELIEF_CORNER_R
    far_corner_z = spec.RELIEF_Z1 - spec.RELIEF_CORNER_R
    assert near_corner_z < spec.V_MOUTH_Z0 < spec.V_MOUTH_Z1 < far_corner_z
    assert spec.RELIEF_CORNER_R == 1.0
    assert spec.V_CUT_LENGTH == spec.RELIEF_X0 + spec.RELIEF_CORNER_R
    assert spec.V_APEX_Y < spec.RELIEF_HEIGHT
    assert "ExtrusionParameters(depth=V_CUT_LENGTH)" in _PART_SOURCE
    assert '\'"ReliefX0" + "ReliefCornerR"\'' in _PART_SOURCE
    # Geometry, not display: the end view no longer hides its tangent edges.
    assert "SetDisplayTangentEdges2" not in _DRAWING_SOURCE


def test_section_shows_the_tap_thread_on_a_visible_thin_layer() -> None:
    # Review final2: section A-A drew the tapped hole as a plain drill.  The
    # section imports its cosmetic thread (at least one instance) and moves
    # it onto a thin continuous visible layer, read back; SolidWorks' own
    # tapped-hole note from that import is deleted there.
    body = _DRAWING_SOURCE[
        _DRAWING_SOURCE.index("def _section_thread_on_visible_layer(") :
    ]
    body = body[: body.index("\nasync def build(")]
    for needle in (
        "import_cosmetic_threads(adapter, section)",
        "if threads[1] < 1:",
        "manager.AddLayer(",
        "layer.Visible = True",
        "int(layer.Style) != 0 or int(layer.Width) != 0",
        "annotation.Layer = SECTION_THREAD_LAYER",
        'if str(annotation.Layer or "") != SECTION_THREAD_LAYER:',
        "if moved < 1:",
    ):
        assert needle in body, needle
    # finalize_drawing's sweep alone removes the one automatic tap note.
    assert "remove_notes_matching" not in body
    assert "expected_redundant_notes=1" in _DRAWING_SOURCE
    assert drawing._COSMETIC_THREAD_ANNOTATION == 1
    caption = _DRAWING_SOURCE.index("position_section_caption(")
    threads = _DRAWING_SOURCE.index(
        "_section_thread_on_visible_layer(adapter, section)"
    )
    iso = _DRAWING_SOURCE.index("import_cosmetic_threads(adapter, iso)")
    assert caption < threads < iso
    assert drawing.TAPPED_HOLE_NOTE == "#4-40 Tapped Hole"


def test_analytic_volumes_match_the_carriage_mass_model() -> None:
    import pn_pen_carriage_geom as carriage

    # The E: the neck 9 x 18, the body 18.3 x 22.2, 18 tall.
    assert part.V_BLOCK == pytest.approx(10228.68)
    # Cut one corner radius past the step, the V's run there lies in the slot:
    # the relief removes that much less.  The apex flat leaves its 2 x 1 tip
    # standing: 35 of the sharp V's 36 mm^2.
    assert part.V_GROOVE == pytest.approx(350.0)
    assert part.V_GROOVE_PAST_STEP == pytest.approx(35.0)
    # The carriage mass model cuts the relief square-cornered and leaves the
    # bore's top chamfer: both under 0.05% of the block.
    assert part.V_RELIEF + part.V_RELIEF_CORNERS + part.V_GROOVE_PAST_STEP == (
        pytest.approx(1903.2)
    )
    corner_r, relief_h = spec.RELIEF_CORNER_R, spec.RELIEF_HEIGHT
    assert part.V_RELIEF_CORNERS == pytest.approx(
        2.0 * (1.0 - math.pi / 4.0) * corner_r**2 * relief_h
    )
    assert 0.0 < part.V_RELIEF_CORNERS < 0.0005 * part.V_TOTAL
    assert 0.0 < part.V_PIVOT_CHAMFER < 0.0005 * part.V_TOTAL
    bore_length = spec.BLOCK_HEIGHT - spec.RELIEF_HEIGHT
    assert part.V_PIVOT_BORE == pytest.approx(math.pi * 4.0 * bore_length)
    tap_r = TAP_DRILL_MM[spec.SET_SCREW_TAP_SPEC.size] / 2.0
    # The exact tap reaches past the bore wall's 9.1 from the front face on its
    # axis, never past the bore axis.
    assert spec.SET_SCREW_TAP_LENGTH == pytest.approx(9.1)
    assert (
        math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
        < part.V_SET_SCREW_TAP
        < math.pi * tap_r**2 * (spec.DEPTH_MID_Z - spec.BODY_Z0)
    )
    block_mass = sum(
        mass
        for name, mass, _x, _z in carriage.plan_mass_items()
        if name.startswith("v-block ")
    )
    sliver = part.V_SET_SCREW_TAP - math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
    carriage_volume = block_mass / carriage.BRASS_G_PER_MM3 - sliver
    assert carriage_volume == pytest.approx(
        part.V_TOTAL - part.V_RELIEF_CORNERS + part.V_PIVOT_CHAMFER
    )


def test_sheet_runs_at_4_to_1_with_3_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert drawing.VIEW_SCALE == (4, 1)
    # Review r5: at 1:1 the iso's tap mouth and bore read as polygons.
    assert drawing.ISO_SCALE == spec.ISOMETRIC_VIEW_SCALE == (3, 2)
    assert _DRAWING_SOURCE.count("scale=VIEW_SCALE") == 4  # three projections + A-A
    assert _DRAWING_SOURCE.count("scale=ISO_SCALE") == 1
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 3:2"
    # Its ink, estimated from the block's box (the old 36 x 18 x 18 block's
    # estimate, 38.2 wide, matched the 38.3 measured at 1:1): 35.0 x 34.9 at
    # 1:1, x1.5, centred 1.8 mm under its centre as measured.  It clears the
    # ream callout (~44 mm either side of its keep), the end view's depth
    # extension line, the title block (top 0.0651) and, along its sloping top,
    # the section caption's left end (x ~0.337, bottom ~0.118); the note
    # beside it stays 5 mm inside the border (0.4188).
    half_w, half_h = 0.0350 * 1.5 / 2.0, 0.0349 * 1.5 / 2.0
    ink_cy = drawing.ISO_CENTER[1] - 0.0018
    left, right = drawing.ISO_CENTER[0] - half_w, drawing.ISO_CENTER[0] + half_w
    assert left > drawing.BOTTOM_KEEP["PivotDia"][0] + 0.044 + 0.005
    assert left > drawing._rz(spec.BODY_Z1) + 0.005
    assert ink_cy - half_h > 0.0651 + 0.003
    top_vertex_x = left + 0.45 * 2.0 * half_w
    ink_top_at_caption = (
        ink_cy + half_h - (0.337 - top_vertex_x) * math.tan(math.radians(30.0))
    )
    assert ink_top_at_caption < drawing.SECTION_CAPTION_XY[1] - 0.015 - 0.003
    assert drawing.ISO_NOTE_XY[0] > right + 0.004
    assert drawing.ISO_NOTE_XY[0] + 0.059 < 0.4188 - 0.005
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in _DRAWING_SOURCE
    assert '"*Back"' in _DRAWING_SOURCE and '"*Left"' in _DRAWING_SOURCE
    assert "create_section_view(" in _DRAWING_SOURCE


def test_no_note_block_no_gdt_no_roughness() -> None:
    # Material and finish ride the title block; the sheet has nothing else to say.
    assert spec.DRAWING_NOTES == ""
    for source in (_PART_SOURCE, _DRAWING_SOURCE):
        assert "Manufacturing Notes" not in source
        for banned in (
            "author_part_pmi",
            "PART_DATUMS",
            "GEOMETRIC_CONTROLS",
            "_gtol",
            "add_datum_feature",
            "add_feature_control_frame",
            "set_basic_dimension",
            "SURFACE_FINISHES",
            "add_surface_finish",
            "apply_color",
        ):
            assert banned not in source, banned


def test_part_stamps_make_critical_drawing_properties() -> None:
    assert "apply_drawing_properties" in _PART_SOURCE
    assert "clear_dimensions_for_drawing" in _PART_SOURCE
    assert "require_saved_drawing_properties" in _PART_SOURCE
    import _config

    registry = _config.parts("pn-pen-v-block")
    assert "brass" in str(registry["material_specification"]).lower()
    assert "bright brass" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
