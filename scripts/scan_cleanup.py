"""Inventory Windows project cleanup candidates; never delete or modify anything.

Run with an existing Python 3.12+ interpreter (no project dependencies needed)::

    python scripts/scan_cleanup.py
    python scripts/scan_cleanup.py --measure --max-entries 20000

JSON goes to stdout. Name matches are leads, not proof of project ownership or
permission to remove anything. Git registrations and primary checkout protection
are reported separately. No process inspection, shutdown, pruning, or Git writes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path
import stat
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ("ha-*", "sp-*", "harmonic-*", "mr-*", "machrev-*")


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def key(path: Path) -> str:
    return os.path.normcase(str(absolute(path)))


def within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def linked_ancestor(path: Path) -> Path | None:
    for component in (path, *path.parents):
        if reparse(component):
            return component
    return None


def positive(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def registrations(repo: Path, warnings: list[str]) -> list[dict]:
    """Read NUL-delimited porcelain, including spaces/newlines in path names."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo), "worktree", "list", "--porcelain", "-z"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"Git worktree inventory unavailable for {repo}: {exc}")
        return []
    if result.returncode:
        warnings.append(
            f"Git worktree inventory failed for {repo}: "
            + os.fsdecode(result.stderr).strip()
        )
        return []
    rows: list[dict] = []
    current: dict = {}
    for field in os.fsdecode(result.stdout).split("\0"):
        if not field:
            if current:
                rows.append(current)
                current = {}
            continue
        name, _, value = field.partition(" ")
        if name == "worktree":
            current = {"path": str(absolute(Path(value))), "repository": str(repo)}
        elif name in ("HEAD", "branch", "locked", "prunable"):
            current[name] = value
        elif name in ("detached", "bare"):
            current[name] = True
    if current:
        rows.append(current)
    return rows


