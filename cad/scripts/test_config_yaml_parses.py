"""Every YAML document under cad/config parses.

Several config files, dimensions.yaml above all, are prose records that no
part reads, so a row that breaks the YAML moves no cache key and no part test
notices.  #814's caf03f2b7 left an unquoted ``r7: +1.4`` in a plain-scalar
row and the whole of dimensions.yaml stopped parsing; only check:config, run
two commits later, caught it.  This gate makes the parse itself an offline
contract for every file the pipeline loads.
An unquoted colon can also parse successfully as a mapping inside a table
cell, so the dimensional record must render, not merely parse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from _buildgraph import all_config_files
from gen_dimensions import load_doc, render_markdown

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


def test_dimension_table_cells_remain_renderable_prose() -> None:
    doc = load_doc()
    table_rows = 0
    for section in doc["sections"]:
        for element in section["elements"]:
            if "table" not in element:
                continue
            for row in element["table"]["rows"]:
                if isinstance(row, dict):
                    assert isinstance(row["raw"], str)
                    continue
                table_rows += 1
                assert all(isinstance(cell, str) for cell in row), (
                    f"{section['heading']}: non-prose table cell in {row!r}"
                )
    assert table_rows > 0
    assert any(line.startswith("| ") for line in render_markdown(doc).splitlines())
