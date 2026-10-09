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
from _hole_spec import blind_cut_dia_mm


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
    drill = blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert rod.PIN_DRILL_DIA == drill
    # A 90-degree countersink is an equal-leg chamfer from the drill to its
    # diameter, and it must stay inside the tine.
    assert rod.PIN_CSK_LEG == pytest.approx((spec.PIN_HOLE_CSK_DIA - drill) / 2.0)
    assert 0.0 < rod.PIN_CSK_LEG < spec.FORK_TINE_THICKNESS
    crown = math.pi * spec.FORK_CROWN_RADIUS**2 / 2.0
    fork_area = spec.FORK_WIDTH * spec.FORK_BASE_BELOW_PIN + crown
    assert rod.fork_outline_area(spec.FORK_BASE_Y) == pytest.approx(fork_area)
    slot_area = spec.FORK_WIDTH * spec.FORK_CROTCH_BELOW_PIN + crown
    assert rod.slot_volume() == pytest.approx(slot_area * spec.FORK_SLOT_WIDTH)
    # The drill crosses the slot: it cuts only the two tines.
    assert rod.pin_hole_volume() == pytest.approx(
        math.pi * (drill / 2.0) ** 2 * 2.0 * spec.FORK_TINE_THICKNESS
    )
    assert rod.finished_volume() == pytest.approx(
        rod.boss_volume()
        - rod.slot_volume()
        - rod.strap_bore_volume()
        - rod.pin_hole_volume()
        - rod.pin_countersink_volume()
    )
    assert 0.0 < rod.finished_volume() < rod.boss_volume()


def test_pin_hole_is_part_owned_and_drawing_geometry_is_derived() -> None:
    assert rod.PIN_HOLE_SPEC is ch_connecting_rod_spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is ch_connecting_rod_spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(ch_connecting_rod_spec.PIN_HOLE_SPEC)
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "HoleSpec(" not in source
    assert "\n        PIN_HOLE_SPEC," in source
    assert "expect_dia_mm=blind_cut_dia_mm(PIN_HOLE_SPEC)" in source


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
    # The pin hole rides its native Ø1.99 THRU ALL callout, its countersink Ø
    # imports from the model, the bore its imported model tolerance and the
    # fork its 3-place model bands; notes never repeat a sheet dimension.
    assert "#47" not in notes
    # #948 ruling R: one 2.200 plate at three places (title block linear_3pl).
    assert "2. RING AND SHANK 2.200 THICK;" in notes
    assert "SYMMETRIC TO SLOT WITHIN 0.10." in notes
    assert "3.00" not in notes and "2.50" not in notes
    assert "0.10 MIN CLR/SIDE" in notes
    assert "RING WALL 4.50 MIN AFTER BORING" in notes
    assert "SLOT CENTRED; TINES EQUAL WITHIN 0.10" in notes
    assert f"{ch_connecting_rod_spec.FORK_TINE_MATCH:.2f}" in notes
    # Peening is a reconstruction choice (issue #746), and the notes say so.
    assert "PEEN PIN MHA-CH-010 INTO BOTH CSKS" in notes
    assert "RECONSTRUCTION CHOICE #746" in notes
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
        ch_connecting_rod_spec.PIN_HOLE_CSK_DIA,
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
    assert "add_native_hole_callout(" in source
    # The callout takes the drill's own circle (a rim pick lands next to the
    # countersink's chamfer edge); the position FCF anchors the 3-o'clock rim.
    assert "edge=visible_circle_edge(adapter, front, _PIN_HOLE_DIA)" in source
    assert source.count("edge_xy=pin_fcf_rim") == 1
    # The countersink Ø is a model dimension with its band, never typed text.
    assert "_add_countersink_line" not in source
    assert "SetText(4" not in source
    assert not hasattr(ch_connecting_rod_notes, "PIN_CSK_QUALIFIER")


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


def test_countersink_diameter_is_model_owned() -> None:
    """The Ø3.200 +/-0.127 countersink prints from a blanked reference sketch
    whose dimension and the chamfer's unprinted leg share one knob."""
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert marked["CountersinkReference"] == {"PinCskDia"}
    assert ch_connecting_rod_notes.DRAWING_PRECISION["CountersinkReference"] == {
        "PinCskDia": 3
    }
    assert "PinCskDia" in drawing.FRONT_KEEP
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'set_global(adapter,"PinCskDia",f"{PIN_HOLE_CSK_DIA}mm")' in build
    assert 'name_dimensions(adapter,"PinCountersinks",["PinCskLeg"])' in build
    # The leg runs from the drill the wizard cut, so the rim lands on PinCskDia
    # exactly (test_ch_rod_pivot_fit: the installed pin's flare fills it).
    assert 'drill_cut=f"{pin_cut.hole_dia_mm:.9g}"' in build
    assert "(csk_leg_dim[0],f'(\"PinCskDia\"-{drill_cut}mm)/2')" in build
    assert "(PIN_HOLE_CSK_DIA-float(drill_cut))/2.0," in build
    assert 'names=(None,"PinCskRefY","PinCskDia")' in build
    assert 'blank_reference_sketches(adapter,("CountersinkReference",))' in build
    # The chamfer leg's drive evaluates to the leg the build cuts.
    assert rod.PIN_CSK_LEG == pytest.approx(
        (ch_connecting_rod_spec.PIN_HOLE_CSK_DIA - rod.PIN_DRILL_DIA) / 2.0
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions(" in source
    assert '"PinCskDia": PIN_CSK_CALLOUT' in source
    assert ch_connecting_rod_notes.PIN_CSK_CALLOUT == "90\u00b0 CSK BOTH SIDES"


def test_fork_print_is_three_place_and_model_owned() -> None:
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert marked["ForkBoss"] == {"ForkThick"}
    assert marked["ForkSlotProfile"] == {"SlotWidth", "SlotDepth", "ForkBossLength"}
    assert marked["ForkProfile"] == {"ForkWidthDim"}
    assert rod.DRAWING_PRECISION is ch_connecting_rod_notes.DRAWING_PRECISION
    assert ch_connecting_rod_notes.DRAWING_PRECISION == {
        "ForkBoss": {"ForkThick": 3},
        "ForkSlotProfile": {"SlotWidth": 3},
        "CountersinkReference": {"PinCskDia": 3},
    }
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'name_dimensions(adapter,"ForkBoss",["ForkThick"])' in build
    assert "fork_lower,fork_upper=deviations(FORK_THICKNESS_BAND)" in build
    assert "(fork_thickness_dim[0],'\"ForkThickness\"')" in build
    assert "apply_drawing_precision(adapter,DRAWING_PRECISION)" in build


def test_model_bands_are_owned_by_named_model_dimensions() -> None:
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert ch_connecting_rod_spec.FORK_THICKNESS_BAND == (0.05, -0.05)
    assert ch_connecting_rod_spec.FORK_SLOT_BAND == (0.127, 0.0)
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)",
        ("ForkBoss", "ForkThick"): "fork_upper",
        ("ForkSlotProfile", "SlotWidth"): "*deviations(FORK_SLOT_BAND)",
        ("CountersinkReference", "PinCskDia"): "csk_upper",
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
