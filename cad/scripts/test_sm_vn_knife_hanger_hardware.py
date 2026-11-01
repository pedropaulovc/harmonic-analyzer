"""Offline contracts for the cut hex bolt and new purchased #10 washer.

Recorded recipe calls are not native geometry proof; the parent owns the COM
build, source-dimension readback and exact-sheet machinist review.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
from copy import deepcopy
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
import draw_sm_vn_knife_hanger_washer as washer_drawing
import sm_vn_knife_hanger_stud_spec as bolt
import sm_vn_knife_hanger_washer_spec as washer
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
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
    assert bolt.THREAD_LENGTH_MIN == pytest.approx(10.62)
    assert bolt.INCOMPLETE_TIP_LEN_MAX == bolt.PITCH
    assert bolt.FULL_FORM_TAIL_MIN == pytest.approx(9.561666666666666)
    assert not hasattr(bolt, "HEAD_DIA")  # No socket-head compatibility alias.
    assert bolt.TIP_Y == 0.0
    assert bolt.HEAD_UNDERFACE_Y == bolt.LENGTH == pytest.approx(46.70)
    assert bolt.HEAD_TOP_Y == bolt.LENGTH + bolt.HEAD_H
    assert bolt.ENGAGEMENT_MIN_D == 1.5


def test_chamfer_band_is_needed_for_full_thread_engagement() -> None:
    # Native radial leg 0.60 +/-0.05 at the title-block 45 +/-1 degrees.
    assert (bolt.CHAMFER_WIDTH_MIN, bolt.CHAMFER_WIDTH_MAX) == pytest.approx(
        (0.55, 0.65)
    )
    assert bolt.CHAMFER_ANGLE_TOLERANCE == angular_band_deg() == 1.0
    steepest = math.radians(bolt.CHAMFER_ANGLE + bolt.CHAMFER_ANGLE_TOLERANCE)
    assert bolt.CHAMFER_AXIAL_MAX == pytest.approx(0.65 * math.tan(steepest))
    assert bolt.CHAMFER_AXIAL_MAX == pytest.approx(0.67309, abs=5e-6)
    # Inside the one incomplete pitch the worst engagement already charges:
    # reach MIN 8.77 - 1 P = 7.7117 >= 1.5D = 7.239.
    assert bolt.CHAMFER_AXIAL_MAX <= bolt.INCOMPLETE_TIP_LEN_MAX == bolt.PITCH
    floor = bolt.ENGAGEMENT_MIN_D * bolt.SHANK_DIA
    assert floor == pytest.approx(7.239)
    tip_loss = max(bolt.CHAMFER_AXIAL_MAX, bolt.INCOMPLETE_TIP_LEN_MAX)
    assert asm.HANGER_REACH_MIN - tip_loss >= floor
    # The smallest leg still takes the cut thread start inside the mount's
    # #25 tap drill (tip flat 3.726 < 3.797).
    tap_drill = TAP_DRILL_MM[bolt.THREAD]
    assert bolt.SHANK_DIA - 2 * bolt.CHAMFER_WIDTH_MIN < tap_drill
    # Left to the title block's two-place row (0.60 +/-0.51) the same leg
    # fails both: 1.149 axial exceeds the one-pitch incomplete tip the tail
    # acceptance prints and the stack charges, and the 0.09 leg leaves the
    # feather start outside the tap drill.
    assert bolt.CHAMFER_WIDTH_TITLE_BLOCK_BAND == printed_band_mm(2) == 0.51
    assert bolt.CHAMFER_AXIAL_MAX_AT_TITLE_BLOCK == pytest.approx(
        1.11 * math.tan(steepest)
    )
    assert bolt.CHAMFER_AXIAL_MAX_AT_TITLE_BLOCK > bolt.INCOMPLETE_TIP_LEN_MAX
    assert "1 PITCH MAX" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    loose_low = bolt.CHAMFER_WIDTH - bolt.CHAMFER_WIDTH_TITLE_BLOCK_BAND
    assert bolt.SHANK_DIA - 2 * loose_low > tap_drill
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


def test_native_controls_are_owned_and_printed_without_precision_rewrites() -> None:
    assert (
        set(bolt_drawing.EXPECTED_CONTROLS) | {bolt_drawing.REFERENCE_CONTROL}
        == set(bolt.DIMENSION_PRECISION)
        == {
            "CutLength",
            "ChamferWidth",
            "ChamferAngle",
            "ThreadLengthMin",
        }
    )
    assert bolt_drawing.REFERENCE_CONTROL == "CutLength"
    assert "CutLength" not in bolt_drawing.EXPECTED_CONTROLS
    # The driving 45-degree ChamferAngle prints natively, whole degrees, with
    # its title-block band retained under swTolGeneral (no printed band).
    assert bolt.DIMENSION_TOLERANCE_TYPES["ChamferAngle"] == 11
    assert bolt.DIMENSION_PRECISION["ChamferAngle"] == 0
    assert bolt_drawing.EXPECTED_CONTROLS["ChamferAngle"] == pytest.approx(
        (math.radians(45.0), -math.radians(1.0), math.radians(1.0))
    )
    assert "ChamferAngle" not in bolt.DIMENSION_CALLOUTS
    assert set(bolt.DRAWING_DIMENSIONS) == {
        "StockTrimProfile",
        "StockDeburrProfile",
        "ThreadTailAcceptance",
    }
    assert set(bolt_drawing.FRONT_KEEP) == set(bolt_drawing.EXPECTED_CONTROLS) | {
        bolt_drawing.REFERENCE_CONTROL
    }
    assert bolt_drawing.EXPECTED_CONTROLS["ChamferWidth"] == pytest.approx(
        (0.00060, -0.00005, 0.00005)
    )
    assert bolt.DIMENSION_TOLERANCE_TYPES["ChamferWidth"] == 4
    # MHA-SM-00 cuts the length at assembly: the driving CutLength prints
    # as the bracketed reference nominal, no band, two places.
    assert bolt_drawing.REFERENCE_NOMINAL == pytest.approx(0.04670)
    assert bolt.DIMENSION_TOLERANCE_TYPES["CutLength"] == 0
    assert bolt.DIMENSION_PRECISION["CutLength"] == 2
    cut_callout = bolt.DIMENSION_CALLOUTS["CutLength"]
    assert cut_callout.splitlines() == [
        "UNDER HEAD TO FINISHED TIP",
        "CUT AT ASSEMBLY",
        "PER MHA-SM-00 STEP 4",
    ]
    for retired in ("THREAD ENGAGEMENT", "TIP CLEARANCE", "MATE:"):
        assert retired not in cut_callout
    assert bolt.DIMENSION_TOLERANCE_TYPES["ThreadLengthMin"] == 5
    assert "1 PITCH MAX" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert "FULL FORM" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert "\n" in bolt.DIMENSION_CALLOUTS["ThreadLengthMin"]
    assert all("\\n" not in text for text in bolt.DIMENSION_CALLOUTS.values())
    # The title block's thread row gives class 2A; the callout does not.
    assert bolt.DIMENSION_CALLOUTS["ThreadLengthMin"].startswith("#10-24 UNC ")
    assert all("2A" not in text for text in bolt.DIMENSION_CALLOUTS.values())
    chamfer_callout = bolt.DIMENSION_CALLOUTS["ChamferWidth"]
    # No literal angle: the 45 degrees is the native ChamferAngle's own text.
    reason = chamfer_callout.replace("MHA-SM-02", "")
    assert not any(character.isdigit() for character in reason)
    assert "DEG" not in chamfer_callout and "°" not in chamfer_callout
    assert "SETS FULL-THREAD ENGAGEMENT" in chamfer_callout
    assert "MHA-SM-02" in chamfer_callout
    source = (SCRIPTS / "draw_sm_vn_knife_hanger_stud.py").read_text(encoding="utf-8")
    assert "build_purchased_fastener_drawing" not in source
    assert "_stock_trim_drawing" in source
    assert "SetPrecision3" not in source and "set_dimension_precision" not in source
    # The chamfer prints on the main view: no detail, hidden lines or
    # per-view scale label.
    for retired in ("end_detail", "CreateDetailViewAt", "set_hidden_lines_visible"):
        assert retired not in source
    assert "Isometric View Note" not in source
    assert bolt_drawing.ISO_SCALE == bolt_drawing.SHEET_SCALE
    assert washer_drawing.SPEC is DRAWINGS_BY_NAME["sm_vn_knife_hanger_washer"]
    assert "build_purchased_fastener_drawing" in washer_drawing.build.__code__.co_names
    for sheet, stem in (
        (bolt_drawing.SPEC, bolt_part.PART_NAME),
        (washer_drawing.SPEC, washer_part.PART_NAME),
    ):
        assert sheet.source.stem == sheet.artifact_stem == stem
        assert sheet.script.is_file()


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


@pytest.mark.parametrize(
    "fault",
    [None, "driven", "nominal", "banded", "brackets", "precision", "missing", "twice"],
)
def test_sheet_readback_refuses_a_lost_reference_cut_length(monkeypatch, fault):
    monkeypatch.setattr(bolt_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        bolt_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    texts = {1: "(", 2: ")"}
    dimension = SimpleNamespace(
        DrivenState=2,
        SystemValue=bolt.LENGTH / 1000,
        Tolerance=SimpleNamespace(Type=0),
    )
    display = SimpleNamespace(
        GetDimension2=lambda _configuration: dimension,
        GetText=lambda index: texts.get(index, ""),
        GetPrimaryPrecision2=lambda: bolt.DIMENSION_PRECISION["CutLength"],
    )
    reference = SimpleNamespace(name="CutLength", GetSpecificAnnotation=lambda: display)
    banded = [SimpleNamespace(name=name) for name in bolt_drawing.EXPECTED_CONTROLS]
    annotations = [reference, *banded]
    if fault == "driven":
        dimension.DrivenState = 1
    elif fault == "nominal":
        dimension.SystemValue += 0.00015
    elif fault == "banded":
        dimension.Tolerance.Type = 4
    elif fault == "brackets":
        texts.clear()
    elif fault == "precision":
        display.GetPrimaryPrecision2 = lambda: 3
    elif fault == "missing":
        annotations.remove(reference)
    elif fault == "twice":
        annotations.append(reference)

    if fault is None:
        # Only the banded controls go on to the machining-control readback.
        assert bolt_drawing.verify_cut_length_reference(None, annotations) == banded
    else:
        with pytest.raises(RuntimeError, match="CutLength"):
            bolt_drawing.verify_cut_length_reference(None, annotations)


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
    washer_notes = _config.parts(washer_part.PART_NAME)["installation_notes"]
    assert "SPOTFACE" not in washer_notes
    assert "SEATS ON THE FACED CROSSBAR TOP" in washer_notes
    for module in ("build_sm_vn_knife_hanger_stud", "draw_sm_vn_knife_hanger_stud"):
        tree = ast.parse((SCRIPTS / f"{module}.py").read_text(encoding="utf-8"))
        imports = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }
        assert "diagnostics.diag_build_91251A157" not in imports
    assert FASTENERS["dt-vn-cone-tip-block-screw"].skus == ("91251A108",)


def test_purchased_note_is_a_consumed_native_part_property(monkeypatch):
    stamped = {}
    linear = []
    tolerances = {}
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
        ("StockDeburrProfile", "ChamferAngle"),
        ("ThreadTailAcceptance", "ThreadLengthMin"),
    ]
    # Cut at MHA-SM-00: the driving length prints as a bracketed reference.
    assert tolerances[("StockTrimProfile", "CutLength")].Type == 0
    assert displays[("StockTrimProfile", "CutLength")].texts == {1: "(", 2: ")"}
    angle = tolerances[("StockDeburrProfile", "ChamferAngle")]
    assert angle.Type == 11
    band = math.radians(angular_band_deg())
    assert (angle.GetMinValue(), angle.GetMaxValue()) == pytest.approx((-band, band))
    assert tolerances[("ThreadTailAcceptance", "ThreadLengthMin")].Type == 5
    assert linear == [("StockDeburrProfile", "ChamferWidth", 0.05)]


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing_profile",
        "wrong_profile",
        "profile_mark",
        "missing_axis",
        "axis_mark",
        "axis_replaces_profile",
        "edit_mode",
        "open_profile",
        "crosses_axis",
        "nonconstruction_axis",
        "profile_select_failed",
        "axis_select_failed",
        "select_data_missing",
    ],
)
def test_trim_recipe_emits_real_cut_and_deburr_with_native_length(monkeypatch, fault):
    """Exercise the vendored revolve at its API boundary, not a geometry stand-in."""
    from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus
    from solidworks_mcp.adapters.solidworks import features as sdk_features
    from solidworks_mcp.adapters.solidworks import sketch as sdk_sketch

    seen = []
    equations = []
    angle = SimpleNamespace(SystemValue=math.radians(bolt.CHAMFER_ANGLE), DrivenState=2)
    display = SimpleNamespace(GetDimension2=lambda _configuration: angle)

    class Recorder:
        def __init__(self):
            self.selection = []
            self.sketch_open = False
            self.profiles = []
            self._sketch_entities = {}
            self.constants = {"swEndCondBlind": 0}
            self.swApp = SimpleNamespace(RevisionNumber=lambda: "34.4.0")
            self.axis = SimpleNamespace(
                ConstructionGeometry=fault != "nonconstruction_axis",
                Select4=self.select_axis,
            )
            self.profile = SimpleNamespace(Select2=self.select_profile)
            self.sketch_manager = SimpleNamespace(
                CreatePoint=self.create_point,
                CreateCenterLine=self.create_axis,
            )
            self.currentModel = SimpleNamespace(
                ClearSelection2=self.clear_selection,
                SelectionManager=SimpleNamespace(CreateSelectData=self.select_data),
                FeatureManager=SimpleNamespace(FeatureRevolve2=self.native_revolve),
                Extension=SimpleNamespace(
                    AddSpecificDimension=lambda *_args: (display, 0)
                ),
            )
            self.currentSketchManager = None

        @staticmethod
        def result(data=None):
            return AdapterResult(status=AdapterResultStatus.SUCCESS, data=data)

        @staticmethod
        def _attempt(operation, default=None):
            try:
                return operation()
            except Exception:
                return default

        @staticmethod
        def _get_attr_or_call(value, name):
            member = getattr(value, name)
            return member() if callable(member) else member

        @staticmethod
        def _get_feature_id(feature):
            return feature.Name

        def _handle_com_operation(self, name, operation):
            try:
                return self.result(operation())
            except Exception as error:
                return AdapterResult(
                    status=AdapterResultStatus.ERROR, error=f"Error in {name}: {error}"
                )

        def clear_selection(self, _all):
            self.selection.clear()

        def select_data(self):
            return None if fault == "select_data_missing" else SimpleNamespace(Mark=0)

        def select_profile(self, append, mark):
            seen.append(("select_profile", append, mark))
            if fault == "profile_select_failed":
                return False
            if not append:
                self.selection.clear()
            if fault != "missing_profile":
                name = (
                    "StockTrimProfile"
                    if fault == "wrong_profile"
                    else "StockDeburrProfile"
                )
                self.selection.append((name, 1 if fault == "profile_mark" else mark))
            return True

        def select_axis(self, append, data):
            seen.append(("select_axis", append, data.Mark))
            if fault == "axis_select_failed":
                return False
            if not append or fault == "axis_replaces_profile":
                self.selection.clear()
            if fault != "missing_axis":
                self.selection.append(
                    (self.axis, 0 if fault == "axis_mark" else data.Mark)
                )
            return True

        def create_axis(self, *points):
            seen.append(("axis", points))
            self.axis_points = points
            return self.axis

        def create_point(self, *point):
            seen.append(("point", point))
            return object()

        def _register_sketch_entity(self, kind, entity):
            self._sketch_entities[kind] = entity
            return kind

        async def create_sketch(self, plane):
            assert not self.sketch_open
            self.sketch_open = True
            self.currentSketchManager = self.sketch_manager
            seen.append(("plane", plane))
            return self.result()

        async def exit_sketch(self):
            self.sketch_open = fault == "edit_mode" and len(self.profiles) == 2
            self.currentSketchManager = None
            # Match the vendored exit_sketch: IDs cannot select a closed sketch.
            self._sketch_entities.clear()
            self.selection.clear()
            return self.result()

        async def add_sketch_constraint(self, *_args):
            return self.result()

        async def create_cut_extrude(self, parameters):
            assert not self.sketch_open
            seen.append(("cut", parameters))
            return self.result()

        def native_revolve(self, *arguments):
            # Official FeatureRevolve2 signature and the actual SW 2026 adapter.
            assert len(arguments) == 20
            assert arguments[:8] == (True, True, False, True, False, False, 0, 0)
            assert arguments[8] == pytest.approx(2 * math.pi)
            assert arguments[9:] == (
                0.0,
                False,
                False,
                0.0,
                0.0,
                0,
                0.0,
                0.0,
                True,
                False,
                True,
            )
            seen.append(("native_revolve", tuple(self.selection)))
            segments = self.profiles[-1]
            closed = all(
                end == next_start
                for (_start, end), (next_start, _next_end) in zip(
                    segments, segments[1:] + segments[:1], strict=True
                )
            )
            ax, _ay, az, bx, _by, bz = self.axis_points
            if (
                self.sketch_open
                or self.selection != [("StockDeburrProfile", 0), (self.axis, 4)]
                or not closed
                or not self.axis.ConstructionGeometry
                or ax != bx
                or az != 0
                or bz != 0
                or any(
                    x <= ax * 1000 for start, end in segments for x, _y in (start, end)
                )
            ):
                return None
            return SimpleNamespace(Name="Cut-Revolve2")

        async def create_revolve(self, parameters):
            seen.append(("revolve", parameters))
            return sdk_features._create_revolve_impl(self, parameters)

    class Dimensions:
        def record(self, name):
            seen.append(("dimension_name", name))

        def apply(self, _adapter, feature):
            seen.append(("dimension_owner", feature))

    async def chain(adapter, points, close=True):
        seen.append(("chain", points, close))
        vertices = list(points) + ([points[0]] if close else [])
        segments = list(zip(vertices, vertices[1:]))
        if len(adapter.profiles) == 1:
            if fault == "open_profile":
                start, (x, y) = segments[-1]
                segments[-1] = (start, (x, y + bolt.CHAMFER_WIDTH))
            elif fault == "crosses_axis":
                _start, end = segments[0]
                segments[0] = ((-bolt.CHAMFER_WIDTH, 0.0), end)
                start, _end = segments[-1]
                segments[-1] = (start, segments[0][0])
        adapter.profiles.append(segments)
        ids = [f"Line{i}" for i in range(len(segments))]
        adapter._sketch_entities.update(zip(ids, segments))
        return ids

    async def between(_adapter, _first, _second, kind, value, _label):
        seen.append(("dimension", kind, value))

    async def nothing(*_args):
        pass

    async def equation(adapter, name, expression):
        equations.append((name, expression))
        seen.append(("equation", name))
        # Deliberately lose incidental exit-sketch selections during solving.
        # The recipe must establish its inputs afterwards, not assume retention.
        adapter.currentModel.ClearSelection2(True)

    async def anchor(_adapter, point, x, y, label):
        seen.append(("anchor", point, x, y, label))

    def select_angle(adapter, ids, mark):
        assert adapter.sketch_open and mark == 0 and ids == ["Line0", "Line3"]
        assert all(entity in adapter._sketch_entities for entity in ids)

    monkeypatch.setattr(bolt_part, "SketchDims", Dimensions)
    monkeypatch.setattr(bolt_part, "add_line_chain", chain)
    monkeypatch.setattr(bolt_part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(bolt_part, "dimension_between", between)
    monkeypatch.setattr(bolt_part, "ensure_fully_defined", nothing)
    monkeypatch.setattr(bolt_part, "drive_dimension", equation)
    monkeypatch.setattr(bolt_part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        bolt_part,
        "_feature_by_name",
        lambda adapter, name: adapter.profile if name == "StockDeburrProfile" else None,
    )
    monkeypatch.setattr(
        bolt_part,
        "name_last_feature",
        lambda _adapter, name: seen.append(("feature", name)),
    )
    monkeypatch.setattr(
        bolt_part, "no_sketch_inference", lambda _adapter: contextlib.nullcontext()
    )
    monkeypatch.setattr(sdk_sketch, "_select_sketch_entities", select_angle)
    if fault is not None:
        message = {
            "profile_select_failed": "cannot select stock deburr profile",
            "axis_select_failed": "cannot select stock deburr axis",
            "select_data_missing": "cannot create stock deburr axis selection",
        }.get(fault, "Failed to create revolve feature")
        with pytest.raises(RuntimeError, match=message):
            asyncio.run(bolt_part._trim_stock(Recorder()))
        assert ("feature", "StockDeburr") not in seen
        return
    asyncio.run(bolt_part._trim_stock(Recorder()))
    (cut,) = [entry[1] for entry in seen if entry[0] == "cut"]
    (deburr,) = [entry[1] for entry in seen if entry[0] == "revolve"]
    assert cut.both_directions and cut.depth > 2 * bolt.SHANK_DIA
    assert deburr.is_cut and deburr.angle == 360
    assert [entry[2] for entry in seen if entry[0] == "chain"] == [True, True]
    assert ("select_profile", False, 0) in seen
    assert ("select_axis", True, 4) in seen
    assert next(
        i for i, entry in enumerate(seen) if entry[0] == "select_profile"
    ) > max(i for i, entry in enumerate(seen) if entry[0] == "equation")
    assert [entry[1] for entry in seen if entry[0] == "axis"] == [
        (0, -bolt.CHAMFER_WIDTH / 1000, 0, 0, 2 * bolt.CHAMFER_WIDTH / 1000, 0)
    ]
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
    assert seen["stock"] == (None, {"bearing_y_mm": 46.70})
    assert seen["equation"] == (
        "CutterRadius@StockDeburrProfile",
        '"StockMajorRadius@StockDeburrProfile" + "ChamferWidth@StockDeburrProfile"',
    )


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


@pytest.mark.parametrize("along_u", [True, False])
def test_dowel_slot_stadium_closes_counter_clockwise(along_u: bool) -> None:
    """The knife mount's datum-C slot (moved from build_fr_top_frame, owner
    ruling 2026-10-24, T+H3) sketches as one closed CCW stadium."""
    import build_sm_knife_mount as part
    import sm_knife_mount_spec as knife_mount

    centre = (5.0, -7.0)
    half_flat, half_w = part.SLOT_FLAT / 2, knife_mount.SLOT_WIDTH / 2
    p1, p2, p3, p4, c_b, c_a = part.slot_stadium_points(
        centre, along_u=along_u, half_flat=half_flat, half_w=half_w
    )
    # Straight sides of the flat run, each end a half round about its centre.
    assert math.dist(p1, p2) == pytest.approx(2 * half_flat)
    assert math.dist(p3, p4) == pytest.approx(2 * half_flat)
    assert math.dist(c_a, c_b) == pytest.approx(2 * half_flat)
    for c, a, b in ((c_b, p2, p3), (c_a, p4, p1)):
        assert math.dist(c, a) == pytest.approx(half_w)
        assert math.dist(c, b) == pytest.approx(half_w)
        # add_arc sweeps counter-clockwise from a to b: the half round
        # bulges away from the slot's centre.
        sweep_mid = (c[0] + (b[1] - a[1]) / 2, c[1] - (b[0] - a[0]) / 2)
        assert math.dist(sweep_mid, centre) == pytest.approx(half_flat + half_w)
    # The sides run along the slot (u when along_u), counter-clockwise.
    axis = 0 if along_u else 1
    assert p1[1 - axis] == pytest.approx(p2[1 - axis])
    area2 = sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip((p1, p2, p3, p4), (p2, p3, p4, p1))
    )
    assert area2 > 0
    # On the dowel line (model x along u), end b is the slot's inner end and
    # end a its outer end, whose whole half round stands in air past the
    # widest printed block's -X face.
    _, _, _, _, inner, outer = (
        point[0]
        for point in part.slot_stadium_points(
            ((part.SLOT_INNER_X + part.SLOT_OUTER_X) / 2.0, 0.0),
            along_u=True,
            half_flat=half_flat,
            half_w=half_w,
        )
    )
    assert inner == pytest.approx(part.SLOT_INNER_X)
    assert outer == pytest.approx(part.SLOT_OUTER_X)
    assert outer + half_w < -(knife_mount.BLK_HALF_X + knife_mount.BLOCK_SIZE_TOL / 2.0)


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


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("axis_sign", [-1.0, 1.0])
def test_stud_head_height_names_actual_hex_and_frontmost_split_trim_arc(
    monkeypatch, reverse, axis_sign
):
    case = _stud_height_case(monkeypatch)
    top = replace(
        case.top_item,
        circle=(0.0, bolt.HEAD_TOP_Y, 0.0, 0.0, axis_sign, 0.0, bolt.HEAD_AF / 2),
    )
    edges = [case.rear_item, case.crown_item, top, case.floor_item, case.bearing_item]
    case.front.scan = ViewEdges("reordered", tuple(reversed(edges) if reverse else edges))
    actual = bolt_drawing._head_height_entities(case.adapter, case.front)
    assert actual[0] is case.bearing
    assert actual[1] is case.top
    point_m = tuple(value / 1000 for value in bolt_drawing._head_height_points_mm()[1])
    assert case.top.closest_calls == [point_m]
    assert case.rear.closest_calls == [point_m]
    assert not case.crown_item.edge.closest_calls
    assert not case.floor_item.edge.closest_calls
    geometry = next(fields for name, fields in case.events if name.endswith("_geometry"))
    assert geometry["bearing_matches"] == geometry["top_matches"] == 1
    assert geometry["circle_count"] == 4


@pytest.mark.parametrize(
    "fault",
    (
        "missing_bearing", "duplicate_bearing", "wrong_bearing_station",
        "one_wrong_endpoint", "infinite_bearing", "zero_length_bearing",
        "wrong_hex_side", "off_segment", "missing_top", "duplicate_top",
        "crown_only", "floor_only", "wrong_top_station", "wrong_top_center",
        "wrong_top_radius", "wrong_top_axis", "nearest_miss", "nearest_missing",
        "nearest_short", "nearest_nan", "same_entity", "not_hlr",
    ),
)
def test_stud_head_height_refuses_nonphysical_or_ambiguous_stations(monkeypatch, fault):
    case = _stud_height_case(monkeypatch)
    bearing, top = case.bearing_item, case.top_item
    edges = [bearing, top]
    if fault == "missing_bearing":
        edges = [top]
    elif fault == "duplicate_bearing":
        edges.append(replace(bearing, edge=case.edge(None)))
    elif fault in ("wrong_bearing_station", "one_wrong_endpoint"):
        points = [
            (x, y + (0.001 if index == 0 or fault == "wrong_bearing_station" else 0.0), z)
            for index, (x, y, z) in enumerate(bearing.line)
        ]
        edges[0] = replace(bearing, line=tuple(points))
    elif fault == "infinite_bearing":
        edges[0] = replace(bearing, line=((math.nan, bolt.LENGTH, 0.0), bearing.line[1]))
    elif fault == "zero_length_bearing":
        point = bolt_drawing._head_height_points_mm()[0]
        edges[0] = replace(bearing, line=(point, point))
    elif fault == "wrong_hex_side":
        edges[0] = replace(
            bearing, line=tuple((x, y, -z) for x, y, z in bearing.line)
        )
    elif fault == "off_segment":
        edges[0] = replace(
            bearing,
            line=((0.0, bolt.LENGTH, bolt.HEAD_AF / math.sqrt(3)),
                  (bolt.HEAD_AF / 8, bolt.LENGTH, 7 * bolt.HEAD_AF / (8 * math.sqrt(3)))),
        )
    elif fault == "missing_top":
        edges = [bearing]
    elif fault == "duplicate_top":
        edges.append(replace(top, edge=case.edge(case.top.nearest)))
    elif fault in ("crown_only", "floor_only"):
        edges[1] = case.crown_item if fault == "crown_only" else case.floor_item
    elif fault.startswith("wrong_top"):
        circle = list(top.circle)
        if fault == "wrong_top_station":
            circle[1] -= 0.001
        elif fault == "wrong_top_center":
            circle[0] += 0.001
        elif fault == "wrong_top_radius":
            circle[6] -= 0.001
        else:
            circle[3:6] = (1.0, 0.0, 0.0)
        edges[1] = replace(top, circle=tuple(circle))
    elif fault == "nearest_miss":
        case.top.nearest = (0.0, bolt.HEAD_TOP_Y / 1000, bolt.HEAD_AF / 2000 + 2e-8)
    elif fault == "nearest_missing":
        case.top.nearest = None
    elif fault == "nearest_short":
        case.top.nearest = (0.0, 0.0)
    elif fault == "nearest_nan":
        case.top.nearest = (math.nan, bolt.HEAD_TOP_Y / 1000, bolt.HEAD_AF / 2000)
    elif fault == "same_entity":
        edges[1] = replace(top, edge=case.bearing)
        case.bearing.nearest = case.top.nearest
    elif fault == "not_hlr":
        case.front.GetDisplayMode2 = lambda: 1
    case.front.scan = ViewEdges("bad physical stations", tuple(edges))
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._head_height_entities(case.adapter, case.front)
    assert not case.creations
    if fault != "not_hlr":
        assert any(name.endswith("_geometry") for name, _fields in case.events)


def test_stud_head_height_creates_native_vertical_dimension_with_strict_edge_readback(monkeypatch):
    case = _stud_height_case(monkeypatch)
    display = bolt_drawing._add_physical_head_height(
        case.adapter, case.front, (0.218, 0.216)
    )
    assert display is case.display
    assert case.selection_log == [
        (case.bearing, False, case.front), (case.top, True, case.front)
    ]
    assert case.creations == [(0.218, 0.216, 0.0)]
    assert case.clears == [True, True]
    assert not case.selections
    assert len(case.scans) == 1  # Creation reuses the just-resolved pair for native readback.
    projected = case.projections[0][1]
    assert projected == [
        tuple(value / 1000 for value in point)
        for point in bolt_drawing._head_height_points_mm()
    ]
    assert case.selection_points == [
        (index, -1, point[0] * case.front.ScaleDecimal + 0.1,
         point[1] * case.front.ScaleDecimal + 0.1, 0.0)
        for index, point in enumerate(projected, start=1)
    ]


@pytest.mark.parametrize("selection_index", [1, 2])
@pytest.mark.parametrize(
    "fault",
    ("activation", "select", "wrong_selected", "missing_selected",
     "selection_count", "selection_type", "selection_point", "null_creation",
     "native_exception"),
)
def test_stud_head_height_refuses_selection_and_creation_failures_without_fallback(
    monkeypatch, fault, selection_index
):
    case = _stud_height_case(monkeypatch)
    case.fault = fault
    case.fault_index = selection_index
    if fault == "null_creation":
        case.result = None
    with pytest.raises(RuntimeError):
        bolt_drawing._add_physical_head_height(case.adapter, case.front, (0.218, 0.216))
    assert case.clears == ([True] if fault == "activation" else [True, True])
    assert not case.selections
    assert len(case.creations) == (1 if fault in ("null_creation", "native_exception") else 0)


@pytest.mark.parametrize("phase", ["created", "settled"])
@pytest.mark.parametrize(
    "fault",
    ("value", "attachments", "kinds", "count", "extra", "missing",
     "dangling", "not_vertical", "vertical_type12", "missing_native", "owner",
     "owner_type", "owner_null", "owner_unknown", "kinds_extra", "attached_empty",
     "kinds_empty"),
)
def test_stud_head_height_proves_native_measurement_and_actual_attachments_at_both_phases(
    monkeypatch, phase, fault
):
    case = _stud_height_case(monkeypatch)
    if fault == "value":
        case.native.SystemValue -= 0.0001
    elif fault == "attachments":
        case.annotation.attached[1] = case.rear
    elif fault == "kinds":
        case.annotation.kinds = (1, 46)
    elif fault == "count":
        case.annotation.count = 1
    elif fault == "extra":
        case.annotation.attached.append(object())
    elif fault == "missing":
        case.annotation.attached[1] = None
    elif fault == "dangling":
        case.annotation.dangling = True
    elif fault == "not_vertical":
        case.display.Type2 = 11
    elif fault == "vertical_type12":
        case.display.Type2 = 12
    elif fault == "missing_native":
        case.display.GetDimension2 = lambda _index: None
    elif fault == "owner":
        case.annotation.Owner = object()
    elif fault == "owner_type":
        case.annotation.OwnerType = 1
    elif fault == "owner_null":
        case.annotation.Owner = None
    elif fault == "owner_unknown":
        case.app.IsSame = lambda first, second: (
            2 if first is case.front and second is case.front else int(first is second)
        )
    elif fault == "kinds_extra":
        case.annotation.kinds = (1, 1, 1)
    elif fault == "attached_empty":
        case.annotation.attached = None
    elif fault == "kinds_empty":
        case.annotation.kinds = None
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        if phase == "created":
            bolt_drawing._add_physical_head_height(case.adapter, case.front, (0.218, 0.216))
        else:
            bolt_drawing._assert_physical_head_height(case.adapter, case.front, case.display)


@pytest.mark.parametrize("missing", ["display", "annotation"])
def test_stud_head_height_missing_native_handles_have_precise_refusals(monkeypatch, missing):
    case = _stud_height_case(monkeypatch)
    display = case.display
    if missing == "display":
        display = None
    else:
        display.GetAnnotation = lambda: None
    with pytest.raises(RuntimeError, match="display dimension is null|has no annotation"):
        bolt_drawing._assert_physical_head_height(
            case.adapter, case.front, display, entities=(case.bearing, case.top)
        )


def test_stud_head_height_linear_native_vertical_proof_uses_exact_model_stations(monkeypatch):
    case = _stud_height_case(monkeypatch)
    assert bolt_drawing._assert_physical_head_height(
        case.adapter, case.front, case.display
    ) == pytest.approx(bolt.HEAD_H)
    assert case.display.Type2 == 2
    assert len(case.scans) == 1
    assert tuple(case.projections[0][1]) == tuple(
        tuple(value / 1000 for value in point)
        for point in bolt_drawing._head_height_points_mm()
    )
    assert any(
        name == "drawing.physical_axial_dimension_native_proof" for name, _ in case.events
    )
    # A reversed exact physical EDGE bijection remains valid.
    case.annotation.attached.reverse()
    assert bolt_drawing._assert_physical_head_height(
        case.adapter, case.front, case.display
    ) == pytest.approx(bolt.HEAD_H)
    assert len(case.scans) == 2


def test_stud_head_height_refusal_reports_canonical_native_metadata(monkeypatch):
    case = _stud_height_case(monkeypatch)
    case.display.Type2 = 12
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._assert_physical_head_height(
            case.adapter, case.front, case.display, entities=(case.bearing, case.top)
        )
    receipt = next(
        fields for name, fields in case.events
        if name == "drawing.physical_axial_dimension_native_refusal"
    )
    expected = {
        "type2": 12, "attached_count": 2, "attached_length": 2,
        "kinds_length": 2, "kinds": (1, 1), "attached_nulls": (False, False),
        "dangling": False, "owner_type": 0, "owner_null": False, "owner_same": 1,
    }
    assert {key: receipt[key] for key in expected} == expected


@pytest.mark.parametrize("getter", ["GetAnnotation", "GetAttachedEntityCount3", "GetDisplayData"])
def test_stud_head_height_native_errors_retain_cause_and_visible_stage(monkeypatch, getter):
    case = _stud_height_case(monkeypatch)
    failure = OSError("native read failed")

    def fail():
        raise failure

    target = case.display if getter == "GetAnnotation" else case.annotation
    setattr(target, getter, fail)
    with pytest.raises(RuntimeError, match="native read failed") as error:
        bolt_drawing._assert_physical_head_height(
            case.adapter, case.front, case.display, entities=(case.bearing, case.top)
        )
    assert error.value.__cause__ is failure
    receipt = next(
        fields for name, fields in case.events
        if name == "drawing.physical_axial_dimension_native_refusal"
    )
    assert receipt["failure_error_type"] == "OSError"
    assert receipt["failure_error"] == "native read failed"


_STUD_SPATIAL_FAULTS = (
    "type12", "missing_data", "arrow_count", "null_arrow", "short_arrow", "long_arrow",
    "nonfinite_arrow", "horizontal", "diagonal", "zero", "same_sign", "different_x",
    "tip_z", "translated", "wrong_span", "zero_scale", "nonfinite_scale",
    "wrong_scale", "projection", "projection_count", "nonfinite_projection",
    "attachment", "duplicate_attachment", "value", "null_value", "nonfinite_value",
)


def _corrupt_stud_native_proof(case, monkeypatch, fault):
    def change_arrow(index, slot, value):
        record = list(case.arrows[index])
        record[slot] = value
        case.arrows[index] = tuple(record)

    if fault == "type12":
        case.display.Type2 = 12
    elif fault == "missing_data":
        case.annotation.GetDisplayData = lambda: None
    elif fault == "arrow_count":
        case.arrows.pop()
    elif fault == "null_arrow":
        case.arrows[0] = None
    elif fault == "short_arrow":
        case.arrows[0] = case.arrows[0][:-1]
    elif fault == "long_arrow":
        case.arrows[0] = (*case.arrows[0], 0.0)
    elif fault == "nonfinite_arrow":
        change_arrow(0, 7, float("nan"))
    elif fault == "horizontal":
        for index, sign in enumerate((1.0, -1.0)):
            change_arrow(index, 3, sign)
            change_arrow(index, 4, 0.0)
    elif fault == "diagonal":
        change_arrow(0, 3, 0.1)
    elif fault == "zero":
        change_arrow(0, 4, 0.0)
    elif fault == "same_sign":
        change_arrow(1, 4, case.arrows[0][4])
    elif fault == "different_x":
        change_arrow(0, 0, case.arrows[0][0] + 0.001)
    elif fault == "tip_z":
        change_arrow(0, 2, 0.001)
    elif fault == "translated":
        for index in range(2):
            change_arrow(index, 1, case.arrows[index][1] + 0.001)
    elif fault == "wrong_span":
        change_arrow(1, 1, case.arrows[1][1] + 0.001)
    elif fault == "zero_scale":
        case.front.ScaleDecimal = 0.0
    elif fault == "nonfinite_scale":
        case.front.ScaleDecimal = float("nan")
    elif fault == "wrong_scale":
        case.front.ScaleDecimal = 3.0
    elif fault in ("projection", "projection_count", "nonfinite_projection"):
        original = physical_axial_dimension.model_points_in_view

        def project(*args, **kwargs):
            points = list(original(*args, **kwargs))
            if args[1] is not case.front:
                return points
            if fault == "projection":
                return [(x, y + 0.001) for x, y in points]
            if fault == "projection_count":
                return points[:1]
            return [(float("nan"), points[0][1]), points[1]]

        monkeypatch.setattr(physical_axial_dimension, "model_points_in_view", project)
    elif fault == "attachment":
        case.annotation.attached[1] = case.rear
    elif fault == "value":
        case.native.SystemValue -= 0.0001
    elif fault == "duplicate_attachment":
        case.annotation.attached[1] = case.bearing
    elif fault == "null_value":
        case.native.SystemValue = None
    elif fault == "nonfinite_value":
        case.native.SystemValue = float("nan")
    else:
        raise AssertionError(f"unknown native proof fault: {fault}")


@pytest.mark.parametrize("phase", ["created", "settled", "saved"])
@pytest.mark.parametrize("fault", _STUD_SPATIAL_FAULTS)
def test_stud_native_spatial_proof_refuses_corruption_at_every_consumer(
    monkeypatch, tmp_path, phase, fault
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    elif phase == "settled":
        case = _settled_stud_height_case(monkeypatch)
    else:
        case = _stud_height_case(monkeypatch)
    # Prove valid data first, then mutate it: no cached proof may survive settle/reopen.
    assert bolt_drawing._assert_physical_head_height(
        case.adapter, case.front, case.display
    ) == pytest.approx(bolt.HEAD_H)
    _corrupt_stud_native_proof(case, monkeypatch, fault)
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        if phase == "created":
            bolt_drawing._add_physical_head_height(
                case.adapter, case.front, (0.218, 0.216)
            )
        elif phase == "settled":
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )
        else:
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


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


@pytest.mark.parametrize("fault", [None, "value", "attachment", "station"])
def test_stud_settled_supplier_census_rescans_physical_head_height(monkeypatch, fault):
    case = _settled_stud_height_case(monkeypatch)
    if fault == "value":
        case.native.SystemValue -= 0.0001
    elif fault == "attachment":
        case.annotation.attached[1] = case.rear
    elif fault == "station":
        case.front.scan = ViewEdges("lost top station", (case.bearing_item, case.floor_item))
    if fault is None:
        bolt_drawing._assert_supplier_references(
            case.adapter, case.identities, case.configurations
        )
        assert len(case.scans) == 2
        assert set(case.supplier_checks) == set(bolt.SUPPLIER_REFERENCE_DIMENSIONS)
    else:
        with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )


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


def _stud_note_source_diagnostic_case(monkeypatch):
    """Separate native contexts; the diagnostic outputs are not acceptance fakes."""
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    case.source = case.front.ReferencedDocument
    case.source_body, case.view_body = object(), object()
    case.source.GetType = lambda: 1
    case.source.GetBodies2 = lambda body_type, visible: (
        (case.source_body,) if (body_type, visible) == (0, False) else ()
    )
    case.source.ConfigurationManager = SimpleNamespace(
        ActiveConfiguration=SimpleNamespace(Name="Default"),
    )
    case.model.Extension = SimpleNamespace(
        GetCorrespondingEntity2=lambda _entity: pytest.fail("reverse mapping receiver must be SOURCE"),
    )
    case.reverse, case.forward = {}, {}
    case.source.Extension = SimpleNamespace(
        GetCorrespondingEntity2=lambda entity: case.reverse.get(id(entity)),
    )
    case.front.GetCorrespondingEntity = lambda entity: case.forward.get(id(entity))
    case.model.SelectionManager.GetSelectedObjectsDrawingView2 = lambda _index, _mark: case.front
    # D1's observed census has five circles, with three identical top-circle
    # frames. Distinct trim data below are controlled native-shaped readbacks,
    # not a claim that D1 captured these currently-unobserved endpoint values.
    frame = (0.0, bolt.HEAD_TOP_Y, 0.0, 0.0, 1.0, 0.0, bolt.HEAD_AF / 2)
    circles = (
        frame, frame, frame,
        (0.0, 46.560428147091706, 0.0, 0.0, 1.0, 0.0, 2.413),
        (0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.813),
    )

    def install(raw, circle, index, body):
        x, y, z, nx, ny, nz, radius = circle
        angle = index * 0.4
        start = (radius * math.cos(angle) / 1000, y / 1000, radius * math.sin(angle) / 1000)
        end = (
            radius * math.cos(angle + 0.2) / 1000, y / 1000,
            radius * math.sin(angle + 0.2) / 1000,
        )
        curve = SimpleNamespace(
            IsCircle=lambda: True, IsLine=lambda: False,
            CircleParams=(x / 1000, y / 1000, z / 1000, nx, ny, nz, radius / 1000),
        )
        raw.GetBody = lambda: body
        raw.GetCurve = lambda: curve
        raw.GetCurveParams3 = lambda: SimpleNamespace(
            StartPoint=start, EndPoint=end, UMinValue=angle, UMaxValue=angle + 0.2, Sense=True,
        )
        raw.GetClosestPointOn = lambda x, y, z: (*start, angle, 0.0)
        return raw

    items = []
    case.canonical_edges, case.drawing_edges = [], []
    for index, circle in enumerate(circles):
        raw = install(SimpleNamespace(), circle, index, case.view_body)
        canonical = install(SimpleNamespace(), circle, index, case.source_body)
        drawing = install(SimpleNamespace(), circle, index, case.view_body)
        case.canonical_edges.append(canonical)
        case.drawing_edges.append(drawing)
        case.reverse[id(raw)] = case.reverse[id(drawing)] = canonical
        case.forward[id(raw)] = case.forward[id(canonical)] = drawing
        items.append(ViewEdge(edge=raw, circle=circle, line=None, vertices=None))
    case.front.scan = ViewEdges("D1-shaped note failure", (case.bearing_item, *items))
    case.note_annotation.attached = case.drawing_edges[0]
    case.diagnostic_candidates = items
    return case


def _refuse_stud_note_source_with_inventory(case):
    with pytest.raises(RuntimeError) as error:
        bolt_drawing._purchased_note_geometry(
            case.adapter, case.front, case.note, text=case.note_text,
        )
    assert str(error.value) == (
        "Purchased Screw Note: actual attached head-top edge is not unique in its source view"
    )
    return next(
        fields for name, fields in case.events
        if name == "drawing.stud_purchased_note_source_inventory"
    )


def test_stud_note_failure_records_all_raw_source_and_view_contexts_without_accepting_mapping(monkeypatch):
    case = _stud_note_source_diagnostic_case(monkeypatch)
    case.selections[:] = [case.note_annotation.attached]
    receipt = _refuse_stud_note_source_with_inventory(case)
    assert receipt["predicate_match_count"] == 0
    assert receipt["candidate_count"] == len(case.front.scan.edges)
    assert receipt["view_name"] == case.front.name
    assert receipt["view_configuration"] == receipt["source_active_configuration_name"] == "Default"
    assert receipt["source_path"] == str(bolt_drawing.SOURCE.resolve())
    assert receipt["source_document_type"] == 1
    assert receipt["current_selection_count"] == 1
    assert receipt["current_selection_inventory"][0]["same_view"] == 1
    assert receipt["current_selection_inventory"][0]["same_attached"] == 1
    assert receipt["native_leader_points_m"][-3:] == case.note_landing
    assert receipt["closest_point_queries_model_m"]["original_coordinate_pick"] == tuple(
        value / 1000 for value in bolt_drawing.HEAD_PICK_MM
    )
    candidates = receipt["candidates"]
    assert [row["candidate_index"] for row in candidates] == list(range(len(case.front.scan.edges)))
    assert all(row["raw"]["same_attached"] == 0 for row in candidates)
    circles = [row for row in candidates if row["scan_circle_mm"] is not None]
    assert [row["reverse_same_attached_reverse"] for row in circles] == [1, 0, 0, 0, 0]
    assert circles[0]["view_forward_reverse"]["same_attached"] == 1
    assert circles[0]["raw"]["source_body_comparisons"][0]["same"] == 0
    assert circles[0]["source_reverse"]["source_body_comparisons"][0]["same"] == 1
    assert len({row["raw"]["circle_params_m"] for row in circles[:3]}) == 1
    assert len({row["raw"]["trim_start_m"] for row in circles[:3]}) == 3
    assert [row["raw"]["trim_u_min"] for row in circles[:3]] == [0.0, 0.4, 0.8]
    assert all(row["raw"]["trim_sense"] is True for row in circles)
    assert all(
        set(row["raw"]["closest_points_m"]) == set(receipt["closest_point_queries_model_m"])
        for row in candidates
    )
    assert not case.rebuilds
    assert case.selections == [case.note_annotation.attached]


def test_stud_note_failure_inventory_distinguishes_duplicate_direct_native_matches(monkeypatch):
    case = _stud_note_source_diagnostic_case(monkeypatch)
    item = case.diagnostic_candidates[0]
    case.note_annotation.attached = item.edge
    case.front.scan = ViewEdges("duplicate direct native note edge", (*case.front.scan.edges, item))
    receipt = _refuse_stud_note_source_with_inventory(case)
    assert receipt["predicate_match_count"] == 2
    assert receipt["candidate_count"] == len(case.front.scan.edges)
    assert [row["candidate_index"] for row in receipt["candidates"]] == list(range(len(case.front.scan.edges)))
    assert sum(row["raw"]["same_attached"] == 1 for row in receipt["candidates"]) == 2


@pytest.mark.parametrize("native_state", [-1, 2])
def test_stud_note_unknown_direct_identity_is_observed_not_accepted_by_successful_mapping(
    monkeypatch, native_state,
):
    case = _stud_note_source_diagnostic_case(monkeypatch)
    original_same = case.app.IsSame
    case.app.IsSame = lambda left, right: (
        native_state
        if right is case.note_annotation.attached
        and any(left is item.edge for item in case.diagnostic_candidates)
        else original_same(left, right)
    )
    receipt = _refuse_stud_note_source_with_inventory(case)
    assert receipt["predicate_match_count"] == 0
    circles = [row for row in receipt["candidates"] if row["scan_circle_mm"] is not None]
    assert all(row["raw"]["same_attached"] == native_state for row in circles)
    assert circles[0]["view_forward_reverse"]["same_attached"] == 1


@pytest.mark.parametrize(
    "fault",
    ["reverse_null", "forward_null", "reverse_error", "forward_error", "curve_error",
     "trim_error", "body_error", "source_bodies_error", "body_same_error"],
)
def test_stud_note_diagnostic_nulls_and_native_getter_errors_never_mask_original_refusal(
    monkeypatch, fault,
):
    case = _stud_note_source_diagnostic_case(monkeypatch)
    cause = OSError(f"diagnostic {fault}")

    def fail(*_args):
        raise cause

    if fault == "reverse_null":
        case.source.Extension.GetCorrespondingEntity2 = lambda _entity: None
    elif fault == "forward_null":
        case.front.GetCorrespondingEntity = lambda _entity: None
    elif fault == "reverse_error":
        case.source.Extension.GetCorrespondingEntity2 = fail
    elif fault == "forward_error":
        case.front.GetCorrespondingEntity = fail
    elif fault == "curve_error":
        case.diagnostic_candidates[0].edge.GetCurve = fail
    elif fault == "trim_error":
        case.diagnostic_candidates[0].edge.GetCurveParams3 = fail
    elif fault == "body_error":
        case.diagnostic_candidates[0].edge.GetBody = fail
    elif fault == "source_bodies_error":
        case.source.GetBodies2 = fail
    elif fault == "body_same_error":
        original_same = case.app.IsSame

        def same(left, right):
            if left is case.view_body and right is case.source_body:
                raise cause
            return original_same(left, right)

        case.app.IsSame = same
    receipt = _refuse_stud_note_source_with_inventory(case)
    assert receipt["predicate_match_count"] == 0
    assert len(receipt["candidates"]) == len(case.front.scan.edges)
    if fault == "reverse_null":
        assert receipt["attached"]["source_reverse_null"] is True
        assert all(row["source_reverse_null"] is True for row in receipt["candidates"])
    elif fault == "forward_null":
        assert receipt["attached"]["source_reverse_null"] is False
        assert receipt["attached"]["view_forward_raw_null"] is True
        assert receipt["attached"]["view_forward_reverse_null"] is True
    else:
        # Check the original getter's readable evidence, not snapshot spelling
        # or a fabricated empty inventory standing in for inaccessible data.
        def errors(value):
            if isinstance(value, dict):
                yield from value.get("errors", ())
                for child in value.values():
                    yield from errors(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    yield from errors(child)

        assert any(
            error["type"] == "OSError" and error["error"] == str(cause)
            for error in errors(receipt)
        )
    assert not case.rebuilds


def test_stud_note_diagnostic_sink_failure_cannot_replace_original_native_guard(monkeypatch):
    case = _stud_note_source_diagnostic_case(monkeypatch)

    def fail(*_args, **_kwargs):
        raise OSError("diagnostic sink failed")

    monkeypatch.setattr(bolt_drawing._telemetry, "event", fail)
    with pytest.raises(RuntimeError, match="actual attached head-top edge is not unique"):
        bolt_drawing._purchased_note_geometry(
            case.adapter, case.front, case.note, text=case.note_text,
        )


def test_stud_note_unique_direct_identity_uses_source_proof_without_failure_inventory(monkeypatch):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)

    def unexpected(*_args, **_kwargs):
        pytest.fail("successful strict direct identity must not invoke failure inventory")

    monkeypatch.setattr(bolt_drawing, "_record_purchased_note_source_failure", unexpected)
    record, _box, landing = bolt_drawing._purchased_note_geometry(
        case.adapter, case.front, case.note, text=case.note_text,
    )
    assert record["physical_head_edge"]["start_m"] == case.note_trim.StartPoint
    assert landing == case.note_landing
    assert not any(name == "drawing.stud_purchased_note_source_inventory" for name, _ in case.events)


def test_stud_original_noncircular_note_uses_native_source_and_full_xyz_without_forward_requirement(monkeypatch):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)

    def forbidden(*_args):
        pytest.fail("forward correspondence is not a universal native acceptance predicate")

    case.front.GetCorrespondingEntity = forbidden
    record, _box, landing = bolt_drawing._purchased_note_geometry(
        case.adapter, case.front, case.note, text=case.note_text,
    )
    assert case.note_edge.GetCurve().IsCircle() is False
    assert case.note_edge.GetCurve().IsLine() is False
    assert record["physical_head_edge"]["start_m"] == case.note_trim.StartPoint
    assert record["physical_head_edge"]["end_m"] == case.note_trim.EndPoint
    assert case.note_projection_inputs[-1] == case.note_trim.StartPoint
    assert landing[2] == case.note_trim.StartPoint[2] * case.front.ScaleDecimal > 0
    assert landing == case.note_landing
    assert not case.rebuilds


@pytest.mark.parametrize(
    "fault",
    ["missing", "duplicate", "same_geometry_impostor", "inverse_null", "foreign_body",
     "null_body", "no_bodies", "duplicate_bodies", "wrong_source", "relative_source",
     "source_type", "source_configuration", "stock_configuration", "raw_trim",
     "missing_endpoint", "ambiguous_endpoint", "curve_null", "trim_null", "nonfinite_u",
     "reversed_u", "invalid_sense", "invalid_kind", "utility_null", "transform_null",
     "point_null", "transform_result_null",
     "projection_nonfinite", "projection_z", "leader_z"],
)
def test_stud_actual_noncircular_note_source_and_native_xyz_refuse_corruption(monkeypatch, fault):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    bolt_drawing._purchased_note_geometry(case.adapter, case.front, case.note, text=case.note_text)
    if fault == "missing":
        case.front.scan = ViewEdges(
            "missing original native note edge",
            tuple(item for item in case.front.scan.edges if item.edge is not case.note_edge),
        )
    elif fault == "duplicate":
        item = next(item for item in case.front.scan.edges if item.edge is case.note_edge)
        case.front.scan = ViewEdges("duplicate original native note edge", (*case.front.scan.edges, item))
    elif fault == "same_geometry_impostor":
        impostor, _canonical = case.install_note_edge(SimpleNamespace(**vars(case.note_trim)), 3006)
        case.front.scan = ViewEdges(
            "equal geometry is not original native identity",
            tuple(
                replace(item, edge=impostor) if item.edge is case.note_edge else item
                for item in case.front.scan.edges
            ),
        )
    elif fault == "inverse_null":
        case.note_source.Extension.GetCorrespondingEntity2 = lambda _entity: None
    elif fault == "foreign_body":
        case.note_model_edge.body = object()
    elif fault == "null_body":
        case.note_model_edge.body = None
    elif fault == "no_bodies":
        case.note_source.GetBodies2 = lambda _kind, _visible: ()
    elif fault == "duplicate_bodies":
        case.note_source.GetBodies2 = lambda _kind, _visible: (case.note_source_body, case.note_source_body)
    elif fault == "wrong_source":
        case.note_source.GetPathName = lambda: str(bolt_drawing.SOURCE.with_name("foreign.SLDPRT").resolve())
    elif fault == "relative_source":
        case.note_source.GetPathName = lambda: bolt_drawing.SOURCE.name
    elif fault == "source_type":
        case.note_source.GetType = lambda: 2
    elif fault == "source_configuration":
        case.note_source.ConfigurationManager.ActiveConfiguration.Name = "FOREIGN"
    elif fault == "stock_configuration":
        case.front.ReferencedConfiguration = bolt.SUPPLIER_STOCK_CONFIGURATION
        case.note_source.ConfigurationManager.ActiveConfiguration.Name = bolt.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "raw_trim":
        case.note_edge.trim = SimpleNamespace(**vars(case.note_trim))
        case.note_edge.trim.EndPoint = (case.note_trim.EndPoint[0] + 0.001, *case.note_trim.EndPoint[1:])
    elif fault == "missing_endpoint":
        case.note_trim.StartPoint = (case.note_trim.StartPoint[0] + 0.001, *case.note_trim.StartPoint[1:])
    elif fault == "ambiguous_endpoint":
        case.note_trim.EndPoint = case.note_trim.StartPoint
    elif fault == "curve_null":
        case.note_model_edge.curve = None
    elif fault == "trim_null":
        case.note_model_edge.trim = None
    elif fault == "nonfinite_u":
        case.note_trim.UMinValue = float("nan")
    elif fault == "reversed_u":
        case.note_trim.UMinValue, case.note_trim.UMaxValue = case.note_trim.UMaxValue, case.note_trim.UMinValue
    elif fault == "invalid_sense":
        case.note_trim.Sense = None
    elif fault == "invalid_kind":
        case.note_edge.curve.kind = None
    elif fault == "utility_null":
        case.app.GetMathUtility = lambda: None
    elif fault == "transform_null":
        case.front.ModelToViewTransform = None
    elif fault == "point_null":
        case.note_math_utility.CreatePoint = lambda _data: None
    elif fault == "transform_result_null":
        case.note_math_utility.CreatePoint = lambda _data: SimpleNamespace(MultiplyTransform=lambda _transform: None)
    elif fault in ("projection_nonfinite", "projection_z"):
        coordinates = (*case.note_landing[:2], float("nan") if fault == "projection_nonfinite" else case.note_landing[2] + 0.001)
        case.note_math_utility.CreatePoint = lambda _data: SimpleNamespace(
            MultiplyTransform=lambda _transform: SimpleNamespace(ArrayData=coordinates),
        )
    elif fault == "leader_z":
        case.note_landing = (*case.note_landing[:2], case.note_landing[2] + 0.001)
    else:
        raise AssertionError(f"unknown original note source corruption {fault}")
    with pytest.raises(RuntimeError, match="Purchased Screw Note"):
        bolt_drawing._purchased_note_geometry(
            case.adapter, case.front, case.note, text=case.note_text,
        )


@pytest.mark.parametrize("getter", ["GetCurve", "GetCurveParams3"])
def test_stud_original_native_note_descriptor_getter_failure_retains_cause(monkeypatch, getter):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    cause = OSError(f"actual original native {getter} failed")

    def fail():
        raise cause

    setattr(case.note_model_edge, getter, fail)
    with pytest.raises(RuntimeError, match="native head-top curve/trim") as error:
        bolt_drawing._purchased_note_geometry(
            case.adapter, case.front, case.note, text=case.note_text,
        )
    assert error.value.__cause__ is cause


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("field", ["curve_type", "trim_curve_type", "start", "end", "u_min", "u_max", "sense"])
def test_stud_original_native_note_trim_descriptor_is_immutable_and_freshly_reproved(
    monkeypatch, tmp_path, phase, field,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    else:
        case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
        _shelve_stud_paper(case)
    captured = dict(case.purchased_note_proof["edge_descriptor"])
    if field == "curve_type":
        case.note_edge.curve.kind += 1
    elif field == "trim_curve_type":
        case.note_trim.CurveType += 1
    elif field == "start":
        case.note_trim.StartPoint = (case.note_trim.StartPoint[0] + 0.000001, *case.note_trim.StartPoint[1:])
    elif field == "end":
        case.note_trim.EndPoint = (case.note_trim.EndPoint[0] + 0.000001, *case.note_trim.EndPoint[1:])
    elif field == "u_min":
        case.note_trim.UMinValue += 0.0000001
    elif field == "u_max":
        case.note_trim.UMaxValue += 0.0000001
    elif field == "sense":
        case.note_trim.Sense = not case.note_trim.Sense
    else:
        raise AssertionError(f"unknown native trim descriptor field {field}")
    assert case.purchased_note_proof["edge_descriptor"] == captured
    with pytest.raises(RuntimeError, match="physical head-top"):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            case.note_check()
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


def test_stud_note_source_configuration_getter_failure_is_not_ignored(monkeypatch):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    cause = OSError("actual native source configuration getter failed")
    original_bind = bolt_drawing._early_bound

    def bind(value, kind):
        if kind == "IConfigurationManager":
            raise cause
        return original_bind(value, kind)

    monkeypatch.setattr(bolt_drawing, "_early_bound", bind)
    with pytest.raises(OSError) as error:
        bolt_drawing._purchased_note_geometry(
            case.adapter, case.front, case.note, text=case.note_text,
        )
    assert error.value is cause


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("fault", ["configuration", "body", "inverse", "path"])
def test_stud_original_note_source_is_freshly_reproved_after_capture(
    monkeypatch, tmp_path, phase, fault,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    else:
        case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
        _shelve_stud_paper(case)
    if fault == "configuration":
        case.note_source.ConfigurationManager.ActiveConfiguration.Name = "FOREIGN"
    elif fault == "body":
        case.note_model_edge.body = object()
    elif fault == "inverse":
        case.note_source.Extension.GetCorrespondingEntity2 = lambda _entity: None
    elif fault == "path":
        case.note_source.GetPathName = lambda: str(bolt_drawing.SOURCE.with_name("foreign.SLDPRT").resolve())
    else:
        raise AssertionError(f"unknown captured source corruption {fault}")
    with pytest.raises(RuntimeError, match="physical head-top source"):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            case.note_check()
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


def _shelve_stud_paper(case):
    def reacquire():
        displays = bolt_drawing._assert_supplier_references(
            case.adapter, case.identities, case.configurations,
        )
        return {"SupplierHeadHeight": displays["SupplierHeadHeight"]}

    case.shelf_check = bolt_drawing.shelve_reference_text(
        case.adapter, reacquire=reacquire, axes={"SupplierHeadHeight": 1},
        force=("SupplierHeadHeight",), label="knife-hanger physical head height",
    )
    case.note_check, case.purchased_note_proof = bolt_drawing._place_purchased_note_above_shelf(
        case.adapter, case.front, case.display, case.note, text=case.note_text, reacquire=reacquire,
    )


def test_stud_actual_headheight_shelf_and_complete_note_clearance_preserve_physical_source(monkeypatch):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    arrows = deepcopy(case.paper_data["arrows"])
    lines = deepcopy(case.paper_data["lines"])
    attached = tuple(case.annotation.attached)
    original_note_attachment, = case.note_annotation.GetAttachedEntities3()
    before = bolt_drawing._assert_supplier_references(
        case.adapter, case.identities, case.configurations,
    )
    assert set(before) == set(bolt.SUPPLIER_REFERENCE_DIMENSIONS)
    assert before["SupplierHeadHeight"] is case.display
    assert case.sheet_index == 0
    initial = reference_text.measure_reference_text(
        case.adapter, case.display, axis=1, label="SupplierHeadHeight",
    )
    assert initial["text"].ymin < arrows[0][1] < initial["text"].ymax
    _shelve_stud_paper(case)
    shelf = reference_text.measure_reference_text(
        case.adapter, case.display, axis=1, label="SupplierHeadHeight",
    )
    _record, note, landing = bolt_drawing._purchased_note_geometry(
        case.adapter, case.front, case.note, text=case.note_text,
    )
    assert shelf["text"].ymin == pytest.approx(0.2291028)
    assert shelf["text"].ymax == pytest.approx(0.2381591)
    assert note.ymin == pytest.approx(0.2403591)
    assert note.ymax == pytest.approx(0.2438591)
    assert case.note_annotation.position[:2] == pytest.approx((0.130, 0.2448848))
    assert landing == case.note_landing
    actual_note_attachment, = case.note_annotation.GetAttachedEntities3()
    assert actual_note_attachment is original_note_attachment
    assert tuple(case.annotation.attached) == attached
    assert case.paper_data["arrows"] == arrows
    assert case.paper_data["lines"] == lines
    assert case.display.GetText(1) == "("
    assert case.native.SystemValue == pytest.approx(bolt.HEAD_H / 1000)
    assert bolt_drawing._assert_physical_head_height(
        case.adapter, case.front, case.display,
    ) == pytest.approx(bolt.HEAD_H)
    case.shelf_check()
    case.note_check()


def test_stud_shelf_reacquires_replaced_native_display_on_active_finished_sheet(monkeypatch):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    _shelve_stud_paper(case)
    fresh = SimpleNamespace(**vars(case.display))
    case.displays["SupplierHeadHeight"] = fresh
    assert bolt_drawing._assert_supplier_references(
        case.adapter, case.identities, case.configurations,
    )["SupplierHeadHeight"] is fresh
    assert case.sheet_index == 0
    case.shelf_check()
    fresh.OffsetText = False
    with pytest.raises(RuntimeError, match="offset|crowds"):
        case.shelf_check()


@pytest.mark.parametrize("phase", ["native_offset_rebuild", "settled"])
@pytest.mark.parametrize(
    "fault", ["full_name", "duplicate", "missing", "owner", "attachment", "value", "band", "config"],
)
def test_stud_shelf_retains_exact_source_census_at_transition_and_late_readback(
    monkeypatch, phase, fault,
):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)

    def corrupt():
        if fault == "full_name":
            case.native.FullName += "@STALE"
        elif fault == "duplicate":
            original = case.front.GetDisplayDimensions
            case.front.GetDisplayDimensions = lambda: (*original(), case.display)
        elif fault == "missing":
            case.displays.pop("SupplierHeadHeight")
        elif fault == "owner":
            case.annotation.Owner = case.views[1]
        elif fault == "attachment":
            case.annotation.attached[1] = case.rear
        elif fault == "value":
            case.native.SystemValue += 0.00001
        elif fault == "band":
            case.native.Tolerance.Type = 2
        else:
            case.front.ReferencedConfiguration = "FOREIGN"

    if phase == "native_offset_rebuild":
        original = case.model.EditRebuild3
        mutated = False

        def rebuild():
            nonlocal mutated
            if case.display.OffsetText is True and not mutated:
                mutated = True
                corrupt()
            return original()

        case.model.EditRebuild3 = rebuild
        with pytest.raises(RuntimeError):
            _shelve_stud_paper(case)
        assert mutated
    else:
        _shelve_stud_paper(case)
        corrupt()
        with pytest.raises(RuntimeError):
            case.shelf_check()


@pytest.mark.parametrize("fault", ["shelf_move", "note_move", "shelf_width", "note_width", "note_angle"])
def test_stud_actual_boundary_refuses_silent_native_moves_and_unmeasured_complete_text(
    monkeypatch, fault,
):
    case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
    if fault == "shelf_move":
        case.annotation.SetPosition2 = lambda *_xyz: True
    elif fault == "note_move":
        case.note_annotation.SetPosition2 = lambda *_xyz: True
    elif fault == "shelf_width":
        case.paper_data["texts"][-1]["w"] = 0.0
    elif fault == "note_width":
        case.note_data["texts"][-1]["w"] = 0.0
    else:
        case.note_data["texts"][-1]["ang"] = math.nan
    with pytest.raises(RuntimeError):
        _shelve_stud_paper(case)


_STUD_PAPER_FAULTS = (
    "offset", "shelf_last_fragment", "note_last_fragment", "note_property", "note_text",
    "note_landing", "note_attachment", "note_dangling", "note_owner", "note_visible",
    "note_missing", "note_duplicate", "foreign_line", "foreign_text", "border", "other_view",
    "shelf_width", "note_width", "note_position", "note_line",
)


def _corrupt_stud_paper(case, fault):
    if fault == "offset":
        case.display.OffsetText = False
    elif fault == "shelf_width":
        case.paper_data["texts"][-1]["w"] = 0.0
    elif fault == "note_width":
        case.note_data["texts"][-1]["w"] = 0.0
    elif fault == "note_position":
        case.note_annotation.position[0] = math.nan
    elif fault == "note_line":
        case.note_data["lines"][0] = [0, 0, 0, 0, 0.210, 0.232, 0, 0.240, 0.232, 0]
    elif fault == "shelf_last_fragment":
        case.paper_data["texts"][-1]["pos"][1] = 0.225
    elif fault == "note_last_fragment":
        case.note_data["texts"].append(
            case.paper_row("HEAD UNMODIFIED", 0.210, 0.233, 0.045, 0.0068741)
        )
    elif fault == "note_property":
        case.note.PropertyLinkedText = bolt_drawing.property_link("Wrong Property")
    elif fault == "note_text":
        case.note.text += " WRONG"
    elif fault == "note_landing":
        case.note_landing = (case.note_landing[0] + 0.001, *case.note_landing[1:])
    elif fault == "note_attachment":
        case.note_annotation.attached = case.bearing
    elif fault == "note_dangling":
        case.note_annotation.dangling = True
    elif fault == "note_owner":
        case.note_annotation.Owner = case.views[1]
    elif fault == "note_visible":
        case.note_annotation.Visible = 0
    elif fault == "note_missing":
        case.note_annotation.GetName = lambda: "DetailItem347@STALE"
    elif fault == "note_duplicate":
        case.foreign_annotations.append(case.note_annotation)
    elif fault in ("foreign_line", "foreign_text"):
        annotation = SimpleNamespace(
            Owner=case.front, OwnerType=0, GetName=lambda: "foreign annotation",
        )
        native = (
            {"lines": [[0, 0, 0, 0, 0.200, 0.232, 0, 0.245, 0.232, 0]]}
            if fault == "foreign_line"
            else {"texts": [case.paper_row("FOREIGN", 0.220, 0.241, 0.030)]}
        )
        case.paper_install(annotation, native, 7, (0.220, 0.232, 0))
        case.foreign_annotations.append(annotation)
    elif fault == "border":
        case.note_data["texts"][-1]["pos"][0] = 0.400
    elif fault == "other_view":
        case.views[1].GetOutline = lambda: (0.210, 0.228, 0.260, 0.246)
    else:
        raise AssertionError(f"unknown actual-paper fault {fault}")


@pytest.mark.parametrize("fault", _STUD_PAPER_FAULTS)
@pytest.mark.parametrize("phase", ["settled", "saved"])
def test_stud_full_actual_paper_proof_refuses_late_complete_text_and_adjacent_ink_drift(
    monkeypatch, tmp_path, fault, phase,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    else:
        case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
        _shelve_stud_paper(case)
    _corrupt_stud_paper(case, fault)
    rebuilds = tuple(case.rebuilds)
    with pytest.raises(RuntimeError):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            case.note_check()
    assert tuple(case.rebuilds) == rebuilds
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


def test_stud_saved_paper_uses_only_fresh_native_reads_not_live_shelf_closures(monkeypatch, tmp_path):
    case = _saved_stud_height_case(monkeypatch, tmp_path)

    def stale():
        raise AssertionError("closed live-COM proof must never be called")

    case.shelf_check = case.note_check = stale
    case.annotation.SetPosition2 = case.note_annotation.SetPosition2 = stale
    case.model.EditRebuild3 = stale
    bolt_drawing._assert_saved_physical_references(
        case.adapter, case.identities, case.configurations,
        serialized_full_names=case.serialized_full_names,
        purchased_note=case.purchased_note_proof,
    )
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model


@pytest.mark.parametrize("phase", ["settled", "saved"])
def test_stud_note_preserves_actual_noncircular_boundary_and_independent_height_outer_rim(
    monkeypatch, tmp_path, phase,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    else:
        case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
        _shelve_stud_paper(case)
    descriptor = case.purchased_note_proof["edge_descriptor"]
    assert descriptor["start_m"] == case.note_trim.StartPoint
    assert descriptor["end_m"] == case.note_trim.EndPoint
    assert descriptor["u"] == (case.note_trim.UMinValue, case.note_trim.UMaxValue)
    assert descriptor["sense"] is case.note_trim.Sense
    assert not case.note_edge.GetCurve().IsCircle()
    assert not case.note_edge.GetCurve().IsLine()
    assert case.note_annotation.attached is case.note_edge
    assert case.annotation.attached[1] is case.top
    if phase == "saved":
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model
    else:
        case.note_check()


def test_stud_note_cold_read_requires_exact_actual_serialized_annotation_name(monkeypatch, tmp_path):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    assert case.purchased_note_proof["name"] == case.note_name != "DetailItem347"
    stale = dict(case.purchased_note_proof, name="DetailItem347")
    with pytest.raises(RuntimeError, match="exact native note census"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names, purchased_note=stale,
        )
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("replacement", ["circle", "other_trim", "foreign_same_geometry"])
def test_stud_note_refuses_other_native_target_despite_identical_projected_head_top_landing(
    monkeypatch, tmp_path, phase, replacement,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    else:
        case = _stud_paper_fixture(_settled_stud_height_case(monkeypatch), monkeypatch)
        _shelve_stud_paper(case)
    original_landing = case.note_landing
    if replacement == "circle":
        case.note_annotation.attached = case.top
    else:
        trim = SimpleNamespace(**vars(case.note_trim))
        if replacement == "other_trim":
            trim.EndPoint = (trim.EndPoint[0] + 0.001, *trim.EndPoint[1:])
        raw, canonical = case.install_note_edge(trim, 3006)
        if replacement == "foreign_same_geometry":
            canonical.body = object()
        case.front.scan = ViewEdges(
            "different original-note target",
            (*case.front.scan.edges, ViewEdge(edge=raw, line=None, circle=None, vertices=None)),
        )
        case.note_annotation.attached = raw
    # Every replacement retains the same complete projected top endpoint.
    assert case.note_landing == original_landing
    message = "source body" if replacement == "foreign_same_geometry" else "source descriptor"
    with pytest.raises(RuntimeError, match=message):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            case.note_check()
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


def _saved_stud_height_case(monkeypatch, tmp_path):
    case = _settled_stud_height_case(monkeypatch)
    _stud_paper_fixture(case, monkeypatch)
    _shelve_stud_paper(case)
    case.scans.clear()
    case.events.clear()
    path = tmp_path / "finished-stud.SLDDRW"
    path.touch()
    case.path = str(path.resolve())
    case.model.GetType = lambda: 3
    case.native_doc_path = str(tmp_path / "Drawing.SLDDRW")
    case.model.GetPathName = lambda: case.native_doc_path
    case.model.GetTitle = lambda: "finished-stud.SLDDRW"
    case.previous_model = object()
    case.open_calls = []
    case.close_calls = []
    case.open_result = (case.model, 0, 0)
    case.app.ActiveDoc = case.model

    def open_doc(*args):
        case.open_calls.append(args)
        case.loaded = True
        return case.open_result

    def close_doc(title):
        case.close_calls.append(title)
        case.loaded = False

    case.app.OpenDoc6 = open_doc
    case.app.CloseDoc = close_doc
    case.app.GetOpenDocumentByName = lambda native_path: (
        case.model if case.loaded and native_path == case.path else None
    )
    monkeypatch.setattr(bolt_drawing, "OUTPUTS", SimpleNamespace(slddrw=path))
    monkeypatch.setattr(
        bolt_drawing, "assert_supplier_reference_dimension",
        supplier_dimensions.assert_supplier_reference_dimension,
    )
    monkeypatch.setattr(supplier_dimensions, "sheet_units", lambda _adapter: "mm")
    # Simulate successful native/PDF saves before the pre-close checkpoint.
    # Annotation COM anchors stay identical while actual document/name fields change.
    original_identities = dict(case.identities)
    case.native_doc_path = case.path
    case.loaded = True
    for name in ("SupplierHeadHeight", "SupplierStockLength"):
        native = case.displays[name].GetDimension2(0)
        native.FullName = f"{native.FullName}@finished-stud"
    case.note_name = "DetailItem347@ACTUAL-SERIALIZED"
    case.purchased_note_proof["name"] = bolt_drawing.capture_serialized_note_name(
        case.adapter, case.note_annotation, case.front,
        drawing_path=path, source_path=bolt_drawing.SOURCE,
        sheet_names=bolt_drawing.SHEET_NAMES, sheet_name=bolt_drawing.SHEET_NAMES[0],
        configuration=case.purchased_note_proof["source"][2], label="Purchased Screw Note",
    )
    case.serialized_full_names = bolt_drawing.capture_serialized_physical_axial_names(
        case.adapter,
        {name: case.references[name] for name in ("SupplierHeadHeight", "SupplierStockLength")},
        case.identities, case.configurations,
        labels=("SupplierHeadHeight", "SupplierStockLength"),
        drawing_path=path, sheet_names=bolt_drawing.SHEET_NAMES,
    )
    assert case.identities == original_identities
    case.loaded = False
    case.adapter.currentModel = case.previous_model
    # Captured creation handles deliberately cannot match the freshly reopened edges.
    for name in ("SupplierHeadHeight", "SupplierStockLength"):
        full_name, owner, _entities, kinds = case.identities[name]
        case.identities[name] = (full_name, owner, (object(), object()), kinds)
    return case


def test_stud_saved_reopen_proves_fresh_geometry_native_full_name_and_supplier_format(
    monkeypatch, tmp_path
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    assert all(
        case.identities[name][0] != actual_name
        for name, actual_name in case.serialized_full_names.items()
    )
    bolt_drawing._assert_saved_physical_references(
        case.adapter, case.identities, case.configurations,
        serialized_full_names=case.serialized_full_names,
        purchased_note=case.purchased_note_proof,
    )
    assert case.open_calls == [(case.path, 3, 3, "", 0, 0)]
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model
    assert not case.loaded
    assert all(record[0] is case.model for record in case.scans)
    assert {id(record[1]) for record in case.scans} == {id(case.front), id(case.stock_case.front)}
    receipt = next(
        fields for _name, fields in case.events if fields.get("phase") == "after_saved_reopen"
    )
    assert receipt["full_name"] == case.native.FullName
    assert receipt["measured_mm"] == pytest.approx(bolt.HEAD_H)
    assert receipt["top_radius_mm"] == pytest.approx(bolt.HEAD_AF / 2)
    assert receipt["bearing_point_mm"][1] == bolt.LENGTH
    assert receipt["top_point_mm"][1] == bolt.HEAD_TOP_Y
    stock_receipt = next(
        fields for name, fields in case.events if name == "drawing.physical_stock_length"
    )
    assert stock_receipt["full_name"] == case.stock_case.native.FullName
    assert stock_receipt["measured_mm"] == pytest.approx(bolt.CATALOG_LENGTH)
    assert stock_receipt["configuration"] == bolt.SUPPLIER_STOCK_CONFIGURATION
    assert stock_receipt["tip_y_mm"] == pytest.approx(bolt.LENGTH - bolt.CATALOG_LENGTH)
    proofs = [
        fields for name, fields in case.events
        if name == "drawing.physical_axial_dimension_native_proof"
    ]
    assert {(fields["label"], fields["phase"]) for fields in proofs} == {
        ("SupplierHeadHeight", "saved"), ("SupplierStockLength", "saved"),
    }


@pytest.mark.parametrize("fault", ["missing", "extra", "empty", "null", "duplicate"])
def test_stud_saved_reader_requires_complete_distinct_serialized_mapping_before_open(
    monkeypatch, tmp_path, fault,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    serialized = dict(case.serialized_full_names)
    if fault == "missing":
        serialized.pop("SupplierStockLength")
    elif fault == "extra":
        serialized["SupplierHeadAF"] = "foreign-serialized-name"
    elif fault == "empty":
        serialized["SupplierHeadHeight"] = ""
    elif fault == "null":
        serialized["SupplierHeadHeight"] = None
    else:
        serialized["SupplierStockLength"] = serialized["SupplierHeadHeight"]
    with pytest.raises(RuntimeError, match="serialized native FullNames"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations, serialized_full_names=serialized,
            purchased_note=case.purchased_note_proof,
        )
    assert not case.open_calls and not case.close_calls and not case.scans
    assert case.adapter.currentModel is case.previous_model


def test_stud_saved_reader_has_no_implicit_original_name_fallback(monkeypatch, tmp_path):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    with pytest.raises(TypeError, match="serialized_full_names"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
        )
    assert not case.open_calls and not case.close_calls


@pytest.mark.parametrize("fault", ["original", "suffix_only", "near_match"])
def test_stud_saved_reader_matches_only_the_actual_serialized_full_names(
    monkeypatch, tmp_path, fault,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    serialized = dict(case.serialized_full_names)
    for name in serialized:
        if fault == "original":
            serialized[name] = case.identities[name][0]
        elif fault == "suffix_only":
            serialized[name] = serialized[name].split("@", 1)[1]
        else:
            serialized[name] += " "
    with pytest.raises(RuntimeError, match="label_match_counts"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations, serialized_full_names=serialized,
            purchased_note=case.purchased_note_proof,
        )
    receipt = next(
        fields for event, fields in case.events
        if event == "drawing.physical_axial_identity_inventory" and fields["phase"] == "saved"
    )
    assert receipt["label_match_counts"] == {
        "SupplierHeadHeight": 0, "SupplierStockLength": 0,
    }
    assert not case.scans
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model


def test_stud_saved_missing_both_names_emits_full_actual_native_inventory_before_refusal(
    monkeypatch, tmp_path,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    case.native.FullName = "ACTUAL-HEAD-AFTER-SAVE"
    case.stock_case.native.FullName = "ACTUAL-STOCK-AFTER-SAVE"
    case.views[3].GetDisplayDimensions = lambda: None
    with pytest.raises(RuntimeError) as failure:
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    receipt = next(
        fields for event, fields in case.events
        if event == "drawing.physical_axial_identity_inventory" and fields["phase"] == "saved"
    )
    assert receipt["document"] == {
        "title": "finished-stud.SLDDRW", "path": case.path, "type": 3,
        "sheet_names": bolt_drawing.SHEET_NAMES,
    }
    assert receipt["expected_original_full_names"] == {
        name: case.identities[name][0] for name in case.serialized_full_names
    }
    assert receipt["expected_serialized_full_names"] == case.serialized_full_names
    assert receipt["label_match_counts"] == {
        "SupplierHeadHeight": 0, "SupplierStockLength": 0,
    }
    observed = {
        (sheet["sheet"], view["view"]): view
        for sheet in receipt["inventory"] for view in sheet["views"]
    }
    assert set(observed) == {
        (bolt_drawing.SHEET_NAMES[index], name)
        for index, names in enumerate((
            (bolt_drawing.SHEET_NAMES[0], "FinishedFront", "FinishedIso"),
            (bolt_drawing.SHEET_NAMES[1], "StockFront", "StockIso"),
        ))
        for name in names
    }
    finished_sheet = observed[(bolt_drawing.SHEET_NAMES[0], bolt_drawing.SHEET_NAMES[0])]
    stock_sheet = observed[(bolt_drawing.SHEET_NAMES[1], bolt_drawing.SHEET_NAMES[1])]
    stock_iso = observed[(bolt_drawing.SHEET_NAMES[1], "StockIso")]
    assert finished_sheet["raw_none"] is True and finished_sheet["count"] == 0
    assert stock_sheet["raw_none"] is False and stock_sheet["count"] == 0
    assert stock_iso["raw_none"] is True and stock_iso["count"] == 0
    for name, owner, actual_full_name in (
        ("SupplierHeadHeight", "FinishedFront", case.native.FullName),
        ("SupplierStockLength", "StockFront", case.stock_case.native.FullName),
    ):
        sheet_name, configuration = case.configurations[owner]
        view = observed[(sheet_name, owner)]
        assert view["configuration"] == configuration
        assert view["source_document_path"] == str(bolt_drawing.SOURCE.resolve())
        dimension = next(row for row in view["dimensions"] if row["full_name"] == actual_full_name)
        assert dimension["annotation_name"] == f"native-annotation:{name}"
        assert dimension["selection_name"] == f"native-selection:{name}"
        assert dimension["owner"] == owner
        assert dimension["owner_type"] == 0 and dimension["owner_same"] == 1
        assert actual_full_name in str(failure.value)
    assert not case.scans
    assert case.close_calls == ["finished-stud.SLDDRW"]


def test_stud_saved_inventory_visits_unexpected_actual_sheets_before_sheet_census_refusal(
    monkeypatch, tmp_path,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    extra_name = "Unexpected actual saved sheet"
    extra_view = SimpleNamespace(
        name=extra_name, ReferencedConfiguration="", ReferencedDocument=None,
        GetDisplayDimensions=lambda: None, GetNextView=lambda: None,
    )
    activate_original = case.model.ActivateSheet
    first_original = case.model.GetFirstView
    case.extra_active = False

    def activate(name):
        case.extra_active = name == extra_name
        return True if case.extra_active else activate_original(name)

    case.model.ActivateSheet = activate
    case.model.GetFirstView = lambda: extra_view if case.extra_active else first_original()
    case.model.GetSheetNames = lambda: (*bolt_drawing.SHEET_NAMES, extra_name)
    with pytest.raises(RuntimeError, match=extra_name):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    receipt = next(
        fields for event, fields in case.events
        if event == "drawing.physical_axial_identity_inventory" and fields["phase"] == "saved"
    )
    assert [sheet["sheet"] for sheet in receipt["inventory"]] == [
        *bolt_drawing.SHEET_NAMES, extra_name,
    ]
    assert receipt["label_match_counts"] == {
        "SupplierHeadHeight": 1, "SupplierStockLength": 1,
    }
    extra_record = receipt["inventory"][-1]["views"][0]
    assert extra_record["view"] == extra_name
    assert extra_record["raw_none"] is True and extra_record["count"] == 0
    assert not case.scans
    assert case.close_calls == ["finished-stud.SLDDRW"]


@pytest.mark.parametrize("getter", ["selection", "annotation", "dimension", "full_name", "view"])
def test_stud_saved_inventory_continues_after_getter_failure_and_chains_original_cause(
    monkeypatch, tmp_path, getter,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    cause = OSError(f"original native {getter} getter failure")

    def fail(*_args):
        raise cause

    if getter == "selection":
        case.display.GetNameForSelection = fail
    elif getter == "annotation":
        case.annotation.GetName = fail
    elif getter == "dimension":
        case.display.GetDimension2 = fail
    elif getter == "full_name":
        class BrokenDimension:
            @property
            def FullName(self):
                raise cause

        broken_dimension = BrokenDimension()
        case.display.GetDimension2 = lambda _index: broken_dimension
    else:
        case.front.GetDisplayDimensions = fail
    with pytest.raises(RuntimeError) as failure:
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert failure.value.__cause__ is cause
    receipt = next(
        fields for event, fields in case.events
        if event == "drawing.physical_axial_identity_inventory" and fields["phase"] == "saved"
    )
    assert receipt["label_match_counts"] == {
        "SupplierHeadHeight": int(getter in ("selection", "annotation")),
        "SupplierStockLength": 1,
    }
    assert [sheet["sheet"] for sheet in receipt["inventory"]] == list(bolt_drawing.SHEET_NAMES)
    stock_view = next(
        view for sheet in receipt["inventory"] for view in sheet["views"]
        if view.get("view") == "StockFront"
    )
    assert stock_view["dimensions"][0]["full_name"] == case.stock_case.native.FullName
    assert str(cause) in str(failure.value)
    if getter == "view":
        front_view = next(
            view for sheet in receipt["inventory"] for view in sheet["views"]
            if view.get("view") == "FinishedFront"
        )
        assert "raw_none" not in front_view and "count" not in front_view
    assert not case.scans
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model


@pytest.mark.parametrize(
    "fault",
    (
        "open_errors", "null_open", "bad_open_shape", "wrong_path", "wrong_type",
        "wrong_current", "sheet_census", "activate_sheet", "missing_dimension",
        "duplicate_dimension", "wrong_owner", "wrong_annotation_owner",
        "same_named_foreign_owner", "wrong_owner_type",
        "wrong_configuration", "value", "attachment", "station", "format", "band",
        "missing_native", "missing_annotation", "close_failure",
    ),
)
def test_stud_saved_reopen_refuses_corruption_and_restores_adapter_even_on_failure(
    monkeypatch, tmp_path, fault
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    if fault == "open_errors":
        case.open_result = (case.model, 4, 0)
    elif fault == "null_open":
        case.open_result = (None, 0, 0)
    elif fault == "bad_open_shape":
        case.open_result = case.model
    elif fault == "wrong_path":
        case.open_result = (SimpleNamespace(
            GetType=lambda: 3, GetPathName=lambda: str(tmp_path / "wrong.SLDDRW")
        ), 0, 0)
    elif fault == "wrong_type":
        case.open_result = (SimpleNamespace(
            GetType=lambda: 1, GetPathName=lambda: case.path
        ), 0, 0)
    elif fault == "wrong_current":
        case.app.ActiveDoc = object()
    elif fault == "sheet_census":
        case.model.GetSheetNames = lambda: (bolt_drawing.SHEET_NAMES[0],)
    elif fault == "activate_sheet":
        case.model.ActivateSheet = lambda _name: False
    elif fault == "missing_dimension":
        case.native.FullName = "Wrong@FinishedFront@Drawing"
    elif fault == "duplicate_dimension":
        original = case.front.GetDisplayDimensions
        case.front.GetDisplayDimensions = lambda: (*original(), case.display)
    elif fault == "wrong_owner":
        case.front.name = "WrongView"
    elif fault == "wrong_annotation_owner":
        case.annotation.Owner = case.views[1]
    elif fault == "same_named_foreign_owner":
        case.annotation.Owner = SimpleNamespace(name=case.front.name)
    elif fault == "wrong_owner_type":
        case.annotation.OwnerType = 1
    elif fault == "wrong_configuration":
        case.front.ReferencedConfiguration = bolt.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "value":
        case.native.SystemValue -= 0.0001
    elif fault == "attachment":
        case.annotation.attached[1] = case.rear
    elif fault == "station":
        case.front.scan = ViewEdges("saved crown only", (case.bearing_item, case.crown_item))
    elif fault == "format":
        case.display.precision += 1
    elif fault == "band":
        case.native.Tolerance.Type = 2
    elif fault == "missing_native":
        case.display.GetDimension2 = lambda _index: None
    elif fault == "missing_annotation":
        case.display.GetAnnotation = lambda: None
    elif fault == "close_failure":
        case.app.CloseDoc = lambda title: case.close_calls.append(title)
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model
    assert case.loaded is (fault == "close_failure")
    if fault not in ("close_failure",):
        assert not any(
            fields.get("phase") == "after_saved_reopen" for _name, fields in case.events
        )


@pytest.mark.parametrize("already_open", [False, True])
def test_stud_saved_proof_requires_existing_closed_finalized_file(
    monkeypatch, tmp_path, already_open
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    if already_open:
        case.loaded = True
    else:
        monkeypatch.setattr(
            bolt_drawing, "OUTPUTS", SimpleNamespace(slddrw=tmp_path / "missing.SLDDRW")
        )
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert not case.open_calls
    assert not case.close_calls
    assert case.adapter.currentModel is case.previous_model


def test_stud_head_height_projects_actual_closest_points_not_nominal_interior_picks(monkeypatch):
    case = _stud_height_case(monkeypatch)
    case.bearing.nearest = (
        case.bearing.nearest[0] + 1e-9, *case.bearing.nearest[1:]
    )
    case.top.nearest = (1e-9, *case.top.nearest[1:])
    bolt_drawing._add_physical_head_height(case.adapter, case.front, (0.218, 0.216))
    assert case.projections[0][1] == [
        tuple(case.bearing.nearest[:3]), tuple(case.top.nearest[:3])
    ]


@pytest.mark.parametrize("nearest", [None, (0.0,), (math.nan, 0.0, 0.0), (1.0, 1.0, 1.0)])
def test_stud_head_height_refuses_unreadable_or_moved_actual_bearing_point(monkeypatch, nearest):
    case = _stud_height_case(monkeypatch)
    case.bearing.nearest = nearest
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._add_physical_head_height(case.adapter, case.front, (0.218, 0.216))
    assert not case.selection_log
    assert not case.creations


@pytest.mark.parametrize(
    "name",
    ("_head_height_entities", "_add_physical_head_height",
     "_assert_physical_head_height", "_assert_saved_physical_references"),
)
def test_stud_physical_head_height_native_entrypoints_are_traced(name):
    assert hasattr(getattr(bolt_drawing, name), "__wrapped__")


@pytest.mark.parametrize("wrong_value", [False, True])
def test_stud_created_readback_reuses_named_pair_without_skipping_native_proof(
    monkeypatch, wrong_value
):
    case = _stud_height_case(monkeypatch)

    def unexpected_scan(*_args, **_kwargs):
        raise AssertionError("creation readback must reuse its freshly resolved physical pair")

    monkeypatch.setattr(bolt_drawing, "scan_view_edges", unexpected_scan)
    if wrong_value:
        case.native.SystemValue -= 0.0001
        with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
            bolt_drawing._assert_physical_head_height(
                case.adapter, case.front, case.display, entities=(case.bearing, case.top)
            )
        return
    assert bolt_drawing._assert_physical_head_height(
        case.adapter, case.front, case.display, entities=(case.bearing, case.top)
    ) == pytest.approx(bolt.HEAD_H)


def test_stud_unique_physical_pair_does_not_repeat_the_bearing_identity_lookup(monkeypatch):
    case = _stud_height_case(monkeypatch)
    comparisons = []

    def same(first, second):
        comparisons.append((first, second))
        return int(first is second)

    case.app.IsSame = same
    bearing, top = bolt_drawing._head_height_entities(case.adapter, case.front)
    assert bearing is case.bearing
    assert top is case.top
    assert comparisons == [(case.bearing, case.top)]


@pytest.mark.parametrize("reverse", [False, True])
def test_stud_changed_geometry_diagnostics_keep_nearest_lines_and_circles_bounded(
    monkeypatch, reverse
):
    case = _stud_height_case(monkeypatch)
    near_line = replace(
        case.bearing_item,
        line=tuple((x, y + 0.001, z) for x, y, z in case.bearing_item.line),
    )
    near_circle = replace(
        case.top_item,
        circle=(*case.top_item.circle[:6], bolt.HEAD_AF / 2 + 0.001),
    )
    far_lines = [
        replace(
            case.bearing_item, edge=case.edge(None),
            line=tuple((x, y + 10 + index, z) for x, y, z in case.bearing_item.line),
        )
        for index in range(16)
    ]
    far_circles = [
        replace(
            case.top_item, edge=case.edge(None),
            circle=(*case.top_item.circle[:6], bolt.HEAD_AF / 2 + 10 + index),
        )
        for index in range(16)
    ]
    invalid_line = replace(
        case.bearing_item,
        line=((math.nan, bolt.LENGTH, 0.0), case.bearing_item.line[1]),
    )
    invalid_circle = replace(
        case.top_item, circle=(*case.top_item.circle[:6], math.nan)
    )
    edges = [*far_lines, *far_circles, invalid_line, invalid_circle, near_line, near_circle]
    case.front.scan = ViewEdges(
        "changed source with near misses", tuple(reversed(edges) if reverse else edges)
    )
    with pytest.raises(RuntimeError, match="SupplierHeadHeight"):
        bolt_drawing._head_height_entities(case.adapter, case.front)
    evidence = next(fields for name, fields in case.events if name.endswith("_geometry"))
    assert evidence["line_count"] == evidence["circle_count"] == 18
    assert len(evidence["lines"]) == len(evidence["circles"]) == 12
    assert evidence["lines"][0]["line_mm"] == near_line.line
    assert evidence["circles"][0]["circle_mm"] == near_circle.circle
    assert evidence["lines"][0]["geometry_error_mm"] == pytest.approx(0.001)
    assert evidence["circles"][0]["geometry_error_mm"] == pytest.approx(0.001)
    assert not evidence["circles"][0]["shape_matches"]


@pytest.mark.parametrize("missing_registered", [False, True])
def test_stud_saved_proof_requires_the_opened_document_to_be_registered_by_exact_path(
    monkeypatch, tmp_path, missing_registered
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    loaded_lookups = []

    def lookup(path):
        assert path == case.path
        if not case.loaded:
            return None
        loaded_lookups.append(path)
        if len(loaded_lookups) == 1:
            return None if missing_registered else object()
        return case.model

    case.app.GetOpenDocumentByName = lookup
    with pytest.raises(RuntimeError, match="wrong current drawing"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model
    assert not case.loaded
    assert not case.scans


@pytest.mark.parametrize("missing_current", [False, True])
def test_stud_saved_proof_refuses_adapter_current_model_drift_before_geometry_readback(
    monkeypatch, tmp_path, missing_current
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    original_activate = case.model.ActivateSheet

    def activate(name):
        result = original_activate(name)
        case.adapter.currentModel = None if missing_current else case.previous_model
        return result

    case.model.ActivateSheet = activate
    with pytest.raises(RuntimeError, match="adapter's exact current drawing"):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert case.close_calls == ["finished-stud.SLDDRW"]
    assert case.adapter.currentModel is case.previous_model
    assert not case.loaded
    assert not case.scans


def test_stud_supplier_head_af_direct_call_preserves_picks_format_and_thread_major(monkeypatch):
    case = _stud_height_case(monkeypatch)
    af_display, height_display, thread_display = object(), object(), object()
    edge_calls, formats, head_calls, imports = [], [], [], []
    thread_annotation = SimpleNamespace(GetSpecificAnnotation=lambda: thread_display)

    def add_edge(_adapter, view, **kwargs):
        edge_calls.append((view, kwargs))
        return af_display

    def add_height(_adapter, view, text_xy):
        head_calls.append((view, text_xy))
        return height_display

    def format_reference(_adapter, display, name):
        formats.append((display, name))
        return name

    def import_major(_adapter, view, **kwargs):
        imports.append((view, kwargs))
        return [thread_annotation]

    monkeypatch.setattr(bolt_drawing, "add_edge_dimension", add_edge)
    monkeypatch.setattr(bolt_drawing, "_add_physical_head_height", add_height)
    monkeypatch.setattr(bolt_drawing, "_format_supplier_reference", format_reference)
    monkeypatch.setattr(bolt_drawing, "curate_view_dimensions", import_major)
    monkeypatch.setattr(
        bolt_drawing, "dimension_name", lambda _adapter, _annotation: "SupplierThreadMajor"
    )
    result = bolt_drawing._add_supplier_references(case.adapter, case.front)
    assert result == {
        name: name for name in ("SupplierHeadAF", "SupplierHeadHeight", "SupplierThreadMajor")
    }
    points_m = case.projections[0][1]
    assert points_m[0] == pytest.approx((
        -bolt.HEAD_AF / 2000, (bolt.LENGTH + bolt.HEAD_H / 3) / 1000,
        bolt.HEAD_AF / (2000 * math.sqrt(3)),
    ))
    assert points_m[1] == pytest.approx((
        bolt.HEAD_AF / 2000, (bolt.LENGTH + bolt.HEAD_H / 3) / 1000,
        bolt.HEAD_AF / (2000 * math.sqrt(3)),
    ))
    assert edge_calls == [(case.front, {
        "p0": (points_m[0][0] * case.front.ScaleDecimal + 0.1,
               points_m[0][1] * case.front.ScaleDecimal + 0.1),
        "p1": (points_m[1][0] * case.front.ScaleDecimal + 0.1,
               points_m[1][1] * case.front.ScaleDecimal + 0.1),
        "text_xy": (0.110, 0.255), "label": "SupplierHeadAF", "orientation": "horizontal",
    })]
    assert head_calls == [(case.front, (0.218, 0.216))]
    assert formats == [
        (af_display, "SupplierHeadAF"), (height_display, "SupplierHeadHeight"),
        (thread_display, "SupplierThreadMajor"),
    ]
    assert imports[0][0] is case.front
    assert imports[0][1]["keep"] == {"SupplierThreadMajor": (0.170, 0.194)}
    assert imports[0][1]["dimensions_by_feature"] is bolt.SUPPLIER_DRAWING_DIMENSIONS


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


def _stud_stock_case(monkeypatch):
    case = _stud_height_case(monkeypatch)
    case.stock_case = _stud_stock_fixture(case)
    case.result = case.stock_case.display
    return case


def _create_stud_stock_reference(case, monkeypatch):
    """Exercise the owned stock consumer, including rebuild/configuration/HLR."""
    stock = case.stock_case
    iso = SimpleNamespace(
        name="StockIso", ReferencedConfiguration="Default", ScaleDecimal=2.0,
    )
    stock.front.ReferencedConfiguration = "Default"
    case.stock_order = []
    case.model.ActivateSheet = lambda name: (
        case.stock_order.append(("sheet", name)) or True
    )
    case.model.EditRebuild3 = lambda: case.stock_order.append(("rebuild",)) or True
    case.model.GetEditSheet = lambda: True

    def place(_adapter, _source, orientation, *_args, **kwargs):
        assert kwargs["scale"] == bolt_drawing.SHEET_SCALE
        return stock.front if orientation == "*Front" else iso

    def hidden(_adapter, view):
        case.stock_order.append(("hlr", view.name))
        view.GetDisplayMode2 = lambda: 2

    original_scan = bolt_drawing.scan_view_edges

    def scan(view, **kwargs):
        assert ("rebuild",) in case.stock_order
        assert ("hlr", view.name) in case.stock_order
        assert view.ReferencedConfiguration == bolt.SUPPLIER_STOCK_CONFIGURATION
        return original_scan(view, **kwargs)

    monkeypatch.setattr(bolt_drawing, "place_view", place)
    monkeypatch.setattr(bolt_drawing, "scan_view_edges", scan)
    monkeypatch.setattr(bolt_drawing, "set_hidden_lines_removed", hidden)
    monkeypatch.setattr(bolt_drawing, "set_view_position", lambda *_args: True)
    monkeypatch.setattr(
        bolt_drawing, "_format_supplier_reference",
        lambda _adapter, display, name: (
            display.GetAnnotation() if name == "SupplierStockLength" else None
        ),
    )
    monkeypatch.setattr(
        bolt_drawing, "add_property_linked_note",
        lambda *_args: SimpleNamespace(
            GetAnnotation=lambda: SimpleNamespace(OwnerType=1)
        ),
    )
    return bolt_drawing._add_stock_reference(case.adapter)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("axis_sign", [-1.0, 1.0])
def test_stud_stock_names_outer_hex_and_exact_original_factory_tip(monkeypatch, reverse, axis_sign):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    tip = replace(
        stock.top_item,
        circle=(*stock.top_item.circle[:4], axis_sign, *stock.top_item.circle[5:]),
    )
    edges = (stock.rear_item, stock.bearing_item, tip)
    stock.front.scan = ViewEdges("reordered stock", tuple(reversed(edges)) if reverse else edges)
    entities, points = bolt_drawing._stock_length_stations(case.adapter, stock.front)
    assert entities[0] is stock.bearing and entities[1] is stock.top
    assert points == (stock.bearing.nearest[:3], stock.top.nearest[:3])
    assert abs(points[0][1] - points[1][1]) * 1000 == pytest.approx(50.8)
    assert bolt_drawing._stock_factory_tip_radius_mm() == (
        BOLT_DIMS.major_dia / 2 - BOLT_DIMS.pitch * 0.851
    )
    # Independently expand the catalogue dimensions and supplier chamfer law;
    # do not pin a separately rounded radius nominal.
    assert bolt_drawing._stock_factory_tip_radius_mm() == pytest.approx(
        4.826 / 2 - (25.4 / 24) * 0.851
    )
    assert stock.top.closest_calls == [stock.top.nearest[:3], stock.top.nearest[:3]]
    receipt = next(
        fields for name, fields in case.events if name == "drawing.physical_stock_length_geometry"
    )
    assert receipt["configuration"] == bolt.SUPPLIER_STOCK_CONFIGURATION
    assert receipt["bearing_matches"] == 1 and receipt["tip_matches"] == 2
    assert len(receipt["lines"]) <= 12 and len(receipt["circles"]) <= 12


@pytest.mark.parametrize(
    "fault",
    (
        "configuration", "hlr", "missing_bearing", "duplicate_bearing",
        "one_wrong_endpoint", "interior_bearing", "outside_segment", "inner_runout",
        "finished_tip", "major_chamfer_junction", "wrong_radius", "wrong_center",
        "wrong_axis", "nonfinite_circle", "false_trim_plane", "false_trim_radius",
        "trim_requery", "missing_point", "short_point", "nonfinite_parameter",
        "bearing_point", "duplicate_tip", "same_entity",
    ),
)
def test_stud_stock_refuses_wrong_geometry_configuration_or_trim(monkeypatch, fault):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    bearing, tip = stock.bearing_item, stock.top_item
    edges = [bearing, tip]
    if fault == "configuration":
        stock.front.ReferencedConfiguration = "Default"
    elif fault == "hlr":
        stock.front.GetDisplayMode2 = lambda: 1
    elif fault == "missing_bearing":
        edges = [tip]
    elif fault == "duplicate_bearing":
        edges.append(replace(bearing, edge=case.edge(stock.bearing.nearest)))
    elif fault == "one_wrong_endpoint":
        x, y, z = bearing.line[0]
        edges[0] = replace(bearing, line=((x, y + 0.001, z), bearing.line[1]))
    elif fault == "interior_bearing":
        edges[0] = replace(
            bearing, line=tuple((x, y, 0.0) for x, y, _z in bearing.line)
        )
    elif fault == "outside_segment":
        edges[0] = replace(bearing, line=(
            bearing.line[0],
            (bolt.HEAD_AF / 8, bolt.LENGTH, 7 * bolt.HEAD_AF / (8 * math.sqrt(3))),
        ))
    elif fault == "inner_runout":
        edges[0] = replace(
            bearing, line=None,
            circle=(0.0, bolt.LENGTH, 0.0, 0.0, 1.0, 0.0, BOLT_DIMS.major_dia / 2 + 0.0508),
        )
    elif fault in (
        "finished_tip", "major_chamfer_junction", "wrong_radius", "wrong_center",
        "wrong_axis", "nonfinite_circle",
    ):
        circle = list(tip.circle)
        if fault == "finished_tip":
            circle[1] = 0.0
        elif fault == "major_chamfer_junction":
            circle[1] += BOLT_DIMS.pitch * 0.851
            circle[6] = BOLT_DIMS.major_dia / 2
        elif fault == "wrong_radius":
            circle[6] += 0.001
        elif fault == "wrong_center":
            circle[0] = 0.001
        elif fault == "wrong_axis":
            circle[3:6] = (1.0, 0.0, 0.0)
        else:
            circle[6] = math.nan
        edges[1] = replace(tip, circle=tuple(circle))
    elif fault in ("false_trim_plane", "false_trim_radius"):
        point = list(stock.top.nearest)
        point[1 if fault == "false_trim_plane" else 2] += 2e-8
        stock.top.nearest = tuple(point)
    elif fault == "trim_requery":
        original = stock.top.GetClosestPointOn
        calls = []

        def closest(*point):
            calls.append(point)
            if len(calls) == 1:
                return original(*point)
            return (stock.top.nearest[0] + 1e-6, *stock.top.nearest[1:])

        stock.top.GetClosestPointOn = closest
    elif fault == "missing_point":
        stock.top.nearest = None
    elif fault == "short_point":
        stock.top.nearest = stock.top.nearest[:3]
    elif fault == "nonfinite_parameter":
        stock.top.nearest = (*stock.top.nearest[:3], math.nan, 0.0)
    elif fault == "bearing_point":
        stock.bearing.nearest = (0.0, bolt.LENGTH / 1000, 0.0, 0.0, 0.0)
    elif fault == "duplicate_tip":
        edges.append(replace(tip, edge=case.edge(stock.top.nearest)))
    elif fault == "same_entity":
        case.app.IsSame = lambda first, second: (
            1 if first is stock.bearing and second is stock.top else int(first is second)
        )
    stock.front.scan = ViewEdges("bad actual stock", tuple(edges))
    with pytest.raises(RuntimeError, match="SupplierStockLength"):
        bolt_drawing._stock_length_stations(case.adapter, stock.front)
    assert not case.creations and not case.selection_log


def test_stud_stock_uses_actual_trimmed_point_not_underlying_circle_extremum(monkeypatch):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    radius_m = stock.top_item.circle[6] / 1000
    actual = (radius_m / math.sqrt(2), stock.top.nearest[1], radius_m / math.sqrt(2))
    stock.top.nearest = (*actual, 0.4, math.nan)
    entities, points = bolt_drawing._stock_length_stations(case.adapter, stock.front)
    assert entities[1] is stock.top
    assert points[1] == actual
    assert stock.top.closest_calls[-1] == actual
    assert points[1] != (0.0, actual[1], radius_m)


def test_stud_stock_consumer_creates_native_linear_with_view_selection_and_creation_proof(monkeypatch):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    # A model IEntity.Select4 is deliberately unusable in this drawing context.
    for edge in (stock.bearing, stock.top):
        edge.Select4 = lambda *_args: pytest.fail("stock must select through IView")
    front, _iso, annotation = _create_stud_stock_reference(case, monkeypatch)
    assert front is stock.front and annotation is stock.annotation
    assert case.creations == [(0.130, 0.160, 0.0)]
    assert case.selection_log == [
        (stock.bearing, False, stock.front), (stock.top, True, stock.front),
    ]
    assert not case.selections and case.clears == [True, True]
    proofs = [
        fields for name, fields in case.events
        if name == "drawing.physical_axial_dimension_native_proof"
    ]
    assert len(proofs) == 1
    assert proofs[0]["label"] == "SupplierStockLength"
    assert proofs[0]["phase"] == "creation" and proofs[0]["type2"] == 2
    assert proofs[0]["measured_mm"] == pytest.approx(50.8)


@pytest.mark.parametrize("selection_index", [1, 2])
@pytest.mark.parametrize(
    "fault",
    (
        "activation", "select", "wrong_selected", "missing_selected", "duplicate_selected",
        "selection_count", "selection_type", "selection_point", "selection_point_readback",
        "null_creation", "native_exception",
    ),
)
def test_stud_stock_consumer_refuses_selection_null_or_creation_failure(
    monkeypatch, selection_index, fault,
):
    case = _stud_stock_case(monkeypatch)
    case.fault_index = selection_index
    # A duplicate selection requires the second selection slot.
    case.fault = fault
    if fault == "duplicate_selected":
        case.fault_index = 2
    if fault == "null_creation":
        case.result = None
    with pytest.raises(RuntimeError, match="SupplierStockLength|native insertion failed"):
        _create_stud_stock_reference(case, monkeypatch)
    assert not case.selections
    assert not any(
        name == "drawing.physical_axial_dimension_native_proof" for name, _ in case.events
    )


@pytest.mark.parametrize("phase", ["creation", "settled", "saved"])
@pytest.mark.parametrize("fault", ("angular", *_STUD_SPATIAL_FAULTS))
def test_stud_stock_native_proof_is_required_at_every_consumer(
    monkeypatch, tmp_path, phase, fault,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    elif phase == "settled":
        case = _settled_stud_height_case(monkeypatch)
    else:
        case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    if fault == "angular":
        stock.display.Type2 = 3
    else:
        _corrupt_stud_native_proof(stock, monkeypatch, fault)
    with pytest.raises(RuntimeError, match="SupplierStockLength"):
        if phase == "creation":
            _create_stud_stock_reference(case, monkeypatch)
        elif phase == "settled":
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )
        else:
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize(
    "fault",
    (
        "configuration", "missing_tip", "wrong_factory_radius", "missing_dimension",
        "duplicate_dimension", "owner", "annotation_owner", "format", "band",
    ),
)
def test_stud_stock_settled_and_saved_census_resolve_fresh_physical_stations(
    monkeypatch, tmp_path, phase, fault,
):
    case = (
        _saved_stud_height_case(monkeypatch, tmp_path) if phase == "saved"
        else _settled_stud_height_case(monkeypatch)
    )
    stock = case.stock_case
    if fault == "configuration":
        stock.front.ReferencedConfiguration = "Default"
    elif fault == "missing_tip":
        stock.front.scan = ViewEdges("lost factory tip", (stock.bearing_item,))
    elif fault == "wrong_factory_radius":
        stock.front.scan = ViewEdges("wrong factory rim", (
            stock.bearing_item,
            replace(
                stock.top_item,
                circle=(*stock.top_item.circle[:6], stock.top_item.circle[6] + 0.001),
            ),
        ))
    elif fault == "missing_dimension":
        stock.front.GetDisplayDimensions = lambda: ()
    elif fault == "duplicate_dimension":
        stock.front.GetDisplayDimensions = lambda: (stock.display, stock.display)
    elif fault == "owner":
        stock.front.name = "WrongStockFront"
    elif fault == "annotation_owner":
        stock.annotation.Owner = case.front
    elif fault == "format":
        stock.display.precision += 1
        monkeypatch.setattr(
            bolt_drawing, "assert_supplier_reference_dimension",
            lambda adapter, display, **settings: (
                supplier_dimensions.assert_supplier_reference_dimension(adapter, display, **settings)
                if settings["label"] == "SupplierStockLength" else None
            ),
        )
        monkeypatch.setattr(supplier_dimensions, "sheet_units", lambda _adapter: "mm")
    elif fault == "band":
        stock.native.Tolerance.Type = 2
    with pytest.raises(RuntimeError):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


@pytest.mark.parametrize("axis_scale", [-7.0, 0.25])
def test_stud_stock_circle_axis_is_compared_after_normalization(monkeypatch, axis_scale):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    tip = replace(
        stock.top_item,
        circle=(*stock.top_item.circle[:4], axis_scale, *stock.top_item.circle[5:]),
    )
    stock.front.scan = ViewEdges("nonunit axis", (stock.bearing_item, tip))
    entities, _points = bolt_drawing._stock_length_stations(case.adapter, stock.front)
    assert entities[1] is stock.top


@pytest.mark.parametrize("reverse", [False, True])
def test_stud_stock_frontmost_distinct_trim_ties_refuse_independent_of_order(monkeypatch, reverse):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    radius_m = stock.top_item.circle[6] / 1000
    angle = 0.4
    x, z = radius_m * math.sin(angle), radius_m * math.cos(angle)
    first = case.edge((x, stock.top.nearest[1], z, 0.4, 0.0))
    second = case.edge((-x, stock.top.nearest[1], z, 2.7, 0.0))
    edges = (
        stock.bearing_item, replace(stock.top_item, edge=first),
        replace(stock.top_item, edge=second),
    )
    stock.front.scan = ViewEdges("tied real arcs", tuple(reversed(edges)) if reverse else edges)
    with pytest.raises(RuntimeError, match="distinct.*frontmost tie"):
        bolt_drawing._stock_length_stations(case.adapter, stock.front)
    assert not case.creations


def test_stud_stock_settled_census_requires_both_native_physical_proofs(monkeypatch):
    case = _settled_stud_height_case(monkeypatch)
    bolt_drawing._assert_supplier_references(case.adapter, case.identities, case.configurations)
    proofs = [
        fields for name, fields in case.events
        if name == "drawing.physical_axial_dimension_native_proof"
    ]
    assert {(fields["label"], fields["phase"]) for fields in proofs} == {
        ("SupplierHeadHeight", "settled"), ("SupplierStockLength", "settled"),
    }
    assert {id(record[1]) for record in case.scans} == {id(case.front), id(case.stock_case.front)}


@pytest.mark.parametrize("name", ["SupplierHeadHeight", "SupplierStockLength"])
@pytest.mark.parametrize("fault", ["captured_sheet", "captured_configuration", "moved_sheet"])
def test_stud_saved_physical_census_requires_each_exact_sheet_and_source_configuration(
    monkeypatch, tmp_path, name, fault,
):
    case = _saved_stud_height_case(monkeypatch, tmp_path)
    is_stock = name == "SupplierStockLength"
    owner = case.identities[name][1]
    if fault == "captured_sheet":
        _sheet, configuration = case.configurations[owner]
        case.configurations[owner] = (
            bolt_drawing.SHEET_NAMES[0 if is_stock else 1], configuration,
        )
    elif fault == "captured_configuration":
        sheet, _configuration = case.configurations[owner]
        case.configurations[owner] = (
            sheet, "Default" if is_stock else bolt.SUPPLIER_STOCK_CONFIGURATION,
        )
    else:
        source = case.stock_case.front if is_stock else case.front
        other = case.front if is_stock else case.stock_case.front
        display = case.stock_case.display if is_stock else case.display
        original_source, original_other = source.GetDisplayDimensions, other.GetDisplayDimensions
        source.GetDisplayDimensions = lambda: tuple(
            value for value in original_source() if value is not display
        )
        other.GetDisplayDimensions = lambda: (*original_other(), display)
    with pytest.raises(RuntimeError, match=name):
        bolt_drawing._assert_saved_physical_references(
            case.adapter, case.identities, case.configurations,
            serialized_full_names=case.serialized_full_names,
            purchased_note=case.purchased_note_proof,
        )
    assert case.adapter.currentModel is case.previous_model
    if fault == "moved_sheet":
        assert case.close_calls == ["finished-stud.SLDDRW"]
    else:
        assert not case.open_calls and not case.close_calls


@pytest.mark.parametrize("fault", ["rebuild", "configuration_readback"])
def test_stud_stock_consumer_refuses_before_scan_when_stock_view_setup_fails(monkeypatch, fault):
    case = _stud_height_case(monkeypatch)

    class UnchangedConfiguration:
        ReferencedConfiguration = property(lambda self: "Default", lambda self, value: None)

    stock = (
        UnchangedConfiguration() if fault == "configuration_readback"
        else SimpleNamespace(ReferencedConfiguration="Default")
    )
    case.model.ActivateSheet = lambda _name: True
    case.model.EditRebuild3 = lambda: fault != "rebuild"
    monkeypatch.setattr(bolt_drawing, "place_view", lambda *_args, **_kwargs: stock)
    monkeypatch.setattr(bolt_drawing, "set_view_position", lambda *_args: True)
    monkeypatch.setattr(bolt_drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(
        bolt_drawing, "scan_view_edges",
        lambda *_args, **_kwargs: pytest.fail("must not scan a stale/finished stock view"),
    )
    with pytest.raises(RuntimeError, match="did not rebuild|references the finished bolt"):
        bolt_drawing._add_stock_reference(case.adapter)
    assert not case.selection_log and not case.creations


def test_stud_stock_geometry_evidence_keeps_actual_points_and_nearest_candidates_bounded(monkeypatch):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    wrong_lines = [
        replace(
            stock.bearing_item, edge=case.edge(None),
            line=tuple((x, y + index + 1, z) for x, y, z in stock.bearing_item.line),
        )
        for index in range(18)
    ]
    wrong_circles = [
        replace(
            stock.top_item, edge=case.edge(None),
            circle=(*stock.top_item.circle[:6], stock.top_item.circle[6] + index + 1),
        )
        for index in range(18)
    ]
    stock.front.scan = ViewEdges(
        "many visible stock edges",
        (*wrong_lines, *wrong_circles, stock.bearing_item, stock.top_item),
    )
    _entities, points = bolt_drawing._stock_length_stations(case.adapter, stock.front)
    geometry = next(
        fields for name, fields in case.events if name == "drawing.physical_stock_length_geometry"
    )
    assert geometry["line_count"] == geometry["circle_count"] == 19
    assert len(geometry["lines"]) == len(geometry["circles"]) == 12
    assert geometry["lines"][0]["native_point_m"] == points[0]
    assert geometry["circles"][0]["native_point_m"] == points[1]
    assert geometry["circles"][0]["membership_error_m"] == 0.0


@pytest.mark.parametrize("name", ["_stock_length_stations", "_assert_physical_stock_length"])
def test_stud_stock_native_entrypoints_are_traced(name):
    assert hasattr(getattr(bolt_drawing, name), "__wrapped__")


@pytest.mark.parametrize("phase", ["creation", "settled", "saved"])
@pytest.mark.parametrize("fault", ["null_document", "wrong_document", "empty_path", "relative_path"])
def test_stud_stock_requires_observed_native_source_document_at_every_consumer(
    monkeypatch, tmp_path, phase, fault,
):
    if phase == "saved":
        case = _saved_stud_height_case(monkeypatch, tmp_path)
    elif phase == "settled":
        case = _settled_stud_height_case(monkeypatch)
    else:
        case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    if fault == "null_document":
        stock.front.ReferencedDocument = None
    else:
        path = {
            "wrong_document": str(
                bolt_drawing.SOURCE.resolve().parent / "foreign" / bolt_drawing.SOURCE.name
            ),
            "empty_path": "",
            "relative_path": bolt_drawing.SOURCE.name,
        }[fault]
        stock.front.ReferencedDocument = SimpleNamespace(GetPathName=lambda: path)
    with pytest.raises(RuntimeError, match="SupplierStockLength.*native.*(document|source)"):
        if phase == "creation":
            _create_stud_stock_reference(case, monkeypatch)
        elif phase == "settled":
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )
        else:
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
    assert not any(record[1] is stock.front for record in case.scans)
    assert not case.creations
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model


def test_stud_stock_source_receipt_reports_observed_document_path_without_source_mutation(monkeypatch):
    case = _stud_stock_case(monkeypatch)
    stock = case.stock_case
    native_path = str(bolt_drawing.SOURCE.resolve())
    path_reads = []
    stock.front.ReferencedDocument = SimpleNamespace(
        GetPathName=lambda: path_reads.append(native_path) or native_path
    )
    bolt_drawing._stock_length_stations(case.adapter, stock.front)
    receipt = next(
        fields for name, fields in case.events if name == "drawing.physical_stock_length_source"
    )
    assert path_reads == [native_path]
    assert receipt["native_source_path"] == native_path
    assert receipt["configuration"] == bolt.SUPPLIER_STOCK_CONFIGURATION


@pytest.mark.parametrize("phase", ["settled", "saved"])
@pytest.mark.parametrize("name", ["SupplierHeadHeight", "SupplierStockLength"])
def test_stud_physical_census_refuses_missing_native_dimension_before_full_name_read(
    monkeypatch, tmp_path, phase, name,
):
    case = (
        _saved_stud_height_case(monkeypatch, tmp_path) if phase == "saved"
        else _settled_stud_height_case(monkeypatch)
    )
    display = case.display if name == "SupplierHeadHeight" else case.stock_case.display
    display.GetDimension2 = lambda _index: None
    with pytest.raises(RuntimeError, match="dimension has no native identity"):
        if phase == "saved":
            bolt_drawing._assert_saved_physical_references(
                case.adapter, case.identities, case.configurations,
                serialized_full_names=case.serialized_full_names,
                purchased_note=case.purchased_note_proof,
            )
        else:
            bolt_drawing._assert_supplier_references(
                case.adapter, case.identities, case.configurations
            )
    if phase == "saved":
        assert case.close_calls == ["finished-stud.SLDDRW"]
        assert case.adapter.currentModel is case.previous_model
