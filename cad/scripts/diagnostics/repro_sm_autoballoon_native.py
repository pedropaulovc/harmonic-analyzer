"""NEVER MERGE: bounded fresh-drawing AutoBalloon reproduction, not a fix.

Run only in an explicitly owned licensed seat: every attempt closes ALL documents.
The standalone native code has no project drawing/assembly helper dependencies.
A saved drawing is evidence only; every native call starts in a newly created one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from sys import exception as active_exception
from zipfile import ZIP_DEFLATED, ZipFile

CONFIG = "Default Simplified"
EXPLODE = "SM_EXPLODED Simplified"
SPRING = "sm-vn-counter-spring"
FIRST_CASES = ("seed", "spring", "spring-hook")
SECOND_CASES = ("spring-screw-neck", "spring-hook-nut-lever", "spring-supports")
CASE_PARTS = {
    "seed": None,
    "spring": (SPRING,),
    "spring-hook": (SPRING, "sm-vn-boss-hook"),
    "spring-screw-neck": (SPRING, "sm-gooseneck-spring-screw", "sm-gooseneck"),
    "spring-hook-nut-lever": (
        SPRING, "sm-vn-boss-hook", "sm-vn-boss-hook-jam-nut", "sm-summing-lever"
    ),
    "spring-supports": (
        SPRING, "sm-vn-boss-hook", "sm-vn-boss-hook-jam-nut", "sm-gooseneck",
        "sm-gooseneck-spring-screw",
    ),
}
OPTIONS = {
    "Layout": 1, "ReverseDirection": False, "IgnoreMultiple": True,
    "InsertMagneticLine": False, "LeaderAttachmentToFaces": False,
    "Style": 1, "Size": 2, "UpperTextContent": 1,
    "ItemNumberStart": 1, "ItemNumberIncrement": 1, "ItemOrder": 1,
}


class SmMinimalReproStop(RuntimeError):
    """Intentional non-success so the existing farm failure capture transports ZIP."""

    def __init__(self, report):
        self.report = report
        super().__init__(f"INTENTIONAL MINIMAL REPRO STOP: {report['stop_reason']}")


def _cast(obj, interface):
    from win32com.client import CastTo, gencache

    if obj is None:
        raise RuntimeError(f"null native {interface}")
    return CastTo(gencache.EnsureDispatch(obj), interface)


def _array(kind, values):
    import pythoncom
    from win32com.client import VARIANT

    code = {"double": pythoncom.VT_R8, "bool": pythoncom.VT_BOOL,
            "string": pythoncom.VT_BSTR}[kind]
    return VARIANT(pythoncom.VT_ARRAY | code, tuple(values))


def _constants(sw, names):
    import pythoncom
    from win32com.client import gencache

    executable = Path(sw.GetExecutablePath())
    root = executable if executable.is_dir() else executable.parent
    path = next(path for path in (root / "swconst.tlb", root / "SOLIDWORKS/swconst.tlb")
                if path.is_file())
    iid, lcid, _syskind, major, minor, _flags = pythoncom.LoadTypeLib(str(path)).GetLibAttr()
    constants = gencache.EnsureModule(iid, lcid, major, minor).constants
    return tuple(int(getattr(constants, name)) for name in names)


def _normal_constants(sw):
    return _constants(sw, (
        "swLineFontVisibleEdgesThickness", "swDetailingNoOptionSpecified", "swLW_NORMAL"
    ))


def _pixels(hwnd, path):
    import win32gui
    from PIL import ImageGrab

    image = ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd), all_screens=True)
    image.save(path)
    return str(path)


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _owned(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if not path.is_relative_to(root) or path == root:
        raise RuntimeError(f"native path escapes owned package: {path}")
    return path


def _close_all(sw):
    if not sw.CloseAllDocuments(True) or sw.GetFirstDocument() is not None:
        raise RuntimeError("owned seat did not close all documents")


def _open(sw, path, kind, *, options=1):
    # Early-bound retval followed by the two [in,out] LONGs; never omit 0,0.
    result = sw.OpenDoc6(str(Path(path).resolve()), kind, options, "", 0, 0)
    if type(result) is not tuple or len(result) != 3:
        raise RuntimeError(f"OpenDoc6 byref shape: {result!r}")
    model, errors, warnings = result
    if model is None or type(errors) is not int or type(warnings) is not int or errors:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors!r}, warnings={warnings!r}")
    return _cast(model, "IModelDoc2")


def _values(transform):
    values = tuple(float(value) for value in _cast(transform, "IMathTransform").ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("invalid native transform")
    return values


def _near(left, right):
    # IMathTransform's last three entries are documented UNUSED.
    return all(abs(left[i] - right[i]) <= 1e-8 for i in range(13))


def _fixture(sw, assembly):
    """Construction-only readback; collapse and return to Default before trials."""
    model = _open(sw, assembly, 2)
    asm = _cast(model, "IAssemblyDoc")
    if not model.ShowConfiguration2(CONFIG):
        raise RuntimeError("owned assembly lacks Default Simplified")
    cfg = _cast(model.GetConfigurationByName(CONFIG), "IConfiguration")
    components = [_cast(raw, "IComponent2") for raw in (asm.GetComponents(False) or ())]
    rows = {}
    for component in components:
        name = str(component.Name2)
        path = _owned(component.GetPathName(), Path(assembly).parent)
        rows[name] = {
            "path": str(path), "stem": path.stem.casefold(),
            "configuration": str(component.ReferencedConfiguration),
            "base_transform": _values(component.Transform2),
        }
    if len(rows) != len(components):
        raise RuntimeError("duplicate component names")
    springs = [component for component in components
               if rows[str(component.Name2)]["stem"] == SPRING]
    if len(springs) != 1 or str(springs[0].ReferencedConfiguration) != "Default":
        raise RuntimeError("fixture must retain the actual Default spring once")
    if springs[0].IsHidden(False):
        raise RuntimeError("retained actual spring is hidden")
    if tuple(asm.GetExplodedViewNames2(CONFIG) or ()) != (EXPLODE,):
        raise RuntimeError("retained native explode/configuration is missing")
    steps = []
    for index in range(int(cfg.GetNumberOfExplodeSteps())):
        step = _cast(cfg.GetExplodeStep(index), "IExplodeStep")
        steps.append({
            "name": str(step.Name), "distance": float(step.ExplodeDistance),
            "components": sorted(str(_cast(c, "IComponent2").Name2)
                                 for c in (step.GetComponents() or ())),
        })
    spring_name = str(springs[0].Name2)
    spring_steps = [step for step in steps if spring_name in step["components"]]
    if len(spring_steps) != 1 or abs(spring_steps[0]["distance"] - .055) > 1e-9:
        raise RuntimeError("spring's real +Y55mm explode step was not retained")
    try:
        if not asm.ShowExploded2(True, EXPLODE):
            raise RuntimeError("cannot display retained native explode")
        for component in components:
            rows[str(component.Name2)]["exploded_transform"] = _values(
                component.GetTotalTransform(True)
            )
        base = rows[spring_name]["base_transform"]
        exploded = rows[spring_name]["exploded_transform"]
        expected = list(base)
        expected[10] += .055
        if not _near(exploded, expected):
            raise RuntimeError("retained spring did not translate global+Y55mm only")
    finally:
        primary = active_exception()
        try:
            if not asm.ShowExploded2(False, EXPLODE) or not model.EditRebuild3():
                raise RuntimeError("fixture did not collapse after construction readback")
            if not model.ShowConfiguration2("Default"):
                raise RuntimeError("fixture did not return to Default")
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note(f"additional construction cleanup: {error}")
    return {"component_count": len(rows), "components": rows, "steps": steps,
            "spring_name": spring_name}


def _pack(sw, assembly, destination):
    """Pack native references into a new owned folder; no source SaveAs."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    _close_all(sw)
    silent, readonly = _constants(sw, ("swOpenDocOptions_Silent", "swOpenDocOptions_ReadOnly"))
    model = _open(sw, assembly, 2, options=silent | readonly)
    extension = _cast(model.Extension, "IModelDocExtension")
    pack = _cast(extension.GetPackAndGo(), "IPackAndGo")
    pack.IncludeDrawings = False
    pack.FlattenToSingleFolder = True
    names = pack.GetDocumentNames()
    if type(names) is not tuple or len(names) != 2 or names[0] is not True:
        raise RuntimeError(f"PackAndGo document names shape: {names!r}")
    if not pack.SetSaveToName2(True, str(destination)):
        raise RuntimeError("PackAndGo destination rejected")
    saved = pack.GetDocumentSaveToNames()
    if type(saved) is not tuple or len(saved) != 3 or saved[0] is not True:
        raise RuntimeError(f"PackAndGo output names shape: {saved!r}")
    paths = [str(_owned(path, destination)) for path in saved[1]]
    if len(paths) != len(names[1]) or len(set(paths)) != len(paths):
        raise RuntimeError("PackAndGo path count/collision")
    statuses = extension.SavePackAndGo(pack)
    if (type(statuses) not in (tuple, list) or len(statuses) != len(paths)
            or any(type(code) is not int or code != 0 for code in statuses)):
        raise RuntimeError(f"PackAndGo save statuses: {statuses!r}")
    if any(not Path(path).is_file() for path in paths):
        raise RuntimeError("PackAndGo omitted a native dependency")
    roots = [Path(path) for old, path in zip(names[1], paths, strict=True)
             if Path(old).resolve() == Path(assembly).resolve()]
    if len(roots) != 1:
        raise RuntimeError("PackAndGo did not identify the owned assembly")
    _close_all(sw)
    return roots[0]


