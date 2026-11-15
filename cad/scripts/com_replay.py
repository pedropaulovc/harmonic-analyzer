"""Record or replay one build's COM conversation.

``record <script> --log P [--summary P] [--kind K] [--out-root DIR] [--callers MODE] [-- ARG...]``
    Run a build script against the live seat exactly as ``python <script>
    ARG...`` would (``run_build``: connect, discard, template pin, teardown),
    recording its build window into ``P``. ``ARG...``, everything after the
    first ``--``, are the script's own arguments (a drawing's artifact stem),
    kept in ``sys.argv`` around the engine, whose ``run_script`` passes none.
    ``--summary`` writes the recording's facts as JSON for dodo, with
    ``replay_gaps`` (what a replay of this recording would need that the
    engine's replay lacks) and, for ``--kind drawing``, ``display`` (the
    window the build's sheet picks hit-tested in). ``--out-root``
    redirects the outputs (side-by-side diagnostic runs only; dodo's builds
    never pass it). ``--callers`` keeps the Python caller of every call
    (``full``), none (``divergence``: a replay names its own at a divergence)
    or none at all (``off``). Exits with the build's own exit code, or 92 when
    the recorder failed where the build's results cannot be trusted
    (``Recovery.RERUN``): dodo re-runs the build once unrecorded, with its
    arguments. A recorder failure after a call's result was in hand
    (``Recovery.DEGRADED``) stops recording and lets the build finish: the exit
    code is the build's, and the summary's ``faults`` mark the recording
    unusable.

``replay <script> --log P --seat-log P --scratch DIR --result P [--kind K] [--base-outputs DIR] [--capture-dir DIR] [-- ARG...]``
    Run the script with SolidWorks absent, serving the log: no live COM, no
    write outside DIR (bar the temporary and telemetry directories), no
    connection beyond loopback, no OTLP export. ``--seat-log`` is a recording
    made on the seat the replay stands for (the shadow passes the build's own;
    a reuse attempt, which stands for the base's seat, the base's): a
    SolidWorks revision other than the log's refuses the replay
    (``input_mismatch``). ``--kind assembly`` or ``drawing`` first stages
    into DIR the output-root files the recording read that it did not write:
    a copy of each the script's Python read, an empty stub of each model only
    SolidWorks opened (``staged``, each output-root file's SHA-256; a Python
    read of a stub: ``stub_reads``), none of them a ``py_outputs`` entry
    unless the script changed it. ``--kind drawing``
    also moves the paths ``_drawing_types`` names under the output root (the
    model, the sheet, PDF, PNG and layout report) into DIR. ``ARG...`` are
    the script's own arguments, as for ``record``. ``--base-outputs``
    compares the Python-written outputs with that output root, file by file.
    The result also names the repository files the build script's own
    execution imported or opened for reading, never the engine's
    (``python_files``); those the log's COM arguments name, which SolidWorks
    opens itself (``solidworks_inputs``; output-root paths that are not the
    log's captured outputs: ``solidworks_out_inputs``); and the log's recipe
    requests that carry a document title counter (``title_echoes``). Exits 0
    for a no-op verdict, 91 for any other verdict, 1 for an infrastructure
    failure.

``diff <a> <b> [--result P] [--kind K] [--base-sidecars DIR] [--new-sidecars DIR]``
    Request divergence and per-member response differences between two logs
    (JSON on stdout), plus what caused the divergence and whether the two
    builds made the same part, assembly or drawing (``_com_outcome``, on
    ``--kind``'s signals: ``truth_cause``, ``outcome``, ``title_echo``,
    ``pdf_cause``; an assembly's sidecar files are compared from the two
    directories) and each log's ``display``; exit 0 when the recipe requests
    are identical. An assembly's or drawing's requests are compared with the
    component arrays SolidWorks enumerated in another order bound to the
    base's by name (``_com_outcome.name_bound``; ``name_bound``: how many,
    and the positional divergence it replaced; a binding that raised is the
    ``judge_faults`` step ``name_bound``, the comparison kept positional).

dodo records every part, FULL assembly and drawing build through ``record``;
before a part build tries to reuse a base's part, or after it evaluates the
shadow replay, it runs ``replay`` and ``diff``, and after an assembly or a
drawing it runs ``diff`` against the nearest base (``_replay_shadow``).
Nothing here is imported by a recipe; ``--help`` imports neither pywin32 nor
the build modules.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import math
import os
import shutil
import sys
import types
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Any

SUMMARY_SCHEMA = 1
REPO_ROOT = Path(__file__).resolve().parents[2]
# Repository files that are never a build's input: the environment and the
# outputs (the replay's own scratch included).
_NOT_INPUTS = (".venv", "cad/out")
# Bound on the requests a ``title_echoes`` result lists (all are counted).
_ECHOES_LISTED = 10
# The output-root subdirectories the engine's replay redirects into its
# scratch root (_com_conversation.redirect_outputs; pinned by test). A
# drawing names others (slddrw/, pdf/, reports/layout-audit/) through
# ``_drawing_types``, which ``replay --kind drawing`` redirects itself
# (:func:`_drawing_outputs`).
_REDIRECTED = ("sldprt", "sldasm", "png", "stl")
# Bound on the paths each ``replay_gaps`` list names (all are counted).
_GAPS_LISTED = 10
# The inert reads _seat_forensics.display_geometry makes (a drawing's
# record_drawing_display): the document window a sheet-coordinate pick
# hit-tests in, four screen pixels (IModelView.GetVisibleBox), and the pixels
# one model millimetre spans, from the projections of the origin and of 1 mm
# along each axis (IModelView.ProjectModelPoint). Their answers are in the log,
# so ``display`` costs no COM call of its own.
_VISIBLE_BOX = "IModelView.GetVisibleBox"
_PROJECT = "IModelView.ProjectModelPoint"
_AXIS_MM = 1e-3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="com_replay.py",
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser(
        "record",
        help="run a build on the live seat, recorded",
        epilog="ARG... after the first -- are the script's own arguments.",
    )
    record.add_argument("script", type=Path)
    record.add_argument("--log", type=Path, required=True)
    record.add_argument("--summary", type=Path, help="write the recording's facts")
    record.add_argument(
        "--kind",
        choices=("part", "assembly", "drawing"),
        default="part",
        help="what the build makes (a drawing's summary reads its display)",
    )
    record.add_argument("--out-root", type=Path, help="redirect the build's outputs")
    record.add_argument(
        "--callers",
        choices=("off", "divergence", "full"),
        help="Python caller capture per recorded call (default: the engine's)",
    )

    replay = sub.add_parser(
        "replay",
        help="replay a log with SolidWorks absent",
        epilog="ARG... after the first -- are the script's own arguments.",
    )
    replay.add_argument("script", type=Path)
    replay.add_argument("--log", type=Path, required=True)
    replay.add_argument(
        "--seat-log",
        type=Path,
        required=True,
        help="a recording made on the seat the replay stands for (its revision)",
    )
    replay.add_argument("--scratch", type=Path, required=True)
    replay.add_argument(
        "--kind",
        choices=("part", "assembly", "drawing"),
        default="part",
        help="what the build makes (an assembly's or drawing's inputs are "
        "staged, a drawing's own output paths redirected)",
    )
    replay.add_argument("--result", type=Path, required=True)
    replay.add_argument(
        "--base-outputs",
        type=Path,
        help="output root the Python-written outputs are compared with",
    )
    replay.add_argument(
        "--capture-dir",
        type=Path,
        help="SolidWorks-written files of the log (default: beside the log)",
    )

    diff = sub.add_parser("diff", help="request/response comparison of two logs")
    diff.add_argument("base", type=Path)
    diff.add_argument("new", type=Path)
    diff.add_argument("--result", type=Path)
    diff.add_argument(
        "--kind",
        choices=("part", "assembly", "drawing"),
        default="part",
        help="what the two builds made: the outcome's signals",
    )
    diff.add_argument("--base-sidecars", type=Path, help="the base's sidecar files")
    diff.add_argument("--new-sidecars", type=Path, help="the new build's sidecars")
    return parser


def _arguments(argv: list[str]) -> argparse.Namespace:
    """``argv`` parsed: this driver's own arguments before the first ``--``,
    the recorded or replayed script's after it (``argv``). They are split
    here rather than by argparse, whose handling of a ``*`` positional after
    another one depends on the Python patch release: before 3.12.7 (CPython
    gh-59317) it binds the positional to ``[]`` with the script's path and
    then rejects ``-- ARG...`` as unrecognized arguments."""
    own, scripts = argv, []
    if "--" in argv:
        at = argv.index("--")
        own, scripts = argv[:at], argv[at + 1 :]
    parser = _parser()
    args = parser.parse_args(own)
    if args.command not in ("record", "replay") and scripts:
        parser.error(f"only record and replay pass arguments to a script: {scripts}")
    args.argv = scripts
    return args


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _offline_telemetry() -> None:
    """A replay exports no OTLP: the sandbox refuses non-loopback sockets, and
    a replay is not a build. Spans and logs still reach the local files."""
    for name in list(os.environ):
        if name.startswith("OTEL_EXPORTER_OTLP_") and name.endswith("_ENDPOINT"):
            del os.environ[name]
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""


def _repo_relative(raw: str) -> str | None:
    """``raw`` as a ``/``-separated path under the repository, or None
    outside it (or under :data:`_NOT_INPUTS`)."""
    absolute = os.path.abspath(raw)
    root = os.path.normcase(str(REPO_ROOT)) + os.sep
    if not os.path.normcase(absolute).startswith(root):
        return None
    relative = absolute[len(root) :].replace(os.sep, "/")
    if any(
        os.path.normcase(relative + "/").startswith(os.path.normcase(prefix + "/"))
        for prefix in _NOT_INPUTS
    ):
        return None
    return relative


class _Owner(Enum):
    """Whose code a stack frame runs, for :func:`_python_files`."""

    RECIPE = "recipe"  # the build script's own code
    ENGINE = "engine"  # _com_conversation, serving or checking for itself
    OTHER = "other"  # helpers, the standard library: look further out


def _python_files(script: Path, scratch: Path) -> Any:
    """Start noting what the build script's own execution loads and reads:
    each file opened for reading and each module imported while, walking out
    from the event, a frame of ``script`` comes before one of the engine
    (``_com_conversation``). The returned callable lists them, with the script
    itself, as repository-relative paths: what the replayed recipe executed or
    read, bar its own outputs under ``scratch``. What the engine loads or
    reads for itself (its frames come first: ``redirect_outputs``' ``_paths``,
    ``_session``, the log, ``check_inputs``' digests) is left out, and so is a
    module the recipe uses after something else imported it (no import
    happens then): a differing input left out is unjudged, the safe
    direction. So is work in a thread or task the script starts, whose frames
    do not reach it."""
    import _com_conversation as conversation

    owners = {
        _code_file(str(script)): _Owner.RECIPE,
        _code_file(conversation.__file__): _Owner.ENGINE,
    }
    seen: dict[str, _Owner] = {}
    opened: set[str] = set()
    imported: set[str] = set()
    writing = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT

    def owner(filename: str) -> _Owner:
        found = seen.get(filename)
        if found is None:
            found = seen[filename] = owners.get(_code_file(filename), _Owner.OTHER)
        return found

    def by_recipe(frame: Any) -> bool:
        while frame is not None:
            found = owner(frame.f_code.co_filename)
            if found is not _Owner.OTHER:
                return found is _Owner.RECIPE
            frame = frame.f_back
        return False

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event not in ("open", "import") or not args:
            return
        try:
            if event == "import":
                if isinstance(args[0], str) and by_recipe(sys._getframe(1)):
                    imported.add(args[0])
                return
            path, mode = args[0], args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else 0
            if isinstance(mode, str) and any(c in mode for c in "wax+"):
                return
            if mode is None and isinstance(flags, int) and flags & writing:
                return
            if isinstance(path, (str, bytes, os.PathLike)) and by_recipe(
                sys._getframe(1)
            ):
                opened.add(os.fsdecode(path))
        except Exception:  # noqa: BLE001 - an audit hook must never fail an open
            return

    sys.addaudithook(hook)

    def files() -> list[str]:
        outputs = _code_file(str(scratch)) + os.sep
        sources = [
            getattr(sys.modules.get(name), "__file__", None) for name in imported
        ]
        found = {
            relative
            for raw in (
                str(script),
                *opened,
                *(source for source in sources if isinstance(source, str)),
            )
            if not _code_file(raw).startswith(outputs)
            and (relative := _repo_relative(raw)) is not None
            and os.path.isfile(raw)
        }
        return sorted(found)

    return files


def _code_file(name: str) -> str:
    """A code object's file name as one path compares on this system."""
    return os.path.normcase(os.path.abspath(name))


def _out_paths(trailer: dict[str, Any]) -> list[str]:
    """The output-root paths (relative, ``/``-separated) the log's COM
    arguments name."""
    found = set()
    for canonical in trailer.get("internal_paths", []):
        for placeholder in ("<OUT>", "<OUT/>"):
            if canonical.startswith(placeholder):
                rest = canonical[len(placeholder) :].lstrip("\\/").replace("\\", "/")
                if rest:
                    found.add(rest)
    return sorted(found)


def _captured(trailer: dict[str, Any]) -> set[str]:
    """The output-root paths of the files SolidWorks wrote that the log keeps."""
    return {rel for files in trailer.get("captured", {}).values() for rel in files}


def _solidworks_inputs(conversation: Any) -> tuple[list[str], list[str]]:
    """Files the log's COM arguments name that SolidWorks opens itself:
    ``(repository-relative paths outside the output root, output-root paths
    that are not the log's captured outputs)``. A path outside the repository
    is no build input and is left out."""
    trailer = conversation.trailer
    named = []
    for canonical in trailer.get("external", {}):
        for placeholder in ("<REPO>", "<REPO/>"):
            if canonical.startswith(placeholder):
                rest = canonical[len(placeholder) :].lstrip("\\/")
                named.append(rest.replace("\\", "/"))
    captured = _captured(trailer)
    inside = [path for path in _out_paths(trailer) if path not in captured]
    return sorted(set(named)), inside


def _replay_gaps(trailer: dict[str, Any], argv: list[str]) -> dict[str, Any]:
    """What a replay of this recording would need that the engine's replay
    lacks, measured on the recording (each list: its ``count`` and the
    ``first`` :data:`_GAPS_LISTED` paths, relative to the output root).

    ``argv``: how many arguments the script ran with (the engine's replay
    passes none; the driver's passes them after ``--``). ``out_paths``: every
    output-root path the log's COM arguments name;
    ``out_paths_unredirected``: those outside :data:`_REDIRECTED`, which
    SolidWorks would write or read outside the engine's scratch root (a
    drawing's own the driver redirects, :func:`_drawing_outputs`).
    ``out_inputs``: named output-root files the log did not capture as
    written (the models it opened, which a replay would have to stage at their
    recorded bytes); ``out_inputs_unredirected`` likewise. ``python_out_reads``:
    output-root files the script's own Python read inside the window that the
    log did not capture (the replay neither stages nor pins them; an upper
    bound, as files the build wrote itself count)."""
    captured = _captured(trailer)
    out_paths = _out_paths(trailer)
    inputs = [path for path in out_paths if path not in captured]
    reads = sorted(
        {
            str(entry[0])
            for entry in trailer.get("reads") or []
            if entry and str(entry[0]) not in captured
        }
    )

    def unredirected(paths: list[str]) -> list[str]:
        return [p for p in paths if p.split("/", 1)[0].lower() not in _REDIRECTED]

    def listed(paths: list[str]) -> dict[str, Any]:
        return {"count": len(paths), "first": paths[:_GAPS_LISTED]}

    return {
        "argv": len(argv),
        "out_paths": listed(out_paths),
        "out_paths_unredirected": listed(unredirected(out_paths)),
        "out_inputs": listed(inputs),
        "out_inputs_unredirected": listed(unredirected(inputs)),
        "python_out_reads": listed(reads),
    }


def _display(log: Any) -> dict[str, Any] | None:
    """The seat's drawing display at the log's last probe, from its answers:
    ``view_window`` (``[width, height]`` pixels) and ``px_per_mm`` (as
    ``_seat_forensics._projected_px_per_mm`` measures it: the largest of the
    three axes' projected millimetre, to 3 decimals). None for a log without
    one; a probe whose answers cannot be read leaves its key out."""
    found: dict[str, Any] = {}
    origin: tuple[float, float] | None = None
    axes: list[float] = []
    for call in log.calls:
        if call.site == _VISIBLE_BOX:
            box = call.result.get("t") if isinstance(call.result, dict) else None
            if (
                isinstance(box, list)
                and len(box) == 4
                and all(type(value) is int for value in box)
            ):
                left, top, right, bottom = box
                found["view_window"] = [abs(right - left), abs(bottom - top)]
            continue
        if call.site != _PROJECT:
            continue
        point = _hex_floats(call.args)[:3]
        screen = _hex_floats(call.result)[:2]
        if len(point) != 3 or len(screen) != 2:
            continue
        if point == [0.0, 0.0, 0.0]:
            origin, axes = (screen[0], screen[1]), []
        elif origin is not None and sorted(point) == [0.0, 0.0, _AXIS_MM]:
            axes.append(round(math.dist(origin, screen), 3))
            found["px_per_mm"] = max(axes)
    return found or None


def _logged_display(log: Path) -> dict[str, Any] | None:
    """:func:`_display` of the log at ``log`` without loading it, for the
    record driver, which still holds the seat: only lines naming a probe site
    are parsed, as ``_com_conversation.LogWriter`` writes them (``w`` the
    site, ``a`` the arguments past an interned dispatch header, which holds no
    float, ``r`` the answer; pinned against ``load`` by test)."""
    probes = []
    with gzip.open(log, "rt", encoding="utf-8") as stream:
        for text in stream:
            if _VISIBLE_BOX not in text and _PROJECT not in text:
                continue
            line = json.loads(text)
            if line.get("w") in (_VISIBLE_BOX, _PROJECT):
                probes.append(
                    types.SimpleNamespace(
                        site=line["w"], args=line.get("a"), result=line.get("r")
                    )
                )
    return _display(types.SimpleNamespace(calls=probes))


def _hex_floats(value: Any) -> list[float]:
    """Every logged float in ``value`` (``{"f": <hex>}``), in order."""
    if isinstance(value, dict):
        if set(value) == {"f"}:
            return [float.fromhex(value["f"])]
        return [f for item in value.values() for f in _hex_floats(item)]
    if isinstance(value, list):
        return [f for item in value for f in _hex_floats(item)]
    return []


def _title_echoes(log: Any) -> dict[str, Any]:
    """The log's recipe requests whose arguments carry a SolidWorks
    new-document title counter (``Part24``): the script echoed the seat's
    session state into a request. A no-op replay issued exactly the log's
    recipe requests, so these are the replay's. ``first``: ``<recipe index>
    <member>`` of the first :data:`_ECHOES_LISTED`."""
    import _com_conversation as conversation
    import _com_outcome

    found = [
        f"{index} {call.site}"
        for index, call in enumerate(conversation.recipe_calls(log.calls))
        if _com_outcome.carries_title_counter(call.args)
    ]
    return {"count": len(found), "first": found[:_ECHOES_LISTED]}


def _summary(
    conversation: Any,
    timing: dict[str, Any] | None,
    faults: list[dict[str, str]],
    exit_code: int,
    argv: list[str],
    display: dict[str, Any] | None,
) -> dict[str, Any]:
    """What dodo publishes and measures about one recorded build; ``display``
    is :func:`_display` of its log."""
    timing = timing or {}
    trailer = timing.get("trailer") or {}
    calls = trailer.get("calls")
    inert = trailer.get("inert_calls")
    audit = trailer.get("escape_audit") or {}
    return {
        "schema": SUMMARY_SCHEMA,
        "exit_code": exit_code,
        "rc": timing.get("rc"),
        "faults": faults,
        "engine": conversation.sha256_file(conversation.ENGINE_FILE),
        "script": timing.get("script"),
        "sw_revision": timing.get("sw_revision"),
        # The process inputs a replay must reproduce (check_inputs pins them).
        "environment": {
            key: os.environ.get(key) for key in conversation.ENVIRONMENT_KEYS
        },
        "complete": trailer.get("status") == "complete" and not faults,
        "outcome": trailer.get("outcome"),
        "calls": calls,
        "inert_calls": inert,
        "recipe_requests": calls - inert
        if isinstance(calls, int) and isinstance(inert, int)
        else None,
        "callers": trailer.get("callers"),
        "clock_seconds": trailer.get("clock_seconds"),
        "window_seconds": trailer.get("window_seconds"),
        "escape_audit_seconds": audit.get("seconds"),
        "script_seconds": timing.get("script_seconds"),
        "capture_files": trailer.get("capture_files"),
        "capture_bytes": trailer.get("capture_bytes"),
        "capture_stored_bytes": trailer.get("capture_stored_bytes"),
        "argv": argv,
        "replay_gaps": _replay_gaps(trailer, argv),
        "display": display,
    }


@contextlib.contextmanager
def _keep_argv(conversation: Any, argv: list[str]) -> Iterator[None]:
    """Run the build script with ``argv`` after its name, as ``python <script>
    ARG...`` would: the engine's ``run_script`` sets ``sys.argv`` to the
    script alone just before it runs the script, so the arguments are put
    back at that moment, around the engine and without changing it."""
    if not argv:
        yield
        return
    import runpy

    run_script, run_path = conversation.run_script, runpy.run_path

    def run_with_argv(path: str, *args: Any, **kwargs: Any) -> Any:
        sys.argv[1:] = argv
        return run_path(path, *args, **kwargs)

    def run_script_with_argv(script: Path) -> int:
        runpy.run_path = run_with_argv
        try:
            return run_script(script)
        finally:
            runpy.run_path = run_path

    conversation.run_script = run_script_with_argv
    try:
        yield
    finally:
        conversation.run_script = run_script


class _Staging(Enum):
    """How :func:`_staged_inputs` puts one output-root file in the scratch root."""

    COPY = "copy"  # the script's Python read it: its bytes
    STUB = "stub"  # SolidWorks alone opened it, and SolidWorks is absent


# What a stub holds (_Staging.STUB): nothing.
_STUB_SHA256 = hashlib.sha256(b"").hexdigest()


@contextlib.contextmanager
def _staged_inputs(
    conversation: Any,
    kind: str,
    inputs: Any,
    staged: dict[str, str],
    stubs: set[str],
) -> Iterator[None]:
    """An assembly's or drawing's replay with the output-root files its
    recording read in the scratch root, where the build's redirected paths
    (``_paths.OUT_*``) look for them, once the engine has made the scratch
    root: ``inputs()``, each with its :class:`_Staging`, none of them the
    log's captured outputs. SolidWorks is absent, but the script's own checks
    are not: without them, one that checks a child exists before placing it
    (``_assembly.place_component``) raises. A file the script's Python read
    is copied; a model only SolidWorks opened, whose answers come from the
    log, is an empty stub (no copy of a large part of the output root inside
    the reuse deadline; a Python read of one is the result's ``stub_reads``).
    ``staged``: each output-root file's SHA-256, hashed once, whose bytes a
    reuse attempt then requires to be the ones their tokens name; ``stubs``:
    those the scratch root holds as stubs. A part's replay is left as it
    is."""
    if kind == "part":
        yield
        return
    redirect, real = conversation.redirect_outputs, conversation.OUT_ROOT

    def staging(out_root: Path) -> None:
        redirect(out_root)
        for relative, how in inputs():
            source = real / relative
            if not source.is_file():
                continue
            target = out_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if how is _Staging.STUB:
                target.touch()
                staged[relative] = conversation.sha256_file(source)
                stubs.add(relative)
                continue
            shutil.copyfile(source, target)
            staged[relative] = conversation.sha256_file(target)

    conversation.redirect_outputs = staging
    try:
        yield
    finally:
        conversation.redirect_outputs = redirect


class _AfterImport:
    """A meta-path finder that runs ``then`` on module ``name`` right after its
    import executes it, once, before any importer binds its names: the import
    stays its importer's own (the recipe's, which ``python_files`` notes)."""

    def __init__(self, name: str, then: Any) -> None:
        self.name, self.then = name, then

    def find_spec(self, fullname: str, path: Any, target: Any = None) -> Any:
        if fullname != self.name:
            return None
        sys.meta_path.remove(self)
        import importlib.machinery

        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        execute, then = spec.loader.exec_module, self.then

        def exec_module(module: types.ModuleType) -> None:
            execute(module)
            then(module)

        spec.loader.exec_module = exec_module  # type: ignore[method-assign]
        return spec


def _redirect_drawing(module: Any, scratch: Path) -> None:
    """``_drawing_types``' output-root paths (``DrawingSpec.source``, the
    staged model the drawing documents; ``DrawingSpec.outputs``;
    ``LAYOUT_REPORT_DIR``) under ``scratch`` instead, as ``redirect_outputs``
    does ``_paths.OUT_*``."""
    real = module.CAD_ROOT / "out"
    source, outputs = module.DrawingSpec.source, module.DrawingSpec.outputs

    def moved(path: Path) -> Path:
        return scratch / path.relative_to(real)

    module.DrawingSpec.source = property(lambda spec: moved(source.fget(spec)))
    module.DrawingSpec.outputs = property(
        lambda spec: {name: moved(path) for name, path in outputs.fget(spec).items()}
    )
    module.LAYOUT_REPORT_DIR = moved(module.LAYOUT_REPORT_DIR)


@contextlib.contextmanager
def _drawing_outputs(conversation: Any, kind: str) -> Iterator[None]:
    """A drawing replayed in the scratch root without a change to the engine
    or to any recipe. A drawing names its model, sheet, PDF, PNG and layout
    report under the output root through ``_drawing_types``, outside the
    engine's redirect (:data:`_REDIRECTED`): once the scratch root is made
    (and staged, :func:`_staged_inputs`), and once the recipe's own import
    has executed ``_drawing_types``, its paths move under the scratch root
    (:func:`_redirect_drawing`). The output root itself also encodes as
    ``<OUT>``, after the scratch root, which lies under it: a model a script
    names there (``_paths.CAD_ROOT``) is the request its recording made. A
    write that still escapes is refused by the replay's guard, as any write
    outside the scratch root is: a refusal, never a stale output."""
    if kind != "drawing":
        yield
        return
    roots, redirect = conversation.Roots, conversation.redirect_outputs
    real = conversation.OUT_ROOT

    class OutputRoots(roots):  # type: ignore[misc, valid-type]
        def __post_init__(self) -> None:
            super().__post_init__()
            if Path(self.out) == real:
                return
            own = self._subs  # type: ignore[attr-defined]
            also = roots(real, self.repo)._subs[:2]  # type: ignore[attr-defined]
            object.__setattr__(self, "_subs", (*own[:2], *also, *own[2:]))

    def redirect_drawing(out_root: Path) -> None:
        redirect(out_root)
        module = sys.modules.get("_drawing_types")
        if module is not None:
            _redirect_drawing(module, out_root)
            return
        sys.meta_path.insert(
            0,
            _AfterImport(
                "_drawing_types", lambda found: _redirect_drawing(found, out_root)
            ),
        )

    conversation.Roots, conversation.redirect_outputs = OutputRoots, redirect_drawing
    try:
        yield
    finally:
        conversation.Roots, conversation.redirect_outputs = roots, redirect
        sys.meta_path[:] = [
            finder for finder in sys.meta_path if not isinstance(finder, _AfterImport)
        ]


def _record(args: argparse.Namespace, script: Path) -> int:
    # _telemetry is imported only once the build is over: until the script
    # imports it, this process is the build process, timed and labelled as one.
    import _com_conversation as conversation

    timing: dict[str, Any] | None = None
    propagated = False
    try:
        with _keep_argv(conversation, args.argv):
            timing = conversation.record_build(
                script,
                args.log.resolve(),
                out_root=args.out_root.resolve() if args.out_root else None,
                callers=conversation.CallerCapture(args.callers)
                if args.callers
                else conversation.DEFAULT_CALLERS,
            )
    except conversation.RecordFault:
        propagated = True
    faults = conversation.record_faults()
    import _telemetry

    rc = timing["rc"] if timing is not None else 1
    rerun = conversation.rerun_required()
    exit_code = conversation.EXIT_RECORD_FAULT if rerun else int(rc)
    if faults:
        first = faults[0]
        recovery = (
            conversation.Recovery.RERUN if rerun else conversation.Recovery.DEGRADED
        )
        consequence = (
            f"the build is re-run unrecorded (exit {exit_code})"
            if rerun
            else "recording stopped there and the build finished on its real "
            f"results (exit {exit_code}); nothing of it is published"
        )
        _telemetry.warn(
            f"[com-replay] recording fault in {first['where']} "
            f"({first['type']}: {first['message']}); this recording is unusable "
            f"and {consequence}",
            where=first["where"],
            fault_type=first["type"],
            fault_count=len(faults),
            recovery=recovery.value,
        )
    if args.summary is not None:
        display = None
        if args.kind == "drawing" and timing is not None and not faults:
            # On the seat: only the log's probe lines are parsed (_logged_display).
            try:
                display = _logged_display(args.log.resolve())
            except Exception as exc:  # noqa: BLE001 - never the summary's
                _telemetry.warn(f"[com-replay] display not read from the log: {exc!r}")
        try:
            _write_json(
                args.summary,
                _summary(conversation, timing, faults, exit_code, args.argv, display),
            )
        except Exception as exc:  # noqa: BLE001 - the recording's, never the build's
            # No summary means dodo publishes nothing; the build itself stands.
            _telemetry.warn(f"[com-replay] summary not written: {exc!r}")
    if propagated:
        # The fault unwound run_build before its own flush.
        _telemetry.shutdown()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = _arguments(sys.argv[1:] if argv is None else argv)
    if args.command == "record":
        # The build's process as unrecorded but for the recorder: its streams
        # are left as they are (run_build reconfigures them itself), and only
        # the engine is loaded before the script runs.
        return _record(args, args.script.resolve())
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    if args.command == "replay":
        _offline_telemetry()

    import _com_conversation as conversation

    if args.command == "diff":
        import _com_outcome

        base, new = conversation.load(args.base), conversation.load(args.new)
        payload = conversation.compare_conversations(base, new)
        positional = payload["request_divergence"]
        bound_fault = None
        if positional is not None and args.kind in _com_outcome.DEPENDENT_KINDS:
            # The components an array lists, by name rather than by the
            # seat's enumeration order (_com_outcome.name_bound).
            try:
                named, bound = _com_outcome.name_bound(base, new)
            except Exception as exc:  # noqa: BLE001 - costs the binding only
                bound_fault = {
                    "step": "name_bound",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            else:
                if bound:
                    new = named
                    payload = conversation.compare_conversations(base, new)
                    payload["name_bound"] = {
                        "arrays": bound,
                        "positional_divergence": positional,
                    }
        _com_outcome.label_feature(payload["request_divergence"])
        payload.update(
            _com_outcome.judge(
                base,
                new,
                payload["request_divergence"],
                conversation.capture_dir_of(args.base),
                conversation.capture_dir_of(args.new),
                kind=args.kind,
                base_sidecars=args.base_sidecars,
                new_sidecars=args.new_sidecars,
            )
        )
        if bound_fault is not None:
            # A judge fault like the judge's own: counted and logged at WARN.
            payload["judge_faults"].insert(0, bound_fault)
        try:
            # Each recording's own drawing display, for a base whose manifest
            # predates ``display``.
            payload["display"] = {"base": _display(base), "new": _display(new)}
        except Exception as exc:  # noqa: BLE001 - costs the display only
            payload["display"] = {"error": f"{type(exc).__name__}: {exc}"}
        if args.result is not None:
            _write_json(args.result, payload)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if payload["request_divergence"] is None:
            return 0
        return conversation.EXIT_REPLAY_NOT_NOOP

    script = args.script.resolve()

    import _telemetry

    # Telemetry creates cad/out/reports/telemetry on first use: do it before the
    # replay's audit hook starts refusing writes outside the scratch root.
    _telemetry.info(f"com_replay replay {script.name} <- {args.log}")
    python_files = _python_files(script, args.scratch.resolve())
    log_path = args.log.resolve()
    # The trailer and calls read below are the log replay_build parses: keep
    # what it loads instead of parsing the log a second time.
    loaded: dict[Path, Any] = {}
    load = conversation.load

    def keeping(path: Path) -> Any:
        loaded[path] = found = load(path)
        return found

    conversation.load = keeping
    staged: dict[str, str] = {}
    stubs: set[str] = set()

    def recorded_inputs() -> list[tuple[str, _Staging]]:
        trailer = loaded[log_path].trailer
        reads = {str(entry[0]) for entry in trailer.get("reads") or [] if entry}
        named = (set(_out_paths(trailer)) | reads) - _captured(trailer)
        python = {rel.casefold() for rel in reads}
        return [
            (rel, _Staging.COPY if rel.casefold() in python else _Staging.STUB)
            for rel in sorted(named)
        ]

    try:
        with (
            _keep_argv(conversation, args.argv),
            _staged_inputs(conversation, args.kind, recorded_inputs, staged, stubs),
            _drawing_outputs(conversation, args.kind),
        ):
            result = conversation.replay_build(
                script,
                log_path,
                args.scratch.resolve(),
                args.base_outputs.resolve() if args.base_outputs else None,
                capture_dir=args.capture_dir.resolve() if args.capture_dir else None,
                seat_log=args.seat_log.resolve(),
            )
    finally:
        conversation.load = load
    files = python_files()
    log = loaded[log_path]
    solidworks_inputs, solidworks_out_inputs = _solidworks_inputs(log)
    replayed = result.to_json()
    if staged:
        # A staged input the script left as it was is no output of its.
        replayed["py_outputs"] = {
            relative: digest
            for relative, digest in result.py_outputs.items()
            if (_STUB_SHA256 if relative in stubs else staged.get(relative)) != digest
        }
        replayed["staged"] = staged
        stubbed = {rel.casefold() for rel in stubs}
        replayed["stub_reads"] = sorted(
            {
                str(entry[0])
                for entry in result.details.get("reads") or []
                if entry and str(entry[0]).casefold() in stubbed
            }
        )
    _write_json(
        args.result,
        {
            **replayed,
            "python_files": files,
            "solidworks_inputs": solidworks_inputs,
            "solidworks_out_inputs": solidworks_out_inputs,
            "title_echoes": _title_echoes(log),
        },
    )
    inert = result.details.get("inert") or {}
    summary = (
        f"replay {script.name}: {result.verdict.value} "
        f"({result.served}/{result.recorded} recipe requests served, inert "
        f"{inert.get('served', 0)}/{inert.get('recorded', 0)} served "
        f"{inert.get('unserved', 0)} unrecorded, {result.seconds:.2f}s)"
    )
    if result.verdict is conversation.Verdict.NOOP:
        _telemetry.success(summary)
    else:
        _telemetry.warn(f"{summary}: {result.details.get('reason')}")
    _telemetry.shutdown()
    if result.verdict is conversation.Verdict.NOOP:
        return 0
    return conversation.EXIT_REPLAY_NOT_NOOP


if __name__ == "__main__":
    sys.exit(main())
