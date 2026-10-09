"""Drawing surface-finish leaders must qualify their part-owned model face."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

import _drawing_common
import _part_pmi
from _gtol_spec import (
    ConeFace,
    CylinderFace,
    PlanarFace,
    SphereFace,
    TorusFace,
    gtol_frame_xml,
)
from _part_pmi import _FaceGeometry
from _surface_finish import SurfaceFinishControl


@dataclass
class _Entity:
    faces: tuple[Any, ...] = ()
    face: Any | None = None

    def GetTwoAdjacentFaces2(self) -> tuple[Any, ...]:
        return self.faces

    def GetFace(self) -> Any | None:
        return self.face


def _control() -> SurfaceFinishControl:
    return SurfaceFinishControl("bore", 1.6, CylinderFace(10.0))


def _geometry(face: Any, diameter_mm: float) -> _FaceGeometry:
    return _FaceGeometry(
        face=face,
        identity=4002,
        parameters=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter_mm / 2000.0),
        outward_normal=None,
        box=(),
    )


@pytest.mark.parametrize("entity_type", ("EDGE", "SILHOUETTE", "FACE"))
def test_surface_finish_accepts_controlled_face_for_every_entity_path(
    monkeypatch: pytest.MonkeyPatch, entity_type: str
) -> None:
    controlled_face = object()
    other_face = object()
    entity = _Entity(faces=(other_face, controlled_face), face=controlled_face)
    selected = controlled_face if entity_type == "FACE" else entity
    geometries = {
        id(controlled_face): _geometry(controlled_face, 10.0),
        id(other_face): _geometry(other_face, 6.0),
    }
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        "_part_pmi._face_geometry", lambda face: geometries[id(face)]
    )

    signatures = _drawing_common._validate_surface_finish_control_face(
        selected, entity_type=entity_type, control=_control(), label="bearing finish"
    )

    assert any(item["geometry"].face is controlled_face for item in signatures)


@pytest.mark.parametrize("entity_type", ("EDGE", "SILHOUETTE", "FACE"))
def test_surface_finish_rejects_entity_without_controlled_face(
    monkeypatch: pytest.MonkeyPatch, entity_type: str
) -> None:
    wrong_face = object()
    entity = _Entity(faces=(wrong_face,), face=wrong_face)
    selected = wrong_face if entity_type == "FACE" else entity
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        "_part_pmi._face_geometry", lambda face: _geometry(face, 6.0)
    )

    with pytest.raises(
        RuntimeError,
        match="selected .* does not touch controlled surface-finish face",
    ):
        _drawing_common._validate_surface_finish_control_face(
            selected,
            entity_type=entity_type,
            control=_control(),
            label="bearing finish",
        )


def test_surface_finish_rejects_unverifiable_entity_type() -> None:
    with pytest.raises(ValueError, match="expected EDGE, SILHOUETTE, or FACE"):
        _drawing_common._surface_finish_entity_faces(
            object(), entity_type="VERTEX", label="bearing finish"
        )


def test_add_surface_finish_validates_part_control_without_audit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = object()
    monkeypatch.delenv("HARMONIC_SURFACE_AUDIT", raising=False)
    monkeypatch.setattr(
        _drawing_common,
        "_select_annotation_entity",
        lambda *_args, **_kwargs: selected,
    )

    def reject(
        entity: Any,
        *,
        entity_type: str,
        control: SurfaceFinishControl,
        label: str,
    ) -> tuple[dict[str, Any], ...]:
        assert entity is selected
        assert entity_type == "EDGE"
        assert control is finish
        assert label == "bearing finish"
        raise RuntimeError("wrong controlled face")

    monkeypatch.setattr(
        _drawing_common, "_validate_surface_finish_control_face", reject
    )
    finish = _control()

    with pytest.raises(RuntimeError, match="wrong controlled face"):
        _drawing_common.add_surface_finish(
            object(),
            object(),
            edge_xy=(0.1, 0.1),
            symbol_xy=(0.2, 0.2),
            control=finish,
            label="bearing finish",
        )


class _Annotation:
    """The ``IAnnotation`` readbacks the attachment guard sends."""

    def __init__(
        self,
        entities: tuple[Any, ...],
        types: tuple[int, ...],
        *,
        count: int | None = None,
        leaders: int = 1,
        dangling: bool = False,
        leader_points: tuple[float, ...] = (),
    ) -> None:
        self.entities, self.types = entities, types
        self.count = len(entities) if count is None else count
        self.leaders, self.dangling, self.leader_points = leaders, dangling, leader_points

    def GetAttachedEntities3(self) -> tuple[Any, ...]:  # noqa: N802
        return self.entities

    def GetAttachedEntityCount3(self) -> int:  # noqa: N802
        return self.count

    def GetAttachedEntityTypes(self) -> tuple[int, ...]:  # noqa: N802
        return self.types

    def GetLeaderCount(self) -> int:  # noqa: N802
        return self.leaders

    def IsDangling(self) -> bool:  # noqa: N802
        return self.dangling

    def GetLeaderPointsAtIndex(self, index: int) -> tuple[float, ...]:  # noqa: N802
        assert index == 0
        return self.leader_points


class _Silhouette:
    """An ``ISilhouetteEdge``: identified only through its owning face."""

    def __init__(self, face: Any) -> None:
        self.face = face

    def GetFace(self) -> Any:  # noqa: N802
        return self.face


class _App:
    def IsSame(self, left: Any, right: Any) -> int:  # noqa: N802
        return int(left is right)


class _Adapter:
    swApp = _App()


@pytest.fixture(autouse=True)
def _plain_early_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)


def _guard(annotation: _Annotation, entity: Any, entity_type: str) -> None:
    _drawing_common._assert_attached_to(
        _Adapter(), annotation, entity, entity_type=entity_type,
        what="surface-finish symbol", label="bore",
    )


@pytest.mark.parametrize(
    ("entity_type", "code"), (("EDGE", 1), ("FACE", 2), ("SILHOUETTE", 46))
)
def test_attachment_guard_accepts_the_inserted_entity(entity_type: str, code: int) -> None:
    face = object()
    entity = _Silhouette(face) if entity_type == "SILHOUETTE" else object()
    # Another silhouette of the same face (the other flank) is the same
    # attachment as far as identity goes; the leader landing tells them apart.
    attached = _Silhouette(face) if entity_type == "SILHOUETTE" else entity
    _guard(_Annotation((attached,), (code,)), entity, entity_type)


@pytest.mark.parametrize(
    ("entities", "types", "count", "expected"),
    (
        # A moved leader on the sfprobe leaves: IsAttached True, no entity.
        ((), (), 0, "entities=0"),
        # A landing that resolved to the neighbouring edge.
        (("other",), (1,), 1, "same_entity=False"),
        # The count, type and entity readbacks disagree.
        (("edge",), (1,), 0, "count=0"),
        (("edge",), (), 1, "types=()"),
        (("edge",), (2,), 1, "types=(2,)"),
        (("edge", "edge"), (1, 1), 2, "entities=2"),
        ((None,), (0,), 1, "same_entity=False"),
    ),
    ids=(
        "detached", "neighbour", "count-disagrees", "type-missing",
        "type-is-face", "two-entities", "null-entity",
    ),
)
def test_attachment_guard_rejects_a_symbol_off_its_edge(
    entities: tuple[Any, ...], types: tuple[int, ...], count: int, expected: str
) -> None:
    edge, other = object(), object()
    resolved = tuple({"edge": edge, "other": other, None: None}[e] for e in entities)
    with pytest.raises(RuntimeError, match=r"lost its edge attachment \(bore\)") as info:
        _guard(_Annotation(resolved, types, count=count), edge, "EDGE")
    assert expected in str(info.value)


@pytest.mark.parametrize(
    ("leaders", "dangling"), ((0, False), (2, False), (1, True)), ids=("none", "two", "dangling")
)
def test_attachment_guard_requires_one_live_leader(leaders: int, dangling: bool) -> None:
    edge = object()
    with pytest.raises(RuntimeError, match=r"lost its edge attachment \(bore\)"):
        _guard(_Annotation((edge,), (1,), leaders=leaders, dangling=dangling), edge, "EDGE")


@pytest.mark.parametrize(
    ("attached", "types", "expected"),
    (
        # IsSame reads 0 for every silhouette, so the owning faces decide:
        # a silhouette of another face is the neighbouring feature.
        (_Silhouette(object()), (46,), "same_entity=False"),
        # A silhouette that has lost its face cannot be identified.
        (_Silhouette(None), (46,), "same_entity=False"),
        # The type readback says edge, however the entity reads.
        (None, (1,), "types=(1,)"),
    ),
    ids=("other-face", "faceless", "type-is-edge"),
)
def test_silhouette_guard_requires_the_selected_silhouettes_face(
    attached: Any, types: tuple[int, ...], expected: str
) -> None:
    selected = _Silhouette(object())
    attached = selected if attached is None else attached
    with pytest.raises(RuntimeError, match=r"lost its silhouette attachment \(bore\)") as info:
        _guard(_Annotation((attached,), types), selected, "SILHOUETTE")
    assert expected in str(info.value)


def test_face_guard_rejects_a_face_that_is_not_the_selected_one() -> None:
    # The former surface/normal/box fallback accepted any face with the
    # selected face's signature; identity is now IsSame or nothing.
    with pytest.raises(RuntimeError, match=r"lost its face attachment \(bore\)"):
        _guard(_Annotation((object(),), (2,)), object(), "FACE")


def test_attachment_guard_refuses_a_kind_it_cannot_prove() -> None:
    with pytest.raises(ValueError, match="cannot verify a DIMENSION attachment"):
        _guard(_Annotation((object(),), (14,)), object(), "DIMENSION")


def test_feature_control_frame_refuses_a_dimension_attachment() -> None:
    class _Adapter:
        currentModel = None

    with pytest.raises(ValueError, match="cannot attach to a DIMENSION"):
        _drawing_common.add_feature_control_frame(
            _Adapter(), None, edge_xy=(0.0, 0.0), frame_xy=(0.0, 0.0),
            characteristic="runout", tolerance="0.01", label="runout",
            entity_type="DIMENSION",
        )


class _FrameXml:
    def __init__(self, datums: tuple[str, ...]) -> None:
        self.xml = gtol_frame_xml("position", "0.10", datums=datums, diameter=True)

    def GetSymbolXml(self) -> str:
        return self.xml


class _NamedAnnotation:
    """A frame's or tag's annotation: its name, selection, attachment and print."""

    def __init__(self, name: str, *, selects: bool = True) -> None:
        self.name = name
        self.selects = selects
        self.position = (0.0, 0.0)
        self.attached: tuple[Any, ...] = ()
        self.types: tuple[int, ...] = ()
        self.prints: list[tuple[str, tuple[float, float]]] = []

    def GetName(self) -> str:
        return self.name

    def Select2(self, _append: bool, _mark: int) -> bool:
        return self.selects

    def SetPosition2(self, x: float, y: float, _z: float) -> bool:
        self.position = (x, y)
        return True

    def GetPosition(self) -> tuple[float, float, float]:
        return (*self.position, 0.0)

    def GetAttachedEntities3(self) -> tuple[Any, ...]:
        return self.attached

    def GetAttachedEntityCount3(self) -> int:
        return len(self.attached)

    def GetAttachedEntityTypes(self) -> tuple[int, ...]:
        return self.types

    def GetDisplayData(self) -> Any:
        prints = self.prints

        class _Data:
            def GetTextCount(self) -> int:
                return len(prints)

            def GetTextAtIndex(self, index: int) -> str:
                return prints[index][0]

            def GetTextPositionAtIndex(self, index: int) -> tuple[float, float, float]:
                return (*prints[index][1], 0.0)

        return _Data()


class _FrameGtol:
    def __init__(self, name: str, datums: tuple[str, ...] = ("A",)) -> None:
        self.annotation = _NamedAnnotation(name)
        self.annotation.position = (0.1466, 0.219)
        self.frames = [_FrameXml(datums)]

    def GetAnnotation(self) -> _NamedAnnotation:
        return self.annotation

    def GetFrameCount(self) -> int:
        return len(self.frames)

    def GetFrame(self, index: int) -> _FrameXml:
        return self.frames[index - 1]


class _DatumTag:
    def __init__(self, label: str = "", name: str = "DetailItem900") -> None:
        self.label = label
        self.annotation = _NamedAnnotation(name)

    def SetLabel(self, label: str) -> bool:
        self.label = label
        return True

    def GetLabel(self) -> str:
        return self.label

    def GetAnnotation(self) -> _NamedAnnotation:
        return self.annotation


class _View:
    def __init__(self, tags: tuple[str, ...], frames: tuple[_FrameGtol, ...]) -> None:
        self.tags = [_DatumTag(label) for label in tags]
        self.frames = frames

    def GetDatumTags(self) -> tuple[_DatumTag, ...]:
        return tuple(self.tags)

    def GetGTols(self) -> tuple[_FrameGtol, ...]:
        return self.frames


_DATUM_B_XY = (0.1613, 0.200)


def _frame_datum(
    monkeypatch: pytest.MonkeyPatch,
    frame: _FrameGtol,
    *,
    attaches_to: Any = "frame",
    selected: tuple[int, Any] | None = None,
    prints: list[tuple[str, tuple[float, float]]] | None = None,
) -> _DatumTag:
    """Run add_frame_datum_feature on a fake seat.

    ``attaches_to`` is what the inserted tag is attached to after the rebuild
    ("frame", another object, or None for nothing).  ``selected`` is what the
    selection manager reports (type, object; default the frame).  ``prints``
    is the tag's printed text (default: its letter 1.5 mm right of and 2 mm
    under the request).  Like farm run 20261009T182549169Z, the tag's
    GetPosition reads x 0.0 with the requested y.
    """
    view = _View(("A",), (frame,))
    kind, picked = selected if selected is not None else (13, frame)
    inserted: list[_DatumTag] = []

    class _SelectionManager:
        def GetSelectedObjectCount2(self, _mark: int) -> int:
            return 1

        def GetSelectedObjectType3(self, _index: int, _mark: int) -> int:
            return kind

        def GetSelectedObject6(self, _index: int, _mark: int) -> Any:
            return picked

    class _Draw:
        SelectionManager = _SelectionManager()

        def ActivateView(self, _name: str) -> bool:
            return True

        def ClearSelection2(self, _all: bool) -> None:
            pass

        def InsertDatumTag2(self) -> _DatumTag:
            tag = _DatumTag()
            view.tags.append(tag)
            inserted.append(tag)
            return tag

    def rebuild(_adapter: Any, *, label: str) -> None:
        annotation = inserted[-1].annotation
        target = frame if attaches_to == "frame" else attaches_to
        if target is not None:
            annotation.attached = (target,)
            annotation.types = (13,)
        annotation.position = (0.0, annotation.position[1])
        annotation.prints = (
            [(inserted[-1].label, (_DATUM_B_XY[0] + 0.0015, _DATUM_B_XY[1] - 0.002))]
            if prints is None
            else prints
        )

    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    monkeypatch.setattr(_drawing_common, "view_name", lambda *_: "Drawing View3")
    monkeypatch.setattr(_drawing_common, "rebuild_drawing", rebuild)
    return _drawing_common.add_frame_datum_feature(
        type("_Adapter", (), {"currentModel": _Draw()})(), view, frame, datum="B",
        symbol_xy=_DATUM_B_XY, label="dowel hole pattern datum B",
    )


def test_frame_datum_symbol_goes_on_the_frame_it_names(monkeypatch) -> None:
    # Farm run 20261009T182549169Z: Select2 on DetailItem354 attached datum B
    # to it (one entity, type 13, named DetailItem354), and GetPosition read
    # x 0.0: the printed letter is the placement proof.
    frame = _FrameGtol("DetailItem354")
    tag = _frame_datum(monkeypatch, frame)
    assert tag.label == "B"
    assert tag.annotation.attached == (frame,)
    assert tag.annotation.GetPosition()[0] == 0.0


@pytest.mark.parametrize(
    ("case", "match"),
    (
        ("not selectable", r"failed to select the frame DetailItem354"),
        ("other frame", r"selected 1 object\(s\), type 13, name 'DetailItem355'"),
        ("a dimension", r"selected 1 object\(s\), type 14, name ''"),
        ("attached to nothing", r"not attached to its frame DetailItem354 .*count=0"),
        ("attached elsewhere", r"not attached .*attached='DetailItem355'"),
        ("printed elsewhere", r"datum B does not print where it was placed .*\(0\.0015, 0\.198\)"),
        ("not printed", r"datum B does not print where it was placed .*printed \[\]"),
    ),
)
def test_frame_datum_symbol_fails_closed_off_its_frame(
    monkeypatch, case: str, match: str
) -> None:
    frame = _FrameGtol("DetailItem354")
    other = _FrameGtol("DetailItem355")
    kwargs: dict[str, Any] = {}
    if case == "not selectable":
        frame.annotation.selects = False
    elif case == "other frame":
        kwargs["selected"] = (13, other)
    elif case == "a dimension":
        kwargs["selected"] = (14, object())
    elif case == "attached to nothing":
        kwargs["attaches_to"] = None
    elif case == "attached elsewhere":
        kwargs["attaches_to"] = other
    elif case == "printed elsewhere":
        kwargs["prints"] = [("B", (0.0015, 0.198))]
    elif case == "not printed":
        kwargs["prints"] = []
    with pytest.raises(RuntimeError, match=match):
        _frame_datum(monkeypatch, frame, **kwargs)


class _DisplayData:
    def __init__(self, texts: list[str]) -> None:
        self.texts = texts

    def GetTextCount(self) -> int:
        return len(self.texts)

    def GetTextAtIndex(self, index: int) -> str:
        return self.texts[index]


def _translated_frame(
    monkeypatch: pytest.MonkeyPatch, prints: Any, *, accepts: Any = lambda _xml: True
) -> tuple[Any, list[str]]:
    """add_feature_control_frame on a fake seat for the slot frame C|B▷.

    ``prints(xml)`` is the frame's printed text for its current XML;
    ``accepts(xml)`` is SetSymbolXml's answer.  Returns the gtol and every
    XML SOLIDWORKS was handed.
    """
    handed: list[str] = []

    class _XmlFrame:
        xml = ""

        def SetSymbolXml(self, xml: str) -> bool:
            handed.append(xml)
            if accepts(xml):
                self.xml = xml
                return True
            return False

        def GetSymbolXml(self) -> str:
            return self.xml

    frame = _XmlFrame()

    class _Annotation:
        def GetAttachedEntityCount3(self) -> int:
            return 1

        def SetLeader3(self, *_args: Any) -> int:
            return 0

        def SetPosition2(self, *_args: Any) -> bool:
            return True

        def GetDisplayData(self) -> _DisplayData:
            return _DisplayData(prints(frame.xml))

    class _Gtol:
        def GetFrameCount(self) -> int:
            return 1

        def GetFrame(self, _index: int) -> _XmlFrame:
            return frame

        def GetFormat(self) -> int:
            return 2

        def GetAnnotation(self) -> _Annotation:
            return _Annotation()

    gtol = _Gtol()

    class _Draw:
        def InsertGtol(self) -> _Gtol:
            return gtol

        def ClearSelection2(self, _all: bool) -> None:
            pass

    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    monkeypatch.setattr(_drawing_common, "_select_annotation_entity", lambda *_, **__: "rim")
    monkeypatch.setattr(_drawing_common, "rebuild_drawing", lambda *_, **__: None)
    monkeypatch.setattr(_drawing_common, "_assert_attached_to", lambda *_, **__: None)
    _drawing_common.add_feature_control_frame(
        type("_Adapter", (), {"currentModel": _Draw()})(), None,
        edge_xy=(0.1, 0.2), frame_xy=(0.078, 0.218), characteristic="position",
        tolerance="0.05", datums=("C", "B"), translated=("B",),
        label="knife-hanger rear dowel slot position",
    )
    return gtol, handed


_VECTOR = ["<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[0,0,0]"]
_INLINE = ["<GTOL-POSI>", "0.05", "C", "B<MOD-TRANS2>"]


def test_translated_frame_prints_the_inline_glyph_first(monkeypatch) -> None:
    gtol, handed = _translated_frame(
        monkeypatch, lambda xml: _INLINE if "&lt;MOD-TRANS2&gt;" in xml else _VECTOR
    )
    assert [_gtol_form(xml) for xml in handed] == ["inline"]
    assert _gtol_form(gtol.GetFrame(1).GetSymbolXml()) == "inline"


@pytest.mark.parametrize(
    ("accepts", "inline_prints"),
    (
        # SOLIDWORKS refuses the inline letter, or takes it and prints it wrong.
        (lambda xml: "&lt;" not in xml, _INLINE),
        (lambda _xml: True, ["<GTOL-POSI>", "0.05", "C", "B"]),
    ),
)
def test_translated_frame_falls_back_to_the_flag_and_its_zero_vector(
    monkeypatch, accepts: Any, inline_prints: list[str]
) -> None:
    # User ruling: the native flag is the last form, its "[0,0,0]" accepted
    # (farm runs 20261009T174542021Z / 20261009T182549169Z printed it).
    gtol, handed = _translated_frame(
        monkeypatch,
        lambda xml: inline_prints if "&lt;MOD-TRANS2&gt;" in xml else _VECTOR,
        accepts=accepts,
    )
    assert [_gtol_form(xml) for xml in handed] == ["inline", "flag"]
    assert _gtol_form(gtol.GetFrame(1).GetSymbolXml()) == "flag"


def test_translated_frame_fails_closed_when_the_flag_prints_another_vector(
    monkeypatch,
) -> None:
    with pytest.raises(
        RuntimeError,
        match=r"no translation-modifier form prints as ruled .*"
        r"inline: prints 0 translation modifier.*flag: prints a translation vector "
        r"\['\[false,false,false\]'\]",
    ):
        _translated_frame(
            monkeypatch,
            lambda xml: ["<GTOL-POSI>", "0.05", "C", "B"]
            if "&lt;" in xml
            else ["<GTOL-POSI>", "0.05", "C", "B", "<MOD-TRANS2>", "[false,false,false]"],
        )


def _gtol_form(xml: str) -> str:
    if "&lt;MOD-TRANS2&gt;" in xml:
        return "inline"
    if "<Translation>true</Translation>" in xml:
        return "flag"
    return "plain"


def test_every_frame_datum_must_be_printed_on_the_sheet(monkeypatch) -> None:
    # Farm run 20261009T171439353Z: the knife mount printed the tap and bore
    # frames to A|B with no B on the sheet (only the frame's unprinted datum
    # identifier named it).
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    front = _View(("A",), (_FrameGtol("DetailItem355", ("A", "B")),))
    top = _View((), (_FrameGtol("DetailItem356", ("A",)), _FrameGtol("DetailItem358", ("A", "B"))))
    with pytest.raises(
        RuntimeError,
        match=r"reference datum\(s\) no tag prints: B by \['DetailItem355', 'DetailItem358'\]; tags print \['A'\]",
    ):
        _drawing_common.assert_frame_datums_defined((front, top), label="knife mount")
    top.tags = [_DatumTag("B")]
    _drawing_common.assert_frame_datums_defined((front, top), label="knife mount")


@pytest.mark.parametrize(
    ("offset_m", "accepted"),
    (
        # The pinion-bracket pivot-bore finish re-solved 0.61 mm along its edge.
        (0.00061, True),
        # A landing on a neighbouring edge 1.5 mm away passed the old 5 mm bound.
        (0.0015, False),
    ),
    ids=("edge-resolve", "neighbouring-edge"),
)
def test_leader_landing_tolerance_is_one_millimetre(offset_m: float, accepted: bool) -> None:
    requested = (0.2055, 0.1175)
    points = (0.136, 0.106, 0.0, requested[0] + offset_m, requested[1], 0.0)
    check = lambda: _drawing_common._assert_leader_lands(  # noqa: E731
        _Annotation((object(),), (1,), leader_points=points), requested,
        what="surface-finish symbol", label="bore",
    )
    if accepted:
        check()
    else:
        with pytest.raises(RuntimeError, match=r"leader attachment moved \(bore\)"):
            check()


# _part_pmi._resolve_faces: the one raw walk the surface-finish faces come from.
#
# The doubles are raw dispatches, as SolidWorks hands them to the walk: they
# answer ``InvokeTypes`` only and assert the whole (dispid, lcid, flags,
# return type, argument types) header of the SolidWorks 2026 type library
# (flags 1 = method, 2 = property get; 3 = int, 9 = IDispatch, 11 = bool,
# 12 = VARIANT).  A read of a member the walk should not send fails.

GET_FIRST_FACE = (1, 0, 1, (9, 0), ())
GET_NEXT_FACE = (2, 0, 1, (9, 0), ())
GET_SURFACE = (3, 0, 1, (9, 0), ())
GET_BOX = (55, 0, 1, (12, 0), ())
FACE_IN_SURFACE_SENSE = (10, 0, 1, (11, 0), ())
IDENTITY = (9, 0, 1, (3, 0), ())
PARAMETERS = {
    4001: (1, 0, 2, (12, 0), ()),  # PlaneParams
    4002: (2, 0, 2, (12, 0), ()),  # CylinderParams
    4003: (82, 0, 2, (12, 0), ()),  # ConeParams2
    4004: (4, 0, 2, (12, 0), ()),  # SphereParams
    4005: (5, 0, 2, (12, 0), ()),  # TorusParams
}


class _RawDispatch:
    """A bare ``PyIDispatch`` stand-in keyed by dispid; any other header fails."""

    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls: list[tuple[Any, ...]] = []

    def InvokeTypes(self, dispid, lcid, flags, ret_type, arg_types, *args):  # noqa: N802
        header = (dispid, lcid, flags, ret_type, arg_types)
        self.calls.append(header)
        assert dispid in self.answers, f"unexpected dispid {dispid}"
        expected, answer = self.answers[dispid]
        assert header == expected
        return answer(*args) if callable(answer) else answer


_BOX = (-0.01, -0.01, -0.01, 0.01, 0.01, 0.01)


def _raw_face(identity: int, parameters, *, flipped: bool = False) -> _RawDispatch:
    surface = _RawDispatch(
        {
            IDENTITY[0]: (IDENTITY, identity),
            PARAMETERS[identity][0]: (PARAMETERS[identity], parameters),
        }
    )
    face = _RawDispatch(
        {
            GET_SURFACE[0]: (GET_SURFACE, surface),
            GET_BOX[0]: (GET_BOX, _BOX),
            FACE_IN_SURFACE_SENSE[0]: (FACE_IN_SURFACE_SENSE, flipped),
            GET_NEXT_FACE[0]: (GET_NEXT_FACE, lambda: face.following),
        }
    )
    face.surface = surface
    face.identity, face.parameters, face.flipped = identity, parameters, flipped
    face.following = None
    return face


class _Part:
    """The ``IPartDoc`` whose one body's raw face list the walk steps through."""

    def __init__(self, *faces: _RawDispatch) -> None:
        # A returned face is bound through the checked-in makepy wrapper.
        pytest.importorskip("win32com.client")
        for face, following in zip(faces, faces[1:]):
            face.following = following
        self.body = _RawDispatch({GET_FIRST_FACE[0]: (GET_FIRST_FACE, faces[0])})

    def GetBodies2(self, *_args):  # noqa: N802
        return [self.body]


