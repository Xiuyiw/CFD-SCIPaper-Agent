from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from cfdpaper.storage import ProjectStore
from cfdpaper.topic_generation.canonical import canonical_json_bytes, canonical_sha256
from cfdpaper.topic_generation.models import make_qoi_definition_assessment
from cfdpaper.topic_generation.snapshot import (
    COMPONENT_NAMES,
    CaseNumericalAssessmentInput,
    NamedScalar,
    ScientificAssessmentSet,
    ScientificRecordSnapshot,
    build_scientific_snapshot,
    load_scientific_snapshot,
)
from tests.topic_generation.factories import populated_scientific_store


def _build_from_store(store: ProjectStore, **changes: object):
    inputs = {
        "project_id": store.status().project_id,
        "cases": store.list_cases(),
        "boundaries": store.list_boundaries(),
        "meshes": store.list_meshes(),
        "fields": store.list_fields(),
        "qois": store.list_qois(),
        "qoi_definition_assessments": store.list_qoi_definition_assessments(),
        "evidence": store.list_evidence(),
        "claims": store.list_claims(),
        "assessments": store.load_scientific_assessment_set(),
    }
    inputs.update(changes)
    return build_scientific_snapshot(**inputs)


def _rehash_component(snapshot, name: str, records: tuple[object, ...]) -> dict[str, object]:
    payload = snapshot.model_dump(mode="python")
    payload[name] = records
    components = list(payload["component_hashes"])
    index = COMPONENT_NAMES.index(name)
    components[index] = {
        **components[index],
        "sha256": canonical_sha256(records, domain=b"cfdpaper-scientific-component-v1"),
    }
    payload["component_hashes"] = tuple(components)
    payload["aggregate_sha256"] = canonical_sha256(
        {
            "project_id": payload["project_id"],
            "component_hashes": payload["component_hashes"],
        },
        domain=b"cfdpaper-scientific-snapshot-v1",
    )
    return payload


def test_assessment_set_saves_reopens_canonically(tmp_path: Path) -> None:
    populated_scientific_store(tmp_path)

    reopened = ProjectStore.open(tmp_path).load_scientific_assessment_set()

    assert isinstance(reopened, ScientificAssessmentSet)
    assert [case.case_id for case in reopened.cases] == ["case-a", "case-b"]
    assert reopened.cases[0].residuals == (NamedScalar(name="response", value=1.0e-6),)


