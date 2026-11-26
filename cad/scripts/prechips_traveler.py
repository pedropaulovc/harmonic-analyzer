"""Render one enrolled part's travelers with the latest prechips release.

prechips is not an HA dependency while it stabilises (owner ruling 2026-11-11,
#2502): a locked prechips made every release change ``uv.lock`` and re-key
every machinist review. The wrapper runs it outside the project environment
with uv's tool runner, from PyPI:

1. ``uv tool run --from prechips@latest python -c <print version>`` resolves
   the newest release. ``@latest`` revalidates uv's cached index and ignores a
   ``uv tool install``-ed copy; a bare ``--from prechips`` would reuse either.
   The version is logged once and recorded on the spans as
   ``prechips.version``, so a sheet can be traced to its generator.
2. ``uv tool run --from prechips==<version> prechips traveler
   cad/process/<stem>/plan.toml --profile P --out cad/out/travelers/<stem>/<file>``
   runs once per ``_process_plans.TRAVELER_PROFILES`` entry, pinned to that
   version so both sheets come from the release just logged:
   ``traveler.html`` under the strict ``pro`` profile, then
   ``traveler-hobby.html`` under ``hobby`` (with its setup pictures).
3. A headless Chromium-family browser (Edge or Chrome; ``HARMONIC_PDF_BROWSER``
   names one explicitly) prints the hobby sheet, with the sheet's own ``@page``
   size and margins, to ``<slug>-traveler.pdf`` beside it. Releases ship that
   PDF (owner ruling 2026-11-14).

A family plan (``_process_plans.family_parts``: one plan for several parts)
renders the same three files for the shared sheet and then, for each part,
``prechips traveler <plan> --placeholder <part id> --shared-file <the shared
PDF's name>``: a one-page sheet that points to the shared one, printed to that
part's own ``<part slug>-traveler.pdf`` beside it. A release ships the shared
PDF once and each part's placeholder under the part's name.

``--standing`` (in place of a stem) renders the shop's standing instructions
instead: the one page of rules common to every traveler, which no traveler
repeats. With the same version resolution and print path it runs ``prechips
standing cad/process/shop --out cad/out/travelers/shop-standing-instructions/
shop-standing-instructions.html`` and prints that page to
``shop-standing-instructions.pdf`` beside it; a release ships the PDF under
``travelers/``. A resolved prechips without the ``standing`` command (argparse
``invalid choice``) exits 1 with a message naming the release it needs. The
page is one sheet by the owner's design: a print on more sheets exits 1 and
removes both files, so a row that grows the page fails loudly.

Only exit 0 from every run and every printed PDF is success. Every previous
traveler is removed first, and a refusal from either run removes every output
and returns that run's exit code (2 for a prechips refusal), so a refusal never
leaves stale or half-paired files behind. uv's own failures exit 1 instead: a
missing ``uv`` or an unreachable PyPI before any sheet is written, and a render
whose ``uv tool run`` failed before prechips ran (stderr carries uv's ``error:``
or ``×`` diagnostic, never prechips' ``prechips:`` prefix), so an
infrastructure failure is never read as a plan or shop-data refusal. A missing
browser (checked before any sheet) or a failed print also exits 1 and removes
every output.

Before printing, ``picture_clip.check`` measures the setup pictures on the
hobby sheet just rendered, in the font it prints in (text past a picture's
edge, text over text, a leader across text). A finding that
``cad/config/picture-clip-baseline.toml`` does not list, or a listed one that
no longer occurs, refuses the plan's pictures: exit 2, every output removed,
each named.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from filelock import FileLock, Timeout
from pypdf import PdfReader
from pypdf.errors import PdfReadError

import _telemetry
import _process_plans
import picture_clip

PACKAGE = "prechips"
_VERSION_PROBE = f"import importlib.metadata as m; print(m.version({PACKAGE!r}))"
BROWSER_ENV = "HARMONIC_PDF_BROWSER"
_BROWSER_NAMES = ("msedge", "chrome", "chromium", "google-chrome")
# Default per-machine and per-user install locations, for a browser not on PATH.
_BROWSER_INSTALLS = (
    ("ProgramFiles(x86)", "Microsoft/Edge/Application/msedge.exe"),
    ("ProgramFiles", "Microsoft/Edge/Application/msedge.exe"),
    ("ProgramFiles", "Google/Chrome/Application/chrome.exe"),
    ("ProgramFiles(x86)", "Google/Chrome/Application/chrome.exe"),
    ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
)
# A traveler prints in ~3 s; this bounds a browser that never exits. It times
# the print alone, never the wait for a print slot.
PRINT_TIMEOUT_S = 120
# Headless prints on one host share it: v51's gate printed 80 travelers at
# -n 8 beside FreeCAD posts on a loaded submitter, and 21 ran past the limit
# (#3460). Every print, from any worktree or build, takes one of these slots.
PRINT_SLOTS = 2
PRINT_LOCK_ENV = "HARMONIC_TRAVELER_PRINT_LOCK"
# The pseudo-stem of the shop's standing page (``prechips:standing`` in doit)
# and the name its HTML, PDF and released file carry.
STANDING_STEM = "standing"
STANDING_NAME = "shop-standing-instructions"


def standing_paths(out: Path = _process_plans.CAD_OUT) -> tuple[Path, Path]:
    """The standing page's HTML and the PDF printed beside it, the file a
    release ships as ``travelers/shop-standing-instructions.pdf``."""
    directory = Path(out) / "travelers" / STANDING_NAME
    return directory / f"{STANDING_NAME}.html", directory / f"{STANDING_NAME}.pdf"


def _uv() -> str:
    """The uv executable: the one running this process under ``uv run``, else PATH."""
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise RuntimeError("uv was not found on PATH; prechips runs with `uv tool run`")
    return uv


def browser() -> str:
    """The Chromium-family browser that prints the hobby sheet to PDF."""
    explicit = os.environ.get(BROWSER_ENV)
    if explicit:
        if not Path(explicit).is_file():
            raise RuntimeError(f"{BROWSER_ENV}={explicit!r} is not a file")
        return explicit
    for name in _BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for variable, relative in _BROWSER_INSTALLS:
        root = os.environ.get(variable)
        if root and (Path(root) / relative).is_file():
            return str(Path(root) / relative)
    raise RuntimeError(
        "no Edge or Chrome found to print the traveler PDF; "
        f"install one or set {BROWSER_ENV} to a Chromium-family browser"
    )


def print_command(browser_path: str, html: Path, pdf: Path, profile: Path) -> list[str]:
    # A private profile keeps the print in its own process: with the user's
    # profile, a launch hands the page to an already-running browser instead.
    return [
        browser_path, "--headless", "--disable-gpu", "--no-first-run",
        "--no-pdf-header-footer", f"--user-data-dir={profile}",
        f"--print-to-pdf={pdf}", html.resolve().as_uri(),
    ]


def print_lock_path() -> Path:
    """The host-wide print slots' lock path; slot ``i`` locks ``<path>.<i>``."""
    override = os.environ.get(PRINT_LOCK_ENV)
    if override:
        return Path(override)
    base = os.environ.get("PROGRAMDATA") or tempfile.gettempdir()
    return Path(base) / "harmonic-analyzer" / "traveler-print.lock"


