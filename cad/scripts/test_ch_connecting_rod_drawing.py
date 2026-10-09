"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import ch_connecting_rod_notes
import ch_connecting_rod_spec
import draw_ch_connecting_rod as drawing
import build_ch_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["ch_connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is ch_connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_connecting_rod_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.LEFT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.FORK_TOP_Y) == (
        ch_connecting_rod_spec.CENTER_DISTANCE,
        ch_connecting_rod_spec.FORK_TOP_Y,
    )
    assert drawing._BBOX_CY == pytest.approx(
        (ch_connecting_rod_spec.RING_BOTTOM_Y + ch_connecting_rod_spec.FORK_TOP_Y) / 2.0
    )
    assert ch_connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert ch_connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
    assert ch_connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert ch_connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert ch_connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert ch_connecting_rod_spec.FORK_WIDTH == rod.FORK_WIDTH
    assert ch_connecting_rod_spec.FORK_THICKNESS == rod.FORK_THICKNESS
    assert ch_connecting_rod_spec.FORK_SLOT_WIDTH == rod.FORK_SLOT_WIDTH
    assert ch_connecting_rod_spec.FORK_BASE_Y == rod.FORK_BASE_Y
    assert ch_connecting_rod_spec.FORK_CROTCH_Y == rod.FORK_CROTCH_Y


def test_fork_reference_lengths_run_from_the_crown_top() -> None:
    # The side view prints the slot depth and the boss length from the tine
    # tops: crown radius (= half the fork width, on the pin) plus the spec's
    # below-pin spans.
    spec = ch_connecting_rod_spec
    assert spec.FORK_CROWN_RADIUS == spec.FORK_WIDTH / 2.0
    assert rod.SLOT_DEPTH == pytest.approx(spec.FORK_CROWN_RADIUS + spec.FORK_CROTCH_BELOW_PIN)
    assert rod.FORK_BOSS_LENGTH == pytest.approx(
        spec.FORK_CROWN_RADIUS + spec.FORK_BASE_BELOW_PIN
    )
    assert rod.SLOT_DEPTH == pytest.approx(14.75)
    assert rod.FORK_BOSS_LENGTH == pytest.approx(18.0)
    # The slot floor stands above the root step, so the bridge is solid.
    assert spec.FORK_BASE_Y < spec.FORK_CROTCH_Y < spec.CENTER_DISTANCE
    # Every drive in the slot sketch evaluates to its built value.
    source = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert "slot_sd.record(\"SlotDepth\",'\"ForkWidth\"/2+\"ForkCrotchBelowPin\"')" in source
    assert (
        "slot_sd.record(\"ForkBossLength\",'\"ForkWidth\"/2+\"ForkBaseBelowPin\"')"
        in source
    )


def test_analytic_volumes_follow_the_fork_geometry() -> None:
    spec = ch_connecting_rod_spec
    hole = spec.PIN_HOLE_DIA
    crown = math.pi * spec.FORK_CROWN_RADIUS**2 / 2.0
    fork_area = spec.FORK_WIDTH * spec.FORK_BASE_BELOW_PIN + crown
    assert rod.fork_outline_area(spec.FORK_BASE_Y) == pytest.approx(fork_area)
    slot_area = spec.FORK_WIDTH * spec.FORK_CROTCH_BELOW_PIN + crown
    assert rod.slot_volume() == pytest.approx(slot_area * spec.FORK_SLOT_WIDTH)
    # The reamed hole crosses the slot: it cuts only the two tines.
    assert rod.pin_hole_volume() == pytest.approx(
        math.pi * (hole / 2.0) ** 2 * 2.0 * spec.FORK_TINE_THICKNESS
    )
    assert rod.finished_volume() == pytest.approx(
        rod.boss_volume()
        - rod.slot_volume()
        - rod.strap_bore_volume()
        - rod.pin_hole_volume()
    )
    assert 0.0 < rod.finished_volume() < rod.boss_volume()


