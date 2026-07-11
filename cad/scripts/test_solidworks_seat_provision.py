"""Offline contracts for shared SolidWorks drawing/Hole Wizard provisioning."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

import provision_solidworks_seat as provision
from _hole_wizard import BA6


def _fixture_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE Standards (
                Name TEXT, enabled INTEGER, Protected INTEGER, CategoryID TEXT,
                TypeID TEXT, DefaultUnits TEXT, TableNamePrefix TEXT,
                OrderID INTEGER, TypeConvertTable TEXT,
                HasStackComponents INTEGER, SmartFastenerComponentTables TEXT,
                HasHoles INTEGER, IsToolbox INTEGER, SWCONST_ENUM_VALUE INTEGER,
                ScrewClearancesExcludedTable TEXT, ScrewClearancesTable TEXT,
                Installed INTEGER, Key INTEGER PRIMARY KEY AUTOINCREMENT
            );
            INSERT INTO Standards VALUES (
                'BSI',1,1,'BSI_Categories','BSI_Types','MILLIMETER','BSI_',6,
                'SW_BSI',1,'BSI_TYPE_BS',1,1,2,'',
                'BSI_DATA_HW_ScrewClearances',1,1
            );
            CREATE TABLE BSI_Categories (
                Name TEXT, enabled INTEGER, Protected INTEGER, TypeID TEXT,
                OrderID INTEGER, HasStackComponents INTEGER, IsToolbox INTEGER,
                HasHoles INTEGER
            );
            INSERT INTO BSI_Categories VALUES
                ('Bolts and Screws',1,1,'BSI_TYPE_BS',0,0,1,1),
                ('Hole Wizard Holes',1,1,'BSI_TYPE_HOLES',9,0,0,1);
            CREATE TABLE BSI_Types (
                CategoryID TEXT, enabled INTEGER, Protected INTEGER, Name TEXT,
                ID TEXT, OrderID INTEGER, HasStackComponents INTEGER,
                HasHoles INTEGER, IsToolbox INTEGER
            );
            INSERT INTO BSI_Types VALUES
                ('BSI_TYPE_BS',1,1,'Hex Bolts','BSI_BS_HEX',0,0,1,0),
                ('BSI_TYPE_HOLES',1,1,'Straight Holes','BSI_HW_HOLES',0,0,1,0),
                ('BSI_TYPE_HOLES',1,1,'Tapped Holes','BSI_HW_TAPS',0,0,1,0);
            CREATE TABLE BSI_Type_Holes (
                ID TEXT, enabled INTEGER, Protected INTEGER, HasHoles INTEGER,
                ValidHoleTypes INTEGER, Name TEXT, Title TEXT,
                HoleDescriptionFormat TEXT, Filename TEXT, PartUnits TEXT,
                ConfigurationTable TEXT, DataTable TEXT, DataTableSortField TEXT,
                PartNumberID TEXT, OrderID INTEGER, StackComponent INTEGER,
                SWconst_Enum_Value INTEGER, DataTableUnits TEXT, AltFilename TEXT,
                key INTEGER PRIMARY KEY, GlobalLengthPartNums INTEGER
            );
            INSERT INTO BSI_Type_Holes VALUES
                ('BSI_HW_HOLES',1,1,1,4,'Tap Drills','Tap Drills',
                 'Tap Drill for %size Tap','','','', '+DATA_HW_TapDrills',
                 'VAL(DIAMETER)','',0,0,56,'','',1,0),
                ('BSI_HW_TAPS',1,1,1,8,'Bottoming Tapped Hole',
                 'Bottoming Tapped Hole','%size Tapped Hole','','','',
                 '+DATA_HW_BottomingTap','val(DIAMETER)','',0,0,57,'','',2,0),
                ('BSI_HW_TAPS',1,1,1,8,'Tapped hole','Tapped hole',
                 '%size Tapped Hole','','','', '+DATA_HW_TappedHole',
                 'val(DIAMETER)','',0,0,58,'','',3,0);
            CREATE TABLE BSI_DATA_HW_TappedHole (
                SIZE TEXT, Pitch TEXT, DIAMETER TEXT, enabled INTEGER,
                key INTEGER PRIMARY KEY, [Name To Match] TEXT
            );
            INSERT INTO BSI_DATA_HW_TappedHole VALUES
                ('M2.5x0.45','0.45','2.5',1,1,NULL);
            CREATE TABLE BSI_DATA_HW_BottomingTap (
                SIZE TEXT, Pitch TEXT, DIAMETER TEXT, enabled INTEGER,
                key INTEGER PRIMARY KEY, [Name To Match] TEXT
            );
            INSERT INTO BSI_DATA_HW_BottomingTap VALUES
                ('M2.5x0.45','0.45','2.5',1,1,NULL);
            CREATE TABLE BSI_DATA_HW_TapDrills (
                SIZE TEXT, DIAMETER TEXT, TAP_DRILL TEXT, enabled INTEGER,
                key INTEGER PRIMARY KEY, [Name To Match] TEXT
            );
            INSERT INTO BSI_DATA_HW_TapDrills VALUES
                ('M2.5x0.45','2.5','2.05',1,1,NULL);
            CREATE TABLE BSI_DATA_THRD (
                SIZE TEXT, THD_DIA TEXT, ADVANCE TEXT, THD_MINOR TEXT,
                THD_MINORI TEXT, TAP_DRILL TEXT, THD_DESC TEXT, TPU TEXT,
                full_size TEXT, series TEXT, enabled INTEGER,
                key INTEGER PRIMARY KEY
            );
            INSERT INTO BSI_DATA_THRD VALUES
                ('M2.5','2.5','0.45','1.993','2.013','2.05','M2.5x0.45',
                 '0.45','M2.5x0.45','',1,1);
            """
        )


