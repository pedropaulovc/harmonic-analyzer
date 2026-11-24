"""The cutoff blade parts each part at the length its plan prints.

The blade's two faces stand one blade width apart, and only the face toward
the part forms its parted face. Touching one face on the faced end, zeroing
the DRO there and parting at Z-L with the other face forming the part leaves
the part one blade width short (#3312). So every plan that parts or grooves
with the cutoff blade says, for each DRO setting, which face touched and what
the DRO was set to. The face the DRO then reads follows: the touched face, or
the other one when the setting is the blade's width. Every cut positioned by
the DRO must name that face. A part parted from the faced end at
``Z-{{cad.part_off_*}}`` lies on the tailstock side of the blade, so its
tailstock-side face cuts it.

Every plan that names a cutoff tool states that tool's width as
``blade_width_in``, equal to the tool's ``width_in`` in the shop inventory, and
only a ``cutoff_blade`` record carries a cutting width (a holder's width is
its body's, not its kerf: #3312's .125 was the 3212A119 holder's). The
parting kerf the plan spaces its parts by follows that width, within an
authored allowance. A blade-width DRO setting prints ``blade_width_in``. A
part-off placed without the DRO measures to the blade's near side, the side
toward the part.

Every ``cad/process/*/plan.toml`` that names a cutoff tool is checked, so a
plan added later is held to the same rule.
"""

from __future__ import annotations

import re
import tomllib

import pytest

import _process_plans
import _shop_equipment

_TOOLS = _shop_equipment.load()["tools"]
# Inventory kinds a plan may part or groove with.
CUTOFF_KINDS = ("cutoff_blade", "cutoff_holder", "cutoff_insert_set")
CUTOFF = {key: tool for key, tool in _TOOLS.items() if tool.get("kind") in CUTOFF_KINDS}
# The kerf a plan spaces its parts by: the blade's width plus at most this
# (wander, or a step over that widens a deep groove).
KERF_OVER_MAX_IN = 0.015

# "{{cad.part_off_in:.3dot}}" -> "<cad.part_off_in>": no colon of a format
# spec is left to end a phrase early.
_BINDING = re.compile(r"\{\{\s*([^}:\s]+)[^}]*\}\}")
_FACE = r"(chuck|tailstock)-side face"
# A DRO setting: the face touched, then the value set there.
_SET = re.compile(
    rf"(?:blade's|its) {_FACE} (?:on|onto) [^.:;]*? and set (?:the )?DRO Z"
    r"(?: there)?(?: to)? ?(?P<value>.*?)(?=[:;]|\.(?:\s|$)|, as in|$)"
)
# The face a setting says the DRO then reads.
_READS = re.compile(
    rf"DRO (?:then |again |now )?reads (?:the |its )?(?:blade's )?{_FACE}"
)
# A cut placed by the DRO: the face named at a Z or on an end's plane, or
# "with that face" (the face the DRO reads).
_CUT = re.compile(
    rf"(?:with (?:that|this) face|(?:the blade's|its|the) {_FACE}) (?:at|on) "
    r"(?P<at>(?:DRO )?Z[-+]?\S*|end [^,.;)]*)"
)
# The datum wordings #3312 found: a face no blade can touch the faced end
# with, and a zero that names no face.
_WRONG = ("Z0-side", "zero DRO Z for the blade")
_OTHER = {"chuck": "tailstock", "tailstock": "chuck"}


def _text(instruction: str) -> str:
    return _BINDING.sub(r"<\1>", instruction)


