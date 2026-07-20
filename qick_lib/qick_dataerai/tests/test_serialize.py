"""Tests for qick_dataerai.serialize."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from qick_dataerai import serialize


def test_config_json_roundtrip(tmp_path):
    cfg = {"reps": 10, "expts": 5, "pulse": {"gain": 0.5}}
    path = str(tmp_path / "cfg.json")
    captured = serialize.write_config_json(path, cfg, run_id="run-xyz")

    doc = json.loads(open(path).read())
    assert doc["cfg"] == cfg
    assert doc["qick_dataerai"]["run_id"] == "run-xyz"
    assert doc["qick_dataerai"]["role"] == "config"
    assert captured["has_program"] is False


def test_nonserializable_config_fallback(tmp_path):
    # A set and a lambda are not JSON-serializable and not numpy.
    cfg = {"a_set": {1, 2, 3}, "a_func": (lambda x: x), "ok": 1}
    path = str(tmp_path / "cfg.json")
    serialize.write_config_json(path, cfg, run_id="r")  # must not raise

    doc = json.loads(open(path).read())
    assert isinstance(doc["cfg"]["a_set"], str)  # degraded to str()
    assert isinstance(doc["cfg"]["a_func"], str)
    assert doc["cfg"]["ok"] == 1


def test_config_numpy_values(tmp_path):
    cfg = {"i": np.int64(7), "f": np.float64(1.5), "arr": np.arange(3)}
    path = str(tmp_path / "cfg.json")
    serialize.write_config_json(path, cfg, run_id="r")  # NpEncoder handles numpy

    doc = json.loads(open(path).read())  # parses without error
    # Encoded as real JSON numbers / a structured value — NOT the str() fallback,
    # so a regression to str() (e.g. NpEncoder dropped) would fail here.
    assert isinstance(doc["cfg"]["i"], int) and doc["cfg"]["i"] == 7
    assert isinstance(doc["cfg"]["f"], float)
    assert not isinstance(doc["cfg"]["arr"], str)


def test_config_encoder_fallback_without_npencoder(tmp_path, monkeypatch):
    import sys
    import types

    # Force `from qick.helpers import NpEncoder` to fail -> base json.JSONEncoder,
    # exercising the ndarray -> tolist() last-resort fallback.
    monkeypatch.setitem(sys.modules, "qick.helpers", types.ModuleType("qick.helpers"))
    path = str(tmp_path / "cfg.json")
    serialize.write_config_json(path, {"arr": np.arange(3)}, run_id="r")
    doc = json.loads(open(path).read())
    assert doc["cfg"]["arr"] == [0, 1, 2]


class _FakeProg:
    cfg = {"reps": 1}

    def dump_prog(self):
        return {"ro_chs": {"0": {"freq": 100}}, "envelopes": {"x": np.arange(3)}}


def test_program_dump_captured(tmp_path):
    path = str(tmp_path / "cfg.json")
    captured = serialize.write_config_json(path, {"reps": 1}, prog=_FakeProg(), run_id="r")

    doc = json.loads(open(path).read())
    assert doc["program"]["class"] == "_FakeProg"
    assert "module" in doc["program"]
    assert "dump_prog" in doc["program"]  # ndarray survived encoding
    assert captured["program_class"] == "_FakeProg"


def test_iq_npz_3tuple(tmp_path):
    path = str(tmp_path / "iq.npz")
    data = (np.arange(5), [np.zeros(5)], [np.ones(5)])
    meta = serialize.write_iq_npz(path, data)

    loaded = np.load(path)
    assert set(loaded.files) >= {"expt_pts", "avg_di_ch0", "avg_dq_ch0"}
    assert np.array_equal(loaded["avg_dq_ch0"], np.ones(5))
    assert "avg_di_ch0" in meta["arrays"]
    assert meta["decimated"] is False


@pytest.mark.parametrize(
    "data,expected_key",
    [
        (([np.zeros(3)], [np.ones(3)]), "avg_di_ch0"),  # 2-tuple
        ({"custom": np.ones(2)}, "custom"),              # dict
        (np.zeros(4), "data"),                           # single ndarray
        ([np.zeros((4, 2))], "iq_ch0"),                  # decimated iq_list
    ],
)
def test_iq_npz_variants(tmp_path, data, expected_key):
    path = str(tmp_path / "iq.npz")
    serialize.write_iq_npz(path, data)
    loaded = np.load(path)
    assert expected_key in loaded.files


def test_iq_npz_2tuple_bare_arrays(tmp_path):
    # A 2-tuple of bare ndarrays (not per-channel lists) -> no _ch suffix.
    path = str(tmp_path / "iq.npz")
    serialize.write_iq_npz(path, (np.zeros(3), np.ones(3)))
    loaded = np.load(path)
    assert "avg_di" in loaded.files and "avg_dq" in loaded.files
    assert "avg_di_ch0" not in loaded.files


def test_iq_npz_4tuple(tmp_path):
    path = str(tmp_path / "iq.npz")
    serialize.write_iq_npz(path, (np.zeros(1), np.zeros(1), np.zeros(1), np.zeros(1)))
    loaded = np.load(path)
    assert {"data_0", "data_1", "data_2", "data_3"} <= set(loaded.files)


def test_iq_npz_multi_element_expt_pts(tmp_path):
    path = str(tmp_path / "iq.npz")
    serialize.write_iq_npz(path, {"x": np.zeros(2)}, expt_pts=[np.arange(2), np.arange(3)])
    loaded = np.load(path)
    assert "expt_pts_0" in loaded.files and "expt_pts_1" in loaded.files


class _ProgWithBuffers:
    di_buf = np.array([1, 2, 3])
    dq_buf = np.array([4, 5, 6])
    loop_dims = [2, 3]


def test_iq_npz_prog_buffers_and_loop_dims(tmp_path):
    path = str(tmp_path / "iq.npz")
    meta = serialize.write_iq_npz(
        path, (np.zeros(2), [np.zeros(2)], [np.zeros(2)]), prog=_ProgWithBuffers()
    )
    loaded = np.load(path)
    assert "di_buf" in loaded.files and "dq_buf" in loaded.files
    assert meta["loop_dims"] == [2, 3]


def test_temp_files_cleaned_up():
    seen = {}
    with serialize.temp_upload_file(".json") as path:
        seen["path"] = path
        assert os.path.exists(path)
    assert not os.path.exists(seen["path"])  # removed on exit
