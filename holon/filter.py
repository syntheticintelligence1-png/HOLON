"""Provisional finding filter (BUILD_PLAN I4; whitepaper §9.6, §10.9).

A replayed witness is a reproducible hypothesis. Before it counts as a finding, we record how each
replay side ran (its provenance) and assign a provisional bin:

  model_defect  some side failed: the real code did not do what the model's witness says;
  finding       every side passed and observed its part of the obstruction, at least one side ran
                a public schedule on a deployed system, and no side relied on an internal harness
                or on emulated storage;
  pending       anything else.

`known_limitation` is never assigned here. It needs I40's bounded model checking to show that no
public path exists. Bins are about reproducibility. The v1 `triage` field (intent) is untouched.

The rule is preregistered as tests_m2/_i4.py::expected_bin (I4 prereg), and the tests check that
this module agrees with it on every small input. The tests do not import this module to decide a bin.
"""
from __future__ import annotations

PROVENANCE = ("public_schedule", "internal_harness", "emulated_storage", "library_api")
BINS = ("finding", "model_defect", "pending")
STATUSES = ("passed", "failed", "not_applicable", "not_run")
BLOCKING = ("internal_harness", "emulated_storage")


def sides(entry: dict) -> dict[str, dict]:
    """Side name -> side object of one law entry of a replay report.

    M1 entries keep a law-level verdict and hold their sides under "sides". M0 entries hold sides
    only, because the frozen tests/test_50_replay.py reads every value of an M0 entry as a side.
    """
    if "sides" in entry:
        s = entry["sides"]
        return dict(s) if isinstance(s, dict) else {}
    return {k: v for k, v in entry.items() if isinstance(v, dict)}


def bin_of(ss: dict[str, dict]) -> str:
    if not ss:
        return "pending"
    vals = [s if isinstance(s, dict) else {} for s in ss.values()]
    if any(s.get("status") == "failed" for s in vals):
        return "model_defect"
    if (all(s.get("status") == "passed" and s.get("obstruction_observed") is True for s in vals)
            and any(s.get("provenance") == "public_schedule" for s in vals)
            and not any(s.get("provenance") in BLOCKING for s in vals)):
        return "finding"
    return "pending"


def provenance_of(ss: dict[str, dict]) -> dict[str, str | None]:
    return {k: (s.get("provenance") if isinstance(s, dict) else None) for k, s in sorted(ss.items())}


def claimed_sides(law: dict, registry_facts_sha256: str | None) -> set[str]:
    """The replay sides a REFUTED law's witness claims, from its hashed IR (holon.evidence)."""
    from .evidence import claimed_sides as _claimed
    return _claimed(law, registry_facts_sha256)


def record_fields(report: dict | None, lid: str, witness, witness_sha256) -> tuple[dict, str]:
    """(witness_provenance, filter_bin) of a REFUTED record, from the committed replay report.

    A record whose witness is not the one the report replayed gets ({}, "pending")."""
    if not isinstance(report, dict) or lid not in (report.get("laws") or {}):
        return {}, "pending"
    if (report.get("witness_sha256") or {}).get(lid) != witness_sha256(witness):
        return {}, "pending"
    ss = sides(report["laws"][lid])
    return provenance_of(ss), bin_of(ss)
