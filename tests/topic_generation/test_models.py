from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

import pytest
from pydantic import BaseModel, ValidationError

from cfdpaper.publication.topics import TopicCandidate
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import (
    GeneratedCandidateEnvelope,
    QoIDefinitionAssessmentRecord,
    ScientificReference,
    SemanticFrame,
    make_qoi_definition_assessment,
)


def qoi_definition_fields() -> dict[str, object]:
    return {
        "qoi_id": " pressure-loss ",
        "provenance_kind": "adapter",
        "source_uri": " synthetic/results.csv ",
        "source_hash": "a" * 64,
        "source_locator": " row:case-1 ",
        "evidence_ids": [" evidence-b ", "evidence-a"],
        "name": " Total   pressure loss ",
        "unit": " Pa ",
        "formula": " p_total,in   -   p_total,out ",
        "spatial_scope": " inlet and outlet planes ",
        "reduction": " area-weighted mean ",
        "temporal_scope": " steady state ",
        "producer_version": " csv-adapter 1.0 ",
    }


def test_canonical_json_and_domain_separated_hashes_are_stable() -> None:
    class ExampleModel(BaseModel):
        value: int

    class ExampleEnum(str, Enum):
        VALUE = "value"

    @dataclass(frozen=True)
    class ExampleDataclass:
        label: str

    left = {
        "z": [ExampleEnum.VALUE, ExampleDataclass("sample")],
        "a": ExampleModel(value=2),
    }
    right = {
        "a": ExampleModel(value=2),
        "z": [ExampleEnum.VALUE, ExampleDataclass("sample")],
    }

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes({"β": "值", 1: "one"}) == '{"1":"one","β":"值"}'.encode()
    assert canonical_json_bytes({"values": {"beta", "alpha"}}) == (b'{"values":["alpha","beta"]}')
    assert canonical_json_bytes(frozenset({"beta", "alpha"})) == b'["alpha","beta"]'
    assert canonical_sha256(left, domain=b"topic-v1") == canonical_sha256(right, domain=b"topic-v1")
    assert canonical_sha256(left, domain=b"topic-v1") != canonical_sha256(right, domain=b"topic-v2")

    seed_script = """
from pydantic import BaseModel
from cfdpaper.publication.topics import TopicCandidate
from cfdpaper.topic_generation.canonical import canonical_json_bytes
from cfdpaper.topic_generation.models import GeneratedCandidateEnvelope

class Payload(BaseModel):
    values: set[str]

print(canonical_json_bytes(Payload(values={"gamma", "alpha", "beta"})).hex())
candidate = TopicCandidate(
    topic_id="seed-check",
    title="Seed check",
    research_question="Is direct candidate JSON deterministic?",
    required_evidence_kinds={"qoi", "boundary", "field", "mesh", "case", "parameter"},
)
envelope = GeneratedCandidateEnvelope(candidates=(candidate,))
print(envelope.candidates[0].model_dump_json())
"""
    seed_outputs = {
        subprocess.check_output(
            [sys.executable, "-c", seed_script],
            env={**os.environ, "PYTHONHASHSEED": seed},
            text=True,
        ).strip()
        for seed in ("1", "2", "17")
    }
    assert len(seed_outputs) == 1

    with pytest.raises(ValueError, match="mapping key collision"):
        canonical_json_bytes({1: "integer key", "1": "string key"})
    with pytest.raises(TypeError, match="mapping key"):
        canonical_json_bytes({object(): "unstable key"})
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json_bytes({"value": float("nan")})
    with pytest.raises(ValueError, match="non-empty"):
        canonical_sha256(left, domain=b"")
    with pytest.raises(ValueError, match="NUL"):
        canonical_sha256(left, domain=b"topic\0v1")
    with pytest.raises(TypeError, match="bytes"):
        canonical_sha256(left, domain="topic-v1")
    with pytest.raises(TypeError, match="unsupported canonical JSON type"):
        canonical_json_bytes(object())
    with pytest.raises(TypeError):
        canonical_sha256(left, b"topic-v1")