def test_snapshot_is_permutation_invariant_for_every_record_component(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    original = _build_from_store(store)
    reversed_snapshot = _build_from_store(
        store,
        cases=list(reversed(store.list_cases())),
        boundaries=tuple(reversed(store.list_boundaries())),
        meshes=list(reversed(store.list_meshes())),
        fields=tuple(reversed(store.list_fields())),
        qois=list(reversed(store.list_qois())),
        qoi_definition_assessments=tuple(reversed(store.list_qoi_definition_assessments())),
        evidence=list(reversed(store.list_evidence())),
        claims=tuple(reversed(store.list_claims())),
        assessments=ScientificAssessmentSet(
            cases=tuple(reversed(store.load_scientific_assessment_set().cases))
        ),
    )

    assert reversed_snapshot.aggregate_sha256 == original.aggregate_sha256
    assert reversed_snapshot == original
    assert load_scientific_snapshot(ProjectStore.open(tmp_path)) == original


def test_free_text_never_substitutes_for_missing_structured_qoi_definition(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path, save_qoi_definition=False)

    snapshot = load_scientific_snapshot(store)

    assert snapshot.qoi_definition_assessments == ()
    assert "qoi-structured-definition-missing:qoi-a" in snapshot.gaps
    assert "qoi-structured-definition-missing:qoi-b" in snapshot.gaps


def test_exact_duplicates_collapse_but_unequal_duplicate_ids_fail_closed(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path)
    cases = store.list_cases()
    collapsed = _build_from_store(store, cases=[*cases, cases[0]])

    assert len(collapsed.cases) == 2
    unequal = cases[0].model_copy(update={"locator": "$.other"})
    with pytest.raises(ValueError, match="duplicate case ID"):
        _build_from_store(store, cases=[*cases, unequal])


def test_replacing_only_qoi_assessment_changes_only_definition_component(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path)
    before = load_scientific_snapshot(store)
    original = store.list_qoi_definition_assessments()[0]
    replacement = make_qoi_definition_assessment(
        **{
            **original.model_dump(mode="python", exclude={"schema_version", "definition_id"}),
            "formula": "response_out - response_reference",
        }
    )

    store.replace_qoi_definition_assessment(
        replacement, expected_definition_id=original.definition_id
    )
    after = load_scientific_snapshot(store)

    assert after.aggregate_sha256 != before.aggregate_sha256
    before_hashes = {item.name: item.sha256 for item in before.component_hashes}
    after_hashes = {item.name: item.sha256 for item in after.component_hashes}
    assert before_hashes["qoi-definitions"] != after_hashes["qoi-definitions"]
    assert {name for name in COMPONENT_NAMES if before_hashes[name] == after_hashes[name]} == set(
        COMPONENT_NAMES
    ) - {"qoi-definitions"}


def test_component_names_order_and_hash_domains_are_exact(tmp_path: Path) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))

    assert COMPONENT_NAMES == (
        "cases",
        "boundaries",
        "meshes",
        "fields",
        "qois",
        "qoi-definitions",
        "evidence",
        "claims",
        "assessments",
    )
    assert tuple(item.name for item in snapshot.component_hashes) == COMPONENT_NAMES
    component_values = {
        "cases": snapshot.cases,
        "boundaries": snapshot.boundaries,
        "meshes": snapshot.meshes,
        "fields": snapshot.fields,
        "qois": snapshot.qois,
        "qoi-definitions": snapshot.qoi_definition_assessments,
        "evidence": snapshot.evidence,
        "claims": snapshot.claims,
        "assessments": snapshot.assessments,
    }
    for name in COMPONENT_NAMES:
        assert snapshot.component_sha256(name) == canonical_sha256(
            component_values[name], domain=b"cfdpaper-scientific-component-v1"
        )
    assert snapshot.component_sha256("cases") != canonical_sha256(
        snapshot.cases, domain=b"cfdpaper-scientific-snapshot-v1"
    )
    assert snapshot.aggregate_sha256 == canonical_sha256(
        {
            "project_id": snapshot.project_id,
            "component_hashes": snapshot.component_hashes,
        },
        domain=b"cfdpaper-scientific-snapshot-v1",
    )


@pytest.mark.parametrize(
    "tampering",
    ["empty-components", "component-name", "component-hash", "aggregate", "content"],
)
def test_direct_snapshot_construction_rejects_inconsistent_hashes(
    tmp_path: Path,
    tampering: str,
) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    payload = snapshot.model_dump(mode="python")
    components = list(payload["component_hashes"])
    if tampering == "empty-components":
        payload["component_hashes"] = ()
    elif tampering == "component-name":
        components[0] = {**components[0], "name": "not-cases"}
        payload["component_hashes"] = tuple(components)
    elif tampering == "component-hash":
        components[0] = {**components[0], "sha256": "0" * 64}
        payload["component_hashes"] = tuple(components)
    elif tampering == "aggregate":
        payload["aggregate_sha256"] = "0" * 64
    else:
        qois = list(payload["qois"])
        qois[0] = {**qois[0], "value": qois[0]["value"] + 1.0}
        payload["qois"] = tuple(qois)

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**payload)


def test_direct_snapshot_construction_rejects_blank_project_id_with_matching_hash(
    tmp_path: Path,
) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    blank_project_id = "   "
    payload = snapshot.model_dump(mode="python")
    payload["project_id"] = blank_project_id
    payload["aggregate_sha256"] = canonical_sha256(
        {
            "project_id": blank_project_id,
            "component_hashes": payload["component_hashes"],
        },
        domain=b"cfdpaper-scientific-snapshot-v1",
    )

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**payload)


def test_snapshot_model_copy_rejects_blank_project_id_with_matching_hash(
    tmp_path: Path,
) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    blank_project_id = "   "
    aggregate = canonical_sha256(
        {
            "project_id": blank_project_id,
            "component_hashes": snapshot.component_hashes,
        },
        domain=b"cfdpaper-scientific-snapshot-v1",
    )

    with pytest.raises(ValidationError):
        snapshot.model_copy(
            update={
                "project_id": blank_project_id,
                "aggregate_sha256": aggregate,
            }
        )


