"""Observable package contract for the frame assembly drawing."""

import draw_fr_frame_assembly as drawing


def test_frame_package_bom_identifies_all_29_released_components() -> None:
    assert drawing.BOM_QUANTITIES == {
        "fr-harmonic-base": 1,
        "fr-tube-frame": 4,
        "fr-vn-tube-frame-cap": 4,
        "fr-rocker-arm-support": 1,
        "fr-vn-lag-screw": 4,
        "fr-top-frame": 1,
        "fr-nameplate": 1,
        "sh-vn-brass-fillister-screw": 4,
        "fr-vn-frame-cross-screw": 8,
        "fr-vn-gooseneck-set-screw": 1,
    }
    assert drawing.BOM_PART_NUMBERS == {
        "fr-harmonic-base": "MHA-FR-01",
        "fr-tube-frame": "MHA-FR-03",
        "fr-vn-tube-frame-cap": "MHA-FR-VN-54",
        "fr-rocker-arm-support": "MHA-FR-05",
        "fr-vn-lag-screw": "MHA-FR-VN-51",
        "fr-top-frame": "MHA-FR-02",
        "fr-nameplate": "MHA-FR-04",
        "sh-vn-brass-fillister-screw": "MHA-SH-VN-51",
        "fr-vn-frame-cross-screw": "MHA-FR-VN-53",
        "fr-vn-gooseneck-set-screw": "MHA-FR-VN-52",
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

import _drawing_projection  # noqa: E402
from _drawing_balloons import _ComponentLeaf  # noqa: E402
import _telemetry  # noqa: E402

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


def test_checked_heights_print_their_model_values() -> None:
    """The overall reference prints the cap stack's .001 grid exactly. The top
    cross-bore axis (MHA-FR-02's taps, .72 under its rail top) sits on the
    .001 grid too, so it prints three places, with the tape-read band the
    setting needs (#2389) rather than the title block's .XXX. The dimension carries
    only its value and band; the setting step names it, from the model."""
    from _title_block_units import render_number

    cap_in = drawing.CAP_TOP_Y / 25.4
    assert cap_in == pytest.approx(round(cap_in, drawing.HEIGHT_PLACES), abs=1e-9)
    assert drawing.HEIGHT_PLACES == 3
    assert drawing.TOP_AXIS_HEIGHT_PLACES == 3
    axis_in = drawing.TOP_SCREW_Y / 25.4
    assert axis_in == pytest.approx(round(axis_in, 3), abs=1e-9)
    assert drawing.TOP_AXIS_HEIGHT_BAND_MM == pytest.approx(0.030 * 25.4)
    printed = render_number(axis_in, drawing.UNIT, drawing.TOP_AXIS_HEIGHT_PLACES)
    band = render_number(
        drawing.TOP_AXIS_HEIGHT_BAND_MM / 25.4, drawing.UNIT, drawing.TOP_AXIS_HEIGHT_PLACES
    )
    assert drawing.TOP_AXIS_HEIGHT_TEXT == f"{printed} ±{band}"
    assert drawing.TOP_AXIS_HEIGHT_TEXT in _step(drawing.steps.TOP_AXIS_SET_KEY)
    assert not hasattr(drawing, "TOP_AXIS_HEIGHT_SUFFIX")


def test_top_frame_underside_is_the_knife_mount_seat_plane() -> None:
    from build_sm_knife_mount import CASTING_UNDERSIDE_Y, MOUNT_GAP
    from fr_frame_attachment_spec import TOP_FRAME_MID_Y, TOP_FRAME_RAIL_TOP_Y
    from fr_top_frame_spec import HALF_H

    # The knife mounts clamp to it and the hanger washers seat on the rail
    # top one band above it: exact contact, no overlap and no gap.
    assert MOUNT_GAP == 0.0
    assert TOP_FRAME_MID_Y - HALF_H == pytest.approx(CASTING_UNDERSIDE_Y, abs=1e-9)
    assert TOP_FRAME_MID_Y + HALF_H == pytest.approx(TOP_FRAME_RAIL_TOP_Y, abs=1e-9)


def test_a_batch_projects_every_point_through_one_transform_read() -> None:
    projection = Projection()
    points = [(0.010, 0.020, 0.030), (0.100, 0.0, 0.0), (-0.050, 0.050, 0.0)]
    sheet = _drawing_projection.model_points_in_view(
        projection.adapter, projection.view, points, label="batch"
    )
    flat = [value for xy in sheet for value in xy]
    assert flat == pytest.approx([0.146, 0.102, 0.150, 0.120, 0.140, 0.090])
    assert projection.reads(MODEL_TO_VIEW_TRANSFORM) == 1
    assert projection.reads(GET_MATH_UTILITY) == 1
    assert projection.created == 3


def test_one_point_projects_to_the_same_sheet_position_as_a_batch() -> None:
    projection = Projection()
    assert _drawing_projection.model_point_in_view(
        projection.adapter, projection.view, (0.010, 0.020, 0.030), label="one"
    ) == pytest.approx((0.146, 0.102))


def test_a_failed_point_names_its_index_identity_and_progress(monkeypatch) -> None:
    recorded = {}
    monkeypatch.setattr(
        _telemetry, "annotate", lambda **attrs: recorded.update(attrs)
    )
    projection = Projection(fail_at=2)
    with pytest.raises(RuntimeError) as failure:
        _drawing_projection.model_points_in_view(
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
            (SimpleNamespace(stem="casting", Name2="fr-top-frame-1"), casting),
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
    from ViewZoomTo2 (``"zoom"``) or the zoomed SetPosition (``"position"``),
    or place the leader starting 1 mm inside the ring (``"leader"``).
    ``centre``: the sheet point the window is zoomed onto.
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
        self.centre: tuple[float, float] | None = None
        self.log: list[tuple[str, float | None]] = []

    def pixel(self) -> float:
        return _FIT_PIXEL_M[self.window_px] if self.span is None else self.span / self.window_px

    def ring_r(self) -> float:
        return (_RING_R_FIT if self.span is None else _RING_R) + self.balloon.ring_grow

    def ViewZoomTo2(self, x1, y1, _z1, x2, y2, _z2):  # noqa: N802
        self.span = x2 - x1
        self.centre = ((x1 + x2) / 2, (y1 + y2) / 2)
        self.log.append(("zoom", self.span))
        if self.fault == "zoom":
            raise RuntimeError("ViewZoomTo2 moved the view, then failed")

    def ViewZoomtofit2(self):  # noqa: N802
        self.span = self.centre = None
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
        if window.fault == "position" and window.span is not None:
            raise RuntimeError("SetPosition failed")
        outside = window.span is not None and any(
            abs(ring - centre) > window.span / 2
            for ring, centre in zip(balloon.centre, window.centre)
        )
        balloon.position = balloon.centre = tuple(position_xy)
        if outside:
            # Run 20261010T073339590Z: item 5's ring, read 52 mm above the
            # zoomed window before SetPosition, landed 1.89 zoomed pixels high.
            balloon.centre = (position_xy[0], position_xy[1] + 1.89 * window.pixel())
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
    [(fit_xy, fit_span), (position_xy, span)] = placed_at
    zoomed = 2 * drawing._SHORT_BALLOON_ZOOM_HALF
    assert fit_span is None and fit_xy == pytest.approx(_TARGET)
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
def test_short_balloon_starting_above_the_zoomed_window_is_placed_at_fit_first(
    monkeypatch, window_px
) -> None:
    """Item 5 starts 52 mm above its target, outside the 24 mm zoomed window,
    where its ring reads a pixel lower against its anchor than inside it; a
    zoomed placement from there landed 1.89 zoomed pixels high (run
    20261010T073339590Z). Placed at fit first, the zoomed placement starts
    inside the window and its ring lands on target."""
    window = _Window(window_px, fit_drift_px=0.0)
    run, placed_at, events = _short_balloon_rig(monkeypatch, window)
    window.balloon.position = window.balloon.centre = (_TARGET[0] - 0.004, _TARGET[1] + 0.052)
    run()
    zoomed = 2 * drawing._SHORT_BALLOON_ZOOM_HALF
    assert [span for _xy, span in placed_at] == [None, pytest.approx(zoomed)]
    final = events["drawing.frame_short_balloon"]
    assert final["failed_checks"] == []
    assert final["placed"]["rendered_circle"][:2] == pytest.approx(_TARGET)


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
        rebound=frozenset({"fr-vn-lag-screw"}),
        bound=(drawing._BoundBalloonProof("5", balloon, balloon.entity, balloon.tip),),
        short=(),
    )
    landings = [SimpleNamespace(stem="fr-vn-lag-screw"), SimpleNamespace(stem="fr-nameplate")]
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
    zoomed = 2 * drawing._SHORT_BALLOON_ZOOM_HALF
    expected = [None, pytest.approx(zoomed)] if fault == "position" else [None]
    assert [span for _xy, span in placed_at] == expected


STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)


