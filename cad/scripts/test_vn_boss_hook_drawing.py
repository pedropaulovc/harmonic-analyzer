"""Offline manufacturing boundaries for the modified purchased anchor."""

import asyncio
import importlib
import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import vn_boss_hook_spec as spec
import draw_vn_boss_hook as drawing
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    # The full 19.05 boss plus the jam nut's thread above it (#1189).
    assert spec.TRIM.shank_length_mm == pytest.approx(22.886)
    assert spec.TRIM.shank_length_mm - 19.05 >= spec.JAM_NUT_THREAD_MM - 1e-3
    assert spec.FINISHED_OVERALL_MM == pytest.approx(40.4755)


def test_deburr_band_clears_receiver_and_retains_full_threads():
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    short_shank = spec.SHANK_LENGTH_MM - spec.FINISHED_OVERALL_TOLERANCE_MM
    assert short_shank - maximum_axial > 17.0


@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "tolerance", "precision", "missing"]
)
def test_drawing_accepts_general_controls_and_rejects_lost_control(monkeypatch, fault):
    """General is toleranced, unlike None; neither replaces a real driving size."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    annotations = []
    for name, nominal, band in (
        (
            "FinishedOverall",
            spec.FINISHED_OVERALL_MM / 1000,
            spec.FINISHED_OVERALL_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferWidth",
            spec.CHAMFER_WIDTH_MM / 1000,
            spec.CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferAngle",
            math.radians(spec.CHAMFER_ANGLE_DEG),
            math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    ):
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda band=band: -band,
            GetMaxValue=lambda band=band: band,
        )
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        annotations.append(
            SimpleNamespace(
                name=name,
                dimension=dimension,
                display=display,
                GetSpecificAnnotation=lambda display=display: display,
            )
        )
    if fault == "reference":
        annotations[0].dimension.DrivenState = 1
    elif fault == "nominal":
        annotations[0].dimension.SystemValue += 0.001
    elif fault == "tolerance":
        # swTolNONE must remain invalid; a no-tolerance spec is a regression.
        annotations[0].dimension.Tolerance.Type = 0
    elif fault == "precision":
        annotations[0].display.GetPrimaryPrecision2 = lambda: (
            spec.DIMENSION_PRECISION["FinishedOverall"] + 1
        )
    elif fault == "missing":
        annotations.pop()
    if fault is None:
        drawing._verify_controls(None, annotations)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_controls(None, annotations)


def test_supplier_nominals_are_distinct_from_the_exact_finished_solid():
    assert spec.SUPPLIER_EYE_ID_MM == anchor.eye_id_mm == pytest.approx(5 / 16 * 25.4)
    assert spec.SUPPLIER_NOMINAL_EYE_OD_MM == pytest.approx(11 / 16 * 25.4)
    assert spec.SUPPLIER_NOMINAL_WIRE_MM == pytest.approx(3 / 16 * 25.4)
    assert anchor.eye_od_mm == pytest.approx(0.6925 * 25.4)
    assert anchor.wire_dia_mm == pytest.approx(0.190 * 25.4)
    assert spec.SUPPLIER_NOMINAL_EYE_OD_MM != pytest.approx(anchor.eye_od_mm)
    assert spec.SUPPLIER_NOMINAL_WIRE_MM != pytest.approx(anchor.wire_dia_mm)
    assert spec.SUPPLIER_STOCK_DIMENSIONS == {
        spec.SUPPLIER_STOCK_FEATURE: {
            "SupplierNominalEyeOD",
            "SupplierNominalWire",
            "SupplierStockShank",
            "SupplierStockOverall",
        }
    }
    assert spec.SUPPLIER_REFERENCE_PRECISION == {
        "EyeID": 0,
        "SupplierNominalEyeOD": 0,
        "SupplierNominalWire": 0,
        "SupplierStockShank": 0,
        "SupplierStockOverall": 0,
    }
    assert spec.SUPPLIER_FRACTION_DENOMINATOR == 16
    assert spec.SUPPLIER_THREAD == "#10-24"
    # Original stock lengths never become finished manufacturing controls.
    assert set(drawing.EXPECTED_CONTROLS) == {
        "FinishedOverall",
        "ChamferWidth",
        "ChamferAngle",
    }


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
@pytest.mark.parametrize("stock_active", [False, True])
def test_simplified_save_excludes_the_source_stock_configuration(
    monkeypatch, module_name, stock_active
):
    part = importlib.import_module(module_name)
    active = part.SUPPLIER_STOCK_CONFIGURATION if stock_active else "Default"

    events = []
    artefacts = {"part": "counter-anchor.SLDPRT"}

    async def save(*_args):
        events.append("save")
        return artefacts

    async def derive(_adapter, part_name, features, path, *, parents):
        events.append(("derive", part_name, features, path, parents))

    async def open_model(path):
        events.append(("open", path))
        return "opened"

    monkeypatch.setattr(part, "active_configuration_name", lambda *_args: active)
    monkeypatch.setattr(part, "save_part_and_images", save)
    monkeypatch.setattr(part, "derive_simplified_on_saved_part", derive)
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(
        part,
        "assert_saved_configurations_regenerate",
        lambda *_args: events.append("saved-cache-readback"),
    )
    monkeypatch.setattr(
        part,
        "assert_simplified_configurations",
        lambda _adapter, name, features, *, parents: events.append(
            ("simplified-readback", name, features, parents)
        ),
    )
    adapter = SimpleNamespace(currentModel=object(), open_model=open_model)
    if stock_active:
        with pytest.raises(RuntimeError):
            asyncio.run(
                part._save_anchor(adapter, "hook-under-test", ("ThreadGroove",))
            )
        assert events == []
        return
    assert (
        asyncio.run(part._save_anchor(adapter, "hook-under-test", ("ThreadGroove",)))
        == artefacts
    )
    assert events == [
        "save",
        (
            "derive",
            "hook-under-test",
            ("ThreadGroove",),
            artefacts["part"],
            ("Default",),
        ),
        ("open", artefacts["part"]),
        "saved-cache-readback",
        ("simplified-readback", "hook-under-test", ("ThreadGroove",), ("Default",)),
    ]


def test_stock_build_uses_the_finished_only_simplified_saver(monkeypatch):
    import build_vn_boss_hook as part

    captured = {}

    async def stock(_adapter, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", stock)
    asyncio.run(part.build(None))
    assert captured["save_threaded_part"] is part._save_anchor
    (component,) = captured["components"]
    assert component.author is part._modified_anchor
    assert component.parameters == {"shank_length_mm": spec.SHANK_LENGTH_MM}


def test_full_stock_envelope_connects_the_source_eye_to_the_original_end():
    crown, shank_start, end = spec.SUPPLIER_STOCK_AXIS_MM
    assert math.dist(crown, end) == pytest.approx(3.0 * 25.4)
    assert math.dist(shank_start, end) == pytest.approx((2 + 5 / 16) * 25.4)
    assert math.dist(crown, end) == pytest.approx(spec.SUPPLIER_STOCK_OVERALL_MM)
    assert math.dist(shank_start, end) == pytest.approx(spec.SUPPLIER_STOCK_SHANK_MM)
    assert crown == (0.0, spec.SUPPLIER_NOMINAL_EYE_OD_MM / 2)
    assert shank_start == (0.0, -spec.SUPPLIER_NOMINAL_EYE_OD_MM / 2)
    outline = spec.SUPPLIER_STOCK_SHANK_OUTLINE_MM
    assert outline[0][1] == outline[1][1] == shank_start[1]
    assert outline[2][1] == outline[3][1] == end[1]
    assert math.dist(outline[0], outline[1]) == pytest.approx(
        spec.SUPPLIER_NOMINAL_WIRE_MM
    )
    # The source envelope and the finished, model-authored acceptance size
    # deliberately have different ends; no stock length relabels that cut.
    assert spec.SUPPLIER_STOCK_OVERALL_MM > spec.FINISHED_OVERALL_MM
    assert spec.SUPPLIER_STOCK_SHANK_MM > spec.SHANK_LENGTH_MM


@pytest.mark.parametrize(
    "count,configuration",
    [
        (4, spec.SUPPLIER_STOCK_CONFIGURATION),
        (5, "Default"),
    ],
)
def test_settled_supplier_gate_rejects_missing_refs_or_finished_stock_view(
    count, configuration
):
    with pytest.raises(RuntimeError):
        drawing._verify_supplier_references(
            None, [None] * count, SimpleNamespace(ReferencedConfiguration=configuration)
        )


class _HookFeature:
    def __init__(self, model, name):
        self.model, self.name = model, name
        self.states = {"Default": False}

    def SetSuppression2(self, state, option, names):
        assert option == 1 and names is None
        self.model.writes.append((self.model.active, self.name, state))
        if self.model.refuse_feature == self.name:
            return False
        if self.model.ignore_feature != self.name:
            self.states[self.model.active] = state == 0
        return True

    def IsSuppressed2(self, option, names):
        assert option == 1 and names is None
        return (self.states[self.model.active],)


def _hook_configuration_fixture(monkeypatch, module_name):
    """Use the existing activation-on-add fake, with configuration-local features."""
    from test_supplier_spring_reference import _Model
    import _configuration_material

    part = importlib.import_module(module_name)

    class Model(_Model):
        def __init__(self):
            super().__init__("Hook.sldprt", [object()])
            self.configurations = {"Default": SimpleNamespace(Name="Default")}
            self.feature_map = {
                name: _HookFeature(self, name)
                for name in (*part.FINISHED_FEATURES, part.SUPPLIER_STOCK_FEATURE)
            }
            self.materials = {"Default": part.MATERIAL}
            self.writes, self.switches, self.rebuilds = [], [], []
            self.refuse_feature = self.ignore_feature = None
            self.parent_error = self.restore_error = None
            self.stock_body_count = None

        @property
        def ActiveConfiguration(self):
            return self.configurations[self.active]

        def AddConfiguration2(
            self, name, comment, alternate, options, parent, description, rebuild
        ):
            created = super().AddConfiguration2(
                name, comment, alternate, options, parent, description, rebuild
            )
            created.Name = name
            for feature in self.feature_map.values():
                feature.states[name] = feature.states[parent]
            self.materials[name] = self.materials[parent]

            def get_parent():
                if self.parent_error:
                    raise self.parent_error
                return self.configurations[parent]

            created.GetParent = get_parent
            return created

        def ShowConfiguration2(self, name):
            self.switches.append(name)
            if name == "Default" and self.restore_error:
                raise self.restore_error
            return super().ShowConfiguration2(name)

        def GetBodies2(self, kind, visible_only):
            assert kind == 0 and visible_only is False
            if self.active == part.SUPPLIER_STOCK_CONFIGURATION:
                if self.stock_body_count is not None:
                    return [object()] * self.stock_body_count
                if module_name == "build_vn_boss_hook":
                    roots = (
                        self.feature_map[name].states[self.active]
                        for name in ("Shank", "Wire")
                    )
                    return [] if all(roots) else [object()]
            return [object()]

        def GetMaterialPropertyName2(self, name):
            return self.materials[name], "test-materials.sldmat"

    model = Model()
    adapter = SimpleNamespace(currentModel=model)

    async def profile(_adapter):
        pass

    async def rebuild(_adapter):
        model.rebuilds.append(model.active)

    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        _configuration_material, "_early_bound", lambda value, _interface: value
    )
    monkeypatch.setattr(part, "null_variant", lambda: None)
    monkeypatch.setattr(
        part, "_feature_by_name", lambda _adapter, name: model.feature_map[name]
    )
    monkeypatch.setattr(part, "force_rebuild", rebuild)
    profile_name = (
        "_supplier_nominal_stock_profile"
        if module_name == "build_vn_boss_hook"
        else "_supplier_stock_profile"
    )
    monkeypatch.setattr(part, profile_name, profile)
    if module_name == "build_vn_boss_hook":
        monkeypatch.setattr(part, "_hard_faults", lambda *_args: [])
    callback = (
        part._supplier_nominal_stock
        if module_name == "build_vn_boss_hook"
        else part._supplier_stock
    )
    return part, callback, adapter, model


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_supplier_configuration_activates_on_add_and_isolates_only_its_intended_features(
    monkeypatch, module_name
):
    part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    asyncio.run(callback(adapter))
    assert model.active == "Default"
    # Calling ShowConfiguration2(STOCK) would return False in this native-faithful
    # fake, so reaching here also exercises the first-switch activation guard.
    assert model.switches == ["Default"]
    stock = part.SUPPLIER_STOCK_CONFIGURATION
    intended = (
        set(part.FINISHED_FEATURES)
        if module_name == "build_vn_boss_hook"
        else {"StockTrim", "StockDeburr"}
    )
    assert {
        (name, state) for config, name, state in model.writes if config == stock
    } == {(name, 0) for name in intended}
    for name, feature in model.feature_map.items():
        assert feature.states["Default"] is False
        assert feature.states[stock] is (name in intended)
    assert model.rebuilds == [stock, "Default"]
    assert model.materials[stock] == part.MATERIAL


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
@pytest.mark.parametrize("fault", ["parent", "suppress", "readback", "body"])
def test_supplier_configuration_restores_finished_after_native_inspection_failure(
    monkeypatch, module_name, fault
):
    _part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    if fault == "parent":
        model.parent_error = RuntimeError("parent read failed")
    elif fault == "suppress":
        model.refuse_feature = "StockDeburr"
    elif fault == "readback":
        model.ignore_feature = "StockDeburr"
    else:
        model.stock_body_count = 1 if module_name == "build_vn_boss_hook" else 0
    with pytest.raises(RuntimeError):
        asyncio.run(callback(adapter))
    assert model.active == "Default"
    assert all(
        feature.states["Default"] is False for feature in model.feature_map.values()
    )
    assert model.switches == ["Default"]


def test_boss_diagram_refuses_independent_cut_faults_and_restores_finished(monkeypatch):
    part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, "build_vn_boss_hook"
    )
    monkeypatch.setattr(part, "_hard_faults", lambda *_args: ["ThreadGroove (1)"])
    with pytest.raises(RuntimeError, match="ThreadGroove"):
        asyncio.run(callback(adapter))
    assert model.active == "Default"


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_restoration_failure_does_not_replace_the_primary_native_exception(
    monkeypatch, module_name
):
    _part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    primary = RuntimeError("parent read failed")
    model.parent_error = primary
    model.restore_error = RuntimeError("restore refused")
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(callback(adapter))
    assert raised.value is primary
    assert any("restore refused" in note for note in raised.value.__notes__)


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_a_restore_failure_without_a_primary_error_is_not_silenced(
    monkeypatch, module_name
):
    _part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    model.restore_error = RuntimeError("restore refused")
    with pytest.raises(RuntimeError, match="restore refused"):
        asyncio.run(callback(adapter))


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_all_finished_feature_states_are_checked_after_the_restore_rebuild(
    monkeypatch, module_name
):
    part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )

    async def rebuild(_adapter):
        # A one-body readback alone would miss these non-generator leaks.
        if model.active == "Default":
            model.feature_map["ThreadGroove"].states["Default"] = True

    monkeypatch.setattr(part, "force_rebuild", rebuild)
    with pytest.raises(RuntimeError, match="ThreadGroove.*suppression leaked"):
        asyncio.run(callback(adapter))


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_restore_guard_skips_an_already_restored_configuration(
    monkeypatch, module_name
):
    part, callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    primary = RuntimeError("stock inspection failed after returning to finished")

    async def rebuild(_adapter):
        if model.active == part.SUPPLIER_STOCK_CONFIGURATION:
            model.active = "Default"
            raise primary

    monkeypatch.setattr(part, "force_rebuild", rebuild)
    with pytest.raises(RuntimeError) as raised:
        asyncio.run(callback(adapter))
    assert raised.value is primary
    assert model.switches == []
    assert not getattr(primary, "__notes__", ())


@pytest.mark.parametrize("module_name", ["build_vn_boss_hook", "build_vn_spring_hook"])
def test_stock_callback_runs_after_material_and_before_save(monkeypatch, module_name):
    part, _callback, adapter, model = _hook_configuration_fixture(
        monkeypatch, module_name
    )
    model.materials["Default"] = ""
    events = []

    async def stock(_adapter, **kwargs):
        model.materials["Default"] = kwargs["material"]
        events.append("material")
        await kwargs["before_save"](_adapter)
        assert model.materials[part.SUPPLIER_STOCK_CONFIGURATION] == kwargs["material"]
        events.append("stock")
        assert model.active == "Default"
        events.append("save")
        return {"part": "Hook.sldprt"}

    monkeypatch.setattr(part, "build_stock_fastener", stock)
    assert asyncio.run(part.build(adapter)) == {"part": "Hook.sldprt"}
    assert events == ["material", "stock", "save"]


def test_source_profile_follows_eye_wire_and_shank_edits_as_one_constrained_sketch(
    monkeypatch,
):
    """Solve the emitted constraints, not a second set of equal-valued literals.

    This is an offline geometric regression, not proof of the native solver or
    displayed construction-geometry visibility.
    """
    import numpy as np
    from scipy.optimize import least_squares
    import build_vn_boss_hook as part
    from _sketch import SketchDims

    def ok(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    class Adapter:
        def __init__(self):
            self.currentSketchManager = SimpleNamespace(AddToDB=False)
            self.currentModel = SimpleNamespace(
                ClearSelection2=lambda _all: self.selected.clear(),
                Extension=SimpleNamespace(
                    AddSpecificDimension=self.reference_dimension
                ),
            )
            self._sketch_entities = {}
            self.coordinates, self.point_indices, self.refs = [], {}, {}
            self.rows, self.relations, self.selected, self.equations = [], [], [], {}

        def point(self, xy):
            xy = tuple(xy)
            if xy == (0.0, 0.0):
                return None
            if xy not in self.point_indices:
                self.point_indices[xy] = len(self.coordinates)
                self.coordinates.extend(xy)
            return self.point_indices[xy]

        async def create_sketch(self, _plane):
            return ok()

        async def exit_sketch(self):
            return ok()

        async def add_circle(self, x, y, radius):
            entity = f"C{len(self._sketch_entities)}"
            self.refs[f"{entity}.center"] = self.point((x, y))
            index = len(self.coordinates)
            self.coordinates.append(radius)
            self._sketch_entities[entity] = SimpleNamespace(
                ConstructionGeometry=False, radius=index
            )
            return ok(entity)

        async def add_line(self, x0, y0, x1, y1):
            entity = f"L{len(self._sketch_entities)}"
            self.refs[f"{entity}.start"] = self.point((x0, y0))
            self.refs[f"{entity}.end"] = self.point((x1, y1))
            self._sketch_entities[entity] = SimpleNamespace(ConstructionGeometry=False)
            return ok(entity)

        async def add_sketch_constraint(self, first, second, kind):
            self.relations.append((first, second, kind))
            return ok()

        async def add_sketch_dimension(self, first, second, kind, value):
            self.rows.append(
                dict(first=first, second=second, kind=kind, value=value, driven=False)
            )
            return ok(f"D{len(self.rows)}")

        def reference_dimension(self, _x, _y, _z, dimension_type, _error):
            assert dimension_type == 12
            first, second = self.selected
            row = dict(
                first=first,
                second=second,
                kind="vertical_distance",
                value=0.0,
                driven=True,
            )
            self.rows.append(row)
            adapter = self

            class Dimension:
                DrivenState = 1

                @property
                def SystemValue(self):
                    a = adapter.xy(np.array(adapter.coordinates), first)
                    b = adapter.xy(np.array(adapter.coordinates), second)
                    return abs(a[1] - b[1]) / 1000.0

            return SimpleNamespace(
                Type2=12, GetDimension2=lambda _index: Dimension()
            ), 0

        def xy(self, values, ref):
            index = None if ref == "origin" else self.refs[ref]
            return np.zeros(2) if index is None else values[index : index + 2]

        def residual(self, values, edits):
            residuals = []
            targets = {
                row["name"]: edits.get(row["name"], row["value"]) for row in self.rows
            }
            for target, expression in self.equations.items():
                source = expression.strip('"').split("@")[0]
                targets[target.split("@")[0]] = targets[source]
            for row in self.rows:
                if row["driven"]:
                    continue
                target = targets[row["name"]]
                if row["kind"] == "diameter":
                    actual = 2.0 * values[self._sketch_entities[row["first"]].radius]
                else:
                    axis = 0 if row["kind"] == "horizontal_distance" else 1
                    actual = abs(
                        self.xy(values, row["first"])[axis]
                        - self.xy(values, row["second"])[axis]
                    )
                residuals.append(actual - target)
            for first, second, kind in self.relations:
                if kind in ("horizontal", "vertical"):
                    delta = self.xy(values, f"{first}.end") - self.xy(
                        values, f"{first}.start"
                    )
                    residuals.append(delta[1 if kind == "horizontal" else 0])
                elif kind in ("horizontal_points", "vertical_points"):
                    axis = 1 if kind == "horizontal_points" else 0
                    residuals.append(
                        self.xy(values, first)[axis] - self.xy(values, second)[axis]
                    )
                elif kind == "midpoint":
                    middle = (
                        self.xy(values, f"{second}.start")
                        + self.xy(values, f"{second}.end")
                    ) / 2.0
                    residuals.extend(self.xy(values, first) - middle)
                elif kind == "coincident":
                    if second in self._sketch_entities:
                        circle = self._sketch_entities[second]
                        distance = np.linalg.norm(
                            self.xy(values, first) - self.xy(values, f"{second}.center")
                        )
                        residuals.append(distance - values[circle.radius])
                    else:
                        residuals.extend(
                            self.xy(values, first) - self.xy(values, second)
                        )
                else:
                    raise AssertionError(f"unmodelled sketch constraint: {kind}")
            return np.array(residuals)

    class RecordedDims(SketchDims):
        def apply(self, adapter, feature):
            assert len(self._rows) == len(adapter.rows)
            for index, (row, (name, _drive)) in enumerate(
                zip(adapter.rows, self._rows, strict=True)
            ):
                row["name"] = name or f"D{index}"
            return [
                (f"{name}@{feature}", drive)
                for name, drive in self._rows
                if name and drive
            ]

    async def nothing(*_args):
        pass

    async def equation(adapter, target, expression):
        adapter.equations[target] = expression

    def point_ref(adapter, ref):
        def select(append, data):
            assert append is True and data is None
            adapter.selected.append(ref)
            return True

        return SimpleNamespace(Select4=select)

    monkeypatch.setattr(part, "SketchDims", RecordedDims)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_resolve_entity_ref", point_ref)
    monkeypatch.setattr(part, "ensure_fully_defined", nothing)
    monkeypatch.setattr(part, "force_rebuild", nothing)
    monkeypatch.setattr(part, "drive_dimension", equation)
    for name in (
        "name_last_feature",
        "mark_dimensions_for_drawing",
        "blank_reference_sketches",
    ):
        monkeypatch.setattr(part, name, lambda *_args: None)
    adapter = Adapter()
    asyncio.run(part._supplier_nominal_stock_profile(adapter))
    assert all(
        entity.ConstructionGeometry is True
        for entity in adapter._sketch_entities.values()
    )
    overall = next(row for row in adapter.rows if row["name"] == "SupplierStockOverall")
    shank = next(row for row in adapter.rows if row["name"] == "SupplierStockShank")
    width = next(row for row in adapter.rows if row["name"] == "SupplierStockWireWidth")
    for od_delta, wire_delta, shank_delta in (
        (0, 0, 0),
        (2, 0, 0),
        (0, 1, 0),
        (2, 1, 5),
    ):
        eye_od = spec.SUPPLIER_NOMINAL_EYE_OD_MM + od_delta
        wire = spec.SUPPLIER_NOMINAL_WIRE_MM + wire_delta
        shank_length = spec.SUPPLIER_STOCK_SHANK_MM + shank_delta
        edits = {
            "SupplierNominalEyeOD": eye_od,
            "SupplierNominalWire": wire,
            "SupplierStockShank": shank_length,
        }
        solved = least_squares(
            adapter.residual,
            np.array(adapter.coordinates),
            args=(edits,),
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
        )
        assert np.max(np.abs(solved.fun)) < 1e-7
        assert np.linalg.matrix_rank(solved.jac, tol=1e-7) == len(adapter.coordinates)
        crown = adapter.xy(solved.x, overall["first"])
        root = adapter.xy(solved.x, shank["first"])
        end = adapter.xy(solved.x, overall["second"])
        assert crown == pytest.approx((0.0, eye_od / 2.0), abs=1e-7)
        assert root == pytest.approx((0.0, -eye_od / 2.0), abs=1e-7)
        assert end == pytest.approx((0.0, -eye_od / 2.0 - shank_length), abs=1e-7)
        assert crown[1] - end[1] == pytest.approx(eye_od + shank_length)
        a, b = (adapter.xy(solved.x, width[ref]) for ref in ("first", "second"))
        assert abs(a[0] - b[0]) == pytest.approx(wire)


@pytest.mark.parametrize("fault", [None, "empty_outline", "not_saved_hidden"])
def test_zero_body_source_is_revealed_rebuilt_and_centred_before_dimension_import(
    monkeypatch, fault
):
    """A dimension callback must not be what first makes a zero-body view fit."""
    events = []
    state = SimpleNamespace(
        revealed=False, rebuilt=False, measured=False, centred=False
    )
    ratio = drawing.STOCK_SCALE[0] / drawing.STOCK_SCALE[1]
    width = (
        (
            spec.SUPPLIER_STOCK_WIRE_CENTER_MM[0]
            + spec.SUPPLIER_NOMINAL_WIRE_MM / 2
            + spec.SUPPLIER_NOMINAL_EYE_OD_MM / 2
        )
        / 1000.0
        * ratio
    )
    height = spec.SUPPLIER_STOCK_OVERALL_MM / 1000.0 * ratio

    class StockView:
        ReferencedConfiguration = ""

        @property
        def Position(self):
            return drawing.STOCK_CENTER

        @Position.setter
        def Position(self, _value):
            assert state.measured and state.rebuilt
            state.centred = True
            events.append("centre")

        def UpdateViewDisplayGeometry(self):
            assert state.revealed and state.rebuilt
            events.append("display-update")
            return None

        def GetOutline(self):
            assert state.revealed and state.rebuilt
            state.measured = True
            events.append("outline")
            return (
                0.100,
                0.100,
                0.100 if fault == "empty_outline" else 0.100 + width,
                0.100 + height,
            )

    stock = StockView()
    sheet = SimpleNamespace(
        GetProperties2=lambda: (2, 2, 2.0, 1.0, False, 0.4318, 0.2794, False),
        GetZoneMargin=lambda _side: 0.0127,
    )

    def rebuild():
        assert state.revealed
        state.rebuilt = True
        events.append("rebuild")
        return True

    draw = SimpleNamespace(
        EditRebuild3=rebuild,
        ActivateView=lambda _name: False,
        GetEditSheet=lambda: True,
        ActiveDrawingView=None,
        GetCurrentSheet=lambda: sheet,
    )
    adapter = SimpleNamespace(currentModel=draw, _attempt=lambda call: call())

    def reveal(_adapter, view, owners, *, view_label):
        assert view is stock and tuple(owners) == (spec.SUPPLIER_STOCK_FEATURE,)
        if fault == "not_saved_hidden":
            return []
        state.revealed = True
        events.append("reveal")
        return list(owners)

    def project(_adapter, view, _points, **_kwargs):
        assert view is stock and state.measured and state.rebuilt
        events.append("project")
        return [(drawing.STOCK_CENTER[0] - 0.010, drawing.STOCK_CENTER[1] + 0.010, 0.0)]

    def curate(_adapter, view, *, keep, **_kwargs):
        assert view is stock and state.centred
        events.append("dimensions")
        return [
            SimpleNamespace(name=name, GetSpecificAnnotation=lambda: object())
            for name in keep
        ]

    placed_notes = []

    def note(_adapter, text, x, y):
        placed_notes.append((text, x, y))
        return object()

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: stock)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_show_hidden_owners", reveal)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", curate)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    monkeypatch.setattr(
        drawing, "supplier_reference_dimension", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(drawing, "add_note", note)
    if fault is not None:
        with pytest.raises(RuntimeError):
            drawing._supplier_stock_diagram(adapter)
        assert "dimensions" not in events
        return
    result_view, refs, notes = drawing._supplier_stock_diagram(adapter)
    assert result_view is stock and len(refs) == 4 and len(notes) == 2
    assert events == [
        "reveal",
        "rebuild",
        "display-update",
        "outline",
        "project",
        "centre",
        "rebuild",
        "dimensions",
    ]
    _title, _x, title_top = placed_notes[0]
    assert title_top < 0.2667
    assert stock.ReferencedConfiguration == spec.SUPPLIER_STOCK_CONFIGURATION
