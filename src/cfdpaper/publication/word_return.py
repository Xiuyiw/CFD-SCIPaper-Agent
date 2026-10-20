"""Bounded author return for generated DOCX, with stable editable SDT anchors.

No XML data binding or document protection is used. The original return file is
read-only; unsupported objects and unresolved edits are reported, not flattened.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path

_STATE_NS = "urn:cfdpaper:word-return:1"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_KINDS = {"paragraph", "heading", "caption", "equation", "figure", "table", "keywords", "reference"}


def _tag(key: str) -> str:
    if not isinstance(key, str) or not key:
        raise ValueError("Anchor key must be a nonempty stable ID")
    return "cfd_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def start_anchor(paragraph, key: str) -> str:
    """Start a rich-text anchor; call end_anchor after adding actual content.

    A block key wraps the paragraph at end; ``block_id::span_id`` wraps just
    the intervening inline content. Keep the paragraph reference: python-docx's
    Document.paragraphs does not enumerate paragraphs nested in block SDTs.
    """
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    name = _tag(key)
    sdt, props = OxmlElement("w:sdt"), OxmlElement("w:sdtPr")
    tag, identifier = OxmlElement("w:tag"), OxmlElement("w:id")
    tag.set(qn("w:val"), name)
    used = paragraph._p.getroottree().getroot().xpath(".//w:sdtPr/w:id/@w:val")
    identifier.set(
        qn("w:val"), str(max([int(v) for v in used if v.lstrip("-").isdigit()] + [0]) + 1)
    )
    props.extend([tag, identifier, OxmlElement("w:richText")])
    sdt.extend([props, OxmlElement("w:sdtContent")])
    paragraph._p.append(sdt)
    return name


def end_anchor(paragraph, key: str) -> None:
    """Finish the block/inline SDT started on this paragraph."""
    name = _tag(key)
    matches = [s for s in paragraph._p if s.tag == f"{{{_W}}}sdt" and _sdt_tag(s) == name]
    if len(matches) != 1:
        raise ValueError(f"Absent or ambiguous open anchor: {key}")
    sdt = matches[0]
    content = sdt.find(f"{{{_W}}}sdtContent")
    if "::" in key:
        while sdt.getnext() is not None:
            content.append(sdt.getnext())
    else:
        paragraph._p.remove(sdt)
        paragraph._p.addprevious(sdt)
        content.append(paragraph._p)


def wrap_anchor(element, key: str) -> str:
    """Wrap an already-created paragraph or native table with one block SDT."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    node = getattr(element, "_p", getattr(element, "_tbl", element))
    if node.tag not in {f"{{{_W}}}p", f"{{{_W}}}tbl"} or "::" in key:
        raise ValueError("wrap_anchor requires a paragraph/table and a block ID")
    name = _tag(key)
    sdt, props = OxmlElement("w:sdt"), OxmlElement("w:sdtPr")
    tag, identifier = OxmlElement("w:tag"), OxmlElement("w:id")
    tag.set(qn("w:val"), name)
    used = [n.get(qn("w:val")) for n in node.getroottree().getroot().iter(qn("w:id"))]
    identifier.set(qn("w:val"), str(max([int(v) for v in used if v and v.isdigit()] + [0]) + 1))
    props.extend([tag, identifier, OxmlElement("w:richText")])
    content = OxmlElement("w:sdtContent")
    sdt.extend([props, content])
    node.addprevious(sdt)
    content.append(node)
    return name


def _sdt_tag(element):
    tag = element.find(f"{{{_W}}}sdtPr/{{{_W}}}tag")
    return tag.get(f"{{{_W}}}val") if tag is not None else None


def _validate_state(state):
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != 1
        or not isinstance(state.get("baseline_id"), str)
        or not state["baseline_id"]
        or not isinstance(state.get("blocks"), list)
    ):
        raise ValueError("Word state requires schema_version 1, baseline_id and blocks")
    seen = set()
    for block in state["blocks"]:
        if (
            not isinstance(block, dict)
            or not isinstance(block.get("id"), str)
            or not block["id"]
            or block["id"] in seen
        ):
            raise ValueError("Word block IDs must be nonempty and unique")
        seen.add(block["id"])
        if block.get("kind") not in _KINDS:
            raise ValueError(f"Unsupported Word block kind: {block.get('kind')}")
        for field in ("section_id", "local_id", "text", "rendered_text"):
            if not isinstance(block.get(field), str):
                raise ValueError(f"Word block {block['id']} requires string {field}")
        span_ids = set()
        for span in block.get("spans", []):
            if (
                not isinstance(span, dict)
                or any(not isinstance(span.get(f), str) for f in ("id", "token", "text"))
                or not span["id"]
                or span["id"] in span_ids
            ):
                raise ValueError(f"Word block {block['id']} has invalid/duplicate spans")
            span_ids.add(span["id"])


