"""Offline contracts for the pinion-return-leaf-spring drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_dt_pinion_spring as spring
import draw_dt_pinion_spring as drawing
import dt_pinion_spring_geometry as geometry
import dt_pinion_spring_section as section
import dt_pinion_spring_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_deviations

_XX_BAND = float(_config.title_block("linear_2pl")["value_in"]) * 25.4
_HOLE_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])
_WEB_TARGET = 2.0  # U27: machined webs >= 2.0 at the printed worst case


def test_spring_contact_rises_with_pivot_while_foot_stays_on_base() -> None:
    from dt_pinion_pivot_block_geometry import BORE_UP
    from pinion_rig_park_geometry import STRAP_LEAN_DEG

    assert geometry.PIVOT_LY == BORE_UP
    assert geometry.STRAP_LEAN_DEG == STRAP_LEAN_DEG
    assert geometry.FOOT_Y == geometry.THICK
    crest = (
        geometry.CREST[0] - geometry.PIVOT_LX,
        geometry.CREST[1] - geometry.PIVOT_LY,
    )
    station = sum(a * b for a, b in zip(crest, geometry.STRAP_U, strict=True))
    assert station == pytest.approx(geometry.CONTACT_T)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-spring_drawing.png")
    assert DRAWINGS_BY_NAME["dt_pinion_spring"].script == Path(drawing.__file__).resolve()
    assert "draw_dt_pinion_spring.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert spring.DRAWING_DIMENSIONS is dt_pinion_spring_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_spring_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (spring.FOOT_LEN, spring.THICK, spring.WIDTH) == (
        dt_pinion_spring_spec.FOOT_LEN,
        dt_pinion_spring_spec.THICK,
        dt_pinion_spring_spec.WIDTH,
    )


def test_every_formed_feature_carries_the_one_formed_band() -> None:
    # Main's r6 ruling (c): the hand-formed profile prints one place with a
    # +/-0.5 band; the blank's cut features ride the title-block .XX row.
    assert dt_pinion_spring_spec.FORMED_TOLERANCE_MM == 0.5
    assert model_toleranced_dimensions(spring) == {
        ("feature_name", "name"): "FORMED_TOLERANCE_MM"
    }
    formed = dt_pinion_spring_spec.FORMED_DIMENSIONS["SpringProfile"]
    precision = dt_pinion_spring_spec.DRAWING_PRECISION_BY_NAME
    assert {name: precision[name] for name in formed} == dict.fromkeys(formed, 1)
    for name in ("StripWidth", "PadWidth", "PadLen"):
        assert precision[name] == 2


def test_profile_is_baselined_from_the_foots_free_end() -> None:
    # Rule 7: the kink start and the tip locate from the free end, the one
    # feature the maker can put a rule on, never from the model origin.
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "KinkStartX" not in source and "FlatTipX" not in source
    free = dt_pinion_spring_spec.FORMED_DIMENSIONS[dt_pinion_spring_spec.FREE_FORM_SKETCH]
    assert free == {"FreeKinkH", "FreeKinkV", "FreeTipH"}
    assert set(drawing.DETAIL_KEEP) == {"KinkR", "FlatLen"}
    assert drawing.DETAIL_SCALE == (5, 1)


def test_pad_webs_clear_two_millimetres_at_the_printed_worst_case() -> None:
    radius = (geometry.HOLE_DIA + _HOLE_OVERSIZE) / 2.0
    width_min = geometry.PAD_WIDTH - _XX_BAND
    across = geometry.PAD_WIDTH / 2.0  # hole from the pad's lower edge
    side_near = across - _XX_BAND - radius
    side_far = width_min - (across + _XX_BAND) - radius
    end_web = geometry.HOLE_FROM_END - _XX_BAND - radius
    pad_web = (geometry.PAD_LEN - _XX_BAND) - (
        geometry.HOLE_FROM_END + _XX_BAND
    ) - radius
    webs = {"near side": side_near, "far side": side_far, "end": end_web}
    webs["toward the strip"] = pad_web
    assert min(webs.values()) >= _WEB_TARGET, webs


def test_hole_callout_picks_the_hole_rim_where_the_pad_puts_it() -> None:
    # pc-r11 (0c5636eab): the callout picked z HOLE_DIA/2, the rim of a hole on
    # the strip's centre plane.  The pad stands PAD_Z off it, so the point fell
    # inside the hole and SelectByID2 found no edge.  The pick must lie on the
    # rim of the hole the Hole Wizard places at the pad's centre.
    centre = (geometry.HOLE_X, geometry.FOOT_Y, geometry.PAD_Z)
    assert drawing.HOLE_CENTER == pytest.approx(centre)
    x, y, z = drawing.HOLE_EDGE_PICK
    assert (x, y) == pytest.approx(centre[:2])
    assert abs(z - centre[2]) == pytest.approx(geometry.HOLE_DIA / 2.0)
    assert abs(z - geometry.PAD_Z) < geometry.PAD_WIDTH / 2.0
    # Positive control: the pc-r11 pick is nowhere near the rim.
    stale = abs(geometry.HOLE_DIA / 2.0 - centre[2])
    assert geometry.HOLE_DIA / 2.0 - stale > 1.0


def test_screw_stands_outboard_east_of_the_back_strap() -> None:
    # 2026-09-24 re-derive: img01's far-left screw is on the DRUM side (east).
    # The base's seat is transferred from this hole: it stands 20.0 east of
    # the pivot bore, the pad and the bend wholly east of the strap flank.
    assert geometry.HOLE_X - geometry.PIVOT_LX == pytest.approx(20.0)
    flank = geometry.PIVOT_LX + geometry.STRAP_HALF_WIDTH
    assert geometry.FOOT_END[0] > geometry.HOLE_X > geometry.FOOT_TAN[0] > flank
    assert geometry.FOOT_END[0] - geometry.HOLE_X == geometry.HOLE_FROM_END
    assert geometry.FOOT_LEN == geometry.PAD_LEN + geometry.FOOT_FLAT


def test_blade_leans_in_to_its_flank_contact() -> None:
    # img04: the crest bears on the east flank about 5 below the arbor; img01
    # reads the blade about 11-13 deg to the flank, leaning in from the foot.
    assert geometry.CONTACT_T == 23.0
    assert 9.0 <= geometry.BLADE_TO_FLANK_DEG <= 13.0
    assert geometry.BLADE_LEAN_DEG > 0.0  # west of vertical, toward the strap
    assert geometry.KINK_START[0] < geometry.BEND_EXIT[0]


def test_free_form_presets_the_crest_into_the_flank() -> None:
    # O2: the part is the installed shape; the maker forms the free shape,
    # whose crest stands PRESET into the parked flank.  The band's low end
    # still leaves a preset.
    assert geometry.PRESET - geometry.FORMED_BAND_MM > 1.0
    assert geometry.FREE_KINK_START[0] < geometry.KINK_START[0]
    assert dt_pinion_spring_spec.FORMED_TOLERANCE_MM == geometry.FORMED_BAND_MM


def test_free_form_prints_from_the_hidden_reference_sketch() -> None:
    # O2 (a): the installed solid plus the FreeForm phantom; the free crest and
    # tip print from the hidden sketch, which the part blanks and the front
    # view shows through the opt-in hidden-sketch curation.
    assert dt_pinion_spring_spec.REFERENCE_SKETCHES == ("FreeForm",)
    build_source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "blank_sketch(adapter, FREE_FORM_SKETCH)" in build_source
    assert 'prefix="Free", construction=True' in build_source
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "hidden_sketches.curate_view_dimensions(" in draw_source
    assert {"FreeKinkH", "FreeKinkV", "FreeTipH"} <= set(drawing.FRONT_KEEP)
    assert "FREE FORM" in dt_pinion_spring_spec.DRAWING_NOTES


def test_front_qualifier_text_clears_its_rows_extension_lines() -> None:
    # pc-r12's render struck FREE, BEND and TANGENT through with the front
    # view's vertical extension lines: each qualified text now sits wholly
    # between or wholly outside the lines at its row.
    for name, lines in drawing.FRONT_ROW_EXTENSION_X.items():
        text = drawing.DIMENSION_CALLOUTS[name]
        half = drawing.QUALIFIER_HALF_WIDTH[text]
        x = drawing.FRONT_KEEP[name][0]
        crossed = [line for line in lines if x - half < line < x + half]
        assert not crossed, (name, text, crossed)
    assert set(drawing.FRONT_ROW_EXTENSION_X) == set(drawing.DIMENSION_CALLOUTS)
    # Positive control: pc-r12's centred kink-row text crossed both lines.
    old_x = drawing._front_x(drawing._FOOT_MID_X)
    half = drawing.QUALIFIER_HALF_WIDTH["FREE, TO KINK TANGENT"]
    assert all(
        old_x - half < line < old_x + half
        for line in drawing.FRONT_ROW_EXTENSION_X["FreeKinkH"]
    )


class _KinkView:
    """A recording IView double for the kink detail's place-move-crop."""

    def __init__(self, *, crop_status: int = 1, crops: bool = True, moves: bool = True):
        self.ScaleRatio = (5.0, 1.0)
        self.Position = (0.300, 0.100)
        self.crop_status = crop_status
        self.crops = crops
        self.moves = moves
        self.cropped = False
        self.calls: list[str] = []
        self.CropViewJaggedOutline = False
        self.CropViewNoOutline = False

    def SetViewPosition(self, target, _update) -> bool:  # noqa: N802
        self.calls.append("SetViewPosition")
        if self.moves:
            self.Position = tuple(float(value) for value in target)
        return True

    def GetOutline(self):  # noqa: N802
        if self.cropped:
            return (0.2225, 0.1665, 0.2575, 0.2015)
        return (0.180, 0.050, 0.300, 0.290)

    def Crop2(self, jagged, no_outline, intensity) -> int:  # noqa: N802
        self.calls.append(f"Crop2({jagged}, {no_outline}, {intensity})")
        self.cropped = self.crops
        return self.crop_status

    def IsCropped(self) -> bool:  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self) -> None:  # noqa: N802
        self.calls.append("UpdateViewDisplayGeometry")


