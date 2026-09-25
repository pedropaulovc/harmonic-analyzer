"""Every YAML document under cad/config parses.

Several config files, dimensions.yaml above all, are prose records that no
part reads, so a row that breaks the YAML moves no cache key and no part test
notices.  #814's caf03f2b7 left an unquoted ``r7: +1.4`` in a plain-scalar
row and the whole of dimensions.yaml stopped parsing; only check:config, run
two commits later, caught it.  This gate makes the parse itself an offline
contract for every file the pipeline loads.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from _buildgraph import all_config_files

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CONFIG_YAMLS = sorted(
    path for pattern in ("*.yaml", "*.yml") for path in CONFIG_DIR.rglob(pattern)
)


def test_the_config_tree_is_not_empty() -> None:
    assert len(CONFIG_YAMLS) > 100


@pytest.mark.parametrize(
    "path", CONFIG_YAMLS, ids=lambda path: path.relative_to(CONFIG_DIR).as_posix()
)
def test_config_yaml_parses(path: Path) -> None:
    yaml.safe_load(path.read_text(encoding="utf-8"))


def test_every_config_yaml_is_a_declared_pipeline_input() -> None:
    """check:recipe's stamp keys on all_config_files(); a YAML outside that
    set could break without re-running this gate."""
    declared = {Path(path).resolve() for path in all_config_files()}
    assert set(CONFIG_YAMLS) <= declared
