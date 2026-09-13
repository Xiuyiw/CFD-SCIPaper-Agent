"""Small, local literature workspace; excerpt checks establish location, not truth.

CSL JSON metadata is retained, not completed from the web. Reference labels are
neutral metadata summaries, not a CSL citation-style implementation.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path, PureWindowsPath

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_STATUSES = {"supported", "unsupported", "needs-review"}


def _nonblank(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")
    return value


def _relative_file(base: Path, value, field: str) -> Path:
    _nonblank(value, field)
    portable = value.replace("\\", "/")
    path = Path(portable)
    windows = PureWindowsPath(value)
    if path.is_absolute() or windows.drive or windows.root or ".." in path.parts:
        raise ValueError(f"{field} must be a relative path without parent traversal")
    result = (base / path).resolve()
    if not result.is_relative_to(base.resolve()):
        raise ValueError(f"{field} must remain inside the literature directory")
    if not result.is_file():
        raise ValueError(f"{field} file not found: {value}")
    return result


def _json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _doi(value):
    value = _nonblank(value, "DOI").strip().casefold()
    return re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", value).strip()


def _normalized(value):
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in value.items()}
    return value


def _year(record):
    issued = record.get("issued", {})
    parts = issued.get("date-parts", []) if isinstance(issued, dict) else []
    if parts and isinstance(parts[0], list) and parts[0]:
        year = parts[0][0]
        if isinstance(year, (int, str)) and not isinstance(year, bool):
            return str(year).strip()
    return ""


def _fallback_key(record):
    title = record.get("title")
    authors = record.get("author")
    year = _year(record)
    if not title or not authors or not year:
        return None
    if not all(
        isinstance(author, dict) and any(author.get(key) for key in ("family", "literal"))
        for author in authors
    ):
        return None
    return (
        _normalized(title),
        json.dumps(_normalized(authors), sort_keys=True, ensure_ascii=False),
        year,
    )


def _merge(target, incoming):
    for key, value in incoming.items():
        if key == "id":
            continue
        if key in target and _normalized(target[key]) != _normalized(value):
            raise ValueError(
                f"Conflicting bibliography metadata {key!r}: "
                f"{target['id']!r} and {incoming['id']!r}"
            )
        if key not in target:
            target[key] = copy.deepcopy(value)


def _bibliography(path):
    if path.suffix.lower() == ".bib":
        pandoc = shutil.which("pandoc")
        if not pandoc:
            raise ValueError(
                "BibLaTeX import requires optional Pandoc on PATH; "
                "install Pandoc or export your bibliography as CSL JSON."
            )
        try:
            result = subprocess.run(
                [pandoc, "-f", "biblatex", "-t", "csljson", str(path)],
                check=True,
                capture_output=True,
                encoding="utf-8",
                timeout=60,
            )
            data = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise ValueError(
                "Pandoc could not convert the bibliography; check the BibLaTeX file "
                "or export CSL JSON."
            ) from exc
    elif path.suffix.lower() == ".json":
        data = _json(path)
    else:
        raise ValueError("bibliography must be a CSL JSON (.json) or BibLaTeX (.bib) file")
    if not isinstance(data, list):
        raise ValueError("CSL JSON bibliography must be a list of records")
    ids = set()
    for record in data:
        if not isinstance(record, dict):
            raise ValueError("Each bibliography record must be an object")
        rid = _nonblank(record.get("id"), "bibliography id")
        if rid in ids:
            raise ValueError(f"Duplicate bibliography id: {rid}")
        ids.add(rid)
        if "DOI" in record:
            record["DOI"] = _doi(record["DOI"])
            _nonblank(record["DOI"], "DOI")
        for key in ("title", "container-title", "URL"):
            if key in record and not isinstance(record[key], str):
                raise ValueError(f"Bibliography {key} must be a string: {rid}")
        for key in ("volume", "issue", "page"):
            if key in record and (
                not isinstance(record[key], (str, int, float)) or isinstance(record[key], bool)
            ):
                raise ValueError(f"Bibliography {key} must be a string or number: {rid}")
        if "author" in record and (
            not isinstance(record["author"], list)
            or not all(isinstance(author, dict) for author in record["author"])
        ):
            raise ValueError(f"Bibliography author must be a list of objects: {rid}")
    return data


def _deduplicate(records):
    # DOI groups first, then exact complete bibliographic keys. Original order
    # determines canonical IDs even if an earlier record has no DOI.
    groups = []
    doi_groups = {}
    for record in records:
        doi = record.get("DOI")
        if doi and doi in doi_groups:
            doi_groups[doi].append(record)
        else:
            group = [record]
            groups.append(group)
            if doi:
                doi_groups[doi] = group
    for group in groups:
        merged = copy.deepcopy(group[0])
        for record in group[1:]:
            _merge(merged, record)
        # Combined metadata can identify a DOI group whose first item is sparse.
        group.append(merged)
    keys = {}
    for index, group in enumerate(groups):
        key = _fallback_key(group[-1])
        if key is not None:
            keys.setdefault(key, []).append(index)
    discarded = set()
    for indices in keys.values():
        dois = {groups[index][-1].get("DOI") for index in indices} - {None}
        if len(dois) > 1:
            continue
        first = indices[0]
        for index in indices[1:]:
            groups[first][-1:] = groups[index][:-1] + groups[first][-1:]
            _merge(groups[first][-1], groups[index][-1])
            discarded.add(index)
    canonical, aliases = [], {}
    for index, group in enumerate(groups):
        if index in discarded:
            continue
        record = group[-1]
        canonical.append(record)
        aliases.update({item["id"]: record["id"] for item in group[:-1]})
    return canonical, aliases


def load_literature(path: Path) -> dict:
    """Load local metadata and author-assessed supports; verify exact excerpts.

    All statuses remain available to the host. ``supported`` is supplied by the
    author/host, not inferred by this loader from substring matching.
    """
    path = Path(path)
    data = _json(path)
    if not isinstance(data, dict):
        raise ValueError("Literature input must be an object")
    bibliography = _relative_file(path.parent, data.get("bibliography"), "bibliography")
    records, aliases = _deduplicate(_bibliography(bibliography))
    saved_aliases = data.get("aliases", {})
    if not isinstance(saved_aliases, dict):
        raise ValueError("aliases must be an object mapping original IDs to canonical IDs")
    for original, target in saved_aliases.items():
        _nonblank(original, "alias id")
        _nonblank(target, "alias target")
        if target not in aliases:
            raise ValueError(f"Unknown alias target: {target}")
        canonical = aliases[target]
        if original in aliases and aliases[original] != canonical:
            raise ValueError(f"Conflicting alias: {original}")
        aliases[original] = canonical
    supports = data.get("supports")
    if not isinstance(supports, list):
        raise ValueError("supports must be a list")
    seen = set()
    for support in supports:
        if not isinstance(support, dict):
            raise ValueError("Each literature support must be an object")
        for key in ("section_id", "evidence_id"):
            if not _TOKEN.fullmatch(_nonblank(support.get(key), key)):
                raise ValueError(f"{key} must be a safe token ID")
        identity = (support["section_id"], support["evidence_id"])
        if identity in seen:
            raise ValueError(f"Duplicate literature support evidence: {identity}")
        seen.add(identity)
        for key in ("locator", "excerpt", "claim", "role", "reference_id", "status"):
            _nonblank(support.get(key), key)
        if support["status"] not in _STATUSES:
            raise ValueError(
                "Literature support status must be supported, unsupported, needs-review"
            )
        reference = support["reference_id"]
        if reference not in aliases:
            raise ValueError(f"Unknown support reference_id: {reference}")
        support["reference_id"] = aliases[reference]
        source = _relative_file(path.parent, support.get("source"), "source")
        if source.suffix.lower() not in {".txt", ".md"}:
            raise ValueError("Literature source must be a UTF-8 .txt or .md file")
        text = source.read_bytes().decode("utf-8-sig")
        if support["excerpt"] not in text:
            raise ValueError(f"Literature excerpt not found exactly in source: {support['source']}")
    return {**data, "records": records, "aliases": aliases, "supports": supports}


def copy_literature(path: Path, output_dir: Path) -> Path:
    """Copy a rereadable local workspace to a new directory, preserving source bytes."""
    path, output_dir = Path(path), Path(output_dir)
    if output_dir.exists():
        raise ValueError(f"Literature output directory already exists: {output_dir}")
    library = load_literature(path)
    output_dir.mkdir(parents=True)
    (output_dir / "sources").mkdir()
    copied = {}
    for support in library["supports"]:
        source = _relative_file(path.parent, support["source"], "source")
        if source not in copied:
            target = Path("sources") / f"source-{len(copied) + 1:04d}{source.suffix.lower()}"
            shutil.copyfile(source, output_dir / target)
            copied[source] = target.as_posix()
        support["source"] = copied[source]
    (output_dir / "bibliography.json").write_text(
        json.dumps(library.pop("records"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    library["bibliography"] = "bibliography.json"
    destination = output_dir / "literature.json"
    destination.write_text(
        json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def _reference_label(record):
    names = []
    for author in record.get("author", []):
        if author.get("literal"):
            names.append(str(author["literal"]))
        else:
            name = " ".join(str(author[key]) for key in ("given", "family") if author.get(key))
            if name:
                names.append(name)
    pieces = ["; ".join(names), _year(record), record.get("title", "")]
    pieces.extend(
        str(record.get(key, "")) for key in ("container-title", "volume", "issue", "page")
    )
    if record.get("DOI"):
        pieces.append(f"doi:{record['DOI']}")
    elif record.get("URL"):
        pieces.append(record["URL"])
    return (
        ". ".join(piece.strip() for piece in pieces if piece.strip()) or f"reference:{record['id']}"
    )


def literature_evidence(library: dict, section_id: str) -> list[dict]:
    """Produce citation evidence only for supports already marked supported."""
    records = {record["id"]: record for record in library["records"]}
    evidence = []
    for support in library["supports"]:
        if support["section_id"] != section_id or support["status"] != "supported":
            continue
        record = records[support["reference_id"]]
        evidence.append(
            {
                "id": support["evidence_id"],
                "kind": "literature",
                "text": _reference_label(record),
                "source": f"doi:{record['DOI']}"
                if record.get("DOI")
                else f"reference:{record['id']}",
            }
        )
    return evidence
