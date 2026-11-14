"""Offline contracts for the oblique-trammel carrier plate (MHA-CH-06-TL-21)."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _oblique_carrier_hole_table as carrier_table
import build_ch_rocker_arm_tl_oblique_carrier as part
import ch_rocker_arm_tl_oblique_carrier_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_carrier as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _feature_requirements import requirements_for
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_arm_tl_oblique_carrier"
INCH = 25.4


def _printed(value_mm: float, places: int) -> float:
    """``value_mm`` as the inch sheet prints it at ``places``, in mm."""
    return round(value_mm / INCH, places) * INCH


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _at(feature: dict) -> tuple[float, float]:
    """A feature's model point back in the carrier frame (X, Y)."""
    x, _y, z = feature["at"]
    return x, -z


def test_interface_contract() -> None:
    # The outline is symmetric about the tap axis and every edge the sheet
    # prints lands on its inch grid.
    assert spec.OUTLINE_X[0] == -spec.OUTLINE_X[1]
    places = spec.DRAWING_PRECISION_BY_NAME
    assert spec.prints_exactly(spec.PLATE_LENGTH, places["PlateLength"])
    assert spec.prints_exactly(spec.PLATE_WIDTH, places["PlateWidth"])
    assert spec.prints_exactly(-spec.OUTLINE_Y[0], places["PlateNearY"])
    assert spec.THICKNESS == trammel.CARRIER_THICK
    # The lever taps stand on the tap axis, below the pin line, inside the
    # plate, the inner one past the lever's slot end.
    for x, y in spec.LEVER_HOLES:
        assert x == 0.0 and spec.OUTLINE_Y[0] < y < spec.LEVER_INNER_END_Y < 0.0
        assert spec.prints_exactly(y, spec.TABLE_LOCATION_PLACES)


def test_every_calculator_position_is_the_calculators() -> None:
    features = _features()
    expected = {
        "pin_hole_a1": trammel.A1,
        "pin_hole_b1": trammel.B1,
        "pin_hole_a2": trammel.A2,
        "pin_hole_b2": trammel.B2,
        "cl_tap_1": trammel.CL,
        "cr_tap_1": trammel.CR,
        "hub_tap_1": trammel.HUB,
        **{
            f"riser_tap_{i}": point
            for i, point in enumerate(trammel.RISER_SCREWS, start=1)
        },
    }
    for name, point in expected.items():
        assert _at(features[name]) == tuple(point), name
    assert spec.PIN_HOLES == trammel.PIN_HOLES
    assert (spec.CL, spec.CR) == (trammel.CL, trammel.CR)
    # The three clamp taps stand at the calculator's stations: CL/CR in the
    # strap's end waste, HUB on the arcs' centreline.
    assert spec.END_CLAMPS == {"CL": trammel.CL, "CR": trammel.CR}
    assert spec.HUB == trammel.HUB
    assert spec.RISER_SCREWS == trammel.RISER_SCREWS
    assert spec.D1 == trammel.D1
    assert math.isclose(-spec.A2_DX, (trammel.D2 - trammel.D1) / 2.0)
    assert spec.A2_DY == trammel.A2[1]
    # The table prints every X from the corner (carrier_table.table_location);
    # the manifest exports each pin's binding location: A1 from the corner,
    # the others as a baseline from A1, including B2 (not B1 + dX).
    for key in ("A1", "B1", "A2", "B2"):
        feature = features[f"pin_hole_{key.lower()}"]
        origin = spec.OUTLINE_X[0] if key == "A1" else trammel.A1[0]
        assert feature["station_nominal"] == pytest.approx(
            _printed(trammel.PIN_HOLES[key][0] - origin, 3)
        )
        assert carrier_table.table_location(key)[0] == trammel.PIN_HOLES[key][0] - spec.OUTLINE_X[0]


def test_pin_table_uses_title_band_and_one_model_owned_local_control() -> None:
    """Owner review 2026-11-07 (rule 10): X/Y LOC from the plate's corner;
    the pins' relation to A1 keeps one ±.005 (NOTE 2), A2/B2's Y from the
    A1-B1 line its .964 ±.002 (NOTE 1)."""
    features = _features()
    assert not hasattr(spec, "POSITION_BAND")
    assert not hasattr(spec, "POSITION_BANDED")
    a1 = features["pin_hole_a1"]
    assert "parent" not in a1 and "height_from" not in a1
    assert a1["station_nominal"] == pytest.approx(_printed(spec.PIN_HOLES["A1"][0] - spec.OUTLINE_X[0], 3))
    assert a1["height_nominal"] == pytest.approx(_printed(spec.PIN_HOLES["A1"][1] - spec.OUTLINE_Y[0], 3))
    for name in ("station", "height"):
        assert a1[name][1] - a1[name][0] == pytest.approx(.010 * INCH)
        assert a1["precision"][name] == 3
    for key in ("B1", "A2", "B2"):
        feature = features[f"pin_hole_{key.lower()}"]
        assert feature["parent"] == "pin_hole_a1"
        assert feature["station"][1] - feature["station"][0] == pytest.approx(.010 * INCH)
        assert feature["precision"]["station"] == 3
    assert "height" not in features["pin_hole_b1"]  # B1 sets the line
    for key in ("a2", "b2"):
        feature = features[f"pin_hole_{key}"]
        assert feature["height_from"] == "pin_hole_a1"
        assert feature["height"] == pytest.approx([.962 * INCH, .966 * INCH])
    assert spec.OUTER_Y_NOTE == "A2, B2: Y .964 ±.002 FROM THE A1-B1 AXIS LINE"
    assert tuple(spec.A2_DY + v for v in spec.OUTER_Y_DEVIATIONS) == pytest.approx(
        [.962 * INCH, .966 * INCH]
    )
    assert spec.DRAWING_DIMENSIONS["PinHoleProfile"] == {"PinHoleDia"}
    for text in spec.CALLOUTS_BELOW.values():
        assert "ERROR" not in text and "1:1" not in text
    source = inspect.getsource(part._author_outer_pin_rows)
    assert 'for dimension_name in ("A2DY", "B2DY")' in source
    assert "OUTER_Y_DEVIATIONS" in source and "tolerance.SetValues(lower, upper)" in source
    build_source = inspect.getsource(part.build)
    assert "_author_outer_pin_rows(adapter)" in build_source
    assert "Outer Pin Row Note" in build_source
    toleranced = model_toleranced_dimensions(part)
    assert toleranced[("PinHoleProfile", "PinHoleDia")] == "*deviations(PIN_HOLE_BAND)"


def test_pin_holes_are_slide_reamed_and_name_the_pin() -> None:
    hole = _features()["pin_hole_a1"]
    assert hole["dia"] == pytest.approx(
        [spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[1], spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]]
    )
    # The reamed hole (.3760-.3770, owner ruling 2026-11-13) always clears
    # the bought shoulder (the trammel's radius error reads this clearance).
    assert 0.0 < spec.PIN_CLEARANCE_MIN < spec.PIN_CLEARANCE_MAX
    assert (spec.PIN_CLEARANCE_MIN, spec.PIN_CLEARANCE_MAX) == pytest.approx(
        trammel.SHOULDER_CARRIER_CLEARANCE
    )
    # Owner ruling 2026-11-07 (rule 4): the fit by its standard name, the
    # clearance REF; rule 7 (#2649): at most two lines of words under the
    # process line, the mate in the hole table's short TL- form.
    assert hole["note"] == (
        "4X REAM THRU RUNNING FIT ON TL-VN-77 (CLEARANCE .0010-.0030)"
    )
    assert len(drawing.PIN_FIT_CALLOUT.splitlines()[1:]) <= 2
    assert "DIAMETRAL" not in drawing.CALLOUTS_BELOW["PinHoleDia"]
    assert "DIAMETRAL" not in drawing.PIN_FIT_CALLOUT


