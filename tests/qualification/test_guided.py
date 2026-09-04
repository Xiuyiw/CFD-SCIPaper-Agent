from __future__ import annotations

from collections.abc import Iterator

import pytest

from cfdpaper.qualification.guided import GuidedIntakeCancelled, build_guided_records
from cfdpaper.qualification.records import GuidedRecords


class ScriptedPrompt:
    def __init__(self, answers: list[str | None]) -> None:
        self._answers: Iterator[str | None] = iter(answers)
        self.keys: list[str] = []

    def ask(self, key: str, message: str) -> str | None:
        assert "schema" not in message.casefold()
        self.keys.append(key)
        return next(self._answers)


def _answers() -> list[str]:
    return [
        "P1",
        "mean_velocity",
        "0.25",
        "m/s",
        "inlet velocity",
        "0.20 m/s",
        "0.25 m/s",
        "intended-study-factor",
        "velocity is the study coordinate",
        "results.csv#boundary=P1",
        "flow model",
        "laminar",
        "laminar",
        "demonstrated-equivalent-or-immaterial",
        "same model in all cases",
        "results.csv#model=P1",
        "pressure-drop monitor span",
        "0.001",
        "1",
        "0.005",
        "<=",
        "restricting",
        "project convergence criterion",
        "results.csv#convergence=P1",
        "mass imbalance",
        "0.0001",
        "1",
        "0.001",
        "<=",
        "blocking",
        "project conservation criterion",
        "results.csv#conservation=P1",
        "demonstrated",
        "analytic pressure-drop comparison",
        "results.csv#verification=P1",
        "not-demonstrated",
        "no external experiment is supplied",
        "results.csv#validation=P1",
        "results.csv",
        "results.csv",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "1",
        "12",
    ]


def test_guided_intake_asks_scientific_questions_in_required_order() -> None:
    prompt = ScriptedPrompt(_answers())

    records = build_guided_records(prompt)

    assert isinstance(records, GuidedRecords)
    assert prompt.keys == [
        "case_id",
        "coordinate_name",
        "coordinate_value",
        "coordinate_unit",
        "boundary_name",
        "boundary_reference",
        "boundary_candidate",
        "boundary_role",
        "boundary_basis",
        "boundary_locator",
        "model_name",
        "model_reference",
        "model_candidate",
        "model_role",
        "model_basis",
        "model_locator",
        "convergence_metric",
        "convergence_observed",
        "convergence_unit",
        "convergence_threshold",
        "convergence_operator",
        "convergence_consequence",
        "convergence_basis",
        "convergence_locator",
        "conservation_metric",
        "conservation_observed",
        "conservation_unit",
        "conservation_threshold",
        "conservation_operator",
        "conservation_consequence",
        "conservation_basis",
        "conservation_locator",
        "verification_status",
        "verification_basis",
        "verification_locator",
        "validation_status",
        "validation_basis",
        "validation_locator",
        "source_uri",
        "source_locator",
        "source_sha256",
        "source_mtime_ns",
        "source_size_bytes",
    ]
    assert records.models[0].verification_status == "demonstrated"
    assert records.models[0].validation_status == "not-demonstrated"


@pytest.mark.parametrize("cancel_at", [0, 8, 42])
def test_guided_cancellation_or_incomplete_answer_returns_no_records(cancel_at: int) -> None:
    answers: list[str | None] = _answers()
    answers[cancel_at] = None if cancel_at != 8 else "   "

    with pytest.raises(GuidedIntakeCancelled):
        build_guided_records(ScriptedPrompt(answers))


def test_guided_result_round_trips_through_strict_loader(tmp_path) -> None:
    from cfdpaper.qualification.records import load_guided_records, write_guided_records

    records = build_guided_records(ScriptedPrompt(_answers()))
    path = tmp_path / "project-records.json"

    write_guided_records(path, records)

    assert load_guided_records(path) == records
