"""Offline contracts for the v2 cone-pivot-post source and drawing."""

from __future__ import annotations

import math
import re
from types import SimpleNamespace
from pathlib import Path

import pytest

import build_cone_pivot_post as part
import cone_pivot_post_spec as spec
import _layout_geometry as layout
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
        round(spec.CRANK_BORE_HEIGHT, 6),
        spec.CRANK_BORE_OFFSET,
    ) == (21.93, 14.6, 72.49, 0.0)
    assert (spec.CRANK_AXIS_HEIGHT, spec.CRANK_BORE_DROP) == (72.7, 0.21)
    assert spec.CRANK_BOSS_LENGTH_IN == 2.8360
    # The spot face is stationed from the post axis, NOT from the cast collar.
    assert spec.CRANK_BOSS_HARVESTED_NORTH_FACE == 21.3753
    assert spec.CRANK_BOSS_START_Z != -spec.HEAD_DIA / 2.0
    # The harvested boss ends where it always did; the spot face stands the
    # retreat south of its harvested station, and the boss is that much shorter.
    assert round(spec.CRANK_BOSS_END_Z, 4) == 50.6591
    retreat = spec.CRANK_SPOT_FACE_RETREAT
    assert spec.CRANK_BOSS_NORTH_FACE == pytest.approx(21.3753 - retreat)
    assert spec.CRANK_BOSS_START_Z == pytest.approx(-(21.3753 - retreat))
    assert spec.CRANK_BOSS_LENGTH == pytest.approx(2.8360 * 25.4 - retreat)
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
    assert part.CRANK_BORE_MM3 == pytest.approx(
        math.pi * (spec.CRANK_BORE_DIA / 2.0) ** 2 * spec.CRANK_BOSS_LENGTH
    )
    assert round(part.ATTACHMENT_HOLES_MM3, 1) == 7661.6


def test_the_spot_face_volumes_are_their_columns() -> None:
    """Brute-force the spot face and its run-out flat on a grid, independently
    of the Simpson integrals the build checks each cut against."""
    station = spec.CRANK_BOSS_NORTH_FACE
    head_r, body_r, boss_r = spec.HEAD_DIA / 2.0, spec.BLOCK_DIA / 2.0, spec.CRANK_BOSS_DIA / 2.0
    axis = spec.CRANK_BORE_HEIGHT
    half = spec.CRANK_SPOT_FACE_WIDTH / 2.0
    bottom = axis - spec.CRANK_SPOT_FACE_RUN_OUT
    n = 600
    dx, dy = 2.0 * half / n, (axis - bottom) / n
    disc = run_out = 0.0
    for i in range(n):
        x = -half + (i + 0.5) * dx
        for k in range(n):
            y = bottom + (k + 0.5) * dy
            radius = head_r if y >= spec.HEAD_BASE_Y else body_r
            proud = max(math.sqrt(max(radius**2 - x * x, 0.0)) - station, 0.0)
            if math.hypot(x, y - axis) > boss_r:
                run_out += proud * dx * dy
    # The disc's upper half lies above the run-out's band: grid the whole disc.
    for i in range(n):
        x = -boss_r + (i + 0.5) * 2.0 * boss_r / n
        for k in range(n):
            y = axis - boss_r + (k + 0.5) * 2.0 * boss_r / n
            if math.hypot(x, y - axis) <= boss_r:
                proud = max(math.sqrt(head_r**2 - x * x) - station, 0.0)
                disc += proud * (2.0 * boss_r / n) ** 2
    assert part.CRANK_SPOT_FACE_RUN_OUT_MM3 == pytest.approx(run_out, rel=2e-3)
    assert part.CRANK_SPOT_FACE_MM3 == pytest.approx(disc, rel=2e-3)


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.TOP_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.JOURNAL_KEEP)
        | set(drawing.REAR_KEEP)
        | {drawing.SPOT_PLAN_DIMENSION}
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
        "SpotFaceWidth",
        "SpotFaceRunOut",
    }
    # No dimension may be placed twice: two views that both carry a value are
    # two chances for the sheet to contradict itself.
    assert (
        len(drawing.FRONT_KEEP)
        + len(drawing.TOP_KEEP)
        + len(drawing.SECTION_KEEP)
        + len(drawing.JOURNAL_KEEP)
        + len(drawing.REAR_KEEP)
        + 1
        == len(kept)
    )