def test_taps_are_unc_and_hold_rule_18() -> None:
    features = _features()
    for name in ("cl_tap_1", "cr_tap_1", "hub_tap_1"):
        assert features[name]["thread"] == "#8-32 UNC-2B", name
    assert features["riser_tap_1"]["thread"] == "#4-40 UNC-2B"
    assert features["lever_tap_1"]["thread"] == "5/16-18 UNC-2B"
    # Full thread only: the plate at its .X low limit less the tap mouth's
    # edge break and one pitch of incomplete lead.
    for thread in (spec.CLAMP_THREAD, spec.RISER_THREAD, spec.LEVER_THREAD):
        pitch = 25.4 / float(thread.rsplit("-", 1)[1])
        band = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME["StockThick"], unit=spec.UNIT)
        full = spec.THICKNESS - band - spec.TAP_MOUTH_BREAK - pitch
        assert math.isclose(spec.ENGAGEMENT_MM[thread], full), thread
    for thread in (spec.CLAMP_THREAD, spec.RISER_THREAD):
        assert spec.ENGAGEMENT_MM[thread] >= 1.5 * THREAD_MAJOR_MM[thread]
    # A finished 12 plate still cannot hold 1.5D of 5/16-18. The lever callout
    # retains the existing RV-01 shortfall as a plain fact, floored (rule 20).
    lever = spec.LEVER_THREAD
    assert spec.ENGAGEMENT_MM[lever] < 1.5 * THREAD_MAJOR_MM[lever]
    assert spec.SHORT_ENGAGEMENT == (lever,)
    # Machinist review r7: the callout names its mate once, then the shortfall.
    lever_number = _config.parts("ch-rocker-arm-tl-oblique-feed-lever")["number"]
    assert lever_number == "MHA-CH-06-TL-26" == drawing.FEED_LEVER_NUMBER
    assert drawing.LEVER_TAP_TEXT.splitlines() == [
        f"HOLDS {lever_number}", spec.LEVER_TAP_CALLOUT
    ]
    assert "LEVER_TAP_TEXT" in inspect.getsource(drawing.build)


def test_walls_hold_rule_17_at_worst_case() -> None:
    assert min(spec.WALLS_MM.values()) >= WALL_TARGET_MM


