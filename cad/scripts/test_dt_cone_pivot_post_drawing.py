"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_cone_pivot_post as part
import dt_cone_pivot_post_spec as spec
from dt_cone_post_envelope import BLOCK_DIA
import _layout_geometry as layout
import draw_dt_cone_pivot_post as drawing
from _assembly import _seed_flip, activate_assembly_contract
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM, SEAT_UM, surface_finish_by_key
from machinist_exceptions import load_exceptions


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_cone_pivot_post"].script
        == Path(drawing.__file__).resolve()
    )


def test_post_preserves_harvested_sizes_and_follows_the_configured_axes() -> None:
    # The cast body sits on the .XX grid (1.60 in, machinist review: rule 17
    # gives it no band tighter than the title block's) inside the 1.65 in
    # envelope the platform is laid out on (#2756); the cone boss keeps the
    # harvested 1.654 face-to-face the cone shaft and gear stack close on.
    assert BLOCK_DIA == 41.91
    assert spec.BODY_DIA == 40.64
    assert spec.CONE_BOSS_LENGTH == 42.011
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT) == (42.672, 26.67)
    assert spec.HEAD_BASE_Y == pytest.approx(spec.BLOCK_HEIGHT - spec.HEAD_HEIGHT)
    assert (spec.CRANK_BOSS_DIA, spec.CRANK_BORE_DIA, spec.CRANK_BORE_OFFSET) == (
        21.844,
        11.1379,
        0.0,
    )
    assert spec.CRANK_BORE_HEIGHT == _config.machine(
        "gear_train", "crank_axis_height_mm"
    )
    assert spec.CRANK_ABOVE_CONE == pytest.approx(
        spec.CRANK_BORE_HEIGHT - spec.BORE_HEIGHT
    )
    assert spec.HEAD_BASE_Y < spec.CRANK_BORE_HEIGHT < spec.BLOCK_HEIGHT
    assert spec.CRANK_BOSS_HEAD_MARGIN_MM == pytest.approx(
        min(
            spec.CRANK_BORE_HEIGHT - spec.CRANK_BOSS_DIA / 2.0 - spec.HEAD_BASE_Y,
            spec.BLOCK_HEIGHT - spec.CRANK_BORE_HEIGHT - spec.CRANK_BOSS_DIA / 2.0,
        )
    )
    assert spec.CRANK_BOSS_HEAD_MARGIN_MM > 0.0
    assert spec.CRANK_BOSS_LENGTH_IN == 2.8360
    # v36 (user ruling 2026-09-28): the boss starts at the harvested head's
    # tangent plane, on the .XXX grid its station prints at, and runs the
    # harvested 2.8360 in from there.
    assert spec.CRANK_BOSS_NORTH_FACE == pytest.approx(0.842 * 25.4)
    assert spec.CRANK_BOSS_NORTH_FACE >= spec.HEAD_DIA / 2.0
    assert spec.CRANK_BOSS_START_Z == -spec.CRANK_BOSS_NORTH_FACE
    assert spec.CRANK_BOSS_END_Z == pytest.approx((2.8360 - 0.842) * 25.4)
    assert spec.CRANK_BOSS_LENGTH == pytest.approx(2.8360 * 25.4)
    from _cone_axis_constants import CONE_AXIS_HEIGHT_MM
    from dt_post_mount_stack import POST_BODY_HEIGHT_MM

    # Both bores .4385 +.0005/0 (owner ruling 2026-11-23, tool audit Q11).
    assert (spec.CONE_BOSS_DIA, spec.BORE_DIA) == (17.272, 11.1379)
    assert spec.BORE_HEIGHT == CONE_AXIS_HEIGHT_MM
    assert spec.BLOCK_HEIGHT == POST_BODY_HEIGHT_MM
    assert spec.INCLINE_DEG == _config.machine("cone_incline", "derived_incline_deg")
    assert (
        spec.ATTACHMENT_THRU_DIA,
        spec.ATTACHMENT_CBORE_DIA,
        spec.ATTACHMENT_CBORE_DEPTH,
    ) == (7.493, 11.5062, 6.0198)
    assert spec.ATTACHMENT_SPACING == 2.0 * spec.ATTACHMENT_X
    # The final volume is the per-feature sum the build checks natively; a
    # constant that drifts from the features (the 2026-09-21 unbored-boss
    # build) fails at import, so only mass coherence is left to pin here.
    assert spec.HARVESTED_VOLUME_MM3 == pytest.approx(
        part._ANALYTIC_FINAL_MM3, abs=0.5e-4, rel=0.0
    )
    assert spec.HARVESTED_MASS_KG == spec.HARVESTED_VOLUME_MM3 * 7.2e-6
    assert part.CRANK_BORE_MM3 == pytest.approx(
        math.pi * (spec.CRANK_BORE_DIA / 2.0) ** 2 * spec.CRANK_BOSS_LENGTH
    )
    assert part.ATTACHMENT_HOLES_MM3 == pytest.approx(
        2.0
        * math.pi
        * (
            (spec.ATTACHMENT_THRU_DIA / 2.0) ** 2
            * (spec.BLOCK_HEIGHT - spec.ATTACHMENT_CBORE_DEPTH)
            + (spec.ATTACHMENT_CBORE_DIA / 2.0) ** 2 * spec.ATTACHMENT_CBORE_DEPTH
        )
    )
    assert part.MAIN_BODY_MM3 == pytest.approx(
        math.pi * (spec.BODY_DIA / 2.0) ** 2 * spec.BLOCK_HEIGHT
    )
    assert part.HEAD_SHELL_MM3 == pytest.approx(
        math.pi
        * ((spec.HEAD_DIA / 2.0) ** 2 - (spec.BODY_DIA / 2.0) ** 2)
        * spec.HEAD_HEIGHT
    )


