"""Recipe-local stock declarations, separate from shared build machinery for cache scope."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


type RecipeAuthor = Callable[..., Awaitable[None]]


@dataclass(frozen=True, slots=True)
class StockRecipeDeclaration:
    """Static import metadata for one verified diagnostic recipe.

    ``threaded`` declares that the recipe cuts a modeled helical thread named
    ``THREAD_FEATURE``; the stock build requires the feature to match, so a
    renamed groove cannot silently save a part without its simplified views.
    """

    sku: str
    module: str
    callable_name: str
    threaded: bool


# Metadata lives beside each recipe: production builders statically import the one
# recipe they use and pass its callable in StockComponent. Importing recipes here
# would make every stock fastener depend on every diagnostic geometry module.
def stock_recipe(sku: str, *, threaded: bool) -> Callable[[RecipeAuthor], RecipeAuthor]:
    """Declare a SKU without wrapping its author or introducing a recipe registry."""
    declaration = StockRecipeDeclaration(
        sku, f"diagnostics.diag_build_{sku}", f"build_{sku}", threaded
    )

    def declare(author: RecipeAuthor) -> RecipeAuthor:
        _validate_author(sku, author, declaration)
        author.__stock_recipe__ = declaration
        return author

    return declare


def _validate_author(
    sku: str, author: RecipeAuthor, declaration: StockRecipeDeclaration
) -> None:
    if not callable(author):
        raise TypeError(f"stock fastener SKU {sku!r} recipe author is not callable")
    if sku != declaration.sku:
        raise ValueError(
            f"stock fastener SKU {sku!r} requires its own recipe, got "
            f"SKU {declaration.sku!r}"
        )
    if getattr(author, "__name__", None) != declaration.callable_name:
        raise ValueError(
            f"stock fastener SKU {sku!r} requires recipe "
            f"{declaration.callable_name!r}, got "
            f"{getattr(author, '__name__', type(author).__name__)!r}"
        )
    # A diagnostic can also be executed directly as __main__. functools.wraps
    # preserves both these author attributes and the declaration on stock rework.
    if getattr(author, "__module__", None) not in (declaration.module, "__main__"):
        raise ValueError(
            f"stock fastener SKU {sku!r} requires recipe module "
            f"{declaration.module!r}, got {getattr(author, '__module__', None)!r}"
        )


def recipe_declaration(sku: str, author: RecipeAuthor) -> StockRecipeDeclaration:
    """Read and validate the declaration carried by the statically imported author."""
    if not callable(author):
        raise TypeError(f"stock fastener SKU {sku!r} recipe author is not callable")
    declaration = getattr(author, "__stock_recipe__", None)
    if not isinstance(declaration, StockRecipeDeclaration):
        raise KeyError(f"unknown stock fastener SKU {sku!r}")
    _validate_author(sku, author, declaration)
    return declaration
