"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import ast
import math
import re
import tomllib
from types import SimpleNamespace
from pathlib import Path

import pytest

import _config
import build_dt_cone_pivot_post as part
import dt_cone_pivot_post_spec as spec
import _layout_geometry as layout
import draw_dt_cone_pivot_post as drawing
from _assembly import _seed_flip, activate_assembly_contract
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import MACHINED_UM, SEAT_UM, surface_finish_by_key


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_cone_pivot_post"].script
        == Path(drawing.__file__).resolve()
    )


def test_post_preserves_harvested_sizes_and_follows_the_configured_axes() -> None:
    assert spec.BLOCK_DIA == 42.011
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT) == (42.7506, 26.6)
    assert spec.HEAD_BASE_Y == pytest.approx(spec.BLOCK_HEIGHT - spec.HEAD_HEIGHT)
    assert (spec.CRANK_BOSS_DIA, spec.CRANK_BORE_DIA, spec.CRANK_BORE_OFFSET) == (
        21.93,
        11.438,
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
    # v36 (user ruling 2026-09-28): the boss starts on the head's tangent
    # plane and runs the harvested 2.8360 in from there.
    assert spec.CRANK_BOSS_NORTH_FACE == spec.HEAD_DIA / 2.0 == 21.3753
    assert spec.CRANK_BOSS_START_Z == -21.3753
    assert round(spec.CRANK_BOSS_END_Z, 4) == 50.6591
    assert spec.CRANK_BOSS_LENGTH == pytest.approx(2.8360 * 25.4)
    from dt_post_mount_stack import CONE_AXIS_HEIGHT_MM, POST_BODY_HEIGHT_MM

    assert (spec.CONE_BOSS_DIA, spec.BORE_DIA) == (17.2, 12.2808)
    assert spec.BORE_HEIGHT == CONE_AXIS_HEIGHT_MM
    assert spec.BLOCK_HEIGHT == POST_BODY_HEIGHT_MM
    assert spec.INCLINE_DEG == _config.machine("cone_incline", "derived_incline_deg")
    assert (
        spec.ATTACHMENT_THRU_DIA,
        spec.ATTACHMENT_CBORE_DIA,
        spec.ATTACHMENT_CBORE_DEPTH,
    ) == (7.14248, 11.50874, 6.0198)
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
        math.pi * (spec.BLOCK_DIA / 2.0) ** 2 * spec.BLOCK_HEIGHT
    )
    assert part.HEAD_SHELL_MM3 == pytest.approx(
        math.pi
        * ((spec.HEAD_DIA / 2.0) ** 2 - (spec.BLOCK_DIA / 2.0) ** 2)
        * spec.HEAD_HEIGHT
    )


def test_current_manufacturing_plan_tracks_post_geometry_without_changing_tooling() -> (
    None
):
    plan_path = (
        Path(part.__file__).resolve().parents[1]
        / "process/dt_cone_pivot_post/plan.toml"
    )
    plan = tomllib.loads(plan_path.read_text(encoding="utf-8"))
    setups = {setup["id"]: setup for setup in plan["setups"]}
    stock = plan["stock"]
    assert stock["length_mm"] == pytest.approx(
        stock["north_allowance_mm"] + spec.BLOCK_HEIGHT + stock["south_grip_mm"]
    )
    assert setups["S1"]["stock_state"]["south_end_z"] == pytest.approx(
        -spec.BLOCK_HEIGHT - stock["south_grip_mm"]
    )
    assert setups["S1"]["hold"]["stickout_mm"] == pytest.approx(
        stock["north_allowance_mm"] + spec.BLOCK_HEIGHT
    )
    assert setups["S2"]["stock_state"]["top_z"] == pytest.approx(
        spec.BLOCK_HEIGHT + stock["south_grip_mm"]
    )
    assert setups["S2"]["stock_state"]["local_thickness"] == {
        "mount_west": spec.BLOCK_HEIGHT,
        "mount_east": spec.BLOCK_HEIGHT,
    }
    head_face = next(op for op in setups["S2"]["ops"] if op["do"] == "face")
    assert head_face["to_z"] == spec.BLOCK_HEIGHT
    incline = math.radians(_config.machine("cone_incline", "derived_incline_deg"))
    journal = plan["frames"]["J3"]
    # 1.5 in: the plan's 38.1 and the spec's 1.5 * 25.4 differ in the last bit.
    assert journal["origin"] == pytest.approx([0.0, spec.BORE_HEIGHT, 0.0], abs=1e-9)
    assert journal["x"] == pytest.approx([math.cos(incline), 0.0, -math.sin(incline)])
    assert journal["z"] == pytest.approx([-math.sin(incline), 0.0, -math.cos(incline)])
    assert plan["frames"]["C4"]["origin"] == [
        0.0,
        spec.CRANK_BORE_HEIGHT,
        spec.CRANK_BOSS_START_Z,
    ]
    index = setups["S3"]["hold"]["index"]
    assert index["angle_deg"] == pytest.approx(spec.INCLINE_DEG)
    assert index["fixture"] == "BS-0" and index["positions"] == 1
    assert plan["construction"] == "one_piece"


