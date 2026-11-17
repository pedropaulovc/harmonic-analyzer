"""SolidWorks adapter interfaces.

Only the base types and the pywin32 adapter are re-exported here. The optional
wrappers (factory, mock, circuit breaker, connection pool, router, VBA) are
imported from their own modules, so importing any adapter module does not load
the MCP server's database, cache and LLM dependencies.
"""

from .base import AdapterHealth, AdapterResult, SolidWorksAdapter
from .pywin32_adapter import PyWin32Adapter

__all__ = [
    "SolidWorksAdapter",
    "AdapterResult",
    "AdapterHealth",
    "PyWin32Adapter",
]
