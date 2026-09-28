"""Observable package contract for the frame assembly drawing."""

import draw_frame_assembly as drawing


def test_frame_package_bom_identifies_all_29_released_components() -> None:
    assert drawing.BOM_QUANTITIES == {
        "harmonic-base": 1,
        "tube-frame": 4,
        "tube-frame-cap": 4,
        "rocker-arm-support": 1,
        "lag-screw": 4,
        "top-frame": 1,
        "nameplate": 1,
        "fillister-screw": 4,
        "frame-cross-screw": 8,
        "gooseneck-set-screw": 1,
    }
    assert drawing.BOM_PART_NUMBERS == {
        "harmonic-base": "MHA-035",
        "tube-frame": "MHA-083",
        "tube-frame-cap": "MHA-133",
        "rocker-arm-support": "MHA-089",
        "lag-screw": "MHA-039",
        "top-frame": "MHA-077",
        "nameplate": "MHA-086",
        "fillister-screw": "MHA-030",
        "frame-cross-screw": "MHA-132",
        "gooseneck-set-screw": "MHA-118",
    }


# --- sheet projection of model points -------------------------------------
#
# The doubles below are raw dispatches: they answer ``InvokeTypes`` only and
# assert the whole (dispid, lcid, flags, return type, argument types) header
# the SolidWorks 2026 type library gives each member (flags 1 = method,
# 2 = property get; 9 = IDispatch, 12 = VARIANT).

import math  # noqa: E402
import re  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

import _drawing_common  # noqa: E402

GET_MATH_UTILITY = (132, 0, 1, (9, 0), ())
MODEL_TO_VIEW_TRANSFORM = (221, 0, 2, (9, 0), ())
CREATE_POINT = (5, 0, 1, (9, 0), ((12, 1),))
MULTIPLY_TRANSFORM = (1, 0, 1, (9, 0), ((9, 1),))
ARRAY_DATA = (3, 0, 2, (12, 0), ())