def test_mounting_counterbores_take_the_last_printable_head_wall_station() -> None:
    """The Ø42.8 head retains 1.5 mm at the counterbores' printed corners."""
    assert spec.DRAWING_PRECISION_BY_NAME["HeadDia"] == 1
    assert spec.DRAWING_PRECISION_BY_NAME["MountWestX"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["MountEastX"] == 2
    head_radius_min = (round(spec.HEAD_DIA, 1) - spec._row(1)) / 2.0
    cbore_radius_max = (
        round(spec.ATTACHMENT_CBORE_DIA, 2) + spec._row(2)
    ) / 2.0
    wall = head_radius_min - (spec.ATTACHMENT_X + spec._row(2)) - cbore_radius_max
    assert spec.ATTACHMENT_X == pytest.approx(12.98)
    assert spec.ATTACHMENT_SPACING == pytest.approx(25.96)
    assert wall == pytest.approx(spec.MOUNT_HEAD_WEB_WORST)
    assert wall >= spec.WEB_FLOOR_MM - 1e-9
    assert wall - 0.01 < spec.WEB_FLOOR_MM


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


def _landscape_sheet() -> tuple[object, tuple]:
    from _drawing_layout_check import DrawableRegion
    from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
    from diagnostics.drawing_layout_audit import _keep_outs
    from test_drawing_layout_check import ZONE_MARGINS

    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    region = DrawableRegion.from_margins(template.width_m, template.height_m, **ZONE_MARGINS)
    return region, _keep_outs(template.width_m, template.height_m)


def _plan_gate(monkeypatch: pytest.MonkeyPatch, labels: list[str]) -> None:
    import diagnostics.drawing_layout_audit as audit

    region, keep_outs = _landscape_sheet()
    sheets = [
        SimpleNamespace(
            name="Sheet1",
            region=region,
            keep_outs=keep_outs,
            annotations=tuple(SimpleNamespace(label=label) for label in labels),
        ),
    ]
    monkeypatch.setattr(audit, "collect_document", lambda _adapter: sheets)
    monkeypatch.setattr(drawing, "_view_outline", lambda _view: (0.213, 0.117, 0.257, 0.2034))
    drawing._assert_native_layout(
        SimpleNamespace(currentModel=object()),
        "journal",
        expected_finish="x",
    )


def test_the_station_must_survive_its_hidden_sketch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hiding a sketch in a view hides what was imported from it (rim-aba9
    lost the station so), so the station and the plan angle come through the
    hidden-owner import, and the gate fails a sheet that lost either."""
    with pytest.raises(RuntimeError, match=r"\['CrankBossStartZ'\] once"):
        _plan_gate(monkeypatch, ["InclineAngle"])
    # Printed twice is as wrong as lost.
    with pytest.raises(RuntimeError, match=r"\['CrankBossStartZ'\] once"):
        _plan_gate(monkeypatch, ["CrankBossStartZ", "CrankBossStartZ", "InclineAngle"])
    with pytest.raises(RuntimeError, match=r"\['InclineAngle'\] once"):
        _plan_gate(monkeypatch, ["CrankBossStartZ"])
    # With both present the gate moves on to the title block.
    def title_block(_obj, _iface):
        raise LookupError("title block")

    monkeypatch.setattr(drawing, "_early_bound", title_block)
    with pytest.raises(LookupError, match="title block"):
        _plan_gate(monkeypatch, ["CrankBossStartZ", "InclineAngle"])


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


def _failing_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args, **_kwargs):
        raise RuntimeError("cone pivot post native annotation layout failed: probe")

    monkeypatch.setattr(drawing, "_assert_native_layout", fail)


@pytest.mark.parametrize("export", ["saveas_fails", "export_raises"])
def test_the_failure_pdf_never_masks_the_layout_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, export: str
) -> None:
    """Whatever the evidence export does -- SaveAs3 throwing inside it, or the
    export itself raising -- the layout gate's own error is what propagates."""
    _failing_layout(monkeypatch)
    monkeypatch.setattr(drawing._seat_forensics, "OUT_FAILURES", tmp_path)
    if export == "saveas_fails":

        def early_bound(_obj, _iface):
            raise OSError("SaveAs3 refused")

        monkeypatch.setattr(drawing, "_early_bound", early_bound)
    else:

        def boom(*_args, **_kwargs):
            raise ValueError("export blew up")

        monkeypatch.setattr(drawing, "_export_failure_pdf", boom)
    adapter = type("Adapter", (), {"currentModel": object()})()
    with pytest.raises(RuntimeError, match="native annotation layout failed: probe"):
        drawing._assert_native_layout_with_evidence(
            adapter, object(), expected_finish="x"
        )


def test_the_failure_evidence_is_the_sheet_as_a_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Model:
        def SaveAs3(self, path, _version, _options):
            Path(path).write_bytes(b"%PDF")

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, iface: obj)
    monkeypatch.setattr(drawing._seat_forensics, "OUT_FAILURES", tmp_path)
    drawing._export_failure_pdf(SimpleNamespace(currentModel=Model()), "native-layout")
    pdfs = sorted(path.name for path in tmp_path.rglob("*.pdf"))
    assert pdfs == ["dt-cone-pivot-post.pdf"]


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
    assert "draw_dt_cone_pivot_post.py" in PRECISION_MIGRATED_DRAWINGS
    # Only the two bores earn a third place, for their limits; the basic plan
    # angle prints the model's exact value (#906, it feeds the frame).
    assert {
        name
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places >= 3
    } == {"CrankBoreDia", "JournalBoreDia", "InclineAngle"}


