# qick_dataerai

Automatic **provenance capture** from [QICK](https://github.com/openquantumhardware/qick)
experiments into [Dataerai](https://dataerai.com).

When a QICK program runs, `qick_dataerai` uploads the experiment **configuration**,
the **raw acquired IQ data**, and any **analysis** figures as linked Dataerai
*assets*, recording the lineage *config → raw data → analysis* as typed
provenance relationships. Any result can then be traced back to the exact
configuration and raw data that produced it.

## Install

```bash
pip install qick[dataerai]
```

This pulls the [Dataerai Python SDK](https://pypi.org/project/dataerai/) and
matplotlib. You also need the `dataerai` daemon binary installed and to be logged
in (`dataerai auth login`).

## Quick start

```python
from dataerai import DataeraiClient
from qick_dataerai import capture_run

prog = MySweepProgram(soccfg, config)
expt_pts, avg_i, avg_q = prog.acquire(soc, progress=True)

with DataeraiClient(binary_path="/usr/local/bin/dataerai") as client:
    result = capture_run(
        client, prog.cfg, (expt_pts, avg_i, avg_q),
        owner_type="user", owner_id=client.auth_status().user_email,
        soccfg=soccfg, prog=prog, fig=plt.gcf(),
        analysis_mode="non_destructive",
    )
print(result.run_id, result.relationship_ids)
```

For step-by-step capture, use `ProvenanceRun` as a context manager
(`log_config` / `log_acquisition` / `log_analysis`). See the
[QICK docs topic](../../docs/topics/qick_dataerai.rst) for the full guide.

## Provenance model

Edges point from the *derived* asset to its *origin* (Dataerai convention):

- `raw_data --acquired_with--> config`
- `analysis --analysis_of--> raw_data`

Every asset of a run shares a `run_id` (in metadata and as a `qick-run:<id>`
tag); all runs are tagged `qick-dataerai`.

## Try it without hardware

```bash
PYTHONPATH=qick_lib python qick_lib/qick_dataerai/examples/provenance_demo.py
```

Drives `capture_run` against a local recording client and prints the provenance
graph it would create — no board or daemon needed.

## Design & tests

See [`DESIGN.md`](DESIGN.md). Run the tests with:

```bash
PYTHONPATH=qick_lib python -m pytest qick_lib/qick_dataerai/tests/
```