def measure(path: Path, args: argparse.Namespace, budget: dict) -> dict:
    """Bounded, non-following logical-byte estimate, not allocated disk usage."""
    result = {"logical_bytes": 0, "files": 0, "entries": 0, "complete": True,
              "skipped_links": 0, "errors": [], "limits": []}
    pending = [(path, 0)]
    while pending:
        if budget["remaining"] <= 0 or time.monotonic() >= budget["deadline"]:
            result["complete"] = False
            result["limits"].append("global entry/time budget")
            break
        current, depth = pending.pop()
        try:
            if linked_ancestor(current) is not None:
                result["skipped_links"] += 1
                result["complete"] = False
                continue
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode):
                result["logical_bytes"] += info.st_size
                result["files"] += 1
                budget["remaining"] -= 1
                result["entries"] += 1
                continue
            if depth >= args.max_depth:
                result["complete"] = False
                if "depth" not in result["limits"]:
                    result["limits"].append("depth")
                continue
            with os.scandir(current) as entries:
                for entry in entries:
                    if budget["remaining"] <= 0 or time.monotonic() >= budget["deadline"]:
                        result["complete"] = False
                        result["limits"].append("global entry/time budget")
                        pending.clear()
                        break
                    budget["remaining"] -= 1
                    result["entries"] += 1
                    child = Path(entry.path)
                    # Do not enqueue junctions, symlinks, or other reparse points.
                    if reparse(child):
                        result["skipped_links"] += 1
                        result["complete"] = False
                    elif entry.is_dir(follow_symlinks=False):
                        pending.append((child, depth + 1))
                    else:
                        result["logical_bytes"] += entry.stat(follow_symlinks=False).st_size
                        result["files"] += 1
        except OSError as exc:
            result["complete"] = False
            result["errors"].append(f"{current}: {exc}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", action="append", type=Path, default=[],
                        help="additional directory whose immediate children are name-matched; repeatable")
    parser.add_argument("--path", action="append", type=Path, default=[],
                        help="additional exact path to inventory, even if missing; repeatable")
    parser.add_argument("--git-repo", action="append", type=Path, default=[],
                        help="additional repository whose registered worktrees are inventoried")
    parser.add_argument("--measure", action="store_true", help="estimate candidate sizes without following links")
    parser.add_argument("--max-entries", type=positive, default=20000,
                        help="global measurement entry budget (default: 20000)")
    parser.add_argument("--max-depth", type=positive, default=6,
                        help="maximum measurement depth (default: 6)")
    parser.add_argument("--seconds", type=positive, default=15,
                        help="global measurement time budget in seconds (default: 15)")
    parser.add_argument("--discovery-entries", type=positive, default=20000,
                        help="global shallow-discovery entry budget (default: 20000)")
    args = parser.parse_args()
    warnings: list[str] = []
    candidates: dict[str, dict] = {}

    def add(path: Path, reason: str, attribution: str) -> None:
        path = absolute(path)
        row = candidates.setdefault(key(path), {"path": str(path), "evidence": [], "attribution": []})
        if reason not in row["evidence"]:
            row["evidence"].append(reason)
        if attribution not in row["attribution"]:
            row["attribution"].append(attribution)

    roots = [ROOT.parent, Path("C:/"), Path("C:/tmp"), *args.root]
    exact = [(Path("C:/farm-build"), "requested exact farm-build path"),
             (ROOT / "wip", "project-local wip"),
             (ROOT / "logs", "project-local logs"),
             (ROOT / "build.log", "project-local build log"),
             (ROOT / "cad/out", "project-generated CAD output and reports")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        local_path = Path(local)
        roots.extend((local_path, local_path / "Temp"))
        exact.append((local_path / "ha-farm", "farm-run.ps1 default log/snapshot home"))
        exact.append((local_path / "harmonic-analyzer", "project buildgraph and archive caches"))
        exact.append((local_path / "harmonic-analyzer-agent-scratchpad", "project review evaluation scratchpad"))
        claude_project = str(ROOT).replace(":", "-").replace("\\", "-").replace("/", "-")
        exact.append((local_path / "Claude" / claude_project, "checkout-specific Claude session directory"))
    for name in ("TEMP", "TMP"):
        if value := os.environ.get(name):
            roots.append(Path(value))
    for temp_root in roots:
        if key(temp_root) in {
            key(Path(value)) for name in ("TEMP", "TMP")
            if (value := os.environ.get(name))
        } or (local and key(temp_root) == key(Path(local) / "Temp")):
            exact.append((temp_root / "machinist-review-codex-home", "machinist_review.py temporary Codex home; may contain auth links"))
    program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    exact.extend((
        (program_data / "harmonic-analyzer", "project machine-wide lock/state directory"),
        (program_data / "solidworks-pool/archive-cache", "shared SolidWorks pool archive cache; not exclusively this project"),
    ))
    if scratch := os.environ.get("HARMONIC_AGENT_SCRATCHPAD"):
        exact.append((Path(scratch) / "harmonic-analyzer/farm-runs", "farm-run.ps1 scratchpad override"))
    for path, reason in exact:
        add(path, reason, "project-specific location; contents not inspected for ownership")
    for path in args.path:
        add(path, "explicit --path", "operator-selected; ownership unverified")

    repos = [ROOT, *args.git_repo]
    pool = ROOT.parent / "solidworks-pool"
    if (pool / ".git").exists():
        repos.append(pool)
    worktrees: list[dict] = []
    seen_repos: set[str] = set()
    for repo in repos:
        repo = absolute(repo)
        if key(repo) not in seen_repos:
            seen_repos.add(key(repo))
            rows = registrations(repo, warnings)
            worktrees.extend(rows)
            for row in rows:
                add(Path(row["path"]), "git worktree registration", f"registered with {repo}")
    registered: dict[str, list[dict]] = {}
    for row in worktrees:
        registered.setdefault(key(Path(row["path"])), []).append(row)

    remaining = args.discovery_entries
    seen_roots: set[str] = set()
    discovery: list[dict] = []
    for root in roots:
        root = absolute(root)
        if key(root) in seen_roots:
            continue
        seen_roots.add(key(root))
        record = {"path": str(root), "complete": False, "examined": 0}
        discovery.append(record)
        try:
            if linked_ancestor(root) is not None:
                record["skipped"] = "reparse point or symlink in root path"
                continue
            with os.scandir(root) as entries:
                for entry in entries:
                    if remaining <= 0:
                        record["skipped"] = "global discovery entry budget exhausted"
                        break
                    remaining -= 1
                    record["examined"] += 1
                    name = entry.name.casefold()
                    if any(fnmatch.fnmatchcase(name, pattern) for pattern in PATTERNS):
                        add(Path(entry.path), f"name match in {root}", "name-only lead; project ownership unverified")
                else:
                    record["complete"] = True
        except OSError as exc:
            record["error"] = str(exc)

    primary = ROOT.resolve()
    # The first non-bare row is Git's main worktree, even when this script is
    # launched from a linked checkout. Protect it and its contents too.
    protected = {primary} | {absolute(repo).resolve() for repo in repos}
    for repo in seen_repos:
        rows = [row for row in worktrees if key(Path(row["repository"])) == repo]
        if rows and not rows[0].get("bare"):
            protected.add(Path(rows[0]["path"]).resolve())
    budget = {"remaining": args.max_entries, "deadline": time.monotonic() + args.seconds}
    measured_roots: list[Path] = []
    for row in sorted(candidates.values(), key=lambda item: (len(Path(item["path"]).parts), item["path"].casefold())):
        path = Path(row["path"])
        row["worktrees"] = registered.get(key(path), [])
        try:
            info = path.lstat()
            row["exists"] = True
            row["kind"] = "directory" if stat.S_ISDIR(info.st_mode) else "file"
            row["modified_utc"] = datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()
            canonical = path.resolve()
            row["protected"] = any(within(canonical, p) or within(p, canonical) for p in protected)
            link = linked_ancestor(path)
            row["reparse_ancestor"] = str(link) if link else None
            row["git_marker"] = (path / ".git").exists() if stat.S_ISDIR(info.st_mode) and not link else None
            if row["protected"]:
                row["review"] = "protected primary checkout, content, or ancestor; not a removal candidate"
            elif row["worktrees"]:
                row["review"] = "registered worktree; inspect Git state and active users separately"
            elif row["git_marker"]:
                row["review"] = "Git checkout not in queried registrations; do not treat as an ordinary folder"
            else:
                row["review"] = "manual attribution and active-use review required; not approved for deletion"
            if args.measure:
                overlap = next((p for p in measured_roots if within(path, p)), None)
                if row["protected"] or link or overlap:
                    row["measurement_skipped"] = "protected path, reparse point, or already covered by a parent candidate"
                else:
                    row["measurement"] = measure(path, args, budget)
                    measured_roots.append(path)
        except FileNotFoundError:
            row["exists"] = False
        except (OSError, RuntimeError) as exc:
            row["error"] = str(exc)
    report = {
        "read_only": True,
        "primary_checkout": str(primary),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "patterns": PATTERNS,
        "scope": "Immediate children only; no generic Temp/AppData purge; no deletion eligibility inferred.",
        "measurement_note": "Logical bytes, not allocated or reclaimable space; partial totals are lower bounds. Do not sum overlapping candidates.",
        "warnings": warnings,
        "discovery": discovery,
        "worktrees": worktrees,
        "candidates": sorted(candidates.values(), key=lambda row: row["path"].casefold()),
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
