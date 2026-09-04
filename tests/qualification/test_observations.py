from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cfdpaper.qualification.models import ExpectedMember
from cfdpaper.qualification.observations import (
    ObservationInputError,
    load_observations,
    validate_expected_membership,
)

HEADERS = (
    "case_id,coordinate_name,coordinate_value,coordinate_unit,variable,value,"
    "value_role,unit,scope,source_locator,aggregation,statistical_window,note\n"
)


def _write(path: Path, body: str, headers: str = HEADERS) -> bytes:
    content = (headers + body).encode("utf-8")
    path.write_bytes(content)
    return content


def _valid_rows() -> str:
    return (
        "P1,mean_velocity,0.25,m/s,pressure_drop,2.0,precomputed-qoi,Pa,"
        "inlet-to-outlet pressure difference,observations.csv#row=2,,,\n"
        "P2,mean_velocity,0.50,m/s,pressure_drop,8.0,precomputed-qoi,Pa,"
        "inlet-to-outlet pressure difference,observations.csv#row=3,,,\n"
        "P3,mean_velocity,0.75,m/s,pressure_drop,18.0,precomputed-qoi,Pa,"
        "inlet-to-outlet pressure difference,observations.csv#row=4,,,\n"
    )


@pytest.mark.parametrize(
    ("headers", "body", "issue_code"),
    [
        (
            HEADERS.replace("case_id,", ""),
            _valid_rows().replace("P1,", "", 1),
            "missing-required-column",
        ),
        (
            HEADERS.rstrip("\n") + ",mystery\n",
            _valid_rows().replace(",,,\n", ",,,x\n"),
            "unknown-column",
        ),
        (HEADERS, _valid_rows().replace(",Pa,", ",rpm,", 1), "unknown-unit"),
        (HEADERS, _valid_rows().replace("observations.csv#row=2", "", 1), "missing-source-locator"),
        (
            HEADERS,
            _valid_rows() + _valid_rows().splitlines(keepends=True)[0],
            "duplicate-observation",
        ),
        (
            HEADERS,
            _valid_rows().replace("precomputed-qoi,Pa", "declared-aggregate,Pa", 1),
            "missing-aggregation",
        ),
    ],
)
def test_csv_input_errors_have_stable_issue_codes(
    tmp_path: Path, headers: str, body: str, issue_code: str
) -> None:
    path = tmp_path / "observations.csv"
    before = _write(path, body, headers)

    with pytest.raises(ObservationInputError) as captured:
        load_observations(path)

    assert captured.value.issue_code == issue_code
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("body", "issue_code"),
    [
        (_valid_rows().splitlines()[0] + ",unexpected\n", "unexpected-row-column"),
        (
            "P1,mean_velocity,0.25,m/s,pressure_drop,2.0,precomputed-qoi,Pa,scope\n",
            "missing-required-value",
        ),
    ],
    ids=["extra-data-column", "short-required-data-row"],
)
def test_csv_rejects_rows_that_do_not_match_the_declared_shape(
    tmp_path: Path, body: str, issue_code: str
) -> None:
    path = tmp_path / "observations.csv"
    before = _write(path, body)

    with pytest.raises(ObservationInputError) as captured:
        load_observations(path)

    assert captured.value.issue_code == issue_code
    assert path.read_bytes() == before


def test_load_observations_preserves_input_bytes_and_row_order(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    before = _write(path, _valid_rows())

    table = load_observations(path)

    assert table.source_sha256 == hashlib.sha256(before).hexdigest()
    assert [row.case_id for row in table.rows] == ["P1", "P2", "P3"]
    assert table.guidance == ()
    assert path.read_bytes() == before


def test_expected_membership_returns_locked_scientific_order(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    rows = _valid_rows().splitlines(keepends=True)
    _write(path, "".join(reversed(rows)))
    table = load_observations(path)
    expected = tuple(
        ExpectedMember(
            case_id=case_id,
            coordinate_name="mean_velocity",
            coordinate_value=value,
            coordinate_unit="m/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet pressure difference",
        )
        for case_id, value in (("P1", 0.25), ("P2", 0.5), ("P3", 0.75))
    )

    ordered = validate_expected_membership(table.rows, expected)

    assert [row.case_id for row in ordered] == ["P1", "P2", "P3"]


def test_expected_membership_accepts_compatible_value_units(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    _write(path, _valid_rows().splitlines(keepends=True)[0])
    table = load_observations(path)
    expected = (
        ExpectedMember(
            case_id="P1",
            coordinate_name="mean_velocity",
            coordinate_value=0.25,
            coordinate_unit="m/s",
            variable="pressure_drop",
            unit="kPa",
            scope="inlet-to-outlet pressure difference",
        ),
    )

    assert validate_expected_membership(table.rows, expected) == table.rows


def test_expected_membership_rejects_missing_member(tmp_path: Path) -> None:
    path = tmp_path / "observations.csv"
    _write(path, "".join(_valid_rows().splitlines(keepends=True)[:2]))
    table = load_observations(path)
    expected = (
        ExpectedMember(
            case_id="P3",
            coordinate_name="mean_velocity",
            coordinate_value=0.75,
            coordinate_unit="m/s",
            variable="pressure_drop",
            unit="Pa",
            scope="inlet-to-outlet pressure difference",
        ),
    )

    with pytest.raises(ObservationInputError) as captured:
        validate_expected_membership(table.rows, expected)

    assert captured.value.issue_code == "missing-expected-member"
