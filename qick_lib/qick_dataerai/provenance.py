"""Provenance capture for QICK experiments.

:class:`ProvenanceRun` is a context manager that uploads a run's configuration,
raw acquired data and analysis outputs to Dataerai as assets, linking them with
typed provenance relationships::

    raw_data  --"acquired_with"-->  config
    analysis  --"analysis_of"---->  raw_data

Every asset in a run shares a ``run_id`` (recorded in metadata and as a
``qick-run:<id>`` tag) so the whole run is discoverable. :func:`capture_run` is
a one-call wrapper for the common case.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from . import serialize

# Relationship vocabulary (Dataerai convention: from = derived, to = origin).
REL_ACQUIRED_WITH = "acquired_with"
REL_ANALYSIS_OF = "analysis_of"

# Tag every asset so a run (or all runs) can be found by tag.
TAG_ALL = "qick-dataerai"

# Metadata keys stamped on every asset.
META_RUN_ID = "qick_dataerai_run_id"
META_ROLE = "qick_dataerai_role"
META_VERSION = "qick_dataerai_version"


def _version() -> str:
    from . import __version__

    return __version__


@dataclass
class UploadRecord:
    """One asset created during a run."""

    role: str  # "config" | "raw_data" | "analysis"
    asset_id: str
    title: str
    transfer_id: Optional[str] = None


@dataclass
class RunResult:
    """Summary of the assets and relationships a run created."""

    run_id: str
    uploads: list[UploadRecord] = field(default_factory=list)
    relationship_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def _ids(self, role: str) -> list[str]:
        return [u.asset_id for u in self.uploads if u.role == role]

    @property
    def config_asset_id(self) -> Optional[str]:
        ids = self._ids("config")
        return ids[0] if ids else None

    @property
    def raw_asset_ids(self) -> list[str]:
        return self._ids("raw_data")

    @property
    def analysis_asset_ids(self) -> list[str]:
        return self._ids("analysis")


class RunError(RuntimeError):
    """Raised in fail-fast mode when an upload or relationship call fails."""


# Accepted on_error modes.
BEST_EFFORT = "best_effort"
FAIL_FAST = "fail_fast"


class ProvenanceRun:
    """Capture a QICK experiment's provenance into Dataerai, step by step.

    Use inside an entered :class:`dataerai.DataeraiClient`::

        with DataeraiClient(binary_path="/path/to/dataerai") as client:
            with ProvenanceRun(client, owner_type="user",
                               owner_id=client.auth_status().user_email) as run:
                run.log_config(prog.cfg, soccfg=soccfg, prog=prog)
                expt_pts, avgi, avgq = prog.acquire(soc)
                run.log_acquisition(prog, (expt_pts, avgi, avgq))
                run.log_analysis(plt.gcf(), analysis_mode="non_destructive")
            print(run.result.run_id, run.result.relationship_ids)

    Args:
        client: An already-constructed/entered ``DataeraiClient`` (or any object
            exposing ``upload`` and ``create_relationship`` — handy for testing).
        owner_type: ``"project"`` or ``"user"``.
        owner_id: The owning project/user id.
        title_prefix: Prefix for every asset title (default ``"QICK run"``).
        collection_id: Optional collection to place every asset in.
        tags: Extra tags merged onto every asset.
        metadata: Extra metadata merged onto every asset.
        on_error: ``"best_effort"`` (default — record failures in
            ``result.errors`` and continue) or ``"fail_fast"`` (raise
            :class:`RunError`).
        run_id: Override the generated run id (default ``uuid4().hex``).
        fig_dpi: DPI for analysis-figure PNGs.
        on_progress: Optional progress callback forwarded to ``client.upload``.
    """

    def __init__(
        self,
        client,
        *,
        owner_type: str,
        owner_id: str,
        title_prefix: str = "QICK run",
        collection_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        on_error: str = BEST_EFFORT,
        run_id: Optional[str] = None,
        fig_dpi: int = 200,
        on_progress: Optional[Callable] = None,
    ) -> None:
        if on_error not in (BEST_EFFORT, FAIL_FAST):
            raise ValueError(f"on_error must be {BEST_EFFORT!r} or {FAIL_FAST!r}, got {on_error!r}")
        self._client = client
        self._owner_type = owner_type
        self._owner_id = owner_id
        self._title_prefix = title_prefix
        self._collection_id = collection_id
        self._extra_tags = list(tags or [])
        self._extra_metadata = dict(metadata or {})
        self._on_error = on_error
        self._fig_dpi = fig_dpi
        self._on_progress = on_progress

        self.run_id = run_id or uuid.uuid4().hex
        self.result = RunResult(run_id=self.run_id)
        self._config_logged = False
        self._last_raw_asset_id: Optional[str] = None

    # ── context manager ──────────────────────────────────────────────────────

    def __enter__(self) -> "ProvenanceRun":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Never swallow the caller's exception; just stop accepting steps.
        return False

    # ── internals ────────────────────────────────────────────────────────────

    def _guard(self, role: str, fn: Callable):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - intentional broad catch
            if self._on_error == FAIL_FAST:
                raise RunError(f"{role} step failed: {exc!r}") from exc
            self.result.errors.append(f"{role}: {exc!r}")
            return None

    def _tags(self, role: str) -> list[str]:
        return [*self._extra_tags, f"qick-run:{self.run_id}", TAG_ALL]

    def _metadata(self, role: str, extra: Optional[dict] = None) -> dict:
        meta = {
            META_RUN_ID: self.run_id,
            META_ROLE: role,
            META_VERSION: _version(),
        }
        meta.update(self._extra_metadata)
        if extra:
            meta.update(extra)
        return meta

    def _upload(self, role, path, *, title, description, extra_metadata) -> Optional[str]:
        def _do():
            res = self._client.upload(
                path,
                title=title,
                owner_type=self._owner_type,
                owner_id=self._owner_id,
                collection_id=self._collection_id,
                description=description,
                tags=self._tags(role),
                metadata=self._metadata(role, extra_metadata),
                on_progress=self._on_progress,
            )
            self.result.uploads.append(
                UploadRecord(
                    role=role,
                    asset_id=res.asset_id,
                    title=title,
                    transfer_id=getattr(res, "transfer_id", None),
                )
            )
            return res.asset_id

        return self._guard(f"upload:{role}", _do)

    def _link(self, from_id, to_id, rel_type, *, analysis_mode=None, qualifier_note=None) -> None:
        if not from_id or not to_id:
            return

        def _do():
            rel = self._client.create_relationship(
                from_id,
                to_id,
                rel_type,
                analysis_mode=analysis_mode,
                qualifier_note=qualifier_note,
                qualifiers={"qick_dataerai_run_id": self.run_id},
            )
            self.result.relationship_ids.append(rel.id)
            return rel.id

        self._guard(f"link:{rel_type}", _do)

    # ── public steps ─────────────────────────────────────────────────────────

    def log_config(self, cfg, *, soccfg=None, prog=None, title=None, description=None,
                   extra_metadata=None) -> Optional[str]:
        """Serialize the experiment configuration to JSON and upload it as the
        run's ``config`` asset.

        Args:
            cfg: The QICK config dict (e.g. ``prog.cfg``) or a ``QickConfig``.
            soccfg: Optional ``QickConfig``/``QickSoc``; its ``get_cfg()`` is
                captured as the hardware config alongside ``cfg``.
            prog: Optional ``AcquireProgram``; its ``dump_prog()`` (ASM + pulse
                state) is captured so the program can be reconstructed.
            title/description: Optional overrides for the asset.
            extra_metadata: Extra metadata for this asset only.

        Returns:
            The config asset id (``None`` if the upload failed in best-effort
            mode). Calling more than once raises ``ValueError``.
        """
        if self._config_logged:
            raise ValueError("log_config() may only be called once per run")
        self._config_logged = True
        title = title or f"{self._title_prefix} — config"

        def _build_and_upload():
            with serialize.temp_upload_file(".json") as path:
                captured = serialize.write_config_json(
                    path, cfg, soccfg=soccfg, prog=prog, run_id=self.run_id
                )
                meta = {"config": captured}
                if extra_metadata:
                    meta.update(extra_metadata)
                return self._upload(
                    "config", path, title=title,
                    description=description or "QICK experiment configuration",
                    extra_metadata=meta,
                )

        # _upload already guards the network call; the serialize step is cheap
        # and deterministic, but wrap the whole thing so a serialize error in
        # best-effort mode is recorded rather than raised.
        return self._guard("config", _build_and_upload)

    def log_acquisition(self, prog=None, data=None, *, decimated=False, expt_pts=None,
                        title=None, description=None, extra_metadata=None) -> Optional[str]:
        """Serialize acquired IQ arrays to an ``.npz`` and upload them as a
        ``raw_data`` asset, then link ``raw_data --acquired_with--> config``.

        Args:
            prog: Optional program; ``di_buf``/``dq_buf``/``loop_dims`` are
                recorded if present.
            data: The return value of ``prog.acquire(...)`` /
                ``acquire_decimated(...)`` (tuple, list, ndarray, or dict).
            decimated: Mark this as a decimated (time-trace) acquisition.
            expt_pts: Optional sweep-point array(s) (auto-pulled from a 3-tuple).
            title/description: Optional overrides.
            extra_metadata: Extra metadata for this asset only.

        Returns:
            The raw_data asset id (``None`` on best-effort failure). May be
            called multiple times; each call makes its own ``acquired_with`` edge
            to the run's single config asset.
        """
        if data is None:
            raise ValueError("log_acquisition() requires the acquired data")
        title = title or f"{self._title_prefix} — raw data"

        def _build_and_upload():
            with serialize.temp_upload_file(".npz") as path:
                shape_meta = serialize.write_iq_npz(
                    path, data, expt_pts=expt_pts, prog=prog, decimated=decimated
                )
                meta = {"acquisition": shape_meta}
                if extra_metadata:
                    meta.update(extra_metadata)
                return self._upload(
                    "raw_data", path, title=title,
                    description=description or "QICK raw acquired IQ data",
                    extra_metadata=meta,
                )

        asset_id = self._guard("raw_data", _build_and_upload)
        if asset_id:
            self._last_raw_asset_id = asset_id
            self._link(asset_id, self.result.config_asset_id, REL_ACQUIRED_WITH)
        return asset_id

    def log_analysis(self, fig=None, *, data=None, of_asset_id=None, analysis_mode=None,
                     title=None, description=None, extra_metadata=None,
                     qualifier_note=None) -> Optional[str]:
        """Upload analysis output(s) and link ``analysis --analysis_of--> raw_data``.

        Provide a matplotlib ``Figure`` (saved as PNG), a ``{name: ndarray}``
        ``data`` dict (saved as ``.npz``), or both (each becomes its own analysis
        asset, each linked to the raw data).

        Args:
            fig: A matplotlib ``Figure`` to capture as a PNG.
            data: A dict of derived arrays to capture as an ``.npz``.
            of_asset_id: Raw-data asset to attribute to; defaults to the most
                recent ``log_acquisition()`` asset. If none exists, no edge is
                made.
            analysis_mode: One of the Dataerai analysis modes
                (``non_destructive``/``altering``/``destructive``/``in_situ``/
                ``ex_situ``/``invasive``/``non_invasive``) or ``None``.
            title/description: Optional overrides.
            extra_metadata: Extra metadata for the asset(s).
            qualifier_note: Free-text note stored on the relationship.

        Returns:
            The last analysis asset id created (``None`` if nothing was uploaded
            or all uploads failed in best-effort mode).
        """
        if fig is None and data is None:
            raise ValueError("log_analysis() requires fig and/or data")
        origin = of_asset_id or self._last_raw_asset_id
        title = title or f"{self._title_prefix} — analysis"
        last_asset_id: Optional[str] = None

        if fig is not None:
            def _build_fig():
                with serialize.temp_upload_file(".png") as path:
                    serialize.write_figure_png(path, fig, dpi=self._fig_dpi)
                    return self._upload(
                        "analysis", path, title=title,
                        description=description or "QICK analysis figure",
                        extra_metadata=dict(extra_metadata or {}, kind="figure"),
                    )

            asset_id = self._guard("analysis", _build_fig)
            if asset_id:
                last_asset_id = asset_id
                self._link(asset_id, origin, REL_ANALYSIS_OF,
                           analysis_mode=analysis_mode, qualifier_note=qualifier_note)

        if data is not None:
            def _build_data():
                with serialize.temp_upload_file(".npz") as path:
                    shape_meta = serialize.write_iq_npz(path, data)
                    return self._upload(
                        "analysis", path,
                        title=f"{title} (data)" if fig is not None else title,
                        description=description or "QICK analysis data",
                        extra_metadata=dict(extra_metadata or {}, kind="data", analysis=shape_meta),
                    )

            asset_id = self._guard("analysis", _build_data)
            if asset_id:
                last_asset_id = asset_id
                self._link(asset_id, origin, REL_ANALYSIS_OF,
                           analysis_mode=analysis_mode, qualifier_note=qualifier_note)

        return last_asset_id


def capture_run(
    client,
    cfg,
    data,
    *,
    owner_type: str,
    owner_id: str,
    soccfg=None,
    prog=None,
    fig=None,
    analysis_data: Optional[dict] = None,
    decimated: bool = False,
    expt_pts=None,
    analysis_mode: Optional[str] = None,
    title_prefix: str = "QICK run",
    collection_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    on_error: str = BEST_EFFORT,
    on_progress: Optional[Callable] = None,
) -> RunResult:
    """Capture a complete QICK experiment in one call.

    Uploads the config and raw ``data``, and — if ``fig`` or ``analysis_data``
    is given — an analysis asset, wiring the standard provenance edges. Equivalent
    to opening a :class:`ProvenanceRun` and calling ``log_config`` /
    ``log_acquisition`` / ``log_analysis`` in order.

    Returns:
        The :class:`RunResult` summarizing what was created.
    """
    run = ProvenanceRun(
        client,
        owner_type=owner_type,
        owner_id=owner_id,
        title_prefix=title_prefix,
        collection_id=collection_id,
        tags=tags,
        metadata=metadata,
        on_error=on_error,
        on_progress=on_progress,
    )
    with run:
        run.log_config(cfg, soccfg=soccfg, prog=prog)
        run.log_acquisition(prog, data, decimated=decimated, expt_pts=expt_pts)
        if fig is not None or analysis_data is not None:
            run.log_analysis(fig=fig, data=analysis_data, analysis_mode=analysis_mode)
    return run.result