@contextmanager
def print_slot(poll_s: float = 0.25) -> Iterator[None]:
    """Hold one of the host's ``PRINT_SLOTS`` while a headless browser prints."""
    path = print_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        for index in range(PRINT_SLOTS):
            lock = FileLock(f"{path}.{index}")
            try:
                lock.acquire(timeout=0)
            except Timeout:
                continue
            try:
                yield
            finally:
                lock.release()
            return
        time.sleep(poll_s)


def print_pdf(browser_path: str, html: Path, pdf: Path) -> None:
    """Print ``html`` to ``pdf``; raise unless a PDF file results."""
    pdf.unlink(missing_ok=True)
    name = Path(browser_path).name
    with (
        print_slot(),
        tempfile.TemporaryDirectory(
            prefix="ha-traveler-pdf-", ignore_cleanup_errors=True
        ) as profile,
    ):
        cmd = print_command(browser_path, html, pdf, Path(profile))
        try:
            result = subprocess.run(
                cmd, capture_output=True, encoding="utf-8", errors="replace",
                timeout=PRINT_TIMEOUT_S, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{name} did not print {html.name} within {PRINT_TIMEOUT_S} s") from exc
    printed = pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-"
    if result.returncode != 0 or not printed:
        output = (result.stderr or result.stdout or "").strip() or "no output"
        raise RuntimeError(
            f"{name} did not print {html.name} to PDF (exit {result.returncode}): {output}"
        )


def pdf_sheets(pdf: Path) -> int:
    """The printed sheets in a browser-printed PDF, read by pypdf."""
    try:
        return len(PdfReader(pdf).pages)
    except PdfReadError as exc:
        raise RuntimeError(f"{pdf.name} is not a readable PDF: {exc}") from exc


def latest_version(uv: str) -> str:
    """The newest prechips release on PyPI, resolved by ``uv tool run``."""
    cmd = [uv, "tool", "run", "--from", f"{PACKAGE}@latest", "python", "-c", _VERSION_PROBE]
    result = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    version = result.stdout.strip()
    if result.returncode != 0 or not version:
        raise RuntimeError(
            f"could not resolve the latest {PACKAGE} from PyPI with `uv tool run` "
            f"(exit {result.returncode}; network access to PyPI is required): "
            + (result.stderr.strip() or "no version printed")
        )
    return version


def uv_error(stderr: str) -> str | None:
    """uv's own diagnostic in a failed ``uv tool run``'s stderr, if any: uv
    prefixes its errors with ``error:`` (fetch, parse, install) or ``×``
    (resolution), while prechips prefixes its refusals with ``prechips:``."""
    for line in stderr.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("error:", "×")):
            return stripped
    return None


