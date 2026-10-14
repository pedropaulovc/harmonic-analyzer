"""Offline contracts for the rocker arm hub filing kit (MHA-CH-006-TL-04/-05)."""

from __future__ import annotations

import re

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_button_spec as button
import ch_rocker_arm_tl_filing_stud_spec as stud
import draw_ch_rocker_arm_tl_filing_button as button_drawing
import draw_ch_rocker_arm_tl_filing_stud as stud_drawing
import export_features
import pytest
from _printed_limits import limits
from prechips.model import TOLERANCE_REQUIREMENTS

BUTTON = "ch_rocker_arm_tl_filing_button"
STUD = "ch_rocker_arm_tl_filing_stud"


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def test_every_marked_dimension_prints_once() -> None:
    marked = set().union(*button.DRAWING_DIMENSIONS.values())
    assert set(button_drawing.FACE_KEEP) | set(button_drawing.EDGE_KEEP) == marked
    assert not set(button_drawing.FACE_KEEP) & set(button_drawing.EDGE_KEEP)
    marked = set().union(*stud.DRAWING_DIMENSIONS.values())
    assert set(stud_drawing.PROFILE_KEEP) | set(stud_drawing.DONOR_KEEP) == marked
    assert not set(stud_drawing.PROFILE_KEEP) & set(stud_drawing.DONOR_KEEP)
    assert set(stud_drawing.PROFILE_DIAMETER_XY) == set(stud_drawing.DONOR_KEEP)


def test_rim_is_the_hub_filing_line() -> None:
    """The filed hub ends at the rim: every button the band allows lies inside
    the hub's printed O.D. band."""
    low, high = _features(BUTTON)["rim"]["dia"]
    hub_low, hub_high = limits(rocker.HUB_DIA, 2)
    assert hub_low <= low < high <= hub_high
    assert low < rocker.HUB_DIA < high


def test_matched_fits_export_the_printed_reference_and_fit_note() -> None:
    """One fact, one source: the print shows the bore and locating diameter
    as references governed by a fit callout, so features.toml carries that
    nominal and that callout text, never a tighter hidden band."""
    for feature, nominal, callout in (
        (
            _features(BUTTON)["bore"],
            button.BORE_DIA,
            button.REFERENCE_CALLOUTS["BoreDia"],
        ),
        (
            _features(STUD)["locating_body"],
            stud.BODY_DIA,
            stud.REFERENCE_CALLOUTS["BodyDia"],
        ),
    ):
        assert "dia" not in feature
        assert feature["dia_nominal"] == nominal
        assert "WITHOUT SHAKE" in feature["note"]
        assert feature["note"] == " ".join(part for part in callout if part)


@pytest.mark.parametrize("stem", [BUTTON, STUD])
def test_every_exported_band_is_a_requirement(stem: str) -> None:
    """One-fact rule: prechips inspects only the bands a feature lists."""
    for name, feature in _features(stem).items():
        for key, value in feature.items():
            if key in TOLERANCE_REQUIREMENTS and isinstance(value, list):
                assert key in feature["requirements"], (name, key)


@pytest.mark.parametrize("stem", [BUTTON, STUD])
def test_every_exported_nominal_lies_inside_its_band(stem: str) -> None:
    """prechips rejects a nominal outside its requirement band; references
    under a fit callout export a nominal with no band."""
    for name, feature in _features(stem).items():
        for key, nominal in feature.items():
            if not key.endswith("_nominal"):
                continue
            band = feature.get(key.removesuffix("_nominal"))
            if band is None:
                assert "note" in feature["requirements"], (name, key)
                continue
            low, high = band
            assert low <= nominal <= high, (name, key)


