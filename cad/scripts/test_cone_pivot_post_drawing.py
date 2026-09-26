"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import re

import pytest
from pathlib import Path

import build_cone_pivot_post as part
import cone_pivot_post_spec as spec
import draw_cone_pivot_post as drawing
from _assembly import _seed_flip
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM, SEAT_UM, surface_finish_by_key


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_pivot_post"].script
        == Path(drawing.__file__).resolve()
    )


def test_v2_harvest_is_the_exact_dimensional_contract() -> None:
    assert (spec.BLOCK_DIA, spec.BLOCK_HEIGHT) == (42.011, 86.0)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT, spec.HEAD_BASE_Y) == (
        44.0,
        26.6,
        59.4,
    )
    assert (
        spec.CRANK_BOSS_DIA,
        spec.CRANK_BORE_DIA,
        spec.CRANK_BORE_HEIGHT,
        spec.CRANK_BORE_OFFSET,
    ) == (21.93, 11.438, 72.7, 0.0)
    assert spec.CRANK_BOSS_LENGTH_IN == 2.8360
    assert round(spec.CRANK_BOSS_LENGTH, 4) == 72.0344
    # The spot face is stationed from the post axis, NOT from the cast collar.
    assert spec.CRANK_BOSS_NORTH_FACE == 21.3753
    assert round(spec.CRANK_BOSS_START_Z, 4) == -21.3753
    assert spec.CRANK_BOSS_START_Z != -spec.HEAD_DIA / 2.0
    assert round(spec.CRANK_BOSS_END_Z, 4) == 50.6591
    assert (spec.CONE_BOSS_DIA, spec.BORE_DIA, spec.BORE_HEIGHT) == (
        17.2,
        12.2808,
        33.368,
    )
    assert spec.INCLINE_DEG == 12.5182
    assert (
        spec.ATTACHMENT_SPACING,
        spec.ATTACHMENT_THRU_DIA,
        spec.ATTACHMENT_CBORE_DIA,
        spec.ATTACHMENT_CBORE_DEPTH,
    ) == (26.88704, 7.14248, 11.50874, 6.0198)
    # The final volume is the per-feature sum the build checks natively; a
    # constant that drifts from the features (the 2026-09-21 unbored-boss
    # build) fails at import, so only mass coherence is left to pin here.
    assert spec.HARVESTED_VOLUME_MM3 == round(part._ANALYTIC_FINAL_MM3, 4)
    assert round(spec.HARVESTED_VOLUME_MM3 * 7.2e-6, 6) == spec.HARVESTED_MASS_KG
    assert round(part.CRANK_BORE_MM3, 1) == 7401.7
    assert round(part.CRANK_SPOT_FACE_MM3, 1) == 93.1
    assert round(part.ATTACHMENT_HOLES_MM3, 1) == 7661.6


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.TOP_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.JOURNAL_KEEP)
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
        "CrankBoreDia",
        "JournalAxisY",
        "ConeBossDia",
        "JournalBoreDia",
        "CrankBossStartZ",
        "InclineAngle",
    }
    # No dimension may be placed twice: two views that both carry a value are
    # two chances for the sheet to contradict itself.
    assert (
        len(drawing.FRONT_KEEP)
        + len(drawing.TOP_KEEP)
        + len(drawing.SECTION_KEEP)
        + len(drawing.JOURNAL_KEEP)
        == len(kept)
    )


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
    assert set(drawing.JOURNAL_KEEP) == cone_owned
    assert drawing.CONE_AXIS_VIEW == part.CONE_AXIS_VIEW == "CONE JOURNAL"


def test_cone_boss_length_lives_in_the_bore_plane_section() -> None:
    """The raised boss's axial extent is dimensioned where its profile is visible."""
    assert drawing.SECTION_SCALE == (1, 1)
    assert set(drawing.SECTION_KEEP) == {"ConeBossLen"}
    assert "ConeBossLen" not in drawing.TOP_KEEP
    start, end = drawing.CONE_SECTION_LINE
    assert start[1] == end[1] == drawing._front_y(spec.BORE_HEIGHT)
    assert start[0] < drawing.FRONT_CENTER[0] < end[0]