def test_no_skid_sag_is_negligible() -> None:
    """The plate spans D1 between its pins; its sag under self-weight and the
    cutting load stays a small fraction of the strap's radial band, so no
    skid or mid-span support is needed."""
    assert round(spec.SAG_SELF_WEIGHT, 2) == 0.02
    assert round(spec.SAG_CUTTING_LOAD, 3) == 0.015
    assert spec.SAG_SELF_WEIGHT + spec.SAG_CUTTING_LOAD < 0.25 * trammel.TOP_EDGE_HALF_BAND


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    printed = set(drawing.TOP_KEEP) | set(drawing.EDGE_KEEP_MODEL_MM)
    # A1's corner row carries the left end's and the -Y edge's values.
    assert printed | drawing.TABLE_ROW_DIMENSIONS == marked
    assert not printed & drawing.TABLE_ROW_DIMENSIONS
    assert not set(drawing.TOP_KEEP) & set(drawing.EDGE_KEEP_MODEL_MM)
    assert marked <= set(spec.DRAWING_PRECISION_BY_NAME)
    assert set(spec.CALLOUT_PREFIXES) <= printed
    assert set(drawing.CALLOUTS_BELOW) <= printed
    # Above-callouts cannot print a line break (pn_pen_v_block_spec): none.
    assert not hasattr(spec, "CALLOUTS_ABOVE")


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """Each band endpoint is a value the inch sheet prints at its places."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                inches = end / INCH
                assert abs(inches - round(inches, places)) < 1e-9, (name, requirement)
            checked += 1
    assert checked


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)
    assert number == "MHA-CH-06-TL-21"


def test_bottom_face_preserves_the_finished_plate_thickness() -> None:
    bottom = requirements_for(drawing)["bottom_face"]
    (face,) = bottom.faces
    assert face.normal == (0.0, -1.0, 0.0)
    assert face.offset_mm == spec.THICKNESS
    feature = _features()["bottom_face"]
    assert feature["normal"] == [0.0, -1.0, 0.0]
    assert feature["plane"] == {
        "frame": "model",
        "axis": "y",
        "value": -spec.THICKNESS,
    }
    assert feature["height_nominal"] == spec.THICKNESS
    assert feature["height"] == pytest.approx([
        spec.THICKNESS - spec.THICKNESS_BAND,
        spec.THICKNESS + spec.THICKNESS_BAND,
    ])


def test_clamp_taps_are_ordinary_through_taps_located_by_the_table() -> None:
    """R4: CL, CR and HUB are each one ordinary #8-32 THRU Hole Wizard tap
    for the common clamp screw; no dowel, spot, precision bore or LEFT
    receiver survives. CL/CR are .XXX table rows from the corner, held to A1
    by NOTE 2; HUB is not tabled (made in situ at the assembly's HUB
    setting)."""
    assert spec.CLAMP_THREAD == spec.HUB_THREAD == "#8-32"
    for hole_spec in (spec.CLAMP_SPEC, spec.HUB_SPEC):
        assert (hole_spec.kind, hole_spec.size, hole_spec.end) == (
            "tapped", "#8-32", "through_all",
        )
    assert not {"ClTap", "CrTap", "HubTap"} & spec.DRAWING_DIMENSIONS.keys()
    assert spec.DRAWING_PRECISION_BY_NAME["ClY"] == spec.TABLE_LOCATION_PLACES
    assert spec.DRAWING_PRECISION_BY_NAME["CrY"] == spec.TABLE_LOCATION_PLACES
    assert not {"HubX", "HubY"} & set(spec.DRAWING_PRECISION_BY_NAME)
    for key in ("CL", "CR", "HUB"):
        assert spec.TABLE_HOLES[key][2] == spec.CLAMP_TAP_DRILL, key
    assert spec.TABLE_ROW_NOTES["HUB"] == "LOCATIONS REF; TL-00 STEP 10"
    for name in ("SPOTS", "SPOT_REFERENCE", "LEFT_CLAMP", "HUB_HOLE_DIA", "CL_DOWEL_BAND"):
        assert not hasattr(spec, name), name
    assert not any("Plane" in feature for feature in spec.DRAWING_DIMENSIONS)
    source = inspect.getsource(part.build)
    assert "for key, point in END_CLAMPS.items():" in source
    assert 'name=f"{prefix}Tap"' in source
    assert 'name="HubTap"' in source
    assert 'placement_dims=[((None, None), ("HubY", None))]' in source
    for retired in ("_spot", "_finished_hub_bore", "LeftClampTap", "HubChamfer"):
        assert retired not in inspect.getsource(part), retired
    features = _features()
    for name in ("cl_tap_1", "cr_tap_1", "hub_tap_1"):
        tap = features[name]
        assert tap["thru"] is True, name
        assert tap["tap_drill_mm"] == spec.CLAMP_TAP_DRILL, name
    for name in ("cl_tap_1", "cr_tap_1"):
        assert features[name]["parent"] == "pin_hole_a1", name
        assert features[name]["height_from"] == "pin_hole_a1", name
        assert {"station", "height"} <= set(features[name]["requirements"]), name
    hub = features["hub_tap_1"]
    assert "station" not in hub["requirements"] and "height" not in hub["requirements"]
    assert hub["note"] == " ".join(drawing.HUB_TAP_NOTE.splitlines())
    assert hub["note"] == "CLAMPS MHA-CH-13 HUB DRILL AND TAP AT ASSEMBLY, TL-00 STEP 10"
    for retired in ("cl_spot", "left_clamp_tap_1", "assembly_hub_bore",
                    "assembly_hub_underside_chamfer"):
        assert retired not in features, retired


def test_in_situ_hub_fit_up_closes_inside_the_strap_top_edge_band() -> None:
    """Owner ruling 5 (option A, 2026-11-01). The HUB on the arcs' centreline
    moves the strap's pivot radially 1:1 against the R800 edge. Drilled in
    situ from the apex (the spindle origin) +Y by HUB_OFFSET, the pin spacing
    moves it with the cut; what reaches the edge at the worst case is the
    DRO setting of the printed offset and the carrier's shift on its pins
    (rule 19: a fit-up that covers the whole range, never root-sum-square)."""
    import ch_rocker_arm_spec as rocker

    assert trammel.HUB[0] == trammel.ARC_CENTRE[0] == 0.0
    assert trammel.HUB[1] - trammel.APEX_Y == pytest.approx(trammel.HUB_OFFSET)
    half = (max(rocker.TOP_EDGE_BAND) - min(rocker.TOP_EDGE_BAND)) / 2.0
    assert half == pytest.approx(0.010 * trammel.INCH)  # .020 one-sided profile
    # The setting: the printed .5125 at a .0001 DRO, held to ±.0005.
    assert spec.inch_text(spec.HUB_OFFSET_PRINTED, spec.HUB_OFFSET_PLACES) == ".5125"
    assert spec.HUB_OFFSET_BAND == pytest.approx(0.0005 * trammel.INCH)
    # The shift: the widest pin clearance, x 1.77 on R.
    shift = trammel.RADIUS_PER_SPACING * spec.PIN_CLEARANCE_MAX
    worst = (
        spec.HUB_OFFSET_BAND + abs(spec.HUB_OFFSET_PRINTED - trammel.HUB_OFFSET) + shift
    )
    assert spec.HUB_RADIAL_STACK == pytest.approx(worst)
    assert f"{spec.HUB_RADIAL_STACK:.3f}" == "0.148"
    assert spec.HUB_RADIAL_STACK < half
    # #2236 P1-A: the HUB setting, each pass's correlated pin error and
    # carriage play, counted once against the same HUB, stay inside half-band
    # plus the owner's accepted .0005 overrun (RV-03, owner 2026-11-13).
    for name, error in spec.PIN_RELATIVE_ERROR.items():
        assert spec.PIN_RELATIVE_STACK[name] == pytest.approx(
            spec.HUB_RADIAL_STACK + error + trammel.CARRIAGE_PLAY_RADIUS
        )
        assert spec.PIN_RELATIVE_STACK[name] <= half + spec.PIN_RELATIVE_OWNER_OVERRUN


def test_table_states_each_size_group_once() -> None:
    """Machinist review r7/r8 (rules 9, 10) and #2649: each size group's
    count, size and process (the pins at their REAM limits, the taps as drill
    and thread, as the sheet-1 callouts print them) and its mate (same-parent
    TL- short forms) print once, in one NOTE cell merged across the group's
    rows, never once per hole; the groups NOTE 1 and NOTE 2 govern flag them
    there. No undefined pass label, no deferral to the callout sheets. Farm
    r10 (20261108T083048016Z): any line past 23 glyphs wrapped and grew its
    row, so each line stays within 23 and a cell within two lines a row."""
    groups = {tags: note.splitlines() for tags, note in carrier_table.NOTE_GROUPS}
    assert spec.CR == pytest.approx((-spec.CL[0], spec.CL[1]))
    assert sorted(tag for tags in groups for tag in tags) == sorted(spec.TABLE_HOLES)
    assert spec.PIN_NUMBER == "MHA-CH-06-TL-VN-77"
    assert groups[("A1", "B1", "A2", "B2")] == [
        "<MOD-DIAM>.3760-.3770", "4X REAM THRU", "RUNNING FIT ON TL-VN-77", "SEE NOTES 1, 2",
    ]
    # CL/CR bench-drilled (2X, as sheet 1); the HUB, the same tap in the same
    # native run, made at assembly (TL-00 step 10, sheet 3).
    assert groups[("CL", "CR", "HUB")] == [
        "CL, CR: 2X <MOD-DIAM>.136 THRU", "8-32 UNC THRU", "HUB: 8-32 AT ASSEMBLY",
        "CLAMPS MHA-CH-13", "SEE NOTE 2",
    ]
    assert groups[("R1", "R2", "R3", "R4")] == [
        "4X <MOD-DIAM>.089 THRU", "4-40 UNC THRU", "HOLDS TL-24", "SEE NOTE 2",
    ]
    assert groups[("L1", "L2")] == ["2X <MOD-DIAM>.257 THRU", "5/16-18 UNC THRU", "HOLDS TL-26"]
    # The pin limits are the sheet-1 4X REAM's .3750 +.0020/+.0010.
    low, high = sorted(spec.PIN_HOLE_BAND)
    assert spec.inch_text(spec.PIN_HOLE_DIA + low, 4) == ".3760"
    assert spec.inch_text(spec.PIN_HOLE_DIA + high, 4) == ".3770"
    for retired in ("R800", "R816", "SEE CALLOUT", "ORIGIN", "X AXIS", "MHA-CH-06-"):
        assert not any(retired in line for lines in groups.values() for line in lines), retired
    for retired in ("HOLE_SIZES_NOTE", "ROW_FLAGS", "ROW_NOTES", "ROW_SIZES", "ROW_MATES"):
        assert not hasattr(carrier_table, retired), retired
    assert carrier_table.NOTE_LINES_PER_ROW == 2
    assert all(
        len(lines) <= carrier_table.NOTE_LINES_PER_ROW * len(tags) for tags, lines in groups.items()
    )
    longest = max(
        len(line.replace("<MOD-DIAM>", "D")) for lines in groups.values() for line in lines
    )
    assert longest <= carrier_table.NOTE_MAX_GLYPHS == 23
    visible = sum(carrier_table.TABLE_WIDTHS) - carrier_table.TABLE_WIDTHS[carrier_table.SIZE_COLUMN]
    assert carrier_table.TABLE_ANCHOR[0] + visible <= 0.216 - 0.030
    # r9 (farm 20261108T070114760Z): at 11/17/17 the rows ran ~14.5 mm; the
    # TAG/X/Y widths stay r8's proven 12/19/19.
    assert carrier_table.TABLE_WIDTHS[:3] == (0.012, 0.019, 0.019)


def test_hub_row_is_tagged_ref_and_agrees_with_sheet_3() -> None:
    """Machinist review r8: the HUB is drawn on the tagged view, so it is
    tagged and tabled; its X/Y are REF (TL-00 step 10 locates it) and agree
    with sheet 3's parenthesized references from A1."""
    assert "HUB" in carrier_table.TABLED_HOLES and "HUB" in carrier_table.TAG_OFFSETS
    assert "HUB" not in carrier_table.A1_RELATED
    assert "HUB: 8-32 AT ASSEMBLY" in dict(carrier_table.NOTE_GROUPS)[("CL", "CR", "HUB")]
    assert carrier_table.ORIGIN_NOTE.endswith("; HUB X/Y REF")
    assert not hasattr(carrier_table, "IN_SITU_HOLES")
    hub_x, hub_y = carrier_table.table_location("HUB")
    a1_x, a1_y = carrier_table.table_location("A1")
    assert (hub_x - a1_x, hub_y - a1_y) == pytest.approx(
        (spec.HUB[0] - spec.PIN_HOLES["A1"][0], spec.HUB[1] - spec.PIN_HOLES["A1"][1])
    )
    # The printed .XXX corner values less A1's give sheet 3's .XX references.
    places = spec.TABLE_LOCATION_PLACES
    printed = [round(value / INCH, places) for value in (hub_x, hub_y, a1_x, a1_y)]
    assert f"{printed[0] - printed[2]:.2f}" == f"{(spec.HUB[0] - spec.PIN_HOLES['A1'][0]) / INCH:.2f}"
    assert f"{printed[1] - printed[3]:.2f}" == f"{(spec.HUB[1] - spec.PIN_HOLES['A1'][1]) / INCH:.2f}"
    hub = _features()["hub_tap_1"]
    assert _at(hub) == pytest.approx(spec.HUB)


