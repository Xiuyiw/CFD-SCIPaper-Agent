"""Optional Pandoc citeproc adapter for first-citation-order numeric references."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def _unsupported(detail):
    return ValueError(f"Unsupported CSL output: {detail}; use a compatible numeric CSL style")


def _run(pandoc, args, text, directory):
    try:
        process = subprocess.run(
            [pandoc, *args],
            input=text,
            encoding="utf-8",
            capture_output=True,
            check=True,
            timeout=60,
            cwd=directory,
        )
        return json.loads(process.stdout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Pandoc citation formatting timed out; check the local CSL style"
        ) from exc
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise RuntimeError(
            "Pandoc could not format the bibliography; check the CSL file and reference metadata"
        ) from exc


def _append(runs, text, flags):
    if not text:
        return
    if runs and {key: value for key, value in runs[-1].items() if key != "text"} == flags:
        runs[-1]["text"] += text
    else:
        runs.append({"text": text, **flags})


def _inlines(nodes, runs, flags, labels):
    for node in nodes:
        kind, content = node["t"], node.get("c")
        if kind == "Str":
            _append(runs, content, flags)
        elif kind in {"Space", "SoftBreak", "LineBreak"}:
            _append(runs, "\n" if kind == "LineBreak" else " ", flags)
        elif kind in {"Emph", "Strong"}:
            _inlines(content, runs, {**flags, "italic" if kind == "Emph" else "bold": True}, labels)
        elif kind == "Link":
            _inlines(content[1], runs, flags, labels)
        elif kind == "Span":
            attr, children = content
            if "csl-indent" in attr[1]:
                raise _unsupported("indented bibliography content")
            if "csl-left-margin" in attr[1]:
                margin = []
                _inlines(children, margin, {}, [])
                labels.append("".join(run["text"] for run in margin).strip())
                continue
            local = dict(flags)
            for key, value in attr[2]:
                if key != "style":
                    continue
                for declaration in value.split(";"):
                    if not declaration.strip():
                        continue
                    name, _, setting = declaration.partition(":")
                    name, setting = name.strip(), setting.strip()
                    flag = {"font-style": "italic", "font-weight": "bold"}.get(name)
                    if flag is None or setting not in {"normal", "italic", "bold"}:
                        raise _unsupported(f"span formatting {declaration!r}")
                    if setting == "normal":
                        local.pop(flag, None)
                    else:
                        local[flag] = True
            if "csl-block" in attr[1]:
                _append(runs, "\n", {})
            _inlines(children, runs, local, labels)
            if "csl-block" in attr[1]:
                _append(runs, "\n", {})
        else:
            raise _unsupported(f"inline element {kind}")


def _blocks(blocks, runs, labels):
    for index, block in enumerate(blocks):
        if index:
            _append(runs, "\n", {})
        if block["t"] in {"Para", "Plain"}:
            _inlines(block["c"], runs, {}, labels)
        elif block["t"] == "Div":
            if "csl-indent" in block["c"][0][1]:
                raise _unsupported("indented bibliography content")
            _blocks(block["c"][1], runs, labels)
        else:
            raise _unsupported(f"bibliography block {block['t']}")


def _entry(entry, number):
    runs, labels = [], []
    _blocks(entry["c"][1], runs, labels)
    text = "".join(run["text"] for run in runs)
    label = rf"(?:\[\s*{number}\s*\]|\(\s*{number}\s*\)|{number}[.)]?)"
    if labels:
        if len(labels) != 1 or not re.fullmatch(label, labels[0]):
            raise _unsupported("bibliography label does not match citation order")
        remove = len(text) - len(text.lstrip())
    else:
        prefix = re.match(
            rf"^\s*(?:\[{number}\]|\({number}\)|{number}[.)](?=\s)|{number}(?=\s))\s*", text
        )
        if prefix is None:
            raise _unsupported("bibliography requires a leading numeric label")
        remove = prefix.end()
    trimmed = []
    for run in runs:
        fragment = run["text"][remove:]
        remove = max(0, remove - len(run["text"]))
        _append(trimmed, fragment, {key: value for key, value in run.items() if key != "text"})
    while trimmed and not trimmed[-1]["text"].rstrip():
        trimmed.pop()
    if trimmed:
        trimmed[-1]["text"] = trimmed[-1]["text"].rstrip()
    text = "".join(run["text"] for run in trimmed)
    if not text.strip():
        raise _unsupported("empty formatted bibliography entry")
    return {"id": entry["c"][0][0][4:], "text": text, "runs": trimmed}


def _extract(document, ids):
    citations, entries = [], []
    for block in document["blocks"]:
        if block["t"] == "Para" and len(block["c"]) == 1 and block["c"][0]["t"] == "Cite":
            citation, rendered = block["c"][0]["c"]
            runs = []
            _inlines(rendered, runs, {}, [])
            if len(citation) != 1:
                raise _unsupported("unexpected citation group")
            citations.append((citation[0]["citationId"], "".join(r["text"] for r in runs)))
        elif block["t"] == "Div" and block["c"][0][0] == "refs":
            entries.extend(block["c"][1])
        else:
            raise _unsupported("expected citation paragraphs and a bibliography Div")
    if citations != [(rid, f"[{number}]") for number, rid in enumerate(ids, 1)]:
        raise _unsupported("citations must be bracket numeric [1]...[N] in supplied record order")
    if any(e["t"] != "Div" or "csl-entry" not in e["c"][0][1] for e in entries):
        raise _unsupported("expected one csl-entry Div per reference")
    if [entry["c"][0][0] for entry in entries] != [f"ref-{rid}" for rid in ids]:
        raise _unsupported("missing, duplicate, or reordered bibliography IDs")
    return [_entry(entry, number) for number, entry in enumerate(entries, 1)]


def format_numeric_bibliography(records: list[dict], style: Path) -> list[dict]:
    """Use local Pandoc/CSL; return unnumbered text and italic/bold runs in input order.

    Supports bracket numeric citations and leading numbered bibliography entries.
    Unsupported typography/structure fails rather than being silently flattened.
    """
    ids = [record.get("id") for record in records]
    if any(not isinstance(rid, str) or not rid.strip() for rid in ids) or len(set(ids)) != len(ids):
        raise ValueError("Bibliography records require unique nonblank string IDs")
    style = Path(style).resolve()
    if not style.is_file():
        raise ValueError(f"CSL style file not found: {style}")
    try:
        root = ET.parse(style).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ValueError("Invalid CSL style; supply a standalone CSL XML file") from exc
    if any(node.get("rel") == "independent-parent" for node in root.iter()):
        raise ValueError("Dependent CSL style: supply its standalone parent CSL file locally")
    if not records:
        return []
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError(
            "CSL formatting requires Pandoc on PATH; install Pandoc or omit the style"
        )
    with tempfile.TemporaryDirectory(prefix="cfdpaper-citeproc-") as directory:
        bibliography = Path(directory) / "bibliography.json"
        bibliography.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        document = _run(pandoc, ["-f", "markdown", "-t", "json"], "", directory)
        document["meta"] = {"link-citations": {"t": "MetaBool", "c": False}}
        document["blocks"] = [
            {
                "t": "Para",
                "c": [
                    {
                        "t": "Cite",
                        "c": [
                            [
                                {
                                    "citationId": rid,
                                    "citationPrefix": [],
                                    "citationSuffix": [],
                                    "citationMode": {"t": "NormalCitation"},
                                    "citationNoteNum": 0,
                                    "citationHash": 0,
                                }
                            ],
                            [],
                        ],
                    }
                ],
            }
            for rid in ids
        ]
        formatted = _run(
            pandoc,
            [
                "-f",
                "json",
                "-t",
                "json",
                "--citeproc",
                "--bibliography",
                str(bibliography),
                "--csl",
                str(style),
            ],
            json.dumps(document, ensure_ascii=False),
            directory,
        )
    try:
        return _extract(formatted, ids)
    except (KeyError, TypeError, IndexError) as exc:
        raise _unsupported("malformed Pandoc JSON structure") from exc