def test_snapshot_model_copy_revalidates_content_updates(tmp_path: Path) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    changed_qois = (
        snapshot.qois[0].model_copy(update={"value": snapshot.qois[0].value + 1.0}),
        *snapshot.qois[1:],
    )

    assert snapshot.model_copy() == snapshot
    with pytest.raises(ValidationError):
        snapshot.model_copy(update={"qois": changed_qois})


def test_snapshot_rejects_forged_or_deleted_gaps(tmp_path: Path) -> None:
    complete_root = tmp_path / "complete"
    complete_root.mkdir()
    complete = load_scientific_snapshot(populated_scientific_store(complete_root))
    forged = ("forged-gap",)
    complete_payload = complete.model_dump(mode="python")
    complete_payload["gaps"] = forged

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**complete_payload)
    with pytest.raises(ValidationError):
        complete.model_copy(update={"gaps": forged})

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing = load_scientific_snapshot(
        populated_scientific_store(missing_root, save_qoi_definition=False)
    )
    assert missing.gaps
    deleted = ()
    missing_payload = missing.model_dump(mode="python")
    missing_payload["gaps"] = deleted

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**missing_payload)
    with pytest.raises(ValidationError):
        missing.model_copy(update={"gaps": deleted})


@pytest.mark.parametrize(
    ("component", "id_field"),
    [("cases", "case_id"), ("qois", "qoi_id"), ("evidence", "evidence_id")],
)
def test_snapshot_rejects_blank_nested_record_ids_even_with_rehashed_content(
    tmp_path: Path,
    component: str,
    id_field: str,
) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    records = list(getattr(snapshot, component))
    records[0] = records[0].model_copy(update={id_field: ""})
    payload = _rehash_component(snapshot, component, tuple(records))

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**payload)


@pytest.mark.parametrize("arrangement", ["reversed", "duplicate"])
def test_snapshot_rejects_noncanonical_record_order_or_duplicates(
    tmp_path: Path,
    arrangement: str,
) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))
    cases = snapshot.cases
    records = tuple(reversed(cases)) if arrangement == "reversed" else (*cases, cases[0])
    payload = _rehash_component(snapshot, "cases", records)

    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**payload)


def test_snapshot_deep_copy_rebuilds_private_immutable_mappings(tmp_path: Path) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))

    copied = snapshot.model_copy(deep=True)

    assert copied == snapshot
    assert copied is not snapshot
    assert copied.boundaries[0].values is not snapshot.boundaries[0].values
    assert copied.boundaries[0].units is not snapshot.boundaries[0].units
    assert copied.meshes[0].quality is not snapshot.meshes[0].quality
    with pytest.raises(TypeError):
        copied.boundaries[0].values["parameter"] = 99.0
    with pytest.raises(TypeError):
        copied.meshes[0].quality["quality_parameter"] = 0.0


@pytest.mark.parametrize(
    ("nonfinite_value", "expected_tag"),
    [
        (math.nan, "nonfinite:nan"),
        (math.inf, "nonfinite:positive-infinity"),
        (-math.inf, "nonfinite:negative-infinity"),
    ],
)
def test_nonfinite_invalid_qoi_is_preserved_as_canonical_gap(
    tmp_path: Path,
    nonfinite_value: float,
    expected_tag: str,
) -> None:
    store = populated_scientific_store(tmp_path)
    original_qois = store.list_qois()
    source = original_qois[0]
    invalid = source.model_copy(update={"status": "invalid", "value": nonfinite_value})

    left = _build_from_store(store, qois=[invalid, original_qois[1]])
    right = _build_from_store(store, qois=[original_qois[1], invalid])
    duplicate = _build_from_store(store, qois=[invalid, original_qois[1], invalid])
    retained = next(qoi for qoi in left.qois if qoi.qoi_id == invalid.qoi_id)

    assert retained.value == expected_tag
    assert retained.source_uri == source.source_uri
    assert retained.source_hash == source.source_hash
    assert retained.locator == source.locator
    assert retained.stale == source.stale
    assert f"qoi-value-nonfinite:{source.qoi_id}" in left.gaps
    assert left.gaps == right.gaps
    assert left.aggregate_sha256 == right.aggregate_sha256
    assert duplicate.aggregate_sha256 == left.aggregate_sha256
    assert canonical_json_bytes(left) == canonical_json_bytes(right)


