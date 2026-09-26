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


def test_part_hidden_reference_sketches_print_from_one_model_view_each() -> None:
    """The part saves its two reference sketches hidden (#880).

    ``_drawing_hidden_sketches`` shows an owner sketch per view in a MODEL
    view only: a derived view (the A section) takes the part's hidden state
    at creation and refuses the per-view show, so it could not print their
    dimensions.  Each sketch is dimensioned by exactly one view, which is the
    one view that shows its witness geometry.
    """
    assert drawing.curate_view_dimensions.__module__ == "_drawing_hidden_sketches"
    model_views = {
        "front": drawing.FRONT_KEEP,
        "top": drawing.TOP_KEEP,
        "cone journal": drawing.JOURNAL_KEEP,
    }
    shown_in = {}
    for sketch in ("JournalPlanReference", "BoreSpacingReference"):
        owned = spec.DRAWING_DIMENSIONS[sketch]
        assert not owned & set(drawing.SECTION_KEEP), sketch
        shown_in[sketch] = [view for view, keep in model_views.items() if owned & set(keep)]
    assert shown_in == {
        "JournalPlanReference": ["top"],
        "BoreSpacingReference": ["cone journal"],
    }


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
    assert "process=FOOT_DOWEL_PREFIX" in source
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
    literals (FOOT_NOTE_XY, FOOT_DOWEL_CALLOUT_XY); both are gone, and so is
    the fixed plan-to-foot slot (foot_callout_shift) the planner replaced."""
    import inspect

    assert not hasattr(drawing, "FOOT_NOTE_XY")
    assert not hasattr(drawing, "FOOT_DOWEL_CALLOUT_XY")
    assert not hasattr(drawing, "foot_callout_shift")
    # The callout names ONE dowel: the edge pick breaks the z tie.
    assert "center_z_mm" in inspect.signature(drawing._circular_edge).parameters


def test_foot_dowel_prefix_is_a_rewrap_not_new_words() -> None:
    """The break at the prefix's end puts the native size/band/depth on its
    own row: joined to "REAM (...) FROM FOOT" that row ran ~120 mm, wider
    than any free field on the sheet.  Same words, same order."""
    from cone_post_dowel_spec import POST_DOWEL_CALLOUT

    assert drawing.FOOT_DOWEL_PREFIX.endswith("\n")
    assert drawing.FOOT_DOWEL_PREFIX.split() == POST_DOWEL_CALLOUT.split()


# S1 leaf 917-s1-9eb0 (drawing:cone_pivot_post): the sheet at the foot view's
# placement, exactly as collect_document read it (describe_sheet, task log
# lines 242-366).  The 1-D sweep failed on it: "no clear place for the caption
# (32.7 x 9.1 mm) and its view [211.4,214.2]..[244.6,261.8]mm".
_9EB0_SHEET = """\
sheet 'Sheet1': 431.8 x 279.4 mm
  inner border (zone margins): [12.7,12.7]..[419.1,266.7]mm
  glyph advance ratio: 0.746
  keep-out title-block: [216.0,0.0]..[431.8,66.0]mm
  view 'Drawing View1': [70.4,63.4]..[125.6,160.6]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View2': [70.4,166.9]..[125.6,251.1]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View3': [200.0,111.4]..[270.0,208.6]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View4': [313.0,85.4]..[407.0,214.6]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Drawing View5': [211.4,214.2]..[244.6,261.8]mm scale 1:2 mode 2 parent-display=False faceted-hlr=False type=7
  view 'Section View A-A': [268.4,202.0]..[321.6,258.0]mm scale 1:1 mode 2 parent-display=False faceted-hlr=False type=2
  dim 'MainBodyDia' owner='Drawing View1' text[estimated]=[142.8,77.2]..[168.9,80.7]mm [148.1,77.2]..[161.2,80.7]mm
      GetPosition=(150.00,80.00)mm
      line: (77.0,70.0)->(77.0,78.2)mm
      line: (119.0,70.0)->(119.0,78.2)mm
      line: (77.0,77.2)->(70.6,77.2)mm
      line: (77.0,77.2)->(119.0,77.2)mm
      leader: (119.0,77.2)->(158.5,77.2)mm
  dim 'MainBodyHt' owner='Drawing View1' text[estimated]=[34.2,109.2]..[49.8,112.7]mm
      GetPosition=(40.00,112.00)mm
      line: (118.0,69.0)->(39.0,69.0)mm
      line: (118.0,155.0)->(39.0,155.0)mm
      leader: (40.0,69.0)->(40.0,109.2)mm
      line: (40.0,155.0)->(40.0,114.8)mm
  dim 'HeadHt' owner='Drawing View1' text[estimated]=[144.2,138.9]..[159.8,142.4]mm
      GetPosition=(150.00,141.70)mm
      line: (121.0,128.4)->(151.0,128.4)mm
      line: (121.0,155.0)->(151.0,155.0)mm
      leader: (150.0,128.4)->(150.0,138.9)mm
      line: (150.0,155.0)->(150.0,144.5)mm
  dim 'CrankAxisY' owner='Drawing View1' text[estimated]=[51.2,102.6]..[74.7,106.1]mm
      GetPosition=(60.00,105.35)mm
      line: (112.5,141.7)->(59.0,141.7)mm
      line: (97.0,69.0)->(59.0,69.0)mm
      line: (60.0,141.7)->(60.0,108.1)mm
      leader: (60.0,69.0)->(60.0,102.6)mm
  dim 'CrankBossDia' owner='Drawing View1' text[estimated]=[124.8,120.0]..[150.9,123.5]mm [130.1,120.0]..[140.6,123.5]mm [117.5,114.4]..[143.6,117.9]mm
      GetPosition=(132.00,120.00)mm
      line: (104.0,132.5)->(115.9,114.4)mm
      line: (92.0,150.9)->(104.0,132.5)mm
      line: (115.9,114.4)->(146.5,114.4)mm
  dim 'CrankBoreDia' owner='Drawing View1' text[estimated]=[131.4,170.3]..[157.5,173.8]mm [136.6,170.3]..[154.9,173.8]mm [152.2,174.8]..[154.8,178.3]mm [152.8,170.3]..[155.4,173.8]mm [155.0,174.8]..[168.0,178.3]mm [155.0,170.3]..[168.0,173.8]mm [128.0,164.7]..[167.2,168.2]mm
      GetPosition=(149.00,172.00)mm
      line: (102.4,145.3)->(126.4,164.7)mm
      line: (93.6,138.1)->(102.4,145.3)mm
      line: (126.4,164.7)->(170.0,164.7)mm
  note 'DetailItem371' owner='Drawing View1' text[exact]=[98.3,98.5]..[180.1,112.4]mm
      GetPosition=(165.00,112.00)mm
      leader: (164.5,110.7)->(164.5,110.7)mm
      leader: (164.5,110.7)->(98.4,97.9)mm
      leader: (164.5,110.7)->(98.4,97.9)mm
  dim 'CrankBossStartZ' owner='Drawing View2' text[estimated]=[58.4,231.0]..[76.7,234.5]mm
      GetPosition=(65.50,233.80)mm
      line: (97.0,244.5)->(64.5,244.5)mm
      line: (123.5,223.1)->(64.5,223.1)mm
      line: (65.5,244.5)->(65.5,236.6)mm
      leader: (65.5,223.1)->(65.5,231.0)mm
  dim 'InclineAngle' owner='Drawing View2' text[estimated]=[136.5,195.6]..[149.6,199.1]mm [113.0,190.1]..[165.3,193.6]mm
      GetPosition=(142.00,195.64)mm
      line: (98.0,171.5)->(98.0,170.3)mm
      line: (106.9,183.1)->(109.5,171.5)mm
      line: (98.0,171.3)->(109.2,172.5)mm
      leader: (109.2,172.5)->(138.0,190.1)mm
  dim 'HeadDia' owner='Drawing View2' text[estimated]=[63.8,188.0]..[89.9,191.5]mm [69.1,188.0]..[79.6,191.5]mm [61.8,182.4]..[77.4,185.9]mm
      GetPosition=(71.00,188.00)mm
      line: (89.9,202.7)->(81.8,182.4)mm
      line: (106.1,243.6)->(89.9,202.7)mm
      leader: (81.8,182.4)->(61.8,182.4)mm
  dim 'CrankBossLen' owner='Drawing View2' text[estimated]=[51.5,209.0]..[61.9,212.5]mm [32.2,203.4]..[76.6,206.9]mm
      GetPosition=(56.00,209.00)mm
      line: (108.0,244.5)->(55.0,244.5)mm
      line: (108.0,172.5)->(55.0,172.5)mm
      line: (56.0,244.5)->(56.0,214.6)mm
      leader: (56.0,172.5)->(56.0,203.4)mm
  dim 'MountWestX' owner='Drawing View2' text[estimated]=[102.9,249.7]..[121.2,253.2]mm
      GetPosition=(110.00,252.50)mm
      leader: (111.4,232.4)->(111.4,250.7)mm
      line: (98.0,248.6)->(98.0,250.7)mm
      leader: (111.4,249.7)->(117.8,249.7)mm
      leader: (111.4,249.7)->(98.0,249.7)mm
      line: (98.0,249.7)->(91.7,249.7)mm
  dim 'MountEastX' owner='Drawing View2' text[estimated]=[67.9,249.7]..[86.2,253.2]mm
      GetPosition=(75.00,252.50)mm
      leader: (84.6,232.4)->(84.6,250.7)mm
      line: (98.0,248.6)->(98.0,250.7)mm
      leader: (84.6,249.7)->(67.9,249.7)mm
      leader: (84.6,249.7)->(98.0,249.7)mm
  dim 'RD1' owner='Drawing View2' text[estimated]=[138.1,250.1]..[146.0,253.6]mm [144.8,250.0]..[171.0,253.5]mm [150.1,250.1]..[186.7,253.6]mm [137.9,244.4]..[166.6,247.9]mm [147.3,244.4]..[173.4,247.9]mm [152.6,244.4]..[170.9,247.9]mm [166.8,244.4]..[198.1,247.9]mm [171.8,244.4]..[184.9,247.9]mm
      GetPosition=(160.00,250.00)mm
      line: (115.8,226.9)->(136.3,244.4)mm
      line: (107.1,219.4)->(115.8,226.9)mm
      leader: (136.3,244.4)->(182.1,244.4)mm
  dim 'JournalBoreDia' owner='Drawing View3' text[estimated]=[274.4,151.3]..[300.5,154.8]mm [279.6,151.3]..[297.9,154.8]mm [295.2,155.8]..[297.8,159.3]mm [295.8,151.3]..[298.4,154.8]mm [298.0,155.8]..[311.0,159.3]mm [298.0,151.3]..[311.0,154.8]mm [272.2,145.7]..[308.8,149.2]mm
      GetPosition=(292.00,153.00)mm
      line: (244.1,149.5)->(270.6,145.7)mm
      line: (232.0,151.2)->(244.1,149.5)mm
      line: (270.6,145.7)->(311.8,145.7)mm
  dim 'JournalAxisY' owner='Drawing View3' text[estimated]=[182.9,154.2]..[201.2,157.7]mm
      GetPosition=(190.00,157.00)mm
      line: (228.4,150.4)->(207.0,150.4)mm
      line: (237.1,117.0)->(207.0,117.0)mm
      line: (208.0,150.4)->(208.0,133.7)mm
      line: (208.0,117.0)->(208.0,133.7)mm
      leader: (208.0,133.7)->(197.1,154.2)mm
      leader: (197.1,154.2)->(182.9,154.2)mm
  dim 'ConeBossDia' owner='Drawing View3' text[estimated]=[284.8,172.0]..[310.9,175.5]mm [290.1,172.0]..[300.6,175.5]mm [263.1,166.4]..[315.3,169.9]mm
      GetPosition=(292.00,172.00)mm
      line: (245.2,155.2)->(261.5,166.4)mm
      line: (231.0,145.5)->(245.2,155.2)mm
      line: (261.5,166.4)->(320.9,166.4)mm
  dim 'CrankAboveCone' owner='Drawing View3' text[estimated]=[179.3,178.5]..[197.6,182.0]mm [193.5,183.0]..[196.1,186.5]mm [196.4,183.0]..[206.8,186.5]mm [196.4,178.5]..[206.8,182.0]mm
      GetPosition=(193.00,183.00)mm
      line: (228.4,150.4)->(207.0,150.4)mm
      line: (237.1,189.7)->(207.0,189.7)mm
      line: (208.0,150.4)->(208.0,170.0)mm
      line: (208.0,189.7)->(208.0,170.0)mm
      leader: (208.0,170.0)->(206.7,178.5)mm
      leader: (206.7,178.5)->(179.3,178.5)mm
  dim 'ConeBossLen' owner='Section View A-A' text[estimated]=[350.5,235.0]..[360.9,238.5]mm [324.5,229.4]..[382.0,232.9]mm
      GetPosition=(355.00,235.00)mm
      line: (291.4,250.7)->(349.7,263.7)mm
      line: (300.5,209.7)->(358.8,222.6)mm
      line: (348.7,263.4)->(353.8,240.6)mm
      leader: (357.8,222.4)->(356.2,229.4)mm
  note 'DetailItem360' owner='Section View A-A' text[exact]=[271.7,177.3]..[317.8,193.7]mm
      GetPosition=(295.00,193.63)mm
