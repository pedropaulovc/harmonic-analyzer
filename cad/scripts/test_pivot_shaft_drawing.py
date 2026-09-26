"""Offline contracts for the pivot-shaft (MHA-065) drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
import _fit_limits
import build_pivot_shaft as part
import draw_pivot_shaft as drawing
import pivot_bracket_spec
import pivot_shaft_spec as spec
import rocker_arm_spec
import rocker_bank_layout as bank
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["pivot_shaft"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_lands_on_the_side_view() -> None:
    """Policy rule 7: a turned part's diameters and lengths sit on the side
    view, and all of them are authored on Right-plane half-profiles. The
    shoulder reliefs' own feature lands in the 5:1 detail of that view."""
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PROFILE_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert not set(drawing.PROFILE_KEEP) & set(drawing.DETAIL_KEEP)
    assert set(drawing.DETAIL_KEEP) == spec.DRAWING_DIMENSIONS["ReliefProfile"]
    assert marked == {
        "ShaftDia",
        "ShoulderDia",
        "ShaftLength",
        "ShoulderLength",
        "JournalLength",
        "DomeHeight",
        "ReliefWidth",
        "ReliefDia",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    # The profile, the reliefs and the caps.
    assert source.count('create_sketch("Right")') == 3
    assert "create_revolve(" in source


def test_only_the_running_fit_carries_a_size_band() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_runs_in_the_bracket_bores() -> None:
    lower, upper = _fit_limits.deviations(spec.SHAFT_DIA_BAND)
    clearance_min = pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + upper)
    clearance_max = pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + lower)
    assert round(clearance_min, 2) == 0.15
    assert clearance_max > clearance_min


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 3,
        "ShoulderDia": 2,
        "ShaftLength": 1,
        "ShoulderLength": 2,
        "JournalLength": 1,
        "DomeHeight": 1,
        "ReliefWidth": 1,
        "ReliefDia": 3,
    }
    assert "draw_pivot_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = float(f"{spec.SHAFT_DIA:.{digits}f}")
    assert abs(printed - spec.SHAFT_DIA) <= math.ulp(spec.SHAFT_DIA)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "assert_imported_precision(" in source


def test_a_shaft_carries_no_gdt() -> None:
    """Policy rule 3: shafts carry no frames and no datums (and the old end
    faces are domes now)."""
    for attribute in (
        "PART_DATUMS",
        "GEOMETRIC_CONTROLS",
        "END_VIEW_NOTE",
        "LENGTH_TOLERANCE_MM",
        "SHAFT_LENGTH",
    ):
        assert not hasattr(spec, attribute)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" not in source


def test_the_length_is_a_cut_to_fit_reference() -> None:
    assert part.SHAFT_LENGTH == bank.PIVOT_SHAFT_LENGTH
    assert spec.LENGTH_CALLOUT == "CUT TO FIT: SPAN OVER BOTH MHA-123 EARS"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(adapter, length_annotations[0]" in source
    assert '{"ShaftLength": LENGTH_CALLOUT}' in source
    assert spec.STOCK_LENGTH > bank.PIVOT_SHAFT_OVERALL_LENGTH + 10


def test_both_ends_are_domed_and_the_height_is_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["NorthCapProfile"] == {"DomeHeight"}
    assert spec.DOME_CALLOUT == "BOTH ENDS"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_dome(adapter, "North", 0.0, -1.0)' in source
    assert '_dome(adapter, "South", SHAFT_LENGTH, 1.0)' in source
    assert spec.DOME_SPHERE_RADIUS > spec.SHAFT_DIA / 2


def test_notes_are_short_specific_facts_with_no_dimension_in_them() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 0 < len(lines) <= 4
    for line in lines:
        assert line == line.upper()
        assert not re.search(r"\d+\.\d|±|\+/-", line)
    assert "NO FLATS" in spec.DRAWING_NOTES
    assert "STEPS" not in spec.DRAWING_NOTES


def test_the_isometric_note_states_the_only_off_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    ratio = re.search(r"(\d+)\s*:\s*(\d+)", spec.ISOMETRIC_VIEW_NOTE)
    assert ratio is not None
    assert (int(ratio.group(1)), int(ratio.group(2))) == drawing.ISO_SCALE


def test_part_stamps_make_critical_properties() -> None:
    config = _config.parts("pivot-shaft")
    assert config["number"] == "MHA-065"
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_surface_finishes_name_the_running_faces() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"pivot_bearing", "pivot_journal", "shoulder_thrust"}
    for control in by_key.values():
        assert control.roughness_um == 1.6
    for key in ("pivot_bearing", "pivot_journal"):
        assert by_key[key].face.diameter_mm == spec.SHAFT_DIA
        # Each probe station is on the O.D., off both reliefs.
        z = -by_key[key].face.contains_z_mm
        north_relief = (spec.JOURNAL_LENGTH - spec.RELIEF_WIDTH, spec.JOURNAL_LENGTH)
        south_face = spec.JOURNAL_LENGTH + spec.SHOULDER_LENGTH
        south_relief = (south_face, south_face + spec.RELIEF_WIDTH)
        for low, high in (north_relief, south_relief):
            assert not low <= z <= high
    # Codex #936 PRRT_kwDOPHDy386mTMXt: rocker 19's hub rocks on the
    # shoulder's south face, which looks -Z at the shoulder's south station.
    thrust = by_key["shoulder_thrust"].face
    assert thrust.normal == (0, 0, -1)
    assert thrust.offset_mm == spec.JOURNAL_LENGTH + spec.SHOULDER_LENGTH
    # Part frame: the north end at z 0, the body toward -z.
    body_z = by_key["pivot_bearing"].face.contains_z_mm
    journal_z = by_key["pivot_journal"].face.contains_z_mm
    assert -spec.JOURNAL_LENGTH < journal_z < 0.0
    assert (
        -bank.PIVOT_SHAFT_LENGTH
        < body_z
        < -(spec.JOURNAL_LENGTH + spec.SHOULDER_LENGTH)
    )
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    for key in by_key:
        assert (
            f'control=surface_finish_by_key(SURFACE_FINISHES,"{key}")' in sheet_source
        )
    assert "roughness_ra=" not in sheet_source


