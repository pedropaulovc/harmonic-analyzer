from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import build_ch_pivot_bracket as part
import ch_pivot_bracket_drawing_spec as drawing_spec
import ch_pivot_bracket_spec as spec
import draw_ch_pivot_bracket as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from ch_pivot_bracket_sides import FOOT_LEN, FOOT_Z1, HOLE_STATION, HOLE_Z

_FRAME_M = 0.0127


def _drawing_source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_registry_row_names_the_bracket_outputs() -> None:
    row = DRAWINGS_BY_NAME["ch_pivot_bracket"]
    assert row.part == "ch_pivot_bracket"
    assert row.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-pivot-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-pivot-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-pivot-bracket_drawing.png")


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is drawing_spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is drawing_spec.DRAWING_DIMENSIONS
    marked = set().union(*drawing_spec.DRAWING_DIMENSIONS.values())
    # Every marked dimension is placed by exactly one view; an unplaced import
    # is deleted silently, a kept name the part never marks never prints.
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    # Every manufactured feature is sized and located: foot (width, length,
    # height), ear (thickness; its width is the foot's), arch radius, bore
    # (size, height, lateral), hold-down hole (size, station, lateral), and
    # the apex tap (native callout + station).
    assert marked == {
        "FootW",
        "FootLen",
        "FootHt",
        "EarThick",
        "ArchRadius",
        "BoreCz",
        "ShaftBoreDia",
        "BoreLateral",
        "HoleStation",
        "HoleDia",
        "HoleLateral",
        "SetScrewLocation",
    }
    assert spec.EAR_W == spec.FOOT_W


def test_the_part_owns_every_printed_decimal_place() -> None:
    assert drawing_spec.DRAWING_PRECISION_BY_NAME == {
        name: 2 for name in set().union(*drawing_spec.DRAWING_DIMENSIONS.values())
    }
    assert drawing.DRAWING_PRECISION_BY_NAME is drawing_spec.DRAWING_PRECISION_BY_NAME
    assert part.DRAWING_PRECISION is drawing_spec.DRAWING_PRECISION
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    labels = set(
        re.findall(r'_set_reference_precision\([^,]+,\s*"([^"]+)"\)', _drawing_source())
    )
    assert labels == set(drawing_spec.DRAWING_REFERENCE_PRECISION) == {"overall height"}


def test_model_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("FootProfile", "FootLen"): "FOOT_LEN_BAND",
        ("Ear", "EarThick"): "EAR_T_BAND",
        ("HoleProfile", "HoleStation"): "STATION_BAND",
        ("SetScrewReference", "SetScrewLocation"): "SET_SCREW_STATION_BAND",
        ("ShaftBoreProfile", "ShaftBoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    assert part.FOOT_LEN_BAND == part.EAR_T_BAND == part.STATION_BAND == 0.10
    assert part.SET_SCREW_STATION_BAND == 0.10
    # The reamed bore holds the drilled-hole growth its set-screw thread
    # count assumes: largest bore = nominal + DRILL_GROWTH.
    upper, lower = drawing_spec.BORE_DIA_BAND
    assert lower == 0.0
    assert abs(spec.BORE_DIA + upper - 2.0 * spec.BORE_RADIUS_MAX) < 1e-9


def test_reference_lines_restate_the_geometry_their_equations_drive() -> None:
    """Each line's value, and the origin anchors that place it on the outline,
    evaluate from the part's globals to the as-built value: the deferred
    equations are neutral, and a global edit moves the line."""
    globals_mm = {"FootW": spec.FOOT_W, "FootZ1": FOOT_Z1, "EarT": spec.EAR_T}

    def evaluate(expression: str) -> float:
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic

    expected = {
        "BoreLateral": spec.FOOT_W / 2.0,
        "HoleLateral": spec.FOOT_W / 2.0,
        # The tap sits at z = 0, the bore axis plane; the station runs from
        # the ear's inboard face, the face every plan length starts on.
        "SetScrewLocation": 0.0 - spec.FOOT_Z0,
    }
    assert (
        tuple(row[0] for row in part.REFERENCE_LINES) == drawing_spec.REFERENCE_SKETCHES
    )
    for (
        sketch,
        plane,
        name,
        start,
        end,
        orientation,
        value,
        drives,
    ) in part.REFERENCE_LINES:
        assert value == expected[name], sketch
        axis = 1 if orientation == "vertical" else 0
        assert abs(end[axis] - start[axis]) == value
        assert end[1 - axis] == start[1 - axis]
        anchors = [abs(c) for c in start if abs(c) > 1e-9]
        assert [evaluate(d) for d in drives] == [value, *anchors], sketch
        assert plane == ("Front" if name == "BoreLateral" else "Top")
    starts = {row[2]: row[3] for row in part.REFERENCE_LINES}
    # Laterals start on the west side face, the tap station on the inboard
    # face (Top-plane sketch y is model -Z).
    assert starts["BoreLateral"][0] == starts["HoleLateral"][0] == -spec.FOOT_W / 2.0
    assert -starts["SetScrewLocation"][1] == spec.FOOT_Z0
    # The hold-down station is the hole's z off that same face.
    assert abs(HOLE_STATION - (HOLE_Z - spec.FOOT_Z0)) < 1e-9
    assert abs(FOOT_LEN - (FOOT_Z1 - spec.FOOT_Z0)) < 1e-9


def test_bore_callout_names_the_mating_pivot_shaft() -> None:
    number = _config.parts("ch-pivot-shaft")["number"]
    assert number == "MHA-CH-005"
    bore = drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert bore.startswith("REAM THRU\n")
    assert bore.endswith(f"PIVOT SHAFT {number}")
    assert drawing.DIMENSION_CALLOUTS["HoleDia"] == "DRILL THRU"
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP) | set(
        drawing.TOP_KEEP
    )