class _KinkModel:
    def ClearSelection2(self, _all) -> None:  # noqa: N802
        pass

    def EditRebuild3(self) -> None:  # noqa: N802
        pass


def _kink_seat(monkeypatch, view: _KinkView) -> list[tuple]:
    """Point draw_pinion_spring's COM helpers at ``view``; returns the log of
    placements and crop circles."""
    log: list[tuple] = []
    # The focus sits a fixed sheet offset from the view's position.
    offset = (-0.050, 0.070)

    def place(_adapter, source, orientation, x, y, *, scale):
        log.append(("place", orientation, (x, y), scale))
        return view

    def model_point(_adapter, _view, point, *, label):
        assert point[:2] == pytest.approx(
            (drawing.DETAIL_FOCUS[0] / 1000.0, drawing.DETAIL_FOCUS[1] / 1000.0)
        )
        return (view.Position[0] + offset[0], view.Position[1] + offset[1])

    def circle(_adapter, _view, center, radius, *, label, add_to_db=False):
        log.append(("circle", center, radius, add_to_db))
        return object()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", model_point)
    monkeypatch.setattr(drawing, "_sketch_circle", circle)
    monkeypatch.setattr(drawing, "_activate_view", lambda *_a, **_k: "Drawing View4")
    return log


def _kink_adapter():
    return type("Adapter", (), {"currentModel": _KinkModel()})()


