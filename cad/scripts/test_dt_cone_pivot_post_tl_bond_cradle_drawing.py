"""Offline contracts for the cone post bond cradle (MHA-DT-005-TL-01)."""

from __future__ import annotations

import math
import re

import _config
import draw_dt_cone_pivot_post_tl_bond_cradle as drawing
import dt_cone_pivot_post_spec as post
import dt_cone_pivot_post_tl_bond_cradle_spec as spec
import export_features

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


def test_crank_pins_carry_the_crank_sleeve_north_face() -> None:
    for name in ("crank_pin_west", "crank_pin_east"):
        pin = _features()[name]
        top = pin["at"][2]
        assert math.isclose(top, -post.CRANK_BOSS_NORTH_FACE)
        assert math.isclose(pin["at"][1], post.CRANK_BORE_HEIGHT)
        assert round(top - spec.BASE_TOP_Z, 2) == 8.62
        low, high = pin["height"]
        assert low <= top - spec.BASE_TOP_Z <= high


def test_cone_pin_tops_lie_in_the_north_cap_plane_square_to_the_journal() -> None:
    cap = post.SURFACE_FINISHES[3].face
    for name in ("cone_pin_near", "cone_pin_far"):
        pin = _features()[name]
        # Top centre on the cap plane, axis anti-parallel to the cap's normal.
        signed = sum(a * n for a, n in zip(pin["at"], cap.normal, strict=True))
        assert math.isclose(signed, cap.offset_mm, abs_tol=1e-9)
        assert all(
            math.isclose(a, -n, abs_tol=1e-12)
            for a, n in zip(pin["axis"], cap.normal, strict=True)
        )
        assert abs(pin["at"][1] - post.BORE_HEIGHT) == spec.CONE_PIN_OFFSET
        # The gauge reads the high (-X) edge.
        assert round(pin["height_nominal"], 2) == 9.93
        assert round(spec.CONE_PIN_CENTRE_HEIGHT, 2) == 9.49


def test_exported_pin_heights_are_the_printed_bands() -> None:
    features = _features()
    for name, nominal, places in (
        ("crank_pin_east", spec.CRANK_PIN_HEIGHT, spec.DRAWING_PRECISION_BY_NAME["CrankPinHeight"]),
        (
            "cone_pin_near",
            spec.CONE_PIN_HIGH_EDGE_HEIGHT,
            spec.DRAWING_PRECISION_BY_NAME["ConePinHighEdge"],
        ),
    ):
        low, high = features[name]["height"]
        assert low < round(nominal, places) < high
        assert features[name]["precision"]["height"] == places