def test_canonical_json_matches_pydantic_temporal_leaf_semantics() -> None:
    class TemporalPayload(BaseModel):
        generated_at: datetime
        report_date: date
        sampling_time: time

    payload = TemporalPayload(
        generated_at=datetime(
            2026,
            8,
            30,
            12,
            34,
            56,
            789000,
            tzinfo=timezone(timedelta(hours=8)),
        ),
        report_date=date(2026, 8, 30),
        sampling_time=time(12, 34, 56, 789000, tzinfo=timezone(timedelta(hours=8))),
    )
    pydantic_json_values = payload.model_dump(mode="json", warnings="error")

    assert canonical_json_bytes(payload) == canonical_json_bytes(pydantic_json_values)
    assert canonical_json_bytes(payload.generated_at) == canonical_json_bytes(
        pydantic_json_values["generated_at"]
    )


def test_semantic_frame_normalizes_references_and_parameter_bindings() -> None:
    fields = {
        "claim_class": "association",
        "predicate_class": "matched-comparison",
        "relation": {
            "relation_class": "difference",
            "polarity": "difference-only",
            "comparison_direction": "variant-vs-reference",
            "quantifier": "pairwise",
        },
        "subject_references": [
            {"kind": "qoi", "id": "qoi-pressure"},
            {"kind": "case", "id": "case-reference"},
        ],
        "contrast_references": [{"kind": "case", "id": "case-variant"}],
        "parameter_bindings": [
            {
                "id": "swirl-number",
                "role": "controlled",
                "case_ids": ["case-variant", "case-reference"],
                "boundary_evidence_ids": ["boundary-b", "boundary-a"],
            },
            {
                "id": "fuel-rate",
                "role": "varied",
                "case_ids": ["case-reference", "case-variant"],
                "boundary_evidence_ids": ["boundary-a", "boundary-b"],
            },
        ],
        "evidence_references": [{"kind": "evidence", "id": "evidence-1"}],
    }

    frame = SemanticFrame.model_validate(fields)

    assert [(item.kind, item.id) for item in frame.subject_references] == [
        ("case", "case-reference"),
        ("qoi", "qoi-pressure"),
    ]
    assert [item.id for item in frame.parameter_bindings] == ["fuel-rate", "swirl-number"]
    assert frame.parameter_bindings[0].case_ids == ("case-reference", "case-variant")
    assert frame.parameter_bindings[0].boundary_evidence_ids == ("boundary-a", "boundary-b")

    duplicate_reference = {**fields, "subject_references": fields["subject_references"] * 2}
    with pytest.raises(ValidationError, match="duplicate scientific reference"):
        SemanticFrame.model_validate(duplicate_reference)


def test_semantic_identifiers_reject_blanks_and_non_strings() -> None:
    base = {
        "claim_class": "association",
        "predicate_class": "matched-comparison",
        "relation": {
            "relation_class": "difference",
            "polarity": "difference-only",
            "comparison_direction": "variant-vs-reference",
            "quantifier": "pairwise",
        },
        "subject_references": [{"kind": "qoi", "id": "qoi-pressure"}],
        "contrast_references": [{"kind": "case", "id": "case-reference"}],
        "parameter_bindings": [
            {
                "id": "fuel-rate",
                "role": "varied",
                "case_ids": ["case-reference", "case-variant"],
                "boundary_evidence_ids": ["boundary-a"],
            },
            {
                "id": "swirl-number",
                "role": "controlled",
                "case_ids": ["case-reference", "case-variant"],
                "boundary_evidence_ids": ["boundary-b"],
            },
        ],
        "evidence_references": [{"kind": "evidence", "id": "evidence-1"}],
    }

    for field_name, kind in (
        ("subject_references", "qoi"),
        ("contrast_references", "case"),
        ("evidence_references", "evidence"),
    ):
        for invalid_id in ("   ", 1, None):
            with pytest.raises(ValidationError):
                SemanticFrame.model_validate(
                    {**base, field_name: [{"kind": kind, "id": invalid_id}]}
                )

    for binding_field in ("id", "case_ids", "boundary_evidence_ids"):
        for invalid_id in ("   ", 1, None):
            invalid_binding = dict(base["parameter_bindings"][0])
            invalid_binding[binding_field] = invalid_id if binding_field == "id" else [invalid_id]
            with pytest.raises(ValidationError):
                SemanticFrame.model_validate({**base, "parameter_bindings": [invalid_binding]})