def test_the_spot_face_run_out_is_dimensioned_face_on() -> None:
    """The run-out flat is on the north face, behind the elevation (which looks
    at the crank boss's far end), so only the rear view shows it face-on."""
    assert set(drawing.REAR_KEEP) == spec.DRAWING_DIMENSIONS["CrankSpotFaceRunOutProfile"]
    assert "*Back" in Path(drawing.__file__).read_text(encoding="utf-8")


def test_the_spot_face_has_its_own_sheet_at_two_to_one() -> None:
    """Sheet 1 had no room to show the D at a size a novice reads (the
    rim-8339 eye pass), so it is sheet 2, at 2:1, which the title block states;
    sheet 1 keeps 1:1 and points there by the derived sheet number."""
    assert drawing.SHEET_NAMES == ("MAIN", "SPOT-FACE")
    assert drawing.SHEET_SCALES == {"MAIN": (1.0, 1.0), "SPOT-FACE": (2.0, 1.0)}
    assert drawing.SPOT_FACE_SCALE == drawing.SHEET_SCALES[drawing.SPOT_FACE_SHEET]
    # Chosen by fit: the largest preferred scale whose views and text lanes
    # fit the sheet; the next preferred one does not.
    fitting = [s for s in drawing.PREFERRED_SCALES if drawing.spot_face_fits(s)]
    assert drawing.SPOT_FACE_SCALE == max(fitting, key=lambda s: s[0] / s[1])
    larger = [
        s
        for s in drawing.PREFERRED_SCALES
        if s[0] / s[1] > drawing.SPOT_FACE_SCALE[0] / drawing.SPOT_FACE_SCALE[1]
    ]
    assert larger and not any(drawing.spot_face_fits(s) for s in larger)
    assert drawing.SEE_SPOT_FACE_SHEET == "SPOT FACE:\nSEE SHEET 2"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "sheet_scales=SHEET_SCALES" in source
    assert "expected_sheet_names=SHEET_NAMES" in source
    # Every sheet-2 view is placed at the sheet's own scale.
    assert source.count("scale=SPOT_FACE_SCALE") == 2


def test_the_spot_face_dimensions_are_labelled_for_what_they_locate() -> None:
    assert drawing.SPOT_FACE_WIDTH_CALLOUT == {"SpotFaceWidth": "SPOT FACE WIDTH"}
    assert drawing.SPOT_FACE_CALLOUTS == {
        "SpotFaceRunOut": "RUN-OUT TO STEP",
        "CrankBossStartZ": "SPOT FACE STATION",
    }
    assert not set(drawing.DIMENSION_CALLOUTS) & (
        set(drawing.SPOT_FACE_WIDTH_CALLOUT) | set(drawing.SPOT_FACE_CALLOUTS)
    )
    # The collar the flat clears is the part's, not a typed 44.
    assert drawing.SPOT_FACE_NOTE == (
        f"SPOT FACE CLEARS <MOD-DIAM>{spec.HEAD_DIA:.0f} COLLAR"
    )
    assert spec.HEAD_DIA == 44.0


def _spot_face_outlines() -> dict[str, tuple[float, float, float, float]]:
    """Sheet-2 view outlines predicted from the part: ``place_view`` centres
    each on its projected bounding box.  The plan's box runs from the cone
    boss's corner (beyond the collar, whose flat trims it at the spot face) to
    the crank boss's far end."""
    f = drawing.SPOT_FACE_SCALE[0] / drawing.SPOT_FACE_SCALE[1] / 1000.0
    plan_depth = drawing.spot_plan_depth_mm()
    half = spec.HEAD_DIA / 2.0 * f
    rear_x, rear_y = drawing.REAR_CENTER
    plan_x, plan_y = drawing.SPOT_PLAN_CENTER
    return {
        "rear view": (
            rear_x - half,
            rear_y - spec.BLOCK_HEIGHT / 2.0 * f,
            rear_x + half,
            rear_y + spec.BLOCK_HEIGHT / 2.0 * f,
        ),
        "spot-face plan": (
            plan_x - half,
            plan_y - plan_depth / 2.0 * f,
            plan_x + half,
            plan_y + plan_depth / 2.0 * f,
        ),
    }


