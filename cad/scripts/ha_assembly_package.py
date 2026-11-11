"""The release's ASSEMBLY.md: the master build sequence and the one assembly
tool and gauge list, reconciled with the shop files (#2391, #2392).

Nothing here is copied from a sheet. The sequence table is ha_build_sequence's
runs, printed with the numbers the sub-assembly sheets print. The tool list is
read from the text the machine's assembly packages print, in each package's
draw script and in the step and sheet-text modules it imports
(``*_assembly_sheet``, ``*_steps``, ``*_fitup``; another package's modules are
that package's): every module-level string as evaluated (whole printed blocks,
sizes filled in) and every string literal in the source (the pieces of text a
function assembles at draw time), never a comment or docstring. Each row of
``TOOLS`` names a tool by the words the sheets use for it and points at its
record in cad/process/shop.toml or cad/config/shop-equipment.toml, so the
list carries only tools some sheet still names, says where, and marks each
OWNED, TO BUY or TO MAKE from the record. test_ha_assembly_package fails when
a sheet names an instrument, gauge or consumable no row covers.

cut_release stages the document beside READOUT.md; run this module to print
it. Reads source and TOML only: no SolidWorks.
"""

from __future__ import annotations

import ast
import importlib
import re
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import ha_build_sequence as build
from _assembly_contract import assembly_contract
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from ha_harmonic_analyzer_assembly_spec import ASM_NAME, BOM_ORDER

SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_ROOT = SCRIPTS_DIR.parent
SHOP_FILES = {
    "shop.toml": CAD_ROOT / "process" / "shop.toml",
    "shop-equipment.toml": CAD_ROOT / "config" / "shop-equipment.toml",
}
DOCUMENT_NAME = "ASSEMBLY.md"

# The machine's assembly packages: every row of the complete machine's BOM,
# then the complete machine itself.
PACKAGES: tuple[str, ...] = (*BOM_ORDER, ASM_NAME)
_TEXT_MODULE_SUFFIXES = ("_assembly_sheet", "_steps", "_fitup")
_PACKAGE_PREFIXES = tuple(sorted({f"{stem.split('-')[0]}_" for stem in PACKAGES}))


def drawing_number(stem: str) -> str:
    return str(assembly_contract(stem).number)


def text_modules(stem: str) -> tuple[Path, ...]:
    """The draw script of package ``stem`` and the text modules it imports:
    its own (same subsystem prefix) and unprefixed fit-up modules, never
    another package's step registry it imports only for a pointer."""
    script = Path(
        DRAWINGS_BY_NAME[f"{stem.replace('-', '_')}_assembly"].script
    ).resolve()
    prefix = f"{stem.split('-')[0]}_"
    imported = sorted(
        path
        for path in map(Path, module_deps_of(script))
        if path.parent == SCRIPTS_DIR
        and path.stem.endswith(_TEXT_MODULE_SUFFIXES)
        and (
            path.stem.startswith(prefix) or not path.stem.startswith(_PACKAGE_PREFIXES)
        )
    )
    return (script, *imported)


def _literals(path: Path) -> tuple[tuple[str, bool], ...]:
    """Every string literal in ``path`` but its docstrings, each with whether
    it is a piece of an f-string (the rest of its text filled in at run time)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    pieces = {
        id(value)
        for node in ast.walk(tree)
        if isinstance(node, ast.JoinedStr)
        for value in node.values
    }
    return tuple(
        (node.value, id(node) in pieces)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    )


def _module_strings(path: Path) -> tuple[str, ...]:
    """Every string the module ``path`` holds at module level once imported,
    through nested containers (dunders such as the docstring excepted)."""
    found: list[str] = []
    pending = [
        value
        for name, value in vars(importlib.import_module(path.stem)).items()
        if not name.startswith("__")
    ]
    seen: set[int] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            found.append(item)
        elif (
            isinstance(item, (tuple, list, set, frozenset, dict))
            and id(item) not in seen
        ):
            seen.add(id(item))
            pending.extend(
                (*item.keys(), *item.values()) if isinstance(item, dict) else item
            )
    return tuple(found)


@dataclass(frozen=True)
class Text:
    """One printable string of a package; ``piece`` when it is only part of
    an f-string, the words around it filled in at run time."""

    text: str
    piece: bool


@cache
def package_texts() -> dict[str, tuple[Text, ...]]:
    """Each package's printable strings, whitespace collapsed, by stem."""
    texts: dict[str, tuple[Text, ...]] = {}
    for stem in PACKAGES:
        found: dict[str, bool] = {}
        for path in text_modules(stem):
            for text, piece in (
                *((text, False) for text in _module_strings(path)),
                *_literals(path),
            ):
                flat = " ".join(text.split())
                if flat:
                    found[flat] = found.get(flat, True) and piece
        texts[stem] = tuple(Text(text, piece) for text, piece in found.items())
    return texts


