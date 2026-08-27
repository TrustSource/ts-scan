"""Stub -- not vendored. This subsystem (checkov's own check-running /
platform-integration / reporting machinery) is unrelated to graph building
and is never called on the graph-construction code path. Any attribute
access returns a MagicMock so unused imports/type-hints/default-params
resolve harmlessly; if something on this path is ever actually CALLED at
runtime, it will misbehave -- that would mean a real dependency was missed,
not that this stub is "working". __all__ is empty so `from x import *`
(checkov's own package __init__.py files do this to auto-register checks)
is a no-op instead of failing on a non-str __all__ entry."""
from unittest.mock import MagicMock

__all__: list = []


def __getattr__(name):
    return MagicMock(name=f"{__name__}.{name}")