"""
_9EB0_CAPTION = (0.0327, 0.0091)
_FOOT = "Drawing View5"


def _sheet_from_dump(text: str):
    """A SheetGeometry from a describe_sheet dump.  The dump has no pictorial
    flag: the view centred on ISO_CENTER is the isometric."""
    from _drawing_layout_check import DrawableRegion
    from _layout_geometry import AnnotationGeometry, Box, Segment, SheetGeometry, ViewGeometry

    box_re = re.compile(r"\[(-?[\d.]+),(-?[\d.]+)\]\.\.\[(-?[\d.]+),(-?[\d.]+)\]")
    seg_re = re.compile(r"\((-?[\d.]+),(-?[\d.]+)\)->\((-?[\d.]+),(-?[\d.]+)\)")
    region, keep_outs, views, rows = None, [], [], []
    for line in text.splitlines():
        boxes = [Box(*(float(v) / 1000.0 for v in m.groups())) for m in box_re.finditer(line)]
        if "inner border" in line:
            region = DrawableRegion(boxes[0].xmin, boxes[0].ymin, boxes[0].xmax, boxes[0].ymax)
        elif line.startswith("  keep-out "):
            keep_outs.append((line.split()[1].rstrip(":"), boxes[0]))
        elif line.startswith("  view '"):
            centre = boxes[0].center()
            views.append(
                ViewGeometry(
                    line.split("'")[1],
                    boxes[0],
                    pictorial=max(abs(a - b) for a, b in zip(centre, drawing.ISO_CENTER)) < 1e-3,
                )
            )
        elif re.match(r"^  [a-z-]+ '", line):
            owner = re.search(r"owner='([^']*)'", line).group(1)
            rows.append((line.split("'")[1], line.split()[0], owner, boxes, []))
        elif re.match(r"^\s+(line|leader):", line):
            role = line.strip().split(":")[0]
            values = (float(v) / 1000.0 for v in seg_re.search(line).groups())
            rows[-1][4].append(Segment(*values, role=role))
    return SheetGeometry(
        "Sheet1",
        0.4318,
        0.2794,
        region,
        tuple(keep_outs),
        tuple(views),
        tuple(
            AnnotationGeometry(label, kind, owner, tuple(boxes), tuple(segments))
            for label, kind, owner, boxes, segments in rows
        ),
    )


def _9eb0(**skip):
    from _layout_planner import sheet_obstacles

    sheet = _sheet_from_dump(_9EB0_SHEET)
    foot = next(view.outline for view in sheet.views if view.name == _FOOT)
    return foot, sheet_obstacles(sheet, skip_views=(_FOOT,), **skip)


def test_9eb0_foot_spot_is_rejected_for_every_caption_arrangement() -> None:
    """(a) Today's spot: over the view the caption crosses the top border,
    left it lands on RD1 (the plan's counterbore callout -- named by its WHOLE
    text box, not one row), right on section A-A."""
    from _layout_planner import box_conflict, caption_boxes

    foot, obstacles = _9eb0()
    reasons = [
        box_conflict(caption, obstacles) or ""
        for _, caption in caption_boxes(foot, _9EB0_CAPTION)
    ]
    assert reasons[0].startswith("border")
    assert reasons[1] == "text RD1 [137.9,244.4]..[198.1,253.6]mm"
    assert "Section View A-A" in reasons[2]


def test_9eb0_foot_group_moves_to_the_nearest_clear_spot() -> None:
    """(b) The 2-D search finds the nearest legal group, and every box in it
    clears everything collect_document read."""
    from _layout_planner import box_conflict, plan_view_group

    foot, obstacles = _9eb0()
    plan = plan_view_group(
        foot, _9EB0_CAPTION, obstacles, label="foot view", view_name=_FOOT
    )
    assert plan.how == "caption beside the view, left"
    assert (plan.view_dx, plan.view_dy) == pytest.approx((0.012, 0.0))
    assert box_conflict(plan.view, obstacles) is None
    assert box_conflict(plan.caption, obstacles) is None


def test_clear_foot_spot_does_not_move() -> None:
    """(c) No churn: with RD1 gone the left caption clears where the view
    stands, and the plan is the current spot."""
    from _layout_planner import plan_view_group

    foot, obstacles = _9eb0(skip_labels=("RD1",))
    plan = plan_view_group(
        foot, _9EB0_CAPTION, obstacles, label="foot view", view_name=_FOOT
    )
    assert (plan.view_dx, plan.view_dy) == (0.0, 0.0)
    assert plan.view == foot
    assert plan.how == "caption beside the view, left"


def test_placed_boxes_keep_off_the_isometric_and_other_views_text() -> None:
    """A pictorial outline excuses a leader clipping its empty corner, not a
    view or a text block laid over the picture; and text keeps one text
    height from another view's annotations (the audit's view-crowding)."""
    from _layout_geometry import Box
    from _layout_planner import box_conflict

    _, obstacles = _9eb0()
    iso = next(box for name, box, pictorial in obstacles.views if pictorial)
    inside = Box(iso.xmin + 0.010, iso.ymin + 0.030, iso.xmin + 0.043, iso.ymin + 0.078)
    assert (box_conflict(inside, obstacles) or "").startswith("pictorial view Drawing View4")
    # 3 mm under RD1's text (9.2 mm tall): clear of text, crowded for a
    # foot-view callout, fine for the plan's own.
    under = Box(0.140, 0.2414 - 0.0181, 0.180, 0.2414)
    assert box_conflict(under, obstacles, owner="Drawing View2") is None
    assert (box_conflict(under, obstacles, owner=_FOOT) or "").startswith("crowding RD1")


def _synthetic_callout(width: float):
    """A foot-view hole callout: rows of ``width`` x 18.1 mm (the platform
    twin's measured height), its shelf under the text, its rim inside the
    foot view.  Synthetic: the contract is the search, not a box."""
    from _layout_geometry import Box, Segment
    from _layout_planner import HoleCallout

    text = Box(0.150, 0.220, 0.150 + width, 0.2381)
    return HoleCallout(
        "RDx",
        _FOOT,
        text,
        Segment(text.xmin, text.ymin, text.xmax, text.ymin, role="leader"),
        (0.2280, 0.2314, 0.0008),
    )


def test_foot_group_plans_the_dowel_callout_with_its_leader() -> None:
    from _layout_planner import box_conflict, leader_conflicts, plan_view_group

    foot, obstacles = _9eb0()
    plan = plan_view_group(
        foot,
        _9EB0_CAPTION,
        obstacles,
        label="foot view",
        view_name=_FOOT,
        callout=_synthetic_callout(0.090),
    )
    placed = obstacles.plus(
        views=((_FOOT, plan.view),), texts=(("foot view caption", plan.caption),)
    )
    assert box_conflict(plan.callout_text, placed, owner=_FOOT) is None
    assert leader_conflicts(plan.callout_leader, placed) == []
    # SolidWorks' shape: the leader leaves the (moved) rim for the nearer
    # shelf end.
    tip = plan.callout_leader[0]
    rim_x, rim_y = 0.2280 + plan.view_dx, 0.2314 + plan.view_dy
    assert ((tip.x0 - rim_x) ** 2 + (tip.y0 - rim_y) ** 2) ** 0.5 == pytest.approx(0.0008)
    assert tip.x1 in (plan.callout_text.xmin, plan.callout_text.xmax)


def test_foot_group_fails_loud_naming_the_nearest_rejection() -> None:
    from _layout_planner import plan_view_group

    foot, obstacles = _9eb0()
    with pytest.raises(RuntimeError, match="no clear place") as failure:
        plan_view_group(
            foot,
            _9EB0_CAPTION,
            obstacles,
            label="foot view",
            view_name=_FOOT,
            callout=_synthetic_callout(0.130),
        )
    message = str(failure.value)
    assert "nearest rejected group: caption over the view" in message
    assert "RDx (130.0 x 18.1 mm), nearest: caption beside the view, left at shift (+12,+0) mm" in message
    assert "text RD1 [137.9,244.4]..[198.1,253.6]mm" in message


def test_callout_search_is_bounded_by_its_budget() -> None:
    """The search runs while the build holds the COM seat: a sheet with no
    room stops after ``callout_budget`` text spots and says so, instead of
    judging every spot of every group (30 x 14641 on a 2 mm grid)."""
    from _layout_planner import CALLOUT_BUDGET, plan_view_group

    assert CALLOUT_BUDGET <= 40_000
    foot, obstacles = _9eb0()
    with pytest.raises(RuntimeError, match="no clear place") as failure:
        plan_view_group(
            foot,
            _9EB0_CAPTION,
            obstacles,
            label="foot view",
            view_name=_FOOT,
            callout=_synthetic_callout(0.130),
            callout_budget=500,
        )
    assert "1 clear view+caption group(s) and 500 text spot(s) (budget 500)" in str(
        failure.value
    )


def test_first_leader_conflict_agrees_with_the_full_list() -> None:
    from _layout_planner import leader_conflict, leader_conflicts

    _, obstacles = _9eb0()
    callout = _synthetic_callout(0.090)
    for dx, dy in ((0.0, 0.0), (-0.070, -0.0074), (0.030, 0.040)):
        leader = callout.leader(dx, dy, (0.0, 0.0))
        full = leader_conflicts(leader, obstacles)
        assert leader_conflict(leader, obstacles) == (full[0] if full else None)


def test_post_plans_its_foot_group_last() -> None:
    """The plan reads every box on the sheet, so it runs after the last
    literal-placed annotation (the Manufacturing Notes block)."""
    import inspect

    build = inspect.getsource(drawing.build)
    assert build.index('"Manufacturing Notes"') < build.index("_place_foot_group(adapter, foot)")
    group = inspect.getsource(drawing._place_foot_group)
    for call in ("plan_view_group(", "sheet_obstacles(", "_collect_sheet(", "HoleCallout("):
        assert call in group
    assert "_collect_sheet(" in inspect.getsource(drawing._assert_native_layout)
    assert "describe_sheet(" in inspect.getsource(drawing._collect_sheet)


def _two_rd1_sheet():
    """Leaf 917-s1-b5d9 (swmaker000006): SolidWorks names hole callouts per
    view, so the plan's RD1 (Drawing View2) and the foot's new dowel callout
    (Drawing View5) are both 'RD1'."""
    from types import SimpleNamespace

    from _layout_geometry import AnnotationGeometry, Box

    return SimpleNamespace(
        annotations=[
            AnnotationGeometry(
                "RD1", "dim", "Drawing View2", text_boxes=(Box(0.138, 0.244, 0.200, 0.2535),)
            ),
            AnnotationGeometry(
                "RD1", "dim", "Drawing View5", text_boxes=(Box(0.151, 0.214, 0.288, 0.232),)
            ),
        ]
    )


def test_foot_callout_read_back_keys_on_label_and_owning_view(monkeypatch) -> None:
    """917-s1-b5d9 died with "post dowel callout 'RD1' was not read back": the
    read-back matched the name alone and found the plan's RD1 too."""
    import diagnostics.drawing_layout_audit as audit

    sheet = _two_rd1_sheet()
    (read,) = drawing._owned_annotations(sheet, "RD1", "Drawing View5")
    assert read.owner == "Drawing View5"
    monkeypatch.setattr(audit, "collect_document", lambda adapter: [sheet])
    box = drawing._annotation_text_box(None, "RD1", "Drawing View5")
    assert (box.xmin, box.ymin, box.xmax, box.ymax) == (0.151, 0.214, 0.288, 0.232)


def test_hole_callout_prefix_keeps_a_trailing_line_break() -> None:
    """RD1 probe (917-s1-rd1probe, swmaker000007): the foot's callout read
    back "...FROM FOOT 2X <MOD-DIAM> 3.188 <HOLE-DEPTH> 8.5" on one 117 mm
    row.  add_native_hole_callout joined process and format text with
    process.rstrip() + " ", which ate FOOT_DOWEL_PREFIX's closing line
    break, so the rewrap never reached the sheet."""
    import inspect

    import _drawing_common as dc

    native = "2X <MOD-DIAM> 3.188 <HOLE-DEPTH> 8.5"
    composed = dc.compose_hole_callout_prefix(drawing.FOOT_DOWEL_PREFIX, native)
    assert composed.splitlines()[-1] == native
    assert composed.splitlines()[-2] == drawing.FOOT_DOWEL_PREFIX.splitlines()[-1]
    # A one-line process still joins its format text with one space.
    assert dc.compose_hole_callout_prefix("DRILL ", " 2X <MOD-DIAM>") == "DRILL 2X <MOD-DIAM>"
    source = inspect.getsource(dc.add_native_hole_callout)
    assert "compose_hole_callout_prefix(process, existing)" in source


def test_a_foot_plan_no_fit_exports_the_sheet_before_raising(monkeypatch, tmp_path) -> None:
    """917-s1-568f failed loud on the planner's no-fit but saved no render, so
    whether the callout was really that wide stayed unknown until a probe
    leaf.  A failed plan exports the sheet (PDF + PNG) under failures/,
    which the leaf uploads, then raises the planner's own error."""
    import inspect

    exported: list[tuple[str, str]] = []

    def save(adapter, path, *, pdf_path):
        exported.append(("pdf", pdf_path))

    def render(pdf, png, *, layout):
        exported.append(("png", str(png)))

    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(drawing, "OUT_FAILURES", tmp_path)
    monkeypatch.setattr(drawing, "save_drawing", save)
    monkeypatch.setattr(drawing, "render_pdf_png", render)
    monkeypatch.setattr(drawing._telemetry, "event", lambda name, **a: events.append((name, a)))

    def no_fit():
        raise RuntimeError("foot view: no clear place for view")

    sizes = {"view": (0.0332, 0.0476), "callout": (0.1357, 0.0181)}
    with pytest.raises(RuntimeError, match="no clear place"):
        drawing._plan_or_export_sheet(object(), no_fit, label="foot view", sizes=sizes)
    kinds = [kind for kind, _ in exported]
    assert kinds == ["pdf", "png"]
    assert all(str(tmp_path) in path for _, path in exported)
    # The span event names the group and the sizes that did not fit.
    ((name, attributes),) = events
    assert name == "layout.no_fit"
    assert attributes["group"] == "foot view"
    assert attributes["callout_mm"] == "135.7 x 18.1"
    assert attributes["view_mm"] == "33.2 x 47.6"
    # A clear plan exports and records nothing.
    exported.clear()
    events.clear()
    assert (
        drawing._plan_or_export_sheet(object(), lambda: "plan", label="foot view", sizes=sizes)
        == "plan"
    )
    assert exported == [] and events == []
    assert "_plan_or_export_sheet(" in inspect.getsource(drawing._place_foot_group)


def _hole_callout_processes() -> list[tuple[str, str]]:
    """Every add_native_hole_callout(process=...) in the draw scripts,
    resolved to its value: a literal, or a module-level name."""
    import ast
    import importlib

    found = []
    for path in sorted(Path(drawing.__file__).resolve().parent.glob("draw_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", "")) == "add_native_hole_callout"
            ):
                continue
            for keyword in node.keywords:
                if keyword.arg != "process":
                    continue
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    found.append((path.stem, keyword.value.value))
                elif isinstance(keyword.value, ast.Name):
                    module = importlib.import_module(path.stem)
                    found.append((path.stem, getattr(module, keyword.value.id)))
    return found


def test_every_line_broken_hole_callout_process_keeps_its_break() -> None:
    """Main's ruling on the RD1 fix: prove the composed prefix for EVERY
    caller whose process ends in a line break, not just the constant."""
    import _drawing_common as dc

    native = "2X <MOD-DIAM> 3.188 <HOLE-DEPTH> 8.5"  # the probe's read-back
    processes = _hole_callout_processes()
    assert ("draw_cone_pivot_post", drawing.FOOT_DOWEL_PREFIX) in processes
    broken = [(stem, text) for stem, text in processes if text.rstrip(" ").endswith("\n")]
    assert broken, "no caller ends its process in a line break"
    for stem, text in broken:
        rows = dc.compose_hole_callout_prefix(text, native).splitlines()
        assert rows[-1] == native, stem
        assert rows[:-1] == text.rstrip().splitlines(), stem
