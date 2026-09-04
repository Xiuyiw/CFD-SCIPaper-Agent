from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "examples" / "steady_laminar_pipe"
AUTHOR = "Fixture Author"
TOPIC_ID = "steady-pipe-pressure-drop"


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_fixture(tmp_path: Path) -> Path:
    project = tmp_path / "steady_laminar_pipe"
    shutil.copytree(FIXTURE_ROOT, project, copy_function=shutil.copy2)
    return project


@pytest.fixture(scope="session")
def installed_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    environment = tmp_path_factory.mktemp("installed-cli")
    wheelhouse = environment / "wheelhouse"
    wheelhouse.mkdir()
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--wheel-dir",
            str(wheelhouse),
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    virtualenv = environment / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(virtualenv)
    python = virtualenv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    site_packages = subprocess.run(
        [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    Path(site_packages, "test-runtime-dependencies.pth").write_text(
        str(sysconfig.get_paths()["purelib"]), encoding="utf-8"
    )
    wheel = next(wheelhouse.glob("*.whl"))
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    executable = virtualenv / ("Scripts/cfdpaper.exe" if os.name == "nt" else "bin/cfdpaper")
    assert executable.is_file()
    return executable


def _cli(executable: Path, project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(executable), *arguments],
        cwd=project,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_cli_ok(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def _find_key(value: object, key: str) -> object:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            try:
                return _find_key(child, key)
            except KeyError:
                pass
    elif isinstance(value, list):
        for child in value:
            try:
                return _find_key(child, key)
            except KeyError:
                pass
    raise KeyError(key)


def _output(project: Path, stage: str, name: str) -> Path:
    return project / ".cfdpaper" / "outputs" / stage / name


def _materialize_failed_convergence(project: Path) -> Path:
    mutation = _read_json(project / "negative" / "failed-convergence-project-records.json")
    assert isinstance(mutation, dict)
    records_path = project / str(mutation["base"])
    records = _read_json(records_path)
    assert isinstance(records, dict)
    replacement = mutation["replace"]
    assert isinstance(replacement, dict)
    assert replacement["pointer"] == "/convergence/1/observed_value"
    convergence = records["convergence"]
    assert isinstance(convergence, list)
    assert convergence[1]["observed_value"] == replacement["old"]
    convergence[1]["observed_value"] = replacement["new"]
    destination = project / "negative" / "failed-convergence-records.materialized.json"
    destination.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return destination


def test_public_fixture_is_physically_self_consistent() -> None:
    oracle = _read_json(FIXTURE_ROOT / "oracle.json")
    records = _read_json(FIXTURE_ROOT / "project-records.json")
    assert isinstance(oracle, dict)
    assert isinstance(records, dict)

    with (FIXTURE_ROOT / "observations.csv").open(encoding="utf-8", newline="") as stream:
        observations = list(csv.DictReader(stream))

    diameter = 0.010
    length = 1.000
    viscosity = 1.000e-3
    density = 1000.0
    velocities = [float(row["coordinate_value"]) for row in observations]
    pressure_drops = [float(row["value"]) for row in observations]
    reynolds_numbers = [density * velocity * diameter / viscosity for velocity in velocities]
    analytic_drops = [32.0 * viscosity * velocity * length / diameter**2 for velocity in velocities]

    assert [row["case_id"] for row in observations] == oracle["cases"]
    assert velocities == oracle["coordinate"]["values"]
    assert pressure_drops == pytest.approx(oracle["qoi"]["values"])
    assert pressure_drops == pytest.approx(analytic_drops)
    assert reynolds_numbers == pytest.approx([500.0, 1000.0, 1500.0])
    assert all(value < 2300.0 for value in reynolds_numbers)

    roles = {item["boundary_id"]: item["comparison_role"] for item in records["boundaries"]}
    assert roles == {
        "prescribed-mean-velocity": "intended-study-factor",
        "fixed-pipe-geometry": "demonstrated-equivalent-or-immaterial",
        "fixed-fluid-properties": "demonstrated-equivalent-or-immaterial",
    }
    assert {item["verification_status"] for item in records["models"]} == {"demonstrated"}
    assert {item["validation_status"] for item in records["models"]} == {"not-demonstrated"}
    for source in records["sources"]:
        source_path = FIXTURE_ROOT / source["source_uri"]
        assert source_path.stat().st_size == source["size_bytes"]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == source["sha256"]


def test_public_fixture_runs_complete_public_cli_chain(tmp_path: Path, installed_cli: Path) -> None:
    project = _copy_fixture(tmp_path)
    oracle = _read_json(project / "oracle.json")
    assert isinstance(oracle, dict)

    _assert_cli_ok(
        _cli(installed_cli, project, "init", str(project), "--project-id", "steady-laminar-pipe")
    )
    _assert_cli_ok(_cli(installed_cli, project, "inspect", str(project)))

    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "qualify",
            str(project),
            "--records",
            str(project / "project-records.json"),
            "--observations",
            str(project / "observations.csv"),
            "--question",
            str(project / "question.json"),
        )
    )

    qualification = _read_json(_output(project, "qualify", "qualification-report.json"))
    assert _find_key(qualification, "status") == oracle["qualification"]["status"]
    assert (
        _find_key(qualification, "verification")["state"] == oracle["qualification"]["verification"]
    )
    assert _find_key(qualification, "validation")["state"] == oracle["qualification"]["validation"]
    candidate_path = _output(project, "qualify", "candidate-qoi-contract.json")
    candidate = _read_json(candidate_path)
    contract_id = str(_find_key(candidate, "qoi_contract_id"))

    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "plan",
            str(project),
            "--candidates",
            str(project / "topic-candidates.json"),
            "--approve-topic",
            TOPIC_ID,
            "--author",
            AUTHOR,
        )
    )
    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "qualify",
            str(project),
            "--approve-qoi-contract",
            contract_id,
            "--author",
            AUTHOR,
        )
    )
    _assert_cli_ok(_cli(installed_cli, project, "analyze", str(project)))

    analysis = _read_json(_output(project, "qualify", "qoi-results.json"))
    values = _find_key(analysis, "values")
    assert isinstance(values, list)
    assert [item["case_id"] for item in values] == oracle["cases"]
    assert [item["value"] for item in values] == pytest.approx(oracle["qoi"]["values"])
    assert _find_key(analysis, "trend") == oracle["qoi"]["trend"]

    ceiling = _read_json(_output(project, "qualify", "claim-ceiling.json"))
    assert _find_key(ceiling, "ceiling") == oracle["qualification"]["claim_ceiling"]
    assert oracle["qualification"]["forbidden_ceiling"] not in json.dumps(ceiling)

    figure_candidate = _read_json(_output(project, "qualify", "candidate-figure-contract.json"))
    figure_id = str(_find_key(figure_candidate, "figure_id"))
    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "figure",
            str(project),
            "--approve-contract",
            figure_id,
            "--author",
            AUTHOR,
        )
    )

    figure_dir = project / ".cfdpaper" / "outputs" / "figure" / figure_id
    with (figure_dir / "source-data.csv").open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    assert len(source_rows) == oracle["figure"]["source_data_rows"]
    assert [float(row["qoi_value"]) for row in source_rows] == pytest.approx(
        oracle["qoi"]["values"]
    )
    script = next(figure_dir.glob("plot_*.py"))
    rendered = subprocess.run(
        [sys.executable, str(script)],
        cwd=figure_dir,
        env=os.environ | {"MPLBACKEND": "Agg"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert (figure_dir / f"{figure_id}.svg").is_file()
    assert (figure_dir / f"{figure_id}.png").is_file()

    _assert_cli_ok(
        _cli(installed_cli, project, "write", str(project), "--artifact", "results-paragraph")
    )
    write_dir = project / ".cfdpaper" / "outputs" / "write"
    delivery = _read_json(write_dir / "delivery.json")
    paragraph = str(_find_key(delivery, "paragraph"))
    for fact in oracle["paragraph"]["required_facts"]:
        assert fact in paragraph
    assert len(paragraph.split()) <= oracle["paragraph"]["maximum_words"]
    backlinks = _find_key(delivery, "backlinks")
    assert isinstance(backlinks, list)
    assert len(backlinks) == oracle["paragraph"]["numeric_backlinks"]
    assert oracle["qualification"]["forbidden_ceiling"] not in paragraph

    before_final_approval = {
        path.name: path.read_bytes() for path in write_dir.iterdir() if path.is_file()
    }
    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "write",
            str(project),
            "--artifact",
            "results-paragraph",
            "--approve-final",
            "--author",
            AUTHOR,
        )
    )
    assert {
        path.name: path.read_bytes() for path in write_dir.iterdir() if path.is_file()
    } == before_final_approval
    generated_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (project / ".cfdpaper" / "outputs").rglob("*")
        if path.is_file() and path.suffix in {".json", ".txt", ".csv", ".svg", ".py"}
    )
    assert oracle["qualification"]["forbidden_ceiling"] not in generated_text


