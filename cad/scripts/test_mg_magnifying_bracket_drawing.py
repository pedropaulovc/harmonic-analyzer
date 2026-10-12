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
        set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP) | set(drawing.BOTTOM_HOLE_KEEP)
        | set(drawing.SIDE_KEEP) | set(drawing.SIDE_SECTION_KEEP)
    )
    assert kept == marked
    # The arm's depth (54.30 from a start buried inside the collar) is not
    # marked: the arm's end is located from the bore axis instead (mreview09
    # blocker 3, the collar located twice from different origins).
    assert marked == {
        "CollarOd", "CollarBore", "CollarLen",
        "ArmWidth", "FlangeWidth", "FlangeDepth", "FlangeHeight",
        "MountingX0", "MountingX1", "MountingY0",
        "ArmThickness", "ArmBelowAxis", "ArmOffset", "SeatToAxis", "ArmEndFromAxis",
    }
    assert "ArmDepth" not in marked
    # Every marked dimension prints at a spec'd precision: the mounting
    # coordinates take theirs in _mounting_coordinate_dimensions (two places,
    # with the position band), the rest from DRAWING_PRECISION.
    precise = set().union(*part.DRAWING_PRECISION.values())
    assert marked - precise == {"MountingX0", "MountingX1", "MountingY0"}
    assert precise <= marked


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
    """The bore nominal and bands are mg_lever_press_fit_geom's (one config-free
    read point for the joint; the collar length stays the configured station's,
    banded by the press contract's COLLAR_LENGTH_BAND); the build models the
    annulus on the Right plane so the end view imports both circles, and sets
    the bands on the bore and the extrude natively."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as lever

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert part.COLLAR_BORE_DIA is press.COLLAR_BORE_DIA
    assert part.COLLAR_BORE_BAND is press.COLLAR_BORE_BAND
    assert part.COLLAR_LENGTH_BAND is press.COLLAR_LENGTH_BAND
    assert part.COLLAR_HALF_LEN is lever.COLLAR_HALF_LEN
    assert 2.0 * part.COLLAR_HALF_LEN == press.PRESS_ZONE_LENGTH
    assert (
        "from mg_lever_press_fit_geom import COLLAR_BORE_BAND, COLLAR_BORE_DIA, COLLAR_LENGTH_BAND"
        in source
    )
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
    # The length band is (upper, lower) like the bore's: deviations() orders it
    # for the bilateral helper, which prints "+0.00/-0.05" at the nominal's
    # two places (the fewest that keep 0.05).
    assert '"Collar", "CollarLen", *deviations(COLLAR_LENGTH_BAND)' in source
    assert press.COLLAR_LENGTH_BAND[0] >= press.COLLAR_LENGTH_BAND[1]
    assert press.COLLAR_LENGTH_BAND != (0.0, 0.0)
    assert "(COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE_DIA / 2.0) ** 2" in source
    assert part.DRAWING_PRECISION["CollarProfile"] == {"CollarOd": 2, "CollarBore": 3}
    assert part.DRAWING_PRECISION["Collar"] == {"CollarLen": 2}
    assert drawing.SIDE_KEEP.keys() == {"CollarOd", "CollarBore"}
    assert "CollarLen" in drawing.FRONT_KEEP
    assert drawing.SIDE_CALLOUTS.keys() == {"CollarOd", "CollarBore"}
    # Policy rule 6: the fit bore names its process; the mate is the lever
    # part, by number and name (machinist review: "rod" read as another part).
    bore_callout = drawing.SIDE_CALLOUTS["CollarBore"]
    assert "REAM OR BORE" in bore_callout
    assert "MHA-MG-003 LEVER" in bore_callout
    assert "ROD" not in bore_callout
    assert all(len(row) <= 24 for row in bore_callout.splitlines())
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(adapter, side_annotations, SIDE_CALLOUTS)" in drawing_source


def test_collar_bore_keeps_the_templates_one_center_mark(monkeypatch) -> None:
    """The project template centre-marks the extruded annulus bore as the end
    view is placed; the v41 sheet's explicit auto_center_marks printed a second
    identical mark over it (retry09 native audit: DetailItem351 and 352, both
    at (266.15, 180) mm).  The sheet now adds none and proves exactly one on
    the bore axis: zero or two fail loud, nothing is deleted, and the proof
    reads the mark's own rendered lines (IDisplayData), not an assumption."""
    import ast
    from types import SimpleNamespace
    import pytest

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    adders = {"auto_center_marks", "AutoInsertCenterMarks2", "InsertCenterMark2", "InsertCenterMark3"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not adders & called
    imported = {
        alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    assert "auto_center_marks" not in imported
    assert drawing._CENTER_MARK_ANNOTATION == 13
    assert "_prove_collar_centre_mark(adapter, side)" in source
    assert "curate_hidden_dimensions(" in source
    assert "add_native_hole_callout(" in source

    right = object()
    axis = (0.26615, 0.180)

    def rim(view):
        assert view is right
        # ViewEdge.circle: centre and radius in mm, on the near end face.
        return SimpleNamespace(circle=(5.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.993))

    def project(adapter, view, xyz, *, label):
        assert view is right
        assert xyz == (0.005, 0.0, 0.0)
        return axis

    def mark(centre, reach=0.005493):
        lines = [
            [0, 0, 0, 0, centre[0] - reach, centre[1], 0.0, centre[0] + reach, centre[1], 0.0],
            [0, 0, 0, 0, centre[0], centre[1] - reach, 0.0, centre[0], centre[1] + reach, 0.0],
        ]
        data = SimpleNamespace(GetLineCount=lambda: len(lines), GetLineAtIndex2=lambda i: lines[i])
        return SimpleNamespace(GetDisplayData=lambda: data)

    marks: list = []
    view_api = SimpleNamespace(
        GetAnnotationsByType=lambda kind: list(marks) if kind == 13 else []
    )
    successes = []
    monkeypatch.setattr(drawing, "_collar_bore_rim", rim)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(
        drawing, "_early_bound", lambda obj, interface: view_api if interface == "IView" else obj
    )
    monkeypatch.setattr(drawing._telemetry, "success", lambda message, **fields: successes.append(message))

    with pytest.raises(RuntimeError, match="0 centre marks"):
        drawing._prove_collar_centre_mark(object(), right)
    marks[:] = [mark(axis), mark(axis)]
    with pytest.raises(RuntimeError, match="2 centre marks"):
        drawing._prove_collar_centre_mark(object(), right)
    assert len(marks) == 2
    marks[:] = [mark((axis[0] + 0.001, axis[1]))]
    with pytest.raises(RuntimeError, match="off the bore axis"):
        drawing._prove_collar_centre_mark(object(), right)
    marks[:] = [mark(axis)]
    drawing._prove_collar_centre_mark(object(), right)
    assert successes and "one centre mark" in successes[-1]


def test_collar_bore_rim_is_picked_on_the_near_end_face(monkeypatch) -> None:
    from types import SimpleNamespace
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as lever
    right = object()
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object(), circle=(*center, *axis, radius))

    def scan(view, *, label):
        assert view is right
        return SimpleNamespace(circle_at=circle_at)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    drawing._collar_bore_rim(right)
    # *Right looks from +X: the face at +COLLAR_HALF_LEN carries the visible
    # rims, and the bore (not the OD) is the circle the mark belongs to.
    assert calls == [((lever.COLLAR_HALF_LEN, 0.0, 0.0), press.COLLAR_BORE_DIA / 2.0, (1.0, 0.0, 0.0))]
    assert drawing.COLLAR_HALF_LEN is lever.COLLAR_HALF_LEN
    assert drawing.COLLAR_BORE_DIA is press.COLLAR_BORE_DIA


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


def test_mounting_rim_scan_uses_the_bottom_views_visible_through_rims(monkeypatch) -> None:
    """The aligned bottom view (*Front, viewer +Z) shows the mounting face:
    the counterbores open on the far (-Z) face, so the callout attaches to the
    through holes' rims on the +Z face, which the view can see."""
    from types import SimpleNamespace
    import magnifying_bracket_joint_layout as joint
    bottom = object()
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    def scan(view, *, label):
        assert view is bottom
        return SimpleNamespace(circle_at=circle_at)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    assert len(drawing._mounting_rims(bottom)) == len(joint.BRACKET_HOLE_POINTS)
    assert [call[0] for call in calls] == [
        (point[0], point[1], joint.SIDE_PLATE_Z[1])
        for point in joint.BRACKET_HOLE_POINTS
    ]
    assert all(call[1] == joint.CLEARANCE_DIA / 2.0 for call in calls)
    assert all(call[2] == (0.0, 0.0, 1.0) for call in calls)


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


def test_counterbore_callout_rides_the_aligned_bottom_view() -> None:
    """mreview09: the mirrored *Back view carrying the hole dimensions was a
    duplicate "not a projection of anything above it"; the callout and the
    coordinates move to the aligned bottom view, the duplicate is gone, and
    the callout names the entry side the view cannot show."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "*Back" not in source
    assert "BACK_CENTER" not in source and "BACK_KEEP" not in source
    assert 'process="' not in source
    assert "process=COUNTERBORE_PROCESS" in source
    assert drawing.COUNTERBORE_PROCESS.startswith("DRILL / COUNTERBORE")
    assert "FAR SIDE" in drawing.COUNTERBORE_PROCESS
    assert "\n" not in drawing.COUNTERBORE_PROCESS  # one row: measured geometry
    assert "edge=rims[1].edge" in source  # the east hole, nearer the block
    assert '"MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0")' in source
    assert "keep=BOTTOM_HOLE_KEEP" in source
    # The callout block (retry09, requested (337, 78) mm): the lower,
    # prefixed counterbore row 117.9 mm wide, centred on the requested x,
    # its baseline 7.3 mm under the requested y, the elbow 1.5 mm before its
    # end nearer the hole; the leader runs from that elbow through the hole's
    # centre.  "FAR SIDE" adds about 23 mm to the row.
    import magnifying_bracket_joint_layout as joint
    assert "callout_xy=(0.212, 0.087)" in source
    callout_x, callout_y = 0.212, 0.087
    half_row = (0.1179 + 0.023) / 2.0
    hole = (
        drawing.BOTTOM_CENTER[0] + 0.019 + joint.BRACKET_HOLE_POINTS[1][0] / 1000.0,
        drawing.BOTTOM_CENTER[1] + joint.BRACKET_HOLE_POINTS[1][1] / 1000.0,
    )
    assert abs(hole[0] - 0.1087) < 1e-9 and abs(hole[1] - 0.110) < 1e-9
    elbow = (callout_x - half_row - 0.0015, callout_y - 0.0073)
    row_top = callout_y + 0.0053  # the thru row's box top
    # The block clears the isometric's outline (x 294.7 mm), the iso note
    # (x 315 mm on), the title block (y 66 mm) and the notes' top row (y 69.5
    # mm) by a text height and more, and sits under the flange height's
    # outside-arrow tail (x 148 mm, down to y 97.25 mm).
    assert callout_x + half_row < 0.2947 - 0.0035
    assert callout_y - 0.0073 > 0.0695 + 0.0035
    assert row_top < 0.09725 - 0.0035
    # The leader climbs from the elbow (below-right of the hole) through the
    # hole: at the 17.70's line (y 81 mm, to x 115.1 mm) and the 4.00's (y 89
    # mm, to x 101.4 mm) it is right of both line ends by a text height.
    dx, dy = hole[0] - elbow[0], hole[1] - elbow[1]
    assert dx < 0.0 < dy

    def leader_x(y: float) -> float:
        return elbow[0] + dx * (y - elbow[1]) / dy

    x1_line = drawing.BOTTOM_HOLE_KEEP["MountingX1"][1] - 0.00278
    x0_line = drawing.BOTTOM_HOLE_KEEP["MountingX0"][1] - 0.00278
    assert leader_x(x1_line) > hole[0] + 0.0064 + 0.0035
    assert leader_x(x0_line) > drawing.BOTTOM_CENTER[0] + 0.019 - 0.039 + 0.0064 + 0.0035
    # It leaves the flange through its lower face (y 103.65 mm) between the
    # hole's own witness (x 108.7 mm) and the flange height's witnesses
    # (x 140 mm on), and ends left of that dimension's column (x 148 mm).
    lower_face = drawing.BOTTOM_CENTER[1] + part.FLANGE_Y[0] / 1000.0
    assert hole[0] + 0.002 < leader_x(lower_face) < 0.140 - 0.002
    assert elbow[0] < 0.148 - 0.002


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


def test_flange_height_is_native_and_the_set_is_one_third_angle_projection() -> None:
    """mreview09 blocker 1 / clarity: one aligned front / bottom / right-side
    set.  The front and bottom views share x; the side view is turned so
    model +Z (down the front view) runs down the sheet, +Y left, and pinned
    by its measured origin to the front view's origin height."""
    import math
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'height = flange.Parameter("D1")' in source
    assert 'height.Name = "FlangeHeight"' in source
    assert "(FLANGE_Y[1] - FLANGE_Y[0])" in source
    assert part.DRAWING_PRECISION["Flange"]["FlangeHeight"] == 2
    assert drawing.BOTTOM_KEEP.keys() == {"FlangeHeight"}
    assert drawing.FRONT_CENTER[0] == drawing.BOTTOM_CENTER[0]
    assert drawing.FRONT_CENTER[1] > drawing.BOTTOM_CENTER[1]
    assert drawing.SIDE_CENTER[0] > drawing.FRONT_CENTER[0]
    assert drawing.SIDE_AXIS_X > drawing.FRONT_CENTER[0] + 0.0296 + 0.0035
    assert drawing.FRONT_ORIGIN_Y == drawing.FRONT_CENTER[1] + 0.02615
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Top", *FRONT_CENTER' in drawing_source
    assert '"*Front", *BOTTOM_CENTER' in drawing_source
    assert '"*Right", *SIDE_CENTER' in drawing_source
    assert "_project_side_view(adapter, front, side)" in drawing_source
    # Turned and pinned BEFORE any import, so every placed text is in the
    # final frame.
    assert drawing_source.index("_project_side_view(adapter, front, side)") < drawing_source.index(
        "curate_view_dimensions("
    )
    assert drawing.SIDE_DOWN_AXIS == (0.0, 0.0, 1.0)
    assert drawing.SIDE_LEFT_AXIS == (0.0, 1.0, 0.0)
    assert "native.Angle = float(native.Angle) - math.pi / 2.0 - math.atan2(dy, dx)" in drawing_source
    assert '_require_axis_along(adapter, native, SIDE_DOWN_AXIS, -math.pi / 2.0, "side view +Z")' in drawing_source
    assert '_require_axis_along(adapter, native, SIDE_LEFT_AXIS, math.pi, "side view +Y")' in drawing_source
    assert "target = (SIDE_AXIS_X, front_origin[1])" in drawing_source
    assert "native.SetViewPosition(double_array(moved), False)" in drawing_source
    assert drawing.PROJECTION_TOL_M == 1e-4
    assert drawing.PROJECTION_ANGLE_TOL == 1e-6
    # Every view prints hidden lines removed (clarity: the dashed bore and
    # counterbores only cluttered the front view's 10.00 and 3.175).
    assert "set_hidden_lines_visible" not in drawing_source
    assert "for view in (front, bottom, side, iso):" in drawing_source
    assert math.isclose(drawing.FRONT_ORIGIN_Y, 0.20615)


def test_projection_refuses_unapplied_native_mutators(monkeypatch) -> None:
    """Exercise getter/setter shapes and independent projection readback.

    This fake sits above the binding; retry10 must still prove the real view.
    """
    import math
    import pytest

    class View:
        def __init__(self, result=True, *, ignore_angle=False, ignore_position=False):
            self._angle = 0.37
            self._position = (0.25, 0.17)
            self.result = result
            self.ignore_angle = ignore_angle
            self.ignore_position = ignore_position

        @property
        def Angle(self):
            return self._angle

        @Angle.setter
        def Angle(self, value):
            if not self.ignore_angle:
                self._angle = value

        @property
        def Position(self):
            return self._position

        def SetViewPosition(self, position, move_children):
            assert move_children is False
            if self.result is True and not self.ignore_position:
                self._position = tuple(position)
            return self.result

    front = object()
    front_origin = (0.134, 0.20615)

    def project(adapter, view, xyz, *, label):
        if view is front:
            return front_origin
        # Deliberately distinguish native Position from the projected origin.
        px, py = view.Position[0] + 0.01, view.Position[1] + 0.02
        x, y = xyz[2], -xyz[1]
        cosine, sine = math.cos(view.Angle), math.sin(view.Angle)
        return (px + cosine * x - sine * y, py + sine * x + cosine * y)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing._telemetry, "success", lambda *args, **kwargs: None)

    side = View()
    drawing._project_side_view(object(), front, side)
    assert side.Angle == pytest.approx(-math.pi / 2.0)
    assert project(None, side, (0.0, 0.0, 0.0), label="proof") == pytest.approx(
        (drawing.SIDE_AXIS_X, front_origin[1])
    )
    # A truthy non-BOOL cannot turn a refused move into a successful mutation.
    for result in (False, None, 1, object()):
        with pytest.raises(RuntimeError, match="failed to move"):
            drawing._project_side_view(object(), front, View(result))
    with pytest.raises(RuntimeError, match="side view \\+Z"):
        drawing._project_side_view(object(), front, View(ignore_angle=True))
    with pytest.raises(RuntimeError, match="side view origin sits"):
        drawing._project_side_view(object(), front, View(ignore_position=True))


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
    # The arm's end from the bore axis is the sketch's horizontal_distance
    # from the end face's lower corner to the origin: marked now, in place of
    # the top view's 54.30 from the arm's buried start (mreview09 blocker 3).
    assert 'f"{end}.start", "origin", "horizontal_distance"' in source
    assert """section.record("ArmEndFromAxis", '"ArmZ1"')""" in source
    assert 'f"{above}.end", "origin", "horizontal_distance"' in source
    assert 'name_last_feature(adapter, "ArmSection")' in source
    assert 'blank_reference_sketches(adapter, ("ArmSection",))' in source
    section = {"ArmThickness", "ArmBelowAxis", "ArmOffset", "SeatToAxis", "ArmEndFromAxis"}
    assert mg_magnifying_bracket_spec.DRAWING_DIMENSIONS["ArmSection"] == section
    assert part.DRAWING_PRECISION["ArmSection"] == {name: 2 for name in section}
    assert "FlangeAboveArm" not in section  # the closing dimension stays unmarked
    assert drawing.SIDE_SECTION_KEEP.keys() == section
    assert "keep=SIDE_SECTION_KEEP" in drawing_source
    # Every import is targeted (the entire-model fallback warned on four
    # views): front, bottom, side and the side's section; the mounting
    # coordinates import by their own feature map.
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
    # One datum chain for the bore axis (blocker 3): the flange's mounting
    # face, named as the plate sees it, and the arm's end, both FROM the axis.
    assert drawing.SECTION_CALLOUTS["SeatToAxis"] == "MOUNTING FACE\nTO BORE AXIS"
    assert drawing.SECTION_CALLOUTS["ArmEndFromAxis"] == "ARM END\nFROM BORE AXIS"
    assert "SEAT FACE" not in "".join(drawing.SECTION_CALLOUTS.values())
    assert "ArmOffset" not in drawing.SECTION_CALLOUTS


