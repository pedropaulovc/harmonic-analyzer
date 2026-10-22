"""Offline supplier-display contracts, not captured native evidence or COM proof.

The independently seeded display and annotation surfaces deliberately do not share
presentation state with the measured model dimension or its source tolerance.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from types import SimpleNamespace

import pytest

import _supplier_dimensions as supplier
import _supplier_washer_drawing as washer_drawing
import _supplier_washer_model as washer_model


@dataclass(frozen=True)
class _Specification:
    label: str
    value_si: float
    expected_mm: float
    units: str
    unit_code: int
    precision: int
    kind: int
    presentation: str
    prefix: str
    suffix: str
    band_mm: tuple[float, float]
    tolerance_precision: int

    def arguments(self):
        return dict(
            label=self.label, expected_mm=self.expected_mm, units=self.units,
            precision=self.precision, presentation=self.presentation,
        )


# MODEL_THICKNESS is intentionally 0.91 mm, not 0.036 * 25.4 mm.
# These are independent offline inputs, not a claim about saved drawing getters.
_SPECIFICATIONS = (
    _Specification(
        "mg back thickness", 0.00091, 0.91, "in", 3, 3, 11, "length",
        "(", " in)", (0.029 * 25.4, 0.043 * 25.4), 3,
    ),
    # OD uses the source's bilateral band, including its below-nominal limits.
    _Specification(
        "pivot shim OD", 0.01, 10.0, "mm", 0, 2, 6, "diameter",
        "(<MOD-DIAM>", " mm)", (9.53, 9.96), 2,
    ),
)


class _Surface(SimpleNamespace):
    """Record property writes; unexpected API calls fail rather than auto-mock."""

    def __init__(self, calls, **members):
        super().__init__(**members)
        object.__setattr__(self, "_calls", calls)

    def __setattr__(self, name, value):
        self._calls.append((name, value))
        if name not in self.__dict__:
            raise AssertionError(f"Unsupported SDK property: {name}")
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        raise AssertionError(f"Unsupported SDK member: {name}")


@pytest.fixture(params=_SPECIFICATIONS, ids=("inch-thickness", "millimetre-OD"))
def washer_native(request, monkeypatch):
    specification = request.param
    calls = []
    # Only COM interface binding is replaced; all shared measurement,
    # presentation, attachment checks and the strict predicate remain real.
    monkeypatch.setattr(supplier, "_early_bound", lambda obj, _interface: obj)
    owner = object()
    entities = (object(), object())
    minimum = (specification.band_mm[0] - specification.expected_mm) / 1000.0
    maximum = (specification.band_mm[1] - specification.expected_mm) / 1000.0
    tolerance_type = 3 if specification.units == "in" else 2
    tolerance = _Surface(
        calls, Type=tolerance_type,
        GetMinValue=lambda: minimum, GetMaxValue=lambda: maximum,
    )
    native = _Surface(
        calls, SystemValue=specification.value_si, Tolerance=tolerance,
        FullName="D1@SupplierWasherWitness@washer.SLDPRT",
    )
    annotation = _Surface(
        calls, Visible=1, OwnerType=0, Owner=owner,
        IsDangling=lambda: False, GetType=lambda: 4,
        GetAttachedEntities3=lambda: entities,
        GetAttachedEntityCount3=lambda: len(entities),
        GetAttachedEntityTypes=lambda: (11, 11),
    )
    # The saved display is specified independently of any production setter.
    state = SimpleNamespace(
        use_document=False, unit=specification.unit_code, fraction=1,
        denominator=0, rounding=False, decimal_rounding=0,
        precisions=(specification.precision, 4, specification.tolerance_precision, 5),
        override=False,
    )
    text = {1: specification.prefix, 2: specification.suffix, 4: ""}

    def set_units(use_document, unit, fraction, denominator, rounding, decimal_rounding):
        calls.append(("SetUnits2", use_document, unit, fraction, denominator,
                      rounding, decimal_rounding))
        state.use_document, state.unit, state.fraction = use_document, unit, fraction
        state.denominator, state.rounding = denominator, rounding
        state.decimal_rounding = decimal_rounding
        return 0

    def set_precision(primary, dual, primary_tolerance, dual_tolerance):
        calls.append(("SetPrecision3", primary, dual, primary_tolerance, dual_tolerance))
        # swDoNotChangePrecisionSetting=-1 preserves each independent field.
        state.precisions = tuple(
            old if requested == -1 else requested
            for old, requested in zip(
                state.precisions, (primary, dual, primary_tolerance, dual_tolerance)
            )
        )
        return 0

    def set_text(part, value):
        calls.append(("SetText", part, value))
        if part not in (1, 2, 4):
            raise AssertionError("Numeric/all-text replacement is forbidden")
        text[part] = value

    display = _Surface(
        calls, Type2=specification.kind, ShowDimensionValue=True,
        ShowParenthesis=False, GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation, GetOverride=lambda: state.override,
        GetUseDocUnits=lambda: state.use_document, GetUnits=lambda: state.unit,
        GetPrimaryPrecision2=lambda: state.precisions[0],
        GetPrimaryTolPrecision2=lambda: state.precisions[2],
        GetFractionBase=lambda: state.fraction,
        GetFractionValue=lambda: state.denominator,
        GetRoundToFraction=lambda: state.rounding,
        GetText=lambda part: text.get(part, ""),
        SetUnits2=set_units, SetPrecision3=set_precision, SetText=set_text,
    )
    return SimpleNamespace(
        specification=specification, calls=calls, display=display, state=state,
        text=text, native=native, tolerance=tolerance, annotation=annotation,
        owner=owner, entities=entities, original_si=specification.value_si,
        original_band=(tolerance_type, minimum, maximum),
    )


def _assert_source_unchanged(case):
    assert case.native.SystemValue == case.original_si
    assert case.native.Tolerance is case.tolerance
    assert (
        case.tolerance.Type,
        case.tolerance.GetMinValue(),
        case.tolerance.GetMaxValue(),
    ) == case.original_band
    assert case.display.GetDimension2(0) is case.native
    assert case.display.GetAnnotation() is case.annotation
    assert case.annotation.Owner is case.owner
    assert case.annotation.Visible == 1
    assert case.annotation.OwnerType == 0
    assert not case.annotation.IsDangling()
    assert case.annotation.GetAttachedEntityCount3() == len(case.entities)
    assert case.annotation.GetAttachedEntityTypes() == (11, 11)
    for actual, original in zip(case.annotation.GetAttachedEntities3(), case.entities):
        assert actual is original


def _presentation_snapshot(case):
    return (
        deepcopy(vars(case.state)), dict(case.text),
        case.display.ShowParenthesis, case.display.ShowDimensionValue,
    )


def test_saved_washer_presentation_is_accepted_without_writes(washer_native):
    case = washer_native
    before = _presentation_snapshot(case)
    supplier.assert_supplier_reference_dimension(
        None, case.display, **case.specification.arguments()
    )
    assert not case.calls
    assert _presentation_snapshot(case) == before
    _assert_source_unchanged(case)


@pytest.mark.parametrize(
    "corruption",
    ("use-doc-units", "units", "primary-precision", "fraction-base",
     "parentheses", "override", "show-value", "prefix", "suffix", "below-callout"),
)
def test_saved_washer_presentation_refuses_each_field_without_repair(
    washer_native, corruption,
):
    case = washer_native
    if corruption == "use-doc-units":
        case.state.use_document = True
    elif corruption == "units":
        case.state.unit = 0 if case.specification.unit_code == 3 else 3
    elif corruption == "primary-precision":
        case.state.precisions = (7, *case.state.precisions[1:])
    elif corruption == "fraction-base":
        case.state.fraction = 2
    elif corruption == "parentheses":
        case.display.ShowParenthesis = True
    elif corruption == "override":
        case.state.override = True
    elif corruption == "show-value":
        case.display.ShowDimensionValue = False
    else:
        part = {"prefix": 1, "suffix": 2, "below-callout": 4}[corruption]
        case.text[part] = "incorrect persisted text"
    case.calls.clear()  # Fault injection is not a production assertion write.
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="native supplier presentation differs"):
        supplier.assert_supplier_reference_dimension(
            None, case.display, **case.specification.arguments()
        )
    assert not case.calls
    assert _presentation_snapshot(case) == before
    _assert_source_unchanged(case)


def test_dressing_washer_preserves_model_band_value_and_attachments(washer_native):
    case = washer_native
    case.state.use_document = True
    case.state.unit = 4
    case.state.fraction = 2
    case.state.precisions = (7, 4, case.specification.tolerance_precision, 5)
    case.display.ShowParenthesis = True
    case.text.update({1: "old prefix", 2: "old suffix", 4: "old callout"})
    case.calls.clear()
    result = supplier.supplier_reference_dimension(
        None, case.display, **case.specification.arguments()
    )
    # The helper already invokes the real strict predicate; do not echo it here.
    assert result is case.display
    assert vars(case.state) == dict(
        use_document=False, unit=case.specification.unit_code, fraction=1,
        denominator=0, rounding=False, decimal_rounding=0,
        precisions=(case.specification.precision, 4,
                    case.specification.tolerance_precision, 5), override=False,
    )
    assert case.text == {1: case.specification.prefix, 2: case.specification.suffix, 4: ""}
    assert case.display.ShowParenthesis is False
    assert case.display.ShowDimensionValue is True
    assert case.calls == [
        ("SetUnits2", False, case.specification.unit_code, 1, 0, False, 0),
        ("SetPrecision3", case.specification.precision, -1, -1, -1),
        ("ShowParenthesis", False),
        ("SetText", 1, case.specification.prefix),
        ("SetText", 2, case.specification.suffix),
        ("SetText", 4, ""),
    ]
    _assert_source_unchanged(case)


@pytest.fixture
def washer_import(washer_native, monkeypatch):
    """Independent source/import displays share only the measured IDimension."""
    case = washer_native
    source_calls = []
    source_state = SimpleNamespace(
        use_document=False, unit=case.specification.unit_code, fraction=1,
        denominator=0, rounding=False,
        precisions=(case.specification.precision, 4,
                    case.specification.tolerance_precision, 5),
        override=False,
    )
    source_text = {
        1: case.specification.prefix, 2: case.specification.suffix, 4: "",
    }
    source = _Surface(
        source_calls, Type2=case.specification.kind,
        ShowDimensionValue=True, ShowParenthesis=False,
        GetDimension2=lambda _index: case.native,
        GetUseDocUnits=lambda: source_state.use_document,
        GetUnits=lambda: source_state.unit,
        GetFractionBase=lambda: source_state.fraction,
        GetFractionValue=lambda: source_state.denominator,
        GetRoundToFraction=lambda: source_state.rounding,
        GetPrimaryPrecision2=lambda: source_state.precisions[0],
        GetPrimaryTolPrecision2=lambda: source_state.precisions[2],
        GetOverride=lambda: source_state.override,
        GetText=lambda part: source_text.get(part, ""),
    )
    label = (
        washer_model.THICKNESS if case.specification.presentation == "length"
        else washer_model.OUTER_DIAMETER
    )
    feature_name, dimension_name = washer_model.SOURCE_DIMENSIONS[label]
    feature = object()

    def find_feature(name):
        assert name == feature_name
        return feature

    model = _Surface([], FeatureByName=find_feature)
    view = _Surface([], ReferencedDocument=model)
    identity_calls = []

    def same(left, right):
        identity_calls.append((left, right))
        return int(left is right)

    adapter = SimpleNamespace(swApp=_Surface([], IsSame=same))

    def named_dimensions(actual_adapter, actual_feature_name, names, *, feature):
        assert actual_adapter is adapter
        assert actual_feature_name == feature_name
        assert names == {dimension_name}
        assert feature is expected_feature
        return {dimension_name: (source, case.native)}

    expected_feature = feature
    monkeypatch.setattr(washer_drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(washer_model, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(washer_drawing, "_named_dimensions", named_dimensions)
    case.state.use_document = True
    case.state.unit = -1
    case.state.fraction = -1
    case.state.denominator = -1

    def persist():
        washer_drawing._persist_imported_units(
            adapter, view, case.display, label=label,
            units=case.specification.units, precision=case.specification.precision,
            expected_mm=case.specification.expected_mm, callout=None,
        )

    return SimpleNamespace(
        imported=case, source=source, source_state=source_state,
        source_text=source_text, source_calls=source_calls,
        identity_calls=identity_calls, persist=persist, adapter=adapter,
    )


def _nonunit_snapshot(case):
    return (
        case.state.precisions, case.state.override, dict(case.text),
        case.display.ShowParenthesis, case.display.ShowDimensionValue,
    )


def _corrupt_nonunit(display, state, text, corruption):
    if corruption == "precision":
        state.precisions = (7, *state.precisions[1:])
    elif corruption == "tolerance-precision":
        state.precisions = (*state.precisions[:2], 7, state.precisions[3])
    elif corruption == "parentheses":
        display.ShowParenthesis = True
    elif corruption == "override":
        state.override = True
    elif corruption == "show-value":
        display.ShowDimensionValue = False
    else:
        text[{"prefix": 1, "suffix": 2, "below-callout": 4}[corruption]] = "wrong"


@pytest.mark.parametrize("denominator", (0, -1, 64))
def test_import_transfers_only_source_unit_fields(washer_import, denominator):
    pair = washer_import
    case = pair.imported
    # Decimal denominator is not interpreted or fabricated, even for mm.
    pair.source_state.denominator = denominator
    source_before = deepcopy(vars(pair.source_state)), dict(pair.source_text)
    nonunit_before = _nonunit_snapshot(case)
    pair.persist()
    assert case.calls == [
        ("SetUnits2", False, case.specification.unit_code, 1, denominator, False, 0),
    ]
    assert (case.state.use_document, case.state.unit, case.state.fraction,
            case.state.denominator, case.state.rounding) == (
        False, case.specification.unit_code, 1, denominator, False,
    )
    assert _nonunit_snapshot(case) == nonunit_before
    assert (vars(pair.source_state), pair.source_text) == source_before
    assert not pair.source_calls
    assert len(pair.identity_calls) == 1
    assert all(entity is case.native for entity in pair.identity_calls[0])
    _assert_source_unchanged(case)


@pytest.mark.parametrize(
    "corruption",
    ("use-doc-units", "units", "fraction", "precision", "tolerance-precision",
     "parentheses", "override", "show-value", "prefix", "suffix", "below-callout",
     "native-type", "native-value"),
)
def test_bad_source_is_refused_before_import_setter(washer_import, corruption):
    pair = washer_import
    case = pair.imported
    if corruption == "use-doc-units":
        pair.source_state.use_document = True
    elif corruption == "units":
        pair.source_state.unit = -1
    elif corruption == "fraction":
        pair.source_state.fraction = -1
    elif corruption == "native-type":
        pair.source.Type2 = 3
    elif corruption == "native-value":
        foreign = _Surface([], SystemValue=0.123)
        object.__setattr__(pair.source, "GetDimension2", lambda _index: foreign)
    else:
        _corrupt_nonunit(pair.source, pair.source_state, pair.source_text, corruption)
    pair.source_calls.clear()
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="model supplier"):
        pair.persist()
    assert not case.calls
    assert not pair.source_calls
    assert not pair.identity_calls
    assert _presentation_snapshot(case) == before
    _assert_source_unchanged(case)


def test_foreign_import_native_is_refused_before_setter(washer_import):
    pair = washer_import
    case = pair.imported
    # Matching value/name cannot substitute for actual IDimension identity.
    foreign = _Surface(
        [], SystemValue=case.native.SystemValue, FullName=case.native.FullName,
    )
    original_getter = case.display.GetDimension2
    object.__setattr__(case.display, "GetDimension2", lambda _index: foreign)
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="not its native source"):
        pair.persist()
    assert not case.calls
    assert not pair.source_calls
    assert len(pair.identity_calls) == 1
    assert pair.identity_calls[0][0] is foreign
    assert pair.identity_calls[0][1] is case.native
    assert _presentation_snapshot(case) == before
    object.__setattr__(case.display, "GetDimension2", original_getter)
    _assert_source_unchanged(case)


@pytest.mark.parametrize(
    "identity",
    (True, False, 1.0, "1", None, 0, -1),
    ids=("boolean-true", "boolean-false", "float-one", "string-one",
         "unreadable-none", "integer-zero", "integer-minus-one"),
)
def test_import_requires_actual_integer_native_identity(washer_import, identity):
    pair = washer_import
    case = pair.imported

    def malformed_identity(left, right):
        pair.identity_calls.append((left, right))
        return identity

    object.__setattr__(pair.adapter.swApp, "IsSame", malformed_identity)
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="not its native source"):
        pair.persist()
    assert not case.calls
    assert not pair.source_calls
    assert len(pair.identity_calls) == 1
    assert all(entity is case.native for entity in pair.identity_calls[0])
    assert _presentation_snapshot(case) == before
    _assert_source_unchanged(case)


@pytest.mark.parametrize(
    "corruption",
    ("precision", "parentheses", "override", "show-value",
     "prefix", "suffix", "below-callout"),
)
def test_import_nonunit_corruption_is_refused_not_repaired(washer_import, corruption):
    pair = washer_import
    case = pair.imported
    _corrupt_nonunit(case.display, case.state, case.text, corruption)
    case.calls.clear()
    before = _nonunit_snapshot(case)
    with pytest.raises(RuntimeError, match="native supplier presentation differs"):
        pair.persist()
    assert case.calls == [
        ("SetUnits2", False, case.specification.unit_code, 1, 0, False, 0),
    ]
    assert _nonunit_snapshot(case) == before
    assert not pair.source_calls
    _assert_source_unchanged(case)


@pytest.mark.parametrize("status", (-1, 1, True, None, "0"))
def test_import_rejects_unit_setter_error(washer_import, status):
    pair = washer_import
    case = pair.imported

    def reject(*arguments):
        case.calls.append(("SetUnits2", *arguments))
        return status

    object.__setattr__(case.display, "SetUnits2", reject)
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="imported supplier units were rejected"):
        pair.persist()
    assert case.calls == [
        ("SetUnits2", False, case.specification.unit_code, 1, 0, False, 0),
    ]
    assert _presentation_snapshot(case) == before
    assert not pair.source_calls
    _assert_source_unchanged(case)


def test_import_rejects_successful_unit_setter_that_does_not_persist(washer_import):
    pair = washer_import
    case = pair.imported

    def no_op(*arguments):
        case.calls.append(("SetUnits2", *arguments))
        return 0

    object.__setattr__(case.display, "SetUnits2", no_op)
    before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="native supplier presentation differs") as caught:
        pair.persist()
    prefix = "supplier washer source/import readback: "
    notes = [note for note in caught.value.__notes__ if note.startswith(prefix)]
    assert len(notes) == 1
    readback = json.loads(notes[0][len(prefix):])
    assert readback["source"]["units"] == case.specification.unit_code
    assert readback["source"]["use_document_units"] is False
    assert readback["imported"]["units"] == -1
    assert readback["imported"]["fraction_base"] == -1
    assert readback["imported"]["fraction_value"] == -1
    assert readback["imported"]["use_document_units"] is True
    assert case.calls == [
        ("SetUnits2", False, case.specification.unit_code, 1, 0, False, 0),
    ]
    assert _presentation_snapshot(case) == before
    assert not pair.source_calls
    _assert_source_unchanged(case)


@pytest.mark.parametrize("corruption", ("source-units", "source-precision"))
def test_source_refusal_note_reports_actual_source_and_import_fields(
    washer_import, corruption,
):
    pair = washer_import
    case = pair.imported
    if corruption == "source-units":
        pair.source_state.unit = 0 if case.specification.unit_code == 3 else 3
    else:
        pair.source_state.precisions = (7, *pair.source_state.precisions[1:])
    source_before = deepcopy(vars(pair.source_state)), dict(pair.source_text)
    imported_before = _presentation_snapshot(case)
    with pytest.raises(RuntimeError, match="model supplier units/precision/reference ink changed") as caught:
        pair.persist()
    prefix = "supplier washer source/import readback: "
    notes = [note for note in caught.value.__notes__ if note.startswith(prefix)]
    assert len(notes) == 1
    readback = json.loads(notes[0][len(prefix):])
    assert readback["source"]["units"] == pair.source_state.unit
    assert readback["source"]["precision"] == pair.source_state.precisions[0]
    assert readback["source"]["use_document_units"] is False
    assert readback["imported"]["units"] == -1
    assert readback["imported"]["fraction_base"] == -1
    assert readback["imported"]["fraction_value"] == -1
    assert readback["imported"]["precision"] == case.specification.precision
    assert readback["imported"]["use_document_units"] is True
    # Deliberately absent optional getters stay errors, not fabricated values.
    for display_readback in (readback["source"], readback["imported"]):
        assert "read_error" in display_readback["selection_name"]
        assert display_readback["system_value"] == case.original_si
    assert "annotation_read_error" in readback["source"]
    assert not case.calls
    assert not pair.source_calls
    assert not pair.identity_calls
    assert (vars(pair.source_state), pair.source_text) == source_before
    assert _presentation_snapshot(case) == imported_before
    _assert_source_unchanged(case)


@pytest.fixture(params=(washer_model.THICKNESS, washer_model.OUTER_DIAMETER),
                ids=("point-contexts", "circle-contexts"))
def attachment_readback_case(request, monkeypatch):
    """Independent COM-transport doubles, never evidence of native applicability."""
    label = request.param
    writes, bindings, identity_calls, forward_calls, reverse_calls = [], [], [], [], []

    def surface(**members):
        return _Surface(writes, **members)

    def bind(handle, interface):
        bindings.append((handle, interface))
        return handle

    monkeypatch.setattr(washer_drawing, "_early_bound", bind)
    # The implementation may use _com._bind for interface-qualified invocation.
    import _com
    monkeypatch.setattr(_com, "_bind", bind)
    monkeypatch.setattr(washer_drawing, "_bind", bind)
    feature_name, dimension_name = washer_model.SOURCE_DIMENSIONS[label]
    source_sketch = surface()
    sketches = {context: surface() for context in
                ("view", "attachment", "normalized", "roundtrip")}
    sketches["source"] = source_sketch
    contexts = {}
    for context, sketch in sketches.items():
        members = []
        for index in range(3 if label == washer_model.THICKNESS else 2):
            # Same IDs and coordinates in different contexts MUST NOT establish identity.
            point = surface(X=0.005, Y=index * 0.00091, Z=0.0,
                            GetID=lambda index=index: (index, 7),
                            GetSketch=lambda sketch=sketch: sketch)
            if label == washer_model.THICKNESS:
                member = point
            else:
                member = surface(
                    GetID=lambda index=index: (index, 7),
                    GetSketch=lambda sketch=sketch: sketch,
                    GetType=lambda: 1, ConstructionGeometry=True,
                    IsCircle=lambda: 1, GetCenterPoint2=lambda point=point: point,
                    GetRadius=lambda index=index: (0.005, 0.002)[index],
                )
            members.append(member)
        contexts[context] = tuple(members)
        object.__setattr__(sketch, "GetSketchPoints2", lambda members=members: tuple(members))
        object.__setattr__(sketch, "GetSketchSegments", lambda members=members: tuple(members))
    if label == washer_model.THICKNESS:
        line = surface(
            GetID=lambda: (8, 9), GetSketch=lambda: source_sketch,
            GetType=lambda: 0, ConstructionGeometry=True,
            GetStartPoint2=lambda: contexts["source"][0],
            GetEndPoint2=lambda: contexts["source"][1],
        )
        object.__setattr__(source_sketch, "GetSketchSegments", lambda: (line,))
    feature = surface(Name=feature_name, GetTypeName2=lambda: "ProfileFeature",
                      GetSpecificFeature2=lambda: source_sketch)
    imported_owner = surface(Name="IndependentImportedOwner",
                             GetTypeName2=lambda: "IndependentImportedFeature")
    source_native = surface(FullName=f"{dimension_name}@{feature_name}@source.SLDPRT",
                            GetFeatureOwner=lambda: feature)
    imported_native = surface(FullName="DrawingD1@IndependentOwner@drawing.SLDDRW",
                              GetFeatureOwner=lambda: imported_owner)
    kind = 11 if label == washer_model.THICKNESS else 6
    source_display = surface(Type2=kind, GetDimension2=lambda _index: source_native)
    annotation = surface(
        Owner=sketches["attachment"], OwnerType=0, Visible=1,
        GetAttachedEntities3=lambda: contexts["attachment"],
        GetAttachedEntityCount3=lambda: len(contexts["attachment"]),
        GetAttachedEntityTypes=lambda: (11 if label == washer_model.THICKNESS else 10,)
        * len(contexts["attachment"]),
        IsDangling=lambda: False,
    )
    display = surface(Type2=kind, GetDimension2=lambda _index: imported_native,
                      GetAnnotation=lambda: annotation)
    forward_map = {
        id(source_sketch): sketches["view"],
        id(sketches["normalized"]): sketches["roundtrip"],
    }
    reverse_map = {
        id(sketches["view"]): source_sketch,
        id(sketches["attachment"]): sketches["normalized"],
        id(sketches["roundtrip"]): sketches["normalized"],
    }
    mapped_feature, reverse_feature = surface(), surface()
    forward_map[id(feature)] = mapped_feature
    forward_map[id(reverse_feature)] = mapped_feature
    reverse_map[id(mapped_feature)] = reverse_feature
    reverse_map[id(imported_owner)] = reverse_feature
    for index in range(len(contexts["source"])):
        forward_map[id(contexts["source"][index])] = contexts["view"][index]
        forward_map[id(contexts["normalized"][index])] = contexts["roundtrip"][index]
        reverse_map[id(contexts["attachment"][index])] = contexts["normalized"][index]
        reverse_map[id(contexts["view"][index])] = contexts["source"][index]
        reverse_map[id(contexts["roundtrip"][index])] = contexts["normalized"][index]
    part_context = {
        id(handle): handle for handle in
        (source_sketch, sketches["normalized"], feature, reverse_feature,
         *contexts["source"], *contexts["normalized"])
    }
    drawing_context = {
        id(handle): handle for handle in
        (sketches["view"], sketches["attachment"], sketches["roundtrip"],
         mapped_feature, imported_owner,
         *contexts["view"], *contexts["attachment"], *contexts["roundtrip"])
    }
    transport_calls = []

    def forward(handle):
        forward_calls.append(handle)
        transport_calls.append(("forward", handle))
        assert id(handle) in part_context, "IView.GetCorresponding requires PART/ASM context"
        return forward_map.get(id(handle))

    def reverse(handle):
        reverse_calls.append(handle)
        transport_calls.append(("reverse", handle))
        assert id(handle) in drawing_context, "GetCorresponding2 requires DRAWING/ASM context"
        return reverse_map.get(id(handle))

    extension = surface(GetCorresponding2=reverse)
    model = surface(
        GetPathName=lambda: "source.SLDPRT", GetType=lambda: 1,
        ConfigurationManager=surface(ActiveConfiguration=surface(Name="SourceConfig")),
        FeatureByName=lambda name: feature if name == feature_name else None,
        Extension=extension,
    )
    view = surface(
        ReferencedDocument=model, ReferencedConfiguration="ViewConfig",
        GetReferencedModelName=lambda: "view-reference.SLDPRT",
        GetOrientationName=lambda: "*Front", GetCorresponding=forward,
    )
    table = {}

    def same(left, right):
        identity_calls.append((left, right))
        result = table.get((id(left), id(right)), 1 if left is right else 0)
        if isinstance(result, Exception):
            raise result
        return result

    adapter = SimpleNamespace(swApp=surface(IsSame=same))

    object.__setattr__(mapped_feature, "GetSpecificFeature2", lambda: sketches["view"])
    object.__setattr__(imported_owner, "GetSpecificFeature2", lambda: sketches["attachment"])
    object.__setattr__(source_display, "GetNameForSelection", lambda: "actual-source-selection")
    object.__setattr__(display, "GetNameForSelection", lambda: "actual-imported-selection")
    source_annotation = surface(Owner=model, OwnerType=0)
    object.__setattr__(source_display, "GetAnnotation", lambda: source_annotation)
    part_context[id(source_annotation)] = source_annotation
    drawing_context[id(annotation)] = annotation

    def named(actual_adapter, actual_feature_name, names, *, feature):
        assert actual_adapter is adapter
        assert actual_feature_name == feature_name
        assert names == {dimension_name}
        assert feature is expected_feature
        return {dimension_name: (source_display, source_native)}

    expected_feature = feature
    monkeypatch.setattr(washer_drawing, "_named_dimensions", named)
    return SimpleNamespace(
        label=label, adapter=adapter, model=model, view=view, display=display,
        annotation=annotation, source_display=source_display, source_native=source_native,
        imported_native=imported_native, imported_owner=imported_owner, feature=feature,
        source_sketch=source_sketch, sketches=sketches, contexts=contexts,
        writes=writes, bindings=bindings, identity_calls=identity_calls,
        forward_calls=forward_calls, reverse_calls=reverse_calls, table=table,
        forward_map=forward_map, reverse_map=reverse_map,
        part_context=part_context, drawing_context=drawing_context,
        transport_calls=transport_calls, mapped_feature=mapped_feature,
        reverse_feature=reverse_feature,
    )


def _attachment_readback(case):
    result = washer_drawing._source_attachment_failure_readback(
        case.adapter, case.model, case.view, case.display, label=case.label,
    )
    for direction, handle in case.transport_calls:
        registry = case.part_context if direction == "forward" else case.drawing_context
        assert id(handle) in registry, f"{direction} correspondence used wrong document context"
    return result


def _scalar_receipt(value):
    return {"value": value, "python_type": type(value).__name__}


def _handle_receipt(value):
    return {"present": value is not None, "python_type": type(value).__name__}


def test_source_attachment_readback_records_independent_contexts_and_full_matrices(
    attachment_readback_case,
):
    case = attachment_readback_case
    contexts = case.contexts
    # These represent independently seeded transport returns, NOT a successful
    # washer/native correspondence. Equal coordinates/IDs do not choose winners.
    case.table[id(contexts["attachment"][0]), id(contexts["source"][0])] = True
    case.table[id(contexts["attachment"][0]), id(contexts["source"][1])] = -3
    case.table[id(contexts["normalized"][0]), id(contexts["source"][0])] = 7
    case.table[id(contexts["roundtrip"][0]), id(contexts["attachment"][0])] = False
    case.table[id(contexts["view"][0]), id(contexts["view"][1])] = None
    result = _attachment_readback(case)
    assert result["label"] == case.label
    reads = result["reads"]
    expected_reads = {
        "source.path": "source.SLDPRT", "source.type": 1,
        "source.configuration": "SourceConfig", "view.configuration": "ViewConfig",
        "view.source_path": "source.SLDPRT", "view.source_identity": 1,
        "dimension.imported_full_name": case.imported_native.FullName,
        "dimension.source_full_name": case.source_native.FullName,
        "dimension.imported_type2": case.display.Type2,
        "dimension.source_type2": case.source_display.Type2,
        "dimension.source_import_identity": 0,
        "dimension.source_owner_identity": 1,
        "dimension.imported_owner_identity": 0,
        "dimension.imported_view_owner_identity": 0,
        "source.feature_type": "ProfileFeature",
        "annotation.count": len(contexts["attachment"]),
        "annotation.types": case.annotation.GetAttachedEntityTypes(),
        "annotation.dangling": False, "annotation.visible": 1,
    }
    for key, value in expected_reads.items():
        assert reads[key] == _scalar_receipt(value), key
    matrix_contexts = {
        "source_self_distinct": ("source", "source"),
        "view_self_distinct": ("view", "view"),
        "attachment_self_distinct": ("attachment", "attachment"),
        "attachment_source": ("attachment", "source"),
        "attachment_view": ("attachment", "view"),
        "normalized_source": ("normalized", "source"),
        "roundtrip_attachment": ("roundtrip", "attachment"),
    }
    for name, (row_context, column_context) in matrix_contexts.items():
        rows, columns = contexts[row_context], contexts[column_context]
        expected = [[_scalar_receipt(case.table.get(
            (id(left), id(right)), 1 if left is right else 0,
        )) for right in columns] for left in rows]
        assert result["matrices"][name] == expected, name
        for left in rows:
            for right in columns:
                assert any(a is left and b is right for a, b in case.identity_calls)
    for context, members in contexts.items():
        for index, member in enumerate(members):
            prefix = f"{context}.members.{index}"
            assert reads[prefix] == _handle_receipt(member)
            assert reads[f"{prefix}.id"] == _scalar_receipt((index, 7))
            assert reads[f"{prefix}.sketch"] == _handle_receipt(case.sketches[context])
            assert reads[f"{prefix}.sketch_source_identity"] == _scalar_receipt(
                1 if context == "source" else 0,
            )
            assert reads[f"{prefix}.sketch_feature_identity"] == _scalar_receipt(
                1 if context == "source" else 0,
            )
            reversed_sketch = case.sketches[
                "source" if context in {"source", "view"} else "normalized"
            ]
            assert reads[f"{prefix}.sketch_reverse"] == _handle_receipt(reversed_sketch)
            assert reads[f"{prefix}.sketch_reverse_identity"] == _scalar_receipt(
                1 if context in {"source", "view"} else 0,
            )
            if case.label == washer_model.THICKNESS:
                for suffix, value in (("x", 0.005), ("y", index * 0.00091), ("z", 0.0)):
                    assert reads[f"{prefix}.{suffix}"] == _scalar_receipt(value)
            else:
                assert reads[f"{prefix}.type"] == _scalar_receipt(1)
                assert reads[f"{prefix}.construction"] == _scalar_receipt(True)
                assert reads[f"{prefix}.radius"] == _scalar_receipt((0.005, 0.002)[index])
                assert reads[f"{prefix}.is_circle"] == _scalar_receipt(1)
                assert reads[f"{prefix}.center.x"] == _scalar_receipt(0.005)
            assert any(handle is member for handle, interface in case.bindings
                       if interface == ("ISketchPoint" if case.label == washer_model.THICKNESS
                                        else "ISketchSegment"))
    assert all(any(handle is member for handle in case.forward_calls)
               for member in contexts["source"] + contexts["normalized"])
    assert all(any(handle is member for handle in case.reverse_calls)
               for member in contexts["attachment"])
    if case.label == washer_model.THICKNESS:
        # The complete 3-point inventory is not reduced to the line's 2 endpoints.
        assert len(result["matrices"]["source_self_distinct"]) == 3
        assert result["matrices"]["endpoint_source"] == [
            [_scalar_receipt(1), _scalar_receipt(0), _scalar_receipt(0)],
            [_scalar_receipt(0), _scalar_receipt(1), _scalar_receipt(0)],
        ]
        assert reads["source.segments.0.start.x"] == _scalar_receipt(0.005)
        assert reads["source.segments.0.end.y"] == _scalar_receipt(0.00091)
    assert not case.writes
    # Handle references may not leak into the receipt; default=repr is for
    # unexpected scalar transport objects, not an excuse to serialize handles.
    json.dumps(result)


@pytest.mark.parametrize("raw", (0, 1, -1, True, False, None, "1"))
def test_source_attachment_readback_preserves_raw_native_identity_types(
    attachment_readback_case, raw,
):
    case = attachment_readback_case
    for left in case.contexts["attachment"]:
        for right in case.contexts["source"]:
            case.table[id(left), id(right)] = raw
    result = _attachment_readback(case)
    matrix = result["matrices"]["attachment_source"]
    assert matrix == [[_scalar_receipt(raw)] * len(case.contexts["source"])] * len(
        case.contexts["attachment"],
    )
    assert not case.writes


@pytest.mark.parametrize("target, member, field", (
    ("model", "GetPathName", "source.path"),
    ("model", "GetType", "source.type"),
    ("view", "ReferencedConfiguration", "view.configuration"),
    ("view", "GetReferencedModelName", "view.referenced_model_name"),
    ("imported_native", "FullName", "dimension.imported_full_name"),
    ("source_native", "FullName", "dimension.source_full_name"),
    ("display", "Type2", "dimension.imported_type2"),
    ("source_display", "Type2", "dimension.source_type2"),
    ("feature", "GetTypeName2", "source.feature_type"),
    ("annotation", "GetAttachedEntityCount3", "annotation.count"),
    ("annotation", "GetAttachedEntityTypes", "annotation.types"),
    ("annotation", "IsDangling", "annotation.dangling"),
    ("annotation", "Visible", "annotation.visible"),
))
@pytest.mark.parametrize("failure", (False, True), ids=("raw-null", "getter-error"))
def test_source_attachment_readback_isolates_each_original_disjunct_getter(
    attachment_readback_case, target, member, field, failure,
):
    case = attachment_readback_case
    error = ValueError(f"{field}: independently injected getter failure")

    def fail():
        raise error

    surface = getattr(case, target)
    if failure and not member.startswith("Get") and member != "IsDangling":
        class FailingProperty(type(surface)):
            def __getattribute__(self, name):
                if name == member:
                    raise error
                return super().__getattribute__(name)

        object.__setattr__(surface, "__class__", FailingProperty)
    else:
        object.__setattr__(surface, member, fail if failure else (
            (lambda: None) if member.startswith("Get") or member == "IsDangling" else None
        ))
    result = _attachment_readback(case)
    expected = ({"read_error": {"type": "ValueError", "message": str(error)}}
                if failure else _scalar_receipt(None))
    assert result["reads"][field] == expected
    # Independent getters and every matrix still run after a bad scalar read.
    survivor = "annotation.visible" if field != "annotation.visible" else "source.type"
    assert result["reads"][survivor] == _scalar_receipt(1)
    assert result["matrices"]["attachment_source"][0][0] == _scalar_receipt(0)
    assert not case.writes


def test_source_attachment_readback_isolates_native_matrix_entry_errors(attachment_readback_case):
    case = attachment_readback_case
    error = RuntimeError("native IsSame refused just this ordered pair")
    left, right = case.contexts["attachment"][0], case.contexts["source"][0]
    case.table[id(left), id(right)] = error
    result = _attachment_readback(case)
    assert result["matrices"]["attachment_source"][0][0] == {
        "read_error": {"type": "RuntimeError", "message": str(error)},
    }
    assert result["matrices"]["attachment_source"][0][1] == _scalar_receipt(0)
    assert result["matrices"]["source_self_distinct"][0][0] == _scalar_receipt(1)
    assert result["reads"]["annotation.visible"] == _scalar_receipt(1)
    assert not case.writes


@pytest.mark.parametrize("missing", ("native-owner", "source-feature", "attached-member",
                                    "forward-member", "normalized-member"))
def test_source_attachment_readback_keeps_null_handles_separate_from_skips(
    attachment_readback_case, missing,
):
    case = attachment_readback_case
    if missing == "native-owner":
        object.__setattr__(case.imported_native, "GetFeatureOwner", lambda: None)
        handle_key, dependent_key = "dimension.imported_owner", "dimension.imported_owner_identity"
    elif missing == "source-feature":
        object.__setattr__(case.model, "FeatureByName", lambda _name: None)
        handle_key, dependent_key = "source.feature", "source.feature_type"
    elif missing == "attached-member":
        object.__setattr__(case.annotation, "GetAttachedEntities3",
                           lambda: (None, *case.contexts["attachment"][1:]))
        handle_key, dependent_key = "attachment.members.0", "attachment.members.0.id"
    elif missing == "forward-member":
        case.forward_map[id(case.contexts["source"][0])] = None
        handle_key, dependent_key = "view.members.0", "view.members.0.id"
    else:
        case.reverse_map[id(case.contexts["attachment"][0])] = None
        handle_key, dependent_key = "normalized.members.0", "normalized.members.0.id"
    result = _attachment_readback(case)
    assert result["reads"][handle_key] == _handle_receipt(None)
    assert result["reads"][dependent_key] == {"skipped": f"{handle_key} unavailable"}
    assert result["reads"]["annotation.visible"] == _scalar_receipt(1)
    assert not case.writes


@pytest.mark.parametrize("context", ("source", "view", "attachment", "normalized", "roundtrip"))
@pytest.mark.parametrize("getter", ("GetID", "GetSketch"))
def test_source_attachment_readback_isolates_member_context_getter_errors(
    attachment_readback_case, context, getter,
):
    case = attachment_readback_case
    member = case.contexts[context][0]
    error = OSError(f"{context} {getter} transport failure")

    def fail():
        raise error

    object.__setattr__(member, getter, fail)
    result = _attachment_readback(case)
    suffix = "id" if getter == "GetID" else "sketch"
    prefix = f"{context}.members.0"
    assert result["reads"][f"{prefix}.{suffix}"] == {
        "read_error": {"type": "OSError", "message": str(error)},
    }
    assert result["reads"][f"{context}.members.1.id"] == _scalar_receipt((1, 7))
    if getter == "GetSketch":
        assert result["reads"][f"{prefix}.sketch_source_identity"] == {
            "skipped": f"{prefix}.sketch unavailable",
        }
    else:
        assert result["reads"][f"{prefix}.sketch"] == _handle_receipt(case.sketches[context])
    assert result["matrices"]["attachment_source"][0][0] == _scalar_receipt(0)
    assert not case.writes


@pytest.mark.parametrize("native_name, key", (
    ("source_native", "dimension.source_owner"),
    ("imported_native", "dimension.imported_owner"),
))
def test_source_attachment_readback_reports_native_owner_getter_errors(
    attachment_readback_case, native_name, key,
):
    case = attachment_readback_case
    error = RuntimeError("independent native GetFeatureOwner failure")

    def fail():
        raise error

    object.__setattr__(getattr(case, native_name), "GetFeatureOwner", fail)
    result = _attachment_readback(case)
    assert result["reads"][key] == {
        "read_error": {"type": "RuntimeError", "message": str(error)},
    }
    identity_key = key + "_identity"
    assert result["reads"][identity_key] == {"skipped": f"{key} unavailable"}
    assert result["reads"]["dimension.imported_full_name"] == _scalar_receipt(
        case.imported_native.FullName,
    )
    assert result["reads"]["dimension.source_full_name"] == _scalar_receipt(
        case.source_native.FullName,
    )
    assert not case.writes


@pytest.mark.parametrize("context", ("source", "view", "attachment", "normalized", "roundtrip"))
def test_source_attachment_readback_continues_after_geometry_getter_error(
    attachment_readback_case, context,
):
    case = attachment_readback_case
    member = case.contexts[context][0]
    error = ValueError(f"{context} geometry unavailable")
    if case.label == washer_model.THICKNESS:
        class FailingCoordinate(type(member)):
            def __getattribute__(self, name):
                if name == "X":
                    raise error
                return super().__getattribute__(name)

        object.__setattr__(member, "__class__", FailingCoordinate)
        failed_suffix, surviving_suffix, surviving_value = "x", "y", 0.0
    else:
        def fail():
            raise error

        object.__setattr__(member, "GetRadius", fail)
        failed_suffix, surviving_suffix, surviving_value = "radius", "construction", True
    result = _attachment_readback(case)
    prefix = f"{context}.members.0"
    assert result["reads"][f"{prefix}.{failed_suffix}"] == {
        "read_error": {"type": "ValueError", "message": str(error)},
    }
    assert result["reads"][f"{prefix}.{surviving_suffix}"] == _scalar_receipt(surviving_value)
    assert result["reads"][f"{context}.members.1.id"] == _scalar_receipt((1, 7))
    assert not case.writes


@pytest.mark.parametrize("failure", (False, True), ids=("raw-null", "getter-error"))
def test_source_attachment_readback_preserves_actual_source_configuration_read(
    attachment_readback_case, failure,
):
    case = attachment_readback_case
    error = RuntimeError("source active configuration Name getter unavailable")
    configuration = case.model.ConfigurationManager.ActiveConfiguration
    if failure:
        class FailingConfiguration(type(configuration)):
            def __getattribute__(self, name):
                if name == "Name":
                    raise error
                return super().__getattribute__(name)

        object.__setattr__(configuration, "__class__", FailingConfiguration)
    else:
        object.__setattr__(configuration, "Name", None)
    result = _attachment_readback(case)
    expected = ({"read_error": {"type": "RuntimeError", "message": str(error)}}
                if failure else _scalar_receipt(None))
    assert result["reads"]["source.configuration"] == expected
    assert result["reads"]["view.configuration"] == _scalar_receipt("ViewConfig")
    assert result["reads"]["annotation.visible"] == _scalar_receipt(1)
    assert not case.writes


def test_source_attachment_readback_records_dimension_and_sketch_feature_correspondence(
    attachment_readback_case,
):
    case = attachment_readback_case
    reads = _attachment_readback(case)["reads"]
    for key, value in {
        "view.orientation": "*Front", "view.source_type": 1,
        "view.referenced_model_name": "view-reference.SLDPRT",
        "source.feature_name": case.feature.Name,
        "dimension.source_owner_name": case.feature.Name,
        "dimension.source_owner_type": "ProfileFeature",
        "dimension.imported_owner_name": "IndependentImportedOwner",
        "dimension.imported_owner_type": "IndependentImportedFeature",
        "dimension.source_selection_name": "actual-source-selection",
        "dimension.imported_selection_name": "actual-imported-selection",
        "dimension.source_self_identity": 1, "dimension.imported_self_identity": 1,
        "dimension.source_import_identity": 0, "dimension.import_source_identity": 0,
        "dimension.owner_identity": 0,
        "dimension.source_owner_sketch_identity": 1,
        "dimension.imported_owner_sketch_identity": 0,
        "dimension.source_annotation_owner_identity": 1,
        "dimension.imported_view_owner_identity": 0,
        "source.sketch_feature_identity": 1,
        "source.sketch_reverse_identity": 1,
        "source.feature_reverse_identity": 0,
        "source.sketch_view_feature_identity": 1,
        "annotation.owner_type": 0, "annotation.owner_view_identity": 0,
    }.items():
        assert reads[key] == _scalar_receipt(value), key
    assert reads["source.sketch_view"] == _handle_receipt(case.sketches["view"])
    assert reads["source.sketch_reverse"] == _handle_receipt(case.source_sketch)
    assert reads["source.feature_view_sketch"] == _handle_receipt(case.sketches["view"])
    for context in case.contexts:
        prefix = f"{context}.members.0"
        assert reads[f"{prefix}.sketch_mapped_feature_identity"] == _scalar_receipt(
            1 if context == "view" else 0,
        )
    assert not case.writes


@pytest.mark.parametrize("inventory", ("source.members", "attachment.members"))
@pytest.mark.parametrize("failure", (False, True), ids=("raw-null", "getter-error"))
def test_source_attachment_readback_isolates_inventory_getter_failure(
    attachment_readback_case, inventory, failure,
):
    case = attachment_readback_case
    error = RuntimeError(f"{inventory} native inventory unavailable")

    def read():
        if failure:
            raise error
        return None

    if inventory == "source.members":
        owner, getter = case.source_sketch, (
            "GetSketchPoints2" if case.label == washer_model.THICKNESS else "GetSketchSegments"
        )
    else:
        owner, getter = case.annotation, "GetAttachedEntities3"
    object.__setattr__(owner, getter, read)
    result = _attachment_readback(case)
    if inventory == "source.members" and case.label != washer_model.THICKNESS:
        # Circle member inventory depends on the independently read segment array.
        expected = {"skipped": "source.segments unavailable"}
        source_receipt = result["reads"]["source.segments"]
    else:
        expected = ({"read_error": {"type": "RuntimeError", "message": str(error)}}
                    if failure else _handle_receipt(None))
        source_receipt = result["reads"][inventory]
    assert result["reads"][inventory] == expected
    if failure:
        assert source_receipt == {"read_error": {"type": "RuntimeError", "message": str(error)}}
    else:
        assert source_receipt == _handle_receipt(None)
    assert result["matrices"]["attachment_source"] == [[{
        "skipped": f"{inventory} unavailable",
    }]]
    assert result["reads"]["annotation.visible"] == _scalar_receipt(1)
    assert result["reads"]["dimension.imported_full_name"] == _scalar_receipt(
        case.imported_native.FullName,
    )
    assert not case.writes


@pytest.mark.parametrize("direction", ("forward", "reverse"))
def test_source_attachment_readback_isolates_correspondence_getter_error(
    attachment_readback_case, direction,
):
    case = attachment_readback_case
    error = RuntimeError(f"native {direction} correspondence failed for one member")
    if direction == "forward":
        target = case.contexts["source"][0]
        method = case.view.GetCorresponding
        owner, getter, field = case.view, "GetCorresponding", "view.members.0"
    else:
        target = case.contexts["attachment"][0]
        method = case.model.Extension.GetCorresponding2
        owner, getter, field = case.model.Extension, "GetCorresponding2", "normalized.members.0"

    def correspondence(handle):
        if handle is target:
            raise error
        return method(handle)

    object.__setattr__(owner, getter, correspondence)
    result = _attachment_readback(case)
    assert result["reads"][field] == {
        "read_error": {"type": "RuntimeError", "message": str(error)},
    }
    assert result["reads"][f"{field}.id"] == {"skipped": f"{field} unavailable"}
    assert result["reads"][field.rsplit(".", 1)[0] + ".1.id"] == _scalar_receipt((1, 7))
    assert result["matrices"]["source_self_distinct"][0][0] == _scalar_receipt(1)
    assert result["reads"]["annotation.visible"] == _scalar_receipt(1)
    assert not case.writes


@pytest.mark.parametrize("kind", (None, True, "11", 1, 0))
def test_source_attachment_readback_does_not_bind_non_sketch_attachment_as_sketch(
    attachment_readback_case, kind,
):
    case = attachment_readback_case
    object.__setattr__(case.annotation, "GetAttachedEntityTypes",
                       lambda: (kind,) * len(case.contexts["attachment"]))
    result = _attachment_readback(case)
    assert result["reads"]["attachment.members.0.attached_type"] == _scalar_receipt(kind)
    reason = ("attachment.members.0.attached_type unavailable" if kind is None else
              "attachment.members.0.attached_type does not identify an available sketch interface")
    for context in ("attachment", "normalized", "roundtrip"):
        prefix = f"{context}.members.0"
        for suffix in ("id", "sketch", "sketch_source_identity", "geometry"):
            assert result["reads"][f"{prefix}.{suffix}"] == {"skipped": reason}
        for member in case.contexts[context]:
            assert not any(handle is member for handle, _interface in case.bindings)
    # An unknown kind never suppresses the actual native identity comparisons.
    assert result["matrices"]["attachment_source"][0][0] == _scalar_receipt(0)
    assert result["matrices"]["attachment_self_distinct"][0][0] == _scalar_receipt(1)
    assert result["reads"]["source.members.0.id"] == _scalar_receipt((0, 7))
    assert not case.writes


def test_source_attachment_readback_binds_external_sketch_attachment_by_actual_kind(
    attachment_readback_case,
):
    case = attachment_readback_case
    kind = 25 if case.label == washer_model.THICKNESS else 24
    interface = "ISketchPoint" if case.label == washer_model.THICKNESS else "ISketchSegment"
    object.__setattr__(case.annotation, "GetAttachedEntityTypes",
                       lambda: (kind,) * len(case.contexts["attachment"]))
    result = _attachment_readback(case)
    assert result["reads"]["attachment.members.0.attached_type"] == _scalar_receipt(kind)
    for context in ("attachment", "normalized", "roundtrip"):
        for index, member in enumerate(case.contexts[context]):
            assert result["reads"][f"{context}.members.{index}.id"] == _scalar_receipt((index, 7))
            assert any(handle is member and actual_interface == interface
                       for handle, actual_interface in case.bindings)
    assert not case.writes


@pytest.mark.parametrize("raw", (0, 1, True, False, None, -4))
def test_source_attachment_readback_compares_imported_feature_owner_to_mapped_source_feature(
    attachment_readback_case, raw,
):
    case = attachment_readback_case
    mapped_source_feature = case.forward_map[id(case.feature)]
    case.table[id(case.imported_owner), id(mapped_source_feature)] = raw
    # Annotation owning-view identity is a separate receipt with separate operands.
    object.__setattr__(case.annotation, "Owner", case.view)
    reads = _attachment_readback(case)["reads"]
    assert reads["dimension.imported_view_owner_identity"] == _scalar_receipt(raw)
    assert reads["annotation.owner_view_identity"] == _scalar_receipt(1)
    assert reads["dimension.imported_owner_identity"] == _scalar_receipt(0)
    assert any(left is case.imported_owner and right is mapped_source_feature
               for left, right in case.identity_calls)
    assert not case.writes


def _typed_attachment_transport(case, monkeypatch):
    """Model interface binding as distinct transport wrappers, not native proof."""
    bound_by_raw_id, calls = {}, []

    def clone(raw):
        if id(raw) not in bound_by_raw_id:
            bound_by_raw_id[id(raw)] = _Surface(
                case.writes, **{key: value for key, value in vars(raw).items() if key != "_calls"},
            )
        return bound_by_raw_id[id(raw)]

    for members in case.contexts.values():
        for raw in members:
            clone(raw)
    for raw in (*case.sketches.values(), case.feature, case.imported_owner,
                case.source_native, case.imported_native, case.model, case.view,
                case.model.Extension, case.display, case.source_display,
                case.annotation, case.source_display.GetAnnotation(),
                case.forward_map[id(case.feature)]):
        clone(raw)
    for registry in (case.part_context, case.drawing_context):
        originals = tuple(registry.values())
        for raw in originals:
            bound = clone(raw)
            registry[id(bound)] = bound
    for raw_id, mapped in tuple(case.forward_map.items()):
        if raw_id in bound_by_raw_id:
            case.forward_map[id(bound_by_raw_id[raw_id])] = mapped
    for raw_id, mapped in tuple(case.reverse_map.items()):
        if raw_id in bound_by_raw_id:
            case.reverse_map[id(bound_by_raw_id[raw_id])] = mapped

    def bind(raw, interface):
        result = bound_by_raw_id.get(id(raw), raw)
        calls.append((raw, interface, result))
        return result

    import _com
    monkeypatch.setattr(_com, "_bind", bind)
    monkeypatch.setattr(washer_drawing, "_bind", bind)
    feature_name, dimension_name = washer_model.SOURCE_DIMENSIONS[case.label]

    def named(adapter, actual_name, names, *, feature):
        assert adapter is case.adapter
        assert actual_name == feature_name
        assert names == {dimension_name}
        assert feature is case.feature or feature is bound_by_raw_id[id(case.feature)]
        return {dimension_name: (case.source_display, case.source_native)}

    monkeypatch.setattr(washer_drawing, "_named_dimensions", named)
    return SimpleNamespace(
        by_raw_id=bound_by_raw_id, calls=calls,
        contexts={context: tuple(bound_by_raw_id[id(raw)] for raw in members)
                  for context, members in case.contexts.items()},
    )


def test_source_attachment_readback_keeps_raw_and_typed_transport_chains_separate(
    attachment_readback_case, monkeypatch,
):
    case = attachment_readback_case
    typed = _typed_attachment_transport(case, monkeypatch)
    interface = "ISketchPoint" if case.label == washer_model.THICKNESS else "ISketchSegment"
    typed_contexts = typed.contexts
    case.table[id(typed_contexts["attachment"][0]), id(typed_contexts["source"][0])] = True
    case.table[id(typed_contexts["normalized"][0]), id(typed_contexts["source"][0])] = -8
    case.table[id(typed_contexts["roundtrip"][0]), id(typed_contexts["attachment"][0])] = None
    result = _attachment_readback(case)
    matrix_contexts = {
        "source_self_distinct": ("source", "source"),
        "view_self_distinct": ("view", "view"),
        "attachment_self_distinct": ("attachment", "attachment"),
        "attachment_source": ("attachment", "source"),
        "attachment_view": ("attachment", "view"),
        "normalized_source": ("normalized", "source"),
        "roundtrip_attachment": ("roundtrip", "attachment"),
    }
    for name, (row_context, column_context) in matrix_contexts.items():
        for prefix, contexts in (("", case.contexts), ("typed_", typed_contexts)):
            rows, columns = contexts[row_context], contexts[column_context]
            assert result["matrices"][prefix + name] == [
                [_scalar_receipt(case.table.get(
                    (id(left), id(right)), 1 if left is right else 0,
                )) for right in columns] for left in rows
            ]
            for left in rows:
                for right in columns:
                    assert any(a is left and b is right for a, b in case.identity_calls)
    for context, members in typed_contexts.items():
        for index, bound in enumerate(members):
            raw = case.contexts[context][index]
            assert bound is not raw
            assert result["reads"][f"typed.{context}.members.{index}"] == _handle_receipt(bound)
            assert result["reads"][f"typed.{context}.members.{index}.id"] == _scalar_receipt((index, 7))
            assert any(actual is raw and actual_interface == interface and converted is bound
                       for actual, actual_interface, converted in typed.calls)
    for context, calls in (("source", case.forward_calls), ("normalized", case.forward_calls),
                           ("attachment", case.reverse_calls)):
        assert all(any(actual is bound for actual in calls) for bound in typed_contexts[context])
    assert not case.writes


@pytest.mark.parametrize("failure", (False, True), ids=("bound-null", "binding-error"))
def test_source_attachment_readback_keeps_binding_failure_out_of_raw_context(
    attachment_readback_case, monkeypatch, failure,
):
    case = attachment_readback_case
    _typed_attachment_transport(case, monkeypatch)
    original_bind = washer_drawing._bind
    target = case.contexts["source"][0]
    error = RuntimeError("independently injected interface binding failure")

    def bind(raw, interface):
        if raw is target:
            if failure:
                raise error
            return None
        return original_bind(raw, interface)

    monkeypatch.setattr(washer_drawing, "_bind", bind)
    result = _attachment_readback(case)
    key = "typed.source.members.0"
    assert result["reads"][key] == (
        {"read_error": {"type": "RuntimeError", "message": str(error)}}
        if failure else _handle_receipt(None)
    )
    assert result["matrices"]["typed_source_self_distinct"][0][0] == {
        "skipped": f"{key} unavailable",
    }
    assert result["reads"]["source.members.0.id"] == _scalar_receipt((0, 7))
    assert result["matrices"]["source_self_distinct"][0][0] == _scalar_receipt(1)
    assert result["reads"]["typed.source.members.1.id"] == _scalar_receipt((1, 7))
    assert not case.writes


@pytest.mark.parametrize("raw", (True, None, -5))
def test_source_attachment_readback_records_bound_dimension_owner_operands(
    attachment_readback_case, monkeypatch, raw,
):
    case = attachment_readback_case
    typed = _typed_attachment_transport(case, monkeypatch)
    source_native = typed.by_raw_id[id(case.source_native)]
    imported_native = typed.by_raw_id[id(case.imported_native)]
    source_feature = typed.by_raw_id[id(case.feature)]
    imported_owner = typed.by_raw_id[id(case.imported_owner)]
    raw_mapped_feature = case.forward_map[id(case.feature)]
    mapped_feature = typed.by_raw_id[id(raw_mapped_feature)]
    case.table[id(source_native), id(imported_native)] = raw
    case.table[id(imported_owner), id(mapped_feature)] = raw
    reads = _attachment_readback(case)["reads"]
    assert reads["typed.dimension.source_import_identity"] == _scalar_receipt(raw)
    assert reads["typed.dimension.imported_view_owner_identity"] == _scalar_receipt(raw)
    assert reads["typed.dimension.import_source_identity"] == _scalar_receipt(0)
    assert reads["typed.dimension.source_self_identity"] == _scalar_receipt(1)
    assert reads["typed.dimension.imported_self_identity"] == _scalar_receipt(1)
    assert reads["typed.dimension.source_owner_identity"] == _scalar_receipt(1)
    assert reads["typed.dimension.imported_owner_identity"] == _scalar_receipt(0)
    assert reads["typed.dimension.owner_identity"] == _scalar_receipt(0)
    assert reads["dimension.source_import_identity"] == _scalar_receipt(0)
    assert reads["dimension.imported_view_owner_identity"] == _scalar_receipt(0)
    for left, right in ((source_native, imported_native), (imported_owner, mapped_feature),
                        (source_feature, source_feature), (imported_owner, source_feature)):
        assert any(a is left and b is right for a, b in case.identity_calls)
    for original, interface, bound in (
        (case.source_native, "IDimension", source_native),
        (case.imported_native, "IDimension", imported_native),
        (case.feature, "IFeature", source_feature),
        (case.imported_owner, "IFeature", imported_owner),
    ):
        assert any(actual is original and actual_interface == interface and converted is bound
                   for actual, actual_interface, converted in typed.calls)
    assert not case.writes


@pytest.mark.parametrize("inventory", ("source", "attachment"))
def test_source_attachment_readback_reacquires_typed_inventory_after_raw_getter_error(
    attachment_readback_case, monkeypatch, inventory,
):
    case = attachment_readback_case
    typed = _typed_attachment_transport(case, monkeypatch)
    error = RuntimeError(f"raw-only {inventory} array getter failed")

    def fail():
        raise error

    if inventory == "source":
        owner, getter = case.source_sketch, (
            "GetSketchPoints2" if case.label == washer_model.THICKNESS else "GetSketchSegments"
        )
        failed_key = "source.members" if case.label == washer_model.THICKNESS else "source.segments"
    else:
        owner, getter, failed_key = case.annotation, "GetAttachedEntities3", "attachment.members"
    object.__setattr__(owner, getter, fail)
    result = _attachment_readback(case)
    assert result["reads"][failed_key] == {
        "read_error": {"type": "RuntimeError", "message": str(error)},
    }
    assert result["matrices"]["attachment_source"] == [[{
        "skipped": f"{inventory}.members unavailable",
    }]]
    assert result["reads"][f"typed.{inventory}.members.0.id"] == _scalar_receipt((0, 7))
    matrix = result["matrices"]["typed_attachment_source"]
    assert len(matrix) == len(typed.contexts["attachment"])
    assert all(len(row) == len(typed.contexts["source"]) for row in matrix)
    assert matrix[0][0] == _scalar_receipt(0)
    assert not case.writes


def _annotation_attachment_transport(case, monkeypatch):
    """Seed annotation correspondence separately from sketch or dimension mapping."""
    source_annotation = case.source_display.GetAnnotation()
    mapped_native = _Surface(case.writes, FullName=case.imported_native.FullName)
    reverse_native = _Surface(case.writes, FullName=case.source_native.FullName)
    mapped_display = _Surface(case.writes, GetDimension2=lambda _index: mapped_native)
    reverse_display = _Surface(case.writes, GetDimension2=lambda _index: reverse_native)
    mapped_annotation = _Surface(
        case.writes, GetType=lambda: 4, GetSpecificAnnotation=lambda: mapped_display,
    )
    reverse_annotation = _Surface(
        case.writes, GetType=lambda: 4, GetSpecificAnnotation=lambda: reverse_display,
    )
    object.__setattr__(source_annotation, "GetType", lambda: 4)
    object.__setattr__(source_annotation, "GetSpecificAnnotation", lambda: case.source_display)
    object.__setattr__(case.annotation, "GetType", lambda: 4)
    object.__setattr__(case.annotation, "GetSpecificAnnotation", lambda: case.display)
    case.forward_map[id(source_annotation)] = mapped_annotation
    case.reverse_map[id(case.annotation)] = reverse_annotation
    case.part_context.update({id(source_annotation): source_annotation,
                              id(reverse_annotation): reverse_annotation})
    case.drawing_context.update({id(case.annotation): case.annotation,
                                 id(mapped_annotation): mapped_annotation})
    typed = _typed_attachment_transport(case, monkeypatch)
    for raw in (mapped_annotation, reverse_annotation, mapped_display, reverse_display,
                mapped_native, reverse_native):
        if id(raw) not in typed.by_raw_id:
            typed.by_raw_id[id(raw)] = _Surface(
                case.writes, **{key: value for key, value in vars(raw).items() if key != "_calls"},
            )
    return SimpleNamespace(
        source=source_annotation, imported=case.annotation,
        forward=mapped_annotation, reverse=reverse_annotation,
        forward_display=mapped_display, reverse_display=reverse_display,
        forward_native=mapped_native, reverse_native=reverse_native, typed=typed,
    )


@pytest.mark.parametrize("raw", (True, 0, None, -12))
def test_source_attachment_readback_records_raw_and_bound_annotation_bridges(
    attachment_readback_case, monkeypatch, raw,
):
    case = attachment_readback_case
    annotations = _annotation_attachment_transport(case, monkeypatch)
    typed = annotations.typed.by_raw_id
    pairs = (
        (annotations.forward, annotations.imported, "source_forward_identity"),
        (annotations.reverse, annotations.source, "imported_reverse_identity"),
        (annotations.forward_display, case.display, "source_forward_display_identity"),
        (annotations.reverse_display, case.source_display, "imported_reverse_display_identity"),
        (annotations.forward_native, case.imported_native, "source_forward_native_identity"),
        (annotations.reverse_native, case.source_native, "imported_reverse_native_identity"),
    )
    for left, right, _key in pairs:
        case.table[id(left), id(right)] = raw
        case.table[id(typed[id(left)]), id(typed[id(right)])] = -21
    reads = _attachment_readback(case)["reads"]
    for left, right, key in pairs:
        assert reads[f"annotation.{key}"] == _scalar_receipt(raw)
        assert reads[f"typed.annotation.{key}"] == _scalar_receipt(-21)
        assert any(a is left and b is right for a, b in case.identity_calls)
        assert any(a is typed[id(left)] and b is typed[id(right)]
                   for a, b in case.identity_calls)
    for prefix, handles in (
        ("annotation", {
            "source_forward": annotations.forward, "imported_reverse": annotations.reverse,
            "source_forward_display": annotations.forward_display,
            "imported_reverse_display": annotations.reverse_display,
            "source_forward_native": annotations.forward_native,
            "imported_reverse_native": annotations.reverse_native,
        }),
        ("typed.annotation", {
            "source_forward": typed[id(annotations.forward)],
            "imported_reverse": typed[id(annotations.reverse)],
            "source_forward_display": typed[id(annotations.forward_display)],
            "imported_reverse_display": typed[id(annotations.reverse_display)],
            "source_forward_native": typed[id(annotations.forward_native)],
            "imported_reverse_native": typed[id(annotations.reverse_native)],
        }),
    ):
        for key, handle in handles.items():
            assert reads[f"{prefix}.{key}"] == _handle_receipt(handle)
        for direction in ("source_forward", "imported_reverse"):
            assert reads[f"{prefix}.{direction}_type"] == _scalar_receipt(4)
        assert reads[f"{prefix}.source_forward_native_full_name"] == _scalar_receipt(
            case.imported_native.FullName,
        )
        assert reads[f"{prefix}.imported_reverse_native_full_name"] == _scalar_receipt(
            case.source_native.FullName,
        )
    assert any(handle is annotations.source for handle in case.forward_calls)
    assert any(handle is typed[id(annotations.source)] for handle in case.forward_calls)
    assert any(handle is annotations.imported for handle in case.reverse_calls)
    assert any(handle is typed[id(annotations.imported)] for handle in case.reverse_calls)
    assert not case.writes
    for native in (case.source_native, case.imported_native,
                   typed[id(case.source_native)], typed[id(case.imported_native)]):
        assert not any(handle is native for handle in case.forward_calls + case.reverse_calls)


@pytest.mark.parametrize("kind", (None, True, 4.0, "4", 5, "getter-error"))
def test_source_attachment_readback_requires_actual_display_annotation_type_for_bridge(
    attachment_readback_case, monkeypatch, kind,
):
    case = attachment_readback_case
    annotations = _annotation_attachment_transport(case, monkeypatch)
    error = RuntimeError("mapped annotation GetType unavailable")

    def get_type():
        if kind == "getter-error":
            raise error
        return kind

    def forbidden():
        raise AssertionError("non-display annotation must not use GetSpecificAnnotation")

    object.__setattr__(annotations.forward, "GetType", get_type)
    object.__setattr__(annotations.forward, "GetSpecificAnnotation", forbidden)
    reads = _attachment_readback(case)["reads"]
    assert reads["annotation.source_forward_type"] == (
        {"read_error": {"type": "RuntimeError", "message": str(error)}}
        if kind == "getter-error" else _scalar_receipt(kind)
    )
    for suffix in ("display", "native", "native_full_name", "display_identity", "native_identity"):
        receipt = reads[f"annotation.source_forward_{suffix}"]
        assert set(receipt) == {"skipped"}
        assert receipt["skipped"]
    # Type/bridge failure does not erase annotation correspondence or the
    # independently reacquired bound annotation chain.
    assert reads["annotation.source_forward_identity"] == _scalar_receipt(0)
    assert reads["typed.annotation.source_forward_type"] == _scalar_receipt(4)
    assert reads["typed.annotation.source_forward_native_identity"] == _scalar_receipt(0)
    assert reads["annotation.imported_reverse_type"] == _scalar_receipt(4)
    assert not case.writes


@pytest.mark.parametrize("direction", ("source_forward", "imported_reverse"))
@pytest.mark.parametrize("stage", ("specific", "native"))
@pytest.mark.parametrize("failure", (False, True), ids=("raw-null", "getter-error"))
def test_source_attachment_readback_isolates_annotation_bridge_getter_failures(
    attachment_readback_case, monkeypatch, direction, stage, failure,
):
    case = attachment_readback_case
    annotations = _annotation_attachment_transport(case, monkeypatch)
    forward = direction == "source_forward"
    annotation = annotations.forward if forward else annotations.reverse
    display = annotations.forward_display if forward else annotations.reverse_display
    error = RuntimeError(f"{direction} {stage} getter failed")

    def fail(*_args):
        if failure:
            raise error
        return None

    if stage == "specific":
        owner, getter, suffix = annotation, "GetSpecificAnnotation", "display"
    else:
        owner, getter, suffix = display, "GetDimension2", "native"
    object.__setattr__(owner, getter, fail)
    reads = _attachment_readback(case)["reads"]
    key = f"annotation.{direction}_{suffix}"
    assert reads[key] == (
        {"read_error": {"type": "RuntimeError", "message": str(error)}}
        if failure else _handle_receipt(None)
    )
    assert reads[f"annotation.{direction}_type"] == _scalar_receipt(4)
    assert reads[f"annotation.{direction}_identity"] == _scalar_receipt(0)
    assert set(reads[f"annotation.{direction}_native_full_name"]) == {"skipped"}
    assert reads[f"typed.annotation.{direction}_native_identity"] == _scalar_receipt(0)
    assert not case.writes


@pytest.mark.parametrize("typed", (False, True), ids=("raw-contexts", "bound-contexts"))
def test_source_attachment_readback_orders_correspondence_by_document_context(
    attachment_readback_case, monkeypatch, typed,
):
    case = attachment_readback_case
    transport = _typed_attachment_transport(case, monkeypatch) if typed else None

    def actual(handle):
        return transport.by_raw_id[id(handle)] if typed else handle

    reads = _attachment_readback(case)["reads"]
    prefix = "typed." if typed else ""

    def ordered(first_direction, first_handle, second_direction, second_handle):
        assert any(
            direction == first_direction and handle is first_handle
            and next_direction == second_direction and next_handle is second_handle
            for (direction, handle), (next_direction, next_handle)
            in zip(case.transport_calls, case.transport_calls[1:])
        ), (first_direction, second_direction)

    for context in ("source", "view", "attachment", "normalized", "roundtrip"):
        owning_sketch = case.sketches[context]
        if context in {"source", "normalized"}:
            view_sketch = case.forward_map[id(owning_sketch)]
            source_sketch = case.reverse_map[id(view_sketch)]
            ordered("forward", actual(owning_sketch), "reverse", actual(view_sketch))
        else:
            source_sketch = case.reverse_map[id(owning_sketch)]
            view_sketch = case.forward_map[id(source_sketch)]
            ordered("reverse", actual(owning_sketch), "forward", actual(source_sketch))
        key = f"{prefix}{context}.members.0"
        assert reads[f"{key}.sketch_view"] == _handle_receipt(actual(view_sketch))
        assert reads[f"{key}.sketch_reverse"] == _handle_receipt(actual(source_sketch))
        assert reads[f"{key}.sketch_view_identity"] == _scalar_receipt(
            1 if context in {"source", "view"} else 0,
        )
        assert reads[f"{key}.sketch_reverse_identity"] == _scalar_receipt(
            1 if context in {"source", "view"} else 0,
        )
    ordered("forward", actual(case.feature), "reverse", actual(case.mapped_feature))
    ordered("reverse", actual(case.imported_owner), "forward", actual(case.reverse_feature))
    for owner in ("source", "imported"):
        key = f"{prefix}dimension.{owner}_owner"
        assert reads[f"{key}_view"] == _handle_receipt(actual(case.mapped_feature))
        assert reads[f"{key}_reverse"] == _handle_receipt(actual(case.reverse_feature))
        assert reads[f"{key}_reverse_identity"] == _scalar_receipt(0)
    assert not case.writes


@pytest.mark.parametrize("typed", (False, True), ids=("raw-contexts", "bound-contexts"))
def test_source_attachment_readback_fixture_rejects_undocumented_correspondence_contexts(
    attachment_readback_case, monkeypatch, typed,
):
    case = attachment_readback_case
    transport = _typed_attachment_transport(case, monkeypatch) if typed else None

    def actual(handle):
        return transport.by_raw_id[id(handle)] if typed else handle

    for handle in (case.sketches["view"], case.sketches["attachment"],
                   case.sketches["roundtrip"], case.imported_owner, case.mapped_feature):
        with pytest.raises(AssertionError, match="requires PART/ASM context"):
            case.view.GetCorresponding(actual(handle))
    for handle in (case.source_sketch, case.sketches["normalized"],
                   case.feature, case.reverse_feature):
        with pytest.raises(AssertionError, match="requires DRAWING/ASM context"):
            case.model.Extension.GetCorresponding2(actual(handle))
    assert not case.writes


@pytest.mark.parametrize("typed", (False, True), ids=("raw-contexts", "bound-contexts"))
@pytest.mark.parametrize("path", ("source-sketch", "view-sketch", "normalized-sketch",
                                  "source-owner", "imported-owner"))
def test_source_attachment_readback_skips_second_hop_after_context_mapping_null(
    attachment_readback_case, monkeypatch, typed, path,
):
    case = attachment_readback_case
    transport = _typed_attachment_transport(case, monkeypatch) if typed else None
    prefix = "typed." if typed else ""
    if path.endswith("sketch"):
        context = path.removesuffix("-sketch")
        target = case.sketches[context]
        first = "sketch_reverse" if context == "view" else "sketch_view"
        second = "sketch_view" if context == "view" else "sketch_reverse"
        key = f"{prefix}{context}.members.0."
        mapping = case.reverse_map if context == "view" else case.forward_map
    else:
        context = "source" if path == "source-owner" else "imported"
        target = case.feature if context == "source" else case.imported_owner
        first = "view" if context == "source" else "reverse"
        second = "reverse" if context == "source" else "view"
        key = f"{prefix}dimension.{context}_owner_"
        mapping = case.forward_map if context == "source" else case.reverse_map
    actual_target = transport.by_raw_id[id(target)] if typed else target
    mapping[id(actual_target)] = None
    reads = _attachment_readback(case)["reads"]
    assert reads[key + first] == _handle_receipt(None)
    assert set(reads[key + second]) == {"skipped"}
    assert not any(handle is None for _direction, handle in case.transport_calls)
    assert not case.writes