@pytest.mark.parametrize(
    ("variant", "first_issue_code"),
    [
        ("missing-middle-member.csv", "missing-expected-member"),
        ("duplicate-middle-member.csv", "duplicate-observation"),
        ("unknown-pressure-unit.csv", "unknown-unit"),
        ("failed-convergence-project-records.json", "failed-blocking-threshold"),
    ],
)
def test_public_fixture_rejects_one_defect_before_downstream_artifacts(
    tmp_path: Path, installed_cli: Path, variant: str, first_issue_code: str
) -> None:
    project = _copy_fixture(tmp_path)
    _assert_cli_ok(
        _cli(installed_cli, project, "init", str(project), "--project-id", "negative-pipe")
    )
    _assert_cli_ok(_cli(installed_cli, project, "inspect", str(project)))

    observations = project / "observations.csv"
    records = project / "project-records.json"
    if variant.endswith(".csv"):
        observations = project / "negative" / variant
    else:
        records = _materialize_failed_convergence(project)

    result = _cli(
        installed_cli,
        project,
        "qualify",
        str(project),
        "--records",
        str(records),
        "--observations",
        str(observations),
        "--question",
        str(project / "question.json"),
    )

    assert result.returncode == 3, result.stdout + result.stderr
    assert first_issue_code in (result.stdout + result.stderr)
    assert not _output(project, "qualify", "candidate-qoi-contract.json").exists()
    assert not _output(project, "qualify", "locked-qoi-contract.json").exists()
    assert not _output(project, "qualify", "qoi-results.json").exists()
    assert not (project / ".cfdpaper" / "outputs" / "figure").exists()
    assert not (project / ".cfdpaper" / "outputs" / "write").exists()


