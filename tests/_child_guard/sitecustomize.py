"""Load the SolidWorks guard into a Python child of a pytest session.

The root conftest puts this directory first on ``PYTHONPATH``; see
``harmonic_solidworks_guard``. Then run the ``sitecustomize`` this one shadows,
if any (a venv's or an agent's own guard). Another copy of this directory (a
nested pytest run from a different checkout or a test's private project) is
skipped: it would install the same guard again and chain back to this copy,
recursing until ``RecursionError`` with dozens of stacked import hooks.
"""

import os
import sys
from importlib.machinery import PathFinder

_HERE = os.path.normcase(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get("HARMONIC_TEST_FORBID_SOLIDWORKS"):
    import harmonic_solidworks_guard

    harmonic_solidworks_guard.install_child_guard()


def _is_a_child_guard(entry):
    directory = os.path.abspath(entry)
    return os.path.normcase(directory) == _HERE or os.path.isfile(
        os.path.join(directory, "harmonic_solidworks_guard.py")
    )


_shadowed = PathFinder.find_spec(
    "sitecustomize", [entry for entry in sys.path if not _is_a_child_guard(entry)]
)
if _shadowed is not None:
    import importlib.util

    _module = importlib.util.module_from_spec(_shadowed)
    _shadowed.loader.exec_module(_module)
