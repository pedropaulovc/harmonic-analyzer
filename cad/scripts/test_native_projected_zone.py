from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import _native_projected_zone as native
from _gtol_spec import CylinderFace, GeometricControl


# Independent installed-schema oracle; neither native readback nor expectations
# are manufactured by calling the production XML writer.
_XML = (
    "<GtolFrame><ToleranceSymbol>GTOL-PERP</ToleranceSymbol>"
    "<ToleranceRangeInfo><PrimaryToleranceValue>0.010</PrimaryToleranceValue>"
    "<PrimaryRangeSymbol>phi</PrimaryRangeSymbol></ToleranceRangeInfo>"
    "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
    "<Projection>31.3</Projection></FeatureInfo></GtolFrame>"
)


def _control() -> GeometricControl:
    return GeometricControl(
        "axis", "perpendicularity", "0.010", CylinderFace(5.0),
        tolerance_zone="diametral", projected_zone_height_mm=31.3,
    )


class _UserUnit:
    # The generated maps define these as properties, not methods.
    UnitType: Any = 0
    SpecificUnitType: Any = 3

    def __init__(self) -> None:
        self.factor: Any = 39.37007874015748
        self.full_name: Any = "inch"
        self.name_arguments: list[bool] = []

    def GetConversionFactor(self) -> float:  # noqa: N802
        return self.factor

    def GetFullUnitName(self, plural: bool) -> str:  # noqa: N802
        self.name_arguments.append(plural)
        return self.full_name


class _Frame:
    def __init__(self, xml: Any = _XML) -> None:
        self.xml = xml
        self.reads = 0

    def GetSymbolXml(self) -> str:  # noqa: N802
        self.reads += 1
        return self.xml


class _Gtol:
    # No legacy PTZ API or SetSymbolXml: the reader cannot change a bad frame.
    def __init__(self, xml: Any = _XML) -> None:
        self.frame: _Frame | None = _Frame(xml)
        self.format: Any = 2
        self.count: Any = 1

    def GetFormat(self) -> int:  # noqa: N802
        return self.format

    def GetFrameCount(self) -> int:  # noqa: N802
        return self.count

    def GetFrame(self, index: int) -> _Frame | None:  # noqa: N802
        assert index == 1
        return self.frame


class _Annotation:
    def __init__(self, gtol: Any, name: str | None = None) -> None:
        self.gtol = gtol
        self.name: Any = name if name is not None else _control().annotation_name
        self.type: Any = 5

    def GetName(self) -> str:  # noqa: N802
        return self.name

    def GetType(self) -> int:  # noqa: N802
        return self.type

    def GetSpecificAnnotation(self) -> Any:  # noqa: N802
        return self.gtol


class _Extension:
    def __init__(self, document: _Document) -> None:
        self.document = document
        self.reload_result: Any = 0
        self.reload_calls: list[tuple[Any, ...]] = []
        self.on_reload = lambda: None

    def GetAnnotations(self) -> Any:  # noqa: N802
        return self.document.annotations

    def ReloadOrReplace(  # noqa: N802
        self, read_only: bool, replace_file_name: str, discard_changes: bool,
        force_reload: bool,
    ) -> int:
        self.reload_calls.append((read_only, replace_file_name, discard_changes, force_reload))
        if type(self.reload_result) is int and self.reload_result == 0:
            self.on_reload()
        return self.reload_result


class _Document:
    def __init__(self, path: str, document_type: int = 1, xml: Any = _XML) -> None:
        self.path: Any = path
        self.type: Any = document_type
        self.title: Any = Path(path).name or "Unsaved Part"
        self.unit: Any = _UserUnit()
        self.unit_requests: list[int] = []
        self.dirty: Any = False
        self.gtol = _Gtol(xml)
        self.annotations: Any = (_Annotation(self.gtol),)
        self.Extension = _Extension(self)
        self.views: Any = ((SimpleNamespace(
            GetName2=lambda: "Sheet1", GetAnnotations=lambda: (),
        ), SimpleNamespace(
            GetName2=lambda: "Front", GetAnnotations=lambda: self.annotations,
        )),)

    def GetType(self) -> int:  # noqa: N802
        return self.type

    def GetTitle(self) -> str:  # noqa: N802
        return self.title

    def GetPathName(self) -> str:  # noqa: N802
        return self.path

    def GetUserUnit(self, unit_type: int) -> _UserUnit:  # noqa: N802
        self.unit_requests.append(unit_type)
        return self.unit

    def GetSaveFlag(self) -> bool:  # noqa: N802
        return self.dirty

    def GetViews(self) -> Any:  # noqa: N802
        return self.views


