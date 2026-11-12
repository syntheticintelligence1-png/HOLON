"""I116 (M6, generality): per-document fallbacks. Contract tests (spec/M6/predictions/I116.json;
prompts/I116_per_document_fallbacks.md).

The wall I112 measured on the spent targets: one document's refusal stops every document. Aave V3 is refused at
DISCH (D2 refuses one document), and EigenLayer at evidence and derive (one transitions document's E2 construct).
HUMAN_ANSWERS Q83 and Q88 (3), in Q77's shape, justified by the stages' semantics, never by a corpus entry:

  (D) DISCH (a DISCH sidecar naming document_fallback "unknown"; holon.analysis.closure.Sidecar.analyses, read by holon
      disch, derive's rule DISCH and holon run's DISCH runner alike). A document whose analysis raises ClassError
      (class class_error) or a KeyError, TypeError or IndexError (class malformed) has no DISCH analysis and no DISCH
      law: its DISCH laws are UNKNOWN, and the miss is recorded in <out>/fallback.json {document, sha256, model, class,
      error}. Every other document's DISCH runs, exactly as without it. A milestone-wide input error (the sidecar, r0,
      a document missing or not a transitions document, two documents naming one model) stays a refusal.
  (E) Evidence and derive (the adoption sidecar spec/<M>/lib/derive_extracted.json naming document_fallback "unknown";
      holon.diagram.evidence.build). An adopted transitions document whose E2 atoms the rule over transitions documents
      does not map (holon.diagram.transitions.TransitionsError, class e2_unmapped) keeps its anchors and gets no atom,
      and the miss is recorded under the evidence document's fallback. Derive rebuilds the set from the same sidecar, so
      its refusal "the evidence set cannot be rebuilt" for that document falls back with it. Evidence is triage, not a
      premise, so a law over the document has the evidence levels [] and its verdict is the checker's.

The composed driver (holon.eval.holon_run) opts in when the protocol names document_fallback {disch, evidence}: it
writes the key into every DISCH sidecar it generates, and into the adoption sidecar holon roles installed for the
entry (never a hand sidecar). Each row carries fallbacks {stage: {documents, classes}}, as counts only.

The planted fixture tests_m6/fixtures/i116/sol (Solidity, compiled by the pinned solc 0.8.24) is written for these
tests from the stages' semantics:
  - Counter is well formed for every stage (the cross-document neighbour).
  - Twice has two writing actions that check msg.sender == owner inline, at two spans. D2 names an inline permission
    class by its check's span, so the document has two classes with one predicate, which D2 refuses.
  - TwiceKept is Twice without its second guarded action (the control).
  - Listed has a dynamic storage array written by index, a path segment Z1 does not map.
  - ListedKept is Listed without the array (the control).
Their expectations are known by construction.

The corpus smoke measures are in results/M6/I116/holon/corpus.json (holon eval holon --protocol
spec/M6/lib/i116_run.json --compose, after I115's landing). The run on I106's targets is labelled contaminated:
post-I107 and commits aggregates only (results/M6/I116/sealed.json; Q56, Q72, Q89).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m6 import test_i112_run_wall as T12

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i116"
SOL = FIX / "sol"
PROTO = "spec/M6/lib/i116_run.json"
PROTO_I112 = "spec/M6/lib/i112_run.json"
OUT = ROOT / "results" / "M6" / "I116"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
BASE = T12.BASE
MORPH_DIRS = T12.MORPH_DIRS
LAW_ID = T12.LAW_ID
protocol, unseconds, verdicts, law_facts, run_holon, git = (T12.protocol, T12.unseconds, T12.verdicts, T12.law_facts,
                                                            T12.run_holon, T12.git)


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I116.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def law(S: Path, M: str, lid: str) -> dict:
    return json.loads((S / "laws" / M / f"{lid}.json").read_text(encoding="utf-8"))


def record(S: Path, M: str, lid: str) -> dict | None:
    p = S / "results" / M / f"{lid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def over(S: Path, M: str, doc: str, rule: str | None = None) -> list[str]:
    """The law ids over the document doc (a file name), of the rule when given."""
    return sorted(k for k, f in law_facts(S, M).items() if f and f.endswith("/" + doc)
                  and (rule is None or law(S, M, k).get("rule") == rule))


def decided(S: Path, M: str, ids: list[str]) -> list[str]:
    return [k for k in ids if (record(S, M, k) or {}).get("status") in ("PROVED", "REFUTED")]


def scratch(tmp: Path, proto: dict, src: Path):
    from holon.eval import holon_run as H
    S = H.scratch_root(ROOT, tmp, "holon/i116", src)
    rel = "results/eval/holon/i116"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    return S, rel, H.Runner(H.Ctx(tmp, src), S, proto, {})


class _Sol(unittest.TestCase):
    """The contracts of tests_m6/fixtures/i116/sol, extracted by the pinned solc 0.8.24 in a scratch root, then the
    composed route's typed part (roles installed, holon_run._rules with route C)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i116-sol-"))
        cls.src = cls.tmp / "src"
        shutil.copytree(SOL, cls.src)
        cls.head = T12._gitify(cls.src)
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def extract(self, S: Path, rel: str, R, names: tuple) -> list[str]:
        files = []
        for n in names:
            side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I116 planted fixture",
                    "target": {"repo": "holon/i116", "commit": self.head, "scope": f"contract {n}"},
                    "output": f"{rel}/facts/{n}.extracted.json", "sources": ["Fixture.sol"],
                    "compiler": {"version": "0.8.24", "settings": {"optimizer": {"enabled": False}}},
                    "transitions": {"commit_interfaces": [], "contract": n}}
            sp = S / rel / "sidecars" / f"extract_{n}.json"
            sp.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
            out = S / rel / "facts" / f"{n}.extracted.json"
            r = R.holon("extract", ["extract", "solidity", "--root", str(S), "--sidecar", str(sp), "--source",
                                    str(self.src), "--out", str(out)])
            if r["status"] != "ok":
                raise AssertionError(r["detail"][-2000:])
            files.append(out.name)
        return files

    def run_of(self, names: tuple, proto_name: str = PROTO, cache: bool = True):
        k = (names, proto_name)
        if cache and k in self.runs:
            return self.runs[k]
        t = self.tmp / f"run{len(list(self.tmp.glob('run*')))}"
        t.mkdir()
        proto = protocol(proto_name)
        S, rel, R = scratch(t, proto, self.src)
        files = self.extract(S, rel, R, names)
        st = T12.typed_part(S, rel, R, proto, files)
        res = (st, S, rel, proto["milestone"])
        if cache:
            self.runs[k] = res
        return res

    def same_neighbour(self, bad: str):
        """Cross-document: Counter's laws byte-identical and its records equal to Counter alone."""
        _a, A, _r, M = self.run_of(("Counter",))
        stb, B, _r, _M = self.run_of(("Counter", bad))
        for s in ("disch", "evidence", "derive"):
            self.assertEqual(stb[s]["status"], "ok", (s, stb[s]["detail"][-2000:]))
        la = over(A, M, "Counter.extracted.json")
        self.assertTrue(la)
        self.assertEqual(la, over(B, M, "Counter.extracted.json"))
        for n in la:
            self.assertEqual((A / "laws" / M / f"{n}.json").read_bytes(), (B / "laws" / M / f"{n}.json").read_bytes(), n)
            ra, rb = record(A, M, n), record(B, M, n)
            self.assertEqual(ra is None, rb is None, n)
            if ra is not None:
                self.assertEqual(unseconds(ra), unseconds(rb), n)
        return A, B, M