def test_pin_edge_break_retains_the_spacer_thrust_seat() -> None:
    """Owner ruling 2026-11-13: no underside chamfer; the purchased spacer
    seats on the title block's broken edge, which leaves it a broad seat."""
    import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
    from _printed_tolerance import edge_break_chamfer_mm

    mouth = (spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]) / 2.0
    assert mouth + edge_break_chamfer_mm(unit=spec.UNIT) < (
        pivot_spacer.OD + pivot_spacer.OD_BAND[1]
    ) / 2.0
    assert spec.SECTION_REFERENCE in spec.REFERENCE_SKETCHES
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_REFERENCE] == {"StockThick"}
    assert not any("Chamfer" in name for name in spec.CALLOUTS_BELOW)
    source = inspect.getsource(part)
    assert "add_chamfer" not in source and "PinChamfer" not in source


def test_section_reference_is_on_its_own_hidden_plane() -> None:
    """The thickness's hidden sketch keeps its own named plane, coincident
    with the Front plane (jig-r6: section A-A imported nothing from the bare
    Front plane). Section A-A is gone; the edge view, parallel to that plane,
    imports from it, and the part is unchanged."""
    assert spec.SECTION_PLANE == "SectionAPlane"
    source = inspect.getsource(part._section_reference)
    assert "create_sketch(SECTION_PLANE)" in source
    assert 'create_sketch("Front")' not in source
    assert "_require_on_section_plane(adapter, feature)" in source
    plane = inspect.getsource(part._section_plane)
    assert "InsertRefPlane(4," in plane
    assert 'blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))' in plane




def test_edge_view_imports_one_hidden_sketch_and_no_body_feature() -> None:
    """The finished thickness is a SectionReference dimension driven from
    Plate's depth (jig-r4/r5: Plate's own depth did not import into the
    section); the edge view imports that one hidden sketch, parallel to it."""
    owners = {
        feature
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        if names & set(drawing.EDGE_KEEP_MODEL_MM)
    }
    assert owners == {spec.SECTION_REFERENCE}
    assert "Plate" not in spec.DRAWING_DIMENSIONS
    assert "StockThick" not in spec.CALLOUTS_BELOW
    assert (spec.SECTION_REFERENCE, "StockThick") not in model_toleranced_dimensions(
        part
    )
    source = inspect.getsource(part)
    assert '"StockThick", \'"PlateThick@Plate"\'' in source
    assert "PIN_CHAMFER_REFERENCE" not in source
    # The stock line stands in A1's +X wall, inside the plate; the text
    # stands left of the plate's -X end and its extension lines are capped to
    # stop 1.5 sheet mm short of it, never running along the view's outline.
    wall = spec.PIN_HOLE_DIA / 2.0
    assert wall + 2.0 <= spec.STOCK_REFERENCE_DX
    text_x = drawing.EDGE_KEEP_MODEL_MM["StockThick"][0]
    assert text_x == spec.OUTLINE_X[0] - drawing._EDGE_TEXT_DX
    assert drawing.EDGE_KEEP_MODEL_MM["StockThick"][1:] == (-spec.THICKNESS / 2.0, 0.0)
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    assert math.isclose(
        drawing.STOCK_WITNESS_MAX_M * 1000.0, drawing._EDGE_TEXT_DX * scale - 1.5
    )
    assert drawing.STOCK_WITNESS_MAX_M > 0.005
    edge = inspect.getsource(drawing._edge_view)
    assert "display.MaxWitnessLineLength = STOCK_WITNESS_MAX_M" in edge


