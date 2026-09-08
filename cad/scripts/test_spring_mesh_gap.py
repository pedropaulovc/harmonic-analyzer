"""Exact raw-mesh separation proof, independent of SolidWorks and Blender."""

import struct

import pytest

from diagnostics import probe_spring_mesh_gap as probe


def binary_stl(triangles):
    return b" " * 80 + struct.pack("<I", len(triangles)) + b"".join(
        struct.pack("<12fH", 0, 0, 1, *sum((tuple(p) for p in triangle), ()), 0)
        for triangle in triangles
    )


def test_exact_gap_and_connected_positive_control():
    low = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    upper = [(0, 2, 0), (1, 2, 0), (0, 3, 0)]
    bank = probe.inspect_stl(binary_stl([low, upper]))
    assert len(bank["components"]) == 2
    assert bank["separating_slabs"] == [
        {"lower": 0, "upper": 1, "axis": "Y", "open_interval": [1.0, 2.0], "gap_lower_bound": 1.0}
    ]
    bridge = [low[2], upper[0], upper[1]]
    joined = probe.inspect_stl(binary_stl([low, bridge, upper]))
    assert len(joined["components"]) == 1
    assert joined["separating_slabs"] == []


def test_degenerate_triangle_is_retained_not_repaired():
    bank = probe.inspect_stl(binary_stl([[(0, 0, 0)] * 3]))
    assert bank["triangle_count"] == 1
    assert bank["components"][0]["zero_area_triangles"] == 1


@pytest.mark.parametrize("raw", [b"", b" " * 80 + struct.pack("<I", 200001), binary_stl([])])
def test_invalid_length_and_budget_refused(raw):
    with pytest.raises(ValueError, match="bounded, complete"):
        probe.inspect_stl(raw)


def test_nonfinite_coordinate_refused():
    with pytest.raises(ValueError, match="nonfinite"):
        probe.inspect_stl(binary_stl([[(float("nan"), 0, 0), (1, 0, 0), (0, 1, 0)]]))
