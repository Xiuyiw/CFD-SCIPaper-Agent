"""A host gets complete compact values without duplicated full upstream reports."""

from cfdpaper.host_tools import _report_context


def test_report_context_keeps_domain_denominator_and_located_full_evidence():
    full = {
        "cases": ["A"],
        "metrics": [
            {
                "evidence_id": "rise",
                "value": "20.0",
                "unit": "%",
                "raw_value": 0.2,
                "domain": "inlet area",
                "comparison_scope": "two located reports",
                "denominator": {"evidence_id": "base", "raw_value": 100, "unit": "Pa"},
                "reference_evidence_id": "base",
                "comparison_evidence_id": "current",
                "parent_support": [
                    {
                        "role": "reference",
                        "domain": "inlet area",
                        "evidence_id": "base",
                        "original_sources": [{"source": "sources/raw.json", "pointer": "/p"}],
                    }
                ],
                "supporting_results": [{"very_long_details": "x" * 10000}],
            }
        ],
    }
    result = _report_context(full)
    row = result["metrics"][0]
    assert row["value"] == "20.0" and row["domain"] == "inlet area"
    assert row["denominator"]["evidence_id"] == "base"
    assert row["details_pointer"] == "/metrics/0"
    assert row["parent_support"][0]["evidence_id"] == "base"
    assert "supporting_results" not in row and "original_sources" not in row["parent_support"][0]
    assert full["metrics"][0]["supporting_results"][0]["very_long_details"] == "x" * 10000
