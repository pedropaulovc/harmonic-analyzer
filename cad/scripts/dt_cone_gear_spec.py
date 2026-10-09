r"""Finite cutter-native authority shared by the cone family and its drawing.

Only a complete, source-qualified T006..T120 numerical packet supplies blank
and tool settings. Missing or stale evidence refuses construction; there is no
ideal-count profile or historical deepened-mesh fallback. Native inspection
sizes come from the same supported core profiles as the actual through cuts.

The retained seat-fit and manufacturing bands are inputs to qualification,
not outputs back-fed into the solver. Numerical qualification may precede the
first farm build: ``native_certificate=False`` is not a construction refusal.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import _config
from cone_pitch import SEAT_PITCH
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from cone_shaft_land_bands import (
    FLAT_AF_BAND,
    SECTION_CONE_GEAR_TEETH,
    SECTION_DIA_BANDS,
    SECTION_FLAT_AF,
    TERMINAL_DIA_MM,
)
from gear_seat_fit import flat_bore_af_band, seat_bore_band
from stock_form_cutter import (
    CustomSixCutter,
    StockFormProfile,
    template_for_teeth,
    translation_for_pitch_tooth_thickness,
)


MM_PER_IN = 25.4

# Family alloy split (config-owned, cad/config/parts/dt-cone-gear.yaml): the
# title-block material (C36000) covers T030-T120; the four tip gears are the
# harder alloy below (dimensions.yaml ch.12 p.21).
_MFG = _config.parts("dt-cone-gear")
BODY_MATERIAL_SPEC = str(_MFG["material_specification"])
TIP_MATERIAL_SPEC = str(_MFG["material_tip_specification"])

TEETH = int(_config.machine("gear_train", "fundamental_cone_teeth"))
CONFIGURATION_TEETH = tuple(range(6, TEETH + 1, 6))
DIAMETRAL_PITCH = _config.machine("gear_train", "diametral_pitch")
PRESSURE_ANGLE_DEG = _config.machine("gear_train", "pressure_angle_deg")
MODULE_MM = MM_PER_IN / DIAMETRAL_PITCH
PITCH_DIA = TEETH * MODULE_MM
# Source-owned acceptance bands; no per-count ideal profile table is current.
TOOTH_THICKNESS_BAND = (0.075, -0.075)  # (upper, lower), actual pitch arc
BACKLASH_ACCEPTANCE_MM = (0.06, 0.41)
UNION_COVERAGE_MIN = 1.1
HANDOVER_JUMP_MAX_MM = 0.005
ROOT_AIR_MIN_MM = 0.02
DRUM_ROOT_AIR_MIN_MM = 0.10
CUSTOM_SIX_TOOL_THICKNESS_MM = 1.05

# A declared per-file native recipe input, not a measurement-family input.
# The parent publishes this authentic JSON only after complete qualification.
STOCK_FORM_PACKET_PATH = Path(__file__).resolve().parents[1] / "calibration/dt-cone-stock-form.json"
MEASUREMENT_SOURCE_PATHS = frozenset((
    "cad/scripts/stock_form_cutter.py",
    "cad/scripts/stock_form_mesh.py",
    "cad/scripts/diagnostics/stock_form_root_angles.py",
    "cad/scripts/diagnostics/stock_form_root_sweep.py",
    "cad/scripts/diagnostics/stock_form_contact_3d.py",
    "cad/scripts/diagnostics/stock_form_contact_continuation.py",
))
OBLIQUE_PHASE_EXCLUDED_TERMS = (
    "cone_flat_free_clock", "BoreFlatClock", "drum_tooth_to_cam_notch_clock",
)


def cutter_template(teeth: int) -> Any:
    """Canonical stock master or the explicitly approved finite N6 tool."""
    _require_member(teeth)
    if teeth == 6:
        return CustomSixCutter(
            DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG, 1.491, 2.35,
            CUSTOM_SIX_TOOL_THICKNESS_MM, "DT6-FORM1",
            "Main-approved N6 PA20 working involute; physical root MIN2.346 mm; finite ground form",
        )
    return template_for_teeth(teeth, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG)


def cutter_record(teeth: int) -> dict[str, Any]:
    """The actual finite tool definition, independent of installed settings."""
    cutter = cutter_template(teeth)
    return {
        "reference_teeth": cutter.reference_teeth,
        "cutter_number": cutter.cutter_number,
        "teeth_range": list(cutter.teeth_range),
        "diametral_pitch": cutter.diametral_pitch,
        "pressure_angle_deg": cutter.pressure_angle_deg,
        "root_radius_mm": cutter.root_radius_mm,
        "base_radius_mm": cutter.base_radius_mm,
        "tip_radius_mm": cutter.tip_radius_mm,
        "pitch_tooth_thickness_mm": cutter.pitch_tooth_thickness_mm,
        "name": cutter.name,
        "source": cutter.source,
    }


def _cutter_geometry(record: dict) -> dict:
    # Preserve tool wording in the packet; do not make it a geometric input.
    return {key: value for key, value in record.items() if key not in {"name", "source"}}


def geometry_inputs() -> dict[str, Any]:
    """Retained factory inputs; never require selected data or native evidence.

    Placement/support inputs are additionally bound by the producer's actual
    config reads and compiled pure-source receipt. This record owns only the
    cutter/inspection contract; it does not invent a second pose authority.
    """
    return {
        "configuration_teeth": list(CONFIGURATION_TEETH),
        "diametral_pitch": DIAMETRAL_PITCH,
        "pressure_angle_deg": PRESSURE_ANGLE_DEG,
        "blank_dia_band_mm": list(BLANK_DIA_BAND),
        "pitch_thickness_band_mm": list(TOOTH_THICKNESS_BAND),
        "face_width_mm": FACE_WIDTH,
        "face_width_band_mm": list(FACE_WIDTH_BAND),
        "bore_dia_band_mm": list(BORE_DIA_BAND),
        "bore_af_band_mm": list(BORE_AF_BAND),
        "flat_clock_tolerance_deg": FLAT_CLOCK_TOLERANCE_DEG,
        "backlash_acceptance_mm": list(BACKLASH_ACCEPTANCE_MM),
        "union_coverage_min": UNION_COVERAGE_MIN,
        "handover_jump_max_mm": HANDOVER_JUMP_MAX_MM,
        "root_air_min_mm": ROOT_AIR_MIN_MM,
        "drum_root_air_min_mm": DRUM_ROOT_AIR_MIN_MM,
        "members": [{
            "teeth": teeth,
            "bore_dia_mm": bore_dia_mm(teeth),
            "bore_af_mm": bore_flat_af_mm(teeth),
            "web_min_mm": WEB_EXCEPTIONS_MM.get(teeth, MACHINED_WEB_TARGET_MM),
            "cutter": _cutter_geometry(cutter_record(teeth)),
        } for teeth in CONFIGURATION_TEETH],
    }


def geometry_sha256(record: Any) -> str:
    """Canonical semantic identity; raw source identities stay separate."""
    return hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest().upper()


def selected_geometry_record(rows: list[dict]) -> list[dict]:
    """Bind selected OUTPUT geometry without making it a solver input."""
    return [{
        "teeth": row["teeth"],
        "cutter": _cutter_geometry(row["cutter"]),
        "selected": {name: row["selected"][name] for name in (
            "outside_dia_mm", "pitch_thickness_mm", "tool_translation_mm",
            "translation_limits_mm", "nominal_plunge_mm", "root_envelope_mm",
            "actual_pitch_tooth_thickness_mm",
        )},
        "printed_profile_root_envelope_mm": row["printed_profile_root_envelope_mm"],
    } for row in sorted(rows, key=lambda row: row["teeth"])]


def _finite(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label}: expected a finite number")
    if nonnegative and value < 0:
        raise ValueError(f"{label}: expected a nonnegative bound")
    return float(value)


def _interval(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(f"{label}: expected a two-ended interval")
    low, high = (_finite(item, label) for item in value)
    if low > high:
        raise ValueError(f"{label}: reversed interval")
    return low, high


def _same_record(actual: Any, expected: Any, label: str) -> None:
    if geometry_sha256(actual) != geometry_sha256(expected):
        raise ValueError(f"{label}: geometry identity differs from the actual source")


def _close(actual: Any, expected: float, label: str) -> None:
    if abs(_finite(actual, label) - expected) > 1e-9:
        raise ValueError(f"{label}: inconsistent with the supported core profile")


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in value
    ):
        raise ValueError(f"{label}: missing or invalid SHA256")
    return value.upper()


def _relative_sources(raw: Any, label: str) -> dict[str, str]:
    """Relocate authentic raw paths without rebinding or ambiguous suffixes."""
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{label}: missing actual source manifest")
    result = {}
    for path, sha in raw.items():
        if not isinstance(path, str):
            raise ValueError(f"{label}: non-string source path")
        normalized = path.replace("\\", "/")
        if normalized.startswith("cad/"):
            relative = normalized
        elif normalized.count("/cad/") == 1:
            relative = "cad/" + normalized.split("/cad/", 1)[1]
        else:
            raise ValueError(f"{label}: source outside the recorded CAD tree")
        if ".." in relative.split("/") or relative in result:
            raise ValueError(f"{label}: ambiguous source path {path}")
        result[relative] = _digest(sha, label)
    return result


def _current_geometry_source_sha256(paths: Any) -> dict[str, str]:
    """Pure geometry source bytes only; never read/import diagnostic engines."""
    root = Path(__file__).resolve().parents[2]
    return {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest().upper()
        for path in paths
        if path.startswith("cad/scripts/") and not path.startswith("cad/scripts/diagnostics/")
    }


def _current_config_reads(records: Any) -> dict[str, Any]:
    """Re-read the producer's finite public getter ledger, not raw metadata."""
    if not isinstance(records, dict) or not records:
        raise ValueError("factory source has no actual geometric config reads")
    allowed = {
        "machine", "fit", "channels", "cone_teeth", "amplitudes", "poses",
        "active_count", "active_channels", "title_block", "materials", "palette",
    }
    values = {}
    for identity in records:
        accessor, separator, path = identity.partition(":")
        if not separator:
            raise ValueError("factory config read lacks its public getter identity")
        keys = path.split("/") if path else []
        if accessor == "parts":
            if len(keys) != 2:
                raise ValueError("factory registry read lacks its exact field")
            values[identity] = _config.parts(keys[0])[keys[1]]
        elif accessor == "cone_teeth":
            if len(keys) != 1:
                raise ValueError("cone-teeth read lacks its exact channel index")
            values[identity] = _config.cone_teeth(int(keys[0]))
        elif accessor in allowed:
            values[identity] = getattr(_config, accessor)(*keys)
        else:
            raise ValueError(f"unqualified geometric config getter {accessor}")
    return values


