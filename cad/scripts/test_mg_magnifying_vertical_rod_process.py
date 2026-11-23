"""The magnifying vertical rod's traveler numbers agree with the joint and the shop.

``cad/process/mg_magnifying_vertical_rod/plan.toml`` types two numbers its
binder cannot read: the tip chamfer's Ø (the drawing's "TIP 45° CHAMFER TO
MINOR Ø", the #4-40 basic minor the clamp joint computes) and the cutoff
blade's width (its relief is one plunge of the P1 blade).
"""

from __future__ import annotations

import tomllib

import _process_plans
import _shop_equipment
import mg_rod_clamp_joint

PLAN = tomllib.loads(
    _process_plans.plan_path("mg_magnifying_vertical_rod").read_text(encoding="utf-8")
)
PARAMETERS = PLAN["parameters"]


def test_the_tip_chamfer_runs_to_the_thread_basic_minor() -> None:
    minor_in = mg_rod_clamp_joint.THREAD_BASIC_MINOR / 25.4
    assert PARAMETERS["tip_chamfer_minor_in"] == round(minor_in, 3)


def test_the_relief_is_one_plunge_of_the_shops_cutoff_blade() -> None:
    blade = _shop_equipment.load()["tools"]["cutoff-blade-p1"]
    assert PARAMETERS["blade_width_in"] == blade["width_in"]
