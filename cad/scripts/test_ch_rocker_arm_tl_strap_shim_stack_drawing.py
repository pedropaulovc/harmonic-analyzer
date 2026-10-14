"""Offline contracts for the rocker strap shim stack (MHA-CH-006-TL-11)."""

from __future__ import annotations

import re

import pytest

import _config
import ch_rocker_arm_spec as rocker
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
        assert top - bottom == pytest.approx(rocker.ARM_DEPTH, abs=0.5)
        assert bottom < y < top


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-strap-shim-stack")["number"]
    assert number == f"{parent}-TL-11"
    assert _config.parts("ch-rocker-arm-tl-strap-shim-stack")["quantity"] == 4


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"GROUND|LAPP|GRIND|MILL|SAW", spec.DRAWING_NOTES.upper())
    # Callouts may name a mating part's Number, never a value.
    for text in [*drawing.CALLOUTS_ABOVE.values(), *drawing.CALLOUTS_BELOW.values()]:
        assert not re.search(r"\d", re.sub(r"MHA-[A-Z]+-\d{3}", "", text))


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
