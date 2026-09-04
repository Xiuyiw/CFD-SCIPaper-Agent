"""Evidence-bounded publication workflow components."""

from typing import Any

__all__ = [
    "FigureDelivery",
    "FigureRenderError",
    "build_figure_delivery",
    "validate_rendered_figure",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import render_figure

        return getattr(render_figure, name)
    raise AttributeError(name)