def _landscape_sheet() -> tuple[object, tuple]:
    from _drawing_layout_check import DrawableRegion
    from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
    from diagnostics.drawing_layout_audit import _keep_outs
    from test_drawing_layout_check import ZONE_MARGINS

    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    region = DrawableRegion.from_margins(template.width_m, template.height_m, **ZONE_MARGINS)
    return region, _keep_outs(template.width_m, template.height_m)


def test_the_plan_depth_is_the_cone_boss_corner_to_the_crank_boss_end() -> None:
    incline = math.radians(spec.INCLINE_DEG)
    corner = (spec.CONE_BOSS_LENGTH / 2.0) * math.cos(incline) + (
        spec.CONE_BOSS_DIA / 2.0
    ) * math.sin(incline)
    assert corner > spec.BLOCK_DIA / 2.0
    assert drawing.spot_plan_depth_mm() == pytest.approx(spec.CRANK_BOSS_END_Z + corner)


def test_the_drawable_region_is_the_templates_zone_margin() -> None:
    from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
    from test_drawing_layout_check import ZONE_MARGINS

    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    assert drawing.DRAWABLE == (
        ZONE_MARGINS["left"],
        ZONE_MARGINS["bottom"],
        template.width_m - ZONE_MARGINS["right"],
        template.height_m - ZONE_MARGINS["top"],
    )


def test_the_spot_face_views_fit_the_sheet_clear_of_the_title_block() -> None:
    region, keep_outs = _landscape_sheet()
    outlines = _spot_face_outlines()
    assert drawing.view_placement_problems(outlines, region, keep_outs) == []
    rear, plan = outlines["rear view"], outlines["spot-face plan"]
    # The run-out text stands between the two views, the station text left of
    # the plan and right of the run-out text.
    run_out_x = drawing.REAR_KEEP["SpotFaceRunOut"][0]
    station_x = plan[0] - drawing.SPOT_PLAN_TEXT_LEFT_OF_VIEW
    assert rear[2] < run_out_x < station_x < plan[0]


def _spot_face_gate(monkeypatch: pytest.MonkeyPatch, labels: list[str]) -> None:
    import diagnostics.drawing_layout_audit as audit

    region, keep_outs = _landscape_sheet()
    outlines = _spot_face_outlines()
    sheets = [
        SimpleNamespace(name="MAIN", region=region, keep_outs=keep_outs, annotations=()),
        SimpleNamespace(
            name="SPOT-FACE",
            region=region,
            keep_outs=keep_outs,
            annotations=tuple(SimpleNamespace(label=label) for label in labels),
        ),
    ]
    monkeypatch.setattr(audit, "collect_document", lambda _adapter: sheets)
    views = {label: label for label in outlines}
    journal_outline = (0.213, 0.117, 0.257, 0.2034)
    monkeypatch.setattr(
        drawing, "_view_outline", lambda view: outlines.get(view, journal_outline)
    )
    drawing._assert_native_layout(
        SimpleNamespace(currentModel=object()),
        "journal",
        spot_face_views=views,
        expected_finish="x",
    )


def test_the_station_must_survive_its_hidden_sketch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sheet 2 hides JournalPlanReference, whose rays read as edges without
    the plan angle.  Hiding a sketch in a view hides what was imported from
    it (rim-aba9 lost the station so), so the station comes from its own
    part-hidden sketch through the hidden-owner import, and the gate fails a
    sheet that lost it."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        '    for view in (rear, plan):\n'
        '        _hide_witness_sketch(adapter, view, "JournalPlanReference")\n'
    ) in source
    assert "plan_annotations = curate_hidden_owner_dimensions(" in source
    assert '"SpotFaceStationReference"' not in source.split("_hide_witness_sketch")[-1]
    with pytest.raises(RuntimeError, match=r"\['CrankBossStartZ'\] once"):
        _spot_face_gate(monkeypatch, ["SpotFaceWidth", "SpotFaceRunOut"])
    # With all three present the gate moves on to sheet 1's title block.
    def sheet_one(_obj, _iface):
        raise LookupError("sheet 1 title block")

    monkeypatch.setattr(drawing, "_early_bound", sheet_one)
    with pytest.raises(LookupError, match="sheet 1 title block"):
        _spot_face_gate(monkeypatch, ["SpotFaceWidth", "SpotFaceRunOut", "CrankBossStartZ"])


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