def test_snapshot_defensively_freezes_nested_mappings_and_input_aliases(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    boundary = store.list_boundaries()[0]
    mesh = store.list_meshes()[0]
    snapshot = _build_from_store(store, boundaries=[boundary], meshes=[mesh])
    digest = snapshot.aggregate_sha256

    boundary.values["parameter"] = 999.0
    mesh.quality["quality_parameter"] = 0.0

    assert snapshot.boundaries[0].values["parameter"] == 1.0
    assert snapshot.meshes[0].quality["quality_parameter"] == pytest.approx(0.81)
    assert snapshot.aggregate_sha256 == digest
    with pytest.raises(TypeError):
        snapshot.boundaries[0].values["parameter"] = 2.0
    with pytest.raises(TypeError):
        snapshot.meshes[0].quality["quality_parameter"] = 0.5


def test_stale_invalid_and_missing_records_remain_visible_as_stable_gaps(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path)
    stale_case = store.list_cases()[0].model_copy(update={"stale": True})
    missing_qoi = store.list_qois()[0].model_copy(
        update={"qoi_id": "qoi-missing", "status": "missing", "value": None}
    )
    invalid_qoi = store.list_qois()[1].model_copy(
        update={"qoi_id": "qoi-invalid", "status": "invalid"}
    )

    left = _build_from_store(store, cases=[stale_case], qois=[missing_qoi, invalid_qoi])
    right = _build_from_store(store, cases=[stale_case], qois=[invalid_qoi, missing_qoi])

    assert [record.case_id for record in left.cases] == ["case-a"]
    assert [record.qoi_id for record in left.qois] == ["qoi-invalid", "qoi-missing"]
    assert left.gaps == right.gaps
    assert left.aggregate_sha256 == right.aggregate_sha256
    assert "source-record-stale:case:case-a" in left.gaps
    assert "qoi-status-invalid:qoi-invalid" in left.gaps
    assert "qoi-status-missing:qoi-missing" in left.gaps


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_nonfinite_scientific_numbers_are_rejected(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        NamedScalar(name="response", value=bad_value)
    with pytest.raises(ValidationError):
        CaseNumericalAssessmentInput(
            case_id="case-a",
            residuals=(),
            residual_targets=(),
            qoi_relative_span=None,
            conservation_inflow=bad_value,
            conservation_outflow=1.0,
            conservation_tolerance=0.01,
            independent_validation_evidence_ids=(),
            engineering_evidence_ids=(),
            sensitivity_evidence_ids=(),
        )


def test_named_scalar_rejects_numeric_strings() -> None:
    with pytest.raises(ValidationError):
        NamedScalar(name="response", value="1.25")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("qoi_relative_span", "0.01"),
        ("conservation_inflow", "10.0"),
        ("conservation_outflow", "9.9"),
        ("conservation_tolerance", "0.01"),
    ],
)
def test_assessment_case_rejects_numeric_strings(field: str, value: str) -> None:
    fields: dict[str, object] = {
        "case_id": "case-a",
        "residuals": (),
        "residual_targets": (),
        "qoi_relative_span": None,
        "conservation_inflow": 10.0,
        "conservation_outflow": 9.9,
        "conservation_tolerance": 0.01,
        "independent_validation_evidence_ids": (),
        "engineering_evidence_ids": (),
        "sensitivity_evidence_ids": (),
    }
    fields[field] = value

    with pytest.raises(ValidationError):
        CaseNumericalAssessmentInput(**fields)


