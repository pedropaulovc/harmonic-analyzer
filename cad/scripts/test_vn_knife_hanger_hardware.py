"""Offline contracts for the cut hex bolt and new purchased #10 washer.

Recorded recipe calls are not native geometry proof; the parent owns the COM
build, source-dimension readback and exact-sheet machinist review.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _mcmaster_92314a253 as bolt_catalogue
import _stock_trim_drawing as trim_drawing
import build_vn_knife_hanger_stud as bolt_part
import build_vn_knife_hanger_washer as washer_part
import draw_vn_knife_hanger_stud as bolt_drawing
import draw_vn_knife_hanger_washer as washer_drawing
import vn_knife_hanger_stud_spec as bolt
import vn_knife_hanger_washer_spec as washer
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import TAP_DRILL_MM
from _mcmaster_92314a253 import DIMS as BOLT_DIMS
from _mcmaster_96659a104 import DIMS as WASHER_DIMS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92314A253 as bolt_recipe
from diagnostics import diag_build_96659A104 as washer_recipe

SCRIPTS = Path(__file__).resolve().parent


def test_catalogue_inputs_are_pure_and_isolated_from_diagnostics() -> None:
    for name, supplier in (
        ("vn_knife_hanger_stud_spec", "_mcmaster_92314a253"),
        ("vn_knife_hanger_washer_spec", "_mcmaster_96659a104"),
    ):
        paths = tuple(map(Path, module_deps_of(SCRIPTS / f"{name}.py")))
        assert supplier in {path.stem for path in paths}
        assert not any("diagnostics" in path.parts for path in paths)
        assert not any(path.stem.startswith("build_") for path in paths)
        assert not any(path.stem in {"_com", "_session"} for path in paths)
    assert bolt.CATALOG_URL == "https://www.mcmaster.com/92314A253/"
    assert washer.CATALOG_URL == "https://www.mcmaster.com/96659A104/"
    assert bolt.CATALOG_CHECKED_DATE == washer.CATALOG_CHECKED_DATE == "2026-10-13"
    assert bolt.CATALOG_STANDARD is None
    assert bolt.CATALOG_DIMENSIONAL_TOLERANCES is None
    assert washer.CATALOG_DIAMETER_TOLERANCES is None
    assert washer.CATALOG_STANDARD == "ASME B18.21.1"
    assert "Table 11" in washer.BOUND_SOURCE


def test_modified_bolt_nominals_and_inspection_are_separate() -> None:
    assert BOLT_DIMS.part_no == bolt.SKU == "92314A253"
    assert bolt.CATALOG_LENGTH == BOLT_DIMS.length == pytest.approx(50.8)
    assert bolt.LENGTH == bolt.UNDERHEAD_LEN == pytest.approx(45.70)
    assert bolt.LENGTH_BAND == (0.15, -0.15)
    assert bolt.LENGTH_MIN == pytest.approx(45.55)
    assert bolt.LENGTH_MAX == pytest.approx(45.85)
    assert bolt.THREAD == "#10-24" and bolt.THREAD_FIT == "UNC-2A"
    assert bolt.SHANK_DIA == BOLT_DIMS.major_dia == pytest.approx(4.826)
    assert (
        bolt.SHANK_DIA_MIN == bolt_catalogue.THREAD_MAJOR_MIN == pytest.approx(4.61772)
    )
    assert (
        bolt.SHANK_DIA_MAX == bolt_catalogue.THREAD_MAJOR_MAX == pytest.approx(4.8006)
    )
    assert bolt.SHANK_DIA_MIN < bolt.SHANK_DIA_MAX < bolt.SHANK_DIA
    assert "ASME B1.1" in bolt_catalogue.THREAD_MAJOR_SOURCE
    assert "external #10-24 class 2A" in bolt_catalogue.THREAD_MAJOR_SOURCE
    assert (
        "https://www.engineersedge.com/screw_threads_chart.htm"
        in bolt_catalogue.THREAD_MAJOR_SOURCE
    )
    assert bolt.PITCH == pytest.approx(25.4 / 24)
    assert bolt.HEAD_AF == BOLT_DIMS.head_af == pytest.approx(7.9375)
    assert bolt.HEAD_H == BOLT_DIMS.head_h == pytest.approx(3.175)
    assert bolt.THREAD_LENGTH == bolt.LENGTH
    assert bolt.THREAD_LENGTH_MIN == pytest.approx(10.62)
    assert bolt.INCOMPLETE_TIP_LEN_MAX == bolt.PITCH
    assert bolt.FULL_FORM_TAIL_MIN == pytest.approx(9.561666666666666)
    assert not hasattr(bolt, "HEAD_DIA")  # No socket-head compatibility alias.
    assert bolt.TIP_Y == 0.0
    assert bolt.HEAD_UNDERFACE_Y == bolt.LENGTH == pytest.approx(45.70)
    assert bolt.HEAD_TOP_Y == bolt.LENGTH + bolt.HEAD_H
    assert bolt.ENGAGEMENT_MIN_D == 1.5


def test_end_preparation_is_real_and_fits_inside_one_pitch() -> None:
    low = bolt.CHAMFER_WIDTH - bolt.CHAMFER_WIDTH_TOLERANCE
    high = bolt.CHAMFER_WIDTH + bolt.CHAMFER_WIDTH_TOLERANCE
    assert bolt.SHANK_DIA - 2 * low < TAP_DRILL_MM[bolt.THREAD]
    worst_axial = high / math.tan(
        math.radians(bolt.CHAMFER_ANGLE - bolt.CHAMFER_ANGLE_TOLERANCE)
    )
    assert 0 < worst_axial < bolt.INCOMPLETE_TIP_LEN_MAX
    assert bolt.CATALOG_LENGTH - bolt.LENGTH > bolt.PITCH


def test_washer_conforming_bounds_and_y_frame() -> None:
    assert washer.SKU == WASHER_DIMS.part_no == "96659A104"
    assert (washer.ID, washer.OD) == pytest.approx((5.5626, 12.7))
    assert (washer.ID_MIN, washer.ID_MAX) == pytest.approx((5.4356, 5.7658))
    assert (washer.OD_MIN, washer.OD_MAX) == pytest.approx((12.573, 13.081))
    assert (washer.THICKNESS_MIN, washer.THICKNESS_MAX) == pytest.approx(
        (0.9144, 1.651)
    )
    assert washer.THICKNESS == pytest.approx(1.2827)
    assert washer.THICKNESS == (washer.THICKNESS_MIN + washer.THICKNESS_MAX) / 2
    assert washer.OD_ID_RUNOUT_MAX == pytest.approx(0.3302)
    assert washer.BOTTOM_Y == 0.0 and washer.TOP_Y == washer.THICKNESS
    assert washer.ID_MIN > bolt.SHANK_DIA
    assert washer.washer_volume() == pytest.approx(
        math.pi / 4 * (washer.OD**2 - washer.ID**2) * washer.THICKNESS
    )


@pytest.mark.parametrize(
    ("part", "spec", "recipe", "number", "threaded"),
    [
        (bolt_part, bolt, bolt_recipe.build_92314A253, "MHA-VN-024", True),
        (washer_part, washer, washer_recipe.build_96659A104, "MHA-VN-060", False),
    ],
)
def test_stock_identity_recipe_and_normalized_frame(
    monkeypatch, part, spec, recipe, number, threaded
) -> None:
    stock = FASTENERS[part.PART_NAME]
    row = _config.parts(part.PART_NAME)
    assert stock is part.SPEC
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"] == part.MATERIAL == "AISI 304"
    assert row["number"] == number and row["process"] == "purchased"
    assert int(row["quantity"]) == 2
    seen = {}

    async def capture(_adapter, **kwargs):
        seen.update(kwargs)
        return {}

    monkeypatch.setattr(part, "build_stock_fastener", capture)
    asyncio.run(part.build(None))
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.transform.translation_mm == (0.0, 0.0, 0.0)
    assert component.transform.rotation_radians == (0.0, 0.0, 0.0)
    assert recipe_declaration(component.sku, component.author) == recipe_declaration(
        spec.SKU, recipe
    )
    assert recipe_declaration(component.sku, component.author).threaded is threaded
    assert seen["screw_axis_planes"] == ("Front Plane", "Right Plane")
    assert bool(seen.get("save_threaded_part")) is threaded


def test_complete_stock_is_positioned_before_production_cut(monkeypatch) -> None:
    seen = []

    async def capture(_adapter, dims):
        seen.append(dims)

    monkeypatch.setattr(bolt_recipe, "build_hex_head_screw", capture)
    asyncio.run(bolt_recipe.build_92314A253(None, bearing_y_mm=bolt.LENGTH))
    (dims,) = seen
    assert dims.length == bolt.CATALOG_LENGTH
    assert dims.underside_y == bolt.HEAD_UNDERFACE_Y
    assert dims.tip_y == pytest.approx(-5.10)
    assert dims.top_y == bolt.HEAD_TOP_Y
    # Retain a modeled runout; never infer full-form thread flush to the head.
    assert dims.runout_r > bolt.SHANK_DIA / 2


def test_washer_recipe_authors_an_annulus_not_a_disc(monkeypatch) -> None:
    seen = []

    class Recorder:
        async def create_sketch(self, plane):
            seen.append(("plane", plane))

        async def exit_sketch(self):
            pass

        async def create_extrusion(self, parameters):
            seen.append(("extrusion", parameters))

    async def circle(_adapter, x, y, radius, _label):
        seen.append(("circle", x, y, radius))

    async def defined(_adapter, label):
        seen.append(("defined", label))

    async def volume(_adapter, _label, expected, _tol):
        seen.append(("volume", expected))

    monkeypatch.setattr(washer_recipe, "check", lambda *_args: None)
    monkeypatch.setattr(washer_recipe, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(washer_recipe, "define_circle", circle)
    monkeypatch.setattr(washer_recipe, "ensure_fully_defined", defined)
    monkeypatch.setattr(washer_recipe, "volume_check", volume)
    monkeypatch.setattr(
        washer_recipe, "no_sketch_inference", lambda _adapter: contextlib.nullcontext()
    )
    asyncio.run(washer_recipe.build_96659A104(Recorder()))
    assert ("plane", "Top") in seen
    assert [entry[1:] for entry in seen if entry[0] == "circle"] == [
        (0.0, 0.0, washer.OD / 2),
        (0.0, 0.0, washer.ID / 2),
    ]
    (extrusion,) = [entry[1] for entry in seen if entry[0] == "extrusion"]
    assert extrusion.depth == washer.THICKNESS and not extrusion.both_directions
    assert ("volume", washer.washer_volume()) in seen
    assert ("defined", "washer annulus") in seen


def test_native_controls_are_owned_and_printed_without_precision_rewrites() -> None:
    assert (
        set(bolt_drawing.EXPECTED_CONTROLS)
        == set(bolt.DIMENSION_PRECISION)
        == {
            "CutLength",
            "ChamferWidth",
            "ChamferAngle",
            "ThreadLengthMin",
        }
    )
    assert set(bolt.DRAWING_DIMENSIONS) == {
        "StockTrimProfile",
        "StockDeburrProfile",
        "ThreadTailAcceptance",
    }
    assert set(bolt_drawing.FRONT_KEEP) == {"CutLength", "ThreadLengthMin"}
    assert set(bolt_drawing.DETAIL_KEEP) == {"ChamferWidth", "ChamferAngle"}
    assert bolt_drawing.SHEET.cut_end_y_mm == bolt.TIP_Y
    assert bolt_drawing.EXPECTED_CONTROLS["CutLength"] == pytest.approx(
        (0.04570, -0.00015, 0.00015)
    )
    assert bolt.DIMENSION_TOLERANCE_TYPES["CutLength"] == 4
    assert bolt.DIMENSION_PRECISION["CutLength"] == 2
    cut_callout = bolt.DIMENSION_CALLOUTS["CutLength"]
    assert "MATE: MHA-SM-002 KNIFE MOUNT" in cut_callout
    assert "THREAD ENGAGEMENT" in cut_callout and "TIP CLEARANCE" in cut_callout
    assert "\n" in cut_callout
    assert bolt.DIMENSION_TOLERANCE_TYPES["ThreadLengthMin"] == 5
    assert "1 PITCH MAX" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert "FULL FORM" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert "\n" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert all("\\n" not in text for text in bolt.DIMENSION_CALLOUTS.values())
    source = (SCRIPTS / "draw_vn_knife_hanger_stud.py").read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" not in source
    assert "_stock_trim_drawing" in source
    assert "SetPrecision3" not in source and "set_dimension_precision" not in source
    assert washer_drawing.SPEC is DRAWINGS_BY_NAME["vn_knife_hanger_washer"]
    assert "build_purchased_fastener_drawing" in washer_drawing.build.__code__.co_names
    for sheet, stem in (
        (bolt_drawing.SPEC, bolt_part.PART_NAME),
        (washer_drawing.SPEC, washer_part.PART_NAME),
    ):
        assert sheet.source.stem == sheet.artifact_stem == stem
        assert sheet.script.is_file()


@pytest.mark.parametrize("name", tuple(bolt_drawing.EXPECTED_CONTROLS))
@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "type", "band", "precision", "missing"]
)
def test_sheet_readback_refuses_lost_cut_or_inspection_control(
    monkeypatch, name, fault
):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    annotations = []
    for key, (nominal, lower, upper) in bolt_drawing.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=bolt.DIMENSION_TOLERANCE_TYPES[key],
            GetMinValue=lambda lower=lower: lower,
            GetMaxValue=lambda upper=upper: upper,
        )
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda key=key: bolt.DIMENSION_PRECISION[key],
        )
        annotations.append(
            SimpleNamespace(
                name=key,
                dimension=dimension,
                display=display,
                GetSpecificAnnotation=lambda display=display: display,
            )
        )
    target = next(annotation for annotation in annotations if annotation.name == name)
    if fault == "reference":
        target.dimension.DrivenState = 1
    elif fault == "nominal":
        target.dimension.SystemValue += 0.001
    elif fault == "type":
        target.dimension.Tolerance.Type = 0
    elif fault == "band":
        target.dimension.Tolerance.GetMaxValue = lambda: 0.01
    elif fault == "precision":
        target.display.GetPrimaryPrecision2 = lambda: bolt.DIMENSION_PRECISION[name] + 1
    elif fault == "missing":
        annotations.remove(target)

    def verify():
        trim_drawing.verify_machining_controls(
            None,
            annotations,
            expected=bolt_drawing.EXPECTED_CONTROLS,
            tolerance_types=bolt.DIMENSION_TOLERANCE_TYPES,
            precision=bolt.DIMENSION_PRECISION,
        )

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError):
            verify()


def test_modified_stock_route_is_complete_not_the_old_socket_recipe() -> None:
    row = _config.parts(bolt_part.PART_NAME)
    assert row["title"] == "Knife-Hanger Bolt"
    machining = row["machining_notes"]
    inspection = row["inspection_notes"]
    assert "PURCHASED HEX HEAD UNMODIFIED" in machining
    assert "CUT END AND UNDER-HEAD LENGTH AS DRAWN" in machining
    assert "NATIVE MIN THREAD TAIL IS FINISHED-PART ACCEPTANCE" in inspection
    assert "NOT A SUPPLIER GRADE" in inspection
    assert "ALL TAIL AFTER INCOMPLETE END THREAD MUST BE FULL FORM" in inspection
    assert not any(
        method in machining + inspection
        for method in ("TRIM ", "RESTORE ", "DEBURR ", "GAUGE ")
    )
    assert len(machining.splitlines()) + len(inspection.splitlines()) == 4
    assert "\n" in machining and "\n" in inspection
    assert "\\n" not in machining and "\\n" not in inspection
    assert not any(character.isdigit() for character in machining + inspection)
    assert "MHA-VN-060" in row["installation_notes"]
    assert "COUNTERBORE" not in row["installation_notes"]
    for module in ("build_vn_knife_hanger_stud", "draw_vn_knife_hanger_stud"):
        tree = ast.parse((SCRIPTS / f"{module}.py").read_text(encoding="utf-8"))
        imports = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }
        assert "diagnostics.diag_build_91251A157" not in imports
    assert FASTENERS["vn-cone-tip-block-screw"].skus == ("91251A108",)


def test_route_and_inspection_notes_are_consumed_native_part_properties(monkeypatch):
    stamped = {}
    linear = []
    angular = []
    native_min = []
    for name in (
        "clear_dimensions_for_drawing",
        "apply_drawing_precision",
        "mark_dimensions_for_drawing",
    ):
        monkeypatch.setattr(bolt_part, name, lambda *_args: None)
    monkeypatch.setattr(
        bolt_part,
        "set_dimension_symmetric_tolerance",
        lambda _adapter, feature, name, band: linear.append((feature, name, band)),
    )
    monkeypatch.setattr(
        bolt_part,
        "set_dimension_symmetric_angular_tolerance",
        lambda _adapter, feature, name, band: angular.append((feature, name, band)),
    )
    monkeypatch.setattr(bolt_part, "_early_bound", lambda value, _kind: value)
    tolerance = SimpleNamespace(Type=0, SetValues=lambda *_args: True)

    def named_dimension(_adapter, feature, name):
        native_min.append((feature, name))
        return None, SimpleNamespace(Tolerance=tolerance)

    monkeypatch.setattr(bolt_part, "_named_dimension", named_dimension)
    monkeypatch.setattr(
        bolt_part,
        "apply_drawing_properties",
        lambda _adapter, _name, properties: stamped.update(properties),
    )
    bolt_part._manufacturing_controls(None)
    row = _config.parts(bolt_part.PART_NAME)
    assert stamped["Machining Route"] == row["machining_notes"]
    assert stamped["Modified-Part Inspection"] == row["inspection_notes"]
    assert "Manufacturing Notes" not in stamped
    assert tolerance.Type == 5
    assert native_min == [("ThreadTailAcceptance", "ThreadLengthMin")]
    assert linear == [
        ("StockTrimProfile", "CutLength", 0.15),
        ("StockDeburrProfile", "ChamferWidth", 0.05),
    ]
    assert angular == [("StockDeburrProfile", "ChamferAngle", 1.0)]


def test_trim_recipe_emits_real_cut_and_deburr_with_native_length(monkeypatch):
    from solidworks_mcp.adapters.solidworks import sketch as sdk_sketch

    seen = []
    equations = []
    angle = SimpleNamespace(SystemValue=math.radians(bolt.CHAMFER_ANGLE), DrivenState=2)
    display = SimpleNamespace(GetDimension2=lambda _configuration: angle)

    class Recorder:
        def __init__(self):
            self.currentModel = SimpleNamespace(
                ClearSelection2=lambda _all: None,
                Extension=SimpleNamespace(
                    AddSpecificDimension=lambda *_args: (display, 0)
                ),
            )
            self.currentSketchManager = SimpleNamespace(
                CreatePoint=self.create_point,
                CreateCenterLine=lambda *_args: object(),
            )

        def create_point(self, *point):
            seen.append(("point", point))
            return object()

        def _register_sketch_entity(self, kind, _entity):
            return kind

        async def create_sketch(self, plane):
            seen.append(("plane", plane))

        async def exit_sketch(self):
            pass

        async def add_sketch_constraint(self, *_args):
            pass

        async def create_cut_extrude(self, parameters):
            seen.append(("cut", parameters))

        async def create_revolve(self, parameters):
            seen.append(("revolve", parameters))

    class Dimensions:
        def record(self, name):
            seen.append(("dimension_name", name))

        def apply(self, _adapter, feature):
            seen.append(("dimension_owner", feature))

    async def chain(_adapter, points, close=True):
        seen.append(("chain", points, close))
        return [f"Line{i}" for i in range(len(points) if close else len(points) - 1)]

    async def between(_adapter, _first, _second, kind, value, _label):
        seen.append(("dimension", kind, value))

    async def nothing(*_args):
        pass

    async def equation(_adapter, name, expression):
        equations.append((name, expression))

    async def anchor(_adapter, point, x, y, label):
        seen.append(("anchor", point, x, y, label))

    monkeypatch.setattr(bolt_part, "SketchDims", Dimensions)
    monkeypatch.setattr(bolt_part, "add_line_chain", chain)
    monkeypatch.setattr(bolt_part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(bolt_part, "dimension_between", between)
    monkeypatch.setattr(bolt_part, "ensure_fully_defined", nothing)
    monkeypatch.setattr(bolt_part, "drive_dimension", equation)
    monkeypatch.setattr(bolt_part, "check", lambda *_args: None)
    monkeypatch.setattr(bolt_part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        bolt_part,
        "name_last_feature",
        lambda _adapter, name: seen.append(("feature", name)),
    )
    monkeypatch.setattr(
        bolt_part, "no_sketch_inference", lambda _adapter: contextlib.nullcontext()
    )
    monkeypatch.setattr(sdk_sketch, "_select_sketch_entities", lambda *_args: None)
    asyncio.run(bolt_part._trim_stock(Recorder()))
    (cut,) = [entry[1] for entry in seen if entry[0] == "cut"]
    (deburr,) = [entry[1] for entry in seen if entry[0] == "revolve"]
    assert cut.both_directions and cut.depth > 2 * bolt.SHANK_DIA
    assert deburr.is_cut and deburr.angle == 360
    trim, prep = [entry[1] for entry in seen if entry[0] == "chain"]
    assert trim[2][1] == trim[3][1] == bolt.TIP_Y
    assert trim[0][1] < bolt.LENGTH - bolt.CATALOG_LENGTH
    assert [entry[1] for entry in seen if entry[0] == "point"] == [
        (0, bolt.LENGTH / 1000, 0),
        (0, bolt.LENGTH / 1000, 0),
    ]
    assert [entry[1:] for entry in seen if entry[0] == "anchor"] == [
        (
            "Line0.start",
            -bolt.SHANK_DIA,
            bolt.LENGTH - bolt.CATALOG_LENGTH - bolt.SHANK_DIA,
            "trim cutter margin",
        ),
        ("Point", 0.0, bolt.LENGTH, "bearing face"),
        ("Point", 0.0, bolt.LENGTH, "bearing face"),
    ]
    radius = bolt.SHANK_DIA / 2
    assert prep == [
        (radius - bolt.CHAMFER_WIDTH, 0.0),
        (radius + bolt.CHAMFER_WIDTH, 0.0),
        (radius + bolt.CHAMFER_WIDTH, bolt.CHAMFER_WIDTH),
        (radius, bolt.CHAMFER_WIDTH),
    ]
    assert ("dimension", "vertical_distance", bolt.LENGTH) in seen
    assert ("dimension_name", "CutLength") in seen
    assert ("dimension_owner", "StockTrimProfile") in seen
    assert ("feature", "StockTrim") in seen and ("feature", "StockDeburr") in seen
    assert ("dimension_name", "CutEndFromBearing") in seen
    assert equations == [
        ("BearingFaceY@StockDeburrProfile", '"BearingFaceY@StockTrimProfile"'),
        ("CutEndFromBearing@StockDeburrProfile", '"CutLength@StockTrimProfile"'),
    ]


def test_production_cut_positions_complete_stock_at_finished_head_pose(monkeypatch):
    seen = {}
    receipt = object()

    async def stock(_adapter, truth, **parameters):
        seen["stock"] = (truth, parameters)
        return receipt

    async def nothing(*_args):
        pass

    async def equation(_adapter, name, expression):
        seen["equation"] = (name, expression)

    body = SimpleNamespace(GetExtremePoint=lambda *_direction: (True, 0.0, 0.0, 0.0))
    model = SimpleNamespace(GetBodies2=lambda *_args: (body,))
    monkeypatch.setattr(bolt_part, "build_92314A253", stock)
    monkeypatch.setattr(bolt_part, "_trim_stock", nothing)
    monkeypatch.setattr(bolt_part, "_thread_tail_acceptance", nothing)
    monkeypatch.setattr(bolt_part, "_manufacturing_controls", lambda _adapter: None)
    monkeypatch.setattr(bolt_part, "force_rebuild", nothing)
    monkeypatch.setattr(bolt_part, "drive_dimension", equation)
    monkeypatch.setattr(bolt_part, "_early_bound", lambda value, _kind: value)
    result = asyncio.run(bolt_part._cut_to_length(SimpleNamespace(currentModel=model)))
    assert result is receipt
    assert seen["stock"] == (None, {"bearing_y_mm": 45.70})
    assert seen["equation"] == (
        "CutterRadius@StockDeburrProfile",
        '"StockMajorRadius@StockDeburrProfile" + "ChamferWidth@StockDeburrProfile"',
    )


@pytest.mark.parametrize("fault", [None, "callout", "link", "text"])
def test_sheet_prints_consumed_route_and_inspection_with_native_text_readback(
    monkeypatch, tmp_path, fault
):
    source = tmp_path / "vn-knife-hanger-stud.SLDPRT"
    source.touch()
    row = _config.parts(bolt_part.PART_NAME)
    properties = {
        "Machining Route": row["machining_notes"],
        "Modified-Part Inspection": row["inspection_notes"],
    }
    printed = []
    required = []
    views = []

    async def open_model(_path):
        pass

    async def finalize(*_args, **_kwargs):
        return {"drawing": "recorded"}

    def place_view(_adapter, _source, orientation, *_args, **_kwargs):
        views.append(orientation)
        return object()

    def read_properties(_model, names, *, required: tuple[str, ...]):
        properties.update({name: properties.get(name, name) for name in names})
        return properties

    def capture_properties(model, names, **kwargs):
        required.extend(kwargs["required"])
        return read_properties(model, names, **kwargs)

    def annotations(_adapter, _view, *, keep, **_kwargs):
        result = []
        for name in keep:
            display = SimpleNamespace(
                GetText=lambda _index, name=name: (
                    bolt.DIMENSION_CALLOUTS.get(name, "").replace("\n", "\r\n")
                    + (" WRONG" if fault == "callout" else "")
                )
            )
            result.append(
                SimpleNamespace(
                    name=name,
                    GetSpecificAnnotation=lambda display=display: display,
                )
            )
        return result

    def note(_adapter, name, x, y, **_kwargs):
        printed.append((name, x, y))
        text = properties[name].replace("\n", "\r\n")
        link = bolt_drawing.property_link(name)
        if fault == "link" and name == "Modified-Part Inspection":
            link = bolt_drawing.property_link("Wrong Property")
        if fault == "text" and name == "Machining Route":
            text += " WRONG"
        return SimpleNamespace(PropertyLinkedText=link, GetText=lambda: text)

    for name in (
        "check",
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "set_hidden_lines_visible",
        "verify_machining_controls",
        "set_dimension_callouts",
        "position_detail_label",
        "position_parent_detail_letter",
    ):
        monkeypatch.setattr(bolt_drawing, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bolt_drawing, "SOURCE", source)
    monkeypatch.setattr(bolt_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        bolt_drawing, "dimension_name", lambda _adapter, item: item.name
    )
    monkeypatch.setattr(bolt_drawing, "read_required_properties", capture_properties)
    monkeypatch.setattr(
        bolt_drawing,
        "new_project_drawing",
        lambda *_args, **_kwargs: (object(), object()),
    )
    monkeypatch.setattr(bolt_drawing, "place_view", place_view)
    monkeypatch.setattr(
        bolt_drawing,
        "end_detail",
        lambda *_args: SimpleNamespace(UpdateViewDisplayGeometry=lambda: None),
    )
    monkeypatch.setattr(bolt_drawing, "curate_view_dimensions", annotations)
    monkeypatch.setattr(bolt_drawing, "add_property_linked_note", note)
    monkeypatch.setattr(bolt_drawing, "finalize_drawing", finalize)
    adapter = SimpleNamespace(currentModel=object(), open_model=open_model)
    if fault is not None:
        with pytest.raises(RuntimeError, match="did not persist"):
            asyncio.run(bolt_drawing.build(adapter))
        return
    assert asyncio.run(bolt_drawing.build(adapter)) == {"drawing": "recorded"}
    assert "Machining Route" in required and "Modified-Part Inspection" in required
    assert "Manufacturing Notes" not in required
    assert views == ["*Front", "*Isometric"]
    assert [name for name, _x, _y in printed] == [
        "Supplier",
        "Supplier SKUs",
        "Stock Name",
        "Machining Route",
        "Modified-Part Inspection",
        "Isometric View Note",
    ]


@pytest.mark.parametrize(
    "recipe",
    (
        "build_fr_top_frame.py",
        "build_sm_knife_mount.py",
        "build_sm_summing_assembly.py",
        "build_ha_harmonic_analyzer_assembly.py",
        "build_vn_knife_hanger_stud.py",
        "draw_fr_top_frame.py",
        "draw_sm_knife_mount.py",
        "draw_vn_knife_hanger_stud.py",
        "diagnostics/diag_build_96659A104.py",
        "diagnostics/diag_mcmaster_hex_head.py",
    ),
)
def test_hanger_direct_adapter_calls_bind_to_the_vendored_sdk(recipe: str) -> None:
    """Reuse the source-only SDK census; never import the adapter or run COM."""
    from test_pd_transgear_adapter_contract import (
        _adapter_calls,
        _adapter_methods,
        _missing,
        _signature,
        _tree,
    )

    tree = _tree(SCRIPTS / recipe)
    calls = _adapter_calls(tree)
    assert calls, f"{recipe}: empty direct adapter-call census"
    assert not _missing(tree), (
        f"{recipe}: undeclared adapter calls: {sorted(_missing(tree))}"
    )
    methods = _adapter_methods()
    point_sizes = {}
    if any(
        isinstance(argument, ast.Starred) for call in calls for argument in call.args
    ):
        from build_fr_top_frame import slot_stadium_points

        producers = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "slot_stadium_points"
        ]
        assert len(producers) == 1, f"{recipe}: unknown coordinate-pack producer"
        target = producers[0].targets[0]
        assert isinstance(target, ast.Tuple)
        assert all(isinstance(name, ast.Name) for name in target.elts)
        # Bind the real two-dimensional producer for BOTH sketch orientations;
        # never assume that a starred name contributes one or three arguments.
        for along_u in (False, True):
            points = slot_stadium_points(
                (0.0, 0.0), along_u=along_u, half_flat=0.355, half_w=1.62
            )
            assert len(points) == len(target.elts)
            assert all(len(point) == 2 for point in points)
        point_sizes = {name.id: len(point) for name, point in zip(target.elts, points)}
    for call in calls:
        source, method = methods[call.func.attr]
        arguments = []
        for argument in call.args:
            if not isinstance(argument, ast.Starred):
                arguments.append(argument)
                continue
            assert isinstance(argument.value, ast.Name)
            assert argument.value.id in point_sizes
            arguments.extend(
                ast.Subscript(
                    value=argument.value, slice=ast.Constant(index), ctx=ast.Load()
                )
                for index in range(point_sizes[argument.value.id])
            )
        assert all(keyword.arg is not None for keyword in call.keywords)
        receiver = (
            []
            if any(
                isinstance(decorator, ast.Name) and decorator.id == "staticmethod"
                for decorator in method.decorator_list
            )
            else [call.func.value]
        )
        try:
            _signature(method).bind(
                *receiver,
                *arguments,
                **{keyword.arg: keyword.value for keyword in call.keywords},
            )
        except TypeError as error:
            pytest.fail(
                f"{recipe}:{call.lineno}: {call.func.attr} cannot bind "
                f"{source}:{method.lineno}: {error}"
            )
