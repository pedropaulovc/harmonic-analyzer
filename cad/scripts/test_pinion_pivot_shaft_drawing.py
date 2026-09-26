"""Offline contracts for the pinion-torque-shaft drawing."""

from __future__ import annotations

import pytest
from pathlib import Path

import pinion_pivot_shaft_spec
import draw_pinion_pivot_shaft as drawing
import build_pinion_pivot_shaft as shaft
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pinion_pivot_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_pivot_shaft_spec.SHAFT_DIA
    part_source = Path(shaft.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-pivot-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_pivot_shaft"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert shaft.DRAWING_DIMENSIONS is pinion_pivot_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.SHAFT_DIA == pinion_pivot_shaft_spec.SHAFT_DIA
    assert drawing.SHAFT_LEN == pinion_pivot_shaft_spec.SHAFT_LEN


def test_sheet_runs_at_1_to_1_with_2_to_1_end_view_and_1_to_2_iso() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1, 2)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(4, 1)" in source  # the end-view override
    assert pinion_pivot_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_pivot_shaft_spec.DRAWING_NOTES
    assert "SPHERICAL CROWN" in notes
    assert "DERIVED AXIS" in notes
    assert "PROFILE 0.05, FORM ONLY (NO DATUM)" in notes
    assert "EXEMPT FROM TITLE-BLOCK EDGE-BREAK" in notes
    assert "(1.20) REF AXIAL HEIGHT" in notes
    assert "1.20+/-0.05" not in notes
    assert "194.40 OVERALL" not in notes
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == "FINAL SIZE"
    assert model_toleranced_dimensions(shaft) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }
    # U27: the length reads the title-block .X band, not a tight tolerance.
    assert pinion_pivot_shaft_spec.DRAWING_PRECISION == {
        "Shaft": {"Depth": 1},
        "PinHoleProfile": {"PinHoleDia": 2},
    }
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_direct_limits_and_native_cylindricity_control_the_body() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert "edge_xy=end_top" in source
    assert "symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024)" in source
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="BOTH CROWNS"' in source
    assert 'entity_type="FACE"' in source
    assert 'entity_type="SILHOUETTE"' not in source
    assert "add_surface_finish(" in source
    assert "CYLINDRICITY" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "Ra 1.6" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "CROWN ROOT CIRCLES" in drawing.DIMENSION_CALLOUTS["Depth"]
    # Main eye pass on pc-ea2: under the end view the diameter's leader ran
    # back through its own stacked "-0.02".  Clear left of the end view the
    # leader rises right from the underline and crosses no tolerance text.
    text_x, text_y = drawing.FRONT_KEEP["ShaftDia"]
    end_view_left = (
        drawing.FRONT_CENTER[0]
        - drawing.END_VIEW_SCALE * pinion_pivot_shaft_spec.SHAFT_DIA / 2.0 / 1000.0
    )
    assert text_x < end_view_left
    assert text_y < drawing.FRONT_CENTER[1]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(shaft.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-pivot-shaft")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_set_pin_holes_print_only_size_and_the_match_drill() -> None:
    # Option E-a: the strap sets the stations at assembly (back-flush, cluster
    # at the back stop), so the print carries the size and the match-drill
    # callout, never a station a floating length band would contradict.
    marked = set().union(*pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    assert {"PinHoleDia"} <= marked
    assert not any(name.startswith("PinHole") and name.endswith("Z") for name in marked)
    callout = drawing.DIMENSION_CALLOUTS["PinHoleDia"]
    assert callout is pinion_pivot_shaft_spec.PIN_HOLE_CALLOUT
    assert "MATCH-DRILL THRU AT ASSEMBLY" in callout
    assert "MHA-056" in callout
    assert "2 PL" in callout
    assert pinion_pivot_shaft_spec.PIN_HOLE_DIA == 25.4 / 16.0
    assert pinion_pivot_shaft_spec.PIN_HOLE_BAND == (0.06, 0.0)


# pc-r7 eye pass: the cylindricity frame and datum A sat on the match-drill
# callout's text and the Ra bar on its shoulder.  The callout is placed from
# the symbols' read-back boxes (_drawing_annotation_extent), and these pin the
# arithmetic and the wiring offline.
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
        label="MHA-062 match-drill callout",
        below={"Ra 1.6": ra},
        beside={"cylindricity frame": frame, "crown profile frame": crown},
    )
    assert placed.text[1] == pytest.approx(ra[3] + extent.CLEAR_GAP_M)
    assert placed.text[0] == pytest.approx(frame[2] + extent.CLEAR_GAP_M)
    for box in (ra, frame, crown):
        assert extent.boxes_clear(placed.text, box)


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
            label="MHA-062 match-drill callout",
            below={},
            beside={"crown profile frame": (0.2455, 0.214, 0.262, 0.265)},
        )


def test_the_match_drill_callout_is_placed_from_every_neighbours_read_back_box() -> (
    None
):
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    call = source[source.index("place_callout_clear(") :]
    call = call[: call.index("add_property_linked_note")]
    assert '== "PinHoleDia"' in call
    for handle in ("bearing_finish", "cylindricity", "datum_a", "crown_profile"):
        assert f"{handle}.GetAnnotation()" in call
    assert call.index("below=") < call.index("bearing_finish") < call.index("beside=")
