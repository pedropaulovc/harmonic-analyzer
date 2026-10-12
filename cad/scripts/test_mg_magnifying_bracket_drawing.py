"""Offline contracts for the magnifying-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import build_mg_magnifying_bracket as part
import draw_mg_magnifying_bracket as drawing
import mg_magnifying_bracket_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-bracket_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_bracket"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_bracket_spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is mg_magnifying_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.BACK_KEEP)
        | set(drawing.RIGHT_KEEP) | set(drawing.RIGHT_SECTION_KEEP)
    )
    assert kept == marked
    assert marked == {
        "CollarOd", "CollarBore", "CollarLen",
        "ArmWidth", "ArmDepth", "FlangeWidth", "FlangeDepth", "FlangeHeight",
        "MountingX0", "MountingX1", "MountingY0",
        "ArmThickness", "ArmBelowAxis", "ArmOffset", "SeatToAxis",
    }


def test_arm_and_flange_dim_names_are_disambiguated() -> None:
    # Arm + flange are both extruded rectangles emitting bare "Width"/"Depth";
    # the build renames them per-feature so the top view's keep map is
    # unambiguous.  The collision would otherwise repoint the wrong dimension.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"ArmWidth", "ArmDepth"' in source
    assert '"FlangeWidth", "FlangeDepth"' in source


def test_bracket_is_uncoupled_from_the_assembly_nominals() -> None:
    # The magnifier assembly places the bracket BY NAME and mates it by named
    # references, so it imports no bracket Python constant -- hence one _spec
    # module is right (no _geom split).
    assert not Path(part.__file__).with_name("magnifying_bracket_geom.py").exists()
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from build_mg_magnifying_bracket import" not in assembly


def test_notes_carry_only_what_no_marked_dim_shows() -> None:
    import mg_lever_press_fit_geom as press
    notes = mg_magnifying_bracket_spec.DRAWING_NOTES
    # The collar's OD, length and bore (with its band), the arm section and the
    # mounting pattern are native dimensions now; the notes carry the press and
    # its retention -- the press contract's own three lines, shared with the
    # lever print -- plus the floor exception.
    assert "Ø12" not in notes and "Ø6.2" not in notes and "Ø5.9" not in notes
    assert "SLIP" not in notes and "GUIDE" not in notes
    assert "ARM 10" not in notes and "SEAT ON SUMMING" not in notes
    lines = notes.splitlines()
    assert lines[:3] == press.PRESS_INSTALLATION_NOTES.splitlines()
    assert "LOCTITE 638" in notes and "SOFT SOLDER OR BRAZE" in notes
    assert f"{press.PRESS_FORCE_MAX_KN:.1f} kN MAX" in notes
    assert "LEVER" in notes
    assert "AISI 1018" not in notes
    assert "BLACK-OXIDE" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes and "X.XXX" not in notes
    assert "MATCH-DRILLED" not in notes
    assert "THICKNESS" not in notes
    assert "#4" not in notes and "CENTRES" not in notes
    assert "UNDRILLED" not in notes and "DO NOT RELEASE" not in notes
    assert len(lines) == 4


def test_collar_press_seat_is_native_and_reads_the_press_contract() -> None:
    """The bore nominal and band are mg_lever_press_fit_geom's (one config-free
    read point for the joint; the collar length stays the configured station's);
    the build models the annulus on the Right plane so the end view imports
    both circles, and sets the band on the bore natively."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as lever

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert part.COLLAR_BORE_DIA is press.COLLAR_BORE_DIA
    assert part.COLLAR_BORE_BAND is press.COLLAR_BORE_BAND
    assert part.COLLAR_HALF_LEN is lever.COLLAR_HALF_LEN
    assert 2.0 * part.COLLAR_HALF_LEN == press.PRESS_ZONE_LENGTH
    assert "from mg_lever_press_fit_geom import COLLAR_BORE_BAND, COLLAR_BORE_DIA" in source
    assert "COLLAR_BORE = " not in source  # no bracket-side copy of the bore
    assert 'await adapter.create_sketch("Right")' in source
    assert 'names=(None, None, "CollarOd")' in source
    assert 'names=(None, None, "CollarBore")' in source
    assert "ExtrusionParameters(depth=2.0 * COLLAR_HALF_LEN, both_directions=True)" in source
    assert 'name_dimensions(adapter, "Collar", ["CollarLen"])' in source
    assert "create_revolve" not in source
    assert (
        '"CollarProfile", "CollarBore", *deviations(COLLAR_BORE_BAND)' in source
    )
    assert "(COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE_DIA / 2.0) ** 2" in source
    assert part.DRAWING_PRECISION["CollarProfile"] == {"CollarOd": 2, "CollarBore": 3}
    assert part.DRAWING_PRECISION["Collar"] == {"CollarLen": 2}
    assert drawing.RIGHT_KEEP.keys() == {"CollarOd", "CollarBore"}
    assert "CollarLen" in drawing.TOP_KEEP
    assert drawing.RIGHT_CALLOUTS.keys() == {"CollarOd", "CollarBore"}
    # Policy rule 6: the fit bore names its process; the mate is the lever
    # part, by number and name (machinist review: "rod" read as another part).
    bore_callout = drawing.RIGHT_CALLOUTS["CollarBore"]
    assert "REAM OR BORE" in bore_callout
    assert "MHA-MG-003 LEVER" in bore_callout
    assert "ROD" not in bore_callout
    assert all(len(row) <= 24 for row in bore_callout.splitlines())
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(adapter, right_annotations, RIGHT_CALLOUTS)" in drawing_source