def test_pin_hole_is_the_reamed_press_hole_for_the_rod_pivot_pin() -> None:
    """User ruling 2026-10-09 (PR #1292 review F1): the MHA-CH-010 pin is
    pressed into both tines as the bar pin is into the amplitude bar
    (ch_rod_pivot_pin_spec holds the fit), so the hole is reamed to a band of
    its own, native on PinHoleDia, not a #47 drill."""
    import _config

    spec = ch_connecting_rod_spec
    assert rod.PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    assert rod.PIN_HOLE_BAND is spec.PIN_HOLE_BAND
    assert drawing._PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    assert spec.PIN_HOLE_DIA == 1.968
    assert spec.PIN_HOLE_BAND == (0.010, 0.0)
    assert not hasattr(spec, "PIN_HOLE_SPEC")
    assert model_toleranced_dimensions(rod)[("PinHoleProfile", "PinHoleDia")] == (
        "*deviations(PIN_HOLE_BAND)"
    )
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'set_global(adapter,"PinHoleDia",f"{PIN_HOLE_DIA}mm")' in build
    assert 'names=(None,"PinHoleY","PinHoleDia")' in build
    assert "drives=(None,'\"CenterDistance\"','\"PinHoleDia\"')" in build
    assert 'name_last_feature(adapter,"PinHoleProfile")' in build
    assert 'name_last_feature(adapter,"PinHole")' in build
    assert (
        ch_connecting_rod_notes.PIN_NUMBER
        == _config.parts("ch-rod-pivot-pin")["number"]
    )


