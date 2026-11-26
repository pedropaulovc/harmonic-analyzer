"""Every end mill's least stick-out is its flute length plus 10 %.

Owner ruling (Pedro) 2026-11-25 on #3386, HA #3624: "min stickout based on
flute length then add 10pct on top of it". A plan's stick-out parameter for an
end mill (any shop tool with a ``flute_length_mm``: square, ball, long-reach
and chamfer mills) is at least that tool's ``flute_length_mm`` x 1.1, to .01
mm, in every ``cad/process/*/plan.toml``, its ``[parameters]`` and each
``[[parts]]`` part's own.

A parameter names its tool by its name: ``END_MILL_PROJECTIONS`` gives the
shop tools each name can mean, and the plan's ``[[tools]]`` refs pick the one
it cuts with. Every parameter whose name holds ``projection`` is either there
or in ``OTHER_PROJECTIONS`` (drills, reamers, the engraver: no flutes on
record), so a new end-mill stick-out cannot slip past the floor.
"""

from __future__ import annotations

import tomllib

import pytest

import _process_plans

SHOP_TOOLS = _process_plans.load_shop()["tools"]

HALF = ("endmill-carbide-3fl-1-2", "basebar-em-half")
QUARTER = ("endmill-carbide-3fl-1-4",)
EIGHTH = ("endmill-carbide-3fl-1-8",)
THIRTYSECOND = ("endmill-carbide-3fl-1-32-downcut",)
CHAMFER = ("chamfer-mill-carbide-1-4-90",)

# Stick-out parameter -> the shop end mills it can pin. A plan lists exactly
# one of them, except a name in SHARED_PROJECTIONS, one floor for several of
# the plan's cutters: it holds every one it lists. A ceiling (``_max_``) is a
# stick-out too: one under the floor leaves no stick-out to set.
END_MILL_PROJECTIONS: dict[str, tuple[str, ...]] = {
    "half_mill_projection_mm": HALF,
    "half_mill_projection_min_mm": HALF,
    "bore_mill_projection_min_mm": HALF,
    "neck_mill_projection_min_mm": HALF,
    "quarter_mill_projection_min_mm": QUARTER,
    "quarter_projection_min_mm": QUARTER,
    "eighth_mill_projection_min_mm": EIGHTH,
    "eighth_mill_projection_max_mm": EIGHTH,
    "em_eighth_projection_min_mm": EIGHTH,
    "eighth_projection_min_mm": EIGHTH,
    "em_projection_min_mm": ("endmill-carbide-3fl-3-8", *THIRTYSECOND),
    "em_projection_max_mm": ("endmill-carbide-3fl-3-8", *THIRTYSECOND),
    "em_thirtysecond_projection_min_mm": THIRTYSECOND,
    "em_thirtysecond_projection_max_mm": THIRTYSECOND,
    "cbore_projection_min_mm": ("endmill-carbide-3fl-1-8-lr-755708",),
    # ms_stop_block: the 1/8 in and the 1/16 in long-reach, one floor.
    "small_mill_projection_min_mm": ("endmill-carbide-3fl-1-16-reach-1-2", *EIGHTH),
    "chamfer_projection_min_mm": CHAMFER,
    # dt_crank_arm countersinks with the chamfer mill.
    "sink_projection_min_mm": CHAMFER,
    "slot_projection_min_mm": ("endmill-carbide-3fl-3-16",),
    "ball_projection_mm": ("ball-endmill-carbide-2fl-1-4",),
}
SHARED_PROJECTIONS = frozenset({"small_mill_projection_min_mm"})

# Stick-outs of tools with no flute length on record: drills, centre and spot
# drills, reamers, cross drills on the lathe, the engraving bit.
OTHER_PROJECTIONS = frozenset(
    {
        "drill_projection_mm",
        "drill_projection_min_mm",
        "drill_projection_max_mm",
        "drill_45_projection_min_mm",
        "drill_54_projection_min_mm",
        "cross_projection_min_mm",
        "spot_projection_mm",
        "spot_projection_min_mm",
        "ream_projection_mm",
        "reamer_projection_mm",
        "engraver_projection_mm",
    }
)