# ----------------------------------------------------------------------------------------------- (D) DISCH
class TestDischUnit(_Sol):
    """P1: holon disch over Twice, with and without the opt-in."""

    def test_p1_disch(self):
        st, S, rel, M = self.run_of(("Twice",))
        self.assertEqual(st["disch"]["status"], "ok", st["disch"]["detail"][-2000:])
        fb = json.loads((S / "gen" / M / "disch" / "fallback.json").read_text(encoding="utf-8"))
        (m,) = fb["documents"]
        self.assertTrue(m["document"].endswith("/Twice.extracted.json"))
        self.assertEqual(m["class"], "class_error")
        self.assertIn("one predicate for two classes", m["error"])
        self.assertEqual(len(m["sha256"]), 64)
        clo = json.loads((S / "gen" / M / "disch" / "closure.json").read_text(encoding="utf-8"))
        con = json.loads((S / "gen" / M / "disch" / "conjuncts.json").read_text(encoding="utf-8"))
        self.assertNotIn(m["model"], clo["models"])
        self.assertNotIn(m["model"], con["models"])
        side = json.loads((S / rel / "sidecars" / "disch.json").read_text(encoding="utf-8"))
        self.assertEqual(side["document_fallback"], "unknown")
        # without the opt-in: exit 3, as before; any other value: refused (exit 2)
        for value, code in ((None, 3), ("opaque", 2), (True, 2)):
            d = dict(side)
            d.pop("document_fallback")
            if value is not None:
                d["document_fallback"] = value
            sp = S / rel / "sidecars" / "disch_variant.json"
            sp.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
            od = S / "gen" / "variant"
            shutil.rmtree(od, ignore_errors=True)
            p = run_holon(["disch", "--milestone", M, "--root", str(S), "--sidecar", str(sp), "--out", str(od)])
            self.assertEqual(p.returncode, code, (value, p.stderr[-1500:]))
            if code == 3:
                self.assertIn("one predicate for two classes", p.stderr)
            self.assertFalse(od.exists(), value)