def test_collar_bore_takes_the_center_mark() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("auto_center_marks(") == 1
    assert "curate_hidden_dimensions(" in source
    assert "add_native_hole_callout(" in source


def test_mounting_pattern_consumes_joint_contract() -> None:
    import magnifying_bracket_joint_layout as joint
    assert part.FLANGE_X is joint.SIDE_PLATE_X
    assert part.FLANGE_Y is joint.SIDE_PLATE_Y
    assert part.FLANGE_Z is joint.SIDE_PLATE_Z
    assert part.BRACKET_HOLE_POINTS is joint.BRACKET_HOLE_POINTS
    assert part.CLEARANCE_SPEC is joint.CLEARANCE_SPEC
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="MountingCounterbores"' in source
    assert "(0.0, 0.0, -1.0)" in source
    assert "cut_volume" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-bracket")
    # One stock, both keys (parent ruling): the collar's press budget is
    # computed for 1018 cold-drawn (mg_lever_press_fit_geom.COLLAR_YIELD_MPA).
    assert config["material"] == config["material_specification"]
    assert config["material"] == "LOW-CARBON STEEL (1018, COLD-DRAWN)"
    assert config["finish"]
    assert int(config["quantity"]) == 1
    # The collar is a press seat, not a running fit (user ruling 2026-10-11).
    assert "fit_class" not in config
    assert "1018 cold-drawn solid stock" in config["process"]
    assert "reamed or bored" in config["process"]
    assert "press seat for the MHA-MG-003 lever rod" in config["process"]


def test_mounting_rim_scan_uses_back_visible_entry_plane(monkeypatch) -> None:
    from types import SimpleNamespace
    import magnifying_bracket_joint_layout as joint
    front = object()
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    def scan(view, *, label):
        assert view is front
        return SimpleNamespace(circle_at=circle_at)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    assert len(drawing._mounting_rims(front)) == len(joint.BRACKET_HOLE_POINTS)
    assert [call[0] for call in calls] == [
        (point[0], point[1], joint.SIDE_PLATE_Z[0])
        for point in joint.BRACKET_HOLE_POINTS
    ]
    assert all(call[1] == joint.COUNTERBORE_DIA / 2.0 for call in calls)


