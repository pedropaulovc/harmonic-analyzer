"""Offline contracts for the channel anchor jam nut (MHA-CH-14) drawing."""

from __future__ import annotations

import ast
import math
import subprocess
import sys
from pathlib import Path

import pytest

import _config
import build_ch_anchor_jam_nut as part
import ch_anchor_jam_nut_spec as spec
import draw_ch_anchor_jam_nut as drawing
import sm_summing_lever_spec as lever
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import printed_band_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-anchor-jam-nut.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-anchor-jam-nut.pdf")
    assert (
        DRAWINGS_BY_NAME["ch_anchor_jam_nut"].script == Path(drawing.__file__).resolve()
    )


def test_dimension_transfer_uses_shared_helper() -> None:
    from _drawing_dimensions import move_model_dimension

    assert drawing.move_model_dimension is move_model_dimension


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_DIMENSIONS == {
        "NutProfile": {"NutOd"},
        "Nut": {"NutThickness"},
        "DriveSlotProfile": {"SlotWidth"},
        "DriveSlot": {"SlotDepth"},
    }


def _calls(path: str) -> list[ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]


def _calls_by_name(path: str) -> dict[str, ast.Call]:
    return {call.func.id: call for call in _calls(path)}


def test_builder_names_every_marked_dimension() -> None:
    named: dict[str, set[str]] = {}
    for call in _calls(part.__file__):
        if call.func.id == "name_dimensions":
            feature = ast.literal_eval(call.args[1])
            named.setdefault(feature, set()).update(ast.literal_eval(call.args[2]))
        elif call.func.id == "define_circle":
            kw = {k.arg: k.value for k in call.keywords}
            named.setdefault("NutProfile", set()).add(ast.literal_eval(kw["names"])[2])
        elif call.func.id == "define_centered_rectangle":
            kw = {k.arg: k.value for k in call.keywords}
            named.setdefault("DriveSlotProfile", set()).update(
                {ast.literal_eval(kw["name_width"]), ast.literal_eval(kw["name_depth"])}
            )
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert names <= named[feature], feature


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        "NutOd": 3,
        "NutThickness": 2,
        "SlotWidth": 2,
        "SlotDepth": 2,
    }


def test_only_the_od_carries_an_explicit_band() -> None:
    # The O.D.'s band sits inside the wall-floor / neighbour window, which the
    # title block's .XXX row overruns; every other size takes the title block.
    assert model_toleranced_dimensions(part) == {("NutProfile", "NutOd"): "OD_BAND"}
    band = printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)
    assert spec.OD_BAND < band
    assert spec.OD - band < 2 * spec.MIN_WALL + THREAD_MAJOR_MM["#6-32"]