def test_part_owns_every_printed_decimal_place() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set().union(
        *spec.DRAWING_DIMENSIONS.values()
    )
    assert "draw_cone_pivot_post.py" in PRECISION_MIGRATED_DRAWINGS
    # Only the two running bores earn a third place, and only because their
    # size limits are what deliver the shaft_in_bushing clearance band.
    assert {
        name
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places >= 3
    } == {"CrankBoreDia", "JournalBoreDia"}


def test_running_bores_close_the_configured_fit_class() -> None:
    import _config
    import cone_gear_shaft_spec
    import crankshaft_spec

    upper, lower = spec.RUNNING_BORE_BAND
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    for bore, shaft_nominal, shaft_band in (
        (
            spec.CRANK_BORE_DIA,
            crankshaft_spec.JOURNAL_DIA,
            crankshaft_spec.JOURNAL_DIA_BAND,
        ),
        (
            spec.BORE_DIA,
            cone_gear_shaft_spec.JOURNAL_DIA,
            cone_gear_shaft_spec.SECTION_DIA_BANDS[0],
        ),
    ):
        shaft_max = shaft_nominal + shaft_band[0]
        shaft_min = shaft_nominal + shaft_band[1]
        clearances = (bore + lower - shaft_max, bore + upper - shaft_min)
        assert tuple(round(value, 3) for value in clearances) == expected


def test_nothing_else_on_the_casting_carries_a_band() -> None:
    """One band, named once, applied to the two features the fit class names.

    The cast body, collar and boss diameters and the mounting-hole stations
    are not accuracy features (cad/docs/tolerance-policy.md, "Result"), so the
    part must not author a tolerance on them at all: the title block's general
    grade is the whole specification.  The one other band is the #917 dowel
    ream's, carried on its Hole Wizard feature (test_cone_post_dowels).
    """
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 3
    assert "set_dimension_symmetric_tolerance" not in source
    assert source.count("deviations(RUNNING_BORE_BAND)") == 2
    assert source.count("deviations(CRANK_ABOVE_CONE_BAND)") == 1
    assert not hasattr(spec, "TURNED_DIAMETER_TOLERANCE_MM")
    assert not hasattr(spec, "CRANK_BORE_TOLERANCE_MM")


def test_the_plan_angle_is_model_geometry_not_sheet_text() -> None:
    """The 12.5182 deg plan incline is a DRIVING model dimension.

    A driven reference angle cannot express it: SOLIDWORKS returns the
    obtuse member of a line pair whatever the ray directions, the selection
    order or the text position.  A driving dimension fixes the quadrant when
    the sketch is authored, and driving it from the same ``ConeIncline``
    global that builds ConeShaftNormal is what stops the printed value and
    the built geometry from drifting apart.
    """
    assert "InclineAngle" in spec.DRAWING_DIMENSIONS["JournalPlanReference"]
    assert "CrankBossStartZ" in spec.DRAWING_DIMENSIONS["JournalPlanReference"]
    assert round(spec.CRANK_BOSS_NEAR_Z, 4) == 21.3753
    assert round(spec.JOURNAL_REFERENCE_X, 6) == 8.669989
    assert round(spec.JOURNAL_REFERENCE_Z, 6) == 39.049088
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'plan.record("InclineAngle", \'"ConeIncline"\')' in source
    assert "add_angular_reference_dimension" not in source
    # A blanked sketch's dimensions never reach InsertModelAnnotations3.
    assert "JournalPlanReference" not in source.split(
        "_blank_reference_geometry(\n        adapter,"
    )[1]


