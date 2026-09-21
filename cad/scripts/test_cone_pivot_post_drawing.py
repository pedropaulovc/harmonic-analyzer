"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import re
from pathlib import Path

import build_cone_pivot_post as part
import cone_pivot_post_spec as spec
import draw_cone_pivot_post as drawing
from _assembly import _seed_flip, activate_assembly_contract
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
    """The cone-axis view alone exposes the boss OD and bore in true shape."""
    cone_owned = (
        spec.DRAWING_DIMENSIONS["ConeBossProfile"]
        | spec.DRAWING_DIMENSIONS["JournalBoreProfile"]
    )
    assert set(drawing.JOURNAL_KEEP) == cone_owned
    assert drawing.CONE_AXIS_VIEW == part.CONE_AXIS_VIEW == "CONE JOURNAL"


def test_cone_boss_length_lives_in_the_bore_plane_section() -> None:
    """The raised boss's axial extent is dimensioned where its profile is visible."""
    assert drawing.SECTION_SCALE == (1, 2)
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
            cone_gear_shaft_spec.SECTION_DIA_BAND,
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
    assert source.count("set_dimension_bilateral_tolerance(") == 2
    assert "set_dimension_symmetric_tolerance" not in source
    assert "deviations(RUNNING_BORE_BAND)" in source
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
    activate_assembly_contract("drive-train")
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
    assert source.count('create_sketch("ConeShaftNormal")') == 2
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
