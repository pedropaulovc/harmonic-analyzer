"""Offline cross-check for the #151 mirror retirement: every re-authored
machine-handed placement, recomputed by importing the assembly modules
SolidWorks-free, is compared against the pre-sweep golden pose dump
(``cad/out/reports/pose-golden/``, captured with
``diagnostics/probe_pose_dump.py dump`` before the sweep).  The v2 post
installation intentionally re-anchors the cone/channel/frame families, so the
expected formulas below now describe the new machine frame; the documented
exceptions carry their own widened tolerances inline (lever-wire 2c artifact,
crank-family solver noise, chain-pattern fill drift).

The golden keys are archived role-local selectors, not current native Name2
identities. Shared-stock comparisons report their canonical file/member and
semantic reference explicitly; only a separate native readback can bridge them
to a rebuilt occurrence. This validator never rewrites the sealed pose dump.

Run: ``uv run python cad/scripts/diagnostics/check_mirror_retirement.py``
"""

# ruff: noqa: E402, E741, F541  (mid-file imports are inherent to the
# sys.path-then-import pattern; I is the incline angle)
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "cad" / "scripts"))
GOLD = REPO / "cad" / "out" / "reports" / "pose-golden"

import _telemetry  # status goes through telemetry, not bare print (AGENTS.md)
import spring_mount_geom
import _recording_geometry as paper_drive_geom

fails = []


def _status(ok: bool, line: str) -> None:
    (_telemetry.debug if ok else _telemetry.error)(line)


_ARCHIVE_MEMBERS = {
    "pd-vn-chain-inner-link": ("sh-vn-chain-link", "InnerLink", "InnerLink"),
    "pd-vn-chain-outer-link": ("sh-vn-chain-link", "OuterLink", "OuterLink"),
    "mg-vn-lever-wire": ("sh-vn-music-wire", "LeverWire", "LeverWire"),
    "pn-vn-pen-wire": ("sh-vn-music-wire", "PenWire", "PenWire"),
    "dt-vn-foot-screw": ("sh-vn-fillister-screw-90280a108", "Default", "FootScrew"),
    "dt-vn-swing-stop-screw": (
        "sh-vn-fillister-screw-90280a108", "Default", "SwingStopScrew"
    ),
}
_ARCHIVE_STOCK = {
    "dt-vn-fillister-screw": "sh-vn-brass-fillister-screw",
    "fr-vn-fillister-screw": "sh-vn-brass-fillister-screw",
    "pd-vn-fillister-screw": "sh-vn-brass-fillister-screw",
    "pd-vn-latch-hook-bracket-screw": "sh-vn-fillister-screw-90280a108",
    "mg-vn-clamp-screw": "sh-vn-clamp-screw",
    "pd-vn-clamp-screw": "sh-vn-clamp-screw",
    "ch-vn-arbor-set-screw": "sh-vn-arbor-set-screw",
    "dt-vn-arbor-set-screw": "sh-vn-arbor-set-screw",
    "mg-vn-thumb-screw": "sh-vn-thumb-screw",
    "ms-vn-thumb-screw": "sh-vn-thumb-screw",
}


def _archive_occurrence(component):
    """Describe an archived selector without claiming a rebuilt native index."""
    parent, separator, leaf = component.rpartition("/")
    stem, dash, ordinal = leaf.rpartition("-")
    if not dash or not ordinal.isdecimal() or int(ordinal) < 1:
        raise ValueError(f"invalid archived occurrence: {component!r}")
    member = _ARCHIVE_MEMBERS.get(stem)
    if member is not None:
        native_stem, configuration, role = member
        reference = f"{role}:{int(ordinal)}"
    else:
        native_stem, configuration = _ARCHIVE_STOCK.get(stem, stem), "Default"
        reference = None
    return {
        "namespace": "archive-role-local",
        "archiveSelector": component,
        "parent": parent if separator else "",
        "nativeStem": native_stem,
        "configuration": configuration,
        "semanticReference": reference,
    }


def _archive_member_key(stem, configuration, reference):
    """Project an exact current member/role into the sealed archive namespace."""
    role, separator, ordinal = reference.partition(":")
    if not separator or not ordinal.isdecimal() or int(ordinal) < 1:
        raise ValueError(f"invalid semantic reference: {reference!r}")
    matches = [
        archived_stem
        for archived_stem, identity in _ARCHIVE_MEMBERS.items()
        if identity == (stem, configuration, role)
    ]
    if len(matches) != 1:
        raise ValueError(f"ambiguous or missing archived member: {(stem, configuration, reference)!r}")
    return f"{matches[0]}-{int(ordinal)}"


def expect(asm, comp, pos, rows, label, pos_tol=1e-3, row_tol=1e-6):
    archived = _archive_occurrence(comp)
    _telemetry.debug(f"archived pose selector {archived!r}; no rebuilt Name2 claim")
    with (GOLD / f"{asm}.json").open(encoding="utf-8") as source:
        g = json.load(source)[archived["archiveSelector"]]
    gp = [v * 1000.0 for v in g[9:12]]
    gr = g[0:9]
    fr = [c for row in rows for c in row]
    dp = max(abs(a - b) for a, b in zip(gp, pos))
    dr = max(abs(a - b) for a, b in zip(gr, fr))
    ok = dp < pos_tol and dr < row_tol
    _status(ok, f"{'OK ' if ok else 'FAIL'} {label:45s} dpos={dp:.6f} drow={dr:.2e}")
    if not ok:
        fails.append((label, gp, pos, gr, fr))


from _transforms import (
    IDENTITY,
    ROT_Y_180,
    ROT_Y_POS90,
    ROT_X_NEG90,
    compose_rows,
    rot_z_rows,
)

# ---- summing --------------------------------------------------------------
import build_sm_summing_assembly as s

