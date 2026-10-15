"""Observable package contract for the frame assembly drawing."""

import draw_fr_frame_assembly as drawing


def test_frame_package_bom_identifies_all_29_released_components() -> None:
    assert drawing.BOM_QUANTITIES == {
        "fr-harmonic-base": 1,
        "fr-tube-frame": 4,
        "vn-tube-frame-cap": 4,
        "fr-rocker-arm-support": 1,
        "vn-lag-screw": 4,
        "fr-top-frame": 1,
        "fr-nameplate": 1,
        "vn-fillister-screw": 4,
        "vn-frame-cross-screw": 8,
        "vn-gooseneck-set-screw": 1,
    }
    assert drawing.BOM_PART_NUMBERS == {
        "fr-harmonic-base": "MHA-FR-001",
        "fr-tube-frame": "MHA-FR-003",
        "vn-tube-frame-cap": "MHA-VN-028",
        "fr-rocker-arm-support": "MHA-FR-005",
        "vn-lag-screw": "MHA-VN-009",
        "fr-top-frame": "MHA-FR-002",
        "fr-nameplate": "MHA-FR-004",
        "vn-fillister-screw": "MHA-VN-006",
        "vn-frame-cross-screw": "MHA-VN-027",
        "vn-gooseneck-set-screw": "MHA-VN-023",
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
        rebound=frozenset({"vn-lag-screw"}),
        bound=(drawing._BoundBalloonProof("5", balloon, balloon.entity, balloon.tip),),
        short=(),
    )
    landings = [SimpleNamespace(stem="vn-lag-screw"), SimpleNamespace(stem="fr-nameplate")]
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


def _step_lines(number: int) -> list[str]:
    steps = drawing.ASSEMBLY_STEPS.splitlines()
    start = next(i for i, line in enumerate(steps) if line.startswith(f"{number}. "))
    end = next(
        (i for i in range(start + 1, len(steps)) if re.match(r"\d+\. ", steps[i])),
        len(steps),
    )
    return steps[start:end]


def _step(number: int) -> str:
    return " ".join(line.strip() for line in _step_lines(number))


def test_assembly_steps_keep_their_crowded_sheet_3_footprint() -> None:
    steps = drawing.ASSEMBLY_STEPS.splitlines()
    assert len(steps) <= 39
    assert max(map(len, steps)) <= 72


def test_step_8_faces_the_support_windows_toward_the_short_ends() -> None:
    # The builder turns MHA-FR-005 so its window normal (local Z, row 2)
    # runs along machine X, the deck's length: the windows face the ends.
    import build_fr_frame_assembly as frame
    from fr_harmonic_base_spec import DECK_LENGTH, DECK_WIDTH

    assert [abs(value) for value in frame.SUPPORT_ROWS[2]] == [1.0, 0.0, 0.0]
    assert DECK_LENGTH > DECK_WIDTH
    step = _step(8)
    assert "WINDOWS FACING THE SHORT ENDS" in step
    assert "LONG SIDES" not in step


def test_step_9_sets_the_nameplate_then_spots_its_base_seats_through_it() -> None:
    # #628: the base sheet prints the four nameplate seats as TRANSFER FROM
    # MHA-FR-004 AT ASSEMBLY, so the step locates the plate on the deck, then
    # spots, drills and taps through it before the screws go in.
    import build_fr_harmonic_base as base

    step = _step(9)
    assert drawing.NAMEPLATE_END_INSET == pytest.approx(base.NAMEPLATE_DECK_CLEARANCE)
    # The inset is section B-B's native dimension, never a number in the note.
    assert "INSET FROM THE NEAR DECK END PER SECTION B-B" in step
    assert not re.search(r"\d\.\d", step)
    place = step.index(
        "SET MHA-FR-004 DECORATED FACE UP, CENTRED FRONT TO REAR, PARALLEL"
    )
    spot = step.index("SPOT MHA-FR-001 THROUGH ITS FOUR HOLES")
    assert place < step.index("CLAMP.") < spot < step.index("TRANSFER CALLOUT")
    assert step.index("TRANSFER CALLOUT") < step.index("SEAT ALL FOUR MHA-VN-006 HEADS")
    assert len(_step_lines(9)) <= 4