def test_running_bores_close_the_configured_fit_class() -> None:
    """User ruling 2026-09-28: MHA-DT-011 runs directly in the restored Ø11.438
    crank bore, so both bores carry the one running band."""
    import _config
    import dt_cone_gear_shaft_spec
    import dt_crankshaft_spec

    upper, lower = spec.RUNNING_BORE_BAND
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    for bore, shaft_nominal, shaft_band in (
        (
            spec.CRANK_BORE_DIA,
            dt_crankshaft_spec.JOURNAL_DIA,
            dt_crankshaft_spec.JOURNAL_DIA_BAND,
        ),
        (
            spec.BORE_DIA,
            dt_cone_gear_shaft_spec.JOURNAL_DIA,
            dt_cone_gear_shaft_spec.SECTION_DIA_BANDS[0],
        ),
    ):
        shaft_max = shaft_nominal + shaft_band[0]
        shaft_min = shaft_nominal + shaft_band[1]
        clearances = (bore + lower - shaft_max, bore + upper - shaft_min)
        assert tuple(round(value, 3) for value in clearances) == expected


def test_nothing_else_on_the_casting_carries_a_band() -> None:
    """Each band named once, applied to the features whose fit needs it.

    The cast body, head and boss diameters and the mounting-hole stations
    are not accuracy features (cad/docs/tolerance-policy.md, "Result"), so the
    part must not author a tolerance on them at all: the title block's general
    grade is the whole specification.
    """
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 3
    assert source.count("set_dimension_symmetric_tolerance(") == 1
    assert source.count("deviations(RUNNING_BORE_BAND)") == 2
    assert source.count("deviations(CRANK_ABOVE_CONE_BAND)") == 1
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
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'plan.record("InclineAngle", \'"ConeIncline"\')' in source
    assert "add_angular_reference_dimension" not in source
    # Hidden through blank_reference_sketches (read back, and the drawing
    # shows it per view), never through the plane/axis blanker.
    assert "JournalPlanReference" not in source.split(
        "_blank_reference_geometry(\n        adapter,"
    )[1]


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
    """#906 (USER RULING 2026-09-26, option ii): rule 3's crank-mesh entry.

    One diametral angularity frame on the crank bore to datum A, the cone
    journal bore, clocked by datum B, the foot seat; its value is the spec
    constant, never sheet text, and it bounds yaw and tilt to about 0.08 deg
    over the boss.  A alone would leave tilt free.
    """
    from _gtol_spec import CylinderFace, PlanarFace

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
    assert frame.tolerance == f"{spec.CRANK_BORE_ANGULARITY_MM:.2f}" == "0.10"
    assert frame.face == CylinderFace(
        spec.CRANK_BORE_DIA, contains_y_mm=spec.CRANK_BORE_HEIGHT
    )
    # The zone spans the boss: 0.0795 deg over its 72.03.
    assert round(spec.CRANK_BORE_ANGLE_LIMIT_DEG, 4) == 0.0795
    assert part.PART_DATUMS is spec.PART_DATUMS
    assert part.GEOMETRIC_CONTROLS is spec.GEOMETRIC_CONTROLS
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert "**crank mesh** — MHA-DT-005's crank bore" in policy
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "datums=PART_DATUMS" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "set_basic_dimensions(adapter, annotations, BASIC_DIMENSIONS)" in source
    for banned in (
        "add_datum_feature(",
        "add_feature_control_frame(",
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
    stripped = re.sub(r"MHA-[A-Z]{2}-\d{3}(?:-T\d{3})?", "", spec.DRAWING_NOTES)
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
        "BossNorth",
    ):
        assert f'"{name}"' in source
    assert '("BossNorth", "PLANE")' in source  # hidden, not removed (#950)
    assert "_create_feature_cylinder_axis(" in source
    assert '"ConeShaftBoss",\n        CONE_BOSS_DIA / 2.0' in source
    assert '(("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X))' in source
    assert not hasattr(part, "CRANK_BORE_DX")
    assert not hasattr(part, "CRANK_BORE_Y")
    assert "HARVESTED_VOLUME_MM3" in source


