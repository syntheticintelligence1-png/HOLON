"""I4 helpers: replay-report sides and the provisional finding-filter rule, fixed at the I4 prereg.

This module is the decision rule for the I4 bin predictions (BUILD_PLAN §0.1, "instruments are
inputs"). holon/filter.py must agree with `expected_bin` on every input
(tests_m2/test_filter.py::TestFilterRule); the tests never import holon/filter.py to decide a bin.

Report shapes (replay/<M>/report.json, written by `holon replay`):
- M0: laws[lid] maps each side name ("go", "solidity") to a side object directly. The frozen
  tests/test_50_replay.py reads every value of laws[lid] as a side, so M0 entries hold sides only.
- M1: laws[lid] keeps its law-level verdict (status, obstruction_reproduced, observed, traces;
  tests_m1 reads them) and adds laws[lid]["sides"], mapping each side name to a side object.

A side object has at least:
  status                "passed" | "failed" | "not_applicable" | "not_run"
  obstruction_observed  bool, set by the harness from the real code's output
  provenance            one of PROVENANCE
  observed, command     what the real code did, and the exact command
"""
from __future__ import annotations

from tests_m2._m2 import ROOT, load_json

PROVENANCE = ("public_schedule", "internal_harness", "emulated_storage", "library_api")
BINS = ("finding", "model_defect", "pending")
STATUSES = ("passed", "failed", "not_applicable", "not_run")
BLOCKING = ("internal_harness", "emulated_storage")


def report(m: str, root=ROOT) -> dict:
    return load_json(root / "replay" / m / "report.json")


def sides(m: str, entry: dict) -> dict[str, dict]:
    """Side name -> side object of one law entry of replay/<m>/report.json."""
    if m == "M0":
        return dict(entry)
    return dict(entry["sides"])


def expected_bin(ss: dict[str, dict]) -> str:
    """The provisional filter_bin of a REFUTED record from its replay sides (BUILD_PLAN I4).

    - model_defect: some side failed (the real code did not do what the model's witness says);
    - finding: every side passed and observed its part of the obstruction, at least one side ran
      a public schedule on a deployed system, and no side relied on an internal harness or on
      emulated storage;
    - pending: anything else (a side not run or model-only, an obstruction not observed, or no
      public schedule). known_limitation is never assigned before I40.
    """
    if not ss:
        return "pending"
    if any(s.get("status") == "failed" for s in ss.values()):
        return "model_defect"
    if (all(s.get("status") == "passed" and s.get("obstruction_observed") is True for s in ss.values())
            and any(s.get("provenance") == "public_schedule" for s in ss.values())
            and not any(s.get("provenance") in BLOCKING for s in ss.values())):
        return "finding"
    return "pending"


def hexbytes(h: str) -> bytes:
    assert isinstance(h, str) and h.startswith("0x"), h
    return bytes.fromhex(h[2:])