@dataclass(frozen=True)
class Tool:
    """One line of the tool list.

    ``pattern`` matches the words the sheets use for the tool (upper case, as
    printed); rows match in order and each span of text counts for the first
    row that matches it. ``records`` are ``"<file>:<table.key>"`` shop
    records; a tool with none is made in the step that names it, or is a
    drawn shop tool with its own sheet. ``packages`` limits a row to the
    packages where its words mean that tool (empty: every package).
    """

    name: str
    pattern: str
    records: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()


TOOLS: tuple[Tool, ...] = (
    # --- shop-made: drawn, or made in the step that names it ---------------
    Tool(
        "Drawn shop tools (each made to its own -TL- sheet)",
        r"MHA-[A-Z]{2}-\d{2}-TL-\d{2}",
    ),
    Tool("Steel press sleeve, made in the step", r"STEEL SLEEVE"),
    # MHA-PD-00's only mandrel is the stub it turns in place.
    Tool(
        "Stub mandrel, turned in place in the lathe chuck",
        r"(?:STUB )?MANDREL(?:'S)?\b",
        packages=("pd-paper-drive",),
    ),
    # --- machines and setting ---------------------------------------------
    Tool(
        "Mill with DRO (PM-30MV)",
        r"\bMILL\b|\bDRO(?:'S)?\b",
        ("shop.toml:machines.pm-30mv",),
    ),
    Tool(
        "Lathe (PM-1127VF-LB)",
        r"\bLATHE\b|\bTAILSTOCK\b",
        ("shop.toml:machines.pm-1127vf-lb",),
    ),
    Tool(
        "Edge finder", r"\bEDGE[- ]FIND\w*", ("shop-equipment.toml:tools.edge-finder",)
    ),
    Tool(
        "Surface plate", r"SURFACE PLATE", ("shop-equipment.toml:gauges.surface-plate",)
    ),
    Tool(
        "Parallels",
        r"\bPARALLELS\b",
        ("shop-equipment.toml:fixtures.parallels-lms-6745",),
    ),
    Tool(
        "V-blocks",
        r"\b(?:ON A|ONTO) V-BLOCKS?\b",
        ("shop-equipment.toml:fixtures.v-blocks",),
    ),
    Tool(
        "3/8 ground setting mandrel",
        r"\d+/\d+ GROUND SETTING MANDREL|\bMANDREL(?:'S)?\b",
        ("shop-equipment.toml:tools.setting-mandrel-375",),
        packages=("dt-drive-train",),
    ),
    # The verb, wherever it stands; not a fit class ("PRESS FIT", "(PRESS)"),
    # a part's press size, or a hand pressed lightly.
    Tool(
        "Arbor press",
        r"(?<!\()\bPRESS(?:ED)?\b(?![- ]FIT|\)| SIZE| LIGHTLY)",
        ("shop-equipment.toml:tools.arbor-press",),
    ),
    # --- measuring --------------------------------------------------------
    Tool(
        "Gauge bar (MHA-SM-00)",
        r"GAUGE BAR",
        ("shop-equipment.toml:gauges.gauge-bar-0472x8",),
    ),
    Tool(
        "Gauge blocks",
        r"GAUGE BLOCKS?|\bBLOCKS ON THAT STOP",
        ("shop-equipment.toml:gauges.gauge-blocks-mitutoyo",),
    ),
    Tool("Pin gauges", r"GAUGE PINS?|PIN GAUGES?", ("shop.toml:gauges.pin-gauges",)),
    Tool("Height gauge", r"HEIGHT GAUGE", ("shop.toml:gauges.height-gauge",)),
    Tool(
        "Depth micrometer or depth gauge",
        r"DEPTH (?:MICROMETER|GAUGE)",
        ("shop-equipment.toml:gauges.depth-micrometer",),
    ),
    Tool(
        "Calipers, 6 in, with depth rod",
        r"\bCALIPERS?(?: DEPTH ROD)?\b",
        ("shop.toml:gauges.calipers",),
    ),
    Tool(
        "Outside micrometers, 0-3 in",
        r"\bMIC(?:ED)?\b|\bMICROMETERS?\b",
        ("shop-equipment.toml:gauges.micrometers",),
    ),
    Tool(
        "Dial test indicator on a magnetic base",
        r"TEST INDICATOR(?: ON A MAGNETIC BASE)?|MAGNETIC BASE",
        ("shop.toml:gauges.dti", "shop-equipment.toml:gauges.mag-base"),
    ),
    Tool(
        "Dial indicators, three at once",
        r"(?:DIAL )?\bINDICATORS?\b",
        (
            "shop-equipment.toml:gauges.dial-indicator",
            "shop-equipment.toml:gauges.dial-indicators-extra",
        ),
    ),
    Tool(
        "Feeler gauge leaves",
        r"(?:\.\d+ )?FEELERS?(?: GAUGES?| GAUGE LEAF| LEAVES| STACKS?)?\b|THICKNESS GAGE",
        ("shop-equipment.toml:gauges.feeler-gauges",),
    ),
    Tool(
        "Digital angle gauge",
        r"DIGITAL ANGLE GAUGE",
        ("shop-equipment.toml:gauges.digital-angle-gauge",),
    ),
    Tool("Protractor", r"\bPROTRACTOR\b", ("shop-equipment.toml:gauges.protractor",)),
    Tool(
        "Steel rule, 48 in",
        r"\bRULE\b",
        ("shop-equipment.toml:tools.steel-rule-48",),
    ),
    Tool("Tape measure", r"TAPE MEASURE", ("shop-equipment.toml:tools.tape-measure",)),
    Tool(
        "Combination square",
        r"\b(?:A|THE) SQUARE (?:STANDING |ON )",
        ("shop-equipment.toml:tools.combination-square-starrett-c11h-12",),
    ),
    Tool(
        "Straightedge", r"\bSTRAIGHTEDGE\b", ("shop-equipment.toml:tools.straightedge",)
    ),
    # --- hand tools -------------------------------------------------------
    Tool(
        "Transfer punches",
        r"(?:\d+/\d+ )?TRANSFER[- ]PUNCH(?:ES)?",
        ("shop-equipment.toml:tools.transfer-punches",),
    ),
    Tool(
        "Taper-pin reamer, 1:48",
        r"TAPER-REAM(?: 1:48)?",
        ("shop-equipment.toml:tools.taper-pin-reamer",),
    ),
    Tool(
        "Bottoming taps",
        r"(?:#?\d+-\d+ )?BOTTOMING TAPS?",
        ("shop-equipment.toml:tools.bottoming-taps",),
    ),
    Tool(
        "Combination wrenches, 1/4-1 in",
        r"\b(?:1/4|5/16|11/32|3/8|7/16|1/2|9/16|5/8|11/16|3/4|13/16|7/8|15/16) WRENCH\b",
        ("shop-equipment.toml:tools.combination-wrenches-tekton-wcb90302",),
    ),
    Tool(
        "Small open-end wrench under 1/4 in",
        r"\b\d+/\d+ WRENCH\b",
        ("shop-equipment.toml:tools.ignition-wrenches",),
    ),
    Tool("Hex keys", r"HEX KEY", ("shop-equipment.toml:tools.hex-keys-bondhus-10937",)),
    Tool(
        "Torque screwdriver, in-lb",
        r"\d+(?:\.\d+)? IN-LB",
        ("shop-equipment.toml:tools.torque-screwdriver",),
    ),
    Tool("Pliers", r"\bPLIERS\b", ("shop-equipment.toml:tools.pliers",)),
    Tool(
        "Hammer and centre punch (staking, peening)",
        r"\bSTAKE\b|\bPEEN\b",
        (
            "shop-equipment.toml:tools.ball-peen-hammer-16oz",
            "shop-equipment.toml:tools.centre-punch-starrett-18a",
        ),
    ),
    Tool(
        "File",
        r"\b(?:ROUND )?FILE\b",
        ("shop-equipment.toml:tools.file-nicholson-10-second-cut",),
    ),
    Tool(
        "Sharpening stone", r"\bSTONE\b", ("shop-equipment.toml:tools.india-stone-ib8",)
    ),
    # --- consumables ------------------------------------------------------
    Tool(
        "Loctite 638 retaining compound",
        r"LOCTITE 638",
        ("shop-equipment.toml:consumables.loctite-638",),
    ),
    Tool(
        "30-minute epoxy",
        r"(?:30-MINUTE )?EPOXY",
        ("shop-equipment.toml:consumables.epoxy-30-minute",),
    ),
    Tool(
        "Soft solder, 60/40 tin-lead, and rosin flux",
        r"SOFT-SOLDER|60/40 TIN-LEAD|ROSIN FLUX|\bSOLDER\b",
        ("shop-equipment.toml:consumables.solder-60-40",),
    ),
    Tool(
        "Paste wax", r"(?:PASTE )?WAX\b", ("shop-equipment.toml:consumables.paste-wax",)
    ),
    Tool("Degreaser", r"DEGREASE", ("shop-equipment.toml:consumables.degreaser",)),
    Tool(
        "Machine oil (ISO VG 32 and light)",
        r"(?:ISO VG 32 |LIGHT )?MACHINE OIL|\bOIL(?:ED)?\b(?! HOLE)",
        ("shop-equipment.toml:consumables.oil-iso-vg32",),
    ),
)
if len({tool.name for tool in TOOLS}) != len(TOOLS):
    raise AssertionError("two tool rows share a name")