def _printed_steps(text: str) -> dict[int, list[str]]:
    """Every numbered step of ``text``: its number to its printed lines."""
    lines = text.splitlines()
    heads = [i for i, line in enumerate(lines) if STEP_HEAD.match(line)]
    bodies = {}
    for start in heads:
        body = []
        for line in lines[start:]:
            if not line.strip() or (body and not line.startswith(drawing.STEPS_HANG)):
                break
            body.append(line)
        bodies[int(STEP_HEAD.match(lines[start]).group(1))] = body
    return bodies


def _step(key: str) -> str:
    lines = _printed_steps(drawing.ASSEMBLY_STEPS)[drawing.steps.step_number(key)]
    return " ".join(line.strip() for line in lines)


def test_step_numbers_follow_the_registry_and_unknown_keys_are_refused() -> None:
    steps = drawing.steps
    assert tuple(drawing.STEP_TEXT) == steps.SEQUENCE
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
        assert steps.step_ref(key) == f"MHA-FR-00 STEP {index}"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")
    assert list(_printed_steps(drawing.ASSEMBLY_STEPS)) == list(
        range(1, len(steps.SEQUENCE) + 1)
    )


def test_every_step_is_one_short_instruction() -> None:
    # Rule 22: at most six printed lines, never wider than the column.
    for key in drawing.steps.SEQUENCE:
        lines = drawing.numbered_step(key)
        assert 1 <= len(lines) <= drawing.STEP_MAX_LINES, key
        assert max(map(len, lines)) <= drawing.STEPS_LINE_WIDTH, key
        assert lines[0].startswith(f"{drawing.steps.step_number(key)}. ")
        assert all(line.startswith(drawing.STEPS_HANG) for line in lines[1:])


def test_a_wrap_never_parts_an_item_or_step_reference_from_its_number() -> None:
    for key in drawing.steps.SEQUENCE:
        lines = drawing.numbered_step(key)
        for line in lines:
            assert not re.search(r"\b(ITEMS?|STEPS?)$", line), (key, line)
        for line in lines[1:]:
            assert not re.match(r"(MIN\b|±)", line.strip()), (key, line)


def test_each_check_and_remedy_is_its_own_step() -> None:
    # A step that checks only checks; a remedy (IF ...) is its own step.
    for key, text in drawing.STEP_TEXT.items():
        if text.startswith("CHECK"):
            assert " AND REPEAT" not in text and "IF " not in text, key
        if text.startswith("IF "):
            assert "CHECK " not in text, key


def test_steps_flow_in_order_through_the_columns_of_sheets_3_onward() -> None:
    notes = drawing.STEP_NOTES
    assert [column.sheet for column, _text in notes] == list(drawing.STEP_SHEET_NAMES)
    assert drawing.SHEET_NAMES[2:] == drawing.STEP_SHEET_NAMES
    sheets = set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_SCALES) == sheets
    printed = []
    for column, text in notes:
        lines = text.splitlines()
        assert len(lines) <= column.max_lines
        assert column.xy[1] - len(lines) * drawing.STEPS_LINE_PITCH >= 0.0127 + 0.005
        assert (
            column.xy[0] + max(map(len, lines)) * drawing.STEPS_CHAR_WIDTH
            <= 0.4318 - 0.0127
        )
        bodies = _printed_steps(text)
        # A step never splits: each prints whole, as numbered_step wraps it.
        for number, body in bodies.items():
            assert tuple(body) == drawing.numbered_step(drawing.steps.SEQUENCE[number - 1])
        printed.extend(bodies)
        # One blank line before every step and group title but the column's
        # first; a title sits directly on its first step.
        heads = {i for i, line in enumerate(lines) if STEP_HEAD.match(line)}
        titles = {
            i
            for i, line in enumerate(lines)
            if i not in heads and line.strip() and not line.startswith(drawing.STEPS_HANG)
        }
        assert min(titles) == 0
        for i in sorted(heads | titles):
            if i and i - 1 not in titles:
                assert lines[i - 1] == "" and lines[i - 2].strip(), (column.sheet, lines[i])
        assert all(i + 1 in heads for i in titles)
    assert printed == list(range(1, len(drawing.steps.SEQUENCE) + 1))


def test_a_continued_column_repeats_its_group_title() -> None:
    titles = [title for title, _key in drawing.STEP_GROUPS]
    for _column, text in drawing.STEP_NOTES:
        first = text.splitlines()[0]
        assert first in titles or (
            first.endswith(" (CONT.)") and first.removesuffix(" (CONT.)") in titles
        )


def _flow_columns(*capacities: int) -> tuple:
    return tuple(
        drawing.StepColumn(f"S{index}", drawing.STEPS_XY, capacity)
        for index, capacity in enumerate(capacities)
    )


def test_flow_moves_a_step_that_does_not_fit_whole_to_the_next_column() -> None:
    groups = (("A", (("1. X",), ("2. Y", "   Y"))), ("B", (("3. Z",),)))
    notes = drawing.flow_steps(groups, _flow_columns(4, 6))
    assert [text.splitlines() for _column, text in notes] == [
        ["A", "1. X"],
        ["A (CONT.)", "2. Y", "   Y", "", "B", "3. Z"],
    ]


@pytest.mark.parametrize(
    ("capacities", "match"),
    [
        ((2,), "overflow"),
        ((9, 9), "no steps reach"),
        ((1, 9), "does not fit an empty column"),
    ],
)
def test_flow_refuses_overflow_and_empty_columns(capacities, match) -> None:
    groups = (("A", (("1. X",), ("2. Y", "   Y"))),)
    with pytest.raises(ValueError, match=match):
        drawing.flow_steps(groups, _flow_columns(*capacities))


def test_flow_refuses_a_line_wider_than_the_column() -> None:
    with pytest.raises(ValueError, match="characters"):
        drawing.flow_steps((("A", (("1. " + "X" * 70,),)),), _flow_columns(9))


def test_no_view_label_repeats_its_sheet_scale() -> None:
    # Over-specification: the title block prints each sheet's scale.
    for caption in (drawing.EXPLODED_CAPTION, drawing.ASSEMBLY_ISO_CAPTION):
        assert not re.search(r"\d+\s*:\s*\d+", caption)
    first, last = (
        drawing.SHEET_NAMES.index(name) + 1
        for name in (drawing.STEP_SHEET_NAMES[0], drawing.STEP_SHEET_NAMES[-1])
    )
    assert f"SHEETS {first}-{last}" in drawing.EXPLODED_CAPTION


def test_steps_name_parts_by_item_and_use_no_private_vocabulary() -> None:
    steps = " ".join(drawing.ASSEMBLY_STEPS.split())
    for word in (
        "GOOSENECK", "DECK", "NEAR-WALL", "FAR-WALL", "NEAR WALL", "FAR WALL",
        "LOWER AXIS", "TOP AXIS", "FRONT", "REAR", "DECORATED", "HUB", "DIA ",
    ):
        assert word not in steps, word
    # A BOM part number prints only as the drawing a callout lives on.
    for number in drawing.BOM_PART_NUMBERS.values():
        assert re.findall(rf"(?<!DRAWING ){re.escape(number)}\b", steps) == [], number
    cited = {int(n) for n in re.findall(r"\bITEM (\d+)", steps)}
    assert cited == set(drawing.ITEM_NUMBERS.values())


def test_the_bom_items_the_steps_cite_are_the_native_tables() -> None:
    native_order = (
        "fr-harmonic-base", "fr-tube-frame", "fr-rocker-arm-support",
        "fr-vn-lag-screw", "fr-top-frame", "fr-vn-tube-frame-cap",
        "fr-nameplate", "sh-vn-brass-fillister-screw",
        "fr-vn-frame-cross-screw", "fr-vn-gooseneck-set-screw",
    )
    assert drawing.ITEM_NUMBERS == {
        stem: index for index, stem in enumerate(native_order, start=1)
    }


class _BomTable:
    """An ITableAnnotation double printing ``items`` in its ITEM NO. column."""

    def __init__(self, items: dict[str, int]) -> None:
        self.rows = [("ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY.")] + [
            (
                str(items[stem]),
                drawing.BOM_PART_NUMBERS[stem],
                drawing.BOM_DESCRIPTIONS[stem],
                str(drawing.BOM_QUANTITIES[stem]),
            )
            for stem in drawing.BOM_COMPONENTS
        ]
        self.RowCount = len(self.rows)
        self.ColumnCount = 4

    def DisplayedText(self, row, column):  # noqa: N802
        return self.rows[row][column]

    def SetColumnWidth(self, _column, width, _flags):  # noqa: N802
        return width

    def SetRowHeight(self, _row, _height, _flags):  # noqa: N802
        return True


class _Rebuilds:
    def __init__(self) -> None:
        self.count = 0

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.count += 1
        return True