# The projected side view's frame (sheet mm): x = 228 - Y, y = 206.15 - Z.
SIDE_OX = drawing.SIDE_AXIS_X * 1000.0
SIDE_OY = drawing.FRONT_ORIGIN_Y * 1000.0


def _side_mm(name: str, keep: dict) -> tuple[float, float]:
    return keep[name][0] * 1000.0, keep[name][1] * 1000.0


def test_side_view_section_hangs_clear_under_the_arm_end() -> None:
    """mreview09 blocker 2 / clarity: the 3.00, (3.35) and 7.50 read ON their
    own dimension lines.  Turned into projection the arm's section dimensions
    across the arm are HORIZONTAL, so they obey retry09's horizontal rule:
    rows centred on the requested x, the lowest row's bottom on the line
    (2.78 mm under the requested y for a lone row, 5.56 mm for two), the line
    running from the rows' far end through both witnesses to an outside-arrow
    tail 6.4 mm past the far one.  The witnesses drop from the arm's end."""
    arm_x = (SIDE_OX - part.ARM_Y[1], SIDE_OX - part.ARM_Y[0])
    flange_x = (SIDE_OX - part.FLANGE_Y[1], SIDE_OX - part.FLANGE_Y[0])
    arm_end = SIDE_OY - part.ARM_Z[1]
    face = SIDE_OY - part.FLANGE_Z[1]
    assert (round(arm_x[0], 2), round(arm_x[1], 2)) == (223.5, 231.0)
    assert (round(flange_x[0], 2), round(flange_x[1], 2)) == (221.65, 234.35)
    assert round(arm_end, 2) == 147.85 and round(face, 2) == 150.96
    text, pitch, lone, tail, iso_left = 3.5, 5.56, 2.78, 6.4, 294.7
    keep = drawing.SIDE_SECTION_KEEP
    offset_x, offset_y = _side_mm("ArmOffset", keep)
    below_x, below_y = _side_mm("ArmBelowAxis", keep)
    thick_x, thick_y = _side_mm("ArmThickness", keep)
    offset_line, below_line, thick_line = offset_y - lone, below_y - pitch, thick_y - pitch
    # Nested from the arm's end: the reference offset (x 231..234.35) nearest,
    # then the lower face from the axis (x 228..231), then the thickness
    # (x 223.5..231), 8 mm apart.
    assert arm_end - text > offset_line + text  # the "(3.35)" row under the end's witness
    assert abs(offset_line - below_line - 8.0) < 0.05 and abs(below_line - thick_line - 8.0) < 0.05
    # "(3.35)" (15.1 mm) hangs right of the flange's end; its box top stays a
    # text height under the arm end's witness (y 147.85 mm, running right).
    offset_row = (offset_x - 7.55, offset_x + 7.55)
    assert offset_row[0] > flange_x[1] + text
    assert offset_line + text < arm_end - text
    # "3.00" (9.1 mm) and "FROM BORE AXIS" (37.8 mm) hang right of the flange
    # too: the value row beside the "(3.35)" row with a text height of air,
    # the callout row a text height under that row's bottom, and the offset's
    # line (to the "(3.35)" row's far end) ends short of the value row.
    value_row = (below_x - 4.55, below_x + 4.55)
    callout_row = (below_x - 18.9, below_x + 18.9)
    assert value_row[0] > offset_row[1] + text
    assert offset_line - (below_line + text) >= text
    assert callout_row[0] > flange_x[1] + text
    assert callout_row[1] < iso_left - text
    assert offset_row[1] < value_row[0] - text
    # "7.50 / ARM THICKNESS" (36.5 mm) hangs left of the arm, its rows clear
    # of its own witness (x 223.5 mm) and a text height under the 3.00's line
    # (whose left tail, x 221.6 mm, that witness crosses: advisory).
    thick_row = (thick_x - 18.25, thick_x + 18.25)
    assert thick_row[1] < arm_x[0] - text
    assert below_line - (thick_line + text) >= text
    assert SIDE_OX - tail < arm_x[0]  # the 3.00's tail reaches past the witness
    # The offset's left tail (6.4 mm past x 231) ends right of the thickness'
    # witness at x 223.5 mm: no crossing (a geometric fact of the part).
    assert arm_x[1] - tail > arm_x[0]
    # Nothing under the arm's end at these x but the counterbore callout,
    # whose thru row's top is y 92.3 mm.
    assert thick_line > 92.3 + text