class _App:
    def __init__(self, path: str, saved: _Document, current: _Document | None = None) -> None:
        self.path = path
        self.saved = saved
        self.opened = current
        self.specification = SimpleNamespace(
            DocumentType=0, ReadOnly=False, Silent=False, Error=0, Warning=0,
        )
        self.open_calls = 0
        self.close_calls: list[str] = []
        self.return_none = False
        self.open_exception: Exception | None = None
        self.close_refused = False

    def GetOpenDocumentByName(self, path: str) -> Any:  # noqa: N802
        assert path == self.path
        return self.opened

    def GetOpenDocSpec(self, path: str) -> Any:  # noqa: N802
        assert path == self.path
        return self.specification

    def OpenDoc7(self, specification: Any) -> Any:  # noqa: N802
        assert specification is self.specification
        assert specification.DocumentType == self.saved.type
        assert specification.ReadOnly is True
        assert specification.Silent is True
        self.open_calls += 1
        self.opened = self.saved
        if self.open_exception is not None:
            raise self.open_exception
        return None if self.return_none else self.saved

    def CloseDoc(self, title: str) -> None:  # noqa: N802
        assert self.opened is not None
        assert title == self.opened.title
        self.close_calls.append(title)
        if not self.close_refused:
            self.opened = None
        return None  # Generated VT_VOID; checking its truthiness would fail.


