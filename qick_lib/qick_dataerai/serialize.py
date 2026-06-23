"""Serialize QICK artifacts to temporary files for upload to Dataerai.

Each writer creates a temporary file, writes the artifact, and returns its path;
the caller uploads it and removes it (see :func:`temp_upload_file`). Heavy
dependencies (``numpy``, ``matplotlib``) and QICK's own ``NpEncoder`` are
imported lazily so this module imports cleanly anywhere.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from typing import Any

from ._optional import require


@contextmanager
def temp_upload_file(suffix: str):
    """Yield the path of a closed, empty temp file; remove it on exit.

    The file is created with ``delete=False`` and closed immediately so the
    uploader can re-open it by path on any platform; it is removed in a
    ``finally`` block regardless of what the caller does.
    """
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    path = handle.name
    handle.close()
    try:
        yield path
    finally:
        try:
            os.remove(path)
        except OSError:  # pragma: no cover - already gone
            pass


def _maybe_numpy():
    try:
        import numpy  # noqa: WPS433 - lazy by design

        return numpy
    except ImportError:  # pragma: no cover - numpy is a hard QICK dep
        return None


def _make_config_encoder():
    """Return a JSON encoder that packs numpy via QICK's ``NpEncoder`` when
    available and degrades any other non-serializable value to ``str()``.
    """
    try:
        from qick.helpers import NpEncoder  # noqa: WPS433 - lazy by design

        base = NpEncoder
    except Exception:  # pragma: no cover - qick always present in practice
        base = json.JSONEncoder

    class _ConfigEncoder(base):  # type: ignore[misc, valid-type]
        def default(self, o):  # noqa: D401 - JSONEncoder hook
            try:
                return super().default(o)
            except TypeError:
                np = _maybe_numpy()
                if np is not None and isinstance(o, np.ndarray):
                    return o.tolist()
                return str(o)

    return _ConfigEncoder


def _program_dump(prog) -> dict:
    """Capture a program's class identity and its ``dump_prog()`` state.

    Falls back to recording the error string if ``dump_prog()`` is unavailable
    or raises, so config capture never fails on the program portion alone.
    """
    info: dict[str, Any] = {
        "class": type(prog).__name__,
        "module": type(prog).__module__,
    }
    dump = getattr(prog, "dump_prog", None)
    if callable(dump):
        try:
            info["dump_prog"] = dump()
        except Exception as exc:  # noqa: BLE001 - best-effort capture
            info["dump_prog_error"] = repr(exc)
    return info


def write_config_json(path: str, cfg, *, soccfg=None, prog=None, run_id: str) -> dict:
    """Write the experiment configuration to *path* as a single JSON document.

    Combines the user ``cfg`` (a dict, or any object exposing ``get_cfg()`` such
    as a ``QickConfig``/``QickSoc``), the optional hardware ``soccfg``, and an
    optional program ASM dump. Values that are not JSON-serializable (and not
    numpy, which is packed via QICK's encoder) are degraded to ``str()``.

    Returns a small JSON-safe dict of facts about what was captured, suitable
    for attaching to the asset's metadata.
    """
    cfg_dict = cfg.get_cfg() if hasattr(cfg, "get_cfg") else cfg
    soccfg_dict = soccfg.get_cfg() if (soccfg is not None and hasattr(soccfg, "get_cfg")) else None
    program = _program_dump(prog) if prog is not None else None

    doc = {
        "qick_dataerai": {"run_id": run_id, "role": "config", "schema": 1},
        "cfg": cfg_dict,
        "soccfg": soccfg_dict,
        "program": program,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, cls=_make_config_encoder())

    captured = {
        "has_soccfg": soccfg_dict is not None,
        "has_program": program is not None,
    }
    if program is not None:
        captured["program_class"] = program.get("class")
    return captured


def _add_channels(arrays: dict, prefix: str, value) -> None:
    """Store *value* under *prefix*, splitting a per-channel list into ``_ch{k}``."""
    np = require("numpy")
    if isinstance(value, (list, tuple)):
        for k, item in enumerate(value):
            arrays[f"{prefix}_ch{k}"] = np.asarray(item)
    else:
        arrays[prefix] = np.asarray(value)


def write_iq_npz(path: str, data, *, expt_pts=None, prog=None, decimated: bool = False) -> dict:
    """Normalize a QICK ``acquire(...)`` return value and ``np.savez_compressed``
    it to *path*.

    Handles every shape the averager programs return:

    * ``(avg_di, avg_dq)`` — ``AveragerProgram.acquire``
    * ``(expt_pts, avg_di, avg_dq)`` — ``RAverager``/``NDAverager``
    * a list of ndarrays — ``acquire_decimated``
    * a single ndarray, or a ``{name: ndarray}`` dict

    Returns a JSON-safe shape map plus ``decimated`` / channel-count facts for
    the asset metadata.
    """
    np = require("numpy")
    arrays: dict[str, Any] = {}

    if isinstance(data, dict):
        for key, value in data.items():
            arrays[str(key)] = np.asarray(value)
    elif isinstance(data, tuple):
        if len(data) == 3:
            pts, avg_di, avg_dq = data
            if expt_pts is None:
                expt_pts = pts
            _add_channels(arrays, "avg_di", avg_di)
            _add_channels(arrays, "avg_dq", avg_dq)
        elif len(data) == 2:
            avg_di, avg_dq = data
            _add_channels(arrays, "avg_di", avg_di)
            _add_channels(arrays, "avg_dq", avg_dq)
        else:
            for k, item in enumerate(data):
                arrays[f"data_{k}"] = np.asarray(item)
    elif isinstance(data, list):
        for k, item in enumerate(data):
            arrays[f"iq_ch{k}"] = np.asarray(item)
    else:
        arrays["data"] = np.asarray(data)

    if expt_pts is not None:
        if isinstance(expt_pts, (list, tuple)):
            for j, pts in enumerate(expt_pts):
                arrays[f"expt_pts_{j}"] = np.asarray(pts)
        else:
            arrays["expt_pts"] = np.asarray(expt_pts)

    if prog is not None:
        for buf_name in ("di_buf", "dq_buf"):
            buf = getattr(prog, buf_name, None)
            if buf is not None:
                arrays[buf_name] = np.asarray(buf)

    np.savez_compressed(path, **arrays)

    shapes = {name: list(arr.shape) for name, arr in arrays.items()}
    meta: dict[str, Any] = {"arrays": shapes, "decimated": bool(decimated)}
    loop_dims = getattr(prog, "loop_dims", None) if prog is not None else None
    if loop_dims is not None:
        try:
            meta["loop_dims"] = [int(d) for d in loop_dims]
        except TypeError:  # pragma: no cover - defensive
            pass
    return meta


def write_figure_png(path: str, fig, *, dpi: int = 200) -> None:
    """Save a matplotlib ``Figure`` to *path* as a tight-bbox PNG."""
    require("matplotlib")
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