def test_edge_view_replaces_section_a_a() -> None:
    """Owner ruling 2026-11-13 left A-A printing only the thickness; its
    short plane never settled (HA #2762) and its full-length fallback gated
    machinist review. The *Front edge view at the sheet's scale, aligned
    under the top view, hidden lines removed, carries the thickness."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for retired in (
        "create_section_view", "position_section_caption", "SetLineInfo",
        "SetPartialSection", "Crop2", "_pin_section", "SECTION_CENTER",
        "SECTION_LINE_STYLE", "SetUserPreferenceInteger(542",
    ):
        assert retired not in source, retired
    edge = inspect.getsource(drawing._edge_view)
    order = [
        edge.index(call)
        for call in (
            'place_view(adapter, str(SOURCE), "*Front", *EDGE_CENTER, scale=VIEW_SCALE)',
            "set_hidden_lines_removed(adapter, edge)",
            "_align_edge_view(adapter, top, edge)",
            "curate_view_dimensions(",
            "MaxWitnessLineLength",
        )
    ]
    assert order == sorted(order)
    assert drawing.EDGE_CENTER[0] == drawing.TOP_CENTER[0]
    build = inspect.getsource(drawing.build)
    assert build.index("curate_view_dimensions(") < build.index(
        "_edge_view(adapter, top)"
    ) < build.index("set_dimension_callouts(")
    settled = build[build.index("def pin_controls_settled"):build.index("return await finalize_drawing")]
    assert "_assert_edge_view(adapter, top, edge, edge_annotations)" in settled


class _FakeEdgeView:
    def __init__(self, outline, position=(0.222, 0.078)):
        self.outline, self.Position, self.moves = outline, position, []

    def UpdateViewDisplayGeometry(self):
        pass

    def GetOutline(self):
        return self.outline

    def SetViewPosition(self, xy, _update):
        self.moves.append(tuple(xy))
        self.Position = tuple(xy)
        return True


def _edge_fakes(monkeypatch, offset):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing._telemetry, "info", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "_edge_offset", lambda _a, _t, _e: offset())


def test_edge_view_is_moved_under_the_top_view_and_read_back(monkeypatch) -> None:
    """Fake-driven: the view moves by the measured offset until it reads
    back within EDGE_ALIGN_TOLERANCE_M; one that will not settle refuses."""
    view = _FakeEdgeView((0.09, 0.075, 0.353, 0.081))
    offsets = iter([(0.002, -0.001), (0.0, 0.0)])
    _edge_fakes(monkeypatch, lambda: next(offsets))
    drawing._align_edge_view(None, None, view)
    assert view.moves == [pytest.approx((0.224, 0.077))]
    _edge_fakes(monkeypatch, lambda: (0.01, 0.0))
    with pytest.raises(RuntimeError, match="not under the top view"):
        drawing._align_edge_view(None, None, view)


@pytest.mark.parametrize("fault", [None, "misaligned", "stale_outline", "title_block",
                                   "above_lane", "hidden", "off_sheet_text", "cap_lost"])
def test_edge_view_check_refuses_a_misplaced_view(monkeypatch, fault) -> None:
    """Fake-driven: the settled check holds the view under the top view, the
    plate it projects inside its own outline (HA #2762: the section's
    outline stayed off the sheet while its transform read centred), inside
    the border, clear of the title block and below the 20.5's text, its
    thickness visible on the sheet with its extension lines capped."""
    centre_y = {"title_block": 0.060, "above_lane": 0.101}.get(fault, 0.078)
    outline = (
        (-0.595, 0.075, -0.519, 0.081) if fault == "stale_outline"
        else (0.088, centre_y - 0.005, 0.356, centre_y + 0.005)
    )
    view = _FakeEdgeView(outline)
    _edge_fakes(monkeypatch, lambda: (0.001, 0.0) if fault == "misaligned" else (0.0, 0.0))

    def edge_map(xyz):
        x, y, _z = xyz
        return 0.222 + x / 2000.0, centre_y + (y + spec.THICKNESS / 2.0) / 2000.0

    monkeypatch.setattr(
        drawing, "_view_mapper",
        lambda _a, v: edge_map if v is view else (lambda _xyz: (0.25, 0.100)),
    )
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, _item: "StockThick")
    cap = 0.0 if fault == "cap_lost" else drawing.STOCK_WITNESS_MAX_M
    monkeypatch.setattr(
        drawing, "_stock_display",
        lambda _a, _items: SimpleNamespace(MaxWitnessLineLength=cap),
    )
    text = (0.750, 0.078, 0.0) if fault == "off_sheet_text" else (0.084, 0.078, 0.0)
    dimension = SimpleNamespace(
        GetPosition=lambda: text, Visible=3 if fault == "hidden" else 1
    )
    if fault is None:
        drawing._assert_edge_view(None, None, view, [dimension])
        return
    with pytest.raises(RuntimeError, match="edge view is not in place"):
        drawing._assert_edge_view(None, None, view, [dimension])


def test_riser_tap_stations_print_their_walls_band_and_name_the_riser() -> None:
    """The riser is self-cut along the jig's band and spotted through these
    taps, so trammel.RISER_SCREW_WALLS assumes their stations at its places."""
    places = trammel.RISER_TAP_STATION_PLACES
    assert spec.RISER_STATION_PLACES == places == 3
    for name in ("RiserX1", "RiserX1R", "RiserY1", "RiserX2", "RiserX2R", "RiserY2"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == places, name
    features = _features()
    for index, (x, y) in enumerate(spec.RISER_SCREWS, start=1):
        tap = features[f"riser_tap_{index}"]
        for name in ("station", "height"):
            assert tap["precision"][name] == places, name
        # The table row is from the corner; the walls' stack assumes one band
        # from A1 (NOTE 2), not two, and that is what the manifest exports.
        assert carrier_table.table_location(f"R{index}") == pytest.approx(
            (x - spec.OUTLINE_X[0], y - spec.OUTLINE_Y[0])
        )
        assert (tap["parent"], tap["height_from"]) == ("pin_hole_a1", "pin_hole_a1")
        assert tap["station_nominal"] == pytest.approx(
            _printed(x - spec.PIN_HOLES["A1"][0], places)
        )
        assert tap["height_nominal"] == pytest.approx(_printed(y, places))
        assert tap["station"][1] - tap["station"][0] == pytest.approx(.010 * INCH)
    riser = _config.parts("ch-rocker-arm-tl-oblique-riser")["number"]
    assert riser == "MHA-CH-06-TL-24"
    # Machinist review r7: the mate once, no assembly instruction.
    assert drawing.RISER_TAP_TEXT == f"HOLDS {riser} SCREWS"
    assert "RiserTaps" not in spec.DRAWING_DIMENSIONS
    assert spec.RISER_WALLS_FROM_A1 >= WALL_TARGET_MM
    assert dict(carrier_table.NOTE_GROUPS)[("R1", "R2", "R3", "R4")].startswith(
        "4X <MOD-DIAM>.089 THRU\n4-40 UNC THRU\nHOLDS TL-24"
    )
    # Three rows (the native two and the mate), ~4.5 mm each, centred on the
    # anchor: under the border, and inside it to the right.
    rows = 2 + len(drawing.RISER_TAP_TEXT.splitlines())
    x, y = (value * 1000.0 for value in drawing.RISER_CALLOUT_XY)
    assert y + 4.5 * rows / 2.0 + 3.0 < _BORDER[3]
    half = 2.36 * len(drawing.RISER_TAP_TEXT) / 2.0
    assert x + half < _BORDER[2]
    source = inspect.getsource(drawing.build)
    assert "RISER_TAP_TEXT" in source
    for retired in ("CLEAR OF ITS CUT EDGES", "END WASTE", "LOCATES"):
        assert retired not in Path(drawing.__file__).read_text(encoding="utf-8"), retired


def test_riser_table_has_each_hole_even_when_model_heights_are_shared() -> None:
    screws = spec.RISER_SCREWS
    assert screws[1][1] == screws[0][1] and screws[3][1] == screws[2][1]
    assert screws[1][0] == -screws[0][0] and screws[3][0] == -screws[2][0]
    source = inspect.getsource(part)
    assert '(("RiserX1ROrigin", _origin_x("RiserX1R")), SharedCoordinate(0))' in source
    assert '(("RiserX2ROrigin", _origin_x("RiserX2R")), SharedCoordinate(2))' in source
    assert not spec.CALLOUT_PREFIXES
    for i, point in enumerate(screws, 1):
        assert spec.TABLE_HOLES[f"R{i}"][:2] == point


def test_every_hole_is_located_from_the_corner_and_related_to_a1() -> None:
    """Owner review 2026-11-07 (rule 10): X/Y LOC run from one origin, the
    plate's lower-left corner an edge finder picks up, never a hole centre.
    The holes whose stacks assume one ±.005 station from A1 (coordinator
    ruling 2026-11-07, option (b)) keep it in flagged NOTE 2; the lever taps
    relate to the -Y edge only and the HUB's row is REF."""
    corner = (spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    assert carrier_table.ORIGIN == corner
    assert spec.DRAWING_DIMENSIONS[spec.STATION_REFERENCE] == {"EdgeX"}
    assert not set(drawing.TOP_KEEP) & {
        "A2DX", "B2DX", "PinSpacing", "LeverX", "EdgeX", "PlateNearY"
    }
    source = inspect.getsource(drawing)
    for retired in ("_arrows_inside", "_cap_near_y_witness", "NEAR_Y_WITNESS"):
        assert retired not in source, retired
    features = _features()
    located = {
        "pin_hole_a1": "A1", "pin_hole_b1": "B1", "pin_hole_a2": "A2",
        "pin_hole_b2": "B2", "cl_tap_1": "CL", "cr_tap_1": "CR",
        "lever_tap_1": "L1", "lever_tap_2": "L2",
        **{f"riser_tap_{i}": f"R{i}" for i in range(1, 5)},
    }
    assert set(located.values()) | {"HUB"} == set(carrier_table.TABLED_HOLES)
    # NOTE 2 names its own tags (r10: no row flags); "R1-R4" is a range.
    named = set()
    for item in carrier_table.A1_RELATION_NOTE.split(":", 1)[0].split(", "):
        span = re.fullmatch(r"([A-Z]+)(\d+)-\1(\d+)", item)
        named |= (
            {f"{span[1]}{i}" for i in range(int(span[2]), int(span[3]) + 1)} if span else {item}
        )
    assert named == set(carrier_table.A1_RELATED)
    for name, tag in located.items():
        feature = features[name]
        places = feature["precision"]["station"]
        x, y = _at(feature)
        assert carrier_table.table_location(tag) == pytest.approx((x - corner[0], y - corner[1]))
        related = tag in carrier_table.A1_RELATED
        # The manifest's one station/height per hole is its binding location:
        # the A1 relation for NOTE 2's rows, the corner row otherwise.
        origin = spec.PIN_HOLES["A1"] if related else corner
        assert feature["station_nominal"] == pytest.approx(_printed(x - origin[0], places)), name
        if tag != "B1":
            assert ("height_from" in feature) is related, name
        if tag not in ("B1", "A2", "B2"):
            assert feature["height_nominal"] == pytest.approx(_printed(y - origin[1], places)), name
        assert (feature.get("parent") == "pin_hole_a1") is related, name
        # prechips Feature forbids extra keys (extra_forbidden).
        assert not any(key.startswith("a1_") or key == "station_from" for key in feature), name
        assert (tag in named) is related, name
        # NOTE 2's rows are flagged once, where their size group is stated.
        group = next(note for tags, note in carrier_table.NOTE_GROUPS if tag in tags)
        assert not related or re.search(r"^SEE NOTES? .*2$", group, re.MULTILINE), name
    assert set(carrier_table.A1_RELATED) == {
        "B1", "A2", "B2", "CL", "CR", "R1", "R2", "R3", "R4"
    }
    note = carrier_table.A1_RELATION_NOTE
    assert note.startswith("B1, A2, B2, CL, CR, R1-R4:") and note.endswith("\u00b1.005")
    assert "LOCATE FROM A1 IN X" in note and "FROM THE A1-B1 AXIS LINE IN Y" in note
    assert carrier_table.ORIGIN_NOTE == (
        "X/Y LOC FROM THE LOWER-LEFT PLATE CORNER; HUB X/Y REF"
    )
    # The lever taps share the corner X of their table rows.
    assert (
        features["lever_tap_1"]["station_nominal"]
        == features["lever_tap_2"]["station_nominal"]
    )
    source = inspect.getsource(carrier_table.create_carrier_hole_table)
    assert "datum_xy=_point(adapter, view, *ORIGIN)" in source
    assert "Reattach" not in source


def test_end_clamp_taps_print_one_2x_callout_naming_the_strap() -> None:
    """Machinist review r7 (rule 10): CL and CR are one size, so one callout
    on CL counts both, and it names the strap it clamps, nothing more."""
    assert drawing.END_CLAMP_COUNT == 2
    assert drawing.END_CLAMP_TAP_TEXT == "CLAMPS MHA-CH-13" == f"CLAMPS {spec.STRAP_NUMBER}"
    assert not hasattr(drawing, "CR_CALLOUT_XY")
    build = inspect.getsource(drawing.build)
    assert 'part_spec.END_CLAMPS["CL"]' in build and "CR_CALLOUT" not in build
    assert build.index("_strip_thread_class(") < build.index("_count_callout(callout, count")
    assert build.index("_count_callout(callout, count") < build.index("_append_callout_below(")
    # The count field, when the native callout carries one, becomes 2X ...
    field = {5: "", 6: "", 7: "<NUM_INST>X <MOD-DIAM><hw-tapdrldia> THRU ALL\n<hw-thread>", 8: ""}
    assert drawing.counted_definitions(field, 2)[7] == (
        "2X <MOD-DIAM><hw-tapdrldia> THRU ALL\n<hw-thread>"
    )
    # ... and otherwise the count leads the drill row.
    plain = {5: "", 6: "", 7: "<MOD-DIAM><hw-tapdrldia> THRU ALL\n<hw-thread>", 8: "X"}
    assert drawing.counted_definitions(plain, 2) == {**plain, 7: f"2X {plain[7]}"}
    later = {5: "", 6: "", 7: "ROW\n<MOD-DIAM>.136", 8: ""}
    assert drawing.counted_definitions(later, 2)[7] == "ROW\n2X <MOD-DIAM>.136"
    for bad in ({5: "", 6: "", 7: "", 8: ""},
                {5: "<MOD-DIAM>", 6: "", 7: "<MOD-DIAM>", 8: ""},
                {5: "<NUM_INST>X ", 6: "<NUM_INST>X ", 7: "", 8: ""},
                {1: ""}):
        with pytest.raises(RuntimeError):
            drawing.counted_definitions(bad, 2)


def test_hole_callouts_carry_no_process_words() -> None:
    """TL-20 convention: the native callout alone, no "DRILL, THEN TAP"."""
    for name in ("CR_PROCESS", "RISER_PROCESS", "LEVER_PROCESS"):
        assert not hasattr(spec, name)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "process=" not in source


def _on_sheet(x: float, y: float) -> tuple[float, float]:
    """Carrier (X, Y) mm -> top-view sheet mm (1:2 about the outline centre)."""
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    cx = sum(spec.OUTLINE_X) / 2.0
    cy = sum(spec.OUTLINE_Y) / 2.0
    return (
        drawing.TOP_CENTER[0] * 1000.0 + (x - cx) * scale,
        drawing.TOP_CENTER[1] * 1000.0 + (y - cy) * scale,
    )


def _top_text(name: str) -> tuple[float, float]:
    x, _zero, minus_y = drawing.TOP_KEEP[name]
    return _on_sheet(x, -minus_y)


def _segment_hits_box(a, b, box) -> bool:
    (x0, y0), (x1, y1) = a, b
    for i in range(201):
        t = i / 200.0
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            return True
    return False


# B landscape (sheet mm): the drawing border and the title block's corner.
_BORDER = (12.7, 12.7, 419.1, 266.7)
_TITLE_BLOCK = (216.0, 12.7, 419.1, 65.0)
_CALLOUT_HALF_WIDTH = 25.0  # "5/16-18 UNC THRU ALL" ~ 21 chars x 2.36 mm


def _callout_box(anchor) -> tuple[float, float, float, float]:
    x, y = anchor[0] * 1000.0, anchor[1] * 1000.0
    return (x - _CALLOUT_HALF_WIDTH, y - 7.4, x + _CALLOUT_HALF_WIDTH, y + 1.8)


def _boxes_overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_every_location_text_stands_outside_the_outline() -> None:
    """jig-r3: hole-location dimensions sat inside the outline, crossing
    holes and each other. Every top-view text but the ream's diameter stands
    outside it, in its lane."""
    diameters = {"PinHoleDia"}
    x0, y0 = _on_sheet(spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    x1, y1 = _on_sheet(spec.OUTLINE_X[1], spec.OUTLINE_Y[1])
    for name in set(drawing.TOP_KEEP) - diameters:
        tx, ty = _top_text(name)
        assert not (x0 - 3.0 < tx < x1 + 3.0 and y0 - 3.0 < ty < y1 + 3.0), name
    for name in drawing.TOP_KEEP:
        tx, ty = _top_text(name)
        assert _BORDER[0] + 6.0 <= tx <= _BORDER[2] - 6.0, name
        assert _BORDER[1] <= ty <= _BORDER[3], name
    # One sheet: the outline lanes fit between the outline and the border.
    outermost = min(_top_text(name)[0] for name in drawing.TOP_KEEP)
    assert outermost - 7.0 > _BORDER[0]


def test_callouts_and_iso_clear_the_title_block() -> None:
    """jig-r3: the iso and its note ran into the title block."""
    for anchor in (
        drawing.CL_CALLOUT_XY,
        drawing.RISER_CALLOUT_XY,
        drawing.LEVER_CALLOUT_XY,
        drawing.HUB_CALLOUT_XY,
    ):
        box = _callout_box(anchor)
        assert not _boxes_overlap(box, _TITLE_BLOCK), anchor
        assert _BORDER[0] < box[0] and box[2] < _BORDER[2], anchor
    iso_half = (30.0, 18.0)  # ~58 x 34 mm at 1:8 (jig-r3 render)
    cx, cy = drawing.ISO_CENTER[0] * 1000.0, drawing.ISO_CENTER[1] * 1000.0
    iso = (cx - iso_half[0], cy - iso_half[1], cx + iso_half[0], cy + iso_half[1])
    assert not _boxes_overlap(iso, _TITLE_BLOCK)
    assert iso[2] < _BORDER[2]
    note_x, note_y = (value * 1000.0 for value in drawing.ISO_NOTE_XY)
    assert note_y - 4.0 > _TITLE_BLOCK[3]
    assert note_x + 2.36 * len(spec.ISOMETRIC_VIEW_NOTE) < _BORDER[2]
    assert spec.ISOMETRIC_VIEW_NOTE.endswith(
        f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    )
    # The edge view's band stands above the title block, below the 20.5's
    # text and left of the iso's note.
    half = spec.THICKNESS / 2.0 * drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1]
    edge_y = drawing.EDGE_CENTER[1] * 1000.0
    assert edge_y - half > _TITLE_BLOCK[3] + 3.0
    assert edge_y + half + 10.0 < _top_text("PlateLength")[1]
    assert _on_sheet(spec.OUTLINE_X[1], 0.0)[0] + 2.0 < note_x


def test_edge_view_text_stands_left_of_the_plate_below_every_top_text() -> None:
    """The thickness's text stands in its lane left of the plate's -X end,
    inside the border, below every top-view text (the ream's block
    included)."""
    x, _y, _z = drawing.EDGE_KEEP_MODEL_MM["StockThick"]
    tx = _on_sheet(x, 0.0)[0]
    assert _BORDER[0] + 10.0 < tx < _on_sheet(spec.OUTLINE_X[0], 0.0)[0] - 6.0
    ty = drawing.EDGE_CENTER[1] * 1000.0
    assert all(ty + 10.0 < _top_text(name)[1] for name in drawing.TOP_KEEP)


def test_tap_callout_leaders_clear_every_station_text() -> None:
    """jig-r2 leader-through-text: a leader runs from its hole to the near
    end of its callout's first line, ~5 mm below the anchor. Each must clear
    every top-view dimension text (approximated as 24 x 6 mm)."""
    leaders = {
        "CL": (spec.CL, drawing.CL_CALLOUT_XY),
        "riser": (spec.RISER_SCREWS[3], drawing.RISER_CALLOUT_XY),
        "lever": (spec.LEVER_HOLES[1], drawing.LEVER_CALLOUT_XY),
    }
    for name, (hole, anchor) in leaders.items():
        start = _on_sheet(*hole)
        ax, ay = anchor[0] * 1000.0, anchor[1] * 1000.0
        side = -1.0 if start[0] < ax else 1.0
        end = (ax + side * _CALLOUT_HALF_WIDTH, ay - 5.3)
        for dim in drawing.TOP_KEEP:
            tx, ty = _top_text(dim)
            box = (tx - 12.0, ty - 3.0, tx + 12.0, ty + 3.0)
            assert not _segment_hits_box(start, end, box), (name, dim)
        box = _callout_box(anchor)
        for dim in drawing.TOP_KEEP:
            tx, ty = _top_text(dim)
            assert not _boxes_overlap(box, (tx - 6.0, ty - 2.0, tx + 6.0, ty + 2.0)), (
                name,
                dim,
            )



def test_all_four_bores_keep_the_unchanged_size_and_locations() -> None:
    bottom = _features()["bottom_face"]
    assert bottom["normal"] == [0.0, -1.0, 0.0]
    exported = _features()
    for key, (x, y) in spec.PIN_HOLES.items():
        name = f"pin_hole_{key.lower()}"
        feature = exported[name]
        assert feature["axis"] == bottom["normal"]
        assert feature["at"] == [x, 0.0, -y]
        assert feature["dia"] == pytest.approx(
            [spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[1], spec.PIN_HOLE_DIA + spec.PIN_HOLE_BAND[0]]
        )
        assert feature["thru"] is True
        assert "note" in feature["requirements"]
        assert feature["note"] == " ".join(drawing.CALLOUTS_BELOW["PinHoleDia"].splitlines())
        (face,) = requirements_for(drawing)[name].faces
        assert face.contains_x_mm == x
        assert face.contains_z_mm == -y
    assert 0.0 < spec.PIN_CLEARANCE_MIN < spec.PIN_CLEARANCE_MAX


def test_hole_table_sheet_owns_every_location() -> None:
    """#2151 (owner Option B): one native hole table on its own sheet, its
    tagged plan the top view; the CARRIER sheet's edge view carries only the
    thickness."""
    assert drawing.SHEET_NAMES == ("CARRIER", "HOLE TABLE", "HUB CLAMP")
    source = inspect.getsource(drawing._hole_table_sheet)
    assert "SHEET_NAMES[1]" in source
    assert "create_carrier_hole_table(adapter, top, source_model, SOURCE)" in source
    build = inspect.getsource(drawing.build)
    assert build.index("_hole_table_sheet(adapter, source_model)") < build.index(
        "_hub_sheet(adapter)"
    )
    assert "settled_checks=(pin_controls_settled, table_settled, hub_settled)" in build
    assert '"Outer Pin Row Note"' in build
    assert not {"ClY", "CrY", "LeverY1", "LeverY2", "RiserY1", "RiserY2"} & set(drawing.TOP_KEEP)
    for retired in ("_LEFT", "_RIGHT", "_LEVER_STATION", "_BAND", "_CHAIN_PLACES"):
        assert not hasattr(drawing, retired), retired


def test_ream_control_is_read_back_on_the_carrier_sheet() -> None:
    """The 4X REAM's final readback runs in the sheet-1 settled check, on the
    CARRIER sheet, restoring whichever sheet was active. The 1.77 and its
    extension-line cap are gone with A1's corner row (TABLE_ROW_DIMENSIONS)."""
    build = inspect.getsource(drawing.build)
    settled = build[build.index("def pin_controls_settled"):build.index("return await finalize_drawing")]
    assert settled.index("ActivateSheet(SHEET_NAMES[0])") < settled.index(
        "_assert_ream_control(adapter, ream[0])"
    ) < settled.index("finally:")
    assert "ActivateSheet(previous)" in settled.split("finally:")[1]
    assert "PlateNearY" in drawing.TABLE_ROW_DIMENSIONS
    ream = inspect.getsource(drawing._assert_ream_control)
    assert 'CALLOUTS_BELOW["PinHoleDia"]' in ream


def test_hub_clamp_tap_has_its_own_sheet_callout_and_reference_position() -> None:
    """Farm 82129 review: the HUB tap is drilled and tapped at assembly, so it
    is not in the table; its sheet prints its native callout saying so and
    its position from A1 as two parenthesized REFERENCE drawing dimensions."""
    assert drawing.SHEET_NAMES[2] == "HUB CLAMP"
    assert "expected_sheet_names=SHEET_NAMES" in inspect.getsource(drawing.build)
    assert "hub_settled = _hub_sheet(adapter)" in inspect.getsource(drawing.build)
    source = inspect.getsource(drawing._hub_sheet)
    assert "SHEET_NAMES[2]" in source
    assert "add_native_hole_callout" in source
    assert "curate_view_dimensions" not in source
    assert "_append_callout_below(callout, HUB_TAP_NOTE" in source
    assert "_hub_reference_position(adapter, top)" in source
    assert "_strip_thread_class(" in source
    assert "set_callout_lengths_to_three_places(" in source
    assert drawing.HUB_TAP_NOTE.splitlines() == [
        "CLAMPS MHA-CH-13 HUB", "DRILL AND TAP AT ASSEMBLY, TL-00 STEP 10"
    ]
    reference = inspect.getsource(drawing._hub_reference_position)
    for call in ("add_edge_dimension(", "set_arc_endpoints_to_center(", "set_reference_dimension(",
                 "assert_dimension_measures(",
                 'orientation=orientation, entities=(a1, hub)'):
        assert call in reference, call
    # Drawing-native only: no model dimension or part write, and no
    # drawing-owned places (_drawing_contract: a *_spec value only).
    assert "SetPrecision3" not in reference
    for forbidden in ("SystemValue =", "SetSystemValue", "Parameter(", "SetValue"):
        assert forbidden not in reference, forbidden
    assert spec.HUB[0] == spec.LEVER_HOLES[0][0] == 0.0
    assert not hasattr(drawing, "HUB_KEEP")
    for retired in ("_left_clamp_sheet", "_left_clamp_depth_callout", "_trace_left_clamp_callout"):
        assert not hasattr(drawing, retired), retired
    assert "_require_left_clamp_thread_min" not in Path(drawing.__file__).read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("axis", ["X", "Y"])
def test_hub_reference_text_and_dimension_line_are_outside_plate(axis) -> None:
    """4031a82a S3: reserve whole text/arrow envelopes, not just an anchor.

    This is an offline paper-layout contract, not a native ink measurement.
    The unchanged single-line parenthesized references get a conservative
    16 x 16 mm text reservation (including either text orientation), and
    their dimension lines get 3 mm arrow/tail clearance on every side.
    Native extension lines must still reach the two hole centres inside.
    """
    x0, y0 = _on_sheet(spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
    x1, y1 = _on_sheet(spec.OUTLINE_X[1], spec.OUTLINE_Y[1])
    plate = (x0, y0, x1, y1)
    mx, _zero, minus_my = drawing.HUB_REFERENCE_TEXT_MODEL_MM[axis]
    tx, ty = _on_sheet(mx, -minus_my)
    a1, hub = (_on_sheet(*point) for point in (drawing._A1, spec.HUB))
    if axis == "X":
        ends = ((a1[0], ty), (hub[0], ty))
        assert ty == pytest.approx(y0 - 18.0)
        assert ty + 8.0 <= y0 - 3.0
        assert min(a1[0], hub[0]) + 8.0 < tx < max(a1[0], hub[0]) - 8.0
    else:
        ends = ((tx, a1[1]), (tx, hub[1]))
        assert tx == pytest.approx(x1 + 28.0)
        assert tx - 8.0 >= x1 + 3.0
        assert min(a1[1], hub[1]) + 8.0 < ty < max(a1[1], hub[1]) - 8.0
    text_box = (tx - 8.0, ty - 8.0, tx + 8.0, ty + 8.0)
    line_box = (
        min(p[0] for p in ends) - 3.0,
        min(p[1] for p in ends) - 3.0,
        max(p[0] for p in ends) + 3.0,
        max(p[1] for p in ends) + 3.0,
    )
    # Reserve the complete four-row native callout/instructions and its
    # shoulder, not only the ordinary two-row _callout_box approximation:
    # its widest row (r8: 40 glyphs at ~2.53 mm, the render's) sets the width.
    callout_x, callout_y = (v * 1000.0 for v in drawing.HUB_CALLOUT_XY)
    half = 2.53 * max(map(len, drawing.HUB_TAP_NOTE.splitlines())) / 2.0
    assert half > 36.0
    callout = (callout_x - half, callout_y - 16.0,
               callout_x + half, callout_y + 16.0)
    iso_x, iso_y = (v * 1000.0 for v in drawing.ISO_CENTER)
    iso = (iso_x - 30.0, iso_y - 18.0, iso_x + 30.0, iso_y + 18.0)
    note_x, note_y = (v * 1000.0 for v in drawing.ISO_NOTE_XY)
    caption = (note_x, note_y - 4.0,
               note_x + 2.36 * len(spec.ISOMETRIC_VIEW_NOTE), note_y + 4.0)
    for box in (text_box, line_box):
        assert _BORDER[0] + 3.0 < box[0] < box[2] < _BORDER[2] - 3.0
        assert _BORDER[1] + 3.0 < box[1] < box[3] < _BORDER[3] - 3.0
        for keepout in (plate, _TITLE_BLOCK, callout, iso, caption):
            assert not _boxes_overlap(box, keepout), (axis, box, keepout)
    assert not _segment_hits_box(*ends, plate)


@pytest.mark.parametrize("fault", [None, "prefix", "suffix", "show_parenthesis", "arc_end", "wrong_value"])
def test_hub_reference_position_is_parenthesized_between_actual_edges(monkeypatch, fault):
    """Fake-driven (not native): the two dimensions run between the A1 and
    HUB edges, on both axes, measure HUB - A1, and their settled readback
    refuses a lost or doubled parenthesis, centred end or value."""
    a1, hub, created, displays, measured = object(), object(), [], [], []
    settled = {"wrong": False}

    class Display:
        def __init__(self):
            # Document "parentheses by default": ShowParenthesis starts True.
            self.text, self.places, self.ShowParenthesis = {}, 2, True
            self.model = SimpleNamespace(GetArcEndCondition=lambda _i: 1, DrivenState=1)

        def GetAnnotation(self):
            return self

        def GetDimension2(self, _index):
            return self.model

        def SetText(self, part, text):
            self.text[part] = text

        def GetText(self, part):
            return self.text.get(part, "")

        def SetPrecision3(self, *_args):
            raise AssertionError("the sheet must not own the reference places")

        def GetPrimaryPrecision2(self):
            return self.places

        def GetUseDocPrecision(self):
            return True

        def IsReferenceDim(self):
            return True

    def add(_adapter, _view, **kwargs):
        created.append(kwargs)
        displays.append(Display())
        return displays[-1]

    def measures(_adapter, display, *, expected_mm, label, entities):
        measured.append((label, expected_mm, entities))
        if settled["wrong"]:
            raise RuntimeError(f"{label} measures the wrong value")

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    def to_sheet(xyz):
        return tuple(v / 1000.0 for v in _on_sheet(xyz[0], -xyz[2]))

    monkeypatch.setattr(drawing, "_view_mapper", lambda *_: to_sheet)
    monkeypatch.setattr(drawing, "_circle_edge", lambda _a, _v, dia, *_a2, **_k: a1 if dia == spec.PIN_HOLE_DIA else hub)
    monkeypatch.setattr(drawing, "add_edge_dimension", add)
    monkeypatch.setattr(drawing, "set_arc_endpoints_to_center", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "set_reference_dimension",
                        lambda _adapter, display, **_k: (display.SetText(1, "("), display.SetText(2, ")")))
    monkeypatch.setattr(drawing, "assert_dimension_measures", measures)
    check = drawing._hub_reference_position(SimpleNamespace(), object())
    assert [item["orientation"] for item in created] == ["horizontal", "vertical"]
    assert all(item["entities"] == (a1, hub) for item in created)
    for axis, item in zip(("X", "Y"), created, strict=True):
        assert item["text_xy"] == pytest.approx(
            to_sheet(drawing.HUB_REFERENCE_TEXT_MODEL_MM[axis])
        )
        assert item["p0"] == pytest.approx(to_sheet(drawing._xy(*drawing._A1)))
        assert item["p1"] == pytest.approx(to_sheet(drawing._xy(*spec.HUB)))
    assert all(display.text == {1: "(", 2: ")"} for display in displays)
    assert all(display.ShowParenthesis is False for display in displays)
    a1x, a1y = spec.PIN_HOLES["A1"]
    assert [expected for _label, expected, _entities in measured] == pytest.approx(
        [abs(spec.HUB[0] - a1x), abs(spec.HUB[1] - a1y)]
    )
    assert all(entities == (a1, hub) for _label, _expected, entities in measured)
    if fault == "prefix":
        displays[0].text[1] = ""
    elif fault == "suffix":
        displays[1].text[2] = ""
    elif fault == "show_parenthesis":
        displays[0].ShowParenthesis = True
    elif fault == "arc_end":
        displays[0].model = SimpleNamespace(GetArcEndCondition=lambda _i: 0)
    elif fault == "wrong_value":
        settled["wrong"] = True
    if fault is None:
        check()
        return
    with pytest.raises(RuntimeError):
        check()
