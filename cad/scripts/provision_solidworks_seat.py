"""Provision shared SolidWorks drawing and British Association standards.

This clones the seat's complete vendor Toolbox data root, creates a custom
``British Association (Harmonic Analyzer)`` standard by copying BSI as the
SolidWorks Toolbox UI does, removes unrelated hardware from that custom
standard, adds the period 6 BA hole/thread rows, validates the clone, and only
then points the seat at it.  The stock database is never modified.

Run through ``scripts/solidworks/provision_seat.ps1`` with SolidWorks closed.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import _telemetry
from _drawing_registry import ASME_B_DRWDOT, ASME_B_SLDDRT
from _hole_wizard import BA6


CUSTOM_STANDARD = "British Association (Harmonic Analyzer)"
SOURCE_PREFIX = "BSI_"
CUSTOM_PREFIX = "HA_BA_"
DATABASE_RELATIVE = Path("lang") / "english" / "swbrowser.sldedb"
MIGRATION_VERSION = 1
DEFAULT_SHARED_ROOT = (
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    / "Harmonic Analyzer"
    / "SOLIDWORKS Standards"
)

EXPECTED_COLUMNS = {
    "BSI_DATA_HW_TappedHole": (
        "SIZE",
        "Pitch",
        "DIAMETER",
        "enabled",
        "key",
        "Name To Match",
    ),
    "BSI_DATA_HW_BottomingTap": (
        "SIZE",
        "Pitch",
        "DIAMETER",
        "enabled",
        "key",
        "Name To Match",
    ),
    "BSI_DATA_HW_TapDrills": (
        "SIZE",
        "DIAMETER",
        "TAP_DRILL",
        "enabled",
        "key",
        "Name To Match",
    ),
    "BSI_DATA_THRD": (
        "SIZE",
        "THD_DIA",
        "ADVANCE",
        "THD_MINOR",
        "THD_MINORI",
        "TAP_DRILL",
        "THD_DESC",
        "TPU",
        "full_size",
        "series",
        "enabled",
        "key",
    ),
}


@dataclass(frozen=True)
class ProvisionManifest:
    migration_version: int
    source_database_sha256: str
    solidworks_registry_version: str
    standard: str
    designation: str
    major_diameter_mm: float
    pitch_mm: float
    core_diameter_mm: float
    included_angle_deg: float


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_provision_manifest(root: Path) -> ProvisionManifest | None:
    path = root / "harmonic-analyzer-standard.json"
    if not path.is_file():
        return None
    try:
        manifest = ProvisionManifest(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid provision manifest: {path}") from exc
    if (
        manifest.migration_version != MIGRATION_VERSION
        or manifest.standard != CUSTOM_STANDARD
        or manifest.designation != BA6.designation
        or manifest.major_diameter_mm != BA6.major_diameter_mm
        or manifest.pitch_mm != BA6.pitch_mm
        or manifest.core_diameter_mm != BA6.core_diameter_mm
        or manifest.included_angle_deg != BA6.angle_deg
    ):
        raise RuntimeError(f"provision manifest is incompatible with this project: {path}")
    return manifest


def _publish_staging(staging: Path, destination: Path) -> None:
    for attempt in range(6):
        try:
            staging.rename(destination)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.25 * (attempt + 1))


def _solidworks_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    return "SLDWORKS.EXE" in result.stdout.upper()


def _is_administrator() -> bool:
    if sys.platform != "win32":
        return False
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def _registry_context() -> tuple[str, Path]:
    if sys.platform != "win32":
        raise RuntimeError("SolidWorks seat provisioning requires Windows")
    import winreg

    root = r"Software\SolidWorks"
    candidates: list[tuple[int, str]] = []
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root) as key:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(key, index)
            except OSError:
                break
            index += 1
            match = re.fullmatch(r"SOLIDWORKS (\d{4})", name)
            if match:
                candidates.append((int(match.group(1)), name))
    if not candidates:
        raise RuntimeError("no installed SolidWorks registry version found")
    _, version = max(candidates)
    general = rf"{root}\{version}\General"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, general) as key:
        toolbox, _ = winreg.QueryValueEx(key, "Toolbox Data Location")
    source = Path(str(toolbox))
    if not source.is_dir():
        raise FileNotFoundError(f"configured Toolbox root is missing: {source}")
    return version, source


def _columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in connection.execute(f"PRAGMA table_info([{table}])"))


def validate_source_schema(database: Path) -> None:
    with closing(
        sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    ) as connection:
        for table, expected in EXPECTED_COLUMNS.items():
            actual = _columns(connection, table)
            if actual != expected:
                raise RuntimeError(
                    f"unsupported Hole Wizard schema for {table}: "
                    f"expected={expected}, actual={actual}"
                )
        bsi = connection.execute(
            "SELECT COUNT(*) FROM Standards WHERE Name='BSI' AND TableNamePrefix='BSI_'"
        ).fetchone()[0]
        if bsi != 1:
            raise RuntimeError("source database has no unique BSI standard to copy")


def _clone_bsi_tables(connection: sqlite3.Connection) -> None:
    tables = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name LIKE 'BSI_%' ORDER BY name"
    ).fetchall()
    if not tables:
        raise RuntimeError("source database contains no BSI tables")
    for old_name, create_sql in tables:
        new_name = CUSTOM_PREFIX + old_name[len(SOURCE_PREFIX) :]
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (new_name,)
        ).fetchone():
            raise RuntimeError(f"custom standard table already exists: {new_name}")
        rewritten = re.sub(
            rf"^(CREATE TABLE\s+)\[?{re.escape(old_name)}\]?",
            rf"\1[{new_name}]",
            create_sql,
            count=1,
            flags=re.IGNORECASE,
        )
        connection.execute(rewritten)
        connection.execute(f"INSERT INTO [{new_name}] SELECT * FROM [{old_name}]")
        for column in _columns(connection, new_name):
            declared = connection.execute(
                f"PRAGMA table_info([{new_name}])"
            ).fetchall()
            column_type = next(row[2] for row in declared if row[1] == column)
            if str(column_type).upper() != "TEXT":
                continue
            connection.execute(
                f"UPDATE [{new_name}] SET [{column}]=REPLACE([{column}], ?, ?) "
                f"WHERE [{column}] LIKE ?",
                (SOURCE_PREFIX, CUSTOM_PREFIX, f"%{SOURCE_PREFIX}%"),
            )


def _insert_standard(connection: sqlite3.Connection) -> None:
    columns = [
        row[1]
        for row in connection.execute("PRAGMA table_info([Standards])")
        if row[1].lower() != "key"
    ]
    row = connection.execute(
        f"SELECT {', '.join(f'[{column}]' for column in columns)} "
        "FROM Standards WHERE Name='BSI'"
    ).fetchone()
    data = dict(zip(columns, row, strict=True))
    data.update(
        {
            "Name": CUSTOM_STANDARD,
            "enabled": 1,
            "Protected": 0,
            "CategoryID": f"{CUSTOM_PREFIX}Categories",
            "TypeID": f"{CUSTOM_PREFIX}Types",
            "TableNamePrefix": CUSTOM_PREFIX,
            "OrderID": max(
                value[0]
                for value in connection.execute("SELECT OrderID FROM Standards")
            )
            + 1,
            "TypeConvertTable": "",
            "HasStackComponents": 0,
            "SmartFastenerComponentTables": "",
            "HasHoles": 1,
            "IsToolbox": 0,
            "SWCONST_ENUM_VALUE": -1,
            "ScrewClearancesExcludedTable": "",
            "ScrewClearancesTable": "",
            "Installed": 1,
        }
    )
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO Standards ({', '.join(f'[{column}]' for column in columns)}) "
        f"VALUES ({placeholders})",
        tuple(data[column] for column in columns),
    )


def _trim_to_ba_holes(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"UPDATE [{CUSTOM_PREFIX}Categories] SET enabled=0, Protected=0"
    )
    connection.execute(
        f"UPDATE [{CUSTOM_PREFIX}Categories] SET enabled=1 "
        "WHERE Name='Hole Wizard Holes'"
    )
    connection.execute(f"UPDATE [{CUSTOM_PREFIX}Types] SET enabled=0, Protected=0")
    connection.execute(
        f"UPDATE [{CUSTOM_PREFIX}Types] SET enabled=1 "
        "WHERE CategoryID=? AND Name='Tapped Holes'",
        (f"{CUSTOM_PREFIX}TYPE_HOLES",),
    )
    connection.execute(
        f"UPDATE [{CUSTOM_PREFIX}Type_Holes] SET enabled=0, Protected=0"
    )
    connection.execute(
        f"UPDATE [{CUSTOM_PREFIX}Type_Holes] SET enabled=1 "
        "WHERE Name IN ('Tapped hole', 'Bottoming Tapped Hole')"
    )

    tapped = f"{CUSTOM_PREFIX}DATA_HW_TappedHole"
    bottoming = f"{CUSTOM_PREFIX}DATA_HW_BottomingTap"
    drills = f"{CUSTOM_PREFIX}DATA_HW_TapDrills"
    threads = f"{CUSTOM_PREFIX}DATA_THRD"
    for table in (tapped, bottoming, drills, threads):
        connection.execute(f"DELETE FROM [{table}]")
    basic = (
        BA6.designation,
        f"{BA6.pitch_mm:g}",
        f"{BA6.major_diameter_mm:g}",
        1,
        1,
        BA6.designation,
    )
    connection.execute(f"INSERT INTO [{tapped}] VALUES (?, ?, ?, ?, ?, ?)", basic)
    connection.execute(f"INSERT INTO [{bottoming}] VALUES (?, ?, ?, ?, ?, ?)", basic)
    connection.execute(
        f"INSERT INTO [{drills}] VALUES (?, ?, ?, ?, ?, ?)",
        (
            BA6.designation,
            f"{BA6.major_diameter_mm:g}",
            f"{BA6.core_diameter_mm:.3f}",
            1,
            1,
            BA6.designation,
        ),
    )
    connection.execute(
        f"INSERT INTO [{threads}] VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            BA6.designation,
            f"{BA6.major_diameter_mm:g}",
            f"{BA6.pitch_mm:g}",
            f"{BA6.core_diameter_mm:.3f}",
            f"{BA6.core_diameter_mm:.3f}",
            f"{BA6.core_diameter_mm:.3f}",
            BA6.designation,
            f"{BA6.pitch_mm:g}",
            BA6.designation,
            "BA",
            1,
            1,
        ),
    )


def migrate_database(database: Path) -> None:
    validate_source_schema(database)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA busy_timeout=5000")
        existing = connection.execute(
            "SELECT COUNT(*) FROM Standards WHERE Name=?", (CUSTOM_STANDARD,)
        ).fetchone()[0]
        if existing:
            verify_database(database)
            return
        connection.execute("BEGIN IMMEDIATE")
        _clone_bsi_tables(connection)
        _insert_standard(connection)
        _trim_to_ba_holes(connection)
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Hole Wizard database integrity check failed: {integrity}")
    verify_database(database)


def verify_database(database: Path) -> None:
    with closing(
        sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    ) as connection:
        standard = connection.execute(
            "SELECT TableNamePrefix, enabled, Protected FROM Standards WHERE Name=?",
            (CUSTOM_STANDARD,),
        ).fetchall()
        if standard != [(CUSTOM_PREFIX, 1, 0)]:
            raise RuntimeError(f"custom BA standard read-back failed: {standard!r}")
        expected = {
            f"{CUSTOM_PREFIX}DATA_HW_TappedHole": (
                BA6.designation,
                f"{BA6.pitch_mm:g}",
                f"{BA6.major_diameter_mm:g}",
            ),
            f"{CUSTOM_PREFIX}DATA_HW_BottomingTap": (
                BA6.designation,
                f"{BA6.pitch_mm:g}",
                f"{BA6.major_diameter_mm:g}",
            ),
            f"{CUSTOM_PREFIX}DATA_HW_TapDrills": (
                BA6.designation,
                f"{BA6.major_diameter_mm:g}",
                f"{BA6.core_diameter_mm:.3f}",
            ),
        }
        for table, row in expected.items():
            actual = connection.execute(f"SELECT * FROM [{table}]").fetchall()
            if len(actual) != 1 or tuple(actual[0][:3]) != row:
                raise RuntimeError(f"{table} read-back failed: {actual!r}")
        thread = connection.execute(
            f"SELECT SIZE, THD_DIA, ADVANCE, THD_MINOR, THD_MINORI, TAP_DRILL "
            f"FROM [{CUSTOM_PREFIX}DATA_THRD]"
        ).fetchall()
        expected_thread = [
            (
                BA6.designation,
                f"{BA6.major_diameter_mm:g}",
                f"{BA6.pitch_mm:g}",
                f"{BA6.core_diameter_mm:.3f}",
                f"{BA6.core_diameter_mm:.3f}",
                f"{BA6.core_diameter_mm:.3f}",
            )
        ]
        if thread != expected_thread:
            raise RuntimeError(f"BA thread-data read-back failed: {thread!r}")


@contextmanager
def _provision_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".provision.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"another seat provisioner holds {lock}") from exc
    os.close(descriptor)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _append_search_path(existing: str, directory: Path) -> str:
    values = [value for value in existing.split(";") if value]
    target = str(directory.resolve())
    if target.lower() not in {value.lower() for value in values}:
        values.insert(0, target)
    return ";".join(values)


def configure_registry(version: str, toolbox_root: Path, template_dir: Path) -> None:
    import winreg

    machine_general = rf"Software\SolidWorks\{version}\General"
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            machine_general,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key,
                "Toolbox Data Location",
                0,
                winreg.REG_SZ,
                str(toolbox_root.resolve()),
            )
    except PermissionError as exc:
        raise PermissionError(
            "setting the shared Hole Wizard database requires an elevated shell"
        ) from exc

    user_root = rf"Software\SolidWorks\{version}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{user_root}\Document Templates") as key:
        winreg.SetValueEx(
            key,
            "Default Draw Template",
            0,
            winreg.REG_SZ,
            str((template_dir / ASME_B_DRWDOT.name).resolve()),
        )
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{user_root}\ExtReferences") as key:
        for value_name in ("Document Template Folders", "Sheet Format Folders"):
            try:
                existing, _ = winreg.QueryValueEx(key, value_name)
            except FileNotFoundError:
                existing = ""
            winreg.SetValueEx(
                key,
                value_name,
                0,
                winreg.REG_SZ,
                _append_search_path(str(existing), template_dir),
            )


def _copy_templates(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for source in (ASME_B_DRWDOT, ASME_B_SLDDRT):
        if not source.is_file() or source.stat().st_size == 0:
            raise FileNotFoundError(f"project drawing standard is missing: {source}")
        shutil.copy2(source, destination / source.name)


def provision(
    *,
    version: str,
    source_root: Path,
    shared_root: Path,
    configure: bool,
    what_if: bool,
) -> tuple[Path, Path]:
    source_database = source_root / DATABASE_RELATIVE
    if not source_database.is_file():
        raise FileNotFoundError(f"source Hole Wizard database is missing: {source_database}")
    template_dir = shared_root / "templates"
    existing_manifest = _read_provision_manifest(source_root)
    if existing_manifest is not None:
        verify_database(source_database)
        _telemetry.info(
            f"provision plan: verify existing={source_root}; "
            f"templates={template_dir}"
        )
        if what_if:
            return source_root, template_dir
        _copy_templates(template_dir)
        if configure:
            configure_registry(version, source_root, template_dir)
        _telemetry.success(f"existing {CUSTOM_STANDARD} verified at {source_root}")
        return source_root, template_dir

    validate_source_schema(source_database)
    source_hash = _sha256(source_database)
    release_name = f"solidworks-data-{source_hash[:12]}-ba6-v{MIGRATION_VERSION}"
    final_toolbox = shared_root / "toolbox" / release_name
    manifest = ProvisionManifest(
        migration_version=MIGRATION_VERSION,
        source_database_sha256=source_hash,
        solidworks_registry_version=version,
        standard=CUSTOM_STANDARD,
        designation=BA6.designation,
        major_diameter_mm=BA6.major_diameter_mm,
        pitch_mm=BA6.pitch_mm,
        core_diameter_mm=BA6.core_diameter_mm,
        included_angle_deg=BA6.angle_deg,
    )
    _telemetry.info(
        f"provision plan: source={source_root}; toolbox={final_toolbox}; "
        f"templates={template_dir}"
    )
    if what_if:
        return final_toolbox, template_dir

    with _provision_lock(shared_root):
        if not final_toolbox.exists():
            staging_parent = shared_root / "toolbox"
            staging_parent.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(prefix=f".{release_name}-", dir=staging_parent)
            )
            try:
                shutil.copytree(source_root, staging, dirs_exist_ok=True)
                migrate_database(staging / DATABASE_RELATIVE)
                (staging / "harmonic-analyzer-standard.json").write_text(
                    json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                _publish_staging(staging, final_toolbox)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
        verify_database(final_toolbox / DATABASE_RELATIVE)
        _copy_templates(template_dir)
        if configure:
            configure_registry(version, final_toolbox, template_dir)

    _telemetry.success(f"provisioned {CUSTOM_STANDARD} at {final_toolbox}")
    _telemetry.success(f"provisioned drawing standards at {template_dir}")
    return final_toolbox, template_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-toolbox-root", type=Path)
    parser.add_argument("--shared-root", type=Path, default=DEFAULT_SHARED_ROOT)
    parser.add_argument("--no-configure", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--what-if", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    version, discovered_source = _registry_context()
    source = (args.source_toolbox_root or discovered_source).resolve()
    shared = args.shared_root.resolve()
    if args.check:
        if _read_provision_manifest(source) is not None:
            final = source
        else:
            source_database = source / DATABASE_RELATIVE
            source_hash = _sha256(source_database)
            final = shared / "toolbox" / (
                f"solidworks-data-{source_hash[:12]}-ba6-v{MIGRATION_VERSION}"
            )
        verify_database(final / DATABASE_RELATIVE)
        for template in (ASME_B_DRWDOT.name, ASME_B_SLDDRT.name):
            path = shared / "templates" / template
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"provisioned drawing standard is missing: {path}")
        _telemetry.success(f"seat standards verified at {shared}")
        return 0
    if _solidworks_running() and not args.what_if:
        raise RuntimeError("close SolidWorks before provisioning its Toolbox database")
    if not args.no_configure and not args.what_if and not _is_administrator():
        raise PermissionError(
            "run the provisioning wrapper from an elevated PowerShell session to "
            "configure the machine-wide SolidWorks Toolbox Data Location; use "
            "--no-configure only for a staged-clone validation"
        )
    provision(
        version=version,
        source_root=source,
        shared_root=shared,
        configure=not args.no_configure,
        what_if=args.what_if,
    )
    return 0


if __name__ == "__main__":
    _telemetry.set_service("solidworks-seat-provision")
    raise SystemExit(main())