def test_generated_candidate_envelope_is_a_deeply_immutable_snapshot() -> None:
    candidate = TopicCandidate(
        topic_id="pressure-loss",
        title="Pressure-loss response",
        research_question="How does pressure loss respond across sampled cases?",
        supporting_evidence_ids=["evidence-b", "evidence-a"],
        required_evidence_kinds={"qoi", "boundary"},
    )
    envelope = GeneratedCandidateEnvelope(candidates=(candidate,))
    initial_digest = canonical_sha256(envelope, domain=b"candidate-envelope-v1")
    initial_serialized = envelope.model_dump(mode="json", warnings="error")

    candidate.title = "Changed input candidate"
    candidate.supporting_evidence_ids.append("evidence-input-tamper")
    candidate.required_evidence_kinds.add("input-tamper")
    try:
        envelope.candidates[0].title = "Changed nested candidate"
    except ValidationError:
        pass
    try:
        envelope.candidates[0].supporting_evidence_ids.append("nested-list-tamper")
    except (AttributeError, TypeError, ValidationError):
        pass
    try:
        envelope.candidates[0].required_evidence_kinds.add("nested-set-tamper")
    except (AttributeError, TypeError, ValidationError):
        pass

    assert canonical_sha256(envelope, domain=b"candidate-envelope-v1") == initial_digest
    assert envelope.model_dump(mode="json", warnings="error") == initial_serialized


def test_qoi_assessment_is_content_addressed_strict_and_frozen() -> None:
    record = make_qoi_definition_assessment(**qoi_definition_fields())
    reconstructed = QoIDefinitionAssessmentRecord.model_validate(record.model_dump(mode="json"))

    assert reconstructed == record
    assert len(record.definition_id) == 64

    incorrect_id = {**record.model_dump(mode="json"), "definition_id": "0" * 64}
    with pytest.raises(ValidationError, match="definition_id does not match canonical content"):
        QoIDefinitionAssessmentRecord.model_validate(incorrect_id)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        QoIDefinitionAssessmentRecord.model_validate(
            {**record.model_dump(mode="json"), "unexpected": "field"}
        )
    with pytest.raises(ValidationError, match="frozen"):
        record.name = "Modified name"


def test_scientific_reference_rejects_blank_id_and_unknown_kind() -> None:
    with pytest.raises(ValidationError, match="scientific reference ID must not be blank"):
        ScientificReference(kind="case", id="   ")
    with pytest.raises(ValidationError, match="Input should be"):
        ScientificReference(kind="unknown", id="case-1")
    for invalid_id in (1, None):
        with pytest.raises(ValidationError, match="string"):
            ScientificReference(kind="case", id=invalid_id)


def test_qoi_definition_normalizes_identity_fields_and_rejects_blanks() -> None:
    normalized = make_qoi_definition_assessment(**qoi_definition_fields())
    equivalent_fields = qoi_definition_fields()
    equivalent_fields.update(
        {
            "evidence_ids": ["evidence-a", "evidence-b"],
            "formula": "p_total,in - p_total,out",
        }
    )
    equivalent = make_qoi_definition_assessment(**equivalent_fields)

    assert normalized.definition_id == equivalent.definition_id
    assert normalized.evidence_ids == ("evidence-a", "evidence-b")
    assert normalized.formula == "p_total,in - p_total,out"

    text_fields = (
        "qoi_id",
        "source_uri",
        "source_locator",
        "name",
        "unit",
        "formula",
        "spatial_scope",
        "reduction",
        "temporal_scope",
        "producer_version",
    )
    for field_name in text_fields:
        blank_fields = qoi_definition_fields()
        blank_fields[field_name] = "  \t  "
        with pytest.raises(ValidationError, match="must not be blank"):
            make_qoi_definition_assessment(**blank_fields)

    for invalid_id in ("   ", 1, None):
        invalid_evidence_fields = qoi_definition_fields()
        invalid_evidence_fields["evidence_ids"] = [invalid_id]
        with pytest.raises(ValidationError):
            make_qoi_definition_assessment(**invalid_evidence_fields)
