"""COM-free packing controls; the *_drawing.py pattern enrolls this gate."""

from copy import deepcopy
from itertools import combinations, product
import math
import random

import pytest

from _drawing_view_packing import (
    Axis,
    AxisAlignment,
    AxisOrder,
    PackingStatus,
    Rect,
    RigidViewGroup,
    pack_view_groups,
)


def group(name, *rectangles):
    return RigidViewGroup(
        name,
        {f"{name}-{index}": rectangle for index, rectangle in enumerate(rectangles)},
    )


def separated(first, second, gap=0):
    return (
        first.xmax + gap <= second.xmin + 1e-12
        or second.xmax + gap <= first.xmin + 1e-12
        or first.ymax + gap <= second.ymin + 1e-12
        or second.ymax + gap <= first.ymin + 1e-12
    )


def assert_valid(result, groups, drawable, obstacles=(), gap=0):
    assert result.status is PackingStatus.PACKED
    assert set(result.translations) == {item.name for item in groups}
    rectangles = []
    for item in groups:
        delta = result.translations[item.name]
        for original in item.rectangles.values():
            moved = original.translated(delta)
            assert moved.xmin >= drawable.xmin - 1e-12
            assert moved.ymin >= drawable.ymin - 1e-12
            assert moved.xmax <= drawable.xmax + 1e-12
            assert moved.ymax <= drawable.ymax + 1e-12
            assert moved.xmax - moved.xmin == pytest.approx(
                original.xmax - original.xmin
            )
            assert moved.ymax - moved.ymin == pytest.approx(
                original.ymax - original.ymin
            )
            assert all(separated(moved, obstacle, gap) for obstacle in obstacles)
            rectangles.append(moved)
    assert all(separated(a, b, gap) for a, b in combinations(rectangles, 2))


def test_valid_layout_is_unchanged_and_inputs_are_not_mutated():
    groups = [
        group("ortho", Rect(1, 1, 3, 3), Rect(1, 4, 3, 6)),
        group("iso", Rect(6, 6, 9, 9)),
    ]
    before = deepcopy(groups)
    result = pack_view_groups(groups, Rect(0, 0, 10, 10), [Rect(6, 0, 10, 3)])
    assert result.translations == {"iso": (0, 0), "ortho": (0, 0)}
    assert result.explored_nodes == 0
    assert groups == before


def test_decorated_view_overflow_is_repaired_without_changing_its_size():
    groups = [group("front", Rect(0.36, 0.23, 0.46, 0.30))]
    drawable = Rect(0.0127, 0.0127, 0.4191, 0.2667)
    result = pack_view_groups(groups, drawable)
    assert_valid(result, groups, drawable)
    assert result.translations["front"][0] < 0
    assert result.translations["front"][1] < 0


def test_projection_group_is_rigid_and_empty_space_in_its_hull_remains_available():
    orthographic = group("ortho", Rect(3, 0, 4, 1), Rect(3, 2, 4, 3), Rect(5, 0, 6, 1))
    iso = group("iso", Rect(1, 1, 2, 2))
    drawable = Rect(0, 0, 3, 3)
    obstacles = [Rect(2, 2, 3, 3)]
    result = pack_view_groups([orthographic, iso], drawable, obstacles)
    assert_valid(result, [orthographic, iso], drawable, obstacles)
    assert result.translations["ortho"] == (-3, 0)
    assert result.translations["iso"] == (0, 0)
    moved = [
        rectangle.translated(result.translations["ortho"])
        for rectangle in orthographic.rectangles.values()
    ]
    assert moved[1].xmin == moved[0].xmin
    assert moved[1].ymin - moved[0].ymin == 2
    assert moved[2].ymin == moved[0].ymin
    assert moved[2].xmin - moved[0].xmin == 2


def test_note_and_title_block_obstacles_are_fixed_and_clearance_is_preserved():
    groups = [group("view", Rect(2, 1, 5, 3)), group("iso", Rect(4, 3, 6, 5))]
    obstacles = (Rect(2, 0, 6, 2), Rect(0, 4, 2, 6))
    drawable = Rect(0, 0, 8, 8)
    before = deepcopy(obstacles)
    result = pack_view_groups(groups, drawable, obstacles, gap_m=0.25)
    assert_valid(result, groups, drawable, obstacles, gap=0.25)
    assert obstacles == before