def test_boss_north_is_the_whole_north_annulus_on_the_journal() -> None:
    """#916: BossNorth sits half a pad length north of ConeShaftNormal on the
    journal axis, faces away from the pads, and its face is the whole annulus
    between the pad and the journal bore."""
    import math

    incline = math.radians(spec.INCLINE_DEG)
    axis = (math.sin(incline), 0.0, math.cos(incline))
    assert part.BOSS_NORTH_NORMAL == pytest.approx([-c for c in axis], abs=1e-12)
    offset = [c - b for c, b in zip(part.BOSS_NORTH_CENTRE, (0.0, spec.BORE_HEIGHT, 0.0))]
    assert offset == pytest.approx(
        [-spec.CONE_BOSS_LENGTH / 2.0 * c for c in axis], abs=1e-12
    )
    assert part.BOSS_NORTH_AREA == pytest.approx(
        math.pi / 4.0 * (spec.CONE_BOSS_DIA**2 - spec.BORE_DIA**2)
    )


class _FakeSurface:
    def __init__(self, root_m: tuple[float, float, float]) -> None:
        self.PlaneParams = (0.0, 0.0, 0.0, *root_m)


class _FakeFace:
    def __init__(self, normal: tuple[float, ...], root_mm: tuple[float, ...]) -> None:
        self.Normal = normal
        self._surface = _FakeSurface(tuple(c / 1000.0 for c in root_mm))

    def GetSurface(self) -> _FakeSurface:
        return self._surface


def test_face_finder_keeps_only_the_square_face_through_the_station() -> None:
    """The finder matches by geometry, never by a view-dependent pick: a
    non-planar face (zero Normal), the opposite end, a face 12.5 deg off
    square and a parallel face off the station all fall out."""
    normal = part.BOSS_NORTH_NORMAL
    centre = part.BOSS_NORTH_CENTRE
    # any root point in the face plane: the centre moved across the axis
    in_plane = (centre[0] + 5.0 * normal[2], centre[1] + 3.0, centre[2] - 5.0 * normal[0])
    target = _FakeFace(normal, in_plane)
    faces = [
        _FakeFace((0.0, 0.0, 0.0), centre),  # the collar OD #916 picked
        _FakeFace(tuple(-c for c in normal), centre),  # the south end
        _FakeFace((0.0, 0.0, -1.0), centre),  # the crank boss's north face
        _FakeFace(normal, tuple(c + 0.01 * n for c, n in zip(centre, normal))),
        target,
    ]
    assert part._planar_faces_on(faces, normal, centre) == [target]