def _crop_kink(adapter, monkeypatch, view: _KinkView) -> list[tuple]:
    log = _kink_seat(monkeypatch, view)
    assert drawing._placed_kink_view(adapter) is view
    drawing._crop_kink_view(adapter, view)
    return log


def test_kink_detail_is_a_cropped_front_model_view(monkeypatch) -> None:
    # pc-r13 (leaf 20260927T001822Z-1-ba1f4546): the native detail's
    # targeted import brought KinkR but not FlatLen.  Detail A is now a *Front
    # model view at 5:1, its kink focus moved onto DETAIL_CENTER, cropped by
    # the fence's 5:1 circle with a plain circular outline.
    view = _KinkView()
    log = _crop_kink(_kink_adapter(), monkeypatch, view)
    assert log[0] == ("place", "*Front", drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)
    kind, center, radius, add_to_db = log[1]
    assert kind == "circle" and not add_to_db
    assert center == pytest.approx(drawing.DETAIL_CENTER, abs=1e-12)
    assert radius == pytest.approx(5 * drawing.DETAIL_RADIUS_MM / 1000.0)
    assert view.calls[0] == "SetViewPosition"
    assert "Crop2(False, False, 1)" in view.calls
    assert not hasattr(drawing, "_kink_detail")
    assert "CreateDetailViewAt4" not in Path(drawing.__file__).read_text(encoding="utf-8")


class _Annotation:
    def __init__(self, name: str) -> None:
        self.name = name


class _DimensionedView:
    def __init__(self) -> None:
        self.names: list[str] = []

    def GetAnnotations(self):  # noqa: N802
        return [_Annotation(name) for name in self.names]


