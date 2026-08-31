"""CFD-Paper-Agent public package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cfd-paper-agent")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.2.0"
