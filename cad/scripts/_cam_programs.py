"""Locate Fusion CAM recipes and the NC programs they post.

Each enrolled part has a recipe at ``cad/process/<stem>/cam.py`` beside its
``plan.toml``. ``fusion_cam.py`` runs it in a local Autodesk Fusion through the
Fusion MCP server and writes one G-code file per recipe program, plus a
``manifest.json`` binding them to their inputs, under ``cad/out/nc/<stem>/``.
Fusion is not part of the build: only an opt-in ``cam:<stem>`` task on a
machine running Fusion produces these files.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from export_features import OUT as CAD_OUT

CAM_STEMS: tuple[str, ...] = ("ch_rocker_arm_tl_oblique_base_bar",)
PROCESS_ROOT = Path(__file__).resolve().parents[1] / "process"
SCRIPTS_DIR = Path(__file__).resolve().parent
# Sent to Fusion as source text, never imported: an input of every cam task.
RUNTIME_PATH = SCRIPTS_DIR / "_fusion_cam_runtime.py"
MANIFEST_NAME = "manifest.json"


def recipe_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "cam.py"


def load_recipe(stem: str) -> ModuleType:
    """Import the recipe's host side; its ``build`` touches ``adsk`` only in Fusion."""
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


def cam_outputs(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """Every file the cam task writes: each program's ``.nc``, then the manifest."""
    directory = nc_dir(stem, out)
    programs = tuple(directory / f"{name}.nc" for name, _ops in load_recipe(stem).PROGRAMS)
    return (*programs, directory / MANIFEST_NAME)