class RawDispatch:
    """A bare ``PyIDispatch`` stand-in keyed by dispid; any other header fails."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def InvokeTypes(self, dispid, lcid, flags, ret_type, arg_types, *args):  # noqa: N802
        header = (dispid, lcid, flags, ret_type, arg_types)
        self.calls.append(header)
        assert dispid in self.answers, f"unexpected dispid {dispid}"
        expected, answer = self.answers[dispid]
        assert header == expected
        return answer(*args) if callable(answer) else answer


# Model-to-sheet: rotate +90 deg about Z, scale 1:5, then translate to the
# view centre (0.150, 0.100) m.  ArrayData layout: row-major rotation (row i
# is the image of axis i), translation, scale, three unused.
VIEW_TRANSFORM = (0, 1, 0, -1, 0, 0, 0, 0, 1, 0.150, 0.100, 0.0, 0.2, 0, 0, 0)


class Projection:
    """``adapter`` and ``view`` whose projection runs through raw dispatches."""

    def __init__(self, *, fail_at: int | None = None):
        # The raw headers come from the checked-in makepy wrapper.
        pytest.importorskip("win32com.client")
        self.created = 0
        self.fail_at = fail_at
        self.transform = RawDispatch({})
        self.transform.values = VIEW_TRANSFORM
        self.utility = RawDispatch({CREATE_POINT[0]: (CREATE_POINT, self._point)})
        self.adapter = SimpleNamespace(
            swApp=RawDispatch({GET_MATH_UTILITY[0]: (GET_MATH_UTILITY, self.utility)})
        )
        self.view = RawDispatch(
            {MODEL_TO_VIEW_TRANSFORM[0]: (MODEL_TO_VIEW_TRANSFORM, self.transform)}
        )

    def _point(self, array):
        assert array.varianttype == 8197  # VT_ARRAY | VT_R8
        index, self.created = self.created, self.created + 1
        xyz = tuple(array.value)

        def multiply(transform):
            assert transform is self.transform
            if index == self.fail_at:
                return None
            v = transform.values
            rotated = [sum(xyz[i] * v[3 * i + j] for i in range(3)) for j in range(3)]
            sheet = [v[12] * rotated[j] + v[9 + j] for j in range(3)]
            return RawDispatch({ARRAY_DATA[0]: (ARRAY_DATA, tuple(sheet))})

        return RawDispatch({MULTIPLY_TRANSFORM[0]: (MULTIPLY_TRANSFORM, multiply)})

    def reads(self, header):
        dispatches = {GET_MATH_UTILITY: self.adapter.swApp, MODEL_TO_VIEW_TRANSFORM: self.view}
        return dispatches[header].calls.count(header)


def test_a_batch_projects_every_point_through_one_transform_read() -> None:
    projection = Projection()
    points = [(0.010, 0.020, 0.030), (0.100, 0.0, 0.0), (-0.050, 0.050, 0.0)]
    sheet = _drawing_common.model_points_in_view(
        projection.adapter, projection.view, points, label="batch"
    )
    flat = [value for xy in sheet for value in xy]
    assert flat == pytest.approx([0.146, 0.102, 0.150, 0.120, 0.140, 0.090])
    assert projection.reads(MODEL_TO_VIEW_TRANSFORM) == 1
    assert projection.reads(GET_MATH_UTILITY) == 1
    assert projection.created == 3


def test_one_point_projects_to_the_same_sheet_position_as_a_batch() -> None:
    projection = Projection()
    assert _drawing_common.model_point_in_view(
        projection.adapter, projection.view, (0.010, 0.020, 0.030), label="one"
    ) == pytest.approx((0.146, 0.102))


def test_a_failed_point_names_its_index_identity_and_progress(monkeypatch) -> None:
    recorded = {}
    monkeypatch.setattr(
        _drawing_common._telemetry, "annotate", lambda **attrs: recorded.update(attrs)
    )
    projection = Projection(fail_at=2)
    with pytest.raises(RuntimeError) as failure:
        _drawing_common.model_points_in_view(
            projection.adapter,
            projection.view,
            [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.002, 0.0, 0.0)],
            label="ends",
            names=["a start", "a end", "b start"],
        )
    message = str(failure.value)
    assert "ends: b start (index 2 of 3) at model (0.002, 0.0, 0.0)" in message
    assert "failed after 2 projected" in message
    assert recorded == {
        "points": 3, "failed_index": 2, "failed_point": "b start", "projected": 2
    }


class _Curve:
    def __init__(self, line: bool) -> None:
        self.line = line

    def IsLine(self) -> bool:  # noqa: N802
        return self.line


class _Edge:
    def __init__(self, key, *, line: bool = True) -> None:
        self.key = key
        self.line = line

    def GetCurve(self) -> _Curve:  # noqa: N802
        return _Curve(self.line)


class _Full:
    """The drawing component whose ``Transform2`` places the part."""

    def __init__(self, values=None) -> None:
        self.values = values
        self.reads = 0

    @property
    def Transform2(self):  # noqa: N802
        self.reads += 1
        if self.values is None:
            raise RuntimeError("an edgeless component's transform must not be read")
        return SimpleNamespace(ArrayData=self.values)


# Component-local -> assembly: translate +10 mm along assembly Y.
SHIFT_Y = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0.0, 0.010, 0.0, 1.0, 0, 0, 0)


def test_top_casting_pick_takes_the_rightmost_edge_long_on_the_sheet(monkeypatch) -> None:
    # Sheet (x, y) = 0.2 * (-(y + 0.010), x) + (0.150, 0.100) for local (x, y).
    left = _Edge((0.0, -0.010, 0.0, 0.050, -0.010, 0.0))  # min x 0.150, 10 mm
    right = _Edge((0.050, -0.110, 0.0, 0.050, -0.010, 0.0))  # min x 0.150, 20 mm
    rightmost = _Edge((0.050, -0.110, 0.0, 0.0, -0.110, 0.0))  # min x 0.170, 10 mm
    # Widest right of all, but 10 mm in the model is 2 mm on the 1:5 sheet.
    short = _Edge((0.0, -0.210, 0.0, 0.010, -0.210, 0.0))
    arc = _Edge((0.0, -0.500, 0.0, 0.050, -0.500, 0.0), line=False)
    unreadable = _Edge(None)
    casting, edgeless = _Full(SHIFT_Y), _Full()
    entities = {
        # Order matters: pairing one edge's end with the next edge's start
        # would give every candidate min x 0.150 and lose ``rightmost``.
        "casting": [arc, left, unreadable, right, rightmost, short],
        "boss": [arc],
    }
    monkeypatch.setattr(
        drawing,
        "visible_component_entities",
        lambda _view, component, _kind: entities[component.stem],
    )
    monkeypatch.setattr(drawing, "_edge_endpoint_key", lambda _adapter, edge: edge.key)
    projection = Projection()

    winner = drawing._exposed_top_casting_edge(
        projection.adapter,
        projection.view,
        [
            (SimpleNamespace(stem="casting", Name2="top-frame-1"), casting),
            (SimpleNamespace(stem="boss", Name2="boss-1"), edgeless),
        ],
    )

    assert winner is rightmost
    assert (casting.reads, edgeless.reads) == (1, 0)
    assert projection.reads(MODEL_TO_VIEW_TRANSFORM) == 1
    assert projection.created == 8  # two ends of each of the four lines


# Short-leader balloons: a drawing window whose GetDisplayData ring depends on
# the viewport. Fit to the sheet a pixel is 0.94 mm on a 640-high seat window
# and 0.68 mm on an 820-high one (swmaker000005/7/8 vs 000004/6); zoomed onto
# the 24 mm square it is 24 mm over the window height.
_FIT_PIXEL_M = {640: 0.00094, 820: 0.00068}
_ARROWTIP = (0.1511, 0.2664)
_OFFSET = (0.008, 0.016)
_TARGET = (_ARROWTIP[0] + _OFFSET[0], _ARROWTIP[1] + _OFFSET[1])
_RING_R = 0.00475
# The ring GetDisplayData draws at fit is smaller, and after the rebuild at
# fit a leader keeps the start the fit render gave it, whatever the zoom (item
# 2 on swmaker000008 and 000005, runs 20260928T144159300Z and
# 20260928T145256004Z: 4.19 mm from a centre whose zoomed ring is 4.89 mm).
_RING_R_FIT = 0.00405


class _Window:
    """``adapter.currentModel``: the zoom state, and what ran under which.

    ``fit_drift_px``: how far GetDisplayData's ring sits off the model at fit,
    in fit pixels. ``rebuild``: what EditRebuild3 does to the balloon besides
    leaving its leader start at the fit ring: move its SetPosition anchor
    (``"position"``) or only its ring (``"ring"``) 1 mm, grow the ring 1 mm
    (``"radius"``), or move the arrowtip 1 mm (``"tip"``). ``fault``: raise
    from ViewZoomTo2 (``"zoom"``) or SetPosition (``"position"``), or place
    the leader starting 1 mm inside the ring (``"leader"``).
    """

    def __init__(
        self,
        window_px: int,
        *,
        fit_drift_px: float,
        fault: str | None = None,
        rebuild: str | None = None,
    ):
        self.window_px = window_px
        self.fit_drift_px = fit_drift_px
        self.fault = fault
        self.rebuild = rebuild
        self.balloon: _ShortBalloon | None = None
        self.span: float | None = None  # None: fit to the sheet
        self.log: list[tuple[str, float | None]] = []

    def pixel(self) -> float:
        return _FIT_PIXEL_M[self.window_px] if self.span is None else self.span / self.window_px

    def ring_r(self) -> float:
        return (_RING_R_FIT if self.span is None else _RING_R) + self.balloon.ring_grow

    def ViewZoomTo2(self, x1, y1, _z1, x2, _y2, _z2):  # noqa: N802
        self.span = x2 - x1
        self.log.append(("zoom", self.span))
        if self.fault == "zoom":
            raise RuntimeError("ViewZoomTo2 moved the view, then failed")

    def ViewZoomtofit2(self):  # noqa: N802
        self.span = None
        self.log.append(("fit", None))

    def GraphicsRedraw2(self):  # noqa: N802
        pass

    def EditRebuild3(self):  # noqa: N802
        self.log.append(("rebuild", self.span))
        balloon = self.balloon
        balloon.leader_r = _RING_R_FIT
        if self.rebuild == "position":
            balloon.position = (balloon.position[0] + 0.001, balloon.position[1])
        if self.rebuild in ("position", "ring"):
            balloon.centre = (balloon.centre[0] + 0.001, balloon.centre[1])
        if self.rebuild == "radius":
            balloon.ring_grow = 0.001
        if self.rebuild == "tip":
            balloon.tip = (balloon.tip[0] + 0.001, balloon.tip[1])


class _ShortBalloon:
    """One balloon: note, annotation and its single attached edge."""

    def __init__(self):
        self.entity = object()
        self.position = (_ARROWTIP[0] - 0.010, _ARROWTIP[1] + 0.005)
        self.centre = self.position
        self.leader_r = _RING_R_FIT
        self.ring_grow = 0.0
        self.tip = _ARROWTIP

    def GetAnnotation(self):  # noqa: N802
        return self

    def GetSpecificAnnotation(self):  # noqa: N802
        return self

    def GetAttachedEntities3(self):  # noqa: N802
        return (self.entity,)


def _short_balloon_rig(monkeypatch, window: _Window):
    balloon = _ShortBalloon()
    window.balloon = balloon
    placed_at: list[tuple[tuple[float, float], float | None]] = []
    events: dict[str, dict] = {}

    def position(_adapter, notes, *, item_number, position_xy, label):
        assert notes == [balloon] and item_number == "5"
        placed_at.append((tuple(position_xy), window.span))
        if window.fault == "position":
            raise RuntimeError("SetPosition failed")
        balloon.position = balloon.centre = tuple(position_xy)
        balloon.leader_r = _RING_R - (0.001 if window.fault == "leader" else 0.0)

    def readback(_adapter, annotation, entity, item):
        assert annotation is balloon and entity is balloon.entity and item == "5"
        pixel = window.pixel()
        drift = window.fit_drift_px * pixel if window.span is None else 0.0
        centre = (balloon.centre[0] + drift, balloon.centre[1] + drift)
        angle = math.atan2(balloon.tip[1] - centre[1], balloon.tip[0] - centre[0])
        start = (
            centre[0] + balloon.leader_r * math.cos(angle),
            centre[1] + balloon.leader_r * math.sin(angle),
        )
        window.log.append(("read", window.span))
        return {
            "failed_checks": [],
            "actual_leader_points": (*start, 0.0, *balloon.tip, 0.0),
            "annotation_position": (*balloon.position, 0.0),
            "rendered_circle": (*centre, window.ring_r()),
            "viewport_pixel_bounds_m": (pixel, pixel),
        }

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "position_bom_balloon", position)
    monkeypatch.setattr(drawing, "_frame_balloon_binding_readback", readback)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.__setitem__(name, attrs)
    )
    adapter = SimpleNamespace(currentModel=window)
    view = SimpleNamespace(UpdateViewDisplayGeometry=lambda: None)

    def run():
        return drawing._short_frame_balloon(adapter, view, balloon, "5", _OFFSET)

    return run, placed_at, events


@pytest.mark.parametrize("window_px", [640, 820])
def test_short_balloon_places_and_rechecks_zoomed_around_the_fit_rebuild(
    monkeypatch, window_px
) -> None:
    """The ring is placed where a pixel is tens of microns on either seat, so
    both windows ask SetPosition for the same point. After the rebuild at fit
    it is read zoomed again: the fit read's ring is off by two fit pixels,
    as GetDisplayData renders at fit, and does not decide; nor does the
    leader start the rebuild left inside the zoomed ring, which the PDF does
    not draw from."""
    window = _Window(window_px, fit_drift_px=2.0)
    run, placed_at, events = _short_balloon_rig(monkeypatch, window)
    run()
    [(position_xy, span)] = placed_at
    zoomed = 2 * drawing._SHORT_BALLOON_ZOOM_HALF
    assert span == pytest.approx(zoomed)
    assert position_xy == pytest.approx(_TARGET)
    assert window.log[-6:] == [
        ("fit", None), ("rebuild", None), ("read", None),
        ("zoom", pytest.approx(zoomed)), ("read", pytest.approx(zoomed)), ("fit", None),
    ]
    final = events["drawing.frame_short_balloon"]
    assert final["failed_checks"] == []
    assert final["fit"]["viewport_pixel_bounds_m"][0] == _FIT_PIXEL_M[window_px]
    assert final["after"]["rendered_circle"][:2] == pytest.approx(_TARGET)


@pytest.mark.parametrize("window_px", [640, 820])
@pytest.mark.parametrize(
    ("rebuild", "fault", "failed"),
    [
        ("position", None, ["fit:position_moved", "rebuilt:circle_position"]),
        ("ring", None, ["rebuilt:circle_position"]),
        ("radius", None, ["rebuilt:ring_radius"]),
        ("tip", None, ["rebuilt:arrowtip_moved"]),
        (None, "leader", ["zoomed:leader_inside_ring"]),
    ],
)
def test_short_balloon_fails_when_placed_inside_or_moved_by_the_rebuild(
    monkeypatch, window_px, rebuild, fault, failed
) -> None:
    """A zoomed read on target proves nothing about the rebuilt drawing the
    export prints. The rebuild moving the SetPosition anchor, the ring or the
    arrowtip 1 mm, or growing the ring 1 mm, fails the leaf, as does a placed
    leader starting 1 mm inside its ring; the view is back at fit."""
    window = _Window(window_px, fit_drift_px=0.0, rebuild=rebuild, fault=fault)
    run, _placed_at, events = _short_balloon_rig(monkeypatch, window)
    with pytest.raises(RuntimeError, match="frame balloon 5 short placement failed"):
        run()
    assert events["drawing.frame_short_balloon"]["failed_checks"] == failed
    assert window.span is None


@pytest.mark.parametrize(
    ("rebuild", "failed"),
    [
        (None, None),
        ("position", ["circle_position", "position_moved"]),
        ("ring", ["circle_position"]),
        ("radius", ["ring_radius"]),
        ("tip", ["arrowtip_moved"]),
    ],
)
def test_a_later_rebuild_that_moves_a_placed_short_balloon_fails_the_final_proof(
    monkeypatch, rebuild, failed
) -> None:
    """Item 5 passes its own placement, then the next balloons' and the
    finalizer's rebuilds re-solve it (Codex on #1111). Read zoomed again
    after the last one, a moved anchor, ring or arrowtip, or a grown ring,
    fails the drawing naming the balloon; untouched, it passes, and the
    window is back at fit either way."""
    window = _Window(640, fit_drift_px=0.0)
    run, _placed_at, _events = _short_balloon_rig(monkeypatch, window)
    proof = drawing._FrameBalloonProof(rebound=frozenset(), bound=(), short=(run(),))
    monkeypatch.setattr(drawing, "_activate_sheet", lambda _adapter, _name: None)
    monkeypatch.setattr(drawing, "assert_balloon_landings", lambda _adapter, landings: None)
    window.rebuild = rebuild
    window.EditRebuild3()
    adapter = SimpleNamespace(currentModel=window)
    if failed is None:
        drawing._assert_frame_balloons_settled(adapter, [], proof)
    else:
        with pytest.raises(
            RuntimeError, match=re.escape(f"frame balloon 5 short leader: {failed!r}")
        ):
            drawing._assert_frame_balloons_settled(adapter, [], proof)
    assert window.span is None


@pytest.mark.parametrize("rebuild", [None, "tip"])
def test_a_later_rebuild_that_moves_a_rebound_balloons_tip_fails_the_final_proof(
    monkeypatch, rebuild
) -> None:
    """A rebound balloon without a short leader (items 3 and 4) keeps the
    arrowtip read after the rebind's last rebuild, to the landing tolerance.
    Its hit-tested component landing is the one the rebind replaced, so only
    the families left alone are proven against theirs."""
    window = _Window(640, fit_drift_px=0.0)
    _short_balloon_rig(monkeypatch, window)
    balloon = window.balloon
    proof = drawing._FrameBalloonProof(
        rebound=frozenset({"lag-screw"}),
        bound=(drawing._BoundBalloonProof("5", balloon, balloon.entity, balloon.tip),),
        short=(),
    )
    landings = [SimpleNamespace(stem="lag-screw"), SimpleNamespace(stem="nameplate")]
    proven = []
    monkeypatch.setattr(drawing, "_activate_sheet", lambda _adapter, _name: None)
    monkeypatch.setattr(
        drawing, "assert_balloon_landings", lambda _adapter, given: proven.extend(given)
    )
    window.rebuild = rebuild
    window.EditRebuild3()
    adapter = SimpleNamespace(currentModel=window)
    if rebuild is None:
        drawing._assert_frame_balloons_settled(adapter, landings, proof)
    else:
        with pytest.raises(RuntimeError, match=re.escape("frame balloon 5: ['arrowtip_moved']")):
            drawing._assert_frame_balloons_settled(adapter, landings, proof)
    assert proven == landings[1:]


@pytest.mark.parametrize("fault", ["zoom", "position"])
def test_short_balloon_restores_fit_when_zooming_or_positioning_fails(
    monkeypatch, fault
) -> None:
    """ViewZoomTo2 can move the view and then raise; SetPosition can raise
    zoomed. Either way the error is the one raised and the window is left at
    fit, the zoom every later pick and the export assume."""
    window = _Window(640, fit_drift_px=0.0, fault=fault)
    run, placed_at, _events = _short_balloon_rig(monkeypatch, window)
    message = "ViewZoomTo2 moved the view" if fault == "zoom" else "SetPosition failed"
    with pytest.raises(RuntimeError, match=message):
        run()
    assert window.span is None and window.log[-1] == ("fit", None)
    assert len(placed_at) == (fault == "position")
