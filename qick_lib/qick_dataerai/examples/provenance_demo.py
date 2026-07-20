"""Runnable, hardware-free demo of qick_dataerai provenance capture.

This does NOT need a QICK board or a running Dataerai daemon. It synthesizes a
sweep dataset and drives :func:`qick_dataerai.capture_run` against a small local
recording client that prints what *would* be uploaded/linked — so you can see the
exact provenance graph a real run produces.

Run it with::

    PYTHONPATH=qick_lib python qick_lib/qick_dataerai/examples/provenance_demo.py

In a real experiment you would instead pass a ``dataerai.DataeraiClient``::

    from dataerai import DataeraiClient
    with DataeraiClient(binary_path="/path/to/dataerai") as client:
        capture_run(client, prog.cfg, prog.acquire(soc),
                    owner_type="user", owner_id=client.auth_status().user_email,
                    soccfg=soccfg, prog=prog)
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from qick_dataerai import capture_run


class RecordingClient:
    """A stand-in for DataeraiClient that prints uploads and links."""

    def __init__(self) -> None:
        self._n = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def upload(self, local_path, *, title, owner_type, owner_id, collection_id=None,
               description=None, alias=None, tags=None, metadata=None, on_progress=None):
        self._n += 1
        asset_id = f"asset-{self._n}"
        role = metadata.get("qick_dataerai_role")
        print(f"  upload  [{role:9}] {asset_id}  '{title}'  ({local_path.split('.')[-1]})")
        return SimpleNamespace(transfer_id=f"xfer-{self._n}", asset_id=asset_id,
                               content_id=f"content-{self._n}", total_bytes=0, chunk_count=1)

    def create_relationship(self, from_asset_id, to_asset_id, rel_type, *,
                            analysis_mode=None, qualifier_note=None,
                            qualifier_time=None, qualifiers=None):
        n = getattr(self, "_rn", 0) + 1
        self._rn = n
        mode = f"  [{analysis_mode}]" if analysis_mode else ""
        print(f"  link    {from_asset_id} --{rel_type}--> {to_asset_id}{mode}")
        return SimpleNamespace(id=f"rel-{n}", type=rel_type, direction="outgoing",
                               from_asset_id=from_asset_id, to_asset_id=to_asset_id,
                               analysis_mode=analysis_mode, qualifier_note=qualifier_note,
                               related_asset={"id": to_asset_id})


def main() -> None:
    # A typical RAveragerProgram-style sweep config + acquired data.
    cfg = {"reps": 100, "expts": 21, "start": 0, "step": 0.1, "readout_length": 1.0}
    expt_pts = np.linspace(0, 2, 21)
    avg_i = [np.cos(expt_pts)]      # one readout channel
    avg_q = [np.sin(expt_pts)]
    data = (expt_pts, avg_i, avg_q)
    analysis = {"amplitude": np.hypot(avg_i[0], avg_q[0])}

    print("Capturing a QICK run into Dataerai (dry run):\n")
    client = RecordingClient()
    result = capture_run(
        client, cfg, data,
        owner_type="user", owner_id="demo@example.com",
        analysis_data=analysis, analysis_mode="non_destructive",
        tags=["t1-experiment"],
    )

    print("\nRun summary:")
    print(f"  run_id           : {result.run_id}")
    print(f"  config asset     : {result.config_asset_id}")
    print(f"  raw data assets  : {result.raw_asset_ids}")
    print(f"  analysis assets  : {result.analysis_asset_ids}")
    print(f"  relationships    : {result.relationship_ids}")
    print(f"  errors           : {result.errors or 'none'}")


if __name__ == "__main__":
    main()