@cache
def shop_records() -> dict[str, dict[str, Any]]:
    return {
        name: tomllib.loads(path.read_text(encoding="utf-8"))
        for name, path in SHOP_FILES.items()
    }


def shop_record(ref: str) -> dict[str, Any]:
    """The shop record ``"<file>:<table.key>"``; a KeyError names a missing one."""
    file, _, dotted = ref.partition(":")
    record: Any = shop_records()[file]
    for part in dotted.split("."):
        record = record[part]
    return record


def status(tool: Tool) -> str:
    """OWNED, TO BUY or TO MAKE, from the tool's shop records."""
    if not tool.records:
        return "TO MAKE"
    records = [shop_record(ref) for ref in tool.records]
    if any(record.get("shop_made") for record in records):
        return "TO MAKE"
    if all(record.get("present", True) is not False for record in records):
        return "OWNED"
    return "TO BUY"


@dataclass(frozen=True)
class Use:
    tool: Tool
    drawings: tuple[str, ...]
    named_as: tuple[str, ...]


def _spans(pattern: str, text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(pattern, text)]


def claimed(text: str, stem: str) -> list[tuple[Tool, int, int, str]]:
    """Each match in package ``stem``'s ``text`` claimed by the first row
    whose pattern covers it."""
    taken: list[tuple[int, int]] = []
    found: list[tuple[Tool, int, int, str]] = []
    for tool in TOOLS:
        if tool.packages and stem not in tool.packages:
            continue
        for start, end, word in _spans(tool.pattern, text):
            if any(start < b and a < end for a, b in taken):
                continue
            taken.append((start, end))
            found.append((tool, start, end, word.strip()))
    return found