expect(
    "sm-summing",
    "sm-knife-mount-1",
    [s.KNIFE[0], s.KNIFE_CONTACT_Y, s.SUMMING_Z + s.HEX_Z_MID],
    IDENTITY,
    "knife-mount front",
)
expect(
    "sm-summing",
    "sm-knife-mount-2",
    [s.KNIFE[0], s.KNIFE_CONTACT_Y, s.SUMMING_Z - s.HEX_Z_MID],
    IDENTITY,
    "knife-mount back",
)
# Revised cut bolts, new SAE washers and dowel pairs are checked against
# actual assembly transforms by build_sm_summing_assembly's per-instance
# readbacks when rebuilt. This historical pose dump does not certify the
# revised hardware; only the unchanged knife-mount and lever poses share it.
expect(
    "sm-summing",
    "sm-summing-lever-1",
    [s.KNIFE[0], s.KNIFE[1], s.SUMMING_Z],
    IDENTITY,
    "sm-summing-lever",
)
expect("sm-summing", "sm-vn-boss-hook-1", list(s.BOSS_HOOK_POS), IDENTITY, "sm-vn-boss-hook")
expect(
    "sm-summing",
    "sm-vn-boss-hook-jam-nut-1",
    list(s.JAM_NUT_POS),
    s.JAM_NUT_ROWS,
    "sm-vn-boss-hook-jam-nut",
)
# The counter and gooseneck now seat on unchanged native supplier surfaces.
# Their analytical insertion seeds are not their final placements and cannot
# be compared against this historical static mirror-retirement pose dump.
# build_sm_summing_assembly certifies the native contacts and final pose ledger.
_telemetry.debug("SKIP static golden poses: counter-spring/gooseneck use native contact seats")

# ---- pen ------------------------------------------------------------------
import build_pn_pen_assembly as p

expect("pn-pen", "pn-pen-hanger-1", list(p.HANGER_POS), IDENTITY, "pn-pen-hanger")
expect("pn-pen", "pn-pen-rod-1", list(p.PEN_ROD_POS), IDENTITY, "pn-pen-rod")
for _stem, _pos, _rows in p.RIDERS:
    archived_key = (
        _archive_member_key(_stem, "PenWire", "PenWire:1")
        if _stem == "sh-vn-music-wire"
        else f"{_stem}-1"
    )
    expect("pn-pen", archived_key, list(_pos), _rows, _stem)
expect("pn-pen", "pn-vn-hanger-screw-1", list(p.HANGER_SCREW_POS), IDENTITY, "pn-vn-hanger-screw")
expect("pn-pen", "pn-vn-pen-hanger-nut-1", list(p.HANGER_NUT_POS), IDENTITY, "pn-vn-pen-hanger-nut")
expect(
    "pn-pen",
    "pn-vn-pen-hanger-jam-nut-1",
    list(p.HANGER_JAM_NUT_POS),
    IDENTITY,
    "pn-vn-pen-hanger-jam-nut",
)

# Each rider's placement euler (derived in the assembly) must reproduce its rows.
from _transforms import euler_from_rows, rows_from_euler

for _stem, _pos, _rows in p.RIDERS:
    fr = rows_from_euler(euler_from_rows(_rows))
    d = max(abs(a - b) for ra, rb in zip(fr, _rows) for a, b in zip(ra, rb))
    _status(d < 1e-9, f"{'OK ' if d < 1e-9 else 'FAIL'} {_stem} euler vs rows drow={d:.2e}")
    if d >= 1e-9:
        fails.append((f"{_stem} euler", fr, _rows))

# ---- magnifier ------------------------------------------------------------
import build_mg_magnifier_assembly as m

expect(
    "mg-magnifier",
    "mg-wheel-bar-1",
    [m.WHEEL_BAR_X0, m.WHEEL_BAR_Y, m.BAR_Z],
    IDENTITY,
    "mg-wheel-bar",
)
expect(
    "mg-magnifier",
    "sh-column-clamp-front-1",
    [m.COLUMN_X, m.WHEEL_BAR_Y, m.COLUMN_Z],
    ROT_Y_POS90,
    "sh-column-clamp-front",
)
expect(
    "mg-magnifier",
    "sh-column-clamp-back-1",
    [m.COLUMN_X, m.WHEEL_BAR_Y, m.COLUMN_Z],
    ROT_Y_POS90,
    "sh-column-clamp-back",
)
expect(
    "mg-magnifier",
    "mg-vn-clamp-screw-1",
    [m.CLAMP_SCREW_X[0], m.WHEEL_BAR_Y, m.BAR_FRONT_Z],
    IDENTITY,
    "mg-vn-clamp-screw-1",
)
expect(
    "mg-magnifier",
    "mg-vn-clamp-screw-2",
    [m.CLAMP_SCREW_X[1], m.WHEEL_BAR_Y, m.BAR_FRONT_Z],
    IDENTITY,
    "mg-vn-clamp-screw-2",
)
expect(
    "mg-magnifier",
    "mg-magnifying-lever-1",
    [m.LEVER_X0, m.LEVER_ROD_Y, m.LEVER_ROD_Z],
    ROT_Y_180,
    "mg-magnifying-lever",
)
expect(
    "mg-magnifier",
    "mg-magnifying-bracket-1",
    list(m.BRACKET_ORIGIN),
    IDENTITY,
    "mg-magnifying-bracket",
)
for index, position in enumerate(m.BRACKET_SCREW_POSITIONS, start=1):
    expect(
        "mg-magnifier",
        f"mg-vn-magnifying-bracket-screw-{index}",
        list(position),
        m.BRACKET_SCREW_ROWS,
        "mg-vn-magnifying-bracket-screw",
    )
