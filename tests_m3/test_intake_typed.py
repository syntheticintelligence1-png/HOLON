"""The I41 intake on a typed milestone (A30 review; not preregistered). The contract is tests_m3/test_intake.py's: the
CLI decides every submission (exit 0, 1 or 2, never a crash) and `holon run` decides the same way. On a typed milestone
(M3 and later) the intake regenerates an I30 law as holon.sorts.run3 writes it (the typed model of
holon.sorts.model3 at gen/<M>/sorts/models/, the law file of holon.sorts.proofs3), requires bend2 and BendTT whatever
the configuration (refusing when BendTT is unavailable), refuses a law whose record holds a bend2-accepted counter-law
(a proof as well would be a kernel disagreement, Q8), and refuses an I24 codec law, for which holon run takes no agent
proof, without regenerating its files. The end-to-end tests pick their laws from the committed records at run time.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._util import ROOT, run_holon

M = "M3"
REASONS = ("bad_submission", "unknown_law", "statement_mismatch", "not_unknown", "escape_hatch", "declares_law",
           "missing_expected_law", "law_file_changed", "generated_file_changed", "kernel_rejected", "over_budget")


def _intake():
    import holon.intake as IN
    return IN


def _record(lid: str) -> dict:
    return json.loads((ROOT / "results" / M / f"{lid}.json").read_text(encoding="utf-8"))


def _write_submission(inbox: Path, lid: str, proof: str, statement_hash: str) -> None:
    d = inbox / lid
    d.mkdir(parents=True)
    (d / "PROOF.bend").write_text(proof, encoding="utf-8")
    (d / "submission.json").write_text(json.dumps({"law_id": lid, "prover": "agent:a30-typed",
                                                   "statement_hash": statement_hash}), encoding="utf-8")


def _tree_digest() -> str:
    h = hashlib.sha256()
    for sub in ("results/" + M, "gen/" + M + "/laws", "gen/" + M + "/proofs", "gen/" + M + "/sorts/models"):
        for p in sorted((ROOT / sub).rglob("*")):
            if p.is_file() and not p.is_symlink():
                h.update(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


class TestTypedKernels(unittest.TestCase):
    def test_typed_milestone_requires_bendtt_whatever_the_configuration(self):
        IN = _intake()
        with mock.patch.object(IN.bend, "verdict_enabled", return_value=False):
            self.assertEqual(IN.required_kernels(M, ROOT), ["bend2", "bendtt"])
        self.assertTrue(IN.typed_milestone(M, ROOT))
        self.assertTrue(IN.typed_laws(M, ROOT), "M3 has I30 laws")
        # I41's state-machine test milestone keeps its rule (no I30 law in its derivation)
        self.assertFalse(IN.typed_milestone("T41", ROOT))

    def test_bendtt_unavailable_refuses_before_any_kernel(self):
        IN = _intake()
        with mock.patch.object(IN.bend, "verdict_available", return_value=False):
            ko = IN.check_kernels({}, None, "gen/M3/proofs/X/PROOF.bend", b"", ["bend2", "bendtt"], 10, {})
        self.assertEqual(ko.reason, "kernel_rejected")
        self.assertIn("BendTT", ko.detail)
        self.assertEqual(ko.kernels["bend2"], "not_run")
        self.assertEqual(ko.kernels["bendtt"], "not_run")


class TestAcceptedCounterLaw(unittest.TestCase):
    """A bend2-accepted counter-law on an UNKNOWN record refuses the submission (not_unknown) before any kernel."""

    class _NoLook:
        def __getattr__(self, name):
            raise AssertionError(f"the decision reached {name}: it must refuse before")

    def _sub(self, tmp: Path):
        IN = _intake()
        _write_submission(tmp, "L_x", "import Base\n", "sha256:" + "1" * 64)
        return IN.read_submission(tmp / "L_x")

    def test_cli_record(self):
        IN = _intake()
        with tempfile.TemporaryDirectory() as t:
            sub = self._sub(Path(t))
            rec = {"status": "UNKNOWN", "statement_hash": "sha256:" + "1" * 64, "prover": "generator",
                   "witnesses": {"e1": {"status": "UNKNOWN", "checker": {"marker": "SOME PROOFS FAIL"}},
                                 "e2": {"status": "UNKNOWN", "checker": {"marker": "ALL PROOFS CHECK"},
                                        "verdict": "failed"}}}
            d = IN.decide(sub, M, rec, self._NoLook(), 10, {}, ROOT)
        self.assertEqual((d["verdict"], d["reason"]), ("refused", "not_unknown"))
        self.assertIn("e2", d["detail"])
        self.assertEqual(IN.accepted_counter_laws(rec), ["e2"])

    def test_run_witnesses(self):
        IN = _intake()
        with tempfile.TemporaryDirectory() as t:
            inbox = Path(t)
            _write_submission(inbox, "L_x", "import Base\n", "sha256:" + "1" * 64)
            got = IN.decide_in_run(M, "L_x", "sha256:" + "1" * 64, {}, "gen/M3/laws/L_x/LAWS.bend",
                                   "gen/M3/proofs/L_x/PROOF.bend", None, {}, ROOT, inbox=inbox,
                                   witnesses={"e": {"checker": {"marker": "ALL PROOFS CHECK"}}})
        d, _proof = got
        self.assertEqual((d["verdict"], d["reason"]), ("refused", "not_unknown"))
        self.assertTrue(d["kernels"]["bend2"] == "not_run")


class TestCliOnTypedMilestone(unittest.TestCase):
    """`holon intake --milestone M3` on a typed law and a codec law: decided (exit 1), never a crash; G1 regenerates
    the typed model and law files and finds them as committed; the tree is unchanged."""

    def test_decides_typed_and_codec_submissions(self):
        IN = _intake()
        typed = sorted(lid for lid in IN.typed_laws(M, ROOT)
                       if (ROOT / "results" / M / f"{lid}.json").is_file() and IN.eligible(_record(lid)))
        self.assertTrue(typed, "an eligible (UNKNOWN) I30 law of M3")
        lid = typed[0]
        codec = sorted(p.stem for p in (ROOT / "results" / M).glob("L_par_*.json")
                       if IN.eligible(json.loads(p.read_text())))
        self.assertTrue(codec, "an eligible (UNKNOWN) codec law of M3")
        from holon.gen.mlaws import law_name
        from holon.sorts.model3 import importable, model_name
        doc = IN.typed_laws(M, ROOT)[lid]["facts"]
        proof = (f"import Base\nimport ../../sorts/models/{importable(model_name(doc))} as M\n"
                 f"import ../../laws/{lid}/LAWS.bend as Laws\n\n"
                 f"def Laws.{law_name(lid)}(kh, s, r_s, a):\n  {{==}}\n")
        before = _tree_digest()
        with tempfile.TemporaryDirectory() as t:
            inbox = Path(t) / "inbox"
            _write_submission(inbox, lid, proof, _record(lid)["statement_hash"])
            _write_submission(inbox, codec[0], f"import Base\nimport ../../laws/{codec[0]}/LAWS.bend as Laws\n",
                              _record(codec[0])["statement_hash"])
            r = run_holon(["intake", "--milestone", M, "--inbox", str(inbox), "--json"], timeout=3600)
        self.assertEqual(r.returncode, 1, r.stderr[-3000:])
        out = json.loads(r.stdout)
        ds = {d["law_id"]: d for d in out["decisions"]}
        self.assertEqual(sorted(ds), sorted([lid, codec[0]]))
        for d in ds.values():
            self.assertEqual(d["verdict"], "refused")
            self.assertIn(d["reason"], REASONS)
        t_ = ds[lid]
        # G1 regenerated the typed model and every law file of M3's I30 laws and found them as committed; the trivial
        # proof reached the kernels and bend2 refused it
        self.assertEqual(t_["differs"], [], t_["detail"])
        self.assertEqual(t_["reason"], "kernel_rejected", t_["detail"])
        self.assertEqual(t_["kernels"], {"bend2": "failed", "bendtt": "not_run", "lean4": "not_applicable"})
        c = ds[codec[0]]
        self.assertEqual(c["reason"], "kernel_rejected", c["detail"])
        self.assertIn("codec", c["detail"])
        self.assertEqual(_tree_digest(), before, "the intake wrote under the repository")


if __name__ == "__main__":
    unittest.main()
