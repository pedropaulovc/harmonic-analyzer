"""Offline contracts for the rocker strap shim stack (MHA-CH-06-TL-11)."""

from __future__ import annotations

import re

import pytest

import _config
import _rocker_interface as rocker_interface
import ch_rocker_arm_tl_strap_shim_stack_spec as spec
import draw_ch_rocker_arm_tl_strap_shim_stack as drawing
import export_features
from _printed_limits import limits

STEM = "ch_rocker_arm_tl_strap_shim_stack"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.EDGE_KEEP) == marked
    assert not set(drawing.FACE_KEEP) & set(drawing.EDGE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.REFERENCE_DIMENSIONS) <= set(drawing.EDGE_KEEP)
    assert not set(drawing.CALLOUTS_ABOVE) & set(drawing.CALLOUTS_BELOW)
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_stack_height_seats_the_centred_strap_on_the_raw_ends() -> None:
    """S4: the turned-over blank rests on its raw ends; datum B, faced at
    (blank + strap) / 2 above the raw underside (plan to_z 5.21875), hangs the
    stack height above the same riser blocks."""
    strap_face_z = 5.21875
    assert spec.STACK_HEIGHT == pytest.approx(spec.RAW_BLANK_THICK - strap_face_z)
    assert spec.STRIP_THICK + spec.SHIM_THICK == pytest.approx(spec.STACK_HEIGHT)
    assert _features()["work_seat"]["height_nominal"] == pytest.approx(2.71875)


def test_prechips_solid_is_the_modelled_stack_in_the_fixture_frame() -> None:
    """The bound inventory solid comes from the same constants as the part,
    and matches the rocker trial's verified envelope and plan Z poses."""
    (solid,) = spec.PRECHIPS_SOLIDS
    assert (
        solid["shape"] == "box" and solid["shim"] is True and solid["bears"] == "face"
    )
    assert solid["at_mm"] == pytest.approx([-10.0, -6.0, 0.0])
    assert solid["size_mm"] == pytest.approx([20.0, 12.0, 2.71875])
    seat = _features()["work_seat"]
    assert seat["length_nominal"] == solid["size_mm"][0]
    assert seat["width_nominal"] == solid["size_mm"][1]
    assert seat["plane"]["value"] == solid["at_mm"][2] + solid["size_mm"][2]


def test_s4_stacks_stay_inside_the_arm_strap_band() -> None:
    """At its widest printed width each S4 stack bears only on the strap; the
    as-bought 3/4 in width would overhang it at X120."""
    half_l = limits(spec.STACK_LENGTH, 1)[1] / 2.0
    for width, fits in (
        (limits(spec.STACK_WIDTH, 1)[1], True),
        (spec.STOCK_WIDTH, False),
    ):
        inside = all(
            spec._strap_band(x + half_l)[0] < y - width / 2.0
            and y + width / 2.0 < spec._strap_band(x - half_l)[1]
            for x, y in spec.S4_STATIONS
        )
        assert inside is fits, width
    # The arm's depth bounds the band the stations sit in.
    for x, y in spec.S4_STATIONS:
        bottom, top = spec._strap_band(x)
        assert top - bottom == pytest.approx(rocker_interface.ARM_DEPTH, abs=0.5)
        assert bottom < y < top


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-strap-shim-stack")["number"]
    assert number == f"{parent}-TL-11"
    assert _config.parts("ch-rocker-arm-tl-strap-shim-stack")["quantity"] == 4


def test_material_names_an_alternative_to_o1() -> None:
    # Annealed static support: no hardness or wear function needs O1 (rule 2).
    part = _config.parts("ch-rocker-arm-tl-strap-shim-stack")
    assert " or " in part["material"]
    assert " or " in part["material_specification"].split(";")[0]


def test_notes_do_not_repeat_the_title_block_burr_note() -> None:
    # The shared title block already says REMOVE BURRS AND BREAK SHARP EDGES.
    assert "BURR" not in spec.DRAWING_NOTES.upper()


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"GROUND|LAPP|GRIND|MILL|SAW", spec.DRAWING_NOTES.upper())
    # Callouts may name a part's Number and the pack's authored fit-up
    # feeler, never another value.
    feeler = f"{spec.FIT_UP_FEELER_NO_GO:.2f} FEELER NO-GO"
    texts = [
        *drawing.CALLOUTS_ABOVE.values(),
        *drawing.CALLOUTS_BELOW.values(),
        drawing.RISER_SEAT_NOTE,
    ]
    for text in texts:
        bare = re.sub(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", "", text.replace(feeler, ""))
        assert not re.search(r"\d", bare), text


def test_shim_fit_up_is_a_go_no_go_pair() -> None:
    # Codex #1448 P1: the strap-face feeler alone passes an over-height pack,
    # which lifts the blank off the riser blocks and bows the span. The pair is
    # the ShimThick callout (bears on the strap face) plus a leadered note on
    # the riser seat (still bears on every MHA-CH-06-TL-10), one line each.
    feeler = f"{spec.FIT_UP_FEELER_NO_GO:.2f} FEELER NO-GO"
    strap = drawing.CALLOUTS_BELOW["ShimThick"]
    risers = drawing.RISER_SEAT_NOTE
    assert "MHA-CH-06 STRAP FACE" in strap and strap.endswith(feeler)
    assert "MHA-CH-06-TL-10" in risers and risers.endswith(feeler)
    for text in (strap, risers):
        assert "\n" not in text and len(text) <= 66, text
    # The leader lands on the riser seat: the edge view's bottom edge (Z0).
    bottom = drawing.EDGE_CENTER[1] - spec.STACK_HEIGHT / 2.0 * 4.0 / 1000.0
    assert abs(drawing.RISER_SEAT_TIP[1] - bottom) < 1e-9
    # ...just inside its right end, so the leader leaves the note's right side
    # and rises clear of its own text (layout audit: leader-through-own-text).
    right_end = drawing.EDGE_CENTER[0] + spec.STACK_LENGTH / 2.0 * 4.0 / 1000.0
    assert right_end - 0.004 <= drawing.RISER_SEAT_TIP[0] < right_end


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
            checked += 1
    assert checked