def test_side_view_axis_stations_read_in_span_either_side_of_the_part() -> None:
    """The mounting face (55.19) and the arm's end (58.30) are VERTICAL
    in-span dimensions from the bore axis: their text (three rows each)
    prints centred on the column, breaking the line, so each column stands
    clear of the part by half its widest row plus a text height, on the side
    its corner is on (the seat corner at Y +6.35 is the flange's LEFT end in
    the turned view, the arm end's corner at Y -3 is on its right)."""
    flange_x = (SIDE_OX - part.FLANGE_Y[1], SIDE_OX - part.FLANGE_Y[0])
    arm_end = SIDE_OY - part.ARM_Z[1]
    face = SIDE_OY - part.FLANGE_Z[1]
    text = 3.5
    seat_x, seat_y = _side_mm("SeatToAxis", drawing.SIDE_SECTION_KEEP)
    end_x, end_y = _side_mm("ArmEndFromAxis", drawing.SIDE_SECTION_KEEP)
    assert seat_x + 18.5 < flange_x[0] - text  # "MOUNTING FACE" ~37 mm
    assert end_x - 18.9 > flange_x[1] + text  # "FROM BORE AXIS" 37.8 mm
    assert face < seat_y < SIDE_OY and arm_end < end_y < SIDE_OY
    # Each block (14.6 mm tall, centred 1 mm under the requested y) keeps a
    # text height from the hung rows under the arm's end and from the
    # diameter rows over the collar; the arm end's column ends at its witness
    # (y 147.85 mm), a text height and more over the "(3.35)" row's top.
    offset_top = _side_mm("ArmOffset", drawing.SIDE_SECTION_KEEP)[1] - 2.78 + text
    assert end_y - 1.03 - 7.31 > offset_top + text
    assert arm_end > offset_top + text
    od_rows_bottom = _side_mm("CollarOd", drawing.SIDE_KEEP)[1] - 5.6
    assert seat_y - 1.03 + 7.31 < od_rows_bottom - text