def _order_seat(monkeypatch, view: _DimensionedView, *, crop_drops: tuple[str, ...]):
    """Record import, read-back and crop order on ``view``; the crop drops
    ``crop_drops`` from it.  Returns the call log and the recorded events."""
    calls: list[str] = []
    events: list[tuple[str, dict]] = []

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        calls.append("import")
        view.names = sorted(keep)
        return ["curated"]

    def crop(_adapter, _view):
        calls.append("crop")
        view.names = [name for name in view.names if name not in crop_drops]

    def names(_adapter, _view):
        calls.append("read")
        return sorted(view.names)

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_kink_view", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", names)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return calls, events


def test_kink_detail_is_dimensioned_before_it_is_cropped(monkeypatch) -> None:
    # pc-r14 (6aebefd18, leaf 20260927T005429Z-1-555a9662): imported into the
    # cropped view, SpringProfile brought FlatLen but not KinkR; the uncropped
    # *Front imports both.  The detail imports while uncropped, then crops,
    # and the pair is read back on both sides of the crop.
    view = _DimensionedView()
    calls, events = _order_seat(monkeypatch, view, crop_drops=())
    assert drawing._dimension_then_crop_kink_view(object(), view) == ["curated"]
    assert calls == ["import", "read", "crop", "read"]
    assert events == [
        (
            "kink_detail.crop",
            {
                "dimensions_before": "FlatLen,KinkR",
                "dimensions_after": "FlatLen,KinkR",
                "lost": "",
            },
        )
    ]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.index("_placed_kink_view(adapter)") < body.index(
        "_dimension_then_crop_kink_view(adapter, detail)"
    ) < body.index("keep=FRONT_KEEP")


def test_kink_detail_fails_loud_when_the_crop_takes_a_dimension(monkeypatch) -> None:
    view = _DimensionedView()
    calls, events = _order_seat(monkeypatch, view, crop_drops=("KinkR",))
    with pytest.raises(RuntimeError, match=r"lost \['KinkR'\] to its crop"):
        drawing._dimension_then_crop_kink_view(object(), view)
    assert events[0][1]["lost"] == "KinkR"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"crop_status": 0}, "not cropped"),
        ({"crops": False}, "not cropped"),
        ({"moves": False}, "kink focus sits at"),
    ],
)
def test_kink_detail_fails_loud_when_the_seat_does_not_obey(
    monkeypatch, kwargs, message
) -> None:
    view = _KinkView(**kwargs)
    with pytest.raises(RuntimeError, match=message):
        _crop_kink(_kink_adapter(), monkeypatch, view)


def test_kink_crop_holds_its_dimensions_and_labels_clear_of_them() -> None:
    # The crop circle is where pc-r12 printed the native detail's circle, so
    # the KinkR and FlatLen text positions tuned there still ride its edge.
    focus = drawing.DETAIL_FOCUS
    radius = drawing.DETAIL_RADIUS_MM
    flat_tip = geometry.FLAT_TIP
    kink_c = geometry.KINK_C
    # The flat's tip and the kink centre both sit inside the fence.
    assert ((flat_tip[0] - focus[0]) ** 2 + (flat_tip[1] - focus[1]) ** 2) ** 0.5 < radius
    assert ((kink_c[0] - focus[0]) ** 2 + (kink_c[1] - focus[1]) ** 2) ** 0.5 < radius
    crop_bottom = drawing.DETAIL_CENTER[1] - drawing.DETAIL_CROP_RADIUS
    assert drawing.DETAIL_LABEL_XY[0] == drawing.DETAIL_CENTER[0]
    assert drawing.DETAIL_LABEL_XY[1] < crop_bottom
    assert drawing.DETAIL_LABEL_TEXT == "DETAIL A\nSCALE 5 : 1"
    # KinkR rides above-left of the circle, FlatLen right of it: neither
    # reaches down to the label.
    for name in ("KinkR", "FlatLen"):
        assert drawing.DETAIL_KEEP[name][1] > drawing.DETAIL_LABEL_XY[1]
    # The fence letter goes west of the front view's fence.
    assert drawing.PARENT_LETTER_OFFSET[0] < -drawing.DETAIL_RADIUS_MM * drawing._S
    assert drawing.PARENT_LETTER_OFFSET[1] == 0.0