def _require_packet_identity(payload: dict) -> None:
    if payload.get("family") != "dt_cone_stock_form" or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("cone stock-form packet has the wrong family/schema")
    if payload.get("qualified") is not True:
        raise ValueError("cone stock-form family is refused or numerically unqualified")
    if type(payload.get("native_certificate")) is not bool:
        raise ValueError("cone packet must distinguish numerical and native qualification")
    if payload.get("source_inputs_only") is not False or payload.get("nominal_engineering_only") is not False:
        raise ValueError("DESIGN/source-only cone data cannot construct a native family")
    expected = geometry_inputs()
    _same_record(payload["geometry_inputs"], expected, "retained factory inputs")
    if _digest(payload["geometry_inputs_sha256"], "input SHA") != geometry_sha256(expected):
        raise ValueError("cone geometry input identity is stale")
    source = payload["source_identity"]
    if source["source_bytes_stable"] is not True:
        raise ValueError("cone source changed during numerical qualification")
    before = _relative_sources(source["before_design_sha256"], "BEFORE")
    after = _relative_sources(source["after_design_sha256"], "AFTER")
    compiled = _relative_sources(source["actual_preimport_project_sha256"], "COMPILED")
    loaded = _relative_sources(source["loaded_algorithm_sha256"], "LOADED")
    if before != after:
        raise ValueError("cone source BEFORE/AFTER differ; no historical rebind")
    if not MEASUREMENT_SOURCE_PATHS <= loaded.keys() or not MEASUREMENT_SOURCE_PATHS <= compiled.keys():
        raise ValueError("cone qualification lacks all SIX actually consumed sources")
    manifest = payload["measurement_engine_sources_sha256"]
    expected_manifest = {path.rsplit("/", 1)[1]: compiled[path] for path in MEASUREMENT_SOURCE_PATHS}
    if not isinstance(manifest, dict) or manifest.keys() != expected_manifest.keys():
        raise ValueError("cone measurement manifest must name exactly SIX real algorithms")
    if {name: _digest(sha, "measurement source") for name, sha in manifest.items()} != expected_manifest:
        raise ValueError("cone measurement manifest is not the actually compiled engine")
    if _digest(payload["measurement_engine_sha256"], "measurement engine SHA") != geometry_sha256(manifest):
        raise ValueError("cone measurement engine digest is inconsistent")
    for path, sha in compiled.items():
        if before.get(path) != sha or after.get(path) != sha:
            raise ValueError(f"cone compiled source identity is inconsistent: {path}")
    for path, sha in loaded.items():
        if compiled.get(path) != sha or before.get(path) != sha:
            raise ValueError(f"cone loaded measurement source identity is inconsistent: {path}")
    pure_required = {
        "cad/scripts/dt_cone_gear_spec.py", "cad/scripts/stock_form_cutter.py",
        "cad/scripts/dt_cylinder_gear_spec.py", "cad/scripts/cone_shaft_land_bands.py",
        "cad/scripts/gear_seat_fit.py", "cad/scripts/dt_cone_support_pose.py",
        "cad/scripts/dt_cone_mesh_domain.py",
        "cad/scripts/stock_form_contact_certificate.py",
    }
    if not pure_required <= compiled.keys():
        raise ValueError("cone qualification lacks its consumed physical-source authority")
    pure = {path: sha for path, sha in compiled.items()
            if not path.startswith("cad/scripts/diagnostics/")}
    if pure != _current_geometry_source_sha256(pure):
        raise ValueError("cone pure geometry source identity is stale")
    reads = source["actual_config_value_reads"]
    _same_record(reads, _current_config_reads(reads), "actual geometric config reads")
    if _digest(source["geometric_config_value_sha256"], "config SHA") != geometry_sha256(reads):
        raise ValueError("cone config semantic identity is inconsistent")
    if _digest(source["domain_pack_sha256"], "domain BEFORE") != _digest(source["domain_pack_after_sha256"], "domain AFTER"):
        raise ValueError("cone candidate input pack changed during qualification")
    if _digest(source["core_loaded_sha256"], "core SHA") != compiled["cad/scripts/stock_form_cutter.py"]:
        raise ValueError("cone core source identity is inconsistent")
    arguments = source["calculation_arguments"]
    if arguments["source_inputs_only"] is not False or arguments["nominal_engineering_only"] is not False:
        raise ValueError("stationary DESIGN arguments cannot qualify production")
    _close(arguments["six_pitch_thickness_mm"], CUSTOM_SIX_TOOL_THICKNESS_MM, "DT6 tool thickness")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate cone packet key {key}")
        result[key] = value
    return result