class TestDischShapes(_Sol):
    """P2: the three shapes, end to end."""

    def test_p2_alone(self):
        st, S, _rel, M = self.run_of(("Twice",))
        for s in ("disch", "derive"):
            self.assertEqual(st[s]["status"], "ok", (s, st[s]["detail"][-2000:]))
        self.assertEqual(over(S, M, "Twice.extracted.json", "DISCH"), [])
        st0, *_ = self.run_of(("Twice",), PROTO_I112)
        self.assertNotEqual(st0["disch"]["status"], "ok")
        self.assertNotIn("derive", st0)

    def test_p2_cross_document(self):
        A, B, M = self.same_neighbour("Twice")
        self.assertEqual(over(B, M, "Twice.extracted.json", "DISCH"), [])

    def test_p2_constrained(self):
        stk, K, _r, M = self.run_of(("TwiceKept",))
        self.assertEqual(stk["run"]["status"], "ok", stk["run"]["detail"][-2000:])
        kd = over(K, M, "TwiceKept.extracted.json", "DISCH")
        self.assertTrue(decided(K, M, kd), kd)
        _s, S, _r, _M = self.run_of(("Twice",))
        self.assertEqual(decided(S, M, over(S, M, "Twice.extracted.json", "DISCH")), [])

        def key(L, stem):
            t = json.dumps(L.get("statement"), sort_keys=True)
            for a, b in ((stem, "X"), (stem.lower(), "x")):
                t = t.replace(a, b)
            return (L.get("rule"), L.get("subform"), t)
        kept = {key(law(K, M, k), "TwiceKept"): (record(K, M, k) or {}).get("status")
                for k in over(K, M, "TwiceKept.extracted.json")}
        for k in over(S, M, "Twice.extracted.json"):
            if (record(S, M, k) or {}).get("status") == "PROVED":
                v = kept.get(key(law(S, M, k), "Twice"), "PROVED")
                self.assertEqual(v, "PROVED", k)


