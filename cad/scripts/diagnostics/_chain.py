"""Import shim for archived diagnostics — see ``_common.py`` in this directory.

Re-exports the real ``cad/scripts/_chain.py`` one directory up so moved
diagnostics that do ``from _chain import ...`` keep resolving.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location("_chain_impl", _SCRIPTS / "_chain.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
