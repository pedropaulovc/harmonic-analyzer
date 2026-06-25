"""Import shim for archived diagnostics.

These probe_/diag_/poc_/fix_ scripts were moved out of ``cad/scripts/`` into
``cad/scripts/diagnostics/`` to declutter the top-level build directory. They
still do ``from _common import ...``, which resolves to *this* file because a
script's own directory is first on ``sys.path``. Re-export the real module that
lives one directory up so the archived scripts keep running unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location("_common_impl", _SCRIPTS / "_common.py")
assert _spec is not None and _spec.loader is not None, f"could not locate _common.py under {_SCRIPTS}"
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