expect(
    "mg-magnifier",
    "mg-magnifying-clamp-1",
    list(m.CLAMP_POS),
    IDENTITY,
    "mg-magnifying-clamp",
)
_rz = compose_rows(rot_z_rows(-90.0), ROT_Y_180)
expect(
    "mg-magnifier",
    "mg-vn-thumb-screw-1",
    [m.CLAMP_X, m.THUMB_SCREW_OUTER_FACE_Y, m.LEVER_ROD_Z],
    _rz,
    "mg-vn-thumb-screw",
)
expect(
    "mg-magnifier",
    "mg-magnifying-vertical-rod-1",
    [m.CLAMP_X, m.VROD_TOP_Y, m.VROD_Z],
    _rz,
    "vertical-rod",
)
expect(
    "mg-magnifier",
    "mg-output-fixture-1",
    list(m.FIXTURE_POSITION),
    m.FIXTURE_ROWS,
    "mg-output-fixture",
)
expect(
    "mg-magnifier",
    "mg-wheel-axle-1",
    [m.WHEEL_X, m.WHEEL_BAR_Y, m.BAR_FRONT_Z],
    ROT_X_NEG90,
    "mg-wheel-axle",
)
expect(
    "mg-magnifier",
    "mg-magnifying-wheel-1",
    [m.WHEEL_X, m.WHEEL_BAR_Y, m.WHEEL_MID_Z],
    IDENTITY,
    "mg-magnifying-wheel",
)
# lever-wire: ACCEPTED delta vs golden -- the old mirror realized this pose
# through the part's bbox-z-centre plane (2c artifact, 0.015 mm / 4e-5 rows);
# the new values are the exact authored intent. Documented; will show once in
# the post-rebuild pose diff.
expect(
    "mg-magnifier",
    "mg-vn-lever-wire-1",
    list(m.HUB_WIRE_END),
    m._HW_ROWS,
    "lever-wire (accepted 2c delta)",
    pos_tol=0.02,
    row_tol=5e-5,
)

# euler/rows agreement for the composed placements
d = max(
    abs(a - b)
    for ra, rb in zip(rows_from_euler([180.0, 0.0, -90.0]), _rz)
    for a, b in zip(ra, rb)
)
_status(
    d < 1e-9,
    f"{'OK ' if d < 1e-9 else 'FAIL'} thumb/vrod euler [180,0,-90] vs composed      drow={d:.2e}",
)
if d >= 1e-9:
    fails.append(("thumb euler", None, None))
d = max(
    abs(a - b)
    for ra, rb in zip(rows_from_euler([0.0, 180.0, 0.0]), ROT_Y_180)
    for a, b in zip(ra, rb)
)
_status(
    d < 1e-9,
    f"{'OK ' if d < 1e-9 else 'FAIL'} ROT_Y_180 euler [0,180,0]                     drow={d:.2e}",
)
if d >= 1e-9:
    fails.append(("ROT_Y_180 euler", None, None))

# ---- drive-train ------------------------------------------------------------
import build_dt_drive_train_assembly as d
import build_fr_harmonic_base as base


def eul(euler, rows, label):
    fr = rows_from_euler(euler)
    dd = max(abs(a - b) for ra, rb in zip(fr, rows) for a, b in zip(ra, rb))
    _status(
        dd < 1e-9, f"{'OK ' if dd < 1e-9 else 'FAIL'} euler {label:40s} drow={dd:.2e}"
    )
    if dd >= 1e-9:
        fails.append((f"euler {label}", euler, rows))


I = d.INCLINE_DEG
eul([0.0, I, 0.0], d.ROT_Y_INCLINE, "ROT_Y_INCLINE")
eul([90.0, I, 0.0], d.ROT_SHAFT_NORTH, "ROT_SHAFT_NORTH")
eul([-90.0, I, 0.0], d.ROT_SHAFT_SOUTH, "ROT_SHAFT_SOUTH")
eul(d.PINCH_WEST_EULER, d.ROT_PINCH_WEST, "PINCH_WEST")
eul(d.FPIN_EULER, d.FPIN_ROWS, "FPIN")
eul([180.0, 0.0, -90.0], compose_rows(d.rot_z_rows(-90.0), ROT_Y_180), "dt-crank-arm")
eul([90.0, 0.0, 0.0], d.ROT_X_POS90, "ROT_X_POS90")
eul([0.0, 90.0, 0.0], d.ROT_Y_POS90, "ROT_Y_POS90")

DT = "dt-drive-train"
expect(
    DT,
    "dt-cylinder-gear-shaft-1",
    [d.X_DRUM, d.Y_DRIVE, d.ARBOR_SOUTH_Z],
    d.ROT_X_POS90,
    "arbor (seed)",
)
expect(
    DT,
    "dt-arbor-pedestal-1",
    [d.X_DRUM, d.Y_BASE_TOP, -d.ARBOR_PEDESTAL_Z],
    IDENTITY,
    "arbor-pedestal south",
)
expect(
    DT,
    "dt-arbor-pedestal-2",
    [d.X_DRUM, d.Y_BASE_TOP, d.ARBOR_PEDESTAL_NORTH_Z],
    ROT_Y_180,
    "arbor-pedestal north",
)
_drive_pivot = d.cone_station(d.PIVOT_STATION)


def platform_station(station):
    """Drive-line station re-anchored from the base's authoritative pivot."""
    point = d.cone_station(station)
    return [
        base.PIVOT_SCREW_XZ[0] + point[0] - _drive_pivot[0],
        point[1],
        base.PIVOT_SCREW_XZ[1] + point[2] - _drive_pivot[2],
    ]


