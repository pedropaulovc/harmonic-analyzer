"""Offline contracts for the magnifying-bracket drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

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
        | set(drawing.BOTTOM_FOOTPRINT_KEEP)
        | set(drawing.SIDE_KEEP) | set(drawing.SIDE_SECTION_KEEP)
    )
    assert kept == marked
    # The arm's depth (54.30 from a start buried inside the collar) is not
    # marked, nor the arm's end from the bore axis as a model dimension: the
    # bore axis has ONE toleranced chain along Z -- the mounting face from
    # the axis, the arm's end past that face -- and the sheet prints their
    # sum as a pure reference dimension (mreview09 blocker 3, mreview10
    # blocker 2).  The arm's thickness and its offset from the flange's
    # hole-datum edge print ONCE, in the bottom view from the ArmFootprint
    # witness (where the arm's end face is seen face-on), so the section's
    # own copies of the same two values (ArmThickness, ArmOffset, which
    # define that sketch) stay unmarked: no duplicate controls.
    assert marked == {
        "CollarOd", "CollarBore", "CollarLen",
        "ArmWidth", "FlangeWidth", "FlangeDepth", "FlangeHeight", "ArmRootR",
        "MountingX0", "MountingX1", "MountingY0",
        "ArmBelowAxis", "SeatToAxis", "ArmPastSeat",
        "FootprintThickness", "FootprintOffset",
    }
    assert "ArmThickness" not in marked and "ArmOffset" not in marked
    assert "ArmDepth" not in marked and "ArmEndFromAxis" not in marked
    # The arm-end sheet reference's places live beside the model's; the
    # drawing reads them through the spec, never a literal.
    assert drawing.DRAWING_REFERENCE_PRECISION is mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION
    assert set(mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION) == {drawing.ARM_END_REFERENCE}
    assert not set(mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION) & marked
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


def test_sheet_carries_no_method_notes() -> None:
    """Machinist review r1 (over-specification): the press, Loctite and
    braze lines were a method, not a requirement.  The bracket sheet carries
    no note block: the bore's matched fit, the collar's stack and the
    mounting holes' mate are stated at their callouts; the press contract's
    installation lines stay the lever's and the assembly's."""
    import mg_lever_press_fit_geom as press

    assert not hasattr(mg_magnifying_bracket_spec, "DRAWING_NOTES")
    assert not hasattr(mg_magnifying_bracket_spec, "GRIP_MIN")
    assert not hasattr(mg_magnifying_bracket_spec, "PRESS_INSTALLATION_NOTES")
    assert press.PRESS_INSTALLATION_NOTES  # unchanged, owned by the press contract
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes"' not in part_source
    assert '{"Isometric View Note": ISOMETRIC_VIEW_NOTE}' in part_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in drawing_source
    assert "MANUFACTURING_NOTES_XY" not in drawing_source
    for text in (
        mg_magnifying_bracket_spec.COLLAR_BORE_CALLOUT,
        mg_magnifying_bracket_spec.COLLAR_LENGTH_CALLOUT,
        drawing.MOUNTING_HOLE_PROCESS,
    ):
        assert "LOCTITE" not in text and "PRESS" not in text.replace("PRESS ZONE", "")
        assert "BRAZE" not in text


def test_collar_press_seat_is_native_and_reads_the_press_contract() -> None:
    """The bore nominal is mg_lever_press_fit_geom's (one config-free read
    point for the joint; the collar length stays the configured station's,
    banded by the press contract's COLLAR_LENGTH_BAND); the build models the
    annulus on the Right plane so the end view imports both circles.  The
    length's band is native; the bore prints its nominal as a REFERENCE under
    a matched-fit callout (machinist review r1: an absolute +0.006/0 band on
    a press bore), so the model carries no bore tolerance."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as lever

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert part.COLLAR_BORE_DIA is press.COLLAR_BORE_DIA
    assert not hasattr(part, "COLLAR_BORE_BAND")
    assert part.COLLAR_LENGTH_BAND is press.COLLAR_LENGTH_BAND
    assert part.COLLAR_HALF_LEN is lever.COLLAR_HALF_LEN
    assert 2.0 * part.COLLAR_HALF_LEN == press.PRESS_ZONE_LENGTH
    assert "from mg_lever_press_fit_geom import COLLAR_BORE_DIA, COLLAR_LENGTH_BAND" in source
    assert "COLLAR_BORE = " not in source  # no bracket-side copy of the bore
    assert 'await adapter.create_sketch("Right")' in source
    assert 'names=(None, None, "CollarOd")' in source
    assert 'names=(None, None, "CollarBore")' in source
    assert "ExtrusionParameters(depth=2.0 * COLLAR_HALF_LEN, both_directions=True)" in source
    assert 'name_dimensions(adapter, "Collar", ["CollarLen"])' in source
    assert "create_revolve" not in source
    assert '"CollarProfile", "CollarBore"' not in source
    # The length band is (upper, lower): deviations() orders it for the
    # bilateral helper, which prints "+0.00/-0.05" at the nominal's two
    # places (the fewest that keep 0.05).
    assert '"Collar", "CollarLen", *deviations(COLLAR_LENGTH_BAND)' in source
    assert press.COLLAR_LENGTH_BAND[0] >= press.COLLAR_LENGTH_BAND[1]
    assert press.COLLAR_LENGTH_BAND != (0.0, 0.0)
    assert "(COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE_DIA / 2.0) ** 2" in source
    assert part.DRAWING_PRECISION["CollarProfile"] == {"CollarOd": 2, "CollarBore": 3}
    assert part.DRAWING_PRECISION["Collar"] == {"CollarLen": 2}
    assert drawing.SIDE_KEEP.keys() == {"CollarOd", "CollarBore"}
    assert "CollarLen" in drawing.FRONT_KEEP
    assert drawing.SIDE_CALLOUTS.keys() == {"CollarOd", "CollarBore"}
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the
    # fit bore names its process; the mate is the lever part, by number and
    # name (machinist review: "rod" read as another part), and the fit is the
    # press contract's diametral interference, matched to that lever.
    bore_callout = drawing.SIDE_CALLOUTS["CollarBore"]
    assert bore_callout is mg_magnifying_bracket_spec.COLLAR_BORE_CALLOUT
    assert bore_callout == (
        "REAM OR BORE: 0.002-0.014\nDIAMETRAL INTERFERENCE ON\nMHA-MG-003 LEVER"
    )
    budget = press.PRESS_FIT_BUDGET
    assert f"{budget['interference_min']:.3f}-{budget['interference_max']:.3f}" in bore_callout
    assert "ROD" not in bore_callout
    assert all(len(row) <= 25 for row in bore_callout.splitlines())
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(adapter, side_annotations, SIDE_CALLOUTS)" in drawing_source
    reference = (
        'set_reference_dimension(\n        adapter, diameters["CollarBore"], '
        'label="collar bore reference nominal", diameter=True\n    )'
    )
    assert reference in drawing_source
    assert drawing_source.index(
        "diameters = _near_side_collar_diameters("
    ) < drawing_source.index(reference)


def test_collar_bore_matched_fit_stays_inside_the_press_budget() -> None:
    """The matched pair the bore callout allows -- any lever zone in its
    printed band, the bore fitted to it at the tightest interference -- stays
    inside the absolute-band press budget the lever's force limit comes from."""
    import mg_lever_press_fit_geom as press

    budget = press.PRESS_FIT_BUDGET
    for rod in (
        press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[1],
        press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[0],
    ):
        offset = rod - press.PRESS_ZONE_DIA
        matched = press.press_fit_budget(
            press_zone_dia_band=(offset, offset),
            collar_bore_dia=rod - budget["interference_max"],
            collar_bore_band=(0.0, 0.0),
        )
        press.check_press_fit_budget(matched)
        assert matched["interference_max"] == pytest.approx(budget["interference_max"])
        for key in ("press_force_max_n", "collar_von_mises_mpa", "engagement"):
            assert matched[key] <= budget[key] * (1.0 + 1e-12), key


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
    assert "_prove_collar_centre_mark(adapter, side, bore_axis)" in source
    assert "bore_axis = _collar_axis(adapter, side, _collar_bore_rim(side_edges))" in source
    assert "curate_hidden_dimensions(" in source
    assert "add_native_hole_callout(" in source

    right = object()
    axis = (0.26615, 0.180)

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
    monkeypatch.setattr(
        drawing, "_early_bound", lambda obj, interface: view_api if interface == "IView" else obj
    )
    monkeypatch.setattr(drawing._telemetry, "success", lambda message, **fields: successes.append(message))

    with pytest.raises(RuntimeError, match="0 centre marks"):
        drawing._prove_collar_centre_mark(object(), right, axis)
    marks[:] = [mark(axis), mark(axis)]
    with pytest.raises(RuntimeError, match="2 centre marks"):
        drawing._prove_collar_centre_mark(object(), right, axis)
    assert len(marks) == 2
    marks[:] = [mark((axis[0] + 0.001, axis[1]))]
    with pytest.raises(RuntimeError, match="off the bore axis"):
        drawing._prove_collar_centre_mark(object(), right, axis)
    marks[:] = [mark(axis)]
    drawing._prove_collar_centre_mark(object(), right, axis)
    assert successes and "one centre mark" in successes[-1]


def test_collar_axis_is_the_rims_centre_projected_to_the_sheet(monkeypatch) -> None:
    from types import SimpleNamespace
    right = object()
    rim = SimpleNamespace(circle=(5.0, 0.0, 0.0, 1.0, 0.0, 0.0, 2.993))

    def project(adapter, view, xyz, *, label):
        assert view is right
        assert xyz == (0.005, 0.0, 0.0)
        assert label == "collar bore axis"
        return (0.228, 0.20615)

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    assert drawing._collar_axis(object(), right, rim) == (0.228, 0.20615)


def test_collar_rims_and_arm_end_are_picked_on_the_near_end_face() -> None:
    """One edge sweep of the side view serves the bore rim (the centre mark's
    and both proofs' axis), the OD rim (the sheet reference's anchor) and
    the arm's end edge (its other pick): *Right looks from +X, so the
    visible rims lie on the face at +COLLAR_HALF_LEN and the arm's end edge
    nearest the viewer at +ARM_HALF_X."""
    from types import SimpleNamespace
    import pytest
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as lever
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis, label))
        return SimpleNamespace(edge=object(), circle=(*center, *axis, radius))

    lines = {}

    def exact_line_through(point, *, label):
        calls.append((point, label))
        start, end = lines[point]
        return SimpleNamespace(
            edge=object(), line=(start, end),
            length_mm=sum((a - b) ** 2 for a, b in zip(start, end)) ** 0.5,
        )

    edges = SimpleNamespace(circle_at=circle_at, exact_line_through=exact_line_through)
    drawing._collar_bore_rim(edges)
    drawing._collar_od_rim(edges)
    midpoint = (part.ARM_HALF_X, (part.ARM_Y[0] + part.ARM_Y[1]) / 2.0, part.ARM_Z[1])
    end_z = part.ARM_Z[1]
    assert end_z == 103.51  # A1 (#1559): 100.40 seat station + 3.11 overhang
    lines[midpoint] = ((5.0, -3.0, end_z), (5.0, 4.5, end_z))
    drawing._arm_end_edge(edges)
    assert calls == [
        ((lever.COLLAR_HALF_LEN, 0.0, 0.0), press.COLLAR_BORE_DIA / 2.0, (1.0, 0.0, 0.0), "bracket collar bore rim"),
        ((lever.COLLAR_HALF_LEN, 0.0, 0.0), part.COLLAR_OD / 2.0, (1.0, 0.0, 0.0), "bracket collar OD rim"),
        ((5.0, 0.75, end_z), "bracket arm end edge"),
    ]
    assert drawing.COLLAR_HALF_LEN is lever.COLLAR_HALF_LEN
    assert drawing.COLLAR_BORE_DIA is press.COLLAR_BORE_DIA
    assert drawing.COLLAR_OD == 12.0 and part.COLLAR_OD == 12.0
    # The pick is proven to be the end face's edge: the far (-X) edge, a
    # side edge through the corner, or a short edge all refuse.
    for wrong in (
        ((-5.0, -3.0, end_z), (-5.0, 4.5, end_z)),
        ((5.0, 0.75, 4.0), (5.0, 0.75, end_z)),
        ((5.0, -3.0, end_z), (5.0, 4.0, end_z)),
    ):
        lines[midpoint] = wrong
        with pytest.raises(RuntimeError, match="not the end face's edge"):
            drawing._arm_end_edge(edges)


