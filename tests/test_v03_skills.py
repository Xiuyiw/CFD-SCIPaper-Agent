import re
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills"
EXPECTED_SKILLS = (
    "cfd-evidence-intake",
    "cfd-qoi-physics",
    "cfd-figure-production",
    "cfd-evidence-writing",
)
REQUIRED_SECTIONS = (
    "Trigger",
    "Do not trigger",
    "Inputs",
    "Outputs",
    "Prerequisites",
    "Workflow",
    "Stop conditions",
    "Fallback",
    "Public fixture reference",
    "Success criteria",
)


def _read_skill(name: str) -> tuple[dict[str, str], str]:
    path = SKILL_ROOT / name / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", content, flags=re.DOTALL)
    assert match is not None, f"{name} must contain YAML frontmatter"
    frontmatter = yaml.safe_load(match.group(1))
    assert isinstance(frontmatter, dict)
    return frontmatter, match.group(2)


def test_v03_ships_exactly_four_thin_skills() -> None:
    assert tuple(sorted(path.name for path in SKILL_ROOT.iterdir() if path.is_dir())) == tuple(
        sorted(EXPECTED_SKILLS)
    )
    for name in EXPECTED_SKILLS:
        assert [path.name for path in (SKILL_ROOT / name).iterdir()] == ["SKILL.md"]


def test_each_skill_declares_the_required_contract_without_private_paths() -> None:
    windows_user_root = "".join(("C:", chr(92), "Users", chr(92)))
    forbidden_paths = (windows_user_root, "/home/", "/Users/", "file://")

    for name in EXPECTED_SKILLS:
        frontmatter, body = _read_skill(name)
        normalized_body = " ".join(body.casefold().split())
        assert frontmatter["name"] == name
        assert isinstance(frontmatter.get("description"), str)
        assert frontmatter["description"].strip()
        for section in REQUIRED_SECTIONS:
            assert re.search(rf"^## {re.escape(section)}$", body, flags=re.MULTILINE)
        assert all(fragment not in body for fragment in forbidden_paths)
        assert "examples/steady_laminar_pipe/" in body
        assert "positive" in body.casefold()
        assert "negative/" in body
        assert "adversarial" in body.casefold()
        assert "running this skill alone is not scientific or author approval" in normalized_body


def test_skills_only_call_the_delivered_v03_cli_sequence() -> None:
    bodies = {name: _read_skill(name)[1] for name in EXPECTED_SKILLS}
    expected_commands = {
        "cfd-evidence-intake": (
            "cfdpaper init PROJECT_ROOT",
            "cfdpaper inspect PROJECT_ROOT",
            "cfdpaper qualify PROJECT_ROOT --records",
            "cfdpaper plan PROJECT_ROOT",
            "cfdpaper qualify PROJECT_ROOT --approve-qoi-contract",
        ),
        "cfd-qoi-physics": ("cfdpaper analyze PROJECT_ROOT",),
        "cfd-figure-production": ("cfdpaper figure PROJECT_ROOT",),
        "cfd-evidence-writing": ("cfdpaper write PROJECT_ROOT",),
    }
    allowed_verbs = {"init", "inspect", "qualify", "plan", "analyze", "figure", "write"}

    for name, prefixes in expected_commands.items():
        body = bodies[name]
        positions = [body.index(prefix) for prefix in prefixes]
        assert positions == sorted(positions)
        commands = re.findall(r"^\s*cfdpaper\s+([a-z-]+)\b", body, flags=re.MULTILINE)
        assert commands
        assert set(commands) <= allowed_verbs

    combined = "\n".join(bodies[name] for name in EXPECTED_SKILLS)
    sequence = [
        "cfdpaper init PROJECT_ROOT",
        "cfdpaper inspect PROJECT_ROOT",
        "cfdpaper qualify PROJECT_ROOT --records",
        "cfdpaper plan PROJECT_ROOT",
        "cfdpaper qualify PROJECT_ROOT --approve-qoi-contract",
        "cfdpaper analyze PROJECT_ROOT",
        "cfdpaper figure PROJECT_ROOT",
        "cfdpaper write PROJECT_ROOT",
    ]
    positions = [combined.index(command) for command in sequence]
    assert positions == sorted(positions)
    assert not re.search(r"^\s*cfdpaper\s+(review|revise|export)\b", combined, re.MULTILINE)


def test_skills_reference_the_public_fixture_stop_expectations() -> None:
    combined = "\n".join(_read_skill(name)[1] for name in EXPECTED_SKILLS).casefold()
    for expectation in (
        "missing-member",
        "duplicate-coordinate",
        "unit",
        "locator",
        "unresolved-nuisance",
        "area integral",
        "smoothing",
        "continuous optim",
        "approval override",
    ):
        assert expectation in combined
