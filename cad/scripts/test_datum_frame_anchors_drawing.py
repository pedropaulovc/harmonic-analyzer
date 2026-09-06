"""Native datum frame relations are observations, not horizontal-only rules."""

from types import SimpleNamespace

import pytest

from diagnostics import probe_datum_frame_anchors as probe


@pytest.mark.parametrize(
    "point,side",
    [
        ((0, 0.5, 0), "left"),
        ((1, 0.5, 0), "right"),
        ((0.5, 0, 0), "bottom"),
        ((0.5, 1, 0), "top"),
    ],
)
def test_all_four_frame_midpoints_are_measured(point, side):
    result = probe.frame_relation(point, (0, 0, 1, 1))
    assert result["matching_side_midpoints"] == (side,)
    assert result["side_midpoint_errors_m"][side] == 0


def test_off_frame_anchor_is_retained_not_projected_or_rejected():
    result = probe.frame_relation((0.1, 0.2, -0.00315), (0.3, 0.4, 0.307, 0.407))
    assert result["matching_side_midpoints"] == ()
    assert result["offset_from_center"] == pytest.approx((-0.2035, -0.2035))


@pytest.mark.parametrize(
    "point,frame",
    [
        ((0, 1), (0, 0, 1, 1)),
        ((0, 0, float("nan")), (0, 0, 1, 1)),
        ((0, 0, 0), (0, 0, 0, 1)),
    ],
)
def test_invalid_native_frame_coordinates_fail(point, frame):
    with pytest.raises(ValueError):
        probe.frame_relation(point, frame)


@pytest.mark.parametrize("value", [-1, 10001])
def test_native_counts_are_bounded(value):
    with pytest.raises(RuntimeError, match="unbounded"):
        probe.count(value)


def test_export_identity_replacement_is_not_hidden_by_same_values():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    with pytest.raises(RuntimeError, match="identity changed"):
        probe.compare(app, {"A": {}}, {"A": (object(),)}, {"A": {}}, {"A": (object(),)})