# ----------------------------------------------------------------------------------------------- (E) evidence
class TestEvidenceUnit(_Sol):
    """P3: the evidence set over Listed, with and without the opt-in."""

    def evidence(self, S: Path, M: str) -> dict:
        return json.loads((S / "gen" / M / "evidence.json").read_text(encoding="utf-8"))

    def test_p3_evidence(self):
        st, S, _rel, M = self.run_of(("Listed",))
        self.assertEqual(st["evidence"]["status"], "ok", st["evidence"]["detail"][-2000:])
        ev = self.evidence(S, M)
        (m,) = ev["fallback"]
        self.assertTrue(m["document"].endswith("/Listed.extracted.json"))
        self.assertEqual(m["class"], "e2_unmapped")
        self.assertTrue(m["error"])
        self.assertIn(m["model"], ev["models"])
        self.assertTrue(ev["models"][m["model"]]["anchors"]["trans"])
        self.assertEqual([a for a in ev["atoms"] if a["model"] == m["model"]], [])
        st0, *_ = self.run_of(("Listed",), PROTO_I112)
        self.assertEqual(st0["evidence"]["status"], "failed")
        self.assertIn("does not map", st0["evidence"]["detail"])

    def test_p3_no_fallback_same_set(self):
        _a, A, _r, M = self.run_of(("Counter",), PROTO_I112)
        _b, B, _r, _M = self.run_of(("Counter",))
        ea, eb = self.evidence(A, M), self.evidence(B, M)
        self.assertNotIn("fallback", eb)
        for e in (ea, eb):
            e.pop("evidence_sha256")
            e["inputs"] = [x for x in e["inputs"] if not x["path"].endswith("derive_extracted.json")]
        self.assertEqual(ea, eb)


class TestEvidenceShapes(_Sol):
    """P4: the three shapes, end to end."""

    def levels(self, S: Path, M: str, doc: str) -> list:
        return [(k, (record(S, M, k) or {}).get("evidence_levels")) for k in over(S, M, doc) if record(S, M, k)]

    def test_p4_alone(self):
        st, S, _rel, M = self.run_of(("Listed",))
        for s in ("evidence", "derive"):
            self.assertEqual(st[s]["status"], "ok", (s, st[s]["detail"][-2000:]))
        lv = self.levels(S, M, "Listed.extracted.json")
        self.assertTrue(lv)
        for k, v in lv:
            self.assertIn(v, (None, []), k)
        st0, *_ = self.run_of(("Listed",), PROTO_I112)
        self.assertNotEqual(st0["evidence"]["status"], "ok")
        self.assertNotEqual(st0["derive"]["status"], "ok")

    def test_p4_cross_document(self):
        A, B, M = self.same_neighbour("Listed")
        ea = json.loads((A / "gen" / M / "evidence.json").read_text(encoding="utf-8"))
        eb = json.loads((B / "gen" / M / "evidence.json").read_text(encoding="utf-8"))
        self.assertEqual([a for a in ea["atoms"] if a["model"] == "Counter.extracted"],
                         [a for a in eb["atoms"] if a["model"] == "Counter.extracted"])
        self.assertEqual(ea["models"]["Counter.extracted"], eb["models"]["Counter.extracted"])

    def test_p4_constrained(self):
        stk, K, _r, M = self.run_of(("ListedKept",))
        ek = json.loads((K / "gen" / M / "evidence.json").read_text(encoding="utf-8"))
        self.assertTrue([a for a in ek["atoms"] if a["model"] == "ListedKept.extracted"])
        self.assertTrue(decided(K, M, over(K, M, "ListedKept.extracted.json")))
        _s, S, _r, _M = self.run_of(("Listed",))
        for k, v in self.levels(S, M, "Listed.extracted.json"):
            self.assertFalse(v, k)


