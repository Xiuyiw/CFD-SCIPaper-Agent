"""Physical manuscript dimensions and figure scaling, in millimetres and points."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicationStyle(BaseModel):
    """Editable review defaults, not a journal compliance certificate."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    page_width_mm: float = Field(default=210, gt=0)
    page_height_mm: float = Field(default=297, gt=0)
    margin_mm: float = Field(default=25, ge=0)
    font_family: str = Field(default="Times New Roman", min_length=1)
    body_pt: float = Field(default=11, gt=0)
    title_pt: float = Field(default=15, gt=0)
    heading_pt: float = Field(default=12, gt=0)
    caption_pt: float = Field(default=10, gt=0)
    reference_pt: float = Field(default=10, gt=0)
    space_after_pt: float = Field(default=8, ge=0)
    line_spacing: float = Field(default=1.08, ge=1)
    figure_width_mm: float = Field(default=160, gt=0)
    minimum_figure_font_pt: float = Field(default=8, gt=0)

    @model_validator(mode="after")
    def usable_page(self):
        if min(self.page_width_mm, self.page_height_mm) <= 2 * self.margin_mm:
            raise ValueError("Margins leave no usable page area")
        if not self.font_family.strip():
            raise ValueError("Font family must not be blank")
        return self


class FigureSizing(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source_width_mm: float | None = Field(default=None, gt=0)
    target_width_mm: float | None = Field(default=None, gt=0)
    minimum_source_font_pt: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def known_font_needs_width(self):
        if self.minimum_source_font_pt is not None and self.source_width_mm is None:
            raise ValueError("Known source font size requires actual source_width_mm")
        return self


def figure_placement(*, pixels, caption, sizing: FigureSizing, style: PublicationStyle):
    """Estimate space for a caption; report actual image scale, never infer font sizes."""
    px_width, px_height = pixels
    if min(px_width, px_height) <= 0:
        raise ValueError("Image dimensions must be positive")
    content_width = style.page_width_mm - 2 * style.margin_mm
    requested = sizing.target_width_mm or style.figure_width_mm
    width = min(requested, content_width)
    # Conservative line count. Actual renderer pagination remains the final check.
    chars_per_line = max(1, int(width * 72 / 25.4 / (style.caption_pt * 0.55)))
    lines = sum(max(1, math.ceil(len(line) / chars_per_line)) for line in caption.split("\n"))
    caption_height = (lines * style.caption_pt * 1.2 + style.space_after_pt + 6) * 25.4 / 72
    available_height = style.page_height_mm - 2 * style.margin_mm - caption_height
    if available_height <= 0:
        raise ValueError("Caption exceeds the usable page; shorten or split the caption")
    width = min(width, available_height * px_width / px_height)
    scale = width / sizing.source_width_mm if sizing.source_width_mm else None
    font = sizing.minimum_source_font_pt * scale if sizing.minimum_source_font_pt else None
    if font is not None and font + 1e-6 < style.minimum_figure_font_pt:
        raise ValueError(
            f"Embedded figure text would be {font:.2f} pt, below "
            f"{style.minimum_figure_font_pt:g} pt; enlarge source text "
            "or revise the figure/page layout"
        )
    return {
        "width_mm": width,
        "height_mm": width * px_height / px_width,
        "effective_dpi": px_width * 25.4 / width,
        "source_width_mm": sizing.source_width_mm,
        "scale": scale,
        "minimum_font_pt": font,
        "caption_height_estimate_mm": caption_height,
    }
