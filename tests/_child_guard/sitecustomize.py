"""Load the SolidWorks guard into a Python child of a pytest session.

The root conftest puts this directory first on ``PYTHONPATH``; see
``harmonic_solidworks_guard``. Then run the ``sitecustomize`` this one shadows,
if any (a venv's or an agent's own guard).
"""

import os
import sys
from importlib.machinery import PathFinder

_HERE = os.path.normcase(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("HARMONIC_TEST_FORBID_SOLIDWORKS"):
    import harmonic_solidworks_guard

    harmonic_solidworks_guard.install_child_guard()

_shadowed = PathFinder.find_spec(
    "sitecustomize",
    [entry for entry in sys.path if os.path.normcase(os.path.abspath(entry)) != _HERE],
)
if _shadowed is not None:
    import importlib.util

    _module = importlib.util.module_from_spec(_shadowed)
    _shadowed.loader.exec_module(_module)
