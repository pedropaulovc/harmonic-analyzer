from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from diagnostics import diag_mcmaster_lib as diag
from diagnostics.diag_build_91247A720 import logo_ring_profile
from diagnostics.diag_build_99607A213 import flare_profile
from diagnostics.sketch_profile import Line


class _Model:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def ClearSelection2(self, _all_selections: bool) -> None:
        self._events.append("clear")

    def SaveAs3(self, path: str, _version: int, _options: int) -> int:
        self._events.append(f"save_as:{Path(path).name}")
        return 0


class _SwApp:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def CloseAllDocuments(self, include_unsaved: bool) -> bool:
        assert include_unsaved is True
        self._events.append("close")
        return True


class _Adapter:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.swApp = _SwApp(events)
        self.currentModel = _Model(events)

    def _attempt(self, call, default=None):
        try:
            return call()
        except Exception:
            return default

    async def save_file(self, _path: str):
        self._events.append("save_file")
        return SimpleNamespace(is_success=True, data=None, error=None)

    async def open_model(self, path: str):
        assert self.currentModel is None, "previous document was not closed"
        self._events.append(f"open:{Path(path).name}")
        self.currentModel = _Model(self._events)
        return SimpleNamespace(is_success=True, data=None, error=None)


def test_stl_arbitration_closes_each_document_before_open_or_compare(
    tmp_path: Path, monkeypatch,
) -> None:
    events: list[str] = []
    adapter = _Adapter(events)
    part_no = "TEST"

    monkeypatch.setattr(diag, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(diag, "MCMASTER_DIR", tmp_path / "vendor")
    monkeypatch.setattr(
        diag,
        "mass_properties",
        lambda _adapter: {
            "volume_mm3": 101.0,
            "surface_mm2": 1000.0,
            "com_mm": [0.0, 0.0, 0.0],
        },
    )
    monkeypatch.setattr(diag, "face_areas", lambda _adapter: [1200.0])
    monkeypatch.setattr(diag, "vendor_face_areas", lambda _truth: [1200.0])
    monkeypatch.setattr(diag, "_early_bound", lambda obj, _name: obj)

    async def _export_views(_adapter, _stem: str) -> dict[str, str]:
        events.append("export_views")
        return {}

    monkeypatch.setattr(diag, "export_views", _export_views)

    def _load(path: str):
        assert adapter.currentModel is None, "last STL document was not closed"
        events.append(f"load:{Path(path).name}")
        return SimpleNamespace(volume=100.0, area=1000.0)

    monkeypatch.setitem(sys.modules, "trimesh", SimpleNamespace(load=_load))
    truth = {
        "mass": {
            "volume_mm3": 100.0,
            "surface_area_mm2": 1000.0,
            "com_mm": [0.0, 0.0, 0.0],
        },
    }

    asyncio.run(diag.gate_and_save(adapter, part_no, truth))

    assert events == [
        "save_file",
        "export_views",
        "close",
        "open:TEST-replica.SLDPRT",
        "clear",
        "save_as:TEST-replica.stl",
        "close",
        "open:TEST.SLDPRT",
        "clear",
        "save_as:TEST-vendor.stl",
        "close",
        "load:TEST-replica.stl",
        "load:TEST-vendor.stl",
    ]


class _PreferenceApp:
    """``ISldWorks.SetUserPreferenceToggle`` is VT_VOID (dispid 45, retval
    ``(24, 0)``), so pywin32 returns ``None`` on SUCCESS and this fake must
    too.  A fake that returned a truthy value would agree with a buggy guard
    instead of with the interface -- the trap
    ``test_sketch_preference_baseline`` already pins."""

    def __init__(self) -> None:
        self.toggles = dict(diag.SEAT_SKETCH_BASELINE.values())

    def GetUserPreferenceToggle(self, toggle: int) -> bool:
        return self.toggles[toggle]

    def SetUserPreferenceToggle(self, toggle: int, value: bool) -> None:
        self.toggles[toggle] = bool(value)


class _SketchManager:
    def __init__(self) -> None:
        self._add_to_db = False
        self.add_to_db_history: list[bool] = []

    @property
    def AddToDB(self) -> bool:
        return self._add_to_db

    @AddToDB.setter
    def AddToDB(self, value: object) -> None:
        self._add_to_db = bool(value)
        self.add_to_db_history.append(self._add_to_db)


class _WeldedSeat:
    """A seat whose sketch database has ALREADY welded the endpoint pairs.

    That is every real seat: an exact-coordinate endpoint written straight to
    the sketch DB is coalesced there at creation, which is why
    ``_common.add_line_chain`` closes its loops while authoring no closure
    relation at all.

    So ``add_sketch_constraint`` here answers a ``merge`` the way SW 2026
    answers it in that state.  Both refs resolve, through ``GetStartPoint2`` /
    ``GetEndPoint2``, to one and the same ``ISketchPoint``;
    ``ISketchRelationManager.AddRelation`` has nothing to merge and returns
    ``None`` WITHOUT raising; the adapter has no COM error to quote and
    reports a bare rejection.  On 2026-09-18 that refusal failed
    ``part:pen_set_screw`` and ``part:knife_hanger_stud`` on three different
    workers, always on the first pair, because every pair is in this state.

    A profile must therefore author to completion against this seat.
    """

    def __init__(self) -> None:
        self.swApp = _PreferenceApp()
        self.currentSketchManager = _SketchManager()
        self.drawn: list[str] = []
        self._next_id = 0

    def _attempt(self, call, default=None):
        try:
            return call()
        except Exception:
            return default

    def _register(self, kind: str):
        self._next_id += 1
        self.drawn.append(kind)
        return SimpleNamespace(
            is_success=True, data=f"{kind}_{self._next_id}", error=None
        )

    async def add_line(self, _x1, _y1, _x2, _y2):
        return self._register("Line")

    async def add_arc(self, _cx, _cy, _x1, _y1, _x2, _y2):
        return self._register("Arc")

    async def add_sketch_constraint(self, entity1, entity2, relation, entity3=None):
        return SimpleNamespace(
            is_success=False,
            data=None,
            error=(
                f"SolidWorks rejected '{relation}' relation on "
                f"'{entity1}' and '{entity2}'"
            ),
        )


@pytest.mark.parametrize(
    ("label", "profile", "loops"),
    [("flare lens", flare_profile, 1), ("logo ring", logo_ring_profile, 2)],
)
def test_a_profile_authors_fully_on_a_seat_that_refuses_every_merge(
    label: str, profile, loops: int
) -> None:
    """Closure must not depend on a relation a welded pair can only refuse.

    Both real profiles are exercised because both really failed: the 2-segment
    flare lens and the 9-segment logo ring, which between them cover a pair
    count of 2 and of 9 and every line/arc adjacency the fleet authors.

    The seat refuses every merge, so this passes only while the authoring path
    asks for none.  Reinstating the merge loop turns the first refusal into a
    ``RuntimeError`` out of ``check()`` and fails this test -- which is what
    happened on the farm.
    """
    segments = profile()

    ids = asyncio.run(
        diag.draw_closed_profile(adapter := _WeldedSeat(), segments, label=label,
                                 loops=loops)
    )

    assert len(ids) == len(segments)
    assert adapter.drawn == [
        "Line" if isinstance(segment, Line) else "Arc" for segment in segments
    ]
    # The weld only happens for geometry that went into the DB directly, and a
    # latched AddToDB would silently change how every LATER sketch is drawn.
    assert adapter.currentSketchManager.add_to_db_history == [True, False]


def test_endpoints_the_seat_left_unwelded_fail_the_build() -> None:
    """The weld is MEASURED, not assumed -- and an unwelded pair is fatal.

    Nothing between the authored coordinates and the finished sketch is
    asserted any more, so this read IS the guarantee.  ``closure`` is
    ``"closed"`` here on purpose: the contour count alone would have accepted
    this sketch, and a loop held together by coordinates with two points still
    sitting at each vertex opens on the next edit.
    """
    state = {
        "contour_count": 1,
        "segment_count": 2,
        "point_count": 4,
        "distinct_point_positions": 2,
        "coincident_point_pairs": 2,
    }

    with pytest.raises(RuntimeError) as raised:
        diag.assert_profile_closed(
            _seat_reading(state), "flare lens", loops=1, feature="FlareProfile"
        )

    # The counts have to travel with the raise: this message is read off a dead
    # leaf's log, where re-reading the sketch is no longer possible.
    message = str(raised.value)
    assert "4 sketch points" in message or "kept 4" in message
    assert "2 distinct places" in message


@pytest.mark.parametrize(
    ("census", "why"),
    [
        ({"coincident_point_pairs": 0}, "measured: every pair welded"),
        ({}, "census unreadable: absent, which is not the same as zero"),
    ],
)
def test_a_welded_or_unmeasured_profile_is_accepted(census: dict, why: str) -> None:
    """The gate must fire on a MEASUREMENT, never on a missing one.

    ``_point_census`` omits the key when the seat returned no readable point
    coordinates, and an RPC hiccup becoming a geometry failure would be a
    guard that fails closed on healthy geometry -- the same rule the
    ``"unknown"`` closure state already follows.
    """
    state = {
        "contour_count": 1,
        "segment_count": 2,
        "point_count": 2,
        **census,
    }

    returned = diag.assert_profile_closed(
        _seat_reading(state), "flare lens", loops=1, feature="FlareProfile"
    )

    assert returned["closure"] == "closed", why


def _seat_reading(state: dict):
    """An adapter whose ONE sketch read answers ``state``.

    The stub sits at ``adapter._attempt`` -- the single COM boundary
    ``record_sketch_closure`` crosses -- so the real tri-state verdict logic,
    the real warnings and the real span all still run over these counts.
    Stubbing ``record_sketch_closure`` itself would have skipped exactly the
    code that decides ``closure``, and faking the twenty COM probes behind it
    would pin their shapes instead of the decision under test.
    """
    return SimpleNamespace(_attempt=lambda _call, default=None: dict(state))
