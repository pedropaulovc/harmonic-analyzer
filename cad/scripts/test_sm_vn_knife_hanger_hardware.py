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
import build_sm_summing_assembly as asm
import build_sm_vn_knife_hanger_stud as bolt_part
import build_sm_vn_knife_hanger_washer as washer_part
import draw_sm_vn_knife_hanger_stud as bolt_drawing
import draw_sm_vn_knife_hanger_washer as washer_drawing
import sm_vn_knife_hanger_stud_spec as bolt
import sm_vn_knife_hanger_washer_spec as washer
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _hole_spec import TAP_DRILL_MM
from _mcmaster_92314a253 import DIMS as BOLT_DIMS
from _mcmaster_96659a104 import DIMS as WASHER_DIMS
from _printed_angular_tolerance import angular_band_deg
from _printed_tolerance import printed_band_mm
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


def test_native_part_controls_keep_reference_length_and_tip_limits(monkeypatch):
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
        lambda *_args: None,
    )
    bolt_part._manufacturing_controls(None)
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


class _KnifeHangerSheet:
    def __init__(self, name):
        self.name = name
        self.views = []
        self.notes = []

    def SetName(self, name):
        self.name = name

    def GetName(self):
        return self.name

    def GetNextView(self):
        return self.views[0] if self.views else None

    def GetAnnotations(self):
        return tuple(note.GetAnnotation() for note in self.notes)


class _KnifeHangerDrawing:
    """Native document/sheet state, without pretending to prove CAD geometry."""

    def __init__(self):
        self.sheets = [_KnifeHangerSheet("Sheet1")]
        self.active = self.sheets[0]
        self.selection = None
        self.copied = None
        self.edit_sheet = True
        self.Extension = SimpleNamespace(SelectByID2=self.select)

    def GetCurrentSheet(self):
        return self.active

    def GetSheetNames(self):
        return tuple(sheet.name for sheet in self.sheets)

    def ActivateSheet(self, name):
        for sheet in self.sheets:
            if sheet.name == name:
                self.active = sheet
                return True
        return False

    def GetFirstView(self):
        return self.active

    def ClearSelection2(self, _all):
        self.selection = None

    def select(self, name, kind, *_args):
        self.selection = next(
            (sheet for sheet in self.sheets if kind == "SHEET" and sheet.name == name),
            None,
        )
        return self.selection is not None

    def EditCopy(self):
        self.copied = self.selection

    def PasteSheet(self, _position, _rename):
        if self.copied is None or self.copied.views:
            return False
        self.active = _KnifeHangerSheet(f"Sheet{len(self.sheets) + 1}")
        self.sheets.append(self.active)
        return True

    def ActivateView(self, name):
        self.edit_sheet = not name
        return bool(name)

    def GetEditSheet(self):
        return self.edit_sheet

    def EditRebuild3(self):
        return True


class _KnifeHangerView:
    def __init__(self, sheet, orientation, x, y, scale):
        self.sheet = sheet
        self.orientation = orientation
        self.Position = (x, y)
        self.ScaleRatio = scale
        self.ReferencedConfiguration = "Default"
        self.dimensions = {}
        self.callouts = []
        sheet.views.append(self)

    def GetName2(self):
        return f"{self.sheet.name}-{self.orientation}"

    def GetNextView(self):
        index = self.sheet.views.index(self) + 1
        return self.sheet.views[index] if index < len(self.sheet.views) else None

    def SetViewPosition(self, position, _move_children):
        self.Position = tuple(getattr(position, "value", position))
        return True

    def GetDisplayDimensions(self):
        return tuple(self.dimensions.values())