def test_the_station_text_stands_left_of_the_plan_half_way_to_the_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both ends of the station are projected from the model onto the placed
    plan, so the text follows the view, not a measured coordinate."""
    projected = {
        "plan post axis": (0.290, 0.1933),
        "plan spot face": (0.290, 0.2311),
    }
    monkeypatch.setattr(
        drawing,
        "model_point_in_view",
        lambda _adapter, _view, _xyz, *, label: projected[label],
    )
    monkeypatch.setattr(drawing, "_view_outline", lambda _view: (0.246, 0.092, 0.334, 0.238))
    keep = drawing._spot_plan_keep(object(), object())
    assert keep == {
        "CrankBossStartZ": (
            pytest.approx(0.246 - drawing.SPOT_PLAN_TEXT_LEFT_OF_VIEW),
            pytest.approx((0.1933 + 0.2311) / 2.0),
        )
    }


def test_a_view_label_centres_under_its_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """The text box does not sit on its insertion point, so the label is
    steered by its rendered extent until its top stands the gap under the view
    outline, centred on it."""

    class Annotation:
        def __init__(self) -> None:
            self.position = (0.041, 0.054, 0.0)

        def GetPosition(self):
            return self.position

        def SetPosition(self, x, y, z):
            self.position = (x, y, z)
            return True

    class Note:
        def __init__(self) -> None:
            self.annotation = Annotation()

        def GetAnnotation(self):
            return self.annotation

        def GetExtent(self):
            # 22 x 4.5 mm, offset from the anchor the way SolidWorks offsets it
            x, y, _z = self.annotation.position
            return (x + 0.0003, y - 0.0050, 0.0, x + 0.0223, y - 0.0005, 0.0)

    class Model:
        def GraphicsRedraw2(self) -> None:
            pass

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, iface: obj)
    note = Note()
    outline = (0.041, 0.054, 0.129, 0.226)
    adapter = type("Adapter", (), {"currentModel": Model()})()
    gap = drawing.VIEW_LABEL_GAP
    drawing._place_note_under(adapter, note, outline, gap=gap, label="rear view label")
    x0, _y0, _z0, x1, y1, _z1 = note.GetExtent()
    assert (x0 + x1) / 2.0 == pytest.approx((outline[0] + outline[2]) / 2.0, abs=1e-4)
    assert y1 == pytest.approx(outline[1] - gap, abs=1e-4)
    assert gap is layout.DEFAULT_MOVE_CLEARANCE_M


def _crank_evidence(boss_lists_spot_face: bool) -> dict:
    """The crank boss's BREP evidence as draw_cone_pivot_post reads it (model
    metres), shaped as the rim-124f leaf logged it (the run-out merges the
    spot face out of CrankSprocketBoss's list) or as before the run-out."""
    y = spec.CRANK_BORE_HEIGHT / 1000.0
    spot = ("plane", (0.0, 0.0, 1.0, 0.0, y, spec.CRANK_BOSS_START_Z / 1000.0))
    far = ("plane", (0.0, 0.0, 1.0, 0.0, y, spec.CRANK_BOSS_END_Z / 1000.0))
    wall = ("cylinder", (0.0, y, 0.0, 0.0, 0.0, 1.0, spec.CRANK_BOSS_DIA / 2000.0))
    return {
        "CrankSprocketBoss": [far, wall, spot] if boss_lists_spot_face else [far, wall],
        "CrankSpotFace": [wall, spot],
    }


@pytest.mark.parametrize("boss_lists_spot_face", [False, True])
def test_the_crank_boss_faces_resolve_to_spot_then_far(boss_lists_spot_face: bool) -> None:
    spot, far = drawing._crank_face_centres(_crank_evidence(boss_lists_spot_face))
    assert spot[2] * 1000.0 == pytest.approx(spec.CRANK_BOSS_START_Z)
    assert far[2] * 1000.0 == pytest.approx(spec.CRANK_BOSS_END_Z)


def test_the_crank_boss_face_set_is_asserted_not_guessed() -> None:
    """A boss missing its far face, or a spot face off its station, fails."""
    evidence = _crank_evidence(False)
    evidence["CrankSprocketBoss"] = evidence["CrankSprocketBoss"][1:]
    with pytest.raises(RuntimeError, match="expected 1"):
        drawing._crank_face_centres(evidence)
    evidence = _crank_evidence(False)
    kind, values = evidence["CrankSpotFace"][1]
    evidence["CrankSpotFace"][1] = (kind, values[:5] + (values[5] - 0.0025,))
    with pytest.raises(RuntimeError, match="spot face"):
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
            adapter, object(), spot_face_views={}, expected_finish="x"
        )


