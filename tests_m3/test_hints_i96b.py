"""I96b (= I46c, second half): the refinement hints derived inside the pack, then the one blind rerun (BUILD_PLAN row
I96b; the key I96b of spec/M3/predictions.json). The instrument is tests_m3/_i96b.py. It imports nothing from holon/
or tools/ and reuses I96a's instrument. The instrument, the protocol spec/M3/lib/blind_rerun_i96.json and this
docstring are fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <B> is the key's base_commit, <P> the pack commit (_i96b.pack_commit: the lead at the commit that lands
I96b), and OUT is audit/blind/I96/.

S  The steps.
   S1  `python -m holon binding --fragments-out --milestone M3 [--check]` writes the fragments binding at the path the
       declared spec/M3/lib/fragments.json names (replay/M2/fragments.json), and nothing else: abstract, doc, facts and
       window from that spec; harness, project and target from spec/M3/lib/binding.json; init from binding.json's keys,
       its facts copy's copy_of and the spec's init doc; JSON with indent 1 and sorted keys, plus a newline. It is
       byte-equal to the lead's committed file. --check exits 0 iff the file's bytes are what a run writes. holon
       land's REGEN runs it right after binding, guarded on spec/<M>/lib/fragments.json.
   S2  `python -m holon refinement --milestone M3 [--check]` (holon/refinement.py) writes
       results/M3/sorts/refinement/hints.json and keys.json, and nothing else, by I30's R5: `holon fragments
       --sources m1,boundary,target` over the fragments binding, with the typed model that the step generates from
       the milestone's typing sidecar into a scratch directory as the evaluator. The results/M2 witness source is
       dropped, on the lead and in the pack alike: it is an outcome. --check runs the step afresh and exits 0 iff each
       file's sha256 equals the committed file's (a missing file is a difference). A CI job runs it.
   S3  holon.statement_diff.derived_under caches a refusal as it caches a success: a tree that refuses is derived once
       per process, and every later entry gets the same refusal.
D  The declared inputs (the protocol's given files, each with its sha256): spec/M1/facts/morph_rollup.json,
   spec/M1/lib/morph_rollup.lib.json, spec/M1/lib/morph_rollup.lean.json, spec/M1/policy_hints.mjs (search
   configuration) and spec/M3/lib/fragments.json. spec/lib/go_slices.lib.json is not packed.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  The build.
   B1  holon/refinement.py names no target (_i96a.identifiers and _i96a.literals of <B>).
   B2  S1's --check exits 0 at HEAD, and spec/M3/lib/fragments.json holds no member of the binding spec (harness,
       project, target, init).
   B3  S2's --check exits 0 at HEAD: the lead reproduces hints.json and keys.json.
   B4  H1 for spec/M1/policy_hints.mjs and spec/M3/lib/fragments.json (_i96b.leak_hits over _i96b.record_words of
       HEAD): no hit and no law id. The first 20-byte address of hints.json that the target's code lacks, planted in a
       copy of policy_hints.mjs, is a hit.
   B5  S3 holds: holon.rules.compute is called once for three derived_under calls over a tree that refuses.
   B6  The I96 brief names `python -m holon binding --fragments-out --milestone M3` after `python -m holon binding
       --milestone M3`, and `python -m holon refinement --milestone M3` after `python -m holon sorts --milestone M3`;
       it holds no status word and no law id of the lead's tree.
   B7  The protocol's declared inputs hold their sha256 at HEAD.
P  The blind rerun (OUT is written after the landing), on the session's own typing.
   P1  OUT/refinement.json is _i96b.refinement_rows(blind tree, lead at <P>): hints.json is equal.
   P2  keys.json is not equal; its diff is recorded.
   P3  All 11 of I95's DISCH disagreements are decided as the lead decides them (OUT/breakdown.json "moves").
   P4  Of I95's 17 SYM, UNDO and FACT disagreements, 15 are decided as the lead decides them (SYM 9, UNDO 4, FACT
       attribution 2), and the two FACT kernel laws over blobhash stay UNKNOWN.
   P5  E2 holds in OUT/compare.json: M3 agreement >= 0.90 over at least 185 matched classes, and every disagreement
       is one of I95's 28.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i46 as I46
from tests_m3 import _i96a as A
from tests_m3 import _i96b as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I96b.json"
DISCH = ("L_disch_",)
KERNEL = ("L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash",
          "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash")


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _checkout() -> tuple[Path, str]:
    cfg = json.loads((ROOT / "config" / "holon.json").read_text(encoding="utf-8"))
    doc = json.loads((ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json").read_text(encoding="utf-8"))
    return Path(cfg["replay"]["morph"]), doc["target"]["commit"]


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = _holon("audit", "prereg", "--milestone", "M3", timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i96b.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_the_step_names_no_target(self):
        src = (ROOT / "holon" / "refinement.py").read_text(encoding="utf-8")
        base = _th()["base_commit"]
        self.assertEqual(sorted(w for w in A.identifiers(ROOT, base)
                                if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", src)), [])
        low = src.lower()
        self.assertEqual(sorted(x for x in A.literals(ROOT, base) if x in low), [])

    def test_r4_b2_the_fragments_binding_is_derived(self):
        r = _holon("binding", "--fragments-out", "--milestone", "M3", "--check", timeout=600)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-2000:])
        spec = json.loads((ROOT / "spec" / "M3" / "lib" / "fragments.json").read_text(encoding="utf-8"))
        self.assertFalse({"harness", "project", "target", "init"} & set(spec.get("binding") or spec))

    def test_r5_b3_the_lead_reproduces_the_refinement(self):
        r = _holon("refinement", "--milestone", "M3", "--check", timeout=3600)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])

    def test_r6_b4_the_declared_configuration_holds_no_outcome(self):
        words, ids = I.record_words(ROOT)
        checkout, commit = _checkout()
        for rel in ("spec/M1/policy_hints.mjs", "spec/M3/lib/fragments.json"):
            res = I.leak_hits((ROOT / rel).read_text(encoding="utf-8"), words, ids, checkout, commit)
            self.assertEqual((res["hits"], res["law_ids"]), ([], []), rel)
        hints = json.loads((ROOT / I.REFINEMENT[0]).read_text(encoding="utf-8"))
        plant = None
        for a in sorted(set(re.findall(r"0x[0-9a-f]{40}(?![0-9a-f])", json.dumps(hints["calls"]).lower()))):
            if "0000" in a:
                continue
            g = subprocess.run(["git", "-C", str(checkout), "grep", "-q", "-i", a[2:], commit, "--"], capture_output=True)
            if g.returncode != 0:
                plant = a
                break
        self.assertIsNotNone(plant)
        text = (ROOT / "spec/M1/policy_hints.mjs").read_text(encoding="utf-8") + f"\n// planted {plant}\n"
        self.assertIn(plant[2:], I.leak_hits(text, words, ids, checkout, commit)["hits"])

    def test_r7_b5_derived_under_caches_refusals(self):
        from holon import rules
        from holon import statement_diff as SD
        calls = []

        def refuse(*a, **k):
            calls.append(1)
            raise ValueError("refused: a stale input")

        saved = rules.compute
        rules.compute = refuse
        try:
            with tempfile.TemporaryDirectory() as tmp:
                for _ in range(3):
                    with self.assertRaises(ValueError):
                        SD.derived_under("M3", Path(tmp), "holon-rules/1.4", 1)
        finally:
            rules.compute = saved
            SD._CATALOG_DERIVED.clear()
        self.assertEqual(len(calls), 1)

    def test_r8_b6_the_brief(self):
        text = (ROOT / "spec" / "M3" / "lib" / "blind_session_i96.md").read_text(encoding="utf-8")
        self.assertFalse(I46.STATUS_WORDS.search(text))
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        self.assertFalse([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", text) if w in ids])
        pos = {c: text.find(c) for c in ("python -m holon binding --milestone M3",
                                          "python -m holon binding --fragments-out --milestone M3",
                                          "python -m holon sorts --milestone M3",
                                          "python -m holon refinement --milestone M3")}
        self.assertTrue(all(v >= 0 for v in pos.values()), pos)
        self.assertLess(pos["python -m holon binding --milestone M3"],
                        pos["python -m holon binding --fragments-out --milestone M3"])
        self.assertLess(pos["python -m holon sorts --milestone M3"], pos["python -m holon refinement --milestone M3"])

    def test_r9_b7_the_declared_inputs_hold_their_pins(self):
        proto = json.loads((ROOT / I.PROTOCOL).read_text(encoding="utf-8"))
        pinned = {g["path"]: g["sha256_at_prereg"] for g in proto["scope"]["given"]
                  if re.fullmatch(r"[0-9a-f]{64}", str(g.get("sha256_at_prereg") or ""))}
        self.assertEqual(sorted(pinned), ["spec/M1/facts/morph_rollup.json", "spec/M1/lib/morph_rollup.lean.json",
                                          "spec/M1/lib/morph_rollup.lib.json", "spec/M1/policy_hints.mjs"])
        for p, s in pinned.items():
            self.assertEqual(_sha(p), s, p)


class TestRun(unittest.TestCase):
    def _moves(self) -> dict:
        return _load("breakdown.json")["moves"]

    def test_p1_the_hints_row(self):
        rows = {r["file"]: r for r in _load("refinement.json")}
        self.assertTrue(rows[I.REFINEMENT[0]]["equal"], rows[I.REFINEMENT[0]])

    def test_p2_the_keys_row(self):
        rows = {r["file"]: r for r in _load("refinement.json")}
        r = rows[I.REFINEMENT[1]]
        self.assertFalse(r["equal"])
        self.assertTrue(r["diff"])

    def test_p3_the_eleven_disch_laws(self):
        mv = {l: v for l, v in self._moves().items() if l.startswith(DISCH)}
        self.assertEqual(len(mv), 11)
        self.assertEqual(sorted(l for l, v in mv.items() if v["blind"] != v["lead"]), [])

    def test_p4_the_seventeen(self):
        mv = {l: v for l, v in self._moves().items() if not l.startswith(DISCH)}
        self.assertEqual(len(mv), 17)
        moved = sorted(l for l, v in mv.items() if v["blind"] == v["lead"])
        self.assertEqual(sorted(set(mv) - set(moved)), sorted(KERNEL))
        self.assertEqual({l: mv[l]["blind"] for l in KERNEL}, {l: "UNKNOWN" for l in KERNEL})

    def test_p5_the_exit_e2(self):
        m3 = _load("compare.json")["milestones"]["M3"]
        self.assertGreaterEqual(m3["matched"], 185)
        self.assertGreaterEqual(m3["agree"], 0.90 * m3["matched"])
        i95 = set(_load("breakdown.json")["moves"])
        new = sorted(l for d in m3["disagreements"] for l in d["lead"]["laws"] if l not in i95)
        self.assertEqual(new, [])


if __name__ == "__main__":
    unittest.main()
