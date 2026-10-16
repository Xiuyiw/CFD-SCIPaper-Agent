"""Connect a selected surface study, author-local figures and existing manuscript tools."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from cfdpaper.publication.figure_recipes import execute_figure_recipes
from cfdpaper.publication.figure_tasks import _asset, _check_preview, _Delivery, _Task
from cfdpaper.publication.manuscript import _inputs, assemble_manuscript, prepare_manuscript
from cfdpaper.publication.section import _Draft, _read, _stage, _write, export_section_docx
from cfdpaper.publication.surface_figures import _read_study

_RESULTS = Path("sections/results")
_PARAMETERS = "sources/cfdpaper-surface-thresholds.json"
_SECTIONS = {
    "methods": (
        "Methods",
        "Define the shared conditions, source fields and observation operators.",
    ),
    "results": (
        "Results",
        "Read the actual surface fields together with area-weighted distributions.",
    ),
    "discussion": (
        "Discussion",
        "Interpret the combined observations and distinguish alternatives.",
    ),
    "conclusion": ("Conclusions", "Answer the research question within the available evidence."),
}
_STYLE = {
    "width_mm": 160,
    "height_mm": 110,
    "font_family": "Times New Roman",
    "font_pt": 9,
    "axis_label_pt": 9,
    "title_pt": 10,
    "tick_pt": 8,
    "legend_pt": 9,
}


def _study(path):
    data, _ = _read_study(path)
    for key in ("study_id", "title", "question", "time_support"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Research study requires a nonblank {key}")
    for identity in [data["study_id"], *[case["id"] for case in data["cases"]]]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity):
            raise ValueError("Study and case IDs must be portable identifiers")
    conditions = data.get("common_conditions")
    if (
        not isinstance(conditions, list)
        or not conditions
        or any(not isinstance(value, str) or not value.strip() for value in conditions)
    ):
        raise ValueError("common_conditions must be a nonempty list of declared conditions")
    definition = data.get("definition")
    if not isinstance(definition, dict) or any(
        not isinstance(definition.get(key), str) or not definition[key].strip()
        for key in ("source", "text")
    ):
        raise ValueError("definition requires source and text")
    source = Path(definition["source"])
    if source.parts[:1] != ("sources",):
        raise ValueError("Definition source must be a relative sources/ file")
    _asset(path.parent, definition["source"])
    if _PARAMETERS in {definition["source"], *[case["source"] for case in data["cases"]]}:
        raise ValueError(f"Selected material conflicts with generated parameters: {_PARAMETERS}")
    return data


def _distinct_output(source, output):
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Use a fresh output outside the source workspace or material directory")


def attach_imported_figure(
    workspace_dir: Path,
    imported_dir: Path,
    output_dir: Path,
    *,
    section_id: str,
    evidence_ids: list[str],
    image_observation: str = "not-viewed",
    observation_note: str = "",
    paragraph_index: int | None = None,
) -> Path:
    """Attach an imported figure to a fresh authoring workspace, without replacing prose.

    The delivery's body_reference must use its local ``{{figure:ID}}`` token. Its
    caption and sizing enter the existing manuscript assembly and global numbering.
    Only declared source/artwork files and import metadata are copied from the figure
    package; bundled drawing Skills are not duplicated into manuscript sources.
    Observation status/notes are caller declarations, never scientific approval.
    ``paragraph_index`` inserts before that zero-based paragraph; None appends.
    """
    workspace_dir, imported_dir, output_dir = map(
        lambda path: Path(path).resolve(), (workspace_dir, imported_dir, output_dir)
    )
    _distinct_output(workspace_dir, output_dir)
    _distinct_output(imported_dir, output_dir)
    manifest_path = _asset(workspace_dir, "manuscript-input.json")
    manifest = _read(manifest_path)
    _, loaded, _, _, _ = _inputs(manifest_path)
    if section_id not in loaded:
        raise ValueError(f"Unknown manuscript section: {section_id}")
    available = {record.id for record in loaded[section_id][1].evidence}
    if not isinstance(evidence_ids, list) or any(
        not isinstance(key, str) or key not in available for key in evidence_ids
    ):
        raise ValueError("Figure paragraph evidence_ids must exist in the target section")
    entry = next(item for item in manifest["sections"] if item["section_id"] == section_id)
    source = _asset(workspace_dir, entry["input"])
    section = _read(source)
    drafts = _read(_asset(workspace_dir, "drafts.json"))
    if section_id not in drafts:
        raise ValueError(f"Missing draft mapping for section: {section_id}")
    draft_path = _asset(workspace_dir, drafts[section_id])
    draft = _read(draft_path)
    if not isinstance(observation_note, str) or (observation_note and not observation_note.strip()):
        raise ValueError("observation_note must be nonblank when provided")
    if paragraph_index is not None and (
        type(paragraph_index) is not int or not 0 <= paragraph_index <= len(draft["paragraphs"])
    ):
        raise ValueError("paragraph_index must be an insertion position within the draft")

    task = _Task.model_validate(_read(_asset(imported_dir, "task.json")))
    metadata = _read(_asset(imported_dir, "delivery.json"))
    if metadata.get("status") != "imported_candidate":
        raise ValueError("Use the candidate directory returned by import_figure_task")
    delivery = _Delivery.model_validate(
        {key: value for key, value in metadata.items() if key in _Delivery.model_fields}
    )
    figure_id = task.figure_id
    if figure_id in {".", ".."} or delivery.figure_id != figure_id:
        raise ValueError("Imported figure identity is invalid or does not match its task")
    existing_ids = {
        *[figure.id for figure in loaded[section_id][1].figures],
        *draft["captions"],
        *draft["image_observations"],
        *draft.get("observation_notes", {}),
    }
    if figure_id.casefold() in {key.casefold() for key in existing_ids}:
        raise ValueError(f"Figure already exists in section {section_id}: {figure_id}")
    if "{{figure:" + figure_id + "}}" not in delivery.body_reference:
        raise ValueError("body_reference must contain the imported figure's local figure token")
    _check_preview(_asset(imported_dir, delivery.preview), task.final_width_mm)
    names = list(
        dict.fromkeys(
            [
                "task.json",
                "delivery.json",
                *[item.path for item in task.sources],
                *delivery.editable_sources,
                delivery.preview,
                *delivery.exports,
            ]
        )
    )
    assets = {name: _asset(imported_dir, name) for name in names}
    relative = Path("sources/figure-tasks") / figure_id
    destination = source.parent / relative
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite author-owned figure sources: {destination}")
    section["figures"].append(
        {
            "id": figure_id,
            "path": (relative / delivery.preview).as_posix(),
            "caption": delivery.caption,
            "description": task.purpose,
            "sizing": delivery.sizing.model_dump(),
        }
    )
    section["source_files"] = list(
        dict.fromkeys(
            [*section.get("source_files", []), *[(relative / name).as_posix() for name in names]]
        )
    )
    paragraph = {
        "text": delivery.body_reference,
        "evidence_ids": evidence_ids,
        "figure_ids": [figure_id],
    }
    draft["paragraphs"].insert(
        len(draft["paragraphs"]) if paragraph_index is None else paragraph_index, paragraph
    )
    draft["captions"][figure_id] = delivery.caption
    draft["image_observations"][figure_id] = image_observation
    if observation_note:
        draft.setdefault("observation_notes", {})[figure_id] = observation_note
    _Draft.model_validate(draft)
    contract = next(
        item for item in manifest["spine"]["sections"] if item["section_id"] == section_id
    )
    contract.setdefault("required_figure_ids", []).append(figure_id)
    with _stage(output_dir) as staged:
        shutil.copytree(workspace_dir, staged, dirs_exist_ok=True)
        target_section = staged / source.parent.relative_to(workspace_dir)
        for name, original in assets.items():
            target = target_section / relative / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        _write(staged / entry["input"], section)
        _write(staged / drafts[section_id], draft)
        _write(staged / "manuscript-input.json", manifest)
    return output_dir


def _definition_text(data):
    return (
        data["definition"]["text"]
        + "\nTime support: "
        + data["time_support"]
        + "\nCommon conditions: "
        + "; ".join(data["common_conditions"])
        + f"\nDomain: {data['domain']}. Quantity: {data['quantity']} ({data['unit']}). "
        + "Weights are supplied face areas in m^2."
    )


def _declarations(data):
    calculations = []
    evidence = [
        {
            "id": "study-definition",
            "kind": "observation",
            "text": _definition_text(data),
            "source": data["definition"]["source"],
        }
    ]
    evidence.extend(
        {
            "id": f"threshold-{index}",
            "kind": "metric",
            "text": f"Declared surface exceedance threshold {index}",
            "source": _PARAMETERS,
            "json_value_ref": {
                "source": _PARAMETERS,
                "pointer": f"/thresholds/{index - 1}",
                "unit": data["unit"],
                "places": 3,
            },
        }
        for index in range(1, len(data["thresholds"]) + 1)
    )
    kind = data.get(
        "quantity_kind",
        "absolute-temperature" if data["unit"] in {"K", "degC", "°C", "C"} else "ordinary",
    )
    for case in data["cases"]:
        common = {
            "source": case["source"],
            "columns": {"value": data["arrays"]["values"], "weight": data["arrays"]["weights"]},
            "units": {"value": data["unit"], "weight": "m^2"},
            "domain": data["domain"],
            "weight_kind": "area",
            "quantity_kind": kind,
        }
        population = f"surface-{case['id']}-population"
        calculations.append({"id": population, "operation": "weighted_population", **common})
        fields = [
            (f"{case['id']}-mean", population, "weighted_mean", "Area-weighted mean"),
            (f"{case['id']}-std", population, "weighted_std", "Area-weighted population SD"),
        ]
        for index, threshold in enumerate(data["thresholds"], 1):
            identity = f"surface-{case['id']}-exceedance-{index}"
            relation = data.get("exceedance_relation", "above")
            calculations.append(
                {
                    "id": identity,
                    "operation": "weighted_exceedance",
                    **common,
                    "threshold": threshold,
                    "exceedance_relation": relation,
                }
            )
            fields.append(
                (
                    f"{case['id']}-exceedance-{index}",
                    identity,
                    "exceedance_fraction",
                    f"Area fraction {relation} {threshold:g} {data['unit']}",
                )
            )
        for identity, calculation, field, label in fields:
            evidence.append(
                {
                    "id": identity,
                    "kind": "metric",
                    "text": f"{label}: {case['label']}",
                    "source": case["source"],
                    "result_ref": {
                        "calculation_id": calculation,
                        "group": "all",
                        "field": field,
                        "places": 3,
                        "percentage": field == "exceedance_fraction",
                    },
                }
            )
    return calculations, evidence


def _recipe(data):
    prefix = (_RESULTS / "figures").as_posix()
    outputs = [
        f"{prefix}/{figure}.{extension}"
        for figure in ("field", "distribution")
        for extension in ("png", "svg", "pdf", "tiff")
    ]
    outputs += [
        f"{prefix}/{name}"
        for name in (
            "field-source-data.csv",
            "threshold-source-data.csv",
            "distribution-source-data.csv",
            "surface-checks.json",
            "surface-figures.json",
        )
    ]
    return {
        "id": "surface-study",
        "script": f"{prefix}/plot.py",
        "section_id": "results",
        "inputs": [
            (_RESULTS / "study.json").as_posix(),
            *[(_RESULTS / case["source"]).as_posix() for case in data["cases"]],
            (_RESULTS / data["definition"]["source"]).as_posix(),
        ],
        "outputs": outputs,
    }


def _figure_metadata(workspace, *, initial=False):
    root = (workspace / _RESULTS).resolve()
    summary = _read(root / "figures/surface-figures.json")
    figures = {item["id"]: item for item in summary["figures"]}
    if not {"field", "distribution"} <= figures.keys():
        raise ValueError("Surface recipe must report field and distribution figure metadata")
    data = _read(root / "input.json")
    if initial:
        data["figures"] = [
            {key: item[key] for key in ("id", "path", "caption", "description", "sizing")}
            for item in figures.values()
        ]
    for figure in data["figures"]:
        if figure["id"] in figures:
            item = figures[figure["id"]]
            path = _asset(root / "figures", item["path"])
            figure["path"] = path.relative_to(root).as_posix()
            figure["sizing"] = item["sizing"]
    _write(root / "input.json", data)


def _host_context(root, data):
    _write(
        root / "research-context.json",
        {
            "study_id": data["study_id"],
            "question": data["question"],
            "time_support": data["time_support"],
            "common_conditions": data["common_conditions"],
            "definition": data["definition"],
            "study": "sections/results/study.json",
            "results": "sections/results/table-results.json",
            "figure_script": "sections/results/figures/plot.py",
        },
    )
    (root / "RESEARCH.md").write_text(
        "# Connected surface research workspace\n\n"
        f"Question: {data['question']}\n\n"
        "Read research-context.json, TASK.md, and each section's TASK.md and "
        "manuscript-context.json. Source paths in the study are relative to sections/results/. "
        "Open both figures and read the definition material before interpreting the comparison.\n\n"
        "The generated spine and duties are provisional: study-definition is a scope fact, "
        "not a scientific central finding. Before writing, update the spine and duties to "
        "the actual finding and each section's evidence needs. Discussion and Conclusions "
        "do not have to repeat every available metric.\n\n"
        "Fill sections/SECTION/draft.json from its empty template, preserving local evidence IDs. "
        "drafts.json is the complete path map, not completed prose. Use {{value:ID}} for bound "
        "numbers and the existing table/figure/equation tokens. table-results.json contains the "
        "calculated observations. Each case has CASE-mean, CASE-std, and CASE-exceedance-N "
        "(one-based threshold order; displayed as percent, raw value remains a fraction). "
        "All four sections can use these IDs. "
        "Do not infer missing model, validation or literature facts.\n\n"
        "study.json owns the surface observation definitions and source paths; generated "
        "surface-* calculations are refreshed from it. Edit the current local figures/plot.py "
        "for style changes; build executes that script, never replaces it from a template. "
        "Source values keep their supplied units. Edit caption prose in the Results draft.\n\n"
        "Build into a new directory. Pass the previous build as baseline for selective figure "
        "refresh and interpretation review. Continue from the returned workspace/; manuscript/ "
        "and manuscript.docx are generated reading views. Reconcile Word-only author edits "
        "into the drafts before another build; this workflow does not import Word edits.\n",
        encoding="utf-8",
    )


def prepare_surface_workspace(study_path: Path, output_dir: Path) -> Path:
    """Prepare portable observations, real figures and EMPTY four-section host draft templates.

    In addition to surface_figures config, study.json requires study_id, title,
    question, time_support, common_conditions: list[str], and
    definition: {source: 'sources/definition.md', text: 'declared observation'}.
    Only selected NPZs and this definition material are copied; no solver runs.
    """
    study_path, output_dir = Path(study_path).resolve(), Path(output_dir).resolve()
    _distinct_output(study_path.parent, output_dir)
    data = _study(study_path)
    calculations, evidence = _declarations(data)
    metric_ids = [item["id"] for item in evidence]
    means = [f"{case['id']}-mean" for case in data["cases"]]
    with _stage(output_dir) as staged, TemporaryDirectory(prefix="cfdpaper-surface-") as temporary:
        source = Path(temporary) / "source"
        result = source / _RESULTS
        result.mkdir(parents=True)
        names = list(
            dict.fromkeys(
                [case["source"] for case in data["cases"]] + [data["definition"]["source"]]
            )
        )
        for name in names:
            target = result / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_asset(study_path.parent, name), target)
        _write(result / _PARAMETERS, {"thresholds": data["thresholds"]})
        names.append(_PARAMETERS)
        _write(result / "study.json", data)
        (result / "figures").mkdir()
        (result / "figures/plot.py").write_text(
            '"""Current author-editable surface figure recipe; retain local style edits."""\n'
            "from pathlib import Path\n"
            "from cfdpaper.publication.render_figure import PlotStyle\n"
            "from cfdpaper.publication.surface_figures import render_surface_study\n\n"
            f"PLOT_STYLE = {_STYLE!r}\n"
            "ROOT = Path(__file__).resolve().parents[1]\n"
            "render_surface_study(ROOT / 'study.json', ROOT / 'figures', "
            "style=PlotStyle(**PLOT_STYLE))\n",
            encoding="utf-8",
        )
        entries, contracts = [], []
        for sid, (title, purpose) in _SECTIONS.items():
            folder = source / "sections" / sid
            folder.mkdir(parents=True, exist_ok=True)
            required = means if sid == "results" else ["study-definition"]
            _write(
                folder / "input.json",
                {
                    "section_id": sid,
                    "title": title,
                    "question": data["question"],
                    "figures": [],
                    "evidence": evidence if sid == "results" else [],
                    "duties": [
                        {
                            "purpose": purpose,
                            "evidence_ids": required,
                            "figure_ids": ["field", "distribution"] if sid == "results" else [],
                        }
                    ],
                    "context": _definition_text(data),
                    "source_files": names if sid == "results" else [],
                    "table_calculations": calculations if sid == "results" else [],
                },
            )
            entries.append(
                {
                    "section_id": sid,
                    "input": f"sections/{sid}/input.json",
                    "evidence_bindings": {key: f"results/{key}" for key in metric_ids}
                    if sid != "results"
                    else {},
                    "depends_on": ["methods", "results"]
                    if sid == "discussion"
                    else ["discussion", "results"]
                    if sid == "conclusion"
                    else [],
                }
            )
            contracts.append(
                {
                    "section_id": sid,
                    "role": sid,
                    "title": title,
                    "purpose": purpose,
                    "required_claim_ids": required,
                    "required_figure_ids": ["field", "distribution"] if sid == "results" else [],
                }
            )
        recipes = [_recipe(data)]
        execute_figure_recipes(source, recipes)
        _figure_metadata(source, initial=True)
        _write(
            source / "manuscript-input.json",
            {
                "title": data["title"],
                "context": data["question"],
                "spine": {
                    "topic_id": data["study_id"],
                    "central_claim_id": "study-definition",
                    "sections": contracts,
                },
                "sections": entries,
            },
        )
        package = prepare_manuscript(source / "manuscript-input.json", Path(temporary) / "prepared")
        shutil.copytree(package, staged, dirs_exist_ok=True)
        shutil.copytree(result / "figures", staged / _RESULTS / "figures", dirs_exist_ok=True)
        shutil.copy2(result / "study.json", staged / _RESULTS / "study.json")
        _write(staged / "figure-recipes.json", recipes)
        mapping = _read(staged / "drafts-template.json")
        for sid, name in mapping.items():
            shutil.copy2(staged / f"sections/{sid}/draft-template.json", staged / name)
        results_draft = _read(staged / mapping["results"])
        results_draft["tables"] = [
            {
                "table_id": "surface-summary",
                "caption": "Area-weighted surface observations.",
                "after_section_id": "results",
                "numeric_columns": list(range(1, 3 + len(data["thresholds"]))),
                "columns": [
                    "Case",
                    "Area-weighted mean",
                    "Population SD",
                    *[
                        "Area fraction at {{value:threshold-" + str(index) + "}}"
                        for index in range(1, len(data["thresholds"]) + 1)
                    ],
                ],
                "rows": [
                    [
                        case["label"],
                        "{{value:" + case["id"] + "-mean}}",
                        "{{value:" + case["id"] + "-std}}",
                        *[
                            "{{value:" + case["id"] + f"-exceedance-{index}" + "}}"
                            for index in range(1, len(data["thresholds"]) + 1)
                        ],
                    ]
                    for case in data["cases"]
                ],
                "evidence_ids": [item["id"] for item in evidence if item["kind"] == "metric"],
            }
        ]
        _write(staged / mapping["results"], results_draft)
        _write(staged / "sections/results/draft-template.json", results_draft)
        _write(staged / "drafts.json", mapping)
        _host_context(staged, data)
    return output_dir


def _sync_definitions(workspace, data):
    source = workspace / _RESULTS / "input.json"
    section = _read(source)
    previous = {
        item["id"]
        for item in section["evidence"]
        if (item.get("result_ref") or {}).get("calculation_id", "").startswith("surface-")
        or (item.get("json_value_ref") or {}).get("source") == _PARAMETERS
    }
    previous.add("study-definition")
    previous_sources = {item["source"] for item in section["evidence"] if item["id"] in previous}
    calculations, evidence = _declarations(data)
    _write(workspace / _RESULTS / _PARAMETERS, {"thresholds": data["thresholds"]})
    section["table_calculations"] = [
        item for item in section["table_calculations"] if not item["id"].startswith("surface-")
    ] + calculations
    section["evidence"] = [
        item for item in section["evidence"] if item["id"] not in previous
    ] + evidence
    section["source_files"] = list(
        dict.fromkeys(
            [
                *[name for name in section.get("source_files", []) if name not in previous_sources],
                data["definition"]["source"],
                _PARAMETERS,
                *[case["source"] for case in data["cases"]],
            ]
        )
    )
    _write(source, section)
    manifest = _read(workspace / "manuscript-input.json")
    for entry in manifest["sections"]:
        if entry["section_id"] in {"methods", "discussion", "conclusion"}:
            bindings = entry.get("evidence_bindings", {})
            entry["evidence_bindings"] = {
                key: value
                for key, value in bindings.items()
                if not (key in previous and value == f"results/{key}")
            }
            entry["evidence_bindings"].update(
                {item["id"]: f"results/{item['id']}" for item in evidence}
            )
    _write(workspace / "manuscript-input.json", manifest)
    return previous_sources


def _definition_changes(workspace, baseline, data):
    if baseline is None or not (baseline / _RESULTS / "study.json").is_file():
        return []
    before = _read(baseline / _RESULTS / "study.json")
    changes = sorted(key for key in before.keys() | data.keys() if before.get(key) != data.get(key))
    name = data["definition"]["source"]
    old_name = before.get("definition", {}).get("source")
    if old_name:
        old = baseline / _RESULTS / old_name
        if not old.is_file() or old.read_bytes() != _asset(workspace / _RESULTS, name).read_bytes():
            changes.append("definition.source_content")
    return changes


def build_research_workspace(workspace_dir: Path, output_dir: Path, baseline_dir=None) -> Path:
    """Build host-written drafts and changed local figure recipes into a new Word candidate.

    baseline_dir normally names a previous build root containing workspace/ and
    manuscript/. The caller's workspace, drafts, scripts and baseline stay unchanged.
    """
    workspace_dir, output_dir = Path(workspace_dir).resolve(), Path(output_dir).resolve()
    _distinct_output(workspace_dir, output_dir)
    baseline = Path(baseline_dir).resolve() if baseline_dir is not None else None
    if baseline is not None and not baseline.is_dir():
        raise ValueError("Research baseline must be an existing build or workspace directory")
    old_workspace = (
        baseline / "workspace"
        if baseline is not None and (baseline / "workspace").is_dir()
        else baseline
    )
    with _stage(output_dir) as staged:
        workspace = staged / "workspace"
        shutil.copytree(workspace_dir, workspace)
        data = _study(workspace / _RESULTS / "study.json")
        definition_changes = _definition_changes(workspace, old_workspace, data)
        previous_sources = _sync_definitions(workspace, data)
        recipes = _read(workspace / "figure-recipes.json")
        registered = next((item for item in recipes if item["id"] == "surface-study"), None)
        if registered is None:
            raise ValueError("Research workspace requires its registered surface-study recipe")
        retired = {(_RESULTS / name).as_posix() for name in previous_sources}
        registered["inputs"] = list(
            dict.fromkeys(
                [
                    *[name for name in registered["inputs"] if name not in retired],
                    *_recipe(data)["inputs"],
                ]
            )
        )
        # Only the declared dependency paths change; the author's script, arguments
        # and output declarations remain the current execution entry point.
        _write(workspace / "figure-recipes.json", recipes)
        statuses = execute_figure_recipes(workspace, recipes, baseline_root=old_workspace)
        _figure_metadata(workspace)
        if baseline is not None:
            state = next(
                (
                    path
                    for path in (
                        baseline / "manuscript/writing-state.json",
                        old_workspace / "writing-state.json",
                        baseline / "writing-state.json",
                    )
                    if path.is_file()
                ),
                None,
            )
            if state is not None:
                shutil.copy2(state, workspace / "writing-state.json")
        manuscript = assemble_manuscript(
            workspace, workspace / "drafts.json", staged / "manuscript"
        )
        export_section_docx(manuscript, staged / "manuscript.docx", layout="near-reference")
        # Keep the next authoring workspace's generated contexts/results current,
        # without copying rendered prose over the original local-ID draft files.
        for entry in _read(workspace / "manuscript-input.json")["sections"]:
            sid = entry["section_id"]
            destination = (workspace / entry["input"]).parent
            for name in (
                "input.json",
                "manuscript-context.json",
                "table-results.json",
                "parameter-results.json",
            ):
                source = manuscript / "sections" / sid / name
                if source.is_file():
                    shutil.copy2(source, destination / name)
        shutil.copy2(manuscript / "writing-state.json", workspace / "writing-state.json")
        _host_context(workspace, data)
        changes = _read(manuscript / "changes.json")
        scientific_changes = [
            item
            for item in changes["changes"]
            if item["category"] in {"source", "evidence", "scientific", "binding", "literature"}
            or (
                item["category"] == "input"
                and set(item.get("fields", []))
                & {
                    "table_calculations",
                    "result_comparisons",
                    "source_files",
                    "context",
                    "question",
                }
            )
        ]
        review_required = bool(definition_changes or scientific_changes)
        _write(
            staged / "refresh.json",
            {
                "figure_recipes": statuses,
                "definition_changes": definition_changes,
                "interpretation_review_required": review_required,
                "interpretation_review_sections": sorted(changes["affected_sections"])
                if review_required
                else [],
                "affected_sections": changes["affected_sections"],
                "unchanged_sections": changes["unchanged_sections"],
            },
        )
        report = (
            (manuscript / "CHANGES.md")
            .read_text(encoding="utf-8")
            .replace(
                "Recheck related figures/tables after source changes; images are not regenerated.",
                "Recheck related figures/tables after source changes; registered image updates "
                "are listed in the research refresh summary.",
            )
        )
        report += (
            "\n## Registered figure refresh\n\n"
            + "\n".join(f"- {item['recipe_id']}: {item['status']}." for item in statuses)
            + "\n"
        )
        if review_required:
            report += (
                "\n## Interpretation review required\n\n"
                + (
                    "Observation definition material changed and needs review: "
                    + ", ".join(definition_changes)
                    + ". "
                    if definition_changes
                    else "Source observations or bound evidence changed. "
                )
                + "Reconsider the affected sections and captions listed above. Bound values "
                "were updated; author interpretation and caption prose were preserved.\n"
            )
        (staged / "CHANGES.md").write_text(report, encoding="utf-8")
    return output_dir
