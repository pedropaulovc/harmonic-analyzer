"""Threaded-joint operational retention: the joint table and its audit.

drawing-simplicity-policy.md rule 9 (operational retention): every threaded
support or fastener exposed to a rotating member's drag, torque reversal or
loss of preload has a mechanical anti-loosening means, installed by a stated
assembly step. A plain seated thread, shoulder, shim or threadlocker alone is
not one, and a cap that retains a cluster axially does not lock a different
interface.

``JOINTS`` holds one row per threaded joint of every assembly in
``_buildgraph.ASSEMBLY_ORDER`` (identical pattern instances share a row and
carry their ``quantity``). Each part an assembly references is classified as
threaded or not (``THREADED_PARTS`` / ``UNTHREADED_PARTS``), so the joint list
is checked against the build's own component enumeration
(``_buildgraph.references_of``): a part added to an assembly fails coverage
until it is classified, and a threaded part fails until a row names it.
``REQUIRED_JOINTS`` registers every joint with its source occurrence, and the
table must match it exactly, so a row deleted while other rows still name its
parts is still caught. A threaded joint replaced by a pinned one keeps a row,
its lock the pin (paper-drive/knob-cup-on-journal, R9-70).

``audit`` is pure. ``main`` writes ``cad/out/reports/joint-retention.json``
and a readable summary beside it; under ``ENFORCEMENT = Enforcement.AUDIT`` it
always exits 0, under ``Enforcement.GATE`` a finding fails the doit check
(``check:joint_retention``). SolidWorks-free.
"""

from __future__ import annotations

import functools
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum

import _buildgraph
import _config
import ch_channel_assembly_steps
import dt_drive_train_steps
import pd_paper_drive_assembly_steps


class Enforcement(StrEnum):
    AUDIT = "audit"  # report every finding, never fail the check
    GATE = "gate"  # any finding fails check:joint_retention


# The one switch: flip to Enforcement.GATE once the reported joints are fixed.
ENFORCEMENT = Enforcement.AUDIT


class Exposure(StrEnum):
    """What operating load reaches the joint about its thread axis."""

    # Clamps parts that never move relative to each other in operation; no
    # operating torque acts about the screw axis. The row's exposure_reason
    # must say why.
    STATIC_CLAMP = "static_clamp"
    # A fixed thread carries, or sits in the drag path of, a member that
    # rotates continuously in one sense.
    ROTATING_DRAG = "rotating_drag"
    # The thread carries or drives a member that rocks, oscillates or
    # reverses, so the torque on it reverses.
    OSCILLATING = "oscillating"
    # The thread's own rotation sets a position, gap or preload.
    ADJUSTER = "adjuster"
    # Not yet classified from the CAD; always a finding.
    UNCLASSIFIED = "unclassified"


EXPOSED = frozenset({Exposure.ROTATING_DRAG, Exposure.OSCILLATING, Exposure.ADJUSTER})


class Lock(StrEnum):
    """The anti-rotation / anti-unscrewing means, separate from axial capture."""

    JAM_NUT = "jam_nut"
    LOCKED_NUT = "locked_nut"  # a nut positively locked by a pin, tab or wire
    CROSS_PIN = "cross_pin"
    KEYED = "keyed"  # keyed or flatted anti-rotation, with axial capture
    STAKED = "staked"
    PEENED = "peened"
    PINCH_CLAMP = "pinch_clamp"  # a pinch screw closes a slit across the thread
    CAPTIVE_BY_GEOMETRY = "captive_by_geometry"  # modelled geometry stops rotation
    THREADLOCKER_ONLY = "threadlocker_only"
    NONE = "none"


NOT_A_LOCK = frozenset({Lock.NONE, Lock.THREADLOCKER_ONLY})

# Stands in for a member or receiver the drawings call for but no assembly
# places (no part stem exists); the audit always reports it.
UNMODELLED = "<unmodelled>"


@dataclass(frozen=True)
class Joint:
    """One threaded joint (or one set of identical pattern instances).

    Part names are ``_buildgraph`` stems (underscored). ``installed_at`` and
    ``lock_step`` are step keys where the assembly has a keyed step list
    (``STEP_LISTS``), otherwise the printed step reference, or "" where no
    step installs it. ``lock_part`` is the locking component's stem, or
    ``"<stem>:<feature>"`` for a modelled feature of the member or receiver;
    ``lock_binds`` names the two parts whose relative rotation the lock
    stops, which must be this joint's member and receiver. A locking part is
    not itself covered by naming it here: threaded lock hardware needs its own
    row. ``member`` or ``receiver`` is ``UNMODELLED`` where the hardware is
    called for but not modelled. ``quantity`` counts instances per machine,
    or per built channel where ``per_channel`` is set (the build places one
    for each of ``_config.active_count()`` channels). ``exception`` is a
    ``RULINGS`` key; only a user ruling creates one, and it waives only the
    joint it names.
    """

    id: str
    assembly: str
    member: str
    receiver: str
    thread: str
    installed_at: str
    exposure: Exposure
    exposure_reason: str
    axial_capture: str
    lock: Lock
    evidence: str
    quantity: int = 1
    lock_part: str = ""
    lock_binds: tuple[str, ...] = ()
    lock_step: str = ""
    exception: str = ""
    per_channel: bool = False

    def instances(self) -> int:
        """How many of this joint the build places."""
        if self.per_channel:
            return self.quantity * _config.active_count()
        return self.quantity


class Kind(StrEnum):
    UNCLASSIFIED_PART = "unclassified_part"
    OMITTED = "omitted"
    DUPLICATE_ID = "duplicate_id"
    UNKNOWN_PART = "unknown_part"
    HARDWARE_UNMODELLED = "hardware_unmodelled"
    UNCLASSIFIED_EXPOSURE = "unclassified_exposure"
    UNREASONED_STATIC_CLAMP = "unreasoned_static_clamp"
    UNLOCKED = "unlocked"
    LOCK_PART_ABSENT = "lock_part_absent"
    LOCK_WRONG_INTERFACE = "lock_wrong_interface"
    LOCK_STEP_ABSENT = "lock_step_absent"
    INSTALL_STEP_ABSENT = "install_step_absent"
    UNKNOWN_EXCEPTION = "unknown_exception"
    EXCEPTION_MISMATCH = "exception_mismatch"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True, order=True)
class Finding:
    assembly: str
    subject: str  # a joint id, or a part stem for coverage findings
    kind: Kind
    detail: str


@dataclass(frozen=True)
class Inventory:
    """What the build knows about each assembly.

    ``parts``: the part stems each assembly's build script references
    directly. ``subassemblies``: the assemblies each one references.
    ``steps``: the keyed step list, for assemblies that have one.
    """

    parts: Mapping[str, frozenset[str]]
    subassemblies: Mapping[str, frozenset[str]] = field(default_factory=dict)
    steps: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def all_parts(self, assembly: str) -> frozenset[str]:
        """Every part in ``assembly``, its sub-assemblies' included."""
        found = set(self.parts.get(assembly, ()))
        for sub in self.subassemblies.get(assembly, ()):
            found |= self.all_parts(sub)
        return frozenset(found)

    def containers(self, assembly: str) -> frozenset[str]:
        """``assembly`` and every assembly that contains it."""
        found = {assembly}
        for parent, subs in self.subassemblies.items():
            if assembly in subs:
                found |= self.containers(parent)
        return frozenset(found)


@dataclass(frozen=True)
class Ruling:
    """A user ruling accepting one named joint without a mechanical lock."""

    joint: str  # the one joint id it waives
    granted: str  # who ruled, when, and where it is recorded


# Keyed by the ``exception`` a row cites. Only the user grants one (policy
# rule 9).
RULINGS: dict[str, Ruling] = {
    "U-MHA-VN-041-threadlocker": Ruling(
        joint="pd-paper-drive/pivot-screw-in-bar",
        granted=(
            "user, 2026-10-02, joint-specific rule-9 ruling relayed with R9-70: keep the "
            "low-strength threadlocker on the MHA-VN-041 shoulder screw. The cross-pin ligament "
            "would be 0.77, a jam nut cannot reach the bar's blind tap, and a pinch slit in "
            "the bar misses the 2.0 wall target with no entry face, so no mechanical lock "
            "fits without changing the photographed 91829A205 head"
        ),
    ),
    "U-MHA-PD-013-no-lock": Ruling(
        joint="pd-paper-drive/thumbnut-on-knob-shaft",
        granted=(
            "user, 2026-10-03, joint-specific rule-9 ruling on the machinist review of "
            "6c385465d: no lock on the MHA-PD-013 thumbnut. The T24 floats 0.05-0.15 under the "
            "flange and turns against it only by its drive-pin backlash, ±0.9° per reversal "
            "((Ø2.5 +0.10 hole - Ø2.381 pin) / 2 on the R7 circle). Any drag it passes is "
            "μ F r_m = 0.15 × 1 N × 5.68 = 0.85 N·mm [INFERENCE: chain axial pull ≤1 N], "
            "against ~360 N·mm to back off a hand-tight nut [INFERENCE: ~400 N preload, μ "
            "0.15 on the 1/4-20 flank and the pilot seat], over 100x. Every positive lock "
            "tried broke a wall or the chain's envelope: a 98335A049 hairpin across the "
            "flange sweeps r ~23 inside the chain band (plates' inner edge r 21.2)"
        ),
    ),
}


@dataclass(frozen=True)
class Occurrence:
    """Where the source places or specifies one required joint."""

    assembly: str
    source: str  # file under cad/scripts
    anchor: str  # literal text in ``source`` at the joint's placement or spec


# Assemblies whose steps are keyed in a step registry.
STEP_LISTS: dict[str, tuple[str, ...]] = {
    "dt_drive_train": dt_drive_train_steps.SEQUENCE,
    "ch_channel": ch_channel_assembly_steps.SEQUENCE,
    "pd_paper_drive": pd_paper_drive_assembly_steps.SEQUENCE,
}


def _lock_part_stem(lock_part: str) -> str:
    return lock_part.split(":", 1)[0]


def audit(
    joints: Iterable[Joint],
    inventory: Inventory,
    *,
    threaded: frozenset[str],
    unthreaded: frozenset[str],
    required: Mapping[str, Occurrence],
    purchased: frozenset[str] = frozenset(),
    unthreaded_stock: Mapping[str, str] | None = None,
    rulings: Mapping[str, Ruling] = RULINGS,
) -> list[Finding]:
    """Every retention and coverage finding, sorted. Empty means clean.

    ``required`` is the joint registry the table must match exactly: a
    registered joint with no row is OMITTED, and a row the registry does not
    list is UNREGISTERED. Stem coverage alone cannot see a missing row when
    another row names the same parts (several screws of one stock).
    ``purchased`` names the bought-in parts; one counts as unthreaded only
    with a reason in ``unthreaded_stock`` (a pin, washer, spring or push-on
    cap), so purchased hardware cannot silently drop out of coverage."""
    unthreaded_stock = unthreaded_stock or {}
    joints = tuple(joints)
    findings: list[Finding] = []

    def flag(assembly: str, subject: str, kind: Kind, detail: str) -> None:
        findings.append(Finding(assembly, subject, kind, detail))

    # Coverage: every registered joint has its row, every row is registered,
    # every referenced part is classified, and every threaded part appears in
    # a row of its assembly or of an assembly containing it.
    rows_by_id = {j.id: j for j in joints}
    for joint_id, occurrence in sorted(required.items()):
        row = rows_by_id.get(joint_id)
        if row is None:
            flag(
                occurrence.assembly,
                joint_id,
                Kind.OMITTED,
                f"required joint has no row ({occurrence.source}: {occurrence.anchor!r})",
            )
        elif row.assembly != occurrence.assembly:
            flag(
                row.assembly,
                joint_id,
                Kind.UNREGISTERED,
                f"registered under {occurrence.assembly}, not {row.assembly}",
            )
    for joint in joints:
        if joint.id not in required:
            flag(
                joint.assembly,
                joint.id,
                Kind.UNREGISTERED,
                "row has no entry in REQUIRED_JOINTS",
            )
    named: dict[str, set[str]] = {}
    for joint in joints:
        named.setdefault(joint.assembly, set()).update({joint.member, joint.receiver})
    for assembly, parts in sorted(inventory.parts.items()):
        rows = set().union(
            *(named.get(a, set()) for a in inventory.containers(assembly))
        )
        for stem in sorted(parts):
            if (stem in threaded) == (stem in unthreaded):
                flag(
                    assembly,
                    stem,
                    Kind.UNCLASSIFIED_PART,
                    "classified both threaded and unthreaded"
                    if stem in threaded
                    else "not classified as threaded or unthreaded",
                )
            elif stem in threaded and stem not in rows:
                flag(
                    assembly, stem, Kind.OMITTED, "threaded part named by no joint row"
                )
            elif (
                stem in purchased
                and stem in unthreaded
                and stem not in unthreaded_stock
            ):
                flag(
                    assembly,
                    stem,
                    Kind.UNCLASSIFIED_PART,
                    "purchased fastener classified unthreaded without a reason",
                )

    for joint_id, count in Counter(j.id for j in joints).items():
        if count > 1:
            assembly = next(j.assembly for j in joints if j.id == joint_id)
            flag(assembly, joint_id, Kind.DUPLICATE_ID, f"{count} rows share this id")

    for joint in joints:

        def bad(kind: Kind, detail: str, joint: Joint = joint) -> None:
            flag(joint.assembly, joint.id, kind, detail)

        in_assembly = inventory.all_parts(joint.assembly)
        for role, stem in (("member", joint.member), ("receiver", joint.receiver)):
            if stem == UNMODELLED:
                bad(
                    Kind.HARDWARE_UNMODELLED,
                    f"{role} is called for but no assembly places it",
                )
            elif stem not in in_assembly:
                bad(Kind.UNKNOWN_PART, f"{role} {stem} is not in {joint.assembly}")

        steps = inventory.steps.get(joint.assembly)
        if steps is not None and joint.installed_at and joint.installed_at not in steps:
            bad(
                Kind.INSTALL_STEP_ABSENT,
                f"step {joint.installed_at!r} is not in the step list",
            )

        ruling = rulings.get(joint.exception) if joint.exception else None
        if joint.exception and ruling is None:
            bad(Kind.UNKNOWN_EXCEPTION, f"{joint.exception!r} is not a user ruling")
        elif ruling is not None and ruling.joint != joint.id:
            bad(
                Kind.EXCEPTION_MISMATCH,
                f"ruling {joint.exception!r} waives {ruling.joint}, not this joint",
            )

        if joint.exposure is Exposure.UNCLASSIFIED:
            bad(Kind.UNCLASSIFIED_EXPOSURE, "load exposure not classified")
        elif (
            joint.exposure is Exposure.STATIC_CLAMP
            and not joint.exposure_reason.strip()
        ):
            bad(
                Kind.UNREASONED_STATIC_CLAMP,
                "static_clamp without the reason no operating torque reaches it",
            )

        excepted = ruling is not None and ruling.joint == joint.id
        if joint.lock in NOT_A_LOCK:
            if joint.exposure in EXPOSED and not excepted:
                bad(
                    Kind.UNLOCKED,
                    f"{joint.exposure} joint retained by {joint.lock}; "
                    "needs a mechanical anti-loosening means",
                )
            continue

        # A declared mechanical lock must exist, act on this interface and be
        # installed by a step of the assembly.
        own_features = {joint.member, joint.receiver}
        lock_stem = _lock_part_stem(joint.lock_part)
        if not joint.lock_part:
            bad(Kind.LOCK_PART_ABSENT, f"{joint.lock} names no locking part or feature")
        elif lock_stem not in in_assembly and lock_stem not in own_features:
            bad(
                Kind.LOCK_PART_ABSENT,
                f"lock part {lock_stem} is not in {joint.assembly}",
            )
        if set(joint.lock_binds) != own_features or len(joint.lock_binds) != 2:
            bound = " and ".join(joint.lock_binds) or "nothing"
            bad(
                Kind.LOCK_WRONG_INTERFACE,
                f"lock binds {bound}, not {joint.member} to {joint.receiver}",
            )
        if not joint.lock_step:
            bad(Kind.LOCK_STEP_ABSENT, "no assembly step installs the lock")
        elif steps is not None and joint.lock_step not in steps:
            bad(
                Kind.LOCK_STEP_ABSENT,
                f"locking step {joint.lock_step!r} is not in the step list",
            )

    return sorted(findings)