def test_every_banded_length_says_what_its_band_holds() -> None:
    """A band tighter than the title block names its reason at the dimension;
    the hold-down station names the support it lands on."""
    banded = {name for _feature, name in model_toleranced_dimensions(part)}
    assert banded <= set(drawing.DIMENSION_CALLOUTS)
    support = _config.parts("fr-rocker-arm-support")["number"]
    assert drawing.DIMENSION_CALLOUTS["HoleStation"] == f"ON {support} SEAT"
    for name in ("FootLen", "EarThick", "SetScrewLocation"):
        assert not re.search(r"\d", drawing.DIMENSION_CALLOUTS[name]), name


# The native definitions of a through-next 4-40 Hole Wizard tap, as the
# fleet's TAP-prefixed callouts carry them (part 5 the thread, part 7 the
# tap drill).
_NATIVE_TAP = {
    5: "TAP <hw-threaddesc> - <hw-threadclass> <hw-thru>",
    6: "",
    7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
    8: "",
}


def test_tap_callout_says_to_bore_and_states_its_engagement() -> None:
    updated = drawing.set_screw_callout_definitions(dict(_NATIVE_TAP))
    assert updated[7] == "<MOD-DIAM><hw-thrutapdrldia> TO BORE"
    assert updated[5] == (
        f"TAP <hw-threaddesc> TO BORE\n{spec.SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT}"
    )
    joined = "\n".join(updated.values())
    # Every Hole Wizard size variable survives; the class and THRU are gone.
    assert "<hw-threaddesc>" in joined and "<hw-thrutapdrldia>" in joined
    assert "<hw-threadclass>" not in joined and "<hw-thru>" not in joined
    # The engagement is the spec's own full-thread minimum, a plain fact.
    fact = drawing.SET_SCREW_QUALIFIER
    assert f"{spec.SET_SCREW_FULL_THREAD_MIN:.2f} MIN" in fact
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY"):
        assert word not in fact


def test_tap_callout_rewrite_refuses_an_unexpected_native_format() -> None:
    blind = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-threadclass> <hw-depth>"}
    with pytest.raises(RuntimeError, match="two native extents"):
        drawing.set_screw_callout_definitions(blind)
    no_class = {**_NATIVE_TAP, 5: "TAP <hw-threaddesc> <hw-thru>"}
    with pytest.raises(RuntimeError, match="not in one callout part"):
        drawing.set_screw_callout_definitions(no_class)