def test_machined_faces_are_called_out_on_the_casting() -> None:
    assert part.SURFACE_FINISHES is spec.SURFACE_FINISHES
    keys = {control.key for control in spec.SURFACE_FINISHES}
    assert keys == {"foot_seat", "crank_bore", "journal_bore"}
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


def test_sheet_carries_no_datums_or_feature_control_frames() -> None:
    assert spec.GEOMETRIC_TOLERANCES_MM == {}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for banned in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "set_dimension_precision(",
        "SetBalloon(",
    ):
        assert banned not in source


def test_manufacturing_notes_do_not_restate_dimensions() -> None:
    # A note may state the axis relationship, but it may not restate a size, a
    # band or a finish: those remain dimensions and native symbols under
    # drawing-simplicity-policy.md rules 1 and 6.
    # drawing-simplicity-policy.md rule 6: at most four short lines.
    lines = spec.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    assert max(len(line) for line in lines) <= 64
    stripped = re.sub(r"MHA-\d+", "", spec.DRAWING_NOTES)
    assert not any(character.isdigit() for character in stripped)
    for banned in ("DIA", "THRU", "DEEP", "C-C", "DATUM", "MACHINE", "Ra"):
        assert banned not in spec.DRAWING_NOTES


def test_source_records_exact_manual_photo_provenance() -> None:
    sources = "\n".join(
        (
            Path(spec.__file__).read_text(encoding="utf-8"),
            Path(part.__file__).read_text(encoding="utf-8"),
        )
    )
    assert "ch30_images/page003_img01.png" in sources
    assert "ch11_images/page002_img05.jpeg" in sources
    assert "page002_img06.jpeg" in sources
    assert "manually rederived" in sources


def test_part_exposes_semantic_mating_references() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for name in (
        "ConeShaftNormal",
        "journal axis",
        "swing pivot",
        "mount east",
        "mount west",
    ):
        assert f'"{name}"' in source
    assert "_create_feature_cylinder_axis(" in source
    assert '"ConeShaftBoss",\n        CONE_BOSS_DIA / 2.0' in source
    assert '(("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X))' in source
    assert not hasattr(part, "CRANK_BORE_DX")
    assert not hasattr(part, "CRANK_BORE_Y")
    assert "HARVESTED_VOLUME_MM3" in source


def test_rotated_post_reverses_the_cone_shaft_axial_mate_side() -> None:
    assert not _seed_flip("cone-shaft axial d=22.01", 22.01)


def test_v2_feature_topology_uses_midplane_extrusions_and_hole_wizard() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert part.ATTACHMENT_HOLE_SPEC.kind == "counterbore_fillister"
    assert part.ATTACHMENT_HOLE_SPEC.size == "1/4"
    assert part.ATTACHMENT_HOLE_SPEC.overrides_mm == {
        "HoleDiameter": spec.ATTACHMENT_THRU_DIA,
        "CounterBoreDiameter": spec.ATTACHMENT_CBORE_DIA,
        "CounterBoreDepth": spec.ATTACHMENT_CBORE_DEPTH,
    }
    assert "_revolved_cylinder" not in source
    assert "create_revolve" not in source
    assert source.count("both_directions=True") == 2
    assert source.count('create_sketch("ConeShaftNormal")') == 3
    assert "angle=-INCLINE_DEG" in source
    assert 'HoleSpec(\n    "counterbore_fillister",\n    "1/4"' in source
    # The mounting pair plus #917 S1's blind dowel pair.
    assert source.count("wizard_holes(") == 2
    assert "attachment_cut.placement_drive_jobs" in source
    assert 'name="AttachmentScrewHoles"' in source
    assert 'name="PostDowelHoles"' in source