def test_mounting_pattern_consumes_joint_contract() -> None:
    import magnifying_bracket_joint_layout as joint
    assert part.FLANGE_X is joint.SIDE_PLATE_X
    assert part.FLANGE_Y is joint.SIDE_PLATE_Y
    assert part.FLANGE_Z is joint.SIDE_PLATE_Z
    assert part.BRACKET_HOLE_POINTS is joint.BRACKET_HOLE_POINTS
    assert part.CLEARANCE_SPEC is joint.CLEARANCE_SPEC
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="MountingHoles"' in source
    assert "MountingCounterbores" not in source
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
    the plain holes enter from the far (-Z) face, so the callout attaches to
    their exit rims on the +Z face, which the view can see."""
    from types import SimpleNamespace
    import magnifying_bracket_joint_layout as joint
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    edges = SimpleNamespace(circle_at=circle_at)
    assert len(drawing._mounting_rims(edges)) == len(joint.BRACKET_HOLE_POINTS)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'bottom_edges = scan_view_edges(bottom, label="bracket mounting face")' in source
    assert "rims = _mounting_rims(bottom_edges)" in source
    assert [call[0] for call in calls] == [
        (point[0], point[1], joint.SIDE_PLATE_Z[1])
        for point in joint.BRACKET_HOLE_POINTS
    ]
    assert all(call[1] == joint.CLEARANCE_DIA / 2.0 for call in calls)
    assert all(call[2] == (0.0, 0.0, 1.0) for call in calls)


def test_plain_hole_volume_and_title_block_bands() -> None:
    """Machinist review r1 blockers: the flange depth's 3.175 ±0.05 and the
    counterbore's 1.55 ±0.05 rescued a wall.  The #2-56 fillister heads now
    bear on the 1/8 stock flange's front face (no counterbore), so the
    flange depth -- the screws' grip -- takes the title block's .XXX band and
    the holes the drilled-hole band: no native band rescues anything."""
    import magnifying_bracket_joint_layout as joint
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        "len(BRACKET_HOLE_POINTS) * math.pi / 4.0 * CLEARANCE_DIA ** 2 * SIDE_PLATE_THICKNESS"
        in source
    )
    assert "COUNTERBORE" not in source
    assert joint.CLEARANCE_DIA == 2.591
    assert joint.COUNTERBORE_DEPTH == 0.0
    assert joint.SIDE_PLATE_THICKNESS == 3.175
    assert joint.FLANGE_THICKNESS_BAND == 0.13
    assert joint.GRIP_BAND == joint.FLANGE_THICKNESS_BAND
    assert '"FlangeProfile", "FlangeDepth"' not in source
    assert "PLATE_THICKNESS_BAND" not in source
    assert 'set_dimension_display_precision(\n        adapter, "MountingHoles", native_names["HoleDiameter"], 3\n    )' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert part.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"] == 3
    assert "MountingHoles" not in part.DRAWING_PRECISION
    assert "#4" not in source
    # Worst-case full-thread engagement in the summing lever's tap (>= 1.5 D)
    # with the grip at its title-block band, and the tip short of the
    # tap's full-thread bottom.
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA
    assert joint.SCREW_TIP_GAP_MIN > 0.0


def test_hole_callout_rides_the_aligned_bottom_view_and_names_its_mate() -> None:
    """mreview09: the mirrored *Back view carrying the hole dimensions was a
    duplicate "not a projection of anything above it"; the callout and the
    coordinates ride the aligned bottom view.  Machinist review r1 blocker:
    the ±0.05 coordinates named no mate -- the callout now names the summing
    lever's two #2-56 taps the pattern matches, and the plain holes have no
    entry side to name."""
    import magnifying_bracket_joint_layout as joint
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "*Back" not in source
    assert "BACK_CENTER" not in source and "BACK_KEEP" not in source
    assert 'process="' not in source
    assert "process=MOUNTING_HOLE_PROCESS" in source
    assert "COUNTERBORE_PROCESS" not in source and "C'BORE" not in source
    assert 'label="two bracket mounting holes"' in source
    assert drawing.MOUNTING_HOLE_PROCESS.endswith("\n")
    rows = drawing.MOUNTING_HOLE_PROCESS.rstrip("\n").split("\n")
    assert rows == ["MATCHES MHA-SM-003", "SUMMING LEVER TAPS"]
    assert joint.TAP_SPEC.size == "#2-56"
    # The mate is the summing lever, by number (its own part config).
    import _config
    assert _config.parts("sm-summing-lever")["number"] == "MHA-SM-003"
    # Two process rows over the native thru row: three physical rows, one
    # fewer than the counterbore callout's four.
    assert 1 + len(rows) == 3
    # The thru row (43.8 mm) is the lowest: the rows over it stay about as
    # narrow, or the leader leaving its near end would run under them.
    assert all(len(row) <= 18 for row in rows)
    assert "MOUNTING FACE" in drawing.SECTION_CALLOUTS["SeatToAxis"]
    assert "edge=rims[1].edge" in source  # the east hole, nearer the block
    assert '"MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0")' in source
    assert "keep=BOTTOM_HOLE_KEEP" in source
    # The callout block (retry09, requested (337, 78) mm, two rows): rows
    # centred on the requested x, the block centred 1 mm under the requested
    # y, the elbow 1.5 mm before the lowest row's end nearer the hole, the
    # leader from that elbow to the hole.  Three physical rows: the two
    # process rows over the native thru row (43.8 mm measured, the lowest).
    # Two row pitches plus a cap height bound the block.
    assert "callout_xy=(0.162, 0.056)" in source
    callout_x, callout_y = 0.162, 0.056
    pitch, text, char = 0.00556, 0.0035, 0.00262
    block = 2 * pitch + text
    bottom = callout_y - 0.001 - block / 2.0
    top = bottom + block
    widths = [len(row) * char for row in rows]  # process rows above the thru row
    half = max(*widths, 0.048) / 2.0  # the widest row, the thru row at its widest guess
    assert bottom > 0.0127 + text  # over the drawable border
    hole = (
        drawing.BOTTOM_CENTER[0] + 0.019 + joint.BRACKET_HOLE_POINTS[1][0] / 1000.0,
        drawing.BOTTOM_CENTER[1] + joint.BRACKET_HOLE_POINTS[1][1] / 1000.0,
    )
    assert abs(hole[0] - 0.0727) < 1e-9 and abs(hole[1] - 0.08879) < 1e-9
    # The block stays right of the offset's hung row at its widest (x 126.2
    # mm) and the flange height's column (x 130 mm), under the thickness'
    # lower tail (y 79.44 mm), left of the isometric's outline (x ~316 mm)
    # and of the title block (x > 216 mm under y 66 mm).
    offset_x, offset_y = drawing.BOTTOM_FOOTPRINT_KEEP["FootprintOffset"]
    height_x = drawing.BOTTOM_KEEP["FlangeHeight"][0]
    thickness_x = drawing.BOTTOM_FOOTPRINT_KEEP["FootprintThickness"][0]
    assert callout_x - half > offset_x + 0.0122 + text
    assert callout_x - half > height_x + 2 * text
    assert callout_x + half < drawing.ISO_CENTER[0] - 0.0343 - text
    assert callout_x + half < 0.216
    arm_face = drawing.BOTTOM_CENTER[1] + part.ARM_Y[0] / 1000.0
    assert top + text < arm_face - 0.00635
    assert offset_x < thickness_x < callout_x + half
    x1_line = drawing.BOTTOM_HOLE_KEEP["MountingX1"][1] - 0.00278
    x0_line = drawing.BOTTOM_HOLE_KEEP["MountingX0"][1] - 0.00278
    lower_face = drawing.BOTTOM_CENTER[1] + part.FLANGE_Y[0] / 1000.0
    for thru_width in (0.040, 0.0438, 0.048):
        elbow = (callout_x - thru_width / 2.0 - 0.0015, bottom)
        dx, dy = hole[0] - elbow[0], hole[1] - elbow[1]
        assert dx < 0.0 < dy

        def leader_x(y: float) -> float:
            return elbow[0] + dx * (y - elbow[1]) / dy

        def leader_y(x: float) -> float:
            return elbow[1] + dy * (x - elbow[0]) / dx

        # The leader climbs left faster than any row above the lowest widens
        # past it, so it runs under none of its own rows: at each upper row's
        # baseline it is a text height left of that row's near end.
        for step, width in enumerate(reversed(widths), start=1):
            assert leader_x(bottom + step * pitch) < callout_x - width / 2.0 - text
        # (Pre-A1 coordinates; the group now sits 36 mm left, 21.21 mm down.)
        # At the 17.70's line (y 81 mm, to x 115.1 mm) and the 4.00's (y 89
        # mm, to x 101.4 mm) it is right of both line ends by a text height;
        # it crosses the offset's column (x 150 mm) under that dimension's
        # run (its foot, the hung row's shoulder, at y 97.1 mm) and reaches
        # the row's height a text height left of the row's widest reach.
        offset_shoulder = offset_y - 0.00278
        assert leader_x(x1_line) > hole[0] + 0.0064 + text
        assert leader_x(x0_line) > drawing.BOTTOM_CENTER[0] + 0.019 - 0.039 + 0.0064 + text
        assert leader_y(offset_x) < offset_shoulder - 0.002
        assert leader_x(offset_shoulder) < offset_x - 0.0122 - text
        # It leaves the flange through its lower face between the hole's own
        # witness and the east stack's witnesses (the flange's east end + 1).
        east_witness = drawing.BOTTOM_CENTER[0] + 0.019 + part.FLANGE_X[1] / 1000.0 + 0.001
        assert hole[0] + 0.002 < leader_x(lower_face) < east_witness - 0.002


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
    # Machinist review r1 blocker: the ±0.05 coordinates are functional, not
    # decorative -- the clearance hole's radial float over the #2-56 major
    # diameter must cover both patterns' (this one and the summing lever's
    # taps) worst-case radial offset, which the title block's ±0.51 would not.
    import magnifying_bracket_joint_layout as joint
    float_mm = (joint.CLEARANCE_DIA - joint.SCREW_MAJOR_DIA) / 2.0
    assert float_mm >= math.sqrt(2.0) * 2.0 * joint.POSITION_BAND
    assert float_mm < math.sqrt(2.0) * 2.0 * 0.51


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
    assert drawing.FRONT_ORIGIN_Y == pytest.approx(
        drawing.FRONT_CENTER[1] + (part.ARM_Z[1] - part.COLLAR_OD / 2.0) / 2000.0
    )
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
    assert math.isclose(drawing.FRONT_ORIGIN_Y, 0.23015)
    # A1 (#1559): the 1:2 isometric carries its scale in the property note.
    assert drawing.ISO_SCALE == (1, 2)
    assert '"*Isometric", *ISO_CENTER, scale=ISO_SCALE' in drawing_source
    assert mg_magnifying_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


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
    """The arm's lower face from the bore axis and the axis' chain along Z
    print from a blanked ArmSection witness on the Right plane (sketch (u, v)
    -> model (-Z, Y)), not from a note; the bore axis is located from the
    seat face.  Offline source contract only: the native import still wants
    farm proof."""
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
    # The bore axis has ONE toleranced chain along Z (mreview10 blocker 2):
    # the seat face from the origin (SeatToAxis), then the arm's end past the
    # seat piece's hole-datum corner (ArmPastSeat); the arm's end from the
    # axis is no model dimension any more -- the sheet prints it as the
    # chain's parenthesised sum.
    assert 'f"{end}.start", f"{below}.start", "horizontal_distance"' in source
    assert "ARM_Z[1] - FLANGE_Z[1]" in source
    assert """section.record("ArmPastSeat", '"ArmZ1" - "FlangeZ1"')""" in source
    assert 'f"{end}.start", "origin", "horizontal_distance"' not in source
    assert "ArmEndFromAxis" not in source
    assert 'f"{above}.end", "origin", "horizontal_distance"' in source
    assert 'name_last_feature(adapter, "ArmSection")' in source
    assert 'blank_reference_sketches(adapter, ("ArmSection", "ArmFootprint"))' in source
    # The sketch's thickness and offset dimensions define it but print in
    # the bottom view from ArmFootprint (retry11: no duplicate controls), so
    # the section marks three: the 3.00 and the Z chain.
    section = {"ArmBelowAxis", "SeatToAxis", "ArmPastSeat"}
    assert mg_magnifying_bracket_spec.DRAWING_DIMENSIONS["ArmSection"] == section
    assert part.DRAWING_PRECISION["ArmSection"] == {name: 2 for name in section}
    assert "FlangeAboveArm" not in section  # the closing dimension stays unmarked
    assert drawing.SIDE_SECTION_KEEP.keys() == section
    assert "keep=SIDE_SECTION_KEEP" in drawing_source
    # Every import is targeted (the entire-model fallback warned on four
    # views): front, bottom, side, the side's section and the bottom's
    # footprint; the mounting coordinates import by their own feature map.
    assert drawing_source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 5
    assert "keep={}" not in drawing_source
    assert "set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)" in drawing_source
    # Every model dimension of the section is toleranced (mreview10 blocker
    # 1: the arm's offset from the flange's hole-datum edge was reference,
    # leaving nothing toleranced between the arm and a flange edge); no
    # model dimension is parenthesised and the plural helper's "(<MOD-DIAM>"
    # prefix (retry08's "(Ø3.35)") is not used at all.
    assert "SECTION_REFERENCE" not in drawing_source
    assert "set_reference_dimensions(" not in drawing_source
    # The arm-end sheet reference and the collar bore's reference nominal.
    assert drawing_source.count("set_reference_dimension(") == 2
    assert "set_reference_dimension(adapter, annotation, label=ARM_END_REFERENCE)" in drawing_source
    # ArmBelowAxis is the Y -3 face, nearer the bore axis than Y +4.5.
    # In the turned side view it prints on the right (x 231 versus 223.5).
    assert -part.ARM_Y[0] < part.ARM_Y[1]
    assert SIDE_OX - part.ARM_Y[0] > SIDE_OX - part.ARM_Y[1]
    assert drawing.SECTION_CALLOUTS["ArmBelowAxis"] == "NEAR ARM FACE\nTO BORE AXIS"
    # The physical overhang is named, but remains the model's ordinary .XX
    # control: no new tight band and no closing model dimension.
    assert drawing.SECTION_CALLOUTS["SeatToAxis"] == "MOUNTING FACE\nTO BORE AXIS"
    assert drawing.SECTION_CALLOUTS["ArmPastSeat"].replace("\n", " ") == "ARM PAST MOUNTING FACE"
    assert "SEAT FACE" not in "".join(drawing.SECTION_CALLOUTS.values())
    assert drawing.SECTION_CALLOUTS.keys() == section
    # Value plus two explicit face-label rows: at most four rows, with each
    # row shorter than the previous ambiguous one-line label.
    arm_rows = drawing.SECTION_CALLOUTS["ArmBelowAxis"].splitlines()
    assert arm_rows == ["NEAR ARM FACE", "TO BORE AXIS"]
    assert 1 + len(arm_rows) <= 4
    assert max(map(len, arm_rows)) <= 13


def test_arm_footprint_controls_the_arm_in_the_bottom_view() -> None:
    """The arm's thickness and its lower face from the flange's hole-datum
    edge print as native, toleranced dimensions in the BOTTOM view -- where
    the arm's end face is drawn face-on inside the flange -- from a blanked
    ArmFootprint witness on the Front plane (sketch (u, v) -> model (X, Y)),
    once on the sheet (the ArmSection's copies of both are unmarked).
    Offline source contract only: the native import still wants farm proof."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Both lines lie on the flange's east end, the one edge the arm's +X face
    # shares, so the shown sketch prints nothing the view does not draw.
    assert part.ARM_HALF_X == part.FLANGE_X[1]
    assert "if ARM_HALF_X != FLANGE_X[1]:" in source
    assert 'await adapter.create_sketch("Front")' in source
    assert "end_x = FLANGE_X[1]" in source
    assert "await adapter.add_line(end_x, FLANGE_Y[0], end_x, ARM_Y[0])" in source
    assert "await adapter.add_line(end_x, ARM_Y[0], end_x, ARM_Y[1])" in source
    assert 'f"{gap}.end", f"{block}.start", "coincident"' in source
    # The hole-datum corner anchors the sketch to the origin (two dimensions,
    # both driven, unmarked), then each piece's far end is pinned over its
    # start (vertical_points and ONE vertical dim, the section's ArmThickness
    # pattern): four dimensions, recorded in creation order.
    assert 'f"{gap}.start", end_x, FLANGE_Y[0], "arm footprint hole-datum corner"' in source
    assert """footprint.record("FootprintCornerX", '"FlangeX1"')""" in source
    assert """footprint.record("FootprintCornerY", '-"FlangeY0"')""" in source
    assert (
        'adapter, f"{gap}.start", f"{gap}.end",\n'
        '        0.0, ARM_Y[0] - FLANGE_Y[0], "arm footprint FootprintOffset",'
    ) in source
    assert """footprint.record("FootprintOffset", '"ArmY0" - "FlangeY0"')""" in source
    assert (
        'adapter, f"{block}.start", f"{block}.end",\n'
        '        0.0, ARM_Y[1] - ARM_Y[0], "arm footprint FootprintThickness",'
    ) in source
    assert """footprint.record("FootprintThickness", '"ArmY1" - "ArmY0"')""" in source
    assert source.count("footprint.record(") == 4
    assert 'await ensure_fully_defined(adapter, "arm footprint sketch")' in source
    assert 'name_last_feature(adapter, "ArmFootprint")' in source
    assert 'drive_jobs += footprint.apply(adapter, "ArmFootprint")' in source
    footprint = {"FootprintThickness", "FootprintOffset"}
    assert mg_magnifying_bracket_spec.DRAWING_DIMENSIONS["ArmFootprint"] == footprint
    assert part.DRAWING_PRECISION["ArmFootprint"] == {name: 2 for name in footprint}
    marked = set().union(*mg_magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    assert not {"FootprintCornerX", "FootprintCornerY"} & marked  # the anchor stays unmarked
    assert drawing.BOTTOM_FOOTPRINT_KEEP.keys() == footprint
    assert "keep=BOTTOM_FOOTPRINT_KEEP" in drawing_source
    assert 'view_label="bottom arm footprint"' in drawing_source
    # No callout: the face-on footprint names its own edges, and a hung row
    # of words could print on either hand into the neighbouring column.
    assert not footprint & set(drawing.SECTION_CALLOUTS)
    assert "BOTTOM_CALLOUTS" not in drawing_source
    assert "FOOTPRINT_CALLOUTS" not in drawing_source


# The projected side view's frame (sheet mm): x = 228 - Y, y = 230.15 - Z.
SIDE_OX = drawing.SIDE_AXIS_X * 1000.0
SIDE_OY = drawing.FRONT_ORIGIN_Y * 1000.0
# A1 (#1559) moved the bottom-view group 36 mm left and 21.21 mm down from
# its retry09..retry15 audited place: the east stack's widest reach (pre-A1
# x 181.1 mm), the counterbore callout's top (pre-A1 y 95.1 mm).  The 1:2
# isometric's outline starts ~34.3 mm left of its centre.
EAST_STACK_RIGHT = 181.1 - 36.0
CALLOUT_TOP = 95.1 - 21.21
ISO_LEFT = drawing.ISO_CENTER[0] * 1000.0 - 34.3
# The same A1 translation in metres for the retry-audited front/bottom pins:
# every view and its dimensions moved left, the bottom group and the arm-end
# stacks down, the collar's stacks up with the bore axis.
SHIFT_X = -0.036
SHIFT_DOWN = -0.02121
SHIFT_UP = 0.024
BOTTOM_OUTLINE_TOP = 0.121938 + SHIFT_DOWN  # retry09 audit, translated


def _side_mm(name: str, keep: dict) -> tuple[float, float]:
    return keep[name][0] * 1000.0, keep[name][1] * 1000.0


def test_side_view_section_hangs_clear_under_the_arm_end() -> None:
    """mreview09 blocker 2 / clarity, retry10's two under-arm crossings: the
    3.00 reads ON its own dimension line and no line runs over another's
    witness.  Retry10 stacked it with the 3.35 and the 7.50, whose outside
    tails crossed the next witness down; those two now control the arm in
    the bottom view (test_bottom_view_east_stack_stands_clear) and the 3.00
    stands alone under the arm.  Turned into projection it is HORIZONTAL,
    so it obeys retry09's horizontal rule: rows centred on the requested x,
    the lowest row's bottom on the line (11.12 mm under the requested y for
    three rows), the line running from the rows' far end through both
    witnesses and, with OUTSIDE arrows, on to a tail 6.4 mm past the far
    witness.  The witnesses drop from the arm's end."""
    arm_x = (SIDE_OX - part.ARM_Y[1], SIDE_OX - part.ARM_Y[0])
    flange_x = (SIDE_OX - part.FLANGE_Y[1], SIDE_OX - part.FLANGE_Y[0])
    arm_end = SIDE_OY - part.ARM_Z[1]
    face = SIDE_OY - part.FLANGE_Z[1]
    assert (round(arm_x[0], 2), round(arm_x[1], 2)) == (223.5, 231.0)
    assert (round(flange_x[0], 2), round(flange_x[1], 2)) == (221.65, 234.35)
    assert round(arm_end, 2) == 126.64 and round(face, 2) == 129.75
    text, pitch, tail, iso_left = 3.5, 5.56, 6.4, ISO_LEFT
    keep = drawing.SIDE_SECTION_KEEP
    assert set(keep) == {"SeatToAxis", "ArmPastSeat", "ArmBelowAxis"}
    below_x, below_y = _side_mm("ArmBelowAxis", keep)
    below_line = below_y - len(drawing.SECTION_CALLOUTS["ArmBelowAxis"].splitlines()) * pitch
    # Its 3 mm span (x 228..231) fits no two 3.556 mm arrowheads inside, so
    # the arrows stand OUTSIDE (retry11: no inside-arrowhead overlap), forced
    # so the proven ink is the drawn ink; the left tail ends in air at x
    # 221.6 mm, under the flange (y 150.96 mm on) and right of the 3.11's
    # column.
    assert drawing.SECTION_ARROW_SIDES == {"ArmBelowAxis": 1}
    assert drawing._ARROWS_INSIDE == 0 and drawing._ARROWS_OUTSIDE == 1
    tail_end = arm_x[1] - 3.0 - tail
    assert round(tail_end, 2) == 221.6
    assert arm_x[1] + tail < iso_left
    # A three-row block (two face-label rows under the native value)
    # hung RIGHT, under nothing (the flange ends at y 150.96 mm, the arm at
    # 147.85 mm): its rows a 2 mm arrow clearance and more right of the
    # 3.11's far witness (the flange's corner, x 234.35 mm) and a text height
    # left of the isometric's outline at the widest letter pitch retry09/10
    # measured (2.85 mm a character); the block's top a text height under
    # the arm end's witness (y 147.85 mm, the reference's).
    arm_rows = drawing.SECTION_CALLOUTS["ArmBelowAxis"].splitlines()
    half_row = max(map(len, arm_rows)) * 2.85 / 2.0
    assert below_x - half_row > flange_x[1] + 2.0
    assert below_x + half_row < iso_left - text
    assert below_line + len(arm_rows) * pitch + text + text <= arm_end
    # The labelled 3.11 hangs below this line, not beside its witnesses.
    # Its column stops short of the 3.00's tail; the widest callout row
    # clears the bottom view's east stack on EITHER hand of that column.
    past_x, past_y = _side_mm("ArmPastSeat", keep)
    half_row = max(len(row) for row in drawing.SECTION_CALLOUTS["ArmPastSeat"].splitlines()) * 2.85
    assert past_x + 2.0 < tail_end
    assert past_x - half_row > EAST_STACK_RIGHT + text
    assert past_y + 4.5 + text < below_line
    assert past_y - 2.78 - len(drawing.SECTION_CALLOUTS["ArmPastSeat"].splitlines()) * pitch > CALLOUT_TOP + text
    assert below_line > CALLOUT_TOP + text


def test_side_view_axis_chain_reads_once_with_its_sum_as_reference() -> None:
    """mreview10 blocker 2: ONE toleranced chain from the mounting face to
    the bore axis.  The 55.19 (mounting face, VERTICAL in-span on the left)
    and the 3.11 past it (ArmPastSeat, hung below its 3.11 mm span, left of
    the arm) are the model's; the arm's end from the axis is a pure sheet
    reference dimension, parenthesised, in-span on the right where retry10's
    model dimension stood, and the arithmetic closes exactly."""
    import pytest
    flange_x = (SIDE_OX - part.FLANGE_Y[1], SIDE_OX - part.FLANGE_Y[0])
    arm_end = SIDE_OY - part.ARM_Z[1]
    face = SIDE_OY - part.FLANGE_Z[1]
    text, lone, tail = 3.5, 2.78, 6.4
    assert round(
        part.ARM_Z[1] - part.FLANGE_Z[1],
        mg_magnifying_bracket_spec.DRAWING_PRECISION["ArmSection"]["ArmPastSeat"],
    ) == pytest.approx(3.11)
    assert part.FLANGE_Z[1] + (part.ARM_Z[1] - part.FLANGE_Z[1]) == pytest.approx(103.51)
    assert round(part.FLANGE_Z[1], 2) + round(part.ARM_Z[1] - part.FLANGE_Z[1], 2) == pytest.approx(103.51)
    seat_x, seat_y = _side_mm("SeatToAxis", drawing.SIDE_SECTION_KEEP)
    past_x, past_y = _side_mm("ArmPastSeat", drawing.SIDE_SECTION_KEEP)
    end_x, end_y = drawing.ARM_END_REFERENCE_XY[0] * 1000.0, drawing.ARM_END_REFERENCE_XY[1] * 1000.0
    assert seat_x + 18.5 < flange_x[0] - text  # "MOUNTING FACE" ~37 mm
    assert end_x - 18.9 > flange_x[1] + text  # "FROM BORE AXIS" 37.8 mm
    assert face < seat_y < SIDE_OY and arm_end < end_y < SIDE_OY
    # The 3.11's labelled block hangs well below the 3.00's line, its
    # column between the mounting-face column and that line's left tail.
    # No label row may reach the bottom view's east stack or counterbore.
    assert seat_x + text < past_x < SIDE_OX - 6.4 - 2.0
    row_width = max(len(row) for row in drawing.SECTION_CALLOUTS["ArmPastSeat"].splitlines()) * 2.85
    assert past_x - row_width > EAST_STACK_RIGHT + text
    assert past_y - lone - len(drawing.SECTION_CALLOUTS["ArmPastSeat"].splitlines()) * 5.56 > CALLOUT_TOP + text
    assert face + tail < seat_y - 1.03 - 7.31 - text
    # The reference block (14.6 mm tall, centred 1 mm under the requested y)
    # keeps a text height from the 3.00's rows under the arm's end; its
    # column ends at its witness (y 147.85 mm), which the 3.00's own witness
    # crosses (extension over extension), a text height and more over the
    # 3.00's value row.
    below_top = _side_mm("ArmBelowAxis", drawing.SIDE_SECTION_KEEP)[1] + text
    assert end_y - 1.03 - 7.31 > below_top + text
    assert arm_end > below_top + text
    od_rows_bottom = _side_mm("CollarOd", drawing.SIDE_KEEP)[1] - 5.6
    assert seat_y - 1.03 + 7.31 < od_rows_bottom - text
    # The reference is a pure sheet dimension: linear, re-anchored to the OD
    # rim's centre, proven on its two named entities to measure ARM_Z[1],
    # parenthesised, its places the spec's, its callout read back.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing.ARM_END_REFERENCE == "arm end from bore axis"
    assert mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION == {
        "arm end from bore axis": 2,
    }
    assert drawing.DRAWING_REFERENCE_PRECISION is mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION
    assert drawing._LINEAR_DIMENSION_TYPES == (2, 11, 12)
    assert 'orientation="vertical"' in source
    assert "entities=(rim.edge, end.edge)" in source
    assert "set_arc_endpoints_to_center(adapter, dimension, label=ARM_END_REFERENCE)" in source
    assert "expected_mm=ARM_Z[1]" in source
    assert "display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)" in source
    assert "display.GetPrimaryPrecision2" in source
    assert drawing.ARM_END_REFERENCE_CALLOUT == "ARM END\nFROM BORE AXIS"
    assert "_set_callout_below(display, ARM_END_REFERENCE_CALLOUT, ARM_END_REFERENCE)" in source
    assert "SetText(4, text)" in source and "GetText(4)" in source
    # The sum is proven on the ink too: the reference joins the section set
    # for the crossing proof and the diameter proof after one rebuild.
    assert "section[ARM_END_REFERENCE] = _arm_end_reference(adapter, side, side_edges)" in source
    assert 'rebuild_drawing(adapter, label="side view annotations")' in source
    assert '_assert_dimensions_clear(section, SECTION_AXES, label="side arm section")' in source
    assert drawing.SECTION_AXES == {
        "ArmBelowAxis": "x",
        "SeatToAxis": "y", "ArmPastSeat": "y", "arm end from bore axis": "y",
    }


def test_side_view_diameters_read_above_the_collar_clear_of_the_axis_witnesses() -> None:
    """retry10's two collar crossings: each diameter line ran through the
    centre to the far rim and crossed the mounting face's axis witness.
    Both diameters now take the near-side single-arrow style (one arrow on
    the rim nearest the text, no line through the centre) and read ABOVE
    the collar, their leaders running steeply down to the near rim, which
    is above the axis witnesses (y 206.15 mm).  Block geometry is retry09's:
    rows centred on the requested x, the value row's bottom at the requested
    y (1 mm higher with a tolerance stack), callout rows 5.6 mm apart under
    it, the elbow 1.6 mm past the lowest row's near end on its baseline.
    The bore's value is now an untoleranced REFERENCE nominal over the three
    matched-fit rows (machinist review r1)."""
    text = 3.5
    collar_top = SIDE_OY + part.COLLAR_OD / 2.0
    od_x, od_y = _side_mm("CollarOd", drawing.SIDE_KEEP)
    bore_x, bore_y = _side_mm("CollarBore", drawing.SIDE_KEEP)
    od_rows = (od_x - 13.65, od_x + 13.65)  # "COLLAR OD" 27.3 mm
    # "REAM OR BORE: PRESS SEAT" printed 61.5 mm (24 characters): the bore
    # callout's widest row scales from it.
    bore_width = 61.5 / 24 * max(
        len(row) for row in drawing.SIDE_CALLOUTS["CollarBore"].splitlines()
    )
    bore_rows = (bore_x - bore_width / 2.0, bore_x + bore_width / 2.0)
    bore_row_count = len(drawing.SIDE_CALLOUTS["CollarBore"].splitlines())
    od_shoulder, bore_shoulder = od_y - 5.6, bore_y - 5.6 * bore_row_count
    od_elbow = (od_rows[1] + 1.6, od_shoulder)
    bore_elbow = (bore_rows[0] - 1.6, bore_shoulder)
    # Above the collar by a text height and more, the OD left, the bore right,
    # a text height apart and both over the origin's witnesses.
    assert min(od_shoulder, bore_shoulder) > collar_top + text
    assert od_rows[1] + text < bore_rows[0]
    assert od_elbow[0] < SIDE_OX < bore_elbow[0]
    assert od_elbow[1] > SIDE_OY and bore_elbow[1] > SIDE_OY
    # Steep leaders: more drop than run from each elbow to the centre, so
    # each lands on the upper half of its rim, over the axis witnesses.
    import math
    for elbow, radius in ((od_elbow, part.COLLAR_OD / 2.0), (bore_elbow, part.COLLAR_BORE_DIA / 2.0)):
        dx, dy = SIDE_OX - elbow[0], SIDE_OY - elbow[1]
        assert abs(dx) < -dy
        reach = math.hypot(dx, dy)
        landing_y = elbow[1] + dy * (reach - radius) / reach
        assert landing_y > SIDE_OY + 1.0
    # The OD rows stay right of the front view's collar-length rows (to
    # x 175.8 mm, retry09), the bore's rows clear of the sheet's right edge
    # and its untoleranced value row under the sheet's top margin.
    assert od_rows[0] > 175.8 + text
    assert bore_rows[1] < 431.8 - 10.0
    assert bore_y + text < 266.7 - 2.0  # drawable top
    # The style and its proof: both imported diameters take the near-side
    # style before the section import, and after the rebuild their ink is
    # read back against both axis witnesses (one group per witness: the two
    # are collinear, and a collinear overlap counts as a crossing).
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "diameters = _near_side_collar_diameters(adapter, side_annotations)" in source
    assert 'set_near_side_diameter(annotation, f"collar {name}")' in source
    assert "_prove_collar_diameters_clear(" in source
    assert '{name: section[name] for name in ("SeatToAxis", ARM_END_REFERENCE)}' in source
    assert drawing._OD_LANDING == (0.8, 1.2) and drawing._BORE_LANDING == (0.5, 1.5)
    assert drawing._RIM_KEEP_OUT == 0.8


def test_collar_length_reads_banded_on_its_own_feature_and_names_its_stack() -> None:
    """Machinist review: 10.00 vs Ø12 read as one feature.  The collar's
    length reads above the collar it measures (front view +Z runs down:
    collar top at y 212.1 mm pre-A1), named along the bore axis.  Machinist
    review r1 blocker: the 0/-0.05 band named no stack -- the callout names
    the MHA-MG-003 lever's press zone, whose length and band the collar's
    are asserted equal to (the rod's dome tip ends flush with the collar's
    outer face, so the band bounds the press contact the force budget uses).
    retry09 printed "ALONG BORE AXIS" (15 characters) 41.5 mm wide over a
    three-row block (y 215.7..230.3 mm pre-A1, the line at the lowest row's
    baseline); the stack row makes four, so the value rises one row pitch
    and the lowest row stays where it was."""
    import mg_lever_press_fit_geom as press

    callout = drawing.DIMENSION_CALLOUTS["CollarLen"]
    assert callout is mg_magnifying_bracket_spec.COLLAR_LENGTH_CALLOUT
    assert "ALONG BORE AXIS" in callout
    assert "MHA-MG-003 LEVER PRESS ZONE" in callout
    assert (press.COLLAR_LENGTH, press.COLLAR_LENGTH_BAND) == (
        press.PRESS_ZONE_LENGTH,
        press.PRESS_ZONE_LENGTH_BAND,
    )
    rows = callout.splitlines()
    assert len(rows) == 3
    x, y = drawing.FRONT_KEEP["CollarLen"]
    assert y == pytest.approx(0.248 + ROW_PITCH)
    # retry09: the lowest row's baseline 8.3 mm under the requested y with
    # three rows; each further row lowers it one pitch more.
    lowest_baseline = y - 0.0083 - ROW_PITCH * (len(rows) + 1 - 3)
    assert lowest_baseline > 0.2121 + SHIFT_UP + 0.0035
    assert y + 0.0063 < 0.2667 - 0.0045  # value row's stack top under the drawable top
    half = 0.0415 / 15 * max(len(row) for row in rows) / 2.0
    assert x > 0.139 + SHIFT_X
    assert x + half < drawing.SIDE_KEEP["CollarOd"][0] - 0.01365 - 0.0035
    assert x - half > 0.020  # inside the sheet's left border
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
    arm_end, near_witness = 0.12664, 0.129 + SHIFT_X  # front view: y = 230.15 - Z, x = 98 + X
    bottom_top = BOTTOM_OUTLINE_TOP
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
    # nothing hangs right of the arm now (the 54.30 is gone), the side view's
    # rows start at x 179.5 mm, and the bottom view's flange height row (14.2
    # mm wide, on either hand of its column at x 166 mm) stays right of the
    # block and a text height under its lowest line (y 132.4 mm).
    assert left > drawing.FRONT_KEEP["FlangeDepth"][0] + TEXT_HEIGHT
    assert left > 0.091 + SHIFT_X + TEXT_HEIGHT
    height_x, height_y = drawing.BOTTOM_KEEP["FlangeHeight"]
    assert right + TEXT_HEIGHT < height_x - 0.0142
    assert height_y - LONE_ROW_DROP + TEXT_HEIGHT + TEXT_HEIGHT < y - ROW_PITCH


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
    assert depth_y - ROW_PITCH > 0.154175 + SHIFT_DOWN + TEXT_HEIGHT
    assert depth_x < 0.091 + SHIFT_X
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
    flange_west, lower_face, hole_row = 0.091 + SHIFT_X, 0.10365 + SHIFT_DOWN, 0.110 + SHIFT_DOWN
    y0_row = 0.0245  # " 6.35 ±0.05 " row, retry09
    x0_row, x1_row = 0.0245, 0.0271  # " 4.00 ±0.05 ", " 17.70 ±0.05 "
    # The row offset hangs ABOVE its span (the hole row, y 110 mm): its
    # shoulder (y - 2.78 mm) and rows over the hole-row witness by a text
    # height, its rows left of the flange, its column left of the flange by
    # the 2 mm arrow clearance; the caption sits far below.
    y0_shoulder = y0_y - LONE_ROW_DROP
    assert y0_shoulder + ROW_BOX[0] > hole_row + TEXT_HEIGHT
    assert y0_shoulder < BOTTOM_OUTLINE_TOP - 0.002  # under the view outline's top (retry09)
    assert y0_x < flange_west - 0.002
    # A1: the group's 36 mm move leaves the hung row ~6.8 mm inside the
    # drawable border (x 12.7 mm), clear by more than a text height.
    assert y0_x - y0_row > 0.0127 + TEXT_HEIGHT
    # The X coordinates: lone rows centred on x, the 4.00's line 8 mm above
    # the 17.70's, the upper line's row box a text height under the row
    # offset's outside-arrow tail (6.4 mm under the lower face, y 103.65 mm,
    # on the column at x 80 mm), the lower line's row box room for the
    # caption (a text height and its gap) over the drawable border (y 12.7
    # mm), and a text height of air between the two row boxes.
    x0_line, x1_line = x0_y - LONE_ROW_DROP, x1_y - LONE_ROW_DROP
    assert abs((x0_line - x1_line) - 0.008) < 1e-9
    assert x0_line + ROW_BOX[1] < lower_face - 0.0064 - TEXT_HEIGHT
    assert x1_line + ROW_BOX[0] > 0.0127 + 2 * TEXT_HEIGHT + drawing.BOTTOM_CAPTION_GAP_M
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
    assert 0.095 + SHIFT_X + 0.0064 < 0.1087 + SHIFT_X


def test_bottom_view_east_stack_stands_clear() -> None:
    """Retry11 (Main): the arm's thickness and its lower face from the
    flange's hole-datum edge control the arm in the BOTTOM view, where its
    end face is drawn face-on inside the flange (x = 134 + X, y = 110 + Y;
    the flange's east end x 139 mm, its faces y 103.65 / 116.35 mm, the
    arm's y 107 / 114.5 mm), beside the flange's height: three VERTICAL
    dimensions in columns east of the flange, every one with OUTSIDE
    arrows.  A vertical dimension with outside arrows draws NO line between
    its witnesses (retry10 ink: the in-span 12.70 and the hung 6.35 printed
    their witnesses, 6.35 mm outside tails and, hung, the run to the
    shoulder), so a foreign witness may cross its empty span; only a tail,
    a run or a shoulder can be crossed, and only foreign text within 2 mm
    of a witness is reported.  A lone row hung off a vertical span sits ON a
    shoulder 2.78 mm under the requested y, beside the column on whichever
    hand SolidWorks takes (the 6.35: left), so every row is kept clear on
    both hands; in-span text prints centred on the column, its box 0.9 mm
    over the requested y's 2.78 mm drop (the 12.70, retry10)."""
    origin_x, origin_y = drawing.BOTTOM_CENTER[0] + 0.019, drawing.BOTTOM_CENTER[1]
    east = origin_x + part.FLANGE_X[1] / 1000.0
    lower_face, top = (origin_y + y / 1000.0 for y in part.FLANGE_Y)
    arm_lower, arm_upper = (origin_y + y / 1000.0 for y in part.ARM_Y)
    assert (round(east, 3), round(lower_face, 5), round(top, 5)) == (0.103, 0.08244, 0.09514)
    assert (round(arm_lower, 5), round(arm_upper, 5)) == (0.08579, 0.09329)
    tail, arrowhead, clearance, overrun = 0.00635, 0.003556, 0.002, 0.001
    offset_x, offset_y = drawing.BOTTOM_FOOTPRINT_KEEP["FootprintOffset"]
    height_x, height_y = drawing.BOTTOM_KEEP["FlangeHeight"]
    thick_x, thick_y = drawing.BOTTOM_FOOTPRINT_KEEP["FootprintThickness"]
    names = {"FlangeHeight", "FootprintOffset", "FootprintThickness"}
    assert drawing.BOTTOM_ARROW_SIDES == {name: drawing._ARROWS_OUTSIDE for name in names}
    assert drawing.BOTTOM_AXES == {name: "y" for name in names}
    # Columns east of the flange's corner witnesses (x 140 mm on), the
    # offset innermost, the thickness OUTERMOST: its tails cross the
    # hole-datum face's and the top's levels (y 100.65..107 and 114.5..
    # 120.85 mm), so every other witness (ending 1 mm past its column) must
    # stop a 2 mm clearance short of its column; the other two hang their
    # rows outside their spans, so the thickness' witnesses cross only
    # their empty spans.
    assert east + overrun + clearance < offset_x < height_x < thick_x
    assert height_x + overrun + clearance < thick_x
    assert offset_x + overrun + clearance < height_x
    # The offset (3.35, witnesses y 103.65 and 107 mm) hangs BELOW: its row
    # (12.2 mm) on a shoulder a 2 mm clearance under the hole-datum
    # witnesses, its run from the shoulder up to the lower witness, its
    # upper tail short of the thickness' upper witness (y 114.5 mm).
    offset_row = 0.0122
    offset_shoulder = offset_y - LONE_ROW_DROP
    assert offset_shoulder + TEXT_HEIGHT < lower_face - clearance
    assert arm_lower + tail < arm_upper
    # The flange height (12.70, witnesses y 103.65 -- over the offset's,
    # collinear -- and 116.35 mm) hangs ABOVE: its row (14.2 mm) on a
    # shoulder a 2 mm clearance over the thickness' upper witness and past
    # its own upper arrowhead, its run from the top witness up to the
    # shoulder; its lower tail (to y 97.3 mm, under the offset's row level)
    # stands a 2 mm arrow clearance right of that row on its right hand.
    height_shoulder = height_y - LONE_ROW_DROP
    assert height_shoulder > arm_upper + clearance
    assert height_shoulder > top + arrowhead
    assert lower_face - tail < offset_shoulder + TEXT_HEIGHT
    assert height_x - (offset_x + offset_row) > clearance
    # The thickness (7.50, witnesses y 107 and 114.5 mm) reads IN-SPAN,
    # centred on the column: its box (12.2 mm, 3.5 mm tall) 2 mm inside
    # both its own witnesses (not reported: the audit's near-text findings
    # are for foreign witnesses), a 2 mm clearance from the flange height's
    # witness ends (x 167 mm, 1.9 mm left of the box and 3.85 mm under or
    # 5.35 mm over it) and under its row; its tails end short of that row
    # by a 2 mm clearance.
    thick_row = 0.0122
    thick_box = (thick_y - LONE_ROW_DROP, thick_y - LONE_ROW_DROP + TEXT_HEIGHT)
    assert abs((thick_box[0] + thick_box[1]) / 2.0 - (arm_lower + arm_upper) / 2.0) < 1e-6
    assert thick_box[0] - arm_lower > 0.0019 and arm_upper - thick_box[1] > 0.0019
    box_left = thick_x - thick_row / 2.0
    witness_end = height_x + overrun
    assert box_left > witness_end
    assert math.hypot(box_left - witness_end, top - thick_box[1]) > clearance
    assert math.hypot(box_left - witness_end, thick_box[0] - lower_face) > clearance
    assert thick_box[1] + clearance < height_shoulder
    assert arm_upper + tail + clearance < height_shoulder
    # Every row on either hand stays left of the counterbore callout's block
    # (x 174 mm on, y <= 95.1 mm) or over it, and under the front view's
    # arm width line (y 132.4 mm) by a text height.
    assert offset_shoulder > CALLOUT_TOP / 1000.0 + clearance
    assert thick_x + thick_row / 2.0 < 0.212 + SHIFT_X + 0.036
    assert height_shoulder + TEXT_HEIGHT + TEXT_HEIGHT < drawing.FRONT_KEEP["ArmWidth"][1] - ROW_PITCH
    # The import, arrow sides and proof ride the rebuilt bottom view.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "bottom_annotations = curate_view_dimensions(" in source
    assert "east_annotations = [*bottom_annotations, *footprint_annotations]" in source
    assert '_set_arrow_sides(adapter, east_annotations, BOTTOM_ARROW_SIDES, label="bottom view")' in source
    assert 'rebuild_drawing(adapter, label="bottom view annotations")' in source
    assert '_assert_dimensions_clear(east, BOTTOM_AXES, label="bottom view east stack")' in source


def test_bottom_view_caption_names_view_a_below_the_lower_view() -> None:
    """The caption belongs under the lower view and its coordinate witnesses,
    not above it between two views, without changing the view centre,
    projection or controls.  Machinist review r1 clarity: "VIEW ON MOUNTING
    FACE" had no viewing arrow -- the caption is now VIEW A, named by the
    front view's letter arrow; the sheet has no note block under it."""
    assert drawing.BOTTOM_CAPTION == "VIEW A"
    outline = tuple(v + s for v, s in zip((0.085412, 0.098062, 0.144588, 0.121938), (SHIFT_X, SHIFT_DOWN) * 2))
    lowest_witness = 0.0800219 + SHIFT_DOWN  # native MountingX1, translated
    caption_height = 0.0042891  # native INote.GetExtent, not cap height
    top = lowest_witness - drawing.BOTTOM_CAPTION_GAP_M - drawing.CAPTION_SETTLE_M
    bottom = top - caption_height
    assert top + drawing.BOTTOM_CAPTION_GAP_M < outline[1]
    assert top + drawing.BOTTOM_CAPTION_GAP_M < lowest_witness
    assert bottom > 0.0127 + drawing.BOTTOM_CAPTION_GAP_M  # over the drawable border
    assert drawing.BOTTOM_CAPTION_GAP_M >= 0.002
    assert drawing.CAPTION_SETTLE_M == 0.0006
    assert abs(drawing.BOTTOM_CAPTION_XY[1] - top) < 0.001
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "adapter, bottom, [*east_annotations, *hole_annotations], hole_callout" in source
    assert "lowest = outline[1]" in source
    assert "lowest - BOTTOM_CAPTION_GAP_M - CAPTION_SETTLE_M" in source
    assert "target[1] - extent[4]" in source
    assert "outline[3] + BOTTOM_CAPTION_GAP_M" not in source
    assert "sheet.SetScale(*SHEET_SCALE, False, False)" in source
    assert "front_annotations" not in source[source.index("def _place_bottom_caption("):source.index("_OD_LANDING")]


def _bottom_caption_fixture(monkeypatch, *, scale_result=True, ignore_move=False):
    from types import SimpleNamespace

    outline = (0.085412, 0.098062, 0.144588, 0.121938)
    extent = [0.0848436, 0.1234967, 0.0, 0.1448913, 0.1277858, 0.0]
    annotation = SimpleNamespace(
        GetTextFormat=lambda index: SimpleNamespace(CharHeight=drawing.TEXT_HEIGHT_M)
    )
    note = SimpleNamespace(
        GetExtent=lambda: tuple(extent),
        GetText=lambda: drawing.BOTTOM_CAPTION,
        GetAnnotation=lambda: annotation,
    )
    controls = ["MountingX1"]
    control_lines = [((0.091, 0.10265), (0.091, 0.0800219))]
    control_texts = [(0.0614351, 0.0810219)]
    hole_lines = [((0.1098238, 0.1093554), (0.1730087, 0.0731132))]
    hole_callout = SimpleNamespace(GetAnnotation=lambda: "RD1")
    moves = []

    def move(adapter, target, dx, dy, *, label):
        assert target is annotation
        assert label == "bottom view caption"
        moves.append((dx, dy))
        if not ignore_move:
            for index in (0, 3):
                extent[index] += dx
            for index in (1, 4):
                extent[index] += dy

    sheet = SimpleNamespace(SetScale=lambda *args: scale_result)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet))
    view = SimpleNamespace(GetOutline=lambda: outline)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "add_note", lambda *args: note)
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(
        drawing, "dimension_segments",
        lambda item: hole_lines if item == "RD1" else control_lines,
    )
    monkeypatch.setattr(drawing, "dimension_text_points", lambda item: control_texts)
    monkeypatch.setattr(drawing._telemetry, "info", lambda *args: None)
    return SimpleNamespace(
        args=(adapter, view, controls, hole_callout),
        note=note,
        annotation=annotation,
        extent=extent,
        outline=outline,
        control_lines=control_lines,
        control_texts=control_texts,
        hole_lines=hole_lines,
        moves=moves,
    )


