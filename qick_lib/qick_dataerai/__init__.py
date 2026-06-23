"""qick_dataerai — automatic provenance capture from QICK experiments into Dataerai.

When a QICK program runs, this package uploads the experiment configuration, the
raw acquired IQ data, and any analysis figures as **linked Dataerai assets**, so
the lineage ``config -> raw data -> analysis`` travels with the data.

Public API
----------
``ProvenanceRun``
    Context manager for multi-step capture (config -> raw -> analysis).
``capture_run``
    One-call helper for the common (config + data [+ figure]) case.
``RunResult`` / ``UploadRecord``
    Dataclasses summarizing the assets and relationships a run created.
``RunError``
    Raised in fail-fast mode when an upload or relationship call fails.

Importing this package never hard-fails: the Dataerai SDK, numpy and matplotlib
are imported lazily, only when a capture step actually needs them (see
``qick_dataerai._optional``).
"""

from pathlib import Path

from .provenance import ProvenanceRun, RunError, RunResult, UploadRecord, capture_run

__all__ = [
    "ProvenanceRun",
    "capture_run",
    "RunResult",
    "UploadRecord",
    "RunError",
    "__version__",
]

try:
    __version__ = (Path(__file__).parent / "VERSION").read_text().strip()
except OSError:  # pragma: no cover - VERSION ships in the wheel
    __version__ = "0.0.0"