def test_the_failure_evidence_has_a_pdf_per_sheet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A PDF save prints the active sheet, so each sheet is activated and
    saved in turn; Main's eye pass needs sheet 2 as much as sheet 1."""
    saved = []

    class Drawing:
        active = ""

        def ActivateSheet(self, name):
            Drawing.active = name
            return True

        def SaveAs3(self, path, _version, _options):
            saved.append(Drawing.active)
            Path(path).write_bytes(b"%PDF")

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, iface: obj)
    monkeypatch.setattr(drawing._seat_forensics, "OUT_FAILURES", tmp_path)
    adapter = SimpleNamespace(currentModel=Drawing())
    drawing._export_failure_pdf(adapter, "native-layout")
    assert saved == list(drawing.SHEET_NAMES)
    pdfs = sorted(path.name for path in tmp_path.rglob("*.pdf"))
    assert pdfs == ["cone-pivot-post-main.pdf", "cone-pivot-post-spot-face.pdf"]


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
    # Only the two bores earn a third place: the cone journal's limits deliver
    # the shaft_in_bushing clearance band, the crank bore prints its H7; the
    # basic plan angle prints the model's exact value (#906, it feeds the
    # frame).
    assert {
        name
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places >= 3
    } == {"CrankBoreDia", "JournalBoreDia", "InclineAngle"}


def test_running_bore_closes_the_configured_fit_class() -> None:
    import _config
    import cone_gear_shaft_spec

    upper, lower = spec.RUNNING_BORE_BAND
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    shaft_nominal = cone_gear_shaft_spec.JOURNAL_DIA
    shaft_upper, shaft_lower = cone_gear_shaft_spec.SECTION_DIA_BANDS[0]
    clearances = (
        spec.BORE_DIA + lower - (shaft_nominal + shaft_upper),
        spec.BORE_DIA + upper - (shaft_nominal + shaft_lower),
    )
    assert tuple(round(value, 3) for value in clearances) == expected


def test_crank_bore_is_an_h7_bushing_seat_with_webs_over_the_floor() -> None:
    """#906 R1: Ø14.6 H7, on the post's symmetry plane, for MHA-149.

    The web numbers are the print-worst table; each is an import-time assert
    in the spec against the 1.5 floor, so this pins the table itself.  R1
    holds the 2.0 target on every web.  The cone axis's own ±0.25 band
    (JOURNAL_AXIS_HEIGHT_TOLERANCE_MM, the shim pack's range) sets how high
    the crank axis can print, so the webs above it read against that band,
    not the ±0.51 .XX grade it replaced.
    """
    assert spec.CRANK_BORE_DIA == 14.6
    assert spec.CRANK_BORE_OFFSET == 0.0
    assert spec.CRANK_BORE_BAND == (0.018, 0.0)
    assert spec.WEB_FLOOR_MM == 1.5
    assert {
        name: round(web, 2) for name, web in spec.CRANK_BORE_WEBS_WORST.items()
    } == {
        "mounting thru hole": 2.0,
        "mounting counterbore": 2.24,
        "top face": 4.78,
        "crank boss OD": 3.26,
    }
    assert min(spec.CRANK_BORE_WEBS_WORST.values()) >= 2.0
    assert "MHA-149" in spec.DRAWING_NOTES.splitlines()[0]


