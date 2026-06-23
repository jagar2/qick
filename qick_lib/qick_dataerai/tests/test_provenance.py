"""Tests for qick_dataerai.provenance using the FakeClient double."""

from __future__ import annotations

import numpy as np
import pytest

from qick_dataerai import ProvenanceRun, RunError, capture_run
from qick_dataerai.provenance import META_ROLE, META_RUN_ID, TAG_ALL
from qick_dataerai.tests.fakeclient import FakeClient


def _cfg():
    return {"reps": 10, "expts": 5, "start": 0, "step": 1}


def _sweep_data():
    # RAveragerProgram.acquire shape: (expt_pts, avg_di, avg_dq) with one RO channel.
    return (np.arange(5), [np.zeros(5)], [np.ones(5)])


def _make_figure():
    plt = pytest.importorskip("matplotlib.pyplot")
    import matplotlib

    matplotlib.use("Agg")
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    return fig


def _run(client, **kw):
    return ProvenanceRun(client, owner_type="user", owner_id="u-1", **kw)


def test_three_uploads_happy_path():
    fig = _make_figure()
    client = FakeClient()
    with _run(client) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())
        run.log_analysis(fig, analysis_mode="non_destructive")

    assert len(client.uploads) == 3
    roles = [u.metadata[META_ROLE] for u in client.uploads]
    assert roles == ["config", "raw_data", "analysis"]
    suffixes = [u.local_path.rsplit(".", 1)[-1] for u in client.uploads]
    assert suffixes == ["json", "npz", "png"]
    assert all(u.existed for u in client.uploads)  # real content at upload time
    assert not run.result.errors


def test_two_relationships_correct():
    fig = _make_figure()
    client = FakeClient()
    with _run(client) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())
        run.log_analysis(fig, analysis_mode="non_destructive")

    assert len(client.relationships) == 2
    acquired, analysis = client.relationships
    assert acquired.rel_type == "acquired_with"
    assert acquired.from_asset_id == run.result.raw_asset_ids[0]
    assert acquired.to_asset_id == run.result.config_asset_id
    assert analysis.rel_type == "analysis_of"
    assert analysis.from_asset_id == run.result.analysis_asset_ids[0]
    assert analysis.to_asset_id == run.result.raw_asset_ids[0]
    assert analysis.analysis_mode == "non_destructive"
    assert len(run.result.relationship_ids) == 2


def test_run_id_propagated():
    client = FakeClient()
    with _run(client, tags=["lab-a"], metadata={"operator": "alice"}) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())

    for upload in client.uploads:
        assert upload.metadata[META_RUN_ID] == run.run_id
        assert upload.metadata["operator"] == "alice"
        assert f"qick-run:{run.run_id}" in upload.tags
        assert TAG_ALL in upload.tags
        assert "lab-a" in upload.tags
    assert client.uploads[0].metadata[META_ROLE] == "config"
    assert client.uploads[1].metadata[META_ROLE] == "raw_data"
    # qualifiers carry the run id so the edge is discoverable too.
    assert client.relationships[0].qualifiers["qick_dataerai_run_id"] == run.run_id


def test_capture_run_equivalent():
    fig = _make_figure()
    client = FakeClient()
    result = capture_run(
        client, _cfg(), _sweep_data(),
        owner_type="user", owner_id="u-1",
        fig=fig, analysis_mode="non_destructive",
    )
    assert len(client.uploads) == 3
    assert [r.rel_type for r in client.relationships] == ["acquired_with", "analysis_of"]
    assert result.config_asset_id is not None
    assert result.analysis_asset_ids


def test_decimated_acquisition():
    client = FakeClient()
    with _run(client) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=[np.zeros((4, 2))], decimated=True)

    raw_uploads = [u for u in client.uploads if u.metadata[META_ROLE] == "raw_data"]
    assert len(raw_uploads) == 1
    acq_meta = raw_uploads[0].metadata["acquisition"]
    assert acq_meta["decimated"] is True
    assert "iq_ch0" in acq_meta["arrays"]


def test_multiple_acquisitions_share_config():
    client = FakeClient()
    with _run(client) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())
        run.log_acquisition(data=_sweep_data())
        run.log_analysis(data={"amp": np.ones(5)})

    acquired = [r for r in client.relationships if r.rel_type == "acquired_with"]
    assert len(acquired) == 2
    assert all(r.to_asset_id == run.result.config_asset_id for r in acquired)
    # analysis (no of_asset_id) attaches to the most recent raw acquisition.
    analysis = [r for r in client.relationships if r.rel_type == "analysis_of"]
    assert analysis[0].to_asset_id == run.result.raw_asset_ids[-1]


def test_best_effort_upload_failure():
    client = FakeClient(fail_on={"upload"})
    with _run(client) as run:
        assert run.log_config(_cfg()) is None
        assert run.log_acquisition(data=_sweep_data()) is None

    assert run.result.config_asset_id is None
    assert run.result.errors  # failures recorded
    assert client.relationships == []  # no edges without assets


def test_best_effort_relationship_failure():
    client = FakeClient(fail_on={"relationship"})
    fig = _make_figure()
    with _run(client) as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())
        run.log_analysis(fig)

    assert len(client.uploads) == 3  # uploads still succeed
    assert run.result.relationship_ids == []
    assert len(run.result.errors) == 2  # both edges failed, recorded


def test_fail_fast_raises_runerror():
    client = FakeClient(fail_on={"upload"})
    with pytest.raises(RunError):
        with _run(client, on_error="fail_fast") as run:
            run.log_config(_cfg())


def test_owner_and_collection_forwarded():
    client = FakeClient()
    with _run(client, collection_id="col-9") as run:
        run.log_config(_cfg())
        run.log_acquisition(data=_sweep_data())

    for upload in client.uploads:
        assert upload.owner_type == "user"
        assert upload.owner_id == "u-1"
        assert upload.collection_id == "col-9"


def test_log_config_twice_raises():
    client = FakeClient()
    run = _run(client)
    run.log_config(_cfg())
    with pytest.raises(ValueError):
        run.log_config(_cfg())


def test_no_relationship_without_config():
    client = FakeClient()
    with _run(client) as run:
        asset_id = run.log_acquisition(data=_sweep_data())

    assert asset_id is not None
    assert client.relationships == []  # no config origin -> no edge
    assert not run.result.errors


def test_invalid_on_error_rejected():
    with pytest.raises(ValueError):
        _run(FakeClient(), on_error="nope")


def test_fail_fast_on_relationship_failure():
    client = FakeClient(fail_on={"relationship"})
    with pytest.raises(RunError):
        with _run(client, on_error="fail_fast") as run:
            run.log_config(_cfg())             # upload ok (only relationships fail)
            run.log_acquisition(data=_sweep_data())  # raw upload ok, then edge raises
    # The raw upload still happened before the failing edge.
    assert any(u.metadata[META_ROLE] == "raw_data" for u in client.uploads)


def test_log_acquisition_requires_data():
    run = _run(FakeClient())
    with pytest.raises(ValueError):
        run.log_acquisition(data=None)


def test_log_analysis_requires_fig_or_data():
    run = _run(FakeClient())
    with pytest.raises(ValueError):
        run.log_analysis()