def _faces() -> dict[str, _RawDispatch]:
    return {
        "bore": _raw_face(4002, (0, 0, 0, 0, 0, 1, 0.004)),
        "taper": _raw_face(4003, (0, 0, 0, 1, 0, 0, 0.005, math.radians(30.0), 0, 1, 0)),
        # PlaneParams: normal xyz, root point xyz.  The deck's surface sense
        # is flipped, so its OUTWARD normal is -Z and it sits at -10 mm on it.
        "deck": _raw_face(4001, (0, 0, 1, 0, 0, 0.01), flipped=True),
        "top": _raw_face(4001, (0, 0, 1, 0, 0, 0.02)),
        "rim": _raw_face(4001, (0, 0, 1, 0, 0, 0.02)),
        "ball": _raw_face(4004, (0, 0, 0, 0.003)),
        "torus": _raw_face(4005, (0, 0, 0, 0, 0, 1, 0.01, 0.002)),
    }


_SPECS = {
    "bore": CylinderFace(8.0),
    "taper": ConeFace(30.0),
    "deck": PlanarFace((0.0, 0.0, -1.0), -10.0),
    "ball": SphereFace(6.0),
    "torus": TorusFace(10.0, 2.0),
}


@pytest.mark.parametrize("label", sorted(_SPECS))
def test_each_spec_type_resolves_its_one_raw_face(label: str) -> None:
    faces = _faces()
    resolved = _part_pmi._resolve_faces(_Part(*faces.values()), {label: _SPECS[label]})
    assert resolved[label]._oleobj_ is faces[label]
    # A face of a surface type the spec does not name stops at its identity.
    for name, face in faces.items():
        if face.identity != faces[label].identity:
            assert face.surface.calls == [IDENTITY], name
            assert GET_BOX not in face.calls, name