def test_mounting_counterbores_keep_the_wall_target_to_the_head() -> None:
    """The Ø1.68 head keeps the .080 in target at the counterbores' printed
    corners (#290: the mm sheet's .X head left only the 1.5 mm floor)."""
    assert spec.DRAWING_PRECISION_BY_NAME["HeadDia"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["MountWestX"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["MountEastX"] == 2
    head_radius_min = (spec.HEAD_DIA - 0.254) / 2.0
    cbore_radius_max = (spec.ATTACHMENT_CBORE_DIA + 0.127) / 2.0
    wall = head_radius_min - (spec.ATTACHMENT_X + 0.254) - cbore_radius_max
    assert spec.ATTACHMENT_X == pytest.approx(12.954)
    assert spec.ATTACHMENT_SPACING == pytest.approx(25.908)
    assert wall == pytest.approx(spec.MOUNT_HEAD_WEB_WORST)
    assert wall >= 2.032 - 1e-9


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.TOP_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.JOURNAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert marked == {
        "MainBodyDia",
        "MainBodyHt",
        "HeadDia",
        "HeadHt",
        "MountWestX",
        "MountEastX",
        "CrankAxisY",
        "CrankAboveCone",
        "CrankBossDia",
        "CrankBossLen",
        "ConeBossLen",
        "ConeBossNorthZ",
        "CrankBoreDia",
        "JournalAxisY",
        "ConeBossDia",
        "JournalBoreDia",
        "CrankBossStartZ",
        "InclineAngle",
        "JournalRimBreak",
    }
    # No dimension may be placed twice: two views that both carry a value are
    # two chances for the sheet to contradict itself.
    assert len(drawing.FRONT_KEEP) + len(drawing.TOP_KEEP) + len(
        drawing.SECTION_KEEP
    ) + len(drawing.JOURNAL_KEEP) + len(drawing.DETAIL_KEEP) == len(kept)


def test_mounting_hole_callouts_cite_their_split_helper_owner() -> None:
    from _drawing_hole_callout import add_native_hole_callout
    from _feature_requirements import requirements_for

    assert drawing.add_native_hole_callout is add_native_hole_callout
    requirements = requirements_for(drawing)
    for name in ("mount_west", "mount_east"):
        assert requirements[name].fields["dia"][1] == (
            "ATTACHMENT_THRU_DIA",
            "UNIT",
            ("_drawing_hole_callout", "add_native_hole_callout"),
        )


def _landscape_sheet() -> tuple[object, tuple]:
    from _layout_geometry import DrawableRegion
    from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
    from diagnostics.drawing_layout_audit import _keep_outs
    ZONE_MARGINS = {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127}

    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    region = DrawableRegion.from_margins(
        template.width_m, template.height_m, **ZONE_MARGINS
    )
    return region, _keep_outs(template.width_m, template.height_m)


def test_view_placement_flags_the_border_and_the_title_block() -> None:
    region, keep_outs = _landscape_sheet()
    outlines = {
        "over the block": (0.300, 0.050, 0.350, 0.120),
        "off the left": (0.005, 0.100, 0.060, 0.150),
        "clear": (0.100, 0.100, 0.150, 0.150),
    }
    problems = drawing.view_placement_problems(outlines, region, keep_outs)
    assert len(problems) == 2
    assert "over the block reaches into the title-block" in problems[0]
    assert "off the left leaves the inner border" in problems[1]


def _crank_evidence() -> dict:
    """The crank boss's BREP evidence as draw_cone_pivot_post reads it (model
    metres): its north face on the head's tangent plane and its far face."""
    y = spec.CRANK_BORE_HEIGHT / 1000.0
    north = ("plane", (0.0, 0.0, 1.0, 0.0, y, spec.CRANK_BOSS_START_Z / 1000.0))
    far = ("plane", (0.0, 0.0, 1.0, 0.0, y, spec.CRANK_BOSS_END_Z / 1000.0))
    wall = ("cylinder", (0.0, y, 0.0, 0.0, 0.0, 1.0, spec.CRANK_BOSS_DIA / 2000.0))
    return {"CrankSprocketBoss": [far, wall, north]}


def test_the_crank_boss_faces_resolve_to_north_then_far() -> None:
    north, far = drawing._crank_face_centres(_crank_evidence())
    assert north[2] * 1000.0 == pytest.approx(spec.CRANK_BOSS_START_Z)
    assert far[2] * 1000.0 == pytest.approx(spec.CRANK_BOSS_END_Z)


def test_the_crank_boss_face_set_is_asserted_not_guessed() -> None:
    """A boss missing a face, or a north face off its station, fails."""
    evidence = _crank_evidence()
    evidence["CrankSprocketBoss"] = evidence["CrankSprocketBoss"][1:]
    with pytest.raises(RuntimeError, match="expected 2"):
        drawing._crank_face_centres(evidence)
    evidence = _crank_evidence()
    kind, values = evidence["CrankSprocketBoss"][2]
    evidence["CrankSprocketBoss"][2] = (kind, values[:5] + (values[5] - 0.0025,))
    with pytest.raises(RuntimeError, match="north face"):
        drawing._crank_face_centres(evidence)


def test_inclined_journal_sizes_live_in_the_true_shape_view() -> None:
    """The cone-axis view alone exposes the boss OD and bore in true shape.

    It is also the one view showing both bores, so the crank-above-cone
    spacing chains off the cone-axis height there.
    """
    cone_owned = (
        spec.DRAWING_DIMENSIONS["ConeBossProfile"]
        | spec.DRAWING_DIMENSIONS["JournalBoreProfile"]
        | spec.DRAWING_DIMENSIONS["BoreSpacingReference"]
    )
    # View C also sees the head side-on; its Ø is given there (r8 rule 11).
    assert set(drawing.JOURNAL_KEEP) == cone_owned | {"HeadDia"}
    assert drawing.CONE_AXIS_VIEW == part.CONE_AXIS_VIEW == "CONE JOURNAL"


def test_cone_boss_length_lives_in_the_bore_plane_section() -> None:
    """The raised boss's axial extent is dimensioned where its profile is
    visible, and the collar's thrust face is located there from the post
    axis (rule 10), not by a symmetry note."""
    assert drawing.SECTION_SCALE == (1, 1)
    assert set(drawing.SECTION_KEEP) == {"ConeBossLen", "ConeBossNorthZ"}
    assert "ConeBossLen" not in drawing.TOP_KEEP
    assert "SYMMETRIC" not in spec.DRAWING_NOTES
    start, end = drawing.CONE_SECTION_LINE
    assert start[1] == end[1] == drawing._front_y(spec.BORE_HEIGHT)
    assert start[0] < drawing.FRONT_CENTER[0] < end[0]


def test_cone_boss_north_station_shares_the_face_to_face_global() -> None:
    """The printed collar-face station and the boss extrusion cannot drift
    apart, and its band is the title block's .XXX (owner ruling 2026-11-24,
    audit part 2 C9), which the stacks book from the station's limits."""
    assert spec.CONE_BOSS_NORTH_STATION == spec.CONE_BOSS_LENGTH / 2.0
    assert spec.CONE_BOSS_NORTH_STATION_DEVIATIONS_MM == spec.printed_deviations(
        spec.CONE_BOSS_NORTH_STATION, 3, unit=spec.UNIT
    )
    assert spec.CONE_BOSS_NORTH_STATION_TOLERANCE_MM == pytest.approx(0.005 * 25.4, abs=1e-3)


def test_part_owns_every_printed_decimal_place() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set().union(
        *spec.DRAWING_DIMENSIONS.values()
    )
    assert "draw_dt_cone_pivot_post.py" in PRECISION_MIGRATED_DRAWINGS
    # The bores earn extra places for their limits, the harvested 1.654 boss
    # length and the closures print .XXX, the rims' break its .004 MAX, and
    # the basic plan angle prints the model's exact value (#906, it feeds the
    # frame).
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places >= 3
    } == {
        "CrankBoreDia",
        "JournalBoreDia",
        "InclineAngle",
        "ConeBossLen",
        "CrankBossLen",
        "CrankAxisY",
        "CrankAboveCone",
        "ConeBossNorthZ",
        "CrankBossStartZ",
        "JournalRimBreak",
    }


def test_running_bores_close_the_configured_fit_class() -> None:
    """User ruling 2026-09-28: MHA-DT-11 runs directly in the Ø11.43 crank
    bore; each bore's band closes the one running fit on its own shaft."""
    import _config
    import dt_cone_gear_shaft_spec
    import dt_crankshaft_spec

    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    for bore, (upper, lower), shaft_nominal, shaft_band in (
        (
            spec.CRANK_BORE_DIA,
            spec.RUNNING_BORE_BAND,
            dt_crankshaft_spec.JOURNAL_DIA,
            dt_crankshaft_spec.JOURNAL_DIA_BAND,
        ),
        (
            spec.BORE_DIA,
            spec.JOURNAL_BORE_BAND,
            dt_cone_gear_shaft_spec.JOURNAL_DIA,
            dt_cone_gear_shaft_spec.SECTION_DIA_BANDS[0],
        ),
    ):
        shaft_max = shaft_nominal + shaft_band[0]
        shaft_min = shaft_nominal + shaft_band[1]
        clearances = (bore + lower - shaft_max, bore + upper - shaft_min)
        assert tuple(round(value, 5) for value in clearances) == expected


def test_nothing_else_on_the_casting_carries_a_band() -> None:
    """Each band named once, applied to the features whose fit needs it.

    The cast body, head and boss diameters and the mounting-hole stations
    are not accuracy features (cad/docs/tolerance-policy.md, "Result"), so the
    part must not author a tolerance on them at all: the title block's general
    grade is the whole specification (#2756 retired the body's one-sided
    band for a smaller nominal).  The one symmetric band is the collar thrust
    face's station; the cone-axis height's capture band is the title block's
    .XX (machinist review: an explicit ±.01 repeated it).
    """
    assert not hasattr(spec, "MAIN_BODY_DIA_BAND")
    assert spec.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM == pytest.approx(0.254)
    assert not hasattr(spec, "TURNED_DIAMETER_TOLERANCE_MM")
    assert not hasattr(spec, "CRANK_BORE_TOLERANCE_MM")


def test_the_plan_angle_is_model_geometry_not_sheet_text() -> None:
    """The configured plan incline is a DRIVING model dimension.

    A driven reference angle cannot express it: SOLIDWORKS returns the
    obtuse member of a line pair whatever the ray directions, the selection
    order or the text position.  A driving dimension fixes the quadrant when
    the sketch is authored, and driving it from the same ``ConeIncline``
    global that builds ConeShaftNormal is what stops the printed value and
    the built geometry from drifting apart.
    """
    assert spec.DRAWING_DIMENSIONS["JournalPlanReference"] == {"InclineAngle"}
    # The station has its own sketch: a view dimensioning only it must not
    # print the plan-angle rays.
    assert spec.DRAWING_DIMENSIONS["CrankBossStationReference"] == {"CrankBossStartZ"}
    assert spec.CRANK_BOSS_NEAR_Z == spec.CRANK_BOSS_NORTH_FACE
    incline = math.radians(_config.machine("cone_incline", "derived_incline_deg"))
    assert spec.JOURNAL_REFERENCE_X == pytest.approx(
        spec.JOURNAL_REFERENCE_LENGTH * math.sin(incline)
    )
    assert spec.JOURNAL_REFERENCE_Z == pytest.approx(
        spec.JOURNAL_REFERENCE_LENGTH * math.cos(incline)
    )


def test_machined_faces_are_called_out_on_the_casting() -> None:
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    keys = {control.key for control in spec.SURFACE_FINISHES}
    assert keys == {"foot_seat", "crank_bore", "journal_bore", "cone_boss_north_face"}
    assert (
        surface_finish_by_key(spec.SURFACE_FINISHES, "foot_seat").roughness_um
        == SEAT_UM
    )
    for key in ("crank_bore", "journal_bore"):
        assert (
            surface_finish_by_key(spec.SURFACE_FINISHES, key).roughness_um
            == MACHINED_UM
        )
    seat = surface_finish_by_key(spec.SURFACE_FINISHES, "foot_seat").face
    assert seat.normal == (0, -1, 0) and seat.offset_mm == 0.0
    crank = surface_finish_by_key(spec.SURFACE_FINISHES, "crank_bore").face
    assert (crank.diameter_mm, crank.contains_y_mm) == (
        spec.CRANK_BORE_DIA,
        spec.CRANK_BORE_HEIGHT,
    )
    journal = surface_finish_by_key(spec.SURFACE_FINISHES, "journal_bore").face
    assert (journal.diameter_mm, journal.contains_y_mm) == (
        spec.BORE_DIA,
        spec.BORE_HEIGHT,
    )


def test_the_one_allowlisted_frame_is_the_crank_bore_angularity() -> None:
    """#906 (USER RULING 2026-09-26, option ii): the package's RV-01 machinist exception.

    One diametral angularity frame on the crank bore to datum A, the cone
    journal bore, clocked by datum B, the foot seat; its value is the spec
    constant, never sheet text, and it bounds yaw and tilt to about 0.08 deg
    over the boss.  A alone would leave tilt free.
    """
    from _gtol_cylinder import CylinderFace
    from _gtol_planar import PlanarFace

    assert spec.GEOMETRIC_TOLERANCES_MM == {}
    journal, foot = spec.PART_DATUMS
    assert journal.letter == "A"
    assert journal.face == CylinderFace(spec.BORE_DIA, contains_y_mm=spec.BORE_HEIGHT)
    assert foot.letter == "B"
    assert foot.face == PlanarFace((0, -1, 0), 0.0)
    assert foot.face == spec.SURFACE_FINISHES[0].face
    (frame,) = spec.GEOMETRIC_CONTROLS
    assert frame.characteristic == "angularity"
    assert frame.tolerance_zone == "diametral"
    assert frame.datums == ("A", "B")
    assert frame.tolerance == spec.CRANK_BORE_ANGULARITY_IN == ".004"
    assert frame.face == CylinderFace(
        spec.CRANK_BORE_DIA, contains_y_mm=spec.CRANK_BORE_HEIGHT
    )
    # The zone spans the boss: 0.0808 deg over its 72.03.
    assert round(spec.CRANK_BORE_ANGLE_LIMIT_DEG, 4) == 0.0808
    assert part.PART_DATUMS is spec.PART_DATUMS
    assert part.GEOMETRIC_CONTROLS is spec.GEOMETRIC_CONTROLS
    exceptions = {
        exception.id: exception
        for exception in load_exceptions(
            _config.CONFIG_DIR, "dt_cone_pivot_post", "part"
        )
    }
    # RV-02 is the callout-precision exception (its own test below).
    assert set(exceptions) == {"RV-01", "RV-02"}
    exception = exceptions["RV-01"]
    assert exception.kind == "accept"
    assert "crank-bore diametral angularity frame" in exception.where


def test_part_exposes_semantic_mating_references() -> None:
    assert not hasattr(part, "CRANK_BORE_DX")
    assert not hasattr(part, "CRANK_BORE_Y")


def test_boss_north_is_the_whole_north_annulus_on_the_journal() -> None:
    """#916: BossNorth sits half a pad length north of ConeShaftNormal on the
    journal axis, faces away from the pads, and its face is the whole annulus
    between the pad and the journal rim's break."""
    import math

    incline = math.radians(spec.INCLINE_DEG)
    axis = (math.sin(incline), 0.0, math.cos(incline))
    assert part.BOSS_NORTH_NORMAL == pytest.approx([-c for c in axis], abs=1e-12)
    offset = [
        c - b for c, b in zip(part.BOSS_NORTH_CENTRE, (0.0, spec.BORE_HEIGHT, 0.0))
    ]
    assert offset == pytest.approx(
        [-spec.CONE_BOSS_LENGTH / 2.0 * c for c in axis], abs=1e-12
    )
    assert part.BOSS_NORTH_AREA == pytest.approx(
        math.pi
        / 4.0
        * (spec.CONE_BOSS_DIA**2 - (spec.BORE_DIA + 2.0 * spec.JOURNAL_RIM_BREAK) ** 2)
    )


def test_rotated_post_reverses_the_cone_shaft_axial_mate_side() -> None:
    activate_assembly_contract("dt-drive-train")
    assert not _seed_flip("cone-shaft axial d=22.01", 22.01)


def test_v2_feature_topology_uses_midplane_extrusions_and_hole_wizard() -> None:
    assert part.ATTACHMENT_HOLE_SPEC.kind == "counterbore_fillister"
    assert part.ATTACHMENT_HOLE_SPEC.size == "1/4"
    assert part.ATTACHMENT_HOLE_SPEC.overrides_mm == {
        "HoleDiameter": spec.ATTACHMENT_THRU_DIA,
        "CounterBoreDiameter": spec.ATTACHMENT_CBORE_DIA,
        "CounterBoreDepth": spec.ATTACHMENT_CBORE_DEPTH,
    }


def test_part_config_is_a_machined_casting() -> None:
    import _config

    config = _config.parts("dt-cone-pivot-post")
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    finish = str(config["finish"])
    assert "RAL 6005" in finish
    assert "SSPC-SP 3" in finish
    assert "MASK MACHINED FACES" in finish
    assert "OIL BARE FACES ISO VG 32" in finish
    assert config["process"] == "machined from solid stock or casting"
    assert int(config["quantity"]) == 1


def test_journal_rims_print_the_thrust_ring_break() -> None:
    """Codex P1 on #916 (PRRT_kwDOPHDy386mTQ-u): the collar's thrust ring is
    bounded by the collar OD edge AND the post's journal rim, and each rim
    ends the journal span the shaft's stack books, so both rims carry the
    break; on the former Ø.483 bore the title block's .010 left the worst-case
    ring under its 1.5 floor.  The Ø.4385 bore (owner ruling 2026-11-23, tool
    audit Q11) widens the ring; the printed .004 MAX stays."""
    import _config
    import dt_cone_gear_shaft_spec as shaft

    break_max = shaft.THRUST_EDGE_BREAK_MAX
    assert spec.JOURNAL_RIM_BREAK == pytest.approx(break_max, abs=1e-12)
    assert spec.JOURNAL_RIM_BREAK_BAND == (0.0, -spec.JOURNAL_RIM_BREAK)
    # R5 fix attempts 1 and 2 printed the break as text, at the bore's
    # callout and in note 2; both readings asked which edges.  The part
    # models it on both rims and the sheet prints its leg natively in detail
    # D, saying which rims and why under the value; no note carries it.
    assert spec.DRAWING_DIMENSIONS["JournalRimBreakReference"] == {"JournalRimBreak"}
    assert spec.DRAWING_PRECISION["JournalRimBreakReference"] == {"JournalRimBreak": 3}
    assert drawing.DIMENSION_CALLOUTS["JournalRimBreak"] == (
        "BOTH BORE RIMS\nKEEPS MHA-DT-04 BEARING AREA"
    )
    assert drawing.DIMENSION_CALLOUTS["JournalBoreDia"] == "REAM THRU, SEE NOTE 2"
    assert "BREAK" not in drawing.SHEET_NOTES
    assert shaft.inch_text(break_max, 3) not in drawing.SHEET_NOTES
    assert "CONE SHAFT MHA-DT-04" in _note(2)
    assert f"EDGE BREAK {shaft.inch_text(break_max, 3)} MAX" in shaft.COLLAR_STOCK_CALLOUT
    ring = shaft.THRUST_RING_MIN
    assert ring - 2.0 * break_max >= shaft.THRUST_RING_FLOOR
    # Ø.4385 bore: the ring now holds the floor even under the general break,
    # and the printed .004 MAX is kept (the ruling moved the bore only).
    general = max(
        float(_config.title_block("edge_break")[key])
        for key in ("radius_mm", "chamfer_max_mm")
    )
    assert ring - break_max - general >= shaft.THRUST_RING_FLOOR
    assert break_max == pytest.approx(0.004 * 25.4)
    # the ring's bore edge is the post's running bore at its band's top
    assert shaft.POST_JOURNAL_BORE_BAND == spec.JOURNAL_BORE_BAND


def test_both_journal_rims_are_broken_in_the_model() -> None:
    """The chamfer takes both rims, one pick at each boss end on the rim
    circle, and comes off the analytic volume; the printed leg's reference
    line runs from the far rim's sharp along the far face."""
    import math

    assert len(part.JOURNAL_RIM_POINTS) == 2
    axis = (-part.BOSS_NORTH_NORMAL[0], 0.0, -part.BOSS_NORTH_NORMAL[2])
    stations = []
    for point in part.JOURNAL_RIM_POINTS:
        offset = [p - b for p, b in zip(point, (0.0, spec.BORE_HEIGHT, 0.0))]
        along = sum(o * a for o, a in zip(offset, axis))
        radial = math.sqrt(sum(o * o for o in offset) - along**2)
        assert radial == pytest.approx(spec.BORE_DIA / 2.0, abs=1e-9)
        stations.append(along)
    assert stations == pytest.approx(
        [-spec.CONE_BOSS_LENGTH / 2.0, spec.CONE_BOSS_LENGTH / 2.0], abs=1e-9
    )
    assert part.JOURNAL_RIM_BREAKS_MM3 == pytest.approx(
        2.0
        * math.pi
        * spec.JOURNAL_RIM_BREAK**2
        * (spec.BORE_DIA / 2.0 + spec.JOURNAL_RIM_BREAK / 3.0)
    )
    assert "JournalRimBreakReference" in part.REFERENCE_SKETCHES
    leg = [
        b - a for a, b in zip(part.JOURNAL_RIM_CORNER_MM, part.JOURNAL_RIM_BREAK_END_MM)
    ]
    assert math.hypot(*leg) == pytest.approx(spec.JOURNAL_RIM_BREAK, abs=1e-12)
    assert sum(component * a for component, a in zip(leg, axis)) == pytest.approx(
        0.0, abs=1e-12
    )
    # The sheet's detail D looks at the very sharp the part's leg starts from.
    assert drawing.RIM_CORNER_MM == pytest.approx(part.JOURNAL_RIM_CORNER_MM, abs=1e-12)


def test_rim_break_detail_stands_in_free_sheet_space() -> None:
    """Detail D (20:1 of Section A-A) and its break's block stand in the open
    sheet over the title block, clear of View C's datum A tag and the
    isometric; its letter is no datum's or view's."""
    region, keep_outs = _landscape_sheet()
    title_block = dict(keep_outs)["title-block"]
    letters = {datum.letter for datum in spec.PART_DATUMS}
    assert drawing.RIM_DETAIL_LETTER not in letters | {"A", drawing.JOURNAL_VIEW_LETTER}
    assert drawing.RIM_DETAIL_SCALE == (20, 1)
    cx, cy = drawing.RIM_DETAIL_CENTER
    r = drawing.RIM_DETAIL_CROP_RADIUS
    assert r == pytest.approx(drawing.RIM_DETAIL_RADIUS_MM * 0.020)
    assert cy - r >= title_block.ymax + 0.010
    assert cx - r > drawing.DATUM_A_TAG_XY[0] + 0.015
    assert cy + r < drawing.ISO_CENTER[1] - 0.030
    keep_x, keep_y = drawing.DETAIL_KEEP["JournalRimBreak"]
    block_left = keep_x - drawing.JOURNAL_RIM_BREAK_TEXT_WIDTH / 2.0
    assert block_left >= cx + r + 0.004 - 1e-12
    assert keep_x + drawing.JOURNAL_RIM_BREAK_TEXT_WIDTH / 2.0 <= region.xmax - 0.005
    assert keep_y - 0.010 > title_block.ymax
    # The label hangs from its top over the circle.
    assert drawing.RIM_DETAIL_LABEL_XY[1] - 0.0135 >= cy + r


def test_collar_thrust_face_adds_no_setup_note() -> None:
    """#914: the collar face gets a finish symbol, not a method note (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).

    Squareness of the north boss end is not functional (the journal locates
    the shaft), so no note may prescribe facing it or a setup for it; the one
    SETUP line is the bore-to-bore requirement that predates the collar.
    """
    lines = spec.DRAWING_NOTES.splitlines()
    assert not [line for line in lines if line.startswith("FACE")]
    assert [line for line in lines if "SETUP" in line] == [
        line for line in lines if line.startswith("BORE BOTH IN ONE SETUP")
    ]
    assert spec.GEOMETRIC_TOLERANCES_MM == {}


def test_north_cone_boss_end_carries_the_running_finish() -> None:
    """#914: the shaft collar runs on the north boss end face (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates))."""
    import math

    from _gtol_planar import PlanarFace
    from dt_cone_pivot_post_installation import POST_ROTATION_Y_DEG

    control = surface_finish_by_key(spec.SURFACE_FINISHES, "cone_boss_north_face")
    assert control.roughness_um == MACHINED_UM
    face = control.face
    assert isinstance(face, PlanarFace)
    incline = math.radians(spec.INCLINE_DEG)
    expected = (-math.sin(incline), 0.0, -math.cos(incline))
    assert all(abs(a - b) < 1e-12 for a, b in zip(face.normal, expected))
    assert face.offset_mm == spec.CONE_BOSS_LENGTH / 2.0
    # North is machine +Z (cone stations grow toward the gears).  The post is
    # installed Ry(180), which maps part (x, y, z) to machine (-x, y, -z), so
    # the north face's outward normal must point to machine +Z.
    assert POST_ROTATION_Y_DEG == 180.0
    machine_normal = (-face.normal[0], face.normal[1], -face.normal[2])
    assert machine_normal[2] > 0.9


def test_foot_seat_mate_rides_its_ra_symbol_not_a_loose_note() -> None:
    """PR #2107 machinist review (clarity, gating): the foot's mate stood in a
    loose general note, not on the callout it explains; it prints over the
    foot seat's Ra.  The part carries no general note; the sheet's only notes
    are the numbered fit notes its bore callouts flag."""
    foot = surface_finish_by_key(spec.SURFACE_FINISHES, "foot_seat")
    assert (
        foot.production_method == spec.FOOT_SEAT_FINISH_TARGET == "SEATS ON MHA-DT-20"
    )
    assert spec.DRAWING_NOTES == ""


def test_body_diameter_claims_no_unmeasurable_flushness() -> None:
    """PR #2107 machinist review (clarity): FLUSH WITH CONE BOSS FACES was not
    guaranteed by the body Ø's and the .827 station's printed limits; each band
    governs its own surface (crank_boss_rim proves the 64T clear of both)."""
    assert "MainBodyDia" not in drawing.DIMENSION_CALLOUTS
    assert not [text for text in drawing.DIMENSION_CALLOUTS.values() if "FLUSH" in text]


def test_body_diameter_takes_the_title_block_band() -> None:
    """MHA-DT-05 machinist review (gating, rule 17): Ø1.654 printed three
    places only because the harvested 42.011 sat off the .XX grid.  #2756 (R5
    machinist review, blocker): on the Ø1.65 envelope the cone boss ends
    stood .002 proud and fell flush or inside the body at its printed limits.
    The cast body is Ø1.60 at the title block's .XX band, inside the
    envelope, so both pads stand at least the title block's edge break proud
    at every printed limit and the mounting holes' outer wall still clears
    its floor."""
    assert spec.DRAWING_PRECISION_BY_NAME["MainBodyDia"] == 2
    assert round(spec.BODY_DIA / 25.4, 2) == pytest.approx(
        spec.BODY_DIA / 25.4, abs=1e-9
    )
    assert spec._printed_limits(spec.BODY_DIA, 2)[1] <= BLOCK_DIA
    assert "MainBodyDia" not in drawing.DIMENSION_SUFFIXES
    assert drawing.FRONT_KEEP["MainBodyDia"][0] == 0.150
    assert spec.MOUNT_OTHER_WEBS_WORST["body foot OD"] == pytest.approx(
        spec._printed_limits(spec.BODY_DIA, 2)[0] / 2.0
        - spec._printed_limits(spec.ATTACHMENT_X, 2)[1]
        - (spec.ATTACHMENT_THRU_DIA + spec._DRILL_OVERSIZE) / 2.0
    )
    assert spec.MOUNT_OTHER_WEBS_WORST["body foot OD"] >= spec.WALL_TARGET_MM
    assert drawing.BODY.fields["dia"][0] == pytest.approx(
        [spec.BODY_DIA - 0.254, spec.BODY_DIA + 0.254]
    )


def test_both_cone_bosses_stand_proud_of_the_body_at_every_limit() -> None:
    """#2756: the north face's least station (.827 - .005, the title block
    since owner ruling 2026-11-24, audit part 2 C9) and the far face's
    (1.654's least less the north face's greatest) each clear the body's
    largest radius by at least the title block's edge break, so the pads are
    real cast bosses a shop can face, never flush with or inside the round."""
    inch = 25.4
    body_r_max = (round(spec.BODY_DIA / inch, 2) + 0.01) / 2.0
    north_min = 0.827 - 0.005
    far_min = (1.654 - 0.005) - (0.827 + 0.005)
    assert spec.CONE_BOSS_STANDOFF_WORST_MM["north"] == pytest.approx(
        (north_min - body_r_max) * inch
    )
    assert spec.CONE_BOSS_STANDOFF_WORST_MM["far"] == pytest.approx(
        (far_min - body_r_max) * inch
    )
    assert spec.CONE_BOSS_STANDOFF_FLOOR_MM == pytest.approx(0.010 * inch)
    assert (
        min(spec.CONE_BOSS_STANDOFF_WORST_MM.values())
        >= spec.CONE_BOSS_STANDOFF_FLOOR_MM
    )
    # On the envelope the north face sat flush at the limits (#2756).
    assert (BLOCK_DIA / inch) / 2.0 >= north_min


def test_one_cone_boss_diameter_counts_both_bosses() -> None:
    """MHA-DT-05 machinist review: SECTION A-A shows a boss at each end of the
    cone bore, and the one Ø printed nowhere said it sized both."""
    assert drawing.DIMENSION_PREFIXES == {"ConeBossDia": "2X "}
    assert drawing._DIMENSION_TEXT_PREFIX == 1
    # A custom prefix replaces the automatic Ø, so the count keeps its token.
    assert drawing.counted_diameter_prefix("2X ", "") == "2X <MOD-DIAM>"
    assert drawing.counted_diameter_prefix("2X ", "<MOD-DIAM>") == "2X <MOD-DIAM>"
    with pytest.raises(RuntimeError, match="already carries 2X"):
        drawing.counted_diameter_prefix("2X ", "2X <MOD-DIAM>")


def test_plan_angle_is_basic_and_prints_the_model_angle() -> None:
    """#906: the basic nominal feeds the retained angularity frame; its
    places spell the configured angle rather than tightening the zone."""
    assert spec.BASIC_DIMENSIONS == frozenset({"InclineAngle"})
    places = spec.DRAWING_PRECISION_BY_NAME["InclineAngle"]
    assert places == 4
    printed = round(spec.INCLINE_DEG, places)
    assert printed == round(
        _config.machine("cone_incline", "derived_incline_deg"), places
    )
    assert abs(printed - spec.INCLINE_DEG) <= 0.5 * 10.0**-places


def test_section_reads_by_its_bore_axis_not_by_a_note() -> None:
    assert "SECTION A-A" not in spec.DRAWING_NOTES


def test_crank_boss_station_prints_on_its_own_dimension_line() -> None:
    """Labelled, stacked, no shelf.  The station's text was once offset to a
    distant shelf, where a blind reader took it for a note, so it never leaves
    its own dimension line; and a bare station was not found as one (Main's
    rim-8339 ruling), so its label stacks with the value.  It stands once, in
    the plan."""
    assert "CrankBossStartZ" in drawing.TOP_KEEP
    assert "CrankBossStartZ" not in drawing.JOURNAL_TEXT_OFFSETS


def test_section_centerline_is_forced_to_print_black_in_center_font() -> None:
    assert drawing._SW_LINE_CENTER == 4


def test_turned_diameters_stand_clear_of_the_head() -> None:
    """r8 (rule 11): Ø42.8 was leadered on the plan's end view of the head.
    The head's Ø stands across it in View C, which sees it side-on.  Not the
    elevation: the head's extension lines there crossed the crank-bore Ra's
    leader (r9).  The crank boss's Ø stands on its end circle in the
    elevation: in the plan its extension lines rose from the profile sketch
    on the boss's north face through the head circle (r13)."""
    assert "HeadDia" in drawing.JOURNAL_KEEP
    assert not {"HeadDia"} & (set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP))
    assert "CrankBossDia" in drawing.FRONT_KEEP
    assert "CrankBossDia" not in drawing.TOP_KEEP
    assert "CrankBossDia" in drawing.NEAR_SIDE_DIAMETERS
    assert drawing.DIMENSION_SUFFIXES["HeadDia"] == " HEAD"
    assert drawing.DIMENSION_CALLOUTS["CrankBossDia"] == "CRANK BOSS"
    assert "HeadDia" not in drawing.DIMENSION_CALLOUTS