def test_search_backtracks_from_nearby_but_impossible_vertical_separations():
    groups = [group("large", Rect(1, 0, 3, 2)), group("short", Rect(1, 0.5, 3, 1.5))]
    drawable = Rect(0, 0, 4, 2)
    result = pack_view_groups(groups, drawable)
    assert_valid(result, groups, drawable)
    assert result.explored_nodes >= 4


@pytest.mark.parametrize(
    "groups,drawable",
    [
        ([group("wide", Rect(0, 0, 4, 1))], Rect(0, 0, 3, 3)),
        (
            [group("a", Rect(0, 0, 2, 2)), group("b", Rect(0, 0, 2, 2))],
            Rect(0, 0, 3, 3),
        ),
    ],
)
def test_exhausted_or_impossible_bounds_report_no_fit(groups, drawable):
    result = pack_view_groups(groups, drawable)
    assert result.status is PackingStatus.DOES_NOT_FIT
    assert result.translations == {}


def test_internal_projection_group_overlap_is_explicitly_unrepairable():
    groups = [group("ortho", Rect(0, 0, 2, 2), Rect(1, 1, 3, 3))]
    result = pack_view_groups(groups, Rect(0, 0, 10, 10))
    assert result.status is PackingStatus.DOES_NOT_FIT
    assert "unrepairable internal overlap" in result.reason
    assert result.explored_nodes == 0


def test_search_budget_does_not_claim_geometric_impossibility():
    groups = [group("a", Rect(0, 0, 2, 2)), group("b", Rect(0, 0, 2, 2))]
    result = pack_view_groups(groups, Rect(0, 0, 4, 4), max_search_nodes=1)
    assert result.status is PackingStatus.SEARCH_LIMIT
    assert result.explored_nodes == 1
    assert result.translations == {}
    assert "feasibility not determined" in result.reason


def test_group_input_order_does_not_change_the_packing():
    groups = [group("b", Rect(0, 0, 2, 2)), group("a", Rect(0, 0, 2, 2))]
    assert pack_view_groups(groups, Rect(0, 0, 4, 4)) == pack_view_groups(
        groups[::-1], Rect(0, 0, 4, 4)
    )


def test_projection_spacing_can_expand_while_actual_view_anchors_stay_aligned():
    footprints = {
        "front": Rect(0, 0, 2, 2),
        "top": Rect(0.5, 1, 2.5, 2),
        "right": Rect(1, -0.5, 2, 1.5),
        "iso": Rect(0, 0, 1, 1),
    }
    positions = {"front": (1, 1), "top": (1, 1.5), "right": (1.5, 1), "iso": (0.5, 0.5)}
    groups = [group(name, rectangle) for name, rectangle in footprints.items()]
    alignments = (
        AxisAlignment(
            Axis.X, "front", "top", positions["front"][0], positions["top"][0]
        ),
        AxisAlignment(
            Axis.Y, "front", "right", positions["front"][1], positions["right"][1]
        ),
    )
    orderings = (AxisOrder(Axis.Y, "front", "top"), AxisOrder(Axis.X, "front", "right"))
    drawable = Rect(0, 0, 4, 4)
    result = pack_view_groups(
        groups, drawable, gap_m=0.1, alignments=alignments, orderings=orderings
    )
    assert_valid(result, groups, drawable, gap=0.1)
    anchors = {
        name: tuple(a + d for a, d in zip(positions[name], result.translations[name]))
        for name in positions
    }
    moved = {
        name: rectangle.translated(result.translations[name])
        for name, rectangle in footprints.items()
    }
    assert anchors["top"][0] == pytest.approx(anchors["front"][0])
    assert anchors["right"][1] == pytest.approx(anchors["front"][1])
    assert moved["front"].ymax + 0.1 <= moved["top"].ymin + 1e-12
    assert moved["front"].xmax + 0.1 <= moved["right"].xmin + 1e-12
    assert anchors["top"][1] - anchors["front"][1] > 0.5
    assert anchors["right"][0] - anchors["front"][0] > 0.5
    # The asymmetric decoration centres remain different despite view alignment.
    assert moved["top"].xmin - moved["front"].xmin == pytest.approx(0.5)
    assert moved["right"].ymin - moved["front"].ymin == pytest.approx(-0.5)


