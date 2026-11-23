"""No lathe traveler runs bar out past the spindle's rear end or catches a
parting part by hand (#3424).

The PM-1127VF-LB's change-gear cover has a hole at the spindle's rear, so
bar can pass out the back, but the spindle supports it only up to its rear
end: bar longer than that runs unsupported, and a slender bar whips, bends
and strikes whatever is near. So bar ends inside the spindle unless an
outboard support is declared. The spindle's length from the jaw fronts to
its rear end is not published (``cad/config/shop-equipment/machines.toml``
``machines.pm-1127vf-lb``, ``jaw_fronts_to_spindle_rear``, to measure);
until the owner tapes it, ``bar_behind_jaw_fronts_max_in`` is the assumed
supported length. A plan's ``bar_length_in`` is the piece the lathe holds,
so the whole piece, grip included, must fit within it: a plan that starts
from longer bar saws a working piece first.

A part parting off falls on its own; the plan says so and keeps hands clear,
never "catch it" (by hand or in a rag beside the turning work).
"""

from __future__ import annotations

import re
import tomllib

import pytest

import _process_plans
import _shop_equipment

LATHE = _shop_equipment.load()["machines"]["pm-1127vf-lb"]
BAR_BEHIND_MAX_IN = LATHE["bar_behind_jaw_fronts_max_in"]

_CATCH = re.compile(r"\bcatch (?:it|the \w+)\b|\bin a rag\b", re.IGNORECASE)


def _plans() -> dict[str, dict]:
    return {
        stem: tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
        for stem in _process_plans.TRAVELER_STEMS
    }


PLANS = _plans()


def test_the_spindle_length_is_recorded_or_to_measure() -> None:
    measured = LATHE["jaw_fronts_to_spindle_rear"]
    assert measured == "to_measure" or (
        isinstance(measured, (int, float)) and measured > BAR_BEHIND_MAX_IN
    )
    assert 0 < BAR_BEHIND_MAX_IN


@pytest.mark.parametrize(
    "stem",
    [
        stem
        for stem, plan in PLANS.items()
        if "bar_length_in" in plan.get("parameters", {})
    ],
)
def test_the_chucked_piece_stays_inside_the_spindle(stem: str) -> None:
    assert PLANS[stem]["parameters"]["bar_length_in"] <= BAR_BEHIND_MAX_IN


def test_no_part_off_is_caught_by_hand() -> None:
    caught = [
        f"{stem}: {text[-80:]}"
        for stem, plan in PLANS.items()
        for setup in plan.get("setups", ())
        for operation in setup.get("operations", ())
        for text in (
            operation.get("instruction", ""),
            operation.get("instruction_detailed", ""),
        )
        if _CATCH.search(text)
    ]
    assert not caught