@functools.lru_cache(maxsize=1)
def build_inventory() -> Inventory:
    """The build's own enumeration: each assembly script's referenced parts
    and sub-assemblies (``_buildgraph.references_of``) and its keyed steps."""
    assemblies = frozenset(_buildgraph.ASSEMBLY_ORDER)
    parts: dict[str, frozenset[str]] = {}
    subassemblies: dict[str, frozenset[str]] = {}
    for assembly in _buildgraph.ASSEMBLY_ORDER:
        references = _buildgraph.references_of(assembly)
        subassemblies[assembly] = frozenset(r for r in references if r in assemblies)
        parts[assembly] = frozenset(r for r in references if r not in assemblies)
    return Inventory(parts, subassemblies, STEP_LISTS)


def purchased_parts() -> frozenset[str]:
    """Stems the part registry marks ``process: purchased``."""
    return frozenset(
        name.replace("-", "_")
        for name, row in _config.parts().items()
        if row.get("process") == "purchased"
    )


def audit_table() -> list[Finding]:
    """The audit of the real table against the real build enumeration."""
    return audit(
        JOINTS,
        build_inventory(),
        threaded=THREADED_PARTS,
        unthreaded=UNTHREADED_PARTS,
        purchased=purchased_parts(),
        unthreaded_stock=UNTHREADED_STOCK,
        required=REQUIRED_JOINTS,
    )


def _part_number(stem: str) -> str:
    if stem == UNMODELLED:
        return ""
    try:
        return str(_config.parts(stem.replace("_", "-")).get("number", ""))
    except KeyError:
        return ""


def report(findings: list[Finding]) -> dict[str, object]:
    """The JSON report: per-assembly counts, the findings and every row."""
    per_assembly: dict[str, dict[str, int]] = {}
    for assembly in _buildgraph.ASSEMBLY_ORDER:
        rows = [j for j in JOINTS if j.assembly == assembly]
        per_assembly[assembly] = {
            "rows": len(rows),
            "instances": sum(j.instances() for j in rows),
            "findings": sum(1 for f in findings if f.assembly == assembly),
        }
    # A deleted row is still a joint: its OMITTED finding names a registered id.
    joint_ids = {j.id for j in JOINTS} | set(REQUIRED_JOINTS)
    return {
        "enforcement": str(ENFORCEMENT),
        "rows": len(JOINTS),
        "per_assembly": per_assembly,
        "failing_joints": sorted(
            {f.subject for f in findings if f.subject in joint_ids}
        ),
        "findings": [asdict(f) for f in findings],
        "joints": [
            {
                **asdict(j),
                "instances": j.instances(),
                "member_number": _part_number(j.member),
                "receiver_number": _part_number(j.receiver),
            }
            for j in JOINTS
        ],
    }


def summary(data: Mapping[str, object], findings: list[Finding]) -> str:
    """The readable summary printed by the check and saved beside the JSON."""
    lines = [
        "# Threaded-joint retention audit",
        "",
        f"Enforcement: {data['enforcement']}. Rows: {data['rows']}. "
        f"Findings: {len(findings)} on {len(data['failing_joints'])} joints "
        f"(policy: cad/docs/drawing-simplicity-policy.md rule 9).",
        "",
        "| assembly | rows | instances | findings |",
        "|---|---:|---:|---:|",
    ]
    per_assembly = data["per_assembly"]
    assert isinstance(per_assembly, dict)
    for assembly, counts in per_assembly.items():
        lines.append(
            f"| {assembly} | {counts['rows']} | {counts['instances']} | {counts['findings']} |"
        )
    lines.append("")
    for finding in findings:
        lines.append(
            f"- {finding.assembly} {finding.subject}: {finding.kind}: {finding.detail}"
        )
    return "\n".join(lines) + "\n"


REPORT_JSON = _buildgraph.CAD_OUT / "reports" / "joint-retention.json"
REPORT_SUMMARY = REPORT_JSON.with_suffix(".md")


def main() -> int:
    findings = audit_table()
    data = report(findings)
    text = summary(data, findings)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    REPORT_SUMMARY.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"report: {REPORT_JSON}")
    if findings and ENFORCEMENT is Enforcement.GATE:
        return 1
    return 0


# --- The table ----------------------------------------------------------------

# Every referenced part that carries a thread (member or receiver).
THREADED_PARTS: frozenset[str] = frozenset(
    {
        "dt_arbor_pedestal",  # #4-40 UNC-2B apex tap through the crown (receiver of MHA-VN-034); its #8 ledge hole is clearance only
        "vn_arbor_set_screw",  # #4-40 UNC-2A x 1/4 cup-point set screw (McMaster 91375A106), member into arbor_pedestal
        "vn_boss_hook",  # #10-24 UNC (McMaster 9490T1 open-eye eyebolt), member into the summing-lever boss tap
        "vn_clamp_screw",  # #8-32 UNC (McMaster 90280A201), member into column_clamp_back: 2 in magnifier, 4 in paper_drive
        "sh_column_clamp_back",  # #8-32 UNC tapped ear holes, receiver of clamp_screw (magnifier and paper_drive)
        "dt_cone_gear_shaft",  # receiver: Sec4 D-flat gripped by cone_tip_collar's #2-56 set screw
        "vn_cone_lock_knob",  # 1/4-20 UNC knurled thumb screw (93585A190), member into harmonic_base (top level)
        "vn_cone_pivot_screw",  # #10-24 UNC shoulder screw (91829A560), member into harmonic_base (top level)
        "dt_cone_swing_platform",  # 1/4-20 through-taps x2, receiver of post_mount_screw
        "vn_cone_tip_adjuster",  # #10-32 cup-tip set screw (94025A164), member into cone_tip_block
        "dt_cone_tip_block",  # #4-40 blind foot tap + #10-32 through adjuster tap + #4-40 far-jaw pinch tap, receiver
        "vn_cone_tip_block_screw",  # #4-40 SHCS (91251A108), member into cone_tip_block foot
        "vn_cone_tip_collar",  # #2-56 own set screw (9414T1 set-screw collar), member gripping cone_gear_shaft
        "vn_cone_tip_pinch_screw",  # #4-40 fillister (91794A112), member into cone_tip_block far jaw; lock of cone_tip_adjuster
        "dt_crank_arm",  # #4-40 through-taps, receiver of crank_handle_pivot_screw and fillister_screw (MHA-VN-006)
        "dt_crank_handle_pivot_screw",  # #4-40 made shoulder screw (MHA-DT-032), member into crank_arm
        "vn_fillister_screw",  # #4-40 brass fillister (90114A511): nameplate into harmonic_base, keeper eye into crank_arm, paper-drive clip and guide screws
        "vn_foot_screw",  # #4-40 fillister (90280A108), member into harmonic_base via pinion_spring foot (top level)
        "vn_frame_cross_screw",  # #10-32 UNF-2A x 1-3/4 (McMaster 90280A837), member: 4 into harmonic_base, 4 into top_frame
        "vn_frame_side_screw",  # #8-32 narrow fillister (McMaster 90280A194, MHA-VN-022); member, x2 into top_frame KeeperTaps (top-level row)
        "sm_gooseneck",  # #6-32 UNC integral slotted spring screw in the brazed end-plug tap (member AND receiver, one component); also the post the frame's 1/4-20 set screw bears on
        "vn_gooseneck_set_screw",  # 1/4-20 UNC square-head cup point (91410A538), member: into top_frame hub tap, grips summing gooseneck
        "vn_guide_lock_screw",  # #4-40 button head (McMaster 91255A108, MHA-VN-046, R9-31), member: 8 into the platen_guide rear through taps
        "vn_hanger_screw",  # #8-32 UNC x 1/2 hex head (McMaster 93075A194), member into the pen-hanger strap tap
        "fr_harmonic_base",  # receiver: #10-32 cross taps, 1/4-20 hold-down seats, #4-40 nameplate seats, and the drive_train screws' seats (top-level rows)
        "vn_knife_hanger_stud",  # 1/2-13 UNC (McMaster 91247A720 hex head x 2), member into the knife-mount top tap
        "sm_knife_mount",  # 1/2-13 UNC-2B x 12.0 blind tap in the top seat, receiver of the knife-hanger stud
        "vn_lag_screw",  # 1/4-20 UNC-2A x 3/4 hex head (92240A540), member: through rocker_arm_support foot into harmonic_base
        "vn_latch_hook_bracket_screw",  # #4-40 narrow fillister (McMaster 90280A108, MHA-VN-043), member: 2 into the support_bar's #4-40 through taps
        "vn_magnifying_bracket_screw",  # #2-56 fillister, member: two in bracket counterbores into summing_lever (top-level row)
        "mg_magnifying_clamp",  # #4-40 UNC-2B tapped ScrewHole (Hole Wizard), receiver of thumb_screw
        "ha_measuring_stick_stop",  # knurled thumbscrew (size not stated) threading up through the block floor, modelled integral (member AND receiver, one component)
        "mg_output_fixture",  # #4-40 UNC tapped cross hole (entry wall), receiver of the 2nd thumb_screw
        "vn_pedestal_hold_down_screw",  # #8-32 x 3/4 fillister (90280A197, MHA-VN-032), member: 2 arbor-pedestal seats in harmonic_base, 4 pivot-bracket seats in rocker_arm_support
        "pn_pen_frame",  # #4-40 UNC-2B tapped hole up through the bottom rail, receiver of pen_set_screw
        "pn_pen_hanger",  # #8-32 tapped hole in the strap, receiver of hanger_screw
        "vn_pen_set_screw",  # #4-40 UNC (McMaster 99607A213 knurled thumb screw), member into the pen-frame rail
        "pn_pen_v_block",  # receiver: Ø2.5 rod set-screw hole drilled thru, "THREAD/FIT TO SUIT SET SCREW AT ASSEMBLY"; the screw is not modelled
        "dt_pinion_cam",  # M2.5 x 0.45 6H tap + supplied ISO 4026 M2.5 x 5 flat-point set screw, member (collar) gripping pinion_lift_rod
        "pd_platen",  # #4-40 tapped through (pd_platen_spec.SOCKET_SPEC), receiver of the 4 clip screws
        "pd_platen_guide",  # #4-40 front bottoming taps (guide screws) + rear through taps (guide-lock screws, R9-48), receiver
        "vn_post_mount_screw",  # 1/4-20 (MSC 40923898 fillister, cut to fit), member into cone_swing_platform
        "pd_rack_pinion",  # 120T disc (MHA-PD-006): 3x #0-80 through taps drilled and tapped at assembly (A06 disc-taps-transferred), receiver of the disc screws
        "fr_rocker_arm_support",  # receiver only of channel screws: 4x #8-32 BracketSeats (top-level rows); its own foot holes are 5/16 clearance
        "vn_slotted_screw",  # #8-32 x 1-1/4 fillister (90280A201, MHA-VN-019), member into harmonic_base tapped seat
        "vn_spring_hook",  # #6-32 eyebolt (McMaster 9489T111, MHA-VN-012); member, x20 into summing_lever tapped plate (top-level row); no channel-internal joint
        "sm_summing_lever",  # receiver: #10-24 counter-anchor, 20x #6-32 channel anchors, two blind #2-56 magnifying-bracket seats
        "pd_support_bar",  # #8-32 blind pivot tap + 2x #4-40 through latch-hook taps (pd_support_bar_spec), receiver of the pivot screw and the latch-hook bracket screws
        "vn_swing_stop_screw",  # #4-40 fillister (90280A108), member into harmonic_base (top level)
        "vn_thumb_screw",  # #4-40 UNC (McMaster 91882A221), member: into magnifying_clamp ScrewHole; 2nd instance into output_fixture cross hole (config qty 2, not placed in the SLDASM)
        "fr_top_frame",  # receiver: #10-32 cross taps, 1/4-20 gooseneck set tap, #8-32 fulcrum-keeper taps (top-level row)
        "pd_transgear_arm",  # MHA-PD-018: 2x #8-32 plate taps through (pd_transgear_arm_spec), receiver; the pin MHA-PD-023 is pressed in a reamed hole
        "vn_transgear_arm_plate_screw",  # #8-32 slotted oval head (McMaster 91790A196, MHA-VN-040), cut to fit; member: 2 into transgear_arm
        "vn_transgear_disc_screw",  # #0-80 slotted fillister (McMaster 91794A055, MHA-VN-039), cut to fit; member: 3 through the hub flange into rack_pinion
        "pd_transgear_knob_shaft",  # MHA-PD-008: 1/4-20 UNC die-cut front thread (thumbnut), receiver; the rear journal is cross-pinned to the cup (MHA-VN-048)
        "vn_transgear_pivot_screw",  # #8-32 shoulder screw (McMaster 91829A205, MHA-VN-041), member into the support_bar's blind pivot tap
        "pd_transgear_thumbnut",  # MHA-PD-013 knurled nut, 1/4-20 UNC-2B through; member on the knob shaft's front thread
        "mg_wheel_axle",  # stud tip carries the hex nut (thread not modelled / not specified on the axle drawing), receiver of wheel_axle_nut
        "vn_wheel_axle_nut",  # hex nut AF8 x 3 on the O5 stud ("commercial hex nut (thread not modelled)"), member
    }
)