def test_plan_names_the_ray_its_basic_angle_runs_to() -> None:
    """r13: the basic 12° ran to an unlabelled dash-dot ray.  A BASIC box
    drops below-text, so a pointer note in the plan names the ray."""
    assert "InclineAngle" not in drawing.DIMENSION_CALLOUTS
    assert drawing.CONE_AXIS_LABEL == "CONE BORE AXIS"
    # The tip stays inside the head circle, where the ray is drawn alone.
    assert drawing.CONE_AXIS_LABEL_TIP_RADIUS_MM < spec.HEAD_DIA / 2.0
    # The text right of the head circle, above the 12° box.
    assert (
        drawing.CONE_AXIS_LABEL_XY[0] > drawing.TOP_CENTER[0] + spec.HEAD_DIA / 2000.0
    )
    assert drawing.CONE_AXIS_LABEL_XY[1] > drawing.TOP_KEEP["InclineAngle"][1]


def test_both_bores_read_size_then_ream_thru_and_flag_their_fit_note() -> None:
    """Novice-rubric screen (rules 12, 26 and 4): neither banded bore named a
    process, and RUNS ON named a mate but no fit.  Both are reamed with owned
    reamers (.4500 and .4835, cone_pivot_post_spec), so each callout reads
    size, REAM, THRU and flags the numbered note that states its standard
    running fit.  The crank bore's process and flag share its one row under
    the size: a third row dropped onto the head's top edge, and the 12° arc
    caps the block above (FRONT_KEEP)."""
    for name, note in (("CrankBoreDia", 1), ("JournalBoreDia", 2)):
        assert name not in drawing.DIMENSION_SUFFIXES
        rows = drawing.DIMENSION_CALLOUTS[name].splitlines()
        assert rows[0] == f"REAM THRU, SEE NOTE {note}"
    # Fit audit 2026-11-23 F02: each note names the journal turned to it.
    assert _note(1).startswith("1. RUNNING FIT: CRANKSHAFT MHA-DT-11 JOURNAL IS TURNED")
    assert _note(2).startswith("2. RUNNING FIT: CONE SHAFT MHA-DT-04 JOURNAL IS TURNED")


