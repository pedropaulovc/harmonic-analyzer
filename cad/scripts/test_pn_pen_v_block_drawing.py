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
    # f-string names (the chamfer legs) are spelled out by the loop's pattern.
    strings |= {f"Chamfer{corner}{leg}" for corner in (2, 4) for leg in ("dx", "dy")}
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
        "LighteningBore",
    ]
    positions = [_PART_SOURCE.index(f'"{name}"') for name in tree_order]
    # The reference sketches' helpers sit above build(); their calls come
    # last, the section's after its cutting plane.
    positions.append(_PART_SOURCE.index("await _section_plane(adapter)"))
    positions += [
        _PART_SOURCE.index(f"drive_jobs += await _{helper}_reference(adapter)")
        for helper in ("relief", "pivot", "lightening")
    ]
    # The tap is built after the bore, so its through_next stops at the bore.
    assert positions == sorted(positions)


def test_every_feature_is_located_from_the_front_face() -> None:
    # drawing-guidelines.md rule 10: no feature across the depth by symmetry.
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {
        "VMouthZ0",
        "VMouthZ1",
        "ReliefZ0",
        "ReliefZ1",
        "PivotZ",
        "LighteningZ",
    } <= marked
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


def test_printed_bands_keep_both_relief_walls_and_clear_the_marker_body() -> None:
    import _config
    from _printed_tolerance import angular_band_deg, printed_band_mm

    places = spec.DRAWING_PRECISION_BY_NAME
    # Final review (rule 10): every depth-wise edge is a baseline from the
    # front face, no edge chained from another.  The body's four stations
    # print .XXX; with nothing chained the far wall holds at the depth's .X.
    stations = ("VMouthZ0", "VMouthZ1", "ReliefZ0", "ReliefZ1")
    for name in stations:
        assert places[name] == 3, name
    assert places["Depth"] == 1
    assert spec.V_MOUTH_Z0 == 3.0 and spec.V_MOUTH_Z1 == 15.0
    assert spec.RELIEF_Z0 == 2.5 and spec.RELIEF_Z1 == 15.5
    # Linear bands; the V's angle prints whole degrees on the angular row.
    band = {name: printed_band_mm(n) for name, n in places.items() if name != "VAngle"}
    assert places["VAngle"] == 0
    body_r = spec.marker.BODY_FRONT_DIA / 2.0
    grip_r = spec.marker.BARREL_DIA / 2.0

    def stack(b: dict[str, float]) -> tuple[float, float, float, float, float]:
        # The seated body's widest chord over the V's printed corners: its
        # angle (the title block's +/-1 deg) and mouth (both edges' bands);
        # the apex height is their reference and carries no band.  The V's
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
        centre = (spec.V_MOUTH_Z0 + spec.V_MOUTH_Z1) / 2.0
        near = (centre - centre_band) - chord - (spec.RELIEF_Z0 + b["ReliefZ0"])
        far = (spec.RELIEF_Z1 - b["ReliefZ1"]) - (centre + centre_band) - chord
        near_wall = spec.RELIEF_Z0 - b["ReliefZ0"]
        far_wall = spec.BLOCK_DEPTH - b["Depth"] - (spec.RELIEF_Z1 + b["ReliefZ1"])
        return chord, near, far, near_wall, far_wall

    chord, near, far, near_wall, far_wall = stack(band)
    assert spec.RELIEF_NEAR_WALL_PRINTED_MIN == pytest.approx(near_wall)
    assert spec.RELIEF_FAR_WALL_PRINTED_MIN == pytest.approx(far_wall)
    assert near_wall == pytest.approx(2.37)
    assert far_wall == pytest.approx(1.57)
    assert min(near_wall, far_wall) >= 1.5
    assert spec.BODY_HALF_CHORD_PRINTED_MAX == pytest.approx(chord)
    assert chord == pytest.approx(6.006, abs=5e-4)
    assert spec.BODY_NEAR_CLEARANCE_PRINTED_MIN == pytest.approx(near)
    assert spec.BODY_FAR_CLEARANCE_PRINTED_MIN == pytest.approx(far)
    assert near == pytest.approx(0.234, abs=5e-4)
    assert far == pytest.approx(0.234, abs=5e-4)
    # The depth's .X is no longer load-bearing: no callout, no exception.
    assert "Depth" not in spec.DIMENSION_CALLOUTS
    # Review r9 (rules 3/4): each .XXX station states its own function under
    # its value, with no dimension in its text.  Each is load-bearing: taken
    # to .XX alone, a relief wall lets the body touch it (the far one also
    # takes the far wall under the 1.5 floor), a V edge leaves 0.005.
    for name in stations:
        loose = dict(band, **{name: printed_band_mm(2)})
        _, near_loose, far_loose, _, far_wall_loose = stack(loose)
        if name == "ReliefZ0":
            assert near_loose == pytest.approx(-0.146, abs=5e-4)
        elif name == "ReliefZ1":
            assert far_loose == pytest.approx(-0.146, abs=5e-4)
            assert far_wall_loose == pytest.approx(1.19)
        else:
            assert min(near_loose, far_loose) == pytest.approx(0.005, abs=5e-4)
        callout = spec.DIMENSION_CALLOUTS[name]
        assert not re.search(r"\d\.\d", callout), name
    # All four at the title block's .XX: the clearance the policy row cites.
    _, near_xx, far_xx, _, far_wall_xx = stack(
        dict(band, **{name: printed_band_mm(2) for name in stations})
    )
    assert near_xx == pytest.approx(-0.598, abs=5e-4)
    assert far_xx == pytest.approx(-0.598, abs=5e-4)
    assert far_wall_xx == pytest.approx(1.19)
    # Review r11: the V's two edges name the grip they centre, the relief's
    # two the body they clear; the outer one of each pair names the marker.
    marker_number = _config.parts("vn-pen-marker")["number"]
    assert spec.DIMENSION_CALLOUTS["VMouthZ0"] == "CENTRES\nGRIP"
    assert (
        spec.DIMENSION_CALLOUTS["VMouthZ1"] == f"CENTRES\nMARKER GRIP\n{marker_number}"
    )
    assert spec.DIMENSION_CALLOUTS["ReliefZ0"] == "CLEARS\nMARKER BODY"
    far_callout = spec.DIMENSION_CALLOUTS["ReliefZ1"]
    assert far_callout.startswith("CLEARS MARKER\nBODY")
    assert marker_number in far_callout
    # Row widths (~3 mm a character at the sheet's text height) fit the room
    # draw_pn_pen_v_block's keeps give them: the front stations beside their
    # views (~21 / ~31 mm), the back ones between the extension lines either
    # side (~38 / ~52 mm).
    room = {"VMouthZ0": 7, "ReliefZ0": 11, "VMouthZ1": 11, "ReliefZ1": 16}
    for name, chars in room.items():
        rows = spec.DIMENSION_CALLOUTS[name].split("\n")
        assert max(len(row) for row in rows) <= chars, name
    # The two beside-view blocks (centred on their keeps) stay between the
    # extension lines either side: the end view's depth (x _rz(18)) and the
    # section's z 0 foot for the near wall; the front view's SetScrewX line
    # (x 0.184) and the end view's z 0 corner for the V's front edge.
    half = 0.0315 / 2.0
    z0_x = drawing.SECTION_KEEP["ReliefZ0"][0]
    assert z0_x - half > drawing._rz(spec.BLOCK_DEPTH) + 0.002
    assert z0_x + half < drawing._sz(0.0) - 0.0015
    half = 0.021 / 2.0
    mouth_x = drawing.RIGHT_KEEP["VMouthZ0"][0]
    assert mouth_x - half > 0.184 + 0.005
    assert mouth_x + half < drawing._rz(0.0) - 0.002
    # The back stations' blocks (~2.8 mm a character, r9's "BODY MHA-VN-060"
    # measured ~42 mm) stand between the front station's extension line and
    # their own, crossing neither.
    for keep, at, name, z0, z1 in (
        (drawing.RIGHT_KEEP, drawing._rz, "VMouthZ1", spec.V_MOUTH_Z0, spec.V_MOUTH_Z1),
        (drawing.SECTION_KEEP, drawing._sz, "ReliefZ1", spec.RELIEF_Z0, spec.RELIEF_Z1),
    ):
        chars = max(len(row) for row in spec.DIMENSION_CALLOUTS[name].split("\n"))
        half = chars * 0.0028 / 2.0
        assert keep[name][0] - half > at(z0) + 0.003, name
        assert keep[name][0] + half < at(z1) - 0.003, name
    # The named-exception row the spec's emitter comments name.
    policy = (
        Path(__file__).resolve().parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert "| MHA-PN-005 pn-pen-v-block |" in policy
    assert _SPEC_SOURCE.count("Named exception: MHA-PN-005 pn-pen-v-block") == 2


def test_section_looks_the_same_way_as_the_paper_end_view() -> None:
    # Review r3 (rule 10 clarity): A-A mirrored the end view, so the V and the
    # relief read as located from opposite faces.  Both now put z 0 left.
    assert drawing._rz(0.0) < drawing._rz(spec.BLOCK_DEPTH)
    assert drawing._sz(0.0) < drawing._sz(spec.BLOCK_DEPTH)
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
    # Keeps mirror with it: the near-wall text left of the front face, the
    # height right of the far wall.
    keep = drawing.SECTION_KEEP
    assert keep["ReliefZ0"][0] < drawing._sz(0.0)
    far_wall_z = spec.RELIEF_Z1
    assert keep["ReliefHeight"][0] > drawing._sz(spec.BLOCK_DEPTH)
    rim = drawing._sz(
        drawing._CZ + spec.PIVOT_BORE_DIA / 2.0 + spec.PIVOT_BORE_TOP_CHAMFER
    )
    # Review r5: with its text right of the far rim the chamfer's line ran
    # under its whole text block to 1 mm off the border.  Text left: the
    # line runs out to the left end of its ~72 mm above-row, clear of the
    # tap callout (to x 0.2563), over PivotZ's text (top 0.2377) and its
    # extension lines, the block 5 mm or more under the top border (0.2667).
    chamfer_x, chamfer_y = keep["PivotChamferSize"]
    assert chamfer_x + 0.012 < rim
    assert chamfer_x - 0.036 > 0.2563 + 0.005
    assert chamfer_y - 0.0084 > 0.2377 + 0.004
    assert chamfer_y + 0.0075 < 0.2667 - 0.005
    assert chamfer_y > keep["PivotZ"][1] + 0.012
    # The printed ReliefHeight is the far wall's chord in the build; both walls
    # stand from the front face, neither chained from the other.
    assert '["ReliefZ0", "ReliefNearWall", "ReliefZ1", "ReliefHeight"]' in _PART_SOURCE
    assert '"ReliefWidth"' not in _PART_SOURCE
    assert drawing._sz(far_wall_z) < keep["ReliefHeight"][0]
    # The caption drops under the far wall's callout rows.
    assert "position_section_caption(" in _DRAWING_SOURCE
    assert drawing.SECTION_CAPTION_XY[1] < keep["ReliefZ1"][1] - 0.015


def test_holes_are_native_wizard_features_with_native_callouts() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    assert spec.LIGHTENING_SPEC.end == "through_all"
    assert _PART_SOURCE.count("wizard_holes(") == 2
    assert "SET_SCREW_TAP_SPEC,\n" in _PART_SOURCE
    assert "LIGHTENING_SPEC,\n" in _PART_SOURCE
    # The reamed pivot bore is a sketched cut whose diameter carries the band.
    assert "define_circle(" in _PART_SOURCE
    assert spec.DRAWING_BANDS == {
        ("PivotBoreProfile", "PivotDia"): spec.PIVOT_BORE_BAND
    }
    assert _DRAWING_SOURCE.count("add_native_hole_callout(") == 2
    assert 'process="TAP"' in _DRAWING_SOURCE
    assert 'process="DRILL"' in _DRAWING_SOURCE
    # The title block owns the thread class (rule 2); the drill's and the
    # reamed bore's leaders stop on the near rim (rule 14).
    assert (
        'omit_title_block_thread_class(tap_callout, label="rod set-screw tap")'
        in _DRAWING_SOURCE
    )
    assert "lightening_callout.GetAnnotation()" in _DRAWING_SOURCE
    assert 'set_near_side_diameter(pivot_dia[0], "reamed pivot-bore diameter")' in (
        _DRAWING_SOURCE
    )


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
    assert omit < rewrite < _DRAWING_SOURCE.index("lightening_rim = ")
    assert _DRAWING_SOURCE.count("_set_tap_callout_text(") == 2  # def + call


def test_v_is_its_angle_and_mouth_with_a_reference_apex() -> None:
    import pn_pen_carriage_geom as carriage

    # Review r11 (rules 3/10): the V prints its included angle (driving, the
    # title block's +/-1 deg); final review: both mouth edges from the front
    # face; the apex height is a driven reference.
    assert spec.V_ANGLE_DEG == 90.0
    assert spec.V_MOUTH_WIDTH == 12.0
    assert (spec.V_MOUTH_Z0 + spec.V_MOUTH_Z1) / 2.0 == spec.BLOCK_DEPTH / 2.0
    assert spec.RELIEF_WIDTH == 13.0
    assert (spec.RELIEF_Z0 + spec.RELIEF_Z1) / 2.0 == spec.BLOCK_DEPTH / 2.0
    assert spec.V_APEX_Y == 6.0
    assert spec.MARKER_AXIS_Y == pytest.approx(6.0 - 5.3 * math.sqrt(2.0))
    assert carriage.BLOCK_BOTTOM_Y == pytest.approx(366.2)
    assert spec.REFERENCE_DIMENSIONS == (("VGrooveProfile", "VApexY"),)
    assert {"VAngle", "VApexY", "VMouthZ0", "VMouthZ1"} == spec.DRAWING_DIMENSIONS[
        "VGrooveProfile"
    ]
    assert spec.DRAWING_DIMENSIONS["ReliefReference"] == {
        "ReliefZ0",
        "ReliefZ1",
        "ReliefHeight",
    }
    assert spec.DRAWING_PRECISION["VGrooveProfile"]["VApexY"] == 1
    # The build: the apex is made driven before the angle drives, so the
    # sketch is never over-defined; the angle follows a "VAngle" global in
    # degrees; the reference display (parentheses, no tolerance) is read back.
    body = _PART_SOURCE[_PART_SOURCE.index("async def _v_groove(") :]
    body = body[: body.index("\nasync def ")]
    driven = body.index('_make_driven(adapter, apex, "V apex height")')
    angle = body.index("_add_driving_v_angle(adapter, flank_a, flank_b)")
    assert driven < angle
    assert 'dims.record("VApexY")\n' in body
    assert 'dims.record("VAngle", \'"VAngle"\')' in body
    assert 'dims.record("VMouthZ0", \'"VMouthFrontZ"\')' in body
    assert 'dims.record("VMouthZ1", \'"VMouthBackZ"\')' in body
    assert '"VMouth"' not in _PART_SOURCE
    assert '"vertical_distance"' in body and '"horizontal_distance"' in body
    assert 'set_global(adapter, "VAngle", f"{V_ANGLE_DEG}deg")' in _PART_SOURCE
    assert '("VApexY", V_APEX_Y)' not in _PART_SOURCE
    assert "dimension.DrivenState = 2" in _PART_SOURCE
    assert "dimension.DrivenState = 1" in _PART_SOURCE
    assert "_author_reference_dimensions(adapter)\n" in _PART_SOURCE
    assert _PART_SOURCE.index("_author_reference_dimensions(adapter)\n") < (
        _PART_SOURCE.index("clear_dimensions_for_drawing(adapter)")
    )
    # The angle's text point (which picks the wedge it measures) lies inside
    # the V: under the apex, over the mouth, between the flanks.
    u, v = part._v_angle_text_point()
    apex_u = -spec.BLOCK_DEPTH / 2.0
    assert 0.0 < v < spec.V_APEX_Y
    half_width = (spec.V_APEX_Y - v) * math.tan(math.radians(spec.V_ANGLE_DEG / 2))
    assert abs(u - apex_u) < half_width
    # On the sheet the angle sits in the V's void, between the back edge's
    # value (top ~0.1528) and the apex (y 0.180).
    angle_x, angle_y = drawing.RIGHT_KEEP["VAngle"]
    assert angle_x == pytest.approx(drawing._rz(drawing._CZ))
    assert drawing._ry(0.0) + 0.006 < angle_y < drawing._ry(spec.V_APEX_Y) - 0.006


def test_v_runs_past_the_step_so_no_knife_edge_shows_in_the_end_view() -> None:
    # Review final2: a closed triangle at each V mouth lip in the paper-end
    # view, which hiding tangent edges did not remove.  It was brass: stopped
    # at the step, the V left a sliver under each flank where the corner arc
    # curves away from the step (0.5 tall at the mouth, thinning to nothing).
    corner_z = spec.RELIEF_Z0 + spec.RELIEF_CORNER_R
    assert spec.V_MOUTH_Z0 < corner_z < spec.BLOCK_DEPTH / 2.0
    sliver_height = corner_z - spec.V_MOUTH_Z0  # the 90 deg flank rises 1:1
    assert sliver_height == pytest.approx(0.5)
    arc_x_at_mouth = (
        spec.RELIEF_X0
        + spec.RELIEF_CORNER_R
        - math.sqrt(spec.RELIEF_CORNER_R**2 - sliver_height**2)
    )
    assert 0.0 < arc_x_at_mouth - spec.RELIEF_X0 < 0.15
    # The cut runs to where both corner arcs end, so every sliver goes; R1.0
    # stays, and past the step the V lies wholly inside the slot.
    assert spec.RELIEF_CORNER_R == 1.0
    assert spec.V_CUT_LENGTH == spec.RELIEF_X0 + spec.RELIEF_CORNER_R
    assert spec.RELIEF_Z0 < spec.V_MOUTH_Z0 < spec.V_MOUTH_Z1 < spec.RELIEF_Z1
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


def test_end_view_rows_stack_without_crossing() -> None:
    # Baselines nested shortest-innermost: the front edge's three rows, the
    # back edge's four under them, the depth's one value under those, each
    # block's line under its last row (RIGHT_KEEP's row maths): no extension
    # line runs through a lower line or block, and the reamed diameter's
    # callout drops under the depth's line.
    keep = drawing.RIGHT_KEEP
    bottom_face = drawing._ry(0.0)
    row = 0.0056

    def rows(name: str) -> int:
        callout = spec.DIMENSION_CALLOUTS.get(name)
        return 1 if callout is None else callout.count("\n") + 2

    def top(name: str) -> float:
        return keep[name][1] - 0.0023 + (rows(name) - 1) * row / 2.0 + 0.004

    def line(name: str) -> float:
        return keep[name][1] - 0.0023 - (rows(name) - 1) * row / 2.0 - 0.001

    assert top("VMouthZ0") < bottom_face - 0.0005
    assert top("VMouthZ1") < bottom_face - 0.0005
    # Each extension line ends ~1 mm under its own dimension line, over the
    # next line out.
    assert line("VMouthZ0") - 0.001 > line("VMouthZ1") + 0.003
    # The back edge's block stands right of the front edge's x _rz(3)
    # extension line, so only its line passes under that line's end.
    assert keep["VMouthZ1"][0] - 0.0165 > drawing._rz(spec.V_MOUTH_Z0) + 0.003
    assert top("Depth") < line("VMouthZ1") - 0.002
    pivot_top = drawing.BOTTOM_KEEP["PivotDia"][1] + 0.009
    assert pivot_top < line("Depth") - 0.003
    assert drawing.BOTTOM_KEEP["PivotDia"][1] - 0.010 > 0.0651 + 0.03


def test_analytic_volumes_match_the_carriage_mass_model() -> None:
    import pn_pen_carriage_geom as carriage

    assert part.V_BLOCK == pytest.approx(11016.0)
    # Cut one corner radius past the step, the V's run there lies in the slot:
    # the relief removes that much less (the two slivers, 0.005 mm^3, aside).
    assert part.V_GROOVE == pytest.approx(360.0)
    assert part.V_GROOVE_PAST_STEP == pytest.approx(36.0)
    # The carriage mass model cuts the relief square-cornered and leaves the
    # bore's top chamfer: both under 0.05% of the block.
    assert part.V_RELIEF + part.V_RELIEF_CORNERS + part.V_GROOVE_PAST_STEP == (
        pytest.approx(2281.5)
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
    # The exact tap reaches past the bore wall's 7.0 on its axis, never past the bore axis.
    assert (
        math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
        < part.V_SET_SCREW_TAP
        < math.pi * tap_r**2 * spec.BLOCK_DEPTH / 2.0
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
    # Its ink (1.5x the 38.3 x 34.5 mm measured at 1:1, centred 1.8 mm above
    # it) clears the ream callout (to x 0.2764), the title block (top
    # 0.0651) and the caption (from x 0.337, bottom 0.116); the note beside
    # it stays 5 mm inside the border (0.4188).
    half_w, half_h = 0.0383 * 1.5 / 2.0, 0.0345 * 1.5 / 2.0
    ink_cy = drawing.ISO_CENTER[1] - 0.0018
    left, right = drawing.ISO_CENTER[0] - half_w, drawing.ISO_CENTER[0] + half_w
    assert left > 0.2764 + 0.005
    assert ink_cy - half_h > 0.0651 + 0.003
    assert ink_cy + half_h < 0.1235  # the end view's depth line
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