def tool_uses() -> tuple[Use, ...]:
    """Every row some package's text names, in ``TOOLS`` order."""
    drawings: dict[str, set[str]] = {}
    named: dict[str, set[str]] = {}
    for stem, texts in package_texts().items():
        for text in texts:
            for tool, _start, _end, word in claimed(text.text, stem):
                drawings.setdefault(tool.name, set()).add(drawing_number(stem))
                named.setdefault(tool.name, set()).add(word)
    return tuple(
        Use(tool, tuple(sorted(drawings[tool.name])), tuple(sorted(named[tool.name])))
        for tool in TOOLS
        if tool.name in drawings
    )


# The words that name an instrument, gauge, machine, hand tool or consumable
# on an assembly sheet. Each must lie inside a TOOLS match, so a sheet that
# starts naming a new tool fails test_ha_assembly_package until a row (and its
# shop record) lists it. Verbs that are also tools (PRESS, STAKE, FILE) and
# plain shapes (SQUARE, BLOCK) are left to their rows.
TOOL_WORDS = re.compile(
    r"\b(?:FEELERS?|GAUGES?|GAGES?|INDICATORS?|MICROMETERS?|MIC|MICED|RULE|"
    r"CALIPERS?|PROTRACTOR|TRANSFER[- ]PUNCH(?:ES)?|REAMERS?|TAPER-REAM|"
    r"WRENCH(?:ES)?|HEX KEYS?|PLIERS|MANDREL|V-BLOCKS?|SURFACE PLATE|PARALLELS|"
    r"STRAIGHTEDGE|EPOXY|LOCTITE|SOLDER|FLUX|WAX|DEGREASE|DEGREASER|SCREWDRIVER|"
    r"DRO|MILL|LATHE|TAILSTOCK|EDGE[- ]FIND\w*|IN-LB|TAPE MEASURE|HAMMER|MALLET|"
    r"OIL(?! HOLE))\b"
)
# Tool words that name a part, not a tool, with why.
NOT_TOOLS: tuple[tuple[str, str], ...] = (
    (r"\b(?:THE|PEN) V-BLOCK\b|\bV-BLOCK,", "MHA-PN-00's V-block is a part of the pen"),
)


