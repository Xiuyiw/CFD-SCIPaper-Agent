"""Refresh author-owned figure tables and a section from the same computed evidence."""

from __future__ import annotations

import csv
import io
import operator
import re
import shutil
from collections import Counter
from pathlib import Path

from cfdpaper.adapters.csv import source_sha256
from cfdpaper.publication.document_blocks import paragraph_identity
from cfdpaper.publication.figure_recipes import _definitions, _relative_name, execute_figure_recipes
from cfdpaper.publication.figure_tasks import _asset
from cfdpaper.publication.section import (
    _assemble_section,
    _calculate_sources,
    _load_input,
    _read,
    _resolve_metric,
    _stage,
    _write,
    export_section_docx,
)


def _metrics(data, root, reports):
    """Small display inputs, with the physical definitions retained once per calculation."""
    definitions = {}
    for item in [*data.table_calculations, *data.result_comparisons]:
        definition = item.model_dump(exclude_none=True)
        locator = definition.get("definition_source")
        if locator:
            name, lines = locator.rsplit(":", 1)
            first, *last = (int(i) for i in re.findall(r"\d+", lines))
            definition["definition_text"] = "\n".join(
                _asset(root, name)
                .read_text(encoding="utf-8-sig")
                .splitlines()[first - 1 : (last or [first])[0]]
            )
        definitions[item.id] = definition
    metrics = {}
    for e in data.evidence:
        if not (v := _resolve_metric(e, root, reports)):
            continue
        calc = v.get("calculation_id")
        parents = {
            p.calculation_id
            for c in data.result_comparisons
            if c.id == calc
            for p in (c.reference, c.comparison)
        }
        metrics[e.id] = {
            "raw_value": v["raw_value"],
            "value": v["value"],
            "unit": v["unit"],
            "ref": (e.result_ref or e.json_value_ref).model_dump(),
            "calculations": sorted(({calc} if calc else set()) | parents),
        }
        if "supporting_results" in v:
            # An unchanged ratio can still have a new physical reference. Keep the two
            # actual operands, not the per-face indices already in table-results.json.
            metrics[e.id]["operands"] = [
                {
                    key: parent[key]
                    for key in ("calculation_id", "group", "field", "unit", "raw_value")
                }
                for parent in v["supporting_results"]
            ]
    return metrics, definitions