def test_side_view_diameters_read_above_the_collar_clear_of_the_axis_witnesses() -> None:
    """Clarity: the bore callout's leader crossed the 55.19's witnesses.
    Both diameters now read ABOVE the collar, their leaders running steeply
    down to the centre; a line through the centre meets the axis witnesses
    (y 206.15 mm, starting 1 mm either side of the origin) only at the
    origin, between their ends.  Block geometry is retry09's: rows centred
    on the requested x, the value row's bottom at the requested y, callout
    rows 5.6 mm apart under it (the first 4.5 mm under a toleranced value),
    the elbow 1.6 mm past the lowest row's near end on its baseline."""
    text = 3.5
    collar_top = SIDE_OY + part.COLLAR_OD / 2.0
    od_x, od_y = _side_mm("CollarOd", drawing.SIDE_KEEP)
    bore_x, bore_y = _side_mm("CollarBore", drawing.SIDE_KEEP)
    od_rows = (od_x - 13.65, od_x + 13.65)  # "COLLAR OD" 27.3 mm
    bore_rows = (bore_x - 30.75, bore_x + 30.75)  # "REAM OR BORE: PRESS SEAT" 61.5 mm
    od_shoulder, bore_shoulder = od_y - 5.6, bore_y - 10.1
    od_elbow = (od_rows[1] + 1.6, od_shoulder)
    bore_elbow = (bore_rows[0] - 1.6, bore_shoulder)
    # Above the collar by a text height and more, the OD left, the bore right,
    # a text height apart and both over the origin's witnesses.
    assert min(od_shoulder, bore_shoulder) > collar_top + text
    assert od_rows[1] + text < bore_rows[0]
    assert od_elbow[0] < SIDE_OX < bore_elbow[0]
    assert od_elbow[1] > SIDE_OY and bore_elbow[1] > SIDE_OY
    # Steep leaders: more drop than run from each elbow to the centre.
    assert abs(od_elbow[0] - SIDE_OX) < od_elbow[1] - SIDE_OY
    assert abs(bore_elbow[0] - SIDE_OX) < bore_elbow[1] - SIDE_OY
    # The OD rows stay right of the front view's collar-length rows (to
    # x 175.8 mm, retry09) and the bore's banded value row under the sheet's
    # top margin.
    assert od_rows[0] > 175.8 + text
    assert bore_y + 1.0 + text + 4.5 < 250.0


