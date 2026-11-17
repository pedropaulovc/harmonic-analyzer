"""Offline contracts for the cut hex bolt and new purchased #10 washer.

Recorded recipe calls are not native geometry proof; the parent owns the COM
build, source-dimension readback and exact-sheet machinist review.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
from dataclasses import replace
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_edge_dimensions as edge_dimensions
import _drawing_annotation_extent as annotation_extent
import _drawing_layout_audit as native_layout
import _drawing_physical_axial_dimension as physical_axial_dimension
import _drawing_serialized_note_identity as serialized_note_identity
import _supplier_dimensions as supplier_dimensions
import _mcmaster_92314a253 as bolt_catalogue
import _supplier_reference_text as reference_text
import _stock_trim_drawing as trim_drawing
import build_sm_summing_assembly as asm
import build_sm_vn_knife_hanger_stud as bolt_part
import build_sm_vn_knife_hanger_washer as washer_part
import draw_sm_vn_knife_hanger_stud as bolt_drawing
import sm_vn_knife_hanger_stud_spec as bolt
import sm_vn_knife_hanger_washer_spec as washer
from _buildgraph import module_deps_of
from _drawing_edges import ViewEdge, ViewEdges
from _fastener_catalog import FASTENERS
from _hole_spec import TAP_DRILL_MM
from _mcmaster_92314a253 import DIMS as BOLT_DIMS
from _mcmaster_96659a104 import DIMS as WASHER_DIMS
from _printed_tolerance import angular_band_deg, printed_band_mm
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_92314A253 as bolt_recipe
from diagnostics import diag_build_96659A104 as washer_recipe

SCRIPTS = Path(__file__).resolve().parent


def test_catalogue_inputs_are_pure_and_isolated_from_diagnostics() -> None:
    for name, supplier in (
        ("sm_vn_knife_hanger_stud_spec", "_mcmaster_92314a253"),
        ("sm_vn_knife_hanger_washer_spec", "_mcmaster_96659a104"),
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
    assert bolt.LENGTH == bolt.UNDERHEAD_LEN == pytest.approx(46.70)
    # The length is cut at MHA-SM-00 to the measured stack: no part band.
    for retired in ("LENGTH_BAND", "LENGTH_MIN", "LENGTH_MAX"):
        assert not hasattr(bolt, retired)
    assert bolt.THREAD == "#10-24" and bolt.THREAD_FIT == "UNC-2A"
    # The stock stays class 2A; the title block's thread row prints the class.
    assert bolt.PRINTED_THREAD == "#10-24 UNC"
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
    assert bolt.THREAD_LENGTH_MIN == pytest.approx(10.6172)  # .418 MIN
    assert bolt.INCOMPLETE_TIP_LEN_MAX == bolt.PITCH
    assert bolt.FULL_FORM_TAIL_MIN == pytest.approx(10.6172 - 25.4 / 24)
    assert not hasattr(bolt, "HEAD_DIA")  # No socket-head compatibility alias.
    assert bolt.TIP_Y == 0.0
    assert bolt.HEAD_UNDERFACE_Y == bolt.LENGTH == pytest.approx(46.70)
    assert bolt.HEAD_TOP_Y == bolt.LENGTH + bolt.HEAD_H
    assert bolt.ENGAGEMENT_MIN_D == 1.5


def test_title_block_chamfer_band_leads_into_the_tap_inside_one_pitch() -> None:
    # Native radial leg .03 under the title block's .XX +/-.01, at its
    # 45 +/-1 degrees.
    assert bolt.CHAMFER_WIDTH_TOLERANCE == printed_band_mm(2, unit="in") == pytest.approx(0.254)
    assert bolt.DIMENSION_PRECISION["ChamferWidth"] == 2
    assert (bolt.CHAMFER_WIDTH_MIN, bolt.CHAMFER_WIDTH_MAX) == pytest.approx(
        (0.508, 1.016)
    )
    assert bolt.CHAMFER_ANGLE_TOLERANCE == angular_band_deg() == 1.0
    steepest = math.radians(bolt.CHAMFER_ANGLE + bolt.CHAMFER_ANGLE_TOLERANCE)
    assert bolt.CHAMFER_AXIAL_MAX == pytest.approx(1.016 * math.tan(steepest))
    # Inside the one incomplete pitch the worst engagement already charges:
    # reach MIN 8.77 - 1 P = 7.7117 >= 1.5D = 7.239.
    assert bolt.CHAMFER_AXIAL_MAX <= bolt.INCOMPLETE_TIP_LEN_MAX == bolt.PITCH
    floor = bolt.ENGAGEMENT_MIN_D * bolt.SHANK_DIA
    assert floor == pytest.approx(7.239)
    tip_loss = max(bolt.CHAMFER_AXIAL_MAX, bolt.INCOMPLETE_TIP_LEN_MAX)
    assert asm.HANGER_REACH_MIN - tip_loss >= floor
    # The smallest leg still takes the cut thread start inside the mount's
    # #25 tap drill on the largest 2A major .1890 (tip flat 3.7846 < 3.797).
    assert bolt.SHANK_DIA_MAX == pytest.approx(4.8006)
    tap_drill = TAP_DRILL_MM[bolt.THREAD]
    assert bolt.SHANK_DIA_MAX - 2 * bolt.CHAMFER_WIDTH_MIN < tap_drill
    assert "1 PITCH MAX" in bolt_drawing.DIMENSION_CALLOUTS["ThreadLengthMin"]
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
    ("part", "spec", "recipe", "number", "threaded", "title_material"),
    [
        (
            bolt_part,
            bolt,
            bolt_recipe.build_92314A253,
            "MHA-SM-VN-52",
            True,
            "18-8 STAINLESS (AS SUPPLIED)",
        ),
        (
            washer_part,
            washer,
            washer_recipe.build_96659A104,
            "MHA-SM-VN-54",
            False,
            "AISI 304",
        ),
    ],
)
def test_stock_identity_recipe_and_normalized_frame(
    monkeypatch, part, spec, recipe, number, threaded, title_material
) -> None:
    stock = FASTENERS[part.PART_NAME]
    row = _config.parts(part.PART_NAME)
    assert stock is part.SPEC
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,)
    assert stock.stock_name == row["stock_name"]
    # The catalogue material is the native library stand-in for mass and
    # rendering; the title block prints the config row.
    assert stock.material == part.MATERIAL == "AISI 304"
    assert row["material"] == title_material
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
    assert dims.tip_y == pytest.approx(-4.10)
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


def _native_machining_control_annotations():
    annotations = []
    for key, (nominal, lower, upper) in bolt_drawing.EXPECTED_CONTROLS.items():
        tolerance = SimpleNamespace(
            Type=bolt.DIMENSION_TOLERANCE_TYPES[key],
            GetMinValue=lambda lower=lower: lower,
            GetMaxValue=lambda upper=upper: upper,
        )
        dimension = SimpleNamespace(
            Name=key, DrivenState=2, SystemValue=nominal, Tolerance=tolerance
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
    return annotations


def _verify_native_machining_controls(annotations):
    trim_drawing.verify_machining_controls(
        annotations,
        expected=bolt_drawing.EXPECTED_CONTROLS,
        tolerance_types=bolt.DIMENSION_TOLERANCE_TYPES,
        precision=bolt.DIMENSION_PRECISION,
    )


@pytest.mark.parametrize("name", tuple(bolt_drawing.EXPECTED_CONTROLS))
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "reference",
        "reference_prefix",
        "nominal",
        "type",
        "minimum",
        "band",
        "precision",
        "missing",
    ],
)
def test_sheet_readback_refuses_lost_cut_or_inspection_control(
    monkeypatch, name, fault
):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    target = next(annotation for annotation in annotations if annotation.name == name)
    if fault == "reference":
        target.dimension.DrivenState = 1
    elif fault == "reference_prefix":
        target.display.GetText = lambda _index: "("
    elif fault == "nominal":
        target.dimension.SystemValue += 0.001
    elif fault == "type":
        target.dimension.Tolerance.Type = 0
    elif fault == "minimum":
        lower = bolt_drawing.EXPECTED_CONTROLS[name][1]
        target.dimension.Tolerance.GetMinValue = lambda: lower - 0.001
    elif fault == "band":
        target.dimension.Tolerance.GetMaxValue = lambda: 0.01
    elif fault == "precision":
        target.display.GetPrimaryPrecision2 = lambda: bolt.DIMENSION_PRECISION[name] + 1
    elif fault == "missing":
        annotations.remove(target)

    def verify():
        _verify_native_machining_controls(annotations)

    if fault is None:
        verify()
    else:
        with pytest.raises(RuntimeError):
            verify()


@pytest.mark.parametrize("obsolete_api", ["absent", "raises"])
def test_machining_controls_use_native_names_without_the_obsolete_getter(
    monkeypatch, obsolete_api
):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()

    def obsolete_getter(*_args):
        pytest.fail("machining controls must not read obsolete GetDimension")

    for annotation in annotations:
        annotation.name = "NotTheNativeDimensionName"
        if obsolete_api == "raises":
            annotation.display.GetDimension = obsolete_getter
    _verify_native_machining_controls(annotations)


@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        " ",
        None,
        False,
        7,
        1.5,
        (),
        [],
        "UnknownNativeControl",
        "ChamferWidth@StockDeburrProfile",
    ],
)
def test_machining_controls_refuse_invalid_native_names(monkeypatch, bad_name):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    annotations[0].dimension.Name = bad_name
    with pytest.raises(RuntimeError):
        _verify_native_machining_controls(annotations)


def test_machining_controls_do_not_coerce_native_names_to_strings(monkeypatch):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    native_name = annotations[0].dimension.Name

    class StringLikeNativeName:
        def __str__(self):
            return native_name

    annotations[0].dimension.Name = StringLikeNativeName()
    with pytest.raises(RuntimeError):
        _verify_native_machining_controls(annotations)


@pytest.mark.parametrize("fault", ["extra", "duplicate", "missing"])
def test_machining_controls_require_the_exact_native_name_inventory(monkeypatch, fault):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    if fault == "missing":
        annotations.pop()
    else:
        extra = _native_machining_control_annotations()[0]
        if fault == "extra":
            extra.dimension.Name = "UnrequestedNativeControl"
        annotations.append(extra)
    with pytest.raises(RuntimeError):
        _verify_native_machining_controls(annotations)


@pytest.mark.parametrize("getter", ["dimension", "name"])
def test_machining_controls_preserve_native_getter_failures(monkeypatch, getter):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    failure = OSError("native machining-control getter failed")

    def failed_dimension(*_args):
        raise failure

    if getter == "dimension":
        annotations[0].display.GetDimension2 = failed_dimension
    else:

        class UnreadableNativeName:
            @property
            def Name(self):
                raise failure

        unreadable = UnreadableNativeName()
        annotations[0].display.GetDimension2 = lambda _configuration: unreadable
    with pytest.raises((OSError, RuntimeError)) as caught:
        _verify_native_machining_controls(annotations)
    assert caught.value is failure or caught.value.__cause__ is failure


@pytest.mark.parametrize("missing", ["display", "dimension"])
def test_machining_controls_refuse_a_missing_native_dimension(monkeypatch, missing):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    if missing == "display":
        annotations[0].GetSpecificAnnotation = lambda: None
    else:
        annotations[0].display.GetDimension2 = lambda _configuration: None
    with pytest.raises((AttributeError, RuntimeError)):
        _verify_native_machining_controls(annotations)


@pytest.mark.parametrize("first_is_valid", [True, False])
def test_machining_controls_read_name_and_values_from_the_same_native_object(
    monkeypatch, first_is_valid
):
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    annotations = _native_machining_control_annotations()
    _verify_native_machining_controls(annotations)
    first = annotations[0].dimension
    decoy = _native_machining_control_annotations()[0].dimension
    decoy.Name = "NotTheIdentifiedNativeControl"
    if first_is_valid:
        decoy.SystemValue += 0.001
    else:
        first.SystemValue += 0.001
    modern_dimensions = iter((first, decoy))
    annotations[0].display.GetDimension2 = (
        lambda _configuration: next(modern_dimensions)
    )
    if first_is_valid:
        _verify_native_machining_controls(annotations)
    else:
        with pytest.raises(RuntimeError):
            _verify_native_machining_controls(annotations)


def test_modified_stock_route_is_complete_not_the_old_socket_recipe() -> None:
    row = _config.parts(bolt_part.PART_NAME)
    assert row["title"] == "Knife-Hanger Bolt"
    note = row["purchased_note"]
    assert note == f"PURCHASED SCREW McMASTER {bolt.SKU}; HEAD UNMODIFIED"
    assert "machining_notes" not in row and "inspection_notes" not in row
    # One line that restates neither the title block nor a native number.
    assert "\n" not in note
    assert not any(character.isdigit() for character in note.replace(bolt.SKU, ""))
    for restated in ("STAINLESS", "AS SUPPLIED", "MIN THREAD TAIL", "2A"):
        assert restated not in note
    assert "MHA-SM-VN-54" in row["installation_notes"]
    assert "COUNTERBORE" not in row["installation_notes"]
    assert "SPOTFACE" not in row["installation_notes"]
    assert "FACED TOP" in row["installation_notes"]
    assert FASTENERS["dt-vn-cone-tip-block-screw"].skus == ("91251A108",)


def test_purchased_note_is_a_consumed_native_part_property(monkeypatch):
    stamped = {}
    tolerances = {}
    for name in (
        "clear_dimensions_for_drawing",
        "apply_drawing_precision",
        "mark_dimensions_for_drawing",
    ):
        monkeypatch.setattr(bolt_part, name, lambda *_args: None)
    assert not hasattr(bolt_part, "set_dimension_symmetric_angular_tolerance")
    monkeypatch.setattr(bolt_part, "_early_bound", lambda value, _kind: value)

    displays = {}

    def named_dimension(_adapter, feature, name):
        values = [0.0, 0.0]
        texts = {}

        def set_values(lower, upper):
            values[:] = [lower, upper]
            return True

        tolerance = SimpleNamespace(
            Type=-1,
            SetValues=set_values,
            GetMinValue=lambda: values[0],
            GetMaxValue=lambda: values[1],
        )
        tolerances[(feature, name)] = tolerance
        display = SimpleNamespace(
            SetText=texts.__setitem__,
            GetText=lambda index: texts.get(index, ""),
            ShowDimensionValue=True,
            texts=texts,
        )
        displays[(feature, name)] = display
        return display, SimpleNamespace(Tolerance=tolerance)

    monkeypatch.setattr(bolt_part, "_named_dimension", named_dimension)
    monkeypatch.setattr(
        bolt_part,
        "apply_drawing_properties",
        lambda _adapter, _name, properties: stamped.update(properties),
    )
    bolt_part._manufacturing_controls(None)
    row = _config.parts(bolt_part.PART_NAME)
    assert stamped["Purchased Screw Note"] == row["purchased_note"]
    assert stamped["Supplier Reference Title"] == bolt_drawing.SUPPLIER_STOCK_TITLE
    assert list(tolerances) == [
        ("StockTrimProfile", "CutLength"),
        ("StockDeburrProfile", "ChamferWidth"),
        ("StockDeburrProfile", "ChamferAngle"),
        ("ThreadTailAcceptance", "ThreadLengthMin"),
    ]
    # Cut at MHA-SM-00: the driving length prints as a bracketed reference.
    assert tolerances[("StockTrimProfile", "CutLength")].Type == 0
    assert displays[("StockTrimProfile", "CutLength")].texts == {1: "(", 2: ")"}
    # The leg and its angle keep the title block's bands natively.
    leg = tolerances[("StockDeburrProfile", "ChamferWidth")]
    assert leg.Type == 11
    assert (leg.GetMinValue(), leg.GetMaxValue()) == pytest.approx((-0.000254, 0.000254))
    angle = tolerances[("StockDeburrProfile", "ChamferAngle")]
    assert angle.Type == 11
    band = math.radians(angular_band_deg())
    assert (angle.GetMinValue(), angle.GetMaxValue()) == pytest.approx((-band, band))
    assert tolerances[("ThreadTailAcceptance", "ThreadLengthMin")].Type == 5


@pytest.mark.parametrize(
    "fault",
    [None, "callout", "link", "text", "checkpoint_missing", "checkpoint_duplicate",
     "capture_wrong_annotation", "capture_wrong_owner", "capture_wrong_configuration",
     "capture_wrong_path"],
)
def test_sheet_prints_purchased_note_and_chamfer_leader_with_native_readback(
    monkeypatch, tmp_path, fault
):
    source = tmp_path / "sm-vn-knife-hanger-stud.SLDPRT"
    source.touch()
    row = _config.parts(bolt_part.PART_NAME)
    properties = {
        "Purchased Screw Note": row["purchased_note"],
        "Supplier Reference Title": bolt_drawing.SUPPLIER_STOCK_TITLE,
    }
    printed = []
    required = []
    views = []
    curated = []
    offsets = []
    projected = []
    finalization = []
    case = _settled_stud_height_case(monkeypatch)
    _stud_paper_fixture(case, monkeypatch)
    case.front.name = "*Front"
    case.views[1].name = "*Isometric"
    references = case.references
    original_identities = bolt_drawing._supplier_reference_identities(case.adapter, references)
    case.native_doc_path = str(tmp_path / "unsaved-drawing.SLDDRW")
    case.model.GetPathName = lambda: case.native_doc_path
    case.model.GetType = lambda: 3
    case.model.GetTitle = lambda: Path(case.native_doc_path).name
    case.app.ActiveDoc = case.model
    case.app.GetOpenDocumentByName = lambda path: (
        case.model if path == case.native_doc_path else None
    )
    output_path = tmp_path / "saved-stud.SLDDRW"
    capture_calls = []
    shared_capture = bolt_drawing.capture_serialized_physical_axial_names

    def capture(adapter, captured_references, identities, configurations, **kwargs):
        capture_calls.append(dict(identities))
        assert identities == original_identities
        assert set(captured_references) == {"SupplierHeadHeight", "SupplierStockLength"}
        assert all(captured_references[name] is references[name] for name in captured_references)
        if fault != "capture_wrong_path":
            assert adapter.currentModel.GetPathName() == str(output_path.resolve())
        result = shared_capture(adapter, captured_references, identities, configurations, **kwargs)
        finalization.append("captured")
        return result

    def saved_reader(_adapter, identities, _configurations, *, serialized_full_names, purchased_note):
        assert identities == original_identities
        assert serialized_full_names == {
            "SupplierHeadHeight": case.native.FullName,
            "SupplierStockLength": case.stock_case.native.FullName,
        }
        assert all(serialized_full_names[name] != identities[name][0] for name in serialized_full_names)
        assert purchased_note["text"] == properties["Purchased Screw Note"]
        assert purchased_note["landing"] == case.note_landing
        assert purchased_note["name"] == case.note_name != "DetailItem347"
        finalization.append("saved physical proof")

    async def open_model(_path):
        pass

    async def finalize(_adapter, _outputs, *, settled_checks, checkpoint, **_kwargs):
        for settled in settled_checks:
            settled()
        assert case.native.FullName == original_identities["SupplierHeadHeight"][0]
        assert case.stock_case.native.FullName == original_identities["SupplierStockLength"][0]
        finalization.append("settled")
        checkpoint("before_native_save")
        case.native_doc_path = str(output_path.resolve())
        for display in case.displays.values():
            native = display.GetDimension2(0)
            native.FullName = f"{native.FullName}@SERIALIZED"
        case.note_name = "DetailItem347@ACTUAL-SERIALIZED"
        checkpoint("after_native_save")
        checkpoint("after_pdf_save")
        finalization.append("saved and strict-audited")
        if fault == "capture_wrong_annotation":
            impostor = SimpleNamespace(**vars(case.annotation))
            case.display.GetAnnotation = lambda: impostor
        elif fault == "capture_wrong_owner":
            case.annotation.Owner = case.views[1]
        elif fault == "capture_wrong_configuration":
            case.front.ReferencedConfiguration = "ForeignConfiguration"
        elif fault == "capture_wrong_path":
            case.model.GetPathName = lambda: str(tmp_path / "wrong.SLDDRW")
        if fault != "checkpoint_missing":
            checkpoint("before_drawing_close")
        if fault == "checkpoint_duplicate":
            checkpoint("before_drawing_close")
        finalization.append("finalized")
        checkpoint("after_drawing_close")
        return {"drawing": "recorded"}

    def place_view(_adapter, _source, orientation, *_args, **_kwargs):
        views.append((orientation, _kwargs["scale"]))
        return case.front if orientation == "*Front" else case.views[1]

    def read_properties(_model, names, *, required: tuple[str, ...]):
        properties.update({name: properties.get(name, name) for name in names})
        return properties

    def capture_properties(model, names, **kwargs):
        required.extend(kwargs["required"])
        return read_properties(model, names, **kwargs)

    def annotations(_adapter, view, *, keep, **_kwargs):
        curated.append((view.name, keep))
        result = []
        for name in keep:
            display = SimpleNamespace(
                GetText=lambda _index, name=name: (
                    bolt_drawing.DIMENSION_CALLOUTS.get(name, "").replace("\n", "\r\n")
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

    def project(_adapter, view, xyz, *, label):
        projected.append((view.name, xyz, label))
        return case.paper_project(_adapter, view, xyz, label=label)

    def callout(_adapter, view, *, property_name, edge_xy, note_xy):
        printed.append((view.name, property_name, edge_xy, note_xy))
        text = properties[property_name].replace("\n", "\r\n")
        link = bolt_drawing.property_link(property_name)
        if fault == "link":
            link = bolt_drawing.property_link("Wrong Property")
        if fault == "text":
            text += " WRONG"
        case.note.PropertyLinkedText = link
        case.note.text = text
        return case.note

    for name in (
        "check",
        "stamp_drawing_summary",
        "create_blank_drawing_sheets",
        "set_hidden_lines_removed",
        "verify_cut_length_reference",
        "verify_machining_controls",
        "set_dimension_callouts",
    ):
        monkeypatch.setattr(bolt_drawing, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bolt_drawing, "SOURCE", source)
    monkeypatch.setattr(bolt_drawing, "OUTPUTS", SimpleNamespace(slddrw=output_path))
    monkeypatch.setattr(bolt_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        bolt_drawing, "dimension_name", lambda _adapter, item: item.name
    )
    monkeypatch.setattr(bolt_drawing, "read_required_properties", capture_properties)
    monkeypatch.setattr(
        bolt_drawing,
        "new_project_drawing",
        lambda *_args, **_kwargs: (case.model, object()),
    )
    monkeypatch.setattr(bolt_drawing, "place_view", place_view)
    monkeypatch.setattr(bolt_drawing, "curate_view_dimensions", annotations)
    monkeypatch.setattr(
        bolt_drawing,
        "offset_dimension_text",
        lambda _adapter, _annotations, positions: offsets.append(positions),
    )
    monkeypatch.setattr(bolt_drawing, "model_point_in_view", project)
    monkeypatch.setattr(bolt_drawing, "add_property_linked_callout", callout)
    monkeypatch.setattr(bolt_drawing, "finalize_drawing", finalize)
    monkeypatch.setattr(
        bolt_drawing, "_add_supplier_references",
        lambda *_args: {name: annotation for name, annotation in references.items()
                       if name != "SupplierStockLength"},
    )
    monkeypatch.setattr(
        bolt_drawing,
        "_add_stock_reference",
        lambda _adapter: (case.stock_case.front, case.views[3], case.stock_case.annotation),
    )
    monkeypatch.setattr(bolt_drawing, "capture_serialized_physical_axial_names", capture)
    monkeypatch.setattr(bolt_drawing, "_assert_saved_physical_references", saved_reader)
    monkeypatch.setattr(bolt_drawing, "view_name", lambda _adapter, view: view.name)
    adapter = case.adapter
    adapter.open_model = open_model
    if fault is not None:
        expected = (
            "did not persist" if fault in ("callout", "link", "text")
            else "checkpoint.*not called" if fault == "checkpoint_missing"
            else "more than once" if fault == "checkpoint_duplicate"
            else "SupplierHeadHeight|serialized|identity"
        )
        with pytest.raises(RuntimeError, match=expected):
            asyncio.run(bolt_drawing.build(adapter))
        if fault == "checkpoint_missing":
            assert not capture_calls
        elif fault == "checkpoint_duplicate":
            assert len(capture_calls) == 1
        assert "saved physical proof" not in finalization
        return
    assert asyncio.run(bolt_drawing.build(adapter)) == {"drawing": "recorded"}
    assert finalization == [
        "settled", "saved and strict-audited", "captured", "finalized", "saved physical proof",
    ]
    assert len(capture_calls) == 1
    assert capture_calls[0] == original_identities
    assert "Purchased Screw Note" in required
    for retired in (
        "Machining Route",
        "Modified-Part Inspection",
        "Isometric View Note",
        "Supplier",
        "Stock Name",
    ):
        assert retired not in required
    # One scale: both views at the sheet's 2:1.
    assert views == [
        ("*Front", bolt_drawing.SHEET_SCALE),
        ("*Isometric", bolt_drawing.SHEET_SCALE),
    ]
    # Every control on the main view; the chamfer text leaves on a leader.
    assert curated == [("*Front", bolt_drawing.FRONT_KEEP)]
    assert offsets == [{"ChamferWidth": bolt_drawing.CHAMFER_TEXT_XY}]
    assert projected
    assert all(head[0] == "*Front" for head in projected)
    assert all(head[1] == pytest.approx(
        (bolt.HEAD_AF / 4000, bolt.HEAD_TOP_Y / 1000, 0.0)
    ) for head in projected)


def test_layout_keeps_text_off_the_part_border_and_title_block() -> None:
    """Offline placement relations; the native PDF proof owns text bounds."""
    scale = bolt_drawing._SHEET_PER_MODEL_MM
    center_x, center_y = bolt_drawing.FRONT_CENTER
    tip_y = bolt_drawing.TIP_SHEET_Y
    assert tip_y == pytest.approx(center_y - bolt.HEAD_TOP_Y / 2 * scale)
    head_left = center_x - bolt.HEAD_AF / 2 * scale
    shank_right = center_x + bolt.SHANK_DIA / 2 * scale
    keep = bolt_drawing.FRONT_KEEP
    # R3 measured ~2.57 mm per character of dimension text and ~5.75 mm per
    # line. The widest cut-length line (28 characters, ~72 mm) stays inside
    # the 12.7 mm border and 10 mm clear of the hex head.
    cut_half_width = 0.036
    assert keep["CutLength"][0] - cut_half_width > 0.0127
    assert keep["CutLength"][0] + cut_half_width < head_left - 0.010
    assert tip_y < keep["CutLength"][1] < tip_y + bolt.LENGTH * scale
    # The tail text (four lines, ~23 mm) sits wholly above the tail's top
    # extension line, right of the shank.
    tail_top = tip_y + bolt.THREAD_LENGTH_MIN * scale
    assert keep["ThreadLengthMin"][1] - 0.0115 > tail_top + 0.005
    assert keep["ThreadLengthMin"][0] > shank_right + 0.040
    # The chamfer dimension line under the tip, its text right and below.
    assert keep["ChamferWidth"][1] < tip_y
    text_x, text_y = bolt_drawing.CHAMFER_TEXT_XY
    assert text_x > shank_right + 0.035 and text_y < keep["ChamferWidth"][1]
    # The native 45 degrees sits in the open wedge right of the tip: on the
    # bisector from the chamfer vertex, clear of the tip-face extension line,
    # below the tail's top extension line and left of its dimension line.
    angle_x, angle_y = keep["ChamferAngle"]
    vertex_x = center_x + (bolt.SHANK_DIA / 2 - bolt.CHAMFER_WIDTH) * scale
    bisector = math.atan2(angle_y - tip_y, angle_x - vertex_x)
    assert bisector == pytest.approx(math.radians(bolt.CHAMFER_ANGLE / 2))
    assert angle_x > shank_right + 0.008
    assert tip_y + 0.004 < angle_y < tail_top - 0.004
    assert angle_x + 0.006 < keep["ThreadLengthMin"][0]
    # The ~20 mm HEAD AF line stands wholly left of the hex's left extension
    # line, off the border.
    af_x, _af_y = bolt_drawing.HEAD_AF_TEXT_XY
    assert af_x + 0.010 < head_left - 0.003
    assert af_x - 0.010 > 0.0127
    # The thread-major chord lies on its own dimension line (8.23 mm under
    # the text position), across the shank between the tail text and the
    # bearing face, and the three-row text stays under the bearing face.
    major_x, major_y = bolt_drawing.THREAD_MAJOR_TEXT_XY
    chord_y = tip_y + bolt.SUPPLIER_THREAD_MAJOR_Y * scale
    assert major_y - chord_y == pytest.approx(0.00823)
    assert bolt.SUPPLIER_REFERENCE_STARTS["SupplierThreadMajor"] == (
        -bolt.SHANK_DIA / 2, bolt.SUPPLIER_THREAD_MAJOR_Y
    )
    bearing_y = tip_y + bolt.LENGTH * scale
    assert keep["ThreadLengthMin"][1] + 0.015 < chord_y < bearing_y - 0.020
    assert major_y + 0.009 < bearing_y
    assert major_x > shank_right + 0.040
    # The purchased note above the head; nothing reaches the title block.
    head_top = tip_y + bolt.HEAD_TOP_Y * scale
    assert bolt_drawing.PURCHASED_NOTE_XY[1] > head_top + 0.015
    assert bolt_drawing.PURCHASED_NOTE_XY[1] < 0.2667 - 0.010
    assert text_y - 0.035 > 0.0127


@pytest.mark.parametrize(
    "recipe",
    (
        "build_fr_top_frame.py",
        "build_sm_knife_mount.py",
        "build_sm_summing_assembly.py",
        "build_ha_harmonic_analyzer_assembly.py",
        "build_sm_vn_knife_hanger_stud.py",
        "draw_fr_top_frame.py",
        "draw_sm_knife_mount.py",
        "draw_sm_vn_knife_hanger_stud.py",
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
        from build_sm_knife_mount import slot_stadium_points

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


def _stud_height_case(monkeypatch):
    """No-COM physical edges, native selection manager and measured dimension."""
    case = SimpleNamespace(
        fault=None, fault_index=1, selections=[], selection_log=[], selection_points=[],
        clears=[], creations=[], scans=[], events=[], projections=[],
    )
    front = SimpleNamespace(
        name="FinishedFront", ReferencedConfiguration="Default",
        GetDisplayMode2=lambda: 2, ScaleDecimal=2.0,
    )
    case.front = front
    bearing_point, top_point = bolt_drawing._head_height_points_mm()

    def selection_fault(name):
        return case.fault == name and len(case.selection_log) == case.fault_index

    def select(edge, append, data):
        case.selection_log.append((edge, append, data.View))
        if selection_fault("select"):
            return False
        if not append:
            case.selections.clear()
        actual = edge
        if selection_fault("wrong_selected"):
            actual = object()
        elif selection_fault("missing_selected"):
            actual = None
        elif selection_fault("duplicate_selected") and case.selections:
            actual = case.selections[0]
        case.selections.append(actual)
        return True

    case.select = select

    def edge(nearest):
        raw = SimpleNamespace(nearest=nearest, closest_calls=[])

        def closest(*xyz):
            raw.closest_calls.append(xyz)
            return raw.nearest

        raw.GetClosestPointOn = closest
        raw.Select4 = lambda append, data: select(raw, append, data)
        return raw

    case.edge = edge
    case.bearing = edge(tuple(value / 1000 for value in bearing_point) + (0.0, 0.0))
    case.top = edge(tuple(value / 1000 for value in top_point) + (0.0, 0.0))
    case.rear = edge((0.0, top_point[1] / 1000, -top_point[2] / 1000, 0.0, 0.0))
    case.bearing_item = ViewEdge(
        edge=case.bearing,
        line=((0.0, bolt.LENGTH, bolt.HEAD_AF / math.sqrt(3)),
              (bolt.HEAD_AF / 2, bolt.LENGTH, bolt.HEAD_AF / (2 * math.sqrt(3)))),
        circle=None, vertices=None,
    )
    case.top_item = ViewEdge(
        edge=case.top, line=None, vertices=None,
        circle=(0.0, bolt.HEAD_TOP_Y, 0.0, 0.0, 1.0, 0.0, bolt.HEAD_AF / 2),
    )
    case.rear_item = replace(case.top_item, edge=case.rear)
    case.crown_item = replace(
        case.top_item, edge=edge(None),
        circle=(0.0, bolt.HEAD_TOP_Y, 0.0, 0.0, 1.0, 0.0, 0.45 * bolt.HEAD_AF),
    )
    case.floor_item = replace(
        case.top_item, edge=edge(None),
        circle=(0.0, bolt.HEAD_TOP_Y - 0.1 * bolt.HEAD_H, 0.0,
                0.0, 1.0, 0.0, bolt.HEAD_AF / 2),
    )
    front.scan = ViewEdges(
        label="fixture physical stations",
        edges=(case.bearing_item, case.crown_item, case.floor_item,
               case.rear_item, case.top_item),
    )
    case.annotation = SimpleNamespace(
        attached=[case.bearing, case.top], kinds=(1, 1), count=2,
        dangling=False, Visible=1, OwnerType=0, Owner=front,
    )
    annotation = case.annotation
    annotation.GetAttachedEntities3 = lambda: annotation.attached
    annotation.GetAttachedEntityTypes = lambda: annotation.kinds
    annotation.GetAttachedEntityCount3 = lambda: annotation.count
    annotation.IsDangling = lambda: annotation.dangling
    station_ys = tuple(
        point[1] / 1000 * front.ScaleDecimal + 0.1
        for point in (bearing_point, top_point)
    )
    case.arrows = [
        (0.2, y, 0.0, 0.0, sign, 0.0, 0.001, 0.001, 0.0, 0.0, 0.0, 1.0)
        for y, sign in zip(station_ys, (1.0, -1.0), strict=True)
    ]
    case.display_data = SimpleNamespace(
        GetArrowHeadCount=lambda: len(case.arrows),
        GetArrowHeadAtIndex2=lambda index: case.arrows[index],
    )
    annotation.GetDisplayData = lambda: case.display_data
    native = SimpleNamespace(
        SystemValue=bolt.HEAD_H / 1000,
        FullName="SupplierHeadHeight@FinishedFront@Drawing",
        Tolerance=SimpleNamespace(Type=0),
    )
    settings = bolt.SUPPLIER_REFERENCE_DIMENSIONS["SupplierHeadHeight"]
    case.native = native
    case.display = SimpleNamespace(
        Type2=2, GetDimension2=lambda _index: native,
        GetAnnotation=lambda: annotation, ShowParenthesis=False, ShowDimensionValue=True,
        GetUseDocUnits=lambda: False,
        GetUnits=lambda: 3 if settings["units"] == "in" else 0,
        precision=settings["precision"], GetFractionBase=lambda: 1,
        GetOverride=lambda: False,
        GetText=lambda index: {
            1: "(", 2: f" {settings['units']})", 4: settings.get("callout", ""),
        }.get(index, ""),
    )
    case.display.GetPrimaryPrecision2 = lambda: case.display.precision
    case.result = case.display
    annotation.GetSpecificAnnotation = lambda: case.display
    manager = SimpleNamespace(
        CreateSelectData=lambda: SimpleNamespace(View=None),
        GetSelectedObjectCount2=lambda _mark: (
            len(case.selections) + (1 if selection_fault("selection_count") else 0)
        ),
        GetSelectedObjectType3=lambda _index, _mark: (
            46 if selection_fault("selection_type") else 1
        ),
        GetSelectedObject6=lambda index, _mark: case.selections[index - 1],
    )

    def set_point(*args):
        case.selection_points.append(args)
        return not (case.fault == "selection_point" and args[0] == case.fault_index)

    manager.SetSelectionPoint2 = set_point
    manager.GetSelectionPoint2 = lambda index, _mark: (
        (9.0, 9.0, 9.0)
        if case.fault == "selection_point_readback" and index == case.fault_index
        else case.selection_points[index - 1][2:]
    )

    def clear(value):
        case.clears.append(value)
        case.selections.clear()

    def create(*xyz):
        case.creations.append(xyz)
        if case.fault == "native_exception":
            raise RuntimeError("native insertion failed")
        return case.result

    case.model = SimpleNamespace(
        SelectionManager=manager, ClearSelection2=clear,
        ActivateView=lambda _name: case.fault != "activation",
        AddVerticalDimension2=create,
    )
    case.app = SimpleNamespace(IsSame=lambda first, second: int(first is second))
    case.adapter = SimpleNamespace(currentModel=case.model, swApp=case.app)

    def scan(view, *, label):
        case.scans.append((case.adapter.currentModel, view, view.scan))
        return view.scan

    def project(_adapter, view, points, *, label):
        case.projections.append((view, points, label))
        return [
            (point[0] * view.ScaleDecimal + getattr(view, "origin", (0.1, 0.1))[0],
             point[1] * view.ScaleDecimal + getattr(view, "origin", (0.1, 0.1))[1])
            for point in points
        ]

    monkeypatch.setattr(bolt_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(edge_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(physical_axial_dimension, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(physical_axial_dimension, "model_points_in_view", project)
    monkeypatch.setattr(
        physical_axial_dimension, "view_name", lambda _adapter, view: view.name
    )
    monkeypatch.setattr(
        edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, _kind, *_members: value,
    )
    monkeypatch.setattr(supplier_dimensions, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(bolt_drawing, "scan_view_edges", scan)
    monkeypatch.setattr(bolt_drawing, "model_points_in_view", project)
    monkeypatch.setattr(bolt_drawing, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(
        bolt_drawing._telemetry, "event",
        lambda name, **fields: case.events.append((name, fields)),
    )
    return case


def _settled_stud_height_case(monkeypatch):
    case = _stud_height_case(monkeypatch)
    front = case.front
    stock_case = _stud_stock_fixture(case)
    case.stock_case = stock_case
    stock, stock_iso = stock_case.front, SimpleNamespace(
        name="StockIso", ReferencedConfiguration=bolt.SUPPLIER_STOCK_CONFIGURATION,
        ScaleDecimal=2.0,
    )
    iso = SimpleNamespace(name="FinishedIso", ReferencedConfiguration="Default", ScaleDecimal=2.0)
    case.views = (front, iso, stock, stock_iso)
    displays = {
        "SupplierHeadHeight": case.display, "SupplierStockLength": stock_case.display,
    }
    case.displays = displays
    for name in bolt.SUPPLIER_REFERENCE_DIMENSIONS:
        if name in displays:
            continue
        owner = front
        native = SimpleNamespace(
            FullName=(f"{name}@SupplierReference@Drawing" if name == "SupplierThreadMajor"
                      else f"{name}@{owner.name}@Drawing"),
            Tolerance=SimpleNamespace(Type=0),
        )
        annotation = SimpleNamespace(
            Owner=owner, OwnerType=0, GetAttachedEntities3=lambda: (case.bearing,),
            GetAttachedEntityTypes=lambda: (1,),
        )
        display = SimpleNamespace(
            GetDimension2=lambda _index, native=native: native,
            GetAnnotation=lambda annotation=annotation: annotation,
        )
        annotation.GetSpecificAnnotation = lambda display=display: display
        displays[name] = display
    for name, display in displays.items():
        annotation = display.GetAnnotation()
        annotation.GetName = lambda name=name: f"native-annotation:{name}"
        display.GetNameForSelection = lambda name=name: f"native-selection:{name}"
    for view in case.views:
        view.ReferencedDocument = SimpleNamespace(
            GetPathName=lambda: str(bolt_drawing.SOURCE.resolve())
        )
    for first, second in ((front, iso), (stock, stock_iso)):
        first.GetNextView = lambda second=second: second
        second.GetNextView = lambda: None
        second.GetDisplayDimensions = lambda: ()
    front.GetDisplayDimensions = lambda: tuple(
        display for name, display in displays.items() if name != "SupplierStockLength"
    )
    stock.GetDisplayDimensions = lambda: (displays["SupplierStockLength"],)
    note = SimpleNamespace(
        PropertyLinkedText=bolt_drawing.property_link("Supplier Reference Title"),
        GetText=lambda: bolt_drawing.SUPPLIER_STOCK_TITLE,
    )
    caption = SimpleNamespace(
        OwnerType=1, GetType=lambda: 6, GetSpecificAnnotation=lambda: note,
    )
    sheet_views = (
        SimpleNamespace(
            name=bolt_drawing.SHEET_NAMES[0], ReferencedConfiguration="", ReferencedDocument=None,
            GetNextView=lambda: front, GetAnnotations=lambda: (),
            GetDisplayDimensions=lambda: None,
        ),
        SimpleNamespace(
            name=bolt_drawing.SHEET_NAMES[1], ReferencedConfiguration="", ReferencedDocument=None,
            GetNextView=lambda: stock, GetAnnotations=lambda: (caption,),
            GetDisplayDimensions=lambda: (),
        ),
    )
    case.sheet_index = 0

    def activate(name):
        case.sheet_index = bolt_drawing.SHEET_NAMES.index(name)
        return True

    case.model.ActivateSheet = activate
    case.model.GetFirstView = lambda: sheet_views[case.sheet_index]
    case.model.GetSheetNames = lambda: bolt_drawing.SHEET_NAMES
    case.model.GetViews = lambda: (
        (sheet_views[0], front, iso), (sheet_views[1], stock, stock_iso),
    )
    case.references = {name: display.GetAnnotation() for name, display in displays.items()}
    case.identities = bolt_drawing._supplier_reference_identities(case.adapter, case.references)
    case.configurations = {
        view.name: (bolt_drawing.SHEET_NAMES[0 if index < 2 else 1],
                    view.ReferencedConfiguration)
        for index, view in enumerate(case.views)
    }
    case.supplier_checks = []
    monkeypatch.setattr(
        bolt_drawing, "assert_supplier_reference_dimension",
        lambda _adapter, _display, **settings: case.supplier_checks.append(settings["label"]),
    )
    return case


def _install_stud_note_source_edges(case):
    """E8's original noncircular head boundary, with separate source/view bodies."""
    case.note_source = case.front.ReferencedDocument
    case.note_source_body, case.note_view_body = object(), object()
    case.note_canonical = {}
    case.note_source.GetType = lambda: 1
    case.note_source.GetBodies2 = lambda body_type, visible: (
        (case.note_source_body,) if (body_type, visible) == (0, False) else ()
    )
    case.note_source.ConfigurationManager = SimpleNamespace(
        ActiveConfiguration=SimpleNamespace(Name=case.front.ReferencedConfiguration),
    )
    case.note_source.Extension = SimpleNamespace(
        GetCorrespondingEntity2=lambda entity: case.note_canonical.get(id(entity)),
    )
    top = (bolt.HEAD_AF / 4000, bolt.HEAD_TOP_Y / 1000, math.sqrt(3) * bolt.HEAD_AF / 4000)
    end = (
        bolt.HEAD_AF / 2000,
        (bolt.HEAD_TOP_Y - (bolt.HEAD_AF / math.sqrt(3) - bolt.HEAD_AF / 2)
         / math.tan(math.radians(60))) / 1000,
        bolt.HEAD_AF / (2000 * math.sqrt(3)),
    )
    # Endpoint/U/sense values are grounded in E8; numeric kernel-kind values
    # below are controlled fake data, not an unobserved native Identity claim.
    case.note_trim = SimpleNamespace(
        StartPoint=top, EndPoint=end, UMinValue=0.002318718406006465,
        UMaxValue=0.004628534409111542, Sense=True, CurveType=3006,
    )

    def install(trim, kind, *, raw=None):
        raw = SimpleNamespace() if raw is None else raw
        curve = SimpleNamespace(kind=kind)
        curve.Identity = lambda: curve.kind
        curve.IsCircle = lambda: curve.kind == 3002
        curve.IsLine = lambda: curve.kind == 3001
        raw.curve = curve
        raw.trim = trim
        raw.GetCurve = lambda: raw.curve
        raw.GetCurveParams3 = lambda: raw.trim
        raw.GetBody = lambda: case.note_view_body
        if not hasattr(raw, "GetClosestPointOn"):
            raw.GetClosestPointOn = lambda _x, _y, _z: (*raw.trim.StartPoint, raw.trim.UMinValue, 0.0)
        canonical = SimpleNamespace(curve=curve, trim=trim, body=case.note_source_body)
        canonical.GetCurve = lambda: canonical.curve
        canonical.GetCurveParams3 = lambda: canonical.trim
        canonical.GetBody = lambda: canonical.body
        canonical.GetClosestPointOn = lambda _x, _y, _z: (
            *canonical.trim.StartPoint, canonical.trim.UMinValue, 0.0,
        )
        case.note_canonical[id(raw)] = canonical
        return raw, canonical

    case.install_note_edge = install
    case.note_edge, case.note_model_edge = install(case.note_trim, 3006)
    case.note_annotation.attached = case.note_edge
    case.front.scan = ViewEdges(
        case.front.scan.label,
        (*case.front.scan.edges, ViewEdge(edge=case.note_edge, line=None, circle=None, vertices=None)),
    )
    # A circular top trim is a DIFFERENT actual native edge, not rejected just
    # by its kind. It shares the original tangent endpoint and projected leader
    # position, so post-capture rejection must retain the full original trim.
    top_circle = SimpleNamespace(
        StartPoint=(-top[0], top[1], top[2]), EndPoint=top,
        UMinValue=5.759586531581287, UMaxValue=6.806784082777885,
        Sense=True, CurveType=3002,
    )
    install(top_circle, 3002, raw=case.top)
    case.note_projection_inputs = []
    case.front.ModelToViewTransform = object()

    def point(data):
        coordinates = tuple(float(value) for value in getattr(data, "value", data))
        case.note_projection_inputs.append(coordinates)

        def multiply(transform):
            assert transform is case.front.ModelToViewTransform
            x, y = case.paper_project(case.adapter, case.front, coordinates, label="native XYZ fake")
            return SimpleNamespace(ArrayData=(x, y, coordinates[2] * case.front.ScaleDecimal))

        return SimpleNamespace(MultiplyTransform=multiply)

    case.note_math_utility = SimpleNamespace(CreatePoint=point)
    case.app.GetMathUtility = lambda: case.note_math_utility
    x, y = case.paper_project(case.adapter, case.front, top, label="native original endpoint fake")
    case.note_landing = (x, y, top[2] * case.front.ScaleDecimal)
    case.note_data["lines"][0][7:10] = case.note_landing
    case.note_data["arrows"][0][0:3] = case.note_landing