def unlisted() -> tuple[tuple[str, str, str], ...]:
    """``(drawing, word, context)`` for every tool word no row covers.

    A word in an f-string piece passes when the same word is covered
    elsewhere in its package: the piece lacks the size or count the run-time
    text fills in beside it."""
    found: list[tuple[str, str, str]] = []
    for stem, texts in package_texts().items():
        covered: set[str] = set()
        loose: list[tuple[Text, re.Match[str]]] = []
        for text in texts:
            spans = [
                (start, end) for _tool, start, end, _word in claimed(text.text, stem)
            ]
            spans += [
                (m.start(), m.end())
                for pattern, _why in NOT_TOOLS
                for m in re.finditer(pattern, text.text)
            ]
            for match in TOOL_WORDS.finditer(text.text):
                if any(a <= match.start() and match.end() <= b for a, b in spans):
                    covered.add(match.group(0))
                else:
                    loose.append((text, match))
        for text, match in loose:
            if text.piece and match.group(0) in covered:
                continue
            context = text.text[max(0, match.start() - 40) : match.end() + 30]
            found.append((drawing_number(stem), match.group(0), context))
    return tuple(found)


def _cell(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "-"


def markdown() -> str:
    ha_steps = build.ha_steps
    printed_at = sorted(
        ha_steps.step_number(key)
        for key in ("frame-built", "drive-train-built", "channel-built")
    )
    erected = 1 + next(
        i for i, phase in enumerate(build.PHASES) if build.FRAME_ERECTED in phase.runs
    )
    apart = [
        i for i, phase in enumerate(build.PHASES, start=1) if phase.frame == "APART"
    ]
    lines = [
        "# MHA-HA-00 build sequence and assembly tools",
        "",
        "Generated from the assembly packages' own steps and the shop files at "
        "this release (cad/scripts/ha_assembly_package.py); a change to a sheet "
        "or a shop record changes this page.",
        "",
        "## Build sequence",
        "",
        "Step numbers are the sub-assembly sheets' own. MHA-HA-00 integration "
        f"steps {', '.join(map(str, printed_at[:-1]))} and {printed_at[-1]} print "
        "the same order. The frame comes apart at "
        f"{build.fr_steps.step_ref(build.FRAME_LIFTED_KEY)} and goes back up on its "
        f"match marks in phase {erected}.",
        "",
        "| # | Phase | Where | Frame | Steps | Match-located steps |",
        "|---|---|---|---|---|---|",
    ]
    for index, phase in enumerate(build.PHASES, start=1):
        lines.append(
            f"| {index} | {phase.title} | {phase.where} | {phase.frame} | "
            f"{'; '.join(run.text for run in phase.runs)} | "
            f"{_cell(build.match_located(phase))} |"
        )
    lines += [
        "",
        "Match-located steps drill, ream, tap or spot a hole through or from a "
        "part already located on another; those on MHA-FR-01 and MHA-FR-02 are "
        f"why the frame is apart for phases {apart[0]}-{apart[-1]}.",
        "",
        "## Assembly tools, gauges and consumables",
        "",
        "Every tool the assembly sheets name, reconciled with cad/process/shop.toml "
        "and cad/config/shop-equipment.toml. OWNED: its shop record says so. "
        "TO BUY: its record has `present = false`. TO MAKE: a drawn shop tool, "
        "made in the step that names it, or its record says `shop_made`. Drills, "
        "taps and reamers a step names only by a part's callout are that part's, "
        "not listed here.",
        "",
        "| Tool | Status | Shop record | Named on | As named |",
        "|---|---|---|---|---|",
    ]
    for use in tool_uses():
        lines.append(
            f"| {use.tool.name} | {status(use.tool)} | "
            f"{_cell(tuple(f'`{ref}`' for ref in use.tool.records))} | "
            f"{_cell(use.drawings)} | {_cell(use.named_as)} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
