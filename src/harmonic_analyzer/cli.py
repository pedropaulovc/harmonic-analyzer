"""Console entry point: cmdhelp discovery plus exact delegation to doit."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence


_CAPABILITY_LINE = "cmdhelp/0.1: text, md, json, llm"


def _print_capabilities() -> int:
    print(_CAPABILITY_LINE)
    return 0


def _repo_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    if (root / "dodo.py").is_file():
        return root
    raise RuntimeError(f"dodo.py not found under editable checkout {root}")


def _load_dodo():
    path = _repo_root() / "dodo.py"
    spec = importlib.util.spec_from_file_location("harmonic_analyzer_dodo", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load task graph from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_doit(args: list[str]) -> int:
    from doit.cmd_base import ModuleTaskLoader
    from doit.doit_cmd import DoitMain

    app = DoitMain(ModuleTaskLoader(_load_dodo()), config_filenames=())
    app.BIN_NAME = "harmonic-analyzer"
    return app.run(args)


def _help_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harmonic-analyzer help", add_help=False)
    parser.add_argument("scope", nargs="*")
    parser.add_argument("--format", choices=("text", "md", "json", "llm"), default="text")
    parser.add_argument("--depth", type=int)
    parser.add_argument("--all", action="store_true", dest="expand_all")
    parser.add_argument("--capabilities", action="store_true")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    return parser


def _render_help(args: list[str]) -> int:
    parser = _help_parser()
    try:
        request = parser.parse_args(args)
    except SystemExit:
        return 3

    if request.capabilities:
        return _print_capabilities()
    if request.show_help:
        parser.print_help()
        return 0

    from .cmdhelp import (
        UnknownScope,
        normalize_scope,
        render_json,
        render_markdown,
        render_text,
        select_commands,
    )

    try:
        scope = normalize_scope(request.scope)
        expansion = "all" if request.expand_all else "bounded"
        selection = select_commands(scope, request.depth, expansion)
    except (UnknownScope, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    if request.format == "json":
        sys.stdout.write(render_json(selection))
        return 0
    if request.format in ("md", "llm"):
        sys.stdout.write(render_markdown(selection))
        return 0
    sys.stdout.write(render_text(selection))
    return 0


def _print_version() -> int:
    try:
        project_version = version("harmonic-analyzer")
    except PackageNotFoundError:
        project_version = "0.1.0"
    print(f"harmonic-analyzer {project_version}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--cmdhelp-capabilities"]:
        return _print_capabilities()
    if args == ["--version"]:
        return _print_version()
    if not args:
        return _run_doit(args)
    if args[0] in ("-h", "--help"):
        return _render_help(args[1:])
    if args[0] == "help":
        return _render_help(args[1:])
    return _run_doit(args)
