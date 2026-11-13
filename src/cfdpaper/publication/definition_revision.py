"""Show physical-definition changes and apply a host's edits to the affected readers only."""

from collections import Counter
from copy import deepcopy

from cfdpaper.publication.document_blocks import paragraph_identity


def mechanism_context(questions, data, metrics, definitions):
    """Locate the declared diagnostics across their actual domains, not just the revised rows."""
    records = {e.id: e for e in data.evidence}
    result = []
    for q in questions:
        keys = q.get("diagnostics")
        if not isinstance(q.get("question"), str) or not q["question"].strip():
            raise ValueError("A mechanism question requires the research question")
        if (
            not isinstance(keys, list)
            or not keys
            or not all(isinstance(k, str) for k in keys)
            or set(keys) - (set(metrics) | set(definitions))
        ):
            raise ValueError("Mechanism questions must locate existing diagnostics")
        selected = {
            k: v for k, v in metrics.items() if k in keys or set(keys) & set(v["calculations"])
        }
        if not selected:
            raise ValueError("No bound results for the selected mechanism diagnostics")
        result.append(
            {
                **q,
                "located_results": {
                    k: {
                        "value": v["value"],
                        "unit": v["unit"],
                        "group": v["ref"].get("group"),
                        "domains": sorted({definitions[c]["domain"] for c in v["calculations"]}),
                        "role": records[k].evidence_role,
                        "source": records[k].source,
                        **({"operands": v["operands"]} if "operands" in v else {}),
                    }
                    for k, v in selected.items()
                },
            }
        )
    return result


def _targets(draft):
    targets, occurrences = {}, Counter()
    for p in draft["paragraphs"]:
        text = p["text"]
        key = p.get("paragraph_id") or paragraph_identity(text, occurrences[text])
        occurrences[text] += 1
        if ("paragraph", key) in targets:
            raise ValueError(f"Ambiguous paragraph identity: {key}")
        targets["paragraph", key] = p
    targets.update({("caption", key): val for key, val in draft["captions"].items()})
    return targets


def describe_changes(
    previous,
    current,
    definitions,
    revised,
    draft,
    recipes,
    figures,
    readers,
    source_digests,
    relations,
):
    """Retain named source operands and scopes, including comparisons with equal rounded values."""
    old_defs = previous["definitions"]
    diffs = {}
    for key in sorted(set(definitions) | set(old_defs)):
        old, new = old_defs.get(key, {}), definitions.get(key, {})
        fields = {
            f: {"before": old.get(f), "after": new.get(f)}
            for f in sorted(set(old) | set(new))
            if old.get(f) != new.get(f)
        }
        if fields:
            diffs[key] = fields
    figure_inputs = {}
    for r in recipes:
        uses = {
            eid
            for b in r.get("result_tables", [])
            for col in b["columns"].values()
            for eid in col["by_row"].values()
        }
        # Also catch raw-field recipes with declared dependencies but without a summary CSV.
        raw_inputs = set(r.get("inputs", []))
        affected = {
            k
            for k in revised
            if k in uses
            or any(
                definitions.get(c, {}).get("source") in raw_inputs
                for c in current[k]["calculations"]
            )
        }
        if affected:
            figure_inputs[r["figure_id"]] = sorted(affected)
    targets = _targets(draft)
    text_items = []
    for item in readers(draft, revised, figure_inputs):
        key = (item["kind"], item["id"])
        obj = targets[key]
        text_items.append(
            {**item, "before": obj["text"] if key[0] == "paragraph" else obj, "after": None}
        )
    # A formula or a table can be a reader even without a paragraph referring to it.
    objects = []
    for kind, field in (("table", "table_id"), ("equation", "equation_id")):
        for obj in draft.get(kind + "s", []):
            if set(obj.get("evidence_ids", [])) & revised:
                objects.append(
                    {"kind": kind, "id": obj[field], "before": deepcopy(obj), "after": None}
                )
    result_pairs = {
        k: {"before": previous["results"][k], "after": current[k]} for k in sorted(revised)
    }
    return {
        "basis": {
            "section_id": previous["section_id"],
            "definition_changes": diffs,
            "results": result_pairs,
            "source_versions": source_digests,
            "reading_relations": relations,
        },
        "figures": [
            {
                "id": f.id,
                "description": f.description,
                "evidence": figure_inputs[f.id],
                "reading": None,
            }
            for f in figures
            if f.id in figure_inputs
        ],
        "readers": text_items,
        "objects": objects,
    }


def reconcile(draft, expected, supplied):
    """Keep author text and formatting on no-change decisions; reject stale/partial patches."""
    if not isinstance(supplied, dict) or supplied.get("basis") != expected["basis"]:
        raise ValueError(
            "Scientific basis changed since inspection; inspect the current change again"
        )
    targets = _targets(draft)
    for group, answer in (("figures", "reading"), ("readers", "after"), ("objects", "after")):

        def identity(item):
            return item.get("kind"), item["id"]

        items = supplied.get(group, [])
        if not isinstance(items, list) or any(
            not isinstance(i, dict) or not isinstance(i.get("id"), str) for i in items
        ):
            raise ValueError(f"Malformed {group} in definition reconciliation")
        entries = {identity(i): i for i in items}
        wanted = expected[group]
        if len(entries) != len(items) or set(entries) != {identity(i) for i in wanted}:
            raise ValueError(f"Incomplete or unrelated {group} in definition reconciliation")
        for item in wanted:
            key = identity(item)
            choice = entries[key]
            if {k: v for k, v in choice.items() if k != answer} != {
                k: v for k, v in item.items() if k != answer
            }:
                raise ValueError(
                    f"Current {group} target changed: {item['id']}; preserve the author edit"
                )
            val = choice.get(answer)
            if group == "objects":
                from cfdpaper.publication.elements import SectionEquation, SectionTable

                field = f"{key[0]}_id"
                if not isinstance(val, dict) or val.get(field) != key[1]:
                    raise ValueError(f"Supply the retained or revised {key[0]} with ID {key[1]}")
                model = SectionTable if key[0] == "table" else SectionEquation
                model.model_validate(val)
                seq = draft[key[0] + "s"]
                pos = next(i for i, obj in enumerate(seq) if obj[field] == key[1])
                seq[pos] = val
                continue
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Provide the actual {answer} for {group}/{item['id']}")
            if group == "readers":
                if key[0] == "paragraph":
                    p = targets[key]
                    if val != p["text"] and p.get("formatting"):
                        raise ValueError(
                            f"Reconcile author character formatting in paragraph {key[1]} first"
                        )
                    p["text"] = val
                    p["paragraph_id"] = key[1]
                else:
                    draft["captions"][key[1]] = val
