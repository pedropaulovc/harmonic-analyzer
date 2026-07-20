"""cmdhelp v0.1 model and renderers for the project task graph.

This module reads only the side-effect-free graph registries. It never imports
``dodo.py``: loading the doit task generators writes digest sidecars and imports
the telemetry/cache stack, which would violate cmdhelp capability discovery's
side-effect-free contract.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal


BINARY = "harmonic-analyzer"
CMDHELP_VERSION = "0.1"
FORMATS = ("text", "md", "json", "llm")
SUMMARY = "Build, verify, export, and release the SolidWorks Michelson harmonic analyzer."
HOMEPAGE = "https://github.com/pedropaulovc/harmonic-analyzer"

OutputDetail = Literal["summary", "full"]


@dataclass(frozen=True)
class CommandSpec:
    selector: str
    summary: str
    description: str
    args: tuple[dict[str, Any], ...] = ()
    flags: tuple[tuple[str, dict[str, Any]], ...] = ()
    examples: tuple[tuple[str, str], ...] = ()
    see_also: tuple[str, ...] = ()

    @property
    def scope(self) -> tuple[str, ...]:
        return tuple(self.selector.split(":", maxsplit=1))

    def definition(self, detail: OutputDetail) -> dict[str, Any]:
        result: dict[str, Any] = {"summary": self.summary}
        if detail == "summary":
            return result
        if self.description:
            result["description"] = self.description
        if self.args:
            result["args"] = [dict(arg) for arg in self.args]
        if self.flags:
            result["flags"] = {name: dict(spec) for name, spec in self.flags}
        result["stdin"] = {"accepted": False}
        result["exit_codes"] = {
            "0": "ok",
            "1": {"when": "one or more selected tasks failed", "recovery": "Inspect the failed task log and rerun the same selector."},
            "2": {"when": "a task action raised an execution error", "recovery": "Inspect stderr and the task log for the underlying exception."},
            "3": {"when": "the invocation or task graph was invalid", "recovery": f"Run {BINARY} help for valid selectors."},
        }
        if self.examples:
            result["examples"] = [
                {"cmd": command, "note": note} for command, note in self.examples
            ]
        if self.see_also:
            result["see_also"] = list(self.see_also)
        result["stability"] = "stable"
        return result


@dataclass(frozen=True)
class HelpSelection:
    commands: tuple[tuple[CommandSpec, OutputDetail], ...]
    scope: tuple[str, ...]


class UnknownScope(ValueError):
    pass


def _project_version() -> str:
    try:
        return version("harmonic-analyzer")
    except PackageNotFoundError:
        return "0.1.0"


def _repo_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    scripts = root / "cad" / "scripts"
    if scripts.is_dir():
        return root
    raise RuntimeError(
        "harmonic-analyzer cmdhelp requires an editable project checkout; "
        f"cad/scripts was not found under {root}"
    )


def _graph_inventory() -> tuple[list[str], tuple[str, ...], list[str], tuple[str, ...], tuple[str, ...], dict[str, str], dict[str, str]]:
    import sys

    scripts = _repo_root() / "cad" / "scripts"
    scripts_text = str(scripts)
    if scripts_text not in sys.path:
        sys.path.insert(0, scripts_text)

    from _buildgraph import ASSEMBLY_ORDER, part_stems
    from _drawing_registry import DRAWINGS_BY_NAME
    from _task_catalog import (
        CHECK_NAMES,
        CHECK_SUMMARIES,
        OPTIONAL_CHECK_NAMES,
        VERIFY_NAMES,
        VERIFY_SUMMARIES,
    )

    return (
        sorted(part_stems()),
        ASSEMBLY_ORDER,
        sorted(DRAWINGS_BY_NAME),
        VERIFY_NAMES,
        (*CHECK_NAMES, *OPTIONAL_CHECK_NAMES),
        VERIFY_SUMMARIES,
        CHECK_SUMMARIES,
    )


def _humanize(stem: str) -> str:
    return stem.replace("_", "-")


def _root_commands() -> list[CommandSpec]:
    return [
        CommandSpec(
            "build",
            "Build every part and assembly and run every required gate.",
            "The fully safe default entry point. SolidWorks tasks serialize on the COM seat while offline checks may fan out.",
            examples=((f"{BINARY} build", "run the complete pipeline"), (f"{BINARY} -n 4 build", "run offline checks with four workers")),
            see_also=("build_bare", "export", "release"),
        ),
        CommandSpec(
            "build_bare",
            "Build parts and assemblies without verification or export.",
            "A faster development build that preserves the same part-to-assembly dependency graph.",
            examples=((f"{BINARY} build_bare", "perform a quick CAD-only rebuild"),),
            see_also=("build",),
        ),
        CommandSpec(
            "part",
            "Build every generated SolidWorks part.",
            "Group task for all part:<stem> selectors.",
            examples=((f"{BINARY} part", "build all parts"),),
        ),
        CommandSpec(
            "assembly",
            "Build or refresh every SolidWorks assembly.",
            "Group task for all assembly:<stem> selectors.",
            examples=((f"{BINARY} assembly", "build all assemblies and their prerequisites"),),
        ),
        CommandSpec(
            "drawing",
            "Build every registered manufacturing drawing.",
            "Group task for all drawing:<stem> selectors.",
            examples=((f"{BINARY} drawing", "build all curated drawings"),),
        ),
        CommandSpec(
            "verify",
            "Run every SolidWorks-backed verification suite.",
            "Group task for the verification suites that reopen saved assemblies through COM.",
            examples=((f"{BINARY} verify", "run every SolidWorks-backed verification suite"),),
        ),
        CommandSpec(
            "check",
            "Run every SolidWorks-free check, including opt-in checks.",
            "Group task for offline checks. The normal build selects only the required subset; selecting this group also runs opt-in checks.",
            examples=((f"{BINARY} check", "run all offline checks"),),
        ),
        CommandSpec(
            "export",
            "Export release-neutral STEP, STL, glTF, scene, and manifest artifacts.",
            "Runs the export graph after the required CAD and verification prerequisites.",
            examples=((f"{BINARY} export", "regenerate neutral exports"),),
            see_also=("build", "release"),
        ),
        CommandSpec(
            "preflight",
            "Run release-only SolidWorks preflight checks.",
            "Proves expensive release contracts such as the reopened drive-train gear ratios.",
            examples=((f"{BINARY} preflight", "run release preflight without publishing"),),
            see_also=("release",),
        ),
        CommandSpec(
            "release",
            "Cut a versioned GitHub release after every build and release gate passes.",
            "Forwards arguments after -- to the release script. With no version, the next compact vNN tag is selected.",
            args=(
                {"name": "release_args", "type": "string", "required": False, "repeatable": True, "description": "Version and release-script options placed after --."},
            ),
            examples=((f"{BINARY} release", "cut the next release"), (f"{BINARY} release -- v22 --draft", "cut an explicit draft release")),
            see_also=("build", "export", "preflight"),
        ),
        CommandSpec(
            "cache_status",
            "Explain remote-cache hits, misses, keys, and per-input digests.",
            "A SolidWorks-free diagnostic. Arguments after -- filter labels or select miss/all detail modes.",
            args=(
                {"name": "filters", "type": "string", "required": False, "repeatable": True, "description": "Label substrings plus the special miss and all values, placed after --."},
            ),
            examples=((f"{BINARY} cache_status -- cone_gear miss", "show cache misses matching cone_gear"),),
        ),
        CommandSpec(
            "help",
            "Show concise, Markdown, or JSON help for the live task inventory.",
            "Implements cmdhelp v0.1. Scope may be a selector, a task group, or a group and stem supplied as separate words.",
            args=(
                {"name": "scope", "type": "string", "required": False, "repeatable": True, "description": "Optional task selector or group and stem."},
            ),
            flags=(
                ("format", {"type": "enum", "enum": list(FORMATS), "default": "text", "description": "Output format."}),
                ("depth", {"type": "int", "default": 0, "description": "Additional task-tree levels to expand."}),
                ("all", {"type": "bool", "description": "Emit the complete task tree with full detail."}),
                ("capabilities", {"type": "bool", "description": "Print the stable cmdhelp capability bit."}),
            ),
            examples=((f"{BINARY} help --format md --depth 1", "emit full Markdown context"), (f"{BINARY} help --format json --depth 1", "emit the invocation schema")),
        ),
    ]


def command_catalog() -> tuple[CommandSpec, ...]:
    parts, assemblies, drawings, verifies, checks, verify_summaries, check_summaries = _graph_inventory()
    commands = _root_commands()

    for stem in parts:
        selector = f"part:{stem}"
        commands.append(CommandSpec(
            selector,
            f"Build the {_humanize(stem)} SolidWorks part.",
            "Build or restore this part and its render/STL sidecars through the shared cache and COM seat.",
            examples=((f"{BINARY} {selector}", f"build only {_humanize(stem)}"),),
            see_also=("part", "build"),
        ))

    for stem in sorted(assemblies):
        selector = f"assembly:{stem}"
        commands.append(CommandSpec(
            selector,
            f"Build or refresh the {_humanize(stem)} SolidWorks assembly.",
            "Restores from cache, performs a full rebuild when the recipe changed, or incrementally refreshes changed references.",
            examples=((f"{BINARY} {selector}", f"build or refresh {_humanize(stem)}"),),
            see_also=("assembly", "verify:soundness"),
        ))

    for stem in drawings:
        selector = f"drawing:{stem}"
        commands.append(CommandSpec(
            selector,
            f"Build the {_humanize(stem)} manufacturing drawing.",
            "Build or restore the registered SLDDRW, PDF, and PNG artifacts against the exact source-model identity.",
            examples=((f"{BINARY} {selector}", f"build the {_humanize(stem)} drawing"),),
            see_also=("drawing", "release"),
        ))

    for name in verifies:
        selector = f"verify:{name}"
        commands.append(CommandSpec(
            selector,
            verify_summaries[name],
            "A stamped SolidWorks-backed gate that acquires the machine-global COM seat.",
            examples=((f"{BINARY} {selector}", f"run the {name} verification suite"),),
            see_also=("verify", "build"),
        ))

    for name in checks:
        selector = f"check:{name}"
        commands.append(CommandSpec(
            selector,
            check_summaries[name],
            "A stamped offline gate that never acquires the SolidWorks COM seat.",
            examples=((f"{BINARY} {selector}", f"run the {name} check"),),
            see_also=("check", "build"),
        ))

    return tuple(sorted(commands, key=lambda command: command.selector))


def normalize_scope(words: list[str]) -> tuple[str, ...]:
    if not words:
        return ()
    if len(words) == 1 and ":" in words[0]:
        return tuple(words[0].split(":", maxsplit=1))
    if len(words) <= 2:
        return tuple(words)
    raise UnknownScope("scope must be one selector or a group and stem")


def select_commands(scope: tuple[str, ...], depth: int | None, expansion: Literal["bounded", "all"] = "bounded") -> HelpSelection:
    catalog = command_catalog()
    by_scope = {command.scope: command for command in catalog}

    if depth is not None and depth < 0:
        raise ValueError("--depth must be zero or greater")

    if not scope:
        limit = float("inf") if expansion == "all" else 1 + (depth or 0)
        detail: OutputDetail = "full" if expansion == "all" or (depth or 0) > 0 else "summary"
        selected = tuple(
            (command, detail) for command in catalog if len(command.scope) <= limit
        )
        return HelpSelection(selected, scope)

    exact = by_scope.get(scope)
    descendants = [command for command in catalog if command.scope[:len(scope)] == scope and command.scope != scope]

    if exact is not None and not descendants:
        return HelpSelection(((exact, "full"),), scope)

    if exact is None and not descendants:
        requested = ":".join(scope)
        raise UnknownScope(f"unknown help scope: {requested}")

    limit = float("inf") if expansion == "all" else len(scope) + 1 + (depth or 0)
    detail = "full" if expansion == "all" or (depth or 0) > 0 else "summary"
    selected = tuple(
        (command, detail) for command in descendants if len(command.scope) <= limit
    )
    return HelpSelection(selected, scope)


def schema_document(selection: HelpSelection) -> dict[str, Any]:
    return {
        "cmdhelp_version": CMDHELP_VERSION,
        "binary": BINARY,
        "version": _project_version(),
        "summary": SUMMARY,
        "homepage": HOMEPAGE,
        "global_flags": {
            "always-execute": {"type": "bool", "description": "Run selected tasks even when doit considers them up to date. Alias: -a."},
            "continue": {"type": "bool", "negate_flag": "--no-continue", "description": "Continue after a task failure. Alias: -c."},
            "verbosity": {"type": "int", "default": 1, "description": "doit output verbosity from 0 through 2. Alias: -v."},
            "reporter": {"type": "enum", "enum": ["console", "error-only", "executed-only", "json", "zero"], "default": "console", "description": "doit execution reporter. Alias: -r."},
            "process": {"type": "int", "default": 0, "description": "Number of parallel workers. Alias: -n."},
            "parallel-type": {"type": "enum", "enum": ["process", "thread"], "default": "process", "description": "Parallel worker implementation. Alias: -P."},
        },
        "commands": {
            command.selector: command.definition(detail)
            for command, detail in selection.commands
        },
    }


def render_json(selection: HelpSelection) -> str:
    return json.dumps(schema_document(selection), indent=2, ensure_ascii=False) + "\n"


def _table(rows: list[tuple[str, ...]]) -> list[str]:
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    header = "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(rows[0])) + " |"
    rule = "| " + " | ".join("-" * widths[index] for index in range(len(widths))) + " |"
    body = [
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in rows[1:]
    ]
    return [header, rule, *body]


def render_markdown(selection: HelpSelection) -> str:
    lines = [
        "---",
        f'cmdhelp_version: "{CMDHELP_VERSION}"',
        f"binary: {BINARY}",
        f"version: {_project_version()}",
        "---",
        "",
        f"# {BINARY}",
        "",
        SUMMARY,
        "",
    ]

    for command, detail in selection.commands:
        definition = command.definition(detail)
        lines.extend([f"## `{BINARY} {command.selector}`", "", definition["summary"], ""])
        if detail == "summary":
            continue
        lines.extend(["### Synopsis", "", f"`{BINARY} [RUN OPTIONS] {command.selector}`", ""])
        if definition.get("description"):
            lines.extend([definition["description"], ""])
        if definition.get("args"):
            rows = [("name", "type", "required", "description")]
            rows.extend((arg["name"], arg["type"], str(arg.get("required", False)).lower(), arg.get("description", "")) for arg in definition["args"])
            lines.extend(["### Arguments", "", *_table(rows), ""])
        if definition.get("flags"):
            rows = [("flag", "type", "default", "description")]
            rows.extend((f"--{name}", spec["type"], str(spec.get("default", "")), spec.get("description", "")) for name, spec in definition["flags"].items())
            lines.extend(["### Flags", "", *_table(rows), ""])
        if definition.get("examples"):
            lines.extend(["### Examples", ""])
            for example in definition["examples"]:
                lines.extend([f"{example.get('note', '')}:", "", "```bash", example["cmd"], "```", ""])
        lines.extend(["### Output", "", "Human-readable task output is written to stdout; diagnostics and telemetry narration use stderr.", ""])
        if definition.get("see_also"):
            lines.extend(["### See also", "", *(f"- `{name}`" for name in definition["see_also"]), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_text(selection: HelpSelection) -> str:
    if not selection.commands:
        return f"{BINARY}: no commands in this scope\n"

    lines = [f"{BINARY} — {SUMMARY}", ""]
    if any(detail == "summary" for _, detail in selection.commands):
        lines.extend(["COMMANDS", ""])
        width = max(len(command.selector) for command, _ in selection.commands)
        lines.extend(f"  {command.selector.ljust(width)}  {command.summary}" for command, _ in selection.commands)
        lines.extend(["", f"For complete agent-readable context: {BINARY} help --format md --depth 1", f"For the invocation schema: {BINARY} help --format json --depth 1"])
        return "\n".join(lines) + "\n"

    for command, _ in selection.commands:
        lines.extend([command.selector, f"  {command.summary}", "", "USAGE", f"  {BINARY} [RUN OPTIONS] {command.selector}", ""])
        if command.description:
            lines.extend([command.description, ""])
        if command.examples:
            lines.append("EXAMPLES")
            lines.extend(f"  {example}" for example, _ in command.examples)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def selector_from_example(command: str) -> str | None:
    """Extract the selected project task from a canonical example for tests."""
    tokens = command.split()
    if not tokens or tokens[0] != BINARY:
        return None
    selectors = {spec.selector for spec in command_catalog()}
    return next((token for token in tokens[1:] if token in selectors), None)


def is_valid_capability_line(value: str) -> bool:
    return re.fullmatch(r"cmdhelp/0\.1: text, md, json, llm\n?", value) is not None