def test_initial_alignment_drift_is_repaired_even_without_box_collision():
    groups = [group("front", Rect(0, 0, 1, 1)), group("top", Rect(2, 2, 3, 3))]
    result = pack_view_groups(
        groups,
        Rect(0, 0, 4, 4),
        alignments=[AxisAlignment(Axis.X, "front", "top", 0.5, 2.5)],
    )
    assert_valid(result, groups, Rect(0, 0, 4, 4))
    assert 0.5 + result.translations["front"][0] == pytest.approx(
        2.5 + result.translations["top"][0]
    )
    assert result.explored_nodes > 0


def test_projection_constraints_can_make_an_otherwise_feasible_layout_impossible():
    groups = [group("a", Rect(0, 0, 1, 1)), group("b", Rect(1, 0, 2, 1))]
    drawable = Rect(0, 0, 2, 1)
    assert pack_view_groups(groups, drawable).status is PackingStatus.PACKED
    result = pack_view_groups(
        groups, drawable, alignments=[AxisAlignment(Axis.X, "a", "b", 0.5, 1.5)]
    )
    assert result.status is PackingStatus.DOES_NOT_FIT


def test_contradictory_order_cycle_is_rejected_without_spatial_search():
    groups = [group("a", Rect(0, 0, 1, 1)), group("b", Rect(1, 0, 2, 1))]
    result = pack_view_groups(
        groups,
        Rect(0, 0, 3, 3),
        orderings=[AxisOrder(Axis.X, "a", "b"), AxisOrder(Axis.X, "b", "a")],
    )
    assert result.status is PackingStatus.DOES_NOT_FIT
    assert result.explored_nodes == 1


@pytest.mark.parametrize(
    "alignment",
    [
        AxisAlignment(Axis.X, "a", "unknown", 0, 0),
        AxisAlignment("x", "a", "b", 0, 0),
        AxisAlignment(Axis.Y, "a", "b", math.nan, 0),
    ],
)
def test_invalid_alignment_is_rejected(alignment):
    groups = [group("a", Rect(0, 0, 1, 1)), group("b", Rect(1, 0, 2, 1))]
    with pytest.raises(ValueError, match="alignment"):
        pack_view_groups(groups, Rect(0, 0, 3, 3), alignments=[alignment])


@pytest.mark.parametrize(
    "ordering", [AxisOrder("y", "a", "b"), AxisOrder(Axis.X, "a", "unknown")]
)
def test_invalid_ordering_is_rejected(ordering):
    groups = [group("a", Rect(0, 0, 1, 1)), group("b", Rect(1, 0, 2, 1))]
    with pytest.raises(ValueError, match="ordering"):
        pack_view_groups(groups, Rect(0, 0, 3, 3), orderings=[ordering])


@pytest.mark.parametrize(
    "bounds",
    [
        (0, 0, 0, 1),
        (1, 0, 0, 1),
        (0, 1, 1, 0),
        (0, 0, math.inf, 1),
        (0, math.nan, 1, 1),
    ],
)
def test_invalid_rectangles_are_rejected(bounds):
    with pytest.raises(ValueError):
        Rect(*bounds)


@pytest.mark.parametrize("gap", [-1, math.inf, math.nan])
def test_invalid_clearance_is_rejected(gap):
    with pytest.raises(ValueError, match="clearance"):
        pack_view_groups([], Rect(0, 0, 1, 1), gap_m=gap)


@pytest.mark.parametrize("budget", [0, -1, 1.5, True])
def test_invalid_search_budget_is_rejected(budget):
    with pytest.raises(ValueError, match="positive integer"):
        pack_view_groups([], Rect(0, 0, 1, 1), max_search_nodes=budget)


@pytest.mark.parametrize(
    "groups",
    [
        [RigidViewGroup("empty", {})],
        [group(" ", Rect(0, 0, 1, 1))],
        [group("same", Rect(0, 0, 1, 1)), group("same", Rect(2, 2, 3, 3))],
        [
            RigidViewGroup("a", {"same": Rect(0, 0, 1, 1)}),
            RigidViewGroup("b", {"same": Rect(2, 2, 3, 3)}),
        ],
    ],
)
def test_invalid_group_identity_is_rejected(groups):
    with pytest.raises(ValueError):
        pack_view_groups(groups, Rect(0, 0, 10, 10))


def test_empty_view_inventory_needs_no_movement():
    result = pack_view_groups([], Rect(0, 0, 1, 1))
    assert result.status is PackingStatus.PACKED
    assert result.translations == {}