# ----------------------------------------------------------------------------------------------- milestone-wide
class TestMilestoneWide(_Sol):
    """P5: a milestone-wide input error stays a refusal under both opt-ins."""

    def test_p5_disch_input_errors(self):
        _st, S, rel, M = self.run_of(("Counter",))
        side = json.loads((S / rel / "sidecars" / "disch.json").read_text(encoding="utf-8"))
        bad_r0 = json.loads(json.dumps(side))
        bad_r0["r0"]["values"] = {"no_such_path_anywhere": ["0x00"]}
        (S / rel / "facts" / "Not.json").write_text('{"facts_version": "none"}\n')
        not_tx = dict(side, documents=side["documents"] + [f"{rel}/facts/Not.json"])
        for name, d, text in (("r0", bad_r0, "r0 names paths"), ("not_tx", not_tx, "not a transitions document")):
            sp = S / rel / "sidecars" / f"disch_{name}.json"
            sp.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
            od = S / "gen" / f"wide_{name}"
            p = run_holon(["disch", "--milestone", M, "--root", str(S), "--sidecar", str(sp), "--out", str(od)])
            self.assertEqual(p.returncode, 2, (name, p.stderr[-1500:]))
            self.assertIn(text, p.stderr, name)
            self.assertFalse(od.exists(), name)

    def test_p5_evidence_input_errors(self):
        st, S, rel, M = self.run_of(("Listed",), cache=False)
        self.assertEqual(st["derive"]["status"], "ok", st["derive"]["detail"][-2000:])
        ep = S / "gen" / M / "evidence.json"
        ev = json.loads(ep.read_text(encoding="utf-8"))
        ev["fallback"] = []
        ep.write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n")
        from holon.eval import holon_run as H
        args = H.derive_args(S, rel, M, protocol(PROTO))
        args[args.index("--out") + 1] = f"laws/{M}_stale"
        p = run_holon(args)
        self.assertNotEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertIn("stale", p.stderr)
        side = S / "spec" / M / "lib" / "derive_extracted.json"
        d = json.loads(side.read_text(encoding="utf-8"))
        self.assertEqual(d["document_fallback"], "unknown")
        d["document_fallback"] = "anything"
        side.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        p = run_holon(["evidence", "--milestone", M, "--root", str(S), "--out", str(S / "gen" / "ev_bad.json")])
        self.assertNotEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertIn("document_fallback", p.stderr)
        self.assertFalse((S / "gen" / "ev_bad.json").exists())


