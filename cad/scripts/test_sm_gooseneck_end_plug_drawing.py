"""Offline contracts for MHA-SM-05, the gooseneck end plug, and its drawing.

Owner rulings 2026-11-08 (Pedro), #2315: an independent part, bonded into
MHA-SM-01 with LOCTITE 638 at MHA-SM-00, tapped #10-24 blind before bonding
for the MHA-SM-VN-56 shoulder screw.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_sm_gooseneck_end_plug as part
import draw_sm_gooseneck_end_plug as drawing
import sm_gooseneck_end_plug_spec as spec
import sm_gooseneck_geom as geom
import sm_gooseneck_spring_joint as joint
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H
from _machinist_review_mode import MachinistReviewMode
from machinist_exceptions import load_exceptions

IN = 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sm-gooseneck-end-plug.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sm-gooseneck-end-plug.pdf")
    entry = DRAWINGS_BY_NAME["sm_gooseneck_end_plug"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.layout == DRAWINGS_BY_NAME["sm_gooseneck"].layout
    assert "draw_sm_gooseneck_end_plug.py" in PRECISION_MIGRATED_DRAWINGS
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_registry_row_is_an_independent_bare_1018_part() -> None:
    row = _config.parts("sm-gooseneck-end-plug")
    assert row["number"] == spec.NUMBER == "MHA-SM-05"
    assert "component_of" not in row
    assert int(row["quantity"]) == 1
    assert row["drawing_unit"] == spec.UNIT == geom.SHEET_UNIT == "in"
    assert "1018" in str(row["material_specification"])
    assert "no plating" in str(row["finish"])
    assert part.MATERIAL == "Plain Carbon Steel"
    # The numbers the notes and callout name are the registries' own.
    assert _config.parts("sm-gooseneck")["number"] == spec.TUBE_NUMBER
    assert _config.parts("sm-vn-gooseneck-shoulder-screw")["number"] == spec.SCREW_NUMBER


def test_plug_is_flush_and_its_spigot_sits_in_the_bore() -> None:
    # Owner rulings 2026-11-08 (Pedro), #2315: head Ø.500 x .60 flush with
    # the tube, spigot Ø.363 x .42 at the bond window.
    assert geom.PLUG_DIA == geom.TUBE_DIA == pytest.approx(0.500 * IN)
    assert geom.PLUG_HEAD_LENGTH == pytest.approx(0.60 * IN)
    assert geom.PLUG_SHANK_LENGTH == pytest.approx(0.42 * IN)
    assert joint.PLUG_SHANK_DIA == pytest.approx(0.363 * IN)
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    clearance = geom.TUBE_BORE_DIA - joint.PLUG_SHANK_DIA
    assert joint.BOND_CLEARANCE_MIN <= clearance <= joint.BOND_CLEARANCE_MAX
    assert part.TAP_DRILL_R < part.SHANK_R < part.PLUG_R
    # The longest printed spigot stays short of the bend's exit tangent.
    assert spec.SPIGOT_LENGTH_MAX == pytest.approx(0.44 * IN)
    assert spec.SPIGOT_LENGTH_MIN == pytest.approx(0.40 * IN)
    assert spec.SPIGOT_LENGTH_MAX < geom.TUBE_STRAIGHT
    assert part.V_PLUG == pytest.approx(
        math.pi
        * (
            (geom.PLUG_DIA / 2.0) ** 2 * geom.PLUG_HEAD_LENGTH
            + (joint.PLUG_SHANK_DIA / 2.0) ** 2 * geom.PLUG_SHANK_LENGTH
        )
    )
    assert part.V_FINAL == pytest.approx(part.V_PLUG - part.V_TAP)


def test_blind_tap_stays_inside_the_head() -> None:
    assert joint.TAP_SPEC.kind.startswith("tapped")
    assert joint.TAP_SPEC.size == "#10-24"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert joint.TAP_SPEC.depth_mm == joint.TAP_DRILL_DEPTH == pytest.approx(0.56 * IN)
    assert joint.TAP_SPEC.overrides_mm == {"ThreadDepth": joint.TAP_THREAD_DEPTH}
    assert joint.TAP_THREAD_DEPTH == pytest.approx(0.44 * IN)
    # The full drill Ø stays in the shortest head; its point stays in the plug.
    assert joint.TAP_DRILL_DEPTH_MAX <= joint.PLUG_HEAD_LENGTH_MIN
    tip = joint.TAP_DRILL_DEPTH_MAX + DRILL_POINT_H * joint.TAP_DRILL_DIA_MAX / 2.0
    assert tip < geom.PLUG_LENGTH
    assert part.V_TAP > 0.0


def test_profile_marks_exactly_the_printed_dimensions() -> None:
    # Head Ø and length, spigot Ø and overall length: the spigot's length is
    # their difference and prints no value of its own.
    names = {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugLength"}
    assert spec.DRAWING_DIMENSIONS == {spec.PROFILE: names}
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "PlugDia": 2,
        "PlugHeadLength": 2,
        "PlugLength": 2,
        "PlugShankDia": 3,
    }
    assert spec.REFERENCE_DIMENSIONS == {spec.PROFILE: frozenset({"PlugShankDia"})}
    assert spec.DIMENSION_CALLOUTS == {spec.PROFILE: {"PlugShankDia": "SEE NOTE 1"}}


def test_only_the_reference_value_is_bracketed_under_its_callout(monkeypatch) -> None:
    class Display:
        def __init__(self) -> None:
            self.ShowParenthesis = False
            self.text: dict[int, str] = {}

        def SetText(self, slot: int, text: str) -> None:
            self.text[slot] = text

        def GetText(self, slot: int) -> str:
            return self.text.get(slot, "")

    displays: dict[str, Display] = {}

    def named(_adapter, _feature, names):
        return {name: (displays.setdefault(name, Display()), None) for name in names}

    monkeypatch.setattr(part, "_named_dimensions", named)
    part._author_dimension_callouts(None)
    part._author_reference_dimensions(None)
    display = displays["PlugShankDia"]
    assert (display.GetText(1), display.GetText(2)) == ("(<MOD-DIAM>", ")")
    assert display.GetText(4) == "SEE NOTE 1"
    assert not display.ShowParenthesis


def test_one_flag_note_states_the_fit_and_the_joint() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert lines == [
        "1. TURN SPIGOT TO MEASURED MHA-SM-01 BORE, CLEARANCE .004-.009,",
        "   FOR ITS LOCTITE 638 BOND INTO MHA-SM-01 AT MHA-SM-00",
    ]
    # No sequence note: the sheet shows the plug alone, so it leaves the
    # bench tapped; the bond is MHA-SM-00 STEP 8 (#2315, no RV-02).
    assert "BEFORE" not in spec.DRAWING_NOTES
    declared = load_exceptions(_config.CONFIG_DIR, "sm-gooseneck-end-plug", "part")
    assert [entry.id for entry in declared] == ["RV-01"]
    # Rule 7: each line ends left of the title block (x 0.216) at the sheet's
    # ~2.42 mm a character.
    assert drawing.NOTES_XY[0] + 0.00242 * max(map(len, lines)) < 0.214
    # The joint's window in plain inch steps, rounded inward at three places.
    window = "-".join(
        f"{inches:.3f}".lstrip("0")
        for inches in (
            math.ceil(round(joint.BOND_CLEARANCE_MIN / IN * 1e3, 6)) / 1e3,
            math.floor(round(joint.BOND_CLEARANCE_MAX / IN * 1e3, 6)) / 1e3,
        )
    )
    assert spec.BOND_WINDOW == window == ".004-.009"
    numbers = {line.split(".", 1)[0] for line in lines if not line.startswith(" ")}
    assert numbers == {"1"}
    printed = " ".join(spec.DIMENSION_CALLOUTS_BY_NAME.values())
    assert set(re.findall(r"SEE NOTE (\d)", printed)) <= numbers
    notes = " ".join(spec.DRAWING_NOTES.split()).upper()
    # No torch, no plating, no sleeve (owner rulings 2026-11-08, #2315).
    for word in ("BRAZE", "BAG-7", "FLUX", "PLATE", "SLEEVE", "BEND"):
        assert word not in notes
    assert "<MOD-DIAM>" not in notes and "Ø" not in notes


def test_tap_callout_states_geometry_and_its_mate_within_four_rows() -> None:
    rows = spec.TAP_CALLOUT_BELOW.splitlines()
    assert rows == ["FOR MHA-SM-VN-56", "ENGAGEMENT .220 MIN (1.16D)"]
    assert max(map(len, rows)) <= 39
    assert spec.TAP_CALLOUT_PRECISION == {
        "hw-tapdrldia": 3,
        "hw-threaddepth": 2,
        "hw-tapdrldepth": 2,
    }


def test_sheet_layout_keeps_views_and_text_apart() -> None:
    keep = drawing.FRONT_KEEP
    half = geom.PLUG_DIA / 2.0 * drawing._S
    end_right = drawing.END_CENTER[0] + half
    # The head Ø stands between the end view and the end face.
    assert end_right + 0.008 < keep["PlugDia"][0] < drawing.END_FACE_X
    # The spigot Ø stands right of the spigot, short of the isometric.
    assert drawing.SPIGOT_END_X < keep["PlugShankDia"][0] < drawing.ISO_CENTER[0] - 0.050
    # The lengths stack over the part, the overall outermost.
    assert drawing.TOP_Y < keep["PlugHeadLength"][1] < keep["PlugLength"][1]
    # The tap callout and the views stay inside the border, the notes under
    # the views and left of the title block.
    assert drawing.TAP_CALLOUT_XY[1] < 0.266
    # The centred callout's widest line (~0.066) clears the left border
    # (~0.015) and ends short of the side view's stacked lengths.
    assert drawing.TAP_CALLOUT_XY[0] - 0.033 > 0.020
    assert drawing.TAP_CALLOUT_XY[0] + 0.033 < drawing.END_FACE_X - 0.010
    assert drawing.NOTES_XY[1] < drawing.FRONT_CENTER[1] - half - 0.020
    assert drawing.SPIGOT_END_X - drawing.END_FACE_X == pytest.approx(
        geom.PLUG_LENGTH * drawing._S
    )