@pytest.mark.parametrize("scale_result", [True, False, None, 1, object()])
def test_bottom_caption_requires_a_real_scale_success(monkeypatch, scale_result) -> None:
    fixture = _bottom_caption_fixture(monkeypatch, scale_result=scale_result)
    if scale_result is True:
        drawing._place_bottom_caption(*fixture.args)
        assert fixture.moves
        assert fixture.extent[4] < fixture.outline[1]
        assert (fixture.extent[0] + fixture.extent[3]) / 2.0 == pytest.approx(
            (fixture.outline[0] + fixture.outline[2]) / 2.0
        )
    else:
        with pytest.raises(RuntimeError, match="cannot pin the sheet scale"):
            drawing._place_bottom_caption(*fixture.args)
        assert not fixture.moves


def test_bottom_caption_uses_the_lower_views_actual_text_and_witness_extent(monkeypatch) -> None:
    fixture = _bottom_caption_fixture(monkeypatch)
    # A lower native text row than its witness must lower the caption further.
    fixture.control_texts[:] = [(0.0614351, 0.0797)]
    drawing._place_bottom_caption(*fixture.args)
    assert fixture.extent[4] == pytest.approx(
        0.0797 - drawing.BOTTOM_CAPTION_GAP_M - drawing.CAPTION_SETTLE_M
    )
    assert fixture.extent[4] < fixture.outline[1]
    assert fixture.extent[1] > 0.0127 + drawing.BOTTOM_CAPTION_GAP_M