def traveler_command(uv: str, version: str, plan: Path, profile: str, html: Path) -> list[str]:
    return [
        uv, "tool", "run", "--from", f"{PACKAGE}=={version}", PACKAGE, "traveler",
        str(plan), "--profile", profile, "--out", str(html),
    ]


def placeholder_command(
    uv: str, version: str, plan: Path, part_id: str, shared_pdf: str, html: Path,
) -> list[str]:
    """One family part's placeholder: the plan passes the same checks as its
    ``PDF_PROFILE`` sheet, then prechips prints the pointer page instead."""
    return [
        *traveler_command(uv, version, plan, _process_plans.PDF_PROFILE, html),
        "--placeholder", part_id, "--shared-file", shared_pdf,
    ]


def standing_command(uv: str, version: str, shop: Path, html: Path) -> list[str]:
    return [
        uv, "tool", "run", "--from", f"{PACKAGE}=={version}", PACKAGE, "standing",
        str(shop), "--out", str(html),
    ]


def _run_prechips(cmd: list[str]) -> tuple[int, str]:
    """Run one pinned prechips render; its stderr (refusal text) still reaches
    the operator. Returns the exit code and that stderr."""
    result = subprocess.run(
        cmd, env=_telemetry.inject_env(), stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", check=False,
    )
    stderr = result.stderr or ""
    sys.stderr.write(stderr)
    return result.returncode, stderr


def _render_failure(version: str, what: str, code: int, stderr: str) -> tuple[RuntimeError, int]:
    """A failed render's error and exit code: prechips' own code for its
    refusal, 1 for a ``uv tool run`` that failed before prechips ran."""
    diagnostic = uv_error(stderr)
    if diagnostic is None:
        return RuntimeError(f"prechips {version} {what} exited with code {code}"), code
    return RuntimeError(
        f"uv could not run prechips {version} for {what} "
        f"(`uv tool run` exited {code}; not a prechips refusal): {diagnostic}"
    ), 1


def _fail(root, stem: str, exc: Exception, code: int, outputs: tuple[Path, ...]) -> int:
    """Remove every output, mark the pipeline span failed and return ``code``."""
    for path in outputs:
        path.unlink(missing_ok=True)
    root.record_exception(exc)
    root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
    _telemetry.error(f"{stem}: {exc}")
    return code