def test_rotated_post_reverses_the_cone_shaft_axial_mate_side() -> None:
    activate_assembly_contract("dt-drive-train")
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

    config = _config.parts("dt-cone-pivot-post")
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


def test_journal_rims_print_the_thrust_ring_break() -> None:
    """Codex P1 on #916 (PRRT_kwDOPHDy386mTQ-u): the collar's thrust ring is
    bounded by the collar OD edge AND the post's journal rim, so the rim
    prints the same derived break; the title block's 0.25 would leave the
    worst-case ring under its 1.5 floor."""
    import _config
    import dt_cone_gear_shaft_spec as shaft

    break_max = shaft.THRUST_EDGE_BREAK_MAX
    assert f"RIMS BREAK {break_max:.1f} MAX" == shaft.POST_JOURNAL_RIM_BREAK
    bore_callout = drawing.DIMENSION_CALLOUTS["JournalBoreDia"]
    assert bore_callout.splitlines()[-1] == shaft.POST_JOURNAL_RIM_BREAK
    assert f"EDGE BREAK {break_max:.1f} MAX" in shaft.COLLAR_STOCK_CALLOUT
    ring = shaft.THRUST_RING_MIN
    assert ring - 2.0 * break_max >= shaft.THRUST_RING_FLOOR
    # the title block's general break on the rim would not hold the floor
    general = max(
        float(_config.title_block("edge_break")[key])
        for key in ("radius_mm", "chamfer_max_mm")
    )
    assert ring - break_max - general < shaft.THRUST_RING_FLOOR
    # the ring's bore edge is the post's running bore at its band's top
    assert shaft.POST_JOURNAL_BORE_BAND == spec.RUNNING_BORE_BAND


def test_head_diameter_lives_on_its_plan_circle() -> None:
    """The front-view crank-bore leaders must not cross a head dimension line."""
    assert "HeadDia" in drawing.TOP_KEEP
    assert "HeadDia" not in drawing.FRONT_KEEP
    # Names the feature, not a process: the part may be turned from bar stock.
    assert drawing.DIMENSION_CALLOUTS["HeadDia"] == "HEAD"


def test_cone_boss_end_faces_are_located_by_symmetry() -> None:
    assert "CONE BOSS END FACES ARE SYMMETRIC ABOUT THE POST AXIS." in spec.DRAWING_NOTES


def test_collar_thrust_face_adds_no_setup_note() -> None:
    """#914: the collar face gets a finish symbol, not a method note (rule 6).

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
    """#914: the shaft collar runs on the north boss end face (rule 5)."""
    import math

    from _gtol_spec import PlanarFace
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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face")' in source
    assert "len(surface_boxes) != len(SURFACE_FINISHES)" in source


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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_add_cone_section_centerline(adapter, section)" in source


def test_crank_boss_station_prints_on_its_own_dimension_line() -> None:
    """Labelled, stacked, no shelf.  The station's text was once offset to a
    distant shelf, where a blind reader took it for a note, so it never leaves
    its own dimension line; and a bare station was not found as one (Main's
    rim-8339 ruling), so its label stacks with the value.  It stands once, in
    the plan."""
    assert "CrankBossStartZ" in drawing.TOP_KEEP
    assert "CrankBossStartZ" not in drawing.JOURNAL_TEXT_OFFSETS


def test_section_centerline_is_forced_to_print_black_in_center_font() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert drawing._SW_LINE_CENTER == 4
    assert "segment.Color = 0" in source
    assert "segment.Style = _SW_LINE_CENTER" in source
    assert "int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER" in source


def test_crank_boss_od_is_labelled_as_the_boss() -> None:
    """The elevation sees the boss's far end: its Ø is the boss."""
    assert drawing.DIMENSION_CALLOUTS["CrankBossDia"] == "CRANK BOSS"