def grid_oracle(sizes, obstacles, alignment_axis=None, ordering_axis=None):
    choices = [
        tuple(
            Rect(x, y, x + width, y + height)
            for x in range(4 - width)
            for y in range(4 - height)
        )
        for width, height in sizes
    ]
    for candidate in product(*choices):
        if alignment_axis is not None:
            first, second = candidate[:2]
            axis = alignment_axis.value
            if first.bounds[axis] != second.bounds[axis]:
                continue
        if ordering_axis is not None:
            first, second = candidate[:2]
            axis = ordering_axis.value
            if first.bounds[axis + 2] > second.bounds[axis]:
                continue
        if not all(separated(a, b) for a, b in combinations(candidate, 2)):
            continue
        if all(
            separated(rectangle, obstacle)
            for rectangle in candidate
            for obstacle in obstacles
        ):
            return True
    return False


def test_small_integer_packings_match_exhaustive_grid_oracle():
    # Integer difference-constraint systems have integer feasible potentials;
    # enumerating the 3x3 integer grid is a complete oracle for these cases.
    randomizer = random.Random(48105)
    drawable = Rect(0, 0, 3, 3)
    for _ in range(100):
        sizes = [
            (randomizer.randint(1, 2), randomizer.randint(1, 2))
            for _ in range(randomizer.randint(1, 3))
        ]
        obstacles = []
        if randomizer.randrange(2):
            x, y = randomizer.randint(0, 2), randomizer.randint(0, 2)
            obstacles = [Rect(x, y, x + 1, y + 1)]
        groups = [
            group(str(index), Rect(0, 0, width, height))
            for index, (width, height) in enumerate(sizes)
        ]
        result = pack_view_groups(groups, drawable, obstacles)
        expected = grid_oracle(sizes, obstacles)
        assert result.status is (
            PackingStatus.PACKED if expected else PackingStatus.DOES_NOT_FIT
        )
        if expected:
            assert_valid(result, groups, drawable, obstacles)


@pytest.mark.parametrize(
    "alignment_axis,ordering_axis",
    [
        (Axis.X, None),
        (Axis.Y, None),
        (Axis.X, Axis.Y),
        (Axis.Y, Axis.X),
        (None, Axis.X),
    ],
)
def test_projection_relations_match_exhaustive_grid_oracle(
    alignment_axis, ordering_axis
):
    drawable = Rect(0, 0, 3, 3)
    for first_size, second_size in product(product((1, 2), repeat=2), repeat=2):
        sizes = [first_size, second_size]
        groups = [
            group(name, Rect(0, 0, width, height))
            for name, (width, height) in zip(("a", "b"), sizes)
        ]
        alignments = ()
        if alignment_axis is not None:
            alignments = (AxisAlignment(alignment_axis, "a", "b", 0, 0),)
        orderings = ()
        if ordering_axis is not None:
            orderings = (AxisOrder(ordering_axis, "a", "b"),)
        result = pack_view_groups(
            groups, drawable, alignments=alignments, orderings=orderings
        )
        expected = grid_oracle(sizes, (), alignment_axis, ordering_axis)
        assert result.status is (
            PackingStatus.PACKED if expected else PackingStatus.DOES_NOT_FIT
        )
        if not expected:
            continue
        assert_valid(result, groups, drawable)
        moved = [
            item.rectangles[f"{item.name}-0"].translated(result.translations[item.name])
            for item in groups
        ]
        if alignment_axis is not None:
            axis = alignment_axis.value
            assert moved[0].bounds[axis] == pytest.approx(moved[1].bounds[axis])
        if ordering_axis is not None:
            axis = ordering_axis.value
            assert moved[0].bounds[axis + 2] <= moved[1].bounds[axis] + 1e-12


def test_decimal_touching_edges_do_not_trigger_spurious_movement():
    groups = [
        group("a", Rect(0.1, 0.1, 0.1 + 0.2, 0.3)),
        group("b", Rect(0.3, 0.1, 0.5, 0.3)),
    ]
    result = pack_view_groups(groups, Rect(0, 0, 0.5, 0.5))
    assert result.status is PackingStatus.PACKED
    assert result.translations == {"a": (0, 0), "b": (0, 0)}


def test_packing_contract_and_implementation_are_enrolled_in_recipe_gate():
    from pathlib import Path

    from test_dodo_recipe import _load_dodo

    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    command_files = {Path(argument).name for argument in recipe["actions"][0][1][0]}
    assert Path(__file__).name in command_files
    dependencies = {Path(path).name for path in recipe["file_dep"]}
    assert {Path(__file__).name, "_drawing_view_packing.py"} <= dependencies