def _standing(out: Path) -> int:
    """Render and print the shop's standing page; see the module docstring."""
    with _telemetry.run_pipeline_span("prechips_traveler", stem=STANDING_STEM) as root:
        html, pdf = standing_paths(out)
        outputs = (html, pdf)
        for path in outputs:
            path.unlink(missing_ok=True)
        shop = _process_plans.SHOP_DIR
        if not _process_plans.shop_files(shop):
            exc = FileNotFoundError(f"{STANDING_STEM}: no shop .toml files in {shop}")
            return _fail(root, STANDING_STEM, exc, 2, outputs)
        try:
            uv = _uv()
            printer = browser()
            with _telemetry.span("prechips.resolve", stem=STANDING_STEM):
                version = latest_version(uv)
        except RuntimeError as exc:
            return _fail(root, STANDING_STEM, exc, 1, outputs)
        root.set_attribute("prechips.version", version)
        _telemetry.info(
            f"{STANDING_STEM}: prechips {version} (latest PyPI release)", prechips_version=version,
        )
        html.parent.mkdir(parents=True, exist_ok=True)
        with _telemetry.span("prechips.standing", stem=STANDING_STEM) as sp:
            sp.set_attribute("prechips.version", version)
            code, stderr = _run_prechips(standing_command(uv, version, shop, html))
        if code != 0:
            if "invalid choice: 'standing'" in stderr:
                exc = RuntimeError(
                    f"prechips {version} has no `standing` command; the shop standing "
                    "page needs the first prechips release that adds `prechips standing` "
                    f"(newer than {version})"
                )
                return _fail(root, STANDING_STEM, exc, 1, outputs)
            exc, code = _render_failure(version, "standing", code, stderr)
            return _fail(root, STANDING_STEM, exc, code, outputs)
        try:
            with _telemetry.span("prechips.pdf", stem=STANDING_STEM, browser=Path(printer).name):
                print_pdf(printer, html, pdf)
            sheets = pdf_sheets(pdf)
            if sheets != 1:
                raise RuntimeError(
                    f"the page prints on {sheets} sheets; the owner's design "
                    "is one sheet (shorten a row, or tighten prechips' standing layout)"
                )
        except RuntimeError as exc:
            return _fail(root, STANDING_STEM, exc, 1, outputs)
        _telemetry.info(f"{STANDING_STEM}: printed {pdf.name}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stem", nargs="?")
    parser.add_argument(
        "--standing", action="store_true",
        help="render the shop's standing instructions page instead of a traveler",
    )
    parser.add_argument("--out", type=Path, default=_process_plans.CAD_OUT)
    args = parser.parse_args(argv)
    if args.standing == (args.stem is not None):
        parser.error("name one traveler stem, or --standing")
    _telemetry.set_service("prechips-traveler")
    if args.standing:
        return _standing(args.out)
    with _telemetry.run_pipeline_span("prechips_traveler", stem=args.stem) as root:
        plan = _process_plans.plan_path(args.stem)
        paths = _process_plans.traveler_paths(args.stem, args.out)
        pdf = _process_plans.traveler_pdf_path(args.stem, args.out)
        # A plan that cannot be read has no parts to name: its own outputs go.
        try:
            placeholders = _process_plans.placeholder_paths(args.stem, args.out)
        except (OSError, ValueError, KeyError):
            placeholders = {}
        outputs = (*paths, pdf, *(p for pair in placeholders.values() for p in pair))
        for path in outputs:
            path.unlink(missing_ok=True)
        if not plan.is_file():
            exc = FileNotFoundError(f"{args.stem}: no process plan at {plan}")
            return _fail(root, PACKAGE, exc, 2, outputs)
        try:
            uv = _uv()
            printer = browser()
            with _telemetry.span("prechips.resolve", stem=args.stem):
                version = latest_version(uv)
        except RuntimeError as exc:
            return _fail(root, args.stem, exc, 1, outputs)
        root.set_attribute("prechips.version", version)
        _telemetry.info(f"{args.stem}: prechips {version} (latest PyPI release)", prechips_version=version)
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        renders = [
            (f"--profile {profile}", profile, traveler_command(uv, version, plan, profile, html))
            for profile, html in zip(_process_plans.TRAVELER_PROFILES.values(), paths, strict=True)
        ] + [
            (
                f"--placeholder {part_id}", _process_plans.PDF_PROFILE,
                placeholder_command(uv, version, plan, part_id, pdf.name, html),
            )
            for part_id, (html, _pdf) in placeholders.items()
        ]
        for what, profile, cmd in renders:
            with _telemetry.span("prechips.traveler", stem=args.stem, profile=profile) as sp:
                sp.set_attribute("prechips.version", version)
                code, stderr = _run_prechips(cmd)
            if code != 0:
                exc, code = _render_failure(version, f"traveler {what}", code, stderr)
                return _fail(root, args.stem, exc, code, outputs)
        sheets = dict(zip(_process_plans.TRAVELER_PROFILES.values(), paths, strict=True))
        try:
            with _telemetry.span("picture_clip", stem=args.stem):
                refused = picture_clip.check(
                    args.stem, sheets[_process_plans.PDF_PROFILE]
                )
        except Exception as exc:  # noqa: BLE001 - any gate error refuses the render, outputs removed
            return _fail(root, args.stem, exc, 2, outputs)
        if refused:
            exc = RuntimeError(
                f"setup pictures on {sheets[_process_plans.PDF_PROFILE].name} "
                "(cad/scripts/picture_clip.py):\n  " + "\n  ".join(refused)
            )
            return _fail(root, args.stem, exc, 2, outputs)
        prints = [(sheets[_process_plans.PDF_PROFILE], pdf), *placeholders.values()]
        for html, printed in prints:
            try:
                with _telemetry.span(
                    "prechips.pdf", stem=args.stem, profile=_process_plans.PDF_PROFILE,
                    browser=Path(printer).name,
                ):
                    print_pdf(printer, html, printed)
            except RuntimeError as exc:
                return _fail(root, args.stem, exc, 1, outputs)
            _telemetry.info(f"{args.stem}: printed {printed.name}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