def test_section_caption_states_no_scale_at_sheet_scale() -> None:
    assert drawing.SECTION_SCALE == drawing.SHEET_SCALE
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'expected = "<VLNAME> <VLLABEL>"\n' in source


def test_crank_boss_station_has_one_driving_global() -> None:
    """The printed station and the plane the boss grows from cannot drift apart."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"CrankBossNearZ": CRANK_BOSS_NEAR_Z,' in source
    assert 'drive_jobs.append(("D1@CrankInterfacePlane", \'"CrankBossNearZ"\'))' in source
    assert 'station.record("CrankBossStartZ", \'"CrankBossNearZ"\')' in source


def _blanked_reference_sketches() -> set[str]:
    """The sketches the post build passes to its one blank_reference_sketches."""
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "blank_reference_sketches"
    ]
    assert len(calls) == 1
    assert getattr(calls[0].args[1], "id", None) == "REFERENCE_SKETCHES"
    return set(part.REFERENCE_SKETCHES)


def test_the_post_saves_every_reference_sketch_hidden() -> None:
    """#880: no reference sketch renders in the part or any assembly.  Each
    one that carries a drawing dimension is saved hidden, read back, and the
    drawing shows it only in the view that dimensions it.  JournalPlanReference
    and BoreSpacingReference were the release's last visibility debt."""
    references = {name for name in spec.DRAWING_DIMENSIONS if name.endswith("Reference")}
    assert references == {
        "JournalPlanReference",
        "CrankBossStationReference",
        "BoreSpacingReference",
    }
    assert _blanked_reference_sketches() == references
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "SHOWN_SKETCH_ALLOWANCES" not in source
    assert "allowed_shown" not in source


def test_every_view_dimensioning_a_hidden_sketch_shows_it_itself() -> None:
    """A part-hidden sketch's dimensions import only through the hidden-owner
    import, which shows the sketch in that one view.  The plan owns the plan
    angle and the crank boss station, View B the bore spacing; no other view
    keeps anything from those sketches, so none of them prints a ray."""
    hidden = {
        item
        for name in _blanked_reference_sketches()
        for item in spec.DRAWING_DIMENSIONS[name]
    }
    assert hidden == {"InclineAngle", "CrankAboveCone", "CrankBossStartZ"}
    assert set(drawing.TOP_KEEP) & hidden == {"InclineAngle", "CrankBossStartZ"}
    assert set(drawing.JOURNAL_KEEP) & hidden == {"CrankAboveCone"}
    for keep in (drawing.FRONT_KEEP, drawing.SECTION_KEEP):
        assert not set(keep) & hidden
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for curated in ("top", "journal"):
        assert f"{curated}_annotations = curate_hidden_owner_dimensions(" in source
    for curated in ("front", "section"):
        assert f"{curated}_annotations = curate_view_dimensions(" in source


def test_crank_bore_is_located_from_the_cone_bore_and_never_binds() -> None:
    """U31: the 16T:64T mesh closes on the bore spacing, so the print states it.

    User ruling 2026-09-28: fixed centres, no drop and no fit-up bushing; the
    printed spacing band is one of crank_mesh_stack's terms, and its
    import-time assert is the never-bind check.
    """
    import crank_mesh_stack

    assert spec.CRANK_ABOVE_CONE == pytest.approx(
        _config.machine("gear_train", "crank_axis_height_mm") - spec.BORE_HEIGHT
    )
    assert spec.CRANK_ABOVE_CONE_BAND == (0.37, 0.0)
    assert crank_mesh_stack.SPACING_PRINTED == round(spec.CRANK_ABOVE_CONE, 2)
    assert abs(crank_mesh_stack.FRAME_DY - spec.CRANK_ABOVE_CONE) < 1e-9
    assert crank_mesh_stack.standard_check().backlash_min_mm > 0.0
    # The foot-to-crank height stays on the front view only as a reference.
    assert "CrankAxisY" in drawing.FRONT_KEEP
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="crank axis height reference"' in drawing_source
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert """set_global(adapter, "CrankAxisY", '"JournalAxisY" + "CrankAboveCone"')""" in source
    # Rule 6: the spacing band is a dimension, never a setup method.
    assert "ONE SETUP" not in spec.DRAWING_NOTES
    assert "BORE-TO-BORE" not in spec.DRAWING_NOTES


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


