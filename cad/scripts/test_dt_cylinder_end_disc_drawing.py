"""Offline contracts for the south cylinder-bank end disc (MHA-DT-26) drawing."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import dt_cylinder_end_disc_spec as spec
import draw_dt_cylinder_end_disc as drawing


def test_loose_thickness_is_compensated_without_moving_the_gear_datum() -> None:
    import cylinder_bank_layout as bank
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(spec.THICKNESS_PLACES)
    assert spec.WASHER_THICK_TOLERANCE_MM == band
    assert spec.WASHER_THICK - band >= 2.0 - 1e-9
    assert bank.DATUM_CHAIN_STACK["south disc, mic-compensated"] == bank.MIC_RESIDUAL
    assert bank.MIC_RESIDUAL < band
    assert bank.FRONT_STRAP_INNER_Z + spec.WASHER_THICK == pytest.approx(
        bank.G0_CAM_FACE_Z
    )


def test_drilled_bore_limits_clear_the_arbor() -> None:
    import dt_cylinder_gear_shaft_spec as arbor
    from _printed_drilled_tolerance import drilled_oversize_mm

    assert spec.WASHER_BORE_BAND == (drilled_oversize_mm(), 0.0)
    assert spec.WASHER_BORE > arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0]


def test_disc_has_running_air_and_continuous_ring_capture_at_the_worst_limits() -> None:
    import cylinder_bank_layout as bank
    import ch_connecting_rod_spec as rod
    import dt_cylinder_gear_spec as gear

    budget = bank.SOUTH_DISC_CLEARANCE
    for name in ("cone worst", "engaged pinion worst"):
        assert budget[name] > spec.RUNNING_AIR_MM + spec.CLEARANCE_SPARE_MM
    # The whole bore edge remains captured, although the outermost ring rim
    # extends beyond this disc. Full-rim coverage is not axial retention.
    assert spec.WASHER_OD / 2.0 < gear.ECCENTRICITY + rod.RING_OUTER_RADIUS
    assert budget["retaining land"] > 0.0


def test_gear_od_disc_fails_the_real_drive_envelope(monkeypatch) -> None:
    import cylinder_bank_layout as bank
    import dt_cylinder_gear_spec as gear

    monkeypatch.setattr(spec, "WASHER_OD", gear.OUTSIDE_DIA)
    with pytest.raises(AssertionError, match="south retaining disc cone worst"):
        spec.installed_clearance_budget(sum(bank.DATUM_CHAIN_STACK.values()))


def test_disc_envelope_books_the_actual_south_datum_band_once() -> None:
    import cone_line
    import cylinder_bank_layout as bank

    datum = sum(bank.DATUM_CHAIN_STACK.values())
    normal = spec.installed_clearance_budget(datum)
    shifted = spec.installed_clearance_budget(datum + 0.10)
    assert normal["cone worst"] - shifted["cone worst"] == pytest.approx(
        0.10 * cone_line.SIN_I
    )
    assert shifted["engaged pinion worst"] == normal["engaged pinion worst"]
    assert shifted["retaining land"] == normal["retaining land"]


@pytest.mark.parametrize("north", [(0.0, 0.0), (0.0, 0.01), (0.01, 0.01)])
def test_axial_section_rejects_a_nonhorizontal_or_degenerate_axis(
    monkeypatch, north
) -> None:
    monkeypatch.setattr(
        drawing, "model_points_in_view", lambda *_args, **_kwargs: ((0.0, 0.0), north)
    )
    with pytest.raises(RuntimeError, match="horizontal turning axis"):
        drawing._require_horizontal_axis(object(), object())


@pytest.fixture
def disc_sheet(monkeypatch, tmp_path):
    """Native text compartments and values survive the real callout boundary."""
    source = tmp_path / "disc.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    state = SimpleNamespace(exported=False)
    native_sizes = {
        "DiscDia": spec.WASHER_OD / 1000.0,
        "BoreDia": spec.WASHER_BORE / 1000.0,
        "DiscThick": spec.WASHER_THICK / 1000.0,
    }

    class Display:
        def __init__(self, name):
            self.dimension = SimpleNamespace(Name=name, SystemValue=native_sizes[name])
            self.precision = spec.DRAWING_PRECISION_BY_NAME[name]
            self.ShowDimensionValue = True
            # The part builder authors no callouts; the fresh drawing starts
            # with empty above/below compartments.
            self.text = {
                1: "" if name == "DiscThick" else "<MOD-DIAM>",
                2: "",
                3: "",
                4: "",
            }
            self.fault = None

        def GetDimension(self):
            return self.dimension

        def GetPrimaryPrecision2(self):
            return self.precision

        def SetText(self, part, text):
            if self.fault and self.fault.part == part and self.fault.kind != "read":
                self.fault.triggered = True
                if self.fault.kind == "write":
                    raise RuntimeError("native callout write failed")
                if self.fault.kind == "ineffective":
                    return
                if self.fault.kind == "partial":
                    self.text[part] = text[:-1]
                    return
                if self.fault.kind == "wrong_compartment":
                    self.text[7 - part] = text
                    return
            if part == 0:
                # Documented native whole-text replacement is NOT a callout:
                # it hides the associative value and replaces its prefix.
                self.text = {1: text, 2: "", 3: "", 4: ""}
                self.ShowDimensionValue = False
            else:
                if part not in self.text:
                    raise ValueError("unsupported native text compartment")
                self.text[part] = text

        def GetText(self, part):
            if self.fault and self.fault.part == part and self.fault.kind == "read":
                self.fault.triggered = True
                raise RuntimeError("native callout read failed")
            return self.text[part]

    class Annotation:
        def __init__(self, name):
            self.display = Display(name)

        def GetSpecificAnnotation(self):
            return self.display

    def attempt(operation):
        # Model the real adapter's swallowing behavior: production must not
        # use this boundary for the required callout write or readback.
        try:
            return operation()
        except RuntimeError:
            return None

    async def open_model(_path):
        return None

    async def finalize(*_args, **_kwargs):
        state.exported = True
        return {}

    adapter = SimpleNamespace(
        currentModel=object(),
        open_model=open_model,
        _attempt=attempt,
        _get_attr_or_call=lambda obj, name: getattr(obj, name),
    )
    monkeypatch.setattr(
        drawing._sw_type_info,
        "early_bound_or_flag",
        lambda obj, *_args: obj,
    )
    monkeypatch.setattr(drawing, "check", lambda *_args: None)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *_args, **_kwargs: (object(), object())
    )
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args: None)
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(drawing, "create_section_view", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        drawing,
        "model_points_in_view",
        lambda *_args, **_kwargs: ((0.0, 0.0), (0.01, 0.0)),
    )
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    state.annotations = [
        Annotation("DiscDia"),
        Annotation("BoreDia"),
        Annotation("DiscThick"),
    ]
    state.displays = {
        annotation.display.GetDimension().Name: annotation.display
        for annotation in state.annotations
    }
    state.original = {
        name: (
            display.GetDimension(),
            display.GetDimension().SystemValue,
            display.GetPrimaryPrecision2(),
            display.GetText(1),
            display.GetText(2),
        )
        for name, display in state.displays.items()
    }
    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda *_args, **_kwargs: state.annotations,
    )
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    state.adapter = adapter
    return state


def test_callout_layout_preserves_native_sizes_and_precision(disc_sheet) -> None:
    # Exercise _set_required_callouts through build, including the real
    # read-only imported-precision check and the export boundary.
    asyncio.run(drawing.build(disc_sheet.adapter))

    assert disc_sheet.exported
    thickness = disc_sheet.displays["DiscThick"]
    bore = disc_sheet.displays["BoreDia"]
    assert thickness.GetText(3) == spec.THICKNESS_CALLOUT.replace("\n", " ")
    assert thickness.GetText(4) == ""
    assert bore.GetText(3) == ""
    assert bore.GetText(4) == spec.BORE_CALLOUT
    for name, display in disc_sheet.displays.items():
        dimension, size, precision, prefix, suffix = disc_sheet.original[name]
        assert display.GetDimension() is dimension
        assert display.GetDimension().SystemValue == size
        assert display.GetPrimaryPrecision2() == precision
        assert display.ShowDimensionValue
        assert display.GetText(1) == prefix
        assert display.GetText(2) == suffix


@pytest.mark.parametrize("target,part", [("BoreDia", 4), ("DiscThick", 3)])
@pytest.mark.parametrize(
    "failure", ["write", "ineffective", "partial", "read", "wrong_compartment"]
)
def test_required_callout_failure_prevents_export(
    disc_sheet, target, part, failure
) -> None:
    fault = SimpleNamespace(part=part, kind=failure, triggered=False)
    disc_sheet.displays[target].fault = fault
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(disc_sheet.adapter))
    assert fault.triggered
    assert not disc_sheet.exported


@pytest.mark.parametrize("target", ["BoreDia", "DiscThick"])
def test_missing_required_callout_prevents_export(disc_sheet, target) -> None:
    disc_sheet.annotations[:] = [
        annotation
        for annotation in disc_sheet.annotations
        if annotation.display.GetDimension().Name != target
    ]
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(disc_sheet.adapter))
    assert not disc_sheet.exported


@pytest.mark.parametrize("target", ["DiscDia", "BoreDia", "DiscThick"])
def test_lost_source_precision_prevents_export(disc_sheet, target) -> None:
    disc_sheet.displays[target].precision += 1
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(disc_sheet.adapter))
    assert not disc_sheet.exported