def test_the_frame_bom_must_number_its_items_as_the_steps_cite_them() -> None:
    adapter = SimpleNamespace(currentModel=_Rebuilds())
    items = dict(drawing.ITEM_NUMBERS)
    proven = drawing._validate_frame_bom(adapter, _BomTable(items))
    assert dict(proven) == {stem: str(number) for stem, number in items.items()}
    items[drawing.CAP], items[drawing.TOP_FRAME] = items[drawing.TOP_FRAME], items[drawing.CAP]
    with pytest.raises(RuntimeError, match="cited by the steps"):
        drawing._validate_frame_bom(adapter, _BomTable(items))


def test_the_support_windows_face_the_short_ends_of_item_1() -> None:
    # The builder turns MHA-FR-05 so its window normal (local Z, row 2)
    # runs along machine X, the base's length: the windows face the ends.
    import build_fr_frame_assembly as frame
    from fr_harmonic_base_spec import DECK_LENGTH, DECK_WIDTH

    assert [abs(value) for value in frame.SUPPORT_ROWS[2]] == [1.0, 0.0, 0.0]
    assert DECK_LENGTH > DECK_WIDTH
    assert "SHORT ENDS" in _step("support-seated")
    assert "LONG SIDES" not in drawing.ASSEMBLY_STEPS


def _nameplate_keys() -> list[str]:
    steps = drawing.steps
    return [
        steps.NAMEPLATE_SET_KEY,
        "nameplate-clamped",
        steps.NAMEPLATE_SPOTTED_KEY,
        "nameplate-lifted",
        steps.NAMEPLATE_SEATS_TAPPED_KEY,
        steps.NAMEPLATE_SCREWED_KEY,
    ]


def test_the_nameplate_is_set_then_its_base_seats_are_spotted_through_it() -> None:
    # #628: the base sheet prints the four nameplate seats as TRANSFER FROM
    # MHA-FR-04 AT ASSEMBLY, so the plate is located on the base first, then
    # spotted through, drilled and tapped before the screws go in.
    import build_fr_harmonic_base as base

    steps = drawing.steps
    assert drawing.NAMEPLATE_END_INSET == pytest.approx(base.NAMEPLATE_DECK_CLEARANCE)
    numbers = [steps.step_number(key) for key in _nameplate_keys()]
    assert numbers == list(range(numbers[0], numbers[0] + len(numbers)))
    # The inset is section B-B's native dimension, never a number in the note.
    placed = _step(steps.NAMEPLATE_SET_KEY)
    assert "SECTION B-B" in placed
    assert not re.search(r"\d\.\d", placed)
    assert drawing.BOM_PART_NUMBERS[drawing.BASE] in _step(steps.NAMEPLATE_SEATS_TAPPED_KEY)


def test_the_nameplate_seats_are_tapped_before_the_columns_go_in() -> None:
    # #2390: the bare base goes on the mill for its nameplate seats; once the
    # columns and top frame stand on it, it cannot.
    steps = drawing.steps
    tapped = steps.step_number(steps.NAMEPLATE_SEATS_TAPPED_KEY)
    assert tapped < steps.step_number("base-sockets-fitted")
    assert drawing.STEP_GROUPS[0][1] == steps.NAMEPLATE_SET_KEY


def test_tube_cross_holes_are_spotted_through_the_clearance_hole_not_drilled() -> None:
    # #2388: nothing is drilled through a casting's clearance hole toward the
    # tapped far wall; the spot is transferred and the tube drilled off the
    # frame. The punch enters the clearance hole with little play.
    from fr_frame_cross_screw import NEAR_WALL_CLEARANCE_DIAMETER

    play = NEAR_WALL_CLEARANCE_DIAMETER / 25.4 - drawing.TRANSFER_PUNCH_IN
    assert 0.0 < play <= 0.005
    steps = drawing.steps
    marked = steps.step_number(steps.LOWER_HOLES_MARKED_KEY)
    lifted = steps.step_number("lower-columns-lifted")
    drilled = steps.step_number(steps.LOWER_HOLES_DRILLED_KEY)
    assert marked < lifted < drilled
    # The screw is tried in the seated column, where a hole off the
    # casting's screw line shows, and the remedy works the tube hole.
    reseated = steps.step_number(steps.COLUMNS_RESEATED_KEY)
    checked = steps.step_number(steps.LOWER_HOLES_CHECKED_KEY)
    assert drilled < reseated < checked
    assert steps.SEQUENCE[checked] == "lower-holes-reworked"
    reassembled = steps.step_number("frame-reassembled")
    upper_checked = steps.step_number(steps.UPPER_HOLES_CHECKED_KEY)
    assert steps.step_number("upper-holes-drilled") < reassembled < upper_checked
    assert drawing.TRANSFER_PUNCH_TEXT in _step(steps.LOWER_HOLES_MARKED_KEY)
    assert "DRILL" not in _step(steps.LOWER_HOLES_MARKED_KEY)


def test_the_set_screw_step_points_to_the_drawing_step_that_tightens_it() -> None:
    # Rule 23 at the package boundary (machinist review blocker): the member
    # it grips is named and MHA-HA-00's levelling step tightens it there.
    import ha_harmonic_analyzer_assembly_steps as ha_steps

    steps = drawing.steps
    started = _step(steps.GOOSENECK_STARTED_KEY)
    assert ha_steps.step_ref("summing-levelled") in started
    assert drawing.GOOSENECK_POST_NUMBER in started
    following = steps.SEQUENCE[steps.step_number(steps.GOOSENECK_STARTED_KEY)]
    assert drawing.STEP_TEXT[following].startswith("CHECK")
    assert drawing.GOOSENECK_POST_NUMBER in drawing.STEP_TEXT[following]


def test_the_nameplate_spot_through_is_declared_on_the_assembly() -> None:
    """The nameplate's spot-through fit-up is an owner-accepted rule-19
    departure: the nominal screw float cannot absorb independent plate/base
    stations."""
    import sh_vn_brass_fillister_screw_spec as screw
    import fr_harmonic_base_spec as base_spec
    import fr_nameplate_drawing_spec as plate
    import fr_nameplate_spec as nameplate
    from _assembly_contract import assembly_contract
    from _drawing_registry import DRAWINGS_BY_NAME
    from _paths import CAD_ROOT
    from _printed_tolerance import printed_band_mm
    from machinist_exceptions import load_exceptions

    name = "fr_frame_assembly"
    assert DRAWINGS_BY_NAME[name].source_kind == "assembly"
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", name, "assembly")
    }
    entry = entries["RV-01"]
    assert not [id_ for id_ in entries if "1667" in id_]
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    assert re.search(r"\brule 19\b", entry.finding)
    first, last = (drawing.steps.step_number(key) for key in _nameplate_keys()[::5])
    assert re.search(rf"\bsteps {first}-{last}\b", entry.where)
    assert not re.search(r"\bstep 9\b", entry.where)
    # Without the spot-through, the plate's .XX station and the base's .XXX
    # tap station, each on both axes, demand far more diametral float than the
    # screw has.
    float_mm = plate.SCREW_HOLE_DIA - screw.SHANK_DIA
    station_band = printed_band_mm(
        plate.DRAWING_PRECISION["ScrewHoles"]["S0X"], unit=nameplate.UNIT
    )
    demand_mm = 2.0 * math.sqrt(2.0) * (
        station_band
        + printed_band_mm(base_spec.HOLE_TABLE_PRECISION, unit=base_spec.UNIT)
    )
    assert float_mm < demand_mm
    # The build reads the same file and ignores the declaration.
    assert assembly_contract("fr-frame").number == "MHA-FR-00"


