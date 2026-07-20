"""Lazy optional-dependency helpers.

``import qick_dataerai`` must succeed on a bare machine (e.g. a docs build or a
board without the Dataerai SDK installed). To make that possible, the package
imports its heavier dependencies — the Dataerai SDK, ``numpy`` and
``matplotlib`` — only at the moment a capture step needs them, through
:func:`require`, which raises a clear, actionable error if the dependency is
missing.
"""

from __future__ import annotations

import importlib
import importlib.util

_HINTS = {
    "numpy": (
        "numpy is required to serialize acquired IQ data; "
        "install it with `pip install numpy`."
    ),
    "matplotlib": (
        "matplotlib is required to save analysis figures; "
        "install it with `pip install matplotlib` (or `pip install qick[dataerai]`)."
    ),
    "dataerai": (
        "the Dataerai SDK is required to upload assets; "
        "install it with `pip install qick[dataerai]` or `pip install dataerai-sdk` "
        "(the SDK is imported as `dataerai` but published as `dataerai-sdk`)."
    ),
}


def require(name: str):
    """Import and return the optional dependency *name*, or raise a clear error.

    Args:
        name: The module to import (e.g. ``"numpy"``).

    Returns:
        The imported module.

    Raises:
        ImportError: If the module is not installed. The message names the
            dependency and how to install it, prefixed with ``qick_dataerai:``.
    """
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        hint = _HINTS.get(name, f"the optional dependency {name!r} is required for this operation.")
        raise ImportError(f"qick_dataerai: {hint}") from exc


def have(name: str) -> bool:
    """Return ``True`` if *name* is importable, without importing it."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False