def test_shoulder_reliefs_clear_the_tool_and_keep_the_seats_flat() -> None:
    """Codex #936 PRRT_kwDOPHDy386mTMXq, at the printed worst case."""
    width_low, width_high = spec.RELIEF_WIDTH_RANGE
    # The .X band as the title block prints it (0.03 in reads +/-0.8).
    one_place = _config.title_block("linear_1pl")
    assert one_place["display"] == f"±{spec.LINEAR_1PL}"
    assert spec.LINEAR_1PL >= one_place["value_in"] * 25.4
    assert spec.LINEAR_3PL == _config.title_block("linear_3pl")["value_in"] * 25.4
    assert spec.CORNER_RADIUS_MAX == _config.title_block("edge_break")["radius_mm"]
    # The narrowest groove still takes in the facing tool's nose.
    assert width_low >= spec.FACING_NOSE_RADIUS
    # The shallowest groove keeps the grooving corner under the O.D.
    assert (spec.RELIEF_DIA + spec.LINEAR_3PL) / 2.0 + spec.CORNER_RADIUS_MAX <= (
        spec.SHAFT_DIA_MIN / 2.0
    )
    # The reliefs print at the places their sizing assumes.
    assert spec.DRAWING_PRECISION["ReliefProfile"] == {"ReliefWidth": 1, "ReliefDia": 3}
    assert round(spec.RELIEF_DIA, 2) == spec.RELIEF_DIA


def test_widest_relief_leaves_each_journal_its_bearing_length() -> None:
    """Codex #936 PRRT_kwDOPHDy386mTMXq: the groove sits under the first
    RELIEF_WIDTH of the north ear's bore and of hub 19's. What is left must
    still bear at L/d 0.5 or more on the O6.35."""
    width_high = spec.RELIEF_WIDTH_RANGE[1]
    assert spec.BEARING_LENGTH_MIN == 0.5 * spec.SHAFT_DIA
    # North journal: the ear's thickness, which the journal length matches.
    assert spec.JOURNAL_LENGTH == pivot_bracket_spec.EAR_T
    north = pivot_bracket_spec.EAR_T - width_high
    # Hub 19: bears on the shoulder's south face, so the south groove is
    # under its bore. The hub may only come out long (HUB_LENGTH_BAND).
    hub_19 = rocker_arm_spec.HUB_LENGTH - rocker_arm_spec.HUB_LENGTH_BAND[1] - width_high
    for remaining in (north, hub_19):
        assert remaining >= spec.BEARING_LENGTH_MIN
    # A groove 0.1 mm wider than the .X band allows breaks the north journal:
    # the requirement binds, it is not decoration.
    assert pivot_bracket_spec.EAR_T - (width_high + 0.1) < spec.BEARING_LENGTH_MIN