def test_the_pin_bears_on_the_whole_tine() -> None:
    """PR #1292 review F1 regression: a 90-degree Ø3.2 countersink sunk into
    each tine for a peened end left 0.92 of land under the pin, under rule
    12's 1.5 floor, while the budget only checked the tine. Built
    independently of the joint budget: the build removes nothing at the pin
    but one straight cylinder through both tines (no chamfer, no second cut
    sunk into a tine face), so the pin's land in each tine is the thinnest
    tine the fork and slot bands leave."""
    spec = ch_connecting_rod_spec
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "add_chamfer(" not in source
    assert "wizard_holes(" not in source
    assert source.count("create_cut_extrude(") == 3  # slot, strap bore, pin hole
    assert not [name for name in dir(rod) if "countersink" in name.lower()]
    assert not [name for name in dir(spec) if "CSK" in name]
    thinnest_tine = (
        spec.FORK_THICKNESS
        + spec.FORK_THICKNESS_BAND[1]
        - (spec.FORK_SLOT_WIDTH + spec.FORK_SLOT_BAND[0])
    ) / 2.0 - spec.FORK_TINE_MATCH / 2.0
    assert thinnest_tine == pytest.approx(1.5865)
    assert thinnest_tine >= 1.5  # drawing-simplicity rule 12 floor
    # Positive control: the countersink this replaced fails the same check.
    old_csk_depth = (3.2 + 0.127 - 1.994) / 2.0  # 90-degree: depth = radial step
    assert thinnest_tine - old_csk_depth < 1.5


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source  # the isometric override
    # The left view stands level with the front (third-angle alignment) so the
    # fork's thickness and slot dimensions fit above its crown.
    assert drawing.LEFT_CENTER == (0.080, drawing.FRONT_CENTER[1])
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in source
    # The notes column clears the left view and the front view's pin
    # annotations; the left view's fork dimensions stay inside the top border.
    assert drawing.NOTES_XY[0] > drawing.FRONT_KEEP["ForkWidthDim"][0] + 0.05
    assert max(y for _, y in drawing.LEFT_KEEP.values()) < 0.260
    assert ch_connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_not_title_block_duplicates() -> None:
    notes = ch_connecting_rod_notes.DRAWING_NOTES
    # The reamed pin hole prints from its native PinHoleDia dimension, the
    # bore rides its imported model tolerance and the fork its 3-place model
    # bands; notes never repeat a sheet dimension.
    assert "#47" not in notes
    assert "3.00" not in notes and "2.50" not in notes
    assert "0.10 MIN CLR/SIDE" in notes
    assert "RING WALL 4.50 MIN AFTER BORING" in notes
    assert "SLOT CENTRED; TINES EQUAL WITHIN 0.10" in notes
    assert f"{ch_connecting_rod_spec.FORK_TINE_MATCH:.2f}" in notes
    # The press fit (user ruling 2026-10-09, PR #1292 review F1) names its
    # pin; the hole's size and band are the model's PinHoleDia (rules 2 and 6,
    # PR #1292 review N1), so no limit of it may ride the note text.
    assert "5. PRESS FIT PIN MHA-CH-010 INTO THE" in notes
    assert "   REAMED PIN HOLE, BOTH TINES." in notes
    for limit in (
        f"{ch_connecting_rod_spec.PIN_HOLE_DIA:.3f}",
        f"{ch_connecting_rod_spec.PIN_HOLE_DIA:.2f}",
        f"+{ch_connecting_rod_spec.PIN_HOLE_BAND[0]:.3f}",
        "\u00d8",
        "REAM THRU",
    ):
        assert limit not in notes, limit
    assert "PEEN" not in notes and "CSK" not in notes and "#746" not in notes
    assert "HEAD" not in notes
    assert "DRAFT" not in notes  # machined from plate, not cast
    assert "HANGS PLUMB" not in notes  # not an inspectable requirement
    assert "SHANK C/L" not in notes  # the 4.00 BASIC from datum B owns it
    assert "Ra " not in notes  # the title-block surface row is never restated
    assert "147.67" not in notes  # the BASIC sheet dimension owns it
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    # Material and finish are title-block rows (simplicity policy rule 1).
    for title_block_word in ("1018", "STEEL", "IRON", "BLACK", "ENAMEL"):
        assert title_block_word not in notes
    for fork_dimension in (
        ch_connecting_rod_spec.FORK_THICKNESS,
        ch_connecting_rod_spec.FORK_SLOT_WIDTH,
    ):
        assert f"{fork_dimension:.2f}" not in notes
    assert max(len(line) for line in notes.splitlines()) <= 40
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = strap bore axis, B = shank left flank (clocking); the pin-hole
    # position frame references both and the bore imports its model-owned fit.
    assert source.count("add_datum_feature(") == 2
    assert 'label="strap bore axis",' in source
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B")' in source
    assert 'characteristic="position"' in source
    assert '"StrapBoreDia": "BORE"' in source
    assert "+0.10/0" not in source
    assert "add_surface_finish(" in source
    # The reamed hole prints its native Ø and band with descriptive text, not
    # a Hole Wizard callout; the position FCF anchors the hole's 3-o'clock rim.
    assert "add_native_hole_callout(" not in source
    assert source.count("edge_xy=pin_fcf_rim") == 1
    assert "SetText(4" not in source
    assert not hasattr(ch_connecting_rod_notes, "PIN_CSK_CALLOUT")


def test_datum_b_leader_clears_the_shank_width_text() -> None:
    """Datum B's leader runs level at the tag's height (the edge attachment
    re-solves square to the vertical flank). Farm audit at 71a6e3107: with the
    tag 10 mm under the pick, the fork-raised bbox centre put that leader at
    y 151.1 mm, 0.37 mm through the 8.00 text [148.2..151.7]."""
    keep_y = drawing.FRONT_KEEP["ShankWidthDim"][1]
    text_top = keep_y + 0.0017  # measured: 3.5 mm text on the y-0.150 keep
    leader_y = drawing.DATUM_B_SYMBOL[1]
    assert leader_y - text_top >= 0.0025
    # The leader meets the shank's left flank, between the ring and the fork.
    flank_x, _ = drawing._sheet_xy(-ch_connecting_rod_spec.SHANK_WIDTH / 2.0, 0.0)
    assert drawing.DATUM_B_EDGE[0] == pytest.approx(flank_x)
    ring_top = drawing._sheet_xy(0.0, ch_connecting_rod_spec.RING_OUTER_RADIUS)[1]
    fork_root = drawing._sheet_xy(0.0, ch_connecting_rod_spec.FORK_BASE_Y)[1]
    assert ring_top < leader_y < fork_root