_ppv = platform_station(d.PIVOT_STATION)
_pps = platform_station(d.POST_STATION)
_ptp = platform_station(d.TIP_BLOCK_STATION)
_pcl = platform_station(d.COLLAR_STATION)
_pad = platform_station(d.ADJ_HEAD_STATION)
expect(
    DT,
    "dt-cone-swing-platform-1",
    [_ppv[0], d.Y_BASE_TOP, _ppv[2]],
    d.ROT_Y_INCLINE,
    "dt-cone-swing-platform",
)
expect(
    DT,
    "dt-cone-pivot-post-1",
    [_pps[0], d.Y_BASE_TOP + d.PLAT_T, _pps[2]],
    ROT_Y_180,
    "dt-cone-pivot-post",
)
expect(
    DT,
    "dt-cone-tip-block-1",
    [_ptp[0], d.Y_BASE_TOP + d.PLAT_T, _ptp[2]],
    d.ROT_Y_INCLINE,
    "dt-cone-tip-block",
)
expect(
    DT,
    "dt-vn-cone-tip-collar-1",
    [_pcl[0], d.Y_DRIVE, _pcl[2]],
    d.ROT_SHAFT_NORTH,
    "dt-vn-cone-tip-collar",
)
expect(
    DT,
    "dt-vn-cone-tip-adjuster-1",
    [_pad[0], d.Y_DRIVE, _pad[2]],
    d.ROT_SHAFT_SOUTH,
    "dt-vn-cone-tip-adjuster",
)
expect(
    DT,
    "dt-vn-cone-tip-block-screw-1",
    [
        _ptp[0] + d.PLAT_HOLDDOWN_LOCAL_X * d.COS_I,
        d.Y_BASE_TOP + d.PLAT_HOLDDOWN_CBORE_DEPTH,
        _ptp[2] - d.PLAT_HOLDDOWN_LOCAL_X * d.SIN_I,
    ],
    d.ROT_X_180,
    "dt-vn-cone-tip-block-screw",
)
expect(
    DT,
    "dt-vn-cone-tip-pinch-screw-1",
    [
        _ptp[0] + (d.TIP_BLOCK_X / 2.0) * d.COS_I,
        d.Y_BASE_TOP + d.PLAT_T + d.TIP_PINCH_Y,
        _ptp[2] - (d.TIP_BLOCK_X / 2.0) * d.SIN_I,
    ],
    d.ROT_PINCH_WEST,
    "dt-vn-cone-tip-pinch-screw",
)
expect(
    DT,
    "dt-vn-cone-lock-knob-1",
    [d.KNOB_X, d.Y_BASE_TOP + d.PLAT_T, d.KNOB_Z],
    IDENTITY,
    "dt-vn-cone-lock-knob",
)
expect(
    DT,
    "dt-vn-cone-pivot-screw-1",
    [
        base.PIVOT_SCREW_XZ[0],
        d.Y_BASE_TOP + d.PSCREW_SHOULDER_LEN,
        base.PIVOT_SCREW_XZ[1],
    ],
    IDENTITY,
    "dt-vn-cone-pivot-screw",
)
expect(
    DT,
    "dt-vn-swing-stop-screw-1",
    [base.STOP_SCREW_XZ[0], d.Y_BASE_TOP, base.STOP_SCREW_XZ[1]],
    IDENTITY,
    "dt-vn-swing-stop-screw",
)
expect(
    DT,
    "dt-alignment-pinion-1",
    [d.APINION_X, d.APINION_Y, d.APINION_Z_FRONT],
    IDENTITY,
    "dt-alignment-pinion",
)
_strap = compose_rows(ROT_Y_180, d.rot_z_rows(d.STRAP_LEAN_DEG))
expect(
    DT,
    "dt-pinion-bracket-1",
    [d.PIVOT_X, d.PIVOT_Y, d.RIG.STRAP_Z_INNER[0]],
    _strap,
    "pinion-bracket front",
)
expect(
    DT,
    "dt-pinion-bracket-2",
    [d.PIVOT_X, d.PIVOT_Y, d.RIG.STRAP_Z_OUTER[1]],
    _strap,
    "pinion-bracket back",
)
expect(
    DT,
    "dt-pinion-pivot-block-1",
    [d.BLOCK_X, d.PIVOT_Y, d.BLOCK_FRONT_Z0 + d.BLOCK_DEPTH],
    ROT_Y_180,
    "pinion-pivot-block front",
)
expect(
    DT,
    "dt-pinion-pivot-block-2",
    [d.BLOCK_X, d.PIVOT_Y, d.BLOCK_BACK_Z0 + d.BLOCK_DEPTH],
    ROT_Y_180,
    "pinion-pivot-block back",
)
expect(
    DT,
    "dt-pinion-pivot-shaft-1",
    [d.PIVOT_X, d.PIVOT_Y, d.PIVOT_SHAFT_Z0],
    # E-a (1c4bea6ac): the torque shaft turns with the strap lean so its
    # cross holes line up with the strap pins.
    d.TORQUE_SHAFT_ROWS,
    "dt-pinion-pivot-shaft",
)
expect(
    DT,
    "dt-pinion-lift-rod-1",
    [d.LIFT_X, d.LIFT_Y, d.LIFT_ROD_Z0],
    d.LIFT_ROD_ROWS,
    "dt-pinion-lift-rod",
)
expect(
    DT,
    "dt-pinion-spring-1",
    [d.SPRING_X, d.Y_BASE_TOP, d.SPRING_Z],
    ROT_Y_180,
    "dt-pinion-spring",
)
expect(
    DT,
    "dt-pinion-cam-pin-1",
    [d._FPIN_ORG[0], d._FPIN_ORG[1], d._STRAP_MID_Z[0]],
    d.FPIN_ROWS,
    "pinion-cam-pin front",
)
expect(
    DT,
    "dt-pinion-cam-pin-2",
    [d._FPIN_ORG[0], d._FPIN_ORG[1], d._STRAP_MID_Z[1]],
    d.FPIN_ROWS,
    "pinion-cam-pin back",
)
expect(
    DT, "dt-pinion-cam-1", [d.LIFT_X, d.LIFT_Y, d.CAM_Z0[0]], d.PINION_CAM_ROWS, "pinion-cam front"
)
expect(
    DT, "dt-pinion-cam-2", [d.LIFT_X, d.LIFT_Y, d.CAM_Z0[1]], d.PINION_CAM_ROWS, "pinion-cam back"
)
expect(
    DT,
    "dt-pinion-lever-1",
    [d.LIFT_X, d.LIFT_Y, d.LEVER_Z],
    d.LEVER_ROWS,
    "dt-pinion-lever",
)
expect(
    DT,
    "dt-pinion-handle-1",
    [d.APINION_X, d.APINION_Y, d.HANDLE_Z],
    d.HANDLE_ROWS,
    "dt-pinion-handle",
)
expect(
    DT,
    "dt-pinion-arbor-1",
    [d.APINION_X, d.APINION_Y, d.ARBOR_Z0],
    d.ARBOR_ROWS,
    "dt-pinion-arbor",
)
for k, (sx, sz) in enumerate(d._BLOCK_SCREW_XZ):
    expect(
        DT,
        f"dt-vn-slotted-screw-{k + 1}",
        [sx, d.BLOCK_TOP_Y, sz],
        IDENTITY,
        f"slotted-screw {k}",
    )
for k, (sx, sz) in enumerate(d._FOOT_SCREW_XZ):
    expect(
        DT,
        f"dt-vn-foot-screw-{k + 1}",
        [sx, d.Y_BASE_TOP + d.SPRING_T, sz],
        IDENTITY,
        f"foot-screw {k}",
    )