def test_check_3_accepts_the_caps_by_their_seats_alone() -> None:
    checks = drawing.ASSEMBLY_CHECKS.splitlines()
    start = next(i for i, line in enumerate(checks) if line.startswith("3. "))
    assert checks[start].startswith(
        "3. ALL FOUR MHA-VN-028 CAPS REACH THEIR INSIDE SEATS"
    )
    assert "TOPS ARE EVEN" not in drawing.ASSEMBLY_CHECKS


class _TextDisplay:
    """A display dimension whose text parts persist unless ``drops``."""

    def __init__(self, *, drops: bool = False) -> None:
        self.parts: dict[int, str] = {}
        self.drops = drops

    def SetText(self, part, text) -> None:  # noqa: N802
        if not self.drops:
            self.parts[part] = text

    def GetText(self, part) -> str:  # noqa: N802
        return self.parts.get(part, "")


class _Rebuilds:
    def __init__(self) -> None:
        self.count = 0

    def EditRebuild3(self) -> bool:  # noqa: N802
        self.count += 1
        return True


def test_top_axis_height_names_itself_in_its_own_native_suffix() -> None:
    # The tube-frame sheet sends the fitter to this height by name.
    from fr_tube_frame_spec import DRAWING_NOTES

    assert "TOP CROSS-BORE AXIS HEIGHT" in DRAWING_NOTES
    assert drawing.TOP_AXIS_HEIGHT_SUFFIX == (
        " TOP CROSS-BORE AXIS HEIGHT FROM BASE UNDERSIDE"
    )
    model = _Rebuilds()
    display = _TextDisplay()
    returned = drawing._set_dimension_suffix(
        SimpleNamespace(currentModel=model),
        display,
        drawing.TOP_AXIS_HEIGHT_SUFFIX,
        label="top axis",
    )
    assert returned is display
    assert display.parts == {2: drawing.TOP_AXIS_HEIGHT_SUFFIX}  # suffix only
    assert model.count == 1


def test_a_suffix_that_does_not_persist_fails_the_sheet() -> None:
    model = _Rebuilds()
    with pytest.raises(RuntimeError, match="top axis: suffix"):
        drawing._set_dimension_suffix(
            SimpleNamespace(currentModel=model),
            _TextDisplay(drops=True),
            drawing.TOP_AXIS_HEIGHT_SUFFIX,
            label="top axis",
        )
    assert model.count == 0