# Every referenced part with no thread of its own.
UNTHREADED_PARTS: frozenset[str] = frozenset(
    {
        "dt_alignment_pinion",  # bonded to pinion_arbor (Loctite 638, drum-bonded)
        "ch_amplitude_bar",  # reamed top pin hole (pressed MHA-CH-011 pin), end notches; pinned/sliding only
        "ch_bar_pivot_pin",  # plain 5/64 drill-rod pin pressed in the bar cheeks, runs in the lever
        "vn_chain_inner_link",  # roller-chain plate, no thread
        "vn_chain_outer_link",  # roller-chain plate, no thread
        "ch_channel_lever",  # Ø6.5 fulcrum bore, #47 bar-pin hole, #21 spring-eye hole; no taps
        "vn_channel_spring_installed",  # 9432K31 extension spring, hook ends in lever hole / eyebolt eye
        "sh_column_clamp_front",  # #8 CLEARANCE ear holes only; clamped in the screw stack
        "dt_cone_gear",  # slides on the MHA-DT-004 D-flat, no thread
        "dt_cone_pivot_post",  # clamped part: counterbored clearance for MHA-VN-031; journals only
        "ch_connecting_rod",  # strap bore on cam + reamed pin hole (pressed MHA-CH-010 pin)
        "vn_counter_spring",  # 1330K524 extension spring: eyes hook the gooseneck screw shank and the boss-hook eye, no thread
        "dt_crank_drive_gear",  # slides on the MHA-DT-004 D-flat against its collar, no thread
        "dt_crank_handle",  # oak handle, runs on the MHA-DT-032 shoulder
        "dt_crank_handle_butt_cup",  # bonded in the handle butt; pocket bored for the MHA-DT-032 head, no thread
        "dt_crank_handle_ferrule",  # bonded (epoxy) to the handle tenon
        "dt_crank_hub",  # pressed into crank_arm, seam-pinned, taper-pinned to crankshaft
        "vn_crank_hub_pin",  # 4 m6 dowel, ISO 2338
        "dt_crank_pin",  # 1:48 taper pin, light drive
        "dt_crank_pin_eye",  # formed brass eye, clamped under fillister_screw (no thread of its own)
        "vn_crank_seat_drive_pin",  # MHA-VN-044 dowel pressed into match-drilled holes, no thread
        "dt_crank_seat_washer",  # MHA-DT-036 turned steel washer, plain bore, no thread
        "dt_crank_pin_ring",  # brass wire keeper ring
        "dt_crank_pinion",  # pinned by crank_pinion_pin
        "dt_crank_pinion_pin",  # plain 1/8 drill-rod drive pin
        "dt_crankshaft",  # journals in MHA-DT-005; pinned (MHA-DT-029), taper-pinned (MHA-DT-009); paper-drive T12 wheel has no thread
        "dt_cylinder_end_disc",  # plain thrust washer on the arbor
        "dt_cylinder_gear",  # runs free on the arbor, no set screw
        "dt_cylinder_gear_shaft",  # plain 3/8 arbor; MHA-VN-034 cups bear in drilled spots, no thread ("NO FLATS; SET-SCREW SPOTS ARE DRILLED AT ASSEMBLY")
        "ch_fulcrum_keeper",  # #8 close-clearance + fillister c'bore (clearance only); Ø6.50 reamed ball bore
        "ch_fulcrum_shaft",  # plain Ø6.35 shaft, no threads
        "pd_guide_lock",  # 1/8 drill holes (R9-49) only; clamped by guide_lock_screw
        "vn_keeper_chain",  # bead chain
        "vn_keeper_chain_link",  # snap loop link
        "vn_knife_hanger_washer",  # 90126A211 SAE washer, clearance ID
        "pd_latch_hook",  # MHA-PD-014 formed spring-steel hook: screw holes drilled thru, latch-pin hole match-drilled at assembly; no thread
        "mg_lever_wire",  # wire, tied through the fixture cross hole; no thread
        "mg_magnifying_bracket",  # two counterbored normal #2 clearance holes in its front mounting flange; no thread
        "mg_magnifying_lever",  # plain Ø6 domed rod
        "mg_magnifying_vertical_rod",  # plain Ø5 domed rod
        "mg_magnifying_wheel",  # Ø5 reamed running bore; no thread
        "ha_measuring_stick",  # plain 8 x 3 brass bar; the stop's thumbscrew tip pinches it
        "fr_nameplate",  # brass plate, #4 clearance holes only
        "pn_pen_marker",  # plain barrel; the thumb-screw tip bears on it (no thread)
        "pn_pen_rod",  # square brass bar; #47 drilled wire hole only
        "pn_pen_wire",  # Ø0.80 wire, tied off (tie-off not modelled)
        "dt_pinion_arbor",  # journal + grip head, crossrod bonded, collar spring-pinned
        "dt_pinion_arbor_collar",  # spring-pinned by MHA-VN-033 (arbor-collar-pinned)
        "dt_pinion_bracket",  # straps: plain bores, pinned to MHA-DT-019 by MHA-VN-033
        "dt_pinion_cam_pin",  # bonded follower pin (cam-pins-bonded)
        "dt_pinion_handle",  # bonded crossrod (handle-bonded)
        "dt_pinion_lever",  # hub cross-pinned by MHA-DT-030 (lever-pin-set)
        "dt_pinion_lever_pin",  # peened cross pin
        "dt_pinion_lift_rod",  # plain Ø6.35 rod; gripped by the MHA-DT-023 set screws (appears as receiver of the cam row, carries no thread)
        "dt_pinion_pivot_block",  # #8 normal-clearance holes only; clamped by MHA-VN-019 (row harmonic-analyzer/pinion-block-hold-down)
        "dt_pinion_pivot_shaft",  # plain shaft, cross-pinned to the straps by MHA-VN-033
        "dt_pinion_spring",  # #4 clearance foot hole; clamped by foot_screw MHA-VN-020 (top-level row)
        "vn_pinion_strap_pin",  # 1/16 spring pin
        "ch_pivot_bracket",  # #8 close-clearance foot holes, reamed ear cross-bore; no taps
        "ch_pivot_shaft",  # plain Ø10 shaft, integral shoulder, domed plain end; "NO FLATS"
        "pd_platen_clip",  # #4 clearance holes only (build_pd_platen_clip); clamped by fillister_screw
        "pd_platen_paper",  # paper sheet, no thread
        "pd_platen_rack",  # soft-soldered to the platen back (A06 rack-soldered); no holes, no thread
        "ch_rocker_arm",  # reamed pivot hub bore + #47 rod-pin hole
        "ch_rod_pivot_pin",  # MHA-CH-010 5/64 drill-rod pin, pressed into the fork's reamed tines, ends dressed flush (rod-forks-pinned); no thread
        "ch_rocker_thrust_washer",  # 1/16 sheet washer, plain bore
        "pd_transgear_arm_plate",  # MHA-PD-019: reamed knob-shaft bore + 2 countersunk clearance screw holes; no thread
        "vn_transgear_collar_cross_pin",  # MHA-VN-037 1/16 slotted spring pin through the drive collar slot and shaft core
        "vn_transgear_knob_cup_pin",  # MHA-VN-048 1/16 slotted spring pin through the knob cup and the shaft's journal
        "pd_transgear_disc_hub",  # MHA-PD-017 brass hub: D-bore on the sleeve's D-flat, plain flange clearance holes for the disc screws; trapped between the seat shoulder and the front bushing, no thread
        "pd_transgear_drive_collar",  # MHA-PD-022: reamed bore, reamed drive-pin holes, rear slot; no thread
        "pd_transgear_feed_pinion",  # MHA-PD-010 12T DP30 feed sleeve: plain bore on the pin, D-flat keying the hub's D-bore; no thread
        "pd_transgear_front_bushing",  # MHA-PD-025 brass bushing faced to fit, reamed bore on the pin; no thread
        "pd_transgear_knob_cup",  # MHA-PD-016: reamed through bore, cross-pinned to the journal at assembly; no thread
        "pd_transgear_knob_thrust_ring",  # MHA-PD-015 loose brass ring, drilled bore; no thread
        "vn_transgear_latch_pin",  # MHA-VN-042 1/8 dowel pressed into the arm's reamed end-face hole
        "pd_transgear_pivot_spacer",  # MHA-PD-020 brass spacer, reamed bore pressed on the pivot shoulder (locating, R9-71); no thread
        "vn_transgear_pivot_spring",  # MHA-VN-049 disc spring on the pivot shoulder; no thread
        "vn_cylinder_bank_spring",  # MHA-VN-052 wave spring loose on the MHA-DT-013 arbor; no thread
        "vn_rocker_bank_spring",  # MHA-VN-053 wave spring loose on the MHA-CH-005 shaft; no thread
        "pd_transgear_pin",  # MHA-PD-023 plain steel pin pressed into the arm's reamed hole, ring groove at the front; no thread
        "pd_transgear_rear_bushing",  # MHA-PD-024 brass bushing faced to fit, reamed bore on the pin; no thread
        "pd_transgear_removable",  # O12 plain bore + 2 drive-pin holes, no thread (build_pd_transgear_removable)
        "vn_transgear_retaining_ring",  # MHA-VN-047 external retaining ring (McMaster 97431A260) in the pin's groove
        "vn_transgear_knob_drive_pin",  # MHA-VN-038 dowel pressed into plain holes, no thread
        "fr_tube_frame",  # columns: socket slip fit; cross holes enlarged so the MHA-VN-027 shank passes "WITHOUT THREAD CONTACT" (MHA-FR-000 STEP 2/5)
        "vn_tube_frame_cap",  # McMaster 9275K141 push-on cap (MHA-FR-000 STEP 7)
        "mg_wheel_bar",  # #8 clearance holes (clamp screws) + #8 close clearance (pen-hanger screw, which threads into pen_hanger in pen.SLDASM)
    }
)

# Purchased parts (registry ``process: purchased``) that carry no thread.
UNTHREADED_STOCK: dict[str, str] = {
    "vn_channel_spring_installed": "extension spring; its hook ends hang in plain holes and eyes",
    "vn_counter_spring": "extension spring; its hook ends hang in plain holes and eyes",
    "vn_keeper_chain": "chain; its end links hang on screws and eyes, carrying no thread",
    "vn_crank_seat_drive_pin": "dowel pin pressed into a plain hole",
    "vn_keeper_chain_link": "plain chain link",
    "vn_knife_hanger_washer": "plain flat washer",
    "vn_pinion_strap_pin": "slotted spring pin pressed into a plain hole",
    "vn_transgear_knob_drive_pin": "dowel pin pressed into a plain hole",
    "vn_transgear_collar_cross_pin": "slotted spring pin in a drilled hole",
    "vn_transgear_knob_cup_pin": "slotted spring pin in a hole match-drilled at assembly",
    "vn_transgear_latch_pin": "dowel pin pressed into a reamed hole",
    "vn_transgear_retaining_ring": "external retaining ring fitted sideways in a groove",
    "vn_transgear_pivot_spring": "disc spring on the pivot shoulder; no thread",
    "vn_cylinder_bank_spring": "wave disc spring loose on the arbor; no thread",
    "vn_rocker_bank_spring": "wave disc spring loose on the pivot shaft; no thread",
    "vn_tube_frame_cap": "push-on round cap over the column end",
}