def test_bottom_caption_refuses_an_ignored_move_above_the_view(monkeypatch) -> None:
    fixture = _bottom_caption_fixture(monkeypatch, ignore_move=True)
    with pytest.raises(RuntimeError, match="top centre requested"):
        drawing._place_bottom_caption(*fixture.args)
    assert fixture.extent[1] > fixture.outline[3]
    assert len(fixture.moves) == 4


@pytest.mark.parametrize("returned", [None, "", True, 1, object(), "WRONG VIEW"])
def test_bottom_caption_requires_native_text_readback(monkeypatch, returned) -> None:
    fixture = _bottom_caption_fixture(monkeypatch)
    fixture.note.GetText = lambda: returned
    with pytest.raises(RuntimeError, match="caption text did not persist"):
        drawing._place_bottom_caption(*fixture.args)


@pytest.mark.parametrize("height", [0.0, 0.0025, float("nan")])
def test_bottom_caption_preserves_native_sheet_text_height(monkeypatch, height) -> None:
    from types import SimpleNamespace

    fixture = _bottom_caption_fixture(monkeypatch)
    fixture.annotation.GetTextFormat = lambda index: SimpleNamespace(CharHeight=height)
    with pytest.raises(RuntimeError, match="native text height"):
        drawing._place_bottom_caption(*fixture.args)