def faults(plan: dict, tools: dict = CUTOFF) -> list[str]:
    """Each place ``plan`` parts or grooves with a face the DRO does not
    read, or with a blade width or kerf that disagrees with the blade's
    record in ``tools`` (inventory key -> record)."""
    refs = {
        tool["id"]: tool["ref"]
        for tool in plan.get("tools", ())
        if tool.get("ref") in tools
    }
    cutoff = set(refs)
    if not cutoff:
        return []
    found: list[str] = []
    width_settings = 0
    for s, setup in enumerate(plan.get("setups", ()), 1):
        reading = None
        for o, op in enumerate(setup.get("operations", ()), 1):
            where = f"setup {s} op {o}"
            text = _text(op.get("instruction", ""))
            found += [f"{where}: says {w!r}" for w in _WRONG if w in text]
            events = sorted(
                [(m.start(), "set", m) for m in _SET.finditer(text)]
                + [(m.start(), "reads", m) for m in _READS.finditer(text)]
                + [(m.start(), "cut", m) for m in _CUT.finditer(text)],
                key=lambda event: event[0],
            )
            cut_at_part_off = False
            for _, kind, match in events:
                if kind == "set":
                    value = match["value"]
                    width = (
                        "blade's width" in value or "<process.blade_width_in>" in value
                    )
                    width_settings += width
                    reading = _OTHER[match[1]] if width else match[1]
                elif kind == "reads":
                    if match[1] != reading:
                        found.append(
                            f"{where}: says the DRO reads the {match[1]}-side face, "
                            f"but its setting reads the {reading}-side face"
                        )
                else:
                    face = match[1] or reading
                    if reading is None:
                        found.append(
                            f"{where}: cuts by the DRO before any blade setting"
                        )
                    elif face != reading:
                        found.append(
                            f"{where}: cuts with the {face}-side face where the DRO "
                            f"reads the {reading}-side face"
                        )
                    if "<cad.part_off" in match["at"]:
                        cut_at_part_off = True
                        if face != "tailstock":
                            found.append(
                                f"{where}: parts from the faced end with the "
                                f"{face}-side face, not the tailstock-side face"
                            )
            if "Z-<cad.part_off" in text and not cut_at_part_off:
                found.append(
                    f"{where}: parts at Z-part_off without naming the face there"
                )
            # A part-off with no DRO setting or cut in it either measures to
            # the blade's near side or repeats an op that does (checked there).
            if (
                op.get("tool") in cutoff
                and re.search(r"\bpart(?:s)? off\b", text, re.IGNORECASE)
                and not events
                and "near side" not in text
                and not re.search(r"\bas (?:in )?op \d+", text, re.IGNORECASE)
            ):
                found.append(
                    f"{where}: part-off placed neither by the DRO nor to the near side"
                )
    parameters = plan.get("parameters", {})
    width = parameters.get("blade_width_in")
    for ref in sorted(set(refs.values())):
        record = tools[ref]
        if record.get("kind") != "cutoff_blade":
            found.append(
                f"{ref} is a {record.get('kind')}, not a blade: no cutting width on record"
            )
        elif width != record["width_in"]:
            found.append(
                f"process.blade_width_in {width!r} is not {ref}'s recorded width "
                f"{record['width_in']}"
            )
    kerf = parameters.get("part_kerf_in")
    if (
        kerf is not None
        and width is not None
        and not width <= kerf <= width + KERF_OVER_MAX_IN
    ):
        found.append(
            f"process.part_kerf_in {kerf} does not follow the blade's {width} "
            f"(+0 to +{KERF_OVER_MAX_IN})"
        )
    if width_settings and not any(
        "<process.blade_width_in>" in _text(op.get("instruction", ""))
        for setup in plan.get("setups", ())
        for op in setup.get("operations", ())
    ):
        found.append("no part-off prints process.blade_width_in")
    return found


def _plans() -> dict[str, dict]:
    plans = {}
    for path in sorted(_process_plans.PROCESS_ROOT.glob("*/plan.toml")):
        plan = tomllib.loads(path.read_text(encoding="utf-8"))
        if any(tool.get("ref") in CUTOFF for tool in plan.get("tools", ())):
            plans[path.parent.name] = plan
    return plans


PLANS = _plans()


