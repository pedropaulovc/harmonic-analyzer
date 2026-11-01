"""The 91829A560 sheet's shown supplier reference lines print no stray ink.

SolidWorks draws the shown construction lines grey OVER the view's edges but
UNDER the dimension extension lines, which are the same width (FRONT 1:1 of
run 20261101T085308503Z). So every line must lie under one of the sheet's own
extension lines; only a witness's start gap may leave a line bare, and then
only on a visible edge. The stacked bottom diameters also keep a clear lane.
"""

from __future__ import annotations

import pytest

import _mcmaster_91829a560 as screw
import draw_dt_vn_cone_pivot_screw as draw
from _supplier_screw_layout import supplier_screw_lane_plan, supplier_screw_margins

ROWS = {name: (value, orientation) for name, value, orientation in screw.SUPPLIER_REFERENCE_DIMENSIONS}
FAR = 1000.0  # witnesses run on to their lanes, beyond the part
# (axis, station, low, high): a horizontal segment on y=station, or vertical on x.
Carrier = tuple[str, float, float, float]


def _line(name: str) -> tuple[tuple[float, float], tuple[float, float]]:
    (x, y), (value, orientation) = screw.SUPPLIER_REFERENCE_STARTS[name], ROWS[name]
    return (x, y), ((x + value, y) if orientation == "horizontal" else (x, y + value))


def _carrier(name: str) -> Carrier:
    (x0, y0), (x1, y1) = _line(name)
    if ROWS[name][1] == "horizontal":
        return ("y", y0, min(x0, x1), max(x0, x1))
    return ("x", x0, min(y0, y1), max(y0, y1))


def _witnesses(gap: float) -> list[Carrier]:
    """Each dimension's two extension lines, from its gap out toward its lane."""
    lanes = supplier_screw_lane_plan(
        screw.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=screw.SUPPLIER_REFERENCE_PLANES,
        sides=screw.SUPPLIER_REFERENCE_SIDES,
    )
    out: list[Carrier] = []
    for name, (_, orientation) in ROWS.items():
        side = lanes[name][0]
        for x, y in _line(name):
            if orientation == "vertical":
                out.append(("y", y, *((x + gap, FAR) if side == "right" else (-FAR, x - gap))))
            else:
                out.append(("x", x, *((y + gap, FAR) if side == "top" else (-FAR, y - gap))))
    return out


# FRONT's visible edges: rims seen edge-on and silhouettes.
HEAD_R, SHOULDER_R = screw.HEAD_DIA / 2.0, screw.SHOULDER_DIA / 2.0
EDGES: tuple[Carrier, ...] = (
    ("y", 0.0, -HEAD_R, HEAD_R),  # head underside rim, over the junction
    ("y", -screw.SHOULDER_LEN, -SHOULDER_R, SHOULDER_R),  # shoulder end rim
    *(("x", side * HEAD_R, 0.0, screw.HEAD_T - screw.HEAD_CHAMFER) for side in (-1, 1)),
    *(("x", side * SHOULDER_R, -screw.SHOULDER_LEN, 0.0) for side in (-1, 1)),
)


def _bare(line: Carrier, covers: list[Carrier]) -> list[tuple[float, float]]:
    """The spans of ``line`` that no collinear cover overlaps."""
    axis, station, low, high = line
    spans = [(low, high)]
    for kind, at, start, end in covers:
        if kind == axis and abs(at - station) < 1e-9:
            spans = [
                piece
                for lo, hi in spans
                for piece in ((lo, min(hi, start)), (max(lo, end), hi))
                if piece[1] - piece[0] > 1e-9
            ]
    return spans