def test_section_b_b_dimensions_the_nameplate_inset_from_the_deck_end(
    monkeypatch,
) -> None:
    stations = {}
    picks = {}
    added = {}
    checked = {}

    def project(_adapter, _view, points, *, label, names):
        stations["points"] = points
        stations["names"] = names
        # 1:3 plan view, machine x to the sheet's right.
        return [(0.300 + point[0] / 3.0, 0.180 - point[2] / 3.0) for point in points]

    def pick(_adapter, view, *, label, target_mm, stations):
        picks[label] = (view, target_mm, stations)
        return f"edge {label}"

    def add(_adapter, view, **kwargs):
        added.update(kwargs, view=view)
        return "display"

    def check(_adapter, display, *, expected_mm, label):
        checked.update(display=display, expected_mm=expected_mm)
        return display

    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "_pick_inset_edge", pick)
    monkeypatch.setattr(drawing, "add_edge_dimension", add)
    monkeypatch.setattr(drawing, "_checked_linear_dimension", check)

    assert drawing._add_nameplate_inset_dimension(None, "B-B") == "display"

    count = len(drawing.NAMEPLATE_INSET_PICK_Z_M)
    assert len(set(drawing.NAMEPLATE_INSET_PICK_Z_M)) == count
    assert len(stations["points"]) == len(stations["names"]) == 2 * count + 2
    plate_x = drawing.NAMEPLATE_MOUNT_POS[0]
    deck_x = plate_x + drawing.NAMEPLATE_END_INSET
    for label, target, offset in (
        ("nameplate lower edge", plate_x, 0),
        ("deck end", deck_x, count),
    ):
        view, target_mm, rows = picks[label]
        assert view == "B-B"
        assert target_mm == pytest.approx(target)
        assert [z for z, _ in rows] == list(drawing.NAMEPLATE_INSET_PICK_Z_M)
        for (z, sheet_xy), point in zip(rows, stations["points"][offset:]):
            assert point == pytest.approx((target / 1000.0, point[1], z))
            assert sheet_xy == pytest.approx((0.300 + target / 3000.0, 0.180 - z / 3.0))
    assert added["view"] == "B-B"
    # The dimension spans exactly the read-back edges; the value check stays.
    assert added["entities"] == ("edge nameplate lower edge", "edge deck end")
    first_z = drawing.NAMEPLATE_INSET_PICK_Z_M[0]
    assert added["p0"] == pytest.approx(
        (0.300 + plate_x / 3000.0, 0.180 - first_z / 3.0)
    )
    assert added["p1"] == pytest.approx(
        (0.300 + deck_x / 3000.0, 0.180 - first_z / 3.0)
    )
    # The text, and the dimension line with it, sit past the base's outer edge:
    # below the plan view, clear of the plate and its lettering, beyond the
    # deck end and away from the plate.
    text_z = drawing.NAMEPLATE_INSET_TEXT_Z_M
    assert text_z * 1000.0 > drawing.BOTTOM_WIDTH / 2.0
    assert stations["points"][-2:] == [
        pytest.approx((plate_x / 1000.0, stations["points"][0][1], text_z)),
        pytest.approx((deck_x / 1000.0, stations["points"][0][1], text_z)),
    ]
    assert added["text_xy"] == pytest.approx(
        (
            0.300 + deck_x / 3000.0 + drawing.NAMEPLATE_INSET_TEXT_OFFSET_M,
            0.180 - text_z / 3.0,
        )
    )
    assert checked == {"display": "display", "expected_mm": drawing.NAMEPLATE_END_INSET}


def _scripted_inset_picks(monkeypatch, readings):
    logged = []
    picked = []

    def read(_adapter, _view, sheet_xy):
        picked.append(tuple(sheet_xy))
        return readings[len(picked) - 1]

    monkeypatch.setattr(drawing, "_read_inset_pick", read)
    monkeypatch.setattr(drawing._telemetry, "info", logged.append)
    return logged, picked


INSET_STATIONS = ((0.025, (0.1, 0.2)), (0.020, (0.1, 0.21)), (0.030, (0.1, 0.19)))


def test_an_inset_pick_off_target_moves_along_z_and_logs_both_readings(
    monkeypatch,
) -> None:
    logged, picked = _scripted_inset_picks(
        monkeypatch,
        [
            ("near line", "fr-frame-1/fr-nameplate-1", (161.666, 161.666)),
            ("target", "fr-frame-1/fr-nameplate-1", (163.01, 162.99)),
        ],
    )
    edge = drawing._pick_inset_edge(
        None, "B-B", label="plate", target_mm=163.0, stations=INSET_STATIONS
    )
    assert edge == "target"
    assert picked == [(0.1, 0.2), (0.1, 0.21)]
    assert len(logged) == 2
    assert "z 25 mm" in logged[0] and "machine x 161.666/161.666 mm" in logged[0]
    assert logged[0].endswith("-> miss")
    assert "z 20 mm" in logged[1] and "machine x 163.010/162.990 mm" in logged[1]
    assert logged[1].endswith("-> hit")