def test_counterbore_volume_and_native_bands() -> None:
    import magnifying_bracket_joint_layout as joint
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "CLEARANCE_DIA ** 2 * SIDE_PLATE_THICKNESS" in source
    assert "(COUNTERBORE_DIA ** 2 - CLEARANCE_DIA ** 2) * COUNTERBORE_DEPTH" in source
    assert joint.CLEARANCE_DIA == 2.591
    assert joint.COUNTERBORE_DIA == 3.8
    assert joint.COUNTERBORE_DEPTH == 1.55
    assert joint.SIDE_PLATE_THICKNESS == 3.175
    assert joint.PLATE_THICKNESS_BAND == 0.05
    assert joint.COUNTERBORE_DEPTH_BAND == 0.05
    assert '"FlangeProfile", "FlangeDepth", PLATE_THICKNESS_BAND' in source
    assert '"MountingCounterbores", native_names["CounterBoreDepth"], COUNTERBORE_DEPTH_BAND' in source
    assert '"MountingCounterbores", native_names["CounterBoreDiameter"], 0.0, 0.10' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert part.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"] == 3
    assert "MountingCounterbores" not in part.DRAWING_PRECISION
    assert "#4" not in source


def test_counterbore_entry_view_callout_and_feature_origin() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Back", *BACK_CENTER' in source
    assert 'process="DRILL / COUNTERBORE"' in source
    assert "set_hidden_lines_removed(adapter, back)" in source
    assert '"MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0")' in source
    assert "curate_hidden_dimensions(" in source
    # The callout hangs below the back view.  AddHoleCallout2 centres its
    # ~117 mm bottom row on x and runs the leader from the counterbore rim to
    # an elbow 2 mm before the row end nearer the hole: below the view that is
    # the row's LEFT end, so the hole must sit left of the elbow for the leader
    # to leave it up-left, outside its own row (retry08 native audit, centred
    # at x 300 mm: the leader cut 3.3 mm of its own row and crossed the 6.35's
    # lower witness, which ends 1 mm left of the hole), and the leader must
    # thread between the 4.00's witnesses at the hole and the flange end,
    # which reach 5.4 mm below the hole centre, on its way to the rim.
    import magnifying_bracket_joint_layout as joint
    assert "callout_xy=(0.337, 0.078)" in source
    callout_x, callout_y = 0.337, 0.078
    # Back mirrors X about the flange's mid-X: sheet x = centre - (X - mid).
    flange_mid_x = (part.FLANGE_X[0] + part.FLANGE_X[1]) / 2.0 / 1000.0
    hole_x = drawing.BACK_CENTER[0] - (joint.BRACKET_HOLE_POINTS[0][0] / 1000.0 - flange_mid_x)
    flange_end_x = drawing.BACK_CENTER[0] - (part.FLANGE_X[0] / 1000.0 - flange_mid_x)
    hole_y = drawing.BACK_CENTER[1]
    assert abs(hole_x - 0.265) < 1e-9 and abs(flange_end_x - 0.269) < 1e-9
    elbow = (callout_x - 0.0606, callout_y - 0.0073)
    assert elbow[0] > hole_x + 0.005  # the leader climbs up-left from the elbow
    witness_bottom = hole_y - 0.0054
    dx, dy = hole_x - elbow[0], hole_y - elbow[1]
    leader_x = elbow[0] + dx * (witness_bottom - elbow[1]) / dy
    assert hole_x + 0.001 < leader_x < flange_end_x - 0.001
    assert leader_x > hole_x - 0.001 + 0.002  # right of the 6.35 witness' end
    assert drawing.BACK_KEEP["MountingX0"][1] > 0.107 > callout_y


def test_coordinates_and_hole_dimensions_are_owned_by_model() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "start = (FLANGE_X[0], FLANGE_Y[0])" in source
    assert 'name_last_feature(adapter, "MountingCoordinates")' in source
    assert 'set_dimension_symmetric_tolerance(adapter, "MountingCoordinates", name, POSITION_BAND)' in source
    assert "model.BlankSketch()" in source
    assert "feature.GetFirstDisplayDimension()" in source
    assert "feature.GetNextDisplayDimension(display)" in source
    assert "resolved[name] = str(dimensions[0].Name)" in source
    assert "dimensions[0].Name =" not in source
    assert "expected one native" in source
    assert mg_magnifying_bracket_spec.DRAWING_POSITION_BAND == 0.05
    assert f"COUNTERBORE FLOOR {mg_magnifying_bracket_spec.GRIP_MIN:.3f} MIN." in mg_magnifying_bracket_spec.DRAWING_NOTES