def _read_stock_form_packet() -> dict:
    try:
        return json.loads(
            STOCK_FORM_PACKET_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            "cone stock-form qualification is missing: publish the authentic "
            f"ALL20/SIX-source packet at {STOCK_FORM_PACKET_PATH}"
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable cone stock-form qualification: {exc}") from exc



@dataclass(frozen=True)
class _QualifiedMember:
    profile: StockFormProfile
    corners: tuple[StockFormProfile, ...]
    floor_limits_mm: tuple[float, float]
    mesh_items: tuple[tuple[str, Any], ...]


def _profile_record(profile: StockFormProfile) -> dict:
    # Same physical record as the actual producer; no engine import.
    return {
        "teeth": profile.teeth,
        "reference_teeth": profile.template.reference_teeth,
        "dp": profile.template.diametral_pitch,
        "pa_deg": profile.template.pressure_angle_deg,
        "blank_radius_mm": profile.blank_radius_mm,
        "radial_translation_mm": profile.radial_translation_mm,
        "helix_angle_deg": profile.helix_angle_deg,
    }


def _profiles_from_row(row: dict) -> tuple[StockFormProfile, tuple[StockFormProfile, ...], tuple[float, float]]:
    teeth = row["teeth"]
    _require_member(teeth)
    if row["qualification"] != "qualified" or row["actual3d_mesh_evaluated"] is not True:
        raise ValueError(f"T{teeth:03d}: actual numerical row is refused")
    _same_record(_cutter_geometry(row["cutter"]), _cutter_geometry(cutter_record(teeth)), f"T{teeth:03d} cutter")
    for key in ("name", "source"):
        if not isinstance(row["cutter"][key], str) or not row["cutter"][key].strip():
            raise ValueError(f"T{teeth:03d}: cutter metadata identity is absent")
    if teeth == 6 and row["cutter"]["name"] != "DT6-FORM1":
        raise ValueError("T006: only the approved DT6-FORM1 custom tool is supported")
    setting = row["selected"]
    if not isinstance(setting, dict) or setting["reconstructed_from_actual_loaded_core"] is not True:
        raise ValueError(f"T{teeth:03d}: no fresh actual-core selected setting")
    od = _finite(setting["outside_dia_mm"], "selected OD")
    thickness = _finite(setting["pitch_thickness_mm"], "selected thickness")
    if od <= 0 or thickness <= 0 or abs(od - round(od, 2)) > 1e-10 or abs(thickness - round(thickness, 3)) > 1e-10:
        raise ValueError(f"T{teeth:03d}: selected print settings are invalid or unquantized")
    cutter = cutter_template(teeth)
    translation = translation_for_pitch_tooth_thickness(teeth, cutter, thickness)
    _close(setting["tool_translation_mm"], translation, "selected tool translation")
    profile = StockFormProfile(teeth, cutter, od / 2.0, setting["tool_translation_mm"])
    _close(setting["nominal_plunge_mm"], profile.plunge_mm, "nominal plunge")
    _close(setting["actual_pitch_tooth_thickness_mm"], profile.pitch_tooth_thickness_mm, "actual pitch thickness")
    _close(profile.pitch_tooth_thickness_mm, thickness, "selected pitch thickness")
    envelope = _interval(setting["root_envelope_mm"], "nominal root envelope")
    _close(envelope[0], profile.root_radius_min_mm, "nominal root MIN")
    _close(envelope[1], profile.root_radius_max_mm, "nominal root MAX")
    translations = tuple(translation_for_pitch_tooth_thickness(teeth, cutter, thickness + side)
                         for side in (TOOTH_THICKNESS_BAND[1], TOOTH_THICKNESS_BAND[0]))
    supplied = _interval(setting["translation_limits_mm"], "manufactured translation limits")
    for actual, expected in zip(supplied, translations, strict=True):
        _close(actual, expected, "manufactured translation")
    # Ordering matches the producer's actual Cartesian OD/process corner law.
    corners = tuple(StockFormProfile(teeth, cutter, (od + side) / 2.0, shift)
                    for side, shift in itertools.product(BLANK_DIA_BAND, translations))
    required_land = max(0.10, 0.25 * MODULE_MM)
    for corner in (profile, *corners):
        corner.require_tip_land(required_land)
    root_min = min(corner.root_radius_min_mm for corner in corners)
    root_max = max(corner.root_radius_max_mm for corner in corners)
    actual_envelope = _interval(row["printed_profile_root_envelope_mm"], "printed-profile root envelope")
    _close(actual_envelope[0], root_min, "printed-profile root MIN")
    _close(actual_envelope[1], root_max, "printed-profile root MAX")
    # The native LIMIT witness is an actual radial envelope, never a filled
    # RootMAX collision disk. Collision authority is the same-q RootSweep.
    scale = 10**DRAWING_PRECISION["GapFloorReference"]["FloorDia"]
    error = max(corner.geometry_error_bound_mm for corner in corners)
    minimum = math.floor(2.0 * (root_min - error) * scale) / scale
    maximum = math.ceil(2.0 * (root_max + error) * scale) / scale
    maximum_bore = math.ceil((bore_dia_mm(teeth) + BORE_DIA_BAND[0]) * 10**BORE_BAND_PLACES - 1e-9) / 10**BORE_BAND_PLACES
    web_required = WEB_EXCEPTIONS_MM.get(teeth, MACHINED_WEB_TARGET_MM)
    if (minimum - maximum_bore) / 2.0 < web_required - 1e-9:
        raise ValueError(f"T{teeth:03d}: printed actual root misses the retained web")
    if teeth == 6 and minimum < 2.346 - 1e-9:
        raise ValueError("T006: actual root misses the approved physical D2.346 MIN")
    return profile, corners, (minimum, maximum)


def _require_stock_phase_evidence(
    arrays: dict, cases: list, source_domain: dict, source_placement: dict,
) -> None:
    """Replay the real aggregate against independently bound ALL17 receipts."""
    from dt_cone_mesh_domain import nominal_source_subdomain, budget_clock_subdomain
    from stock_form_contact_certificate import (
        require_actual_read_phase, require_continuous_certificate,
        require_whole_period_envelope,
    )

    domains = {
        "nominal_actual3d": nominal_source_subdomain(source_placement, source_domain),
        "budget_actual3d": budget_clock_subdomain(source_domain),
    }
    expected_scopes = {
        "nominal_actual3d": "DESIGN_NOMINAL_SUBDOMAIN",
        "budget_actual3d": "BUDGET_CLOCK_NOMINAL_SUBDOMAIN",
    }
    for name, domain in domains.items():
        if domain["scope"] != expected_scopes[name] or domain["production_source_domain"] is not False:
            raise ValueError("q0/CLOCK proof lacks its deliberate independently supplied mathematical role")
    reports = {name: [] for name in domains}
    nominal_reference = None
    for case_id, calculation, driver, driven in cases:
        for name, domain in domains.items():
            report = calculation[name]
            if report["source_domain_proved"] is not True:
                raise ValueError("stock phase requires admitted actual q0/CLOCK geometry, not an aggregate status")
            _same_record(report["driver_profile"], _profile_record(driver), "stock-phase actual cone")
            _same_record(report["driven_profile"], _profile_record(driven), "stock-phase actual drum")
            _same_record(report["placement"], source_placement, "stock-phase actual physical setup")
            _same_record(report["continuous_source_domain"], domain, "independent stock-phase source subdomain")
            certificate = report["continuous_contact_certificate"]
            require_continuous_certificate(
                report, domain, driver, driven, certificate,
                coverage_floor=UNION_COVERAGE_MIN, row_floor=0.0,
                handover_max_mm=HANDOVER_JUMP_MAX_MM,
            )
            require_whole_period_envelope(report, domain, driver, driven)
            cells = report["full_period_cells"]
            if not cells:
                raise ValueError("stock-phase residual advance has no genuine whole-period TE enclosure")
            previous = 0.0
            for cell in cells:
                phase = _interval(cell["actual_driver_interval_rad"], "stock-phase actual whole-period cell")
                if phase[1] <= phase[0] or abs(phase[0] - previous) > 1e-12:
                    raise ValueError("stock-phase actual whole-period TE proof omits/reorders phase")
                previous = phase[1]
                _interval(cell["signed_running_te_interval_rad"], "stock-phase whole-cell physical signed TE")
                _require_root_air(
                    cell["root_air"], phase, certificate["sides"]["lower"]["phase_cells"], domain,
                )
            _close(previous, driver.angular_pitch_rad, "stock-phase complete driver period")
            reads = report["actual_read_phases"]
            if not isinstance(reads, list) or len(reads) != 21:
                raise ValueError("stock-phase source case omits genuine direct physical read phases")
            for index, read in enumerate(reads):
                _close(read["actual_driver_phase_rad"], arrays["driver_read_phases_rad"][index], "stock-phase requested actual read order")
                if read["direct_actual_phase_query"] is not True or read["periodic_point_substitution"] is not False:
                    raise ValueError("stock-phase physical read substituted a periodic endpoint query")
                _interval(read["signed_running_te_interval_rad"], "stock-phase actual read TE")
                require_actual_read_phase(
                    report, domain, driver, driven, read,
                    expected_phase_rad=arrays["driver_read_phases_rad"][index],
                )
            reports[name].append(report)
            if case_id == "nominal" and name == "nominal_actual3d":
                nominal_reference = report
    if nominal_reference is None or any(len(values) != 17 for values in reports.values()):
        raise ValueError("stock-phase selected nominal/all16 real source case set is incomplete")
    for index, read in enumerate(nominal_reference["actual_read_phases"]):
        value = _finite(read["reference_signed_running_te_rad"], "true q0 point-root TE reference")
        bound = _finite(read["reference_error_bound_rad"], "true q0 point numerical error", nonnegative=True)
        low, high = _interval(read["signed_running_te_interval_rad"], "genuine selected q0 point TE proof")
        if value - bound > low or value + bound < high:
            raise ValueError("q0 point numerical reference does not enclose its genuine root proof")
        _close(arrays["nominal_signed_running_te_rad"][index], value, "true 3D nominal point reference")
        _close(arrays["nominal_reference_numerical_bound_rad"][index], bound, "paid 3D point numerical error")
        for name, width_name in (
            ("budget_actual3d", "robust_half_width_rad"),
            ("nominal_actual3d", "nominal_pose_half_width_rad"),
        ):
            intervals = [_interval(report["actual_read_phases"][index]["signed_running_te_interval_rad"], "same-stall actual profile TE") for report in reports[name]]
            expected = math.nextafter(max(bound, *(max(abs(low - value), abs(high - value)) for low, high in intervals)), math.inf)
            _close(arrays[width_name][index], expected, "ALL17 same-stall source/reference half-width")
    for name, interval_name in (
        ("budget_actual3d", "robust_signed_te_interval_rad"),
        ("nominal_actual3d", "nominal_pose_signed_te_interval_rad"),
    ):
        intervals = [_interval(report["whole_period_signed_running_te_interval_rad"], "actual whole-phase profile TE")
                     for report in reports[name]]
        _same_record(arrays[interval_name], (min(row[0] for row in intervals), max(row[1] for row in intervals)), "ALL17 actual whole-phase residual TE envelope")


def _operating_stock_phase_arrays(record: dict, teeth: int, driven_teeth: int, source_datum: dict) -> dict:
    """Read measured 3D stock phase; no planar recompute, midpoint or tare."""
    if (record["schema"] != "dt-cone-operating-stock-phase/1"
            or record["operating_source_state"] != "OPERATING_NOTCH_UP"
            or type(record["operating_driver_sense"]) is not int or record["operating_driver_sense"] != -1
            or record["shaft_advance_included"] is not False or record["datum_tare_rad"] is not None
            or record["excluded_terms"] != list(OBLIQUE_PHASE_EXCLUDED_TERMS)
            or record["half_width_scope"] != "nominal/all16 SAME requested stall; numerical reference bound included once"
            or record["phase_change_scope"] != "genuine whole-period intervals bound residual TE(psi+s)-TE(psi); pay the relevant width once when adding crank shaft advance"):
        raise ValueError("operating 3D stock phase lacks its physical datum/source/payment contract")
    _same_record(record["manufactured_datum_mapping"], source_datum, "physical OPERATING_NOTCH_UP SOURCE datum")
    arrays = {}
    for name in (
        "driver_read_phases_rad", "nominal_driven_advance_rad",
        "nominal_signed_running_te_rad", "nominal_reference_numerical_bound_rad",
        "robust_half_width_rad", "nominal_pose_half_width_rad",
    ):
        values = record[name]
        if not isinstance(values, list) or len(values) != 21:
            raise ValueError(f"actual operating stock phase requires all 21 {name}")
        arrays[name] = tuple(_finite(value, name) for value in values)
    for index, phase in enumerate(arrays["driver_read_phases_rad"]):
        _close(phase, -index * math.pi, "actual 3D physical read order")
        reference = arrays["nominal_signed_running_te_rad"][index]
        advance = arrays["nominal_driven_advance_rad"][index]
        _close(advance + phase * teeth / driven_teeth, reference, "untared running-direction 3D reference")
        numerical = arrays["nominal_reference_numerical_bound_rad"][index]
        nominal = arrays["nominal_pose_half_width_rad"][index]
        robust = arrays["robust_half_width_rad"][index]
        if not (0.0 <= numerical <= nominal and numerical <= robust):
            raise ValueError("3D stock-phase half-widths omit the paid numerical reference")
    for name in ("robust_signed_te_interval_rad", "nominal_pose_signed_te_interval_rad"):
        arrays[name] = _interval(record[name], name)
    return arrays


def _require_root_air(
    proof: dict, phase: tuple[float, float], certified_cells: list, source_domain: dict,
) -> None:
    """Bind summary air to the already-validated COMPLETE material receipts.

    The shared receiver, not a RootMAX disk or a summary flag, must establish
    driver RootSweep and directed driven-root/full-driver-material exclusion.
    """
    if proof["qualified"] is not True or proof["root_is_carrying"] is not False:
        raise ValueError("actual finite root material air is unresolved or mislabeled carrying")
    _same_record(proof["root_air_requirements_mm"], source_domain["root_air_requirements_mm"], "directed SOURCE root floors")
    containing = [
        cell for cell in certified_cells
        if cell["phase_cell_rad"][0] <= phase[0] + 1e-12
        and phase[1] <= cell["phase_cell_rad"][1] + 1e-12
    ]
    if len(containing) != 1:
        raise ValueError("root air is not bound to one actual continuous source/phase cell")
    cell = containing[0]
    _same_record(proof["driver_root_proof"], cell["root_proof"], "actual driver material RootSweep")
    _same_record(proof["driven_root_material_proof"], cell["driven_root_material_proof"], "actual driven-root/full-driver-material sweep")
    driver_air = _finite(proof["driver_root_air_lower_mm"], "driver root material air")
    driven_air = _finite(proof["driven_root_air_lower_mm"], "driven root material air")
    _close(driver_air, cell["root_proof"]["physical_root_air_lower_bound_mm"], "actual driver root air")
    _close(driven_air, cell["driven_root_material_proof"]["root_air_lower_mm"], "actual driven root air")
    if driver_air < ROOT_AIR_MIN_MM or driven_air < DRUM_ROOT_AIR_MIN_MM:
        raise ValueError("complete actual directed root material air misses .02/.10")



def _require_contact_report(
    report: dict, driver: StockFormProfile, driven: StockFormProfile,
    source_domain: dict, source_placement: dict,
) -> dict:
    from stock_form_contact_certificate import (
        require_actual_read_phase, require_continuous_certificate,
        require_whole_period_envelope,
    )

    teeth = driver.teeth
    if report["qualification"] != "qualified" or report.get("production_qualified") is False:
        raise ValueError("selected actual-profile contact report is refused or DESIGN only")
    margins = report["margins"]
    required = {
        "supported_union_coverage", "handover_jump_mm", "phase_reserve_rad",
        "continuous_carrying", "tight_backlash_mm", "loose_backlash_mm",
        "cone_root_air_mm", "drum_root_air_mm",
    }
    if not required <= margins.keys() or any(_finite(value, "contact margin") < 0 for value in margins.values()):
        raise ValueError("actual contact margins are missing or refused")
    _finite(report["oblique_phase_bound_rad"], "oblique budget bound", nonnegative=True)
    _finite(report["nominal_oblique_phase_bound_rad"], "nominal oblique bound", nonnegative=True)
    robust = report["all_corner_actual3d"]
    if robust["production_source_qualified"] is not True or robust["metric"] != "STOCK-FORM COVERAGE" or robust["is_conjugate"] is not False:
        raise ValueError("actual supported UNION is unqualified or mislabeled")
    if robust["operating_driver_sense"] != -1 or robust["continuous_carrying_contact"] is not True:
        raise ValueError("actual running direction or continuous carrying proof is absent")
    coverage = _finite(robust["stock_form_coverage_lower"], "actual UNION coverage", nonnegative=True)
    if coverage < UNION_COVERAGE_MIN or _finite(robust["uncovered_phase_rad"], "uncovered phase") != 0.0:
        raise ValueError("actual whole-pitch supported UNION has a gap or insufficient coverage")
    reserve = _finite(robust["phase_reserve_rad"], "phase reserve", nonnegative=True)
    gap = _finite(robust["noncarrying_pair_normal_gap_upper_mm"], "noncarrying gap", nonnegative=True)
    errors = robust["numerical_error_bounds"]
    if not {"surface_mm", "phase_motion_mm", "te_rad"} <= errors.keys():
        raise ValueError("actual UNION lacks paid numerical enclosures")
    for value in errors.values():
        _finite(value, "actual numerical error", nonnegative=True)
    for handover in robust["handovers"]:
        if handover["continuous"] is not True or _finite(
            handover["pitch_displacement_jump_upper_mm"], "paid physical handover", nonnegative=True,
        ) > HANDOVER_JUMP_MAX_MM:
            raise ValueError("actual physical handover is unresolved or above .005")
    continuous = robust["continuous_contact_certificate"]
    _same_record(robust["placement"], source_placement, "actual SOURCE placement")
    _same_record(robust["continuous_source_domain"], source_domain, "continuous SOURCE domain")
    require_continuous_certificate(
        robust, source_domain, driver, driven, continuous,
        coverage_floor=UNION_COVERAGE_MIN, row_floor=0.0,
        handover_max_mm=HANDOVER_JUMP_MAX_MM,
    )
    require_whole_period_envelope(robust, source_domain, driver, driven)
    backlash = report["actual_driven_backlash"]
    tight = _finite(backlash["tight_lower_mm"], "rooted driven tight backlash")
    loose = _finite(backlash["loose_upper_mm"], "rooted driven loose backlash")
    if not BACKLASH_ACCEPTANCE_MM[0] <= tight <= loose <= BACKLASH_ACCEPTANCE_MM[1]:
        raise ValueError("actual independently rooted driven backlash misses its retained band")
    inspection_radius = (
        (teeth + driven.teeth) * MODULE_MM / 2.0
        + _config.fit("cone_drum_oblique_mesh", "edge_slack_mm")
    ) * driven.teeth / (teeth + driven.teeth)
    _close(backlash["source_inspection_radius_mm"], inspection_radius, "SOURCE inspection Rop")
    _close(backlash["physical_driven_pitch_radius_mm"], driven.pitch_radius_mm, "physical driven Rp")
    reads = report["signed_read_matrix"]
    if reads["all_reads_bounded"] is not True or reads["units"] != "signed cylinder radians" or reads["datum"] != "physical CAM-NOTCH/cone-lock zero; no alignment-index feature or mean/home subtraction":
        raise ValueError("actual untared mechanical-datum read evidence is missing")
    if len(reads["rows"]) != 21:
        raise ValueError("all twenty-one physical read stalls are required")
    actual_reads = robust["actual_read_phases"]
    if not isinstance(actual_reads, list) or len(actual_reads) != 21:
        raise ValueError("all twenty-one direct physical phase queries are required")
    _same_record(report["actual_signed_read_phases"], actual_reads, "canonical actual physical read queries")
    te_bound = 0.0
    for index, read in enumerate(reads["rows"]):
        actual = actual_reads[index]
        require_actual_read_phase(
            robust, source_domain, driver, driven, actual,
            expected_phase_rad=-index * math.pi,
        )
        _close(read["driver_phase_rad"], -index * math.pi, "physical read phase")
        if read["qualification"] not in {"pointwise bounded", "interval bounded"}:
            raise ValueError("physical signed read is unresolved")
        _same_record(read["read_phase_interval_rad"], [-index * math.pi, -index * math.pi], "direct physical read phase")
        te = _interval(read["signed_running_te_interval_rad"], "untared signed TE")
        _same_record(te, actual["signed_running_te_interval_rad"], "human projection of canonical signed TE")
        te_bound = max(te_bound, abs(te[0]), abs(te[1]))
    cells = report["full_period_cells"]
    if not cells:
        raise ValueError("actual whole-period driven-root cells are missing")
    _same_record(cells, robust["full_period_cells"], "canonical whole-period actual engine cells")
    inspection_cells = report["source_inspection_backlash_cells"]
    if not isinstance(inspection_cells, list) or len(inspection_cells) != len(cells):
        raise ValueError("SOURCE inspection backlash projection omits whole-period actual cells")
    previous = 0.0
    observed_backlash = []
    for cell, inspection in zip(cells, inspection_cells, strict=True):
        low, high = _interval(cell["actual_driver_interval_rad"], "actual driven-root phase cell")
        if high <= low or abs(low - previous) > 1e-12:
            raise ValueError("actual whole-period driven-root cells have a gap/overlap")
        previous = high
        angular = _interval(cell["correlated_backlash"]["backlash_interval_rad"], "same-q actual driven backlash")
        if angular[0] <= 0:
            raise ValueError("actual same-q driven backlash is not positive")
        _same_record(inspection["actual_driver_interval_rad"], [low, high], "SOURCE backlash actual phase cell")
        _same_record(inspection["correlated_backlash_interval_rad"], angular, "SOURCE correlated angular backlash")
        expected_backlash = (
            math.nextafter(angular[0] * inspection_radius, -math.inf),
            math.nextafter(angular[1] * inspection_radius, math.inf),
        )
        _same_record(
            inspection["source_calibrated_backlash_interval_mm"],
            expected_backlash, "SOURCE Rop same-q driven backlash",
        )
        _same_record(
            inspection["physical_pitch_arc_backlash_interval_mm"],
            cell["correlated_backlash_interval_mm"], "distinct physical Rp same-q pitch arc",
        )
        observed_backlash.append(expected_backlash)
        air = cell["root_air"]
        _require_root_air(air, (low, high), continuous["sides"]["lower"]["phase_cells"], source_domain)
        _interval(cell["signed_running_te_interval_rad"], "whole-cell signed TE")
    _close(previous, 2.0 * math.pi / teeth, "whole-period endpoint")
    _close(tight, min(value[0] for value in observed_backlash), "whole-period tight backlash")
    _close(loose, max(value[1] for value in observed_backlash), "whole-period loose backlash")
    return {
        "coverage_min": coverage, "phase_reserve_rad": reserve,
        "noncarrying_gap_mm": gap, "te_bound_rad": te_bound,
    }


@lru_cache(maxsize=1)
def _qualified_members(encoded: str) -> tuple[_QualifiedMember, ...]:
    """Reuse real immutable profiles after the fresh provenance gate above."""
    payload = json.loads(encoded)
    rows = payload["rows"]
    if not isinstance(rows, list) or len(rows) != len(CONFIGURATION_TEETH):
        raise ValueError("native cone qualification requires exactly ALL20 rows")
    counts = [row["teeth"] for row in rows]
    if any(type(teeth) is not int for teeth in counts) or sorted(counts) != list(CONFIGURATION_TEETH):
        raise ValueError("native cone qualification requires each physical count once")
    if _digest(payload["selected_geometry_sha256"], "selected geometry SHA") != geometry_sha256(selected_geometry_record(rows)):
        raise ValueError("selected cone OUTPUT geometry identity is inconsistent")
    stack = payload["centre_stack_source_mm"]
    components = stack["opening_components"]
    if stack["measured_in_this_scope"] is not True:
        raise ValueError("whole booked cone centre stack was not numerically qualified")
    booked = _finite(components["booked_total"], "booked centre opening", nonnegative=True)
    derived = _finite(components["derived_total"], "derived centre opening", nonnegative=True)
    _close(booked, _config.fit("cone_drum_oblique_mesh", "centre_opening_mm"), "booked opening")
    _close(stack["opening_total"], max(booked, derived), "whole source opening")
    _close(components["selected_total"], max(booked, derived), "selected opening")
    for value in components.values():
        _finite(value, "centre opening component", nonnegative=True)
    poses = payload["source_identity"]["all_source_pose_inputs"]
    if set(poses) != {str(teeth) for teeth in CONFIGURATION_TEETH}:
        raise ValueError("source pose receipt lacks the exact ALL20 family")
    import dt_cylinder_gear_spec as drum
    from dt_cone_mesh_domain import continuous_source_domain, nominal_placement_record

    drum_corners = drum.manufacturing_corner_profiles()
    members = []
    for row in sorted(rows, key=lambda value: value["teeth"]):
        teeth = row["teeth"]
        profile, corners, floors = _profiles_from_row(row)
        source_domain = continuous_source_domain(teeth)
        if (source_domain["scope"] != "FULL_PRODUCTION_SOURCE_DOMAIN"
                or source_domain["production_source_domain"] is not True):
            raise ValueError("native cone requires the complete unconditional production SOURCE domain")
        source_placement = nominal_placement_record(teeth)
        source_pose = poses[str(teeth)]
        _same_record(row["geometry"], source_pose["geometry"], "actual cone placement")
        _same_record(row["continuous_source_domain"], source_pose["domain"], "actual BEFORE physical source domain")
        _same_record(row["continuous_source_domain"], source_domain, "independent whole physical SOURCE domain")
        if row["oblique_phase_bound_excluded_terms"] != list(OBLIQUE_PHASE_EXCLUDED_TERMS):
            raise ValueError("cone budget bound double-books or drops the physical clock scope")
        selected_reports = [candidate for candidate in row["candidates"]
                            if candidate.get("qualification") == "qualified"
                            and candidate.get("setting") == row["selected"]]
        if len(selected_reports) != 1:
            raise ValueError(f"T{teeth:03d}: selected setting has no unique actual report")
        selected = selected_reports[0]
        if selected["actual3d_mesh_evaluated"] is not True:
            raise ValueError("selected cone geometry has no actual3D calculation")
        cam = selected["integral_cam_body_exclusion"]
        if cam["qualified"] is not True:
            raise ValueError("source integral cam-body exclusion is unresolved")
        _same_record(selected["driver_profile"], _profile_record(profile), "selected cone profile")
        _same_record(selected["driven_profile"], _profile_record(drum.STOCK_FORM), "selected drum profile")
        _same_record(selected["manufactured_cone_corners"], [_profile_record(p) for p in corners], "actual cone corners")
        _same_record(selected["manufactured_drum_corners"], [_profile_record(p) for p in drum_corners], "actual drum corners")
        cases = selected["actual_profile_cases"]
        expected_cases = {"nominal"} | {f"C{ci:02d}-D{di:02d}" for ci, di in itertools.product(range(4), repeat=2)}
        if not isinstance(cases, list) or len(cases) != 17 or {case["case_id"] for case in cases} != expected_cases:
            raise ValueError("selected cone requires nominal plus all SIXTEEN distinct actual profile cases")
        metrics = []
        stock_phase_cases = []
        for case in cases:
            if case.get("actual_source_nominal_pose") is True:
                raise ValueError("stationary nominal-pose DESIGN cannot replace whole source qualification")
            ci, di = case["cone_corner_index"], case["drum_corner_index"]
            if case["case_id"] == "nominal":
                if ci is not None or di is not None:
                    raise ValueError("nominal actual-profile case has corner indices")
                cone_profile, drum_profile = profile, drum.STOCK_FORM
            else:
                if type(ci) is not int or type(di) is not int or not 0 <= ci < 4 or not 0 <= di < 4 or case["case_id"] != f"C{ci:02d}-D{di:02d}":
                    raise ValueError("actual profile case has incorrect physical corner indices")
                cone_profile, drum_profile = corners[ci], drum_corners[di]
            _same_record(case["cone"], _profile_record(cone_profile), "actual case cone")
            _same_record(case["drum"], _profile_record(drum_profile), "actual case drum")
            calculation = case["calculation"]
            stock_phase_cases.append((case["case_id"], calculation, cone_profile, drum_profile))
            _same_record(calculation["all_corner_actual3d"]["driver_profile"], case["cone"], "actual UNION cone")
            _same_record(calculation["all_corner_actual3d"]["driven_profile"], case["drum"], "actual UNION drum")
            metrics.append(_require_contact_report(
                calculation, cone_profile, drum_profile, source_domain, source_placement,
            ))
        nominal = next(case["calculation"] for case in cases if case["case_id"] == "nominal")
        _same_record(selected["all_corner_actual3d"], nominal["all_corner_actual3d"], "selected nominal-profile UNION")
        _same_record(row["signed_read_matrix"], nominal["signed_read_matrix"], "selected physical reads")
        bound = max(_finite(case["calculation"]["oblique_phase_bound_rad"], "actual case oblique bound", nonnegative=True) for case in cases)
        _close(row["oblique_phase_bound_rad"], bound, "ALL-profile oblique bound")
        _same_record(row["stock_phase_3d"], selected["stock_phase_3d"], "selected actual operating 3D stock phase")
        stock_phase = _operating_stock_phase_arrays(
            selected["stock_phase_3d"], teeth, drum.TEETH, source_domain["manufactured_datum_mapping"],
        )
        _require_stock_phase_evidence(stock_phase, stock_phase_cases, source_domain, source_placement)
        mesh = {
            "qualification": "qualified", "refusal": None,
            **stock_phase,
            "coverage_min": min(metric["coverage_min"] for metric in metrics),
            "phase_reserve_rad": min(metric["phase_reserve_rad"] for metric in metrics),
            "noncarrying_gap_mm": max(metric["noncarrying_gap_mm"] for metric in metrics),
            "te_bound_rad": max(metric["te_bound_rad"] for metric in metrics),
            "oblique_phase_bound_rad": bound,
            "oblique_phase_bound_excluded_terms": OBLIQUE_PHASE_EXCLUDED_TERMS,
            "centre_mm": (teeth + drum.TEETH) * MODULE_MM / 2.0
                         + _config.fit("cone_drum_oblique_mesh", "edge_slack_mm"),
            "native_certificate": payload["native_certificate"],
        }
        members.append(_QualifiedMember(profile, corners, floors, tuple(mesh.items())))
    return tuple(members)


def _qualified_family(payload: dict | None = None) -> tuple[dict, tuple[_QualifiedMember, ...]]:
    try:
        payload = _read_stock_form_packet() if payload is None else payload
        if not isinstance(payload, dict):
            raise ValueError("cone stock-form packet must be an actual JSON object")
        _require_packet_identity(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return payload, _qualified_members(encoded)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError, OSError) as exc:
        raise ValueError(f"incomplete cone stock-form qualification: {exc}") from exc


def require_qualified_stock_family(payload: dict | None = None) -> dict:
    """Validate complete ALL20 numerical authority, independently of native proof."""
    return _qualified_family(payload)[0]


def _family_member(teeth: int) -> _QualifiedMember:
    _require_member(teeth)
    return _qualified_family()[1][CONFIGURATION_TEETH.index(teeth)]


def stock_form_profile(teeth: int) -> StockFormProfile:
    """The real supported native cut; no missing-input or ideal-N substitute."""
    return _family_member(teeth).profile


def manufacturing_corner_profiles(teeth: int) -> tuple[StockFormProfile, ...]:
    """All four actual OD/thickness corners in the producer's canonical order."""
    return _family_member(teeth).corners


def stock_form_mesh_data(teeth: int) -> dict:
    """Actual qualified 3D inspection/budget bounds; never a planar fallback."""
    return dict(_family_member(teeth).mesh_items)


def _require_member(teeth: int) -> None:
    if type(teeth) is not int or teeth not in CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")


def outside_dia_mm(teeth: int) -> float:
    """Actual qualified blank diameter; unavailable data deliberately refuses."""
    return 2.0 * stock_form_profile(teeth).blank_radius_mm


def tooth_thickness_mm(teeth: int) -> float:
    """Actual installed cutter's circular pitch thickness, not an ideal tooth."""
    return stock_form_profile(teeth).pitch_tooth_thickness_mm



BORE_DIA = 0.375 * MM_PER_IN  # 9.525 (3/8") at T120; smaller on the tip gears
# Face width (user ruling 2026-09-28): the cone set is a solid stack.  Every
# gear is one seat pitch thick, so each bears on its neighbour and the stack
# on MHA-DT-007 sets every station (dt_cone_gear_stack); no gear is bonded.  The
# face is SEAT_PITCH floored to the four places it prints, so the modelled
# stack closes without interference.  Every gear grew SOUTH: its north face
# stays on the station layout (cone_line), so T006's north face -- the
# datum the MHA-VN-016 stack collar is feelered off -- does not move.  The band
# is the cylinder bank's L20 d' rule (+/-0.025 per gear, the 20-gear stack
# accepted at +/-0.20), so it is faced to a micrometer on both sides.
FACE_WIDTH = math.floor(SEAT_PITCH * 1e4) / 1e4
FACE_WIDTH_BAND = (0.025, -0.025)
# Flat clock (user ruling 2026-09-28): the bore's D-flat is the gear's
# angular datum on MHA-DT-004, and its outward normal passes through the centre
# of the phase-0 tooth on local +X, so every gear keeps the clock it is
# placed at.  Index the teeth off the flat on one setup; the native
# BoreFlatClock angular dimension carries this band (error_budget.yaml
# cone_flat_clock), the cylinder gear's CAM_PHASE_TOLERANCE_DEG precedent.
FLAT_CLOCK_TOLERANCE_DEG = 0.25


def floor_radius_min_mm(teeth: int) -> float:
    """Minimum radial envelope of the actual translated finite root arc."""
    return stock_form_profile(teeth).root_radius_min_mm


def floor_radius_max_mm(teeth: int) -> float:
    """Maximum radial envelope, not a filled RootMAX material disk."""
    return stock_form_profile(teeth).root_radius_max_mm


def floor_limits_mm(teeth: int) -> tuple[float, float]:
    """Qualified printed root-envelope diameters including every tool corner."""
    return _family_member(teeth).floor_limits_mm


def bore_dia_mm(teeth: int) -> float:
    """Return the configured bore that fits the matching stepped-shaft land."""
    _require_member(teeth)
    # T006/T012 share the actual terminal reader. Their strength acceptance
    # is rederived below from the current cutter-owned printed floor MINs.
    if teeth <= 12:
        return TERMINAL_DIA_MM
    if teeth == 18:
        return 0.125 * MM_PER_IN
    if teeth == 24:
        return 0.25 * MM_PER_IN
    return BORE_DIA


def material_specification(teeth: int) -> str:
    """Return the configuration-owned alloy printed in that sheet's title block."""
    _require_member(teeth)
    return TIP_MATERIAL_SPEC if teeth <= 24 else BODY_MATERIAL_SPEC


FAMILY_BORES_MM = {teeth: bore_dia_mm(teeth) for teeth in CONFIGURATION_TEETH}

# The sole special web is the user's T006 >=0.62 ruling; T012 and the other
# gears must achieve the ordinary 2.0 target, not merely the 1.5 hard floor.
# These are acceptance inputs; the factory checks every actual cutter corner.
MACHINED_WEB_FLOOR_MM = 1.5
MACHINED_WEB_TARGET_MM = 2.0
WEB_EXCEPTIONS_MM: dict[int, float] = {6: 0.62}
TERMINAL_WEB_REQUIREMENTS_MM = {
    6: WEB_EXCEPTIONS_MM[6],
    12: MACHINED_WEB_TARGET_MM,
}

# Printed places of the bore band (model-owned, DRAWING_PRECISION).
BORE_BAND_PLACES = 3


# The band is UNIFORM: BoreCutDia is one model dimension across all twenty
# configurations. Keep the retained seat class independent of selected cutter
# settings so numerical qualification does not require its own output first.
def _seat_fit_band() -> tuple[float, float]:
    """(upper, lower): the round seat fit that holds on every gear land."""
    carried = [
        seat_bore_band(band)
        for band, teeth in zip(SECTION_DIA_BANDS, SECTION_CONE_GEAR_TEETH)
        if teeth
    ]
    return (min(band[0] for band in carried), max(band[1] for band in carried))


def terminal_web_bore_upper_mm() -> float:
    """Largest bore deviation admitted by the qualified terminal root limits."""
    scale = 10**BORE_BAND_PLACES
    cap = min(
        floor_limits_mm(teeth)[0] - 2.0 * minimum
        - math.ceil(bore_dia_mm(teeth) * scale - 1e-9) / scale
        for teeth, minimum in TERMINAL_WEB_REQUIREMENTS_MM.items()
    )
    return math.floor(cap * scale + 1e-9) / scale


BORE_BAND_FIT_UPPER, BORE_BAND_LOWER = _seat_fit_band()
BORE_DIA_BAND = (
    round(BORE_BAND_FIT_UPPER, BORE_BAND_PLACES),
    round(BORE_BAND_LOWER, BORE_BAND_PLACES),
)
if BORE_DIA_BAND[0] - BORE_DIA_BAND[1] < 0.02 - 1e-9:
    raise AssertionError(
        f"cone-gear seat bore band {BORE_DIA_BAND[0]:+.3f}/"
        f"{BORE_DIA_BAND[1]:+.3f} is under 0.02 wide"
    )


def terminal_web_mm(teeth: int) -> float:
    """Print-worst radial ligament, read from the actual cutter and fit."""
    if teeth not in TERMINAL_WEB_REQUIREMENTS_MM:
        raise ValueError(f"T{teeth:03d} is not carried by the terminal land")
    scale = 10**BORE_BAND_PLACES
    maximum_bore = math.ceil((bore_dia_mm(teeth) + BORE_DIA_BAND[0]) * scale - 1e-9) / scale
    return (floor_limits_mm(teeth)[0] - maximum_bore) / 2.0




# --- D-bore (user ruling 2026-09-28) -----------------------------------------
#
# Every bore is a D: the round bore above plus one flat, parallel to the
# land's flat, whose outward normal is local +X (through the phase-0 tooth,
# FLAT_CLOCK_TOLERANCE_DEG).  Across-flat (AF) is measured from the flat to
# the far side of the round bore, the land's own AF nominal; the band keeps
# 0.01-0.03 AF clearance on the land's FLAT_AF_BAND.  One band for all twenty,
# so one BoreAF tolerance serves every configuration.
BORE_AF_BAND = flat_bore_af_band(FLAT_AF_BAND)  # (+0.020, +0.010)
BORE_AF_PLACES = 3


def land_section(teeth: int) -> int:
    """Index of the MHA-DT-004 land (cone_shaft_land_bands) carrying ``teeth``."""
    _require_member(teeth)
    for section, carried in enumerate(SECTION_CONE_GEAR_TEETH):
        if teeth in carried:
            return section
    raise AssertionError(f"no MHA-DT-004 land carries the T{teeth:03d} cone gear")


def bore_flat_af_mm(teeth: int) -> float:
    """Return the configuration's nominal bore across-flat."""
    across_flat = SECTION_FLAT_AF[land_section(teeth)]
    if across_flat is None:
        raise AssertionError(f"the T{teeth:03d} land has no flat")
    return across_flat


def bore_flat_offset_mm(teeth: int) -> float:
    """Distance from the bore axis to the flat (AF minus the bore radius)."""
    return bore_flat_af_mm(teeth) - bore_dia_mm(teeth) / 2.0


def bore_flat_segment_area_mm2(teeth: int) -> float:
    """Area the flat leaves standing inside the round bore (a circular
    segment), per unit face: the solid gains this over a round bore."""
    radius = bore_dia_mm(teeth) / 2.0
    offset = bore_flat_offset_mm(teeth)
    return radius * radius * math.acos(offset / radius) - offset * math.sqrt(
        radius * radius - offset * offset
    )


for _teeth in CONFIGURATION_TEETH:
    if not 0.0 < bore_flat_offset_mm(_teeth) < bore_dia_mm(_teeth) / 2.0:
        raise AssertionError(
            f"T{_teeth:03d} bore AF {bore_flat_af_mm(_teeth)} does not cut a "
            f"flat into its Ø{bore_dia_mm(_teeth)} bore"
        )


def bore_surface_finish(teeth: int) -> SurfaceFinishControl:
    """Return the bore finish control qualified by this configuration's bore."""
    return SurfaceFinishControl(
        "cone_gear_bore",
        MACHINED_UM,
        CylinderFace(bore_dia_mm(teeth)),
        native_attachment="model",
    )


# Part PMI is authored while the default T120 configuration is active. Each
# sheet resolves its own "cone_gear_bore" finish row: using T120's row would
# reject the actual terminal bore on T006/T012.
SURFACE_FINISHES = (bore_surface_finish(TEETH),)
BORE_SURFACE_FINISHES: dict[int, tuple[SurfaceFinishControl, ...]] = {
    teeth: (bore_surface_finish(teeth),) for teeth in CONFIGURATION_TEETH
}

# The part's two construction-only authoring sketches.  The part saves both
# hidden (they would otherwise render in every assembly that places a gear);
# the sheet's front view shows them again to import their dimensions.
TOOTH_REFERENCE_SKETCH = "ToothThicknessReference"
GAP_FLOOR_SKETCH = "GapFloorReference"
REFERENCE_SKETCHES = (TOOTH_REFERENCE_SKETCH, GAP_FLOOR_SKETCH)

# The three blank sizes, actual circular pitch-thickness acceptance and
# functional root-envelope limits. ToothThickness and FloorDia are driving
# dimensions in construction-only INSPECTION sketches, not cutter controls.
# The finite translated root is an off-centre arc, not a bowed ideal chord.
# Native tolerances remain meaningful: the pitch thickness has its retained
# bilateral band; the root envelope has the qualified per-count LIMIT pair.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlankProfile": {"BlankDia"},
    "Blank": {"FaceWidth"},
    "BoreProfile": {"BoreCutDia", "BoreAF", "BoreFlatClock"},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness"},
    GAP_FLOOR_SKETCH: {"FloorDia"},
}