def test_neighbour_gap_charges_both_taps_position_zones() -> None:
    # Code review C06: two adjacent anchors, each tap at the far edge of the
    # lever's RFS spring-hole zone toward the other, and both nuts at the top
    # of their O.D. band; the thinnest nut at the bottom of it.
    zone = float(lever.GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"])
    assert zone <= 0.15  # owner ruling: Ø0.30 -> Ø0.15 (or tighter)
    # Each centre sits within a zone radius of true position; worst, each
    # moves that radius toward the other.
    left_tap = 0.0 + zone / 2.0
    right_tap = lever.CHANNEL_PITCH - zone / 2.0
    spacing = right_tap - left_tap
    assert spacing == pytest.approx(lever.CHANNEL_PITCH - zone)
    assert spec.CENTRE_SPACING_WORST == pytest.approx(spacing)
    od_max, od_min = spec.OD + spec.OD_BAND, spec.OD - spec.OD_BAND
    gap = spacing - od_max  # two radii of od_max between the centres
    assert spec.NEIGHBOUR_GAP_WORST == pytest.approx(gap)
    assert gap >= spec.NEIGHBOUR_CLEARANCE
    wall = (od_min - THREAD_MAJOR_MM["#6-32"]) / 2.0
    assert spec.WALL_WORST == pytest.approx(wall)
    assert wall >= spec.MIN_WALL
    # The old Ø0.30 zone with the old 6.66 ±0.14 nut overlapped its neighbour,
    # and at Ø0.30 no O.D. window is left between the .060 wall floor and the
    # neighbour gap: no turnable band fits.
    assert lever.CHANNEL_PITCH - 0.30 - (6.66 + 0.14) < 0.0
    window = (lever.CHANNEL_PITCH - 0.30 - spec.NEIGHBOUR_CLEARANCE) - (
        2.0 * spec.MIN_WALL + THREAD_MAJOR_MM["#6-32"]
    )
    assert window < 0.0
    # The zone opens it enough to hold the explicit band.
    assert spec.CENTRE_SPACING_WORST - spec.NEIGHBOUR_CLEARANCE - (
        2.0 * spec.MIN_WALL + THREAD_MAJOR_MM["#6-32"]
    ) >= 2.0 * spec.OD_BAND


def test_spec_margins() -> None:
    assert spec.WALL_WORST >= WALL_FLOOR_MM
    assert spec.UNDER_SLOT_WORST >= WALL_FLOOR_MM
    assert spec.NEIGHBOUR_GAP_WORST >= 0.249
    assert spec.WALL_WORST == pytest.approx(
        (spec.OD_MIN - THREAD_MAJOR_MM["#6-32"]) / 2
    )
    assert spec.UNDER_SLOT_WORST == pytest.approx(
        spec.THICKNESS_MIN - spec.SLOT_DEPTH_MAX
    )
    # The cut is narrower than the O.D., and its span runs out past it.
    assert 0.0 < spec.SLOT_WIDTH < spec.OD
    assert spec.SLOT_SPAN > spec.OD
    # Fork prongs fit beside the shank: the cut is narrower than the bore, so
    # a ring of nut stands each side of the thread under the prongs.
    assert spec.SLOT_WIDTH < spec.TAP_DRILL_DIA
    assert spec.SLOT_DEPTH < spec.THICKNESS
    assert spec.THICKNESS - spec.SLOT_DEPTH >= WALL_FLOOR_MM


def test_tap_is_the_anchor_thread_through() -> None:
    assert spec.THREAD == "#6-32"
    assert spec.TAP_SPEC.kind == "tapped"
    assert spec.TAP_SPEC.end == "through_all"
    assert spec.TAP_DRILL_DIA == pytest.approx(TAP_DRILL_MM["#6-32"])
    wizard = _calls_by_name(part.__file__)["wizard_holes"]
    assert ast.unparse(wizard.args[1]) == "TAP_SPEC"
    assert {k.arg: ast.unparse(k.value) for k in wizard.keywords}["name"] == (
        "'ThreadBore'"
    )


def test_analytic_volume() -> None:
    r, d = spec.OD / 2.0, spec.TAP_DRILL_DIA / 2.0
    assert part.V_DISC == pytest.approx(math.pi * r**2 * spec.THICKNESS)
    assert part.V_THREAD == pytest.approx(math.pi * d**2 * spec.THICKNESS)
    # A full-width strip is the whole circle.
    assert part._strip_area(r, r) == pytest.approx(math.pi * r**2)
    assert 0.0 < part.V_SLOT < spec.SLOT_WIDTH * spec.OD * spec.SLOT_DEPTH
    assert part.V_TOTAL == pytest.approx(part.V_DISC - part.V_THREAD - part.V_SLOT)


def test_callouts_and_no_notes() -> None:
    assert not hasattr(spec, "DRAWING_NOTES")
    assert drawing.DIMENSION_CALLOUTS == {
        "SlotWidth": "SLOT THRU ACROSS",
        "NutOd": spec.OD_CALLOUT,
        "NutThickness": spec.THICKNESS_CALLOUT,
    }
    # The thin nut's engagement shortfall is printed as a plain fact.
    assert spec.ENGAGEMENT_MIN < 1.5 * spec.THREAD_MAJOR
    # The O.D.'s explicit band is bounded by the wall as well as the neighbour.
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) == {"NutOd"}
    assert spec.MIN_WALL <= spec.WALL_WORST
    text = Path(drawing.__file__).read_text(encoding="utf-8").upper()
    for banned in ("LOCTITE", "THREADLOCK", "NYLON", "EXCEPTION", "RULING"):
        assert banned not in text


def test_registry_row() -> None:
    row = _config.parts("ch-anchor-jam-nut")
    assert row["number"] == "MHA-CH-14"
    assert row["title"] == "Channel Anchor Jam Nut"
    assert int(row["quantity"]) == 20
    assert "C36000" in str(row["material_specification"])
    assert row["finish"]
    assert row["process"]
    assert part.MATERIAL == "Brass"


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls_by_name(drawing.__file__)[
                "read_required_properties"
            ].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    build_calls = _calls_by_name(part.__file__)
    stamp = build_calls["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    assert stamp.lineno < build_calls["save_part_and_images"].lineno
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []


def test_no_finish_symbol_and_no_gdt() -> None:
    names = set(_calls_by_name(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish_symbol",
    }
    assert spec.SURFACE_FINISHES == ()


def test_spec_imports_no_com_or_drawing_modules() -> None:
    code = (
        "import sys, ch_anchor_jam_nut_spec\n"
        "bad = sorted(m for m in sys.modules if m.startswith("
        "('win32', 'pythoncom', 'pywintypes', 'solidworks_mcp', '_drawing', "
        "'_com')))\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(spec.__file__).parent,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == ""


def test_printed_shortfalls_are_owner_declared_minors() -> None:
    """Machinist gate 2026-10-17: a stated shortfall with no declaration gates."""
    from machinist_exceptions import load_exceptions

    engagement, wall = load_exceptions(_config.CONFIG_DIR, "ch_anchor_jam_nut", "part")
    assert (engagement.kind, wall.kind) == ("minor", "minor")
    assert spec.THICKNESS_CALLOUT in engagement.where
    assert "rule 18" in engagement.finding
    assert drawing.DIMENSION_CALLOUTS_ABOVE["NutOd"] in wall.where
    assert "rule 17" in wall.finding
    assert engagement.reason.startswith("owner ruling 2026-10-17")
    # The inch wall (.0605 at the .060 floor) is the owner's 2026-11-01 ruling.
    assert wall.reason.startswith(
        "Owner ruling 2026-11-01: thin walls above the .060 floor but under the .080 target"
    )
    assert "coordinator ruling" not in Path(spec.__file__).read_text(encoding="utf-8")
