"""TRIAL (owner 2026-11-22): the shared column clamp plan agrees with the two
single-part plans it would replace.

``cad/process/families/sh_column_clamp/plan.toml`` is one prechips family plan
for MHA-SH-01 and MHA-SH-02. The two single-part plans stay the enrolled
travelers and the CAM recipes' source, so the shared plan must carry the same
numbers, tools and program names, and must not enrol anything.
"""

from __future__ import annotations

import re
import tomllib

import pytest

import _cam_programs
import _process_plans
import prechips_traveler

FAMILY = "sh_column_clamp"
STEMS = {"front": "sh_column_clamp_front", "back": "sh_column_clamp_back"}
# The shared plan's own numbers: the six blanks and the bar they come off.
FAMILY_ONLY = {"blank_count", "bar_length_in"}


def _load(path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


PLAN = _load(_process_plans.family_plan_path(FAMILY))
SINGLE = {key: _load(_process_plans.plan_path(stem)) for key, stem in STEMS.items()}
PARTS = {part["id"]: part for part in PLAN["parts"]}
TEXT = _process_plans.family_plan_path(FAMILY).read_text(encoding="utf-8")


def test_the_family_plan_enrols_nothing():
    assert FAMILY not in _process_plans.TRAVELER_STEMS
    assert FAMILY not in _cam_programs.CAM_STEMS
    assert set(STEMS.values()) <= set(_process_plans.TRAVELER_STEMS)


@pytest.mark.parametrize("key", STEMS)
def test_each_half_reads_its_single_plans_parameters(key):
    merged = PLAN["parameters"] | PARTS[key]["parameters"]
    single = SINGLE[key]["parameters"]
    assert {name: merged[name] for name in single} == single
    # Nothing but the family's own numbers and the other half's is added.
    other = SINGLE["back" if key == "front" else "front"]["parameters"]
    assert set(merged) - set(single) - FAMILY_ONLY <= set(other)


def test_a_shared_parameter_is_one_both_single_plans_agree_on():
    front, back = (SINGLE[key]["parameters"] for key in STEMS)
    for name, value in PLAN["parameters"].items():
        if name not in FAMILY_ONLY:
            assert front[name] == back[name] == value, name


def test_the_bar_covers_the_blanks_and_kerfs():
    numbers = PLAN["parameters"]
    assert numbers["blank_count"] == sum(
        plan["parameters"]["quantity"] for plan in SINGLE.values()
    )
    assert numbers["bar_length_in"] == pytest.approx(
        numbers["blank_count"] * numbers["blank_length_max_in"]
        + (numbers["blank_count"] - 1) * numbers["kerf_in"]
    )


@pytest.mark.parametrize("key", STEMS)
def test_each_half_binds_its_single_plans_manifest(key):
    cad = SINGLE[key]["cad"]
    assert PARTS[key]["adapter"] == cad["adapter"]
    assert PARTS[key]["part"] == cad["part"]
    assert PARTS[key]["file"].endswith(f"out/features/{STEMS[key]}/features.toml")


def test_one_tool_list_holds_both_plans_tools():
    family = {tool["id"]: tool["ref"] for tool in PLAN["tools"]}
    both = {
        tool["id"]: tool["ref"] for plan in SINGLE.values() for tool in plan["tools"]
    }
    assert family == both
    assert (
        PLAN["stock_refs"]
        == SINGLE["front"]["stock_refs"]
        == SINGLE["back"]["stock_refs"]
    )


def test_the_setups_name_exactly_the_recipes_programs():
    posted = {
        name
        for stem in STEMS.values()
        for name, _ops in _cam_programs.load_recipe(stem).PROGRAMS
    }
    setups = TEXT[TEXT.index("[[setups]]") :]
    # A shared setup writes its two files as CFnn/CBnn_name.
    named = set()
    for both, front, back, tail, single in re.findall(
        r"\b(CF(\d\d)/CB(\d\d)_(\w+))|\b(C[FB]\d\d_\w+)", setups
    ):
        if both:
            assert front == back, both
            named |= {f"CF{front}_{tail}", f"CB{back}_{tail}"}
        else:
            named.add(single)
    assert named == posted


def test_every_setup_of_one_half_names_it_and_its_program():
    for setup in PLAN["setups"]:
        programs = set(re.findall(r"\bC([FB])\d\d", setup.get("datum", "")))
        if setup.get("part") == "front":
            assert programs == {"F"}, setup["title"]
        elif programs == {"F"}:
            pytest.fail(f"{setup['title']}: a front-only program in a shared setup")


def test_the_override_runs_the_named_source_uncached():
    plan = _process_plans.family_plan_path(FAMILY)
    released = prechips_traveler.traveler_command("uv", "1.2.3", plan, "pro", plan)
    assert released[2:5] == ["run", "--from", "prechips==1.2.3"]
    trial = prechips_traveler.traveler_command(
        "uv", "1.2.3", plan, "pro", plan, "C:/src/prechips"
    )
    assert trial[2:6] == ["run", "--no-cache", "--from", "C:/src/prechips"]