JOINTS: tuple[Joint, ...] = (
    # --- frame (MHA-FR-000), and the gooseneck set screw that grips a summing part ---
    Joint(
        id="fr-frame/cross-screw-in-base",
        assembly="fr_frame",
        member="vn_frame_cross_screw",
        receiver="fr_harmonic_base",
        thread="#10-32 UNF-2A/2B",
        quantity=4,
        installed_at="MHA-FR-000 STEP 6",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="retains a tube_frame column in its base socket; base and columns never move relative to each other and no operating member bears on or turns about the horizontal screw axis (the screw passes clearance holes in both tube walls)",
        axial_capture="narrow fillister head seated on the Ø9 spotface of the base pad; thread engages near and far casting segments of the interrupted 46 mm bottoming tap",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (lower cross screws, BASE_SCREW_Y/BASE_SCREW_SEAT_Z) + module asserts; fr_harmonic_base_fasteners.py:BASE_CROSS_TAP_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 2, 6 ('TIGHTEN ONLY UNTIL EVERY HEAD SEATS'), ASSEMBLY_CHECKS 2",
    ),
    Joint(
        id="fr-frame/cross-screw-in-top-frame",
        assembly="fr_frame",
        member="vn_frame_cross_screw",
        receiver="fr_top_frame",
        thread="#10-32 UNF-2A/2B",
        quantity=4,
        installed_at="MHA-FR-000 STEP 6",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="retains the top_frame casting on a tube_frame column; casting and columns are stationary relative to each other and no rotating/rocking member turns about the horizontal screw axis (clearance through both tube walls)",
        axial_capture="narrow fillister head seated on the Ø9 boss spotface; thread engages near and far wall of the top_frame interrupted #10-32 bottoming tap (SideTaps)",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (upper cross screws, TOP_SCREW_Y/TOP_SCREW_SEAT_Z); build_fr_top_frame.py:SIDE_TAP_SPEC, step 13 SideTaps; draw_fr_frame_assembly.py ASSEMBLY_STEPS 5, 6, ASSEMBLY_CHECKS 2",
    ),
    Joint(
        id="fr-frame/support-hold-down-in-base",
        assembly="fr_frame",
        member="vn_lag_screw",
        receiver="fr_harmonic_base",
        thread="1/4-20 UNC-2A/2B",
        quantity=4,
        installed_at="MHA-FR-000 STEP 8",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps the rocker_arm_support foot to the base deck; the support never moves on the base, and the rocker pivot it carries turns about machine Z (horizontal), so the rocker's reaction reaches these vertical (Y-axis) screws as cyclic tension/shear, not as torque about their own axis",
        axial_capture="hex head's under-head washer face bears on the 6.35 support foot (5/16 clearance drill); 12.42 mm (1.956D) engagement in the blind 13.2-deep 1/4-20 UNC-2B base seat",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (lag-screw seed + grid) and LAG_* asserts; fr_harmonic_base_fasteners.py:HOLD_DOWN_SEAT_SPEC/HOLD_DOWN_ENGAGEMENT; fr_rocker_arm_support_spec.py:HOLE_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 8 ('DRAW DOWN EVENLY UNTIL ALL HEADS SEAT')",
    ),
    Joint(
        id="fr-frame/nameplate-screw-in-base",
        assembly="fr_frame",
        member="vn_fillister_screw",
        receiver="fr_harmonic_base",
        thread="#4-40 UNC",
        quantity=4,
        installed_at="MHA-FR-000 STEP 9",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="holds the cosmetic nameplate flat on the base deck; plate and base never move relative to each other and nothing in operation touches or turns the plate",
        axial_capture="fillister head seated flush on the plate's decorated face; 4.85 of shank engaged in the 6.0-deep #4-40 bottoming-tapped base seat",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (nameplate corner screws, NAMEPLATE_SCREW_* asserts); fr_harmonic_base_fasteners.py:NAMEPLATE_SCREW_HOLE_DEPTH; build_fr_harmonic_base.py:NAMEPLATE_SEAT_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 9",
    ),
    Joint(
        id="ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame",
        assembly="ha_harmonic_analyzer",
        member="vn_gooseneck_set_screw",
        receiver="fr_top_frame",
        thread="1/4-20 UNC",
        quantity=1,
        installed_at="MHA-FR-000 STEP 10",
        exposure=Exposure.OSCILLATING,
        exposure_reason="cup point is the ONLY retention of the summing gooseneck post (MHA-SM-001) in the top_frame rail-hub bore, both its slid-to-level height and its rotation; the post's arm carries the counter-spring hung from the rocking summing lever, so the load it reacts cycles every stroke",
        axial_capture="threads into the through-to-bore 1/4-20 GooseneckTap in the east-rail hub rib; square head outboard; cup point bears radially on the Ø16 post (as modelled it stands 0.15 clear)",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (gooseneck-set-screw, SET_SCREW_TIP_X) + module comment; build_fr_top_frame.py:SET_TAP_SPEC, step 14 GooseneckTap; build_sm_summing_assembly.py docstring + gooseneck placement; spring_mount_geom.py docstring ('setup slides the gooseneck until level'); draw_fr_frame_assembly.py ASSEMBLY_STEPS 10 ('START MHA-VN-023 ... LEAVE ITS CUP POINT CLEAR'), ASSEMBLY_CHECKS 5",
    ),
    # --- drive_train (MHA-DT-000): cone set and crank, and their screws into the frame's base ---
    Joint(
        id="dt-drive-train/post-mount-screws",
        assembly="dt_drive_train",
        member="vn_post_mount_screw",
        receiver="dt_cone_swing_platform",
        thread="1/4-20",
        quantity=2,
        installed_at="post-and-tip-block",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "Clamp MHA-DT-005 to MHA-DT-020, and MHA-DT-005 journals the continuously turning MHA-DT-004 "
            "cone shaft and, directly, the hand-turned MHA-DT-011 crankshaft, whose handle load "
            "turns through 360 deg every revolution; journal drag and that rotating crank load "
            "reach the post-to-plate joint as a cyclic moment about vertical that only head and "
            "face friction resist (the post is deliberately turned on the screws' clearance at "
            "fit-up, so nothing else locates it in rotation)"
        ),
        axial_capture=(
            "fillister head on the MHA-DT-005 counterbore floor; thread through the MHA-DT-020 1/4-20 "
            "through-tap, cut flush to 0.3 short of the underside (0.90D min, named exception "
            "MHA-VN-031, engagement only); left loose at post-and-tip-block, tightened at "
            "tip-adjuster-set"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py post_screws placement + lock_mate 'clamped in the post "
            "counterbore', cone-shaft revolute on 'journal axis@dt-cone-pivot-post'; "
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 2 (post-and-tip-block) and 3 "
            "(tip-adjuster-set 'TIGHTEN BOTH MHA-VN-031'), 4 (crank-mesh-checked 'FIT MHA-DT-011 "
            "DIRECTLY IN THE MHA-DT-005 CRANK BORE'); vn_post_mount_screw_spec.THREAD; "
            "dt_cone_swing_platform_spec.POST_MOUNT_SPEC; policy Named exceptions MHA-VN-031"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-block-hold-down",
        assembly="dt_drive_train",
        member="vn_cone_tip_block_screw",
        receiver="dt_cone_tip_block",
        thread="#4-40",
        quantity=1,
        installed_at="post-and-tip-block",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "The one screw is MHA-DT-021's only anchor, and MHA-DT-021 carries the running MHA-DT-004 tip "
            "in the MHA-VN-017 cup: the shaft's end-play thrust acts 1.0 off the screw axis "
            "(dt_cone_tip_block_spec.FOOT_TAP_OFFSET_X) and the radial tip load acts off it along "
            "the shaft, so a moment about the vertical screw axis varies with mesh load every "
            "crank turn (and reverses with the crank); a single screw lets the block turn about "
            "it, and the build's 'tip-block anti-spin' parallel mate has no physical "
            "counterpart (no dowel, key, pocket or second screw)"
        ),
        axial_capture=(
            "SHCS head on the MHA-DT-020 underside counterbore floor, thread up into the blind #4-40 "
            "tap in the MHA-DT-021 foot; tightened 'SNUG'"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py tip_holddown placement + lock_mate 'clamped in the "
            "platform hold-down counterbore', parallel_mate 'tip-block anti-spin (rides the "
            "plate)'; cone_tip_block_spec HOLDDOWN_THREAD / FOOT_TAP_OFFSET_X (user ruling "
            "2026-09-29: one #4-40 SHCS); draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 2 "
            "(post-and-tip-block '... INTO THE MHA-DT-021 FOOT, SNUG')"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-adjuster",
        assembly="dt_drive_train",
        member="vn_cone_tip_adjuster",
        receiver="dt_cone_tip_block",
        thread="#10-32",
        quantity=1,
        installed_at="tip-adjuster-set",
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "Its turn sets MHA-DT-004's end play (run in until the shaft stops shuttling, back off "
            "1/8 turn), and the shaft tip turns continuously against its cup, putting friction "
            "drag about the screw's own axis"
        ),
        axial_capture=(
            "thread engagement only: headless cup-tip set screw in the block's #10-32 "
            "through-tap, 1.0D min (named exception MHA-VN-017); cup bears on the shaft tip"
        ),
        lock=Lock.PINCH_CLAMP,
        lock_part="vn_cone_tip_pinch_screw",
        lock_binds=("vn_cone_tip_adjuster", "dt_cone_tip_block"),
        lock_step="tip-adjuster-set",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 3 (tip-adjuster-set 'THREAD MHA-VN-017 ... "
            "BACK OFF 1/8 TURN; TIGHTEN MHA-VN-018 ACROSS THE SLIT'); cone_tip_block_spec "
            "SLIT_FLOOR / WORST_SLIT_BREAKTHROUGH_MM (slit opens into the adjuster thread), "
            "PINCH_THREAD; build_dt_drive_train_assembly.py parallel_mate 'adjuster anti-spin "
            "(pinch-locked)'; policy Named exceptions MHA-VN-017 ('the pinch screw across the slit "
            "locks it'); cone_stack_end_play.SHAFT_END_PLAY"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-pinch-screw",
        assembly="dt_drive_train",
        member="vn_cone_tip_pinch_screw",
        receiver="dt_cone_tip_block",
        thread="#4-40",
        quantity=1,
        installed_at="tip-adjuster-set",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Only closes the block's top slit: block, both jaws and the pinched adjuster ride the "
            "platform as one and never move relative to each other, and the adjuster's cup drag "
            "acts about the adjuster axis, perpendicular to this screw, reacted by jaw friction "
            "on the adjuster thread, so no operating torque acts about the pinch axis"
        ),
        axial_capture=(
            "fillister head on the block's +X face over the drilled-to-slot near-jaw clearance; "
            "threads into the far jaw only (>= 1.5D)"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py pinch_screw placement and 'pinch screw in the "
            "cross-bore' mates, head-on-+X assert; cone_tip_block_spec PINCH_THREAD, "
            "WORST_PINCH_ENGAGEMENT_MM; config/parts/vn-cone-tip-pinch-screw.yaml "
            "installation_notes; CONE_CRANK_STEPS 3 (tip-adjuster-set 'TIGHTEN MHA-VN-018 ACROSS "
            "THE SLIT'); CONSUMABLES_NOTES '#4-40 ... SCREWS: SNUG'"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-collar-set-screw",
        assembly="dt_drive_train",
        member="vn_cone_tip_collar",
        receiver="dt_cone_gear_shaft",
        thread="#2-56",
        quantity=1,
        installed_at="tip-adjuster-set",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "MHA-VN-016 turns as one with MHA-DT-004 (its set screw on the Sec4 D-flat) and rubs nothing "
            "that moves relative to it: the D-flat-keyed stack floats a feeler gap south of it "
            "and the tip block stands clear north (collar-to-block air), so no friction torque "
            "acts about the radial set-screw axis; stack float thrust and start/stop inertia "
            "load the screw across its axis"
        ),
        axial_capture=(
            "collar's own hex-socket cup-point set screw bearing on the shaft's Sec4 D-flat; "
            "collar set one COLLAR_FEELER off T006"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py tip_collar placement + 'tip collar set screw on the "
            "D-flat' parallel mate; cone_tip_collar_spec SET_SCREW_THREAD; cone_stack_end_play "
            "(collar and block never touch); CONE_CRANK_STEPS 2 (post-and-tip-block 'SLIP MHA-VN-016 "
            "ON') and 3 (tip-adjuster-set 'LOCK ITS SET SCREW ON THE FLAT')"
        ),
    ),
    Joint(
        id="dt-drive-train/handle-pivot-screw",
        assembly="dt_drive_train",
        member="dt_crank_handle_pivot_screw",
        receiver="dt_crank_arm",
        thread="#4-40",
        quantity=1,
        installed_at="crank-handle-fitted",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "The oak MHA-DT-008 spins on the oiled shoulder once per crank turn relative to the arm, "
            "and its bonded MHA-DT-035 cup floor bears on the screw head when the handle is pulled "
            "out (end play 0.25-1.0), so bore and head friction drag the screw about its own "
            "axis in one sense for each crank direction"
        ),
        axial_capture=(
            "shoulder seated tight on the arm's outboard face (ArmSeat on HandleSeat); thread "
            "through the arm's #4-40 tap, tip filed flush with the inboard face"
        ),
        lock=Lock.THREADLOCKER_ONLY,
        lock_step="crank-handle-fitted",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 7 (crank-handle-fitted 'THREAD IT INTO "
            "MHA-DT-006 WITH LOCTITE 222, SHOULDER TIGHT; ... FILE THE TIP FLUSH'), CONSUMABLES_NOTES; "
            "build_dt_drive_train_assembly.py handle_screw placement and 'MHA-DT-032 shoulder seated' "
            "mates; crank_handle_pivot_screw_spec THREAD_SIZE; crank_arm_spec "
            "HANDLE_PIVOT_HOLE_SPEC; policy Named exceptions MHA-DT-035 ('the head bears on the floor')"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/cone-pivot-screw-in-base",
        assembly="ha_harmonic_analyzer",
        member="vn_cone_pivot_screw",
        receiver="fr_harmonic_base",
        thread="#10-24 UNC",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("other-base-mounting"),
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "MHA-DT-020, carrying the whole cone set and crank, swings on the oiled shoulder out to "
            "the MHA-VN-015 stop and back at every zeroing (CHECKS 4/5), dragging the shoulder "
            "about the screw axis one way then the other; in running, the crank and mesh "
            "reaction on the knob-clamped platform also bears on the shoulder"
        ),
        axial_capture=(
            "shoulder bottomed on the base top, thread tail in the blind #10-24 UNC-2B base seat; "
            "head stands 0.25 above the plate (no head clamp on the platform)"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py pivot_screw placement ('base-threaded STATIC ... "
            "shoulder bottoms on the base top') and PSCREW_* asserts; vn_cone_pivot_screw_spec.THREAD; "
            "draw_dt_drive_train_assembly.py INTERFACE_NOTES ('BASE MHA-FR-001 ... RECEIVES MHA-VN-014'), "
            "CHECKS 4 ('SWING THE CONE SET ON MHA-VN-014 TO THE MHA-VN-015 STOP'), rig_steps "
            "other-base-mounting"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/cone-lock-knob-in-base",
        assembly="ha_harmonic_analyzer",
        member="vn_cone_lock_knob",
        receiver="fr_harmonic_base",
        thread="1/4-20 UNC",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("other-base-mounting"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Hand-set operator clamp of a stationary setting: tightened with the cone set engaged "
            "and loosened only to swing it (CHECKS 4); in running the platform does not move, "
            "and its mesh reaction reaches the stud across its axis (stud in the platform notch) "
            "and as friction under the head, not as torque about the stud axis"
        ),
        axial_capture=(
            "collarless knurled head bears on the MHA-DT-020 top; stud through the platform notch "
            "into the blind 1/4-20 UNC-2B base seat"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py lock_knob placement ('platform clamp, engaged end'), "
            "require_lock_seat_fit; cone_lock_knob_spec THREAD / require_seat_fit; "
            "draw_dt_drive_train_assembly.py CHECKS 4 ('LOOSEN MHA-VN-013 ... TIGHTEN MHA-VN-013'), "
            "INTERFACE_NOTES"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/swing-stop-screw-in-base",
        assembly="ha_harmonic_analyzer",
        member="vn_swing_stop_screw",
        receiver="fr_harmonic_base",
        thread="#4-40",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("other-base-mounting"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Screwed fully home with its head seated on the base top and carrying no member: "
            "engaged, the platform edge stands >= 2.0 clear of it; at zeroing the swung "
            "platform's edge only bears on the side of the head, across the screw axis"
        ),
        axial_capture="head seated on the base top; thread in the blind #4-40 base seat",
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py stop_screw placement, _STOP_ENGAGED_GAP >= 2.0 assert, "
            "require_stop_seat_fit; swing_stop_screw_spec (screwed fully home, the head is the "
            "stop); draw_dt_drive_train_assembly.py CHECKS 4 comment, INTERFACE_NOTES"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/spring-foot-screw-in-base",
        assembly="ha_harmonic_analyzer",
        member="vn_foot_screw",
        receiver="fr_harmonic_base",
        thread="#4-40",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("rig-seats-transferred"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Clamps the MHA-DT-024 foot pad to the base. The spring's load lies in the strap swing "
            "plane through the screw axis (blade preloaded on the parked MHA-DT-014 flank, deflected "
            "further only while the pinion is engaged for zeroing), so it bends the foot about "
            "the bank axis and reaches the screw as tension and shear, not as torque about its "
            "vertical axis"
        ),
        axial_capture=(
            "narrow fillister head on the spring foot pad through its #4 clearance hole into "
            "the transferred blind #4-40 UNC-2B base seat (tapped_bottoming)"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py spring_foot_screw placement, _FOOT_SCREW_XZ, "
            "_require_clearance_size('pinion spring foot'), _require_tapped_thread('foot-screw "
            "base seat'); vn_foot_screw_spec.THREAD; draw_dt_drive_train_assembly.py rig_steps "
            "rig-seats-transferred ('FIT ... 1X MHA-VN-020'), INTERFACE_NOTES"
        ),
    ),
    # --- drive_train (MHA-DT-000): cylinder bank and pinion rig, and their screws into the base ---
    Joint(
        id="dt-drive-train/arbor-apex-set-screw",
        assembly="dt_drive_train",
        member="vn_arbor_set_screw",
        receiver="dt_arbor_pedestal",
        thread="#4-40 UNC",
        quantity=2,
        installed_at="cylinder-bank-located",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "Each screw is the only thing holding the stationary arbor MHA-DT-013 in its pedestal; "
            "20 oiled MHA-DT-012 gears spin on that arbor (check 3), so their journal drag, which "
            "reverses with crank direction and hand zeroing (check 5), reaches the screw through its cup point"
        ),
        axial_capture="cup point tightened into a #43 spot drilled in MHA-DT-013 through the crown tap; screw rides only its own #4-40 thread in the crown",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py BANK_STEPS 9E ('RUN THE BACK MHA-VN-034 IN TIGHT, THEN THE FRONT ONE'); "
            "build_dt_drive_train_assembly.py arbor set screw placement (_lock_static, ~L3819-3831); "
            "dt_arbor_pedestal_spec.SET_SCREW_HOLE_SPEC (#4-40 tapped, through_next); arbor_set_screw_spec docstring; "
            "dt_cylinder_gear_shaft_spec.DRAWING_NOTES; CONSUMABLES_NOTES ('#4-40 ... SCREWS: SNUG', no threadlocker)"
        ),
    ),
    Joint(
        id="dt-drive-train/pinion-cam-set-screw",
        assembly="dt_drive_train",
        member="dt_pinion_cam",
        receiver="dt_pinion_lift_rod",
        thread="M2.5 x 0.45 (ISO 4026 M2.5 X 5 flat-point set screw supplied with MHA-DT-023, 6H tap in the cam)",
        quantity=2,
        installed_at="cams-and-lever-fitted",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "The set screw is the only drive between the lift rod MHA-DT-017 and each eccentric cam: the lever turns "
            "the rod ~-72 deg to lift the MHA-DT-025 follower pins against MHA-DT-024, and the spring drives the cams "
            "back to park, so the torque the screw carries reverses every engage/park cycle"
        ),
        axial_capture=(
            "flat point clamped on the plain round Ø6.35 rod (slip-fit Ø6.40 bore, no flat or spot); the collars "
            "are set on 66MA leaves 0.25/0.90 off the MHA-DT-018 blocks and also carry the rod's axial location"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py rig_steps 'cams-and-lever-fitted' (set screw loose) and 'cam-collars-set' "
            "(pinion_rig_fitup COLLAR SET: 'LOCK SCREWS'); dt_pinion_cam_spec.DRAWING_NOTES; pinion_cam_geometry "
            "SET_SCREW_Z/TAP_DRILL_DIA; build_dt_drive_train_assembly.py pinion cam mates (~L5805-5841, 'set-pin anti-spin')"
        ),
    ),
    Joint(
        id="dt-drive-train/keeper-eye-anchor-screw",
        assembly="dt_drive_train",
        member="vn_fillister_screw",
        receiver="dt_crank_arm",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="crank-hub-fitted",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "The screw alone clamps the straight tail of the MHA-DT-028 keeper eye on the continuously turning crank "
            "arm; the MHA-VN-035 chain hangs from the eye loop beside the screw, and as the arm turns, gravity on "
            "the chain swings round the arm frame, so its pull on the loop puts a moment about the screw axis "
            "that reverses once per crank turn"
        ),
        axial_capture="fillister head clamps the 1.0 brass eye tail on the arm's outboard face; shank in the arm's #4-40 through tap, tip short of the inboard face",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 6 ('CLAMP MHA-DT-028 UNDER MHA-VN-006'); "
            "build_dt_drive_train_assembly.py anchor block (~L722-766: ANCHOR_THREAD_ENGAGEMENT, through tap) and "
            "placement (~L4400-4414); crank_pin_eye_spec docstring (tail clamped under the screw); CONSUMABLES_NOTES"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/arbor-pedestal-hold-down",
        assembly="ha_harmonic_analyzer",
        member="vn_pedestal_hold_down_screw",
        receiver="fr_harmonic_base",
        thread="#8-32 UNC",
        quantity=2,
        installed_at=dt_drive_train_steps.step_ref("cylinder-bank-located"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Clamps each cast MHA-DT-002 pedestal's ledge to base MHA-FR-001; neither moves in operation (the arbor is "
            "fixed by MHA-VN-034). The gears' journal drag acts about the horizontal arbor axis, perpendicular to "
            "this vertical screw, so it reaches the screw only as tension/shear through the foot; no member "
            "rotates on or about the screw axis"
        ),
        axial_capture="fillister head on the pedestal's 18-long ledge through a #8 close-clearance hole; >=1.5D thread in a transfer-tapped bottoming seat",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py BANK_STEPS 9A/9C ('TIGHTEN MHA-VN-032 AND RECHECK') and INTERFACE_NOTES; "
            "build_dt_drive_train_assembly.py ~L3377-3410 (_require_tapped_thread 'pedestal hold-down base seat', "
            "engagement checks) and pattern ~L5602-5621; arbor_pedestal_spec SCREW_HOLE_SPEC/SCREW_Z"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/pinion-block-hold-down",
        assembly="ha_harmonic_analyzer",
        member="vn_slotted_screw",
        receiver="fr_harmonic_base",
        thread="#8-32 UNC",
        quantity=4,
        installed_at=dt_drive_train_steps.step_ref("rig-seats-transferred"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Two screws clamp each MHA-DT-018 pivot block to base MHA-FR-001; the blocks never move in operation. The "
            "rocking pivot shaft and lift rod turn in the blocks about horizontal axes along the bank, "
            "perpendicular to these vertical screws, and the two-screw spacing carries any yaw as a shear couple, "
            "so no operating torque acts about a screw axis"
        ),
        axial_capture="fillister head on the block top through a #8 normal-clearance hole; 11.25 (2.7D) in a transfer-tapped bottoming seat",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py rig_steps 'rig-seats-transferred' ('FIT {slotted}X MHA-VN-019') and INTERFACE_NOTES; "
            "build_dt_drive_train_assembly.py ~L3159-3192 (block screw engagement, _BLOCK_SCREW_XZ) and 2x2 grid pattern "
            "~L5582-5601; build_dt_pinion_pivot_block.py SCREW_HOLE_SPEC"
        ),
    ),
    # --- channel (MHA-CH-000): its screws into frame parts (nothing threads inside the bank) ---
    Joint(
        id="ha-harmonic-analyzer/north-pivot-bracket-hold-down",
        assembly="ha_harmonic_analyzer",
        member="vn_pedestal_hold_down_screw",
        receiver="fr_rocker_arm_support",
        thread="#8-32",
        quantity=2,
        installed_at=ch_channel_assembly_steps.step_ref("north-ear-datum"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the north pivot_bracket foot to the stationary rocker_arm_support "
            "rail (neither moves in operation); two screws per foot, so any moment "
            "about one screw's axis is reacted in shear by the other screw and the "
            "rocker bank's oscillating drag acts about the pivot-shaft axis (Z), "
            "perpendicular to the vertical screw axes"
        ),
        axial_capture="fillister head on the bracket foot top face; thread in a bottoming-tapped #8-32 2B blind seat transferred through the foot",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py BRACKET_SCREW_XZ loop + header (MHA-VN-032, #8-32 x 3/4 fillister, two per foot); "
            "vn_pedestal_hold_down_screw_spec.THREAD; rocker_bracket_seat_layout.SEAT_SPEC (tapped_bottoming #8-32 2B); "
            "draw_dt_drive_train_assembly.py BANK_STEPS step north-pivot-bracket-set (MHA-DT-000 STEP 10: 'DRILL AND TAP THE RAIL "
            "THROUGH ITS FEET ... UNSCREW IT AND LIFT IT OFF'); draw_ch_channel_assembly.py step north-ear-datum (MHA-CH-000 "
            "STEP 3: 'SLIDE THE ... EAR SOUTH OVER THE NORTH JOURNAL, SCREW IT DOWN AND RECHECK ITS S-OFFSET Y'); "
            "ch_channel_assembly_steps.NORTH_BRACKET_SET_REF; "
            "config parts/vn-pedestal-hold-down-screw.yaml (90280A197)"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/south-pivot-bracket-hold-down",
        assembly="ha_harmonic_analyzer",
        member="vn_pedestal_hold_down_screw",
        receiver="fr_rocker_arm_support",
        thread="#8-32",
        quantity=2,
        installed_at=ch_channel_assembly_steps.step_ref("south-bracket-spring-set"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the south pivot_bracket foot to the stationary rocker_arm_support "
            "rail (neither moves in operation); two screws per foot react any moment "
            "about one screw's axis in shear through the other, and the rocker bank's "
            "oscillating drag and end thrust act about/along the pivot-shaft axis (Z), "
            "perpendicular to the vertical screw axes"
        ),
        axial_capture="fillister head on the bracket foot top face; thread in a bottoming-tapped #8-32 2B blind seat transferred through the blade-set foot",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py BRACKET_SCREW_XZ loop + header; rocker_bracket_seat_layout.SEAT_SPEC; "
            "draw_ch_channel_assembly.py _fitup_steps 'south-bracket-spring-set' (MHA-CH-000 STEP 5: 'TRANSFER ITS SEATS ... "
            "SCREW DOWN, PULL THE BLADE'), left screwed down through 'shaft-cut-to-fit' (STEP 6: 'UNSCREW THE NORTH ... "
            "AND SLIDE IT OFF NORTH; DRAW THE SHAFT NORTH ... REFIT AS STEP 3; "
            "SOUTH EAR LEFT AT ITS STEP 5 SETTING')"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/fulcrum-keeper-screw-in-top-frame",
        assembly="ha_harmonic_analyzer",
        member="vn_frame_side_screw",
        receiver="fr_top_frame",
        thread="#8-32",
        quantity=2,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the only fastener of each fulcrum_keeper, which carries the end of the "
            "fulcrum_shaft that the 20 oscillating channel_levers rock on (shaft free "
            "in the Ø6.50 ball bore); the shaft-end reaction is 14.75 off the screw "
            "along the shaft, so the reversing horizontal lever/bar loads apply a "
            "reversing torque about the single screw's vertical axis, and no dowel or "
            "second screw reacts it"
        ),
        axial_capture="slotted narrow-fillister head seated flush in the keeper foot counterbore (CBORE_DEPTH 3.9624); thread in top_frame KeeperTaps #8-32 x 10 blind",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py keeper loop (frame-side-screw at FULCRUM_SHAFT_Z +- KEEPER_SCREW_Z_OFF) + header "
            "('foot screws down into the rail's tapped #8-32 holes'); ch_fulcrum_keeper_spec.py docstring/SCREW_X/"
            "SCREW_HOLE_SPEC/BORE_DIA + DRAWING_NOTES 3; build_fr_top_frame.py KEEPER_TAP_SPEC (#8-32 blind, ThreadDepth 10) "
            "step 15 'KeeperTaps'; config parts/vn-frame-side-screw.yaml (90280A194); no printed install step found"
        ),
    ),
    # --- summing, pen and the top level (the channel spring anchors) ---
    Joint(
        id="sm-summing/knife-hanger-in-mount",
        assembly="sm_summing",
        member="vn_knife_hanger_stud",
        receiver="sm_knife_mount",
        thread="1/2-13 UNC",
        quantity=2,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the thread is the only support of the knife-edge bearing block on which the summing lever "
            "rocks back and forth (freed lever_rock DOF); the block hangs MOUNT_GAP 0.25 below the casting "
            "underside, so nothing clamps it and the thread engagement (11.3735 mm, asserted) also sets the "
            "knife height -- rocking friction and reversing lever loads reach the unclamped thread"
        ),
        axial_capture=(
            "hex head (91247A720) seated on the knife-hanger washer on the crossbar top; bolt passes the "
            "crossbar's O13.49 clearance hole and engages 11.37 of the 12.0-deep blind tap; the block is "
            "NOT drawn up against the casting (0.25 gap), so there is no joint preload"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_sm_summing_assembly.py: module docstring, HANGER_STUD_Y/KNIFE_MOUNT_THREAD_ENGAGEMENT, "
            "_assert_knife_hanger_stack; build_sm_knife_mount.py: MOUNT_GAP, STUD_TAP_SPEC; "
            "sm_knife_mount_spec.py DRAWING_NOTES (TAP 1/2-13 UNC-2B X 12.0); vn-knife-hanger-stud.yaml (91247A720)"
        ),
    ),
    Joint(
        id="sm-summing/boss-hook-in-lever",
        assembly="sm_summing",
        member="vn_boss_hook",
        receiver="sm_summing_lever",
        thread="#10-24 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the eyebolt rides the rocking summing lever and carries the counter-spring tension, which cycles "
            "with every rock; the spring loop working in the open eye and any off-plane pull twist the eye "
            "about the shank, and the spring pulls the anchor out of its tap"
        ),
        axial_capture=(
            "thread only: trimmed 9490T1 shank engages the full 19.05 boss height (thread starts at the boss "
            "top face, cut end at the boss underside); no shoulder, nut or head seats -- the wire bend has "
            "the shank diameter"
        ),
        lock=Lock.THREADLOCKER_ONLY,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_sm_summing_assembly.py: _assert_counter_spring_hang, build() 'boss-hook keyed' lock_mate "
            "(a CAD mate, not hardware); build_sm_summing_lever.py: _counter_anchor_tap ('NO NUT: this tap is "
            "the nut'); sm_summing_lever_spec.COUNTER_HOLE_SPEC; stock_anchor_geom.ANCHOR_9490T1; vn_boss_hook_spec.py; "
            "cad/config/parts/vn-boss-hook.yaml installation_notes ('THREAD DIRECTLY INTO ... TAPPED BOSS; NO NUT. "
            "CLOCK EYE TO PULL PLANE. USE REMOVABLE MEDIUM-STRENGTH THREADLOCKER.')"
        ),
    ),
    Joint(
        id="sm-summing/gooseneck-spring-screw",
        assembly="sm_summing",
        member="sm_gooseneck",
        receiver="sm_gooseneck",
        thread="#6-32 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the counter spring's double-loop top eye encircles the exposed shank coaxially and swings with "
            "every rock of the summing lever, so its rubbing friction acts directly about the screw axis in "
            "alternating senses"
        ),
        axial_capture=(
            "slotted round-head #6-32 x 14 set to 8.00 +/-0.25 exposed shank in the 6.0-deep tap in the "
            "brazed end plug; the head does not seat on the end face (it is the eye retainer), so the screw "
            "carries no clamp preload"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "sm_gooseneck_spec.py DRAWING_NOTES items 3-5 (BRAZE PLUG, TAP #6-32 X 6.0, SPRING SCREW ... 8.00 "
            "+/-0.25 SHANK EXPOSED ... MODELED INTEGRAL); build_sm_gooseneck.py docstring + 'EndScrew' revolve; "
            "sm_gooseneck_geom.SCREW_SHANK_LEN/PLUG_T; build_sm_summing_assembly.py _assert_counter_spring_top_hang"
        ),
    ),
    Joint(
        id="pn-pen/hanger-screw-in-hanger",
        assembly="pn_pen",
        member="vn_hanger_screw",
        receiver="pn_pen_hanger",
        thread="#8-32 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the single screw is the only thing holding the hanger to the wheel bar, and the pen rod "
            "reciprocates up and down through the hanger's guide block 6 mm across from the screw axis "
            "(guide x +3, screw x -3), so the rod's sliding friction applies a reversing moment about the "
            "screw axis"
        ),
        axial_capture=(
            "hex head (93075A194, #8-32 x 1/2) on the wheel-bar back face; shank through the bar's #8 close "
            "clearance hole into the strap tap, clamping bar between head and strap; thread protrudes past "
            "the strap front"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_pn_pen_assembly.py: M6.10 fastener block (HANGER_SCREW_POS, HANGER_THREAD_PROTRUSION), "
            "build() hanger-screw mates; build_pn_pen_hanger.py: SCREW_TAP_SPEC HoleSpec('tapped','#8-32'), "
            "SCREW_HOLE_XY; mg_wheel_bar_geom.PEN_HANGER_HOLE_SPEC (clearance #8); vn-hanger-screw.yaml (93075A194)"
        ),
    ),
    Joint(
        id="pn-pen/thumb-screw-in-stirrup",
        assembly="pn_pen",
        member="vn_pen_set_screw",
        receiver="pn_pen_frame",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the thumb screw rides the reciprocating pen carriage and its flat tip holds the marker in the "
            "v-block groove; the pen's up/down travel reverses the nib drag on the paper and the marker's "
            "inertia ALONG the screw axis every stroke, cycling the only preload the joint has (a hand-set "
            "clamp, but not a stationary one)"
        ),
        axial_capture=(
            "knurled thumb screw (99607A213) threaded up through the bottom-rail tap; its flat tip bears on "
            "the marker barrel underside (tangent), reacting against the groove roof -- the tip contact is "
            "the only preload"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_pn_pen_assembly.py: module docstring ('pen-set-screw threads UP through its bottom rail and "
            "presses the marker'), SET_SCREW_POS/_SCREW_TIP_LOCAL_Y, riders lock_mate (CAD only); "
            "build_pn_pen_frame.py: SET_SCREW_TAP_SPEC HoleSpec('tapped','#4-40'); pn_pen_frame_spec.py note 2; "
            "vn-pen-set-screw.yaml (99607A213)"
        ),
    ),
    Joint(
        id="pn-pen/v-block-set-screw-on-rod",
        assembly="pn_pen",
        member=UNMODELLED,
        receiver="pn_pen_v_block",
        thread="unresolved: Ø2.5 drill, thread or fit to suit the set screw at assembly",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the side set screw is the only thing pinning the v-block, and with it the marker, to the "
            "bottom of the reciprocating pen rod; the block rides the rod's up/down travel and the nib "
            "drag on the paper reverses with pen direction, so the load the screw carries reverses every "
            "stroke"
        ),
        axial_capture=(
            "none modelled: the rod drops 13 into the block's rod bore and the block is lock-mated to the "
            "rod; the set screw the drawing calls for is not a part, so no BOM row, length, point or lock "
            "exists"
        ),
        lock=Lock.NONE,
        evidence=(
            "pn_pen_v_block_spec.py: comment 'a side set screw (front face, over that bore) pins it', "
            "SCREW_HOLE_DIA/SCREW_HOLE_XY, DRAWING_NOTES ('ROD SET-SCREW HOLE Ø2.5 DRILL THRU ... "
            "THREAD/FIT TO SUIT SET SCREW AT ASSEMBLY'); build_pn_pen_assembly.py module docstring "
            "('a side set screw pins it in the real device', 'lock-mated to the rod'); "
            "build_pn_pen_v_block.py docstring ('a small front hole for the rod set screw')"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/channel-anchor-in-summing-plate",
        assembly="ha_harmonic_analyzer",
        member="vn_spring_hook",
        receiver="sm_summing_lever",
        thread="#6-32 UNC",
        quantity=1,
        per_channel=True,  # build_ch_channel_assembly places one per range(CHANNELS)
        installed_at="",
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "per-channel calibration unscrews each anchor to set its spring preload (5% of preload per turn); "
            "the anchor also rides the rocking summing lever under a channel-spring load that cycles with the "
            "crank, and that spring pulls the anchor out of its tap"
        ),
        axial_capture=(
            "thread only: the Ø3.175 neck shoulders on the plate top face as a DOWN-stop when fully seated, "
            "but calibration backs it off that shoulder (up to 1.143 mm / 1 counted turn), leaving 3.49 mm "
            "(~4.4 threads) of plate engagement and no seated face; the supplied hex nut is discarded"
        ),
        lock=Lock.THREADLOCKER_ONLY,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ha_harmonic_analyzer_assembly.py module docstring (channel spring anchors thread DOWN into "
            "the 20 #6-32 taps); build_ch_channel_assembly.py _assert_spring_mount; vn_spring_hook_spec.py "
            "docstring + DRAWING_NOTES ('DISCARD THE SUPPLIED HEX NUT; NO NUT IS INSTALLED'), "
            "ADJUSTMENT_TRAVEL_MM/ADJUSTMENT_TURNS; sm_summing_lever_spec.HOLE_SPEC; stock_anchor_geom.ANCHOR_9489T111; "
            "cad/config/parts/vn-spring-hook.yaml installation_notes ('RUN DOWN UNTIL NECK SEATS ON PLATE TOP; BACK "
            "OUT 1 TURN MAX TO SET CHANNEL PRELOAD. CLOCK EYE TO SPRING PULL PLANE. USE REMOVABLE MEDIUM-STRENGTH "
            "THREADLOCKER.')"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/stick-stop-thumbscrew",
        assembly="ha_harmonic_analyzer",
        member="ha_measuring_stick_stop",
        receiver="ha_measuring_stick_stop",
        thread="unstated (knurled thumbscrew, modelled integral)",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp on a loose gauge: the stop is pinched at a chosen mark on the measuring "
            "stick, which is parked on the deck and is not part of any running chain -- no operating torque "
            "or motion reaches the thumbscrew axis"
        ),
        axial_capture=(
            "thumbscrew runs up through the block's 4.0 floor; its tip pinches the stick against the window "
            "roof; head hangs under the block"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ha_measuring_stick_stop.py module docstring (thumbscrew screws UP through the floor to pinch "
            "the bar; head merged), SLOT_FLOOR/HEAD_H; ha-measuring-stick-stop.yaml process; "
            "build_ha_harmonic_analyzer_assembly.py STOP_POS block"
        ),
    ),
    # --- magnifier ---
    Joint(
        id="ha-harmonic-analyzer/magnifying-bracket-screws",
        assembly="ha_harmonic_analyzer",
        member="vn_magnifying_bracket_screw",
        receiver="sm_summing_lever",
        thread="#2-56 UNC",
        quantity=2,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamp the bracket flange to the summing lever; both rock together "
            "about the knife edge without relative motion at the seat. Two "
            "screws react the bracket moment as a shear couple, not operating "
            "spin friction about either screw axis"
        ),
        axial_capture="fillister heads on the bracket counterbore floors; shanks pass normal #2 clearance into the lever's blind bottoming #2-56 seats",
        lock=Lock.NONE,
        evidence=(
            "build_mg_magnifier_assembly.py BRACKET_SCREW_POSITIONS loop, screws locked "
            "to bracket; magnifying_bracket_joint_layout.CLEARANCE_SPEC/TAP_SPEC"
        ),
    ),
    Joint(
        id="mg-magnifier/wheel-axle-nut",
        assembly="mg_magnifier",
        member="vn_wheel_axle_nut",
        receiver="mg_wheel_axle",
        thread="not specified (hex nut AF 8 x 3 on the O5 stud; 'thread not modelled'; axle drawing calls no thread) [plausibly M5]",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the nut retains the magnifying wheel, which the lever-wire (WIRE 1) turns back and forth every "
            "harmonic cycle (yoke-coupled to the rocking lever); the hub's outboard face rubs the O9 washer "
            "the nut seats on, so reversing friction drag reaches the nut thread; the uniform O5 stud has "
            "no shoulder, so the nut's own position also sets the hub end play (ADJUSTER character too)"
        ),
        axial_capture="nut seats on the O9 x 1 washer at stud y=14 (washer modelled as the axle's integral 'Collar' feature), stud tip 3 proud",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build ('wheel-axle nut' place + lock_mate 'wheel-axle nut locked to the axle'); "
            "build_vn_wheel_axle_nut.py docstring; mg_wheel_axle_spec.py NUT_AF/NUT_H/NUT_BORE_DIA/COLLAR_*; "
            "build_mg_wheel_axle.py docstring (hub 3..13, washer 13..14, nut 14..17); config parts/vn-wheel-axle-nut.yaml process"
        ),
    ),
    Joint(
        id="mg-magnifier/clamp-thumb-screw",
        assembly="mg_magnifier",
        member="vn_thumb_screw",
        receiver="mg_magnifying_clamp",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp: pinches the sliding clamp block onto the lever rod at the chosen "
            "magnification radius; block, rod, vertical rod and fixture then ride the lever as one rigid "
            "body (lock mates), the lever rocks about the knife line (machine Z) perpendicular to the "
            "screw axis (machine Y), and the wire pull on the offset vertical rod makes a moment about the "
            "lever-rod axis (X), so no operating torque acts about the screw axis"
        ),
        axial_capture="tip bears on the Ø6 lever rod through the tapped hole that breaks into the lever bore (modelled backed-out, tip tangent)",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build ('thumb-screw (clamp)', lock_mate 'thumb-screw locked to clamp'; "
            "docstring 'Documented simplifications'); build_mg_magnifying_clamp.py ScrewHole HoleSpec('tapped','#4-40'); "
            "mg_magnifying_clamp_spec.py DRAWING_NOTES; diag_mcmaster_thumb.py THUMB_SPECS['91882A221']"
        ),
    ),
    Joint(
        id="mg-magnifier/fixture-thumb-screw",
        assembly="mg_magnifier",
        # thumb_screw's one placed instance is the magnifying-clamp screw; the
        # builder omits this second one, so the stem does not cover it.
        member=UNMODELLED,
        receiver="mg_output_fixture",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp: locks the output-fixture collar at its set height on the vertical rod "
            "(sets the trace's vertical placement); collar and rod never move relative in operation, and the "
            "wire tension acts along the rod (Y) at the hook in front of the rod, i.e. no moment about the "
            "radial screw axis (Z)"
        ),
        axial_capture="tip bears on the Ø5 vertical rod through the tapped entry wall of the radial cross hole (screw NOT placed in mg-magnifier.SLDASM)",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_output_fixture.py docstring ('a small reeded screw (separate thumb-screw part) locks it'); "
            "mg_output_fixture_spec.py CROSS_HOLE_SPEC + DRAWING_NOTES 3 (TAP THE ENTRY WALL ONLY #4-40 UNC); "
            "config parts/vn-thumb-screw.yaml quantity 2; dimensions.yaml ch20 'Thumb screw ... (x2: clamp + output fixture)'; "
            "build_mg_magnifier_assembly.py docstring ('the output fixture's clamp screw is omitted')"
        ),
    ),
    Joint(
        id="mg-magnifier/wheel-bar-clamp-screws",
        assembly="mg_magnifier",
        member="vn_clamp_screw",
        receiver="sh_column_clamp_back",
        thread="#8-32 UNC",
        quantity=2,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "close the stack wheel-bar -> front arc -> back arc around the fixed front column; bar, arcs and "
            "column never move relative in operation; the only operating load (the wheel's small reversing "
            "drag/wire pull on the bar) is reacted by the two screws 35 apart as a shear couple across their "
            "axes, not as torque about either screw axis"
        ),
        axial_capture="fillister head on the wheel-bar front face; shank through #8 clearance in bar + front arc; threads into the back arc's tapped ears",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build (clamp-screw seed + lock_mate + linear_component_pattern x2, CLAMP_SCREW_X); "
            "build_sh_column_clamp_back.py HOLE_SPEC tapped #8-32; sh_column_clamp_front_geom.py EAR_HOLE_SPEC clearance #8; "
            "sh_column_clamp_front_spec.py DRAWING_NOTES; mg_wheel_bar_geom.py CLAMP_HOLE_SPEC; diag_mcmaster_fillister.py 90280A201"
        ),
    ),
    # --- paper_drive (MHA-PD-000, pd_paper_drive_assembly_steps) ---
    Joint(
        id="pd-paper-drive/clamp-screw-in-back-arc",
        assembly="pd_paper_drive",
        member="vn_clamp_screw",
        receiver="sh_column_clamp_back",
        thread="#8-32 UNC",
        quantity=4,
        installed_at="bar-clamped",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps support bar + front arc + back arc around a stationary frame column; none of these parts moves in operation, the head sits 0.2 sub-flush in a bar counterbore so the sliding platen never touches it, and the platen's X-wise slide drag reaches the pair of screws per column only as shear across their Z axes, never as torque about them",
        axial_capture="fillister head seated in the support_bar front counterbore (CLAMP_CBORE_DEPTH, 0.2 recess); shank through bar + column_clamp_front #8 clearance; threads into column_clamp_back's through #8-32 tap",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence="build_pd_paper_drive_assembly.py:build (clamp-screw seeds + 'support clamp-screw pattern') and _assert_fastener_stacks (90280A201 clamps); draw_pd_paper_drive_assembly._step_text 'bar-clamped'; build_sh_column_clamp_back.HOLE_SPEC tapped #8-32; build_pd_support_bar.CLAMP_HOLE_SPEC/CLAMP_HOLE_X; sh_column_clamp_front_geom.EAR_HOLE_SPEC",
    ),
    Joint(
        id="pd-paper-drive/clip-screw-in-platen",
        assembly="pd_paper_drive",
        member="vn_fillister_screw",
        receiver="pd_platen",
        thread="#4-40 UNC",
        quantity=4,
        installed_at="clips-fitted",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps each brass paper clip to the platen, and both travel together as one body. The clip's spring-rail reaction acts along the screw axis (preload only), and two screws per clip stop the clip turning, so no operating torque acts about either screw axis",
        axial_capture="fillister head on the clip's integral seat boss (SCREW_SEAT_STACK); shank through the clip #4 clearance into the platen's through #4-40 tap, 4.0 mm engagement, tip flush with the platen back",
        lock=Lock.NONE,
        evidence="build_pd_paper_drive_assembly.py:build ('platen clip-screw grid') and _assert_fastener_stacks (clip #4-40 engagement, tip flush); draw_pd_paper_drive_assembly._step_text 'clips-fitted'; pd_platen_spec.SOCKET_SPEC tapped #4-40 through; build_pd_platen_clip.SCREW_SEAT_STACK",
    ),
    Joint(
        id="pd-paper-drive/guide-screw-in-guide",
        assembly="pd_paper_drive",
        member="vn_fillister_screw",
        receiver="pd_platen_guide",
        thread="#4-40 UNC",
        quantity=10,
        installed_at="guides-screwed",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps the platen to its two guide rails, which move together as one body. The rails slide on the support bar's top edge, and that drag runs along X, transverse to the screw axes (Z), shared in shear by 5 screws per rail. No operating torque acts about any screw axis",
        axial_capture="fillister head 0.2 sub-flush in the platen front counterbore; shank through the platen #4 hole into the guide's front #4-40 tap (through, R9-64), 5.27 mm engagement, tip stopping inside the rail",
        lock=Lock.NONE,
        evidence="build_pd_paper_drive_assembly.py:build ('platen guide-screw grid') and _assert_fastener_stacks (90114A511 guide screws); draw_pd_paper_drive_assembly._step_text 'guides-screwed'; pd_platen_guide_spec.TAPPED_HOLE_SPEC; build_pd_platen_guide.GUIDE_SCREW_THREAD_ENGAGEMENT/GUIDE_SCREW_TIP_INSIDE_MIN",
    ),
    Joint(
        id="pd-paper-drive/lock-screw-in-guide",
        assembly="pd_paper_drive",
        member="vn_guide_lock_screw",
        receiver="pd_platen_guide",
        thread="#4-40 UNC",
        quantity=8,
        installed_at="platen-hung",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps each guide-lock plate to the back of its guide rail, and both travel with the platen as one body. The plate stands the fitted lock gap (0.05-0.25, R9-47) off the bar's back face and only touches if the platen is pulled forward, a load along the screw axis. Two screws per plate stop it turning, so no operating torque acts about either screw axis",
        axial_capture="button head on the 2-mm guide_lock back face; shank through the lock's 1/8 drilled hole into the guide's rear #4-40 tap (through, R9-48), tip stopping inside the rail",
        lock=Lock.NONE,
        evidence="build_pd_paper_drive_assembly.py:build ('platen lock-screw grid', LOCK_SCREW_XY); draw_pd_paper_drive_assembly._step_text 'platen-hung' (fitted loose) and 'guide-locks-set' (snug, push, tighten); vn_guide_lock_screw_spec.ENGAGEMENT_WORST; build_pd_platen_guide.HOLE_X/LOCK_SCREW_THREAD_ENGAGEMENT (4 per rail x 2 rails); pd_guide_lock_spec.HOLE_SPEC; pd_platen_guide_spec.LOCK_GAP_FIT",
    ),
    Joint(
        id="pd-paper-drive/arm-plate-screws",
        assembly="pd_paper_drive",
        member="vn_transgear_arm_plate_screw",
        receiver="pd_transgear_arm",
        thread="#8-32 UNC",
        quantity=2,
        installed_at="arm-plate-fitted",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the arm plate to the arm; the two never move relative to each other. The knob "
            "shaft's journal drag in the plate bore acts about the knob axis, offset from both screws, "
            "and the two-screw pattern reacts it as in-plane shear across both screw axes, not as "
            "torque about either one (judgement call)"
        ),
        axial_capture=(
            "82-degree oval head seated in the plate's countersink; thread through the arm's #8-32 "
            "through tap (worst-case engagement ~1.7 D), tip cut flush at arm-plate-screws-cut"
        ),
        lock=Lock.NONE,
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'arm-plate-fitted' (snug, then tighten in turn) and "
            "'arm-plate-screws-cut'; build_pd_paper_drive_assembly.py 'transgear-arm-plate-screw #' "
            "placements (PLATE_SCREW_XY); transgear_hanger_joints.PLATE_SCREW_ENGAGEMENT_WORST_D; "
            "transgear_arm_spec plate taps"
        ),
    ),
    Joint(
        id="pd-paper-drive/pivot-screw-in-bar",
        assembly="pd_paper_drive",
        member="vn_transgear_pivot_screw",
        receiver="pd_support_bar",
        thread="#8-32 UNC",
        installed_at="hanger-pivoted",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the transgear arm swings on this shoulder screw: down to unlatch for a gear change, up to "
            "re-mesh, and it rocks within the latch play when the feed drive reverses. The arm's "
            "friction on the shoulder and under the head acts about the screw axis, in both senses"
        ),
        axial_capture=(
            "shoulder bottomed on the bar's back face with the MHA-PD-020 spacer pressed on it flush; the "
            "MHA-VN-049 spring under the head holds the arm on the spacer (room 0.70-0.95, "
            "transgear_hanger_joints.SPRING_ROOM_MIN/MAX); thread in the bar's blind #8-32 tap "
            "(worst-case engagement ~0.53 D, transgear_hanger_joints.PIVOT_ENGAGEMENT_WORST_D)"
        ),
        lock=Lock.THREADLOCKER_ONLY,
        lock_step="hanger-pivoted",
        exception="U-MHA-VN-041-threadlocker",
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'hanger-pivoted' ('SEAT IT IN THE MHA-PD-007 BAR'S "
            "BLIND TAP WITH LOW-STRENGTH THREADLOCKER; THE ARM FALLS FREELY'); "
            "build_pd_paper_drive_assembly.py 'vn-transgear-pivot-screw' placement; "
            "pd_support_bar_spec.PIVOT_TAP_THREAD; transgear_hanger_joints.SPRING_ROOM_MIN/MAX, "
            "HANGER_SWING_MARGIN, LATCH_ARM_ANGLE_PLAY and PIVOT_ENGAGEMENT_WORST_D"
        ),
    ),
    Joint(
        id="pd-paper-drive/disc-screws",
        assembly="pd_paper_drive",
        member="vn_transgear_disc_screw",
        receiver="pd_rack_pinion",
        thread="#0-80 UNF",
        quantity=3,
        installed_at="disc-taps-transferred",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "fix the 120T disc to the hub flange, whose D-bore is keyed on the feed sleeve's D-flat; "
            "disc, hub and sleeve turn as one body. The drive torque acts about the pin axis, and the three screws "
            "on the flange's bolt circle carry it as shear across their own axes, never as torque "
            "about them"
        ),
        axial_capture=(
            "fillister head on the hub flange; shank through the flange clearance into the disc's "
            "#0-80 through tap transferred at assembly (worst-case engagement ~1.56 D), tip cut below "
            "the disc rear face at disc-screws-cut"
        ),
        lock=Lock.NONE,
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'disc-cluster-assembled', 'disc-taps-transferred' and "
            "'disc-screws-cut'; build_pd_paper_drive_assembly.py 'transgear-disc-screw (' placements and "
            "lock mates; pd_rack_pinion_spec.TAP_SPEC; vn_transgear_disc_screw_spec.ENGAGEMENT_WORST_D; "
            "pd_transgear_disc_hub_geometry.SCREW_COUNT"
        ),
    ),
    Joint(
        id="pd-paper-drive/knob-cup-on-journal",
        assembly="pd_paper_drive",
        member="pd_transgear_knob_cup",
        receiver="pd_transgear_knob_shaft",
        thread="none: Ø8.5 reamed slip fit, cross-pinned (R9-70 replaced the #8-32 screw)",
        installed_at="knob-stack-fitted",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "the cup rides the rear end of the knob shaft's journal, which spins in the arm plate "
            "bore with the chain-driven T24 and reverses when the paper is wound back. The cup's "
            "front face runs 0.2 behind the plate's rear boss and is the rear stop of the knob's end "
            "float, so whenever the knob is drawn forward the cup rubs the stationary boss about the "
            "shaft axis"
        ),
        axial_capture=(
            "the MHA-VN-048 1/16 x 5/8 slotted spring pin pressed through the cup and the journal, "
            "3.0 from the cup's front face, in a Ø1.6 +0.05/0 hole match-drilled with the cup set "
            "on a 0.2 feeler at the boss; the pin carries the end-float thrust and the drag in "
            "shear, its ends inside the cup's O.D."
        ),
        lock=Lock.CROSS_PIN,
        lock_part="vn_transgear_knob_cup_pin",
        lock_binds=("pd_transgear_knob_cup", "pd_transgear_knob_shaft"),
        lock_step="knob-stack-fitted",
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'knob-stack-fitted' (cup on the feeler, "
            "match-drill, press the pin); build_pd_paper_drive_assembly.py 'knob stack: cup pin "
            "locked to the knob cup' and KNOB_CUP_PIN_Z0; transgear_knob_cup_spec "
            "PIN_HOLE_FROM_FRONT and the pin-hole walls; transgear_knob_cup_pin_spec"
        ),
    ),
    Joint(
        id="pd-paper-drive/latch-hook-bracket-screws-in-bar",
        assembly="pd_paper_drive",
        member="vn_latch_hook_bracket_screw",
        receiver="pd_support_bar",
        thread="#4-40 UNC",
        quantity=2,
        installed_at="latch-hook-fitted",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamp the one-piece latch hook's base to the fixed support bar, so the hook's base "
            "does not move in operation; only its arm flexes. The latch load on the hook reaches "
            "the screw pair, 7 mm apart, as in-plane shear plus a couple the pair reacts in shear, not "
            "as torque about either screw axis (judgement call)"
        ),
        axial_capture=(
            "narrow fillister head on the hook base's 0.8 sheet; shank through the base's drilled "
            "hole into the bar's #4-40 through tap, 8.725 mm nominal engagement"
        ),
        lock=Lock.NONE,
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'latch-hook-fitted' and 'hook-pin-hole-match-drilled'; "
            "build_pd_paper_drive_assembly.py 'latch-hook-bracket-screw (x' placements; "
            "pd_support_bar_spec.BRACKET_TAP_X/BRACKET_TAP_SPEC; vn_latch_hook_bracket_screw_spec."
            "ENGAGEMENT_NOMINAL"
        ),
    ),
    Joint(
        id="pd-paper-drive/thumbnut-on-knob-shaft",
        assembly="pd_paper_drive",
        member="pd_transgear_thumbnut",
        receiver="pd_transgear_knob_shaft",
        thread="1/4-20 UNC",
        installed_at="fitup-pose-set",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the nut seats on the drive collar's pilot, faced 0.05-0.15 proud of the T24's front "
            "face, so it clamps only the collar to itself and the T24 floats free under its flange "
            "(R9-70). The drive goes T24 -> the two pressed drive pins -> collar -> the MHA-VN-037 "
            "cross pin -> shaft, but the free T24 rocks through its pin backlash at each "
            "reversal and, pushed forward, can rub the flange (machinist review of 6c385465d)"
        ),
        axial_capture=(
            "the nut's flange seat face bears on the collar pilot's faced front; 1/4-20 UNC-2B "
            "through on the shaft's die-cut front thread, finger-tight at fitup-pose-set and "
            "tightened on the pilot at collar-pinned; the flange spans the T24 bore and retains "
            "the wheel on the drive pins; removed by hand for gear swaps"
        ),
        lock=Lock.NONE,
        exception="U-MHA-PD-013-no-lock",
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'pilot-faced-to-fit', 'collar-pinned' ('THUMBNUT "
            "TIGHT ON THE PILOT') and 'fitup-accepted' (T24 free under the nut); "
            "build_pd_paper_drive_assembly.py THUMBNUT_Z0 on the pilot and 'transgear-thumbnut "
            "(seated on the collar pilot' placement; transgear_drive_collar_spec PILOT_PROUD_RANGE, "
            "NUT_PILOT_BEARING_WORST and CHAIN_OFFSET_MARGIN"
        ),
    ),
)