def test_mixed_spec_types_resolve_in_one_walk() -> None:
    faces = _faces()
    part = _Part(*faces.values())
    resolved = _part_pmi._resolve_faces(part, dict(_SPECS))
    assert {label: face._oleobj_ for label, face in resolved.items()} == {
        label: faces[label] for label in _SPECS
    }
    assert part.body.calls == [GET_FIRST_FACE]
    assert all(face.calls.count(GET_SURFACE) == 1 for face in faces.values())


@pytest.mark.parametrize("label", sorted(_SPECS))
def test_a_twin_face_fails_the_exactly_one_contract(label: str) -> None:
    faces = _faces()
    face = faces[label]
    twin = _raw_face(face.identity, face.parameters, flipped=face.flipped)
    part = _Part(*faces.values(), twin)
    with pytest.raises(RuntimeError, match=f"^{label}: face spec .* matched 2 faces"):
        _part_pmi._resolve_faces(part, {label: _SPECS[label]})


def test_coplanar_faces_still_fail_the_exactly_one_contract() -> None:
    with pytest.raises(RuntimeError, match="matched 2 faces"):
        _part_pmi._resolve_faces(
            _Part(*_faces().values()), {"face": PlanarFace((0.0, 0.0, 1.0), 20.0)}
        )


def test_a_spec_no_face_matches_fails_the_exactly_one_contract() -> None:
    with pytest.raises(RuntimeError, match="matched 0 faces"):
        _part_pmi._resolve_faces(_Part(*_faces().values()), {"bore": CylinderFace(9.0)})