def test_assessment_arrays_are_strict_sorted_and_unique() -> None:
    assessment = CaseNumericalAssessmentInput(
        case_id=" case-a ",
        residuals=[
            NamedScalar(name="z", value=2.0),
            NamedScalar(name="a", value=1.0),
        ],
        residual_targets=[],
        qoi_relative_span=None,
        conservation_inflow=1.0,
        conservation_outflow=1.0,
        conservation_tolerance=0.0,
        case_evidence_ids=[" evidence-case-z ", "evidence-case-a"],
        convergence_evidence_ids=[" evidence-convergence-z ", "evidence-convergence-a"],
        conservation_evidence_ids=[" evidence-conservation-z ", "evidence-conservation-a"],
        independent_validation_evidence_ids=[" evidence-z ", "evidence-a"],
        engineering_evidence_ids=[],
        sensitivity_evidence_ids=[],
    )

    assert assessment.case_id == "case-a"
    assert [item.name for item in assessment.residuals] == ["a", "z"]
    assert assessment.independent_validation_evidence_ids == (
        "evidence-a",
        "evidence-z",
    )
    assert assessment.case_evidence_ids == ("evidence-case-a", "evidence-case-z")
    assert assessment.convergence_evidence_ids == (
        "evidence-convergence-a",
        "evidence-convergence-z",
    )
    assert assessment.conservation_evidence_ids == (
        "evidence-conservation-a",
        "evidence-conservation-z",
    )
    with pytest.raises(ValidationError):
        CaseNumericalAssessmentInput(
            case_id="case-a",
            residuals={"a": 1.0},
            conservation_inflow=1.0,
            conservation_outflow=1.0,
            conservation_tolerance=0.0,
            independent_validation_evidence_ids=(),
            engineering_evidence_ids=(),
            sensitivity_evidence_ids=(),
        )
    with pytest.raises(ValidationError):
        CaseNumericalAssessmentInput(
            case_id="case-a",
            independent_validation_evidence_ids=[1],
            conservation_inflow=1.0,
            conservation_outflow=1.0,
            conservation_tolerance=0.0,
            residuals=(),
            residual_targets=(),
            qoi_relative_span=None,
            engineering_evidence_ids=(),
            sensitivity_evidence_ids=(),
        )
    with pytest.raises(ValidationError, match="duplicate NamedScalar name"):
        CaseNumericalAssessmentInput(
            case_id="case-a",
            residuals=[NamedScalar(name="a", value=1), NamedScalar(name="a", value=2)],
            conservation_inflow=1.0,
            conservation_outflow=1.0,
            conservation_tolerance=0.0,
            residual_targets=(),
            qoi_relative_span=None,
            independent_validation_evidence_ids=(),
            engineering_evidence_ids=(),
            sensitivity_evidence_ids=(),
        )


@pytest.mark.parametrize(
    ("field", "evidence_id"),
    (
        ("case_evidence_ids", "evidence-qoi-a"),
        ("convergence_evidence_ids", "evidence-conservation-a"),
        ("conservation_evidence_ids", "evidence-residual-a"),
    ),
)
def test_persisted_assessment_rejects_wrong_kind_for_required_scientific_evidence(
    tmp_path: Path, field: str, evidence_id: str
) -> None:
    store = populated_scientific_store(tmp_path)
    original = store.load_scientific_assessment_set()
    first = original.cases[0].model_copy(update={field: (evidence_id,)})
    replacement = ScientificAssessmentSet(cases=(first, *original.cases[1:]))

    with pytest.raises(
        RuntimeError,
        match="scientific assessment evidence kind or source mismatch",
    ):
        store.save_scientific_assessment_set(replacement)

    assert store.load_scientific_assessment_set() == original


def test_nested_poisoned_named_scalar_is_revalidated() -> None:
    poisoned = NamedScalar(name="response", value=1.0).model_copy(update={"value": math.nan})

    with pytest.raises(ValidationError):
        CaseNumericalAssessmentInput(
            case_id="case-a",
            residuals=(poisoned,),
            residual_targets=(),
            qoi_relative_span=None,
            conservation_inflow=1.0,
            conservation_outflow=1.0,
            conservation_tolerance=0.0,
            independent_validation_evidence_ids=(),
            engineering_evidence_ids=(),
            sensitivity_evidence_ids=(),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"case_id": "   "},
        {"conservation_inflow": math.inf},
        {"independent_validation_evidence_ids": ("evidence-a", "evidence-a")},
    ],
)
def test_nested_poisoned_assessment_case_is_revalidated(changes: dict[str, object]) -> None:
    valid = CaseNumericalAssessmentInput(
        case_id="case-a",
        residuals=(),
        residual_targets=(),
        qoi_relative_span=None,
        conservation_inflow=1.0,
        conservation_outflow=1.0,
        conservation_tolerance=0.0,
        independent_validation_evidence_ids=(),
        engineering_evidence_ids=(),
        sensitivity_evidence_ids=(),
    )
    poisoned = valid.model_copy(update=changes)

    with pytest.raises(ValidationError):
        ScientificAssessmentSet(cases=(poisoned,))


