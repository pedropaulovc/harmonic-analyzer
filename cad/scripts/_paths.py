"""CAD paths, templates and unit constants.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from pathlib import Path

CAD_ROOT = Path(__file__).resolve().parents[1]


OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"


OUT_SLDASM = CAD_ROOT / "out" / "sldasm"


OUT_PNG = CAD_ROOT / "out" / "png"


OUT_STL = CAD_ROOT / "out" / "stl"


# Vendored input artefacts a build imports at run time (e.g. the nameplate
# engraving DXF). A build script that reads one of these must resolve it under
# this dir so dodo's data_deps_of picks it up as a file_dep + cache-key input.
REFERENCES_DIR = CAD_ROOT / "references"


# The repo-owned part template every part is created from (hand-made in
# SolidWorks; carries the doc properties the COM API cannot write -- the
# DimXpert block-tolerance decimals + angular value). run_build pins the
# seat's default part template to it before building, so NewPart inherits it
# on ANY seat; dodo folds it into every part's recipe/cache key (path
# duplicated there deliberately -- importing _buildgraph here would drag graph
# tooling into every part's dep closure).
PART_TEMPLATE = CAD_ROOT / "templates" / "harmonic-analyzer.PRTDOT"


IN = 25.4  # inch -> mm


# Roller-chain link component prefixes; contact between two of these is an
# articulating-mechanism contact, not an interference fault (check_no_interference).
_CHAIN_LINK_PREFIXES = ("vn-chain-inner-link", "vn-chain-outer-link")


DEFAULT_VIEWS = ("isometric",)