def test_section_b_b_dimensions_the_nameplate_inset_from_the_deck_end(
    monkeypatch,
) -> None:
    stations = {}
    picks = {}
    added = {}
    checked = {}
    leaves = [object()]
    walks = []
    settled = []

    def component_leaves(_adapter, view, *, label):
        walks.append(view)
        return leaves

    def project(_adapter, _view, points, *, label, names):
        stations["points"] = points
        stations["names"] = names
        # 1:3 plan view, machine x to the sheet's right.
        return [(0.300 + point[0] / 3.0, 0.180 - point[2] / 3.0) for point in points]

    def pick(_adapter, view, *, leaves, label, stem, target_mm, stations_m):
        picks[label] = (view, stem, target_mm, stations_m, leaves)
        return drawing._InsetEdgeReference(
            label, f"model {label}", f"edge {label}", f"{stem}-1", f"component {stem}"
        )

    def add(_adapter, view, edges, *, text_xy, label):
        added.update(view=view, entities=edges, text_xy=text_xy, label=label)
        return "display"

    def check(_adapter, display, *, expected_mm, places, label):
        checked.update(display=display, expected_mm=expected_mm, places=places)
        return display

    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "_pick_inset_edge", pick)
    monkeypatch.setattr(drawing, "_add_inset_dimension", add)
    monkeypatch.setattr(drawing, "_checked_linear_dimension", check)
    monkeypatch.setattr(drawing, "_view_component_leaves", component_leaves)
    monkeypatch.setattr(
        drawing, "_assert_inset_dimension_settled",
        lambda _adapter, proof, *, phase: settled.append((proof, phase)),
    )

    proof = drawing._add_nameplate_inset_dimension(None, "B-B")
    assert proof.display == "display" and proof.view == "B-B"
    assert walks == ["B-B"]  # One snapshot shared by both target rays.
    assert settled == [(proof, "creation rebuild")]

    assert len(set(drawing.NAMEPLATE_INSET_PICK_Z_M)) == len(
        drawing.NAMEPLATE_INSET_PICK_Z_M
    )
    assert len(stations["points"]) == len(stations["names"]) == 2
    plate_x = drawing.NAMEPLATE_MOUNT_POS[0]
    deck_x = plate_x + drawing.NAMEPLATE_END_INSET
    y_mm = drawing.NAMEPLATE_MOUNT_POS[1]
    for label, stem, target in (
        ("nameplate lower edge", "fr-nameplate", plate_x),
        ("deck end", "fr-harmonic-base", deck_x),
    ):
        assert picks[label] == (
            "B-B",
            stem,
            pytest.approx(target),
            drawing.NAMEPLATE_INSET_PICK_Z_M,
            leaves,
        )
    assert added["view"] == "B-B"
    # The dimension spans exactly the read-back edges; the value check stays.
    assert added["entities"] == ("edge nameplate lower edge", "edge deck end")
    # The text, and the dimension line with it, sit past the base's outer edge:
    # below the plan view, clear of the plate and its lettering, beyond the
    # deck end and away from the plate.
    text_z = drawing.NAMEPLATE_INSET_TEXT_Z_M
    assert text_z * 1000.0 > drawing.BOTTOM_WIDTH / 2.0
    assert stations["points"][-2:] == [
        pytest.approx((plate_x / 1000.0, y_mm / 1000.0, text_z)),
        pytest.approx((deck_x / 1000.0, y_mm / 1000.0, text_z)),
    ]
    assert added["text_xy"] == pytest.approx(
        (
            0.300 + deck_x / 3000.0 + drawing.NAMEPLATE_INSET_TEXT_OFFSET_M,
            0.180 - text_z / 3.0,
        )
    )
    assert checked == {
        "display": "display",
        "expected_mm": drawing.NAMEPLATE_END_INSET,
        "places": drawing.INSET_PLACES,
    }
    # The inset prints .16 exactly on its .XX grid.
    assert drawing.NAMEPLATE_END_INSET == pytest.approx(0.16 * 25.4, abs=1e-9)


def _scripted_inset_edges(monkeypatch, rays, readback, *, selected_view="B-B"):
    """Script model hits and distinct mapped/selected section entities."""
    logged, selected, events, mapped = [], [], [], []
    section_edge = readback[0] if readback else None
    source_component = object()
    raw_entities, safe_entities, safe_reads = {}, {}, []
    for row in rays:
        if row is None or row[0] in raw_entities:
            continue
        name = row[0]
        safe_entities[name] = SimpleNamespace(
            IsSafe=True, name=f"safe {name}", GetComponent=lambda: None,
        )

        def retain(name=name):
            safe_reads.append(name)
            return safe_entities[name]

        raw_entities[name] = SimpleNamespace(GetSafeEntity=retain, GetComponent=lambda: None)

    def bound(value, kind):
        if kind == "IEntity" and isinstance(value, str):
            return raw_entities.get(value, value)
        return value

    def cast(_adapter, _view, *, leaves, stem, target_mm, stations_m):
        return "fr-frame-1/fr-nameplate-1", source_component, list(rays)

    def map_edge(_adapter, view, edge, *, component, label):
        assert component is source_component
        mapped.append((view, edge, component, label))
        return section_edge

    def select(_adapter, view, kind, xy, *, label, entity=None):
        selected.append((view, kind, xy, label, entity))
        return entity

    monkeypatch.setattr(drawing, "_early_bound", bound)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view)
    monkeypatch.setattr(drawing, "_inset_edge_rays", cast)
    monkeypatch.setattr(drawing, "_inset_section_edge", map_edge)
    monkeypatch.setattr(drawing, "_select_view_entity", select)
    monkeypatch.setattr(drawing, "_read_selected_inset_edge", lambda _adapter: readback)
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    adapter = SimpleNamespace(
        raw_entities=raw_entities, safe_entities=safe_entities, safe_reads=safe_reads,
        source_component=source_component,
        swApp=SimpleNamespace(IsSame=lambda a, b: int(a == b)),
        currentModel=SimpleNamespace(SelectionManager=SimpleNamespace(
            GetSelectedObjectsDrawingView2=lambda _index, _mark: selected_view,
        )),
    )
    return logged, selected, events, mapped, adapter


INSET_STATIONS = (0.025, 0.020, 0.030)


def test_the_first_station_whose_ray_meets_an_edge_chooses_it(monkeypatch) -> None:
    logged, selected, events, mapped, adapter = _scripted_inset_edges(
        monkeypatch,
        [None, ("edge at 20", 0.0523), ("edge at 30", 0.0523)],
        ("selected", "fr-frame-1/fr-nameplate-1", (163.01, 162.99)),
    )
    edge = drawing._pick_inset_edge(
        adapter,
        "B-B",
        leaves=(),
        label="plate",
        stem="fr-nameplate",
        target_mm=163.0,
        stations_m=INSET_STATIONS,
    )
    assert edge == drawing._InsetEdgeReference(
        "plate", adapter.safe_entities["edge at 20"], "selected", "fr-frame-1/fr-nameplate-1",
        adapter.source_component,
    )
    assert mapped == [("B-B", adapter.safe_entities["edge at 20"], adapter.source_component, "plate")]
    assert adapter.safe_reads == ["edge at 20"]  # Only the chosen model edge is retained.
    assert edge.model_edge is not adapter.raw_entities["edge at 20"]
    assert adapter.raw_entities["edge at 20"].GetComponent() is None
    assert edge.model_edge.GetComponent() is None  # Safe acquisition did not cause the absent owner.
    assert selected == [("B-B", "EDGE", None, "plate", "selected")]
    assert len(logged) == 1
    assert "fr-frame-1/fr-nameplate-1 y 52.300 z 20 mm" in logged[0]
    assert "machine x 163.010/162.990 mm" in logged[0]
    assert logged[0].endswith("-> hit")
    assert events == [
        (
            "drawing.inset_edge",
            {
                "label": "plate",
                "instance": "fr-frame-1/fr-nameplate-1",
                "owner": "fr-frame-1/fr-nameplate-1",
                "expected_view": "B-B",
                "selected_view": "B-B",
                "machine_y_mm": pytest.approx(52.3),
                "station_z_mm": 20.0,
                "rays": 3,
                "machine_x_mm": (163.01, 162.99),
                "hit": True,
                "same_entity": True,
                "same_view": True,
                "same_owner": True,
            },
        )
    ]


def test_a_model_hit_without_a_safe_entity_refuses_before_selection(monkeypatch):
    _logged, selected, _events, mapped, adapter = _scripted_inset_edges(
        monkeypatch, [("model", 0.0523)], ("selected", "fr-nameplate-1", (163.0, 163.0)),
    )
    adapter.raw_entities["model"].GetSafeEntity = lambda: None
    with pytest.raises(RuntimeError, match="failed to retain a safe model edge"):
        drawing._pick_inset_edge(
            adapter, "B-B", leaves=(), label="plate", stem="fr-nameplate",
            target_mm=163.0, stations_m=(0.025,),
        )
    assert selected == [] and mapped == []


def test_rays_meeting_no_edge_on_any_station_fail_the_sheet(monkeypatch) -> None:
    logged, selected, _events, mapped, adapter = _scripted_inset_edges(
        monkeypatch, [None, None, None], None
    )
    with pytest.raises(RuntimeError) as failure:
        drawing._pick_inset_edge(
            adapter,
            "B-B",
            leaves=(),
            label="deck end",
            stem="fr-harmonic-base",
            target_mm=167.0,
            stations_m=INSET_STATIONS,
        )
    message = str(failure.value)
    assert "no ray down machine -y through x 167 mm at z (25.0, 20.0, 30.0) mm" in message
    assert message.endswith("meets an edge of fr-frame-1/fr-nameplate-1")
    assert selected == [] and logged == [] and mapped == []