def test_flange_height_is_native_and_primary_views_stay_aligned() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'height = flange.Parameter("D1")' in source
    assert 'height.Name = "FlangeHeight"' in source
    assert "(FLANGE_Y[1] - FLANGE_Y[0])" in source
    assert part.DRAWING_PRECISION["Flange"]["FlangeHeight"] == 2
    assert drawing.FRONT_KEEP.keys() == {"FlangeHeight"}
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.BACK_CENTER[0] != drawing.FRONT_CENTER[0]
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", *FRONT_CENTER' in drawing_source


def test_arm_section_is_native_and_locates_the_bore_axis() -> None:
    """The arm's thickness and its position across the flange print from a
    blanked ArmSection witness on the Right plane (sketch (u, v) -> model
    (-Z, Y)), not from a note; the bore axis is located from the seat face.
    Offline source contract only: the native import still wants farm proof."""
    import pytest
    import magnifying_bracket_joint_layout as joint
    source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Model directions the dimensions rely on: the arm sits 3.00 below the bore
    # axis and 3.35 above the flange's hole-datum (lower) face, 7.50 thick; the
    # seat face is the flange's +Z face, the summing installation's seat plane.
    assert part.ARM_Y == (-3.0, 4.5)
    assert -part.ARM_Y[0] == 3.0
    assert part.ARM_Y[1] - part.ARM_Y[0] == 7.5
    assert part.ARM_Y[0] - part.FLANGE_Y[0] == pytest.approx(3.35)
    assert part.FLANGE_Z[1] == joint.SIDE_PLATE_Z[1]
    assert part.ARM_Z[1] > part.FLANGE_Z[1]  # the arm's end stands past the seat
    assert "seat_u = -FLANGE_Z[1]" in source
    assert "end_u = -ARM_Z[1]" in source
    assert "_make_construction(adapter, line)" in source
    # The bore axis, extended to the arm's end station as a centerline, so the
    # 3.00 reads off its end there with short witnesses (not back to the
    # collar's centre through the arm).
    assert "await adapter.add_centerline(end_u, 0.0, 0.0, 0.0)" in source
    assert 'f"{axis}.start", f"{end}.start", "vertical_points"' in source
    assert 'f"{end}.start", f"{axis}.start", "vertical_distance"' in source
    # Each seat piece's arm-side corner sits on the arm face it was drawn at:
    # the piece below the arm ends on the arm's LOWER face (end.start), the
    # piece above starts on its upper face (end.end).  Same-named pairing
    # (below.end with end.end) dragged the lower piece up to the arm's top and
    # ArmOffset re-solved its seat-face witness to Y +0.35, above the bore
    # axis (retry08 native audit: extension line at sheet y 180.4 mm).
    assert '(below, "end", "start"),' in source
    assert '(above, "start", "end"),' in source
    assert 'f"{piece}.{corner}", f"{end}.{arm_corner}", "horizontal_points"' in source
    assert 'f"{piece}.{corner}", f"{end}.{corner}"' not in source
    assert """section.record("ArmThickness", '"ArmY1" - "ArmY0"')""" in source
    assert """section.record("ArmBelowAxis", '-"ArmY0"')""" in source
    assert """section.record("ArmOffset", '"ArmY0" - "FlangeY0"')""" in source
    assert """section.record("SeatToAxis", '"FlangeZ1"')""" in source
    assert 'name_last_feature(adapter, "ArmSection")' in source
    assert 'blank_reference_sketches(adapter, ("ArmSection",))' in source
    assert mg_magnifying_bracket_spec.DRAWING_DIMENSIONS["ArmSection"] == {
        "ArmThickness", "ArmBelowAxis", "ArmOffset", "SeatToAxis",
    }
    assert part.DRAWING_PRECISION["ArmSection"] == {
        "ArmThickness": 2, "ArmBelowAxis": 2, "ArmOffset": 2, "SeatToAxis": 2,
    }
    assert drawing.RIGHT_SECTION_KEEP.keys() == {
        "ArmThickness", "ArmBelowAxis", "ArmOffset", "SeatToAxis",
    }
    assert "keep=RIGHT_SECTION_KEEP" in drawing_source
    # Every import is targeted (the entire-model fallback warned on four
    # views); the back view keeps no model dimension, so it imports none.
    assert drawing_source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 4
    assert "keep={}" not in drawing_source
    assert "set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)" in drawing_source
    # ArmOffset is a LINEAR reference: the plural helper's "(<MOD-DIAM>"
    # prefix printed it as "(Ø3.35)" on retry08.
    assert "set_reference_dimensions(" not in drawing_source
    assert "for name in SECTION_REFERENCE:" in drawing_source
    assert 'set_reference_dimension(adapter, matches[0], label=f"arm section {name}")' in drawing_source
    assert drawing.SECTION_REFERENCE == ("ArmOffset",)
    assert drawing.SECTION_CALLOUTS["ArmThickness"] == "ARM THICKNESS"
    assert "BORE AXIS" in drawing.SECTION_CALLOUTS["ArmBelowAxis"]
    assert "SEAT FACE" in drawing.SECTION_CALLOUTS["SeatToAxis"]
    assert "ArmOffset" not in drawing.SECTION_CALLOUTS
    # The section's witnesses run left of the arm's end (x 207.85 mm), its
    # texts outside the view: the thickness and seat-face dimensions above
    # (y > 191.9 mm), the two from the arm's lower face below (y < 168.1 mm).
    right = drawing.RIGHT_SECTION_KEEP
    assert all(right[name][0] < 0.20785 for name in ("ArmThickness", "ArmBelowAxis", "ArmOffset"))
    assert right["ArmThickness"][1] > 0.1919 and right["SeatToAxis"][1] > 0.1919
    assert right["ArmBelowAxis"][1] < 0.1681 and right["ArmOffset"][1] < 0.1681
    assert right["ArmOffset"][0] < right["ArmThickness"][0] < right["ArmBelowAxis"][0]
    # Hung text (retry08 native audit): rows requested beyond a vertical
    # dimension's span print LEFT of its column, as wide as the widest row,
    # on a shoulder at the lowest row's baseline (the value row at the
    # requested y, a callout row 5.56 mm under it; a lone row 2.78 mm under).
    # "FROM BORE AXIS" printed over x 167.6..204.7 mm from its x 205 column;
    # "(Ø3.35)" ran a 20.4 mm shoulder from x 167 to 146.6 mm, across the top
    # view's 54.30 column at x 147 mm (enforced shoulder-crosses-line), its
    # text 2.5 mm from the 3.00's rows (text-separation).
    row = 0.00556
    text = 0.0035
    below_axis_row = 0.0378  # "FROM BORE AXIS", shoulder width
    offset_row = 0.0152  # "(3.35)": the 20.4 mm "(Ø3.35)" shoulder less the Ø glyph
    thickness_x, thickness_y = right["ArmThickness"]
    below_x, below_y = right["ArmBelowAxis"]
    offset_x, offset_y = right["ArmOffset"]
    arm_depth_column = drawing.TOP_KEEP["ArmDepth"][0]
    # The reference offset's shoulder clears the 54.30 column by a text height,
    # and by a line weight even if the Ø glyph's 5.3 mm were not saved.
    assert offset_x - offset_row > arm_depth_column + text
    assert offset_x - (offset_row + 0.0053) > arm_depth_column + 0.0005
    # and its text clears the 3.00's rows by one (its box ends 1.9 mm before
    # its shoulder's end; the rows' box starts 0.4 mm after theirs).
    assert (below_x - below_axis_row + 0.0004) - (offset_x - 0.0019) > text
    # Its dimension line ends at its single row, above the 3.00's shoulder, so
    # neither can cross the other, and its text sits a text height and more
    # under its own witness along the hole-datum face (y 173.65 mm).
    assert offset_y - row / 2.0 > below_y - row + 0.002
    assert offset_y - row / 2.0 + 0.0045 < 0.17365 - text
    # Its column stands clear of the 3.00's rows by the 2 mm arrow-to-text
    # clearance and left of the thickness' witnesses (which end 1 mm past
    # its column), so the offset's outside-arrow tail (6.35 mm past y 177 mm)
    # crosses neither.
    assert offset_x < below_x - below_axis_row + 0.0004 - 0.002
    assert offset_x < thickness_x - 0.001 - 0.002
    # The thickness' shoulder (lowest row's baseline) sits above every other
    # column's reach: the offset's tail ends 6.35 mm over the arm's lower face.
    assert thickness_y - row > 0.177 + 0.00635 + 0.002
    # The 54.30's column clears the arm's x 139 mm edge and the rows it hangs
    # right of it (x ~142..171 mm, y 135.4..146.5 mm) stay a text height and
    # more under the offset's text.
    assert arm_depth_column > 0.139 + 0.0025
    assert offset_y - row / 2.0 > drawing.TOP_KEEP["ArmDepth"][1] + 0.0045 + text
    # The bore's three-row callout (rows ~65 mm wide, x ~198..263 mm) keeps
    # its v41 column below-left of the collar: its block must clear the
    # collar's x (266.15 mm) on one side or the leader from the bore's rim to
    # the shoulder's near end cuts through its own rows (layout audit
    # leader-through-text), and right of the collar is the isometric.  Its
    # top stays a text height and more under the 3.00's rows.
    bore_x, bore_y = drawing.RIGHT_KEEP["CollarBore"]
    assert bore_x + 0.0325 < 0.26615
    assert bore_y + 0.008 < right["ArmBelowAxis"][1] - 0.0045 - 0.0035
    assert bore_y - 0.008 > 0.13375 + 0.0035  # above the back view's 36.00