@pytest.fixture
def native_seams(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(native, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(native._telemetry, "event", lambda name, **fields: events.append((name, fields)))
    return events


def _capture(document: _Document) -> dict[str, Any]:
    return native.capture_projected_gtol(
        document, document.gtol, expected_xml=_XML, key="axis", phase="authored",
        migrated=True,
    )


def _saved_state(tmp_path: Path, *, drawing: bool = False, already_open: bool = False) -> SimpleNamespace:
    path = tmp_path / ("saved.SLDDRW" if drawing else "saved.SLDPRT")
    path.write_bytes(b"source-only fake file; no native runtime")
    path_string = str(path.resolve())
    saved = _Document(path_string, 3 if drawing else 1)
    current = _Document(path_string, saved.type) if already_open else None
    app = _App(path_string, saved, current)
    adapter = SimpleNamespace(swApp=app, currentModel=current)
    if current is not None:
        current.Extension.on_reload = lambda: setattr(app, "opened", saved)
    return SimpleNamespace(path=path, saved=saved, current=current, app=app, adapter=adapter)


def _audit(state: SimpleNamespace) -> tuple[dict[str, Any], ...]:
    return native.require_saved_projected_gtols(
        state.adapter, state.path, (_control(),), label="saved axis",
    )


def test_capture_records_exact_xml_raw_units_without_physical_pass(native_seams: Any) -> None:
    document = _Document("")
    native_xml = _XML.replace("0.010", ".010").replace(">31.3<", ">31.3000<")
    document.gtol.frame.xml = native_xml
    receipt = _capture(document)
    assert receipt["expected_xml"] == _XML
    assert receipt["applied_xml"] == native_xml
    assert receipt["requested_projected_zone_height_mm"] == 31.3
    assert receipt["readback_projected_zone_height_xml_numeric"] == 31.3
    assert receipt["xml_semantics_match"] is True
    assert receipt["migrated"] is True
    assert receipt["physical_projection_unit_qualification"] == "UNQUALIFIED"
    assert receipt["physical_projection_unit_verified"] is False
    assert receipt["length_conversion_factor_raw"] == document.unit.factor
    assert receipt["length_specific_unit_type_raw"] == 3
    assert receipt["length_specific_unit_enum"] == "swINCHES"
    assert receipt["length_unit_full_name_raw"] == "inch"
    assert document.unit_requests == [0]
    assert document.unit.name_arguments == [False]
    assert native_seams[-1] == ("native.projected_zone_readback", receipt)


@pytest.mark.parametrize("xml", (
    _XML.replace(">31.3<", ">39.2375<"),
    _XML.replace("<FeatureInfo>", "<Unused>").replace("</FeatureInfo>", "</Unused>"),
    _XML.replace("GTOL-PERP", "GTOL-POSI"),
    _XML.replace("<PrimaryRangeSymbol>phi</PrimaryRangeSymbol>", ""),
    _XML.replace("0.010", "0.020"),
))
def test_capture_refuses_semantic_loss_and_records_authentic_wrong_xml(
    native_seams: Any, xml: str,
) -> None:
    document = _Document("", xml=xml)
    with pytest.raises(RuntimeError, match="invalid projected frame XML|did not persist source semantics"):
        _capture(document)
    event, fields = native_seams[-1]
    assert event == "native.projected_zone_readback"
    assert fields["applied_xml"] == xml
    assert fields["expected_xml"] == _XML
    assert fields["xml_semantics_match"] is False
    assert fields["physical_projection_unit_verified"] is False


@pytest.mark.parametrize("readback", (None, True, 31.3, "method"))
def test_capture_bstr_guard_rejects_nonstring_return(native_seams: Any, readback: Any) -> None:
    document = _Document("")
    document.gtol.frame.xml = document.gtol.frame.GetSymbolXml if readback == "method" else readback
    with pytest.raises(RuntimeError, match="XML readback is not a string"):
        _capture(document)


@pytest.mark.parametrize("readback", ("", "<GtolFrame>"))
def test_capture_rejects_empty_or_malformed_bstr(native_seams: Any, readback: str) -> None:
    document = _Document("", xml=readback)
    with pytest.raises(RuntimeError, match="invalid projected frame XML readback"):
        _capture(document)


@pytest.mark.parametrize("field,value,message", (
    ("format", 1, "not current format"),
    ("format", True, "not an integer"),
    ("count", 0, "exactly one frame"),
    ("count", 2, "exactly one frame"),
    ("count", True, "not an integer"),
    ("frame", None, "current frame is unavailable"),
))
def test_capture_requires_exact_native_current_frame_shape(
    native_seams: Any, field: str, value: Any, message: str,
) -> None:
    document = _Document("")
    setattr(document.gtol, field, value)
    with pytest.raises(RuntimeError, match=message):
        _capture(document)


@pytest.mark.parametrize("factor", (None, True, 0, -1, float("nan"), float("inf")))
def test_capture_refuses_missing_or_invalid_unit_scale(native_seams: Any, factor: Any) -> None:
    document = _Document("")
    document.unit.factor = factor
    with pytest.raises(RuntimeError, match="conversion factor is not finite positive"):
        _capture(document)


@pytest.mark.parametrize("field,value,message", (
    ("UnitType", 1, "non-length unit"),
    ("UnitType", False, "not an integer"),
    ("SpecificUnitType", 99, "unknown native length unit"),
    ("SpecificUnitType", lambda: 0, "not an integer"),
    ("full_name", None, "length unit name.*not a nonempty string"),
    ("full_name", "", "length unit name.*not a nonempty string"),
))
def test_capture_uses_real_unit_property_shapes_failclosed(
    native_seams: Any, field: str, value: Any, message: str,
) -> None:
    document = _Document("")
    setattr(document.unit, field, value)
    with pytest.raises(RuntimeError, match=message):
        _capture(document)


def test_capture_missing_native_unit_is_not_a_fake_mm_default(native_seams: Any) -> None:
    document = _Document("")
    document.unit = None
    with pytest.raises(RuntimeError, match="length unit is unavailable"):
        _capture(document)


def test_capture_refuses_ordinary_source_before_native_getters(native_seams: Any) -> None:
    ordinary = _XML.replace(
        "<FeatureInfo><ProjectedToleranceZone>true</ProjectedToleranceZone>"
        "<Projection>31.3</Projection></FeatureInfo>", "",
    )
    with pytest.raises(ValueError, match="requires a projected source control"):
        native.capture_projected_gtol(
            object(), object(), expected_xml=ordinary, key="ordinary", phase="authored",
        )


def test_saved_part_force_reloads_same_file_without_discard_and_reads_fresh_handles(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    result = _audit(state)
    assert state.current.Extension.reload_calls == [(False, str(state.path.resolve()), False, True)]
    assert state.app.open_calls == 0
    assert state.app.close_calls == []
    assert state.adapter.currentModel is state.saved
    assert state.current.gtol.frame.reads == 1
    assert state.saved.gtol.frame.reads == 1
    assert result[0]["phase"] == "after_saved_reload"
    assert result[0]["migrated"] is None
    assert result[0]["document_path"] == str(state.path.resolve())
    assert result[0]["physical_projection_unit_verified"] is False
    phases = [fields["phase"] for name, fields in native_seams if name == "native.projected_zone_readback"]
    assert phases == ["before_saved_reload", "after_saved_reload"]


@pytest.mark.parametrize("dirty", (True, None, 1, object()))
def test_saved_part_refuses_dirty_or_nonbool_state_without_reload_or_close(
    tmp_path: Path, native_seams: Any, dirty: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.current.dirty = dirty
    with pytest.raises(RuntimeError, match="refuse to discard dirty or unreadable"):
        _audit(state)
    assert state.current.Extension.reload_calls == []
    assert state.app.close_calls == []
    assert state.app.opened is state.current


@pytest.mark.parametrize("status", (3, 14, True, False, None, 0.0))
def test_saved_part_checks_exact_reload_integer_status(
    tmp_path: Path, native_seams: Any, status: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.current.Extension.reload_result = status
    message = "reload failed" if type(status) is int else "not an integer"
    with pytest.raises(RuntimeError, match=message):
        _audit(state)
    assert state.saved.gtol.frame.reads == 0


def test_saved_part_wrong_document_refuses_before_reload(tmp_path: Path, native_seams: Any) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.current.path = str(tmp_path / "other.SLDPRT")
    with pytest.raises(RuntimeError, match="acquired the wrong document"):
        _audit(state)
    assert state.current.Extension.reload_calls == []


def test_saved_part_projection_loss_uses_reacquired_annotation_not_old_handle(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.saved.gtol.frame.xml = _XML.replace(">31.3<", ">1<")
    with pytest.raises(RuntimeError, match="did not persist source semantics"):
        _audit(state)
    assert state.current.gtol.frame.xml == _XML
    assert state.saved.gtol.frame.reads == 1
    assert native_seams[-1][1]["applied_xml"] == state.saved.gtol.frame.xml


def test_saved_part_unit_context_change_refuses_even_when_xml_matches(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.saved.unit.SpecificUnitType = 0
    state.saved.unit.factor = 1000.0
    state.saved.unit.full_name = "millimeter"
    with pytest.raises(RuntimeError, match="document units changed across saved reload"):
        _audit(state)
    assert state.saved.gtol.frame.xml == state.current.gtol.frame.xml


def test_saved_part_requires_successful_reacquisition(tmp_path: Path, native_seams: Any) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.current.Extension.on_reload = lambda: setattr(state.app, "opened", None)
    with pytest.raises(RuntimeError, match="not reacquired after reload"):
        _audit(state)


@pytest.mark.parametrize("drawing", (False, True))
def test_closed_saved_native_document_opens_readonly_and_closes_void_return(
    tmp_path: Path, native_seams: Any, drawing: bool,
) -> None:
    state = _saved_state(tmp_path, drawing=drawing)
    result = _audit(state)
    assert state.app.open_calls == 1
    assert state.app.close_calls == [state.saved.title]
    assert state.app.opened is None
    assert result[0]["phase"] == "after_saved_reopen"
    assert result[0]["migrated"] is None
    assert result[0]["annotation_name"] == _control().annotation_name
    assert result[0]["view_name"] == ("Front" if drawing else "")
    assert result[0]["physical_projection_unit_qualification"] == "UNQUALIFIED"
    assert state.adapter.currentModel is None


@pytest.mark.parametrize("failure", ("xml", "unit", "error", "error_type", "none", "exception"))
def test_closed_native_audit_closes_loaded_target_on_all_read_or_open_failures(
    tmp_path: Path, native_seams: Any, failure: str,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    if failure == "xml":
        state.saved.gtol.frame.xml = _XML.replace(">31.3<", ">1<")
        message = "did not persist source semantics"
    elif failure == "unit":
        state.saved.unit.factor = None
        message = "conversion factor is not finite positive"
    elif failure == "error":
        state.app.specification.Error = 1
        message = "saved native open failed"
    elif failure == "error_type":
        state.app.specification.Error = False
        message = "not an integer"
    elif failure == "none":
        state.app.return_none = True
        message = "saved native open failed"
    else:
        state.app.open_exception = RuntimeError("OpenDoc7 failed after loading")
        message = "OpenDoc7 failed after loading"
    with pytest.raises(RuntimeError, match=message):
        _audit(state)
    assert state.app.close_calls == [state.saved.title]
    assert state.app.opened is None


def test_native_close_requires_actual_closed_readback(tmp_path: Path, native_seams: Any) -> None:
    state = _saved_state(tmp_path, drawing=True)
    state.app.close_refused = True
    with pytest.raises(RuntimeError, match="saved audit document did not close"):
        _audit(state)
    assert state.app.close_calls == [state.saved.title]


def test_saved_drawing_refuses_pre_finalize_open_state(tmp_path: Path, native_seams: Any) -> None:
    state = _saved_state(tmp_path, drawing=True, already_open=True)
    with pytest.raises(RuntimeError, match="finalize and close the drawing"):
        _audit(state)
    assert state.app.open_calls == 0
    assert state.app.close_calls == []


@pytest.mark.parametrize("failure", ("missing", "duplicate", "wrongtype", "no_gtol", "nonarray"))
def test_saved_named_annotation_contracts_refuse_and_close(
    tmp_path: Path, native_seams: Any, failure: str,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    annotation = state.saved.annotations[0]
    if failure == "missing":
        state.saved.annotations = ()
        message = "missing saved projected annotations"
    elif failure == "duplicate":
        state.saved.annotations = (annotation, _Annotation(_Gtol()))
        message = "duplicate saved projected annotation"
    elif failure == "wrongtype":
        annotation.type = 6
        message = "is not a GTol"
    elif failure == "no_gtol":
        annotation.gtol = None
        message = "has no GTol"
    else:
        state.saved.annotations = "not a native annotation array"
        message = "native array readback is not an array"
    with pytest.raises(RuntimeError, match=message):
        _audit(state)
    assert state.app.opened is None
    assert state.app.close_calls == [state.saved.title]


def test_saved_drawing_enumerates_every_sheet_not_only_active_view(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    first = SimpleNamespace(GetName2=lambda: "Sheet1", GetAnnotations=lambda: ())
    second = SimpleNamespace(GetName2=lambda: "RearSheet", GetAnnotations=lambda: ())
    feature = SimpleNamespace(GetName2=lambda: "Rear", GetAnnotations=lambda: state.saved.annotations)
    state.saved.views = ((first,), (second, feature))
    result = _audit(state)
    assert result[0]["view_name"] == "Rear"
    assert state.app.opened is None


def test_saved_reader_requires_projected_existing_file_without_native_work(
    tmp_path: Path, native_seams: Any,
) -> None:
    ordinary = GeometricControl("axis", "perpendicularity", "0.010", CylinderFace(5.0))
    with pytest.raises(ValueError, match="requires projected controls"):
        native.require_saved_projected_gtols(object(), tmp_path / "missing.SLDPRT", (ordinary,), label="ordinary")
    with pytest.raises(ValueError, match="existing SLDPRT or SLDDRW"):
        native.require_saved_projected_gtols(object(), tmp_path / "missing.SLDPRT", (_control(),), label="missing")


def test_saved_reload_reacquired_wrong_document_refuses(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, already_open=True)
    state.saved.path = str(tmp_path / "wrong.SLDPRT")
    with pytest.raises(RuntimeError, match="acquired the wrong document"):
        _audit(state)
    assert state.saved.gtol.frame.reads == 0


def test_closed_audit_never_closes_wrong_identity_lookup(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    state.saved.path = str(tmp_path / "other.SLDDRW")
    with pytest.raises(RuntimeError, match="acquired the wrong document"):
        _audit(state)
    assert state.app.close_calls == []
    assert state.app.opened is state.saved


def test_closed_audit_missing_open_spec_has_no_open_or_close(
    tmp_path: Path, native_seams: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    monkeypatch.setattr(state.app, "GetOpenDocSpec", lambda _path: None)
    with pytest.raises(RuntimeError, match="open specification is unavailable"):
        _audit(state)
    assert state.app.open_calls == 0
    assert state.app.close_calls == []


def test_saved_reader_duplicate_source_identity_refuses_before_native_work(
    tmp_path: Path, native_seams: Any,
) -> None:
    with pytest.raises(ValueError, match="duplicate projected control annotation names"):
        native.require_saved_projected_gtols(
            object(), tmp_path / "missing.SLDPRT", (_control(), _control()), label="duplicates",
        )


def test_saved_drawing_refuses_unnamed_direct_helper_frame(
    tmp_path: Path, native_seams: Any,
) -> None:
    state = _saved_state(tmp_path, drawing=True)
    state.saved.annotations[0].name = "GTol1"
    with pytest.raises(RuntimeError, match="missing saved projected annotations"):
        _audit(state)
    assert state.app.close_calls == [state.saved.title]
    assert state.app.opened is None