def test_ring_and_shank_note_is_the_spec_s_plate() -> None:
    """PR #1292 review F4: note 2 prints the one plate thickness and its
    symmetry zone from the spec, so a spec edit can never leave the print
    stating the old plate (#948 ruling R: 2.200 at three places, the title
    block's linear_3pl band, which the spec's band restates)."""
    import _config

    spec = ch_connecting_rod_spec
    lines = ch_connecting_rod_notes.DRAWING_NOTES.splitlines()
    assert lines[2] == f"2. RING AND SHANK {spec.RING_THICKNESS:.3f} THICK;"
    assert lines[3] == f"   SYMMETRIC TO SLOT WITHIN {spec.RING_SLOT_SYMMETRY:.2f}."
    assert spec.SHANK_THICKNESS == spec.RING_THICKNESS
    assert spec.SHANK_THICKNESS_BAND == spec.RING_THICKNESS_BAND
    linear_3pl = _config.title_block("linear_3pl")["value_in"] * 25.4
    assert spec.RING_THICKNESS_BAND == pytest.approx((linear_3pl, -linear_3pl))


def test_fork_print_is_three_place_and_model_owned() -> None:
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert marked["ForkBoss"] == {"ForkThick"}
    assert marked["ForkSlotProfile"] == {"SlotWidth", "SlotDepth", "ForkBossLength"}
    assert marked["ForkProfile"] == {"ForkWidthDim"}
    assert rod.DRAWING_PRECISION is ch_connecting_rod_notes.DRAWING_PRECISION
    assert ch_connecting_rod_notes.DRAWING_PRECISION == {
        "ForkBoss": {"ForkThick": 3},
        "ForkSlotProfile": {"SlotWidth": 3},
        "PinHoleProfile": {"PinHoleDia": 3},
    }
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'name_dimensions(adapter,"ForkBoss",["ForkThick"])' in build
    assert "fork_lower,fork_upper=deviations(FORK_THICKNESS_BAND)" in build
    assert "(fork_thickness_dim[0],'\"ForkThickness\"')" in build
    assert "apply_drawing_precision(adapter,DRAWING_PRECISION)" in build


def test_reamed_pin_hole_is_a_native_three_place_dimension() -> None:
    """PR #1292 review N1 (policy rules 2 and 6): the press hole's Ø1.968
    +0.010/0 is the PinHoleDia model dimension -- marked, authored at three
    places with its native band -- imported into the front view with the
    process beneath it, never general-note text."""
    spec = ch_connecting_rod_spec
    assert ch_connecting_rod_notes.DRAWING_DIMENSIONS["PinHoleProfile"] == {
        "PinHoleDia"
    }
    assert ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"] == {
        "PinHoleDia": 3
    }
    # The band is written at three places, as the precision prints it.
    assert all(round(d, 3) == d for d in spec.PIN_HOLE_BAND)
    assert model_toleranced_dimensions(rod)[("PinHoleProfile", "PinHoleDia")] == (
        "*deviations(PIN_HOLE_BAND)"
    )
    assert "PinHoleDia" in drawing.FRONT_KEEP
    assert drawing.FRONT_CALLOUTS["PinHoleDia"] == "THRU - REAM"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)" in source
    )
    assert (
        "assert_imported_precision(\n"
        '        adapter, front_annotations, DRAWING_PRECISION["PinHoleProfile"]\n'
        "    )" in source
    )
    # The Ø text stands up and right of the fork, clear of the FCF frame below
    # it and the notes column.
    hole_x, hole_y = drawing._sheet_xy(0.0, spec.CENTER_DISTANCE)
    text_x, text_y = drawing.FRONT_KEEP["PinHoleDia"]
    assert text_x > hole_x + 0.040 and text_y > hole_y + 0.010
    assert text_y > drawing.NOTES_XY[1] + 0.040
    assert text_y < 0.267