@pytest.mark.parametrize("extent", [
    (0.1, 0.1, 0.0),
    (0.1, 0.1, 0.0, 0.1, 0.11, 0.0),
    (0.1, 0.1, 0.0, 0.2, float("nan"), 0.0),
])
def test_bottom_caption_requires_positive_finite_native_extent(monkeypatch, extent) -> None:
    fixture = _bottom_caption_fixture(monkeypatch)
    fixture.note.GetExtent = lambda: extent
    with pytest.raises(RuntimeError, match="note has no rendered extent"):
        drawing._place_bottom_caption(*fixture.args)


def test_bottom_caption_refuses_the_hole_callout_leader_overlap(monkeypatch) -> None:
    fixture = _bottom_caption_fixture(monkeypatch)
    fixture.hole_lines[:] = [((0.09, 0.073), (0.14, 0.078))]
    with pytest.raises(RuntimeError, match="hole callout's leader"):
        drawing._place_bottom_caption(*fixture.args)


def test_native_hole_dimensions_keep_names_and_route_annotations(monkeypatch) -> None:
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
        # The Wizard cuts its own 0.102 in, not the pinned 2.591.
        WizardDimension("Thru Hole Dia.@MountingHoles", 0.102 * 25.4),
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
        "MountingHoles": holes,
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
    assert resolved == {"HoleDiameter": "Thru Hole Dia."}
    calls = []
    monkeypatch.setattr(part, "set_dimension_symmetric_tolerance", lambda *args: calls.append(("symmetric", args)))
    monkeypatch.setattr(part, "set_dimension_bilateral_tolerance", lambda *args: calls.append(("bilateral", args)))
    monkeypatch.setattr(part, "set_dimension_display_precision", lambda *args: calls.append(("precision", args)))
    part._apply_native_mounting_annotations(adapter, resolved)
    # No native band: the drilled holes take the title block's band.
    assert calls == [("precision", (adapter, "MountingHoles", "Thru Hole Dia.", 3))]
    assert [dim.Name for dim in native] == original_names
    duplicate = WizardDimension("Second Hole Dia.@MountingHoles", 2.591)
    displays.append(SimpleNamespace(GetDimension=lambda: duplicate))
    with pytest.raises(RuntimeError, match="expected one native HoleDiameter, found 2"):
        part._resolve_native_mounting_dimensions(adapter)
    displays.pop()
    native[0].SystemValue = 2.7 / 1000.0
    with pytest.raises(RuntimeError, match="expected one native HoleDiameter, found 0 among"):
        part._resolve_native_mounting_dimensions(adapter)
    native[0].SystemValue = 2.591 / 1000.0
    native[0].FullName = "Hole Depth@MountingHoles"
    with pytest.raises(RuntimeError, match="expected one native HoleDiameter, found 0"):
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
        "set_dimension_bilateral_tolerance",
        "_apply_native_mounting_annotations",
        "apply_drawing_precision",
        "_arm_root_radius_max_limit",
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


