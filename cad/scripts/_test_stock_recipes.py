"""Test-only recipe discovery; production keeps recipe-local static dependencies."""

from __future__ import annotations

import importlib
import re
from functools import cache
from pathlib import Path

from _stock_recipe import StockRecipeDeclaration, recipe_declaration


@cache
def discovered_recipes() -> dict[str, StockRecipeDeclaration]:
    """Collect local declarations without maintaining a second SKU table in tests."""
    recipes: dict[str, StockRecipeDeclaration] = {}
    diagnostics = Path(__file__).resolve().parent / "diagnostics"
    for path in sorted(diagnostics.glob("diag_build_*.py")):
        identifier = path.stem.removeprefix("diag_build_")
        if not re.fullmatch(r"[0-9A-Z_]+", identifier):
            continue
        module = importlib.import_module(f"diagnostics.{path.stem}")
        author = getattr(module, f"build_{identifier}", None)
        declaration = getattr(author, "__stock_recipe__", None)
        if declaration is None:
            continue
        declaration = recipe_declaration(declaration.sku, author)
        if declaration.sku in recipes:
            raise ValueError(
                f"duplicate stock recipe declaration for {declaration.sku!r}"
            )
        recipes[declaration.sku] = declaration
    if not recipes:
        raise ValueError("no recipe-local stock declarations discovered")
    return recipes