def _patch_table(path, binding, metrics):
    """Use stable row keys; change only explicitly bound cells; preserve unbound author data."""
    key, columns = binding["row_key"], binding["columns"]
    if not isinstance(columns, dict) or not columns or key in columns:
        raise ValueError("Result columns must be nonempty and must not replace the row key")
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    reader = csv.DictReader(io.StringIO(raw.decode(encoding), newline=""), strict=True)
    names = reader.fieldnames or []
    if len(set(names)) != len(names) or ({key} | columns.keys()) - set(names):
        raise ValueError(f"Missing or ambiguous author table columns: {path.name}")
    rows = list(reader)
    if any(None in r or None in r.values() or not r[key].strip() for r in rows):
        raise ValueError(f"Invalid author table row: {path.name}")
    lookup = {r[key]: r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError(f"Duplicate author table row key: {path.name}/{key}")
    touched = False
    for col, spec in columns.items():
        if not isinstance(spec, dict) or not {"unit", "by_row"} <= spec.keys() <= {
            "unit",
            "by_row",
            "fixed",
        }:
            raise ValueError(f"Unexpected column binding for {path.name}/{col}")
        unit, by_row = spec["unit"], spec["by_row"]
        fixed = spec.get("fixed", {})
        # A reference compared with itself can be a declared constant. Unknown new
        # categories in a bound column must not silently retain an old/manual number.
        if (
            not isinstance(by_row, dict)
            or not by_row
            or not isinstance(fixed, dict)
            or set(by_row) & set(fixed)
            or (set(by_row) | set(fixed)) != set(lookup)
        ):
            raise ValueError(
                f"Missing author table keys or ambiguous binding for {path.name}/{col}"
            )
        for label, constant in fixed.items():
            if type(constant) not in (int, float) or float(lookup[label][col]) != constant:
                raise ValueError(f"Fixed author cell differs: {path.name}/{label}/{col}")
        for label, eid in by_row.items():
            metric = metrics.get(eid)
            if metric is None or metric["unit"] != unit:
                raise ValueError(
                    f"Unknown result or unit mismatch: {path.name}/{label}/{col}/{eid}"
                )
            value = metric["raw_value"]
            if metric["ref"].get("percentage", False):
                value *= 100  # Ratio -> percent; a native % quantity is not scaled twice.
            try:
                same = float(lookup[label][col]) == value
            except ValueError:
                same = False
            if not same:
                lookup[label][col] = repr(value)
                touched = True
    if touched:
        with path.open("w", encoding=encoding, newline="") as stream:
            writer = csv.DictWriter(
                stream, names, lineterminator="\r\n" if b"\r\n" in raw else "\n"
            )
            writer.writeheader()
            writer.writerows(rows)


def _prepare_recipes(root, data, metrics, revised_definitions):
    raw = _read(_asset(root, "figure-recipes.json"))
    if not isinstance(raw, list) or not raw or not all(isinstance(r, dict) for r in raw):
        raise ValueError("Declare at least one explicitly trusted local figure recipe")
    recipes = _definitions([{k: v for k, v in r.items() if k != "result_tables"} for r in raw])
    figures = {f.id: f for f in data.figures}
    protected = {
        name.casefold()
        for name in (
            "input.json",
            "draft.json",
            "figure-recipes.json",
            "reading-relations.json",
            *data.source_files,
        )
    }
    protected.update(r["script"].casefold() for r in recipes)
    figure_paths = {_relative_name(f.path).casefold() for f in data.figures}
    patches, figure_ids = {}, set()
    for r, declared in zip(recipes, raw, strict=True):
        figure = figures.get(r.get("figure_id"))
        if not figure or r.get("section_id") != data.section_id or figure.id in figure_ids:
            raise ValueError("Each linked recipe must own one distinct figure in this section")
        figure_ids.add(figure.id)
        path = _relative_name(figure.path)
        outputs = {name.casefold() for name in r["outputs"]}
        if path not in r["outputs"] or outputs & ((figure_paths - {path.casefold()}) | protected):
            raise ValueError(
                f"Figure {figure.id}: declare its own preview, not other figures or sources"
            )
        for b in declared.get("result_tables", []):
            name = _relative_name(b["path"])
            if (
                name not in r["inputs"]
                or Path(name).suffix.lower() != ".csv"
                or name.casefold() in protected
            ):
                raise ValueError("A result table must be a separate declared CSV recipe input")
            if name in patches and patches[name] != b:
                raise ValueError(f"Conflicting result bindings for {name}")
            patches[name] = b
            for column in b["columns"].values():
                if set(column["by_row"].values()) & revised_definitions:
                    raise ValueError(
                        f"{name}: physical definition changed. Reconcile the author's figure "
                        "labels, display and text before establishing a new baseline."
                    )
    for name, binding in patches.items():
        _patch_table(_asset(root, name), binding, metrics)
    return recipes


def _affected(draft, evidence_ids, images):
    """Report local readers of changed results/images, not every paragraph in a section."""
    changed = set(evidence_ids)
    viewed = set(images)

    def tokens(s):
        return set(re.findall(r"\{\{value:([A-Za-z0-9_.-]+)\}\}", s))

    readers = []
    counts = Counter()
    for p in draft["paragraphs"]:
        t = p["text"]
        key = p.get("paragraph_id") or paragraph_identity(t, counts[t])
        counts[t] += 1
        uses = (set(p["evidence_ids"]) | tokens(t)) & changed
        figs = set(p["figure_ids"]) & viewed
        if uses or figs:
            readers.append(
                {"kind": "paragraph", "id": key, "evidence": sorted(uses), "figures": sorted(figs)}
            )
    for fid, caption in draft["captions"].items():
        uses = tokens(caption) & changed
        if uses or fid in viewed:
            readers.append(
                {
                    "kind": "caption",
                    "id": fid,
                    "evidence": sorted(uses),
                    "figures": [fid] if fid in viewed else [],
                }
            )
    return readers


def _reading_relations(root, draft, metrics):
    """Check comparisons explicitly supplied by the host. Never infer physical causation."""
    path = root / "reading-relations.json"
    if not path.exists():
        return []
    targets = {
        ("caption", k): set(re.findall(r"\{\{value:([A-Za-z0-9_.-]+)\}\}", v))
        for k, v in draft["captions"].items()
    }
    for p in draft["paragraphs"]:
        if p.get("paragraph_id"):
            targets["paragraph", p["paragraph_id"]] = set(p["evidence_ids"])
    ops = {
        "<": operator.lt,
        ">": operator.gt,
        "<=": operator.le,
        ">=": operator.ge,
        "==": operator.eq,
    }
    confirmed = []
    for rel in _read(path):
        target = (rel["kind"], rel["id"])
        left, right = rel["left"], rel["right"]
        ids = targets.get(target)
        if (
            ids is None
            or not {left, right} <= metrics.keys()
            or rel["op"] not in ops
            or (target[0] == "paragraph" and not {left, right} <= ids)
        ):
            raise ValueError(
                f"Invalid reading relation for {target}: check target, evidence and operator"
            )
        a, b = metrics[left], metrics[right]
        if a["unit"] != b["unit"] or bool(a["ref"].get("percentage")) != bool(
            b["ref"].get("percentage")
        ):
            raise ValueError(f"Incompatible reading relation units for {target}: {left}, {right}")
        if not ops[rel["op"]](a["raw_value"], b["raw_value"]):
            raise ValueError(
                f"Revise {target[0]} '{target[1]}': {left} ({a['value']} {a['unit']}) "
                f"is no longer {rel['op']} {right} ({b['value']} {b['unit']}). "
                "No new build published; update the interpretation on the author's current text."
            )
        confirmed.append(rel)
    return confirmed


def refresh_section(
    workspace: Path, output: Path, *, baseline: Path | None = None, docx=False
) -> dict:
    """Explicitly execute the current, trusted local scripts in a new section workspace.

    baseline names a previous output, not a mutable source workspace. A changed
    value is rebound, not a license to rewrite its interpretation. The returned
    readers identify the captions/paragraphs to reread. Outputs are candidates.
    """
    workspace, output = Path(workspace).resolve(), Path(output).resolve()
    baseline = Path(baseline).resolve() if baseline is not None else None
    for src in (workspace, baseline):
        if src is not None and (output.is_relative_to(src) or src.is_relative_to(output)):
            raise ValueError("Use a fresh output outside the current workspace and baseline")
    previous = _read(_asset(baseline, "refresh.json")) if baseline else None
    with _stage(output) as staged:
        root = staged / "workspace"
        shutil.copytree(workspace, root)
        data = _load_input(root / "input.json", check_images=False)
        source_digests = {name: source_sha256(_asset(root, name)) for name in data.source_files}
        # Use the saved values for a prose/style-only return, but only when the complete
        # input declaration and all its source bytes still describe the same calculation.
        same_inputs = bool(
            previous
            and source_digests == previous.get("source_digests")
            and data.model_dump() == previous.get("section_input")
            and (baseline / "section/table-results.json").is_file()
        )
        draft_path = _asset(root, "draft.json")
        draft = _read(draft_path)
        if previous is not None and previous["section_id"] != data.section_id:
            raise ValueError("The baseline belongs to a different section")
        reports = (
            _read(_asset(baseline, "section/table-results.json"))
            if same_inputs
            else _calculate_sources(data, root, write=False)
        )
        metrics, definitions = _metrics(data, root, reports)
        redefined = set()
        if previous:
            for k, v in metrics.items():
                old = previous["results"].get(k)
                if not old:
                    continue
                if (
                    old["unit"] != v["unit"]
                    or old["ref"] != v["ref"]
                    or any(
                        definitions.get(c) != previous["definitions"].get(c)
                        for c in v["calculations"]
                    )
                ):
                    redefined.add(k)
        relations = _reading_relations(root, draft, metrics)
        recipes = _prepare_recipes(root, data, metrics, redefined)
        statuses = execute_figure_recipes(
            root,
            recipes,
            baseline_root=baseline / "workspace" if baseline else None,
            baseline_states=previous["figure_recipes"] if previous else None,
            baseline_definitions=previous["recipes"] if previous else None,
        )
        # A source workspace can itself be the last build's mutable workspace;
        # compare with the frozen rendered section, never with today's author edits.
        changed_images = []
        prior_figures = {}
        if baseline:
            prior_figures = {
                f["id"]: f for f in _read(_asset(baseline, "section/section.json"))["figures"]
            }
        for f in data.figures:
            before = prior_figures.get(f.id)
            current = _asset(root, f.path)
            if baseline:
                different = (
                    not before
                    or current.read_bytes()
                    != _asset(baseline / "section", before["path"]).read_bytes()
                )
            else:
                initial = workspace / f.path
                different = not initial.is_file() or current.read_bytes() != initial.read_bytes()
            if different:
                changed_images.append(f.id)
                draft["image_observations"][f.id] = "not-viewed"
                draft.get("observation_notes", {}).pop(f.id, None)
        if draft != _read(draft_path):
            _write(draft_path, draft)
        changes = {}
        if previous:
            for key in sorted(metrics.keys() | previous["results"].keys()):
                a = previous["results"].get(key)
                b = metrics.get(key)
                if a == b and key not in redefined:
                    continue
                changes[key] = {"before": a, "after": b}
        readers = _affected(draft, changes, changed_images)
        _assemble_section(root, draft_path, staged / "section", computed_reports=reports)
        if docx:
            export_section_docx(
                staged / "section", staged / "section.docx", layout="near-reference"
            )
        result = {
            "section_id": data.section_id,
            "results": metrics,
            "definitions": definitions,
            "recipes": recipes,
            "figure_recipes": statuses,
            "changed_results": changes,
            "changed_images": changed_images,
            "unlinked_figures": sorted(
                {f.id for f in data.figures} - {r["figure_id"] for r in recipes}
            ),
            "readers_to_review": readers,
            "checked_relations": relations,
            "section_input": data.model_dump(),
            "source_digests": source_digests,
            "calculation": "reused" if same_inputs else "computed",
        }
        _write(staged / "refresh.json", result)
    return result
