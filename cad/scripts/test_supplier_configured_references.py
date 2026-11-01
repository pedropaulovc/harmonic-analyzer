"""Offline native-inventory regressions; not a claim of SOLIDWORKS parity."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_dimensions as drawing_dimensions
import _supplier_chain_dimensions as chain_dimensions
import _supplier_chain_stock as chain_stock
import _supplier_spring_drawing as supplier_drawing


class _NativeDimension:
    def __init__(self, name, owner, value_mm):
        self.FullName = f"{name}@{owner}@native-part.SLDPRT"
        self.value_mm = value_mm
        self.Tolerance = SimpleNamespace(Type=0)

    def GetSystemValue3(self, which, configuration_names):
        assert which == 3
        raw_names = getattr(configuration_names, "value", configuration_names)
        names = (raw_names,) if isinstance(raw_names, str) else tuple(raw_names)
        if names != (chain_stock.SUPPLIER_REFERENCE_CONFIGURATION,):
            # An unqualified/installed-member lookup must not happen to pass.
            return (1.3 / 1000.0,)
        return (self.value_mm / 1000.0,)


class _Display:
    def __init__(self, name, owner, value_mm):
        self.native = _NativeDimension(name, owner, value_mm)
        self.options = None
        self.OffsetText = False

    def GetDimension2(self, index):
        assert index == 0
        return self.native


class _Annotation:
    def __init__(self, display):
        self.display = display
        self.position = self.line_position = (0.0, 0.0, 0.0)

    def GetType(self):
        return 4

    def GetSpecificAnnotation(self):
        return self.display

    def SetPosition2(self, x, y, z):
        self.position = (x, y, z)
        if not self.display.OffsetText:
            self.line_position = self.position
        return True


class _View:
    def __init__(self, name, configuration):
        self.Name = name
        self.ReferencedConfiguration = configuration
        self.annotations = []
        self.Position = (0.073, 0.119)
        self.ScaleRatio = (1.0, 2.0)
        self.source_points = ()
        self.dimension_positions = {}
        self.outline = (0.05, 0.12, 0.15, 0.16)
        self.outline_calls = 0

    def GetOutline(self):
        self.outline_calls += 1
        return self.outline

    def GetAnnotations(self):
        return tuple(self.annotations)

    def GetDisplayDimensionCount(self):
        return len(self.annotations)

    @property
    def ModelToViewTransform(self):
        scale = self.ScaleRatio[0] / self.ScaleRatio[1]
        x, y = self.Position
        return SimpleNamespace(
            apply=lambda point: (x + point[0] * scale, y + point[1] * scale)
        )


def _chain_sheet(
    monkeypatch,
    *,
    connecting,
    position=(0.073, 0.119),
    scale=(1.0, 2.0),
    outline=(0.05, 0.12, 0.15, 0.16),
):
    views = {
        "free_front": _View("front", chain_stock.SUPPLIER_REFERENCE_CONFIGURATION),
        "free_top": _View("top", chain_stock.SUPPLIER_REFERENCE_CONFIGURATION),
        "installed_iso": _View("installed", "InnerLink"),
    }
    views["free_front"].source_points = (
        (0.001, -chain_stock.ROLLER_DIAMETER / 2000),
        (0.001 + 2 * chain_stock.PITCH / 1000, chain_stock.ROLLER_DIAMETER / 2000),
    )
    # The TOP ink: the roller outline alone, or roller to pin outline (three
    # pitches across), whose pin length sets the height.
    top_width, top_height = (
        (3 * chain_stock.PITCH, chain_stock.CONNECTING_PIN_LENGTH)
        if connecting
        else (chain_stock.ROLLER_DIAMETER, chain_stock.ROLLER_WIDTH)
    )
    views["free_top"].source_points = (
        (0.002, -top_height / 2000),
        (0.002 + top_width / 1000, top_height / 2000),
    )
    for view in views.values():
        view.Position = position
        view.ScaleRatio = scale
        view.outline = outline

    def reference_bounds(key):
        assert key in chain_dimensions.SOURCE_FEATURES
        view = views[key]
        assert (
            view.ReferencedConfiguration == chain_stock.SUPPLIER_REFERENCE_CONFIGURATION
        )
        # Only the validated bounds boundary is faked here. Its source curves
        # and current native transform are unrelated to cells or GetOutline.
        transform = view.ModelToViewTransform
        xs, ys = zip(*(transform.apply(point) for point in view.source_points))
        return (min(xs), min(ys), max(xs), max(ys))

    values = {
        chain_stock.PIN_DIMENSION: chain_stock.PIN_DIAMETER,
        chain_stock.ROLLER_DIMENSION: chain_stock.ROLLER_DIAMETER,
        chain_stock.PITCH_DIMENSION: chain_stock.PITCH,
        chain_stock.WIDTH_DIMENSION: chain_stock.ROLLER_WIDTH,
        chain_stock.PLATE_DIMENSION: chain_stock.PLATE_THICKNESS,
        chain_stock.LENGTH_DIMENSION: chain_stock.CONNECTING_PIN_LENGTH,
    }
    for module in (chain_dimensions, supplier_drawing):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        supplier_drawing, "iter_views", lambda _adapter: tuple(views.values())
    )
    monkeypatch.setattr(supplier_drawing, "view_name", lambda _adapter, view: view.Name)
    for module in (chain_dimensions, drawing_dimensions):
        monkeypatch.setattr(
            module,
            "dimension_name",
            lambda _adapter, annotation: annotation.display.native.FullName.split("@")[0],
        )
    monkeypatch.setattr(
        drawing_dimensions._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_members: value,
    )
    monkeypatch.setattr(drawing_dimensions, "rebuild_drawing", lambda *_args, **_kwargs: None)

    def curate(_adapter, view, *, keep, dimensions_by_feature, **_kwargs):
        owner = (
            chain_stock.FRONT_FEATURE
            if view is views["free_front"]
            else chain_stock.SECTION_FEATURE
        )
        assert set(keep) <= dimensions_by_feature[owner]
        view.dimension_positions = dict(keep)
        view.annotations = [
            _Annotation(_Display(name, owner, values[name])) for name in keep
        ]
        for name, annotation in zip(keep, view.annotations, strict=True):
            annotation.SetPosition2(*keep[name], 0.0)
        return view.annotations

    def present(_adapter, display, **options):
        # Presentation is covered by the shared supplier-dimension tests. This
        # collaborator retains its actual inputs while the real family reader
        # below owns configured values, owner/inventory and rebuild reacquisition.
        display.options = options

    def assert_presentation(_adapter, display, **options):
        assert display.options == options

    monkeypatch.setattr(chain_dimensions, "curate_view_dimensions", curate)
    monkeypatch.setattr(chain_dimensions, "supplier_reference_dimension", present)
    monkeypatch.setattr(
        chain_dimensions, "assert_supplier_reference_dimension", assert_presentation
    )
    checks = chain_dimensions.annotate_chain_stock(
        SimpleNamespace(_attempt=lambda operation: operation()),
        views,
        connecting=connecting,
        reference_bounds=reference_bounds,
    )
    return views, checks[0]


@pytest.mark.parametrize("connecting,expected_count", [(False, 4), (True, 6)])
def test_supplier_inventory_retains_exact_nominals_and_reacquires_rebuilt_annotations(
    monkeypatch,
    connecting,
    expected_count,
):
    views, settled = _chain_sheet(monkeypatch, connecting=connecting)
    assert (
        sum(view.GetDisplayDimensionCount() for view in views.values())
        == expected_count
    )
    assert not views["installed_iso"].annotations
    pin = next(
        annotation.display
        for annotation in views["free_front"].annotations
        if annotation.display.native.FullName.startswith(
            chain_stock.PIN_DIMENSION + "@"
        )
    )
    assert pin.native.value_mm == pytest.approx(2.2987, abs=1e-12)
    assert pin.native.value_mm != pytest.approx(0.091 * 25.4, abs=1e-8)
    assert pin.options["precision"] == 3
    assert pin.options["presentation"] == "diameter"
    # Rebuild replaces annotation COM objects. A retained pre-rebuild handle
    # cannot prove the final inventory: only newly returned objects survive.
    for view in views.values():
        replacements = []
        for annotation in view.annotations:
            old = annotation.display
            name, owner, _ = old.native.FullName.split("@")
            new = _Display(name, owner, old.native.value_mm)
            new.options = dict(old.options)
            new.OffsetText = old.OffsetText
            replacements.append(_Annotation(new))
            old.native.value_mm = -1.0
        view.annotations = replacements
    settled()


@pytest.mark.parametrize(
    "fault", ["owner", "value", "band", "missing", "foreign", "configuration"]
)
def test_final_supplier_readback_rejects_source_or_inventory_drift(monkeypatch, fault):
    views, settled = _chain_sheet(monkeypatch, connecting=True)
    front = views["free_front"]
    display = front.annotations[0].display
    if fault == "owner":
        display.native.FullName = f"{chain_stock.PIN_DIMENSION}@InstalledPin@part"
    elif fault == "value":
        display.native.value_mm = 1.3  # Installed stand-in pin is not supplier stock.
    elif fault == "band":
        display.native.Tolerance.Type = 2
    elif fault == "missing":
        front.annotations.pop()
    elif fault == "foreign":
        views["installed_iso"].annotations.append(
            _Annotation(_Display("ForeignSize", "InstalledPin", 1.3)),
        )
    elif fault == "configuration":
        front.ReferencedConfiguration = "OuterLink"
    with pytest.raises(RuntimeError):
        settled()


def test_connecting_application_references_are_explicit_not_physical_roller_claims(
    monkeypatch,
):
    views, settled = _chain_sheet(monkeypatch, connecting=True)
    displays = {
        annotation.display.native.FullName.split("@")[0]: annotation.display
        for view in views.values()
        for annotation in view.annotations
    }
    assert displays[chain_stock.ROLLER_DIMENSION].options["callout"] == "FOR ROLLER"
    assert (
        displays[chain_stock.WIDTH_DIMENSION].options["callout"] == "FOR ROLLER WIDTH"
    )
    assert displays[chain_stock.LENGTH_DIMENSION].native.value_mm == pytest.approx(
        8.509
    )
    assert displays[chain_stock.PLATE_DIMENSION].native.value_mm == pytest.approx(0.762)
    settled()


@pytest.mark.parametrize("connecting", [False, True])
@pytest.mark.parametrize(
    "position,scale,outline",
    [
        ((0.073, 0.119), (1.0, 2.0), (0.05, 0.12, 0.15, 0.16)),
        ((0.182, 0.221), (2.0, 1.0), (-2.0, -3.0, 4.0, 5.0)),
    ],
    ids=["stale", "padded"],
)
def test_chain_annotation_positions_follow_source_ink_not_stale_outline(
    monkeypatch, connecting, position, scale, outline
):
    views, settled = _chain_sheet(
        monkeypatch,
        connecting=connecting,
        position=position,
        scale=scale,
        outline=outline,
    )
    ratio = scale[0] / scale[1]
    x, y = position
    front_left = x + 0.001 * ratio
    front_right = front_left + 2 * chain_stock.PITCH / 1000 * ratio
    front_bottom = y - chain_stock.ROLLER_DIAMETER / 2000 * ratio
    front_top = y + chain_stock.ROLLER_DIAMETER / 2000 * ratio
    expected_front = {
        chain_stock.PIN_DIMENSION: (front_left - 0.014, front_bottom - 0.008),
        chain_stock.ROLLER_DIMENSION: (front_right + 0.014, front_bottom - 0.008),
        chain_stock.PITCH_DIMENSION: (
            (front_left + front_right) / 2,
            front_top + 0.008,
        ),
    }
    top_left = x + 0.002 * ratio
    top_right = top_left + (
        3 * chain_stock.PITCH if connecting else chain_stock.ROLLER_DIAMETER
    ) / 1000 * ratio
    plate_span_x = top_left + chain_stock.PITCH / 1000 * ratio
    expected_top = {chain_stock.WIDTH_DIMENSION: (top_left - 0.014, y)}
    if connecting:
        expected_top.update(
            {
                chain_stock.PLATE_DIMENSION: (
                    plate_span_x - 0.003,
                    y + chain_stock.CONNECTING_PIN_LENGTH / 2000 * ratio + 0.004,
                ),
                chain_stock.LENGTH_DIMENSION: (top_right + 0.020, y),
            }
        )
    for key, expected in (("free_front", expected_front), ("free_top", expected_top)):
        assert set(views[key].dimension_positions) == set(expected)
        for name, xy in expected.items():
            assert views[key].dimension_positions[name] == pytest.approx(xy)
    if connecting and ratio == 2.0:
        # At the 2:1 fit the shelved two-row plate REF (about 8 mm tall, 16 mm
        # wide, centred 10 mm left of its line) sits above the roller outline,
        # short of the roller-width line, inside a 40 mm cell centred on the ink;
        # its line stands clear left of the plate outline it measures.
        plate_x, plate_y = views["free_top"].dimension_positions[
            chain_stock.PLATE_DIMENSION
        ]
        assert plate_y - 0.004 > y + chain_stock.ROLLER_WIDTH / 2000 * ratio + 0.001
        assert plate_y + 0.004 < y + 0.020
        assert plate_x - 0.010 - 0.008 > top_left - 0.014 + 0.002
        assert plate_x < plate_span_x
    assert not views["installed_iso"].dimension_positions
    settled()
    assert all(view.outline_calls == 0 for view in views.values())


@pytest.mark.parametrize("connecting", [False, True])
def test_chain_top_shelves_text_without_moving_native_lines(monkeypatch, connecting):
    views, settled = _chain_sheet(
        monkeypatch, connecting=connecting, scale=(5.0, 1.0)
    )
    top = views["free_top"]
    by_name = {
        annotation.display.native.FullName.split("@")[0]: annotation
        for annotation in top.annotations
    }
    shelves = {chain_stock.WIDTH_DIMENSION: -0.024}
    if connecting:
        shelves[chain_stock.PLATE_DIMENSION] = -0.010
        shelves[chain_stock.LENGTH_DIMENSION] = 0.024
    for name, dx in shelves.items():
        annotation = by_name[name]
        line = top.dimension_positions[name]
        assert annotation.display.OffsetText is True
        assert annotation.line_position == pytest.approx((*line, 0.0))
        assert annotation.position == pytest.approx((line[0] + dx, line[1], 0.0))
    settled()
    by_name[chain_stock.WIDTH_DIMENSION].display.OffsetText = False
    with pytest.raises(RuntimeError, match="text returned to its native dimension line"):
        settled()


def test_chain_top_fit_lane_accommodates_five_to_one_source_gauge():
    import draw_sh_vn_chain_link as chain_drawing

    cells = supplier_drawing.supplier_fit_cells(
        supplier_drawing.supplier_state_cells(0.08, maximum=False),
        chain_drawing._CHAIN_SUPPLIER_MARGINS,
        label="chain reference",
    )
    top = next(box for name, _center, box in cells if name == "free_top")
    available_height = top[3] - top[1]
    assert chain_stock.ROLLER_WIDTH / 1000 * 5 < available_height
    assert chain_stock.ROLLER_WIDTH / 1000 * 8 > available_height


def test_chain_top_roller_square_projects_over_front_roller_circle():
    import draw_sh_vn_chain_link as chain_drawing

    cells = {
        name: center
        for name, center, _box in supplier_drawing.supplier_fit_cells(
            supplier_drawing.supplier_state_cells(0.08, maximum=False),
            chain_drawing._CHAIN_SUPPLIER_MARGINS,
            label="chain reference",
        )
    }
    # Each diagram's ink is centred in its cell: FRONT runs pin left edge to
    # roller right edge, TOP is the roller square alone (both at 5:1).
    front_ink_centre = (
        -chain_stock.PIN_DIAMETER / 2 + chain_stock.PITCH + chain_stock.ROLLER_DIAMETER / 2
    ) / 2
    roller_x = cells["free_front"][0] + (chain_stock.PITCH - front_ink_centre) / 1000 * 5
    assert cells["free_top"][0] == pytest.approx(roller_x)


def test_connecting_link_top_fit_lane_accommodates_two_to_one_pin_length():
    cells = supplier_drawing.supplier_fit_cells(
        supplier_drawing.supplier_state_cells(0.08, maximum=False),
        chain_dimensions.SUPPLIER_MARGINS,
        label="connecting link reference",
    )
    top = next(box for name, _center, box in cells if name == "free_top")
    available_height = top[3] - top[1]
    assert chain_stock.CONNECTING_PIN_LENGTH / 1000 * 2 < available_height
    assert chain_stock.CONNECTING_PIN_LENGTH / 1000 * 4 > available_height


def test_wire_nominal_cannot_be_read_from_the_installed_envelope(monkeypatch):
    from _mcmaster_9666k56 import DIA
    from _mcmaster_9666k56_reference import (
        SUPPLIER_REFERENCE_CONFIGURATION,
        SUPPLIER_REFERENCE_DIMENSION,
        SUPPLIER_REFERENCE_FEATURE,
    )

    monkeypatch.setattr(
        supplier_drawing, "_early_bound", lambda value, _interface: value
    )
    display = _Display(SUPPLIER_REFERENCE_DIMENSION, SUPPLIER_REFERENCE_FEATURE, DIA)
    supplier_drawing.assert_supplier_configuration_value(
        display,
        SUPPLIER_REFERENCE_CONFIGURATION,
        0.7874,
        label="supplier wire circle",
    )
    display.native.value_mm = 0.8
    with pytest.raises(RuntimeError, match="configured supplier dimension changed"):
        supplier_drawing.assert_supplier_configuration_value(
            display,
            SUPPLIER_REFERENCE_CONFIGURATION,
            DIA,
            label="supplier wire circle",
        )