def _prepare_case(sw, seed, case, out_dir, baseline):
    target = _pack(sw, seed, Path(out_dir) / case)
    keep = CASE_PARTS[case]
    if keep is not None:
        model = _open(sw, target, 2)
        asm = _cast(model, "IAssemblyDoc")
        model.ClearSelection2(True)
        removed = 0
        for raw in tuple(asm.GetComponents(False) or ()):
            component = _cast(raw, "IComponent2")
            path = _owned(component.GetPathName(), target.parent)
            if path.stem.casefold() not in keep:
                if not component.Select4(True, None, False):
                    raise RuntimeError("could not select owned component for deletion")
                removed += 1
        if removed and not _cast(model.Extension, "IModelDocExtension").DeleteSelection2(0):
            raise RuntimeError("native component deletion failed")
        model.ClearSelection2(True)
        # Save only the owned assembly, then reread actual reopened native objects.
        model.SaveAs3(str(target), 0, 1)
        _close_all(sw)
    fixture = _fixture(sw, target)
    expected = baseline["components"]
    if keep is not None:
        expected = {name: row for name, row in expected.items() if row["stem"] in keep}
    if set(fixture["components"]) != set(expected):
        raise RuntimeError("post-deletion component count/identities changed")
    for name, row in fixture["components"].items():
        old = expected[name]
        if (row["configuration"] != old["configuration"]
                or not _near(row["base_transform"], old["base_transform"])
                or not _near(row["exploded_transform"], old["exploded_transform"])):
            raise RuntimeError(f"post-deletion retained pose/configuration drift: {name}")
    _close_all(sw)
    return target, fixture


