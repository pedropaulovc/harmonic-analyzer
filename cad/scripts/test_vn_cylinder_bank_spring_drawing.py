"""Offline contracts for the MHA-VN-052 cylinder bank spring (McMaster 9714K392)."""

from __future__ import annotations

import asyncio
import contextlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_vn_cylinder_bank_spring as part
import vn_cylinder_bank_spring_spec as spec
import vn_rocker_bank_spring_spec as rocker_spec
import vn_transgear_pivot_spring_spec as pivot_spec
import vn_disc_spring_supplier_stock as supplier
from _fastener_catalog import FASTENERS
from _test_stock_recipes import discovered_recipes
from diagnostics import diag_build_9714K392 as recipe

STEM = "vn-cylinder-bank-spring"
NUMBER = "MHA-VN-052"
STOCK_NAME = "Wave Disc Spring"
BUILD = "build_9714K392"
IN = 25.4
LBF = 4.4482216


def test_catalogue_row_is_the_registered_mcmaster_wave_spring() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("9714K392",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"] == STOCK_NAME
    assert stock.material == row["material"] == part.MATERIAL
    assert row["number"] == NUMBER
    assert int(row["quantity"]) == spec.COUNT == 1
    metadata = discovered_recipes()[spec.SKU]
    assert metadata.module == recipe.__name__
    assert getattr(recipe, metadata.callable_name) is getattr(recipe, BUILD)
    assert metadata.threaded is False


def test_spec_carries_the_live_catalogue_facts() -> None:
    """mcmaster.com/9714K392, read live 2026-10-09."""
    assert spec.ID == pytest.approx(0.385 * IN)
    assert spec.OD == pytest.approx(0.5 * IN)
    assert spec.THICKNESS == pytest.approx(0.005 * IN)
    assert spec.FREE_HEIGHT == pytest.approx(0.05 * IN)
    assert spec.WORKING_HEIGHT == pytest.approx(0.024 * IN)
    assert spec.WORKING_LOAD_N == pytest.approx(1.5 * LBF)
    # The model is the installed envelope at the 0.95 set gap.
    assert spec.MODEL_HEIGHT == spec.INSTALLED_HEIGHT == pytest.approx(0.95)
    assert spec.WORKING_HEIGHT <= spec.MODEL_HEIGHT < spec.FREE_HEIGHT


@pytest.fixture
def nominal_diagram(monkeypatch):
    """Measure the actual authored entities; never return the requested size.

    This is an offline geometry/readback fake, not a native solver or a claim
    about saved-body/configuration parity. The native fully-defined and hidden
    sketch gates still run, including their failure paths.
    """
    import _drawing_tolerances
    import _sketch

    def success(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    class Tolerance:
        Type = 0
        minimum = maximum = 0.0

        def SetValues(self, minimum, maximum):
            self.minimum, self.maximum = minimum, maximum
            return True

        def GetMinValue(self):
            return self.minimum

        def GetMaxValue(self):
            return self.maximum

    class Display:
        MarkedForDrawing = False
        precision = 0

        def __init__(self, value, entity):
            self.dimension = SimpleNamespace(
                SystemValue=value / 1000.0,
                Tolerance=Tolerance(),
                entity=entity,
            )

        def SetPrecision3(self, primary, dual, tolerance, dual_tolerance):
            if tolerance >= 0:
                self.precision = tolerance
            return 0

        def GetPrimaryTolPrecision2(self):
            return self.precision

    class Adapter:
        def __init__(self, failure=None):
            self.currentModel = self
            self.currentSketchManager = SimpleNamespace(AddToDB=False)
            self.active = self.last = self.selected = None
            self.sketches = {}
            self.entities = {}
            self.failure = failure
            self.Extension = SimpleNamespace(SelectByID2=self.select)

        async def create_sketch(self, plane):
            self.active = SimpleNamespace(
                plane=plane,
                segments=[],
                dimensions=[],
                Visible=2,
                checked=False,
            )
            self.active.GetSketchSegments = lambda: (
                self.active.segments[:-1]
                if self.failure == "missing_geometry"
                else self.active.segments
            )
            return success()

        def GetActiveSketch2(self):
            return self.active

        async def exit_sketch(self):
            self.last, self.active = self.active, None
            return success()

        async def add_line(self, x0, y0, x1, y1):
            return self.add_entity(
                SimpleNamespace(
                    kind="line",
                    start=(x0, y0),
                    end=(x1, y1),
                    ConstructionGeometry=False,
                )
            )

        async def add_circle(self, x, y, radius):
            return self.add_entity(
                SimpleNamespace(
                    kind="circle",
                    center=(x, y),
                    radius=radius,
                    ConstructionGeometry=False,
                )
            )

        def add_entity(self, segment):
            segment.GetType = lambda: (
                3
                if self.failure == "segment_type"
                else (1 if segment.kind == "circle" else 0)
            )
            segment.IsCircle = lambda: 0 if self.failure == "partial_circle" else 1
            segment.GetLength = lambda: (
                (2.0 if self.failure == "segment_length" else 1.0)
                * (
                    2.0 * math.pi * segment.radius
                    if segment.kind == "circle"
                    else math.dist(segment.start, segment.end)
                )
                / 1000.0
            )
            name = f"entity{len(self.entities)}"
            self.entities[name] = segment
            self.active.segments.append(segment)
            return success(name)

        def point(self, reference):
            if reference == "origin":
                return (0.0, 0.0)
            entity, point = reference.split(".")
            return getattr(self.entities[entity], point)

        async def add_sketch_constraint(self, first, second, kind):
            return success()

        async def add_sketch_dimension(self, first, second, kind, requested):
            if kind == "diameter":
                measured = 2.0 * self.entities[first].radius
            elif kind == "linear":
                segment = self.entities[first]
                measured = math.dist(segment.start, segment.end)
            else:
                a, b = self.point(first), self.point(second)
                if kind == "horizontal_distance":
                    measured = abs(a[0] - b[0])
                elif kind == "vertical_distance":
                    measured = abs(a[1] - b[1])
                else:
                    measured = math.dist(a, b)
            assert measured == pytest.approx(requested, abs=1e-10)
            display = Display(measured, (first, second, kind))
            if self.failure == "value":
                display.dimension.SystemValue += 0.0001
            self.active.dimensions.append(display)
            return success()

        async def check_sketch_fully_defined(self):
            self.active.checked = True
            return success(
                {
                    "definition_state": (
                        "under_defined"
                        if self.failure == "underdefined"
                        else "fully_defined"
                    )
                }
            )

        def rename(self, name):
            self.last.Name = name
            self.sketches[name] = self.last

        def FeatureByName(self, name):
            return self.sketches.get(name)

        def select(self, name, *_args):
            self.selected = self.FeatureByName(name)
            return self.selected is not None

        def ClearSelection2(self, _all):
            self.selected = None

        def BlankSketch(self):
            if self.failure != "visible":
                self.selected.Visible = 1

        def named(self, feature, name):
            display = next(
                item
                for item in self.sketches[feature].dimensions
                if item.dimension.Name == name
            )
            return display, display.dimension

    def apply(dims, adapter, feature):
        displays = adapter.sketches[feature].dimensions
        assert len(displays) == len(dims._rows)
        for index, (display, (name, _drive)) in enumerate(
            zip(displays, dims._rows, strict=True)
        ):
            display.dimension.Name = name or f"D{index + 1}"
        return []

    def mark(adapter, feature, names):
        for name in names:
            display, _dimension = adapter.named(feature, name)
            display.MarkedForDrawing = adapter.failure != "unmarked"

    for module in (supplier, _sketch, _drawing_tolerances):
        monkeypatch.setattr(module, "_early_bound", lambda value, interface: value)
    for module in (supplier, _drawing_tolerances):
        monkeypatch.setattr(
            module,
            "_named_dimension",
            lambda adapter, feature, name: adapter.named(feature, name),
        )
    monkeypatch.setattr(supplier.SketchDims, "apply", apply)
    monkeypatch.setattr(
        supplier, "name_last_feature", lambda adapter, name: adapter.rename(name)
    )
    monkeypatch.setattr(supplier, "mark_dimensions_for_drawing", mark)

    def author(source, *, failure=None):
        adapter = Adapter(failure)
        features = asyncio.run(
            supplier.author_supplier_references(adapter, spec=source)
        )
        return adapter, features

    return author


@pytest.mark.parametrize(
    ("source", "inner", "outer", "low", "high", "thickness", "count", "band_type"),
    [
        (spec, 9.779, 12.7, -0.635, 0.635, 0.127, 6, 4),
        (rocker_spec, 6.731, 9.3218, -0.0762, 0.6858, 0.1524, 4, 2),
        (pivot_spec, 5.08, 10.7442, -0.5969, 0.5969, 0.28702, 6, 0),
    ],
)
def test_authored_nominal_diagrams_carry_native_geometry_and_supplier_bands(
    nominal_diagram,
    source,
    inner,
    outer,
    low,
    high,
    thickness,
    count,
    band_type,
) -> None:
    adapter, features = nominal_diagram(source)
    assert set(features) == set(adapter.sketches)
    assert all(
        sketch.Visible == 1 and sketch.checked for sketch in adapter.sketches.values()
    )
    assert all(
        not segment.ConstructionGeometry
        for sketch in adapter.sketches.values()
        for segment in sketch.segments
    )
    plan = adapter.sketches["DiscSupplierPlan"]
    assert len(plan.segments) == 2
    assert [2.0 * circle.radius for circle in plan.segments] == pytest.approx(
        [inner, outer]
    )
    assert all(circle.center == (0.0, 0.0) for circle in plan.segments)
    envelope = adapter.sketches["DiscSupplierHeight"].segments
    assert len(envelope) == 4
    expected_corners = [
        (-outer / 2.0, low),
        (-outer / 2.0, high),
        (outer / 2.0, high),
        (outer / 2.0, low),
    ]
    for line, corner in zip(envelope, expected_corners, strict=True):
        assert line.start == pytest.approx(corner, abs=1e-12)
    assert all(
        line.end == envelope[(index + 1) % 4].start
        for index, line in enumerate(envelope)
    )
    strip = adapter.sketches["DiscSupplierStrip"].segments
    assert len(strip) == 4
    assert math.dist(strip[0].start, strip[0].end) == pytest.approx(
        thickness, abs=1e-12
    )
    if source is rocker_spec:
        assert strip[0].start == pytest.approx((3.3655, 0.2286), abs=1e-12)
        assert strip[0].end == pytest.approx((3.3655, 0.381), abs=1e-12)
    if source is pivot_spec:
        assert math.dist(strip[0].start, strip[0].end) != pytest.approx(0.011 * IN)
        shaft = adapter.sketches["DiscSupplierShaft"].segments
        assert len(shaft) == 1
        assert shaft[0].radius * 2.0 == pytest.approx(4.826)
    marked = [
        display
        for sketch in adapter.sketches.values()
        for display in sketch.dimensions
        if display.MarkedForDrawing
    ]
    assert len(marked) == count
    assert {display.dimension.Name for display in marked} == {
        supplier.SUPPLIER_DIMENSION_NAMES[key]
        for key in source.SUPPLIER_DRAWING_PRECISION
    }
    for key in ("SupplierID", "SupplierOD"):
        display, dimension = adapter.named("DiscSupplierPlan", key)
        tolerance = dimension.Tolerance
        assert tolerance.Type == band_type
        if band_type:
            assert display.GetPrimaryTolPrecision2() == 3
            assert tolerance.GetMaxValue() == pytest.approx(0.000254)
            assert tolerance.GetMinValue() == pytest.approx(
                -0.000254 if band_type == 4 else -0.000508
            )
    if source is not rocker_spec:
        gauge = adapter.sketches["DiscSupplierApplication"]
        expected = (
            {"SupplierWorkingHeight": 0.6096, "SupplierWorkingDeflection": 0.6604}
            if source is spec
            else {"SupplierWorkingHeight": 0.6858}
        )
        assert {
            display.dimension.Name: display.dimension.SystemValue * 1000.0
            for display in gauge.dimensions
            if display.MarkedForDrawing
        } == pytest.approx(expected, abs=1e-12)

    # The pre-fit contract comes from the same geometry, including shaft and
    # gauge extents, rather than whichever outline a native view happened to return.
    extents = supplier.supplier_diagram_extents(source)
    for key, plane in (
        ("free_top", "Top"),
        ("free_front", "Front"),
        ("free_right", "Right"),
    ):
        points = []
        for sketch in adapter.sketches.values():
            if sketch.plane != plane:
                continue
            for segment in sketch.segments:
                if segment.kind == "line":
                    points.extend((segment.start, segment.end))
                else:
                    x, y = segment.center
                    points.extend(
                        (
                            (x - segment.radius, y - segment.radius),
                            (x + segment.radius, y + segment.radius),
                        )
                    )
        if not points:
            assert key not in extents
            continue
        actual = (
            max(x for x, _y in points) - min(x for x, _y in points),
            max(y for _x, y in points) - min(y for _x, y in points),
        )
        assert all(value > 0.0 for value in actual)
        assert extents[key] == pytest.approx(actual, abs=1e-12)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("value", "exact supplier dimension"),
        ("unmarked", "exact supplier dimension"),
        ("underdefined", "sketch not fully defined"),
        ("visible", "still visible"),
        ("missing_geometry", "native nominal diagram segments changed"),
        ("segment_type", "native nominal diagram segment type changed"),
        ("segment_length", "native nominal diagram segment lengths changed"),
        ("partial_circle", "requires complete circles"),
    ],
)
def test_nominal_diagrams_reject_bad_native_readbacks(
    nominal_diagram, failure, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        nominal_diagram(spec, failure=failure)


class _Recorder:
    """A fake SolidWorks that records every call a recipe makes."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def log(self, name: str, args=(), kwargs=None) -> None:
        self.events.append((name, tuple(args), dict(kwargs or {})))

    async def create_sketch(self, *args):
        self.log("create_sketch", args)
        return "ok"

    async def exit_sketch(self, *args):
        self.log("exit_sketch", args)
        return "ok"

    async def create_extrusion(self, *args):
        self.log("create_extrusion", args)
        return "ok"


def _record(monkeypatch) -> list[tuple]:
    adapter = _Recorder()

    async def define_circle(_adapter, x, y, radius, label, **kwargs):
        adapter.log("circle", (x, y, radius, label))
        return label

    async def volume_check(_adapter, label, expected, tol):
        adapter.log("volume_check", (label, expected, tol))
        return expected

    @contextlib.contextmanager
    def no_inference(_adapter):
        adapter.log("no_inference_enter")
        yield
        adapter.log("no_inference_exit")

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(
        recipe, "name_last_feature", lambda _a, name: adapter.log("name", (name,))
    )
    monkeypatch.setattr(recipe, "volume_check", volume_check)
    monkeypatch.setattr(recipe, "define_circle", define_circle)
    monkeypatch.setattr(recipe, "no_sketch_inference", no_inference)
    asyncio.run(getattr(recipe, BUILD)(adapter))
    return adapter.events


def test_recipe_is_the_installed_envelope_annulus(monkeypatch) -> None:
    calls = _record(monkeypatch)
    names = [c[0] for c in calls]
    assert calls[0] == ("create_sketch", ("Top",), {})
    circles = [c[1] for c in calls if c[0] == "circle"]
    assert sorted(r for _x, _y, r, _ in circles) == pytest.approx(
        [spec.ID / 2.0, spec.OD / 2.0]
    )
    assert all((x, y) == (0.0, 0.0) for x, y, _r, _ in circles)
    enter, leave = names.index("no_inference_enter"), names.index("no_inference_exit")
    assert all(enter < i < leave for i, n in enumerate(names) if n == "circle")
    (extrude,) = [c for c in calls if c[0] == "create_extrusion"]
    assert extrude[1][0].depth == pytest.approx(spec.MODEL_HEIGHT)
    assert not extrude[1][0].both_directions
    assert [c[1][0] for c in calls if c[0] == "name"] == ["SpringProfile", "SpringBody"]
    (volume,) = [c for c in calls if c[0] == "volume_check"]
    assert volume[1][1] == pytest.approx(
        math.pi / 4.0 * (spec.OD**2 - spec.ID**2) * spec.MODEL_HEIGHT
    )


def test_standalone_recipe_run_is_catalog_only(monkeypatch, tmp_path) -> None:
    from diagnostics import diag_mcmaster_lib as lib

    assert not hasattr(recipe, "replica_main")
    saved: list[str] = []
    built: list = []

    class _Adapter:
        async def create_part(self):
            return "ok"

        async def save_file(self, path):
            saved.append(path)
            return "ok"

    async def fake_recipe(adapter, truth=None):
        built.append(adapter)

    async def no_views(_adapter, _stem):
        return {}

    async def no_close(_adapter):
        return None

    monkeypatch.setattr(recipe, "check", lambda *a, **k: True)
    monkeypatch.setattr(recipe, BUILD, fake_recipe)
    monkeypatch.setattr(lib, "OUT_DIR", tmp_path)
    monkeypatch.setattr(lib, "assert_seat_sketch_baseline", lambda *a: None)
    monkeypatch.setattr(lib, "mass_properties", lambda _a: {"volume_mm3": 13.0})
    monkeypatch.setattr(lib, "export_views", no_views)
    monkeypatch.setattr(lib, "close_all", no_close)
    adapter = _Adapter()
    artefacts = asyncio.run(recipe.build_catalog(adapter))
    assert built == [adapter]
    assert saved == [str((tmp_path / f"{spec.SKU}-catalog.SLDPRT").resolve())]
    assert artefacts["sldprt"] == str(tmp_path / f"{spec.SKU}-catalog.SLDPRT")


def test_no_vendor_model_is_tracked() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not list(root.glob(f"cad/references/**/{spec.SKU}*.SLDPRT"))


def test_installation_note_fits_the_sheet() -> None:
    lines = _config.parts(STEM)["installation_notes"].splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines), lines