def test_relief_keeps_the_thrust_faces_whole_annulus() -> None:
    """Codex #936 PRRT_kwDOPHDy386mTMXq: the groove must not eat the thrust
    face. Its flat starts where the grooving corner ends; at the groove's
    high limit that is still inside the hub's and the ear's bores, so each
    seats on the same annulus a plain shoulder gives -- its own bore edge to
    the shoulder's O10 -- as MHA-148 seats hub 0 at the other end."""
    import rocker_thrust_washer_spec as washer

    flat_start = spec.RELIEF_DIA + spec.LINEAR_3PL + 2.0 * spec.CORNER_RADIUS_MAX
    mating_bores = (rocker_arm_spec.PIVOT_HOLE_DIA, pivot_bracket_spec.BORE_DIA)
    assert flat_start <= min(mating_bores)
    # The O10 shoulder sits inside the O10.20 hub face, so hub 19 bears on
    # the shoulder's whole face; the washer gives hub 0 its own bore out.
    assert spec.SHOULDER_DIA <= rocker_arm_spec.HUB_DIA == washer.OD
    assert washer.BORE_DIA >= rocker_arm_spec.PIVOT_HOLE_DIA


def test_relief_volume_is_two_annular_grooves() -> None:
    outer = spec.SHAFT_DIA / 2.0
    inner = spec.RELIEF_DIA / 2.0
    assert part.V_RELIEFS == 2.0 * math.pi * (outer**2 - inner**2) * spec.RELIEF_WIDTH


def test_detail_sits_in_the_open_field() -> None:
    """Under the profile's length dimension, right of the notes, left of the
    title block."""
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    left, right = drawing.DETAIL_CENTER[0] - radius, drawing.DETAIL_CENTER[0] + radius
    top = drawing.DETAIL_CENTER[1] + radius
    assert top < drawing.PROFILE_KEEP["ShaftLength"][1]
    assert right < 0.218
    assert left > 0.12
    # The fence takes in both grooves and the shoulder O.D.
    fence = drawing.DETAIL_RADIUS_MM
    reach = spec.SHOULDER_LENGTH / 2.0 + spec.RELIEF_WIDTH
    assert reach < fence
    assert spec.SHOULDER_DIA / 2.0 < fence


# Measured on the r743-2R render (5100x3300 px on 431.8x279.4 mm): an Ra
# symbol at note text height runs 14.7 mm right of and 7.2 mm above its
# leader end; the relief callouts' "BOTH SHOULDER FACES" line runs ~52 mm,
# centred on its dimension text.
FINISH_SYMBOL_WIDTH = 0.0147
FINISH_SYMBOL_HEIGHT = 0.0072
RELIEF_CALLOUT_HALF_WIDTH = 0.026
TITLE_BLOCK_TOP = 0.065


def test_finishes_print_at_note_height() -> None:
    """r743-2R: at the template's default height the three Ra symbols printed
    ~18 mm tall, the journal's over the profile and DETAIL A's across the
    length dimension."""
    assert drawing.FINISH_CHAR_HEIGHT == 0.0025
    source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert source.count("char_height=FINISH_CHAR_HEIGHT") == len(spec.SURFACE_FINISHES)


def test_detail_annotations_keep_off_the_fence_and_each_other() -> None:
    """r743-2R: the O5.700 callout ran across the fence, and the thrust-face
    Ra's leader crossed the ReliefWidth callout. The Ra now leads right, over
    the south groove, to a symbol outside the fence and above the title
    block; the O5.700 callout ends left of the fence."""
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    cx, cy = drawing.DETAIL_CENTER
    symbol = drawing.SHOULDER_FINISH_SYMBOL
    attach = drawing.SHOULDER_FINISH_ATTACH
    # The body sits wholly outside the fence, right of it.
    assert symbol[0] > cx + radius
    assert symbol[1] > TITLE_BLOCK_TOP
    assert symbol[1] + FINISH_SYMBOL_HEIGHT < drawing.PROFILE_KEEP["ShaftLength"][1]
    # The leader runs through air: above the body flank and under the shoulder
    # O.D. where it leaves the face.
    scale = drawing.DETAIL_SCALE[0] / 1000.0
    flank = cy + spec.SHAFT_DIA / 2.0 * scale
    shoulder_top = cy + spec.SHOULDER_DIA / 2.0 * scale
    assert flank < attach[1] < shoulder_top
    assert flank < symbol[1]
    # The ReliefWidth callout sits above everything the Ra draws.
    width_text = drawing.DETAIL_KEEP["ReliefWidth"]
    assert width_text[1] > symbol[1] + FINISH_SYMBOL_HEIGHT
    # The O5.700 callout ends left of the fence.
    dia_x, dia_y = drawing.DETAIL_KEEP["ReliefDia"]
    fence_left = cx - math.sqrt(radius**2 - (dia_y - cy) ** 2)
    assert dia_x + RELIEF_CALLOUT_HALF_WIDTH < fence_left