def _plain(element):
    """Visible text, not field instructions or deleted-text revision content."""
    chunks = []

    def visit(node):
        if node.tag in {f"{{{_W}}}t", f"{{{_M}}}t"}:
            chunks.append(node.text or "")
            return
        if node.tag == f"{{{_W}}}tab":
            chunks.append("\t")
        elif node.tag in {f"{{{_W}}}br", f"{{{_W}}}cr"}:
            chunks.append("\n")
        elif node.tag == f"{{{_W}}}p" and chunks and chunks[-1] != "\n":
            chunks.append("\n")
        for child in node:
            visit(child)

    visit(element)
    return "".join(chunks)


def _element_positions(root):
    """Map each descendant to a text range; supports comments spanning runs."""
    positions, chunks, length = {}, [], 0

    def visit(node):
        nonlocal length
        start = length
        if node.tag in {f"{{{_W}}}t", f"{{{_M}}}t"}:
            value = node.text or ""
        elif node.tag == f"{{{_W}}}tab":
            value = "\t"
        elif node.tag in {f"{{{_W}}}br", f"{{{_W}}}cr"}:
            value = "\n"
        else:
            value = ""
        chunks.append(value)
        length += len(value)
        for child in node:
            visit(child)
        positions[node] = (start, length)

    visit(root)
    return "".join(chunks), positions


def _formatting(element):
    _, positions = _element_positions(element)
    records = []
    for run in element.iter(f"{{{_W}}}r"):
        start, end = positions[run]
        if start == end:
            continue
        props = run.find(f"{{{_W}}}rPr")
        record = {"start": start, "end": end}
        if props is not None:
            for field, tag in (("bold", "b"), ("italic", "i")):
                prop = props.find(f"{{{_W}}}{tag}")
                if prop is not None:
                    record[field] = prop.get(f"{{{_W}}}val", "true") not in {"0", "false", "off"}
            vertical = props.find(f"{{{_W}}}vertAlign")
            if vertical is not None:
                value = vertical.get(f"{{{_W}}}val")
                record["superscript"] = value == "superscript"
                record["subscript"] = value == "subscript"
        # Coalesce split runs with equal formatting; saving Word must not be an edit.
        if records and {k: v for k, v in records[-1].items() if k not in {"start", "end"}} == {
            k: v for k, v in record.items() if k not in {"start", "end"}
        }:
            records[-1]["end"] = end
        else:
            records.append(record)
    return [record for record in records if len(record) > 2]


def _normalize_paragraph_styles(records, styles):
    """Use display identity, not Word's locale-specific internal style IDs."""
    names = {style.style_id: style.name for style in styles}
    display_names = set(names.values())
    result = deepcopy(records)
    for record in result:
        attrs = record.get("pStyle")
        if not attrs or "name" in attrs:
            continue
        identifier = attrs.get("val", "")
        name = names.get(identifier)
        if name is None and identifier in display_names:
            name = identifier
        if name is None:
            # A pre-normalization generated baseline used e.g. Heading1. Word
            # may have replaced that ID with "1", while retaining Heading 1.
            matches = [
                value
                for value in display_names
                if value.replace(" ", "").casefold() == identifier.casefold()
            ]
            if len(matches) == 1:
                name = matches[0]
        if name is not None:
            record["pStyle"] = {"name": name}
    return result


def _paragraph_format(element, styles):
    result = []
    for paragraph in element.iter(f"{{{_W}}}p"):
        props = paragraph.find(f"{{{_W}}}pPr")
        record = {}
        if props is not None:
            for prop in props:
                name = prop.tag.rsplit("}", 1)[-1]
                if name in {"pStyle", "jc", "ind", "spacing", "keepNext", "keepLines"}:
                    record[name] = {k.rsplit("}", 1)[-1]: v for k, v in prop.attrib.items()}
        result.append(record)
    return _normalize_paragraph_styles(result, styles)


def _semantic_xml(element):
    """Ignore Word run splitting/formatting, retain equation structure/content."""
    local = element.tag.rsplit("}", 1)[-1]
    if local in {"rPr", "ctrlPr"}:
        return []
    children = [item for child in element for item in _semantic_xml(child)]
    merged_children = []
    for child in children:
        if isinstance(child, str) and merged_children and isinstance(merged_children[-1], str):
            merged_children[-1] += child
        else:
            merged_children.append(child)
    children = merged_children
    if local in {"r", "t"}:
        return ([element.text] if element.text else []) + children
    attrs = sorted((k, v) for k, v in element.attrib.items() if "rsid" not in k)
    return [
        [
            element.tag,
            attrs,
            element.text if element.text and element.text.strip() else "",
            children,
        ]
    ]


def _objects(element, document):
    from lxml import etree

    objects = []
    for node in element.iter():
        if node.tag in {f"{{{_M}}}oMath", f"{{{_M}}}oMathPara"}:
            if node.getparent().tag == f"{{{_M}}}oMathPara":
                continue
            objects.append({"kind": "math", "value": _semantic_xml(node)})
        elif node.tag == f"{{{_W}}}fldSimple":
            objects.append({"kind": "field", "value": [node.get(f"{{{_W}}}instr"), _plain(node)]})
        elif node.tag in {f"{{{_W}}}drawing", f"{{{_W}}}pict"}:
            media = []
            for item in node.iter():
                for attr in (f"{{{_R}}}embed", f"{{{_R}}}link", f"{{{_R}}}id"):
                    rid = item.get(attr)
                    if rid:
                        relation = document.part.rels.get(rid)
                        if relation is None:
                            media.append(["missing", rid])
                        elif relation.is_external:
                            media.append(["external", relation.target_ref])
                        else:
                            media.append(hashlib.sha256(relation.target_part.blob).hexdigest())
            crops = [
                (item.tag, sorted(item.attrib.items()))
                for item in node.iter()
                if item.tag.rsplit("}", 1)[-1] == "srcRect"
            ]
            objects.append({"kind": "image", "value": [media, crops]})
        elif node.tag in {f"{{{_W}}}object", f"{{{_W}}}altChunk"}:
            objects.append({"kind": "unsupported", "value": etree.tostring(node).decode()})
    # Complex fields span runs; include each instruction and its cached display.
    field_stack = []
    for node in element.iter():
        if node.tag == f"{{{_W}}}fldChar":
            kind = node.get(f"{{{_W}}}fldCharType")
            if kind == "begin":
                field_stack.append({"instruction": "", "text": "", "result": False})
            elif kind == "separate" and field_stack:
                field_stack[-1]["result"] = True
            elif kind == "end" and field_stack:
                value = field_stack.pop()
                objects.append(
                    {
                        "kind": "field",
                        "value": [re.sub(r"\s+", " ", value["instruction"]).strip(), value["text"]],
                    }
                )
        elif field_stack and node.tag == f"{{{_W}}}instrText":
            field_stack[-1]["instruction"] += node.text or ""
        elif field_stack and field_stack[-1]["result"] and node.tag == f"{{{_W}}}t":
            field_stack[-1]["text"] += node.text or ""
    if field_stack:
        objects.append({"kind": "unsupported", "value": "unclosed field"})
    # Baselines are JSON; normalize tuples before comparison after a reload.
    return json.loads(json.dumps(objects))


def _table_data(element):
    tables = list(element.iter(f"{{{_W}}}tbl"))
    if not tables:
        return None
    if len(tables) != 1:
        return {"unsupported": "nested_tables"}
    rows = []
    for row in tables[0].findall(f"{{{_W}}}tr"):
        cells = []
        for cell in row.findall(f"{{{_W}}}tc"):
            if any(n.tag in {f"{{{_W}}}gridSpan", f"{{{_W}}}vMerge"} for n in cell.iter()):
                return {"unsupported": "merged_cells"}
            cells.append(_plain(cell))
        rows.append(cells)
    return {"rows": rows}


def _table_prose(element):
    return [
        _plain(p)
        for p in element.iter(f"{{{_W}}}p")
        if not any(a.tag == f"{{{_W}}}tbl" for a in p.iterancestors())
    ]


def _layout(element):
    """Only inline dimensions; media content/crop is checked separately."""
    records = []
    for node in element.iter():
        if node.tag.rsplit("}", 1)[-1] == "inline":
            extent = next((e for e in node if e.tag.rsplit("}", 1)[-1] == "extent"), None)
            if extent is not None:
                records.append({"cx": int(extent.get("cx")), "cy": int(extent.get("cy"))})
    return records


def _anchors(document):
    result = {}
    for node in document._element.iter(f"{{{_W}}}sdt"):
        result.setdefault(_sdt_tag(node), []).append(node)
    return result


def write_word_state(document, state: dict) -> None:
    """Embed an unmapped custom XML baseline, with automatic object snapshots."""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.opc.packuri import PackURI
    from docx.opc.part import Part
    from lxml import etree

    _validate_state(state)
    stored, anchors = deepcopy(state), _anchors(document)
    baseline = {}
    for block in state["blocks"]:
        matches = anchors.get(_tag(block["id"]), [])
        if len(matches) != 1:
            raise ValueError(f"Word export needs one anchor for {block['id']}")
        element = matches[0]
        baseline[block["id"]] = {
            "text": _plain(element),
            "objects": _objects(element, document),
            "formatting": _formatting(element),
            "paragraph_format": _paragraph_format(element, document.styles),
            "layout": _layout(element),
            "spans": {},
            "table": _table_data(element),
            "table_prose": _table_prose(element) if _table_data(element) else [],
            "paragraph_count": len(list(element.iter(f"{{{_W}}}p"))),
        }
        if block["kind"] in {"caption", "reference", "keywords"}:
            visible, semantic_display = _plain(element), block["rendered_text"]
            baseline[block["id"]]["display_prefix"] = (
                visible[: -len(semantic_display)]
                if semantic_display and visible.endswith(semantic_display)
                else ""
            )
        for span in block.get("spans", []):
            match = anchors.get(_tag(block["id"] + "::" + span["id"]), [])
            if len(match) != 1 or element not in match[0].iterancestors():
                raise ValueError(f"Word export needs an internal anchor for {span['id']}")
            baseline[block["id"]]["spans"][span["id"]] = _plain(match[0])
    stored["_word_baseline"] = baseline
    # Preserve pre-existing unanchored content as a boundary, not new author prose.
    stored["_word_unanchored"] = [
        _plain(p)
        for p in document._element.iter(f"{{{_W}}}p")
        if not any(
            a.tag == f"{{{_W}}}sdt" and _sdt_tag(a) in {_tag(b["id"]) for b in state["blocks"]}
            for a in p.iterancestors()
        )
    ]
    root = etree.Element(f"{{{_STATE_NS}}}state", nsmap={None: _STATE_NS})
    etree.SubElement(root, f"{{{_STATE_NS}}}json").text = json.dumps(stored, ensure_ascii=False)
    blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
    old = []
    for rid, relation in document.part.rels.items():
        if relation.reltype == RT.CUSTOM_XML and not relation.is_external:
            try:
                if etree.fromstring(relation.target_part.blob).tag == root.tag:
                    old.append(rid)
            except etree.XMLSyntaxError:
                pass
    for rid in old:
        document.part.drop_rel(rid)
    part = Part(
        PackURI("/customXml/cfdpaper-word-state.xml"),
        "application/xml",
        blob,
        document.part.package,
    )
    document.part.relate_to(part, RT.CUSTOM_XML)


def _read_state(document):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from lxml import etree

    states = []
    for relation in document.part.rels.values():
        if relation.reltype != RT.CUSTOM_XML or relation.is_external:
            continue
        try:
            root = etree.fromstring(
                relation.target_part.blob,
                parser=etree.XMLParser(resolve_entities=False, no_network=True),
            )
        except etree.XMLSyntaxError:
            continue
        if root.tag == f"{{{_STATE_NS}}}state":
            value = root.find(f"{{{_STATE_NS}}}json")
            states.append(json.loads(value.text) if value is not None else None)
    if len(states) != 1:
        raise ValueError("DOCX needs exactly one recoverable cfdpaper Word baseline")
    _validate_state(states[0])
    if not isinstance(states[0].get("_word_baseline"), dict):
        raise ValueError("Word baseline object snapshots are absent")
    for block in states[0]["blocks"]:
        if "paragraph_format" in block:
            block["paragraph_format"] = _normalize_paragraph_styles(
                block["paragraph_format"], document.styles
            )
        baseline = states[0]["_word_baseline"].get(block["id"], {})
        if "paragraph_format" in baseline:
            baseline["paragraph_format"] = _normalize_paragraph_styles(
                baseline["paragraph_format"], document.styles
            )
    return states[0]


def _conflict(kind, block_id=None, **details):
    return {"type": kind, "block_id": block_id, **details}


def _comments(document, element_blocks):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from lxml import etree

    full_text, positions = _element_positions(document._element)
    starts, ends, references = {}, {}, set()
    for node in document._element.iter():
        identifier = node.get(f"{{{_W}}}id")
        if node.tag == f"{{{_W}}}commentRangeStart":
            starts[identifier] = node
        elif node.tag == f"{{{_W}}}commentRangeEnd":
            ends[identifier] = node
        elif node.tag == f"{{{_W}}}commentReference":
            references.add(identifier)
    result, conflicts = [], []
    for relation in document.part.rels.values():
        if relation.reltype != RT.COMMENTS or relation.is_external:
            continue
        root = etree.fromstring(relation.target_part.blob)
        for comment in root:
            identifier = comment.get(f"{{{_W}}}id")
            start, end = starts.get(identifier), ends.get(identifier)
            if start is None or end is None or identifier not in references:
                conflicts.append(_conflict("comment_anchor_missing", comment_id=identifier))
                continue
            a, b = positions[start][0], positions[end][0]
            owners = [
                (positions[element][1] - positions[element][0], bid)
                for element, bid in element_blocks.items()
                if positions[element][0] <= a <= b <= positions[element][1]
            ]
            owner = min(owners)[1] if owners else None
            offset = next((positions[e][0] for e, bid in element_blocks.items() if bid == owner), 0)
            result.append(
                {
                    "id": identifier,
                    "author": comment.get(f"{{{_W}}}author", ""),
                    "date": comment.get(f"{{{_W}}}date"),
                    "text": _plain(comment),
                    "block_id": owner,
                    "start": a - offset,
                    "end": b - offset,
                    "anchor_text": full_text[a:b],
                    "status": "unresolved",
                    "suggested_action": "review",
                }
            )
    return result, conflicts


def read_word_return(path: str | Path) -> dict:
    """Recover supported author edits and explicit, localizable conflicts."""
    from docx import Document
    from lxml import etree

    from cfdpaper.publication.document_blocks import stable_block_id

    document = Document(path)
    state, anchors = _read_state(document), _anchors(document)
    conflicts, records, element_blocks = [], [], {}
    missing, extra_paragraphs = set(), set()
    order = {node: index for index, node in enumerate(document._element.iter())}
    for original in state["blocks"]:
        bid = original["id"]
        matches = anchors.get(_tag(bid), [])
        if len(matches) != 1:
            conflicts.append(
                _conflict(
                    "missing_anchor" if not matches else "duplicate_anchor",
                    bid,
                    baseline=deepcopy(original),
                )
            )
            missing.add(bid)
            continue
        element, block = matches[0], deepcopy(original)
        element_blocks[element] = bid
        baseline = state["_word_baseline"][bid]
        local = []
        for node in [*element.iter(), *element.iterancestors()]:
            if node.tag in {
                f"{{{_W}}}{tag}"
                for tag in ("ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange")
            }:
                local.append(
                    _conflict(
                        "unresolved_revision",
                        bid,
                        xml=etree.tostring(node).decode(),
                        author=node.get(f"{{{_W}}}author"),
                    )
                )
            if node.tag == f"{{{_W}}}sectPr":
                local.append(
                    _conflict("unsupported_structure", bid, object_kind=node.tag.rsplit("}", 1)[-1])
                )
            if node.tag.rsplit("}", 1)[-1] == "anchor" and "wordprocessingDrawing" in node.tag:
                local.append(_conflict("unsupported_structure", bid, object_kind="floating_image"))
        objects = _objects(element, document)
        if any(o["kind"] == "unsupported" for o in objects):
            local.append(_conflict("unsupported_object", bid))
        elif objects != baseline["objects"]:
            changed = next(
                (o["kind"] for o in objects if o not in baseline["objects"]),
                next((o["kind"] for o in baseline["objects"] if o not in objects), "object"),
            )
            local.append(
                _conflict(
                    "object_modified",
                    bid,
                    object_kind=changed,
                    baseline=baseline["objects"],
                    author=objects,
                )
            )
        paragraphs = list(element.iter(f"{{{_W}}}p"))
        text_element = element
        if original["kind"] == "paragraph" and len(paragraphs) > baseline.get("paragraph_count", 1):
            if original.get("spans") or objects or local:
                local.append(_conflict("paragraph_split_with_protected_content", bid))
            else:
                text_element = paragraphs[0]
                extra_paragraphs.update(paragraphs[1:])
        table = _table_data(element)
        if table and _table_prose(element) != baseline.get("table_prose", []):
            local.append(
                _conflict(
                    "table_caption_or_note_modified",
                    bid,
                    baseline=baseline.get("table_prose", []),
                    author=_table_prose(element),
                )
            )
        if table and ("unsupported" in table or not baseline.get("table")):
            local.append(_conflict("unsupported_structure", bid, object_kind="table"))
        elif table != baseline.get("table"):
            old_rows = (baseline.get("table") or {}).get("rows", [])
            new_rows = (table or {}).get("rows", [])
            same_shape = [len(r) for r in old_rows] == [len(r) for r in new_rows]
            content = block.get("content")
            if (
                same_shape
                and old_rows[1:] == new_rows[1:]
                and isinstance(content, dict)
                and "columns" in content
                and "rows" in content
                and len(content["rows"]) + 1 == len(new_rows)
            ):
                block["content"]["columns"] = new_rows[0]
            else:
                local.append(
                    _conflict(
                        "table_structure_or_text_modified", bid, baseline=old_rows, author=new_rows
                    )
                )
        # Restore semantic tokens by explicit span identity, never number matching.
        text, positions = _element_positions(text_element)
        replacements = []
        for span in original.get("spans", []):
            matches = anchors.get(_tag(bid + "::" + span["id"]), [])
            if len(matches) != 1 or element not in matches[0].iterancestors():
                local.append(
                    _conflict(
                        (
                            "missing_anchor"
                            if not matches
                            else "duplicate_anchor"
                            if len(matches) > 1
                            else "misplaced_anchor"
                        ),
                        bid,
                        span_id=span["id"],
                    )
                )
                continue
            actual = _plain(matches[0])
            if actual != baseline["spans"][span["id"]]:
                local.append(
                    _conflict(
                        "protected_span_modified",
                        bid,
                        span_id=span["id"],
                        token=span["token"],
                        baseline=span["text"],
                        author=actual,
                    )
                )
            start, end = positions[matches[0]]
            replacements.append((start, end, span["token"]))
        for start, end, token in sorted(replacements, reverse=True):
            text = text[:start] + token + text[end:]
        prefix = baseline.get("display_prefix", "")
        if prefix and not text.startswith(prefix):
            local.append(
                _conflict("generated_label_modified", bid, baseline=prefix, author=_plain(element))
            )
        elif prefix:
            text = text[len(prefix) :]
        layout = _layout(element)
        if len(layout) != len(baseline["layout"]) or any(
            abs(a["cy"] * b["cx"] - a["cx"] * b["cy"]) > max(*a.values(), *b.values())
            for a, b in zip(layout, baseline["layout"], strict=False)
        ):
            local.append(_conflict("image_aspect_ratio_modified", bid))
        if not local:
            block["text"] = (
                original["text"] if table or _plain(text_element) == baseline["text"] else text
            )
            block["rendered_text"] = (
                original["rendered_text"] if table else _plain(text_element)[len(prefix) :]
            )
            formatting = _formatting(text_element)
            if formatting != baseline["formatting"]:
                block["formatting"] = formatting
                block["formatting_source_text"] = _plain(text_element)
            paragraph_format = _paragraph_format(text_element, document.styles)
            if paragraph_format != baseline["paragraph_format"]:
                block["paragraph_format"] = paragraph_format
            if layout != baseline["layout"]:
                block["layout"] = layout
        conflicts.extend(local)
        records.append((order[element], block))
    # Newly inserted ordinary paragraphs are assigned identity from explicit neighbors.
    unanchored = list(state.get("_word_unanchored", []))
    original_order = [b["id"] for b in state["blocks"]]
    for paragraph in document._element.iter(f"{{{_W}}}p"):
        if paragraph not in extra_paragraphs and any(
            a in element_blocks for a in paragraph.iterancestors()
        ):
            continue
        text = _plain(paragraph)
        if text in unanchored:
            unanchored.remove(text)
            continue
        paragraph_objects = _objects(paragraph, document)
        if not text.strip() and not paragraph_objects:
            continue
        position = order[paragraph]
        prior = [item for pos, item in sorted(records, key=lambda x: x[0]) if pos < position]
        later = [item for pos, item in sorted(records, key=lambda x: x[0]) if pos > position]
        before = prior[-1] if prior else None
        after = later[0] if later else None
        props = _paragraph_format(paragraph, document.styles)
        style_attrs = props[0].get("pStyle", {}) if props else {}
        style = style_attrs.get("name", style_attrs.get("val", ""))
        if style == "Title" or (not before and after and after["kind"] == "heading"):
            conflicts.append(_conflict("generated_title_modified", text=text, position=position))
            continue
        if style.startswith("Heading"):
            conflicts.append(_conflict("unanchored_heading", text=text, position=position))
            continue
        section = (before or after or {}).get("section_id")
        left = (
            original_order.index(before["id"]) if before and before["id"] in original_order else -1
        )
        right = (
            original_order.index(after["id"])
            if after and after["id"] in original_order
            else len(original_order)
        )
        missing_here = any(
            bid in missing for bid in original_order[min(left, right) + 1 : max(left, right)]
        )
        if (
            not section
            or missing_here
            or (before and after and before["section_id"] != after["section_id"])
            or paragraph_objects
            or any(n.tag in {f"{{{_W}}}ins", f"{{{_W}}}del"} for n in paragraph.iter())
            or any(a.tag == f"{{{_W}}}tbl" for a in paragraph.iterancestors())
        ):
            conflicts.append(_conflict("unanchored_content", text=text, position=position))
            continue
        neighbors = {
            "before": before["id"] if before else None,
            "after": after["id"] if after else None,
        }
        new_local_id = (
            "author-"
            + hashlib.sha256(
                json.dumps(
                    [state["baseline_id"], neighbors, position, text], sort_keys=True
                ).encode()
            ).hexdigest()[:24]
        )
        new_id = stable_block_id(section, "paragraph", new_local_id)
        records.append(
            (
                position,
                {
                    "id": new_id,
                    "local_id": new_local_id,
                    "kind": "paragraph",
                    "section_id": section,
                    "text": text,
                    "rendered_text": text,
                    "spans": [],
                    "neighbors": neighbors,
                    "formatting": _formatting(paragraph),
                    "paragraph_format": _paragraph_format(paragraph, document.styles),
                },
            )
        )
        element_blocks[paragraph] = new_id
    expected_headings = [b["section_id"] for b in state["blocks"] if b["kind"] == "heading"]
    ordered_blocks = [b for _, b in sorted(records, key=lambda item: item[0])]
    actual_headings = [b["section_id"] for b in ordered_blocks if b["kind"] == "heading"]
    if len(actual_headings) == len(expected_headings) and actual_headings != expected_headings:
        conflicts.append(
            _conflict("section_order_modified", baseline=expected_headings, author=actual_headings)
        )
    active_section = None
    for block in ordered_blocks:
        if block["kind"] == "heading":
            active_section = block["section_id"]
        elif (
            active_section
            and block["kind"] != "reference"
            and block["section_id"] != active_section
        ):
            conflicts.append(
                _conflict(
                    "cross_section_move",
                    block["id"],
                    baseline=block["section_id"],
                    author=active_section,
                )
            )
    comments, comment_conflicts = _comments(document, element_blocks)
    conflicts.extend(comment_conflicts)
    return {
        "schema_version": 1,
        "baseline_id": state["baseline_id"],
        "state": state,
        "blocks": ordered_blocks,
        "comments": comments,
        "conflicts": conflicts,
        "source_path": str(Path(path).resolve()),
    }


