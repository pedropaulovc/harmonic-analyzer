"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import os
import tempfile


def pytest_configure(config):
    """Point the machine-wide build-graph syntax-facts store at a throwaway
    directory for this test session.

    ``_buildgraph`` persists parse results in ``%LOCALAPPDATA%`` so real graph
    loads skip re-parsing unchanged sources. A test may patch analyzer internals;
    were its results saved to the real store they would be served, under a
    genuine content key, to every later build on this machine. Tests therefore
    never read or write the real store. An explicit setting (``off`` or a path)
    is respected.
    """
    if "HARMONIC_BUILDGRAPH_CACHE" not in os.environ:
        os.environ["HARMONIC_BUILDGRAPH_CACHE"] = tempfile.mkdtemp(
            prefix="buildgraph-facts-"
        )
