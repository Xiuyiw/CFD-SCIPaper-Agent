"""Optional local stdio MCP transport over the same task functions as Python/CLI.

The SDK is intentionally imported only when creating a server. Normal imports,
CLI use and scientific workflows therefore do not require the MCP extra.
"""

from __future__ import annotations

from importlib import import_module


def create_server():
    """Create an SDK 1.x server without starting a transport or a model provider."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as error:
        if error.name != "mcp":
            raise
        raise RuntimeError(
            'Optional MCP support is not installed. Install "cfd-paper-agent[mcp]" '
            '(SDK requirement: "mcp>=1.28,<2").'
        ) from error

    from cfdpaper import host_tools

    server = FastMCP(
        "CFD-Paper-Agent",
        log_level="WARNING",
        instructions=(
            "Use explicit workspace paths and existing scientific materials. "
            "Tools provide computed evidence, physical definitions and artifact paths; "
            "the host/author makes scientific judgments. Read located full sources "
            "when needed. Never treat successful export as scientific or visual validation."
        ),
    )
    for function in (
        host_tools.inspect_materials,
        host_tools.prepare_analysis_task,
        host_tools.run_analysis_task,
        host_tools.research_task,
        host_tools.writing_context,
        host_tools.manuscript_task,
        host_tools.author_task,
        host_tools.workbench_task,
    ):
        server.tool()(function)
    return server


def serve() -> None:
    """Run only the local stdio transport; no HTTP listener or LLM network calls."""
    server = create_server()
    # Load the native numerical library before stdio starts its stdin reader.
    # Windows OpenBLAS initialization can otherwise block during the first tool
    # import (numpy/numpy#24290; modelcontextprotocol/python-sdk#2832).
    import_module("numpy")
    server.run(transport="stdio")


def main() -> None:
    """Console/module entry point for the optional local MCP server."""
    serve()


if __name__ == "__main__":
    main()
