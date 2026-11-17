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
import sm_vn_knife_hanger_stud_spec as bolt
import sm_vn_knife_hanger_washer_spec as washer
from _buildgraph import module_deps_of
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
    assert stamped["Supplier Reference Title"] == bolt.SUPPLIER_STOCK_TITLE
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


