"""SolidWorks-free contracts for the drawing-sketch inference guards.

``de2fc7af`` made ``swSketchInference`` / ``AutomaticRelations`` /
``InferFromModel`` a declared ON baseline at the APPLICATION level, and
``top_frame``'s D-D section was promptly cut 4.29 degrees oblique (0.674 mm off
station at the rail face) because its cutting line was authored through the
inference engine.  ``_drawing_common`` now owns one idiom for every
drawing-sketch primitive: ``sketch_geometry_direct_to_db``, a read-back that
refuses drift above 1e-9 m, and an explicit ``Select4`` for the primitives whose
object feeds a selection-precondition API.

The section path is already pinned through ``create_section_view`` in
``test_rocker_arm_support_drawing.py``.  These cases cover the parts of the
idiom that path does not execute -- the exception route out of the guard, the
selection companion's two refusals, the circle traversal, and
``create_view_theoretical_datum`` -- each one written against a mutation that
otherwise ships silently: a dropped restore, an unchecked ``Select4``, a radius
compared against a diameter, a removed centre or point read-back, and a datum
whose ``DisplayWhenAdded`` restore or read-back is gone.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common


def _member(obj, name):
    """Stand in for the adapter's method-or-property COM read."""
    value = getattr(obj, name, None)
    return value() if callable(value) else value


def _adapter(model=None):
    return SimpleNamespace(_get_attr_or_call=_member, currentModel=model)


def _point(x, y, z=0.0):
    return SimpleNamespace(X=x, Y=y, Z=z)


class _SketchManager:
    """Records ``AddToDB`` at creation time and every value written to it."""

    def __init__(self, add_to_db: bool = False, snap: float = 0.0) -> None:
        self.AddToDB = add_to_db
        self.DisplayWhenAdded = False
        self.add_to_db_when_created: bool | None = None
        self.display_when_created: bool | None = None
        self.writes: list[bool] = []
        self.raise_on_create = False
        self._snap = snap

    def __setattr__(self, name: str, value: object) -> None:
        if name == "AddToDB" and "writes" in self.__dict__:
            self.writes.append(bool(value))
        super().__setattr__(name, value)

    def CreatePoint(self, x, y, z):
        self.add_to_db_when_created = self.AddToDB
        self.display_when_created = self.DisplayWhenAdded
        if self.raise_on_create:
            raise RuntimeError("the seat died mid-create")
        return _point(x + self._snap, y, z)


