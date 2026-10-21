"""The optional transport accepts the same multi-source/derived/formula request."""

import asyncio
import json

import pytest


def test_report_mcp_accepts_nested_sources_and_returns_bound_percent_and_formula(tmp_path):
    pytest.importorskip("mcp")
    from mcp.shared.memory import create_connected_server_and_client_session

    from cfdpaper.mcp_server import create_server

    (tmp_path / "A.json").write_text('{"in":120,"out":0}', encoding="utf-8")
    (tmp_path / "reference.json").write_text('{"figure":100}', encoding="utf-8")
    (tmp_path / "method.md").write_text(
        "Numerical comparison with reference denominator.\n", encoding="utf-8"
    )

    async def check():
        async with create_connected_server_and_client_session(create_server()) as session:
            response = await session.call_tool(
                "report_task",
                {
                    "root": str(tmp_path),
                    "output": str(tmp_path / "prepared"),
                    "title": "Pressure comparison",
                    "question": "What does the percentage mean?",
                    "cases": [
                        {"id": "A", "source": "A.json", "sources": {"ref": "reference.json"}}
                    ],
                    "quantities": [
                        {
                            "id": "p",
                            "label": "Native difference",
                            "domain": "fixed supports",
                            "unit": "Pa",
                            "comparison": "/in",
                            "reference": "/out",
                        },
                        {
                            "id": "r",
                            "label": "Reference",
                            "domain": "fixed supports",
                            "unit": "Pa",
                            "source_key": "ref",
                            "pointer": {"A": "/figure"},
                            "table": False,
                        },
                    ],
                    "derived": [
                        {
                            "id": "excess",
                            "label": "Relative excess",
                            "reference": "r_A",
                            "comparison": "p_A",
                            "field": "relative_change",
                            "percentage": True,
                            "domain": "fixed supports",
                            "comparison_scope": "numerical contrast only",
                            "definition_source": "method.md:L1",
                        }
                    ],
                    "formulas": {
                        "ratio": {
                            "source": "method.md#definition",
                            "expression": {
                                "kind": "fraction",
                                "children": [
                                    {"kind": "symbol", "text": "p"},
                                    {"kind": "symbol", "text": "r"},
                                ],
                            },
                        }
                    },
                },
            )
            assert not response.isError, response.content
            result = response.structuredContent or json.loads(response.content[0].text)
            metric = next(m for m in result["context"]["metrics"] if m["evidence_id"] == "excess")
            assert metric["value"] == "20.000" and metric["unit"] == "%"
            assert metric["denominator"]["evidence_id"] == "r_A"
            assert metric["parent_support"][0]["domain"] == "fixed supports"
            assert "supporting_results" not in metric
            assert result["context"]["formulas"][0]["token"] == "{{math:ratio}}"

    asyncio.run(check())