@pytest.mark.parametrize("fault", [None, "callout", "link", "text"])
def test_sheet_prints_purchased_note_and_chamfer_leader_with_native_readback(
    monkeypatch, tmp_path, fault
):
    import _drawing_sheets as drawing_sheets
    from solidworks_mcp.adapters.solidworks import drawing as native_drawing

    source = tmp_path / "sm-vn-knife-hanger-stud.SLDPRT"
    source.touch()
    properties = {
        "Purchased Screw Note": _config.parts(bolt_part.PART_NAME)["purchased_note"],
        "Supplier Reference Title": bolt_drawing.SUPPLIER_STOCK_TITLE,
    }
    document = _KnifeHangerDrawing()

    async def open_model(_path):
        pass

    def get_attr_or_call(value, name):
        attribute = getattr(value, name)
        return attribute() if callable(attribute) else attribute

    adapter = SimpleNamespace(
        currentModel=object(),
        open_model=open_model,
        _attempt=lambda operation, **_kwargs: operation(),
        _get_attr_or_call=get_attr_or_call,
    )

    def new_drawing(_adapter, *_args, **_kwargs):
        _adapter.currentModel = document
        return document, document.GetCurrentSheet()

    async def finalize(_adapter, *_args, expected_sheet_names, **_kwargs):
        assert _adapter.currentModel is document
        assert document.GetSheetNames() == tuple(expected_sheet_names)
        return {"drawing": "recorded"}

    def place_view(_adapter, _source, orientation, x, y, *, scale):
        return _KnifeHangerView(document.active, orientation, x, y, scale)

    def read_properties(_model, names, *, required):
        properties.update({name: properties.get(name, name) for name in names})
        assert all(properties[name] for name in required)
        return properties

    def display_dimension(view, name):
        native = SimpleNamespace(
            FullName=f"{name}@SupplierReference@native-part.SLDPRT"
        )
        display = SimpleNamespace(
            name=name,
            OffsetText=False,
            GetText=lambda _index: (
                bolt.DIMENSION_CALLOUTS.get(name, "").replace("\n", "\r\n")
                + (" WRONG" if fault == "callout" else "")
            ),
            GetDimension2=lambda _index: native,
        )
        annotation = SimpleNamespace(
            name=name,
            Owner=view,
            position=None,
            GetSpecificAnnotation=lambda: display,
            GetAttachedEntities3=lambda: (),
            GetAttachedEntityTypes=lambda: (),
        )
        display.GetAnnotation = lambda: annotation
        view.dimensions[name] = display
        return display

    def annotations(_adapter, view, *, keep, **_kwargs):
        return [display_dimension(view, name).GetAnnotation() for name in keep]

    def offset_text(_adapter, annotations, positions):
        for annotation in annotations:
            if annotation.name in positions:
                annotation.GetSpecificAnnotation().OffsetText = True
                annotation.position = positions[annotation.name]

    def project(_adapter, view, xyz, *, label):
        scale = view.ScaleRatio[0] / view.ScaleRatio[1]
        return tuple(view.Position[index] + scale * xyz[index] for index in (0, 1))

    def project_points(_adapter, view, points, *, label):
        return [project(_adapter, view, point, label=label) for point in points]

    def linked_note(owner, property_name, *, bad_link=False, bad_text=False):
        link = bolt_drawing.property_link(
            "Wrong Property" if bad_link else property_name
        )
        text = properties[property_name].replace("\n", "\r\n")
        note = SimpleNamespace(
            PropertyLinkedText=link,
            GetText=lambda: text + (" WRONG" if bad_text else ""),
        )
        annotation = SimpleNamespace(
            Owner=owner,
            OwnerType=1 if isinstance(owner, _KnifeHangerSheet) else 2,
            GetType=lambda: 6,
            GetSpecificAnnotation=lambda: note,
        )
        note.GetAnnotation = lambda: annotation
        return note

    def callout(_adapter, view, *, property_name, edge_xy, note_xy):
        note = linked_note(
            view, property_name, bad_link=fault == "link", bad_text=fault == "text"
        )
        note.edge_xy = edge_xy
        note.position = note_xy
        view.callouts.append(note)
        return note

    def sheet_note(_adapter, property_name, *_position):
        note = linked_note(document.active, property_name)
        document.active.notes.append(note)
        return note

    for name in (
        "check",
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "verify_cut_length_reference",
        "verify_machining_controls",
        "set_dimension_callouts",
    ):
        monkeypatch.setattr(bolt_drawing, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bolt_drawing, "SOURCE", source)
    monkeypatch.setattr(bolt_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing_sheets, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        native_drawing._sw_type_info, "early_bound", lambda value, *_args: value
    )
    monkeypatch.setattr(
        native_drawing._sw_type_info, "early_bound_or_flag", lambda value, *_args: value
    )
    monkeypatch.setattr(
        bolt_drawing, "dimension_name", lambda _adapter, item: item.name
    )
    monkeypatch.setattr(bolt_drawing, "read_required_properties", read_properties)
    monkeypatch.setattr(bolt_drawing, "new_project_drawing", new_drawing)
    monkeypatch.setattr(bolt_drawing, "place_view", place_view)
    monkeypatch.setattr(bolt_drawing, "curate_view_dimensions", annotations)
    monkeypatch.setattr(bolt_drawing, "offset_dimension_text", offset_text)
    monkeypatch.setattr(bolt_drawing, "model_point_in_view", project)
    monkeypatch.setattr(bolt_drawing, "model_points_in_view", project_points)
    monkeypatch.setattr(
        bolt_drawing,
        "add_edge_dimension",
        lambda _adapter, view, *, label, **_kwargs: display_dimension(view, label),
    )
    # This test owns note/control readback and real document transitions;
    # supplier dimension formatting has its own native-inventory tests.
    monkeypatch.setattr(
        bolt_drawing,
        "_format_supplier_reference",
        lambda _adapter, display, _name: display.GetAnnotation(),
    )
    monkeypatch.setattr(bolt_drawing, "add_property_linked_callout", callout)
    monkeypatch.setattr(bolt_drawing, "add_property_linked_note", sheet_note)
    monkeypatch.setattr(bolt_drawing, "finalize_drawing", finalize)
    if fault is not None:
        with pytest.raises(RuntimeError, match="did not persist"):
            asyncio.run(bolt_drawing.build(adapter))
        return

    assert asyncio.run(bolt_drawing.build(adapter)) == {"drawing": "recorded"}
    finished, stock = document.sheets
    assert len(finished.views) == len(stock.views) == 2
    assert all(
        view.ReferencedConfiguration != bolt_drawing.SUPPLIER_STOCK_CONFIGURATION
        for view in finished.views
    )
    assert all(
        view.ReferencedConfiguration == bolt_drawing.SUPPLIER_STOCK_CONFIGURATION
        for view in stock.views
    )
    front = next(view for view in finished.views if view.orientation == "*Front")
    chamfer = front.dimensions["ChamferWidth"]
    assert chamfer.OffsetText
    assert chamfer.GetAnnotation().position == bolt_drawing.CHAMFER_TEXT_XY
    (purchased_note,) = front.callouts
    assert purchased_note.PropertyLinkedText == bolt_drawing.property_link(
        "Purchased Screw Note"
    )
    assert purchased_note.GetText().replace("\r", "") == properties[
        "Purchased Screw Note"
    ]
    head_xy = project(
        adapter,
        front,
        (bolt.HEAD_AF / 4000, bolt.HEAD_TOP_Y / 1000, 0.0),
        label="head",
    )
    assert purchased_note.edge_xy == pytest.approx(head_xy)
    assert not finished.notes
    (caption,) = stock.notes
    assert caption.GetAnnotation().Owner is stock
    assert caption.GetAnnotation().OwnerType == 1
    assert caption.PropertyLinkedText == bolt_drawing.property_link(
        "Supplier Reference Title"
    )
    assert caption.GetText().replace("\r", "") == properties["Supplier Reference Title"]


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
