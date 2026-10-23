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


@pytest.mark.parametrize("transport", (
    "source-readback-runtime", "source-readback-interrupt",
    "imported-readback-runtime", "imported-readback-interrupt",
    "json-runtime", "json-interrupt", "note-runtime", "note-interrupt",
))
def test_import_primary_identity_getter_failure_survives_secondary_transport(
    washer_import, monkeypatch, transport,
):
    pair = washer_import
    case = pair.imported
    attempts = []
    secondary = (KeyboardInterrupt if transport.endswith("interrupt") else RuntimeError)(
        "secondary source/import failure transport"
    )

    class Primary(RuntimeError):
        def add_note(self, note):
            attempts.append("note")
            if transport.startswith("note-"):
                raise secondary
            super().add_note(note)

    primary = Primary("actual imported native identity getter failed")

    def identity(*_args):
        attempts.append("IsSame")
        raise primary

    # Execute the real source-presentation guard and fail the real independent
    # native identity read, before any imported-unit setter can run.
    object.__setattr__(pair.adapter.swApp, "IsSame", identity)
    actual_readback = washer_drawing._saved_display_readback

    def readback(display):
        role = "source" if display is pair.source else "imported"
        attempts.append(role + "-readback")
        if transport.startswith(role + "-readback-"):
            raise secondary
        return actual_readback(display)

    monkeypatch.setattr(washer_drawing, "_saved_display_readback", readback)
    if transport.startswith("json-"):
        def serialize(*_args, **_kwargs):
            attempts.append("json")
            raise secondary
        monkeypatch.setattr(washer_drawing, "json", SimpleNamespace(dumps=serialize))
    before = _presentation_snapshot(case)
    source_before = deepcopy(vars(pair.source_state)), dict(pair.source_text)
    with pytest.raises(Primary) as caught:
        pair.persist()
    assert caught.value is primary
    assert attempts.count("IsSame") == 1
    assert attempts.count("source-readback") == 1
    assert attempts.count("imported-readback") == int(not transport.startswith("source-readback-"))
    if transport.startswith("json-"):
        assert attempts.count("json") == 1 and "note" not in attempts
    elif transport.startswith("note-"):
        assert attempts.count("note") == 1
    assert not case.calls and not pair.source_calls
    assert _presentation_snapshot(case) == before
    assert (vars(pair.source_state), pair.source_text) == source_before
    _assert_source_unchanged(case)
