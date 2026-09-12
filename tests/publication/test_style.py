import pytest

from cfdpaper.publication.style import FigureSizing, PublicationStyle, figure_placement


def test_physical_scaling_not_dpi_guess():
    result = figure_placement(
        pixels=(2000, 1000),
        caption="Flow response.",
        sizing=FigureSizing(source_width_mm=200, target_width_mm=100, minimum_source_font_pt=16),
        style=PublicationStyle(),
    )
    assert result["width_mm"] == 100
    assert result["minimum_font_pt"] == 8
    assert result["scale"] == 0.5
    assert result["effective_dpi"] == 508


def test_unknown_source_font_is_not_inferred():
    result = figure_placement(
        pixels=(100, 50), caption="Caption", sizing=FigureSizing(), style=PublicationStyle()
    )
    assert result["minimum_font_pt"] is None
    assert result["scale"] is None


def test_high_dpi_does_not_rescue_small_font():
    with pytest.raises(ValueError, match="enlarge source text"):
        figure_placement(
            pixels=(20000, 10000),
            caption="Caption",
            sizing=FigureSizing(source_width_mm=200, target_width_mm=100, minimum_source_font_pt=8),
            style=PublicationStyle(),
        )


def test_tall_figure_and_caption_space_are_both_considered():
    short = figure_placement(
        pixels=(500, 2000), caption="Caption", sizing=FigureSizing(), style=PublicationStyle()
    )
    long = figure_placement(
        pixels=(500, 2000),
        caption="Shared-scale temperature distribution. " * 20,
        sizing=FigureSizing(),
        style=PublicationStyle(),
    )
    assert long["width_mm"] < short["width_mm"]
    assert long["height_mm"] + long["caption_height_estimate_mm"] <= 247.0001


@pytest.mark.parametrize("kwargs", [{"margin_mm": 110}, {"body_pt": float("nan")}])
def test_invalid_style(kwargs):
    with pytest.raises(ValueError):
        PublicationStyle(**kwargs)