def test_collar_length_and_arm_length_read_on_their_own_features() -> None:
    """Machinist review: 10.00 vs Ø12 read as one feature, and the 54.30 sat
    under two foreign witness lines.  The collar's length reads above the
    collar it measures (top view +Z runs down: collar top at y 212.1 mm),
    named along the bore axis; the arm's length text slides below the arm's
    end (y 147.8 mm) and its column right of the x 139 mm witnesses."""
    assert "ALONG BORE AXIS" in drawing.DIMENSION_CALLOUTS["CollarLen"]
    assert drawing.TOP_KEEP["CollarLen"][1] > 0.2121
    assert drawing.TOP_KEEP["CollarLen"][0] > 0.139
    assert drawing.TOP_KEEP["ArmDepth"][1] < 0.1478
    assert drawing.TOP_KEEP["ArmDepth"][0] > 0.139 + 0.00175
    assert drawing.TOP_KEEP["FlangeWidth"][0] < drawing.TOP_KEEP["CollarLen"][0]


def test_native_counterbore_dimensions_keep_names_and_route_annotations(monkeypatch) -> None:
    """Offline routing contract, not proof of native SOLIDWORKS geometry."""
    from types import SimpleNamespace
    import pytest
    import _appearance
    import _com
    import _custom_properties
    import _feature_tree
    import _part_checks
    import _part_properties
    import _part_save
    import _rebuild
    import _session
    import _sketch
    import _sketch_rectangle

    class WizardDimension:
        def __init__(self, full_name, nominal):
            self.FullName = full_name
            self.SystemValue = nominal / 1000.0

        @property
        def Name(self):
            return self.FullName.split("@")[0]

        @Name.setter
        def Name(self, value):
            raise AssertionError("Hole Wizard dimension identifiers must not be renamed")

    height = SimpleNamespace(Name="D1", SystemValue=12.7 / 1000.0)
    native = [
        WizardDimension("Thru Hole Dia.@MountingCounterbores", 2.591),
        WizardDimension("Counterbore Dia.@MountingCounterbores", 3.8),
        WizardDimension("Counterbore Depth@MountingCounterbores", 1.55),
    ]
    original_names = [dim.Name for dim in native]
    displays = [SimpleNamespace(GetDimension=lambda dim=dim: dim) for dim in native]
    holes = SimpleNamespace(
        GetFirstDisplayDimension=lambda: displays[0] if displays else None,
        GetNextDisplayDimension=lambda current: (
            displays[displays.index(current) + 1]
            if displays.index(current) + 1 < len(displays) else None
        ),
    )
    features = {
        "Flange": SimpleNamespace(Parameter=lambda name: height if name == "D1" else None),
        "MountingCounterbores": holes,
    }
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))
    monkeypatch.setattr(_appearance, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_custom_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_feature_tree, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_checks, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_save, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_rebuild, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_session, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch_rectangle, "_early_bound", lambda value, interface: value)
    resolved = part._resolve_native_mounting_dimensions(adapter)
    assert height.Name == "FlangeHeight"
    assert resolved == {
        "HoleDiameter": "Thru Hole Dia.",
        "CounterBoreDiameter": "Counterbore Dia.",
        "CounterBoreDepth": "Counterbore Depth",
    }
    calls = []
    monkeypatch.setattr(part, "set_dimension_symmetric_tolerance", lambda *args: calls.append(("symmetric", args)))
    monkeypatch.setattr(part, "set_dimension_bilateral_tolerance", lambda *args: calls.append(("bilateral", args)))
    monkeypatch.setattr(part, "set_dimension_display_precision", lambda *args: calls.append(("precision", args)))
    part._apply_native_mounting_annotations(adapter, resolved)
    assert calls == [
        ("symmetric", (adapter, "MountingCounterbores", "Counterbore Depth", 0.05)),
        ("bilateral", (adapter, "MountingCounterbores", "Counterbore Dia.", 0.0, 0.10)),
        ("precision", (adapter, "MountingCounterbores", "Thru Hole Dia.", 3)),
        ("precision", (adapter, "MountingCounterbores", "Counterbore Dia.", 2)),
        ("precision", (adapter, "MountingCounterbores", "Counterbore Depth", 2)),
    ]
    assert [dim.Name for dim in native] == original_names
    duplicate = WizardDimension("Second Counterbore Dia.@MountingCounterbores", 3.8)
    displays.append(SimpleNamespace(GetDimension=lambda: duplicate))
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 2"):
        part._resolve_native_mounting_dimensions(adapter)
    displays.pop()
    missing = displays.pop(1)
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    displays.insert(1, missing)
    native[1].SystemValue = 3.9 / 1000.0
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    native[1].SystemValue = 3.8 / 1000.0
    native[1].FullName = "Counterbore Depth@MountingCounterbores"
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    assert height.Name == "FlangeHeight"