def test_crank_bore_mate_line_stands_clear_of_the_head_height_extension() -> None:
    """Machinist review of farm run 20261101T142805608Z: the RUNS ON
    MHA-DT-11 underline sat 0.8 mm over HeadHt's upper extension line (the
    head's top edge), parallel to it.  That render put the underline 7.31 mm
    under the requested y and the box 2.6 mm past its 156.3 mm right end, at
    x 0.1330; View C's nearest text (the 1.694 block) starts at 180.6 mm.
    The block keeps two rows.  Its second row, "REAM THRU, SEE NOTE 1", is
    four glyphs (~2.7 mm each, centred) wider than RUNS ON MHA-DT-11, and the
    1.694 block lost its two word rows (5.5 mm each of its 19 mm), so the
    crowding check asks that smaller block's height of air."""
    x, y = drawing.FRONT_KEEP["CrankBoreDia"]
    underline_y = y - 0.00731
    assert underline_y - drawing._front_y(spec.BLOCK_HEIGHT) >= 0.0025
    row = drawing.DIMENSION_CALLOUTS["CrankBoreDia"]
    assert "\n" not in row
    grown = (len(row) - len("RUNS ON MHA-DT-11")) * 0.0027 / 2.0
    box_right = 0.1563 + (x - 0.1330) + 0.0026 + grown
    assert "CrankAboveCone" not in drawing.DIMENSION_CALLOUTS
    spacing_block_height = 0.0190 - 2 * 0.0055
    assert 0.1806 - box_right >= spacing_block_height