def test_an_inset_edge_read_back_off_target_fails_the_sheet(monkeypatch) -> None:
    # A corner's edge along y meets the ray too: its far end is off target.
    logged, selected, events, _mapped, adapter = _scripted_inset_edges(
        monkeypatch,
        [("corner", 0.0508)],
        ("corner", "fr-frame-1/fr-nameplate-1", (167.0, 170.0)),
    )
    with pytest.raises(RuntimeError, match="167.000/170.000 mm, not the section's named edge"):
        drawing._pick_inset_edge(
            adapter,
            "B-B",
            leaves=(),
            label="deck end",
            stem="fr-harmonic-base",
            target_mm=167.0,
            stations_m=(0.025,),
        )
    assert len(selected) == 1 and logged[0].endswith("-> miss")
    assert events[0][1]["hit"] is False


@pytest.mark.parametrize("change", ["entity", "view", "owner"])
def test_inset_pick_at_the_right_x_still_requires_the_named_entity_view_and_instance(
    monkeypatch, change,
) -> None:
    owner = "fr-nameplate-2" if change == "owner" else "fr-frame-1/fr-nameplate-1"
    logged, _selected, events, _mapped, adapter = _scripted_inset_edges(
        monkeypatch, [("model", 0.0523)], ("selected", owner, (163.0, 163.0)),
        selected_view="A-A" if change == "view" else "B-B",
    )
    if change == "entity":
        monkeypatch.setattr(drawing, "_inset_section_edge", lambda *_a, **_k: "other section edge")
    with pytest.raises(RuntimeError, match="not the section's named edge"):
        drawing._pick_inset_edge(
            adapter, "B-B", leaves=(), label="plate", stem="fr-nameplate",
            target_mm=163.0, stations_m=(0.025,),
        )
    assert logged[-1].endswith("-> miss")
    assert events[-1][1][f"same_{change}"] is False


class _RayModel:
    """A referenced assembly whose one body answers scripted ray hits.

    ``components`` are the view's drawing-component leaves (a hidden one is
    not shown); ``hits`` are ``(ray, kind, part xyz, entity)``, and the
    readback lists them nine doubles per hit, in order, with the entity per
    hit alongside.
    """

    def __init__(self, components, hits) -> None:
        self.components = components
        self.hits = hits
        self.Extension = self
        self.casts = []

    def leaves(self):
        return [
            _ComponentLeaf(
                name=component.Name2,
                component=component,
                identities=frozenset({component.stem}),
                visible=not component.IsSuppressed(),
                path=f"fr-frame-1/{component.Name2}",
            )
            for component in self.components
        ]

    def RayIntersections(self, bodies, starts, vectors, options, radius, offset, flag):  # noqa: N802
        self.casts.append((list(bodies), list(starts), list(vectors), options, radius, offset, flag))

    def GetRayIntersectionsPoints(self):  # noqa: N802
        return [
            value
            for ray, kind, (x, y, z), _entity in self.hits
            for value in (0.0, float(ray), float(kind), x, y, z, 0.0, 1.0, 0.0)
        ]

    def GetRayIntersectionsTopology(self):  # noqa: N802
        return [entity for _ray, _kind, _xyz, entity in self.hits]


def _ray_component(stem, name, values, *, top_part_y=0.0, suppressed=False):
    component = _Full(values)
    component.Name2 = name
    component.stem = stem
    component.GetPathName = lambda: f"C:/out/{stem}.SLDPRT"
    component.IsSuppressed = lambda: suppressed
    body = SimpleNamespace(
        GetExtremePoint=lambda x, y, z: (True, 0.0, top_part_y, 0.0), name=f"{name} body"
    )
    component.GetBodies3 = lambda _kind: ([body], None)
    component.GetCorrespondingEntity = lambda entity: f"{name}:{entity}"
    return component


def _ray_adapter(monkeypatch, model):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dispatch_array", list)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        drawing, "_view_component_leaves",
        lambda *_args, **_kwargs: pytest.fail("ray cast must reuse supplied component snapshot"),
    )

    def attempt(call, default=None):
        try:
            return call()
        except Exception:
            return default

    return SimpleNamespace(_attempt=attempt), SimpleNamespace(ReferencedDocument=model)


def test_inset_rays_go_down_machine_y_through_each_station_and_keep_the_highest_edge(
    monkeypatch,
) -> None:
    # The plate is Ry(180) in the frame (local x = -X, z = -Z), moved so its
    # local x 0.150 lands at machine x 163, its top face at machine y 52.3.
    values = (-1, 0, 0, 0, 1, 0, 0, 0, -1, 0.313, 0.0, 0.0, 1.0, 0, 0, 0)
    plate = _ray_component("fr-nameplate", "fr-nameplate-1", values, top_part_y=0.0523)
    other = _ray_component("fr-harmonic-base", "fr-harmonic-base-1", values)
    ghost = _ray_component("fr-nameplate", "fr-nameplate-2", values, suppressed=True)
    hits = [
        # Station 0: the top edge (kind EDGE|FACE bits), then the underside.
        (0, 4 | 1, (0.150, 0.0523, -0.025), "top"),
        (0, 4, (0.150, 0.0508, -0.025), "bottom"),
        # Station 1: a face only.
        (1, 1, (0.150, 0.0523, -0.020), "face"),
        # Station 2: the underside first in the readback, then the top.
        (2, 4, (0.150, 0.0508, -0.030), "bottom"),
        (2, 4, (0.150, 0.0523, -0.030), "top"),
    ]
    model = _RayModel([other, plate, ghost], hits)
    adapter, view = _ray_adapter(monkeypatch, model)

    name, component, rays = drawing._inset_edge_rays(
        adapter, view, leaves=model.leaves(), stem="fr-nameplate",
        target_mm=163.0, stations_m=INSET_STATIONS,
    )

    assert name == "fr-frame-1/fr-nameplate-1"
    assert component is plate  # Ownership is explicit; model edges need not expose GetComponent.
    assert rays == [
        ("fr-nameplate-1:top", pytest.approx(0.0523)),
        None,
        ("fr-nameplate-1:top", pytest.approx(0.0523)),
    ]
    (bodies, starts, vectors, options, radius, offset, flag), = model.casts
    assert [body.name for body in bodies] == ["fr-nameplate-1 body"]
    # Rays start a margin above the body's top, in part coordinates, and
    # point down machine -y (local -y too, under Ry(180)).
    margin = drawing._ORIGIN_MARGIN_M
    assert starts == pytest.approx(
        [0.150, 0.0523 + margin, -0.025, 0.150, 0.0523 + margin, -0.020,
         0.150, 0.0523 + margin, -0.030]
    )
    assert vectors == pytest.approx([0.0, -1.0, 0.0] * 3)
    assert (options, radius, offset, flag) == (
        drawing._RAY_OPTIONS, drawing._RAY_RADIUS_M, drawing._RAY_OFFSET_M, True
    )
    assert plate.reads == 1 and other.reads == 0 and ghost.reads == 0


def test_inset_rays_need_exactly_one_shown_instance_with_a_body(monkeypatch) -> None:
    values = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1.0, 0, 0, 0)
    twins = [
        _ray_component("fr-nameplate", "fr-nameplate-1", values),
        _ray_component("fr-nameplate", "fr-nameplate-2", values),
    ]
    adapter, view = _ray_adapter(monkeypatch, _RayModel(twins, []))
    with pytest.raises(RuntimeError, match="2 shown fr-nameplate instances, expected one"):
        drawing._inset_edge_rays(
            adapter, view, leaves=_RayModel(twins, []).leaves(),
            stem="fr-nameplate", target_mm=163.0, stations_m=(0.025,),
        )
    bodiless = _ray_component("fr-nameplate", "fr-nameplate-1", values)
    bodiless.GetBodies3 = lambda _kind: (None, None)
    adapter, view = _ray_adapter(monkeypatch, _RayModel([bodiless], []))
    with pytest.raises(RuntimeError, match="'fr-frame-1/fr-nameplate-1' resolves no solid body"):
        drawing._inset_edge_rays(
            adapter, view, leaves=_RayModel([bodiless], []).leaves(),
            stem="fr-nameplate", target_mm=163.0, stations_m=(0.025,),
        )


class _InsetDrawing:
    """Record exact entity/view selections without a screen-pick API."""

    def __init__(self) -> None:
        self.calls = []
        self.SelectionManager = self
        self.selected = []
        self.view = None
        self.display = object()

    def ActivateView(self, name):  # noqa: N802
        self.calls.append(("activate", name))
        return True

    def ClearSelection2(self, _all):  # noqa: N802
        self.selected.clear()

    def CreateSelectData(self):  # noqa: N802
        return SimpleNamespace(View=None)

    def GetSelectedObjectCount2(self, _mark):  # noqa: N802
        return len(self.selected)

    def GetSelectedObject6(self, index, _mark):  # noqa: N802
        return self.selected[index - 1]

    def GetSelectedObjectsDrawingView2(self, index, _mark):  # noqa: N802
        return self.view

    def AddDimension2(self, x, y, z):  # noqa: N802
        self.calls.append(("add", x, y, tuple(self.selected)))
        return self.display