# Each printed toleranced dimension -> the exported feature and requirement
# that owns its band. Reference sizes governed by a matched-fit callout and
# the thread designation own no band.
PRINTED_OWNERS = {
    BUTTON: (
        button,
        {
            "DiscDia": ("rim", "dia"),
            "DiscThick": ("hub_seat_face", "thickness"),
        },
        {"BoreDia"},
    ),
    STUD: (
        stud,
        {
            "SeatStation": ("button_seat", "station"),
            "ShoulderStation": ("body_shoulder", "station"),
            "ReliefEndStation": ("thread", "length"),
            "HeadBackStation": ("head_back_face", "station"),
            "TailEndStation": ("vise_tail", "station"),
            "HeadDia": ("button_seat", "dia"),
            "TailDia": ("vise_tail", "dia"),
            "ReliefDia": ("thread_relief", "dia"),
        },
        {"BodyDia", "ThreadDia"},
    ),
}


@pytest.mark.parametrize("stem", [BUTTON, STUD])
def test_every_printed_band_has_a_requirement_owner(stem: str) -> None:
    """One-fact coverage: every printed toleranced dimension reaches prechips
    as a listed requirement band at its printed places."""
    spec, owners, exempt = PRINTED_OWNERS[stem]
    assert set(owners) | exempt == set(spec.DRAWING_PRECISION_BY_NAME)
    features = _features(stem)
    for printed, (name, key) in owners.items():
        feature = features[name]
        assert key in feature["requirements"], printed
        places = spec.DRAWING_PRECISION_BY_NAME[printed]
        nominal = feature[f"{key}_nominal"]
        # The model nominal is the printed value, so the band's endpoints are
        # the printed ones.
        assert round(nominal, places) == nominal, printed
        assert feature[key] == limits(nominal, places), printed
    # Each printed roughness symbol is a listed finish requirement on the
    # exported feature of the same name.
    assert spec.SURFACE_FINISHES
    for control in spec.SURFACE_FINISHES:
        owner = features[control.key]
        assert "finish_ra" in owner["requirements"], control.key
        assert owner["finish_ra"] == control.roughness_um, control.key


def test_body_carries_the_hub_and_both_buttons_inside_the_stack() -> None:
    """At every printed button thickness and hub length the whole hub and at
    least half the upper button sit on the lapped body (its length the worst
    case of the two printed tip stations), and the nut lands on the upper
    button (body short of the stack top)."""
    stud = _features(STUD)
    seat_low, seat_high = stud["button_seat"]["station"]
    start_low, start_high = stud["body_shoulder"]["station"]
    body_low, body_high = seat_low - start_high, seat_high - start_low
    thick_low, thick_high = _features(BUTTON)["hub_seat_face"]["thickness"]
    hub_high = rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
    assert body_high < 2 * thick_low + rocker.HUB_LENGTH
    assert body_low - (thick_high + hub_high) >= thick_low / 2


def test_kit_holds_the_hub_coaxiality_and_filed_band() -> None:
    """The manual-arc centre shift (pin in the pivot bore, button bore on the
    pin, rim runout to its bore) keeps the filed hub inside the arm's printed
    coaxiality and O.D. band."""
    body_min = stud.BODY_DIA + stud.BODY_BAND[1]
    shift = (
        (rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0] - body_min) / 2
        + (button.BORE_DIA + button.BORE_BAND[0] - body_min) / 2
        + button.OD_RUNOUT_TIR / 2
    )
    assert shift == pytest.approx(stud.HUB_CENTRE_SHIFT_MAX)
    assert 2 * shift <= rocker.HUB_COAXIALITY_DIA
    rim_low, rim_high = _features(BUTTON)["rim"]["dia"]
    hub_low, hub_high = limits(rocker.HUB_DIA, 2)
    assert hub_low <= rim_low - 2 * shift and rim_high + 2 * shift <= hub_high


def test_head_and_nut_stay_inside_the_rim_outside_the_bore() -> None:
    """A file laid on either rim clears the head and the nut corners at the
    worst case of every printed band."""
    rim_low = _features(BUTTON)["rim"]["dia"][0]
    head_low, head_high = _features(STUD)["button_seat"]["dia"]
    assert button.BORE_DIA + button.BORE_BAND[0] < head_low
    assert head_high < rim_low
    assert stud.NUT_CORNER_DIA < rim_low