def test_collar_length_reads_banded_on_its_own_feature() -> None:
    """Machinist review: 10.00 vs Ø12 read as one feature.  The collar's
    length reads above the collar it measures (front view +Z runs down:
    collar top at y 212.1 mm), named along the bore axis, its three rows
    centred on x 155 mm (retry09: y 215.7..230.3 mm, the line at y 215.7 mm
    from x 129 to 175.8 mm); the band's 15.7 mm stack keeps the value row
    (~27 mm) inside the widest callout row (41.5 mm)."""
    assert "ALONG BORE AXIS" in drawing.DIMENSION_CALLOUTS["CollarLen"]
    x, y = drawing.FRONT_KEEP["CollarLen"]
    assert y - 0.0083 > 0.2121 + 0.0035
    assert x > 0.139
    assert x + 0.02075 < drawing.SIDE_KEEP["CollarOd"][0] - 0.01365 - 0.0035
    assert drawing.FRONT_KEEP["FlangeWidth"][0] < x
    assert "ArmDepth" not in drawing.FRONT_KEEP


# Hung-text geometry measured on retry09's native audit (20261012T124257186Z):
# a dimension whose text is requested beyond its span prints its value row's
# box 0.9..4.5 mm above the requested y and a callout row one pitch (5.56 mm)
# under it; a lone row's baseline sits 2.78 mm under the requested y.
ROW_PITCH = 0.00556
TEXT_HEIGHT = 0.0035
ROW_BOX = (0.0009, 0.0045)
LONE_ROW_DROP = 0.00278