def _inset_dimension_harness(monkeypatch):
    draw = _InsetDrawing()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: "B-B")
    view = object()

    def edge(name):
        result = SimpleNamespace(name=name)

        def select(append, data):
            assert data.View is view
            assert append == bool(draw.selected)
            draw.calls.append(("select4", name, append))
            draw.selected.append(result)
            draw.view = view
            return True

        result.Select4 = select
        return result

    adapter = SimpleNamespace(
        currentModel=draw, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)),
    )
    return adapter, view, (edge("plate"), edge("deck")), draw


def test_inset_dimension_selects_only_its_mapped_section_entities(monkeypatch) -> None:
    adapter, view, edges, draw = _inset_dimension_harness(monkeypatch)
    display = drawing._add_inset_dimension(
        adapter, view, edges, text_xy=(0.4, 0.1), label="inset"
    )
    assert display is draw.display
    assert draw.calls == [
        ("activate", "B-B"),
        ("select4", "plate", False),
        ("select4", "deck", True),
        ("add", 0.4, 0.1, edges),
    ]
    assert draw.selected == []


@pytest.mark.parametrize("change", ["entity", "view", "count"])
def test_changed_section_selection_is_refused_before_dimension_creation(monkeypatch, change):
    adapter, view, edges, draw = _inset_dimension_harness(monkeypatch)
    if change == "entity":
        draw.GetSelectedObject6 = lambda *_args: object()
    elif change == "view":
        draw.GetSelectedObjectsDrawingView2 = lambda *_args: object()
    else:
        draw.GetSelectedObjectCount2 = lambda *_args: 2
    with pytest.raises(RuntimeError, match="selection changed identity or view"):
        drawing._add_inset_dimension(
            adapter, view, edges, text_xy=(0.4, 0.1), label="inset"
        )
    assert not any(call[0] == "add" for call in draw.calls)


