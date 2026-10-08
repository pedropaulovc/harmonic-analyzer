"""Offline contracts for the cone post bond cradle (MHA-DT-005-TL-01)."""

from __future__ import annotations

import math
import re

import _config
import draw_dt_cone_pivot_post_tl_bond_cradle as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_bond_cradle_spec as spec
import export_features
from _printed_tolerance import printed_band_mm
from prechips.model import TOLERANCE_REQUIREMENTS

STEM = "dt_cone_pivot_post_tl_bond_cradle"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    views = (
        drawing.PLAN_KEEP,
        drawing.ELEVATION_KEEP,
        drawing.SECTION_A_KEEP,
        drawing.SECTION_B_KEEP,
    )
    printed = [name for view in views for name in view]
    assert len(printed) == len(set(printed))
    assert set(printed) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set(printed)
    assert set(drawing.DIMENSION_CALLOUTS) <= set(printed)


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("dt-cone-pivot-post")["number"]
    number = _config.parts("dt-cone-pivot-post-tl-bond-cradle")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy_and_permit_the_built_up_blocks() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert spec.BUILT_UP_PERMISSION_NOTE in lines
    assert export_features.requirement_manifest(STEM)["construction"] == "built_up_permitted"


def test_seats_take_the_post_body_and_its_raw_tail_on_one_axis() -> None:
    features = _features()
    assert features["body_seat"]["dia_nominal"] >= post.BLOCK_DIA
    assert spec.TAIL_SEAT_DIA > spec.BODY_SEAT_DIA
    assert features["body_seat"]["axis"] == features["tail_seat"]["axis"] == [0.0, 1.0, 0.0]
    # Both seats sit below the saddle tops: the post lies in them, not on them.
    assert spec.BLOCK_TOP_Z > -spec.TAIL_SEAT_DIA / 2.0 > spec.BASE_TOP_Z


def test_seats_are_matched_fits_without_a_hidden_diameter_band() -> None:
    features = _features()
    for key, callout in (
        ("body_seat", drawing.BODY_SEAT_CALLOUT),
        ("tail_seat", drawing.TAIL_SEAT_CALLOUT),
    ):
        seat = features[key]
        # The callout prints as the exported fit note; no diameter limits
        # ride behind the reference size.
        assert "dia" not in seat
        assert "note" in seat["requirements"]
        assert seat["note"] == callout
        flat = " ".join(callout.split())
        assert f"{spec.POST_NUMBER} CONE PIVOT POST" in flat
        assert "WITHOUT SHAKE" in flat


def test_pin_tops_print_from_the_post_axis_within_a_quarter_of_the_post_band() -> None:
    features = _features()
    crank_band = 0.51  # CrankBossStartZ at .XX
    cone_band = 0.51 / 2.0  # the north cap: half the .XX ConeBossLen
    for name, nominal, post_band in (
        ("crank_pin_west", post.CRANK_BOSS_NORTH_FACE, crank_band),
        ("crank_pin_east", post.CRANK_BOSS_NORTH_FACE, crank_band),
        ("cone_pin_east", post.CONE_BOSS_LENGTH / 2.0, cone_band),
        ("cone_pin_west", post.CONE_BOSS_LENGTH / 2.0, cone_band),
    ):
        pin = features[name]
        # One relation to the seat axis, no chain through the base top.
        assert pin["height_from"] == "body_seat"
        low, high = pin["height"]
        # The explicit band rides on the PRINTED nominal, so its limits are
        # the sheet's own numbers (21.38 +/-0.12 -> [21.26, 21.50]).
        printed = round(nominal, spec.PIN_TOP_PLACES)
        assert pin["height_nominal"] == printed
        assert math.isclose((low + high) / 2.0, printed)
        assert [round(low, spec.PIN_TOP_PLACES), round(high, spec.PIN_TOP_PLACES)] == [low, high]
        assert 0.0 < (high - low) / 2.0 <= 0.25 * post_band + 1e-12


def test_crank_pins_carry_the_crank_sleeve_north_face() -> None:
    for name in ("crank_pin_west", "crank_pin_east"):
        pin = _features()[name]
        assert abs(pin["at"][2] + post.CRANK_BOSS_NORTH_FACE) <= spec.PIN_TOP_ROUNDING
        assert math.isclose(pin["at"][1], post.CRANK_BORE_HEIGHT)


def test_cone_pin_tops_bear_on_the_north_cap_annulus_either_side_of_the_journal() -> None:
    cap = post.SURFACE_FINISHES[3].face
    across = []
    for name in ("cone_pin_east", "cone_pin_west"):
        pin = _features()[name]
        # Top centre on the cap plane, axis anti-parallel to the cap's normal.
        signed = sum(a * n for a, n in zip(pin["at"], cap.normal, strict=True))
        assert abs(signed - cap.offset_mm) <= spec.PIN_TOP_ROUNDING
        assert all(
            math.isclose(a, -n, abs_tol=1e-12)
            for a, n in zip(pin["axis"], cap.normal, strict=True)
        )
        # Off the journal axis, onto the cap between the bore and the rim: a
        # top on the axis would sit over the bore.
        rel = (pin["at"][0], pin["at"][1] - post.BORE_HEIGHT, pin["at"][2])
        along = sum(r * a for r, a in zip(rel, pin["axis"], strict=True))
        radial = [r - along * a for r, a in zip(rel, pin["axis"], strict=True)]
        assert post.BORE_DIA / 2.0 < math.hypot(*radial) < post.CONE_BOSS_DIA / 2.0
        across.append(radial)
    # Opposite sides, equally: the tops straddle the journal axis.
    assert all(math.isclose(e, -w, abs_tol=1e-9) for e, w in zip(*across, strict=True))