def test_arm_width_hangs_below_the_arm_end_between_the_aligned_views() -> None:
    """retry09: a HORIZONTAL dimension's rows requested beyond its span print
    centred on the requested x ("10.00 / ARM WIDTH" at x 88 mm printed over
    x 75..101 mm) and its dimension line runs on under the lowest row to that
    row's far end, so the flange width's witness (x 91 mm) cut both rows.
    The block reads below the arm's end instead, hung left of its witnesses
    (x 129/139 mm), between the aligned front and bottom views."""
    x, y = drawing.FRONT_KEEP["ArmWidth"]
    widest = 0.02605  # "ARM WIDTH" row, retry09
    left, right = x - widest / 2.0, x + widest / 2.0
    arm_end, near_witness = 0.14785, 0.129  # front view: y = 206.15 - Z, x = 134 + X
    bottom_top = 0.121938  # bottom view outline's top, retry09 audit
    # Hung left of its span: the rows end short of the near witness by the
    # audit's arrow/extension clearance (2 mm); the dimension line, at the
    # lowest row's baseline, runs under the arm's end.
    assert right < near_witness - 0.002
    assert y - ROW_PITCH < arm_end - 0.002
    # The value row's top under the arm's end, the callout row's bottom a
    # text height over the bottom view: the block sits between the views.
    assert y + ROW_BOX[1] < arm_end
    assert (y - ROW_PITCH) + ROW_BOX[0] > bottom_top + TEXT_HEIGHT
    # A text height of air to every line beside the block: the flange depth's
    # column (x 89 mm) and the flange width's witness (x 91 mm) on the left;
    # nothing hangs right of the arm now (the 54.30 is gone), and the side
    # view's thickness rows (x 181.75 mm on) are far right.
    assert left > drawing.FRONT_KEEP["FlangeDepth"][0] + TEXT_HEIGHT
    assert left > 0.091 + TEXT_HEIGHT
    assert right + TEXT_HEIGHT < drawing.SIDE_SECTION_KEEP["ArmThickness"][0] - 0.01825