def test_reamed_pin_hole_band_prints_at_the_value_s_places(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Farm render of 1b1f2f7fd printed "Ø1.968 +0.01/0.00": the shared
    setter prints a band at the fewest places that hold it (two, for 0.010),
    under a value authored at three.  The part build re-sets PinHoleDia's
    tolerance places from the same DRAWING_PRECISION entry as its value's,
    after both the band and the value places are authored."""
    import _drawing_marks
    import inspect

    from _fit_limits import deviations

    spec = ch_connecting_rod_spec
    value_places = ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"][
        "PinHoleDia"
    ]
    # The defect: left to the shared setter the band reads +0.01/0.00.
    assert _drawing_marks._tolerance_places(*deviations(spec.PIN_HOLE_BAND)) == 2
    assert value_places == 3

    calls: list[tuple[int, int, int, int]] = []

    class Display:
        tolerance_places = 2

        def SetPrecision3(
            self, primary: int, dual: int, primary_tol: int, dual_tol: int
        ) -> int:
            calls.append((primary, dual, primary_tol, dual_tol))
            self.tolerance_places = primary_tol
            return 0

        def GetPrimaryTolPrecision2(self) -> int:
            return self.tolerance_places

    display = Display()
    looked_up: list[tuple[str, str]] = []

    def named_dimension(_adapter, feature: str, name: str):
        looked_up.append((feature, name))
        return display, None

    monkeypatch.setattr(rod, "_named_dimension", named_dimension)
    monkeypatch.setattr(rod, "_early_bound", lambda value, _type: value)
    places = rod.tolerance_at_dimension_places(object(), "PinHoleProfile", "PinHoleDia")
    assert looked_up == [("PinHoleProfile", "PinHoleDia")]
    # Primary (value) places untouched; the tolerance takes the value's places.
    assert calls == [(-1, -1, value_places, -1)]
    assert places == display.tolerance_places == value_places

    build = inspect.getsource(rod.build)
    band = build.index('"PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_BAND)')
    value = build.index("apply_drawing_precision(adapter, DRAWING_PRECISION)")
    tolerance = build.index(
        'tolerance_at_dimension_places(adapter, "PinHoleProfile", "PinHoleDia")'
    )
    assert band < tolerance and value < tolerance


def test_side_view_fork_dimensions_stand_clear_of_each_other() -> None:
    """Farm render of 1b1f2f7fd: centred over the slot, the 2.625's stacked
    +0.127/0.000 touched the 6.075's dimension line and arrows, and the
    6.075's extension line and the 14.75's top arrow tail ran through its
    0.000; the 14.75 and 18.00 values stood 1 mm apart.  Model each side-view
    text frame, line and tail from the measured ink and require air between
    every text and any other dimension's ink."""
    d = drawing
    spec = ch_connecting_rod_spec
    gap = d.SIDE_TEXT_CLEARANCE_MM
    arrow = d.ARROW_HALF_WIDTH_MM
    # Measured on the same render: extension lines run ~1.1 mm past their
    # dimension line; text is 3.4 mm tall.
    overshoot, half_text = 1.1, 1.7

    def mm(name: str) -> tuple[float, float]:
        x, y = d.LEFT_KEEP[name]
        return x * 1000.0, y * 1000.0

    cx = d.LEFT_CENTER[0] * 1000.0
    top = d._left_xy(0.0, spec.FORK_TOP_Y)[1] * 1000.0
    crotch = d._left_xy(0.0, spec.FORK_CROTCH_Y)[1] * 1000.0
    base = d._left_xy(0.0, spec.FORK_BASE_Y)[1] * 1000.0
    fork = spec.FORK_THICKNESS / 2.0
    slot = spec.FORK_SLOT_WIDTH / 2.0
    reach = d.DIM_ARROW_REACH_MM

    sx, sy = mm("SlotWidth")
    s_line = sy - d.SLOT_WIDTH_LINE_DROP_MM
    tx, ty = mm("ForkThick")
    t_line = ty - d.FORK_THICK_LINE_DROP_MM
    dx, dy = mm("SlotDepth")
    bx, by = mm("ForkBossLength")
    vertical = d.VERTICAL_TEXT_HALF_WIDTH_MM

    Box = tuple[float, float, float, float]  # x0, y0, x1, y1 (mm)
    ink: dict[str, dict[str, Box]] = {
        "SlotWidth": {
            "text": (
                sx - d.SLOT_WIDTH_TEXT_HALF_WIDTH_MM,
                s_line,
                sx + d.SLOT_WIDTH_TEXT_HALF_WIDTH_MM,
                sy + d.SLOT_WIDTH_TEXT_RISE_MM,
            ),
            # Run out under its text on the left, the right tail outside.
            "line": (
                sx - d.SLOT_WIDTH_TEXT_HALF_WIDTH_MM,
                s_line - arrow,
                cx + slot + reach,
                s_line + arrow,
            ),
            "left ext": (cx - slot, top, cx - slot, s_line + overshoot),
            "right ext": (cx + slot, top, cx + slot, s_line + overshoot),
        },
        "ForkThick": {
            "text": (
                tx - d.FORK_THICK_TEXT_HALF_WIDTH_MM,
                ty - half_text,
                tx + d.FORK_THICK_TEXT_HALF_WIDTH_MM,
                ty + half_text,
            ),
            "line": (
                cx - fork - reach,
                t_line - arrow,
                cx + fork + reach,
                t_line + arrow,
            ),
            "left ext": (cx - fork, top, cx - fork, t_line + overshoot),
            "right ext": (cx + fork, top, cx + fork, t_line + overshoot),
        },
        "SlotDepth": {
            "text": (dx - vertical, dy - half_text, dx + vertical, dy + half_text),
            "top tail": (dx - arrow, top, dx + arrow, top + reach),
            "bottom tail": (dx - arrow, crotch - reach, dx + arrow, crotch),
            "top ext": (cx + fork, top, dx + overshoot, top),
            "bottom ext": (cx + slot, crotch, dx + overshoot, crotch),
        },
        "ForkBossLength": {
            "text": (bx - vertical, by - half_text, bx + vertical, by + half_text),
            "top tail": (bx - arrow, top, bx + arrow, top + reach),
            "bottom tail": (bx - arrow, base - reach, bx + arrow, base),
            "top ext": (cx + fork, top, bx + overshoot, top),
            "bottom ext": (cx + fork, base, bx + overshoot, base),
        },
    }

    def air(a: Box, b: Box) -> float:
        return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])

    for owner, items in ink.items():
        text = items["text"]
        for other, other_items in ink.items():
            if other == owner:
                continue
            for part, box in other_items.items():
                assert air(text, box) >= gap - 1e-9, (owner, other, part)
    # The slot's text stands left of the fork, its line just above the tines.
    assert ink["SlotWidth"]["text"][2] < cx - fork
    assert 1.0 <= s_line - top