def test_foot_seat_is_the_one_finish_controlled_face() -> None:
    (control,) = drawing_spec.SURFACE_FINISHES
    assert control.key == "foot_seat"
    assert control.roughness_um == 3.2
    assert control.face.normal == (0, -1, 0)
    assert control.face.offset_mm == 0.0


def test_projected_views_stay_aligned_and_ordered() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    seat = drawing._front_y(0.0)
    apex = drawing._front_y(spec.EAR_TOP_Y)
    assert abs((seat + apex) / 2.0 - drawing.FRONT_CENTER[1]) < 1e-12
    plan_top = drawing._top_y(spec.FOOT_Z0)
    plan_bottom = drawing._top_y(FOOT_Z1)
    assert abs((plan_top + plan_bottom) / 2.0 - drawing.TOP_CENTER[1]) < 1e-12
    # Room for the two lateral lanes between the elevation and the plan.
    lanes = (drawing.TOP_KEEP["HoleLateral"][1], drawing.TOP_KEEP["FootW"][1])
    assert plan_bottom > lanes[0] > lanes[1] > apex + 0.010


def test_every_annotation_anchor_prints_inside_the_sheet() -> None:
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["ch_pivot_bracket"].layout]
    anchors = {
        **drawing.FRONT_KEEP,
        **drawing.TOP_KEEP,
        "front view": drawing.FRONT_CENTER,
        "plan view": drawing.TOP_CENTER,
        "isometric view": drawing.ISO_CENTER,
        "set-screw callout": drawing.SET_SCREW_CALLOUT_XY,
        "overall height": drawing.OVERALL_HEIGHT_XY,
    }
    for label, (x, y) in anchors.items():
        assert _FRAME_M < x < template.width_m - _FRAME_M, label
        assert _FRAME_M < y < template.height_m - _FRAME_M, label
        assert not (
            x > template.title_block_left_m and y < template.title_block_top_m
        ), f"{label} is inside the title block"


def test_apex_tap_callout_fits_above_the_plan_between_the_lanes() -> None:
    from _drawing_annotation_extent import CLEAR_GAP_M
    from _layout_geometry import estimate_text_box

    # The native callout font as MHA-DT-002 printed it (cap 3.5 mm,
    # 109.7 mm per 42 glyphs, lines 16.8 pt apart).
    drill = (
        f"Ø{blind_cut_dia_mm(spec.SET_SCREW_HOLE_SPEC):.2f} {drawing.SET_SCREW_EXTENT}"
    )
    thread = f"{drawing.SET_SCREW_PROCESS} 4-40 UNC {drawing.SET_SCREW_EXTENT}"
    box = estimate_text_box(
        f"{drill}\n{thread}\n{drawing.SET_SCREW_QUALIFIER}",
        anchor=drawing.SET_SCREW_CALLOUT_XY,
        height=0.0035,
        reference=2,  # swCENTER
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["ch_pivot_bracket"].layout]
    assert box.xmin >= _FRAME_M + CLEAR_GAP_M
    assert box.ymax <= template.height_m - _FRAME_M - CLEAR_GAP_M
    # Wholly above the plan's top edge and every extension line drawn off it.
    assert box.ymin >= drawing._top_y(spec.FOOT_Z0) + CLEAR_GAP_M
    # Its leader drops from the block's east end to the tap's east rim: east
    # of the plan centre (where the hole station's witness ends) and west of
    # the east edge (where the right lanes' witnesses start).
    assert drawing.TOP_CENTER[0] < box.xmax < drawing._EAST_X
    # Clear of the tap station's text above its span.
    set_screw_text_x = drawing.TOP_KEEP["SetScrewLocation"][0]
    assert box.xmax + 0.015 < set_screw_text_x


def test_tap_note_solidworks_adds_is_removed() -> None:
    source = _drawing_source()
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source


def test_registry_row_carries_the_title_block_material_specification() -> None:
    config = _config.parts("ch-pivot-bracket")
    assert config["number"] == "MHA-CH-008"
    assert config["material_specification"]
    assert int(config["quantity"]) == 2