def test_mounting_hole_callout_says_drill_after_its_size() -> None:
    # r5 machinist review (rule 12): "2X Ø7.14 THRU ALL" left drill or ream
    # unsaid.  R5 fix attempt 3 (rule 26): DRILL on its own row above the
    # size read process first, so it goes between the size and THRU.
    native = {
        5: "<HOLE-SPOT><MOD-DIAM><hw-cbdiam> <HOLE-DEPTH><hw-cbdepth>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-diam> <hw-thru>",
        8: "",
    }
    updated = drawing.mount_hole_callout_definitions(native)
    assert updated == {**native, 7: "<NUM_INST>X <MOD-DIAM><hw-diam> DRILL <hw-thru>"}
    assert "\n" not in updated[7]
    with pytest.raises(RuntimeError, match="THRU row"):
        drawing.mount_hole_callout_definitions({**native, 5: native[7]})
    with pytest.raises(RuntimeError, match="callout parts"):
        drawing.mount_hole_callout_definitions({5: native[5], 7: native[7]})
    with pytest.raises(RuntimeError, match="no single"):
        drawing.mount_hole_callout_definitions(
            {**native, 7: "<NUM_INST>X <MOD-DIAM><hw-diam> THRU ALL"}
        )


def test_thrust_face_station_flags_note_2_which_names_the_collar() -> None:
    """r5 (rule 4) asked the ±.002 station to say whose collar it sets.  The
    novice rubric (rule 7) keeps a location to its value and band, so the
    cone bore's note 2 names the MHA-DT-04 collar on the face at that station
    and the station flags it (fan-out r1).  The face's Ra symbol keeps no
    text: the spec is shared by other slices' parts, so the sheet does not
    re-key it."""
    assert drawing.DIMENSION_CALLOUTS["ConeBossNorthZ"] == "SEE NOTE 2"
    face = surface_finish_by_key(spec.SURFACE_FINISHES, "cone_boss_north_face")
    assert face.production_method == ""
    assert drawing._NORTH_BOSS_FINISH_OFFSET == (-0.006, 0.008)
    assert "MHA-DT-04" in _note(2)
    # R5 fix attempt 1 (blocker): a bare COLLAR named no mate, so the collar
    # is named by number; the rims' break left the note for detail D.
    line = drawing.SHEET_NOTES.splitlines()[2]
    assert line == "   MHA-DT-04 COLLAR RUNS ON .827 FACE."
    # Above the upper extension line, below the sheet border.
    assert drawing.SECTION_KEEP["ConeBossNorthZ"][1] > 0.250