def _stud_paper_fixture(case, monkeypatch):
    """Actual c356 FINISHED primitives through the real native dump/shelf boundary."""
    monkeypatch.setattr(native_layout, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(serialized_note_identity, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(serialized_note_identity, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(reference_text, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(annotation_extent, "_early_bound", lambda value, _kind: value)
    case.front.origin = (0.110, 0.1208028)
    case.front.GetOutline = lambda: (0.0964745, 0.1138592, 0.1235255, 0.2261408)
    case.views[1].GetOutline = lambda: (0.3223184, 0.0811521, 0.3576816, 0.1888479)
    case.views[1].GetAnnotations = lambda: ()
    case.views[3].GetAnnotations = lambda: ()
    case.stock_case.front.GetAnnotations = lambda: (case.stock_case.annotation,)
    case.stock_case.annotation.GetType = lambda: 4
    stock_caption = case.model.GetViews()[1][0].GetAnnotations()[0]
    stock_caption.GetName = lambda: "Supplier Reference Title"
    case.adapter._attempt = lambda fn: fn()
    case.sheet = SimpleNamespace(
        GetProperties2=lambda: (12, 0, 2, 1, 0, 0.4318, 0.2794, 0),
        GetZoneMargin=lambda _side: 0.0127,
    )
    case.model.GetCurrentSheet = lambda: case.sheet
    case.rebuilds = []
    case.model.EditRebuild3 = lambda: case.rebuilds.append(case.sheet_index) or True

    def project(_adapter, view, point, *, label):
        ox, oy = getattr(view, "origin", (0.1, 0.1))
        return (point[0] * view.ScaleDecimal + ox, point[1] * view.ScaleDecimal + oy)

    monkeypatch.setattr(bolt_drawing, "model_point_in_view", project)
    case.paper_project = project

    def row(text, x, y, width, z=0.0):
        return {"t": text, "pos": [x, y, z], "w": width, "h": 0.0035,
                "ref": 1, "ang": 0.0, "font": "Century Gothic", "ls": 0.001}

    def data(native):
        result = SimpleNamespace()
        for key, count, getter in (
            ("lines", "GetLineCount", "GetLineAtIndex2"),
            ("arrows", "GetArrowHeadCount", "GetArrowHeadAtIndex2"),
            ("arcs", "GetArcCount", "GetArcAtIndex2"),
            ("polylines", "GetPolyLineCount", "GetPolylineAtIndex2"),
            ("polygons", "GetPolygonCount", "GetPolygonAtIndex"),
            ("triangles", "GetTriangleCount", "GetTriangleAtIndex"),
            ("ellipses", "GetEllipseCount", "GetEllipseAtIndex2"),
        ):
            setattr(result, count, lambda key=key: len(native.get(key, ())))
            setattr(result, getter, lambda index, key=key: native[key][index])
        result.GetLineAtIndex3 = result.GetLineAtIndex2
        result.GetTextCount = lambda: len(native.get("texts", ()))
        for method, key in (
            ("GetTextAtIndex", "t"), ("GetTextPositionAtIndex", "pos"),
            ("GetTextHeightAtIndex", "h"), ("GetTextRefPositionAtIndex", "ref"),
            ("GetTextAngleAtIndex", "ang"), ("GetTextFontAtIndex", "font"),
            ("GetTextLineSpacingAtIndex", "ls"), ("GetTextInBoxWidthAtIndex", "w"),
        ):
            setattr(result, method, lambda index, key=key: native["texts"][index][key])
        return result

    def install(annotation, native, kind, position):
        annotation.position = list(position)
        annotation.native = native
        annotation.GetPosition = lambda: tuple(annotation.position)
        annotation.GetType = lambda: kind
        annotation.Visible = 1
        annotation.Layer = ""
        annotation.GetLeaderCount = lambda: 0
        annotation.GetDisplayData = lambda: data(native)

        def move(x, y, z):
            dx, dy = x - annotation.position[0], y - annotation.position[1]
            for item in native.get("texts", ()):
                item["pos"][0] += dx
                item["pos"][1] += dy
            annotation.position[:] = (x, y, z)
            return True

        annotation.SetPosition2 = move

    case.paper_install = install
    case.paper_row = row
    case.paper_data = {
        "lines": [
            [0, 0, 0, 0, 0.1189375, 0.2142028, 0, 0.219, 0.2142028, 0],
            [0, 0, 0, 0, 0.1149688, 0.2205528, 0, 0.219, 0.2205528, 0],
            [0, 0, 0, 0, 0.218, 0.2142028, 0, 0.218, 0.2078528, 0],
            [0, 0, 0, 0, 0.218, 0.2205528, 0, 0.218, 0.2269028, 0],
        ],
        "arrows": [
            [0.218, y, 0, 0, sign, 0, 0.003556, 0.000762, 0, 0, 0, 1]
            for y, sign in ((0.2142028, -1), (0.2205528, 1))
        ],
        "texts": [
            row("(0.125 in)", 0.2079253, 0.216, 0.0201493),
            row("HEAD HEIGHT", 0.2030497, 0.2104437, 0.0299007),
        ],
    }
    case.arrows = case.paper_data["arrows"]
    install(case.annotation, case.paper_data, 4, (0.218, 0.216, 0))
    case.display.OffsetText = False
    case.display.IsHoleCallout = lambda: False
    for name, rows in (
        ("SupplierHeadAF", [
            row("(", 0.1014104, 0.2552722, 0.0017208),
            row("5", 0.10545, 0.2578294, 0.0025861),
            row("16", 0.1041569, 0.2532011, 0.0051722),
            row('" in)', 0.1103549, 0.2552722, 0.0082347),
            row("HEAD AF", 0.1001903, 0.2476449, 0.0196194),
        ]),
        ("SupplierThreadMajor", [row("THREAD MAJOR NOMINAL", 0.140, 0.186, 0.060)]),
    ):
        display = case.displays[name]
        install(display.GetAnnotation(), {"texts": rows}, 4, (0.110, 0.255, 0))
        display.IsHoleCallout = lambda: False
    case.note_text = _config.parts(bolt_part.PART_NAME)["purchased_note"]
    z = 2 * math.sqrt(3) * bolt.HEAD_AF / 4000
    case.note_data = {
        "texts": [row(case.note_text, 0.130, 0.2354743, 0.141191, z)],
        "lines": [[0, 0, 0, 0, 0.1291411, 0.238506, z, 0.1139687, 0.2205528, z]],
        "arrows": [[0.1139687, 0.2205528, z, 0.6454763, 0.7637803, 0,
                    0.003556, 0.000762, 1, 0, 0, 1]],
    }
    case.note_name = "DetailItem347"
    note_annotation = SimpleNamespace(
        OwnerType=0, Owner=case.front, attached=case.top, dangling=False,
        GetName=lambda: case.note_name,
    )
    install(note_annotation, case.note_data, 6, (0.130, 0.240, z))
    move_note_text = note_annotation.SetPosition2

    def move_note(x, y, z):
        dx, dy = x - note_annotation.position[0], y - note_annotation.position[1]
        result = move_note_text(x, y, z)
        case.note_data["lines"][0][4] += dx
        case.note_data["lines"][0][5] += dy
        return result

    note_annotation.SetPosition2 = move_note
    note_annotation.GetAttachedEntityCount3 = lambda: 1
    note_annotation.GetAttachedEntityTypes = lambda: (1,)
    note_annotation.GetAttachedEntities3 = lambda: (note_annotation.attached,)
    note_annotation.IsDangling = lambda: note_annotation.dangling
    note_annotation.GetLeaderCount = lambda: 1
    note_annotation.GetLeaderPointsAtIndex = lambda _index: (
        note_annotation.position[0] - 0.0005098,
        note_annotation.position[1] - 0.0017837, z, *case.note_landing,
    )
    case.note_landing = (0.1139687, 0.2205528, z)
    case.note = SimpleNamespace(
        PropertyLinkedText=bolt_drawing.property_link("Purchased Screw Note"),
        text=case.note_text, GetAnnotation=lambda: case.note_annotation,
        # Deliberately includes the leader: this MUST NOT drive text placement.
        GetExtent=lambda: (0.1139143, 0.2207167, 0, 0.271182, 0.240256, 0),
        IsBomBalloon=lambda: False,
    )
    case.note.GetText = lambda: case.note.text
    note_annotation.GetSpecificAnnotation = lambda: case.note
    case.note_annotation = note_annotation
    case.foreign_annotations = []
    case.front.GetAnnotations = lambda: (
        *(display.GetAnnotation() for name, display in case.displays.items()
          if name != "SupplierStockLength"),
        case.note_annotation, *case.foreign_annotations,
    )
    _install_stud_note_source_edges(case)
    return case


@pytest.mark.parametrize(
    "name",
    ("_head_height_entities", "_add_physical_head_height",
     "_assert_physical_head_height", "_assert_saved_physical_references"),
)
def test_stud_physical_head_height_native_entrypoints_are_traced(name):
    assert hasattr(getattr(bolt_drawing, name), "__wrapped__")


def _stud_stock_fixture(case):
    """A second actual stock-view fixture; never borrow finished geometry/scale."""
    stock = SimpleNamespace(adapter=case.adapter)
    stock.front = front = SimpleNamespace(
        name="StockFront", ReferencedConfiguration=bolt.SUPPLIER_STOCK_CONFIGURATION,
        GetDisplayMode2=lambda: 2, ScaleDecimal=2.0,
        ReferencedDocument=SimpleNamespace(GetPathName=lambda: str(bolt_drawing.SOURCE.resolve())),
    )
    bearing_point = tuple(
        value / 1000 for value in bolt_drawing._head_height_points_mm()[0]
    )
    tip_y = bolt.LENGTH - bolt.CATALOG_LENGTH
    # Independent source expression, not a rounded expected radius.
    tip_radius = BOLT_DIMS.major_dia / 2 - BOLT_DIMS.pitch * 0.851
    tip_point = (0.0, tip_y / 1000, tip_radius / 1000)
    stock.bearing = case.edge((*bearing_point, 0.0, math.nan))
    stock.top = case.edge((*tip_point, 0.0, math.nan))
    stock.rear = case.edge((0.0, tip_y / 1000, -tip_radius / 1000, 0.0, math.nan))
    stock.bearing_item = replace(case.bearing_item, edge=stock.bearing)
    stock.top_item = ViewEdge(
        edge=stock.top, line=None, vertices=None,
        circle=(0.0, tip_y, 0.0, 0.0, 1.0, 0.0, tip_radius),
    )
    stock.rear_item = replace(stock.top_item, edge=stock.rear)
    front.scan = ViewEdges(
        "actual supplier stock stations",
        (stock.rear_item, stock.bearing_item, stock.top_item),
    )
    front.SelectEntity = lambda edge, append: case.select(
        edge, append, SimpleNamespace(View=front)
    )
    stock.annotation = annotation = SimpleNamespace(
        attached=[stock.bearing, stock.top], kinds=(1, 1), count=2,
        dangling=False, Visible=1, OwnerType=0, Owner=front,
    )
    annotation.GetAttachedEntities3 = lambda: annotation.attached
    annotation.GetAttachedEntityTypes = lambda: annotation.kinds
    annotation.GetAttachedEntityCount3 = lambda: annotation.count
    annotation.IsDangling = lambda: annotation.dangling
    stock.arrows = [
        (0.2, point[1] * front.ScaleDecimal + 0.1, 0.0, 0.0, sign, 0.0,
         0.001, 0.001, 0.0, 0.0, 0.0, 1.0)
        for point, sign in zip((bearing_point, tip_point), (1.0, -1.0), strict=True)
    ]
    stock.display_data = SimpleNamespace(
        GetArrowHeadCount=lambda: len(stock.arrows),
        GetArrowHeadAtIndex2=lambda index: stock.arrows[index],
    )
    annotation.GetDisplayData = lambda: stock.display_data
    stock.native = native = SimpleNamespace(
        FullName="SupplierStockLength@StockFront@Drawing",
        SystemValue=bolt.CATALOG_LENGTH / 1000, Tolerance=SimpleNamespace(Type=0),
    )
    settings = bolt.SUPPLIER_REFERENCE_DIMENSIONS["SupplierStockLength"]
    stock.display = display = SimpleNamespace(
        Type2=2, GetDimension2=lambda _index: native, GetAnnotation=lambda: annotation,
        ShowParenthesis=False, ShowDimensionValue=True, GetUseDocUnits=lambda: False,
        GetUnits=lambda: 3 if settings["units"] == "in" else 0,
        precision=settings["precision"], GetFractionBase=lambda: 1,
        GetOverride=lambda: False,
        GetText=lambda index: {
            1: "(", 2: f" {settings['units']})", 4: settings.get("callout", ""),
        }.get(index, ""),
    )
    display.GetPrimaryPrecision2 = lambda: display.precision
    annotation.GetSpecificAnnotation = lambda: display
    return stock


@pytest.mark.parametrize("name", ["_stock_length_stations", "_assert_physical_stock_length"])
def test_stud_stock_native_entrypoints_are_traced(name):
    assert hasattr(getattr(bolt_drawing, name), "__wrapped__")
