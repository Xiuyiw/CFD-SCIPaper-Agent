"""Optional MCP transport must not become a base-package dependency."""

import asyncio
import builtins
import importlib
import json
from datetime import timedelta
from pathlib import Path

import pytest


def test_import_and_base_tools_do_not_import_mcp(monkeypatch):
    original = builtins.__import__

    def without_mcp(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ModuleNotFoundError("No module named 'mcp'", name="mcp")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_mcp)
    from cfdpaper import host_tools, mcp_server

    importlib.reload(host_tools)
    importlib.reload(mcp_server)
    with pytest.raises(RuntimeError, match=r"cfd-paper-agent\[mcp\]"):
        mcp_server.create_server()


def test_server_registers_only_named_task_functions_and_runs_stdio(monkeypatch):
    import sys
    from types import ModuleType

    from cfdpaper import host_tools, mcp_server

    calls = {}

    class FastMCP:
        def __init__(self, name, **kwargs):
            calls["name"] = name
            calls["log_level"] = kwargs["log_level"]
            self.functions = {}

        def tool(self, **kwargs):
            def register(function):
                self.functions[function.__name__] = function
                return function

            return register

        def run(self, **kwargs):
            calls["run"] = kwargs
            calls.setdefault("startup", []).append("stdio")

    module = ModuleType("mcp.server.fastmcp")
    module.FastMCP = FastMCP
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", module)
    server = mcp_server.create_server()
    expected = {
        "inspect_materials",
        "prepare_analysis_task",
        "run_analysis_task",
        "report_task",
        "research_task",
        "writing_context",
        "manuscript_task",
        "author_task",
        "workbench_task",
    }
    assert set(server.functions) == expected
    assert all(function is getattr(host_tools, name) for name, function in server.functions.items())
    monkeypatch.setattr(
        mcp_server, "import_module", lambda name: calls.setdefault("startup", []).append(name)
    )
    mcp_server.serve()
    assert calls["startup"] == ["numpy", "stdio"]
    assert calls["log_level"] == "WARNING"
    assert calls["run"] == {"transport": "stdio"}


def test_sdk_protocol_lists_and_calls_same_business_function(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession
    from mcp.shared.memory import create_connected_server_and_client_session

    from cfdpaper import host_tools, mcp_server

    (tmp_path / "definition.md").write_text("Declared domain and weighting.\n", encoding="utf-8")

    async def check():
        server = mcp_server.create_server()
        async with create_connected_server_and_client_session(server) as session:
            assert isinstance(session, ClientSession)
            tools = await session.list_tools()
            assert len(tools.tools) == 9
            response = await session.call_tool("inspect_materials", {"root": str(tmp_path)})
            assert not response.isError
            actual = response.structuredContent
            if actual is None:
                actual = json.loads(response.content[0].text)
            assert actual == host_tools.inspect_materials(tmp_path)

    asyncio.run(check())


def test_sdk_stdio_subprocess_preserves_analysis_values_sources_and_definitions(tmp_path):
    import sys

    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from cfdpaper import host_tools

    source = tmp_path / "source"
    source.mkdir()
    (source / "regions.csv").write_text(
        "case,region,area [m2],rate [W]\nA,inner,2,10\nA,outer,3,15\n",
        encoding="utf-8",
    )
    (source / "method.md").write_text(
        "Regions inner and outer are disjoint.\nRate is W; area is m2.\nFixed case.\n",
        encoding="utf-8",
    )
    package = tmp_path / "package"
    host_tools.prepare_analysis_task(source, package)
    proposal = json.loads((package / "proposal-example.json").read_text(encoding="utf-8"))
    calculation = proposal["candidates"][0]["calculations"][0]
    calculation.update(
        domain="two disjoint wall regions",
        comparison={"status": "supported", "scope": "fixed case"},
        missing_questions=[],
        expected_members=[["inner"], ["outer"]],
        expected_groups=["A"],
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    direct = host_tools.run_analysis_task(
        package, proposal_path, "regional-transport", tmp_path / "direct"
    )

    async def check():
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "cfdpaper.mcp_server"]
        )
        async with (
            stdio_client(parameters) as streams,
            ClientSession(*streams, read_timeout_seconds=timedelta(seconds=60)) as session,
        ):
            await session.initialize()
            response = await session.call_tool(
                "run_analysis_task",
                {
                    "package": str(package),
                    "proposal": str(proposal_path),
                    "candidate_id": "regional-transport",
                    "output": str(tmp_path / "stdio"),
                },
            )
            assert not response.isError
            result = response.structuredContent
            assert result is not None
            assert result["context"]["selected_analysis"] == direct["context"]["selected_analysis"]
            assert result["context"]["writing_input"] == direct["context"]["writing_input"]
            assert Path(result["artifacts"]["writing_package"]).is_dir()
            assert Path(result["artifacts"]["plot_script"]).is_file()
            for actual, expected in zip(
                result["context"]["metrics"], direct["context"]["metrics"], strict=True
            ):
                assert actual["resolved"] == expected["resolved"]
                assert (
                    actual["result_details"]["json_pointer"]
                    == expected["result_details"]["json_pointer"]
                )
            assert json.loads(
                Path(result["artifacts"]["table_results"]).read_text(encoding="utf-8")
            ) == json.loads(Path(direct["artifacts"]["table_results"]).read_text(encoding="utf-8"))

    asyncio.run(check())