def _mm(*points: tuple[float, float]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Sheet-mm polyline corners -> a list of metre segments."""
    scaled = [(x / 1000.0, y / 1000.0) for x, y in points]
    return [(scaled[i], scaled[i + 1]) for i in range(len(scaled) - 1)]


def test_section_crossings_reports_retry10_and_clears_both_stacks() -> None:
    """The pure crossing rule on measured ink (retry10 native audit,
    20261012T164103041Z): the 3.35's outside-arrow tail (x 231 -> 225 mm)
    ran over the 3.00's x 228 mm witness and the 3.00's tail (228 -> 222 mm)
    over the 7.50's x 223.5 mm witness; a line through a witness collinear
    with one of its own (x 231 mm, shared by all three) is exempt.  On the
    side view's new stack (the 3.00 alone under the arm, the chain's
    columns clear) and the bottom view's east stack (no span ink: a
    vertical dimension with outside arrows draws witnesses, tails and, hung,
    the run and shoulder) it reports nothing."""
    retry10_axes = {"ArmOffset": "x", "ArmBelowAxis": "x", "ArmThickness": "x"}
    retry10 = {
        "ArmOffset": _mm((262.0, 142.5), (231.0, 142.5), (225.0, 142.5))
        + _mm((231.0, 150.0), (231.0, 141.5)) + _mm((234.35, 150.0), (234.35, 141.5)),
        "ArmBelowAxis": _mm((262.0, 134.5), (228.0, 134.5), (222.0, 134.5))
        + _mm((228.0, 147.0), (228.0, 133.5)) + _mm((231.0, 147.0), (231.0, 133.5)),
        "ArmThickness": _mm((182.0, 126.5), (231.0, 126.5), (237.0, 126.5))
        + _mm((223.5, 147.0), (223.5, 125.5)) + _mm((231.0, 147.0), (231.0, 125.5)),
    }
    assert drawing._section_crossings(retry10, retry10_axes) == [
        ("ArmOffset", "ArmBelowAxis"),
        ("ArmBelowAxis", "ArmThickness"),
    ]
    side = {
        "ArmBelowAxis": _mm((282.5, 128.89), (228.0, 128.89), (221.6, 128.89))
        + _mm((228.0, 146.85), (228.0, 127.89)) + _mm((231.0, 146.85), (231.0, 127.89)),
        "SeatToAxis": _mm((198.0, 206.15), (198.0, 185.0)) + _mm((198.0, 170.0), (198.0, 150.96))
        + _mm((227.0, 206.15), (197.0, 206.15)) + _mm((220.65, 150.96), (197.0, 150.96)),
        "ArmPastSeat": _mm((212.0, 157.36), (212.0, 100.04), (234.8, 100.04))
        + _mm((230.0, 147.85), (211.0, 147.85)) + _mm((233.35, 150.96), (211.0, 150.96)),
        drawing.ARM_END_REFERENCE: _mm((259.0, 147.85), (259.0, 170.5))
        + _mm((259.0, 185.1), (259.0, 206.15))
        + _mm((229.0, 206.15), (260.0, 206.15)) + _mm((232.0, 147.85), (260.0, 147.85)),
    }
    assert drawing._section_crossings(side, drawing.SECTION_AXES) == []
    # The bottom view's east stack as designed (BOTTOM_KEEP, BOTTOM_FOOTPRINT_
    # KEEP): the offset hung below on its right hand, the flange height hung
    # above on its left hand, the thickness in-span; the thickness' witnesses
    # cross the two empty spans and the collinear hole-datum witnesses meet.
    bottom = {
        "FootprintOffset": _mm((140.0, 103.65), (151.0, 103.65)) + _mm((140.0, 107.0), (151.0, 107.0))
        + _mm((150.0, 103.65), (150.0, 97.12), (162.2, 97.12)) + _mm((150.0, 107.0), (150.0, 113.35)),
        "FlangeHeight": _mm((140.0, 103.65), (167.0, 103.65)) + _mm((140.0, 116.35), (167.0, 116.35))
        + _mm((166.0, 116.35), (166.0, 123.52), (151.8, 123.52)) + _mm((166.0, 103.65), (166.0, 97.3)),
        "FootprintThickness": _mm((140.0, 107.0), (176.0, 107.0)) + _mm((140.0, 114.5), (176.0, 114.5))
        + _mm((175.0, 107.0), (175.0, 100.65)) + _mm((175.0, 114.5), (175.0, 120.85)),
    }
    assert drawing._section_crossings(bottom, drawing.BOTTOM_AXES) == []
    # What the proof guards: had the flange height drawn its span, the
    # thickness' witnesses would cross it; and the exemption is by the
    # owner's OWN witness only -- the offset's run meets the flange height's
    # hole-datum witness collinear with its own (exempt), but crosses one
    # 0.65 mm lower, inside the run.
    spanned = dict(bottom)
    spanned["FlangeHeight"] = bottom["FlangeHeight"] + _mm((166.0, 103.65), (166.0, 116.35))
    assert drawing._section_crossings(spanned, drawing.BOTTOM_AXES) == [
        ("FlangeHeight", "FootprintThickness"),
    ]
    lowered = dict(bottom)
    lowered["FlangeHeight"] = _mm((140.0, 103.0), (167.0, 103.0)) + bottom["FlangeHeight"][1:]
    assert drawing._section_crossings(lowered, drawing.BOTTOM_AXES) == [
        ("FootprintOffset", "FlangeHeight"),
    ]
    # Line over line counts both ways; a slanted stroke is named as such.
    lines = {"A": _mm((0.0, 10.0), (20.0, 10.0)), "B": _mm((10.0, 10.0), (30.0, 10.0))}
    assert drawing._section_crossings(lines, {"A": "x", "B": "x"}) == [("A", "B"), ("B", "A")]
    assert drawing._section_crossings({"A": _mm((0.0, 0.0), (1.0, 1.0))}, {"A": "x"}) == [("A", "slanted")]
    assert drawing._stroke_axis(((0.0, 0.0), (0.0, 0.0))) == ""


def test_assert_dimensions_clear_reads_the_rebuilt_ink(monkeypatch) -> None:
    import pytest
    ink = {
        "FlangeHeight": _mm((140.0, 103.65), (167.0, 103.65)) + _mm((140.0, 116.35), (167.0, 116.35))
        + _mm((166.0, 116.35), (166.0, 123.52), (151.8, 123.52)) + _mm((166.0, 103.65), (166.0, 97.3)),
        "FootprintThickness": _mm((140.0, 107.0), (176.0, 107.0)) + _mm((140.0, 114.5), (176.0, 114.5))
        + _mm((175.0, 107.0), (175.0, 100.65)) + _mm((175.0, 114.5), (175.0, 120.85)),
    }
    axes = {"FlangeHeight": "y", "FootprintThickness": "y"}
    events, successes = [], []
    monkeypatch.setattr(drawing, "dimension_segments", lambda annotation: ink[annotation])
    monkeypatch.setattr(drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs)))
    monkeypatch.setattr(drawing._telemetry, "success", lambda message, **fields: successes.append(message))
    drawing._assert_dimensions_clear({name: name for name in ink}, axes, label="bottom view east stack")
    assert events[-1][0] == "drawing.dimensions_clear" and events[-1][1]["crossings"] == "[]"
    assert events[-1][1]["label"] == "bottom view east stack"
    assert successes and successes[-1].startswith("bottom view east stack: no dimension line over a foreign witness")
    ink["FlangeHeight"] = ink["FlangeHeight"] + _mm((166.0, 103.65), (166.0, 116.35))
    with pytest.raises(
        RuntimeError,
        match=r"bottom view east stack dimension lines run over witnesses: \[\('FlangeHeight', 'FootprintThickness'\)\]",
    ):
        drawing._assert_dimensions_clear({name: name for name in ink}, axes, label="bottom view east stack")
    ink["FootprintThickness"] = []
    with pytest.raises(RuntimeError, match=r"bottom view east stack dimensions draw no lines: \['FootprintThickness'\]"):
        drawing._assert_dimensions_clear({name: name for name in ink}, axes, label="bottom view east stack")


def test_set_arrow_sides_reads_each_side_back(monkeypatch) -> None:
    from types import SimpleNamespace
    import pytest

    class Stubborn:
        @property
        def ArrowSide(self) -> int:
            return 0

        @ArrowSide.setter
        def ArrowSide(self, value: int) -> None:
            pass

    displays = {
        "FlangeHeight": SimpleNamespace(ArrowSide=0),
        "FootprintOffset": SimpleNamespace(ArrowSide=0),
        "FootprintThickness": SimpleNamespace(ArrowSide=0),
        "MountingY0": SimpleNamespace(ArrowSide=0),
    }
    annotations = [
        SimpleNamespace(name=name, GetSpecificAnnotation=lambda d=display: d)
        for name, display in displays.items()
    ]
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    drawing._set_arrow_sides(object(), annotations, drawing.BOTTOM_ARROW_SIDES, label="bottom view")
    assert {name: d.ArrowSide for name, d in displays.items()} == {
        "FlangeHeight": 1, "FootprintOffset": 1, "FootprintThickness": 1, "MountingY0": 0,
    }
    displays["FlangeHeight"] = Stubborn()
    annotations[0] = SimpleNamespace(name="FlangeHeight", GetSpecificAnnotation=lambda: displays["FlangeHeight"])
    with pytest.raises(RuntimeError, match="bottom view FlangeHeight did not keep its arrows on side 1"):
        drawing._set_arrow_sides(object(), annotations, drawing.BOTTOM_ARROW_SIDES, label="bottom view")
    with pytest.raises(RuntimeError, match=r"no arm section dimension to set arrow sides: \['ArmPastSeat'\]"):
        drawing._set_arrow_sides(
            object(), annotations[1:], {"FootprintOffset": 1, "ArmPastSeat": 1}, label="arm section"
        )


def test_near_side_collar_diameters_style_both_and_prove_against_each_station(monkeypatch) -> None:
    import pytest
    from types import SimpleNamespace
    styled = []
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "set_near_side_diameter", lambda annotation, label: styled.append(label))
    od, bore = SimpleNamespace(name="CollarOd"), SimpleNamespace(name="CollarBore")
    assert drawing._near_side_collar_diameters(object(), [od, bore]) == {"CollarOd": od, "CollarBore": bore}
    assert styled == ["collar CollarOd", "collar CollarBore"]
    with pytest.raises(RuntimeError, match=r"not imported to the side view: \['CollarBore'\]"):
        drawing._near_side_collar_diameters(object(), [od])
    # One assert_leaders_clear group per axis station (the two witnesses are
    # collinear along y 206.15 mm, and a collinear overlap counts as a
    # crossing), each with both diameters, the crank drive gear's bands and
    # a centre-to-far-edge band for the station.
    ink = {
        "CollarOd": _mm((218.05, 219.05), (224.3, 210.9)),
        "CollarBore": _mm((240.05, 219.05), (230.0, 208.3)),
        "SeatToAxis": _mm((227.0, 206.15), (197.0, 206.15)),
        "arm end from bore axis": _mm((229.0, 206.15), (260.0, 206.15)),
    }
    groups = []
    monkeypatch.setattr(drawing, "dimension_segments", lambda annotation: ink[annotation])
    monkeypatch.setattr(
        drawing, "assert_leaders_clear", lambda g, *, centre, keep_out, lands_within, label: groups.append(
            (sorted(g), centre, keep_out, lands_within, label)
        )
    )
    axis = (0.228, 0.20615)
    drawing._prove_collar_diameters_clear(
        {"CollarOd": "CollarOd", "CollarBore": "CollarBore"},
        {"SeatToAxis": "SeatToAxis", "arm end from bore axis": "arm end from bore axis"},
        axis=axis,
    )
    od_r, bore_r = part.COLLAR_OD / 2000.0, drawing.COLLAR_BORE_DIA / 2000.0
    expected_keep_out = {"CollarOd": 0.8 * od_r, "CollarBore": 0.8 * bore_r}
    expected_lands = {"CollarOd": (0.8 * od_r, 1.2 * od_r), "CollarBore": (0.5 * bore_r, 1.5 * bore_r)}
    assert groups == [
        (
            ["CollarBore", "CollarOd", "SeatToAxis"], axis, expected_keep_out,
            {**expected_lands, "SeatToAxis": (0.0, od_r + 0.002)},
            "collar diameters against SeatToAxis",
        ),
        (
            ["CollarBore", "CollarOd", "arm end from bore axis"], axis, expected_keep_out,
            {**expected_lands, "arm end from bore axis": (0.0, od_r + 0.002)},
            "collar diameters against arm end from bore axis",
        ),
    ]


def test_arm_end_reference_is_a_proven_linear_sheet_dimension(monkeypatch) -> None:
    """The side-view drawing-native dimension: entity picks (OD rim, arm end
    edge), linear by Type2, the rim's end on its centre, measured on those
    entities, THEN parenthesised, its places looked up in the spec and read
    back, its callout read back.  Any step's refusal is loud."""
    from types import SimpleNamespace
    import pytest

    rim, end = SimpleNamespace(edge=object()), SimpleNamespace(edge=object())
    calls: list = []
    annotation = object()

    class Display:
        Type2 = 2

        def __init__(self) -> None:
            self.precision = 3
            self.text = {}

        def GetAnnotation(self):
            return annotation

        def SetPrecision3(self, primary, dual, tol_primary, tol_dual):
            calls.append(("precision", primary, dual, tol_primary, tol_dual))
            self.precision = primary
            return 0  # SetPrecision3's native integer success status, not bool

        def GetPrimaryPrecision2(self):
            return self.precision

        def SetText(self, kind, text):
            calls.append(("text", kind, text))
            self.text[kind] = text + "\r"

        def GetText(self, kind):
            return self.text.get(kind)

    display = Display()
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "_collar_od_rim", lambda edges: rim)
    monkeypatch.setattr(drawing, "_arm_end_edge", lambda edges: end)

    def add(adapter_, view, **kwargs):
        calls.append(("add", view, kwargs))
        return display

    monkeypatch.setattr(drawing, "add_edge_dimension", add)
    monkeypatch.setattr(
        drawing, "set_arc_endpoints_to_center", lambda a, d, *, label: calls.append(("arc", d, label))
    )
    monkeypatch.setattr(
        drawing, "assert_dimension_measures",
        lambda a, d, *, expected_mm, label, entities: calls.append(("measures", d, expected_mm, label, entities)),
    )
    monkeypatch.setattr(
        drawing, "set_reference_dimension", lambda a, ann, *, label: calls.append(("reference", ann, label))
    )
    side, edges = object(), object()
    assert drawing._arm_end_reference(adapter, side, edges) is annotation
    label = drawing.ARM_END_REFERENCE
    assert [c[0] for c in calls] == ["add", "arc", "measures", "reference", "precision", "text"]
    add_call = calls[0]
    assert add_call[1] is side
    assert add_call[2]["entities"] == (rim.edge, end.edge)
    assert add_call[2]["orientation"] == "vertical" and add_call[2]["label"] == label
    assert add_call[2]["text_xy"] == drawing.ARM_END_REFERENCE_XY
    assert calls[1] == ("arc", display, label)
    assert calls[2] == ("measures", display, part.ARM_Z[1], label, (rim.edge, end.edge))
    assert calls[3] == ("reference", annotation, label)
    assert calls[4] == ("precision", 2, -1, -1, -1)
    assert calls[5] == ("text", 4, "ARM END\nFROM BORE AXIS")
    # Refusals: a diametric readback, places that did not take, a callout
    # that did not persist.
    for kind in (3, 14):
        display.Type2 = kind
        with pytest.raises(RuntimeError, match="expected a linear dimension"):
            drawing._arm_end_reference(adapter, side, edges)
    display.Type2 = 12
    display.GetPrimaryPrecision2 = lambda: 3
    with pytest.raises(RuntimeError, match="prints 3 decimal places, not 2"):
        drawing._arm_end_reference(adapter, side, edges)
    display.GetPrimaryPrecision2 = lambda: 2
    display.GetText = lambda kind: "ARM END"
    with pytest.raises(RuntimeError, match="callout-below text did not persist"):
        drawing._arm_end_reference(adapter, side, edges)


