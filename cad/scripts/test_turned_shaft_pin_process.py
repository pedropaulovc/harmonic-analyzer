"""The sawn pins' and domed parts' lathe travelers agree with their models.

``dt_crank_pinion_pin`` and ``dt_pinion_handle`` are cut from rod used as
supplied on the diameter: a piece is sawn and each end faced in the 3-jaw.
``test_turned_bush_process`` holds their adapter binding and stock records;
these tests hold what it cannot see: the sawn piece leaves the facing
allowances over the drawing's length, and the rod is the drawing's reference
diameter. The domed parts (``turned_shaft``) are blanks sawn from rod used as
supplied: each faced end keeps a skim (the lever's end B is cut at the root of
its sacrificial stub, so end A alone is faced), and the rod lies in the
drawing's diameter band.
"""

from __future__ import annotations

import math
import tomllib

import pytest

import _process_plans
import export_features

IN = 25.4
# The ends sawn before facing: the handle's piece is sawn at both ends, the
# pin's off a rod end faced first (Setup 2, in its split bush).
SAWN_ENDS = {"dt_crank_pinion_pin": 1, "dt_pinion_handle": 2}


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


@pytest.mark.parametrize("stem", sorted(SAWN_ENDS))
def test_the_sawn_piece_leaves_each_sawn_end_its_facing(stem: str) -> None:
    parameters = _plan(stem)["parameters"]
    far = export_features.requirement_manifest(stem)["features"]["far_end"]
    allowance = parameters["regrip_allowance_in"]
    if SAWN_ENDS[stem] == 2:
        allowance += parameters["face_allowance_in"]
    assert parameters["saw_length_in"] == pytest.approx(
        far["length_nominal"] / IN + allowance, abs=1e-3
    )
    assert parameters["saw_length_in"] * IN > far["length"][1]


@pytest.mark.parametrize("stem", sorted(SAWN_ENDS))
def test_the_rod_is_the_drawings_reference_diameter(stem: str) -> None:
    stock_dia_in = _plan(stem)["parameters"]["stock_dia_in"]
    outer = export_features.requirement_manifest(stem)["features"]["outer"]
    assert stock_dia_in * IN == pytest.approx(outer["dia_ref"])


# The domed parts: a blank sawn from rod used as supplied on the diameter,
# each end faced (turned_shaft's sawn-blank route).
BLANKS = ("dt_pinion_cam_pin", "mg_magnifying_lever")


@pytest.mark.parametrize("stem", BLANKS)
def test_the_domed_parts_are_sawn_blanks_on_turned_shaft(stem: str) -> None:
    plan = _plan(stem)
    assert stem in _process_plans.TRAVELER_STEMS
    assert plan["cad"]["adapter"] == "turned_shaft"
    assert {"blank_length_in", "end_stickout_in"} <= set(plan["parameters"])


@pytest.mark.parametrize("stem", BLANKS)
def test_the_blank_leaves_a_skim_on_each_faced_end(stem: str) -> None:
    parameters = _plan(stem)["parameters"]
    far = export_features.requirement_manifest(stem)["features"]["far_end"]
    if "length" in far:
        longest = far["length"][1]
    else:
        # A domed far end: its root station's maximum plus the cap the form
        # tool's arc leaves over the rod as supplied.
        form_r = parameters["dome_form_radius_in"] * IN
        half_dia = parameters["stock_dia_in"] * IN / 2
        longest = far["root_station"][1] + form_r - math.sqrt(form_r**2 - half_dia**2)
    spare = parameters["blank_length_in"] * IN - longest
    if "stub_allowance_in" in parameters:
        # The stub that carried the threading centre is stock allowance
        # beyond end B, whose face is cut at its root: end A alone is faced.
        end_a = spare - parameters["stub_allowance_in"] * IN
        assert 0.005 * IN <= end_a <= 0.1 * IN
    else:
        assert 0.005 * IN <= spare / 2 <= 0.05 * IN


@pytest.mark.parametrize("stem", BLANKS)
def test_the_blank_rod_is_the_drawings_diameter_as_supplied(stem: str) -> None:
    stock = _plan(stem)["parameters"]["stock_dia_in"]
    outer = export_features.requirement_manifest(stem)["features"]["outer"]
    if "dia" in outer:
        assert outer["dia"][0] <= stock * IN <= outer["dia"][1]
    else:
        assert stock * IN == pytest.approx(outer["dia_ref"])
