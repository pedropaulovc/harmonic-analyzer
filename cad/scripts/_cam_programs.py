"""Locate CAM recipes and the NC programs they post.

Each part milled on the CNC mill has a recipe at ``cad/process/<stem>/cam.py``
beside its enrolled ``plan.toml``; the recipe file is its enrolment (no list
names the parts). ``cam_nc.py`` runs it in headless FreeCAD (``freecadcmd``,
FreeCAD's CAM workbench) and writes one G-code file per recipe program, their
estimated cycle times (``cycle_times.json``) and a ``manifest.json`` binding
them to their inputs, under ``cad/out/nc/<stem>/``. FreeCAD is part of the
build on the submitter: ``build`` and ``release`` run every enrolled part's
``cam:<stem>`` task there (no farm worker has FreeCAD), and a release ships the
files under ``nc/<stem>/``.

A family plan (``_process_plans.family_parts``) has **one** recipe, beside it,
which posts every program of the family once: the programs every part runs
and each part's own, into the one ``cad/out/nc/<family stem>/`` with one
``cycle_times.json`` and one ``manifest.json`` that binds both parts' feature
bundles. The family's parts have no recipe, task or ``nc/`` directory of their
own; their placeholder travelers name the family's programs.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import _process_plans
import _shop_equipment
from export_features import OUT as CAD_OUT, bundle_paths

PROCESS_ROOT = _process_plans.PROCESS_ROOT


def cam_stems(root: Path = PROCESS_ROOT) -> tuple[str, ...]:
    """The parts milled on the CNC mill: each ``<stem>`` under ``root`` with a
    ``cam.py``, sorted. Each one's programs are posted by every build and
    shipped by every release."""
    return tuple(sorted(path.parent.name for path in root.glob("*/cam.py")))


CAM_STEMS: tuple[str, ...] = cam_stems()
# A recipe posts its traveler's milled setups: a part with NC has a traveler.
if _untraveled := sorted(set(CAM_STEMS) - set(_process_plans.TRAVELER_STEMS)):
    raise ValueError(
        f"CAM recipes beside no enrolled (non-placeholder) plan: {_untraveled}"
    )
SCRIPTS_DIR = Path(__file__).resolve().parent
# Executed by freecadcmd, never imported on the host: an input of every cam task.
RUNTIME_PATH = SCRIPTS_DIR / "_freecad_cam_runtime.py"
# The shop inventory's CNC records, where cam_nc.verify's jaw-clearance floor
# lives: an input of every cam task (the inventory's other files are not).
CNC_EQUIPMENT_PATH = _shop_equipment.DIRECTORY / "cnc.toml"
# The runtime reads its job spec's path from this variable (its own SPEC_ENV).
SPEC_ENV = "HARMONIC_CAM_SPEC"
CYCLE_TIMES_NAME = "cycle_times.json"
MANIFEST_NAME = "manifest.json"


def recipe_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "cam.py"


def cam_parts(stem: str) -> tuple[str, ...]:
    """The registry parts a recipe posts for: its family plan's parts, else
    its own stem. The plan is the one beside the recipe (``PROCESS_ROOT``),
    the root ``CAM_STEMS`` was read from."""
    return _process_plans.part_stems(stem, PROCESS_ROOT)


def cam_inputs(stem: str, out: Path = CAD_OUT) -> dict[str, Path]:
    """Every file a posted set depends on, by the name ``manifest.json``
    records its SHA-256 under: the scoped feature bundle (``features``,
    ``step``; a family's, one pair per part, ``features/<part stem>`` and
    ``step/<part stem>``), the ``plan``, each shop file
    (``shop/<name>.toml``), the shop inventory's ``shop-equipment/cnc.toml``
    (``cam_nc.verify``'s jaw-clearance floor lives there; no other inventory
    file is an input, so an unrelated record edit leaves every posted set
    fresh), the ``recipe`` and the FreeCAD ``runtime``."""
    family = _process_plans.family_parts(stem, PROCESS_ROOT)
    bundles: dict[str, Path] = {}
    for part in family.values():
        bundles[f"features/{part}"], bundles[f"step/{part}"] = bundle_paths(part, out)
    if not family:
        bundles["features"], bundles["step"] = bundle_paths(stem, out)
    return {
        **bundles,
        "plan": _process_plans.plan_path(stem),
        **{f"shop/{path.name}": path for path in _process_plans.shop_files()},
        "shop-equipment/cnc.toml": CNC_EQUIPMENT_PATH,
        "recipe": recipe_path(stem),
        "runtime": RUNTIME_PATH,
    }


def load_recipe(stem: str) -> ModuleType:
    """Import the recipe's host side; its ``build`` touches FreeCAD only inside freecadcmd."""
    path = recipe_path(stem)
    spec = importlib.util.spec_from_file_location(f"cam_recipe_{stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load CAM recipe {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.STEM != stem:
        raise ValueError(f"{path}: STEM {module.STEM!r} is not {stem!r}")
    return module


def nc_dir(stem: str, out: Path = CAD_OUT) -> Path:
    return Path(out) / "nc" / stem


def program_names(stem: str) -> tuple[str, ...]:
    """The recipe's program names, read statically from its literal ``PROGRAMS``
    so a broken recipe fails its own ``cam:<stem>`` task, never task loading."""
    tree = ast.parse(recipe_path(stem).read_text(encoding="utf-8"))
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == "PROGRAMS":
            return tuple(name for name, _ops in ast.literal_eval(node.value))
    raise ValueError(f"{recipe_path(stem)} has no literal PROGRAMS")


def cam_outputs(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """Every file the cam task writes: each program's ``.nc``, the cycle times,
    then the manifest."""
    directory = nc_dir(stem, out)
    return (
        *(directory / f"{name}.nc" for name in program_names(stem)),
        directory / CYCLE_TIMES_NAME,
        directory / MANIFEST_NAME,
    )