def test_across_flange_controls_locate_the_bore_without_an_optional_reference() -> None:
    """The 3.35 and 7.50 are NOT a closure across the 12.70 flange.
    Its real Y bounds leave 1.85 at the far edge; the real collar/bore axis
    is Y 0, so the existing 3.35 + 3.00 controls locate it at 6.35 without REF."""
    import magnifying_bracket_joint_layout as joint

    assert part.FLANGE_Y is joint.SIDE_PLATE_Y
    lower_edge, far_edge = part.FLANGE_Y
    arm_lower, arm_upper = part.ARM_Y
    offset = arm_lower - lower_edge
    width = arm_upper - arm_lower
    arm_from_axis = -arm_lower
    remainder = far_edge - arm_upper
    assert offset == pytest.approx(3.35)
    assert width == pytest.approx(7.50)
    assert arm_from_axis == pytest.approx(3.00)
    assert far_edge - lower_edge == pytest.approx(12.70)
    assert remainder == pytest.approx(1.85)
    assert offset + width != pytest.approx(far_edge - lower_edge)
    assert offset + width + remainder == pytest.approx(far_edge - lower_edge)
    assert offset + arm_from_axis == pytest.approx(-joint.SIDE_PLATE_Y[0])
    assert offset + arm_from_axis == pytest.approx(6.35)
    # Every controlling size keeps its routine .XX grade.  Only the arm's
    # Z-chain sum is printed as REF; the Y controls need no duplicate sum.
    assert part.DRAWING_PRECISION["ArmSection"]["ArmBelowAxis"] == 2
    assert part.DRAWING_PRECISION["ArmSection"]["ArmPastSeat"] == 2
    assert part.DRAWING_PRECISION["ArmFootprint"] == {
        "FootprintThickness": 2, "FootprintOffset": 2,
    }
    marked = set().union(*part.DRAWING_DIMENSIONS.values())
    assert mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION == {drawing.ARM_END_REFERENCE: 2}
    assert "FlangeAboveArm" not in marked
    assert drawing.BOTTOM_FOOTPRINT_KEEP.keys() == {"FootprintOffset", "FootprintThickness"}
    assert drawing.SIDE_SECTION_KEEP.keys() == {"ArmBelowAxis", "SeatToAxis", "ArmPastSeat"}


@pytest.mark.parametrize("status", [-1, 1, None, True, False, object()])
def test_reference_precision_requires_native_integer_success(monkeypatch, status) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    display = SimpleNamespace(
        SetPrecision3=lambda *args: status,
        GetPrimaryPrecision2=lambda: 2,  # correct places cannot hide a refusal
    )
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    with pytest.raises(RuntimeError, match="SetPrecision3 did not succeed"):
        drawing._set_reference_precision(adapter, display, label=drawing.ARM_END_REFERENCE)


@pytest.mark.parametrize("places", [3, None, True, "2", object()])
def test_reference_precision_requires_native_applied_places(monkeypatch, places) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    display = SimpleNamespace(SetPrecision3=lambda *args: 0, GetPrimaryPrecision2=lambda: places)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    with pytest.raises(RuntimeError, match="sheet dimension prints"):
        drawing._set_reference_precision(adapter, display, label=drawing.ARM_END_REFERENCE)