def _plans() -> list[tuple[str, dict]]:
    return [
        (path.parent.name, tomllib.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_process_plans.PROCESS_ROOT.glob("*/plan.toml"))
    ]


def _projections() -> list[tuple[str, str, str, object, frozenset[str]]]:
    """(stem, scope, name, value, the plan's tool refs) of every parameter
    whose name holds ``projection``; scope is ``parameters`` or the part's
    id."""
    found = []
    for stem, plan in _plans():
        refs = frozenset(tool["ref"] for tool in plan.get("tools", ()) if "ref" in tool)
        scopes = [("parameters", plan.get("parameters", {}))] + [
            (part["id"], part.get("parameters", {})) for part in plan.get("parts", ())
        ]
        for scope, parameters in scopes:
            for name, value in parameters.items():
                if "projection" in name:
                    found.append((stem, scope, name, value, refs))
    return found


PROJECTIONS = _projections()
END_MILL_CASES = [case for case in PROJECTIONS if case[2] in END_MILL_PROJECTIONS]


def floor_mm(tool: str) -> float:
    """The ruling's least stick-out for a shop end mill."""
    return round(SHOP_TOOLS[tool]["flute_length_mm"] * 1.1, 2)


@pytest.mark.parametrize(
    ("stem", "scope", "name", "value", "refs"),
    END_MILL_CASES,
    ids=[f"{stem}-{scope}-{name}" for stem, scope, name, _, _ in END_MILL_CASES],
)
def test_end_mill_stickout_is_at_least_flute_length_plus_ten_percent(
    stem, scope, name, value, refs
) -> None:
    listed = [tool for tool in END_MILL_PROJECTIONS[name] if tool in refs]
    if name in SHARED_PROJECTIONS:
        assert listed, f"{stem} {scope}.{name}: the plan lists none of {END_MILL_PROJECTIONS[name]}"
    else:
        assert len(listed) == 1, (
            f"{stem} {scope}.{name}: the plan lists {listed or 'none'} of "
            f"{END_MILL_PROJECTIONS[name]}, not exactly one"
        )
    assert isinstance(value, (int, float)), f"{stem} {scope}.{name} = {value!r} is not a number"
    for tool in listed:
        assert value >= floor_mm(tool), (
            f"{stem} {scope}.{name} = {value} mm is under {tool}'s flute length "
            f"{SHOP_TOOLS[tool]['flute_length_mm']} + 10 %, {floor_mm(tool)} mm"
        )


def test_every_projection_parameter_is_classified() -> None:
    unknown = sorted(
        f"{stem} {scope}.{name}"
        for stem, scope, name, _, _ in PROJECTIONS
        if name not in END_MILL_PROJECTIONS and name not in OTHER_PROJECTIONS
    )
    assert not unknown, (
        "stick-out parameters in neither END_MILL_PROJECTIONS nor "
        f"OTHER_PROJECTIONS: {unknown}"
    )


def test_the_tables_name_only_live_parameters_and_shop_end_mills() -> None:
    assert not END_MILL_PROJECTIONS.keys() & OTHER_PROJECTIONS
    assert SHARED_PROJECTIONS <= END_MILL_PROJECTIONS.keys()
    used = {name for _, _, name, _, _ in PROJECTIONS}
    assert sorted(END_MILL_PROJECTIONS.keys() - used) == []
    assert sorted(OTHER_PROJECTIONS - used) == []
    for name, tools in END_MILL_PROJECTIONS.items():
        for tool in tools:
            assert "flute_length_mm" in SHOP_TOOLS.get(tool, {}), (
                f"{name}: {tool} is not a shop tool with a flute length"
            )


def test_the_floor_is_the_rulings() -> None:
    # The 1/2 in carbide, 1 in of flute: 27.94 mm; the 1/4 in, 1.125: 31.43.
    assert floor_mm("endmill-carbide-3fl-1-2") == 27.94
    assert floor_mm("endmill-carbide-3fl-1-4") == 31.43
