"""Threaded-joint operational retention: the joint table and its audit.

drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) (operational retention): every threaded
support or fastener exposed to a rotating member's drag, torque reversal or
loss of preload has a mechanical anti-loosening means, installed by a stated
assembly step. A plain seated thread, shoulder, shim or threadlocker alone is
not one, and a cap that retains a cluster axially does not lock a different
interface.

``JOINTS`` holds one row per threaded joint of every machine assembly
(``_buildgraph.MACHINE_ASSEMBLIES``: shop-fixture jigs are not operating
machinery; identical pattern instances share a row and
carry their ``quantity``). Each part an assembly references is classified as
threaded or not (``THREADED_PARTS`` / ``UNTHREADED_PARTS``), so the joint list
is checked against the build's own component enumeration
(``_buildgraph.references_of``): a part added to an assembly fails coverage
until it is classified, and a threaded part fails until a row names it.
``REQUIRED_JOINTS`` registers every joint with its source occurrence, and the
table must match it exactly, so a row deleted while other rows still name its
parts is still caught. Shared purchase stock does not merge operational joints:
the drive-train foot and swing stop retain independent IDs and quantities even
though both use the same Default member. A threaded joint replaced by a pinned
one keeps a row, its lock the pin (paper-drive/knob-cup-on-journal, R9-70).

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
import ha_harmonic_analyzer_assembly_steps
import mg_magnifier_assembly_steps
import pd_paper_drive_assembly_steps
import sm_gooseneck_spring_screw_geom as gooseneck_screw


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
# drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads)).
RULINGS: dict[str, Ruling] = {
    "U-MHA-PD-13-no-lock": Ruling(
        joint="pd-paper-drive/thumbnut-on-knob-shaft",
        granted=(
            "user, 2026-10-03, joint-specific drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) ruling on the machinist review of "
            "6c385465d: no lock on the MHA-PD-13 thumbnut; re-granted 2026-10-11 for "
            "#8-32 after the inch change. The T24 floats 0.05-0.15 under the "
            "flange and turns against it only by its drive-pin backlash, ±0.9° per reversal "
            "((Ø2.5 +0.10 hole - Ø2.381 pin) / 2 on the R7 circle). Any drag it passes is "
            "μ F r_m = 0.15 × 1 N × 5.68 = 0.85 N·mm [INFERENCE: chain axial pull ≤1 N], "
            "against ~330 N·mm to back off a hand-tight nut [INFERENCE: ~400 N preload, μ "
            "0.15 on the #8-32 flank (d2 3.65, P 0.794) and on the pilot seat at the 10-03 "
            "mean radius 4.24; F (0.5 d2 μ / cos 30° - P / 2π + μ r)], over 300x. "
            "Every positive lock "
            "tried broke a wall or the chain's envelope: a 98335A049 hairpin across the "
            "flange sweeps r ~23 inside the chain band (plates' inner edge r 21.2)"
        ),
    ),
    "U-MHA-FR-VN-52-no-lock": Ruling(
        joint="ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame",
        granted=(
            "user, 2026-10-12, joint-specific drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) ruling on PR #1348 (Q5, option (a), "
            "no jam nut): adjustable by design, periodic re-set; user 2026-10-12. The "
            "MHA-FR-VN-52 cup point sets the gooseneck post's slid-to-level height and is "
            "re-set when it drifts, so the screw stays bare in the hub boss's spot-faced tap"
        ),
    ),
    "U-MHA-PN-VN-52-no-lock": Ruling(
        joint="pn-pen/rod-set-screw-in-v-block",
        granted=(
            "user, 2026-10-14, joint-specific drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) ruling on PR #1436: "
            "no lock; the MHA-PN-VN-52 set screw is an operator adjustment and a light clamp, and the "
            "v-block's .367 tap leaves no room for a jam screw. Period-faithful to the 1898 machine: "
            "the plain 91375A105 cup point goes in bare, nothing added to its thread"
        ),
    ),
    "U-MHA-PN-VN-51-no-lock": Ruling(
        joint="pn-pen/thumb-screw-in-stirrup",
        granted=(
            "user, 2026-11-01, joint-specific drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads) ruling on PR #2119: "
            "'Owner ruling 2026-11-01: MHA-PN-VN-51 knurled thumb screw is an operator adjustment, slackened "
            "at every marker change; no lock (as U-MHA-PN-VN-52)'. The 99607A213 thumb screw stays "
            "finger-tight and bare in the stirrup's bottom-rail tap"
        ),
    ),
    "U-MHA-MG-03-no-lock": Ruling(
        joint="mg-magnifier/lever-in-bracket",
        granted=(
            "user, 2026-10-20, approved MG threaded-lever redesign: "
            "'no further thread locking needed because mg-magnifying-lever "
            "does not experience rotational forces'. This accepts no added "
            "lock for this joint, not a demonstrated immunity to vibration. "
            "The lever is installed to projection without a shoulder or preload; "
            "vibration can still change projection or back the thread out. "
            "The assembly package declares RV-02; the two mating part packages "
            "declare the same joint-specific departure."
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
    "mg_magnifier": mg_magnifier_assembly_steps.SEQUENCE,
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
    """The build's own enumeration: each machine assembly script's referenced
    parts and sub-assemblies (``_buildgraph.references_of``) and its keyed
    steps."""
    assemblies = frozenset(_buildgraph.ASSEMBLY_ORDER)
    parts: dict[str, frozenset[str]] = {}
    subassemblies: dict[str, frozenset[str]] = {}
    for assembly in _buildgraph.MACHINE_ASSEMBLIES:
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
    for assembly in _buildgraph.MACHINE_ASSEMBLIES:
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
        f"(policy: cad/docs/drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads)).",
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
        "dt_arbor_pedestal",  # #4-40 UNC-2B apex tap through the crown (receiver of MHA-SH-VN-54); its #8 ledge hole is clearance only
        "sh_vn_arbor_set_screw",  # #4-40 x 1/4 cup point (91375A106), channel brackets and drive-train pedestals
        "ch_pivot_bracket",  # #4-40 UNC-2B apex tap through the ear's arch into the bore (receiver of MHA-SH-VN-54); #8 foot hole is clearance only
        "sm_vn_boss_hook",  # #10-24 UNC (McMaster 9490T1 open-eye eyebolt), member into the summing-lever boss tap
        "sh_vn_clamp_screw",  # #8-32 UNC (90280A201), magnifier and paper-drive column clamps
        "sh_column_clamp_back",  # #8-32 UNC tapped ear holes, receiver of clamp_screw (magnifier and paper_drive)
        "dt_cone_gear_shaft",  # receiver: Sec4 D-flat gripped by cone_tip_collar's #2-56 set screw
        "dt_vn_cone_lock_knob",  # 1/4-20 UNC knurled thumb screw (93585A190), member into harmonic_base (top level)
        "dt_vn_cone_pivot_screw",  # #10-24 UNC shoulder screw (91829A560), member into harmonic_base (top level)
        "dt_cone_swing_platform",  # 1/4-20 through-taps x2, receiver of post_mount_screw
        "dt_vn_cone_tip_adjuster",  # #10-32 cup-tip set screw (94025A164), member into cone_tip_block
        "dt_cone_tip_block",  # #4-40 blind foot tap + #10-32 through adjuster tap + #4-40 far-jaw pinch tap, receiver
        "dt_vn_cone_tip_block_screw",  # #4-40 SHCS (91251A108), member into cone_tip_block foot
        "dt_vn_cone_tip_collar",  # custom collar + stock #2-56 94355A213 flat-point screw on the shaft D-flat
        "dt_vn_cone_tip_pinch_screw",  # #4-40 fillister (91794A112), member into cone_tip_block far jaw; lock of cone_tip_adjuster
        "dt_crank_arm",  # #4-40 through-taps, receiver of crank_handle_pivot_screw and MHA-SH-VN-51
        "dt_crank_handle_pivot_screw",  # #4-40 made shoulder screw (MHA-DT-32), member into crank_arm
        "sh_vn_brass_fillister_screw",  # #4-40 brass (90114A511), keeper eye, nameplate and paper guides
        "sh_vn_fillister_screw_90280a108",  # #4-40 (90280A108), spring foot, swing stop and latch-hook bracket
        "fr_vn_frame_cross_screw",  # #10-32 UNF-2A x 1-3/4 (McMaster 90280A837), member: 4 into harmonic_base, 4 into top_frame
        "ch_vn_frame_side_screw",  # #2-56 fillister (McMaster 91794A080, MHA-CH-VN-52); member, x2 into top_frame KeeperTaps (top-level row)
        "ch_fulcrum_keeper",  # #1-72 UNF crown tap through to the shaft bore (receiver of MHA-CH-VN-55); its #2 foot hole is clearance only
        "ch_vn_fulcrum_set_screw",  # #1-72 UNF x 5/32 cup-point set screw (McMaster 91375A942, MHA-CH-VN-55), member: x2, one into each fulcrum_keeper crown tap
        "sm_gooseneck",  # receiver: 1/4-28 blind-tapped solid end piece brazed into the 1/2 in tube arm; its sleeve is the post gripped by the frame's set screw
        "sm_gooseneck_spring_screw",  # made MHA-SM-04 1/4-28 slotted cheese-head screw: clamps the counter-spring upper eye on its plain Ø6.35 body to the end piece
        "fr_vn_gooseneck_set_screw",  # 1/4-20 UNC x 3/4 square-head cup point (91410A540), member: into top_frame hub boss tap, grips summing gooseneck
        "pd_vn_guide_lock_screw",  # #4-40 slotted pan head (McMaster 91792A108, MHA-PD-VN-60, R9-31), member: 8 into the platen_guide rear through taps
        "pn_vn_hanger_screw",  # #8-32 UNC x 1 hex head (McMaster 93075A199), member through the pen-hanger strap's clearance hole into the hanger nut and jam nut
        "fr_harmonic_base",  # receiver: #10-32 cross taps, 1/4-20 hold-down seats, #4-40 nameplate seats, and the drive_train screws' seats (top-level rows)
        "sm_vn_boss_hook_jam_nut",  # McMaster 90760A140 thin #10-24 hex nut (MHA-SM-VN-55), member: jammed on the summing-lever boss top face, locking the boss hook
        "sm_vn_knife_hanger_stud",  # #10-24 UNC cut plain hex bolt (McMaster 92314A253 x 2), member into the knife-mount top tap
        "sm_knife_mount",  # #10-24 UNC-2B bottoming tap (9.65 full thread, 11.24 drill) in the top seat, receiver of the knife-hanger bolt; a plain reamed dowel slip hole and an open dowel slot
        "fr_vn_lag_screw",  # 1/4-20 UNC-2A x 3/4 hex head (92240A540), member: through rocker_arm_support foot into harmonic_base
        "mg_vn_magnifying_bracket_screw",  # #2-56 fillister, member: two in bracket counterbores into summing_lever (top-level row)
        "pd_vn_platen_clip_screw",  # #2-56 brass slotted pan head (92446A077, MHA-PD-VN-65), member: 4 into the platen's through taps, clamping the paper clips
        "mg_magnifying_clamp",  # MHA-MG-02 hex: #4-40 top-face thumb tap (receiver of thumb_screw) + #4-40 bottom-face blind tap (receiver of vertical_rod)
        "mg_magnifying_vertical_rod",  # MHA-MG-04: #4-40 UNC-2A turned top end with relief, member into the clamp's bottom tap, seats on its shoulder
        "mg_magnifying_bracket",  # 1/4-20 UNC-2B through neck; plain flange clearance holes
        "mg_magnifying_lever",  # quarter-inch brass body, flat UNC-2A threaded end
        "ms_stop_block",  # MHA-MS-02: #4-40 UNC-2B floor tap for the shared thumbscrew + 2x #2-56 cover taps
        "ms_vn_stop_plate_screw",  # #2-56 x 1/4 brass fillister (McMaster 90114A124, MHA-MS-VN-51), member: 2 into ms_stop_block through the cover plate
        "mg_output_fixture",  # #4-40 UNC axial tap from the spigot face into the rod bore (mg_output_fixture_spec.TAP_SPEC), receiver of the 2nd thumb_screw
        "dt_vn_pedestal_hold_down_screw",  # #8-32 x 3/4 fillister (90280A197, MHA-DT-VN-62), member: 2 arbor-pedestal seats in harmonic_base
        "ch_vn_bracket_hold_down_screw",  # #8-32 x 5/8 fillister (90280A196, MHA-CH-VN-57), member: 2 pivot-bracket seats in rocker_arm_support
        "pn_pen_frame",  # #4-40 UNC-2B tapped hole up through the bottom rail, receiver of pen_set_screw
        "pn_vn_pen_hanger_jam_nut",  # McMaster 90760A009 thin #8-32 hex nut (MHA-PN-VN-55), member: jammed against the hanger nut on hanger_screw
        "pn_vn_pen_hanger_nut",  # McMaster 90480A009 #8-32 hex nut (MHA-PN-VN-54), receiver of hanger_screw on the strap front
        "pn_vn_pen_set_screw",  # #4-40 UNC (McMaster 99607A213 knurled thumb screw), member into the pen-frame rail
        "pn_vn_pen_rod_set_screw",  # #4-40 UNC x 3/16 cup-point set screw (McMaster 91375A105, MHA-PN-VN-52), member into the pen v-block's tap, cup on the rod's pivot end
        "pn_vn_pen_adjust_nut",  # McMaster 92671A115 brass #0-80 hex nut (MHA-PN-VN-53), member: jam nut on the pen rod's top adjuster stud
        "pn_pen_v_block",  # receiver: #4-40 UNC-2B Hole Wizard tap through the front face into the pivot bore, receiver of pen_rod_set_screw
        "pn_pen_rod",  # receiver: #0-80 UNF-2B blind tap in the square's top face, receiver of pen_adjust_screw
        "pn_pen_adjust_screw",  # made MHA-PN brass eye stud, #0-80 UNF member into the pen rod's top tap; carries the jam nut
        "dt_pinion_cam",  # #2-56 UNC-2B tap + supplied ASME B18.3 #2-56 x 3/16 flat-point socket set screw, member (collar) gripping pinion_lift_rod
        "pd_platen",  # #2-56 tapped through (pd_platen_spec.SOCKET_SPEC), receiver of the 4 clip screws
        "pd_platen_guide",  # #4-40 front bottoming taps (guide screws) + rear through taps (guide-lock screws, R9-48), receiver
        "dt_vn_post_mount_screw",  # 1/4-20 (MSC 40923906 fillister, 4 in stock cut to fit), member into cone_swing_platform
        "pd_rack_pinion",  # 120T disc (MHA-PD-06): 3x #0-80 through taps drilled and tapped at assembly (A06 disc-taps-transferred), receiver of the disc screws
        "fr_rocker_arm_support",  # receiver only of channel screws: 4x #8-32 BracketSeats (top-level rows); its own foot holes are 5/16 clearance
        "dt_vn_slotted_screw",  # #8-32 x 1-1/2 fillister (90280A203, MHA-DT-VN-57), member into harmonic_base tapped seat
        "ch_vn_spring_hook",  # #6-32 eyebolt (McMaster 9489T111, MHA-CH-VN-51); member, x20 into summing_lever tapped plate (top-level row), receiver of its jam nut; no channel-internal joint
        "ch_anchor_jam_nut",  # MHA-CH-14 made brass round nut, #6-32 tapped through, member: x20 jammed on the summing-lever plate underside, locking each channel anchor (top-level row)
        "sm_summing_lever",  # receiver: #10-24 counter-anchor, 20x #6-32 channel anchors, two blind #2-56 magnifying-bracket seats
        "pd_support_bar",  # #8-32 blind pivot tap + 2x #4-40 through latch-hook taps (pd_support_bar_spec), receiver of the pivot screw and the latch-hook bracket screws
        "sh_vn_thumb_screw",  # #4-40 UNC (91882A221), magnifier clamp/output fixture and measuring-stick stop
        "fr_top_frame",  # receiver: #10-32 cross taps, 1/4-20 gooseneck set tap, #2-56 fulcrum-keeper taps (top-level row)
        "pd_transgear_arm",  # MHA-PD-18: 2x #8-32 plate taps through (pd_transgear_arm_spec), receiver; the pin MHA-PD-23 is pressed in a reamed hole
        "pd_vn_transgear_arm_plate_screw",  # #8-32 slotted oval head (McMaster 91790A199, MHA-PD-VN-56), 1-in stock cut to fit; member: 2 into transgear_arm
        "pd_vn_transgear_disc_screw",  # #0-80 slotted fillister (McMaster 91794A055, MHA-PD-VN-55), cut to fit; member: 3 through the hub flange into rack_pinion
        "pd_transgear_knob_shaft",  # MHA-PD-08: #8-32 UNC die-cut front thread (thumbnut), receiver; the rear journal is cross-pinned to the cup (MHA-PD-VN-62)
        "pd_vn_transgear_pivot_screw",  # #8-32 shoulder screw (McMaster 90325A174, MHA-PD-VN-57), member into the support_bar's through pivot tap
        "pd_transgear_thumbnut",  # MHA-PD-13 knurled nut, #8-32 UNC-2B through; member on the knob shaft's front thread
        "mg_wheel_axle",  # 3/16 drill-rod pin, #4-40 UNC front end (mg_wheel_axle_spec.THREAD_CALLOUT), receiver of the wheel-axle nuts
        "mg_vn_wheel_axle_nut",  # McMaster 92671A005 brass #4-40 hex nut x2 (nut + locknut), member
    }
)

# Every referenced part with no thread of its own.
UNTHREADED_PARTS: frozenset[str] = frozenset(
    {
        "dt_alignment_pinion",  # bonded to pinion_arbor (Loctite 638, drum-bonded)
        "ch_amplitude_bar",  # reamed top pin hole (pressed MHA-CH-11 pin), end notches; pinned/sliding only
        "ch_bar_pivot_pin",  # plain 5/64 drill-rod pin pressed in the bar cheeks, runs in the lever
        "sh_vn_chain_link",  # InnerLink and OuterLink members; pins and rollers, no thread
        "pd_vn_chain_connecting_link",  # clip-retained roller-chain link, no thread
        "ch_channel_lever",  # Ø6.5 fulcrum bore, #47 bar-pin hole, #21 spring-eye hole; no taps
        "ch_vn_channel_spring_installed",  # 9432K31 extension spring, hook ends in lever hole / eyebolt eye
        "sh_column_clamp_front",  # #8 CLEARANCE ear holes only; clamped in the screw stack
        "dt_cone_gear",  # slides on the MHA-DT-04 D-flat, no thread
        "dt_cone_pivot_post",  # clamped part: counterbored clearance for MHA-DT-VN-61; journals only
        "ch_connecting_rod",  # strap bore on cam + reamed pin hole (pressed MHA-CH-10 pin)
        "sm_vn_counter_spring",  # 1330K524 extension spring: upper eye clamped on the MHA-SM-04 screw, lower eye hooks the boss-hook eye, no thread
        "dt_crank_drive_gear",  # slides on the MHA-DT-04 D-flat against its collar, no thread
        "dt_crank_handle",  # oak handle, runs on the MHA-DT-32 shoulder
        "dt_crank_handle_butt_cup",  # bonded in the handle butt; pocket bored for the MHA-DT-32 head, no thread
        "dt_crank_handle_ferrule",  # bonded (epoxy) to the handle tenon
        "dt_crank_hub",  # pressed into crank_arm, seam-pinned, taper-pinned to crankshaft
        "dt_vn_crank_hub_pin",  # 4 m6 dowel, ISO 2338
        "dt_crank_pin",  # 1:48 taper pin, light drive
        "dt_crank_pin_eye",  # formed brass eye, clamped under fillister_screw (no thread of its own)
        "dt_vn_crank_seat_drive_pin",  # MHA-DT-VN-67 dowel pressed into match-drilled holes, no thread
        "dt_crank_pin_ring",  # brass wire keeper ring
        "dt_crank_pinion",  # pinned by crank_pinion_pin
        "dt_crank_pinion_pin",  # plain 1/8 drill-rod drive pin
        "dt_crankshaft",  # journals in MHA-DT-05; pinned (MHA-DT-29), taper-pinned (MHA-DT-09); paper-drive T12 wheel has no thread
        "dt_cylinder_end_disc",  # plain thrust washer on the arbor
        "dt_cylinder_gear",  # runs free on the arbor, no set screw
        "dt_cylinder_gear_shaft",  # plain 3/8 arbor; MHA-SH-VN-54 cups bear in drilled spots, no thread ("NO FLATS; SET-SCREW SPOTS ARE DRILLED AT ASSEMBLY")
        "ch_fulcrum_shaft",  # plain Ø6.35 shaft with two set-screw flats, no threads
        "pd_guide_lock",  # 1/8 drill holes (R9-49) only; clamped by guide_lock_screw
        "dt_vn_keeper_chain",  # bead chain
        "dt_vn_keeper_chain_link",  # snap loop link
        "sm_vn_knife_mount_dowel",  # MHA-SM-VN-53 1/8 dowels, two pressed into the crossbar's blind underside reams per knife mount, slip in the knife mount's round hole and slot
        "sm_vn_knife_hanger_washer",  # new 18-8 SAE washer (McMaster 96659A104), hex-head bearing on the faced crossbar top; no thread
        "pd_latch_hook",  # MHA-PD-14 formed spring-steel hook: screw holes drilled thru, latch-pin hole match-drilled at assembly; no thread
        "sh_vn_music_wire",  # LeverWire and PenWire members, wrapped/tied, no thread
        "mg_magnifying_wheel",  # reamed .1890 running bore + two Ø1 wire-tie holes; no thread
        "mg_wheel_drum",  # MHA-MG-10 brass drum pressed on the wheel's spigot; no thread
        "mg_wheel_axle_spacer",  # MHA-MG-11 brass sleeve, drilled clearance on the wheel axle; no thread
        "ms_stick",  # MHA-MS-01 plain 8 x 3 brass bar; the stop's thumbscrew tip pinches it
        "ms_stop_plate",  # MHA-MS-03 brass cover plate: 2 plain clearance holes for the #2-56 screws; no thread
        "fr_nameplate",  # brass plate, #4 clearance holes only
        "pn_vn_pen_marker",  # purchased Sharpie Fine Point; plain barrel, the thumb-screw tip bears on it (no thread)
        "dt_pinion_arbor",  # journal + grip head, crossrod bonded, collar spring-pinned
        "dt_pinion_arbor_collar",  # spring-pinned by MHA-DT-VN-63 (arbor-collar-pinned)
        "dt_pinion_bracket",  # straps: plain bores, pinned to MHA-DT-19 by MHA-DT-VN-63
        "dt_pinion_cam_pin",  # bonded follower pin (cam-pins-bonded)
        "dt_pinion_handle",  # bonded crossrod (handle-bonded)
        "dt_pinion_lever",  # hub cross-pinned by MHA-DT-30 (lever-pin-set)
        "dt_pinion_lever_pin",  # peened cross pin
        "dt_pinion_lift_rod",  # plain Ø6.35 rod; gripped by the MHA-DT-23 set screws (appears as receiver of the cam row, carries no thread)
        "dt_pinion_pivot_block",  # #8 normal-clearance holes only; clamped by MHA-DT-VN-57 (row harmonic-analyzer/pinion-block-hold-down)
        "dt_pinion_pivot_shaft",  # plain shaft, cross-pinned to the straps by MHA-DT-VN-63
        "dt_pinion_spring",  # #4 clearance foot hole; clamped by foot-screw MHA-SH-VN-52 (top-level row)
        "dt_vn_pinion_strap_pin",  # 1/16 spring pin
        "ch_pivot_shaft",  # plain Ø6.35 rod, domed both ends, two set-screw flats; no thread
        "pd_platen_clip",  # #2 clearance holes only (build_pd_platen_clip); clamped by platen_clip_screw
        "pd_platen_paper",  # paper sheet, no thread
        "pd_platen_rack",  # soft-soldered to the platen back (A06 rack-soldered); no holes, no thread
        "ch_rocker_arm",  # reamed pivot hub bore + #47 rod-pin hole
        "ch_rod_pivot_pin",  # MHA-CH-10 5/64 drill-rod pin, pressed into the fork's reamed tines, ends dressed flush (rod-forks-pinned); no thread
        "ch_vn_rocker_thrust_washer",  # MHA-CH-VN-56 carbon-steel ring shim (McMaster 3088A429) loose on the MHA-CH-05 shaft, north and south; no thread
        "pd_transgear_arm_plate",  # MHA-PD-19: reamed knob-shaft bore + 2 countersunk clearance screw holes; no thread
        "pd_vn_transgear_knob_cup_pin",  # MHA-PD-VN-62 1/16 slotted spring pin through the knob cup and the shaft's journal
        "pd_transgear_disc_hub",  # MHA-PD-17 brass hub: D-bore on the sleeve's D-flat, plain flange clearance holes for the disc screws; trapped between the seat shoulder and the front bushing, no thread
        "pd_transgear_drive_collar",  # MHA-PD-22: matching D-bore on the knob shaft, reamed drive-pin holes; no thread
        "pd_transgear_feed_pinion",  # MHA-PD-10 shifted 12T 32DP PA20 sleeve: plain bore on the pin, D-flat keying the hub's D-bore; no thread
        "pd_transgear_front_bushing",  # MHA-PD-25 brass bushing, printed length, reamed bore on the pin; no thread
        "pd_transgear_knob_cup",  # MHA-PD-16: reamed through bore, cross-pinned to the journal at assembly; no thread
        "pd_transgear_knob_thrust_ring",  # MHA-PD-15 loose brass ring, drilled bore; no thread
        "pd_vn_transgear_latch_pin",  # MHA-PD-VN-58 1/8 dowel pressed into the arm's reamed end-face hole
        "pd_vn_transgear_arm_plate_locating_pin",  # MHA-PD-VN-64 2 mm dowels pressed into the arm's through reams
        "pd_transgear_pivot_spacer",  # MHA-PD-20 brass spacer, reamed bore pressed on the pivot shoulder (locating, R9-71); no thread
        "pd_vn_transgear_pivot_spring",  # MHA-PD-VN-63 disc spring on the pivot shoulder; no thread
        "pd_vn_transgear_pivot_shim",  # MHA-PD-VN-67 DIN 988 shim on the pivot shoulder under the head; no thread
        "dt_vn_cylinder_bank_spring",  # MHA-DT-VN-68 wave spring loose on the MHA-DT-13 arbor; no thread
        "ch_vn_rocker_bank_spring",  # MHA-CH-VN-54 wave spring loose on the MHA-CH-05 shaft; no thread
        "pd_transgear_pin",  # MHA-PD-23 plain steel pin pressed into the arm's reamed hole, ring groove at the front; no thread
        "pd_transgear_rear_bushing",  # MHA-PD-24 brass bushing, printed length, reamed bore on the pin; no thread
        "pd_transgear_removable",  # O12 plain bore + 2 drive-pin holes, no thread (build_pd_transgear_removable)
        "pd_vn_transgear_retaining_ring",  # MHA-PD-VN-61 external retaining ring (McMaster 97431A260) in the pin's groove
        "pd_vn_transgear_knob_drive_pin",  # MHA-PD-VN-54 dowel pressed into plain holes, no thread
        "fr_tube_frame",  # columns: socket slip fit; cross holes enlarged so the MHA-FR-VN-53 shank passes "WITHOUT THREAD CONTACT" (MHA-FR-00 STEP 2/5)
        "fr_vn_tube_frame_cap",  # McMaster 9275K141 push-on cap (MHA-FR-00 STEP 7)
        "mg_vn_wheel_axle_back_washer",  # MHA-MG-VN-54 brass #10 washer (McMaster 92916A480) loose on the axle pin; no thread
        "mg_vn_wheel_axle_front_washer",  # MHA-MG-VN-55 brass #4 washer (McMaster 92916A250) loose on the axle's #4-40 end; no thread
        "mg_wheel_bar",  # #8 clearance holes (clamp screws) + #8 close clearance (pen-hanger screw, which runs into the hanger nut and jam nut in pen.SLDASM) + the reamed .1865 axle-pin press bore
        "pn_pen_hanger",  # #8 close-clearance strap hole for the hanger screw; slots and brazed plates, no thread
    }
)

# Purchased parts (registry ``process: purchased``) that carry no thread.
UNTHREADED_STOCK: dict[str, str] = {
    "ch_vn_channel_spring_installed": "extension spring; its hook ends hang in plain holes and eyes",
    "sm_vn_counter_spring": "extension spring; its hook ends hang in plain holes and eyes",
    "sh_vn_chain_link": "InnerLink and OuterLink roller-chain members; pins/rollers only, no thread",
    "pd_vn_chain_connecting_link": "clip-retained roller-chain link; pins only, no thread",
    "dt_vn_keeper_chain": "chain; its end links hang on screws and eyes, carrying no thread",
    "dt_vn_crank_seat_drive_pin": "dowel pin pressed into a plain hole",
    "dt_vn_keeper_chain_link": "plain chain link",
    "sm_vn_knife_mount_dowel": "dowel pin pressed into a blind reamed hole",
    "sm_vn_knife_hanger_washer": "plain SAE washer under the knife-hanger hex head; no thread",
    "dt_vn_pinion_strap_pin": "slotted spring pin pressed into a plain hole",
    "pd_vn_transgear_knob_drive_pin": "dowel pin pressed into a plain hole",
    "pd_vn_transgear_knob_cup_pin": "slotted spring pin in a hole match-drilled at assembly",
    "pd_vn_transgear_latch_pin": "dowel pin pressed into a reamed hole",
    "pd_vn_transgear_arm_plate_locating_pin": "dowel pin pressed into the arm's through ream",
    "pd_vn_transgear_retaining_ring": "external retaining ring fitted sideways in a groove",
    "pd_vn_transgear_pivot_spring": "disc spring on the pivot shoulder; no thread",
    "pd_vn_transgear_pivot_shim": "shim ring on the pivot shoulder under the head; no thread",
    "dt_vn_cylinder_bank_spring": "wave disc spring loose on the arbor; no thread",
    "ch_vn_rocker_bank_spring": "wave disc spring loose on the pivot shaft; no thread",
    "ch_vn_rocker_thrust_washer": "ring shim loose on the pivot shaft; no thread",
    "fr_vn_tube_frame_cap": "push-on round cap over the column end",
    "mg_vn_wheel_axle_back_washer": "plain washer loose on the wheel-axle pin; no thread",
    "mg_vn_wheel_axle_front_washer": "plain washer loose on the wheel-axle's threaded end; no thread",
    "pn_vn_pen_marker": "felt-tip marker; its barrel lies in the v-block groove under the thumb screw; no thread",
    "sh_vn_music_wire": "LeverWire and PenWire music-wire members; hooked/wrapped or tied through the adjuster eye, no thread",
}

JOINTS: tuple[Joint, ...] = (
    # --- frame (MHA-FR-00), and the gooseneck set screw that grips a summing part ---
    Joint(
        id="fr-frame/cross-screw-in-base",
        assembly="fr_frame",
        member="fr_vn_frame_cross_screw",
        receiver="fr_harmonic_base",
        thread="#10-32 UNF-2A/2B",
        quantity=4,
        installed_at="MHA-FR-00 STEP 6",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="retains a tube_frame column in its base socket; base and columns never move relative to each other and no operating member bears on or turns about the horizontal screw axis (the screw passes clearance holes in both tube walls)",
        axial_capture="narrow fillister head seated on the Ø9 spotface of the base pad; thread engages near and far casting segments of the interrupted 46 mm bottoming tap",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (lower cross screws, BASE_SCREW_Y/BASE_SCREW_SEAT_Z) + module asserts; fr_harmonic_base_fasteners.py:BASE_CROSS_TAP_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 2, 6 ('TIGHTEN ONLY UNTIL EVERY HEAD SEATS'), ASSEMBLY_CHECKS 2",
    ),
    Joint(
        id="fr-frame/cross-screw-in-top-frame",
        assembly="fr_frame",
        member="fr_vn_frame_cross_screw",
        receiver="fr_top_frame",
        thread="#10-32 UNF-2A/2B",
        quantity=4,
        installed_at="MHA-FR-00 STEP 6",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="retains the top_frame casting on a tube_frame column; casting and columns are stationary relative to each other and no rotating/rocking member turns about the horizontal screw axis (clearance through both tube walls)",
        axial_capture="narrow fillister head seated flush in the Ø9 boss counterbore; thread engages near and far wall of the top_frame interrupted #10-32 bottoming tap (SideTaps)",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (upper cross screws, TOP_SCREW_Y/TOP_SCREW_SEAT_Z); build_fr_top_frame.py:SIDE_TAP_SPEC, step 13 SideTaps; draw_fr_frame_assembly.py ASSEMBLY_STEPS 5, 6, ASSEMBLY_CHECKS 2",
    ),
    Joint(
        id="fr-frame/support-hold-down-in-base",
        assembly="fr_frame",
        member="fr_vn_lag_screw",
        receiver="fr_harmonic_base",
        thread="1/4-20 UNC-2A/2B",
        quantity=4,
        installed_at="MHA-FR-00 STEP 8",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps the rocker_arm_support foot to the base deck; the support never moves on the base, and the rocker pivot it carries turns about machine Z (horizontal), so the rocker's reaction reaches these vertical (Y-axis) screws as cyclic tension/shear, not as torque about their own axis",
        axial_capture="hex head's under-head washer face bears on the 6.35 support foot (5/16 clearance drill); unchanged 12.42 mm stock insertion into the through-tapped 1/4-20 UNC-2B deck seat, with useful engagement limited by retained casting",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (lag-screw seed + grid) and LAG_* asserts; fr_harmonic_base_fasteners.py:HOLD_DOWN_SEAT_SPEC/HOLD_DOWN_ENGAGEMENT; fr_rocker_arm_support_spec.py:HOLE_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 8 ('DRAW DOWN EVENLY UNTIL ALL HEADS SEAT')",
    ),
    Joint(
        id="fr-frame/nameplate-screw-in-base",
        assembly="fr_frame",
        member="sh_vn_brass_fillister_screw",
        receiver="fr_harmonic_base",
        thread="#4-40 UNC",
        quantity=4,
        installed_at="MHA-FR-00 STEP 9",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="holds the cosmetic nameplate flat on the base deck; plate and base never move relative to each other and nothing in operation touches or turns the plate",
        axial_capture="fillister head seated flush on the plate's decorated face; unchanged 4.85 mm nominal stock insertion into the through-tapped #4-40 UNC-2B deck seat",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (nameplate corner screws, NAMEPLATE_SCREW_* asserts); fr_harmonic_base_fasteners.py:NAMEPLATE_SEAT_SPEC; build_fr_harmonic_base.py:NAMEPLATE_SEAT_SPEC; draw_fr_frame_assembly.py ASSEMBLY_STEPS 9",
    ),
    Joint(
        id="ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame",
        assembly="ha_harmonic_analyzer",
        member="fr_vn_gooseneck_set_screw",
        receiver="fr_top_frame",
        thread="1/4-20 UNC",
        quantity=1,
        installed_at="MHA-FR-00 STEP 10",
        exposure=Exposure.OSCILLATING,
        exposure_reason="cup point is the ONLY retention of the summing gooseneck post (MHA-SM-01) in the top_frame rail-hub bore, both its slid-to-level height and its rotation; the post's arm carries the counter-spring hung from the rocking summing lever, so the load it reacts cycles every stroke",
        axial_capture="threads into the through-to-bore 1/4-20 GooseneckTap through the east-rail hub boss's Ø10 spot face; square head standing proud outboard; cup point bears radially on the gooseneck's Ø15.875 sleeve (as modelled it stands 0.21 clear)",
        lock=Lock.NONE,
        evidence="build_fr_frame_assembly.py:build (gooseneck-set-screw, SET_SCREW_TIP_X, McMaster 91410A540 SHANK_LEN) + module comment; build_fr_top_frame.py:SET_TAP_SPEC, step 8 SetBoss/SetSpotFace, step 14 GooseneckTap; build_sm_summing_assembly.py docstring + gooseneck placement; spring_mount_geom.py docstring ('setup slides the gooseneck until level'); draw_fr_frame_assembly.py ASSEMBLY_STEPS 10 ('START MHA-FR-VN-52 ... LEAVE ITS CUP POINT CLEAR'), ASSEMBLY_CHECKS 5",
        exception="U-MHA-FR-VN-52-no-lock",
    ),
    # --- drive_train (MHA-DT-00): cone set and crank, and their screws into the frame's base ---
    Joint(
        id="dt-drive-train/post-mount-screws",
        assembly="dt_drive_train",
        member="dt_vn_post_mount_screw",
        receiver="dt_cone_swing_platform",
        thread="1/4-20",
        quantity=2,
        installed_at="post-and-tip-block",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "Clamp MHA-DT-05 to MHA-DT-20, and MHA-DT-05 journals the continuously turning MHA-DT-04 "
            "cone shaft and, directly, the hand-turned MHA-DT-11 crankshaft, whose handle load "
            "turns through 360 deg every revolution; journal drag and that rotating crank load "
            "reach the post-to-plate joint as a cyclic moment about vertical that only head and "
            "face friction resist (the post is deliberately turned on the screws' clearance at "
            "fit-up, so nothing else locates it in rotation)"
        ),
        axial_capture=(
            "fillister head on the MHA-DT-05 counterbore floor; thread through the MHA-DT-20 1/4-20 "
            "through-tap, cut flush to 0.3 short of the underside (0.90D min, pending ruling "
            "#1019 MHA-DT-VN-61, engagement only); left loose at post-and-tip-block, tightened at "
            "tip-adjuster-set"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py post_screws placement + lock_mate 'clamped in the post "
            "counterbore', cone-shaft revolute on 'journal axis@dt-cone-pivot-post'; "
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 2 (post-and-tip-block) and 3 "
            "(tip-adjuster-set 'TIGHTEN BOTH MHA-DT-VN-61'), 4 (crank-mesh-checked 'FIT MHA-DT-11 "
            "DIRECTLY IN THE MHA-DT-05 CRANK BORE'); dt_vn_post_mount_screw_spec.THREAD; "
            "dt_cone_swing_platform_spec.POST_MOUNT_SPEC; pending exception ruling #1019 MHA-DT-VN-61"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-block-hold-down",
        assembly="dt_drive_train",
        member="dt_vn_cone_tip_block_screw",
        receiver="dt_cone_tip_block",
        thread="#4-40",
        quantity=1,
        installed_at="post-and-tip-block",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "The one screw is MHA-DT-21's only anchor, and MHA-DT-21 carries the running MHA-DT-04 tip "
            "in the MHA-DT-VN-55 cup: the shaft's end-play thrust acts 1.0 off the screw axis "
            "(dt_cone_tip_block_spec.FOOT_TAP_OFFSET_X) and the radial tip load acts off it along "
            "the shaft, so a moment about the vertical screw axis varies with mesh load every "
            "crank turn (and reverses with the crank); a single screw lets the block turn about "
            "it, and the build's 'tip-block anti-spin' parallel mate has no physical "
            "counterpart (no dowel, key, pocket or second screw)"
        ),
        axial_capture=(
            "SHCS head on the MHA-DT-20 underside counterbore floor, thread up into the blind #4-40 "
            "tap in the MHA-DT-21 foot; tightened 'SNUG'"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py tip_holddown placement + lock_mate 'clamped in the "
            "platform hold-down counterbore', parallel_mate 'tip-block anti-spin (rides the "
            "plate)'; cone_tip_block_spec HOLDDOWN_THREAD / FOOT_TAP_OFFSET_X (user ruling "
            "2026-09-29: one #4-40 SHCS); draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 2 "
            "(post-and-tip-block '... INTO THE MHA-DT-21 FOOT, SNUG')"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-adjuster",
        assembly="dt_drive_train",
        member="dt_vn_cone_tip_adjuster",
        receiver="dt_cone_tip_block",
        thread="#10-32",
        quantity=1,
        installed_at="tip-adjuster-set",
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "Its turn sets MHA-DT-04's end play (run in until the shaft stops shuttling, back off "
            "1/8 turn), and the shaft tip turns continuously against its cup, putting friction "
            "drag about the screw's own axis"
        ),
        axial_capture=(
            "thread engagement only: headless cup-tip set screw in the block's #10-32 "
            "through-tap, 1.0D min (pending ruling #975 MHA-DT-VN-55); cup bears on the shaft tip"
        ),
        lock=Lock.PINCH_CLAMP,
        lock_part="dt_vn_cone_tip_pinch_screw",
        lock_binds=("dt_vn_cone_tip_adjuster", "dt_cone_tip_block"),
        lock_step="tip-adjuster-set",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 3 (tip-adjuster-set 'THREAD MHA-DT-VN-55 ... "
            "BACK OFF 1/8 TURN; TIGHTEN MHA-DT-VN-56 ACROSS THE SLIT'); cone_tip_block_spec "
            "SLIT_FLOOR / WORST_SLIT_BREAKTHROUGH_MM (slit opens into the adjuster thread), "
            "PINCH_THREAD; build_dt_drive_train_assembly.py parallel_mate 'adjuster anti-spin "
            "(pinch-locked)'; pending exception ruling #975 MHA-DT-VN-55 ('the pinch screw across the slit "
            "locks it'); cone_stack_end_play.SHAFT_END_PLAY"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-pinch-screw",
        assembly="dt_drive_train",
        member="dt_vn_cone_tip_pinch_screw",
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
            "WORST_PINCH_ENGAGEMENT_MM; config/parts/dt-vn-cone-tip-pinch-screw.yaml "
            "installation_notes; CONE_CRANK_STEPS 3 (tip-adjuster-set 'TIGHTEN MHA-DT-VN-56 ACROSS "
            "THE SLIT'); CONSUMABLES_NOTES '#4-40 ... SCREWS: SNUG'"
        ),
    ),
    Joint(
        id="dt-drive-train/tip-collar-set-screw",
        assembly="dt_drive_train",
        member="dt_vn_cone_tip_collar",
        receiver="dt_cone_gear_shaft",
        thread="#2-56",
        quantity=1,
        installed_at="tip-adjuster-set",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "MHA-DT-VN-54 turns as one with MHA-DT-04 (its set screw on the Sec4 D-flat) and rubs nothing "
            "that moves relative to it: the D-flat-keyed stack floats a feeler gap south of it "
            "and the tip block stands clear north (collar-to-block air), so no friction torque "
            "acts about the radial set-screw axis; stack float thrust and start/stop inertia "
            "load the screw across its axis"
        ),
        axial_capture=(
            "94355A213 stock flat-point set screw, as supplied, landed on the shaft's Sec4 D-flat; "
            "custom collar set one COLLAR_FEELER off T006; receiver carries >=1.5D full thread"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py tip_collar placement + 'tip collar set screw on the "
            "D-flat' parallel mate; dt_vn_cone_tip_collar_spec SCREW_LANDING_MARGIN_MM, "
            "WORST_FULL_ENGAGEMENT_MM and WORST_WALLS_MM; cone_stack_end_play "
            "(collar and block never touch); CONE_CRANK_STEPS 'LOCK ITS SET SCREW ON THE FLAT'"
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
            "The oak MHA-DT-08 spins on the oiled shoulder once per crank turn relative to the arm, "
            "and its bonded MHA-DT-35 cup floor bears on the screw head when the handle is pulled "
            "out (end play 0.25-1.0), so bore and head friction drag the screw about its own "
            "axis in one sense for each crank direction"
        ),
        axial_capture=(
            "shoulder seated tight on the arm's outboard face (ArmSeat on HandleSeat); thread "
            "through the arm's #4-40 tap, tip filed flush with the inboard face"
        ),
        # Rule 23 staked end (#1174), after the PD pivot screw's user ruling
        # 2026-10-15 and the standing no-threadlocker rule (2026-10-16).
        lock=Lock.STAKED,
        lock_part="dt_crank_arm:staked tap mouth",
        lock_binds=("dt_crank_handle_pivot_screw", "dt_crank_arm"),
        lock_step="crank-handle-fitted",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 7 (crank-handle-fitted 'NO THREADLOCKER, "
            "SHOULDER TIGHT. FILE THE TIP FLUSH ... THEN STAKE THE TAP MOUTH ONTO IT AT 2 OPPOSITE "
            "POINTS') and HANDLE_STAKE_NOTE; build_dt_drive_train_assembly.py handle_screw placement "
            "and 'MHA-DT-32 shoulder seated' mates; dt_crank_handle_pivot_screw_spec THREAD_SIZE and "
            "INSTALLED_CONFIG (tip filed flush); dt_crank_arm_spec HANDLE_PIVOT_HOLE_SPEC"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/cone-pivot-screw-in-base",
        assembly="ha_harmonic_analyzer",
        member="dt_vn_cone_pivot_screw",
        receiver="fr_harmonic_base",
        thread="#10-24 UNC",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("other-base-mounting"),
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "MHA-DT-20, carrying the whole cone set and crank, swings on the oiled shoulder out to "
            "the MHA-SH-VN-52 stop and back at every zeroing (CHECKS 4/5), dragging the shoulder "
            "about the screw axis one way then the other; in running, the crank and mesh "
            "reaction on the knob-clamped platform also bears on the shoulder"
        ),
        axial_capture=(
            "shoulder bottomed on the base top, thread tail in the through #10-24 UNC-2B base seat; "
            "head stands 0.25 above the plate (no head clamp on the platform)"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py pivot_screw placement ('base-threaded STATIC ... "
            "shoulder bottoms on the base top') and PSCREW_* asserts; dt_vn_cone_pivot_screw_spec.THREAD; "
            "draw_dt_drive_train_assembly.py INTERFACE_NOTES ('BASE MHA-FR-01 ... RECEIVES MHA-DT-VN-52'), "
            "CHECKS 4 ('SWING THE CONE SET ON MHA-DT-VN-52 TO THE MHA-SH-VN-52 STOP'), rig_steps "
            "other-base-mounting"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/cone-lock-knob-in-base",
        assembly="ha_harmonic_analyzer",
        member="dt_vn_cone_lock_knob",
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
            "collarless knurled head bears on the MHA-DT-20 top; stud through the platform notch "
            "into the through 1/4-20 UNC-2B base seat"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py lock_knob placement ('platform clamp, engaged end'), "
            "require_lock_seat_fit; cone_lock_knob_spec THREAD / require_seat_fit; "
            "draw_dt_drive_train_assembly.py CHECKS 4 ('LOOSEN MHA-DT-VN-51 ... TIGHTEN MHA-DT-VN-51'), "
            "INTERFACE_NOTES"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/swing-stop-screw-in-base",
        assembly="ha_harmonic_analyzer",
        member="sh_vn_fillister_screw_90280a108",
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
        axial_capture="head seated on the base top; thread in the through #4-40 base seat",
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
        member="sh_vn_fillister_screw_90280a108",
        receiver="fr_harmonic_base",
        thread="#4-40",
        quantity=1,
        installed_at=dt_drive_train_steps.step_ref("rig-seats-transferred"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Clamps the MHA-DT-24 foot pad to the base. The spring's load lies in the strap swing "
            "plane through the screw axis (blade preloaded on the parked MHA-DT-14 flank, deflected "
            "further only while the pinion is engaged for zeroing), so it bends the foot about "
            "the bank axis and reaches the screw as tension and shear, not as torque about its "
            "vertical axis"
        ),
        axial_capture=(
            "narrow fillister head on the spring foot pad through its #4 clearance hole into "
            "the transferred through #4-40 UNC-2B base seat"
        ),
        lock=Lock.NONE,
        evidence=(
            "build_dt_drive_train_assembly.py spring_foot_screw placement, _FOOT_SCREW_XZ, "
            "_require_clearance_size('pinion spring foot'), _require_tapped_thread('foot-screw "
            "base seat'); sh_vn_fillister_screw_90280a108_spec.THREAD; draw_dt_drive_train_assembly.py rig_steps "
            "rig-seats-transferred ('FIT ... 1X MHA-SH-VN-52'), INTERFACE_NOTES"
        ),
    ),
    # --- drive_train (MHA-DT-00): cylinder bank and pinion rig, and their screws into the base ---
    Joint(
        id="dt-drive-train/arbor-apex-set-screw",
        assembly="dt_drive_train",
        member="sh_vn_arbor_set_screw",
        receiver="dt_arbor_pedestal",
        thread="#4-40 UNC",
        quantity=2,
        installed_at="cylinder-bank-located",
        exposure=Exposure.ROTATING_DRAG,
        exposure_reason=(
            "Each screw is the only thing holding the stationary arbor MHA-DT-13 in its pedestal; "
            "20 oiled MHA-DT-12 gears spin on that arbor (check 3), so their journal drag, which "
            "reverses with crank direction and hand zeroing (check 5), reaches the screw through its cup point"
        ),
        axial_capture="cup point tightened into a #43 spot drilled in MHA-DT-13 through the crown tap; screw rides only its own #4-40 thread in the crown",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py BANK_STEPS 9E ('RUN THE BACK MHA-SH-VN-54 IN TIGHT, THEN THE FRONT ONE'); "
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
        thread="#2-56 UNC (ASME B18.3 #2-56 X 3/16 flat-point socket set screw supplied with MHA-DT-23, 2B tap in the cam)",
        quantity=2,
        installed_at="cams-and-lever-fitted",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "The set screw is the only drive between the lift rod MHA-DT-17 and each eccentric cam: the lever turns "
            "the rod ~-72 deg to lift the MHA-DT-25 follower pins against MHA-DT-24, and the spring drives the cams "
            "back to park, so the torque the screw carries reverses every engage/park cycle"
        ),
        axial_capture=(
            "flat point clamped on the plain round Ø6.35 rod (slip-fit Ø.2510 reamed bore, no flat or spot); the collars "
            "are set on 66MA leaves 0.25/0.90 off the MHA-DT-18 blocks and also carry the rod's axial location"
        ),
        # Rule 23 staked tap mouth (#1176), as the channel's fulcrum set screws
        # (fulcrum-set-screws-staked); no threadlocker on any thread.
        lock=Lock.STAKED,
        lock_part="dt_pinion_cam:staked tap mouth",
        lock_binds=("dt_pinion_cam", "dt_pinion_lift_rod"),
        lock_step="cam-collars-set",
        evidence=(
            "draw_dt_drive_train_assembly.py rig_steps 'cams-and-lever-fitted' (set screw loose) and 'cam-collars-set' "
            "(pinion_rig_fitup COLLAR_SET_STEP: 'TIGHTEN THEIR SET SCREWS AND STAKE EACH TAP MOUTH AT 2 POINTS'); "
            "dt_pinion_cam_spec.DRAWING_NOTES; dt_pinion_cam_geometry SET_SCREW_Z/SET_SCREW_MAJOR_DIA (tap 45 deg or more "
            "off the follower contact, test_cam_set_screw_hole_stays_clear_of_the_follower); "
            "build_dt_drive_train_assembly.py cam-on-rod concentric, axial and CAM_ROD_PHASE_DEG anti-spin mates"
        ),
    ),
    Joint(
        id="dt-drive-train/keeper-eye-anchor-screw",
        assembly="dt_drive_train",
        member="sh_vn_brass_fillister_screw",
        receiver="dt_crank_arm",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="crank-hub-fitted",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "The screw alone clamps the straight tail of the MHA-DT-28 keeper eye on the continuously turning crank "
            "arm; the MHA-DT-VN-65 chain hangs from the eye loop beside the screw, and as the arm turns, gravity on "
            "the chain swings round the arm frame, so its pull on the loop puts a moment about the screw axis "
            "that reverses once per crank turn"
        ),
        axial_capture="fillister head clamps the 1.0 brass eye tail on the arm's outboard face; shank in the arm's #4-40 through tap, tip short of the inboard face",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py CONE_CRANK_STEPS 6 ('CLAMP MHA-DT-28 UNDER MHA-SH-VN-51'); "
            "build_dt_drive_train_assembly.py anchor block (~L722-766: ANCHOR_THREAD_ENGAGEMENT, through tap) and "
            "placement (~L4400-4414); crank_pin_eye_spec docstring (tail clamped under the screw); CONSUMABLES_NOTES"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/arbor-pedestal-hold-down",
        assembly="ha_harmonic_analyzer",
        member="dt_vn_pedestal_hold_down_screw",
        receiver="fr_harmonic_base",
        thread="#8-32 UNC",
        quantity=2,
        installed_at=dt_drive_train_steps.step_ref("cylinder-bank-located"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Clamps each cast MHA-DT-02 pedestal's ledge to base MHA-FR-01; neither moves in operation (the arbor is "
            "fixed by MHA-SH-VN-54). The gears' journal drag acts about the horizontal arbor axis, perpendicular to "
            "this vertical screw, so it reaches the screw only as tension/shear through the foot; no member "
            "rotates on or about the screw axis"
        ),
        axial_capture=(
            "fillister head on the pedestal's 18-long ledge through a #8 close-clearance hole; "
            "transferred through-tapped #8-32 UNC-2B deck seat in 13 mm nominal skin; "
            "minimum checked source-model full-form overlap 10.10 mm (>=1.5D)"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py BANK_STEPS 9A/9C ('TIGHTEN MHA-DT-VN-62 AND RECHECK') and INTERFACE_NOTES; "
            "build_dt_drive_train_assembly.py ~L3377-3410 (_require_tapped_thread 'pedestal hold-down base seat', "
            "engagement checks) and pattern ~L5602-5621; arbor_pedestal_spec SCREW_HOLE_SPEC/SCREW_Z"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/pinion-block-hold-down",
        assembly="ha_harmonic_analyzer",
        member="dt_vn_slotted_screw",
        receiver="fr_harmonic_base",
        thread="#8-32 UNC",
        quantity=4,
        installed_at=dt_drive_train_steps.step_ref("rig-seats-transferred"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "Two screws clamp each MHA-DT-18 pivot block to base MHA-FR-01; the blocks never move in operation. The "
            "rocking pivot shaft and lift rod turn in the blocks about horizontal axes along the bank, "
            "perpendicular to these vertical screws, and the two-screw spacing carries any yaw as a shear couple, "
            "so no operating torque acts about a screw axis"
        ),
        axial_capture=(
            "fillister head on the block top through a #8 normal-clearance hole; "
            "38.1 mm stock less the 25.232 mm raised block gives 12.868 mm nominal "
            "insertion (13.378 mm maximum) into the transferred through-tapped "
            "#8-32 UNC-2B deck seat; the 13 mm nominal skin limits the minimum checked "
            "source-model full-form overlap to 10.10 mm; any exit protrusion is into "
            "pocket air"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "draw_dt_drive_train_assembly.py rig_steps 'rig-seats-transferred' ('FIT {slotted}X MHA-DT-VN-57') and INTERFACE_NOTES; "
            "build_dt_drive_train_assembly.py ~L3159-3192 (block screw engagement, _BLOCK_SCREW_XZ) and 2x2 grid pattern "
            "~L5582-5601; build_dt_pinion_pivot_block.py SCREW_HOLE_SPEC"
        ),
    ),
    # --- channel (MHA-CH-00): the apex set screws, and its screws into frame parts ---
    Joint(
        id="ch-channel/pivot-bracket-apex-set-screw",
        assembly="ch_channel",
        member="sh_vn_arbor_set_screw",
        receiver="ch_pivot_bracket",
        thread="#4-40 UNC",
        quantity=2,
        installed_at="set-screws-driven",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "Each screw's cup on its flat is all that holds the plain MHA-CH-05 shaft in its ear, axially and "
            "in rotation; the 20 MHA-CH-06 hubs rock on that shaft with every cam turn, so their journal drag, "
            "which reverses each stroke, reaches the screw through the flat it bears on"
        ),
        axial_capture="cup point snugged on a flat milled on MHA-CH-05 under the ear's apex tap; screw rides only its own #4-40 thread in the R8 arch wall",
        # Staked, not threadlocked: ruling U-MHA-CH-VN-53-channel-threadlocker
        # (Loctite 222) was retired, superseded by the user's standing
        # no-threadlocker rule; coordinator ruling after the user's ask timed
        # out, 2026-10-16. Mirrors the keeper set screws' stake below.
        lock=Lock.STAKED,
        lock_part="ch_pivot_bracket:staked tap mouth",
        lock_binds=("sh_vn_arbor_set_screw", "ch_pivot_bracket"),
        lock_step="set-screws-driven",
        evidence=(
            "draw_ch_channel_assembly.py _fitup_steps 'set-screws-driven' ('RUN ONE MHA-SH-VN-54 DOWN EACH APEX TAP "
            "ONTO ITS FLAT, NORTH FIRST; SNUG, AND STAKE EACH TAP MOUTH AT 2 POINTS.'); build_ch_channel_assembly.py apex set screw "
            "placement (SET_SCREW_TIP_Y); ch_pivot_bracket_spec.SET_SCREW_HOLE_SPEC (#4-40 tapped, through_next) "
            "and SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT; ch_pivot_shaft_spec flats (FLAT_DEPTH, FLAT_LENGTH)"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/north-pivot-bracket-hold-down",
        assembly="ha_harmonic_analyzer",
        member="ch_vn_bracket_hold_down_screw",
        receiver="fr_rocker_arm_support",
        thread="#8-32",
        quantity=1,
        installed_at=ch_channel_assembly_steps.step_ref("north-ear-datum"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the north pivot_bracket foot to the stationary rocker_arm_support "
            "rail (neither moves in operation); one screw per foot, but the bracket "
            "cannot turn about it: the pivot shaft runs through both brackets' ear "
            "bores, so either bracket's yaw is reacted by the shaft and the other "
            "bracket's screw, and the rocker bank's oscillating drag acts about the "
            "pivot-shaft axis (Z), perpendicular to the vertical screw axis"
        ),
        axial_capture="fillister head on the bracket foot top face; thread in a bottoming-tapped #8-32 2B blind seat transferred through the foot",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py BRACKET_SCREW_XZ loop + header (MHA-CH-VN-57, #8-32 x 5/8 fillister, one per foot); "
            "ch_vn_bracket_hold_down_screw_spec.THREAD; rocker_bracket_seat_layout.SEAT_SPEC (tapped_bottoming #8-32 2B); "
            "draw_dt_drive_train_assembly.py BANK_STEPS step north-pivot-bracket-set (MHA-DT-00 STEP 10: 'DRILL AND TAP THE RAIL "
            "THROUGH ITS FOOT ... SCREW IT DOWN AND RECHECK Y'), left screwed down while draw_ch_channel_assembly.py step "
            "north-ear-datum pushes the plain shaft south through the ear; "
            "ch_channel_assembly_steps.NORTH_BRACKET_SET_REF; "
            "config parts/ch-vn-bracket-hold-down-screw.yaml (90280A196)"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/south-pivot-bracket-hold-down",
        assembly="ha_harmonic_analyzer",
        member="ch_vn_bracket_hold_down_screw",
        receiver="fr_rocker_arm_support",
        thread="#8-32",
        quantity=1,
        installed_at=ch_channel_assembly_steps.step_ref("south-bracket-screwed"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the south pivot_bracket foot to the stationary rocker_arm_support "
            "rail (neither moves in operation); one screw per foot, but the bracket "
            "cannot turn about it: the pivot shaft runs through both brackets' ear "
            "bores, so either bracket's yaw is reacted by the shaft and the other "
            "bracket's screw, and the rocker bank's oscillating drag and end thrust "
            "act about/along the pivot-shaft axis (Z), perpendicular to the vertical "
            "screw axis"
        ),
        axial_capture="fillister head on the bracket foot top face; thread in a bottoming-tapped #8-32 2B blind seat transferred through the blade-set foot",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py BRACKET_SCREW_XZ loop + header; rocker_bracket_seat_layout.SEAT_SPEC; "
            "draw_ch_channel_assembly.py _fitup_steps 'south-bracket-screwed' (MHA-CH-00 STEP 6: 'TRANSFER THE SOUTH "
            "MHA-CH-08 FOOT HOLE INTO THE MHA-FR-05 RAIL, TAP AS MHA-FR-05, SCREW DOWN ONE MHA-CH-VN-57')"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/fulcrum-keeper-screw-in-top-frame",
        assembly="ha_harmonic_analyzer",
        member="ch_vn_frame_side_screw",
        receiver="fr_top_frame",
        thread="#2-56",
        quantity=2,
        installed_at=ch_channel_assembly_steps.step_ref(
            ch_channel_assembly_steps.KEEPERS_SET_KEY
        ),
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the only fastener of each fulcrum_keeper, which carries the end of the "
            "fulcrum_shaft that the 20 oscillating channel_levers rock on (shaft held "
            "in the keeper's reamed bore by the MHA-CH-VN-55 set screw); the shaft-end "
            "reaction is 8.25 off the screw along the shaft, so the reversing horizontal "
            "lever/bar loads apply a reversing torque about the single screw's vertical "
            "axis, and no dowel or second screw reacts it"
        ),
        axial_capture="slotted fillister head seated flush in the keeper foot counterbore (CBORE_DEPTH 2.1082); thread in top_frame KeeperTaps #2-56 x 7.6 thread / 11.5 drill blind, transferred from the foot hole at fit-up",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_ch_channel_assembly.py keeper loop (frame-side-screw at FULCRUM_KEEPER_CENTRE_Z +- KEEPER_SCREW_Z_OFF) + header; "
            "ch_fulcrum_keeper_spec.py docstring/SCREW_X/SCREW_HOLE_SPEC/KEEPER_TAP_SPEC (#2-56 blind, 11.5 drill, "
            "ThreadDepth 7.6; FOOT_SCREW_ENGAGEMENT_D) + DRAWING_NOTES 2; build_fr_top_frame.py step 'KeeperTaps' "
            "consumes KEEPER_TAP_SPEC; config parts/ch-vn-frame-side-screw.yaml (91794A080); draw_ch_channel_assembly.py "
            "step fulcrum-keepers-set ('TRANSFER EACH FOOT HOLE INTO THE RAIL, TAP AS MHA-FR-02, SCREW DOWN ONE MHA-CH-VN-52')"
        ),
    ),
    Joint(
        id="ch-channel/fulcrum-shaft-set-screw-in-keeper",
        assembly="ch_channel",
        member="ch_vn_fulcrum_set_screw",
        receiver="ch_fulcrum_keeper",
        thread="#1-72 UNF",
        quantity=2,
        installed_at=ch_channel_assembly_steps.SET_SCREWS_STAKED_KEY,
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the two set screws alone hold the plain fulcrum_shaft axially and in rotation "
            "in its keepers; the 20 channel_lever hubs rock on that shaft, so their reversing "
            "journal drag reaches each screw through its cup point on the shaft flat"
        ),
        axial_capture="cup point tightened onto the 0.3-deep set-screw flat of MHA-CH-04 through the keeper crown tap; screw rides only its own #1-72 thread in the crown (>= 1.5D full thread at the worst case, ch_fulcrum_shaft_spec.SET_SCREW_ENGAGEMENT_D)",
        lock=Lock.STAKED,
        lock_part="ch_fulcrum_keeper:staked tap mouth",
        lock_binds=("ch_vn_fulcrum_set_screw", "ch_fulcrum_keeper"),
        lock_step=ch_channel_assembly_steps.SET_SCREWS_STAKED_KEY,
        evidence=(
            "build_ch_channel_assembly.py keeper loop (ch-vn-fulcrum-set-screw on each keeper's crown tap axis); "
            "ch_fulcrum_keeper_spec.SET_SCREW_HOLE_SPEC (#1-72 tapped, through_next) + DRAWING_NOTES 2; "
            "draw_ch_fulcrum_keeper.SET_SCREW_QUALIFIER ('STAKE AT ASSEMBLY PER MHA-CH-00 STEP 13'); "
            "draw_ch_channel_assembly.py step fulcrum-set-screws-staked ('TIGHTEN ONE MHA-CH-VN-55 SET SCREW ONTO EACH "
            "FLAT AND STAKE EACH TAP MOUTH AT 2 POINTS'); ch_fulcrum_shaft_spec FLAT_DEPTH / FLAT_PITCH / "
            "FLAT_STATION_WINDOW_MM; config parts/ch-vn-fulcrum-set-screw.yaml (91375A942)"
        ),
    ),
    # --- summing, pen and the top level (the channel spring anchors) ---
    Joint(
        id="sm-summing/knife-hanger-in-mount",
        assembly="sm_summing",
        member="sm_vn_knife_hanger_stud",
        receiver="sm_knife_mount",
        thread="#10-24 UNC",
        quantity=2,
        installed_at="MHA-SM-00 STEP 6",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamps the knife-edge bearing block's top seat to the stationary crossbar underside (MOUNT_GAP 0); "
            "block and casting never move relative to each other. The two pressed MHA-SM-VN-53 dowels, held in "
            "the crossbar's underside reams and slipped into the block's round hole and slot (owner ruling "
            "2026-10-24, T+H3), react any torque about the screw axis, and the lever rock (freed lever_rock DOF) "
            "acts about machine Z, perpendicular to the vertical (Y) screw, so it reaches the thread only as "
            "cyclic tension and shear, never as torque about its own axis"
        ),
        axial_capture=(
            "plain hex head (92314A253) seated on a new 18-8 SAE washer (96659A104), whose lower "
            "bearing face seats on the crossbar's faced top; MHA-SM-00 step 4 cuts each bolt under "
            "the head to the crossbar-underside-to-washer-top height measured at its own hole plus "
            "8.92 +/-0.15, so the bolt passes the O6.045 clearance hole and reaches 8.9173 nominal "
            "(8.77..9.07 worst case) into the 9.65 +/-0.13 full thread of the #10-24 bottoming tap, "
            "drawing the block up against the casting. The independently inspected full-form cut "
            "tail covers the longest reach with 0.4916667 spare; one incomplete tip pitch leaves "
            "7.7116667 full engagement, with 0.45 minimum tip air"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "coordinator ruling 2026-10-16 (period hardware, #1188 finding): a doweled static clamp needs "
            "no lock, so the bolt goes in plain. "
            "build_sm_summing_assembly.py: module docstring, HANGER_STUD_Y/HANGER_REACH_MIN/HANGER_REACH_MAX, "
            "_assert_knife_hanger_stack; sm_summing_assembly_spec.py HANGER_FIT_REACH/"
            "HANGER_FIT_REACH_TOL; build_sm_knife_mount.py: MOUNT_GAP; sm_knife_mount_spec.py "
            "STUD_TAP_SPEC/STUD_TAP_THREAD_DEPTH_MIN/PIN_HOLE_X; fr_top_frame_spec.py HANGER_GRIP/"
            "HANGER_PIN_X; sm_vn_knife_mount_dowel_spec.py; "
            "sm_vn_knife_hanger_washer_spec.py; sm_vn_knife_hanger_stud_spec.py THREAD_LENGTH_MIN/"
            "INCOMPLETE_TIP_LEN_MAX; cad/config/parts/sm-vn-knife-hanger-stud.yaml "
            "(92314A253) installation_notes; "
            "sm_summing_assembly_sheet.ASSEMBLY_STEPS 4-6, ASSEMBLY_CHECKS 1"
        ),
    ),
    Joint(
        id="sm-summing/boss-hook-in-lever",
        assembly="sm_summing",
        member="sm_vn_boss_hook",
        receiver="sm_summing_lever",
        thread="#10-24 UNC",
        quantity=1,
        installed_at="MHA-SM-00 STEP 2",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the eyebolt rides the rocking summing lever and carries the counter-spring tension, which cycles "
            "with every rock; the spring loop working in the open eye and any off-plane pull twist the eye "
            "about the shank, and the spring pulls the anchor out of its tap"
        ),
        axial_capture=(
            "trimmed 9490T1 shank engages the full 19.05 boss height (cut end at the boss underside) and "
            "stands one jam-nut height plus a pitch of full thread above the boss top face, where the "
            "MHA-SM-VN-55 thin nut bears; no shoulder or head seats -- the wire bend has the shank diameter"
        ),
        lock=Lock.JAM_NUT,
        lock_part="sm_vn_boss_hook_jam_nut",
        lock_binds=("sm_vn_boss_hook", "sm_summing_lever"),
        lock_step="MHA-SM-00 STEP 2",
        evidence=(
            "coordinator ruling on #1189 (option a): thin #10-24 jam nut under the eye, tightened on the "
            "boss top face once the eye is clocked. build_sm_summing_assembly.py: "
            "_assert_counter_spring_hang (full boss engagement, jam-nut thread above the boss), JAM_NUT_POS "
            "and the 'boss-hook jam nut locked to lever' lock_mate; build_sm_summing_lever.py: "
            "_counter_anchor_tap; sm_summing_lever_spec.COUNTER_HOLE_SPEC; stock_anchor_geom.ANCHOR_9490T1; "
            "sm_vn_boss_hook_spec.py JAM_NUT_THREAD_MM/SHANK_LENGTH_MM; sm_vn_boss_hook_jam_nut_spec.py; "
            "cad/config/parts/sm-vn-boss-hook.yaml and sm-vn-boss-hook-jam-nut.yaml (90760A140, McMaster 10-24 "
            "narrow-profile listing read live 2026-10-16: zinc-plated steel, 5/16 wide, 7/64 high) "
            "installation_notes; sm_summing_assembly_sheet.ASSEMBLY_STEPS 2, ASSEMBLY_CHECKS 5"
        ),
    ),
    Joint(
        id="sm-summing/boss-hook-jam-nut-on-hook",
        assembly="sm_summing",
        member="sm_vn_boss_hook_jam_nut",
        receiver="sm_vn_boss_hook",
        thread="#10-24 UNC",
        quantity=1,
        installed_at="MHA-SM-00 STEP 2",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "the jam nut is tightened against the boss top face with the eye held clocked; nut, eyebolt "
            "and lever then ride as one body, and the spring's twist on the eye reaches that body through "
            "the boss thread and the nut's bearing face -- no operating torque acts on the nut's own faces"
        ),
        axial_capture="thin hex nut bearing on the boss top face, jammed against the eyebolt's thread flanks",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_sm_summing_assembly.py JAM_NUT_POS/JAM_NUT_ROWS and its lock_mate; "
            "sm_vn_boss_hook_jam_nut_spec.py; sm-vn-boss-hook-jam-nut.yaml (90760A140)"
        ),
    ),
    Joint(
        id="sm-summing/gooseneck-spring-screw",
        assembly="sm_summing",
        member="sm_gooseneck_spring_screw",
        receiver="sm_gooseneck",
        thread=gooseneck_screw.THREAD,
        quantity=1,
        installed_at="MHA-SM-00 STEP 8",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "user ruling 2026-09-21: tighten the head to clamp the supplier upper-eye "
            "band against the end piece's face. Clamp preload prevents eye rotation "
            "relative to the screw and end piece; the spring flexes below this static "
            "joint, not by swivelling on the thread. No operating rubbing torque reaches "
            "the screw axis."
        ),
        axial_capture=(
            "made MHA-SM-04 slotted cheese head clamps the double-loop band, seated on "
            "the screw's plain Ø6.35 body, to the face of MHA-SM-01's solid Ø12.70 "
            "end piece; full thread engagement runs in the end piece's blind 1/4-28 "
            "UNF-2B tap past its arm-end counterbore, which keeps the screw's die "
            "run-out out of the tap's full thread. The deepest screw tip stays inside "
            "the tap's full thread, and the bottoming tap's lead inside its drill."
        ),
        lock=Lock.NONE,
        evidence=(
            "user, 2026-09-21, binding upper-eye clamp ruling: static nonrotating "
            "eye, no threadlocker; owner rulings 2026-10-27 (#1951): 1/4-28 UNF "
            "screw with a plain Ø6.35 body and slotted cheese head, blind 1/4-28 "
            "tap in the solid end piece; owner minors sm-gooseneck.yaml RV-01 "
            "(counterbore wall 1.78 MIN under the 2.0 target) and "
            "sm-gooseneck-spring-screw.yaml RV-01 (head retention 0.95 under the "
            "1.0 check); sm_gooseneck_spring_joint.py "
            "ENGAGEMENT_MIN/COUNTERBORE_DEPTH_MIN/SCREW_RUNOUT_INTRUSION_MAX/"
            "PLUG_WALL_MIN/COUNTERBORE_WALL_MIN/DRILL_POINT_SHANK_WALL_MIN/"
            "HEAD_RETENTION_MIN/LOOP_PLAIN_MARGIN_MIN/LOOP_CORNER_CLEARANCE_MIN/"
            "TIP_THREAD_MARGIN_MIN/TAP_LEAD_DRILL_MARGIN_MIN; "
            "build_sm_summing_assembly.py gooseneck spring screw lock_mate "
            "(CAD restraint, not mechanical locking hardware); the installation "
            "step is in the summing assembly's Manufacturing Notes property "
            "(UPPER_EYE_CLAMP_NOTES) and printed as MHA-SM-00 step 8 "
            "(sm_summing_assembly_sheet.ASSEMBLY_STEPS 8, ASSEMBLY_CHECKS 3); "
            "_counter_spring_hang.assert_counter_spring_top_hang"
        ),
    ),
    Joint(
        id="pn-pen/hanger-screw-in-nut",
        assembly="pn_pen",
        member="pn_vn_hanger_screw",
        receiver="pn_vn_pen_hanger_nut",
        thread="#8-32 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the single screw is the only thing holding the hanger to the wheel bar, and the pen rod "
            "reciprocates up and down through the hanger's two U guide slots about 7 mm across from the "
            "screw axis (rod line x PEN_ROD_X, screw x -3), so the rod's sliding friction applies a "
            "reversing moment about the screw axis"
        ),
        axial_capture=(
            "hex head (93075A199, #8-32 x 1) on the wheel-bar back face; shank through the bar's #8 close "
            "clearance hole and the strap's #8 close clearance hole into the 90480A009 hex nut bearing on "
            "the strap front, clamping bar and strap between head and nut; two full pitches past the jam nut"
        ),
        lock=Lock.JAM_NUT,
        lock_part="pn_vn_pen_hanger_jam_nut",
        lock_binds=("pn_vn_hanger_screw", "pn_vn_pen_hanger_nut"),
        lock_step=(
            "nut held on the strap front while the screw is tightened from behind the bar, then the thin "
            "90760A009 nut jammed against it (pn-vn-pen-hanger-nut.yaml / pn-vn-pen-hanger-jam-nut.yaml "
            "installation_notes; drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads))"
        ),
        evidence=(
            "build_pn_pen_assembly.py: M6.10 fastener block (HANGER_SCREW_POS, HANGER_NUT_POS, "
            "HANGER_JAM_NUT_POS, HANGER_THREAD_PAST_NUT >= THREAD_PAST_MIN_PITCHES pitches past the jam "
            "nut, HANGER_NUT_RIM_RADIAL, HANGER_TIP_TO_RIM), build() hanger-screw mates and the two nut "
            "lock_mates; pn_pen_hanger_spec.py: SCREW_HOLE_SPEC HoleSpec('clearance','#8',fit='close'), "
            "SCREW_HOLE_XY, nut flats inside SCREW_HOLE_EDGE_DISTANCE; mg_wheel_bar_geom.PEN_HANGER_HOLE_SPEC "
            "(clearance #8); pn-vn-hanger-screw.yaml (93075A199, mcmaster.com/93075A199 read live 2026-10-14: "
            "8-32 x 1, fully threaded); pn-vn-pen-hanger-nut.yaml (90480A009, McMaster 8-32 hex-nut listing "
            "read live 2026-10-14: zinc-plated steel, 11/32 wide, 1/8 high); pn-vn-pen-hanger-jam-nut.yaml "
            "(90760A009, McMaster 8-32 narrow-profile listing read live 2026-10-14: zinc-plated steel, "
            "1/4 wide, 3/32 high)"
        ),
    ),
    Joint(
        id="pn-pen/hanger-jam-nut-on-screw",
        assembly="pn_pen",
        member="pn_vn_pen_hanger_jam_nut",
        receiver="pn_vn_hanger_screw",
        thread="#8-32 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "the jam nut bears only on the hanger nut's outer face; once jammed, screw, nut and jam nut "
            "act as one body, and the rod's reversing moment reaches that body only through the strap "
            "face under the hanger nut and the bar face under the screw head -- no operating torque acts "
            "on the jam nut's own faces"
        ),
        axial_capture="thin hex nut jammed on the hanger nut's outer face, against the screw's thread flanks",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_pn_pen_assembly.py HANGER_JAM_NUT_POS and its lock_mate; pn_vn_pen_hanger_jam_nut_spec.py; "
            "pn-vn-pen-hanger-jam-nut.yaml (90760A009)"
        ),
    ),
    Joint(
        id="pn-pen/thumb-screw-in-stirrup",
        assembly="pn_pen",
        member="pn_vn_pen_set_screw",
        receiver="pn_pen_frame",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the thumb screw rides the reciprocating pen carriage and its flat tip holds the marker grip in "
            "the v-block's V-groove; the pen's up/down travel reverses the nib drag on the paper and the "
            "marker's inertia ALONG the screw axis every stroke, cycling the only preload the joint has (a "
            "hand-set clamp, but not a stationary one)"
        ),
        axial_capture=(
            "knurled thumb screw (99607A213) threaded up through the stirrup's bottom-rail tap; its flat tip "
            "bears on the marker grip underside (tangent) and presses the grip into the V flanks -- the tip "
            "contact is the only preload"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        exception="U-MHA-PN-VN-51-no-lock",
        evidence=(
            "build_pn_pen_assembly.py: module docstring ('pn-vn-pen-set-screw (the thumb screw) threads up "
            "through its bottom rail and presses the grip into the V'), RIDERS lock_mate (CAD only); "
            "pn_pen_carriage_geom.py THUMB_SCREW_POS/THUMB_SCREW_REACH; pn_pen_frame_spec.py "
            "SET_SCREW_TAP_SPEC HoleSpec('tapped','#4-40'); pn-vn-pen-set-screw.yaml (99607A213)"
        ),
    ),
    Joint(
        id="pn-pen/rod-set-screw-in-v-block",
        assembly="pn_pen",
        member="pn_vn_pen_rod_set_screw",
        receiver="pn_pen_v_block",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the cup-point set screw is the only thing holding the v-block (and with it the marker's yaw, "
            "45 deg to the paper) on the rod's turned pivot end; the block hangs from it as the wire lifts "
            "the rod, rides the rod's up/down travel, and the nib drag on the paper reverses with pen "
            "direction, so the load it reacts reverses every stroke"
        ),
        axial_capture=(
            "#4-40 x 3/16 cup point (91375A105) in the block's front-face tap, recessed below the face, its "
            "cup biting the Ø.126 pivot end inside the pivot bore and carrying the hanging carriage; the "
            "square's shoulder seats on the block top and sets the height"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        exception="U-MHA-PN-VN-52-no-lock",
        evidence=(
            "pn_pen_v_block_spec.py SET_SCREW_TAP_SPEC HoleSpec('tapped', '#4-40', end='through_next'), "
            "SET_SCREW_Y/PIVOT_BORE_X; pn_pen_carriage_geom.py ROD_SET_SCREW_POS (cup on the bore wall); "
            "build_pn_pen_assembly.py RIDERS lock_mate; pn-vn-pen-rod-set-screw.yaml (91375A105). The .367 "
            "tap holds the 4.76 screw with no room for a second jam screw; the user waived "
            "drawing-guidelines.md rule 23 for this joint (U-MHA-PN-VN-52-no-lock)"
        ),
    ),
    Joint(
        id="pn-pen/adjust-screw-in-rod",
        assembly="pn_pen",
        member="pn_pen_adjust_screw",
        receiver="pn_pen_rod",
        thread="#0-80 UNF",
        quantity=1,
        installed_at="",
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "the eye stud sets the pen height on the wire (screwed in or out of the rod top at setup) and "
            "then carries the whole carriage's weight and the pen wire's reversing pull every stroke"
        ),
        axial_capture=(
            "#0-80 stud threaded 4.0 (2.6 D) into the rod's blind top tap; the wire ties through the eye "
            "head above the jam nut"
        ),
        lock=Lock.JAM_NUT,
        lock_part="pn_vn_pen_adjust_nut",
        lock_binds=("pn_pen_adjust_screw", "pn_pen_rod"),
        lock_step=(
            "brass #0-80 jam nut run down the stud and tightened on the rod's top face once the pen height "
            "is set (drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads))"
        ),
        evidence=(
            "pn_pen_rod_spec.py STUD_TAP_SPEC/STUD_ENGAGEMENT; pn_pen_adjust_screw_spec.py THREAD; "
            "pn_pen_carriage_geom.py STUD_POS/NUT_POS (nut seated on the rod top); "
            "build_pn_pen_assembly.py RIDERS lock_mate; pn-vn-pen-adjust-nut.yaml (92671A115)"
        ),
    ),
    Joint(
        id="pn-pen/adjust-nut-on-stud",
        assembly="pn_pen",
        member="pn_vn_pen_adjust_nut",
        receiver="pn_pen_adjust_screw",
        thread="#0-80 UNF",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "the jam nut is tightened against the rod's top face; nut, stud and rod then ride as one body, "
            "and the only operating load, the pen wire's pull at the eye, acts ALONG the stud axis -- no "
            "operating torque acts about the thread axis"
        ),
        axial_capture="hex nut bearing on the rod's top face, jammed against the stud's thread flanks",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "pn_pen_carriage_geom.py NUT_POS/NUT_ROWS; pn_vn_pen_adjust_nut_spec.py; "
            "build_pn_pen_assembly.py RIDERS lock_mate; pn-vn-pen-adjust-nut.yaml (92671A115)"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/channel-anchor-in-summing-plate",
        assembly="ha_harmonic_analyzer",
        member="ch_vn_spring_hook",
        receiver="sm_summing_lever",
        thread="#6-32 UNC",
        quantity=1,
        per_channel=True,  # build_ch_channel_assembly places one per range(CHANNELS)
        installed_at=ha_harmonic_analyzer_assembly_steps.step_ref("channel-anchors-set"),
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "per-channel calibration unscrews each anchor to set its spring preload (5% of preload per turn); "
            "the anchor also rides the rocking summing lever under a channel-spring load that cycles with the "
            "crank, and that spring pulls the anchor out of its tap"
        ),
        axial_capture=(
            "the trimmed 9489T111 shank crosses the full 7.00 uniform coefficient-plate tap and carries the MHA-CH-14 jam "
            "nut on the plate underside, which bears the spring's upward pull; the Ø3.175 neck shoulders on the plate top "
            "only when fully seated (calibration backs it off up to 1 counted turn), and at the worst case "
            "(shortest in-band part, whole budget backed out) two full turns still show below the nut"
        ),
        lock=Lock.JAM_NUT,
        lock_part="ch_anchor_jam_nut",
        lock_binds=("ch_vn_spring_hook", "sm_summing_lever"),
        lock_step=ha_harmonic_analyzer_assembly_steps.step_ref("channel-anchors-set"),
        evidence=(
            "coordinator rulings 2026-10-16 (period hardware; option A after the hex-pitch collision): a made "
            "round #6-32 jam nut on the plate underside, driven by a forked driver through its notched face "
            "while the eye is held at its clocking. "
            "build_ha_harmonic_analyzer_assembly.py module docstring (channel spring anchors thread DOWN into "
            "the 20 #6-32 taps); build_ch_channel_assembly.py _assert_spring_mount and "
            "CHANNEL_ANCHOR_NUT_XY/CHANNEL_ANCHOR_NUT_ROWS; ch_vn_spring_hook_spec.py SHANK_LENGTH_MM/"
            "PROTRUSION_MAX_MM/full_threads_past_nut_mm/ADJUSTMENT_TURNS/ANCHOR_INSTALL_STEP; "
            "sm_summing_lever_spec.HOLE_SPEC; stock_anchor_geom.ANCHOR_9489T111; ch_anchor_jam_nut_spec.py; "
            "cad/config/parts/ch-vn-spring-hook.yaml installation_notes"
        ),
    ),
    Joint(
        id="ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor",
        assembly="ha_harmonic_analyzer",
        member="ch_anchor_jam_nut",
        receiver="ch_vn_spring_hook",
        thread="#6-32 UNC",
        quantity=1,
        per_channel=True,  # build_ch_channel_assembly places one per range(CHANNELS)
        installed_at=ha_harmonic_analyzer_assembly_steps.step_ref("channel-anchors-set"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "the jam nut is tightened against the plate underside with the eye held clocked; nut, anchor and "
            "lever then ride as one body, and the spring's twist on the eye reaches that body through the "
            "plate thread and the nut's bearing face -- no operating torque acts on the nut's own faces"
        ),
        axial_capture="round nut bearing on the plate underside, jammed against the anchor's thread flanks",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step=ha_harmonic_analyzer_assembly_steps.step_ref("channel-anchors-set"),
        evidence=(
            "build_ch_channel_assembly.py CHANNEL_ANCHOR_NUT_XY/CHANNEL_ANCHOR_NUT_ROWS; "
            "ch_anchor_jam_nut_spec.py; ch-anchor-jam-nut.yaml"
        ),
    ),
    # --- measuring stick ---
    Joint(
        id="ms-measuring-stick/stop-thumbscrew",
        assembly="ms_measuring_stick",
        member="sh_vn_thumb_screw",
        receiver="ms_stop_block",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="MHA-MS-00 STEP 5",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp on a gauge: the stop is pinched at a chosen mark on the measuring "
            "stick, which is parked on the deck and is not part of any running chain -- no operating torque "
            "or motion reaches the thumbscrew axis"
        ),
        axial_capture=(
            "thumbscrew points down through the block's .336 tapped wall into the window; its tip presses "
            "the stick's plain face so the graduated face bears on the opposite fixed window wall; "
            "knurled head and collar sit above the block's tapped face"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "ms_stop_spec.py THUMB_TAP_SPEC (#4-40 through the tapped wall); ms_measuring_stick_assembly_spec.py "
            "THUMB_ORIGIN/THUMB_TIP_Y/THUMB_COLLAR_FACE_Y (tip on the stick's plain face, collar above the "
            "tapped block face); build_ms_measuring_stick_assembly.py "
            "'stop thumbscrew points down onto the stick's plain face'"
        ),
    ),
    Joint(
        id="ms-measuring-stick/plate-screws",
        assembly="ms_measuring_stick",
        member="ms_vn_stop_plate_screw",
        receiver="ms_stop_block",
        thread="#2-56 UNC",
        quantity=2,
        installed_at="MHA-MS-00 STEP 4",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "cover-plate screws: the plate closes the block's window and never moves against the block; "
            "the stick slides inside the window and the thumbscrew clamps its graduated face against the "
            "opposite fixed window wall, so no operating torque reaches the screw axes"
        ),
        axial_capture=(
            "fillister heads bear on the plate's outer face through its .094 #2 close clearance holes; threads in the "
            "block's #2-56 blind taps, tips short of the tapped depth"
        ),
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "ms_stop_spec.py PLATE_TAP_SPEC/PLATE_CLEARANCE_SPEC, PLATE_HOLE_XS; "
            "ms_measuring_stick_assembly_spec.py PLATE_SCREW_ORIGINS/PLATE_SCREW_TAP_RESERVE; "
            "build_ms_measuring_stick_assembly.py 'cover plate screws into the block'"
        ),
    ),
    # --- magnifier ---
    Joint(
        id="ha-harmonic-analyzer/magnifying-bracket-screws",
        assembly="ha_harmonic_analyzer",
        member="mg_vn_magnifying_bracket_screw",
        receiver="sm_summing_lever",
        thread="#2-56 UNC",
        quantity=2,
        installed_at=ha_harmonic_analyzer_assembly_steps.step_ref("magnifier-bracket-screwed"),
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "clamp the bracket flange to the summing lever; both rock together "
            "about the knife edge without relative motion at the seat. Two "
            "screws react the bracket moment as a shear couple, not operating "
            "spin friction about either screw axis"
        ),
        axial_capture="fillister heads on the bracket flange front face; shanks pass normal #2 clearance into the lever's blind bottoming #2-56 seats",
        lock=Lock.NONE,
        evidence=(
            "build_mg_magnifier_assembly.py BRACKET_SCREW_POSITIONS loop, screws locked "
            "to bracket; magnifying_bracket_joint_layout.CLEARANCE_SPEC/TAP_SPEC"
        ),
    ),
    Joint(
        id="mg-magnifier/wheel-axle-nut",
        assembly="mg_magnifier",
        member="mg_vn_wheel_axle_nut",
        receiver="mg_wheel_axle",
        thread="#4-40 UNC",
        quantity=2,
        installed_at=mg_magnifier_assembly_steps.ENDSHAKE_SET_KEY,
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the nut retains the magnifying wheel, which the lever-wire (WIRE 1) turns back and forth every "
            "harmonic cycle (yoke-coupled to the rocking lever); the spigot face rubs the MHA-MG-VN-55 washer "
            "the nut seats on, so reversing friction drag reaches the nut thread; the nut's own position "
            "also sets the hub endshake (ADJUSTER character too)"
        ),
        axial_capture=(
            "first nut run down on the MHA-MG-VN-55 washer at the spigot face until the wheel turns free "
            "without rattle (endshake 0.05-0.15, mg_wheel_group.ENDSHAKE); the back washer MHA-MG-VN-54 "
            "seats the hub on the MHA-MG-11 axle spacer, which seats on the bar front face"
        ),
        lock=Lock.JAM_NUT,
        lock_part="mg_vn_wheel_axle_nut:locknut",
        lock_binds=("mg_vn_wheel_axle_nut", "mg_wheel_axle"),
        lock_step=mg_magnifier_assembly_steps.LOCKNUT_JAMMED_KEY,
        evidence=(
            "build_mg_magnifier_assembly.py:build (lock_mates 'wheel-axle nut locked to the axle' / 'wheel-axle locknut locked to the axle' at NUT_D / LOCKNUT_D); "
            "build_mg_vn_wheel_axle_nut.py + diagnostics/diag_build_92671A005.py; "
            "mg_vn_wheel_axle_nut_spec.py THREAD/COUNT; mg_wheel_axle_spec.py THREAD_CALLOUT; "
            "mg_wheel_group.py NUT_D/LOCKNUT_D/ENDSHAKE; config parts/mg-vn-wheel-axle-nut.yaml installation_notes"
        ),
    ),
    Joint(
        id="mg-magnifier/lever-in-bracket",
        assembly="mg_magnifier",
        member="mg_magnifying_lever",
        receiver="mg_magnifying_bracket",
        thread="1/4-20 UNC",
        quantity=1,
        installed_at=mg_magnifier_assembly_steps.LEVER_THREADED_KEY,
        exposure=Exposure.ADJUSTER,
        exposure_reason=(
            "rotation of the unseated thread sets the installed ThreadProjection; "
            "there is no shoulder or preload, so this is not a static clamp. "
            "The nominal load has no torque about the X thread axis, but the "
            "knife-rocking assembly exposes it to vibration and possible backoff."
        ),
        axial_capture=(
            "1/4-20 UNC-2A lever end in the steel UNC-2B through neck, installed "
            "to native ThreadProjection, with at least 1.5D FULL engaged thread; "
            "the tip reaches the far face and the plain rod has no shoulder"
        ),
        lock=Lock.NONE,
        exception="U-MHA-MG-03-no-lock",
        evidence="mg_lever_thread_joint.py; mg_magnifier_assembly_spec.THREAD_PROJECTION; mg_magnifier_assembly_sheet.STEP_TEXT",
    ),
    Joint(
        id="mg-magnifier/clamp-thumb-screw",
        assembly="mg_magnifier",
        member="sh_vn_thumb_screw",
        receiver="mg_magnifying_clamp",
        thread="#4-40 UNC",
        quantity=1,
        installed_at=mg_magnifier_assembly_steps.CLAMP_SET_KEY,
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp: pinches the hex clamp onto the Ø6.35 lever rod at the chosen "
            "magnification radius; clamp, vertical rod and fixture then ride the lever as one rigid "
            "body (lock mates), the lever rocks about the knife line (machine Z) perpendicular to the "
            "screw axis (machine Y), and the wire pull lies in the plumb plane through the screw axis "
            "(option A1, #1559), so no operating torque acts about the screw axis"
        ),
        axial_capture="tip bears on the Ø6.35 lever rod through the top-face #4-40 tap on the hex axis that breaks into the lever bore across the corners (modelled backed-out, tip tangent)",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build ('thumb-screw (clamp)', lock_mate 'thumb-screw locked to clamp'; "
            "docstring 'Documented simplifications'); build_mg_magnifying_clamp.py ThumbTap from "
            "mg_magnifying_clamp_geom.py THUMB_TAP_SPEC + THUMB_ENGAGEMENT_WORST; "
            "mg_magnifying_clamp_spec.py DRAWING_NOTES; sh_vn_thumb_screw_spec.py THUMB_SPEC"
        ),
    ),
    Joint(
        id="mg-magnifier/vertical-rod-in-clamp",
        assembly="mg_magnifier",
        member="mg_magnifying_vertical_rod",
        receiver="mg_magnifying_clamp",
        thread="#4-40 UNC",
        quantity=1,
        installed_at="",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "screwed home on its shoulder against the clamp's bottom face (owner ruling #1559: no set "
            "screw, bonding or thread lock); rod, clamp and fixture ride the lever as one rigid body, and "
            "the lever wire's pull at the fixture hook lies in the plumb plane through the rod axis "
            "(option A1: hook, rod and drum lane coplanar), so its moment is about machine Z and no "
            "operating torque acts about the rod's thread axis (machine Y)"
        ),
        axial_capture="shoulder seated on the clamp's bottom face by thread torque; worst-case full-thread engagement mg_rod_clamp_joint.ENGAGEMENT_WORST 4.605 >= 1.5D (4.2675)",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build (lock_mate 'vertical-rod locked to clamp'; VROD_TOP_Y = clamp bottom face + SHOULDER_X); "
            "build_mg_magnifying_clamp.py RodTap from mg_rod_clamp_joint.py ROD_TAP_SPEC + ENGAGEMENT_WORST; "
            "mg_magnifying_vertical_rod_geom.py SHOULDER_X + SEAT_LAND_WORST; "
            "sh_vn_music_wire_lever_geom.py HOOK_Z == DRUM_END_Z"
        ),
    ),
    Joint(
        id="mg-magnifier/fixture-thumb-screw",
        assembly="mg_magnifier",
        member="sh_vn_thumb_screw",
        receiver="mg_output_fixture",
        thread="#4-40 UNC",
        quantity=1,
        installed_at=mg_magnifier_assembly_steps.FIXTURE_SET_KEY,
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason=(
            "hand-set operator clamp: locks the output fixture's hex body at its set height on the vertical rod "
            "(sets the trace's vertical placement); fixture and rod never move relative in operation, the "
            "wire pull at the spigot groove (in the rod's plane) runs mostly along the rod (Y), and the fixture rides "
            "the lever as one rigid body with the clamp chain, i.e. no operating torque about the horizontal "
            "screw axis (fixture local X, the spigot axis)"
        ),
        axial_capture="tip bears on the Ø5 vertical rod through the #4-40 tap running axially from the spigot face into the rod bore (modelled backed-out, tip tangent, collar standing off the spigot face)",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence=(
            "build_mg_magnifier_assembly.py:build ('thumb-screw (output fixture)', lock_mate 'output-fixture thumb-screw locked to fixture'; "
            "FIXTURE_SCREW_TIP_X = rod radius, FIXTURE_SCREW_STANDOFF > 0; docstring 'both thumb screws are modeled backed-out'); "
            "mg_output_fixture_geom.py TAP_SPEC + SPIGOT_FACE_X (axial tap from the spigot face into the rod bore); "
            "mg_output_fixture_spec.py TAP_SPEC + DRAWING_NOTES; config parts/sh-vn-thumb-screw.yaml aggregate quantity 3 (MG x2 + MS x1); "
            "dimensions.yaml ch20 thumb screw x2 (sliding clamp + output fixture)"
        ),
    ),
    Joint(
        id="mg-magnifier/wheel-bar-clamp-screws",
        assembly="mg_magnifier",
        member="sh_vn_clamp_screw",
        receiver="sh_column_clamp_back",
        thread="#8-32 UNC",
        quantity=2,
        installed_at=mg_magnifier_assembly_steps.COLUMN_CLAMP_STARTED_KEY,
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
            "sh_column_clamp_back_geom.py HOLE_SPEC tapped #8-32; sh_column_clamp_front_geom.py EAR_HOLE_SPEC clearance #8; "
            "sh_column_clamp_fit.py grip and screw-line budget; mg_wheel_bar_geom.py CLAMP_HOLE_SPEC; diag_mcmaster_fillister.py 90280A201"
        ),
    ),
    # --- paper_drive (MHA-PD-00, pd_paper_drive_assembly_steps) ---
    Joint(
        id="pd-paper-drive/clamp-screw-in-back-arc",
        assembly="pd_paper_drive",
        member="sh_vn_clamp_screw",
        receiver="sh_column_clamp_back",
        thread="#8-32 UNC",
        quantity=4,
        installed_at="bar-clamped",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps support bar + front arc + back arc around a stationary frame column; none of these parts moves in operation, the head sits 0.80 sub-flush in a bar counterbore so the sliding platen never touches it, and the platen's X-wise slide drag reaches the pair of screws per column only as shear across their Z axes, never as torque about them",
        axial_capture="fillister head seated in the support_bar front counterbore (CLAMP_CBORE_DEPTH, 0.80 recess); shank through bar + column_clamp_front #8 clearance; threads into column_clamp_back's through #8-32 tap",
        lock=Lock.NONE,
        lock_part="",
        lock_binds=(),
        lock_step="",
        evidence="build_pd_paper_drive_assembly.py:build (clamp-screw seeds + 'support clamp-screw pattern') and _assert_fastener_stacks (90280A201 clamps); draw_pd_paper_drive_assembly._step_text 'bar-clamped'; sh_column_clamp_back_geom.HOLE_SPEC tapped #8-32; build_pd_support_bar.CLAMP_HOLE_SPEC/CLAMP_HOLE_X; sh_column_clamp_front_geom.EAR_HOLE_SPEC",
    ),
    Joint(
        id="pd-paper-drive/clip-screw-in-platen",
        assembly="pd_paper_drive",
        member="pd_vn_platen_clip_screw",
        receiver="pd_platen",
        thread="#2-56 UNC",
        quantity=4,
        installed_at="clips-fitted",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps each brass paper clip to the platen, and both travel together as one body. The clip's spring-rail reaction acts along the screw axis (preload only), and two screws per clip stop the clip turning, so no operating torque acts about either screw axis",
        axial_capture="pan head directly on the clip's flat 0.8 brass sheet (no seat boss); shank through the clip #2 clearance into the platen's through #2-56 tap and rear boss, 5.55 mm engagement (pd_platen_spec.SOCKET_THREAD_ENGAGEMENT, 2.54D), tip flush with the boss",
        lock=Lock.NONE,
        evidence="build_pd_paper_drive_assembly.py:build ('platen clip-screw grid') and _assert_fastener_stacks (clip #2-56 engagement, tip flush); draw_pd_paper_drive_assembly._step_text 'clips-fitted'; pd_platen_spec.SOCKET_SPEC tapped #2-56 through; build_pd_platen_clip.CLIP_THICKNESS",
    ),
    Joint(
        id="pd-paper-drive/guide-screw-in-guide",
        assembly="pd_paper_drive",
        member="sh_vn_brass_fillister_screw",
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
        member="pd_vn_guide_lock_screw",
        receiver="pd_platen_guide",
        thread="#4-40 UNC",
        quantity=8,
        installed_at="platen-hung",
        exposure=Exposure.STATIC_CLAMP,
        exposure_reason="clamps each guide-lock plate to the back of its guide rail, and both travel with the platen as one body. The plate stands the fitted lock gap (0.05-0.25, R9-47) off the bar's back face and only touches if the platen is pulled forward, a load along the screw axis. Two screws per plate stop it turning, so no operating torque acts about either screw axis",
        axial_capture="slotted pan head on the 1/16-sheet guide_lock back face; shank through the lock's 1/8 drilled hole into the guide's rear #4-40 tap (through, R9-48), tip stopping inside the rail",
        lock=Lock.NONE,
        evidence="build_pd_paper_drive_assembly.py:build ('platen lock-screw grid', LOCK_SCREW_XY); draw_pd_paper_drive_assembly._step_text 'platen-hung' (fitted loose) and 'guide-locks-set' (snug, push, tighten); pd_vn_guide_lock_screw_spec.ENGAGEMENT_WORST; build_pd_platen_guide.HOLE_X/LOCK_SCREW_THREAD_ENGAGEMENT (4 per rail x 2 rails); pd_guide_lock_spec.HOLE_SPEC; pd_platen_guide_spec.LOCK_GAP_FIT",
    ),
    Joint(
        id="pd-paper-drive/arm-plate-screws",
        assembly="pd_paper_drive",
        member="pd_vn_transgear_arm_plate_screw",
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
        member="pd_vn_transgear_pivot_screw",
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
            "shoulder bottomed on the bar's back face with the MHA-PD-20 spacer pressed on it flush; the "
            "MHA-PD-VN-63 spring under the MHA-PD-VN-67 shim and the head holds the arm on the spacer "
            "(room 0.70-1.00, transgear_hanger_joints.SPRING_ROOM_MIN/MAX); thread through the bar's "
            "#8-32 through tap, the tip faced 0.20-0.50 below the front face at fit-up "
            "(worst-case engagement ~1.52 D, transgear_hanger_joints.PIVOT_ENGAGEMENT_WORST_D)"
        ),
        lock=Lock.STAKED,
        lock_part="pd_support_bar:staked tap mouth",
        lock_binds=("pd_vn_transgear_pivot_screw", "pd_support_bar"),
        lock_step="hanger-pivoted",
        evidence=(
            "user ruling 2026-10-15 (rule 23 staked end): draw_pd_paper_drive_assembly._step_text "
            "'hanger-pivoted' (face the tip below the bar's front face, then stake the tap's front "
            "mouth onto it; threadlocker optional) and its stake detail view; "
            "build_pd_paper_drive_assembly.py 'pd-vn-transgear-pivot-screw' placement and its "
            "tip-recess check; pd_support_bar_spec.PIVOT_TAP_THREAD (through); "
            "pd_vn_transgear_pivot_screw_spec.TIP_RECESS; transgear_hanger_joints.SPRING_ROOM_MIN/MAX, "
            "LATCH_ARM_ANGLE_PLAY and PIVOT_ENGAGEMENT_WORST_D"
        ),
    ),
    Joint(
        id="pd-paper-drive/disc-screws",
        assembly="pd_paper_drive",
        member="pd_vn_transgear_disc_screw",
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
            "lock mates; pd_rack_pinion_spec.TAP_SPEC; pd_vn_transgear_disc_screw_spec.ENGAGEMENT_WORST_D; "
            "pd_transgear_disc_hub_geometry.SCREW_COUNT"
        ),
    ),
    Joint(
        id="pd-paper-drive/knob-cup-on-journal",
        assembly="pd_paper_drive",
        member="pd_transgear_knob_cup",
        receiver="pd_transgear_knob_shaft",
        thread="none: Ø6 reamed slip fit, cross-pinned (R9-70 replaced the rear screw)",
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
            "the MHA-PD-VN-62 1/16 x 5/8 slotted spring pin pressed through the cup and the journal, "
            "3.0 from the cup's front face, in a Ø1.6 +0.05/0 hole match-drilled with the cup set "
            "on a 0.2 feeler at the boss; the pin carries the end-float thrust and the drag in "
            "shear, its ends inside the cup's O.D."
        ),
        lock=Lock.CROSS_PIN,
        lock_part="pd_vn_transgear_knob_cup_pin",
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
        member="sh_vn_fillister_screw_90280a108",
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
            "pd_support_bar_spec.BRACKET_TAP_X/BRACKET_TAP_SPEC; pd_latch_hook_bracket_screw_spec."
            "ENGAGEMENT_NOMINAL"
        ),
    ),
    Joint(
        id="pd-paper-drive/thumbnut-on-knob-shaft",
        assembly="pd_paper_drive",
        member="pd_transgear_thumbnut",
        receiver="pd_transgear_knob_shaft",
        thread="#8-32 UNC",
        installed_at="collar-shoulder-seated",
        exposure=Exposure.OSCILLATING,
        exposure_reason=(
            "the nut seats on the drive collar's pilot, faced 0.05-0.15 proud of the T24's front "
            "face, so its axial clamp passes through the collar's rear face onto the shaft's "
            "actual pinion front face F while the T24 floats free under its flange. The drive "
            "goes T24 -> the two pressed drive pins -> collar -> D-flat -> shaft; the free T24 "
            "rocks through its pin backlash at each reversal and, pushed forward, can rub the "
            "flange (machinist review of 6c385465d)"
        ),
        axial_capture=(
            "the nut's flange seat face bears on the collar pilot's faced front; #8-32 UNC-2B "
            "through on the shaft's die-cut front thread. At collar-shoulder-seated the collar's "
            "fitted rear face bears on actual F and reacts the nut's axial clamp, independently "
            "of its D-flat torque key; the flange retains the wheel on the drive pins and is "
            "removed by hand for gear swaps"
        ),
        lock=Lock.NONE,
        exception="U-MHA-PD-13-no-lock",
        evidence=(
            "draw_pd_paper_drive_assembly._step_text 'pilot-faced-to-fit', "
            "'collar-rear-faced-to-fit', 'collar-shoulder-seated' and 'fitup-accepted' "
            "(T24 free under the nut); "
            "build_pd_paper_drive_assembly.py THUMBNUT_Z0 on the pilot and 'transgear-thumbnut "
            "(seated on collar pilot' placement; transgear_drive_collar_spec PILOT_PROUD_RANGE, "
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
        "fr_frame", "build_fr_frame_assembly.py", '"fr-vn-lag-screw"'
    ),
    "fr-frame/nameplate-screw-in-base": Occurrence(
        "fr_frame", "build_fr_frame_assembly.py", "NAMEPLATE_SCREW_"
    ),
    "ha-harmonic-analyzer/gooseneck-set-screw-in-top-frame": Occurrence(
        "ha_harmonic_analyzer", "build_fr_frame_assembly.py", '"fr-vn-gooseneck-set-screw"'
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
        "dt_drive_train", "build_dt_drive_train_assembly.py", '"dt-vn-cone-tip-adjuster"'
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
        "dt_drive_train", "build_dt_drive_train_assembly.py", '"sh-vn-arbor-set-screw"'
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
        '"dt-vn-pedestal-hold-down-screw"',
    ),
    "ha-harmonic-analyzer/pinion-block-hold-down": Occurrence(
        "ha_harmonic_analyzer", "build_dt_drive_train_assembly.py", '"dt-vn-slotted-screw"'
    ),
    "ch-channel/pivot-bracket-apex-set-screw": Occurrence(
        "ch_channel", "build_ch_channel_assembly.py", '"sh-vn-arbor-set-screw"'
    ),
    "ha-harmonic-analyzer/north-pivot-bracket-hold-down": Occurrence(
        "ha_harmonic_analyzer", "ch_channel_assembly_steps.py", "north-ear-datum"
    ),
    "ha-harmonic-analyzer/south-pivot-bracket-hold-down": Occurrence(
        "ha_harmonic_analyzer", "ch_channel_assembly_steps.py", "south-bracket-screwed"
    ),
    "ha-harmonic-analyzer/fulcrum-keeper-screw-in-top-frame": Occurrence(
        "ha_harmonic_analyzer", "build_ch_channel_assembly.py", '"ch-vn-frame-side-screw"'
    ),
    "ch-channel/fulcrum-shaft-set-screw-in-keeper": Occurrence(
        "ch_channel", "build_ch_channel_assembly.py", '"ch-vn-fulcrum-set-screw"'
    ),
    "ha-harmonic-analyzer/channel-anchor-in-summing-plate": Occurrence(
        "ha_harmonic_analyzer", "build_ch_channel_assembly.py", "direct threaded seat"
    ),
    "ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor": Occurrence(
        "ha_harmonic_analyzer", "build_ch_channel_assembly.py", "CHANNEL_ANCHOR_NUT_XY"
    ),
    "ms-measuring-stick/stop-thumbscrew": Occurrence(
        "ms_measuring_stick",
        "build_ms_measuring_stick_assembly.py",
        "stop thumbscrew points down onto the stick's plain face",
    ),
    "ms-measuring-stick/plate-screws": Occurrence(
        "ms_measuring_stick",
        "build_ms_measuring_stick_assembly.py",
        "cover plate screws into the block",
    ),
    "sm-summing/knife-hanger-in-mount": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", "HANGER_STUD_Y"
    ),
    "sm-summing/boss-hook-in-lever": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", "boss-hook keyed"
    ),
    "sm-summing/boss-hook-jam-nut-on-hook": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", "JAM_NUT_POS"
    ),
    "sm-summing/gooseneck-spring-screw": Occurrence(
        "sm_summing", "build_sm_summing_assembly.py", '"sm-gooseneck-spring-screw"'
    ),
    "pn-pen/hanger-screw-in-nut": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", "HANGER_NUT_POS"
    ),
    "pn-pen/hanger-jam-nut-on-screw": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", "HANGER_JAM_NUT_POS"
    ),
    "pn-pen/thumb-screw-in-stirrup": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", '"pn-vn-pen-set-screw", THUMB_SCREW_POS'
    ),
    "pn-pen/rod-set-screw-in-v-block": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", '"pn-vn-pen-rod-set-screw", ROD_SET_SCREW_POS'
    ),
    "pn-pen/adjust-screw-in-rod": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", '"pn-pen-adjust-screw", STUD_POS'
    ),
    "pn-pen/adjust-nut-on-stud": Occurrence(
        "pn_pen", "build_pn_pen_assembly.py", '"pn-vn-pen-adjust-nut", NUT_POS'
    ),
    "ha-harmonic-analyzer/magnifying-bracket-screws": Occurrence(
        "ha_harmonic_analyzer", "build_mg_magnifier_assembly.py", "BRACKET_SCREW_POSITIONS"
    ),
    "mg-magnifier/wheel-axle-nut": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "wheel-axle nut locked to the axle"
    ),
    "mg-magnifier/lever-in-bracket": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "bracket affixes the lever"
    ),
    "mg-magnifier/clamp-thumb-screw": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "thumb-screw locked to clamp"
    ),
    "mg-magnifier/vertical-rod-in-clamp": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "vertical-rod locked to clamp"
    ),
    "mg-magnifier/fixture-thumb-screw": Occurrence(
        "mg_magnifier", "build_mg_magnifier_assembly.py", "output-fixture thumb-screw locked to fixture"
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
        "pd_paper_drive", "build_pd_paper_drive_assembly.py", '"pd-vn-transgear-pivot-screw",'
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
        "transgear-thumbnut (seated on collar pilot",
    ),
}

if __name__ == "__main__":
    sys.exit(main())