def test_migration_copies_bsi_to_ba_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source.sldedb"
    clone = tmp_path / "clone.sldedb"
    _fixture_database(source)
    original = source.read_bytes()
    shutil.copy2(source, clone)

    provision.migrate_database(clone)
    provision.migrate_database(clone)
    provision.verify_database(clone)

    assert source.read_bytes() == original
    with sqlite3.connect(clone) as connection:
        categories = connection.execute(
            "SELECT Name FROM HA_BA_Categories WHERE enabled=1"
        ).fetchall()
        types = connection.execute(
            "SELECT Name FROM HA_BA_Types WHERE enabled=1"
        ).fetchall()
        assert categories == [("Hole Wizard Holes",)]
        assert types == [("Tapped Holes",)]
        core = connection.execute(
            "SELECT TAP_DRILL FROM HA_BA_DATA_HW_TapDrills"
        ).fetchone()[0]
        assert float(core) == pytest.approx(BA6.core_diameter_mm)


def test_migration_rejects_unknown_hole_wizard_schema(tmp_path: Path) -> None:
    database = tmp_path / "bad.sldedb"
    _fixture_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE BSI_DATA_HW_TappedHole ADD COLUMN Surprise TEXT")
    with pytest.raises(RuntimeError, match="unsupported Hole Wizard schema"):
        provision.validate_source_schema(database)


def test_provisioned_toolbox_is_a_stable_rerun_source(tmp_path: Path) -> None:
    source_root = tmp_path / "stock"
    database = source_root / provision.DATABASE_RELATIVE
    database.parent.mkdir(parents=True)
    _fixture_database(database)
    shared = tmp_path / "shared"

    first, _ = provision.provision(
        version="SOLIDWORKS 2026",
        source_root=source_root,
        shared_root=shared,
        configure=False,
        what_if=False,
    )
    second, _ = provision.provision(
        version="SOLIDWORKS 2026",
        source_root=first,
        shared_root=shared,
        configure=False,
        what_if=False,
    )

    assert second == first
    assert len(list((shared / "toolbox").iterdir())) == 1
    provision.verify_database(second / provision.DATABASE_RELATIVE)


def test_existing_provision_what_if_is_read_only(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "provisioned"
    database = source_root / provision.DATABASE_RELATIVE
    database.parent.mkdir(parents=True)
    _fixture_database(database)
    provision.migrate_database(database)
    (source_root / "harmonic-analyzer-standard.json").write_text(
        "{}\n", encoding="utf-8"
    )
    monkeypatch.setattr(provision, "_read_provision_manifest", lambda _root: object())

    def mutation_forbidden(*_args, **_kwargs):
        raise AssertionError("--what-if attempted to mutate the seat")

    monkeypatch.setattr(provision, "_copy_templates", mutation_forbidden)
    monkeypatch.setattr(provision, "configure_registry", mutation_forbidden)
    shared = tmp_path / "shared"
    toolbox, templates = provision.provision(
        version="SOLIDWORKS 2026",
        source_root=source_root,
        shared_root=shared,
        configure=True,
        what_if=True,
    )

    assert toolbox == source_root
    assert templates == shared / "templates"
    assert not shared.exists()