def test_final_forced_volume_guard_follows_annotations_before_publication() -> None:
    """Source ordering only; the parent must still validate rebuilt native geometry."""
    import ast

    source = Path(part.__file__).read_text(encoding="utf-8")
    build = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    rebuild, guard, publish = build.body[-3:]
    assert isinstance(rebuild, ast.Expr) and isinstance(rebuild.value, ast.Await)
    assert rebuild.value.value.func.id == "force_rebuild"
    assert isinstance(guard, ast.Expr) and isinstance(guard.value, ast.Await)
    call = guard.value.value
    assert call.func.id == "volume_check"
    assert call.args[1].value == "final magnifying-bracket (annotations neutral)"
    assert call.args[2].id == "expected"
    assert ast.unparse(call.args[3]) == "0.02 * cut_volume"
    assert isinstance(publish, ast.Return) and isinstance(publish.value, ast.Await)
    assert publish.value.value.func.id == "save_part_and_images"
    for mutation in (
        "_resolve_native_mounting_dimensions",
        "_mounting_coordinate_dimensions",
        "set_dimension_symmetric_tolerance",
        "_apply_native_mounting_annotations",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "apply_drawing_properties",
        "blank_reference_sketches",
    ):
        calls = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == mutation
        ]
        assert calls, mutation
        assert all(node.lineno < rebuild.lineno for node in calls), mutation