def test_kit_solids_validate_and_follow_the_specs() -> None:
    from prechips.model import FixtureSolid

    for solid in stud.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    solids = {solid["name"]: solid for solid in stud.PRECHIPS_SOLIDS}
    assert len(solids) == len(stud.PRECHIPS_SOLIDS)

    def span(name: str) -> tuple[float, float]:
        solid = solids[name]
        z, length = solid["at_mm"][2], solid["length_mm"]
        end = z + length * solid["axis"][2]
        return min(z, end), max(z, end)

    seat = -(rocker.HUB_LENGTH + button.THICKNESS)
    assert span("upper button") == pytest.approx((0.0, button.THICKNESS))
    assert span("lower button") == pytest.approx((seat, -rocker.HUB_LENGTH))
    assert span("stud pin") == pytest.approx((seat, seat + stud.BODY_LENGTH))
    assert span("stud relief") == pytest.approx(
        (seat + stud.BODY_LENGTH, seat + stud.BODY_LENGTH + stud.RELIEF_WIDTH)
    )
    assert span("stud thread") == pytest.approx(
        (seat + stud.BODY_LENGTH + stud.RELIEF_WIDTH, seat + stud.THREAD_END)
    )
    assert span("stud head") == pytest.approx((seat - stud.HEAD_LENGTH, seat))
    assert span("stud tail") == pytest.approx(
        (seat - stud.TAIL_END, seat - stud.HEAD_LENGTH)
    )
    assert span("nut")[0] == pytest.approx(button.THICKNESS)
    assert span("stud pin")[1] < span("nut")[0] < span("stud thread")[1]
    assert stud.RELIEF_DIA < stud.THREAD_MODEL_DIA - 1.299038 * 25.4 / 24.0
    rim_low, rim_high = _features(BUTTON)["rim"]["dia"]
    for name in ("upper button", "lower button"):
        assert rim_low <= solids[name]["dia_mm"] <= rim_high
    for name in ("upper button bore", "lower button bore"):
        assert solids[name]["void"] and solids[name]["dia_mm"] == button.BORE_DIA
    assert solids["stud pin"]["dia_mm"] == stud.BODY_DIA
    assert solids["stud tail"]["dia_mm"] == stud.TAIL_DIA
    assert (
        solids["nut"]["supply"] == "bought"
        and stud.NUT_SKU in solids["nut"]["fastener"]
    )


def test_inventory_kit_binds_its_solids_from_the_stud_spec(tmp_path) -> None:
    import tomllib

    import _process_plans as plans

    assert "ch_rocker_arm_tl_filing_stud_spec" in plans.shop_spec_modules()
    inventory, _, _ = plans.bind_shop(tmp_path)
    kit = tomllib.loads(inventory.read_text(encoding="utf-8"))["fixtures"]
    assert kit["hub-filing-buttons"]["solids"] == stud.PRECHIPS_SOLIDS


@pytest.mark.parametrize(
    "dashed", ["ch-rocker-arm-tl-filing-button", "ch-rocker-arm-tl-filing-stud"]
)
def test_number_is_the_parent_number_plus_a_tool_suffix(dashed: str) -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    assert re.fullmatch(
        re.escape(parent) + r"-TL-\d{2}", _config.parts(dashed)["number"]
    )


@pytest.mark.parametrize("notes", [button.DRAWING_NOTES, stud.DRAWING_NOTES])
def test_notes_follow_the_simplicity_policy(notes: str) -> None:
    assert 1 <= len(notes.splitlines()) <= 4
    # The only figure a note may carry is a named exception's stated shortfall.
    assert not re.search(r"\d", notes.replace(button.RIM_WALL_NOTE, ""))
    assert "GROUND" not in notes and "GRIND" not in notes
