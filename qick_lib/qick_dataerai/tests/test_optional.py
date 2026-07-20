"""Tests for the optional-dependency guard and import-safety."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import qick_dataerai
from qick_dataerai import _optional, serialize
from qick_dataerai import ProvenanceRun, RunError
from qick_dataerai.tests.fakeclient import FakeClient


def test_require_missing_raises_clear(monkeypatch):
    import importlib

    real = importlib.import_module

    def fake_import(name, *a, **k):
        if name == "matplotlib":
            raise ImportError("no matplotlib")
        return real(name, *a, **k)

    monkeypatch.setattr("qick_dataerai._optional.importlib.import_module", fake_import)
    with pytest.raises(ImportError) as exc:
        _optional.require("matplotlib")
    assert "qick_dataerai" in str(exc.value)
    assert "matplotlib" in str(exc.value)


def test_have_false_for_missing():
    assert _optional.have("definitely_not_a_real_module_xyz") is False
    assert _optional.have("json") is True


def test_log_analysis_without_matplotlib(monkeypatch):
    def boom(name):
        if name == "matplotlib":
            raise ImportError("qick_dataerai: matplotlib is required ...")
        return __import__(name)

    monkeypatch.setattr(serialize, "require", boom)

    # best_effort: records the error, no crash, returns None.
    client = FakeClient()
    run = ProvenanceRun(client, owner_type="user", owner_id="u")
    assert run.log_analysis(fig=object()) is None
    assert run.result.errors

    # fail_fast: raises RunError.
    run2 = ProvenanceRun(client, owner_type="user", owner_id="u", on_error="fail_fast")
    with pytest.raises(RunError):
        run2.log_analysis(fig=object())


def test_import_package_with_no_optional_deps():
    """`import qick_dataerai` must succeed even if numpy/matplotlib/dataerai are
    unimportable (they are only needed lazily, per-step)."""
    qick_lib = str(Path(qick_dataerai.__file__).resolve().parents[1])
    code = (
        "import sys\n"
        "for m in ('numpy', 'matplotlib', 'dataerai'):\n"
        "    sys.modules[m] = None\n"  # force ImportError on `import <m>`
        "import qick_dataerai\n"
        "print('ok', qick_dataerai.__version__)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={"PYTHONPATH": qick_lib, "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("ok ")