# Every threaded joint the build calls for, with the source occurrence that
# places or specifies it. Kept apart from JOINTS so that deleting a row is an
# OMITTED finding even where another row names the same stems. Not derived
# automatically: the build's placements cannot be enumerated offline without
# running SolidWorks, and its threaded interference contracts list only
# joints whose modelled threads overlap (no integral, unmodelled, or
# mate-only joint). test_joint_retention checks every anchor still occurs in
# its source.
REQUIRED_JOINTS: dict[str, Occurrence] = {
    "fr-frame/cross-screw-in-base": Occurrence(
        "fr_frame", "build_fr_frame_assembly.py", "BASE_SCREW_SEAT_Z"
    ),
    "fr-frame/cross-screw-in-top-frame": Occurrence(
        "fr_frame", "build_fr_frame_assembly.py", "TOP_SCREW_SEAT_Z"
    ),
    "fr-frame/support-hold-down-in-base": Occurrence(
        "fr_frame", "build_fr_frame_assembly.py", '"vn-lag-screw"'
    ),
    "fr-frame/nameplate-screw-in-base": Occurrence(
        "fr_frame", "build_fr_frame_assembly.py", "NAMEPLATE_SCREW_"
    ),
    "ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame": Occurrence(
        "ha_harmonic_analyzer", "build_fr_frame_assembly.py", '"vn-gooseneck-set-screw"'
    ),
    "dt-drive-train/post-mount-screws": Occurrence(
        "dt_drive_train",
        "build_dt_drive_train_assembly.py",
        "clamped in the post counterbore",
    ),
    "dt-drive-train/tip-block-hold-down": Occurrence(
        "dt_drive_train",
        "build_dt_drive_train_assembly.py",
        "clamped in the platform hold-down counterbore",
    ),
    "dt-drive-train/tip-adjuster": Occurrence(
        "dt_drive_train", "build_dt_drive_train_assembly.py", '"vn-cone-tip-adjuster"'
    ),
    "dt-drive-train/tip-pinch-screw": Occurrence(
        "dt_drive_train", "build_dt_drive_train_assembly.py", "pinch screw in the cross-bore"
    ),
    "dt-drive-train/tip-collar-set-screw": Occurrence(
        "dt_drive_train",
        "build_dt_drive_train_assembly.py",
        "tip collar set screw on the D-flat",
    ),
    "dt-drive-train/handle-pivot-screw": Occurrence(
        "dt_drive_train", "build_dt_drive_train_assembly.py", '"dt-crank-handle-pivot-screw"'
    ),
    "dt-drive-train/arbor-apex-set-screw": Occurrence(
        "dt_drive_train", "build_dt_drive_train_assembly.py", '"vn-arbor-set-screw"'
    ),
    "dt-drive-train/pinion-cam-set-screw": Occurrence(
        "dt_drive_train", "draw_dt_drive_train_assembly.py", "cam-collars-set"
    ),
    "dt-drive-train/keeper-eye-anchor-screw": Occurrence(
        "dt_drive_train", "build_dt_drive_train_assembly.py", "ANCHOR_THREAD_ENGAGEMENT"
    ),
    "ha-harmonic-analyzer/cone-pivot-screw-in-base": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", "PSCREW_"
    ),
    "ha-harmonic-analyzer/cone-lock-knob-in-base": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", "require_lock_seat_fit"
    ),
    "ha-harmonic-analyzer/swing-stop-screw-in-base": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", "require_stop_seat_fit"
    ),
    "ha-harmonic-analyzer/spring-foot-screw-in-base": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", "_FOOT_SCREW_XZ"
    ),
    "ha-harmonic-analyzer/arbor-pedestal-hold-down": Occurrence(
        "ha_harmonic_analyzer",
        "build_dt_drive_train_assembly.py",
        '"vn-pedestal-hold-down-screw"',
    ),
    "ha-harmonic-analyzer/pinion-block-hold-down": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", '"vn-slotted-screw"'
    ),
    "ha-harmonic-analyzer/north-pivot-bracket-hold-down": Occurrence(
        "ha_harmonic_analyzer", "ch_channel_assembly_steps.py", "north-ear-datum"
    ),
    "ha-harmonic-analyzer/south-pivot-bracket-hold-down": Occurrence(
        "ha_harmonic_analyzer", "ch_channel_assembly_steps.py", "south-bracket-spring-set"
    ),
    "ha-harmonic-analyzer/fulcrum-keeper-screw-in-top-frame": Occurrence(
        "ha_harmonic_analyzer", "build_ch_channel_assembly.py", '"vn-frame-side-screw"'
    ),
    "ha-harmonic-analyzer/channel-anchor-in-summing-plate": Occurrence(
        "ha_harmonic_analyzer", "build_ch_channel_assembly.py", "direct threaded seat"
    ),
    "ha-harmonic-analyzer/stick-stop-thumbscrew": Occurrence(
        "ha_harmonic_analyzer", "build_ha_measuring_stick_stop.py", "thumbscrew"
    ),
    "sm-summing/knife-hanger-in-mount": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", "HANGER_STUD_Y"
    ),
    "sm-summing/boss-hook-in-lever": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", "boss-hook keyed"
    ),
    "sm-summing/gooseneck-spring-screw": Occurrence(
        "sm_summing", "sm_gooseneck_spec.py", "SPRING SCREW"
    ),
    "pn-pen/hanger-screw-in-hanger": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", "HANGER_SCREW_POS"
    ),
    "pn-pen/thumb-screw-in-stirrup": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", "SET_SCREW_POS"
    ),
    "pn-pen/v-block-set-screw-on-rod": Occurrence(
        "pn_pen", "pn_pen_v_block_spec.py", "SCREW_HOLE_DIA"
    ),
    "ha-harmonic-analyzer/magnifying-bracket-screws": Occurrence(
        "ha_harmonic_analyzer", "build_mg_magnifier_assembly.py", "BRACKET_SCREW_POSITIONS"
    ),
    "mg-magnifier/wheel-axle-nut": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "wheel-axle nut locked to the axle"
    ),
    "mg-magnifier/clamp-thumb-screw": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "thumb-screw locked to clamp"
    ),
    "mg-magnifier/fixture-thumb-screw": Occurrence(
        "mg_magnifier", "mg_output_fixture_spec.py", "CROSS_HOLE_SPEC"
    ),
    "mg-magnifier/wheel-bar-clamp-screws": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "CLAMP_SCREW_X"
    ),
    "pd-paper-drive/clamp-screw-in-back-arc": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "support clamp-screw pattern"
    ),
    "pd-paper-drive/clip-screw-in-platen": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "platen clip-screw grid"
    ),
    "pd-paper-drive/guide-screw-in-guide": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "platen guide-screw grid"
    ),
    "pd-paper-drive/lock-screw-in-guide": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "platen lock-screw grid"
    ),
    "pd-paper-drive/arm-plate-screws": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "transgear-arm-plate-screw #"
    ),
    "pd-paper-drive/pivot-screw-in-bar": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", '"vn-transgear-pivot-screw",'
    ),
    "pd-paper-drive/disc-screws": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "transgear-disc-screw ("
    ),
    "pd-paper-drive/knob-cup-on-journal": Occurrence(
        "pd_paper_drive",
        "build_pd_paper_drive_assembly.py",
        "knob stack: cup pin locked to the knob cup",
    ),
    "pd-paper-drive/latch-hook-bracket-screws-in-bar": Occurrence(
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", "latch-hook-bracket-screw (x"
    ),
    "pd-paper-drive/thumbnut-on-knob-shaft": Occurrence(
        "pd_paper_drive",
        "build_pd_paper_drive_assembly.py",
        "transgear-thumbnut (seated on the collar pilot",
    ),
}

if __name__ == "__main__":
    sys.exit(main())