def _inset_correspondence_harness(monkeypatch):
    """Distinct model/view wrappers resolve into one canonical part edge."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "B-B")
    canonical = object()
    section_edge = object()
    state = {"mapped": section_edge, "canonical": canonical, "returned": canonical, "same": 1}
    calls, events = [], []
    part = SimpleNamespace()
    component = SimpleNamespace(Name2="fr-nameplate-1", GetModelDoc2=lambda: part)
    model_edge = SimpleNamespace(GetComponent=lambda: None, IsSafe=True)

    def reverse(edge):
        calls.append(("reverse", edge))
        return state["canonical"] if edge is model_edge else state["returned"]

    def corresponding(edge):
        calls.append(("section", edge))
        return state["mapped"]

    part.Extension = SimpleNamespace(GetCorrespondingEntity2=reverse)
    view = SimpleNamespace(GetCorrespondingEntity=corresponding)
    adapter = SimpleNamespace(
        source_component=component,
        swApp=SimpleNamespace(IsSame=lambda *_args: state["same"]),
    )
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return adapter, view, model_edge, section_edge, part, state, calls, events


def test_ownerless_model_hit_uses_explicit_component_for_source_roundtrip(monkeypatch):
    adapter, view, model_edge, section_edge, _part, _state, calls, events = (
        _inset_correspondence_harness(monkeypatch)
    )
    assert model_edge.GetComponent() is None  # Observed before AND after GetSafeEntity on the farm.
    assert drawing._inset_section_edge(
        adapter, view, model_edge, component=adapter.source_component, label="plate",
    ) is section_edge
    assert calls == [
        ("section", model_edge), ("reverse", model_edge), ("reverse", section_edge),
    ]
    assert events[-1][1]["source_identity"] == 1
    assert events[-1][1]["expected_instance"] == "fr-nameplate-1"
    assert events[-1][1]["expected_view"] == "B-B"
    assert events[-1][1]["model_safe"] is True
    assert events[-1][1]["canonical_available"] is True
    assert events[-1][1]["returned_available"] is True


def test_a_retained_model_entity_that_is_no_longer_safe_refuses_rebuild_mapping(monkeypatch):
    adapter, view, model_edge, _section, _part, _state, calls, events = (
        _inset_correspondence_harness(monkeypatch)
    )
    drawing._inset_section_edge(
        adapter, view, model_edge, component=adapter.source_component, label="plate",
    )
    calls.clear()
    model_edge.IsSafe = False  # Deleted topology cannot supply a surviving reference.
    with pytest.raises(RuntimeError, match="not safe across rebuilds"):
        drawing._inset_section_edge(
            adapter, view, model_edge, component=adapter.source_component, label="plate",
        )
    assert calls == []  # Do not dereference invalid topology in the mapping APIs.
    assert events[-1][1]["model_safe"] is False


@pytest.mark.parametrize(
    "change", ["missing_section", "missing_model_source", "missing_reverse_source", "different", "unknown", "unloaded"],
)
def test_missing_or_unproven_section_correspondence_fails_without_a_fallback(monkeypatch, change):
    adapter, view, model_edge, _section_edge, _part, state, _calls, events = (
        _inset_correspondence_harness(monkeypatch)
    )
    if change == "missing_section":
        state["mapped"] = None
    elif change == "missing_model_source":
        state["canonical"] = None
    elif change == "missing_reverse_source":
        state["returned"] = None
    elif change == "different":
        state["same"] = 0
    elif change == "unknown":
        state["same"] = -1
    else:
        adapter.source_component.GetModelDoc2 = lambda: None
    with pytest.raises(RuntimeError, match="no source-verified section edge"):
        drawing._inset_section_edge(
            adapter, view, model_edge, component=adapter.source_component, label="plate",
        )
    assert events[-1][1]["source_identity"] != 1


def _typed_inset_edge(kind=1):
    edge = SimpleNamespace(kind=kind)
    edge.GetType = lambda: edge.kind
    return edge


def _settled_inset_harness(monkeypatch):
    import _drawing_edge_dimensions

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda *_args: "B-B")
    model_edges = (object(), object())
    initial_edges = (_typed_inset_edge(), _typed_inset_edge())
    components = (object(), object())
    state = {
        "edges": initial_edges, "attached": initial_edges, "dangling": False,
        "types": (), "inventory": (), "equality_unknown": False,
    }
    native = SimpleNamespace(SystemValue=drawing.NAMEPLATE_END_INSET / 1000.0)
    annotation = SimpleNamespace(
        IsDangling=lambda: state["dangling"],
        GetAttachedEntityTypes=lambda: state["types"],
        GetAttachedEntities3=lambda: state["attached"],
    )
    display = SimpleNamespace(
        GetAnnotation=lambda: annotation, GetDimension2=lambda _index: native,
        Type2=2,
    )
    state["inventory"] = (display,)
    view = SimpleNamespace(GetDisplayDimensions=lambda: state["inventory"])
    references = tuple(
        drawing._InsetEdgeReference(label, source, entity, instance, component)
        for label, source, entity, instance, component in zip(
            ("plate", "deck"), model_edges, initial_edges,
            ("fr-nameplate-1", "fr-harmonic-base-1"), components,
        )
    )
    proof = drawing._InsetDimensionProof(view, display, references)
    adapter = SimpleNamespace(swApp=SimpleNamespace(
        IsSame=lambda a, b: -1 if state["equality_unknown"] else int(a is b),
    ))
    mapped, events = [], []

    def map_edge(_adapter, actual_view, source, *, component, label):
        assert actual_view is view
        assert component is components[model_edges.index(source)]
        mapped.append(source)
        return state["edges"][model_edges.index(source)]

    monkeypatch.setattr(drawing, "_inset_section_edge", map_edge)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return adapter, proof, state, native, model_edges, mapped, events


def test_settled_inset_reacquires_both_section_refs_and_checks_the_native_dimension(monkeypatch):
    adapter, proof, state, _native, model_edges, mapped, events = _settled_inset_harness(monkeypatch)
    drawing._assert_inset_dimension_settled(adapter, proof, phase="creation rebuild")
    # Section regeneration replaces the view wrappers; the native attachment
    # array can reverse its order. The model identities remain authoritative.
    regenerated = (_typed_inset_edge(), _typed_inset_edge())
    state.update(edges=regenerated, attached=regenerated[::-1])
    drawing._assert_inset_dimension_settled(adapter, proof)
    assert mapped == [*model_edges, *model_edges]
    assert events[-1][1]["measured_mm"] == pytest.approx(drawing.NAMEPLATE_END_INSET)
    assert events[-1][1]["section_owned"] is True
    assert events[-1][1]["expected_instances"] == ("fr-nameplate-1", "fr-harmonic-base-1")
    assert events[-1][1]["types"] == ()  # Native summary is empty even on the screen control.
    assert events[-1][1]["attached_entity_types"] == (1, 1)


def test_initial_nondangling_read_does_not_admit_references_lost_on_rebuild(monkeypatch):
    adapter, proof, state, _native, _sources, _mapped, events = _settled_inset_harness(monkeypatch)
    drawing._assert_inset_dimension_settled(adapter, proof, phase="creation rebuild")
    state.update(dangling=True, attached=(), types=())
    with pytest.raises(RuntimeError, match="dangles after the final rebuild"):
        drawing._assert_inset_dimension_settled(adapter, proof)
    assert events[-1][1]["phase"] == "final rebuild"
    assert events[-1][1]["dangling"] is True
    assert events[-1][1]["expected_view"] == "B-B"


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ("missing", "named entities"),
        ("foreign", "named entities"),
        ("duplicate", "named entities"),
        ("extra", "named entities"),
        ("unknown_identity", "named entities"),
        ("value", "measures"),
        ("nonfinite", "measures"),
        ("type", "edge/linear type"),
        ("entity_types", "edge/linear type"),
        ("owner", "owned by its section view"),
    ],
)
def test_rebuilt_inset_requires_real_named_refs_value_type_and_section_owner(monkeypatch, change, error):
    adapter, proof, state, native, _sources, _mapped, events = _settled_inset_harness(monkeypatch)
    if change == "missing":
        state["attached"] = ()
    elif change == "foreign":
        state["attached"] = (object(), object())
    elif change == "duplicate":
        state["attached"] = (state["edges"][0], state["edges"][0])
    elif change == "extra":
        state["attached"] = (*state["edges"], object())
    elif change == "unknown_identity":
        state["equality_unknown"] = True
    elif change == "value":
        native.SystemValue = 0.005334  # Prior off-target, but still a real native dimension.
    elif change == "nonfinite":
        native.SystemValue = math.nan
    elif change == "type":
        proof.display.Type2 = 3  # swAngularDimension: cannot be read as a length.
    elif change == "entity_types":
        state["edges"][0].kind = 2  # A real face, despite a dimension that still measures 4 mm.
        state["types"] = (1, 1)  # A plausible legacy summary cannot override the actual entity type.
    else:
        state["inventory"] = ()
    with pytest.raises(RuntimeError, match=error):
        drawing._assert_inset_dimension_settled(adapter, proof)
    assert events[-1][1]["reference_failure"]
    assert events[-1][1]["expected_view"] == "B-B"



def test_a_checked_linear_dimension_refuses_to_dangle(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    annotation = SimpleNamespace(IsDangling=lambda: True, GetAttachedEntityTypes=lambda: (1, 1))
    display = SimpleNamespace(
        GetDimension2=lambda _index: SimpleNamespace(SystemValue=0.004),
        GetAnnotation=lambda: annotation,
    )
    with pytest.raises(RuntimeError, match="inset is dangling \\(attached entity types \\(1, 1\\)\\)"):
        drawing._checked_linear_dimension(
            None, display, expected_mm=4.0, places=drawing.INSET_PLACES, label="inset"
        )


class _InsetSelection:
    """A drawing whose selection manager holds one scripted object."""

    def __init__(self, picked, kind) -> None:
        self.picked, self.kind = picked, kind
        self.calls = []
        self.SelectionManager = self

    def ClearSelection2(self, _all):  # noqa: N802
        self.calls.append(("clear",))

    def GetSelectedObjectCount2(self, _mark):  # noqa: N802
        return 2  # the view, then the edge

    def GetSelectedObjectType3(self, index, _mark):  # noqa: N802
        assert index == 2
        return self.kind

    def GetSelectedObject6(self, index, _mark):  # noqa: N802
        assert index == 2
        return self.picked


def _inset_selection_adapter(monkeypatch, picked, kind=1):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "_edge_endpoint_key", lambda _adapter, edge: edge.key)
    draw = _InsetSelection(picked, kind)

    def attempt(call, default=None):
        try:
            return call()
        except Exception:
            return default

    return SimpleNamespace(currentModel=draw, _attempt=attempt), draw


def test_a_selected_inset_edge_reads_back_in_machine_x(monkeypatch) -> None:
    # Component-local x 0.150 m, moved +13 mm along machine x: 163 mm.
    plate = _Full((1, 0, 0, 0, 1, 0, 0, 0, 1, 0.013, 0.0, 0.0, 1.0, 0, 0, 0))
    plate.Name2 = "fr-frame-1/fr-nameplate-1"
    edge = SimpleNamespace(
        key=(0.150, 0.0523, 0.010, 0.150, 0.0523, 0.040), GetComponent=lambda: plate
    )
    adapter, draw = _inset_selection_adapter(monkeypatch, edge)

    picked, owner, xs = drawing._read_selected_inset_edge(adapter)

    assert picked is edge and owner == "fr-frame-1/fr-nameplate-1"
    assert xs == pytest.approx((163.0, 163.0))
    assert draw.calls == [("clear",)]


def test_a_selection_that_is_not_a_component_edge_reads_no_x(monkeypatch) -> None:
    orphan = SimpleNamespace(key=(0.0,) * 6, GetComponent=lambda: None)
    for picked, kind, reason in (
        (None, 1, "selection type 1"),
        ("silhouette", 11, "selection type 11"),
        (orphan, 1, "edge without a component"),
    ):
        adapter, _ = _inset_selection_adapter(monkeypatch, picked, kind)
        assert drawing._read_selected_inset_edge(adapter) == (None, reason, None)


def test_height_dimensions_stand_clear_of_the_cutting_plane_letters() -> None:
    # PR #1468 r4 machinist review: the (1044.8) line struck the right-hand
    # B-B letter, and the A-A arrow shared its corridor. Both height lines now
    # stand right of the letters and left of section A-A, each with clearance;
    # the sections stay apart and inside the border.
    from fr_harmonic_base_spec import BOTTOM_LENGTH

    front_half = BOTTOM_LENGTH / 2.0 / 8.0 / 1000.0  # the 1:8 view's flange
    section_half = BOTTOM_LENGTH / 2.0 / 3.0 / 1000.0  # both 1:3 sections
    letters_right = (
        drawing.WORKING_FRONT_CENTER[0] + front_half + drawing.CUTTING_LETTER_REACH_M
    )
    top_axis_x = drawing.TOP_AXIS_HEIGHT_TEXT_XY[0]
    overall_x = drawing.OVERALL_HEIGHT_TEXT_XY[0]
    base_left = drawing.BASE_SECTION_CENTER[0] - section_half
    clearance = drawing.HEIGHT_LINE_CLEARANCE_M
    assert letters_right + clearance <= top_axis_x
    assert top_axis_x + clearance <= overall_x
    # r6 review: a visible gap between the front view's dimensions and A-A.
    assert overall_x + drawing.VIEW_GAP_M <= base_left
    assert drawing.VIEW_GAP_M >= 0.006
    base_right = drawing.BASE_SECTION_CENTER[0] + section_half
    top_left = drawing.TOP_SECTION_CENTER[0] - section_half
    top_right = drawing.TOP_SECTION_CENTER[0] + section_half
    assert top_left - base_right >= 0.006
    assert top_right <= 0.4191 - 0.002  # B-size inner border, 17 in less 0.5 in


class _FrameBomExtent:
    def __init__(self, heights):
        self.heights = heights
        self.RowCount = len(heights)

    def GetAnnotation(self):  # noqa: N802
        return SimpleNamespace(GetPosition=lambda: (0.018, 0.414, 0.0))

    def GetRowHeight(self, row):  # noqa: N802
        return self.heights[row]


@pytest.mark.parametrize("last_row_height", [0.018, 0.038])
def test_set_screw_balloon_uses_measured_wrapped_bom_and_keeps_native_tip(
    monkeypatch, last_row_height
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    table = _FrameBomExtent([0.008] * 10 + [last_row_height])
    tip = (0.116, 0.277)
    leader = (0.127, 0.315, 0.0, *tip, 0.0)
    note = SimpleNamespace(GetAnnotation=lambda: SimpleNamespace(
        GetLeaderPointsAtIndex=lambda _index: leader,
    ))
    landings = [SimpleNamespace(stem="fr-vn-gooseneck-set-screw", note=note)]
    monkeypatch.setattr(drawing, "rendered_balloon_circle", lambda *_a, **_k: (0.127, 0.315, 0.005))
    monkeypatch.setattr(drawing, "_balloon_item_number", lambda *_a, **_k: "10")
    placed = []

    def short(adapter, view, actual_note, item, offset):
        placed.append((actual_note, item, (tip[0] + offset[0], tip[1] + offset[1])))
        return "proof"

    monkeypatch.setattr(drawing, "_short_frame_balloon", short)
    assert drawing._place_frame_set_screw_balloon(None, None, table, landings) == "proof"
    [(actual_note, item, target)] = placed
    assert actual_note is note and item == "10"
    assert target == pytest.approx((
        0.127, min(0.414 - sum(table.heights) - 0.005 - 0.004, tip[1] + 0.020),
    ))
    assert target[1] + 0.005 <= 0.414 - sum(table.heights) - 0.003
    assert math.dist(target, tip) < 0.030
    assert leader[-3:-1] == tip


@pytest.mark.parametrize("height", [0.0, -0.001, float("nan"), float("inf")])
def test_frame_bom_extent_refuses_unreadable_native_row_heights(monkeypatch, height) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    with pytest.raises(RuntimeError):
        drawing._frame_bom_bottom(_FrameBomExtent([0.008, height]))


def _frame_balloon_clearance_fixture():
    # Sheet metres, matching the two adjacent lanes on the reviewed sheet 2.
    return {
        "bottom": 0.314,
        "circle": (0.127, 0.297, 0.005),
        "cap_circle": (0.114, 0.306, 0.005),
        "leader": (0.125, 0.2925, 0.0, 0.116, 0.277, 0.0),
        "cap_leader": (0.1135, 0.301, 0.0, 0.112, 0.280, 0.0),
    }


def test_lowered_set_screw_balloon_clears_bom_and_cap_leader() -> None:
    assert drawing._frame_bom_balloon_failures(**_frame_balloon_clearance_fixture()) == []


@pytest.mark.parametrize(
    ("change", "failure"),
    [
        ({"circle": (0.127, 0.315, 0.005)}, "bom_rule_clearance"),
        ({"bottom": 0.303}, "bom_rule_clearance"),
        ({"circle": (0.119, 0.306, 0.005)}, "cap_balloon_clearance"),
        ({"leader": (0.125, 0.2925, 0.0, 0.105, 0.280, 0.0)}, "cap_leader_collision"),
        ({"cap_leader": (0.127, 0.300, 0.0, 0.127, 0.280, 0.0)}, "cap_leader_collision"),
        ({"cap_leader": ()}, "missing_leader"),
    ],
)
def test_native_bom_or_neighbour_collision_refuses_set_screw_placement(change, failure) -> None:
    state = _frame_balloon_clearance_fixture()
    state.update(change)
    assert failure in drawing._frame_bom_balloon_failures(**state)


@pytest.mark.parametrize(
    ("bottom", "balloon_y", "clears"),
    [
        (0.314, 0.297, True),
        (0.303, 0.297, False),  # Rebuilt BOM grew down into the settled ring.
        (0.314, 0.309, False),  # Balloon drifted up although the table did not move.
        (0.305001, 0.297, True),  # 3.001 mm of air around the complete outer ring.
        (0.304999, 0.297, False),  # 2.999 mm must not meet the 3 mm floor.
    ],
)
def test_final_native_clearance_guard_reads_rebuilt_table_and_both_leaders(
    monkeypatch, bottom, balloon_y, clears
) -> None:
    from contextlib import nullcontext

    state = _frame_balloon_clearance_fixture()
    reads = []

    def note(name):
        leader = state["leader" if name == "set" else "cap_leader"]
        return SimpleNamespace(
            name=name, GetAnnotation=lambda: SimpleNamespace(
                GetLeaderPointsAtIndex=lambda _index: leader,
            ),
        )

    screw, cap = note("set"), note("cap")
    proof = SimpleNamespace(
        annotation=SimpleNamespace(GetSpecificAnnotation=lambda: screw),
        target=state["circle"][:2],
    )
    landings = [SimpleNamespace(stem="fr-vn-tube-frame-cap", note=cap)]
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "_zoomed_on", lambda *_a: nullcontext())
    monkeypatch.setattr(drawing, "_frame_bom_bottom", lambda _table: bottom)

    def rendered(actual_note, **_kwargs):
        reads.append(actual_note.name)
        if actual_note is screw:
            return (state["circle"][0], balloon_y, state["circle"][2])
        return state["cap_circle"]

    monkeypatch.setattr(drawing, "rendered_balloon_circle", rendered)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None))
    if clears:
        drawing._assert_frame_bom_balloon_clearance(adapter, object(), landings, proof)
    else:
        with pytest.raises(RuntimeError, match="bom_rule_clearance"):
            drawing._assert_frame_bom_balloon_clearance(adapter, object(), landings, proof)
    assert "set" in reads and "cap" in reads


def _isometric_mm(point: tuple[float, float, float]) -> tuple[float, float]:
    """Model mm on a SolidWorks *Isometric, Y up: right (1, 0, -1)/sqrt 2,
    up (-1, 2, -1)/sqrt 6, in model mm at 1:1."""
    x, y, z = point
    return (x - z) / math.sqrt(2.0), (2.0 * y - x - z) / math.sqrt(6.0)


def _box_corners(x, y, z):
    return [(a, b, c) for a in x for b in y for c in z]


def _deck_detail_boxes():
    """Each detail's exploded parts, as model-mm boxes from their specs."""
    import fr_frame_explode_spec as explode
    import fr_nameplate_spec as plate
    from fr_harmonic_base_spec import STACK_HEIGHT
    from fr_rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ
    from fr_vn_lag_screw_spec import HEAD_AF
    from sh_vn_brass_fillister_screw_spec import HEAD_DIA, HEAD_H

    head = HEAD_AF / math.sqrt(3.0)  # hex corner radius
    screw_x = [x for x, _z in SUPPORT_HOLD_DOWN_XZ]
    screw_z = [z for _x, z in SUPPORT_HOLD_DOWN_XZ]
    support = _box_corners(
        (
            min(screw_x) - head + explode.SUPPORT_ASIDE_X,
            max(screw_x) + head + explode.SUPPORT_ASIDE_X,
        ),
        (
            STACK_HEIGHT + explode.SUPPORT_LIFT,
            drawing._LAG_SCREW_UNDER_HEAD_Y
            + drawing.LAG_HEAD_H
            + explode.SUPPORT_LIFT
            + explode.SUPPORT_SCREW_WITHDRAW,
        ),
        (min(screw_z) - head, max(screw_z) + head),
    )
    lift = explode.NAMEPLATE_LIFT
    x0 = plate.MOUNT_POS[0] + explode.NAMEPLATE_ASIDE_X
    z0 = plate.MOUNT_POS[2]
    nameplate = _box_corners(
        (x0 - plate.PLATE_HEIGHT, x0),
        (
            plate.MOUNT_FRONT_Y - plate.PLATE_THICKNESS + lift,
            plate.MOUNT_FRONT_Y + HEAD_H + explode.NAMEPLATE_SCREW_WITHDRAW + lift,
        ),
        (z0 - plate.PLATE_WIDTH - HEAD_DIA / 2.0, z0 + HEAD_DIA / 2.0),
    )
    return {"C": support, "D": nameplate}