def test_the_turned_parts_are_covered() -> None:
    assert set(PLANS) >= {
        "ch_rocker_hub",
        "ch_rocker_strap_tl_hub_plug",
        "dt_cone_gear_tl_arbor_collar",
        "dt_crank_handle_butt_cup",
        "dt_crank_handle_ferrule",
        "dt_pinion_cam",
        "mg_wheel_axle_spacer",
        "sm_gooseneck_end_plug",
    }


@pytest.mark.parametrize("stem", sorted(PLANS))
def test_the_blade_parts_with_the_face_the_dro_reads(stem: str) -> None:
    assert faults(PLANS[stem]) == []


# Synthetic records, so the controls do not move with the inventory.
_SYN_TOOLS = {
    "blade": {"kind": "cutoff_blade", "width_in": 0.0625},
    "holder": {"kind": "cutoff_holder", "width_in": 0.125},
}


def _synthetic(
    *instructions: str, width: float | None = 0.0625, ref: str = "blade"
) -> dict:
    parameters = {"part_kerf_in": 0.075}
    if width is not None:
        parameters["blade_width_in"] = width
    return {
        "parameters": parameters,
        "tools": [{"id": "cutoff", "ref": ref}],
        "setups": [
            {"operations": [{"tool": "cutoff", "instruction": i} for i in instructions]}
        ],
    }


def _faults(plan: dict) -> list[str]:
    return faults(plan, _SYN_TOOLS)


_RIGHT = (
    "Bring the blade's chuck-side face onto the faced end and set DRO Z there to "
    "the blade's width, miked across its cutting edge "
    "({{process.blade_width_in:.4dot}} nominal): the DRO then reads the blade's "
    "tailstock-side face. Part off with that face at Z-{{cad.part_off_in:.3dot}}. "
    "Catch the part."
)


def test_the_check_refuses_the_datum_3312_found() -> None:
    wrong = _synthetic(
        "Touch the blade's Z0-side face on the faced end and zero DRO Z for the "
        "blade there. Part off at Z-{{cad.part_off_in:.3dot}}. Catch the part."
    )
    assert len(_faults(wrong)) >= 2
    # Touched with the chuck-side face and zeroed there: the DRO reads that
    # face, so a part-off at Z-part_off with it leaves the part short.
    zeroed = _synthetic(
        "Bring the blade's chuck-side face onto the faced end and set DRO Z there "
        "to 0. Part off with that face at Z-{{cad.part_off_in:.3dot}}."
    )
    assert any("not the tailstock-side face" in f for f in _faults(zeroed))
    assert _faults(_synthetic(_RIGHT)) == []


def test_the_check_holds_the_width_and_kerf_to_the_blade_record() -> None:
    assert any("recorded width" in f for f in _faults(_synthetic(_RIGHT, width=0.125)))
    assert any("recorded width" in f for f in _faults(_synthetic(_RIGHT, width=None)))
    # #3312's .125 was the holder's body width, not a blade's kerf.
    holder = _synthetic(_RIGHT, width=0.125, ref="holder")
    assert any("not a blade" in f for f in _faults(holder))
    for kerf in (0.05, 0.13):
        plan = _synthetic(_RIGHT)
        plan["parameters"]["part_kerf_in"] = kerf
        assert any("does not follow the blade" in f for f in _faults(plan)), kerf


def test_a_groove_cut_toward_the_chuck_reads_the_touched_face() -> None:
    # The part on the chuck side of the blade: its chuck-side face, touched
    # and set to a position, forms the part's face.
    groove = _synthetic(
        "Touch its chuck-side face on the pilot's shoulder over a paper shim and "
        "set DRO Z+.300. Plunge at DRO Z+.100, then at DRO Z0 (its chuck-side "
        "face on end B's plane) to the neck."
    )
    assert _faults(groove) == []
    swapped = _synthetic(
        "Touch its chuck-side face on the pilot's shoulder and set DRO Z+.300. "
        "Plunge at DRO Z0 (its tailstock-side face on end B's plane)."
    )
    assert _faults(swapped)