def test_diameters_on_circles_run_onto_their_near_rims() -> None:
    """r5 and r8: two rim-to-rim lines through one centre crossed there."""
    assert set(drawing.NEAR_SIDE_DIAMETERS) == {
        "CrankBossDia",
        "CrankBoreDia",
        "ConeBossDia",
        "JournalBoreDia",
    }


def test_removed_view_letter_is_not_a_datum_letter() -> None:
    """r5: VIEW B read as datum B."""
    letters = {datum.letter for datum in spec.PART_DATUMS}
    assert drawing.JOURNAL_VIEW_LETTER not in letters | {"A"}


def test_datum_a_and_journal_finish_stand_off_the_body() -> None:
    """r5: datum A sat on Ø12.281's leader and the Ra landed on its triangle.
    r13 (rule 14): both stood inside View C's body outline."""
    right_of_body = drawing.JOURNAL_CENTER[0] + spec.BODY_DIA / 2000.0
    # Both right of the view, below the size's text; each leader lands
    # further round the rim than the one above it (the size's at about
    # -24 degrees), so none crosses another.
    for xy in (drawing.JOURNAL_BORE_FINISH_XY, drawing.DATUM_A_TAG_XY):
        assert xy[0] > right_of_body
        assert xy[1] < drawing.JOURNAL_KEEP["JournalBoreDia"][1]
    assert drawing.DATUM_A_TAG_XY[1] < drawing.JOURNAL_BORE_FINISH_XY[1]
    assert -90.0 < drawing.DATUM_A_LANDING_DEG < drawing.JOURNAL_BORE_FINISH_DEG < -30.0


