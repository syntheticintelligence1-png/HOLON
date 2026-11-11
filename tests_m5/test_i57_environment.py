"""I57: environment modules (BUILD_PLAN §4 I57, milestone M5; whitepaper §12 row L9; I54's definitions.L9). This
docstring is the contract that tests_m5/test_i57_environment.py checks.

The key is I57 (spec/M5/predictions/I57.json). Instruments fixed at the prereg, pinned by sha256 in PINNED:
tests_m5/_i57.py (L9's inputs assembled apart from holon/, the replay rule, admissibility), spec/M5/lib/I57_modules.json
(the three module records), spec/M5/lib/I57_laws.json (the law basis), spec/M5/lib/I57_observe.py (the observation
tool, also pinned in the key's thresholds.observation_tool) with its plan spec/M5/lib/I57_observe_plan.json, and
prompts/I57_environment_modules.md. L9 is measured by I54's definition, unchanged (tests_m5/_i54.py l9).

Rules
  T1 The modules: one per category (da window, l1_chain finality_depth, fetcher availability), provenance premise,
     parameters equal to the key's pinned_parameters (I54 R6).
  T2 The tool: stdlib only, reads neither the module records nor any module parameter, and writes producer, reads and
     source_sha256 from its own run.
  O1 Observation sets: results/M5/env/observations/<set>.json for the three sets of the plan, each an
     inputs.schema.json observation_set, admitted by the key's rule (producer and source_sha256 the pinned tool's,
     reads in the tool's forms); obs-fetch-archive holds n_committed committed items and n_committed / flip_every
     flipped ones; obs-da-beacon holds the plan's n items less the unresolved ones listed in its meta file; every set
     has at least K * slice_min_n items.
  O2 A set that is not admitted is not passed to the metric: its module fails R1.
  G1 `python -m holon m5 env` writes gen/M5/env/ (the model, each law's LAWS.bend and PROOF.bend in the forms module
     and axiom), laws/M5/ENV.json, results/M5/L_env_*.json and results/M5/env/sensitivity.json; --check exits 0.
  G2 Each record: one module premise (the class's module and category) in its environment block, the axiom form's
     havoc premise, statuses equal to the key's construction table (C1), checker evidence for both forms; the checker
     re-run on each PROOF.bend prints ALL PROOFS CHECK with the expected law present; no escape hatch in any
     generated Bend file.
  L1 `python -m holon m5 l9` writes results/M5/l9_I57.json; its L9 equals tests_m5/_i54.py l9 over the inputs that
     tests_m5/_i57.py assembles; --check exits 0.
  P1..P7 the key's predictions (P1 and P4 informed, not counted); R1..R2 its regressions.

Gaps preregistered
  E-G7 Same author: the tool, the plan, the instrument and holon/m5 are written by one session (as I54's E-G1).
  E-G8 The tool is the truth's only producer, and the builder wrote it: the lead's condition makes its provenance
       checkable (pinned sha256, recorded reads), not independent.
  E-G9 Constructed negatives: obs-fetch-archive's committed-false class is flipped hashes, which no archive can hold;
       it shows the fetcher does not fabricate, nothing harder.
  E-G10 The l1 set is one hour of one load-balanced endpoint's views; a depth-d reorg is far rarer than that window.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import unittest

from tests_m5 import _i54 as I
from tests_m5 import _i57 as J
from tests_m5._m5 import ROOT, file_sha256, git, holon_module, load_json, predictions, validate

KEY = "I57"
PINNED = {
    "prompts/I57_environment_modules.md": "22f921641af7afd1fd1f6bb1621809d7149c174d584fcda9f01c8b40bf02baec",
    "spec/M5/lib/I57_laws.json": "9fa1cda69821c20d02c9a482490e01e215f62f01c8573734e67e641ec4bdd335",
    "spec/M5/lib/I57_modules.json": "2c7b17cbafee63f1c045ae9311cd8e778214886dec46b5c8525fac8080e807fc",
    "spec/M5/lib/I57_observe.py": "9ffac5405dfa6cb0fe6770eab280ef64c602bbfe8e6c00f9a4920a820c700b98",
    "spec/M5/lib/I57_observe_plan.json": "49280131915e8c7353a7c33f0d1fd7360c2dff2e716a10bb84b13c3a8c974e17",
    "tests_m5/_i57.py": "86952d9beccd58190b19c7ee4e8b6751005fbea20056dfd763b7f9e588501bf8",
}
STDLIB = {"__future__", "argparse", "bisect", "hashlib", "json", "sys", "time", "urllib", "urllib.error",
          "urllib.request", "pathlib"}


def key() -> dict:
    return predictions(KEY)


def th() -> dict:
    return key()["thresholds"]


def schema() -> dict:
    return load_json(ROOT / "spec" / "M5" / "lib" / "inputs.schema.json")


def holon(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=1800)


def l9_out() -> dict:
    return load_json(ROOT / "results" / "M5" / "l9_I57.json")


def module_report(mid: str) -> dict:
    return l9_out()["L9"]["modules"][mid]


def items(name: str) -> list[dict]:
    doc = J.read_set(name)
    if doc is None:
        raise AssertionError(f"{name}: no observation set")
    return doc["items"]


class TestInstruments(unittest.TestCase):
    def test_pins(self):
        for p, h in sorted(PINNED.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        self.assertEqual(sorted(th()["instruments"]), sorted(PINNED))
        self.assertEqual(th()["observation_tool"]["sha256"], PINNED["spec/M5/lib/I57_observe.py"])

    def test_t1_modules(self):
        mods = J.modules()
        self.assertEqual(sorted((m["category"], m["family"]) for m in mods),
                         [("da", "window"), ("fetcher", "availability"), ("l1_chain", "finality_depth")])
        for m in mods:
            self.assertEqual(validate(m, {"$defs": schema()["$defs"], **schema()["$defs"]["module_record"]}), [])
            self.assertEqual(m["provenance"], "premise")
            self.assertEqual(th()["pinned_parameters"][m["id"]], m["parameters"])
        self.assertEqual(sorted(c["module"] for c in J.laws()),
                         sorted(["env-da-retention", "env-da-retention", "env-fetch-archive", "env-l1-confirmations"]))
        self.assertEqual(sorted(c["id"] for c in J.laws()), sorted(J.LAW_IDS))

    def test_t2_tool(self):
        src = (ROOT / "spec" / "M5" / "lib" / "I57_observe.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module)
        self.assertLessEqual(mods, STDLIB)
        for word in ("I57_modules", "RETENTION", "MIN_EPOCHS", "config/spec", "131072 *", "pinned_parameters"):
            self.assertNotIn(word, src, word)
        self.assertIn('PRODUCER = "spec/M5/lib/I57_observe.py"', src)
        self.assertEqual(th()["observation_tool"]["producer"], "spec/M5/lib/I57_observe.py")


class TestObservations(unittest.TestCase):
    def test_o1_sets(self):
        tool, pl = th()["observation_tool"], J.plan()
        sch = {"$defs": schema()["$defs"], **schema()["$defs"]["observation_set"]}
        for s in J.SETS:
            doc = J.read_set(s)
            self.assertIsNotNone(doc, s)
            self.assertEqual(validate(doc, sch), [], s)
            self.assertEqual(J.admitted(doc, tool), (True, "admitted"), s)
            self.assertEqual(doc["set"], s)
            self.assertIn("FILE spec/M5/lib/I57_observe_plan.json", doc["reads"])
            self.assertGreaterEqual(len(doc["items"]), I.K * I.SLICE_MIN_N, s)
        cfg = pl["sets"]
        fe = items("obs-fetch-archive")
        n = cfg["obs-fetch-archive"]["n_committed"]
        self.assertEqual(sum(1 for o in fe if not o["flipped"]), n)
        self.assertEqual(sum(1 for o in fe if o["flipped"]), len(range(0, n, cfg["obs-fetch-archive"]["flip_every"])))
        meta = load_json(J.OBS_DIR / "obs-da-beacon.meta.json")
        self.assertEqual(len(items("obs-da-beacon")) + len(meta["unresolved"]), cfg["obs-da-beacon"]["n"])

    def test_o2_unadmitted_set_fails_r1(self):
        key_ = key()
        inp = J.l9_inputs(ROOT, key_)
        for s in inp["observation_sets"]:
            if s["set"] == "obs-fetch-archive":
                s["producer"] = "hand"
        tool = th()["observation_tool"]
        inp["observation_sets"] = [s for s in inp["observation_sets"] if J.admitted(s, tool)[0]]
        out = I.l9(inp)
        self.assertFalse(out["modules"]["env-fetch-archive"]["rules"]["R1"])
        self.assertFalse(out["modules"]["env-fetch-archive"]["validated"])


class TestGenerated(unittest.TestCase):
    def test_g1_env_check(self):
        r = holon("m5", "env", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHECK OK", r.stdout)

    def test_g2_records(self):
        bend = holon_module("holon.bend")
        mods = {m["id"]: m for m in J.modules()}
        st = th()["statuses"]
        for cls in J.laws():
            rec = load_json(ROOT / "results" / "M5" / f"{cls['id']}.json")
            self.assertEqual(rec["law_id"], cls["id"])
            m = mods[cls["module"]]
            self.assertEqual(rec["environment"]["premises"],
                             [{"id": m["id"], "category": m["category"], "form": "module", "module": m["id"]}])
            ax = rec["axiom_form"]
            self.assertEqual([(p["category"], p["form"]) for p in ax["environment"]["premises"]],
                             [(m["category"], "havoc")])
            self.assertEqual(rec["status"], st["module"][cls["id"]])
            self.assertEqual(ax["status"], st["axiom"][cls["id"]])
            for form in (rec, ax):
                self.assertTrue(J.checked(form["evidence"]), cls["id"])
                proof = ROOT / form["artifacts"]["proof"]
                lawsf = ROOT / form["artifacts"]["laws"]
                self.assertIn(f"law {form['evidence']['law']}:", lawsf.read_text(encoding="utf-8"))
                r = bend.check(proof)
                self.assertTrue(r.ok, f"{proof}: {r.out[:400]}")
                for f in (proof, lawsf, ROOT / form["artifacts"]["model"]):
                    self.assertEqual(J.hatches(f.read_text(encoding="utf-8")), [], f)
            self.assertEqual(rec.get("ledger_assumptions"), [])
            self.assertEqual(rec.get("model_assumptions"), [])


class TestL9(unittest.TestCase):
    def test_l1_l9_by_i54_definition(self):
        r = holon("m5", "l9", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        want = I.l9(J.l9_inputs(ROOT, key()))
        self.assertEqual(l9_out()["L9"], want)


class TestPredictions(unittest.TestCase):
    def test_p1_da_not_validated_by_r4(self):
        m = module_report("env-da-retention")
        exp = next(p for p in key()["predictions"] if p["id"] == "I57-P1")["expected"]
        got = dict(m["rules"], validated=m["validated"])
        self.assertEqual(got, exp)

    def test_p2_fetch_validated(self):
        m = module_report("env-fetch-archive")
        self.assertTrue(m["validated"], m["rules"])
        self.assertEqual(m["worst"], 1.0)

    def test_p3_l1_not_validated_by_r5_only(self):
        m = module_report("env-l1-confirmations")
        self.assertFalse(m["validated"])
        self.assertEqual(sorted(k for k, v in m["rules"].items() if not v), ["R5"])
        d = th()["pinned_parameters"]["env-l1-confirmations"]["d"]
        self.assertEqual(sum(1 for o in items("obs-l1-depth") if o["head"] - o["t"] >= d and not o["observed"]), 0)

    def test_p4_served_retention_exceeds_minimum(self):
        W = th()["pinned_parameters"]["env-da-retention"]["W"]
        obs = items("obs-da-beacon")
        mid = [o for o in obs if W < o["q"] - o["t"] <= 2 * W]
        self.assertGreater(len(mid), 0)
        self.assertGreaterEqual(sum(o["observed"] for o in mid) / len(mid), 0.9)
        self.assertGreaterEqual(sum(1 for o in obs if not o["observed"] and o["q"] - o["t"] <= 4 * W), 5)

    def test_p5_no_false_below_the_head(self):
        self.assertEqual(sum(1 for o in items("obs-l1-depth") if o["head"] - o["t"] >= 1 and not o["observed"]), 0)

    def test_p6_sensitivity_replays(self):
        s = l9_out()["L9"]["sensitivity"]
        self.assertEqual(sorted(s["counted"]), ["L_env_fact_da_window", "L_env_fact_fetch", "L_env_undo_reorg"])
        self.assertEqual(s["count"], 3)
        self.assertEqual(s["unreplayed"], [])

    def test_p7_l9_outcome(self):
        L = l9_out()["L9"]
        exp = next(p for p in key()["predictions"] if p["id"] == "I57-P7")["expected"]
        for k in ("coverage", "base_coverage", "new_coverage"):
            self.assertEqual([L[k]["numerator"], L[k]["denominator"]], exp[k], k)
        self.assertEqual(L["validated_categories"], exp["validated_categories"])
        self.assertEqual(L["thresholds"], exp["thresholds"])
        self.assertEqual(L["overall"], exp["overall"])


class TestRegressions(unittest.TestCase):
    def test_r1_nothing_earlier_changes(self):
        base = th()["base_commit"]
        paths = ["results/M0", "results/M1", "results/M2", "results/M3", "results/M4", "gen/M0", "gen/M1", "gen/M2",
                 "gen/M3", "gen/M4", "laws/M0", "laws/M1", "laws/M2", "laws/M3", "laws/M4", "replay", "spec/M1",
                 "spec/M2", "spec/M3", "spec/M4", "facts", "predictions", "schemas", "tests", "bend/probes",
                 "spec/M5/preregistration.json", "spec/M5/controls", "spec/M5/predictions/I54.json",
                 "results/M5/definitions_base.json", "results/M5/l10_census_base.json", "tests_m5/_i54.py",
                 "tests_m5/_m5.py", "tests_m5/test_m5_definitions.py", "spec/M5/lib/environment_classes.json",
                 "spec/M5/lib/inputs.schema.json"]
        self.assertEqual(git("diff", "--stat", base, "--", *paths).decode(), "")
        for args in (("audit", "prereg", "--milestone", "M5"), ("m5", "prereg", "--check"),
                     ("m5", "metrics", "--base", "--check")):
            r = holon(*args)
            self.assertEqual(r.returncode, 0, " ".join(args) + "\n" + r.stdout[-2000:] + r.stderr[-2000:])
        r = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_r2_existing_laws_keep_their_outcomes(self):
        base = th()["base_commit"]
        dep = load_json(ROOT / "spec" / "M5" / "preregistration.json")["base"]["l9_dependent"]
        self.assertEqual(len(dep), 222)
        now = {r["law_id"]: r for r in J.records(ROOT, ("M2", "M3"))}
        changed = []
        for lid in dep:
            m = "M3" if (ROOT / "results" / "M3" / f"{lid}.json").is_file() else "M2"
            old = json.loads(git("show", f"{base}:results/{m}/{lid}.json"))
            if now[lid]["status"] != old["status"]:
                changed.append(lid)
        self.assertEqual(changed, [])
        pairs = {p["law"] for p in J.sensitivity(ROOT, th()["observation_tool"])}
        self.assertEqual(pairs & set(dep), set())
        L = l9_out()["L9"]
        self.assertEqual(L["base_coverage"]["numerator"], 0)


if __name__ == "__main__":
    unittest.main()
