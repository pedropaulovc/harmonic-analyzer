"""Exact native receipt excerpts plus synthetic ink-geometry regressions."""

from copy import deepcopy
import importlib.util
import math
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "vm2_clearance", Path(__file__).with_name("analyze_vm2_datum_clearance.py")
)
clearance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clearance)

# Exact cold_open numeric excerpts from cad/out/reports/datum-placement:
# rack-native-lifecycle-original/receipt.json
# SHA256 61d727b28118ee255c13400d1c38e4835756fa0a46d2203ac2d36b5af39765b3
# rack-native-lifecycle-above/receipt.json
# SHA256 0c75ec299392ea6717f3642f742a8101fb77f75ab69bf060d98920872d824f79
# Those receipts' moved/scaled datum primitives were stale, not valid clearance
# evidence. The separate moved-position regression below preserves that failure.
DATUM_LINES = [
    [0.0, 0.21804349740134313, 0.17344369111470476, 0.0015, 0.21021748685958663, 0.1672184554564894, 0.0015],
    [0.0, 0.21021748685958663, 0.1672184554564894, 0.0015, 0.20386748685958664, 0.1672184554564894, 0.0015],
    [0.0, 0.20386748685958664, 0.1637184554564894, 0.0015, 0.19686748685958663, 0.1637184554564894, 0.0015],
    [0.0, 0.19686748685958663, 0.1637184554564894, 0.0015, 0.19686748685958663, 0.1707184554564894, 0.0015],
    [0.0, 0.19686748685958663, 0.1707184554564894, 0.0015, 0.20386748685958664, 0.1707184554564894, 0.0015],
    [0.0, 0.20386748685958664, 0.1707184554564894, 0.0015, 0.20386748685958664, 0.1637184554564894, 0.0015],
]
DATUM_TRIANGLES = [[
    0.21717196440919298, 0.17453933259055066, 0.0015,
    0.21891503039349328, 0.17234804963885886, 0.0015,
    0.2161261248186128, 0.171918508378442, 0.0015, 1.0, 0.0,
]]
ABOVE_LINES = [
    [0.0, 0.0, -1.0, -1.0, 0.2179167314369191, 0.17638202455082344, -0.0014000000000000002, 0.17372847193628543, 0.20569618047401306, -0.0014000000000000054],
    [0.0, 0.0, -1.0, -1.0, 0.22208326856308092, 0.17361797544917654, -0.0013999999999999998, 0.2179167314369191, 0.17638202455082344, -0.0014000000000000002],
    [0.0, 0.0, -1.0, -1.0, 0.17372847193628543, 0.20569618047401306, -0.0014000000000000054, 0.1438590280637145, 0.20569618047401306, -0.001399999999999898],
]
ORIGINAL_LINES = [
    [0.0, 0.0, -1.0, -1.0, 0.2182136522094996, 0.17325101133898063, -0.0014000000000000002, 0.17372847193628543, 0.12969618047401307, -0.0014000000000000054],
    [0.0, 0.0, -1.0, -1.0, 0.2217863477905004, 0.17674898866101935, -0.0013999999999999998, 0.2182136522094996, 0.17325101133898063, -0.0014000000000000002],
    [0.0, 0.0, -1.0, -1.0, 0.17372847193628543, 0.12969618047401307, -0.0014000000000000054, 0.1438590280637145, 0.12969618047401307, -0.0013999999999998976],
]


@pytest.fixture
def stage():
    return deepcopy({
        "position": [0.21021748685958663, 0.1672184554564894, 0.0015],
        "dimension_position": [0.158, 0.213, -0.0014],
        "datum_lines": DATUM_LINES, "datum_triangles": DATUM_TRIANGLES,
        "dimension_lines": ABOVE_LINES, "dimension_triangles": [],
    })


def test_actual_original_crossing_is_rejected(stage):
    stage["dimension_position"] = [0.158, 0.13699999999999998, -0.0014]
    stage["dimension_lines"] = ORIGINAL_LINES
    assert clearance.minimum_clearance(stage) == 0
    with pytest.raises(RuntimeError, match="ink clearance"):
        clearance.assert_clearance(stage)


def test_actual_above_cold_open_has_measured_clearance(stage):
    assert clearance.assert_clearance(stage) == pytest.approx(0.0019472434563040006, abs=1e-14)