@pytest.fixture
def identity_early_bound(monkeypatch):
    """Drop the early-bound casts; the doubles are already the interfaces."""
    monkeypatch.setattr(drawing_common, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(
        drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )


def test_direct_to_db_restores_add_to_db_when_the_block_raises():
    """A COM failure mid-create must not leave the SEAT direct-to-DB.

    ``AddToDB`` outlives the document, the recipe and the leaf, so a restore
    that only runs on the normal exit leaks direct-to-DB authoring into every
    recipe that follows on that seat -- silently, because nothing downstream
    reads the preference back.
    """
    manager = _SketchManager()

    with pytest.raises(ZeroDivisionError):
        with drawing_common.sketch_geometry_direct_to_db(manager):
            assert manager.AddToDB is True
            raise ZeroDivisionError("a COM call died mid-block")

    assert manager.AddToDB is False
    assert manager.writes == [True, False]


def test_nested_guard_does_not_switch_inference_back_on_early(
    identity_early_bound,
):
    """An inner block must not restore inference while the outer is drawing.

    This is what the LIVE read of the previous value buys: the inner exit reads
    back ``True`` and restores ``True``.  A value captured once by the outer
    caller and passed down would put ``False`` back on the inner exit, with the
    outer block still authoring geometry.
    """
    manager = _SketchManager()

    with drawing_common.sketch_geometry_direct_to_db(manager):
        with drawing_common.sketch_geometry_direct_to_db(manager):
            pass
        assert manager.AddToDB is True

    assert manager.AddToDB is False


def test_selection_refuses_a_declined_select4(identity_early_bound):
    """``Select4`` returning False must raise, not fall through.

    ``CreateDetailViewAt4`` and ``CreateSectionViewAt5`` consume the current
    SELECTION rather than an object, so an unchecked failure crops or sections
    whatever was selected before -- or nothing.
    """
    segment = SimpleNamespace(Select4=lambda append, data: False)
    adapter = _adapter(
        SimpleNamespace(
            SelectionManager=SimpleNamespace(
                CreateSelectData=lambda: SimpleNamespace(View=None),
                GetSelectedObjectCount2=lambda mark: 1,
            )
        )
    )

    with pytest.raises(RuntimeError, match="failed to select the detail fence"):
        drawing_common.select_sketch_geometry(
            adapter, segment, object(), what="detail fence", label="A"
        )


def test_selection_refuses_a_stale_extra_selection(identity_early_bound):
    """Two selected entities is the wrong precondition, even though Select4 won.

    A stale selection plus the new segment is two entities, and both consuming
    APIs read one of them without saying which.
    """
    segment = SimpleNamespace(Select4=lambda append, data: True)
    adapter = _adapter(
        SimpleNamespace(
            SelectionManager=SimpleNamespace(
                CreateSelectData=lambda: SimpleNamespace(View=None),
                GetSelectedObjectCount2=lambda mark: 2,
            )
        )
    )

    with pytest.raises(RuntimeError, match="produced 2 entities"):
        drawing_common.select_sketch_geometry(
            adapter, segment, object(), what="detail fence", label="A"
        )


def test_circle_read_back_measures_radius_not_diameter(identity_early_bound):
    """The fence's radius must be compared against the radius it was authored.

    A guard that cannot tell a radius from a diameter accepts a fence twice the
    requested size, which crops a different set of features into the detail
    than its dimensions were written for.
    """
    center = (0.010, 0.020, 0.0)
    radius = 0.005

    drawing_common.assert_sketch_circle_placed(
        _adapter(),
        SimpleNamespace(GetCenterPoint2=lambda: _point(*center), GetRadius=lambda: radius),
        center,
        radius,
        what="detail fence",
        label="A",
    )

    with pytest.raises(RuntimeError, match=r"radius sits 5 mm"):
        drawing_common.assert_sketch_circle_placed(
            _adapter(),
            SimpleNamespace(
                GetCenterPoint2=lambda: _point(*center),
                GetRadius=lambda: radius * 2.0,
            ),
            center,
            radius,
            what="detail fence",
            label="A",
        )


def test_circle_read_back_refuses_a_snapped_centre(identity_early_bound):
    """A fence whose centre moved crops the wrong feature at the right size."""
    with pytest.raises(RuntimeError, match=r"centre point sits 0\.674 mm"):
        drawing_common.assert_sketch_circle_placed(
            _adapter(),
            SimpleNamespace(
                GetCenterPoint2=lambda: _point(0.010, 0.020 + 0.000674),
                GetRadius=lambda: 0.005,
            ),
            (0.010, 0.020, 0.0),
            0.005,
            what="detail fence",
            label="A",
        )


def test_read_back_refuses_an_absent_member_as_a_placement_failure(
    identity_early_bound,
):
    """An absent COM member must refuse by name, not raise TypeError or pass.

    ``_get_attr_or_call`` is ``getattr(obj, name, None)``, so a member the
    strict early-bound wrapper does not declare reads back as ``None``.  Left
    unchecked that is a ``TypeError`` from ``float(None)`` -- a guard that reads
    like a code bug rather than a refusal.

    The refusal has to name what is actually missing, which is why the endpoint
    case is anchored: an absent POINT must be reported as an absent point, not
    as an absent coordinate OF that point ("has no end point X"), which is what
    comes out if the point check is dropped and the coordinate read catches the
    ``None`` one hop later -- a message that says the endpoint exists when it
    does not.
    """
    adapter = _adapter()

    with pytest.raises(RuntimeError, match=r"has no end point$"):
        drawing_common.assert_sketch_line_placed(
            adapter,
            SimpleNamespace(GetStartPoint2=lambda: _point(0.0, 0.0)),
            ((0.0, 0.0, 0.0), (0.001, 0.0, 0.0)),
            what="centreline",
            label="Top",
        )

    with pytest.raises(RuntimeError, match="has no radius"):
        drawing_common.assert_sketch_circle_placed(
            adapter,
            SimpleNamespace(GetCenterPoint2=lambda: _point(0.0, 0.0), GetRadius=lambda: None),
            (0.0, 0.0, 0.0),
            0.005,
            what="detail fence",
            label="A",
        )

    # A legitimate origin coordinate is not absence: the check is an identity
    # test, never truthiness.
    drawing_common.assert_sketch_geometry_placed(
        adapter,
        (("position", _point(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),),
        what="theoretical datum point",
        label="hole table origin",
    )


def _datum_doubles(monkeypatch, manager):
    monkeypatch.setattr(drawing_common, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(drawing_common, "view_name", lambda *_: "Top")
    monkeypatch.setattr(drawing_common, "rebuild_drawing", lambda *a, **k: None)
    model = SimpleNamespace(
        SketchManager=manager,
        ActivateView=lambda name: True,
        ClearSelection2=lambda flag: None,
    )
    return _adapter(model)


def test_theoretical_datum_restores_display_when_added_on_failure(monkeypatch):
    """The datum's second preference must unwind too, on the exception route.

    ``DisplayWhenAdded`` is application-level exactly like ``AddToDB``, and it
    is written OUTSIDE the contextmanager because the shared idiom owns only
    ``AddToDB``.  A dropped restore there leaves every later recipe's
    direct-to-DB geometry visible on its sheet.
    """
    manager = _SketchManager()
    manager.raise_on_create = True
    adapter = _datum_doubles(monkeypatch, manager)

    with pytest.raises(RuntimeError, match="the seat died mid-create"):
        drawing_common.create_view_theoretical_datum(
            adapter, object(), point_xy=(0.030, 0.040), label="hole table origin"
        )

    assert (manager.add_to_db_when_created, manager.display_when_created) == (True, True)
    assert manager.AddToDB is False
    assert manager.DisplayWhenAdded is False


def test_theoretical_datum_refuses_a_snapped_point(monkeypatch):
    """A snapped theoretical sharp silently relocates a whole hole table.

    The datum sits where two faces WOULD have met before the fillet, so it is
    never on the geometry the view shows and the real filleted edge that
    replaced it is a fraction of a millimetre away.  Every coordinate the
    native hole table prints is measured from this point.
    """
    adapter = _datum_doubles(monkeypatch, _SketchManager(snap=0.0003))

    with pytest.raises(RuntimeError, match=r"position sits 0\.3 mm"):
        drawing_common.create_view_theoretical_datum(
            adapter, object(), point_xy=(0.030, 0.040), label="hole table origin"
        )


def test_theoretical_datum_returns_the_point_it_authored(monkeypatch):
    """The guarded happy path still yields the datum, at the requested place."""
    manager = _SketchManager()
    adapter = _datum_doubles(monkeypatch, manager)

    point = drawing_common.create_view_theoretical_datum(
        adapter, object(), point_xy=(0.030, 0.040), label="hole table origin"
    )

    assert (point.X, point.Y, point.Z) == (0.030, 0.040, 0.0)
    assert manager.add_to_db_when_created is True
    assert manager.AddToDB is False
    assert manager.DisplayWhenAdded is False