def _datum_b_frame_clears_the_notes(tag_y: float) -> bool:
    frame_bottom = tag_y - drawing._DATUM_TAG_FRAME_HEIGHT
    return frame_bottom >= drawing.NOTES_ANCHOR[1] + drawing._DATUM_NOTES_CLEARANCE - 1e-12


def _journal_sheet(text_box, spacing_segments):
    return SimpleNamespace(
        annotations=(
            layout.AnnotationGeometry(
                label="JournalAxisY", kind="dim", owner="v", text_boxes=(text_box,)
            ),
            layout.AnnotationGeometry(
                label="CrankAboveCone",
                kind="dim",
                owner="v",
                segments=tuple(spacing_segments),
            ),
        )
    )


# The 8f4aea333 control's audit: text [172.0,154.2]..[208.0,157.7] mm, crossed
# by CrankAboveCone's line (208.0,150.4)->(208.0,170.0) mm.
_CONTROL_TEXT = layout.Box(0.1720, 0.1542, 0.2080, 0.1577)
_SPACING_LINE = layout.Segment(0.2080, 0.1504, 0.2080, 0.1700, "line")


def test_datum_b_frame_clears_what_crossed_it() -> None:
    """Leaf w3-1026 (layout check with #1026's degenerate-line fix): datum B's
    frame sat on the manufacturing notes.  The placement now derives from the
    measured extents; the old one is the positive control."""
    assert not _datum_b_frame_clears_the_notes(drawing._front_y(-9.0))
    assert _datum_b_frame_clears_the_notes(drawing.DATUM_B_TAG_XY[1])
    # Still below the foot seat it tags.
    assert drawing.DATUM_B_TAG_XY[1] < drawing._front_y(0.0)


def test_33_37_text_is_placed_from_the_box_the_check_reads() -> None:
    """The audit's box width follows the sheet's calibrated glyph advance
    (34.0 mm on w3-1026, 36.0 mm on the 8f4aea333 control), so the shift comes
    from the box itself: the control's crossed box moves 2 mm left, and a
    narrower box moves right up to the same clearance."""
    box, line_x, shift = drawing.journal_axis_text_shift(
        _journal_sheet(_CONTROL_TEXT, [_SPACING_LINE])
    )
    assert box == _CONTROL_TEXT
    assert line_x == pytest.approx(0.2080)
    assert shift == pytest.approx(-0.002)

    narrow = layout.Box(0.1720, 0.1542, 0.2060 - 0.005, 0.1577)
    _, _, shift = drawing.journal_axis_text_shift(
        _journal_sheet(narrow, [_SPACING_LINE])
    )
    assert shift == pytest.approx(0.005)


def test_33_37_text_takes_the_nearest_line_beside_it() -> None:
    """Only a vertical line that runs alongside the text and lies right of its
    left edge bounds it; the nearest such line wins."""
    segments = [
        # Below the text: does not run alongside it.
        layout.Segment(0.2000, 0.1400, 0.2000, 0.1530, "line"),
        # Left of the text's left edge.
        layout.Segment(0.1700, 0.1500, 0.1700, 0.1700, "line"),
        # Horizontal.
        layout.Segment(0.1900, 0.1560, 0.2200, 0.1560, "line"),
        layout.Segment(0.2150, 0.1500, 0.2150, 0.1700, "line"),
        _SPACING_LINE,
    ]
    _, line_x, _ = drawing.journal_axis_text_shift(
        _journal_sheet(_CONTROL_TEXT, segments)
    )
    assert line_x == pytest.approx(0.2080)


def test_33_37_placement_fails_loud_without_its_line() -> None:
    """With no spacing line alongside, the placement premise is gone: it must
    raise rather than leave the text wherever it landed."""
    below = layout.Segment(0.2080, 0.1400, 0.2080, 0.1530, "line")
    with pytest.raises(RuntimeError, match="no vertical CrankAboveCone line"):
        drawing.journal_axis_text_shift(_journal_sheet(_CONTROL_TEXT, [below]))