for k, (sx, sz) in enumerate(d._PEDESTAL_SCREW_XZ):
    expect(
        DT,
        f"dt-vn-pedestal-hold-down-screw-{k + 1}",
        [sx, d.Y_BASE_TOP + d.ARBOR_PED_FLANGE_T, sz],
        IDENTITY,
        f"pedestal-hold-down-screw {k}",
    )
expect(
    DT,
    "dt-cone-gear-shaft-1",
    platform_station(d.SHAFT_FRONT_STATION),
    d.ROT_Y_INCLINE,
    "dt-cone-gear-shaft",
)


def on_shaft(station, face):
    c = platform_station(station)
    return [c[0] - (face / 2.0) * d.SIN_I, d.Y_DRIVE, c[2] - (face / 2.0) * d.COS_I]


expect(
    DT,
    "dt-crank-drive-gear-1",
    on_shaft(d.GEAR64_CENTRE_STATION, d.GEAR64_FACE),
    d.ROT_Y_INCLINE,
    "crank-drive-gear 64T",
)
for j in range(20):
    expect(
        DT,
        f"dt-cone-gear-{j + 1}",
        # BDT: seed at the shifted T120 station, grown from the south face.
        on_shaft(
            d.SHAFT_T120_STATION
            + d.GEAR_AXIS_SHIFT
            + (d.CONE_FACE_STATION_REFERENCE - d.CONE_FACE) / 2.0
            + j * d.SEAT_PITCH,
            d.CONE_FACE,
        ),
        d.ROT_Y_INCLINE,
        f"cone-gear j={j}",
    )
cylinder_rows = compose_rows(ROT_Y_180, d.rot_z_rows(-1.5))
for j in range(20):
    expect(
        DT,
        f"dt-cylinder-gear-{j + 1}",
        [d.X_DRUM, d.Y_DRIVE, d.Z_DRUM0 + d.Z_PITCH * j + d.DRUM_FACE / 2.0],
        cylinder_rows,
        f"cylinder-gear j={j}",
    )
# The crank family is a fully mated keyed chain: the golden dump records its
# SOLVED pose, which sits ~1.2 um / 3.9e-7 rows off the insert intent (mate
# solver epsilon). Compare with a solver-noise allowance. The family rides the
# restored fixed crank axis (X_CRANK, Y_CRANK).
_SOLVED = dict(pos_tol=0.005, row_tol=1e-6)
expect(
    DT,
    "dt-crankshaft-1",
    [d.X_CRANK, d.Y_CRANK, d.CRANKSHAFT_Z0],
    d.ROT_X_POS90,
    "dt-crankshaft",
    **_SOLVED,
)
expect(
    DT,
    "dt-crank-hub-1",
    [d.X_CRANK, d.Y_CRANK, d.CRANK_HUB_Z0],
    d.ROT_X_POS90,
    "dt-crank-hub",
    **_SOLVED,
)
expect(
    DT,
    "dt-vn-crank-hub-pin-1",
    d.CRANK_HUB_PIN_ORIGIN,
    d.CRANK_HUB_PIN_ROWS,
    "dt-vn-crank-hub-pin",
    **_SOLVED,
)
expect(
    DT,
    "dt-crank-pinion-1",
    [d.X_CRANK, d.Y_CRANK, d.PINION_TOOTH_Z - d.PINION_FACE / 2.0],
    d.rot_z_rows(-d.PINION_SEED_DEG),
    "crank-pinion 16T",
    **_SOLVED,
)
expect(
    DT,
    "dt-crank-arm-1",
    [d.X_CRANK, d.Y_CRANK, d.CRANK_ARM_ORIGIN_Z],
    compose_rows(d.rot_z_rows(-90.0), ROT_Y_180),
    "dt-crank-arm",
    **_SOLVED,
)
expect(
    DT,
    "dt-crank-handle-1",
    [d.X_CRANK, d.Y_CRANK - d.ARM_C2C, d.CRANK_ARM_Z0],
    d.ROT_Y_POS90,
    "dt-crank-handle",
    **_SOLVED,
)

# ---- channel ---------------------------------------------------------------
import math
import build_ch_channel_assembly as c
import channel_kinematics

