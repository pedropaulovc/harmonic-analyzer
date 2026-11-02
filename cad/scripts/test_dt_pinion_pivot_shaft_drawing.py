"""Offline contracts for the pinion-torque-shaft drawing."""

from __future__ import annotations

import pytest
from pathlib import Path

import dt_pinion_pivot_shaft_spec
import draw_dt_pinion_pivot_shaft as drawing
import build_dt_pinion_pivot_shaft as shaft
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = dt_pinion_pivot_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == dt_pinion_pivot_shaft_spec.SHAFT_DIA
    part_source = Path(shaft.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-pivot-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_pinion_pivot_shaft"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert shaft.DRAWING_DIMENSIONS is dt_pinion_pivot_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.PROFILE_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.PROFILE_KEEP)
    assert set(dt_pinion_pivot_shaft_spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.SHAFT_DIA == dt_pinion_pivot_shaft_spec.SHAFT_DIA
    assert drawing.SHAFT_LEN == dt_pinion_pivot_shaft_spec.SHAFT_LEN


def test_one_side_view_carries_the_lathe_dimensions_and_a_detail_the_crown() -> None:
    # drawing-guidelines.md rule 11: the diameter, the body and the overall
    # length all read in the side view; no end view.
    assert set(drawing.PROFILE_KEEP) == {
        "OverallLength",
        "ShaftLength",
        "ShaftDia",
        "PinHoleDia",
    }
    assert set(drawing.DETAIL_KEEP) == {"CapFrontSag", "CapFrontR"}
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.DETAIL_SCALE == (5, 1)
    assert drawing.ISO_SCALE == (1, 2)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front"' not in source
    assert source.count("place_view(") == 2
    assert dt_pinion_pivot_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    assert "for view in (profile, iso):" in source
    assert "set_hidden_lines_removed(adapter, detail)" in source


def test_overall_length_is_a_tip_to_tip_reference_over_the_body() -> None:
    spec = dt_pinion_pivot_shaft_spec
    assert spec.OVERALL_LEN == pytest.approx(spec.SHAFT_LEN + 2.0 * spec.CAP_SAG)
    source = Path(shaft.__file__).read_text(encoding="utf-8")
    assert 'pin_holes.record("OverallLength", \'"ShaftLen" + 2 * "CapSag"\')' in source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Singular helper, so it prints "(189.4)" with no diameter glyph (r3).
    assert "set_reference_dimensions(" not in drawing_source
    assert (
        'set_reference_dimension(adapter, overall[0], label="overall length")'
        in drawing_source
    )
    # Overall outermost, over the body length.
    assert (
        drawing.PROFILE_KEEP["OverallLength"][1]
        > drawing.PROFILE_KEEP["ShaftLength"][1]
    )
    assert drawing.DIMENSION_CALLOUTS["ShaftLength"] == "CYLINDRICAL BODY"


def test_running_fit_names_its_mate_and_the_sheet_carries_no_gdt() -> None:
    import _config

    block = _config.parts("dt-pinion-pivot-block")["number"]
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == f"RUNNING FIT IN\n{block} BORES"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert not hasattr(dt_pinion_pivot_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    assert 'entity_type="SILHOUETTE"' in source
    assert "char_height=FINISH_CHAR_HEIGHT" in source
    # The diameter stands outside the front end, short of DETAIL A's fence
    # (inside the border: left of the back end it ran over it, r3); the
    # pin-hole callout under the bar, left of the front hole it leads to.
    assert drawing.PROFILE_KEEP["ShaftDia"][0] > drawing.FRONT_END_X
    assert drawing.PROFILE_KEEP["ShaftDia"][0] < (
        drawing.DETAIL_CENTER[0] - drawing._DETAIL_FENCE_R - 0.020
    )
    assert drawing.PROFILE_KEEP["PinHoleDia"][1] < drawing.SHAFT_LOWER_FLANK_Y
    assert drawing.PROFILE_KEEP["PinHoleDia"][0] < drawing.FRONT_PIN_X - 0.030


def test_linked_notes_are_few_and_carry_no_dimension_or_general_tolerance() -> None:
    notes = dt_pinion_pivot_shaft_spec.DRAWING_NOTES
    assert notes == "CENTRES OK."
    assert model_toleranced_dimensions(shaft) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }
    # U27: the lengths read the title-block band, not a tight tolerance (#290:
    # .XX, the row the rig's stacks read).
    assert dt_pinion_pivot_shaft_spec.DRAWING_PRECISION == {
        "ShaftProfile": {"ShaftDia": 4, "ShaftLength": 2},
        "CapFrontProfile": {"CapFrontSag": 2, "CapFrontR": 2},
        "PinHoleProfile": {"PinHoleDia": 4, "OverallLength": 2},
    }
    assert dt_pinion_pivot_shaft_spec.CROWN_CALLOUT == "BOTH ENDS"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(shaft.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("dt-pinion-pivot-shaft")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_set_pin_holes_print_only_size_and_the_match_drill() -> None:
    # Option E-a: the strap sets the stations at assembly (back-flush, cluster
    # at the back stop), so the print carries the size and the match-drill
    # callout, never a station a floating length band would contradict.
    marked = set().union(*dt_pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    assert {"PinHoleDia"} <= marked
    assert not any(name.startswith("PinHole") and name.endswith("Z") for name in marked)
    callout = drawing.DIMENSION_CALLOUTS["PinHoleDia"]
    # The hole specification only (Main's re-ruling, 2026-09-26): the
    # drilling pose is MHA-DT-00's SHAFT DRILL SET, and the sheet points at
    # that step through the registry, so a renumbered sequence carries it
    # (Codex #858, PRRT_kwDOPHDy386mTbPB).  The pointer is sheet text: the
    # part's spec never reads the registry (Main's TbPB ruling 1).
    import _config
    import dt_drive_train_steps

    key = drawing.SHAFT_DRILL_STEP_KEY
    assert key == "straps-pinned-to-torque-shaft"
    assert dt_pinion_pivot_shaft_spec.PIN_HOLE_CALLOUT.split("\n") == [
        "MATCH-DRILL THRU AT ASSEMBLY",
        "IN MHA-DT-14 CROSS HOLES, 2 PL",
    ]
    pin = _config.parts("dt-vn-pinion-strap-pin")["number"]
    assert callout == (
        f"{dt_pinion_pivot_shaft_spec.PIN_HOLE_CALLOUT},\n"
        f"PRESS FIT FOR {pin} SPRING PIN,\n"
        f"PER {dt_drive_train_steps.step_ref(key)}"
    )
    assert "dt_drive_train_steps" not in Path(
        dt_pinion_pivot_shaft_spec.__file__
    ).read_text(encoding="utf-8")
    assert dt_pinion_pivot_shaft_spec.PIN_HOLE_DIA == 25.4 / 16.0
    assert dt_pinion_pivot_shaft_spec.PIN_HOLE_BAND == pytest.approx(
        (0.0025 * 25.4, 0.0)
    )


# The shared callout-placement helper (_drawing_annotation_extent), pinned
# offline with the read-backs of this sheet's earlier layout (pc-r7 eye pass:
# the cylindricity frame and datum A sat on the match-drill callout's text).
def test_callout_text_box_is_the_shoulder_span_mirrored_about_the_text_centre() -> None:
    import _drawing_annotation_extent as extent

    lines = [
        (0.068, 0.2227, 0.1156, 0.205),  # sloped leader down to the hole
        (0.066, 0.2227, 0.193, 0.2227),  # the shoulder under the text
        (0.100, 0.259, 0.104, 0.259),  # a short stacked-tolerance rule
    ]
    assert extent.callout_text_box(lines, (0.125, 0.241)) == pytest.approx(
        (0.066, 0.2227, 0.193, 0.2593)
    )
    with pytest.raises(RuntimeError, match="no shoulder"):
        extent.callout_text_box([lines[0]], (0.125, 0.241))


def test_the_callout_moves_above_the_ra_lane_and_right_of_the_end_view_frames(
    monkeypatch,
) -> None:
    import _drawing_annotation_extent as extent
    from _drawing_layout_check import DrawableRegion

    offset = [0.0, 0.0]
    text = (0.066, 0.2227, 0.193, 0.2593)

    def ink(_adapter, _annotation, *, label):
        dx, dy = offset
        box = (text[0] + dx, text[1] + dy, text[2] + dx, text[3] + dy)
        return extent.CalloutInk(label, box, ())

    def move(_adapter, _annotation, dx, dy, *, label):
        offset[0] += dx
        offset[1] += dy

    monkeypatch.setattr(extent, "callout_ink", ink)
    monkeypatch.setattr(extent, "move_annotation", move)
    monkeypatch.setattr(extent, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        extent, "sheet_region", lambda _a: DrawableRegion(0.0127, 0.0127, 0.419, 0.2667)
    )
    ra = (0.147, 0.205, 0.194, 0.223)
    frame = (0.063, 0.215, 0.085, 0.232)
    crown = (0.2455, 0.214, 0.262, 0.229)
    placed = extent.place_callout_clear(
        None,
        None,
        label="MHA-DT-19 match-drill callout",
        below={"Ra 1.6": ra},
        beside={"cylindricity frame": frame, "crown profile frame": crown},
    )
    lands = extent.CLEAR_GAP_M + extent.PLACE_SETTLE_M
    assert placed.text[1] == pytest.approx(ra[3] + lands)
    assert placed.text[0] == pytest.approx(frame[2] + lands)
    for box in (ra, frame, crown):
        assert extent.boxes_clear(placed.text, box)


def test_a_move_that_reads_back_a_hair_short_still_clears(monkeypatch) -> None:
    """Cold build #877 (swmaker000006, leaf 20260927T150045Z-1-3febc7c2): the
    callout was moved to exactly frame + CLEAR_GAP_M, read back a hair short
    of it, and the strict proof failed on a float.  The move lands a settle
    margin past the gap, so a read-back short by far less than that margin
    still proves clear at the full gap."""
    import _drawing_annotation_extent as extent
    from _drawing_layout_check import DrawableRegion

    short = 1e-9
    offset = [0.0, 0.0]
    text = (0.0870, 0.2281, 0.1614, 0.2539)

    def ink(_adapter, _annotation, *, label):
        dx, dy = offset
        box = (text[0] + dx, text[1] + dy, text[2] + dx, text[3] + dy)
        return extent.CalloutInk(label, box, ())

    def move(_adapter, _annotation, dx, dy, *, label):
        offset[0] += dx - short if dx else 0.0
        offset[1] += dy - short if dy else 0.0

    monkeypatch.setattr(extent, "callout_ink", ink)
    monkeypatch.setattr(extent, "move_annotation", move)
    monkeypatch.setattr(extent, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        extent, "sheet_region", lambda _a: DrawableRegion(0.0127, 0.0127, 0.419, 0.2667)
    )
    frame = (0.0587, 0.2150, 0.0853, 0.2320)  # the failing leaf's read-back

    def place():
        offset[:] = [0.0, 0.0]
        return extent.place_callout_clear(
            None,
            None,
            label="MHA-DT-19 match-drill callout",
            below={},
            beside={"cylindricity frame": frame},
        )

    placed = place()
    assert extent.boxes_clear(placed.text, frame)
    assert placed.text[0] - frame[2] > extent.CLEAR_GAP_M
    # Control: placed at exactly the gap, the same short read-back fails.
    monkeypatch.setattr(extent, "PLACE_SETTLE_M", 0.0)
    with pytest.raises(RuntimeError, match="crowds"):
        place()


class _LateBoundSheet:
    """A pywin32 dynamic dispatch: a zero-argument method is auto-invoked on
    attribute access (the value, not a callable) until ``_FlagAsMethod`` names
    it.  GetCurrentSheet hands one back on a seat (pc-858x928)."""

    def __init__(self) -> None:
        self.flagged: set[str] = set()

    def _FlagAsMethod(self, *names: str) -> None:
        self.flagged.update(names)

    def __getattr__(self, name: str):
        if name not in ("GetProperties", "GetProperties2"):
            raise AttributeError(name)
        value = (12.0, 12.0, 1.0, 1.0, 0.0, 0.4318, 0.2794, 1.0)
        if name in self.flagged:
            return lambda: value
        return value

    def GetZoneMargin(self, _side: int) -> float:
        return 0.0127


def test_the_sheet_region_reads_a_late_bound_sheet() -> None:
    import _drawing_annotation_extent as extent
    from types import SimpleNamespace

    sheet = _LateBoundSheet()
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet),
        _attempt=lambda call: call(),
    )
    region = extent.sheet_region(adapter)
    assert "GetProperties2" in sheet.flagged
    assert region.xmin == pytest.approx(0.0127)
    assert region.xmax == pytest.approx(0.4318 - 0.0127)
    assert region.ymax == pytest.approx(0.2794 - 0.0127)


def test_a_callout_too_long_to_fit_fails_loud_instead_of_re_colliding(
    monkeypatch,
) -> None:
    import _drawing_annotation_extent as extent
    from _drawing_layout_check import DrawableRegion

    monkeypatch.setattr(
        extent,
        "callout_ink",
        lambda _a, _n, *, label: extent.CalloutInk(
            label, (0.066, 0.23, 0.25, 0.26), ()
        ),
    )
    monkeypatch.setattr(extent, "move_annotation", lambda *_a, **_k: None)
    monkeypatch.setattr(extent, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        extent, "sheet_region", lambda _a: DrawableRegion(0.0127, 0.0127, 0.419, 0.2667)
    )
    with pytest.raises(RuntimeError, match="crowds"):
        extent.place_callout_clear(
            None,
            None,
            label="MHA-DT-19 match-drill callout",
            below={},
            beside={"crown profile frame": (0.2455, 0.214, 0.262, 0.265)},
        )