def test_nothing_else_on_the_casting_carries_a_band() -> None:
    """Each band named once, applied to the features whose fit needs it.

    The cast body, collar and boss diameters and the mounting-hole stations
    are not accuracy features (cad/docs/tolerance-policy.md, "Result"), so the
    part must not author a tolerance on them at all: the title block's general
    grade is the whole specification.
    """
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_bilateral_tolerance(") == 3
    assert source.count("set_dimension_symmetric_tolerance(") == 1
    assert source.count("deviations(RUNNING_BORE_BAND)") == 1
    assert source.count("deviations(CRANK_BORE_BAND)") == 1
    assert source.count("deviations(CRANK_ABOVE_CONE_BAND)") == 1
    assert not hasattr(spec, "TURNED_DIAMETER_TOLERANCE_MM")
    assert not hasattr(spec, "CRANK_BORE_TOLERANCE_MM")


def test_the_cone_axis_height_carries_the_shim_packs_band() -> None:
    """The post sets the cone shaft's height and MHA-141's shim pack takes up
    what it leaves; the pack's range holds 0.25 for the post.  The .XX grade
    (+/-0.51) overruns that, so the height carries its own band -- the
    loosest the pack allows -- on the model dimension, where the sheet
    imports it, and nowhere as a literal or a frame."""
    assert spec.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM == 0.25
    # The title block's general grades by places: .X, .XX, .XXX.
    general = {1: 0.8, 2: 0.51, 3: 0.13}
    assert spec.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM < general[
        spec.DRAWING_PRECISION_BY_NAME["JournalAxisY"]
    ]
    assert spec.GEOMETRIC_TOLERANCES_MM == {}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert re.search(
        r'set_dimension_symmetric_tolerance\(\s*adapter,\s*"ConeBossProfile",'
        r'\s*"JournalAxisY",\s*JOURNAL_AXIS_HEIGHT_TOLERANCE_MM,?\s*\)',
        source,
    )


def test_the_plan_angle_is_model_geometry_not_sheet_text() -> None:
    """The 12.5182 deg plan incline is a DRIVING model dimension.

    A driven reference angle cannot express it: SOLIDWORKS returns the
    obtuse member of a line pair whatever the ray directions, the selection
    order or the text position.  A driving dimension fixes the quadrant when
    the sketch is authored, and driving it from the same ``ConeIncline``
    global that builds ConeShaftNormal is what stops the printed value and
    the built geometry from drifting apart.
    """
    assert spec.DRAWING_DIMENSIONS["JournalPlanReference"] == {"InclineAngle"}
    # The station has its own sketch: a view dimensioning only it must not
    # print the plan-angle rays (MHA-016 sheet 2).
    assert spec.DRAWING_DIMENSIONS["SpotFaceStationReference"] == {"CrankBossStartZ"}
    assert spec.CRANK_BOSS_NEAR_Z == spec.CRANK_BOSS_NORTH_FACE
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
    assert keys == {"foot_seat", "crank_bore", "journal_bore", "cone_boss_north_face"}
    assert (
        surface_finish_by_key(spec.SURFACE_FINISHES, "foot_seat").roughness_um
        == SEAT_UM
    )
    # #906 A2: the crank bore seats the bushing; only the cone journal runs.
    assert (
        surface_finish_by_key(spec.SURFACE_FINISHES, "crank_bore").roughness_um
        == SEAT_UM
    )
    assert (
        surface_finish_by_key(spec.SURFACE_FINISHES, "journal_bore").roughness_um
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
    # The zone spans the boss, so the spot face's retreat (a shorter boss)
    # loosens the angle it holds: 0.0795 deg over 72.03, 0.0824 over 69.53.
    assert round(spec.CRANK_BORE_ANGLE_LIMIT_DEG, 4) == 0.0824
    assert part.PART_DATUMS is spec.PART_DATUMS
    assert part.GEOMETRIC_CONTROLS is spec.GEOMETRIC_CONTROLS
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert "**crank mesh** — MHA-016's crank bore" in policy
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


def test_journal_rims_print_the_thrust_ring_break() -> None:
    """Codex P1 on #916 (PRRT_kwDOPHDy386mTQ-u): the collar's thrust ring is
    bounded by the collar OD edge AND the post's journal rim, so the rim
    prints the same derived break; the title block's 0.25 would leave the
    worst-case ring under its 1.5 floor."""
    import _config
    import cone_gear_shaft_spec as shaft

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


def test_collar_diameter_lives_on_its_plan_circle() -> None:
    """The front-view crank-bore leaders must not cross a collar dimension line."""
    assert "HeadDia" in drawing.TOP_KEEP
    assert "HeadDia" not in drawing.FRONT_KEEP
    # Names the feature, not a process: the part may be turned from bar stock.
    assert drawing.DIMENSION_CALLOUTS["HeadDia"] == "COLLAR"


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
    from cone_pivot_post_installation import POST_ROTATION_Y_DEG

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
    """#906: the plan angle feeds the crank bore's angularity frame (rule 4),
    so it is boxed BASIC and prints the model's 12.5182 exactly."""
    assert spec.BASIC_DIMENSIONS == frozenset({"InclineAngle"})
    assert spec.DRAWING_PRECISION_BY_NAME["InclineAngle"] == 4
    assert round(spec.INCLINE_DEG, 4) == spec.INCLINE_DEG


def test_section_reads_by_its_bore_axis_not_by_a_note() -> None:
    assert "SECTION A-A" not in spec.DRAWING_NOTES
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_add_cone_section_centerline(adapter, section)" in source


def test_spotface_station_prints_its_value_on_its_own_dimension_line() -> None:
    """Labelled, stacked, no shelf.  On sheet 1 the station's text was once
    offset to a distant shelf, where a blind reader took it for a note, so it
    never leaves its own dimension line.  The "no label" half is Main's
    rim-8339 station-label ruling's to change: a bare 18.88 was not found as
    the station, so on sheet 2 the label stacks with the value in the
    dimension's own text, like the width and run-out beside it.  It stands
    once, on sheet 2's plan, not on sheet 1's."""
    assert "CrankBossStartZ" not in drawing.DIMENSION_CALLOUTS
    assert drawing.SPOT_FACE_CALLOUTS["CrankBossStartZ"] == "SPOT FACE STATION"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(adapter, annotations, SPOT_FACE_CALLOUTS)\n" in source
    assert "CrankBossStartZ" not in drawing.TOP_KEEP
    assert drawing.SPOT_PLAN_DIMENSION == "CrankBossStartZ"
    assert '{"CrankBossStartZ":' not in source
    assert "offset_dimension_text(adapter, plan_annotations" not in source


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
    assert 'station.record("CrankBossStartZ", \'"CrankBossNearZ"\')' in source
    # Saved hidden (no new #880 visibility debt); the drawing shows it per view.
    assert 'blank_reference_sketches(adapter, ("SpotFaceStationReference",))' in source


def test_crank_bore_is_located_from_the_cone_bore_inside_the_mesh_window() -> None:
    """U31: the 16T:64T mesh closes on the bore spacing, so the print states it.

    #906 R1: the MHA-149 bushing takes up the mesh at fit-up, and
    crank_mesh_stack carries the printed spacing band as one of its terms,
    placed CRANK_BORE_DROP below the frame; its import-time assert is the
    window check.
    """
    import crank_mesh_stack

    assert round(spec.CRANK_ABOVE_CONE, 3) == 39.122
    assert spec.CRANK_ABOVE_CONE_BAND == (0.37, 0.0)
    assert crank_mesh_stack.SPACING_PRINTED == round(spec.CRANK_ABOVE_CONE, 2)
    assert abs(crank_mesh_stack.FRAME_DY - spec.CRANK_ABOVE_CONE - spec.CRANK_BORE_DROP) < 1e-9
    assert min(crank_mesh_stack.OPEN_MARGIN, crank_mesh_stack.CLOSE_MARGIN) > 0.0
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


def _datum_b_frame_clears_the_notes(tag_y: float) -> bool:
    frame_bottom = tag_y - drawing._DATUM_TAG_FRAME_HEIGHT
    return frame_bottom >= drawing.NOTES_ANCHOR[1] + drawing._DATUM_NOTES_CLEARANCE - 1e-12


def _journal_axis_text_clears_the_spacing_line(text_x: float) -> bool:
    right = text_x + drawing._JOURNAL_AXIS_TEXT_RIGHT
    line_x = drawing.JOURNAL_KEEP["CrankAboveCone"][0]
    return right <= line_x - drawing._TEXT_LINE_CLEARANCE + 1e-12


def test_datum_b_and_the_33_37_text_clear_what_crossed_them() -> None:
    """Leaf w3-1026 (layout check with #1026's degenerate-line fix): datum B's
    frame sat on the manufacturing notes, and the crank spacing's extension
    line at x 208.0 crossed the 33.37 text.  Both placements now derive from
    the measured extents; the old ones are the positive control."""
    assert not _datum_b_frame_clears_the_notes(drawing._front_y(-9.0))
    assert _datum_b_frame_clears_the_notes(drawing.DATUM_B_TAG_XY[1])
    # Still below the foot seat it tags.
    assert drawing.DATUM_B_TAG_XY[1] < drawing._front_y(0.0)
    assert not _journal_axis_text_clears_the_spacing_line(0.190)
    assert _journal_axis_text_clears_the_spacing_line(
        drawing.JOURNAL_TEXT_OFFSETS["JournalAxisY"][0]
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "JOURNAL_TEXT_OFFSETS,\n" in source
    assert "position=DATUM_B_TAG_XY," in source
    assert '"Manufacturing Notes", *NOTES_ANCHOR)' in source