def test_flange_depth_block_clears_the_flange_width_block() -> None:
    """retry09: the flange depth's value row (top y 209.5 mm) sat 1.9 mm under
    the flange width's callout row (bottom y 211.4 mm), and the audit reads two
    blocks within a text height (3.57 mm) as one dimension."""
    depth_x, depth_y = drawing.FRONT_KEEP["FlangeDepth"]
    width_x, width_y = drawing.FRONT_KEEP["FlangeWidth"]
    depth_top = depth_y + ROW_BOX[1]
    width_bottom = (width_y - ROW_PITCH) + ROW_BOX[0]
    assert width_bottom - depth_top > TEXT_HEIGHT + 0.0001
    # The depth's shoulder stays over the flange's top edge (y 154.2 mm) and
    # its column left of the width's witness at x 91 mm, as before.
    assert depth_y - ROW_PITCH > 0.154175 + TEXT_HEIGHT
    assert depth_x < 0.091
    assert width_x < drawing.FRONT_KEEP["CollarLen"][0]


def test_mounting_coordinates_hang_clear_on_the_bottom_view() -> None:
    """The holes' coordinates ride the aligned bottom view (x = 134 + X,
    y = 110 + Y; the flange's west end x 91 mm, its lower face y 103.65 mm,
    the holes at x 95 / 108.7 mm on y 110 mm).  The row offset (6.35 ±0.05
    from the lower face) hangs LEFT of the flange: a vertical dimension's
    rows requested beyond its span print left of its column on a shoulder at
    the lowest row's baseline, 2.78 mm under the requested y for a lone row.
    The two X coordinates hang UNDER the flange, lone rows centred on the
    requested x with the line at the baseline running right to the far
    witness: 4.00 (to x 101.4 mm) over 17.70 (to x 115.1 mm), 8 mm apart,
    both under the lower-face witnesses' reach."""
    y0_x, y0_y = drawing.BOTTOM_HOLE_KEEP["MountingY0"]
    x0_x, x0_y = drawing.BOTTOM_HOLE_KEEP["MountingX0"]
    x1_x, x1_y = drawing.BOTTOM_HOLE_KEEP["MountingX1"]
    flange_west, lower_face, hole_row = 0.091, 0.10365, 0.110
    notes_top = 0.0695  # manufacturing notes' top row (y 70 mm requested)
    y0_row = 0.0245  # " 6.35 ±0.05 " row, retry09
    x0_row, x1_row = 0.0245, 0.0271  # " 4.00 ±0.05 ", " 17.70 ±0.05 "
    # The row offset hangs ABOVE its span (the hole row, y 110 mm): its
    # shoulder (y - 2.78 mm) and rows over the hole-row witness by a text
    # height, its rows left of the flange, its column left of the flange by
    # the 2 mm arrow clearance; the notes sit far below (y <= 70 mm).
    y0_shoulder = y0_y - LONE_ROW_DROP
    assert y0_shoulder + ROW_BOX[0] > hole_row + TEXT_HEIGHT
    assert y0_shoulder < 0.121938 - 0.002  # under the view outline's top (retry09)
    assert y0_x < flange_west - 0.002
    assert y0_x - y0_row > 0.020 + TEXT_HEIGHT
    # The X coordinates: lone rows centred on x, the 4.00's line 8 mm above
    # the 17.70's, the upper line's row box a text height under the row
    # offset's outside-arrow tail (6.4 mm under the lower face, y 103.65 mm,
    # on the column at x 80 mm), the lower line's row box a text height over
    # the notes, and a text height of air between the two row boxes.
    x0_line, x1_line = x0_y - LONE_ROW_DROP, x1_y - LONE_ROW_DROP
    assert abs((x0_line - x1_line) - 0.008) < 1e-9
    assert x0_line + ROW_BOX[1] < lower_face - 0.0064 - TEXT_HEIGHT
    assert x1_line + ROW_BOX[0] > notes_top + TEXT_HEIGHT
    assert (x0_line + ROW_BOX[0]) - (x1_line + ROW_BOX[1]) > TEXT_HEIGHT
    # Both rows sit left of the flange's west end (the near witness of both,
    # x 91 mm) by the arrow clearance, so each line runs right from under its
    # row across nothing but its own witnesses; the 4.00's far witness
    # (x 95 mm) ends 1 mm under its line, short of the 17.70's line, and the
    # 17.70's far witness (x 108.7 mm) drops right of the 4.00's tail end
    # (x 101.4 mm).
    assert x0_x + x0_row / 2.0 < flange_west - 0.002
    assert x1_x + x1_row / 2.0 < flange_west - 0.002
    assert x0_x == x1_x
    assert 0.095 + 0.0064 < 0.1087


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