class TestBytes(_Sol):
    """P6: without the opt-ins nothing changes; with them and nothing falling back, the same bytes."""

    def test_p6_no_earlier_sidecar_or_protocol_names_it(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            if "document_fallback" in p.read_text(encoding="utf-8"):
                found.append(p.relative_to(ROOT).as_posix())
        for p in sorted((ROOT / "spec").glob("M[4-6]/lib/i*_run.json")):
            it = str(json.loads(p.read_text(encoding="utf-8")).get("iteration") or "")
            if p.name != "i116_run.json" and not (it[1:].isdigit() and int(it[1:]) >= 116) \
                    and "document_fallback" in p.read_text(encoding="utf-8"):
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_p6_disch_same_bytes(self):
        _a, A, _r, M = self.run_of(("Counter",), PROTO_I112)
        _b, B, _r, _M = self.run_of(("Counter",))
        self.assertFalse((B / "gen" / M / "disch" / "fallback.json").exists() and json.loads(
            (B / "gen" / M / "disch" / "fallback.json").read_text())["documents"])
        for n in ("closure.json", "conjuncts.json"):
            da = json.loads((A / "gen" / M / "disch" / n).read_text(encoding="utf-8"))
            db = json.loads((B / "gen" / M / "disch" / n).read_text(encoding="utf-8"))
            for d in (da, db):
                d["sidecar"].pop("sha256")
            self.assertEqual(da, db, n)


# ----------------------------------------------------------------------------------------------- the corpus
class TestCorpusSmoke(unittest.TestCase):
    """P7-P9: smoke measures on I51's 20 entries (contaminated by I51, I103-I112 and I107)."""

    def doc(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I116/holon/corpus.json is missing")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def rows(self) -> dict:
        return {r["id"]: r for r in self.doc()["rows"]}

    def test_p7_stage_reach(self):
        e = pred("I116-P7")["expected"]
        self.assertEqual(self.doc()["preflight"]["status"], "ok")
        reach: dict = {}
        fb = {"disch": 0, "evidence": 0}
        for i, r in self.rows().items():
            self.assertTrue(r.get("compose"), i)
            for s, v in (r.get("stages") or {}).items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(i)
                elif v.get("status") not in ("not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {s} has no reason")
            for s in fb:
                fb[s] += ((r.get("fallbacks") or {}).get(s) or {}).get("documents", 0)
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)
        self.assertEqual(fb["disch"], e["disch_fallback_documents"])
        self.assertEqual(fb["evidence"], e["evidence_fallback_documents"])

    def test_p8_laws_aggregate(self):
        e = pred("I116-P8")["expected"]
        rows = self.rows()
        aggs = [(k, f) for r in rows.values() for k, f in (r.get("laws_aggregate") or {}).items()]
        for i, r in rows.items():
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
        for k, f in aggs:
            self.assertEqual(set(f), {"derived", "decided", "unknown"}, k)
            self.assertEqual(f["derived"], f["decided"] + f["unknown"], k)
        self.assertGreaterEqual(sum(f["derived"] for _k, f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for _k, f in aggs), e["decided_at_least"])

    def test_p9_nothing_per_law_committed(self):
        base = OUT / "holon"
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if LAW_ID.search(p.relative_to(base).as_posix()):
                hits.append(p.relative_to(base).as_posix())
                continue
            if p.name == "corpus.json":
                for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                    if LAW_ID.search(json.dumps({k: v for k, v in r.items() if k != "laws_aggregate"})):
                        hits.append(f"corpus.json:{r['id']}")
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if LAW_ID.search(text):
                hits.append(p.relative_to(base).as_posix())
        self.assertEqual(hits, [])
        for r in self.rows().values():
            self.assertIn("fallbacks", r, r["id"])
            if r.get("laws_aggregate"):
                self.assertEqual(len(r["laws_bundle_sha256"]), 64, r["id"])


class TestSealedContaminated(unittest.TestCase):
    """P10-P11: I106's targets, contaminated: post-I107 (aggregates only; Q56, Q72, Q89)."""

    def targets(self) -> dict:
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        return {x["id"]: x for x in d["targets"]}

    @staticmethod
    def total(x: dict, k: str) -> int:
        return sum(f[k] for f in (x.get("laws_aggregate") or {}).values())

    def test_p10_spent_targets(self):
        e = pred("I116-P10")["expected"]
        t = self.targets()
        for i, x in t.items():
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, i)
            for f in (x.get("laws_aggregate") or {}).values():
                self.assertEqual(set(f), {"derived", "decided", "unknown"}, i)
            self.assertGreaterEqual(self.total(x, "derived"), e["derived_at_least_each"], i)
        s1, s2 = t["s1"], t["s2"]
        self.assertEqual(s2["stages"].get("disch"), "ok")
        self.assertGreaterEqual(s2["fallbacks"]["disch"]["documents"], 1)
        self.assertIn("class_error", s2["fallbacks"]["disch"]["classes"])
        for s in ("evidence", "derive"):
            self.assertEqual(s1["stages"].get(s), "ok", s)
        self.assertGreaterEqual(s1["fallbacks"]["evidence"]["documents"], 1)
        self.assertIn("e2_unmapped", s1["fallbacks"]["evidence"]["classes"])

    def test_p11_gate(self):
        """Q88 (1): at least 1 law decided on the corpus and at least 1 on at least one spent target."""
        t = self.targets()
        rows = json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))["rows"]
        corpus = sum(f["decided"] for r in rows for f in (r.get("laws_aggregate") or {}).values())
        self.assertGreaterEqual(corpus, 1)
        self.assertGreaterEqual(max(self.total(x, "decided") for x in t.values()), 1)


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_p12_morph_record_moves_only_by_restamp(self):
        T12.TestRegressions.test_p14_morph_record_moves_only_by_restamp(self)

    def test_p12_protocol_is_i112s_plus_the_opt_in(self):
        """i116_run.json is I112's plus document_fallback; once I115 lands, plus exactly the keys its i115_keys lists
        (dotted paths, as I115's landed protocol names them)."""
        a = json.loads((ROOT / PROTO_I112).read_text(encoding="utf-8"))
        b = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(b.pop("document_fallback"), {"disch": "unknown", "evidence": "unknown"})
        b.pop("document_fallback_doc")
        for path in b.pop("i115_keys", []):
            for d in (a, b):
                *head, last = path.split(".")
                for h in head:
                    d = d.get(h, {})
                d.pop(last, None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i116"):
            self.assertIn(f"name: {job}", wf, job)


if __name__ == "__main__":
    unittest.main()
