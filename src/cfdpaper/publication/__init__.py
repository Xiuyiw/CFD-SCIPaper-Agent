"""Evidence-bounded publication workflow components."""

from typing import Any

__all__ = [
    "FigureDelivery",
    "FigureRenderError",
    "ParagraphRenderError",
    "build_figure_delivery",
    "render_results_paragraph",
    "validate_rendered_figure",
]


def __getattr__(name: str) -> Any:
    if name in {"ParagraphRenderError", "render_results_paragraph"}:
        from . import results_paragraph

        return getattr(results_paragraph, name)
    if name in __all__:
        from . import render_figure

        return getattr(render_figure, name)
    raise AttributeError(name)