def test_bottom_mounting_coordinates_keep_full_witness_ink_and_no_crossings(monkeypatch) -> None:
    """Designed ink, not a farm observation: BOTH mounting X dimensions and
    the hole-Y dimension retain their full flange/hole witnesses in the same
    strict no-ink/slant/crossing guard after dropping the optional REF."""
    west = {
        "MountingX0": _mm((62.75, 89.02), (101.4, 89.02))
        + _mm((91.0, 102.65), (91.0, 88.02)) + _mm((95.0, 102.65), (95.0, 88.02)),
        "MountingX1": _mm((61.45, 81.02), (115.1, 81.02))
        + _mm((91.0, 102.65), (91.0, 80.02)) + _mm((108.7, 102.65), (108.7, 80.02)),
        "MountingY0": _mm((80.0, 103.65), (80.0, 97.25))
        + _mm((80.0, 110.0), (80.0, 113.82), (55.5, 113.82))
        + _mm((90.0, 103.65), (79.0, 103.65)) + _mm((114.1, 110.0), (79.0, 110.0)),
    }
    axes = drawing.BOTTOM_WEST_AXES
    assert axes == {"MountingX0": "x", "MountingX1": "x", "MountingY0": "y"}
    assert west.keys() == drawing.BOTTOM_HOLE_KEEP.keys()
    assert drawing._section_crossings(west, axes) == []
    monkeypatch.setattr(drawing, "dimension_segments", lambda annotation: west[annotation])
    monkeypatch.setattr(drawing._telemetry, "event", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing._telemetry, "success", lambda *args, **kwargs: None)
    annotations = {name: name for name in west}
    drawing._assert_dimensions_clear(annotations, axes, label="bottom view mounting coordinates")
    original = west["MountingX0"]
    west["MountingX0"] = original + _mm((70.0, 100.0), (110.0, 100.0))
    with pytest.raises(RuntimeError, match="dimension lines run over witnesses"):
        drawing._assert_dimensions_clear(annotations, axes, label="bottom view mounting coordinates")
    west["MountingX0"] = original + _mm((70.0, 100.0), (71.0, 101.0))
    with pytest.raises(RuntimeError, match="slanted"):
        drawing._assert_dimensions_clear(annotations, axes, label="bottom view mounting coordinates")
    west["MountingX0"] = []
    with pytest.raises(RuntimeError, match="dimensions draw no lines"):
        drawing._assert_dimensions_clear(annotations, axes, label="bottom view mounting coordinates")


def test_bottom_mounting_coordinates_keep_the_rebuilt_full_stack_proof() -> None:
    import inspect

    source = inspect.getsource(drawing.build)
    assert "hole_annotations = curate_hidden_dimensions(" in source
    assert "west = {dimension_name(adapter, a): a for a in hole_annotations}" in source
    assert "if set(west) != set(BOTTOM_HOLE_KEEP) or len(west) != len(hole_annotations):" in source
    assert "if set(east) != set(BOTTOM_AXES) or len(east) != len(east_annotations):" in source
    rebuild = 'rebuild_drawing(adapter, label="bottom view annotations")'
    east_proof = '_assert_dimensions_clear(east, BOTTOM_AXES, label="bottom view east stack")'
    west_proof = '_assert_dimensions_clear(west, BOTTOM_WEST_AXES, label="bottom view mounting coordinates")'
    caption = "adapter, bottom, [*east_annotations, *hole_annotations], hole_callout"
    arrow = "_add_view_a_arrow(adapter, front)"
    assert (
        source.index(rebuild) < source.index(east_proof) < source.index(west_proof)
        < source.index(caption) < source.index(arrow)
    )


def test_view_a_letter_arrow_points_the_bottom_view_at_the_mounting_face(monkeypatch) -> None:
    """Machinist review r1 clarity: "VIEW ON MOUNTING FACE" had no viewing
    arrow.  A letter A on the front view, its leader tip on the mounting
    face's edge (Z 100.40, front y = 230.15 - Z mm) west of both holes,
    names the bottom view, captioned VIEW A; the letter stands under the
    tip, clear of the flange depth's column and the arm width's rows."""
    import magnifying_bracket_joint_layout as joint

    (text_x, text_y), (tip_x, tip_y) = drawing.VIEW_A_ARROW
    mounting_face_y = drawing.FRONT_ORIGIN_Y - joint.SIDE_PLATE_Z[1] / 1000.0
    assert tip_y == pytest.approx(mounting_face_y, abs=1e-6)
    flange_west = 0.098 + joint.SIDE_PLATE_X[0] / 1000.0
    west_hole = 0.098 + min(point[0] for point in joint.BRACKET_HOLE_POINTS) / 1000.0
    assert flange_west < tip_x < west_hole
    letter = drawing.VIEW_LETTER_HEIGHT
    # The letter hangs under the tip, over the bottom view, 2 mm clear of the
    # flange depth's column (its witnesses and outside-arrow tail, x 53 mm)
    # and left of the arm width's rows (x >= 64 mm).
    assert text_y < tip_y and text_y - letter > BOTTOM_OUTLINE_TOP + TEXT_HEIGHT
    assert text_x > drawing.FRONT_KEEP["FlangeDepth"][0] + 0.002
    assert text_x + letter < 0.064
    calls = []
    monkeypatch.setattr(
        drawing, "add_leader_note", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    adapter, front = object(), object()
    drawing._add_view_a_arrow(adapter, front)
    assert calls == [(
        (adapter, "A"),
        {
            "text_xy": (text_x, text_y),
            "attach_xy": (tip_x, tip_y),
            "view": front,
            "label": "view A viewing arrow",
            "height": letter,
        },
    )]
    assert drawing.BOTTOM_CAPTION == "VIEW " + calls[0][0][1]


def test_arm_root_corners_carry_one_max_radius() -> None:
    """Machinist review r1 clarity: the arm-to-flange inside corners were
    sharp.  The three concave edges on the flange's front face (the arm's
    east face is flush with the flange's east end) take one fillet whose
    radius prints as a single MAX limit (swTolMAX), the part model at the
    printed max; the bounding box is unchanged."""
    spec = mg_magnifying_bracket_spec
    assert spec.ARM_ROOT_R_MAX == 1.0
    assert spec.ARM_ROOT_R_BAND == (0.0, -spec.ARM_ROOT_R_MAX)
    assert spec.RADIUS_TOL_TYPE == 6  # swTolMAX
    assert spec.DRAWING_DIMENSIONS["ArmRootFillet"] == {"ArmRootR"}
    assert spec.DRAWING_PRECISION["ArmRootFillet"] == {"ArmRootR": 1}
    assert "ArmRootR" in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["ArmRootR"] == "ARM ROOT\nCORNERS"
    flange_front = part.FLANGE_Z[0]
    edges = part.ARM_ROOT_EDGES
    assert len(edges) == 3
    assert all(point[2] == flange_front for point, _length in edges)
    assert sum(length for _point, length in edges) == pytest.approx(
        (part.ARM_Y[1] - part.ARM_Y[0]) + 2 * 2 * part.ARM_HALF_X
    )
    assert part.ARM_HALF_X == part.FLANGE_X[1]  # the east face is flush: no corner
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "ArmRootFillet")' in source
    assert 'name_dimensions(adapter, "ArmRootFillet", ["ArmRootR"])' in source
    assert "drive_jobs.append((arm_root[0], '\"ArmRootRMax\"'))" in source
    assert "(1.0 - math.pi / 4.0) * ARM_ROOT_R_MAX ** 2" in source
    assert "tolerance.Type = RADIUS_TOL_TYPE" in source
    assert source.index("apply_drawing_precision(adapter, DRAWING_PRECISION)") < source.index(
        "_arm_root_radius_max_limit(adapter)\n    clear_dimensions_for_drawing"
    )


@pytest.mark.parametrize("returned", [None, "", True, 1, object()])
def test_dimension_callout_requires_native_bstr_readback(monkeypatch, returned) -> None:
    from types import SimpleNamespace

    written = []
    display = SimpleNamespace(
        SetText=lambda kind, text: written.append((kind, text)),
        GetText=lambda kind: returned,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    with pytest.raises(RuntimeError, match="callout-below text did not persist"):
        drawing._set_callout_below(display, "ARM PAST\nMOUNTING\nFACE", "ArmPastSeat")
    assert written == [(4, "ARM PAST\nMOUNTING\nFACE")]


def test_physical_overhang_remains_one_native_control_with_readback() -> None:
    import inspect

    build = inspect.getsource(drawing.build)
    assert drawing.SECTION_CALLOUTS["ArmPastSeat"] == "ARM PAST\nMOUNTING\nFACE"
    assert 'overhang_display = section["ArmPastSeat"].GetSpecificAnnotation()' in build
    assert "if overhang_display is None:" in build
    assert '_set_callout_below(overhang_display, SECTION_CALLOUTS["ArmPastSeat"], "ArmPastSeat")' in build
    assert drawing.SIDE_SECTION_KEEP["ArmPastSeat"] == pytest.approx((0.212, 0.1195 + SHIFT_DOWN))
    assert part.DRAWING_PRECISION["ArmSection"]["ArmPastSeat"] == 2
    assert "ArmPastSeat" not in mg_magnifying_bracket_spec.DRAWING_REFERENCE_PRECISION


@pytest.mark.parametrize("kind", [2, 11, 12, 3, True, False, None, 2.0, object()])
def test_near_arm_face_label_keeps_strict_native_linear_control(monkeypatch, kind) -> None:
    from types import SimpleNamespace

    labels, measures = [], []
    display = SimpleNamespace(Type2=kind)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(
        drawing, "assert_dimension_measures",
        lambda adapter, native, **kwargs: measures.append((native, kwargs)),
    )
    monkeypatch.setattr(
        drawing, "_set_callout_below",
        lambda native, text, label: labels.append((native, text, label)),
    )
    if type(kind) is int and kind in (2, 11, 12):
        drawing._label_near_arm_face(object(), annotation)
        assert measures == [(display, {"expected_mm": 3.0, "label": "ArmBelowAxis"})]
        assert labels == [(display, "NEAR ARM FACE\nTO BORE AXIS", "ArmBelowAxis")]
    else:
        with pytest.raises(RuntimeError, match="expected a linear dimension"):
            drawing._label_near_arm_face(object(), annotation)
        assert measures == [] and labels == []


def test_near_arm_face_label_refuses_a_changed_model_value_or_face(monkeypatch) -> None:
    from types import SimpleNamespace

    display = SimpleNamespace(
        Type2=11, GetDimension2=lambda index: SimpleNamespace(SystemValue=0.0045)
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    import _drawing_edge_dimensions
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(
        _drawing_edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda obj, *args: obj,
    )
    with pytest.raises(RuntimeError, match="measures 4.5 mm, expected 3 mm"):
        drawing._label_near_arm_face(object(), annotation)
    monkeypatch.setattr(drawing, "ARM_Y", (-4.5, 3.0))
    with pytest.raises(RuntimeError, match="nearest the bore axis"):
        drawing._label_near_arm_face(object(), annotation)


def test_arm_face_label_is_applied_before_the_existing_full_witness_proof() -> None:
    import inspect

    source = inspect.getsource(drawing.build)
    label = '_label_near_arm_face(adapter, section["ArmBelowAxis"])'
    rebuild = 'rebuild_drawing(adapter, label="side view annotations")'
    proof = '_assert_dimensions_clear(section, SECTION_AXES, label="side arm section")'
    assert source.index(label) < source.index(rebuild) < source.index(proof)


def test_footprint_offset_nudge_keeps_the_native_two_millimetre_text_gap() -> None:
    # Native15's actual ink top was y 102.0211 mm, 1.6289 mm below the
    # flange-height witness. Only the existing label position moves 0.4 mm;
    # witnesses, arrow sides and every full-stack crossing proof stay intact.
    old_y = 0.1003 + SHIFT_DOWN
    new_y = drawing.BOTTOM_FOOTPRINT_KEEP["FootprintOffset"][1]
    assert old_y - new_y == pytest.approx(0.0004)
    native_gap = 0.0016289 + old_y - new_y
    assert native_gap >= 0.002
    assert drawing.BOTTOM_FOOTPRINT_KEEP["FootprintOffset"][0] == pytest.approx(0.150 + SHIFT_X)
    assert drawing.BOTTOM_KEEP["FlangeHeight"] == pytest.approx((0.166 + SHIFT_X, 0.1263 + SHIFT_DOWN))
    assert drawing.BOTTOM_ARROW_SIDES["FootprintOffset"] == drawing._ARROWS_OUTSIDE