def test_cone_pin_tops_carry_their_mutual_match() -> None:
    for name in ("cone_pin_east", "cone_pin_west"):
        assert _features()[name]["note"] == spec.CONE_PIN_TOPS_NOTE
    assert drawing.DIMENSION_CALLOUTS["ConePinFromAxis"].replace("\n", " ") == (
        "2X " + spec.CONE_PIN_TOPS_NOTE
    )


def test_every_exported_band_is_a_requirement() -> None:
    """prechips inspects only the bands a feature lists."""
    for name, feature in _features().items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list) and len(value) == 2:
                assert key in feature["requirements"], (name, key)


# Each printed dimension -> the exported feature and requirement owning its
# band. The seat diameters are matched fits (reference sizes; the fit note
# is the requirement) and the pin diameter names the stock dowel.
PRINTED_OWNERS = {
    "BaseLength": ("base_far_end", "length"),
    "BaseWidth": ("base_east_side", "width"),
    "BaseThick": ("base_top", "thickness"),
    "StopHeight": ("stop_top", "height"),
    "StopThick": ("foot_stop", "thickness"),
    "StopWidth": ("stop_east_side", "width"),
    "StopSideX": ("stop_west_side", "width"),
    "BodySaddleHeight": ("saddle_tops", "height"),
    "TailSaddleHeight": ("saddle_tops", "height"),
    "BodySaddleThick": ("body_saddle_north", "thickness"),
    "BodySaddleY": ("body_saddle_south", "station"),
    "TailSaddleThick": ("tail_saddle_north", "thickness"),
    "TailSaddleY": ("tail_saddle_south", "station"),
    "SaddleWidth": ("saddle_east_sides", "width"),
    "SaddleSideX": ("saddle_west_sides", "width"),
    "CrankPinY": ("crank_pin_west", "station"),
    "CrankPinWestX": ("crank_pin_west", "width"),
    "CrankPinEastX": ("crank_pin_east", "width"),
    "CrankPinFromAxis": ("crank_pin_east", "height"),
    "ConePinY": ("cone_pin_east", "station"),
    "ConePinEntryEastX": ("cone_pin_east", "width"),
    "ConePinEntryWestX": ("cone_pin_west", "width"),
    "ConePinFromAxis": ("cone_pin_west", "height"),
    "BodySeatAxisX": ("body_seat", "width"),
    "BodySeatAxisHeight": ("body_seat", "height"),
    "TailSeatAxisX": ("tail_seat", "width"),
    "TailSeatAxisHeight": ("tail_seat", "height"),
}
BAND_EXEMPT = {"BodySeatDia", "TailSeatDia", "CrankPinDia"}


def test_every_printed_dimension_has_a_band_owner_at_its_printed_limits() -> None:
    """A dimension printed but not exported as a listed requirement band goes
    uninspected: every printed linear dimension reaches prechips at the
    sheet's own limits."""
    angular = {"ConePinTilt"}
    assert set(PRINTED_OWNERS) | BAND_EXEMPT | angular == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features()
    for printed, (name, key) in PRINTED_OWNERS.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        assert feature["precision"][key] == places, printed
        low, high = feature[key]
        printed_nominal = round(feature[f"{key}_nominal"], places)
        # General-grade bands sit on the printed nominal at its places.
        if printed not in {"CrankPinFromAxis", "ConePinFromAxis"}:
            band = printed_band_mm(places)
            assert [low, high] == [
                round(printed_nominal - band, 12),
                round(printed_nominal + band, 12),
            ], printed
        assert low < printed_nominal < high, printed


def test_cone_pin_tilt_and_seat_finishes_are_requirements() -> None:
    features = _features()
    tol = float(_config.title_block("angular")["value_deg"])
    for name in ("cone_pin_east", "cone_pin_west"):
        pin = features[name]
        assert "land_angle_deg" in pin["requirements"]
        assert pin["land_angle_deg"] == [12.5 - tol, 12.5 + tol]
        assert "angle_deg" not in pin["requirements"]
    for control in spec.SURFACE_FINISHES:
        seat = features[control.key]
        assert "finish_ra" in seat["requirements"]
        assert seat["finish_ra"] == control.roughness_um


def test_every_band_carries_a_printed_nominal_inside_it() -> None:
    """prechips refuses a nominal outside its band: every listed band carries
    a nominal that is the printed value, at the band's places, within it."""
    for name, feature in _features().items():
        for key in feature["requirements"]:
            band = feature[key]
            if not (isinstance(band, list) and len(band) == 2):
                continue
            nominal_key = "land_angle_nominal_deg" if key == "land_angle_deg" else f"{key}_nominal"
            assert nominal_key in feature, (name, key)
            value = feature[nominal_key]
            low, high = band
            assert low <= value <= high, (name, nominal_key, value, band)
            assert value == round(value, feature["precision"][key]), (name, nominal_key)