def test_dowel_pair_prints_on_a_foot_view_with_its_match_ream_callout() -> None:
    """#917 S1: the blind Ø.1255 slip-fit pair opens only on the foot, so a
    foot view carries it; the native callout states size, band and depth,
    and its prefix names the mating platform and the reamer."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Bottom"' in source
    assert "process=POST_DOWEL_CALLOUT" in source
    assert '{"hw-diam": 3, "hw-depth": 1}' in source
    assert 'label="post dowel reamed holes"' in source
    assert drawing.FOOT_VIEW_NOTE == "VIEW C - FOOT\nSCALE 1:2"
    # The foot view is not a note: its caption stays out of the manufacturing
    # block, which keeps within rule 6's four lines.
    assert "VIEW C" not in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) <= 4




def test_bore_rim_com_scan_is_traced() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert ('@_telemetry.traced("drawing.bore_rim_scan")\n' "def _bore_rim_edge") in source


def test_part_config_is_a_machined_casting() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-pivot-post")
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    finish = str(config["finish"])
    assert "RAL 6005" in finish
    assert "SSPC-SP 3" in finish
    assert "50-75 um DFT" in finish
    assert "MASK MACHINED FACES" in finish
    assert "OIL BARE FACES ISO VG 32" in finish
    assert config["process"] == "machined from solid stock or casting"
    assert int(config["quantity"]) == 1


def test_collar_diameter_lives_on_its_plan_circle() -> None:
    """The front-view crank-bore leaders must not cross a collar dimension line."""
    assert "HeadDia" in drawing.TOP_KEEP
    assert "HeadDia" not in drawing.FRONT_KEEP
    # Names the feature, not a process: the part may be turned from bar stock.
    assert drawing.DIMENSION_CALLOUTS["HeadDia"] == "COLLAR"


def test_cone_boss_end_faces_are_located_by_symmetry() -> None:
    assert "CONE BOSS END FACES ARE SYMMETRIC ABOUT THE POST AXIS." in spec.DRAWING_NOTES


def test_plan_angle_prints_one_place_under_the_one_degree_band() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME["InclineAngle"] == 1


def test_section_reads_by_its_bore_axis_not_by_a_note() -> None:
    assert "SECTION A-A" not in spec.DRAWING_NOTES
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_add_cone_section_centerline(adapter, section)" in source


def test_spotface_station_prints_its_value_on_its_own_dimension_line() -> None:
    """The 21.38 station is a plain dimension: no label, no offset shelf."""
    assert "CrankBossStartZ" not in drawing.DIMENSION_CALLOUTS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '{"CrankBossStartZ":' not in source
    # Left of the Ø44 circle and right of the crank-boss length's line.
    x, _y = drawing.TOP_KEEP["CrankBossStartZ"]
    assert drawing.TOP_KEEP["CrankBossLen"][0] < x < drawing._top_x(-spec.HEAD_DIA / 2.0)


def test_section_centerline_is_forced_to_print_black_in_center_font() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing._SW_LINE_CENTER == 4
    assert "segment.Color = 0" in source
    assert "segment.Style = _SW_LINE_CENTER" in source
    assert "int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER" in source


def test_crank_boss_od_is_labelled_as_the_boss() -> None:
    """The elevation sees the boss's far end: its Ø is the boss, not a spotface."""
    assert drawing.DIMENSION_CALLOUTS["CrankBossDia"] == "CRANK BOSS"
    assert "SPOTFACE" not in drawing.DIMENSION_CALLOUTS.values()


def test_section_caption_states_no_scale_at_sheet_scale() -> None:
    assert drawing.SECTION_SCALE == drawing.SHEET_SCALE
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'expected = "<VLNAME> <VLLABEL>"\n' in source