def test_views_are_projected_and_hidden_lines_removed() -> None:
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "add_feature_control_frame" not in source
    assert "add_datum_feature" not in source
    assert "process=HOLE_PROCESS" in source
    assert drawing.HOLE_PROCESS == "#30 DRILL"
    assert geometry.HOLE_DIA == pytest.approx(0.1285 * 25.4, abs=1e-3)  # No. 30 drill
    assert source.count("add_edge_dimension(") == 1  # the two hole locations


def test_bend_coupon_qualifies_the_tightest_accepted_radius() -> None:
    # Codex #859 (PRRT_kwDOPHDy386mTao0): both R3.3 bends may be formed at
    # R3.3 - band, so the mandatory coupon bends over that low limit or under
    # it, never the nominal.  The mandrel is a 7/32 in drill rod.
    policy = (Path(__file__).parents[1] / "docs" / "tolerance-policy.md").read_text(
        encoding="utf-8"
    )
    mandrel_r = 7.0 / 32.0 * 25.4 / 2.0
    assert "7/32 in (Ø5.56) drill-rod mandrel, R2.78" in policy
    assert round(mandrel_r, 2) == 2.78
    low_limit = min(geometry.R_BEND, geometry.R_KINK) - geometry.FORMED_BAND_MM
    assert mandrel_r <= low_limit
    # Positive control: the nominal R3.3 mandrel the coupon used to name misses it.
    assert geometry.MIN_INSIDE_BEND_R > low_limit


def test_notes_carry_no_dimension_and_stay_short() -> None:
    notes = dt_pinion_spring_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert "TEMPLATE" in notes and "FORM" in notes
    assert "COIL" not in notes
    # The blank's orientation is the coupon's (Codex #859, PRRT_kwDOPHDy386mTtoA).
    assert "ALONG ROLL LENGTH (BENDS ACROSS ROLLING DIRECTION)" in notes
    policy = (Path(__file__).parents[1] / "docs" / "tolerance-policy.md").read_text(
        encoding="utf-8"
    )
    assert "bend line across the rolling direction, as the part is cut" in policy
    assert max(len(line) for line in notes.splitlines()) <= 63
    assert not any(ch.isdigit() for ch in notes)
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    spec = _config.parts("dt-pinion-spring")
    # The title-block cell holds one line (<= 30 characters); the full
    # stock callout stays in the material specification.
    assert len(spec["material"]) <= 30
    assert "17-7 PH" in spec["material"] and "Cond C" in spec["material"]
    assert "0.015 in (0.381 mm)" in spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_registry_names_the_stock_the_section_models() -> None:
    # #859 ruling 4: 17-7 PH Condition C, 0.015 in, McMaster-Carr 2325K19
    # (+/-0.00075 in on the vendor page), sheared 1/4 in wide.  The width is a
    # sheared, .XX-printed dimension, so its band is the title block's.
    spec = _config.parts("dt-pinion-spring")["material_specification"]
    assert "McMaster-Carr 2325K19" in spec and "ASTM A693" in spec
    assert "Condition C" in spec and "+/-0.00075 in" in spec
    assert section.THICK == pytest.approx(0.015 * 25.4)
    assert section.THICK_BAND == pytest.approx((0.00075 * 25.4, -0.00075 * 25.4))
    assert section.WIDTH == pytest.approx(0.25 * 25.4)
    assert printed_deviations(section.WIDTH, section.WIDTH_PLACES) == pytest.approx(
        (-_XX_BAND, _XX_BAND), abs=0.005
    )
    assert dt_pinion_spring_spec.DRAWING_PRECISION_BY_NAME["StripWidth"] == 2
    assert spring.MATERIAL == "AISI 304"  # the library's stainless stand-in


def test_every_inside_radius_meets_the_17_7_ph_bend_minimum() -> None:
    # No 17-7 PH source publishes a Condition C bend radius; the proxy is NASA
    # SP-5089 (1968) Table XXXI, 17-7 PH (STA) 0.012-0.016 in: R 0.13 in.
    # Condition C is less ductile than STA, so the bend trial is still due
    # (cad/docs/tolerance-policy.md).
    proxy = 0.13 * 25.4
    assert min(geometry.R_BEND, geometry.R_KINK) >= proxy - 1e-9
    assert geometry.MIN_INSIDE_BEND_R == pytest.approx(proxy)
    # The larger bend keeps the blade inside O5's 9-13 deg only with the bend
    # starting at the pad's edge.
    assert geometry.FOOT_FLAT == 0.0