def test_empty_assessment_loader_default(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    with store.connect() as connection:
        connection.execute("DELETE FROM scientific_assessment_state")

    assert ProjectStore.open(tmp_path).load_scientific_assessment_set() == ScientificAssessmentSet()


def test_empty_assessment_state_becomes_stable_per_case_snapshot_gaps(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    with store.connect() as connection:
        connection.execute("DELETE FROM scientific_assessment_state")

    snapshot = load_scientific_snapshot(ProjectStore.open(tmp_path))

    assert snapshot.assessments == ScientificAssessmentSet()
    assert snapshot.gaps == (
        "case-numerical-assessment-missing:case-a",
        "case-numerical-assessment-missing:case-b",
    )


def test_partial_assessment_reports_only_missing_current_case_order_independently(
    tmp_path: Path,
) -> None:
    store = populated_scientific_store(tmp_path)
    case_a_assessment = store.load_scientific_assessment_set().cases[0]

    left = _build_from_store(
        store,
        cases=tuple(reversed(store.list_cases())),
        assessments=ScientificAssessmentSet(cases=(case_a_assessment,)),
    )
    right = _build_from_store(
        store,
        cases=store.list_cases(),
        assessments=ScientificAssessmentSet(cases=(case_a_assessment,)),
    )

    assert left.gaps == ("case-numerical-assessment-missing:case-b",)
    assert right.gaps == left.gaps
    assert right.aggregate_sha256 == left.aggregate_sha256


def test_complete_assessment_has_no_missing_case_gap(tmp_path: Path) -> None:
    snapshot = load_scientific_snapshot(populated_scientific_store(tmp_path))

    assert not any(gap.startswith("case-numerical-assessment-missing:") for gap in snapshot.gaps)


def test_stale_case_keeps_source_gap_without_missing_assessment_gap(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    stale_case = store.list_cases()[0].model_copy(update={"stale": True})
    case_a_assessment = store.load_scientific_assessment_set().cases[0]

    snapshot = _build_from_store(
        store,
        cases=(stale_case,),
        assessments=ScientificAssessmentSet(cases=(case_a_assessment,)),
    )

    assert "source-record-stale:case:case-a" in snapshot.gaps
    assert "case-numerical-assessment-missing:case-a" not in snapshot.gaps


def test_missing_assessment_gaps_cannot_be_deleted_or_forged(tmp_path: Path) -> None:
    store = populated_scientific_store(tmp_path)
    snapshot = _build_from_store(store, assessments=ScientificAssessmentSet())
    assert snapshot.gaps == (
        "case-numerical-assessment-missing:case-a",
        "case-numerical-assessment-missing:case-b",
    )

    payload = snapshot.model_dump(mode="python")
    payload["gaps"] = ()
    with pytest.raises(ValidationError):
        ScientificRecordSnapshot(**payload)
    with pytest.raises(ValidationError):
        snapshot.model_copy(update={"gaps": ("forged-gap",)})


@pytest.mark.parametrize(
    "failure",
    ["missing-case", "stale-case", "missing-evidence", "stale-evidence", "version-mismatch"],
)
def test_invalid_assessment_save_never_overwrites_current_row(tmp_path: Path, failure: str) -> None:
    store = populated_scientific_store(tmp_path)
    original = store.load_scientific_assessment_set()
    candidate = original.model_copy(deep=True)
    first = candidate.cases[0]
    if failure == "missing-case":
        first = first.model_copy(update={"case_id": "case-missing"})
    elif failure == "missing-evidence":
        first = first.model_copy(
            update={"independent_validation_evidence_ids": ("evidence-missing",)}
        )
    elif failure == "stale-case":
        with store.connect() as connection:
            connection.execute(
                "UPDATE cases SET metadata_json = "
                '\'{"locator": "$.parameter[0]", "stale": true}\' '
                "WHERE case_id = 'case-a'"
            )
    elif failure == "stale-evidence":
        with store.connect() as connection:
            connection.execute(
                "UPDATE evidence SET metadata_json = '{\"stale\": true}' "
                "WHERE evidence_id = 'evidence-qoi-a'"
            )
    else:
        with store.connect() as connection:
            connection.execute(
                "UPDATE evidence SET source_version_hash = ? WHERE evidence_id = 'evidence-qoi-a'",
                ("0" * 64,),
            )
    candidate = candidate.model_copy(update={"cases": (first, *candidate.cases[1:])})

    with pytest.raises(RuntimeError, match="missing|stale|version mismatch"):
        store.save_scientific_assessment_set(candidate)

    assert store.load_scientific_assessment_set() == original