def test_section_caption_states_no_scale_at_sheet_scale() -> None:
    assert drawing.SECTION_SCALE == drawing.SHEET_SCALE


def test_the_post_saves_every_reference_sketch_hidden() -> None:
    """#880: no reference sketch renders in the part or any assembly.  Each
    one that carries a drawing dimension is saved hidden, read back, and the
    drawing shows it only in the view that dimensions it.  JournalPlanReference
    and BoreSpacingReference were the release's last visibility debt."""
    references = {
        name for name in spec.DRAWING_DIMENSIONS if name.endswith("Reference")
    }
    assert references == {
        "JournalPlanReference",
        "CrankBossStationReference",
        "ConeBossStationReference",
        "BoreSpacingReference",
        "JournalRimBreakReference",
    }


def test_crank_bore_is_located_from_the_cone_bore_and_never_binds() -> None:
    """U31: the 16T:64T mesh closes on the bore spacing, so the print states it.

    User ruling 2026-09-28: fixed centres, no drop and no fit-up bushing; the
    printed spacing band is one of crank_mesh_stack's terms, and its standard
    check's worst-corner backlash > 0 is the never-bind check.
    """
    import crank_mesh_stack

    assert spec.CRANK_ABOVE_CONE == pytest.approx(
        _config.machine("gear_train", "crank_axis_height_mm") - spec.BORE_HEIGHT
    )
    assert spec.CRANK_ABOVE_CONE_BAND == (0.3556, 0.0)
    places = spec.DRAWING_PRECISION_BY_NAME["CrankAboveCone"]
    assert crank_mesh_stack.SPACING_PRINTED == pytest.approx(
        round(spec.CRANK_ABOVE_CONE / 25.4, places) * 25.4
    )
    assert abs(crank_mesh_stack.FRAME_DY - spec.CRANK_ABOVE_CONE) < 1e-9
    # The spacing is on its print grid, so the printed nominal is the model
    # and the band's low corner is the mesh centre itself; the configured
    # centre extension is what closes the two pitch radii on it.
    assert crank_mesh_stack.SPACING_PRINTED == pytest.approx(spec.CRANK_ABOVE_CONE, abs=1e-9)
    assert crank_mesh_stack.CLOSING_TERMS["crank bore spacing"] == pytest.approx(0.0, abs=1e-9)
    import build_dt_drive_train_assembly as bdt

    assert math.hypot(bdt._DX16, spec.CRANK_ABOVE_CONE) == pytest.approx(
        crank_mesh_stack.R64
        + crank_mesh_stack.R16
        + _config.fit("crank_mesh", "c2c_slack_mm"),
        abs=1e-9,
    )
    assert crank_mesh_stack.standard_check().backlash_min_mm > 0.0
    # The foot-to-crank height stays on the front view only as a reference.
    assert "CrankAxisY" in drawing.FRONT_KEEP
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the spacing band is a dimension, never a setup method.
    assert "ONE SETUP" not in spec.DRAWING_NOTES
    assert "BORE-TO-BORE" not in spec.DRAWING_NOTES


def test_point_relations_use_the_point_relation_types() -> None:
    """swConstraintType_HORIZONTAL/VERTICAL apply only to lines.

    r6 (farm, 2026-09-23) related BoreSpacingReference's start point to the
    origin with plain "horizontal": SOLIDWORKS returned a relation, but the
    sketch stayed under-defined.  A point pair must use the *_points type.
    """

    from solidworks_mcp.adapters.solidworks.sketch import RELATION_NAME_MAP

    assert RELATION_NAME_MAP["horizontal_points"] == 25  # swConstraintType_HORIZPOINTS


_SPACING_LINE = layout.Segment(0.2080, 0.1504, 0.2080, 0.1700, "line")


def test_datum_b_tag_sits_under_the_foot_seat() -> None:
    """Datum B's tag point stands under the foot seat it tags, so its leader
    reaches the seat."""
    assert drawing.DATUM_B_TAG_XY[1] < drawing._front_y(0.0)


def test_cone_axis_height_stands_on_its_own_line_clear_of_the_spacing() -> None:
    """r3 (View C): the 1.50's text, offset onto the line it shared with the
    1.694, dropped a jogged leader down that line until the two merged.  Its
    own line now stands well left of the spacing's, its text on that line
    between the foot and the cone axis."""
    assert "JournalAxisY" not in drawing.JOURNAL_TEXT_OFFSETS
    x, y = drawing.JOURNAL_KEEP["JournalAxisY"]
    assert x < drawing.JOURNAL_KEEP["CrankAboveCone"][0] - 0.010
    foot_y = drawing.CONE_AXIS_SHEET_Y - spec.BORE_HEIGHT / 1000.0
    assert foot_y + 0.010 < y < drawing.CONE_AXIS_SHEET_Y - 0.010
    # The control sheet's spacing line starts at the cone axis.
    assert drawing.CONE_AXIS_SHEET_Y == pytest.approx(_SPACING_LINE.y0, abs=5e-4)


