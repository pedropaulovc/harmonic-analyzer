"""SolidWorks MCP Server - Python Implementation with FastMCP and PydanticAI.

This is a comprehensive Python implementation of the SolidWorks MCP server, providing
88+ tools for SolidWorks automation with enhanced security, configurability, and modern
Python architectures.

Original TypeScript implementation rights and IP remain with the original author. This
Python implementation adds FastMCP integration, PydanticAI capabilities, and
comprehensive testing for local and remote deployment scenarios.

The package root imports nothing else: the server lives in
``solidworks_mcp.server`` and its configuration in ``solidworks_mcp.config``, so
importing the COM adapters does not load the server stack.

Author: Andrew Bartels (hobby mechanical engineer learning LLMs and MCP) License: MIT
"""

from .version import __version__

__all__ = ["__version__"]