def test_actual_moved_annotation_with_old_datum_ink_is_rejected(stage):
    # Exact moved position in both original/above receipts; datum ink stayed put.
    stage["position"] = [0.21821748685958664, 0.1722184554564894, 0.0015]
    with pytest.raises(ValueError, match="annotation anchor"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("offset, outcome", [(0.5e-8, "valid"), (2e-8, "stale")])
def test_anchor_consistency_uses_fixed_ten_nanometre_threshold(stage, offset, outcome):
    stage["position"][0] += offset
    if outcome == "stale":
        with pytest.raises(ValueError, match="annotation anchor"):
            clearance.minimum_clearance(stage)
        return
    assert clearance.minimum_clearance(stage) > 0.001


@pytest.mark.parametrize("field", ["position", "dimension_position"])
@pytest.mark.parametrize("bad", [None, [], [0, 0], [0, 0, 0, 0], [math.nan, 0, 0], [0, math.inf, 0], [0, 0, -math.inf], ["0", 0, 0], [True, 0, 0]])
def test_invalid_annotation_coordinates_rejected(stage, field, bad):
    stage[field] = bad
    with pytest.raises(ValueError, match="position"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("field", ["position", "dimension_position"])
def test_missing_annotation_coordinates_rejected(stage, field):
    stage.pop(field)
    with pytest.raises(ValueError, match="position"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("field", ["datum_lines", "dimension_lines", "datum_triangles", "dimension_triangles"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, "0", True])
def test_nonfinite_or_nonnumeric_primitive_rejected(stage, field, bad):
    if field == "dimension_triangles":
        stage[field] = deepcopy(DATUM_TRIANGLES)
    stage[field][0][0] = bad
    with pytest.raises(ValueError, match="primitive"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("field", ["datum_lines", "dimension_lines", "datum_triangles"])
def test_missing_ink_rejected(stage, field):
    stage[field] = []
    with pytest.raises(ValueError, match="missing"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("field", ["datum_lines", "dimension_lines", "datum_triangles"])
@pytest.mark.parametrize("row", [None, [], [0, 0]])
def test_malformed_primitive_shape_rejected(stage, field, row):
    stage[field] = [row]
    with pytest.raises(ValueError, match="primitive"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("point", [(-0.001, 0.1), (0.432, 0.1), (0.1, 0.28)])
def test_out_of_sheet_ink_rejected(stage, point):
    stage["dimension_lines"][0][4:6] = point
    with pytest.raises(ValueError, match="sheet coordinate domain"):
        clearance.minimum_clearance(stage)


def triangle_stage(winding="forward"):
    vertices = [(0.1, 0.1), (0.2, 0.1), (0.1, 0.2)]
    if winding == "reverse":
        vertices.reverse()
    triangle = [value for x, y in vertices for value in (x, y, 0)] + [1, 0]
    return {
        "position": [0.1, 0.1, 0], "dimension_position": [0.12, 0.12, 0],
        "datum_lines": [[0, 0.1, 0.1, 0, 0.09, 0.1, 0]],
        "datum_triangles": [triangle],
        "dimension_lines": [[0, 0, -1, -1, 0.12, 0.12, 0, 0.13, 0.12, 0]],
        "dimension_triangles": [],
    }


@pytest.mark.parametrize("winding", ["forward", "reverse"])
def test_segment_entirely_inside_filled_triangle_is_zero_clearance(winding):
    assert clearance.minimum_clearance(triangle_stage(winding)) == 0


def test_datum_segment_inside_dimension_triangle_is_zero_clearance():
    value = triangle_stage()
    value["dimension_triangles"] = value["datum_triangles"]
    value["datum_triangles"] = [[0.31, 0.1, 0, 0.32, 0.1, 0, 0.31, 0.11, 0, 1, 0]]
    value["datum_lines"] = [[0, 0.12, 0.12, 0, 0.13, 0.12, 0]]
    value["position"] = [0.12, 0.12, 0]
    value["dimension_lines"] = [[0, 0, -1, -1, 0.3, 0.2, 0, 0.31, 0.2, 0]]
    assert clearance.minimum_clearance(value) == 0


def test_triangle_contained_in_other_triangle_is_zero_clearance():
    value = triangle_stage()
    value["dimension_lines"] = [[0, 0, -1, -1, 0.3, 0.2, 0, 0.31, 0.2, 0]]
    value["dimension_triangles"] = [[0.12, 0.12, 0, 0.13, 0.12, 0, 0.12, 0.13, 0, 1, 0]]
    assert clearance.minimum_clearance(value) == 0


def test_segment_inside_triangle_bounding_box_but_outside_ink_is_separate():
    value = triangle_stage()
    value["dimension_lines"] = [[0, 0, -1, -1, 0.18, 0.18, 0, 0.19, 0.18, 0]]
    assert clearance.minimum_clearance(value) == pytest.approx(0.06 / math.sqrt(2))


def test_segment_on_triangle_boundary_has_zero_clearance():
    value = triangle_stage()
    value["dimension_lines"] = [[0, 0, -1, -1, 0.12, 0.1, 0, 0.13, 0.1, 0]]
    assert clearance.minimum_clearance(value) == 0


def test_degenerate_triangle_is_rejected(stage):
    stage["datum_triangles"] = [[0.1, 0.1, 0, 0.2, 0.1, 0, 0.3, 0.1, 0, 1, 0]]
    with pytest.raises(ValueError, match="degenerate"):
        clearance.minimum_clearance(stage)


@pytest.mark.parametrize("first, second, expected", [
    (((0, 0), (1, 1)), ((0, 1), (1, 0)), 0),
    (((0, 0), (1, 0)), ((1, 0), (2, 1)), 0),
    (((0, 0), (2, 0)), ((1, 0), (3, 0)), 0),
    (((0, 0), (0, 0)), ((1, 0), (2, 0)), 1),
    (((0, 0), (1, 0)), ((0, 2), (1, 2)), 2),
])
def test_segment_distance_crossing_touching_collinear_and_degenerate(first, second, expected):
    assert clearance.segment_distance(first, second) == expected


@pytest.mark.parametrize("limit", [0, -0.001, math.nan, math.inf, "0.001", True, 10**400])
def test_invalid_clearance_limit_rejected(stage, limit):
    with pytest.raises(ValueError, match="positive and finite"):
        clearance.assert_clearance(stage, limit)