_rz = getattr(c, "rot_z_rows", None) or (
    lambda deg: [
        [math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0],
        [-math.sin(math.radians(deg)), math.cos(math.radians(deg)), 0.0],
        [0.0, 0.0, 1.0],
    ]
)
CH = "ch-channel"
amplitudes = __import__("_config").amplitudes()
st0 = channel_kinematics.solve_state(0.0)
arm_rows = compose_rows(_rz(st0["arm_tilt"]), ROT_Y_180)
rod_rows = compose_rows(_rz(st0["rod_tilt"]), ROT_Y_180)
_t = math.radians(st0["arm_tilt"])
arm_dx = c.ARM_PIVOT_LOCAL_Y * math.sin(_t)
arm_dy = c.ARM_PIVOT_LOCAL_Y * math.cos(_t)
expect(
    CH,
    "ch-pivot-shaft-1",
    [c.PIVOT[0], c.PIVOT[1], c.PIVOT_SHAFT_Z],
    IDENTITY,
    "ch-pivot-shaft",
)
expect(
    CH,
    "ch-fulcrum-shaft-1",
    [c.FULCRUM[0], c.FULCRUM[1], c.FULCRUM_SHAFT_Z],
    IDENTITY,
    "ch-fulcrum-shaft",
)
# The feet run outboard (2026-10-09): the south bracket turns Ry180.
expect(
    CH,
    "ch-pivot-bracket-1",
    [c.PIVOT[0], c.SUPPORT_APEX_Y, c._bracket_sides.MOUNT_Z["S"]],
    ROT_Y_180,
    "pivot-bracket rocker south",
)
expect(
    CH,
    "ch-pivot-bracket-2",
    [c.PIVOT[0], c.SUPPORT_APEX_Y, c._bracket_sides.MOUNT_Z["N"]],
    IDENTITY,
    "pivot-bracket rocker north",
)
expect(
    CH,
    "ch-fulcrum-keeper-1",
    [c.FULCRUM[0], c.RAIL_TOP_Y, c.FULCRUM_SHAFT_Z + c.KEEPER_Z_OFF],
    [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]],
    "fulcrum keeper +z (rear)",
)
expect(
    CH,
    "ch-fulcrum-keeper-2",
    [c.FULCRUM[0], c.RAIL_TOP_Y, c.FULCRUM_SHAFT_Z - c.KEEPER_Z_OFF],
    [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]],
    "fulcrum keeper -z (front)",
)
expect(
    CH,
    "ch-vn-frame-side-screw-1",
    [
        c.FULCRUM[0],
        c.RAIL_TOP_Y + c.KEEPER_SCREW_SEAT_H,
        c.FULCRUM_SHAFT_Z + c.KEEPER_SCREW_Z_OFF,
    ],
    IDENTITY,
    "keeper foot screw +z",
)
expect(
    CH,
    "ch-vn-frame-side-screw-2",
    [
        c.FULCRUM[0],
        c.RAIL_TOP_Y + c.KEEPER_SCREW_SEAT_H,
        c.FULCRUM_SHAFT_Z - c.KEEPER_SCREW_Z_OFF,
    ],
    IDENTITY,
    "keeper foot screw -z",
)
expect(
    CH,
    "ch-vn-fulcrum-set-screw-1",
    [c.FULCRUM[0], c.SET_SCREW_SEAT_Y, c.FULCRUM_SHAFT_Z + c.KEEPER_Z_OFF],
    IDENTITY,
    "keeper set screw +z",
)
expect(
    CH,
    "ch-vn-fulcrum-set-screw-2",
    [c.FULCRUM[0], c.SET_SCREW_SEAT_Y, c.FULCRUM_SHAFT_Z - c.KEEPER_Z_OFF],
    IDENTITY,
    "keeper set screw -z",
)
_SOLV = dict(pos_tol=0.005, row_tol=1e-5)
for j in range(1, 20):
    z_gap = c.z_station(j) + c.ARM_MID_DZ - c.PITCH / 2.0
    expect(
        CH,
        f"pivot-bushing-{j}",
        [c.PIVOT[0], c.PIVOT[1], z_gap],
        IDENTITY,
        f"pivot-bushing gap {j - 1}",
        **_SOLV,
    )
    expect(
        CH,
        f"lever-bushing-{j}",
        [c.FULCRUM[0], c.FULCRUM[1], z_gap],
        IDENTITY,
        f"lever-bushing gap {j - 1}",
        **_SOLV,
    )
# Channel springs also use native-seated poses, not their analytical seeds.
# build_ch_channel_assembly certifies their contacts and actual mount clearances.
_telemetry.debug("SKIP static golden poses: channel-spring-installed uses native contact seats")
for j in range(20):
    zj = c.z_station(j)
    z_mid = zj + c.ARM_MID_DZ
    st = channel_kinematics.solve_state(amplitudes[j])
    expect(
        CH,
        f"ch-rocker-arm-{j + 1}",
        [c.PIVOT[0] - arm_dx, c.PIVOT[1] - arm_dy, z_mid],
        arm_rows,
        f"rocker-arm ch{j:02d}",
        **_SOLV,
    )
    expect(
        CH,
        f"ch-connecting-rod-{j + 1}",
        [c.RING_CENTER[0], c.RING_CENTER[1], zj + c.CAM_DZ],
        rod_rows,
        f"connecting-rod ch{j:02d}",
        **_SOLV,
    )
    expect(
        CH,
        f"ch-amplitude-bar-{j + 1}",
        [st["bar_origin_x"], st["bar_origin_y"], z_mid - c.BAR_WIDTH / 2.0],
        rows_from_euler([st["bar_tilt"], -90.0, 0.0]),
        f"amplitude-bar ch{j:02d}",
        **_SOLV,
    )
    expect(
        CH,
        f"ch-channel-lever-{j + 1}",
        [c.FULCRUM[0], c.FULCRUM[1], z_mid],
        compose_rows(_rz(st["lever_tilt"]), ROT_Y_180),
        f"channel-lever ch{j:02d}",
        **_SOLV,
    )
    expect(
        CH,
        f"ch-vn-spring-hook-{j + 1}",
        [*spring_mount_geom.CHANNEL_ANCHOR_XY, z_mid],
        IDENTITY,
        f"spring-hook ch{j:02d}",
    )
    expect(
        CH,
        f"ch-anchor-jam-nut-{j + 1}",
        [*c.CHANNEL_ANCHOR_NUT_XY, z_mid],
        c.CHANNEL_ANCHOR_NUT_ROWS,
        f"spring-hook jam nut ch{j:02d}",
    )

# ---- paper-drive -------------------------------------------------------------
import build_pd_paper_drive_assembly as p

# The module's own SolidWorks-free layout asserts (rack phase, gear mesh,
# knob clearance, chain anchors) double as the offline smoke test.
p._assert_rack_mesh()
p._assert_gear_mesh()
p._assert_knob_shaft_clearance()
p._assert_chain_layout()
_telemetry.debug("OK  paper-drive module layout asserts")

PD = "pd-paper-drive"
# The sealed golden dump predates the 1.010 bar (owner ruling 2026-11-01, B2):
# its bar centred on the clamp line, which the shortened bar keeps (CLAMP_Y).
expect(PD, "pd-support-bar-1", [0.0, p.CLAMP_Y, p.BAR_Z], IDENTITY, "pd-support-bar")
for i, sx in enumerate((1.0, -1.0)):
    expect(
        PD,
        f"sh-column-clamp-front-{i + 1}",
        [sx * p.COLUMN_X, p.CLAMP_Y, p.COLUMN_Z],
        p.ROT_Y_POS90,
        f"column-clamp-front x{sx * p.COLUMN_X:+.0f}",
    )
    expect(
        PD,
        f"sh-column-clamp-back-{i + 1}",
        [sx * p.COLUMN_X, p.CLAMP_Y, p.COLUMN_Z],
        p.ROT_Y_POS90,
        f"column-clamp-back x{sx * p.COLUMN_X:+.0f}",
    )
for i, x in enumerate(p.CLAMP_HOLE_X):
    expect(
        PD,
        f"mg-vn-clamp-screw-{i + 1}",
        [-x, p.CLAMP_Y, p.BAR_FRONT_Z],
        IDENTITY,
        f"clamp-screw x{-x:+.1f}",
    )
