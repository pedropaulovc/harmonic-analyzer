"""Every fit band a build script hands to SolidWorks is valid at import time.

A band only reaches ``_fit_deviations.deviations`` (or the bilateral setter) inside
``build()``, which needs a SolidWorks seat. So an inverted or zero-width band
used to pass the whole offline suite and fail its farm leaf instead: warm-c486
lost ``part:dt_crank_drive_gear`` to "fit band is inverted: (0.025, 0.025)" at
``build_crank_drive_gear.build()`` -> ``deviations(BORE_DIA_BAND)``.

This file finds every band consumer by reading the scripts' source, resolves each
argument in the imported module (the value ``build()`` would see), and applies
the same checks ``build()`` would:

* ``deviations(band)`` / ``fit_limits(nominal, band)`` / ``band_text(band)`` and
  ``_feature_requirements.limits(model, places, band)`` take ``(upper, lower)``;
  the helper must accept it and return lower < upper.
* ``set_dimension_bilateral_tolerance(..., *BAND)`` splats ``(lower, upper)``
  straight into the setter, which refuses lower >= upper.

A second test inventories every module-level ``*_BAND`` / ``*_BANDS`` /
``*_BAND_MM`` tuple in the ``build_*``, ``*_spec``, ``*_geometry`` and ``*_geom``
modules. Each must be fed to a checked consumer, be listed in
``INDEXED_FIT_BANDS`` (a fit band read by index, checked the same way), or be
listed in ``NOT_FIT_BANDS`` with the reason it is not a fit.

Isolated AST-source controls also exercise both scanners and their source
anchors against empty discovery and one-directory-deep source moves.
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import _fit_close_running
import _fit_deviations
import _fit_text
import _gear_fit_limits

SCRIPTS = Path(__file__).resolve().parent

# Helpers that take an (upper, lower) band, and the positional index of the band.
_BAND_HELPERS = {"deviations": 0, "band_text": 0, "fit_limits": 1, "limits": 2}
_SETTER = "set_dimension_bilateral_tolerance"

# A consumer whose argument is a name local to build() (so it cannot be read off
# the imported module) must say here which module-level expression build()
# derives it from. "each" checks a tuple of bands; "values" checks a band mapping.
LOCAL_BAND_SOURCES: dict[tuple[str, str], tuple[str, str]] = {
    # for section, band in enumerate(SECTION_DIA_BANDS): ... deviations(band)
    ("build_dt_cone_gear_shaft", "band"): ("SECTION_DIA_BANDS", "each"),
    # def gear_tip_band_mm(grade): band = ...; deviations(band)
    ("_gear_fit_limits", "band"): (
        "(gear_tip_band_mm('standard'), gear_tip_band_mm('contact_critical'))",
        "each",
    ),
    # Fixture builders apply the same bands their specs publish on the sheet.
    ("build_ch_rocker_arm_tl_c_stop_bar", "band"): ("DRAWING_BANDS", "values"),
    ("build_ch_rocker_arm_tl_diamond_pin", "band"): ("DRAWING_BANDS", "values"),
    ("build_ch_rocker_arm_tl_inspection_box", "band"): ("DRAWING_BANDS", "values"),
    # def _printed_limits(nominal, places): ... GENERAL_BAND_BY_PLACES[places]
    ("dt_cone_tip_block_spec", "GENERAL_BAND_BY_PLACES[places]"): (
        "GENERAL_BAND_BY_PLACES",
        "values",
    ),
    # for configuration, teeth in CONFIGS: band = band_for(teeth); deviations(band)
    ("build_dt_cone_gear", "band"): (
        "(blank_dia_band(6), tooth_thickness_band(6),"
        " blank_dia_band(12), tooth_thickness_band(12))",
        "each",
    ),
    # for name, band in (("BlankDia", blank_dia_band(teeth)), ...): deviations(band)
    ("draw_dt_cone_gear", "band"): (
        "(blank_dia_band(6), tooth_thickness_band(6),"
        " blank_dia_band(12), tooth_thickness_band(12))",
        "each",
    ),
    # for feature, name, band_for in _BANDED_DIMENSIONS: band = band_for(teeth)
    ("_cone_gear_readback", "band"): (
        "(blank_dia_band(6), tooth_thickness_band(6),"
        " blank_dia_band(12), tooth_thickness_band(12))",
        "each",
    ),
}

# Consumer modules that cannot be imported without SolidWorks, with the reason.
# Empty today: every band consumer imports offline.
OFFLINE_IMPORT_EXCLUSIONS: dict[str, str] = {}

# Module-level *_BAND tuples that are not fit bands, so no checked consumer
# reads them. A new band tuple must be fed to a consumer above or listed here.
NOT_FIT_BANDS: dict[tuple[str, str], str] = {
    ("build_dt_drive_train_assembly", "ARBOR_PED_SOUTH_Z_BAND"): (
        "plan z extent of the south pedestal foot (clearance geometry)"
    ),
    ("build_dt_drive_train_assembly", "ARBOR_PED_NORTH_Z_BAND"): (
        "plan z extent of the north pedestal foot (clearance geometry)"
    ),
    # The 16T/T120 and row checks (c'' variant B): print-worst (lower, upper)
    # deviations already derived by printed_deviations/deviations from each
    # printed band, corners of the clearance scans rather than fits.
    ("build_dt_drive_train_assembly", "_PINION_FACE_BAND"): (
        "16T face print-worst deviations (clearance/engagement corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_SHOULDER_BAND"): (
        "16T shoulder print-worst deviations (T120 air corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_TIP_RADIUS_BAND"): (
        "16T tip-radius print-worst deviations (T120 air corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_TURNED_DIA_BAND"): (
        "16T turned-band diameter print-worst deviations (T120 radial and band contact corners)"
    ),
    ("build_dt_drive_train_assembly", "_BOSS_NORTH_BAND"): (
        "post crank-boss north face print-worst deviations (16T station corners)"
    ),
    ("build_dt_drive_train_assembly", "_CONE_BOSS_NORTH_BAND"): (
        "post cone-boss north face print-worst deviations (cone stack corners)"
    ),
    ("build_dt_drive_train_assembly", "_COLLAR_WIDTH_BAND"): (
        "cone-shaft collar print-worst deviations (cone stack corners)"
    ),
    ("build_dt_drive_train_assembly", "_CRANK_HEIGHT_BAND"): (
        "crank-above-cone print-worst deviations (radial clearance corners)"
    ),
    ("build_dt_drive_train_assembly", "_T120_NORTH_BAND"): (
        "T120 north-face (upper, lower) station band sampled by the T120 scan"
    ),
    ("build_dt_drive_train_assembly", "_ARB_Z_BANDS"): (
        "(z extent, minimum gap) pairs for the swing-plate clearance sweep"
    ),
    ("build_dt_drive_train_assembly", "_SWING_RIG_BANDS"): (
        "(z low, z high, name) pinion-rig extents for the engage-swing sweep"
    ),
    ("build_dt_drive_train_assembly", "_SPRING_Z_BAND"): (
        "plan z extent of the return spring for the engage-swing sweep"
    ),
    ("build_dt_drive_train_assembly", "CRANK_COLUMN_BANDS"): (
        "(z front, z rear, diameter, name) crank-seat column extents for the "
        "radial clearance sweep"
    ),
    ("dt_pinion_spring_geometry", "FORMED_CONTACT_BANDS"): (
        "names of the formed dimensions the contact corners perturb, not a band"
    ),
    ("vn_transgear_arm_plate_screw_spec", "STOCK_LENGTH_BAND"): (
        "the oval-head screw's B18.6.3 length tolerance (plus, minus): indexed "
        "for the shortest stock left proud of the arm before its cut"
    ),
    ("vn_transgear_disc_screw_spec", "STOCK_LENGTH_BAND"): (
        "the fillister screw's B18.6.3 length tolerance (plus, minus): indexed "
        "for the stock's reach past the disc's rear face before its cut"
    ),
    ("vn_guide_lock_screw_spec", "SHANK_LEN_BAND"): (
        "the button-head screw's B18.6.3 length tolerance (plus, minus): "
        "indexed for the shortest reach into the platen guide's through tap"
    ),
    ("vn_cylinder_bank_spring_spec", "ID_BAND"): (
        "McMaster 9714K392's catalogue ID tolerance (plus, minus): indexed for "
        "the tightest spring against the largest arbor"
    ),
    ("vn_cylinder_bank_spring_spec", "OD_BAND"): (
        "McMaster 9714K392's catalogue OD tolerance (plus, minus): indexed for "
        "its seat on the washer and strap faces"
    ),
    ("vn_rocker_bank_spring_spec", "ID_BAND"): (
        "McMaster 9714K24's catalogue ID tolerance (plus, minus): indexed to show "
        "it reaches under the pivot shaft (the slide-free check at fit-up)"
    ),
    ("vn_rocker_bank_spring_spec", "OD_BAND"): (
        "McMaster 9714K24's catalogue OD tolerance (plus, minus): indexed for "
        "the largest spring under the hub's O10.2"
    ),
}

# (upper, lower) fit bands that no helper reads: the owning module indexes them
# to print or derive limits. An inverted one prints wrong limits, so they get
# the same check as a helper-fed band.
INDEXED_FIT_BANDS: dict[tuple[str, str], str] = {
    ("dt_alignment_pinion_spec", "BASE_TANGENT_SPAN_BAND"): (
        "indexed into the span-measurement note text"
    ),
    ("dt_cone_gear_shaft_spec", "STOCK_DIA_BAND"): (
        "the 5/8 bar's supplied size band, indexed for the thrust ring's "
        "worst-case width (THRUST_RING_MIN)"
    ),
    ("vn_cone_pivot_screw_spec", "SHOULDER_DIA_BAND"): (
        "McMaster 91829A560 supplied shoulder diameter +0/-0.0254 mm; "
        "upper/lower deviations used by the platform's stock pivot fit"
    ),
    ("vn_cone_pivot_screw_spec", "SHOULDER_LEN_BAND"): (
        "McMaster 91829A560 supplied shoulder length +0.0508/0 mm; "
        "upper/lower deviations used by the platform's stock axial stack"
    ),
    ("dt_crankshaft_spec", "SEAT_COLLAR_BAND"): (
        "the seat face's station deviations, indexed for the hub-to-sprocket air"
    ),
    ("pd_transgear_removable_spec", "PLATE_BAND"): (
        "the wheel plate's thickness deviations, indexed for the hub-to-sprocket "
        "air and the chain envelope's reach"
    ),
    ("ch_connecting_rod_spec", "RING_THICKNESS_BAND"): (
        "2.200 plate at three places stated in note 2 (title-block linear_3pl), "
        "indexed by cylinder_bank_layout for the thickest ring its cam slot holds"
    ),
    ("ch_bar_pivot_pin_spec", "PIN_BLANK_LENGTH_BAND"): (
        "the drill-rod blank's cut-length deviations: indexed into the blank "
        "note and the dressing-stock stack (blank_excess_min/max)"
    ),
    ("dt_cylinder_gear_spec", "WHOLE_DEPTH_BAND"): (
        "indexed into the cylinder gear-data whole-depth limits"
    ),
    ("ch_connecting_rod_spec", "SHANK_THICKNESS_BAND"): (
        "same 2.200 plate as the ring (note 2), indexed by cylinder_bank_layout "
        "for the thickest shank its cam slot holds"
    ),
    ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"): (
        "centred (cylinder_bank_layout asserts it): indexed as the symmetric "
        "tolerance and the fit-up mic limits"
    ),
    ("dt_pinion_arbor_collar_spec", "BORE_BAND"): (
        "the title block's drilled-hole row, indexed for the slide-clearance, "
        "wall and pin-end-depth stacks (not printed on the bore)"
    ),
    ("dt_pinion_arbor_geometry", "DRUM_LEN_BAND"): "indexed into the drum-length limits",
    ("dt_pinion_handle_geometry", "ROD_DIA_BAND"): (
        "indexed by pinion_arbor_spec for the cross-rod fit limits"
    ),
    ("dt_cone_swing_platform_pivot_spec", "PIVOT_HOLE_BAND"): (
        "the pivot bore reamed 6.350 H7 on the 91829A560 shoulder: indexed into "
        "the Hole Wizard diameter tolerance, the cone set stack's and support "
        "pose's pivot float and the assembly's pivot air"
    ),
    ("vn_cone_tip_collar_spec", "BORE_DIA_BAND"): (
        "the finished bore's seat band, indexed to re-centre the modelled bore "
        "(BORE_MODEL_DIA_BAND, the band the build sets natively)"
    ),
    ("ch_rocker_thrust_washer_spec", "BORE_BAND"): (
        "the title block's drilled-hole row, indexed for the washer's wall "
        "floor and the spring-on-face check (not printed on the bore)"
    ),
    ("ch_rocker_arm_spec", "PIVOT_HOLE_BAND"): (
        "indexed into the hub's wall floor (HUB_DIA_MIN); the build also "
        "sets it natively on PivotDia"
    ),
    ("vn_transgear_collar_cross_pin_spec", "HOLE_BAND"): (
        "the spring pin's drilled cross hole (functional, R9-11): indexed for "
        "HOLE_MAX against the B18.8.2 window and the fit-up step's limits"
    ),
    ("vn_transgear_knob_cup_pin_spec", "HOLE_BAND"): (
        "MHA-VN-037's cross-hole band reused for the hole match-drilled through "
        "cup and journal: indexed for HOLE_MAX against the B18.8.2 window"
    ),
    ("vn_transgear_latch_pin_spec", "DIA_BAND"): (
        "the pressed dowel's catalogue diameter: read by min/max for the press "
        "interference against the arm's blind hole"
    ),
    ("vn_knife_mount_dowel_spec", "DIA_BAND"): (
        "the pressed dowel's catalogue diameter: read by min/max for the press "
        "interference against the knife mount's reamed blind hole"
    ),
    ("vn_knife_hanger_stud_spec", "LENGTH_BAND"): (
        "the socket head screw's catalogue length tolerance: indexed into "
        "LENGTH_MIN/LENGTH_MAX for the tap reach and bottoming stack"
    ),
    ("ch_rocker_arm_tl_profile_fixture_spec", "ROD_PIN_XY_BAND"): (
        "indexed for the symmetric rod-pin coordinate tolerance and position budget"
    ),
    ("ch_rocker_arm_tl_profile_fixture_spec", "DRILLED_BAND"): (
        "indexed by _feature_requirements.limits for drilled-hole inspection limits"
    ),
    ("ch_rocker_arm_tl_vise_stop_spec", "SCREW_LENGTH_BAND"): (
        "indexed for the ISO 4762 screw's minimum engagement and maximum protrusion"
    ),
    ("dt_cone_pivot_post_tl_saw_cradle_spec", "DRILLED_BAND"): (
        "indexed by _feature_requirements.limits for the stud-drill inspection limits"
    ),
    ("ch_rocker_arm_tl_c_stop_bar_spec", "DRILLED_BAND"): (
        "indexed by _feature_requirements.limits for screw-hole inspection limits"
    ),
    ("ch_rocker_arm_tl_inspection_box_spec", "DRILLED_BAND"): (
        "indexed by _feature_requirements.limits for tap-drill inspection limits"
    ),
    ("ch_rocker_arm_tl_filing_button_spec", "BORE_BAND"): (
        "matched-fit design intent, indexed by filing_stud_spec for bore clearance"
    ),
    ("ch_rocker_arm_tl_filing_stud_spec", "BODY_BAND"): (
        "matched-fit design intent, indexed for the rocker and filing-button clearances"
    ),
    ("ch_rocker_arm_tl_pivot_screw_spec", "SHOULDER_BAND"): (
        "matched-fit design intent, indexed for the rocker and fixture-bore clearances"
    ),
    ("ch_rocker_arm_tl_pivot_screw_spec", "HEAD_BAND"): (
        "matched-fit design intent, indexed for the outline-template bush clearance"
    ),
    ("ch_rocker_arm_tl_profile_fixture_spec", "STAND_DROP_BAND"): (
        "indexed for the hub-shim gap, strap air and stand-pocket engagement"
    ),
}

KNOWN_BAD: dict[str, pytest.MarkDecorator] = {}


@dataclass(frozen=True)
class BandUse:
    module: str  # consumer module stem
    line: int
    expression: str  # the argument as written
    order: str  # "upper_lower" (helpers) or "lower_upper" (setter splat)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _band_uses() -> list[BandUse]:
    uses: list[BandUse] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in _BAND_HELPERS:
                index = _BAND_HELPERS[name]
                if len(node.args) > index:
                    arg = node.args[index]
                    uses.append(
                        BandUse(path.stem, node.lineno, ast.unparse(arg), "upper_lower")
                    )
            elif name == _SETTER:
                # A splat that is not itself a helper call hands the setter a
                # raw (lower, upper) pair.
                for arg in node.args:
                    if isinstance(arg, ast.Starred) and not isinstance(
                        arg.value, ast.Call
                    ):
                        uses.append(
                            BandUse(
                                path.stem,
                                node.lineno,
                                ast.unparse(arg.value),
                                "lower_upper",
                            )
                        )
    return uses


BAND_USES = _band_uses()


def _import(module: str) -> Any:
    if module in OFFLINE_IMPORT_EXCLUSIONS:
        pytest.skip(f"{module}: {OFFLINE_IMPORT_EXCLUSIONS[module]}")
    return importlib.import_module(module)


def _resolve(use: BandUse) -> list[tuple[str, Any]]:
    """The value(s) build() passes, read from the imported consumer module."""
    module = _import(use.module)
    key = (use.module, use.expression)
    if key in LOCAL_BAND_SOURCES:
        source, how = LOCAL_BAND_SOURCES[key]
        value = eval(source, vars(module))  # noqa: S307 -- repo source
        if how == "values":
            return [(f"{source}[{places!r}]", band) for places, band in value.items()]
        assert how == "each", f"unknown local-source mode {how!r}"
        return [(f"{source}[{i}]", band) for i, band in enumerate(value)]
    try:
        value = eval(use.expression, vars(module))  # noqa: S307 -- repo source
    except NameError as error:
        raise AssertionError(
            f"{use.module}:{use.line}: band argument {use.expression!r} is not a "
            "module-level value, so this test cannot see what build() passes. Add "
            "it to LOCAL_BAND_SOURCES with the module-level value it derives from."
        ) from error
    return [(use.expression, value)]


@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        ("build_ch_rocker_arm_tl_c_stop_bar", "DRAWING_BANDS"),
        ("build_ch_rocker_arm_tl_inspection_box", "DRAWING_BANDS"),
        (
            "build_ch_rocker_arm_tl_diamond_pin",
            "(LAND_BAND, LAND_HEIGHT_BAND, SHANK_BAND, NECK_BAND, REAM_BAND, COLLAR_END_BAND)",
        ),
    ],
)
def test_fixture_local_sources_cover_every_band(module_name: str, expected: str) -> None:
    module = _import(module_name)
    source = eval(expected, vars(module))  # noqa: S307 -- repo source
    bands = list(source.values()) if isinstance(source, dict) else list(source)
    resolved = _resolve(BandUse(module_name, 0, "band", "upper_lower"))
    assert [band for _, band in resolved] == bands
    assert all(any(band is actual for _, actual in resolved) for band in bands)


def _check_band(label: str, band: Any, order: str) -> None:
    assert isinstance(band, tuple) and len(band) == 2, f"{label}: not a 2-tuple: {band!r}"
    assert all(isinstance(v, (int, float)) for v in band), f"{label}: {band!r}"
    if order == "upper_lower":
        # Exactly what build() does; raises on an inverted or zero-width band.
        lower, upper = _fit_deviations.deviations(band)
    else:
        lower, upper = band
    assert lower < upper, f"{label}: lower {lower} >= upper {upper} ({order})"
    assert upper - lower > 0.0, f"{label}: zero-width band {band!r}"


def _case_ids() -> list[Any]:
    params = []
    seen: set[str] = set()
    for use in BAND_USES:
        case_id = f"{use.module}:{use.expression}"
        if case_id in seen:
            continue
        seen.add(case_id)
        marks = [KNOWN_BAD[case_id]] if case_id in KNOWN_BAD else []
        params.append(pytest.param(use, id=case_id, marks=marks))
    return params


def test_band_uses_are_found() -> None:
    # A scanner that silently finds nothing would pass every case below.
    helpers = [u for u in BAND_USES if u.order == "upper_lower"]
    assert len(helpers) >= 50, f"band consumer scan found only {len(helpers)} helper uses"
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    assert "build_dt_crank_drive_gear:BORE_DIA_BAND" in ids, (
        "missing band consumer anchor: build_dt_crank_drive_gear:BORE_DIA_BAND"
    )
    assert "build_dt_cone_gear_shaft:band" in ids, (
        "missing band consumer anchor: build_dt_cone_gear_shaft:band"
    )
    # Per-source anchors: neither the new fixture builders nor their exported
    # limit consumers may disappear behind a rich unrelated source's count.
    for module in (
        "build_ch_rocker_arm_tl_c_stop_bar",
        "build_ch_rocker_arm_tl_diamond_pin",
        "build_ch_rocker_arm_tl_inspection_box",
    ):
        assert f"{module}:band" in ids, f"missing band consumer anchor: {module}:band"
    for module in (
        "ch_rocker_arm_tl_c_stop_bar_spec",
        "ch_rocker_arm_tl_inspection_box_spec",
        "ch_rocker_arm_tl_profile_fixture_spec",
        "ch_rocker_arm_tl_vise_stop_spec",
        "dt_cone_pivot_post_tl_saw_cradle_spec",
    ):
        assert f"{module}:DRILLED_BAND" in ids, (
            f"missing band consumer anchor: {module}:DRILLED_BAND"
        )


def test_known_bad_ids_are_live() -> None:
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    assert set(KNOWN_BAD) <= ids, set(KNOWN_BAD) - ids
    assert set(LOCAL_BAND_SOURCES) <= {(u.module, u.expression) for u in BAND_USES}


@pytest.mark.parametrize("use", _case_ids())
def test_every_band_build_passes_is_valid(use: BandUse) -> None:
    for label, band in _resolve(use):
        _check_band(f"{use.module}:{use.line} {label}", band, use.order)


def _inventory() -> list[tuple[str, str]]:
    """(module, name) of every module-level *_BAND / *_BANDS / *_BAND_MM
    assignment whose value is a tuple, in the band-owning module families."""
    found: list[tuple[str, str]] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        stem = path.stem
        if not (
            stem.startswith("build_")
            or stem.endswith(("_spec", "_geometry", "_geom"))
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith(
                    ("_BAND", "_BANDS", "_BAND_MM")
                ):
                    found.append((stem, target.id))
    return found


def test_every_band_tuple_is_checked_or_classified() -> None:
    checked: set[int] = set()
    for use in BAND_USES:
        if use.module in OFFLINE_IMPORT_EXCLUSIONS:
            continue
        module = importlib.import_module(use.module)
        key = (use.module, use.expression)
        if key in LOCAL_BAND_SOURCES:
            source = eval(LOCAL_BAND_SOURCES[key][0], vars(module))  # noqa: S307
            checked.add(id(source))
            checked.update(id(band) for _, band in _resolve(use))
            continue
        try:
            checked.add(id(eval(use.expression, vars(module))))  # noqa: S307
        except NameError:
            continue  # reported by the per-use test
    unclassified = []
    for module_name, name in _inventory():
        value = getattr(importlib.import_module(module_name), name)
        if not isinstance(value, tuple):
            continue  # a scalar .X/.XX half-width, not a two-sided band
        key = (module_name, name)
        if id(value) in checked or key in NOT_FIT_BANDS or key in INDEXED_FIT_BANDS:
            continue
        unclassified.append(f"{module_name}.{name} = {value!r}")
    assert not unclassified, (
        "band tuples that no checked consumer reads; feed them through "
        "_fit_deviations.deviations or list them in NOT_FIT_BANDS with a reason: "
        + "; ".join(unclassified)
    )


@pytest.mark.parametrize(
    ("module_name", "name"),
    sorted(INDEXED_FIT_BANDS),
    ids=[f"{m}:{n}" for m, n in sorted(INDEXED_FIT_BANDS)],
)
def test_indexed_fit_bands_are_valid(module_name: str, name: str) -> None:
    band = getattr(importlib.import_module(module_name), name)
    _check_band(f"{module_name}.{name}", band, "upper_lower")


def test_classification_lists_are_current() -> None:
    inventory = set(_inventory())
    assert ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND") in inventory, (
        "missing band inventory anchor: dt_cylinder_gear_spec:OVERALL_THICKNESS_BAND"
    )
    for module, name in (
        ("ch_rocker_arm_tl_c_stop_bar_spec", "BAR_HEIGHT_BAND"),
        ("ch_rocker_arm_tl_diamond_pin_spec", "LAND_BAND"),
        ("ch_rocker_arm_tl_inspection_box_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_profile_fixture_spec", "ROD_PIN_XY_BAND"),
        ("dt_cone_pivot_post_tl_saw_cradle_spec", "DRILLED_BAND"),
    ):
        assert (module, name) in inventory, (
            f"missing band inventory anchor: {module}:{name}"
        )
    for listing in (NOT_FIT_BANDS, INDEXED_FIT_BANDS):
        stale = set(listing) - inventory
        assert not stale, f"listed constants that are gone: {sorted(stale)}"
    assert not set(NOT_FIT_BANDS) & set(INDEXED_FIT_BANDS)


@pytest.fixture
def band_use_source_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """AST-only sources: every consumer anchor plus a rich unrelated module."""
    anchors = {
        "build_dt_crank_drive_gear": "BORE_DIA_BAND",
        "build_dt_cone_gear_shaft": "band",
        "build_ch_rocker_arm_tl_c_stop_bar": "band",
        "build_ch_rocker_arm_tl_diamond_pin": "band",
        "build_ch_rocker_arm_tl_inspection_box": "band",
        "ch_rocker_arm_tl_c_stop_bar_spec": "DRILLED_BAND",
        "ch_rocker_arm_tl_inspection_box_spec": "DRILLED_BAND",
        "ch_rocker_arm_tl_profile_fixture_spec": "DRILLED_BAND",
        "ch_rocker_arm_tl_vise_stop_spec": "DRILLED_BAND",
        "dt_cone_pivot_post_tl_saw_cradle_spec": "DRILLED_BAND",
    }
    for module, expression in anchors.items():
        (tmp_path / f"{module}.py").write_text(
            f"deviations({expression})\n", encoding="utf-8"
        )
    (tmp_path / "build_unrelated.py").write_text(
        "".join(f"deviations(UNRELATED_{i}_BAND)\n" for i in range(60)),
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    return tmp_path


def test_band_uses_anchor_rejects_no_match(
    band_use_source_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The positive control makes an actual scanner-glob mutation fail too.
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    test_band_uses_are_found()
    monkeypatch.setitem(globals(), "SCRIPTS", band_use_source_tree / "nowhere")
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    with pytest.raises(AssertionError, match="band consumer scan found only 0"):
        test_band_uses_are_found()


@pytest.mark.parametrize(
    ("module", "expression"),
    [
        ("build_dt_crank_drive_gear", "BORE_DIA_BAND"),
        ("build_dt_cone_gear_shaft", "band"),
        ("build_ch_rocker_arm_tl_c_stop_bar", "band"),
        ("build_ch_rocker_arm_tl_diamond_pin", "band"),
        ("build_ch_rocker_arm_tl_inspection_box", "band"),
        ("ch_rocker_arm_tl_c_stop_bar_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_inspection_box_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_profile_fixture_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_vise_stop_spec", "DRILLED_BAND"),
        ("dt_cone_pivot_post_tl_saw_cradle_spec", "DRILLED_BAND"),
    ],
)
def test_band_uses_anchor_rejects_one_directory_deep_source(
    band_use_source_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    expression: str,
) -> None:
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    test_band_uses_are_found()
    moved = band_use_source_tree / "moved"
    moved.mkdir()
    (band_use_source_tree / f"{module}.py").rename(moved / f"{module}.py")
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    # Sixty unrelated helpers still meet the count; only this source is lost.
    with pytest.raises(
        AssertionError, match=f"missing band consumer anchor: {module}:{expression}"
    ):
        test_band_uses_are_found()


@pytest.fixture
def band_inventory_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """AST-only assignments satisfy real lists without importing their owners."""
    names = set(NOT_FIT_BANDS) | set(INDEXED_FIT_BANDS) | {
        ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"),
        ("ch_rocker_arm_tl_c_stop_bar_spec", "BAR_HEIGHT_BAND"),
        ("ch_rocker_arm_tl_diamond_pin_spec", "LAND_BAND"),
        ("ch_rocker_arm_tl_inspection_box_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_profile_fixture_spec", "ROD_PIN_XY_BAND"),
        ("dt_cone_pivot_post_tl_saw_cradle_spec", "DRILLED_BAND"),
    }
    by_module: dict[str, list[str]] = {}
    for module, name in sorted(names):
        by_module.setdefault(module, []).append(f"{name} = (0.02, -0.02)\n")
    for module, assignments in by_module.items():
        (tmp_path / f"{module}.py").write_text(
            "".join(assignments), encoding="utf-8"
        )
    (tmp_path / "build_unrelated.py").write_text(
        "".join(f"UNRELATED_{i}_BAND = (0.02, -0.02)\n" for i in range(60)),
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    return tmp_path


def test_inventory_anchor_rejects_no_match(
    band_inventory_source_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_classification_lists_are_current()
    monkeypatch.setitem(globals(), "SCRIPTS", band_inventory_source_tree / "nowhere")
    with pytest.raises(
        AssertionError,
        match="missing band inventory anchor: dt_cylinder_gear_spec:OVERALL_THICKNESS_BAND",
    ):
        test_classification_lists_are_current()


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"),
        ("ch_rocker_arm_tl_c_stop_bar_spec", "BAR_HEIGHT_BAND"),
        ("ch_rocker_arm_tl_diamond_pin_spec", "LAND_BAND"),
        ("ch_rocker_arm_tl_inspection_box_spec", "DRILLED_BAND"),
        ("ch_rocker_arm_tl_profile_fixture_spec", "ROD_PIN_XY_BAND"),
        ("dt_cone_pivot_post_tl_saw_cradle_spec", "DRILLED_BAND"),
    ],
)
def test_inventory_anchor_rejects_one_directory_deep_source(
    band_inventory_source_tree: Path, module: str, name: str
) -> None:
    test_classification_lists_are_current()
    moved = band_inventory_source_tree / "moved"
    moved.mkdir()
    (band_inventory_source_tree / f"{module}.py").rename(moved / f"{module}.py")
    # Unrelated assignments and every other source cannot replace this anchor.
    with pytest.raises(
        AssertionError, match=f"missing band inventory anchor: {module}:{name}"
    ):
        test_classification_lists_are_current()


@pytest.mark.parametrize(
    ("band", "order"),
    [
        ((0.025, 0.025), "upper_lower"),  # the warm-c486 crank_drive_gear band
        ((0.010, 0.050), "upper_lower"),
        ((0.050, 0.010), "lower_upper"),
        ((0.020, 0.020), "lower_upper"),
    ],
)
def test_check_band_rejects_inverted_and_zero_width_bands(
    band: tuple[float, float], order: str
) -> None:
    # The guard must fail on the shapes it exists to catch, in both argument
    # orders, or every parametrized case above passes vacuously.
    with pytest.raises((AssertionError, ValueError)):
        _check_band("synthetic", band, order)


@pytest.mark.parametrize(
    ("source", "replacement"),
    [
        ("REAM_H7", (0.017, 0.002)),
        ("SHAFT_G6_3_TO_6_MM", (-0.006, -0.015)),
    ],
)
def test_measured_close_running_clearance_tracks_shared_bands(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    replacement: tuple[float, float],
) -> None:
    hole_lower, hole_upper = _fit_deviations.deviations(_fit_close_running.REAM_H7)
    shaft_lower, shaft_upper = _fit_deviations.deviations(_fit_close_running.SHAFT_G6_3_TO_6_MM)
    expected = hole_lower - shaft_upper, hole_upper - shaft_lower
    assert _fit_close_running.measured_close_running_clearance_mm() == pytest.approx(expected)
    assert 0.0 < expected[0] < expected[1]

    # Change each input independently: a copied clearance literal cannot pass.
    monkeypatch.setattr(_fit_close_running, source, replacement)
    hole_lower, hole_upper = _fit_deviations.deviations(_fit_close_running.REAM_H7)
    shaft_lower, shaft_upper = _fit_deviations.deviations(_fit_close_running.SHAFT_G6_3_TO_6_MM)
    changed = hole_lower - shaft_upper, hole_upper - shaft_lower
    assert changed != expected
    assert _fit_close_running.measured_close_running_clearance_mm() == pytest.approx(changed)


@pytest.mark.parametrize("grade", ("standard", "contact_critical"))
def test_gear_tip_grade_reads_its_shared_configuration(grade: str) -> None:
    import _config

    configured = tuple(float(value) for value in _config.fit("gear_tip", f"{grade}_band_mm"))
    assert _gear_fit_limits.gear_tip_band_mm(grade) == configured
    assert configured[0] == 0.0
    assert configured[1] < 0.0


def test_gear_tip_grade_reader_tracks_config_edits(monkeypatch: pytest.MonkeyPatch) -> None:
    import _config

    seen = []

    def fit_value(*keys: str):
        seen.append(keys)
        return [0.0, -0.03]

    monkeypatch.setattr(_config, "fit", fit_value)
    assert _gear_fit_limits.gear_tip_band_mm("standard") == (0.0, -0.03)
    assert seen == [("gear_tip", "standard_band_mm")]


def test_gear_tip_grade_reader_refuses_unknown_or_inverted_grades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import _config

    with pytest.raises(ValueError, match="unsupported gear-tip grade"):
        _gear_fit_limits.gear_tip_band_mm("routine")
    monkeypatch.setattr(_config, "fit", lambda *keys: (-0.02, 0.0))
    with pytest.raises(ValueError, match="inverted"):
        _gear_fit_limits.gear_tip_band_mm("contact_critical")


@pytest.mark.parametrize("band", [(0.025, 0.025), (0.010, 0.050)])
def test_fit_helpers_share_band_validation(band: tuple[float, float]) -> None:
    for helper in (
        _fit_deviations.validate_band,
        _fit_deviations.deviations,
        _fit_text.band_text,
        lambda value: _fit_text.fit_limits(6.0, value),
    ):
        with pytest.raises(ValueError) as error:
            helper(band)
        assert str(error.value) == f"fit band is inverted: {band!r}"


@pytest.mark.parametrize(
    ("band", "text"),
    [
        ((0.025, 0.010), "+0.03/+0.01"),
        ((0.000, -0.020), "+0.00/-0.02"),
        ((0.012, 0.000), "+0.01/-0.00"),
        ((-0.010, -0.030), "-0.01/-0.03"),
    ],
)
def test_fit_text_preserves_released_band_signs(
    band: tuple[float, float], text: str
) -> None:
    assert _fit_text.band_text(band) == text
    assert _fit_deviations.deviations(band) == (band[1], band[0])


def test_fit_limits_preserves_precision_and_diameter_prefix() -> None:
    assert _fit_text.fit_limits(6.0, (0.012, 0.0)) == "6.012 MAX / 6.000 MIN"
    assert _fit_text.fit_limits(
        6.0, (0.012, 0.0), decimals=2, diameter=True
    ) == "<MOD-DIAM>6.01 MAX / <MOD-DIAM>6.00 MIN"