@pytest.mark.parametrize(
    "analysis_request", ("area integration", "smoothing", "continuous optimum")
)
def test_public_fixture_rejects_unsupported_analysis_requests(
    tmp_path: Path, installed_cli: Path, analysis_request: str
) -> None:
    project = _copy_fixture(tmp_path)
    question = _read_json(project / "question.json")
    assert isinstance(question, dict)
    proposal = question["proposal"]
    assert isinstance(proposal, dict)
    if analysis_request == "continuous optimum":
        proposal["continuous_optimum"] = True
    else:
        proposal["operator"] = analysis_request.replace(" ", "-")
    requested = project / "unsupported-question.json"
    requested.write_text(json.dumps(question), encoding="utf-8")
    _assert_cli_ok(
        _cli(installed_cli, project, "init", str(project), "--project-id", "adversarial")
    )
    _assert_cli_ok(_cli(installed_cli, project, "inspect", str(project)))

    result = _cli(
        installed_cli,
        project,
        "qualify",
        str(project),
        "--records",
        str(project / "project-records.json"),
        "--observations",
        str(project / "observations.csv"),
        "--question",
        str(requested),
    )

    assert result.returncode == 2
    assert not _output(project, "qualify", "locked-qoi-contract.json").exists()
    assert not _output(project, "qualify", "claim-ceiling.json").exists()
    assert not (project / ".cfdpaper" / "outputs" / "figure").exists()
    assert not (project / ".cfdpaper" / "outputs" / "write").exists()


def test_public_fixture_rejects_author_override(tmp_path: Path, installed_cli: Path) -> None:
    project = _copy_fixture(tmp_path)
    _assert_cli_ok(_cli(installed_cli, project, "init", str(project), "--project-id", "author"))
    _assert_cli_ok(_cli(installed_cli, project, "inspect", str(project)))
    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "qualify",
            str(project),
            "--records",
            str(project / "project-records.json"),
            "--observations",
            str(project / "observations.csv"),
            "--question",
            str(project / "question.json"),
        )
    )
    candidate = _read_json(_output(project, "qualify", "candidate-qoi-contract.json"))
    contract_id = str(_find_key(candidate, "qoi_contract_id"))
    _assert_cli_ok(
        _cli(
            installed_cli,
            project,
            "plan",
            str(project),
            "--candidates",
            str(project / "topic-candidates.json"),
            "--approve-topic",
            TOPIC_ID,
            "--author",
            AUTHOR,
        )
    )

    result = _cli(
        installed_cli,
        project,
        "qualify",
        str(project),
        "--approve-qoi-contract",
        contract_id,
        "--author",
        "Different Author",
    )

    assert result.returncode == 2
    assert not _output(project, "qualify", "locked-qoi-contract.json").exists()