expect(
    PD,
    "pd-platen-1",
    [p.PLATE_X0, p.PLATE_Y0, p.PLATE_FRONT_Z],
    IDENTITY,
    "pd-platen",
    **_SOLV,
)
expect(
    PD,
    "pd-platen-rack-1",
    [p.RACK_X0, p.RACK_Y0, p.RACK_BACK_Z],
    p.ROT_X_180,
    "pd-platen-rack",
    **_SOLV,
)
for i, gy in enumerate(p.GUIDE_Y):
    expect(
        PD,
        f"pd-platen-guide-{i + 1}",
        [p.PLATE_X0 + p.GUIDE_LENGTH, gy, p.BAR_FRONT_Z],
        p.ROT_Y_180,
        f"platen-guide y{gy:.0f}",
        **_SOLV,
    )
# The sealed golden dump predates the 22.5 x 9.8 plate on a 1.2 lip (PR #1897):
# x stays the hole pattern on the station (station ± 11, unchanged), y the
# rail edges the dump recorded; the current placement is the assembly's
# LOCK_PLATE_Y, proved by its own native build.
for i, x_c in enumerate(p.LOCK_STATION_X):
    station = p.PLATE_X0 + p.PLATE_WIDTH - x_c
    expect(
        PD,
        f"pd-guide-lock-{2 * i + 1}",
        [station + p.LOCK_HOLE_PATTERN_X, p.GUIDE_Y[1] + p.GUIDE_HEIGHT, p.LOCK_Z0],
        _rz(180.0),
        f"guide-lock top x{x_c:.0f}",
        **_SOLV,
    )
    expect(
        PD,
        f"pd-guide-lock-{2 * i + 2}",
        [station - p.LOCK_HOLE_PATTERN_X, p.GUIDE_Y[0], p.LOCK_Z0],
        IDENTITY,
        f"guide-lock bottom x{x_c:.0f}",
        **_SOLV,
    )
for i, (_sx, clip_x, clip_y, rz) in enumerate(p.CLIP_PLACEMENTS):
    expect(
        PD,
        f"pd-platen-clip-{i + 1}",
        [clip_x, clip_y, p.PLATE_FRONT_Z - p.CLIP_THICKNESS],
        _rz(rz),
        f"platen-clip x{clip_x:+.0f} Rz{rz:+.0f}",
        **_SOLV,
    )
_paper_side = paper_drive_geom.RECORDING_PAPER_LEFT_INSET_MM
_paper_y = p.PLATE_Y0 + p.PLATE_HEIGHT - paper_drive_geom.RECORDING_PAPER_HEIGHT_MM - 3.0
expect(
    PD,
    "pd-platen-paper-1",
    [p.PLATE_X0 + _paper_side, _paper_y, p.PLATE_FRONT_Z - 0.5],
    IDENTITY,
    "pd-platen-paper",
    **_SOLV,
)
# The MHA-PD-VN-65 #2-56 clip screws are their own stem; the MHA-DT-VN-50 guide
# screws number from 1 on their own.
for i, (x, y) in enumerate(p.CLIP_SCREW_XY):
    expect(
        PD,
        f"pd-vn-platen-clip-screw-{i + 1}",
        [x, y, p.PLATE_FRONT_Z - p.CLIP_THICKNESS],
        IDENTITY,
        f"clip screw {i + 1}",
        **_SOLV,
    )
for i, (x, y) in enumerate(p.GUIDE_SCREW_XY):
    expect(
        PD,
        f"dt-vn-fillister-screw-{i + 1}",
        [x, y, p.PLATE_FRONT_Z + p.PLATEN_CBORE_DEPTH],
        IDENTITY,
        f"guide screw {i + 1}",
        **_SOLV,
    )
# R9-31: the guide-lock screws are their own slotted pan-head stem (MHA-PD-VN-60).
for i, (x, y) in enumerate(p.LOCK_SCREW_XY):
    expect(
        PD,
        f"pd-vn-guide-lock-screw-{i + 1}",
        [x, y, p.LOCK_Z0 + p.LOCK_THICK],
        p.ROT_Y_180,
        f"lock screw {i + 1}",
        **_SOLV,
    )
# Hanger: the arm swings on the pivot P at theta; the plate carries the knob K.
_P = [p.PIVOT_XY[0], p.PIVOT_XY[1]]
_arm_rows = p.rot_z_rows(p.ARM_ANGLE_DEG)
expect(PD, "pd-transgear-pivot-spacer-1", [*_P, p.SPACER_Z0], IDENTITY, "pivot spacer")
expect(PD, "pd-transgear-arm-1", [*_P, p.ARM_Z0], _arm_rows, "pd-transgear-arm")
expect(
    PD,
    "pd-vn-transgear-pivot-screw-1",
    [*_P, p.PIVOT_SCREW_Z0],
    p.ROT_X_POS90,
    "pivot screw",
)
expect(
    PD, "pd-vn-transgear-pivot-spring-1", [*_P, p.PIVOT_SPRING_Z0], IDENTITY, "pivot spring"
)
_K = [p.KNOB_SHAFT_XY[0], p.KNOB_SHAFT_XY[1]]
expect(PD, "pd-transgear-arm-plate-1", [*_K, p.PLATE_Z0], _arm_rows, "arm plate")
for i, (x, y) in enumerate(p.PLATE_SCREW_XY):
    expect(
        PD,
        f"pd-vn-transgear-arm-plate-screw-{i + 1}",
        [x, y, p.PLATE_SCREW_Z0],
        p.ROT_X_POS90,
        f"arm plate screw {i + 1}",
    )
expect(
    PD,
    "pd-vn-transgear-latch-pin-1",
    list(p.LATCH_PIN_POS),
    p.rot_z_rows(p.ARM_ANGLE_DEG - 90.0),
    "latch pin",
)
# Latch hook by translation, its screws through its base into the bar.
expect(PD, "pd-latch-hook-1", list(p.LATCH_HOOK_POS), IDENTITY, "latch hook")
for i, pos in enumerate(p.HOOK_BRACKET_SCREW_POS):
    expect(
        PD,
        f"pd-vn-latch-hook-bracket-screw-{i + 1}",
        list(pos),
        p.ROT_X_POS90,
        f"latch-hook screw {i + 1}",
    )
