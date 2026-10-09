r"""Pure-data contract for the MHA-PD-005 composite platen rack.

The rack is purchased SDP/SI A 1B12-Y324, a 48 in commercial brass strip.
Its catalog face width and height are 3/16 in; its pitch and pressure angle
must match the feed sleeve. It is cut to the platen length, then soft-soldered
to the backer. No braze gap, solder fillet, tooth-form accuracy or inventory
promise is invented. The CAD represents nominal standard straight-flank
rack teeth; profile shift changes assembly axis distance, not the rack.

Local frame: length along +X, backer bottom at Y=0, front face at Z=0.
The backer spans the full depth; the rack is centred in that depth, with its
plain bottom at BACKER_HEIGHT and tooth crests at BAR_HEIGHT. The union has
no modelled solder thickness. EndStockProfile is a hidden model-owned
witness of the strip's section and joint line, not a second solid body.
Routine fabricated sizes use the title-block .XX band. Bought strip sizes
are parenthesized references; the SKU, not a new accuracy band, owns them.
The nominal CAD end phase is not a cut-indexing requirement: the actual
purchased rack's gap phase is accommodated when the mesh is set at assembly.
The separate paper_drive_rack_travel contract clips every physical carrier
to the shortest finished cut length, reserves an end-affected strip at each
phase-unknown end and defines the mandatory engaged-feed operating window. That
assembly/traveler requirement is not a hardware stop or supplier accuracy
claim, and it must preserve the complete located recording-paper sweep.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import _gear_quality as quality

import pd_transgear_feed_pinion_spec as FEED
from pd_platen_spec import PLATE_WIDTH

MM_PER_IN = FEED.MM_PER_IN
DP = FEED.DIAMETRAL_PITCH
PA_DEG = FEED.PRESSURE_ANGLE_DEG
MODULE_MM = FEED.MODULE_MM

# Primary product fields: https://shop.sdp-si.com/a-1b12-y324.html .
# Catalog p1-193: https://sdp-si.com/D820/PDFS/Gears.pdf (Y = PA20).
# Commercial class supplies no numerical pitch-accuracy certificate here.
PURCHASED_RACK_SUPPLIER = "SDP/SI"
PURCHASED_RACK_SKU = "A 1B12-Y324"
PURCHASED_RACK_MATERIAL = "Brass"
PURCHASED_RACK_DP = 32.0
PURCHASED_RACK_PA_DEG = 20.0
PURCHASED_RACK_LENGTH_IN = 48.0
PURCHASED_RACK_LENGTH_MM = PURCHASED_RACK_LENGTH_IN * MM_PER_IN
PURCHASED_RACK_FACE_WIDTH_IN = 3.0 / 16.0
PURCHASED_RACK_HEIGHT_IN = 3.0 / 16.0
PURCHASED_RACK_QUALITY_CLASS = "Commercial"
if DP != PURCHASED_RACK_DP or PA_DEG != PURCHASED_RACK_PA_DEG:
    raise AssertionError("purchased rack pitch/PA no longer match the feed sleeve")

CUT_LENGTH_MM = PLATE_WIDTH
BAR_LENGTH = CUT_LENGTH_MM  # rack and backer end flush with the platen
BAR_HEIGHT = 12.0  # accepted exposed band below the guide rail
BAR_THICKNESS = 6.0  # accepted edge-on photo envelope
RACK_HEIGHT = PURCHASED_RACK_HEIGHT_IN * MM_PER_IN
RACK_THICKNESS = PURCHASED_RACK_FACE_WIDTH_IN * MM_PER_IN
BACKER_HEIGHT = BAR_HEIGHT - RACK_HEIGHT
RACK_Z0 = (BAR_THICKNESS - RACK_THICKNESS) / 2.0

PITCH = math.pi * MODULE_MM
ADDENDUM = MODULE_MM
DEDENDUM = FEED.DEDENDUM_FACTOR * MODULE_MM
PITCH_LINE_Y = BAR_HEIGHT - ADDENDUM
ROOT_Y = PITCH_LINE_Y - DEDENDUM
CUT_TOP_Y = BAR_HEIGHT + 1.0  # seed-cut overrun, not a finished size
TAN_PA = math.tan(math.radians(PA_DEG))
GAP_COUNT = int(BAR_LENGTH / PITCH)
FIRST_GAP_X = PITCH / 2.0  # nominal CAD phase; not a finished-end control


def half_width(y: float) -> float:
    """Gap half-width in mm: quarter pitch at the reference line."""
    return PITCH / 4.0 + (y - PITCH_LINE_Y) * TAN_PA


# One-millimetre pins fit the purchased 32-DP, 20-degree straight flanks.
# Actual certified pin diameters, not this nominal, enter every correction.
INCOMING_GAUGE_PIN_DIA_MM = 1.0


class RackGaugePinContact(NamedTuple):
    centre_y_mm: float
    flank_contact_y_mm: float
    root_clearance_mm: float


def rack_gauge_pin_contact_mm(actual_pin_diameter_mm: float) -> RackGaugePinContact:
    """Nominal flank seating; verify both flanks and root freedom on receipt.

    This proves the chosen pin's source-profile seat, not purchased accuracy.
    A physically obstructed or incomplete seat is an incoming REJECT.
    """
    if (
        isinstance(actual_pin_diameter_mm, bool)
        or not math.isfinite(actual_pin_diameter_mm)
        or actual_pin_diameter_mm <= 0.0
    ):
        raise ValueError("rack gauge pin diameter must be finite and positive")
    radius = actual_pin_diameter_mm / 2.0
    angle = math.radians(PA_DEG)
    centre_y = PITCH_LINE_Y + (radius / math.cos(angle) - PITCH / 4.0) / TAN_PA
    contact_y = centre_y - radius * math.sin(angle)
    root_clearance = centre_y - radius - ROOT_Y
    if not (ROOT_Y < contact_y < BAR_HEIGHT and root_clearance > 0.0):
        raise ValueError("rack gauge pin cannot seat on both full flanks clear of the root")
    return RackGaugePinContact(centre_y, contact_y, root_clearance)


def rack_over_pins_span_mm(
    *, pitch_intervals: int, actual_pin_diameters_mm: tuple[float, float]
) -> float:
    """Outside-pin MACHINE-X span, parallel to the rack, for counted gaps.

    The finished cut phase is irrelevant. Count actual intervening pitches;
    never substitute FIRST_GAP_X/GAP_COUNT for the physical station manifest.
    Unequal pin diameters change seat heights, so Euclidean distance is NOT
    this measurement. Correct using each pin's actual certified diameter.
    This span controls gap-centre index only: symmetric gap-width variation
    can leave it unchanged. It does NOT certify both-flank normal/thickness
    errors or the complete rack contact profile.
    """
    if (
        isinstance(pitch_intervals, bool)
        or not isinstance(pitch_intervals, int)
        or pitch_intervals < 1
    ):
        raise ValueError("rack gauge span needs a positive counted pitch interval")
    if len(actual_pin_diameters_mm) != 2:
        raise ValueError("rack gauge span needs two actual certified pin diameters")
    first, second = actual_pin_diameters_mm
    rack_gauge_pin_contact_mm(first)
    rack_gauge_pin_contact_mm(second)
    return pitch_intervals * PITCH + (first + second) / 2.0


def _require_stock_dimension_maximum_mm(
    label: str, measured_maximum_mm: float, uncertainty_mm: float, limit_mm: float
) -> float:
    if not all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0.0
        for value in (measured_maximum_mm, uncertainty_mm)
    ):
        raise ValueError(f"incoming rack {label} and uncertainty must be finite positive values")
    paid_upper = math.nextafter(math.fsum((measured_maximum_mm, uncertainty_mm)), math.inf)
    if paid_upper > limit_mm:
        raise ValueError(
            f"REJECT incoming rack {label} upper {paid_upper:.6f} mm exceeds "
            f"source maximum {limit_mm:.6f} mm"
        )
    return paid_upper


def require_rack_stock_section_measurements_mm(
    *,
    measured_stock_height_max_mm: float,
    stock_height_measurement_uncertainty_mm: float,
    measured_face_width_max_mm: float,
    face_width_measurement_uncertainty_mm: float,
) -> tuple[float, float]:
    """Receive actual whole-stock height/face extrema with paid calibration.

    Height and face width are separate measurements, not a catalog-square
    equality. Extrema cover the complete stock used; isolated sample readings
    do not supply them. This accepts only section size, NOT product identity,
    flank seating, pitch/index, full-face lead or the loaded assembly.
    """
    return (
        _require_stock_dimension_maximum_mm(
            "stock height", measured_stock_height_max_mm,
            stock_height_measurement_uncertainty_mm, quality.rack_stock_height_max_mm(),
        ),
        _require_stock_dimension_maximum_mm(
            "face width", measured_face_width_max_mm,
            face_width_measurement_uncertainty_mm, quality.rack_face_width_max_mm(),
        ),
    )

class RackMeasuredUpperBound(NamedTuple):
    """Certified whole-domain maximum and its positive compound uncertainty.

    Uncertainty includes calibration, datum capture, actual gauge radii and
    any enclosure/model adjustment used by the named inspection method.
    The owning field supplies units; zero is allowed for a measured error,
    never for its uncertainty. These are enclosures, not sample extrema.
    """

    measured_maximum: float
    uncertainty: float


class RackFeatureMapping(NamedTuple):
    """One connected native feature in the common physical stock datum.

    Patches are (u0, u1, v0, v1) rectangles. Each encloses its CONTINUOUS
    domain, with u normalized over the whole native feature and v over the
    actual complete measured face. Never renormalize individual patches.
    Crest indices run 0..N; gap stations identify both flanks and roots.
    The mapping covers the entire material boundary outside the certified
    root envelope. No rack-normal or normal-derivative bound is inferred.
    """

    feature_id: str
    kind: str
    station: int
    start_vertex_id: str
    end_vertex_id: str
    parameter_patches: tuple[tuple[float, float, float, float], ...]
    global_datum_id: str
    native_mapping_ref: str


class RackWireSecantReading(NamedTuple):
    """Wire CENTRE coordinates in the one material XY datum.

    Each positive XY uncertainty is compound method/datum/calibration error,
    not a source instrument floor substituted for an actual calibration.
    The SAME physical wire/entered diameter at both heights has one common
    normal-radius offset, which cancels only under the straight-SIDE MODEL.
    """

    xy_mm: tuple[float, float]
    x_uncertainty_mm: float
    y_uncertainty_mm: float
    wire_id: str
    wire_diameter_mm: float


class RackFlankEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    # Signed X-equivalent errors x +/- tan(PA)*y, NOT unit-normal distance.
    constraint_error_band_mm: tuple[float, float]
    constraint_uncertainty_mm: float
    boundary_mm: RackMeasuredUpperBound
    side_secant: tuple[RackWireSecantReading, RackWireSecantReading]


class RackCrestEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    boundary_mm: RackMeasuredUpperBound


class RackRootEnclosure(NamedTuple):
    mapping: RackFeatureMapping
    # Encloses ALL root material toward the pinion, including transitions.
    intrusion_mm: RackMeasuredUpperBound


class RackFormInspectionReceipt(NamedTuple):
    """External whole-material POINT enclosures, not a point-cloud adapter.

    A qualified extrusion process or actual functional roll must justify
    complete material, both-side intercept and root envelopes over every
    native feature and the complete actual face. A scalar roll result alone
    cannot establish these XY enclosures. The named evidence is a premise,
    not a synthetic vendor certificate or a local rack-normal/C1 bound.
    One independently captured material/fixture/end XY reference applies to
    every station, face and side; even a global flank/pin-seat Y fit is
    forbidden because it can erase uniform tooth-thickness error. Each
    compound uncertainty pays actual calibration, datum, angle/projection,
    gauge diameter, certification and thermal effects above the source
    instrument-only floor. No real receipt is synthesized by this module.
    """

    stock_id: str
    global_datum_id: str
    datum_reference_kind: str
    datum_reference_xy_mm: tuple[float, float]
    method_ref: str
    calibration_ref: str
    trace_ref: str
    whole_point_enclosure_ref: str
    inspection_basis: str
    boundary_partition_ref: str
    native_mapping_ref: str
    parameterization: str
    physical_gap_stations: tuple[int, ...]
    stock_height_mm: RackMeasuredUpperBound
    face_width_mm: RackMeasuredUpperBound
    # Minimum carrying face after ALL actual edge zones; does not crop v.
    measured_usable_face_min_mm: float
    usable_face_measurement_uncertainty_mm: float
    enclosures: tuple[RackFlankEnclosure | RackCrestEnclosure | RackRootEnclosure, ...]


class RackFormAdmissionReport(NamedTuple):
    """Conditional drawn-form conformance, NEVER a hardware/mesh verdict.

    The physical qualifier must still pay root intrusion and prove >=.25 mm
    whole-box separation; root normals are not assumed inactive here.
    Separate index receipts and assembled rigid face/axis alignment remain
    independent obligations. No hardware qualification boolean is returned.
    """

    scope: str
    constraint_relative_mm: float
    active_boundary_mm: float
    root_intrusion_mm: float
    global_datum_id: str
    station_ids: tuple[int, ...]
    feature_ids: tuple[str, ...]
    stock_height_upper_mm: float
    face_width_upper_mm: float
    status_text: str
    usable_face_lower_mm: float
    receipt: RackFormInspectionReceipt
    working_side_form_model_premise: str
    working_side_angle_bands_rad: tuple[tuple[str, tuple[float, float]], ...]


def _rack_receiving_number(value: float, label: str, *, positive: bool = False) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0.0)):
        raise ValueError(f"UNKNOWN rack {label}: finite numeric"
                         + (" positive" if positive else "") + " value required")
    return float(value)


def _rack_receiving_reference(value: str, label: str) -> None:
    if (type(value) is not str or not value.strip()
            or value.strip().lower() in {"unknown", "none", "n/a", "todo"}):
        raise ValueError(f"UNKNOWN rack {label}: actual evidence reference required")


def _rack_paid_form_maximum(
    record: RackMeasuredUpperBound, limit: float, label: str, *, minimum_uncertainty: float
) -> float:
    if not isinstance(record, RackMeasuredUpperBound):
        raise ValueError(f"UNKNOWN rack {label}: certified maximum/uncertainty required")
    measured = _rack_receiving_number(record.measured_maximum, label)
    uncertainty = _rack_receiving_number(record.uncertainty, f"{label} uncertainty",
                                         positive=True)
    if uncertainty < minimum_uncertainty:
        raise ValueError(f"UNKNOWN rack {label}: uncertainty below declared shop floor")
    if measured < 0.0:
        raise ValueError(f"UNKNOWN rack {label}: nonnegative maximum required")
    paid = math.nextafter(math.fsum((measured, uncertainty)), math.inf)
    if paid > limit:
        raise ValueError(f"REJECT rack {label}: paid {paid!r} exceeds source {limit!r}")
    return paid


def _require_rack_continuous_coverage(mapping: RackFeatureMapping) -> None:
    """Prove rectangle-union coverage, not a grid/sample-point assertion."""
    patches = mapping.parameter_patches
    if not isinstance(patches, tuple) or not patches:
        raise ValueError("UNKNOWN rack continuous feature/face coverage")
    for patch in patches:
        if not isinstance(patch, tuple) or len(patch) != 4:
            raise ValueError("UNKNOWN rack continuous parameter patch")
        u0, u1, v0, v1 = (
            _rack_receiving_number(value, "parameter patch") for value in patch
        )
        if not (0.0 <= u0 < u1 <= 1.0 and 0.0 <= v0 < v1 <= 1.0):
            raise ValueError("UNKNOWN rack full-native u/full-face v parameter patch")
    u_edges = sorted({0.0, 1.0, *(value for patch in patches for value in patch[:2])})
    for u0, u1 in zip(u_edges, u_edges[1:]):
        intervals = sorted((v0, v1) for a, b, v0, v1 in patches if a <= u0 and b >= u1)
        covered_to = 0.0
        for v0, v1 in intervals:
            if v0 > covered_to:
                break
            covered_to = max(covered_to, v1)
        if covered_to < 1.0:
            raise ValueError("UNKNOWN rack incomplete continuous feature/face coverage")


def require_rack_working_side_secant_angle_band_rad(
    *, readings: tuple[RackWireSecantReading, RackWireSecantReading], flank_kind: str,
) -> tuple[float, float]:
    """Paid secant angle under the named straight/smooth working-SIDE model.

    This backs its conditional angular admission; it never infers arbitrary
    local normals, straightness, roughness or a vendor certificate from pins.
    Both wire centres are in the same native material XY datum, lower then
    upper Y. A common actual radius is NOT corrected twice with nominal wire
    data: its fixed normal-offset vector cancels in the difference.
    """
    from paper_drive_geom import feed_rack_working_side_angle_band_rad

    quality.purchased_rack_working_side_form_model_premise()
    if (not isinstance(readings, tuple) or len(readings) != 2
            or any(not isinstance(reading, RackWireSecantReading) for reading in readings)):
        raise ValueError("UNKNOWN rack two typed same-wire centre secant readings")
    if flank_kind not in {"left-flank", "right-flank"}:
        raise ValueError("UNKNOWN rack working-side secant native flank identity")
    for reading in readings:
        _rack_receiving_reference(reading.wire_id, "secant actual wire identity")
        _rack_receiving_number(reading.wire_diameter_mm, "secant actual wire diameter", positive=True)
        if not isinstance(reading.xy_mm, tuple) or len(reading.xy_mm) != 2:
            raise ValueError("UNKNOWN rack secant centre coordinates in the common XY datum")
        for coordinate in reading.xy_mm:
            _rack_receiving_number(coordinate, "secant wire centre coordinate")
        ux = _rack_receiving_number(reading.x_uncertainty_mm, "secant centre X uncertainty", positive=True)
        uy = _rack_receiving_number(reading.y_uncertainty_mm, "secant centre Y uncertainty", positive=True)
        if ux < quality.wire_measurement_uncertainty_mm() or uy < quality.pitch_index_measurement_uncertainty_mm():
            raise ValueError("UNKNOWN rack secant XY uncertainty below source instrument floors")
    lower, upper = readings
    if lower.wire_id != upper.wire_id or lower.wire_diameter_mm != upper.wire_diameter_mm:
        raise ValueError("REJECT rack secant requires SAME physical wire and diameter at both heights")
    dy = math.fsum((upper.xy_mm[1], -lower.xy_mm[1]))
    if dy < quality.rack_flank_secant_minimum_height_mm():
        raise ValueError("REJECT rack measured secant height separation below source minimum")
    sign = -1 if flank_kind == "left-flank" else 1
    dx = sign * math.fsum((upper.xy_mm[0], -lower.xy_mm[0]))
    ux = math.nextafter(math.fsum((lower.x_uncertainty_mm, upper.x_uncertainty_mm)), math.inf)
    uy = math.nextafter(math.fsum((lower.y_uncertainty_mm, upper.y_uncertainty_mm)), math.inf)
    dx_low = math.nextafter(dx - ux, -math.inf)
    dx_high = math.nextafter(dx + ux, math.inf)
    dy_low = math.nextafter(dy - uy, -math.inf)
    dy_high = math.nextafter(dy + uy, math.inf)
    if dx_low <= 0.0 or dy_low <= 0.0:
        raise ValueError("REJECT rack secant uncertainty does not retain native flank/height direction")
    angle = (
        math.nextafter(math.atan2(dx_low, dy_high), -math.inf),
        math.nextafter(math.atan2(dx_high, dy_low), math.inf),
    )
    required = feed_rack_working_side_angle_band_rad()
    if angle[0] < required[0] or angle[1] > required[1]:
        raise ValueError("REJECT rack complete paid secant-angle interval leaves source working-SIDE band")
    return angle


def require_rack_form_admission_mm(
    *, receipt: RackFormInspectionReceipt, required_gap_stations: tuple[int, ...]
) -> RackFormAdmissionReport:
    """Receive the whole finite material envelope at the source shop resolution.

    Corrected pin XY/actual-diameter observations can inform the external
    method, but finite contacts, raw clouds and filtered/C1 booleans cannot
    establish a whole point envelope. Only the explicit process/functional
    evidence and continuous material data above are admitted, including
    every physically manifested station. The report is conditional on
    truthful external evidence, not a claim that purchased stock was measured.
    """
    # Deferred pure import avoids Spec <-> Geom initialization cycles. Neither
    # caller-supplied limits nor a missing-source nominal fallback is allowed.
    from paper_drive_geom import (
        feed_rack_form_admission_controls,
        feed_rack_receiving_boundary_uncertainty_mm,
        feed_rack_receiving_constraint_uncertainty_mm,
        feed_rack_receiving_root_uncertainty_mm,
    )
    from _printed_tolerance import printed_band_mm

    controls = feed_rack_form_admission_controls()
    if not isinstance(receipt, RackFormInspectionReceipt):
        raise ValueError("UNKNOWN rack whole-point-envelope inspection receipt")
    stations = required_gap_stations
    if (not isinstance(stations, tuple) or not stations
            or any(type(station) is not int or station < 0 for station in stations)
            or stations != tuple(range(len(stations)))
            or not isinstance(receipt.physical_gap_stations, tuple)
            or any(type(station) is not int for station in receipt.physical_gap_stations)
            or receipt.physical_gap_stations != stations):
        raise ValueError("UNKNOWN rack complete physical gap-station manifest")
    # Cut phase is uncontrolled. Two pitch end strips and one complete-feature
    # span give this conservative necessary count, NOT the nominal CAD count.
    minimum_length = CUT_LENGTH_MM - printed_band_mm(DRAWING_PRECISION_BY_NAME["Length"])
    minimum_count = math.floor(minimum_length / PITCH) - 3
    if len(stations) < minimum_count:
        raise ValueError("UNKNOWN rack sample-only manifest cannot cover the finite stock")
    for field in (
        "stock_id", "global_datum_id", "method_ref", "calibration_ref", "trace_ref",
        "whole_point_enclosure_ref", "boundary_partition_ref", "native_mapping_ref",
    ):
        _rack_receiving_reference(getattr(receipt, field), field)
    if receipt.inspection_basis not in {"qualified-extrusion-process", "actual-functional-roll"}:
        raise ValueError("UNKNOWN rack whole-point process/functional evidence basis")
    if receipt.datum_reference_kind not in {"independent-material", "independent-fixture",
                                            "independent-end"}:
        raise ValueError("UNKNOWN rack independent global XY datum; no flank/pin fitting")
    if (not isinstance(receipt.datum_reference_xy_mm, tuple)
            or len(receipt.datum_reference_xy_mm) != 2):
        raise ValueError("UNKNOWN rack actual global XY datum coordinates")
    for value in receipt.datum_reference_xy_mm:
        _rack_receiving_number(value, "global XY datum coordinate")
    if receipt.parameterization != "full-native-u/full-actual-face-v":
        raise ValueError("UNKNOWN rack whole-native/whole-face parameterization")
    if not isinstance(receipt.stock_height_mm, RackMeasuredUpperBound) or not isinstance(
        receipt.face_width_mm, RackMeasuredUpperBound
    ):
        raise ValueError("UNKNOWN rack separate actual stock section receipts")
    height, width = require_rack_stock_section_measurements_mm(
        measured_stock_height_max_mm=receipt.stock_height_mm.measured_maximum,
        stock_height_measurement_uncertainty_mm=receipt.stock_height_mm.uncertainty,
        measured_face_width_max_mm=receipt.face_width_mm.measured_maximum,
        face_width_measurement_uncertainty_mm=receipt.face_width_mm.uncertainty,
    )
    usable_face = _rack_receiving_number(receipt.measured_usable_face_min_mm,
                                         "actual usable face minimum", positive=True)
    usable_uncertainty = _rack_receiving_number(
        receipt.usable_face_measurement_uncertainty_mm, "usable face uncertainty", positive=True
    )
    usable_lower = math.nextafter(math.fsum((usable_face, -usable_uncertainty)), -math.inf)
    usable_upper = math.nextafter(math.fsum((usable_face, usable_uncertainty)), math.inf)
    if usable_lower <= 0.0 or usable_upper > width:
        raise ValueError("UNKNOWN rack nonempty calibrated whole usable face after edge zones")
    expected = {
        *((kind, station) for station in stations for kind in ("left-flank", "right-flank", "root")),
        *(("crest", index) for index in range(len(stations) + 1)),
    }
    if not isinstance(receipt.enclosures, tuple) or not receipt.enclosures:
        raise ValueError("UNKNOWN rack full feature enclosures")
    by_feature = {}
    feature_ids = set()
    constraint_lows, constraint_highs = [], []
    maxima = {"active_boundary_mm": 0.0, "root_intrusion_mm": 0.0}
    side_angle_bands = []
    boundary_uncertainty_floor = feed_rack_receiving_boundary_uncertainty_mm()
    constraint_uncertainty_floor = feed_rack_receiving_constraint_uncertainty_mm()
    root_uncertainty_floor = feed_rack_receiving_root_uncertainty_mm()
    for enclosure in receipt.enclosures:
        if not isinstance(enclosure, (RackFlankEnclosure, RackCrestEnclosure, RackRootEnclosure)):
            raise ValueError("UNKNOWN rack typed complete feature enclosure")
        mapping = enclosure.mapping
        if not isinstance(mapping, RackFeatureMapping) or type(mapping.station) is not int:
            raise ValueError("UNKNOWN rack connected native feature mapping")
        for field in ("feature_id", "start_vertex_id", "end_vertex_id", "global_datum_id",
                      "native_mapping_ref"):
            _rack_receiving_reference(getattr(mapping, field), field)
        if (mapping.global_datum_id != receipt.global_datum_id
                or mapping.native_mapping_ref != receipt.native_mapping_ref):
            raise ValueError("UNKNOWN rack per-feature datum/refit is forbidden")
        key = (mapping.kind, mapping.station)
        if (key not in expected or key in by_feature or mapping.feature_id in feature_ids
                or mapping.start_vertex_id == mapping.end_vertex_id):
            raise ValueError("UNKNOWN rack duplicate/unexpected/disconnected feature")
        if ((isinstance(enclosure, RackFlankEnclosure)
             and mapping.kind not in {"left-flank", "right-flank"})
                or (isinstance(enclosure, RackCrestEnclosure) and mapping.kind != "crest")
                or (isinstance(enclosure, RackRootEnclosure) and mapping.kind != "root")):
            raise ValueError("UNKNOWN rack feature type disagrees with native mapping")
        _require_rack_continuous_coverage(mapping)
        by_feature[key] = mapping
        feature_ids.add(mapping.feature_id)
        if isinstance(enclosure, RackRootEnclosure):
            paid = _rack_paid_form_maximum(
                enclosure.intrusion_mm, controls["root_intrusion_mm"],
                "whole root-material intrusion",
                minimum_uncertainty=root_uncertainty_floor,
            )
            maxima["root_intrusion_mm"] = max(maxima["root_intrusion_mm"], paid)
            continue
        paid = _rack_paid_form_maximum(
            enclosure.boundary_mm, controls["active_boundary_mm"],
            "whole active material point boundary",
            minimum_uncertainty=boundary_uncertainty_floor,
        )
        maxima["active_boundary_mm"] = max(maxima["active_boundary_mm"], paid)
        if isinstance(enclosure, RackFlankEnclosure):
            side_angle_bands.append((
                mapping.feature_id,
                require_rack_working_side_secant_angle_band_rad(
                    readings=enclosure.side_secant, flank_kind=mapping.kind,
                ),
            ))
            band = enclosure.constraint_error_band_mm
            if not isinstance(band, tuple) or len(band) != 2:
                raise ValueError("UNKNOWN rack both-flank signed constraint enclosure")
            low, high = (_rack_receiving_number(value, "flank constraint") for value in band)
            if low > high:
                raise ValueError("UNKNOWN rack ordered flank constraint enclosure")
            uncertainty = _rack_receiving_number(enclosure.constraint_uncertainty_mm,
                                                 "flank constraint uncertainty", positive=True)
            if uncertainty < constraint_uncertainty_floor:
                raise ValueError("UNKNOWN rack flank constraint uncertainty below declared shop floor")
            constraint_lows.append(math.nextafter(math.fsum((low, -uncertainty)), -math.inf))
            constraint_highs.append(math.nextafter(math.fsum((high, uncertainty)), math.inf))
    if set(by_feature) != expected:
        raise ValueError("UNKNOWN rack missing either flank/crest/root or physical station")
    chain = [by_feature[("crest", 0)]]
    for index, station in enumerate(stations):
        chain.extend((by_feature[("left-flank", station)], by_feature[("root", station)],
                      by_feature[("right-flank", station)], by_feature[("crest", index + 1)]))
    if any(first.end_vertex_id != second.start_vertex_id
           for first, second in zip(chain, chain[1:])):
        raise ValueError("UNKNOWN rack full native boundary partition is disconnected")
    vertices = (chain[0].start_vertex_id, *(mapping.end_vertex_id for mapping in chain))
    if len(set(vertices)) != len(vertices):
        raise ValueError("UNKNOWN rack boundary mapping loops or refits features")
    relative = math.nextafter(math.fsum((max(constraint_highs), -min(constraint_lows))), math.inf)
    if relative > controls["constraint_relative_mm"]:
        raise ValueError("REJECT rack BOTH-flank relative constraint range exceeds source")
    return RackFormAdmissionReport(
        "whole-point-envelope", relative, maxima["active_boundary_mm"],
        maxima["root_intrusion_mm"],
        receipt.global_datum_id, stations, tuple(mapping.feature_id for mapping in chain),
        height, width, controls["status_text"], usable_lower, receipt,
        controls["working_side_form_model_premise"], tuple(side_angle_bands),
    )


RACK_FLANK_INSPECTION_PROPERTY = "Rack Flank Inspection"


def rack_flank_inspection_callout_text() -> str:
    """Source-owned shop checks; whole-material proof stays off the print."""
    from paper_drive_geom import feed_rack_form_admission_controls

    controls = feed_rack_form_admission_controls()
    return "\n".join((
        f"CHECK FLANKS {PA_DEG:g} DEG +/-{controls['working_side_angle_deviation_deg']:g}; SAME WIRE/DIA",
        f"MEASURED SECANT DY >={controls['working_side_secant_minimum_height_mm']:g} MM; PAY BOTH XY READINGS",
        f"MIC/WIRE U +/-{controls['wire_measurement_uncertainty_mm']:g} MM; "
        f"INDICATOR U +/-{controls['indicator_measurement_uncertainty_mm']:g} MM",
    ))


GAP_AREA = (half_width(ROOT_Y) + half_width(BAR_HEIGHT)) * (BAR_HEIGHT - ROOT_Y)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length"},
    "Bar": {"BackerDepth"},
    "EndStockProfile": {"RackDepth", "RackHeight", "RackInset", "SeamHeight"},
    "OverallHeightReference": {"OverallHeight"},
}
DRAWING_PRECISION = {
    feature: {name: 2 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# Overall height is the backer plus the as-supplied strip, not another stock
# accuracy requirement competing with the purchased height reference.
DRAWING_REFERENCE_DIMENSIONS = frozenset(
    {"RackDepth", "RackHeight", "OverallHeight"}
)
DRAWING_NOMINALS_MM = {
    "Length": BAR_LENGTH,
    "BackerDepth": BAR_THICKNESS,
    "RackDepth": RACK_THICKNESS,
    "RackHeight": RACK_HEIGHT,
    "RackInset": RACK_Z0,
    "SeamHeight": BACKER_HEIGHT,
    "OverallHeight": BAR_HEIGHT,
}



# The purchase identity defines the teeth; no finite form-cutter alternative.
PURCHASED_RACK_NOTE = (
    f"PURCHASED RACK: {PURCHASED_RACK_SUPPLIER} {PURCHASED_RACK_SKU}; "
    f"{PURCHASED_RACK_LENGTH_IN:g} IN"
)
GEAR_DATA = (
    f"{PURCHASED_RACK_NOTE}; {DP:g} DP, {PA_DEG:g}\N{DEGREE SIGN} PA; "
    f"{PURCHASED_RACK_MATERIAL.upper()}"
)
INCOMING_RACK_INSPECTION_NOTE = (
    f"STOCK HEIGHT {quality.rack_stock_height_max_mm():g} MAX; "
    f"FACE WIDTH {quality.rack_face_width_max_mm():g} MAX; "
    f"ALL USABLE GAPS X-INDEX RANGE {quality.rack_pitch_index_deviation_mm():g} MAX; "
    f"ASSEMBLED RIGID FACE/AXIS LEAD {quality.rack_face_lead_deviation_mm():g} MAX; REJECT EXCESS"
)
DRAWING_NOTES = "\n".join(
    (
        "SOFT-SOLDERED RACK/BACKER JOINT; ENDS FLUSH",
        "END TOOTH PHASE NOT CONTROLLED; SET MESH AT ASSEMBLY",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
ENLARGED_END_VIEW_NOTE = "ENLARGED END VIEW SCALE 4:1"
