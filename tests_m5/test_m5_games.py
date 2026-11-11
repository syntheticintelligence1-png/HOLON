"""I56: bounded games over F(M3) (BUILD_PLAN §4 I56; whitepaper §12 row L6, §12.4, §11.4 N3, §11.3 O35, §5.7). This
docstring is the contract that tests_m5/test_m5_games.py checks.

The definitions are thresholds.definitions of the key I56 (spec/M5/predictions/I56.json): immutable under the prereg
audit. L6 itself is I54's definition (key I54), unchanged; I56 adds V9 and the corpus rule that the lead's review of I54
(PR #134, comment 6800406794, conditions 1 and 5) requires before any record is scored. Instruments fixed at the
prereg, pinned by sha256 in PINNED: tests_m5/_i56.py (the definitions written out a second time, independently of
holon/games), spec/M5/lib/games_M3.json (the target's documents, run member, classes and trusted flags, N3 and O35
anchors) and prompts/I56_games.md. The key also pins I54's 14 game controls and the sidecar by sha256.

Rules (tests below; the key's definitions hold the full text)
  K1 The instruments are the preregistered ones; the key's control and sidecar pins hold; the sidecar's documents and
     initial state hash to their pins; its classes are exactly the instrument's (G-C1, G-C2), each with a trusted flag.
  F1 `python -m holon games flows` writes gen/M5/games/value_flows.json and results/M5/games/v9.json; --check exits 0.
     Every value-moving action the instrument finds (VM1-VM4) has a complete entry listing each of its constructs;
     the document names the sidecar's documents by sha256.
  F2 results/M5/games/v9.json is the instrument's V9 coverage of the committed document.
  F3 spec/M5/lib/games_M3_flows.json pins the document's sha256, and its first commit changes no file under
     results/M5/games/ and is an ancestor of every commit that adds a game record (V8 before the records).
  C1 One control game record per I54 game control (kind control, horizon the document's number of actions), valid
     under I54's V1-V8; its class verdicts, strategy lengths and payoffs are the instrument's (I54's enumeration).
  C2 The engine reads no control's truth, id, family or file name: a renamed control without its truth gets the
     same verdicts (G-K3).
  T1 A target game record exists exactly for the members of F(M3) whose witness has a schedule that runs (G-W, G-R);
     its classes, verdicts, payoffs, witness length and horizon are the instrument's; no target class is irrational
     or irrational_bounded (G-T3); every record validates against I54's inputs schema.
  T2 results/M5/games/attempts.json lists every member of F(M3) without a game record with a reason, and every
     UNKNOWN class of a target record.
  B1 Every game module's LAWS.bend states exactly its expected laws, holds no escape hatch, and Bend prints ALL PROOFS
     CHECK on its PROOF.bend; a record's evidence names that law.
  E1 N3: one recommit and one continuation law per n3 law with a non-empty continuation, in laws/M5/games/, each with
     premises P-gas (and P-bond for the recommit law); their statuses follow the instrument's reading of the run;
     a law with an empty continuation is UNKNOWN with its reason.
  E2 O35: the backlog writers are the instrument's; each writer with no construct other than VM1 has a PROVED ∀k law.
  L1 results/M5/games/l6.json is the instrument's l6_v9 over the committed records (I54's l6 after V9), with the
     corpus not_measured pending the corpus-truth key; with V9 failing, holon's metric demotes every target record
     (V9) and judges decided not_judged, as the instrument does.
  D1 `python -m holon games run --check` exits 0 (every file regenerates byte for byte); holon/games names no
     document's contract and no law id of the sidecar (target-agnostic).

Predictions (I56-P1..P5; outcomes recorded nowhere before the build): N3's recommit law PROVED; N3's continuation law
PROVED; O35's backlog writers commitBatch, commitBatchWithProof and commitState, each ∀k law PROVED; the 14 controls
decided correctly; decided over F(M3) between 1 and 10 of 49. A miss is a Surprise, never a reason to edit anything.
Regressions (I56-R1..R3): M0-M4 unchanged with the audits and the freeze check; I54's outputs unchanged; F(M3) = 49.

Gaps preregistered: the key's E-G1..E-G6 (same author; payoffs from the extracted evaluator, not inside Bend; witness
games under-approximate a target's strategies; cross-member amounts are atoms; no corpus scoring; trusted flags are a
judgment).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m5 import _i54 as I
from tests_m5 import _i56 as G
from tests_m5._m5 import ROOT, blobs, dumps, file_sha256, git, holon_module, load_json, predictions, tree_files, validate

KEY = "I56"
PINNED = {
    "prompts/I56_games.md": "e0a4ce93195443cc998726e65ae931447423432de5e198de57bd973289c559db",
    "spec/M5/lib/games_M3.json": "78967599ce56d713b3adb8c5160505bb2602b1956f6f2ecf1760833517b8e2da",
    "tests_m5/_i56.py": "30ae6e5fcc80a8eb06e8255bd1ef11223c79feaefb264d17bf9b805fb29bb9aa",
}
GAMES = ROOT / "results" / "M5" / "games"
GEN = ROOT / "gen" / "M5" / "games"
LAWS = ROOT / "laws" / "M5" / "games"
FLOWS = GEN / "value_flows.json"
PIN = ROOT / "spec" / "M5" / "lib" / "games_M3_flows.json"


def key() -> dict:
    return predictions(KEY)


def i54_base() -> dict:
    return load_json(ROOT / "spec" / "M5" / "preregistration.json")["base"]


def population() -> list[str]:
    return sorted(i54_base()["l6_findings"])


def schema() -> dict:
    return load_json(ROOT / "spec" / "M5" / "lib" / "inputs.schema.json")


def holon(*args: str, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout)


_C: dict = {}


def sc() -> dict:
    if "sc" not in _C:
        _C["sc"] = G.sidecar()
        _C["docs"] = G.documents(_C["sc"])
    return _C["sc"]


def docs() -> dict:
    sc()
    return _C["docs"]


def record_of(fid: str) -> dict:
    return load_json(ROOT / "results" / "M3" / f"{fid}.json")


def game_records() -> dict:
    d = GAMES / "records"
    return {json.loads(p.read_text())["finding"]: json.loads(p.read_text()) for p in sorted(d.glob("*.json"))}


def controls() -> list[dict]:
    return [load_json(ROOT / p) for p in sorted(key()["thresholds"]["pins"]["controls"])]


def expect_target(fid: str, game: dict | None) -> dict:
    return {"classes": {c["id"]: c["trusted"] for c in sc()["classes"]},
            "witness_length": game["steps"] if game else None,
            "value_flows_sha256": load_json(PIN)["value_flows_sha256"]}


def target_games() -> dict:
    if "tg" not in _C:
        _C["tg"] = {fid: G.target_game(record_of(fid), sc(), docs()) for fid in population()}
    return _C["tg"]


def bend_check(proof: Path) -> str:
    hb = holon_module("holon.bend")
    r = hb.check(proof)
    return (r.out or "").strip().splitlines()[0] if (r.out or "").strip() else ""


class TestPreregistration(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):  # K1
        self.assertTrue(PINNED)
        for p, h in sorted(PINNED.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        self.assertEqual(sorted(PINNED), sorted(key()["thresholds"]["instruments"]))

    def test_pins(self):  # K1
        pins = key()["thresholds"]["pins"]
        self.assertEqual(len(pins["controls"]), 14)
        for p, h in sorted({**pins["controls"], **pins["sidecar"]}.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        for d in sc()["documents"]:
            self.assertEqual(file_sha256(ROOT / d["path"]), d["sha256"], d["path"])
        self.assertEqual(file_sha256(ROOT / sc()["run"]["init"]), sc()["run"]["init_sha256"])

    def test_classes(self):  # K1
        ids = [c["id"] for c in sc()["classes"]]
        self.assertEqual(ids, G.classes(sc(), docs()))
        self.assertTrue(set(sc()["member_caller"]) <= set(G.groups(docs())))
        for c in sc()["classes"]:
            self.assertIsInstance(c["trusted"], bool, c["id"])
            self.assertTrue(c["why"], c["id"])
            self.assertEqual(c["trusted"], c["id"].endswith(".onlyOwner"), c["id"])


class TestFlows(unittest.TestCase):
    def test_value_flows_document(self):  # F1
        r = holon("games", "flows", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = load_json(FLOWS)
        self.assertEqual(doc["documents"], {d["member"]: d["sha256"] for d in sc()["documents"]})
        acts = [e["action"] for e in doc["entries"]]
        self.assertEqual(acts, sorted(acts))
        vm = G.value_moving(docs())
        self.assertEqual(sorted(acts), sorted(vm), "one entry per value-moving action, and no other")
        for e in doc["entries"]:
            got = {f["construct"] for f in e["flows"]}
            self.assertTrue(set(vm[e["action"]]) <= got, e["action"])
            self.assertTrue(e["complete"], e["action"])
        self.assertEqual(sorted((x["member"], x["family"], x["asset"]) for x in doc["ledgers"]),
                         sorted((m, f, a) for (m, f), a in G.claim_ledgers(docs()).items()))

    def test_v9_report(self):  # F2
        self.assertEqual(load_json(GAMES / "v9.json"), G.v9_coverage(load_json(FLOWS), docs()))

    def test_flows_pin_precedes_records(self):  # F3
        pin = load_json(PIN)
        self.assertEqual(pin["value_flows_sha256"], file_sha256(FLOWS))
        first = git("log", "--diff-filter=A", "--format=%H", "--", str(PIN.relative_to(ROOT))).decode().split()
        self.assertTrue(first, "the pin is not committed")
        c0 = first[-1]
        changed = git("show", "--name-only", "--format=", c0).decode().split()
        self.assertFalse([f for f in changed if f.startswith("results/M5/games/")], changed)
        adds = git("log", "--diff-filter=A", "--format=%H", "--", "results/M5/games/records/").decode().split()
        self.assertTrue(adds, "no game record is committed")
        for c in adds:
            self.assertNotEqual(c, c0)
            r = subprocess.run(["git", "merge-base", "--is-ancestor", c0, c], cwd=ROOT)
            self.assertEqual(r.returncode, 0, f"{c} adds a game record but does not descend from the pin {c0}")


class TestControls(unittest.TestCase):
    def test_control_records(self):  # C1
        recs = game_records()
        sch = schema()
        for doc in controls():
            rec = recs.get(doc["id"])
            self.assertIsNotNone(rec, doc["id"])
            self.assertEqual(rec["kind"], "control")
            self.assertEqual(rec["horizon"], len(doc["actions"]))
            self.assertEqual(validate(rec, dict(sch, **sch["$defs"]["game_record"])), [], doc["id"])
            exp = {"classes": {a["id"]: a["trusted"] for a in doc["actors"]}, "witness_length": len(doc["witness"]),
                   "value_flows_sha256": I.flows_sha256(doc)}
            self.assertEqual(I.validate_game(rec, exp), [], doc["id"])
            truth = G.control_record_truth(doc)
            got = {c["class"]: (c["verdict"], c.get("strategy_length"), c["payoff"]) for c in rec["classes"]}
            self.assertEqual(got, truth, doc["id"])

    def test_engine_reads_no_truth_or_name(self):  # C2
        eng = holon_module("holon.games.engine")
        for doc in controls():
            blind = {k: v for k, v in doc.items() if k not in ("truth", "family")}
            blind["id"] = "g_blind_0"
            blind["horizon"] = 1
            a = eng.solve(doc)
            b = eng.solve(blind)
            self.assertEqual(a["classes"], b["classes"], doc["id"])


class TestTargets(unittest.TestCase):
    def test_target_records(self):  # T1
        recs = game_records()
        sch = schema()
        for fid, (game, why) in sorted(target_games().items()):
            rec = recs.get(fid)
            if game is None:
                self.assertIsNone(rec, f"{fid}: a record without a game ({why})")
                continue
            self.assertIsNotNone(rec, fid)
            self.assertEqual(rec["kind"], "target")
            self.assertEqual(validate(rec, dict(sch, **sch["$defs"]["game_record"])), [], fid)
            self.assertEqual((rec["witness_length"], rec["horizon"]), (game["steps"], game["steps"]), fid)
            got = {c["class"]: c for c in rec["classes"]}
            self.assertEqual(got, game["classes"], fid)
            self.assertEqual(rec["verdict"], game["verdict"], fid)
            self.assertFalse([c for c in rec["classes"] if c["verdict"] in ("irrational", "irrational_bounded")], fid)
            self.assertEqual(I.validate_game(rec, expect_target(fid, game)), [], fid)
        self.assertFalse(set(recs) - set(population()) - {d["id"] for d in controls()})

    def test_attempts(self):  # T2
        att = load_json(GAMES / "attempts.json")
        recs = game_records()
        for fid in population():
            if fid not in recs:
                self.assertTrue(att["findings"][fid]["reason"], fid)
            else:
                for c in recs[fid]["classes"]:
                    if c["verdict"] == "UNKNOWN":
                        self.assertTrue(att["classes"][fid][c["class"]], (fid, c["class"]))


class TestBend(unittest.TestCase):
    def test_modules_check(self):  # B1
        recs = game_records()
        mods = sorted(p.parent for p in (GEN / "bend").glob("*/LAWS.bend"))
        self.assertTrue(mods)
        named = {r["evidence"]["law"] for r in recs.values()}
        for d in mods:
            laws = re.findall(r"^law (\S+):", (d / "LAWS.bend").read_text(), re.M)
            self.assertTrue(laws, d)
            for f in ("game.bend", "LAWS.bend", "PROOF.bend"):
                t = (d / f).read_text()
                self.assertNotRegex(t, r"\?[A-Za-z_]|@unsafe|def [A-Za-z0-9_.]+\?\(|import \"", f"{d}/{f}")
            self.assertEqual(bend_check(d / "PROOF.bend"), "ALL PROOFS CHECK", d)
            exp = json.loads((d / "laws.json").read_text())
            self.assertEqual(sorted(laws), sorted(exp), d)
        code = {"rational": "G.Rat{}", "irrational": "G.Irr{}", "irrational_bounded": "G.IrrB{}", "UNKNOWN": "G.Unk{}"}
        for r in recs.values():
            self.assertEqual((r["evidence"]["marker"], r["evidence"]["law_present"]), ("ALL PROOFS CHECK", True))
            hits = [d for d in mods if r["evidence"]["law"] in json.loads((d / "laws.json").read_text())]
            self.assertEqual(len(hits), 1, r["finding"])
            text = (hits[0] / "LAWS.bend").read_text()
            m = re.search(rf"^law {re.escape(r['evidence']['law'])}:\n((?:  .*\n)+)", text, re.M)
            self.assertIsNotNone(m, r["finding"])
            vec = "[" + ", ".join(code[c["verdict"]] for c in r["classes"]) + "]"
            self.assertIn(f"{{G.verdicts() == {vec} : List<&2, G.V>}}", m.group(1), r["finding"])
        self.assertTrue(named)


class TestEcon(unittest.TestCase):
    def econ(self, lid: str) -> dict:
        return load_json(GAMES / "econ" / f"{lid}.json")

    def test_n3(self):  # E1
        for law in sc()["n3"]["laws"]:
            rd = G.n3(record_of(law), sc(), docs())
            rec_r = self.econ(f"L_econ_n3_recommit_{law}")
            rec_c = self.econ(f"L_econ_n3_continuation_{law}")
            if rd["status"] == "UNKNOWN":
                self.assertEqual((rec_r["status"], rec_c["status"]), ("UNKNOWN", "UNKNOWN"), law)
                self.assertTrue(rec_r["reason"])
                continue
            want_r = G.n3_status(rd["recommit"] == "negative" and rd["refuse"] == "nonneg",
                                 "undetermined" in (rd["recommit"], rd["refuse"]))
            adv = list(rd["adversaries"].values())
            want_c = G.n3_status(bool(adv) and all(v == "nonneg" for v in adv), "undetermined" in adv)
            self.assertEqual(rec_r["status"], want_r, law)
            self.assertEqual(rec_c["status"], want_c, law)
            self.assertEqual(sorted(rec_r["premises"]), ["P-bond", "P-gas"])
            self.assertEqual(sorted(rec_c["premises"]), ["P-gas"])
            for r in (rec_r, rec_c):
                self.assertTrue((LAWS / f"{r['law_id']}.json").is_file(), r["law_id"])
                if r["status"] in ("PROVED", "REFUTED"):
                    self.assertEqual((r["checker"]["marker"], r["checker"]["law_present"]), ("ALL PROOFS CHECK", True))
                else:
                    self.assertTrue(r["reason"], r["law_id"])

    def test_o35(self):  # E2
        st = G.o35_static(sc(), docs())
        summ = load_json(GAMES / "summary.json")
        self.assertEqual(sorted(summ["o35_writers"]), sorted(st))
        for b, cons in sorted(st.items()):
            r = self.econ(f"L_econ_o35_backlog_{b}")
            if set(cons) <= {"VM1"}:
                self.assertEqual(r["status"], "PROVED", b)
                self.assertEqual((r["checker"]["marker"], r["checker"]["law_present"]), ("ALL PROOFS CHECK", True))
            else:
                self.assertEqual(r["status"], "UNKNOWN", b)


class TestL6(unittest.TestCase):
    def inputs(self) -> dict:
        recs = list(game_records().values())
        expect = {fid: expect_target(fid, g) for fid, (g, _w) in target_games().items()}
        return {"population": population(), "expect": expect, "records": recs, "controls": controls(),
                "corpus_truth": None, "corpus_expect": {}}

    def test_l6(self):  # L1
        v9 = load_json(GAMES / "v9.json")
        self.assertEqual(load_json(GAMES / "l6.json"), G.l6_v9(self.inputs(), v9))

    def test_v9_gate(self):  # L1
        met = holon_module("holon.games.metric")
        bad = {"numerator": 0, "denominator": 1, "missing": ["x"], "holds": False}
        got = met.l6_v9(self.inputs(), bad)
        self.assertEqual(got, G.l6_v9(self.inputs(), bad))
        self.assertEqual(got["thresholds"]["decided"], "not_judged")
        self.assertEqual(got["decided"]["numerator"], 0)

    def test_corpus_pending(self):  # L1
        got = load_json(GAMES / "l6.json")
        self.assertEqual(got["corpus"], {"label": "not_measured", "reason": G.PENDING_CORPUS})


class TestDeterminism(unittest.TestCase):
    def test_run_check(self):  # D1
        r = holon("games", "run", "--check")
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])

    def test_target_agnostic(self):  # D1
        pkg = ROOT / "holon" / "games"
        self.assertTrue(pkg.is_dir())
        names = {d["member"] for d in sc()["documents"]} | set(sc()["n3"]["laws"]) | {sc()["o35"]["law"]}
        names |= {c["id"].split(".")[-1] for c in sc()["classes"] if "." in c["id"]}
        for p in sorted(pkg.glob("*.py")):
            t = p.read_text()
            for n in sorted(names):
                self.assertNotIn(n, t, f"{p.name} names {n}")


class TestPredictions(unittest.TestCase):
    def econ(self, lid: str) -> dict:
        return load_json(GAMES / "econ" / f"{lid}.json")

    def test_p1_n3_recommit(self):
        law = "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter"
        self.assertEqual(self.econ(f"L_econ_n3_recommit_{law}")["status"], "PROVED")

    def test_p2_n3_continuation(self):
        law = "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter"
        self.assertEqual(self.econ(f"L_econ_n3_continuation_{law}")["status"], "PROVED")

    def test_p3_o35_backlog(self):
        summ = load_json(GAMES / "summary.json")
        self.assertEqual(sorted(summ["o35_writers"]), ["commitBatch", "commitBatchWithProof", "commitState"])
        for b in summ["o35_writers"]:
            self.assertEqual(self.econ(f"L_econ_o35_backlog_{b}")["status"], "PROVED", b)

    def test_p4_controls(self):
        c = load_json(GAMES / "l6.json")["controls"]
        self.assertEqual((c["strict_correct"], c["items"]), (14, 14))
        self.assertEqual((c["false_rational"], c["false_irrational"], c["invalid"]), ([], [], {}))

    def test_p5_decided(self):
        d = load_json(GAMES / "l6.json")["decided"]
        self.assertEqual(d["denominator"], 49)
        self.assertTrue(1 <= d["numerator"] <= 10, d)
        recs = game_records()
        for fid in population():
            if fid in recs and recs[fid]["verdict"] != "UNKNOWN":
                self.assertEqual(recs[fid]["verdict"], "rational", fid)


class TestRegressions(unittest.TestCase):
    def test_r1_m0_m4_unchanged(self):
        base = key()["thresholds"]["base_commit"]
        paths = [f"{d}/{m}" for d in ("results", "gen", "laws", "replay") for m in ("M0", "M1", "M2", "M3", "M4")]
        paths += [f"spec/{m}" for m in ("M1", "M2", "M3", "M4")] + ["laws/CONTRACTS", "facts", "schemas", "tests"]
        out = git("diff", "--stat", base, "HEAD", "--", *paths).decode().strip()
        self.assertEqual(out, "", out)
        for m in ("M2", "M3", "M4", "M5"):
            r = holon("audit", "prereg", "--milestone", m)
            self.assertIn("PREREG OK", r.stdout, m + r.stdout[-2000:] + r.stderr[-2000:])
        r = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertIn("FROZEN OK", r.stdout + r.stderr)

    def test_r2_i54_unchanged(self):
        base = key()["thresholds"]["base_commit"]
        paths = ["spec/M5/preregistration.json", "spec/M5/controls", "results/M5/definitions_base.json",
                 "results/M5/l10_census_base.json"]
        out = git("diff", "--stat", base, "HEAD", "--", *paths).decode().strip()
        self.assertEqual(out, "", out)
        for args in (["prereg"], ["controls"], ["census"], ["metrics", "--base"]):
            r = holon("m5", *args, "--check")
            self.assertIn("CHECK OK", r.stdout, args)

    def test_r3_population(self):
        self.assertEqual(len(population()), 49)


if __name__ == "__main__":
    unittest.main()