def test_drawing_side_callout_precision_is_the_declared_exception() -> None:
    # Codjiflo on #2106: a part-authored precision does not reach a Hole
    # Wizard callout (run 20261102T230110877Z), so this sheet writes its
    # callout places at drawing time, the declared exception RV-02.
    from machinist_exceptions import load_exceptions

    entry = {
        e.id: e
        for e in load_exceptions(_config.CONFIG_DIR, "dt_cone_pivot_post", "part")
    }["RV-02"]
    assert entry.kind == "accept"
    assert entry.reason.startswith(
        "Owner ruling 2026-11-08 (Pedro), #2144 item 1.2"
    )
    assert "#2144" in entry.reason and "20261102T230110877Z" in entry.reason
    assert "draw_dt_cone_pivot_post.build" in entry.where
    assert (spec.MOUNT_HOLE_CALLOUT_PLACES, spec.MOUNT_CBORE_DEPTH_PLACES) == (3, 2)
    assert "written as 3" in entry.where and "written as 2" in entry.where
    assert all(name in entry.where for name in drawing.MOUNT_HOLE_PRECISION)


def _note(number: int) -> str:
    """Numbered note ``number`` of the sheet's block, its lines joined."""
    lines = drawing.SHEET_NOTES.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{number}. "))
    body = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("   "):
            break
        body.append(line.strip())
    return " ".join(body)


def test_numbered_notes_state_each_bores_fit_and_its_locations_mates() -> None:
    """Novice-rubric screen (rules 4, 7 and 26): the four location dimensions
    carried their mates in words, the 1.694 named its mesh only by tooth
    count, and the bores said RUNS ON with no fit.  Each bore's numbered note
    names the running fit and the journal turned last to it by drawing
    number (fit audit 2026-11-23 F02, rule 4 form 2: the clearance prints on
    the journal's sheet), and the mates its locations serve: the bore
    spacing and the crank boss's north-face station set the 16T crank pinion
    against the 64T crank drive gear (rule 4: a gear centre distance names
    the mesh), and the MHA-DT-04 collar runs on the cone boss's north face.
    The cone-axis height takes the title block's .XX band, so rule 4 asks no
    mate of it.  Four lines in all (rule 7)."""
    import dt_crank_drive_gear_spec as gear64
    import dt_crank_pinion_spec as pinion

    assert drawing.SHEET_NOTES == "\n".join(
        (
            "1. RUNNING FIT: CRANKSHAFT MHA-DT-11 JOURNAL IS TURNED TO THIS BORE.",
            "2. RUNNING FIT: CONE SHAFT MHA-DT-04 JOURNAL IS TURNED TO THIS BORE;",
            "   MHA-DT-04 COLLAR RUNS ON .827 FACE.",
            "3. 1.694 AND .842 SET MESH OF PINION MHA-DT-10 WITH GEAR MHA-DT-07.",
        )
    )
    assert len(drawing.SHEET_NOTES.splitlines()) <= 4
    assert "CLEARANCE" not in drawing.SHEET_NOTES
    # The cited values are the ones the locations print.
    for value, name in (
        (spec.CRANK_ABOVE_CONE, "CrankAboveCone"),
        (spec.CRANK_BOSS_NORTH_FACE, "CrankBossStartZ"),
        (spec.CONE_BOSS_NORTH_STATION, "ConeBossNorthZ"),
    ):
        text = f"{value / 25.4:.{spec.DRAWING_PRECISION_BY_NAME[name]}f}".removeprefix("0")
        assert text in drawing.SHEET_NOTES
    # Every mate by its registered drawing number; the 16T and 64T are the
    # crank pinion and the crank drive gear.
    for stem, number in (
        ("dt-crankshaft", "MHA-DT-11"),
        ("dt-crank-pinion", "MHA-DT-10"),
        ("dt-crank-drive-gear", "MHA-DT-07"),
        ("dt-cone-gear-shaft", "MHA-DT-04"),
    ):
        assert _config.parts(stem)["number"] == number
        assert number in drawing.SHEET_NOTES
    assert "MHA-DT-21" not in drawing.SHEET_NOTES
    assert (pinion.TEETH, gear64.TEETH) == (16, 64)
    for private in ("DIAMETRAL", "RUNS ON MHA", "16T", "64T", "T120", "MATCHES"):
        assert private not in drawing.SHEET_NOTES


def test_locations_print_their_value_band_and_note_flag_only() -> None:
    """Novice-rubric screen (rule 7): a location carries its value and band
    and nothing else; fan-out r1 (rules 4, 7): a tight location whose mate
    sits in a numbered note flags that note, so the reader reaches it."""
    flagged = {
        "ConeBossNorthZ": "SEE NOTE 2",
        "CrankBossStartZ": "SEE NOTE 3",
        "CrankAboveCone": "SEE NOTE 3",
    }
    callouts = {**drawing.DIMENSION_CALLOUTS, **drawing.DIMENSION_CALLOUTS_ABOVE}
    for name, flag in flagged.items():
        assert callouts[name] == flag
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) == {"CrankAboveCone"}
    assert "MHA-DT-04 COLLAR RUNS ON .827 FACE." in _note(2)
    assert _note(3).startswith("3. 1.694 AND .842 SET MESH")
    for name in ("JournalAxisY", "CrankAxisY", "MountWestX", "MountEastX"):
        assert name not in callouts
    for name in (*flagged, "JournalAxisY", "CrankAxisY", "MountWestX", "MountEastX"):
        assert name not in drawing.DIMENSION_SUFFIXES
        assert name not in drawing.DIMENSION_PREFIXES


def test_every_callout_keeps_at_most_two_lines_of_words() -> None:
    """Rule 7: size and process lines plus at most two lines of words; the
    crank boss length keeps one reason, the mate its south face seats.  A
    bore's REAM THRU row (with its note flag) is its process line."""
    for text in drawing.DIMENSION_CALLOUTS.values():
        lines = text.splitlines()
        words = lines[1:] if lines[0].startswith("REAM THRU") else lines
        assert len(words) <= 2
    assert drawing.DIMENSION_CALLOUTS["CrankBossLen"] == "SEATS\nMHA-DT-11 COLLAR"


def test_numbered_notes_stand_in_free_sheet_space() -> None:
    """Bottom left: under the elevation's datum B frame (it hangs 7 mm under
    its tag point), inside the border and left of the title block, at the
    sheet's ~2.7 mm glyph advance and 5.5 mm row pitch."""
    region, keep_outs = _landscape_sheet()
    title_block = dict(keep_outs)["title-block"]
    x, top = drawing.NOTES_XY
    lines = drawing.SHEET_NOTES.splitlines()
    assert top <= drawing.DATUM_B_TAG_XY[1] - 0.007 - 0.005
    assert top - len(lines) * 0.0055 >= region.ymin + 0.005
    assert x >= region.xmin + 0.005
    assert x + max(len(line) for line in lines) * 0.0027 <= title_block.xmin - 0.005


def test_view_c_is_labelled_by_its_letter_alone() -> None:
    """Novice-rubric screen (rule 26): 'VIEW C - CONE JOURNAL / LOOK ALONG
    CONE AXIS' followed the standard label with prose; arrow C on SECTION A-A
    already says what it looks along."""
    assert drawing.JOURNAL_VIEW_LABEL == "VIEW C"
    head_left = drawing.JOURNAL_CENTER[0] - spec.HEAD_DIA / 2000.0
    assert head_left < drawing.JOURNAL_VIEW_LABEL_XY[0] < drawing.JOURNAL_CENTER[0]