# Keep the source-owned blank band: every OD/thickness corner must retain
# finite cutter support, tip land, root air and web before construction.
BLANK_DIA_BAND = (0.10, -0.10)


def configuration_number(part_number: str, teeth: int) -> str:
    """Return one configuration sheet's drawing number, e.g. ``MHA-DT-003-T006``."""
    _require_member(teeth)
    number = part_number.strip().upper()
    if not number:
        raise ValueError("cone-gear part number must not be blank")
    return f"{number}-T{teeth:03d}"


# --- Decimal places, authored ON THE PART ------------------------------------
#
# Policy rule 2: places and bands are model properties.  Three places belong
# on the fitted bore, across-flat, tooth thickness and gap-floor limits, so
# both ends of each narrow floor window print without rounding inward.
# Tip diameter prints two places with its own BLANK_DIA_BAND (below); face
# width prints four, like the cylinder gear's OverallThickness under the same
# rule: three would round one limit of the +/-0.025 band inward.  The flat
# clock prints one place of degrees, the cylinder gear's NotchPhase precedent:
# +/-0.25 needs no more.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlankProfile": {"BlankDia": 2},
    "Blank": {"FaceWidth": 4},
    "BoreProfile": {"BoreCutDia": 3, "BoreAF": BORE_AF_PLACES, "BoreFlatClock": 1},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness": 3},
    GAP_FLOOR_SKETCH: {"FloorDia": 3},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )
