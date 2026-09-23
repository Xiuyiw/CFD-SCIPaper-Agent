"""Portable host figure tasks and non-executing import of editable deliveries."""

from __future__ import annotations

import ast
import json
import math
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import Field, model_validator

from cfdpaper.publication.section import _Record, _stage, _write
from cfdpaper.publication.style import FigureSizing, PublicationStyle, figure_placement


class _Source(_Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    path: str
    role: Literal["data", "field_image", "context", "editable_source"]
    description: str
    original_path: str | None = None


class _Label(_Record):
    text: str
    unit: str  # Use "1" for dimensionless numeric quantities; "" for qualitative labels.


class _Relationship(_Record):
    from_: str = Field(alias="from")
    to: str
    meaning: str
    status: Literal["observed", "hypothesis", "method"]


class _Task(_Record):
    figure_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    kind: Literal["data", "schematic", "hybrid"]
    purpose: str
    claim_ceiling: str
    sources: list[_Source] = Field(min_length=1)
    labels: list[_Label] = Field(min_length=1)
    relationships: list[_Relationship] = Field(default_factory=list)
    final_width_mm: float = Field(default=160, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_route(self):
        ids = [s.id.casefold() for s in self.sources]
        if len(ids) != len(set(ids)) or any(key in {".", ".."} for key in ids):
            raise ValueError("Source IDs must be unique")
        if self.kind in {"data", "hybrid"}:
            if not any(s.role == "data" for s in self.sources):
                raise ValueError("Data and hybrid figures require a data source")
            if not any(label.unit.strip() for label in self.labels):
                raise ValueError("Quantitative figures require explicit units (1 if dimensionless)")
        return self


class _Delivery(_Record):
    figure_id: str
    editable_sources: list[str] = Field(min_length=1)
    preview: str
    caption: str
    exports: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sizing: FigureSizing = Field(default_factory=FigureSizing)


def _asset(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or ":" in name:
        raise ValueError(f"Asset path must stay relative to its package: {name}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing or out-of-package asset: {name}")
    if path.stat().st_size == 0:
        raise ValueError(f"Empty asset: {name}")
    return path


def _load(path: Path, model):
    return model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _check_editable(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".py":
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.name)
        if not tree.body:
            raise ValueError("Plot script is empty")
        return
    if suffix not in {".svg", ".drawio"}:
        raise ValueError("Editable sources must be Python, SVG, or uncompressed draw.io XML")
    root = ET.parse(path).getroot()
    tags = {element.tag.rsplit("}", 1)[-1] for element in root.iter()}
    if suffix == ".svg":
        if root.tag.rsplit("}", 1)[-1] != "svg" or not tags.intersection(
            {"text", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
        ):
            raise ValueError("SVG must contain editable vector elements, not only a raster image")
    elif "mxGraphModel" not in tags or not any(
        e.tag == "mxCell" and (e.get("vertex") == "1" or e.get("edge") == "1") for e in root.iter()
    ):
        raise ValueError("draw.io source must contain uncompressed editable cells")


def _check_preview(path: Path, final_width_mm: float) -> dict:
    if path.suffix.lower() not in {".png", ".tif", ".tiff"}:
        raise ValueError("Preview must be a PNG or TIFF image")
    with Image.open(path) as image:
        image.load()
        if min(image.size) < 2 or all(lo == hi for lo, hi in image.convert("RGB").getextrema()):
            raise ValueError("Preview is blank or too small")
        width, height = image.size
    return {
        "width_px": width,
        "height_px": height,
        "final_width_mm": final_width_mm,
        "final_height_mm": final_width_mm * height / width,
        "effective_ppi": width * 25.4 / final_width_mm,
    }


def prepare_figure_task(input_path: Path, output_dir: Path) -> Path:
    """Copy declared sources and usable Skill guidance into a new host task package.

    Input paths are relative to the JSON input and retain their relative hierarchy under
    sources/, so declared scripts, helpers and data keep working together after relocation.
    No script is rewritten, executed, or scanned to guess undeclared dependencies.
    """
    input_path, output_dir = Path(input_path), Path(output_dir)
    task = _load(input_path, _Task)
    resolved = [_asset(input_path.parent, item.path) for item in task.sources]
    skill = Path(__file__).resolve().parents[1] / "skills/cfd-figure-production"
    if not skill.is_dir():
        skill = Path(__file__).resolve().parents[3] / "skills/cfd-figure-production"
    with _stage(output_dir) as staged:
        for item, source in zip(task.sources, resolved, strict=True):
            item.original_path = item.path
            item.path = (Path("sources") / item.original_path).as_posix()
            target = staged / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        _write(staged / "task.json", task.model_dump(by_alias=True))
        shutil.copytree(skill, staged / "skills/cfd-figure-production")
        reference = "skills/cfd-figure-production/references/external-backends.md"
        (staged / "prompt.md").write_text(
            f"# Figure task: {task.figure_id}\n\n"
            f"Read task.json, {reference}, and the linked schematic adaptation when needed.\n"
            f"Route: {task.kind}. Produce the relationship described in purpose, within "
            "claim_ceiling; preserve source rows, cases, exact labels and units.\n"
            "Data layers use the existing Matplotlib/data-analysis route. Conceptual layers "
            "use editable SVG or draw.io; distinguish observed, hypothesis and method arrows.\n"
            "A field_image is a read-only real field export or reference: never ask an image "
            "model to synthesize, replace, or retouch its quantitative field/colorbar.\n"
            "Preserve supplied editable_source files and local author edits; for a requested "
            "label edit change only that label, not data, layout or other styles.\n"
            "Image generation is optional composition exploration only, never a data source.\n"
            "Keep paths relative to this package and source dependencies in sources/. "
            "Declared input paths retain their hierarchy under sources/; source IDs do not "
            "determine paths. Resolve script inputs from __file__, not the shell directory. "
            "Include required native fields and helper modules, not only the final PNG. "
            "Return delivery.json following delivery-template.json, with real editable files, "
            "a nonblank PNG/TIFF preview and caption. Include other exports/dependencies in "
            "exports. Do not list unchanged sources/ files as delivery artifacts; they are "
            "preserved automatically. Do not overwrite task files or original sources.\n"
            "In sizing, declare the actual source_width_mm and minimum_source_font_pt when "
            "known from the editable source; leave unknown values null. Font size must refer "
            "to that source width, not raster DPI. target_width_mm must match the task's "
            "final_width_mm. These are declarations, not automatically detected measurements.\n"
            f"Inspect at {task.final_width_mm:g} mm final width; check labels, arrows, units "
            "and source-data mapping. Record raster-only components and any remaining issues "
            "in notes. Export success is not scientific approval.\n",
            encoding="utf-8",
        )
        editable = "figure.svg" if task.kind == "schematic" else "plot_figure.py"
        _write(
            staged / "delivery-template.json",
            {
                "figure_id": task.figure_id,
                "editable_sources": [editable],
                "preview": "figure.png",
                "caption": "Replace with the evidence-bounded caption.",
                "exports": [],
                "notes": [],
                "sizing": FigureSizing(target_width_mm=task.final_width_mm).model_dump(),
            },
        )
    return output_dir


def import_figure_task(
    package_dir: Path,
    delivery_path: Path,
    output_dir: Path,
    *,
    style: PublicationStyle | None = None,
) -> Path:
    """Preserve source provenance and copy a candidate delivery without running its scripts.

    Syntax/image checks establish usable file types, not correspondence between returned
    artwork and source numbers or scientific approval. Author review remains necessary.
    Sizing uses declared source metadata and the existing Word placement calculation;
    the report applies to this style and caption, not a later changed manuscript layout.
    """
    package_dir, delivery_path, output_dir = map(Path, (package_dir, delivery_path, output_dir))
    task = _load(package_dir / "task.json", _Task)
    delivery = _load(delivery_path, _Delivery)
    if delivery.figure_id != task.figure_id:
        raise ValueError("Delivery figure_id does not match task")
    target_width = delivery.sizing.target_width_mm
    if target_width is not None and not math.isclose(target_width, task.final_width_mm):
        raise ValueError("Delivery sizing.target_width_mm conflicts with task final_width_mm")
    delivery.sizing = delivery.sizing.model_copy(update={"target_width_mm": task.final_width_mm})
    originals = [(item.path, _asset(package_dir, item.path)) for item in task.sources]
    names = [*delivery.editable_sources, delivery.preview, *delivery.exports]
    if len({Path(name).as_posix().casefold() for name in names}) != len(names):
        raise ValueError("Delivery artifact paths must be unique")
    paths = {name: _asset(delivery_path.parent, name) for name in names}
    for name in names:
        first = Path(name).parts[0].casefold()
        if first in {"sources", "task.json", "delivery.json", "skills"}:
            raise ValueError(f"Delivery would replace preserved task material: {name}")
    for name in delivery.editable_sources:
        try:
            _check_editable(paths[name])
        except (SyntaxError, ET.ParseError) as exc:
            raise ValueError(f"Invalid editable source syntax: {name}") from exc
    suffixes = {paths[name].suffix.lower() for name in delivery.editable_sources}
    if task.kind in {"data", "hybrid"} and ".py" not in suffixes:
        raise ValueError("Data and hybrid deliveries require the data plotting script")
    if task.kind == "schematic" and not suffixes.intersection({".svg", ".drawio"}):
        raise ValueError("Schematic deliveries require editable SVG or draw.io")
    preview_geometry = _check_preview(paths[delivery.preview], task.final_width_mm)
    config = style or PublicationStyle()
    placement = figure_placement(
        pixels=(preview_geometry["width_px"], preview_geometry["height_px"]),
        caption=f"Figure {task.figure_id}. {delivery.caption}",
        sizing=delivery.sizing,
        style=config,
    )
    preview_geometry.update(
        final_width_mm=placement["width_mm"],
        final_height_mm=placement["height_mm"],
        effective_ppi=placement["effective_dpi"],
    )
    with _stage(output_dir) as staged:
        for name, path in [*originals, *paths.items()]:
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        _write(staged / "task.json", task.model_dump(by_alias=True))
        shutil.copytree(package_dir / "skills", staged / "skills")
        _write(
            staged / "delivery.json",
            {
                **delivery.model_dump(),
                "kind": task.kind,
                "status": "imported_candidate",
                "scientific_approval": False,
                "checks": {"editable_syntax": True, "preview_decoded_nonblank": True},
                "preview_geometry": preview_geometry,
                "placement": placement,
                "placement_style": config.model_dump(),
                "font_size_basis": (
                    "declared_source_metadata"
                    if delivery.sizing.minimum_source_font_pt is not None
                    else "unknown"
                ),
                "sources": [source.model_dump() for source in task.sources],
            },
        )
    return output_dir
