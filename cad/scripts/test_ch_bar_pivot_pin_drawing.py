"""Offline contracts for the bar pivot pin (MHA-CH-11) part and drawing.

The installed pressed pin under ``cad/docs/drawing-guidelines.md``: three
native model dimensions whose places (and the diameter's band) the PART owns,
the installed length as REFERENCE, the blank under the title block's band,
the mates and the stock named at the diameter, no GD&T, no roughness symbol,
and one note line.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_bar_pivot_pin as part
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_notes as notes
import ch_bar_pivot_pin_spec as spec
import ch_channel_lever_spec as lever
import draw_ch_bar_pivot_pin as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-bar-pivot-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-bar-pivot-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-bar-pivot-pin_drawing.png")
    entry = DRAWINGS_BY_NAME["ch_bar_pivot_pin"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "ch_bar_pivot_pin"
    assert part.PART_NAME == entry.artifact_stem == "ch-bar-pivot-pin"


def test_installed_model_is_flush_with_the_bar() -> None:
    assert spec.PIN_INSTALLED_LENGTH == bar.BAR_WIDTH
    assert part.HALF_LEN == pytest.approx(bar.BAR_WIDTH / 2.0)
    assert part.V_PIN == pytest.approx(
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * bar.BAR_WIDTH
    )


def test_pin_axis_and_mid_plane_contract() -> None:
    build = _build_source()
    # Axis1 = part X (Top x Front), centred on the origin: the Right Plane is
    # the pin's axial mid-plane, which the assembly lands on the bar's.
    assert 'name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0' in build
    assert 'create_sketch("Front")' in build
    assert '"pin centred on origin"' in build
    assert "RevolveParameters(angle=360.0)" in build
    assert "volume_check(" in build
    assert "create_configuration" not in build  # one INSTALLED configuration


def test_notes_module_is_the_single_source_of_the_marked_dimension_set() -> None:
    """The drawing contract lives in ch_bar_pivot_pin_notes, out of the spec
    the channel assembly and the fit test import."""
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "REFERENCE_DIMENSIONS"):
        assert not hasattr(spec, name), name
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"PinDia", "PinLen", "BlankLen"}
    assert notes.REFERENCE_DIMENSIONS == {"PinLen"}
    assert not hasattr(drawing, "RIGHT_KEEP")


def test_blank_length_is_a_model_dimension_on_a_hidden_sketch() -> None:
    """Machinist round 1 (#1305): the blank length sat in a note. It prints
    from the part's blanked BlankReference sketch (the rod-pin pattern).
    Round 2: its only job is to stand proud of both faces before dressing,
    so it takes the title block's band, not a tighter one of its own; the
    ch-channel-lever r5 review moved it off .XX; on the inch sheet the .X band
    (+/-.1) would let it fall short of the bar, so it prints .30 under .XX."""
    from _printed_tolerance import printed_band_mm

    build = _build_source()
    assert notes.DRAWING_DIMENSIONS["BlankReference"] == {"BlankLen"}
    assert 'set_global(adapter, "BlankLen", f"{PIN_BLANK_LENGTH}mm")' in build
    assert 'blank.record("BlankLen", \'"BlankLen"\')' in build
    assert 'blank_reference_sketches(adapter, ("BlankReference",))' in build
    assert "hidden_sketches.curate_view_dimensions(" in _source()
    places = notes.DRAWING_PRECISION["BlankReference"]["BlankLen"]
    assert places == spec.PIN_BLANK_LENGTH_PLACES
    band = printed_band_mm(places, unit=spec.UNIT)
    assert spec.PIN_BLANK_LENGTH_BAND == (band, -band)
    assert spec.BUDGET["blank_excess_min"] > 0.0
    assert drawing.FRONT_KEEP["BlankLen"][1] < drawing.FRONT_KEEP["PinLen"][1] - 0.015


def test_blank_ends_run_from_the_pin_corners_to_the_blank_length() -> None:
    """ENFORCE review 2026-10-23: the 7.5 BLANK witnesses rose from empty
    space past the installed outline. The blank's two ends (construction
    geometry, drawn dashed on the sheet) leave the installed pin's corners,
    stand at the blank's cut length, span its diameter, and lie wholly
    outside the installed outline, so the cut length has drawn geometry to
    dimension between."""
    pin_r, half_len = spec.PIN_DIA / 2.0, spec.PIN_INSTALLED_LENGTH / 2.0
    chains = part.BLANK_END_CHAINS
    assert set(chains) == {"left", "right"}
    end_xs = []
    for side, sign in (("left", -1.0), ("right", 1.0)):
        start, top, bottom, finish = chains[side]
        assert start == pytest.approx((sign * half_len, pin_r))
        assert finish == pytest.approx((sign * half_len, -pin_r))
        # Stubs along the pin's edges, the end line square across them.
        assert start[1] == top[1] and bottom[1] == finish[1]
        assert top[0] == bottom[0]
        assert top[1] - bottom[1] == pytest.approx(spec.PIN_DIA)
        assert abs(top[0]) > half_len
        end_xs.append(top[0])
    assert end_xs[1] - end_xs[0] == pytest.approx(spec.PIN_BLANK_LENGTH)
    assert end_xs[0] == pytest.approx(-end_xs[1])


def test_precision_and_band_are_authored_on_the_part() -> None:
    assert "draw_ch_bar_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()
    # The diameter is the as-bought drill rod: no model band (its stock
    # fraction prints as a REFERENCE; the supplier's grind governs).
    assert model_toleranced_dimensions(part) == {}


def test_print_carries_no_gdt_or_roughness() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_one_note_and_the_mates_at_their_dimensions() -> None:
    """Machinist round 1 (#1305): the press/punch line was a method, the
    flush dressing assembly wording, and the mates sat away from the Ø they
    govern; the drill-rod stock explains the tight grind band. Each now rides
    its dimension; one note says what the views show."""
    assert "PUNCH" not in notes.DRAWING_NOTES and "DRESS" not in notes.DRAWING_NOTES
    source = _source()
    # r1: SOLIDWORKS printed nothing of a multi-line callout above a value.
    assert 'location="above"' not in source
    assert source.count("set_dimension_callouts(") == 1
    # The installed length's callout stays inside the pin's 10:1 length
    # (~2.5 mm a character at the sheet's text height), clear of both rows'
    # witnesses.
    pin_len_on_sheet = 2.0 * drawing.HALF_LEN
    assert len(notes.DIMENSION_CALLOUTS["PinLen"]) * 0.0025 < pin_len_on_sheet - 0.006
    # The diameter's three-line callout hangs clear of the pin's outline.
    assert drawing.FRONT_KEEP["PinDia"][1] - 4 * 0.0045 > (
        drawing.FRONT_CENTER[1] + drawing.HALF_DIA + 0.002
    )
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_in_the_callouts_are_live() -> None:
    assert _config.parts("ch-amplitude-bar")["number"] == notes.BAR_NUMBER
    assert _config.parts("ch-channel-lever")["number"] == notes.LEVER_NUMBER
    assert str(lever.BAR_PIN_HOLE_SPEC.size).lstrip("#") == "47"


def test_sheet_runs_at_10_to_1_and_lands_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert drawing.VIEW_SCALE == (10, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    (dia_x, dia_y) = drawing.FRONT_KEEP["PinDia"]
    assert dia_y > drawing.FRONT_CENTER[1] + drawing.HALF_DIA
    assert dia_x < drawing.FRONT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.FRONT_KEEP["PinLen"][1] < drawing.FRONT_CENTER[1] - drawing.HALF_DIA
    for x, y in (*drawing.FRONT_KEEP.values(), drawing.NOTES_XY):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    # Third-angle: the end view projects right of the side view on its Y.
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_LEN
        < drawing.RIGHT_CENTER[0] - drawing.HALF_DIA - 0.010
    )
    assert (
        drawing.RIGHT_CENTER[0] + drawing.HALF_DIA
        < drawing.ISO_CENTER[0] - drawing.HALF_LEN - 0.010
    )


class _Display:
    def __init__(self, keeps: bool) -> None:
        self.keeps = keeps
        self._side = 2  # swDimArrowsSmart

    @property
    def ArrowSide(self) -> int:  # noqa: N802 - the COM member name
        return self._side

    @ArrowSide.setter
    def ArrowSide(self, value: int) -> None:  # noqa: N802 - the COM member name
        if self.keeps:
            self._side = value


class _Annotation:
    def __init__(self, name: str, keeps: bool = True) -> None:
        self.name = name
        self.display = _Display(keeps)

    def GetSpecificAnnotation(self) -> _Display:  # noqa: N802 - the COM member name
        return self.display


def test_installed_length_holds_its_arrows_inside(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """r2 layout audit: the installed length's smart arrows stood outside its
    span and crossed the blank's extension lines 3.25 mm beyond each end."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, a: a.name)
    assert drawing.ARROWS_INSIDE == ("PinLen",)
    annotations = [
        _Annotation("PinDia"),
        _Annotation("PinLen"),
        _Annotation("BlankLen"),
    ]
    drawing._set_arrows_inside(None, annotations)
    assert [a.display.ArrowSide for a in annotations] == [2, 0, 2]
    with pytest.raises(RuntimeError, match="did not keep its arrows inside"):
        drawing._set_arrows_inside(None, [_Annotation("PinLen", keeps=False)])
    with pytest.raises(RuntimeError, match="no pin dimension"):
        drawing._set_arrows_inside(None, [_Annotation("PinDia")])
    assert "_set_arrows_inside(adapter, front_annotations)" in _source()


def test_part_registry_row() -> None:
    config = _config.parts("ch-bar-pivot-pin")
    assert config["number"] == "MHA-CH-11"
    assert int(config["quantity"]) == 20
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert config["process"] == (
        "cut from drill rod; pressed into the bar at assembly, ends dressed flush"
    )
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36
