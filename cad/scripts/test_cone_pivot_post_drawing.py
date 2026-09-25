"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import re
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
    grade is the whole specification.
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
    assert source.count("wizard_holes(") == 1
    assert "attachment_cut.placement_drive_jobs" in source
    assert 'name="AttachmentScrewHoles"' in source




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


def test_deep_mounting_holes_carry_a_drilling_note() -> None:
    """U37: the 2X mounting holes run the full post height in cast iron."""
    assert "DRILL MOUNTING HOLES FROM TOP FACE" in spec.DRAWING_NOTES
    assert "CONE BORE AT BREAKOUT" in spec.DRAWING_NOTES


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