def _note(raw):
    note = _cast(raw, "INote")
    annotation = _cast(note.GetAnnotation(), "IAnnotation")
    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
    entities = tuple(annotation.GetAttachedEntities3() or ())
    owners = []
    for kind, entity in zip(kinds, entities, strict=True):
        if kind not in (1, 2):  # swSelEDGES, swSelFACES
            owners.append("")
        else:
            component = _cast(_cast(entity, "IEntity").GetComponent(), "IComponent2")
            owners.append(str(component.Name2))
    return {"text": str(note.GetBomBalloonText(True)), "raw_text": str(note.GetText()),
            "name": str(note.GetName()), "owners": owners, "attached": note.IsAttached(),
            "dangling": annotation.IsDangling(), "attachment_types": list(kinds)}


def _attempt(sw, assembly, drawing_template, bom_template, out_dir, index, baseline):
    _close_all(sw)  # Every attempt, including 2-4, reopens the native input.
    _open(sw, assembly, 2)
    draw = _cast(sw.NewDocument(str(drawing_template), 12, .4318, .2794), "IModelDoc2")
    ddoc = _cast(draw, "IDrawingDoc")
    if draw.GetPathName() != "" or len(ddoc.GetSheetNames()) != 1:
        raise RuntimeError("attempt needs one fresh unsaved template sheet")
    ddoc.EditSheet()
    sheet = _cast(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(1., 4., True, False):
        raise RuntimeError("sheet scale did not apply")
    view = _cast(ddoc.CreateDrawViewFromModelView3(
        str(assembly), "*Isometric", .112, .150, 0.
    ), "IView")
    view.ScaleRatio = _array("double", (1., 4.))
    view.SetDisplayMode4(False, 3, False, True, True)
    if view.GetDisplayMode2() not in (3, 7) or not view.GetDisplayEdgesInShadedMode():
        raise RuntimeError("authored Shaded-with-Edges did not read back")
    if view.ReferencedConfiguration != CONFIG:
        view.ReferencedConfiguration = CONFIG
        if not draw.EditRebuild3():
            raise RuntimeError("native configuration rebuild failed")
    if view.IsExploded() and not view.ShowExploded(False):
        raise RuntimeError("view did not collapse")
    if not view.ShowExploded(True) or not view.IsExploded() or not draw.EditRebuild3():
        raise RuntimeError("native view explode failed")
    if not view.SetViewPosition(
        _array("double", (.112, .14183459188114247)), False
    ) or not draw.EditRebuild3():
        raise RuntimeError("native view placement failed")
    pose = {"transform": _values(view.ModelToViewTransform), "position": list(view.Position),
            "scale": float(view.ScaleDecimal), "angle": float(view.Angle)}
    if (pose["scale"] != .25 or pose["angle"] != 0.
            or (baseline is not None and any(
                abs(pose["transform"][i] - baseline["transform"][i]) > 1e-8
                for i in (*range(9), 12)))):
        raise RuntimeError("attempt camera orientation/scale drift")
    pose["translation_delta"] = (
        [pose["transform"][i] - baseline["transform"][i] for i in (9, 10, 11)]
        if baseline is not None else [0., 0., 0.]
    )
    # Geometry reduction can change this offset. Record it; no compensation loop
    # and no claim that matching view.Position guarantees identical projection.
    name = str(view.GetName2())
    if not ddoc.ActivateView(name):
        raise RuntimeError("could not activate the actual named view")
    draw.ClearSelection2(True)
    extension = _cast(draw.Extension, "IModelDocExtension")
    if not extension.SelectByID2(name, "DRAWINGVIEW", 0., 0., 0., False, 0, None, 0):
        raise RuntimeError("could not select the actual named view")
    bom = _cast(view.InsertBomTable6(
        False, .226, .258, 1, 2, "", str(bom_template), False, 0, False, False, True
    ), "IBomTableAnnotation")
    feature = _cast(bom.BomFeature, "IBomFeature")
    if not feature.SetConfigurations(True, _array("bool", (True,)),
                                     _array("string", (CONFIG,))):
        raise RuntimeError("BOM configuration did not bind")
    feature.PartConfigurationGrouping, feature.DisplayAsOneItem = 2, True
    configurations = feature.GetConfigurations(False, None)
    if (type(configurations) is not tuple or len(configurations) != 2
            or tuple(configurations[0]) != (CONFIG,) or tuple(configurations[1]) != (True,)):
        raise RuntimeError(f"BOM configuration byref shape/state: {configurations!r}")
    if feature.PartConfigurationGrouping != 2 or feature.DisplayAsOneItem is not True:
        raise RuntimeError("BOM grouping did not bind")
    options = _cast(ddoc.CreateAutoBalloonOptions(), "IAutoBalloonOptions")
    preference, no_option, normal = _normal_constants(sw)
    original = extension.GetUserPreferenceInteger(preference, no_option)
    hwnd = _cast(sw.Frame(), "IFrame").GetHWndx64()
    row = {"index": index, "seat_pid": sw.GetProcessID(), "view_pose": pose,
           "native_calls": 0, "secondary_errors": []}
    try:
        if not extension.SetUserPreferenceInteger(preference, no_option, normal):
            raise RuntimeError("Normal line weight did not apply")
        if extension.GetUserPreferenceInteger(preference, no_option) != normal:
            raise RuntimeError("Normal line weight readback failed")
        for key, value in OPTIONS.items():
            setattr(options, key, value)
        draw.ClearSelection2(True)
        if not ddoc.ActivateView(name) or not extension.SelectByID2(
            name, "DRAWINGVIEW", 0., 0., 0., False, 0, None, 0
        ):
            raise RuntimeError("final view selection failed")
        row["native_calls"] = 1
        raw = ddoc.AutoBalloon5(options)
        row["raw_count"] = len(raw) if type(raw) in (tuple, list) else None
        row["raw_collection_type"] = type(raw).__name__
        try:
            row["post_call_png"] = _pixels(
                hwnd, Path(out_dir) / f"attempt-{index}-post-call.png"
            )
        except BaseException as error:
            row["secondary_errors"].append(f"passive post-call capture: {error}")
        if raw is not None and type(raw) not in (tuple, list):
            raise RuntimeError("AutoBalloon returned a non-array")
        row["raw_notes"] = [_note(note) for note in (raw or ())]
        row["raw_texts"] = [note["text"] for note in row["raw_notes"]]
        row["inventory"] = [_note(note) for note in (view.GetNotes() or ())
                            if _cast(note, "INote").IsBomBalloon()]
        # Target identity is discovered from actual rows AFTER native observations.
        table = _cast(bom, "ITableAnnotation")
        headers = [str(table.DisplayedText2(0, column, False))
                   for column in range(int(table.ColumnCount))]
        item_column = next(i for i, text in enumerate(headers)
                           if text.upper().startswith("ITEM NO"))
        row["bom_rows"] = []
        target_items = []
        target_names = set()
        for native_row in range(1, int(table.RowCount)):
            item = str(table.DisplayedText2(native_row, item_column, False)).strip()
            components = [_cast(c, "IComponent2") for c in
                          (bom.GetComponents2(native_row, CONFIG) or ())]
            identities = [{"name": str(c.Name2), "path": str(c.GetPathName()),
                           "configuration": str(c.ReferencedConfiguration)}
                          for c in components]
            row["bom_rows"].append({"row": native_row, "item": item,
                                    "components": identities})
            matches = [c for c in identities if Path(c["path"]).stem.casefold() == SPRING]
            if matches:
                if any(c["configuration"] != "Default" for c in matches):
                    raise RuntimeError("spring BOM component configuration changed")
                target_items.append(item)
                target_names.update(c["name"] for c in matches)
        if len(target_items) != 1:
            raise RuntimeError("actual spring does not map to exactly one BOM row")
        row["spring_item"] = target_items[0]
        notes = row["raw_notes"] + row["inventory"]
        if any("*" in note["text"] or "*" in note["raw_text"] for note in notes):
            raise RuntimeError("asterisk is invalid BOM linkage, not a creation omission")
        if any(not note["attached"] or note["dangling"] or not note["owners"]
               or any(not owner.strip() for owner in note["owners"]) for note in notes):
            raise RuntimeError("invalid/unreadable balloon ownership or attachment")
        raw_owned = any(target_names.intersection(note["owners"]) for note in row["raw_notes"])
        actual_owned = any(target_names.intersection(note["owners"]) for note in row["inventory"])
        raw_text_present = any(note["text"].strip() == row["spring_item"] for note in row["raw_notes"])
        actual_text_present = any(note["text"].strip() == row["spring_item"] for note in row["inventory"])
        if raw_owned != actual_owned or raw_owned != raw_text_present or actual_owned != actual_text_present:
            raise RuntimeError("raw/independent owned coverage or owned/text disagreement")
        row["spring_omitted"] = not raw_owned and not actual_owned
        row["view_outline"] = list(view.GetOutline())
        box = row["view_outline"]
        if len(box) != 4 or not (0 <= box[0] < box[2] <= .4318
                                and 0 <= box[1] < box[3] <= .2794):
            raise RuntimeError("native view is off sheet; not an accepted visible-spring repro")
        row["visible_spring_verified"] = False
        row["visual_review"] = "parent must confirm real spring visible in post-call pixels"
        print(json.dumps({"attempt": index, "raw_count": row["raw_count"],
                          "raw_texts": row["raw_texts"], "spring_item": row["spring_item"],
                          "spring_omitted": row["spring_omitted"]}), flush=True)
    except BaseException as error:
        row["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if (not extension.SetUserPreferenceInteger(preference, no_option, original)
                    or extension.GetUserPreferenceInteger(preference, no_option) != original):
                raise RuntimeError("Normal restoration readback failed")
        except BaseException as error:
            row["secondary_errors"].append(f"Normal restore: {error}")
        # Never save/export/reopen a drawing before the raw+independent observations.
        if "raw_notes" in row and "inventory" in row:
            target = Path(out_dir) / f"attempt-{index}.SLDDRW"
            try:
                row["drawing_save_return"] = draw.SaveAs3(str(target), 0, 3)
                if not target.is_file() or target.stat().st_size <= 0:
                    raise RuntimeError("post-observation drawing evidence not saved")
                row["drawing"] = str(target)
            except BaseException as error:
                row["secondary_errors"].append(f"post-observation save: {error}")
    return row


def _bundle(sw, source, drawing_template, bom_template, report, out_dir):
    delivery = _pack(sw, source, Path(out_dir) / "native-delivery")
    shutil.copy2(drawing_template, delivery.parent / Path(drawing_template).name)
    shutil.copy2(bom_template, delivery.parent / Path(bom_template).name)
    shutil.copy2(__file__, delivery.parent / "repro_sm_autoballoon_native.py")
    selected_case = next(case for case in report["cases"] if case["assembly"] == str(source))
    attempts = selected_case["attempts"]
    first = next((attempt for attempt in attempts if attempt["spring_omitted"]), attempts[0])
    evidence = [Path(first[key]) for key in ("drawing", "post_call_png")]
    for path in evidence:
        shutil.copy2(path, delivery.parent / path.name)
    command = (
        "python repro_sm_autoballoon_native.py "
        f'--assembly "{delivery.name}" '
        f'--drawing-template "{Path(drawing_template).name}" '
        f'--bom-template "{Path(bom_template).name}" '
        f'--out replay-1 --seat-pid {report["seat_pid"]}'
    )
    report["bundle"] = {
        "assembly": delivery.name, "drawing_template": Path(drawing_template).name,
        "bom_template": Path(bom_template).name,
        "evidence": [path.name for path in evidence], "one_call_command": command,
        "seat_warning": "replace PID with explicitly owned licensed seat; ALL its documents close",
        "replay": "one fresh native drawing/view/BOM/AutoBalloon call; no seed or reduction loop",
        "component_count": selected_case["fixture"]["component_count"],
        "purpose": (
            "native omission candidate; visual confirmation pending" if first["spring_omitted"]
            else "non-reproduction evidence; not a reproducer"
        ),
        "minimum_claim": "none: full SM is only a seed; no global minimum or necessity claim",
    }
    compact = {
        "diagnostic_only_never_merge": True, "bundle": report["bundle"],
        "stop_reason": report["stop_reason"], "cases": [],
    }
    for case in report.get("prior_cases", []) + report["cases"]:
        compact["cases"].append({
            "case": case["case"], "component_count": case["fixture"]["component_count"],
            "attempts": [
                {key: attempt[key] for key in (
                    "index", "native_calls", "raw_count", "raw_collection_type", "raw_texts",
                    "spring_item", "spring_omitted", "view_pose", "error", "secondary_errors"
                ) if key in attempt}
                | {"inventory_texts": [note["text"] for note in attempt.get("inventory", [])]}
                for attempt in case["attempts"]
            ],
        })
    (delivery.parent / "result.json").write_text(json.dumps(compact, indent=2), encoding="utf-8")
    files = [path for path in delivery.parent.rglob("*") if path.is_file()]
    if len(files) >= 250 or any(path.is_symlink() for path in files):
        raise RuntimeError("native bundle is not a small regular-file package")
    allowed = {".sldasm", ".sldprt", ".slddrw", ".drwdot", ".sldbomtbt", ".py", ".json", ".png"}
    if any(path.suffix.casefold() not in allowed for path in files):
        raise RuntimeError("unexpected payload type in native repro package")
    sizes = [path.stat().st_size for path in files]
    if any(size >= 256 * 1024 * 1024 for size in sizes) or sum(sizes) >= 1024**3:
        raise RuntimeError("native payload exceeds bounded capture file/total sizes")
    target = Path(out_dir) / "repro.zip"
    with ZipFile(target, "x", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(delivery.parent))
    if target.stat().st_size >= 256 * 1024 * 1024:
        raise RuntimeError("native ZIP exceeds farm per-file capture budget")
    return str(target)


def run(sw_app, *, assembly, drawing_template, bom_template, out_dir,
        cases=FIRST_CASES, seed_report=None):
    """One bounded leaf; no auto-retry, settings sweep, or standalone seed B."""
    assembly, drawing_template, bom_template, out_dir = map(
        Path, (assembly, drawing_template, bom_template, out_dir)
    )
    if tuple(cases) not in (FIRST_CASES, SECOND_CASES):
        raise ValueError("only the two predeclared leaf case lists are accepted")
    if any(not path.is_file() for path in (assembly, drawing_template, bom_template)):
        raise FileNotFoundError("native assembly and both actual templates are required")
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "result.json").exists() or (out_dir / "repro.zip").exists():
        raise RuntimeError("a new capture directory is required for each execution")
    source_hash = _sha(assembly)
    report = {"diagnostic_only_never_merge": True, "source_assembly": str(assembly),
              "source_sha256": source_hash, "seat_pid": sw_app.GetProcessID(),
              "requested_cases": list(cases), "cases": [], "native_calls": 0,
              "errors": [], "stop_reason": "incomplete", "next_action": "none"}
    prior = None
    if tuple(cases) == SECOND_CASES:
        if seed_report is None:
            raise ValueError("leaf2 requires the separately cleared completed leaf1 report")
        prior = json.loads(Path(seed_report).read_text(encoding="utf-8"))
        if (prior.get("source_sha256") != source_hash
                or tuple(prior.get("requested_cases", ())) != FIRST_CASES
                or prior.get("stop_reason") != "next leaf requires parent clearance"
                or prior.get("native_calls") != 12):
            raise RuntimeError("leaf2 does not continue the predeclared completed first leaf")
        report["prior_cases"] = prior["cases"]
    selected = None
    try:
        owned_seed = _pack(sw_app, assembly, out_dir / "owned-seed")
        baseline_fixture = _fixture(sw_app, owned_seed)
        if baseline_fixture["component_count"] != 16:
            raise RuntimeError("full SM seed must contain the actual16 component instances")
        seed_pose = prior["seed_pose"] if prior is not None else None
        seed_omissions = None
        for case in cases:
            target, fixture = _prepare_case(sw_app, owned_seed, case, out_dir, baseline_fixture)
            result = {"case": case, "assembly": str(target), "fixture": fixture,
                      "attempts": [], "spring_omissions": 0}
            report["cases"].append(result)
            for index in range(1, 5):
                if sw_app.GetProcessID() != report["seat_pid"]:
                    raise RuntimeError("held seat PID changed")
                attempt = _attempt(sw_app, target, drawing_template, bom_template,
                                   target.parent, index, seed_pose)
                result["attempts"].append(attempt)
                report["native_calls"] += attempt["native_calls"]
                if "error" in attempt or attempt["secondary_errors"]:
                    raise RuntimeError("native attempt/cleanup failed; retained primary/secondary evidence")
                if seed_pose is None:
                    seed_pose = attempt["view_pose"]
                result["spring_omissions"] += int(attempt["spring_omitted"])
            report["seed_pose"] = seed_pose
            if case == "seed":
                seed_omissions = result["spring_omissions"]
                selected = target
                continue  # Always exercise the user's actual one-component fixture.
            if case == "spring" and seed_omissions == 0 and result["spring_omissions"] == 0:
                report["stop_reason"] = (
                    "not reproduced in either fixture; unknown base rate/prestate; no repro delivered"
                )
                report["next_action"] = (
                    "stop; no hook case or retry; a native preceding-history seed needs new clearance"
                )
                selected = target
                break
            if case != "seed" and result["spring_omissions"]:
                report["stop_reason"] = "smallest tested native-omission subset; visual confirmation pending"
                report["next_action"] = (
                    "parent must verify real spring visible in post-call image before accepting repro; "
                    "no full-to-reduced causal, global-minimum or deterministic claim"
                )
                selected = target
                break
        else:
            report["stop_reason"] = (
                "next leaf requires parent clearance" if tuple(cases) == FIRST_CASES
                else "bounded reductions did not reproduce; no minimum-part repro delivered"
            )
            report["next_action"] = (
                "only the remaining three predeclared candidates may run in leaf2"
                if tuple(cases) == FIRST_CASES else "stop; no automatic third leaf"
            )
        report["total_native_calls_including_prior_leaf"] = (
            report["native_calls"] + (prior["native_calls"] if prior is not None else 0)
        )
        if report["total_native_calls_including_prior_leaf"] > 24:
            raise RuntimeError("predeclared native call cap exceeded")
        if selected is not None:
            report["native_zip"] = _bundle(
                sw_app, selected, drawing_template, bom_template, report, out_dir
            )
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
        report["stop_reason"] = "construction/native/packaging failure; not a passing fixture"
    finally:
        try:
            _close_all(sw_app)
        except BaseException as error:
            report["errors"].append(f"final close: {error}")
        report["cached_source_unchanged"] = _sha(assembly) == source_hash
        if not report["cached_source_unchanged"]:
            report["errors"].append("cached source changed during owned-copy diagnostic")
        (out_dir / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SmMinimalReproStop(report)


def _replay(sw, *, assembly, drawing_template, bom_template, out_dir):
    """Portable consumer: exactly one native attempt on ANY supplied real fixture."""
    assembly, drawing_template, bom_template = (
        Path(path).resolve() for path in (assembly, drawing_template, bom_template)
    )
    if not all(path.is_file() for path in (assembly, drawing_template, bom_template)):
        raise FileNotFoundError("replay requires the real native assembly and both templates")
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    report = {"diagnostic_only_never_merge": True, "source_assembly": str(assembly),
              "seat_pid": sw.GetProcessID(), "native_calls": 0, "attempts": [], "errors": [],
              "stop_reason": "single-call replay incomplete"}
    try:
        attempt = _attempt(sw, assembly, drawing_template, bom_template, out_dir, 1, None)
        report["attempts"].append(attempt)
        report["native_calls"] = attempt["native_calls"]
        report["stop_reason"] = (
            "single-call replay observation failure" if "error" in attempt or attempt["secondary_errors"]
            else "single-call native spring omission; verify post-call image"
            if attempt["spring_omitted"] else "single-call native spring present; not reproduced"
        )
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            _close_all(sw)
        except BaseException as error:
            report["errors"].append(f"final close: {error}")
        (out_dir / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    raise SmMinimalReproStop(report)


def _attach():
    from win32com.client import GetActiveObject

    return _cast(GetActiveObject("SldWorks.Application"), "ISldWorks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly", type=Path, required=True)
    parser.add_argument("--drawing-template", type=Path, required=True)
    parser.add_argument("--bom-template", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seat-pid", type=int, required=True,
                        help="explicitly owned licensed seat; ALL its documents will close")
    args = parser.parse_args()
    sw = _attach()
    if sw.GetProcessID() != args.seat_pid:
        raise RuntimeError("active SOLIDWORKS is not the explicitly owned seat")
    _replay(sw, assembly=args.assembly, drawing_template=args.drawing_template,
            bom_template=args.bom_template, out_dir=args.out)


if __name__ == "__main__":
    main()