def test_every_reference_line_sits_on_an_edge_or_a_witness() -> None:
    assert set(ROWS) == set(screw.SUPPLIER_REFERENCE_STARTS) == set(screw.SUPPLIER_REFERENCE_SIDES)
    assert set(ROWS) == set(screw.SUPPLIER_REFERENCE_FORMATS)
    # One Front sketch: the head diameter's witnesses cover the head height.
    assert screw.SUPPLIER_REFERENCE_PLANES == {}
    major_r = screw.THREAD_MAJOR / 2.0
    assert {name: _line(name) for name in ROWS} == {
        "SupplierHeadHeight": ((-HEAD_R, 0.0), (-HEAD_R, screw.HEAD_T)),
        "SupplierHeadDiameter": ((-HEAD_R, 0.0), (HEAD_R, 0.0)),
        "SupplierShoulderLength": ((SHOULDER_R, 0.0), (SHOULDER_R, -screw.SHOULDER_LEN)),
        "SupplierShoulderDiameter": ((-SHOULDER_R, 0.0), (SHOULDER_R, 0.0)),
        # Beside the thread, in air, on the shoulder diameter's right witness.
        "SupplierThreadLength": ((SHOULDER_R, -screw.SHOULDER_LEN), (SHOULDER_R, -screw.UNDERHEAD_LEN)),
        "SupplierThreadDiameter": ((-major_r, -screw.SHOULDER_LEN), (major_r, -screw.SHOULDER_LEN)),
    }


@pytest.mark.parametrize("gap", (0.5, 0.76, 1.0))  # measured ~0.76 mm at FRONT 1:1
def test_only_witness_gaps_leave_reference_ink_bare_and_only_on_edges(gap: float) -> None:
    covers = _witnesses(gap)
    for name in ROWS:
        spans = _bare(_carrier(name), covers)
        assert sum(hi - lo for lo, hi in spans) <= gap + 1e-9, name
        axis, station = _carrier(name)[:2]
        for lo, hi in spans:  # grey on a black edge, never on paper
            assert any(
                kind == axis and abs(at - station) < 1e-9 and start - 1e-9 <= lo and hi <= end + 1e-9
                for kind, at, start, end in EDGES
            ), (name, lo, hi)
        # Up to the shoulder step, the far shoulder-length witness reaches the
        # thread chord's end: the chords and the thread length are all covered.
        if gap <= SHOULDER_R - screw.THREAD_MAJOR / 2.0 and name not in (
            "SupplierHeadHeight",
            "SupplierShoulderLength",
        ):
            assert spans == [], name


def test_shoulder_diameter_lane_drop_is_reserved_before_the_fit() -> None:
    base = supplier_screw_margins(
        screw.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=screw.SUPPLIER_REFERENCE_PLANES,
        sides=screw.SUPPLIER_REFERENCE_SIDES,
    )
    margins = draw.supplier_margins()
    assert set(margins) == set(base) == {"*Front"}
    left, bottom, right, top = base["*Front"]
    assert margins["*Front"] == (left, bottom + draw.SHOULDER_DIAMETER_DROP_M, right, top)
    lanes = supplier_screw_lane_plan(
        screw.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=screw.SUPPLIER_REFERENCE_PLANES,
        sides=screw.SUPPLIER_REFERENCE_SIDES,
    )
    # Ø.190 inner, Ø.250 outer: the drop separates exactly that stacked pair.
    assert lanes["SupplierThreadDiameter"] == ("bottom", pytest.approx(0.006))
    assert lanes["SupplierShoulderDiameter"] == ("bottom", pytest.approx(0.014))
    assert draw.SHOULDER_DIAMETER_DROP_M > 0.0


def test_lowering_moves_the_whole_shoulder_diameter_and_reads_it_back(monkeypatch) -> None:
    events: list[object] = []

    class Annotation:
        position = (0.1, 0.05, 0.0)

        def GetPosition(self):
            return self.position

        def SetPosition2(self, x, y, z):
            events.append(("set", display.OffsetText, x, y))
            self.position = (x, y, z)
            return True

    class Display:
        OffsetText = True

        def GetAnnotation(self):
            return annotation

    annotation, display = Annotation(), Display()
    monkeypatch.setattr(draw, "_early_bound", lambda raw, _interface: raw)
    monkeypatch.setattr(draw, "rebuild_drawing", lambda _adapter, *, label: events.append("rebuild"))
    draw._lower_shoulder_diameter(object(), {"SupplierShoulderDiameter": display})
    # Offset mode off first, so the dimension line moves with its text.
    assert events == [("set", False, 0.1, pytest.approx(0.05 - draw.SHOULDER_DIAMETER_DROP_M)), "rebuild"]

    annotation.SetPosition2 = lambda *_args: False
    with pytest.raises(RuntimeError, match="failed to lower"):
        draw._lower_shoulder_diameter(object(), {"SupplierShoulderDiameter": display})