# Disc cluster on the MHA-PD-23 pin at S: pin and both bushings Ry(180), the
# MHA-PD-VN-61 ring in the pin's groove.
_S = [p.STUD_XY[0], p.STUD_XY[1]]
expect(PD, "pd-transgear-pin-1", [*_S, p.PIN_Z0], p.ROT_Y_180, "pd-transgear-pin")
expect(
    PD,
    "pd-transgear-rear-bushing-1",
    [*_S, p.REAR_BUSHING_Z0],
    p.ROT_Y_180,
    "rear bushing",
)
expect(
    PD,
    "pd-transgear-feed-pinion-1",
    [*_S, p.FEED_Z0],
    p.ROT_Y_180,
    "feed pinion",
    **_SOLV,
)
expect(PD, "pd-rack-pinion-1", [*_S, p.DISC_Z0], IDENTITY, "rack-pinion disc", **_SOLV)
expect(PD, "pd-transgear-disc-hub-1", [*_S, p.DISC_Z0], IDENTITY, "disc hub", **_SOLV)
for i, (x, y) in enumerate(p.DISC_SCREW_XY):
    expect(
        PD,
        f"pd-vn-transgear-disc-screw-{i + 1}",
        [x, y, p.DISC_SCREW_Z0],
        p.ROT_X_NEG90,
        f"disc screw {i + 1}",
        **_SOLV,
    )
expect(
    PD,
    "pd-transgear-front-bushing-1",
    [*_S, p.FRONT_BUSHING_Z0],
    p.ROT_Y_180,
    "front bushing",
)
expect(
    PD,
    "pd-vn-transgear-retaining-ring-1",
    [*_S, p.CLUSTER.RING_REAR_Z],
    p.ROT_Y_180,
    "retaining ring",
)
# Knob stack at K: the T24 is inserted first (-1), then the crank T12 and the
# T18 spare.
expect(
    PD,
    "pd-transgear-removable-1",
    [*_K, p.REMOVABLE_Z0],
    IDENTITY,
    "removable T24",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-drive-collar-1",
    [*_K, p.KNOB_COLLAR_Z0],
    IDENTITY,
    "drive collar",
    **_SOLV,
)
for i, (x, y) in enumerate(p.KNOB_DRIVE_PIN_XY):
    expect(
        PD,
        f"pd-vn-transgear-knob-drive-pin-{i + 1}",
        [x, y, p.KNOB_DRIVE_PIN_Z0],
        p.ROT_X_NEG90,
        f"knob drive pin {i + 1}",
        **_SOLV,
    )
expect(
    PD,
    "pd-transgear-knob-shaft-1",
    [*_K, p.KNOB_SHAFT_Z0],
    p.rot_z_rows(p.THIRD_PHASE_DEG),
    "knob shaft",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-thumbnut-1",
    [*_K, p.THUMBNUT_Z0],
    p.ROT_X_NEG90,
    "thumbnut",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-knob-thrust-ring-1",
    [*_K, p.KNOB_RING_Z0],
    p.ROT_X_POS90,
    "knob thrust ring",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-knob-cup-1",
    [*_K, p.KNOB_CUP_Z0],
    p.ROT_X_POS90,
    "knob cup",
    **_SOLV,
)
expect(
    PD,
    "pd-vn-transgear-knob-cup-pin-1",
    [*_K, p.KNOB_CUP_PIN_Z0],
    IDENTITY,
    "knob cup pin",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-removable-2",
    [-p.CHAIN_CRANK_CENTRE[0], p.CHAIN_CRANK_CENTRE[1], p.REMOVABLE_Z0],
    IDENTITY,
    "removable T12 (crank)",
    **_SOLV,
)
expect(
    PD,
    "pd-transgear-removable-3",
    list(p.SPARE_GEAR_POS),
    p.ROT_X_NEG90,
    "removable T18 spare",
)

# Chain links: every link should sit near the mirrored loop at its station,
# oriented along the forward chord (inner = even stations, outer = odd).
# The pattern's own fill drifts up to ~0.51 mm along-path from this ideal
# chord model (the build itself gates links at <= 2.0 mm off the centreline),
# so the tolerance here is coarse -- it still catches any chirality error,
# which would be a ~250 mm x flip.
from _chain import LINK_PITCH, loop_point_tangent


def _link_expect(name, station, label):
    x0, y0, _ = loop_point_tangent(
        station * LINK_PITCH,
        dx=p.CHAIN_KNOB_CENTRE[0],
        dy=p.CHAIN_KNOB_CENTRE[1],
        mirror_x=True,
    )
    x1, y1, _ = loop_point_tangent(
        (station + 1) * LINK_PITCH,
        dx=p.CHAIN_KNOB_CENTRE[0],
        dy=p.CHAIN_KNOB_CENTRE[1],
        mirror_x=True,
    )
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    expect(
        PD, name, [x0, y0, p.CHAIN_MID_Z], _rz(ang), label, pos_tol=0.75, row_tol=0.05
    )


_link_ok = True
try:
    _link_expect("pd-vn-chain-inner-link-1", 0, "chain seed inner @0")
    _link_expect("pd-vn-chain-outer-link-1", 1, "chain seed outer @1")
except Exception as e:
    _telemetry.error(f"chain seed check errored: {e}")
    fails.append(("chain seed lookup", repr(e)))
    _link_ok = False
if _link_ok and not fails:
    # The pattern fills stations 2..65; the closing inner link and the
    # connecting link are seated at 66 and 67.
    for k in range(1, p.LINK_COUNT // 2):
        _link_expect(f"pd-vn-chain-inner-link-{k + 1}", 2 * k, f"chain inner @{2 * k}")
    for k in range(1, p.LINK_COUNT // 2 - 1):
        _link_expect(
            f"pd-vn-chain-outer-link-{k + 1}", 2 * k + 1, f"chain outer @{2 * k + 1}"
        )
    closing = p.LINK_COUNT - 1
    _link_expect("pd-vn-chain-connecting-link-1", closing, f"chain connecting @{closing}")

if fails:
    for f in fails:
        _telemetry.error(f"FAIL DETAIL: {f}")
    sys.exit(1)
_telemetry.success("ALL CHECKS PASSED")
