Capturing provenance with Dataerai
==================================

The ``qick_dataerai`` package automatically captures the **provenance** of a QICK
experiment into `Dataerai <https://dataerai.com>`_: when a program runs, it
uploads the experiment configuration, the raw acquired IQ data, and any analysis
figures as linked Dataerai *assets*. The lineage of a measurement —
*configuration → raw data → analysis* — is recorded as typed relationships, so
any result can be traced back to the exact configuration and raw data that
produced it.

This package ships in the QICK repository but is optional: it is only imported
when you use it, and it depends on the `Dataerai Python SDK
<https://pypi.org/project/dataerai/>`_.

Installation
------------

.. code-block:: bash

   pip install qick[dataerai]

You must also have the ``dataerai`` daemon binary installed and be logged in
(``dataerai auth login``) before uploading.

One-call capture
----------------

For the common case — capturing a config, an acquisition, and one analysis
figure — use :func:`qick_dataerai.capture_run`:

.. code-block:: python

   import matplotlib.pyplot as plt
   from dataerai import DataeraiClient
   from qick_dataerai import capture_run

   prog = MySweepProgram(soccfg, config)
   expt_pts, avg_i, avg_q = prog.acquire(soc, progress=True)

   plt.plot(expt_pts, avg_i[0])
   fig = plt.gcf()

   with DataeraiClient(binary_path="/usr/local/bin/dataerai") as client:
       result = capture_run(
           client, prog.cfg, (expt_pts, avg_i, avg_q),
           owner_type="user", owner_id=client.auth_status().user_email,
           soccfg=soccfg, prog=prog,
           fig=fig, analysis_mode="non_destructive",
       )
   print(result.run_id, result.relationship_ids)

Step-by-step capture
--------------------

For finer control — multiple acquisitions, several analyses, or custom titles —
open a :class:`qick_dataerai.ProvenanceRun` and log each step:

.. code-block:: python

   from dataerai import DataeraiClient
   from qick_dataerai import ProvenanceRun

   with DataeraiClient(binary_path="/usr/local/bin/dataerai") as client:
       with ProvenanceRun(client, owner_type="user",
                          owner_id=client.auth_status().user_email,
                          title_prefix="T1 measurement") as run:
           run.log_config(prog.cfg, soccfg=soccfg, prog=prog)

           expt_pts, avg_i, avg_q = prog.acquire(soc, progress=True)
           run.log_acquisition(prog, (expt_pts, avg_i, avg_q))

           # ... fit / plot ...
           run.log_analysis(plt.gcf(), analysis_mode="non_destructive")

       print(run.result.run_id)

Every asset created in a run shares a ``run_id`` — stored both in the asset
metadata (``qick_dataerai_run_id``) and as a ``qick-run:<id>`` tag — and every
run is tagged ``qick-dataerai``. You can therefore find one run, or all QICK
runs, by tag search in Dataerai.

The provenance model
--------------------

``qick_dataerai`` creates two kinds of typed relationship, following Dataerai's
convention that an edge points from the *derived* asset to its *origin*:

* ``raw_data --acquired_with--> config`` — the raw data was acquired with this
  configuration/program.
* ``analysis --analysis_of--> raw_data`` — the analysis was computed from this
  raw data.

The optional ``analysis_mode`` on an analysis edge records how the measurement
affected the sample (one of ``non_destructive``, ``altering``, ``destructive``,
``in_situ``, ``ex_situ``, ``invasive``, ``non_invasive``).

What gets serialized
--------------------

* **config** — a JSON document combining ``prog.cfg`` (or a ``QickConfig``), the
  hardware ``soccfg`` (via ``get_cfg()``), and the program's ``dump_prog()``
  (ASM + pulse state). numpy values are packed with QICK's own encoder; anything
  that cannot be serialized is stored as its ``str()`` so capture never fails on
  an exotic config value.
* **raw data** — the return value of ``acquire()`` / ``acquire_decimated()``
  normalized into a compressed ``.npz`` (per-channel ``avg_di_ch*`` / ``avg_dq_ch*``,
  ``expt_pts``, decimated ``iq_ch*``, and a ``{name: ndarray}`` dict are all
  handled).
* **analysis** — a matplotlib figure saved as a PNG and/or a ``{name: ndarray}``
  dict saved as an ``.npz``.

Error handling
--------------

By default a run is **best-effort** (``on_error="best_effort"``): if an upload or
link fails, the failure is recorded in ``run.result.errors`` and the run
continues, so a provenance hiccup never crashes the physics workflow. Pass
``on_error="fail_fast"`` to raise :class:`qick_dataerai.RunError` on the first
failure instead.

Trying it without hardware
--------------------------

A full tutorial notebook lives at ``qick_demos/10_Dataerai_provenance.ipynb``: it
simulates a T1 measurement and captures it against a local recording client, so it
runs end-to-end **without a board or a Dataerai login**, then shows how to swap in
the real :class:`dataerai.DataeraiClient`. A minimal script version is at
``qick_lib/qick_dataerai/examples/provenance_demo.py``.