def test_each_deck_detail_circle_holds_its_exploded_hardware() -> None:
    boxes = _deck_detail_boxes()
    for detail in drawing.DECK_DETAILS:
        centre = _isometric_mm(detail.centre_xyz)
        reach = max(
            math.dist(_isometric_mm(corner), centre) for corner in boxes[detail.letter]
        )
        # The parts it enlarges, with at least 2 mm of model air to the crop.
        assert reach <= detail.crop_radius_mm - 2.0, (detail.letter, reach)
        # And no idle margin: the circle is no more than 20 % over its parts.
        assert reach >= detail.crop_radius_mm / 1.2, (detail.letter, reach)


def test_deck_details_stand_in_the_free_column_of_sheet_2() -> None:
    # Measured on sheet 2 of run 20261103T090647187Z: the exploded view's
    # balloons end 175 mm from the left, the inner border is at 267 mm, the
    # BOM's bottom rule at 314 mm and the title block's top at 66 mm.
    rows = []
    for detail in drawing.DECK_DETAILS:
        x, y = detail.centre
        r = detail.radius_m
        assert 0.185 <= x - r and x + r <= 0.267 - 0.002, detail.letter
        assert y + r <= 0.314 - 0.010, detail.letter
        label_bottom = detail.label_xy[1] - 3 * 0.005  # three note lines
        assert label_bottom >= 0.066 + 0.010, detail.letter
        rows.append((label_bottom, y + r))
    rows.sort()
    for (_, below_top), (above_label_bottom, _) in zip(rows, rows[1:]):
        assert below_top + 0.005 <= above_label_bottom
    assert {detail.letter for detail in drawing.DECK_DETAILS} == {"C", "D"}


def test_deck_detail_labels_name_their_bom_items() -> None:
    items = {stem: str(n) for n, stem in enumerate(drawing.BOM_COMPONENTS, 1)}
    assert drawing.SUPPORT_DETAIL.label_text(items) == (
        "DETAIL C\n"
        f"ITEMS {items['fr-rocker-arm-support']} AND {items['fr-vn-lag-screw']}\n"
        "SCALE 1:3"
    )
    assert drawing.NAMEPLATE_DETAIL.stems == (
        "fr-nameplate",
        "sh-vn-brass-fillister-screw",
    )