def _edits(base, changed):
    return [
        (a, b, changed[c:d])
        for tag, a, b, c, d in SequenceMatcher(None, base, changed, autojunk=False).get_opcodes()
        if tag != "equal"
    ]


def _merge_text(base, author, current):
    if author == base:
        return current
    if current == base or author == current:
        return author
    left, right = _edits(base, author), _edits(base, current)
    for a, b, replacement in left:
        for c, d, other in right:
            if (a, b, replacement) == (c, d, other):
                continue
            if max(a, c) < min(b, d) or (a == b and c <= a <= d) or (c == d and a <= c <= b):
                return None
    result = base
    for a, b, replacement in sorted(set(left + right), reverse=True):
        result = result[:a] + replacement + result[b:]
    return result


def _semantic_block(block):
    return {
        k: v
        for k, v in block.items()
        if k not in {"rendered_text", "formatting", "paragraph_format", "layout"}
    }


def merge_word_blocks(
    base_blocks: list[dict], author_blocks: list[dict], current_blocks: list[dict]
) -> dict:
    """Three-way merge by stable ID; conflict records retain both full candidates."""
    maps = []
    for label, blocks in (
        ("base", base_blocks),
        ("author", author_blocks),
        ("current", current_blocks),
    ):
        mapping = {b["id"]: b for b in blocks}
        if len(mapping) != len(blocks):
            raise ValueError(f"Duplicate {label} block IDs")
        maps.append(mapping)
    base, author, current = maps
    merged, conflicts = {}, []
    for bid in dict.fromkeys([*base, *author, *current]):
        b, a, c = base.get(bid), author.get(bid), current.get(bid)
        if b is None:
            if a is not None and c is not None and a != c:
                conflicts.append(
                    _conflict("new_id_collision", bid, author=deepcopy(a), current=deepcopy(c))
                )
            merged[bid] = deepcopy(c if c is not None else a)
            continue
        if a is None or c is None:
            remaining = c if a is None else a
            if remaining is not None and _semantic_block(remaining) != _semantic_block(b):
                conflicts.append(
                    _conflict(
                        "delete_modify",
                        bid,
                        baseline=deepcopy(b),
                        author=deepcopy(a),
                        current=deepcopy(c),
                    )
                )
                merged[bid] = deepcopy(remaining)
            continue
        text = _merge_text(b["text"], a["text"], c["text"])
        if text is None:
            conflicts.append(
                _conflict(
                    "overlapping_edit",
                    bid,
                    baseline=deepcopy(b),
                    author=deepcopy(a),
                    current=deepcopy(c),
                )
            )
            merged[bid] = deepcopy(c)
            continue
        result = deepcopy(c)
        result["text"] = text
        for field in set(a) | set(c):
            if field in {"id", "text", "rendered_text", "spans"}:
                continue
            av, bv, cv = a.get(field), b.get(field), c.get(field)
            if (
                field in {"formatting", "paragraph_format", "layout", "formatting_source_text"}
                and field not in c
                and field in a
            ):
                # A fresh scientific compilation has no author layout projection;
                # absence is not an explicit instruction to erase an old override.
                result[field] = deepcopy(av)
                continue
            if av != bv and cv != bv and av != cv:
                conflicts.append(
                    _conflict(
                        "field_edit",
                        bid,
                        field=field,
                        baseline=bv,
                        author=deepcopy(av),
                        current=deepcopy(cv),
                    )
                )
            elif av != bv:
                result[field] = deepcopy(av)
        if a.get("spans", []) != b.get("spans", []) and a.get("spans") != c.get("spans"):
            conflicts.append(
                _conflict(
                    "protected_binding_modified",
                    bid,
                    author=deepcopy(a["spans"]),
                    current=deepcopy(c["spans"]),
                )
            )
        rendered = text
        for span in result.get("spans", []):
            rendered = rendered.replace(span["token"], span["text"])
        result["rendered_text"] = rendered
        merged[bid] = result
    # Preserve a one-sided move; use stable neighboring IDs for inserted blocks.
    surviving = set(merged)
    base_order = [b["id"] for b in base_blocks if b["id"] in surviving]
    a_order = [b["id"] for b in author_blocks if b["id"] in base and b["id"] in surviving]
    c_order = [b["id"] for b in current_blocks if b["id"] in base and b["id"] in surviving]
    common = set(base_order) & set(a_order) & set(c_order)
    original = [bid for bid in base_order if bid in common]
    aa, cc = [bid for bid in a_order if bid in common], [bid for bid in c_order if bid in common]
    if aa != original and cc != original and aa != cc:
        conflicts.append(_conflict("order_edit", baseline=original, author=aa, current=cc))
    order = list(c_order if cc != original else a_order)
    for source in (current_blocks, author_blocks):
        ids = [b["id"] for b in source if b["id"] in surviving]
        for index, bid in enumerate(ids):
            if bid in order:
                continue
            prior = next((other for other in reversed(ids[:index]) if other in order), None)
            later = next((other for other in ids[index + 1 :] if other in order), None)
            where = order.index(prior) + 1 if prior else order.index(later) if later else len(order)
            order.insert(where, bid)
    order.extend(bid for bid in merged if bid not in order)
    return {"blocks": [merged[bid] for bid in order], "conflicts": conflicts}