def test_spotface_station_has_one_driving_global() -> None:
    """The printed station and the plane the boss grows from cannot drift apart."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"CrankBossNearZ": CRANK_BOSS_NEAR_Z,' in source
    assert 'drive_jobs.append(("D1@CrankInterfacePlane", \'"CrankBossNearZ"\'))' in source
    assert 'plan.record("CrankBossStartZ", \'"CrankBossNearZ"\')' in source


def test_crank_bore_is_located_from_the_cone_bore_inside_the_mesh_window() -> None:
    """U31: the 16T:64T mesh closes on the bore spacing, so the print states it.

    Re-adds the spec's stated worst-case contributors and proves the printed
    band, read against the model nominal, stays inside what the centre-distance
    contract leaves for the spacing.
    """
    assert round(spec.CRANK_ABOVE_CONE, 3) == 39.332
    assert spec.CRANK_ABOVE_CONE_BAND == (0.37, 0.0)
    window_lo, window_hi = -0.150, 0.540
    crank_float = 0.0375 + 0.075 / 72.03 * 5.65
    cone_float = 0.0375 + 0.075 / 42.01 * 5.68
    float_open = crank_float + cone_float
    plan_angle = 0.063
    station = 0.015
    dc_ddy = 39.332 / 39.735
    lo = (window_lo + plan_angle + station) / dc_ddy
    hi = (window_hi - float_open - plan_angle - station) / dc_ddy
    printed = round(spec.CRANK_ABOVE_CONE, 2)
    upper, lower = spec.CRANK_ABOVE_CONE_BAND
    assert lo < printed + lower - spec.CRANK_ABOVE_CONE
    assert printed + upper - spec.CRANK_ABOVE_CONE < hi
    # The assembly check reads backlash at rest (crank dropped by gravity):
    # every in-print post must land inside the drive-train sheet's 0.20-0.55.
    backlash_lo = 0.28 + 0.517 * (
        dc_ddy * (printed + lower - spec.CRANK_ABOVE_CONE)
        - plan_angle
        - station
        - crank_float
    )
    backlash_hi = 0.28 + 0.517 * (
        dc_ddy * (printed + upper - spec.CRANK_ABOVE_CONE)
        + plan_angle
        + station
        + cone_float
    )
    assert 0.20 <= backlash_lo < backlash_hi <= 0.55
    # The foot-to-crank height stays on the front view only as a reference.
    assert "CrankAxisY" in drawing.FRONT_KEEP
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="crank axis height reference"' in drawing_source
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert """set_global(adapter, "CrankAxisY", '"JournalAxisY" + "CrankAboveCone"')""" in source
    assert "ONE SETUP" in spec.DRAWING_NOTES
    assert "BORE-TO-BORE" in spec.DRAWING_NOTES


def test_deep_mounting_holes_keep_their_wall_to_the_cone_journal() -> None:
    """U37: the 2X mounting holes run the full post height in cast iron, past
    the cone journal.  Until #917 S1 a method note ("... CHECK CONE BORE AT
    BREAKOUT") guarded that; the holes are now transferred from the platform
    and the model asserts the wall instead (rule 6, Main)."""
    assert "CONE BORE AT BREAKOUT" not in spec.DRAWING_NOTES
    assert spec.MOUNT_JOURNAL_WALL_WORST >= spec.MOUNT_JOURNAL_WALL_TARGET == 2.0
    assert spec.MOUNT_JOURNAL_WALL_FLOOR == 1.5
    # The holes still run the full height: through below a top counterbore.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec(\n    "counterbore_fillister",\n    "1/4"' in source


def test_point_relations_use_the_point_relation_types() -> None:
    """swConstraintType_HORIZONTAL/VERTICAL apply only to lines.

    r6 (farm, 2026-09-23) related BoreSpacingReference's start point to the
    origin with plain "horizontal": SOLIDWORKS returned a relation, but the
    sketch stayed under-defined.  A point pair must use the *_points type.
    """
    import re as _re

    from solidworks_mcp.adapters.solidworks.sketch import RELATION_NAME_MAP

    assert RELATION_NAME_MAP["horizontal_points"] == 25  # swConstraintType_HORIZPOINTS
    source = Path(part.__file__).read_text(encoding="utf-8")
    calls = _re.findall(
        r"add_sketch_constraint\(\s*([^,]+),\s*([^,]+),\s*\"(\w+)\"", source
    )
    assert calls, "no sketch relations found"
    for entity1, entity2, relation in calls:
        is_point_pair = entity2.strip() != "None" and (
            ".start" in entity1 or ".end" in entity1 or ".center" in entity1
        )
        if is_point_pair and relation in {"horizontal", "vertical"}:
            raise AssertionError(
                f"line-only relation {relation!r} on points {entity1} / {entity2}"
            )
    assert '"origin", "horizontal_points"' in source


def _catalog_rows(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _catalog_rows(value)
    if isinstance(node, list):
        if node and all(isinstance(cell, str) for cell in node):
            yield node
        for item in node:
            yield from _catalog_rows(item)


def test_dimension_catalog_row_matches_the_spec() -> None:
    # dimensions.yaml is the narrative geometry catalog; its cone-pivot-post
    # row must state the collar the part is built with, not the retired
    # v2-harvest O42.7506 (Codex PRRT_kwDOPHDy386l4aOa).
    import yaml

    catalog = Path(spec.__file__).resolve().parents[1] / "config" / "dimensions.yaml"
    rows = [
        row
        for row in _catalog_rows(yaml.safe_load(catalog.read_text(encoding="utf-8")))
        if row[0].startswith("`cone-pivot-post`")
    ]
    assert len(rows) == 1
    dims = rows[0][1]
    assert f"Ø{spec.HEAD_DIA:.1f} ± 0.4 × {spec.HEAD_HEIGHT:g} upper collar" in dims
    assert f"y {spec.HEAD_BASE_Y:g}..{spec.BLOCK_HEIGHT:g}" in dims
    assert f"Ø{spec.BLOCK_DIA:g} × {spec.BLOCK_HEIGHT:.1f} tall" in dims
    assert f"bore on the body centreline at y {spec.CRANK_BORE_HEIGHT:g}" in dims
    assert "42.7506" not in " ".join(rows[0])


def test_mount_holes_clear_the_journal_bore_at_print_worst() -> None:
    """#917 S1 (Main): the mounting holes are transferred, so the method note
    "DRILL MOUNTING HOLES FROM TOP FACE; CHECK CONE BORE AT BREAKOUT." goes
    (rule 6).  Its requirement -- the holes clear the cone journal bore --
    becomes a model assert: the vertical Ø7.142 through-hole and the
    inclined Ø12.2808 journal are skew, so the wall is the axis distance
    |x| cos(incline) less both radii, at the title block's worst case."""
    import math

    import _config
    from _fit_limits import deviations

    assert "DRILL" not in spec.DRAWING_NOTES
    assert "BREAKOUT" not in spec.DRAWING_NOTES
    # crankhub removes this one in #906; S1 leaves it.
    assert "BORE BOTH IN ONE SETUP" in spec.DRAWING_NOTES
    # The spec mirrors the title block's grades (it may not read the config).
    xx = _config.title_block("linear_2pl")["value_in"] * 25.4
    assert spec.TITLE_BLOCK_BAND_BY_PLACES[2] == pytest.approx(xx, abs=0.005)
    assert spec.TITLE_BLOCK_ANGLE_BAND_DEG == _config.title_block("angular")["value_deg"]
    assert spec.DRILLED_HOLE_PLUS == _config.title_block("drilled_hole")["plus_mm"]
    assert spec.DRAWING_PRECISION_BY_NAME["MountWestX"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["InclineAngle"] == 1

    def wall(x: float, incline: float, hole: float, bore: float, offset: float) -> float:
        return x * math.cos(math.radians(incline)) - offset - hole / 2.0 - bore / 2.0

    nominal = wall(spec.ATTACHMENT_X, spec.INCLINE_DEG, 7.14248, 12.2808, 0.0)
    worst = wall(
        spec.ATTACHMENT_X - 0.51,
        spec.INCLINE_DEG + 1.0,
        7.14248 + 0.10,
        12.2808 + deviations(spec.RUNNING_BORE_BAND)[1],
        0.51,  # the journal's implied (unprinted) location off the post axis
    )
    assert spec.MOUNT_JOURNAL_WALL_NOMINAL == pytest.approx(nominal)
    assert spec.MOUNT_JOURNAL_WALL_WORST == pytest.approx(worst)
    assert round(nominal, 3) == 3.412
    assert round(worst, 3) == 2.301
    assert worst >= 2.0
    # The counterbore never reaches the journal: its floor stands far above
    # the bore's top.
    cbore_floor = spec.BLOCK_HEIGHT - spec.ATTACHMENT_CBORE_DEPTH
    assert cbore_floor - (spec.BORE_HEIGHT + 12.2858 / 2.0) > 40.0


def test_foot_view_group_is_placed_from_read_back_boxes() -> None:
    """S1 leaf 917-s1-5974 failed drawing:cone_pivot_post's layout audit:
    the foot caption (DetailItem378, [212.0,259.0]..[244.8,268.2] mm) crossed
    the top inner border by 1.46 mm, and the dowel callout (RD1) ran its
    leader across the plan (Drawing View2).  Both came from unmeasured
    literals (FOOT_NOTE_XY, FOOT_DOWEL_CALLOUT_XY); both are gone."""
    import inspect

    from _layout_geometry import Box

    assert not hasattr(drawing, "FOOT_NOTE_XY")
    assert not hasattr(drawing, "FOOT_DOWEL_CALLOUT_XY")
    gap = drawing.FOOT_LAYOUT_GAP
    foot = Box(0.2050, 0.2150, 0.2510, 0.2555)
    plan = Box(0.0600, 0.1700, 0.1500, 0.2700)
    callout = Box(0.1760, 0.2150, 0.2260, 0.2290)
    dowel_y = 0.2313
    cx, cy = drawing.foot_callout_shift(plan, foot, callout, dowel_y, gap)
    moved = Box(callout.xmin + cx, callout.ymin + cy, callout.xmax + cx, callout.ymax + cy)
    assert moved.xmax == pytest.approx(foot.xmin - gap)
    assert (moved.ymin + moved.ymax) / 2.0 == pytest.approx(dowel_y)
    assert moved.xmin >= plan.xmax + gap
    # Under the plan's counterbore callout text, which shares the field.
    ceiling = 0.2400
    cx, cy = drawing.foot_callout_shift(plan, foot, callout, dowel_y, gap, ceiling)
    assert callout.ymax + cy == pytest.approx(ceiling - gap)
    with pytest.raises(RuntimeError, match="does not fit between"):
        drawing.foot_callout_shift(Box(0.06, 0.17, 0.19, 0.27), foot, callout, dowel_y, gap)
    # The callout names ONE dowel: the edge pick breaks the z tie.
    assert "center_z_mm" in inspect.signature(drawing._circular_edge).parameters


# S1 leaf 917-s1-ac4f (drawing:cone_pivot_post): the caption-over-view plan
# with the view dropped under it landed the foot view on the journal view:
# "foot view [211.4,205.9]..[244.6,253.6]mm dropped onto the journal view
# [200.0,111.4]..[270.0,208.6]mm under its caption".  Border top 266.7; the
# caption (5974's box) 32.8 x 9.2 mm; gaps 2 mm: 62.9 mm needed, 58.1 there.
_AC4F_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_AC4F_JOURNAL = (0.2000, 0.1114, 0.2700, 0.2086)
_AC4F_FOOT_UNDROPPED = (0.2114, 0.21415, 0.2446, 0.26185)
_AC4F_FOOT_DROPPED = (0.2114, 0.2059, 0.2446, 0.2536)
_AC4F_CAPTION = (0.0328, 0.0092)


def _obstacles(*views: tuple[str, tuple[float, float, float, float]], texts=()):
    from _drawing_layout_check import DrawableRegion
    from _layout_geometry import Box
    from _layout_planner import SheetObstacles

    x0, y0, x1, y1 = _AC4F_BORDER
    return SheetObstacles(
        region=DrawableRegion(x0, y0, x1, y1),
        views=tuple((name, Box(*box), False) for name, box in views),
        texts=tuple((name, Box(*box)) for name, box in texts),
    )


def test_foot_caption_plan_rejects_the_ac4f_drop_and_slides_the_view() -> None:
    """Main's order: first the caption over its view with the view slid
    sideways (nearest first), then the caption beside the view."""
    from _layout_geometry import Box
    from _layout_planner import box_conflict, plan_caption

    obstacles = _obstacles(("Drawing View3", _AC4F_JOURNAL))
    # The ac4f outcome is rejected, naming the journal view.
    assert "Drawing View3" in (box_conflict(Box(*_AC4F_FOOT_DROPPED), obstacles) or "")
    plan = plan_caption(
        Box(*_AC4F_FOOT_UNDROPPED), _AC4F_CAPTION, obstacles, label="foot view"
    )
    assert plan.how == "caption over the view"
    assert plan.view_dx != 0.0
    # Nearest clear slide: left, until the view clears the journal by 2 mm.
    assert plan.view.xmax == pytest.approx(_AC4F_JOURNAL[0] - 0.002, abs=0.001)
    assert plan.caption.ymax <= _AC4F_BORDER[3] - 0.002 + 1e-9
    assert plan.caption.ymin >= plan.view.ymax + 0.002 - 1e-9
    assert box_conflict(plan.view, obstacles) is None
    assert box_conflict(plan.caption, obstacles) is None


def test_foot_caption_falls_back_beside_the_view_then_fails_naming_every_box() -> None:
    from _layout_geometry import Box
    from _layout_planner import plan_caption

    # A journal band across the whole sheet: no slide clears it under a drop.
    wide = ("wide journal", (0.0127, 0.1114, 0.4191, 0.2086))
    plan = plan_caption(
        Box(*_AC4F_FOOT_UNDROPPED), _AC4F_CAPTION, _obstacles(wide), label="foot view"
    )
    assert plan.how == "caption beside the view, left"
    assert plan.view_dx == plan.view_dy == 0.0
    assert plan.caption.ymax == pytest.approx(_AC4F_FOOT_UNDROPPED[3])
    assert plan.caption.xmax == pytest.approx(_AC4F_FOOT_UNDROPPED[0] - 0.002)
    # Text filling both sides too: nothing fits, and the failure names it all.
    left = ("left text", (0.10, 0.23, 0.2090, 0.2665))
    right = ("right text", (0.2470, 0.23, 0.40, 0.2665))
    with pytest.raises(RuntimeError, match="no clear place") as failure:
        plan_caption(
            Box(*_AC4F_FOOT_UNDROPPED),
            _AC4F_CAPTION,
            _obstacles(wide, texts=(left, right)),
            label="foot view",
        )
    message = str(failure.value)
    for name in ("wide journal", "left text", "right text", "border"):
        assert name in message



def test_post_places_its_foot_caption_with_the_planner() -> None:
    """The ac4f drop rule (foot_caption_shift) is gone; the build asks the
    planner, with the whole sheet as obstacles, and dumps the sheet."""
    import inspect

    assert not hasattr(drawing, "foot_caption_shift")
    source = inspect.getsource(drawing._place_foot_group)
    assert "plan_caption(" in source
    assert "sheet_obstacles(" in source
    assert "_collect_sheet(" in source
    assert "_collect_sheet(" in inspect.getsource(drawing._assert_native_layout)
    assert "describe_sheet(" in inspect.getsource(drawing._collect_sheet)
