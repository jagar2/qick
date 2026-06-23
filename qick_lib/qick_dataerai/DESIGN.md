# qick_dataerai — design

Date: 2026-06-23
Status: Proposed
Upstream dependency: the Dataerai Python SDK's `DataeraiClient.create_relationship`
(added alongside this package; see the Dataerai repo's
`20260623_QICK_Provenance_Integration` ADR).

## What this adds

A standalone, optional package (`qick_lib/qick_dataerai/`) that captures the
provenance of a QICK experiment into Dataerai. It is a pure consumer of the
Dataerai SDK — it `upload()`s artifacts and `create_relationship()`s the edges —
and adds no hard dependency to the core `qick` package.

## How it works

- **`ProvenanceRun`** (context manager) with `log_config` / `log_acquisition` /
  `log_analysis`, plus a one-call **`capture_run`** wrapper.
- Each step serializes its artifact to a temp file (`serialize.py`), uploads it
  as a Dataerai asset, and links it:
  - `raw_data --acquired_with--> config`
  - `analysis --analysis_of--> raw_data`
- Every asset shares a `run_id` (metadata `qick_dataerai_run_id` + tag
  `qick-run:<id>`) and the `qick-dataerai` tag, so a run is discoverable.

### Serialization (`serialize.py`)
- **config** → JSON: `prog.cfg`/`QickConfig.get_cfg()` + `soccfg.get_cfg()` +
  `prog.dump_prog()`, encoded with a subclass of QICK's `NpEncoder` that degrades
  any non-serializable value to `str()` (so capture never fails on an exotic
  config value).
- **raw data** → `.npz` (`np.savez_compressed`): normalizes every `acquire()`
  shape — `(avg_di, avg_dq)`, `(expt_pts, avg_di, avg_dq)`, decimated `iq_list`,
  a single ndarray, or a dict.
- **analysis** → PNG (matplotlib figure) and/or `.npz` (arrays dict).

### Optional dependencies (`_optional.py`)
`import qick_dataerai` never hard-fails: `numpy`, `matplotlib` and the `dataerai`
SDK are imported lazily via `require(name)`, which raises a clear, actionable
`ImportError` only when a step needs the missing dependency.

### Error handling
`on_error="best_effort"` (default) records per-step failures in
`result.errors` and continues; `on_error="fail_fast"` raises `RunError`.

## Role in QICK

`qick_dataerai` sits beside `qick` as an in-repo extension (like the external
QICK-DAWG / SpinQICK, but bundled). It imports `qick.helpers.NpEncoder` lazily
and is otherwise decoupled — it depends only on the Dataerai SDK's `upload` /
`create_relationship` contract and can target any future relationship API by
changing one call.

## Verification

- **Unit:** `qick_lib/qick_dataerai/tests/` — 35 tests, all green via
  `PYTHONPATH=qick_lib python -m pytest qick_lib/qick_dataerai/tests/`. Coverage:
  - `test_provenance.py` — 3 uploads + 2 correctly-directed relationships,
    `run_id`/tags/role propagation, `capture_run` equivalence, decimated
    acquisition, multiple acquisitions sharing one config, best-effort
    upload/relationship failure, fail-fast `RunError`, owner/collection
    forwarding, double-`log_config` guard, no-config-no-edge, invalid `on_error`.
  - `test_serialize.py` — config JSON round-trip, **non-serializable fallback**,
    numpy values, program dump capture, IQ `.npz` for 3-tuple/2-tuple/dict/
    single/decimated shapes, temp-file cleanup.
  - `test_optional.py` — clear `ImportError` message, `have()`, `log_analysis`
    without matplotlib (best-effort + fail-fast), and a subprocess proving
    `import qick_dataerai` succeeds with numpy/matplotlib/dataerai unimportable.
  Tests use a `FakeClient` double + tempfiles — **no live daemon or socket**.
- **Manual demo:** `examples/provenance_demo.py` (output captured in
  `demos/qick-dataerai/output.txt`) runs the full flow with a recording client.
- **e2e:** Deferred — a true end-to-end needs a logged-in Dataerai stack +
  hardware/sim; the SDK round-trip is covered by the Dataerai repo's acceptance
  criteria (`doc/test-plans/qick-provenance-acceptance-criteria.md`).