def test_inset_picks_that_never_reach_the_target_fail_naming_every_reading(
    monkeypatch,
) -> None:
    logged, _ = _scripted_inset_picks(
        monkeypatch,
        [
            ("near line", "fr-frame-1/fr-harmonic-base-1", (168.334, 168.334)),
            (None, "selection type 5", None),
            # One end on target is not enough: the edge must lie along z there.
            ("slant", "fr-frame-1/fr-harmonic-base-1", (167.0, 170.0)),
        ],
    )
    with pytest.raises(RuntimeError) as failure:
        drawing._pick_inset_edge(
            None, "B-B", label="deck end", target_mm=167.0, stations=INSET_STATIONS
        )
    message = str(failure.value)
    assert "no pick lies at machine x 167 mm" in message
    assert "machine x 168.334/168.334 mm" in message
    assert "selection type 5" in message
    assert "machine x 167.000/170.000 mm" in message
    assert len(logged) == 3 and all(line.endswith("-> miss") for line in logged)


class _InsetPickDraw:
    """A drawing whose zoomed coordinate pick returns one scripted object."""

    def __init__(self, picked, kind) -> None:
        self.picked, self.kind = picked, kind
        self.calls = []
        self.Extension = self
        self.SelectionManager = self

    def ActivateView(self, name):  # noqa: N802
        self.calls.append(("activate", name))
        return True

    def ClearSelection2(self, _all):  # noqa: N802
        self.calls.append(("clear",))

    def ViewZoomTo2(self, *box):  # noqa: N802
        self.calls.append(("zoom", box))

    def ViewZoomtofit2(self):  # noqa: N802
        self.calls.append(("fit",))

    def SelectByID2(self, name, kind, x, y, *_rest):  # noqa: N802
        self.calls.append(("select", kind, x, y))
        return self.picked is not None

    def GetSelectedObjectCount2(self, _mark):  # noqa: N802
        return 2  # the view, then the edge

    def GetSelectedObjectType3(self, index, _mark):  # noqa: N802
        assert index == 2
        return self.kind

    def GetSelectedObject6(self, index, _mark):  # noqa: N802
        assert index == 2
        return self.picked


def _inset_pick_adapter(monkeypatch, picked, kind=1):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view)
    monkeypatch.setattr(drawing, "_edge_endpoint_key", lambda _adapter, edge: edge.key)
    draw = _InsetPickDraw(picked, kind)

    def attempt(call, default=None):
        try:
            return call()
        except Exception:
            return default

    return SimpleNamespace(currentModel=draw, _attempt=attempt), draw


def test_an_inset_pick_reads_back_its_edge_in_machine_x(monkeypatch) -> None:
    # Component-local x 0.150 m, moved +13 mm along machine x: 163 mm.
    plate = _Full((1, 0, 0, 0, 1, 0, 0, 0, 1, 0.013, 0.0, 0.0, 1.0, 0, 0, 0))
    plate.Name2 = "fr-frame-1/fr-nameplate-1"
    edge = SimpleNamespace(
        key=(0.150, 0.0523, 0.010, 0.150, 0.0523, 0.040), GetComponent=lambda: plate
    )
    adapter, draw = _inset_pick_adapter(monkeypatch, edge)

    picked, owner, xs = drawing._read_inset_pick(adapter, "B-B", (0.1, 0.2))

    assert picked is edge and owner == "fr-frame-1/fr-nameplate-1"
    assert xs == pytest.approx((163.0, 163.0))
    half = drawing._HIT_ZOOM_HALF
    # Zoomed onto the station for the pick, back to fit before the read-back.
    assert draw.calls[:5] == [
        ("activate", "B-B"),
        ("clear",),
        ("zoom", (0.1 - half, 0.2 - half, 0.0, 0.1 + half, 0.2 + half, 0.0)),
        ("select", "EDGE", 0.1, 0.2),
        ("fit",),
    ]


def test_an_inset_pick_that_is_not_a_component_edge_reads_no_x(monkeypatch) -> None:
    orphan = SimpleNamespace(key=(0.0,) * 6, GetComponent=lambda: None)
    for picked, kind, reason in (
        (None, 1, "no edge"),
        ("silhouette", 11, "selection type 11"),
        (orphan, 1, "edge without a component"),
    ):
        adapter, _ = _inset_pick_adapter(monkeypatch, picked, kind)
        assert drawing._read_inset_pick(adapter, "B-B", (0.1, 0.2)) == (
            None,
            reason,
            None,
        )