def test_model_bands_are_owned_by_named_model_dimensions() -> None:
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert ch_connecting_rod_spec.FORK_THICKNESS_BAND == (0.05, -0.05)
    assert ch_connecting_rod_spec.FORK_SLOT_BAND == (0.127, 0.0)
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)",
        ("ForkBoss", "ForkThick"): "fork_upper",
        ("ForkSlotProfile", "SlotWidth"): "*deviations(FORK_SLOT_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }


def test_bore_finish_is_routed_clear_of_the_lower_dimension_stack() -> None:
    edge_x, edge_y = drawing.BORE_FINISH_EDGE
    symbol_x, symbol_y = drawing.BORE_FINISH_SYMBOL
    assert symbol_x > edge_x
    assert symbol_y > edge_y
    assert symbol_y > drawing.FRONT_KEEP["StrapBoreDia"][1] + 0.010
    assert symbol_x < 0.250


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-connecting-rod")
    # Main ruling 2026-10: machined from 1018 plate, black finish.
    assert spec["material"] == rod.MATERIAL == "Plain Carbon Steel"
    assert spec["material_specification"] == "AISI 1018 low-carbon steel plate"
    assert spec["finish"] == (
        "BLACK ENAMEL; MASK STRAP BORE, PIN HOLE AND FORK SLOT; "
        "OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 20
