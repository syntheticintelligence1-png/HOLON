"""I118 (M6, generality): the post-derive walls. Contract tests (spec/M6/predictions/I118.json;
prompts/I118_post_derive_walls.md).

The walls I116 measured on Aave V3, after derive: the composed coverage stage refuses over one extraction sidecar,
holon bind exits 1 having bound no law, and the typed runner exits 1 writing no record. HUMAN_ANSWERS Q92, in Q77's
shape, justified by the stages' semantics, never by a corpus entry or a spent target:

  (C) Coverage (protocol document_fallback.coverage "typed_only"; holon coverage --sidecars .. --typed-only). An
      extraction sidecar whose document was not extracted (reason not_extracted) or that holon types made opaque
      (reason opaque, gen/<M>/sorts/opaque.json) is not walked and is listed under the report's skipped. No law is over
      such a document (I111's O2-O7), so no record reads its entry. Found on the planted fixture before the prereg: one
      document the frontend refuses (its sidecar stays beside the others) refuses holon coverage (exit 3), and then
      every record over every document refuses (holon.records.coverage_field: no entry in gen/<M>/coverage.json), so
      the runner writes no record at all.
  (R) The runners (document_fallback.run "unknown"; holon_run._run_routed). A runner group whose holon run exits
      non-zero is re-run once per law document; a document whose own re-run fails has every law of the group over it
      recorded UNKNOWN with the error (attempts [.., {kind: document_fallback, stage: run, runner, error}]). A failure
      not confined to one document (exit 2, or, with at least two documents, the same masked failure in every one)
      stays a refusal: no record of the group is kept, and the runner's aggregate says milestone_refusal.
  (B) The binding (document_fallback.bind "unknown"; holon bind --unbound document). I115's --unbound skip, plus: an
      error other than BindingError while binding a law over document D, whose model no other document's law shares,
      unbinds every law over D with the error (spec/bindings/<M>.fallback.json). Any other error still refuses (exit
      1, nothing written). binding_check (I115) then refuses every decided record over D.
  (3) spec/schemas/evidence.schema.json gains an optional fallback (I116's (E) writes it only under its opt-in).

The planted fixture tests_m6/fixtures/i118/sol (Solidity, the pinned solc 0.8.24) is written for these tests from the
stages' semantics: Counter (the neighbour), Guarded (the control of every shape, and the planted document of each:
its extraction over its sidecar's term budget; its coverage entry taken out before the run; its typed model taken out
before bind) and Dyn (a dynamic storage array: opaque at types). Expectations are known by construction.

The corpus smoke measures are results/M6/I118/holon/corpus.json (holon eval holon --protocol
spec/M6/lib/i118_run.json --compose). The run on I106's targets is labelled contaminated: post-I107 and commits
aggregates only (results/M6/I118/sealed.json and families.json; Q56, Q72, Q89).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_m6 import test_i112_run_wall as T12
from tests_m6 import test_i116_per_document_fallbacks as T16

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i118"
SOL = FIX / "sol"
PROTO = "spec/M6/lib/i118_run.json"
PROTO_I116 = "spec/M6/lib/i116_run.json"
OUT = ROOT / "results" / "M6" / "I118"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
FAMILIES = OUT / "families.json"
LAW_ID = T12.LAW_ID
OVER_BUDGET = 5   # Guarded's planted term budget: every action's term exceeds it, so the frontend refuses the contract
NEW = ("bind", "coverage", "run")
protocol, unseconds, law_facts = T12.protocol, T12.unseconds, T12.law_facts
law, record, over, decided = T16.law, T16.record, T16.over, T16.decided


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I118.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def hl(R, args: list[str]) -> subprocess.CompletedProcess:
    """python -m holon in the scratch root, as the composed driver runs it (holon_run.Runner)."""
    p = subprocess.run([sys.executable, "-m", "holon", *args], cwd=R.root, env=R.env, capture_output=True, text=True,
                       timeout=1800)
    return p


def without(proto: dict, *stages: str) -> dict:
    d = json.loads(json.dumps(proto))
    for s in stages:
        d["document_fallback"].pop(s)
    return d


def scratch(tmp: Path, proto: dict, src: Path):
    from holon.eval import holon_run as H
    S = H.scratch_root(ROOT, tmp, "holon/i118", src)
    rel = "results/eval/holon/i118"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    return S, rel, H.Runner(H.Ctx(tmp, src), S, proto, {})


class _Sol(unittest.TestCase):
    """The contracts of tests_m6/fixtures/i118/sol, extracted in a scratch root, then the composed route's typed part
    (roles installed, holon_run._rules with route C, the run and bind steps), with an optional planted fault."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i118-sol-"))
        cls.src = cls.tmp / "src"
        shutil.copytree(SOL, cls.src)
        cls.head = T12._gitify(cls.src)
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def extract(self, S: Path, rel: str, R, names: tuple, over_budget: tuple = ()) -> list[str]:
        """The extracted files; a contract in over_budget gets a sidecar whose term budget its walk exceeds, so the
        frontend refuses it and only its sidecar remains (as the composed driver leaves a failed extraction's)."""
        files = []
        for n in names:
            tr = {"commit_interfaces": [], "contract": n, **({"term_budget": OVER_BUDGET} if n in over_budget else {})}
            side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I118 planted fixture",
                    "target": {"repo": "holon/i118", "commit": self.head, "scope": f"contract {n}"},
                    "output": f"{rel}/facts/{n}.extracted.json", "sources": ["Fixture.sol"],
                    "compiler": {"version": "0.8.24", "settings": {"optimizer": {"enabled": False}}},
                    "transitions": tr}
            sp = S / rel / "sidecars" / f"extract_{n}.json"
            sp.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
            out = S / rel / "facts" / f"{n}.extracted.json"
            r = R.holon("extract", ["extract", "solidity", "--root", str(S), "--sidecar", str(sp), "--source",
                                    str(self.src), "--out", str(out)])
            if n in over_budget:
                if r["status"] == "ok" or out.exists():
                    raise AssertionError(f"{n}: the planted term budget did not refuse the extraction")
                continue
            if r["status"] != "ok":
                raise AssertionError(r["detail"][-2000:])
            files.append(out.name)
        return files

    def run_of(self, names: tuple, proto=PROTO, over_budget: tuple = (), fault: str | None = None,
               fault_doc: str = "Guarded", key=None):
        """(stages, S, rel, M, R). fault: "coverage_entry" (fault_doc's entry out of gen/<M>/coverage.json before the
        run step), "coverage_file" (gen/<M>/coverage.json removed before the run step), "model" (fault_doc's typed
        model out of gen/<M>/sorts/models after the run step, before bind)."""
        from holon.eval import holon_run as H
        k = key or (names, json.dumps(proto, sort_keys=True) if isinstance(proto, dict) else proto, over_budget, fault)
        if k in self.runs:
            return self.runs[k]
        t = self.tmp / f"run{len(self.runs)}"
        t.mkdir()
        p = protocol(proto) if isinstance(proto, str) else json.loads(json.dumps(proto))
        S, rel, R = scratch(t, p, self.src)
        files = self.extract(S, rel, R, names, over_budget)
        M = p["milestone"]
        orig_run, orig_bind = H._run_routed, H._bind

        def run_hook(R_, S_, M_, *a, **kw):
            cov = S_ / "gen" / M_ / "coverage.json"
            if fault == "coverage_entry":
                d = json.loads(cov.read_text(encoding="utf-8"))
                d["documents"] = [x for x in d["documents"] if not x["document"].endswith(f"/{fault_doc}.extracted.json")]
                cov.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
            if fault == "coverage_file":
                cov.unlink()
            return orig_run(R_, S_, M_, *a, **kw)

        def bind_hook(R_, S_, M_, *a, **kw):
            if fault == "model":
                for q in sorted((S_ / "gen" / M_ / "sorts" / "models").glob(f"{fault_doc}[._]extracted*")):
                    q.unlink()
            return orig_bind(R_, S_, M_, *a, **kw)
        with mock.patch.object(H, "_run_routed", run_hook), mock.patch.object(H, "_bind", bind_hook):
            st = T12.typed_part(S, rel, R, p, files)
        res = (st, S, rel, M, R)
        self.runs[k] = res
        return res

    def counter_same(self, A: Path, B: Path, M: str):
        """Counter's laws byte-identical and its records equal (seconds removed) between two runs."""
        la = over(A, M, "Counter.extracted.json")
        self.assertTrue(la)
        self.assertEqual(la, over(B, M, "Counter.extracted.json"))
        for n in la:
            self.assertEqual((A / "laws" / M / f"{n}.json").read_bytes(), (B / "laws" / M / f"{n}.json").read_bytes(), n)
            ra, rb = record(A, M, n), record(B, M, n)
            self.assertIsNotNone(ra, n)
            self.assertEqual(unseconds(ra), unseconds(rb), n)

    def assert_fallback_records(self, S: Path, M: str, ids: list[str], stage: str = "run"):
        self.assertTrue(ids)
        for n in ids:
            rec = record(S, M, n)
            self.assertIsNotNone(rec, n)
            self.assertEqual(rec["status"], "UNKNOWN", n)
            a = rec["attempts"][-1]
            self.assertEqual((a["kind"], a["stage"]), ("document_fallback", stage), n)
            self.assertTrue(a["error"].strip(), n)
            self.assertIsNone(rec.get("witness"), n)


# ----------------------------------------------------------------------------------------------- (C) coverage
class TestCoverageUnit(_Sol):
    """P1: holon coverage over Counter, Guarded (not extracted) and Dyn (opaque)."""

    def test_p1_typed_only(self):
        st, S, rel, M, R = self.run_of(("Counter", "Guarded", "Dyn"), over_budget=("Guarded",))
        xs = sorted(p.relative_to(S).as_posix() for p in (S / rel / "sidecars").glob("extract_*.json"))
        self.assertEqual(len(xs), 3)
        base = ["coverage", "--milestone", M, "--root", str(S), "--sidecars", ",".join(xs)]
        out = S / "gen" / "cov_unit.json"
        p = hl(R, base + ["--out", str(out)])
        self.assertEqual(p.returncode, 3, p.stderr[-2000:])
        p = hl(R, base + ["--typed-only", "--out", str(out)])
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        rep = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([d["document"].rsplit("/", 1)[-1] for d in rep["documents"]], ["Counter.extracted.json"])
        self.assertEqual([(d["document"].rsplit("/", 1)[-1], d["reason"]) for d in rep["skipped"]],
                         [("Dyn.extracted.json", "opaque"), ("Guarded.extracted.json", "not_extracted")])
        p = hl(R, ["coverage", "--milestone", M, "--root", str(S), "--typed-only", "--out", str(out)])
        self.assertEqual(p.returncode, 2, p.stderr[-2000:])


class TestCoverageShapes(_Sol):
    """P2: the three shapes through the composed route, and the wall under I116's protocol."""

    def test_p2_alone(self):
        st, S, _rel, M, _R = self.run_of(("Guarded", "Dyn"), over_budget=("Guarded",))
        for s in ("types", "derive"):
            self.assertEqual(st[s]["status"], "ok", (s, st[s]["detail"][-2000:]))
        self.assertEqual(over(S, M, "Guarded.extracted.json"), [])
        if "coverage" in st:   # only when a law is derived (Dyn's are none over an opaque document)
            self.assertEqual(st["coverage"]["status"], "ok", st["coverage"]["detail"][-2000:])

    def test_p2_cross_document(self):
        _a, A, _r, M, _R = self.run_of(("Counter",))
        st, B, _r, _M, _R = self.run_of(("Counter", "Guarded", "Dyn"), over_budget=("Guarded",))
        for s in ("coverage", "run"):
            self.assertEqual(st[s]["status"], "ok", (s, st[s]["detail"][-2000:]))
        self.counter_same(A, B, M)
        rep = json.loads((B / "gen" / M / "coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(d["reason"] for d in rep["skipped"]), ["not_extracted", "opaque"])

    def test_p2_constrained(self):
        _c, C, _r, M, _R = self.run_of(("Counter", "Guarded"))
        self.assertTrue(decided(C, M, over(C, M, "Guarded.extracted.json")))
        _b, B, _r, _M, _R = self.run_of(("Counter", "Guarded", "Dyn"), over_budget=("Guarded",))
        self.assertEqual(over(B, M, "Guarded.extracted.json"), [])

    def test_p2_wall_under_i116(self):
        st, S, _r, M, _R = self.run_of(("Counter", "Guarded", "Dyn"), proto=PROTO_I116, over_budget=("Guarded",))
        self.assertNotEqual(st["coverage"]["status"], "ok")
        self.assertEqual(sum(1 for i in over(S, M, "Counter.extracted.json") if record(S, M, i)), 0)


# ----------------------------------------------------------------------------------------------- (R) the runners
class TestRunShapes(_Sol):
    """P3: Guarded's coverage entry out before the run step."""

    def test_p3_without_opt_in(self):
        st, S, _r, M, _R = self.run_of(("Counter", "Guarded"), proto=without(protocol(PROTO), "run"),
                                       fault="coverage_entry")
        self.assertNotEqual(st["run"]["status"], "ok")
        ids = sorted(law_facts(S, M))
        # amended (spec/M6/amendments/I118.jsonl): the runner stops at the first law over Guarded, so the records it
        # decided before it are written; none over Guarded is, and the group is not complete
        self.assertEqual([i for i in over(S, M, "Guarded.extracted.json") if record(S, M, i)], [])
        self.assertTrue([i for i in ids if not record(S, M, i)])

    def test_p3_cross_document_and_constrained(self):
        _c, C, _r, M, _R = self.run_of(("Counter", "Guarded"))
        st, B, _r, _M, R = self.run_of(("Counter", "Guarded"), fault="coverage_entry")
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        self.counter_same(C, B, M)
        g = over(B, M, "Guarded.extracted.json")
        self.assertTrue(decided(C, M, over(C, M, "Guarded.extracted.json")))   # the control decides
        self.assertEqual(decided(B, M, g), [])
        self.assert_fallback_records(B, M, g)
        runners = st["run"]["runners"] if "runners" in st["run"] else None
        agg = runners or json.loads(st["run"]["detail"].split("per runner: ", 1)[1].rsplit("; ", 1)[0])
        self.assertEqual(sum(v.get("fallback_documents", 0) for v in agg.values()), 1)
        self.assertEqual(sum(v.get("fallback_laws", 0) for v in agg.values()), len(g))

    def test_p3_alone(self):
        st, S, _r, M, _R = self.run_of(("Guarded",), fault="coverage_entry")
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        self.assert_fallback_records(S, M, over(S, M, "Guarded.extracted.json"))


class TestRunMilestoneWide(_Sol):
    """P4: gen/<M>/coverage.json removed before the run step: the same failure in every document."""

    def test_p4_refusal(self):
        st, S, _r, M, _R = self.run_of(("Counter", "Guarded"), fault="coverage_file")
        self.assertNotEqual(st["run"]["status"], "ok")
        agg = json.loads(st["run"]["detail"].split("per runner: ", 1)[1].rsplit("; ", 1)[0])
        self.assertTrue(any(v.get("milestone_refusal") for v in agg.values()), agg)
        self.assertEqual([i for i in sorted(law_facts(S, M)) if record(S, M, i)], [])


# ----------------------------------------------------------------------------------------------- (B) the binding
class TestBindShapes(_Sol):
    """P5: Guarded's typed model out after the run step, before bind."""

    def bind(self, R, S: Path, M: str, mode: str) -> subprocess.CompletedProcess:
        for q in sorted((S / "spec" / "bindings").glob(f"{M}.*json")) + [S / "spec" / "bindings" / f"{M}.json"]:
            if q.exists():
                q.unlink()
        return hl(R, ["bind", "--milestone", M, "--root", str(S), "--unbound", mode])

    def test_p5_shapes(self):
        _c, C, _r, M, _R = self.run_of(("Counter", "Guarded"))
        st, B, _r, _M, R = self.run_of(("Counter", "Guarded"), fault="model")
        self.assertEqual(st["bind"]["status"], "ok", st["bind"]["detail"][-2000:])
        self.assertEqual(st["bind"]["aggregate"]["fallback_documents"], 1)
        g = over(B, M, "Guarded.extracted.json")
        self.assertEqual(st["bind"]["aggregate"]["fallback_laws"], len(g))
        bc = json.loads((C / "spec" / "bindings" / f"{M}.json").read_text(encoding="utf-8"))["laws"]
        bb = json.loads((B / "spec" / "bindings" / f"{M}.json").read_text(encoding="utf-8"))["laws"]
        cn = over(B, M, "Counter.extracted.json")
        self.assertEqual({k: bc[k] for k in cn}, {k: bb[k] for k in cn})
        self.assertEqual(sorted(set(g) & set(bb)), [])
        ub = json.loads((B / "spec" / "bindings" / f"{M}.unbound.json").read_text(encoding="utf-8"))["laws"]
        for n in g:
            self.assertTrue(ub[n].startswith("document fallback: FileNotFoundError: "), ub[n])
        fb = json.loads((B / "spec" / "bindings" / f"{M}.fallback.json").read_text(encoding="utf-8"))
        (d,) = fb["documents"]
        self.assertTrue(d["document"].endswith("/Guarded.extracted.json"))
        self.assertEqual((d["class"], d["laws"]), ("FileNotFoundError", len(g)))
        self.assertEqual(decided(B, M, g), [])   # binding_check refused every decided record over Guarded
        self.assertTrue(decided(C, M, over(C, M, "Guarded.extracted.json")))
        self.assertEqual(decided(B, M, cn), decided(C, M, cn))
        self.assertTrue(decided(B, M, cn))
        # the modes on the same faulted tree: skip refuses as before, document falls back again
        p = self.bind(R, B, M, "skip")
        self.assertEqual(p.returncode, 1, p.stderr[-2000:])
        self.assertFalse((B / "spec" / "bindings" / f"{M}.json").exists())
        p = self.bind(R, B, M, "document")
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertEqual(json.loads((B / "spec" / "bindings" / f"{M}.json").read_text(encoding="utf-8"))["laws"], bb)


class TestBindMilestoneWide(_Sol):
    """P6: a failure not confined to one document refuses."""

    def test_p6_shared_model(self):
        from holon import bindings as BD
        _c, C, _r, M, _R = self.run_of(("Counter", "Guarded"))
        tmp = Path(tempfile.mkdtemp(prefix="holon-i118-b-", dir=self.tmp))
        S = tmp / "root"
        shutil.copytree(C, S, symlinks=True)
        for q in sorted((S / "spec" / "bindings").glob(f"{M}*.json")):
            q.unlink()
        shared = S / "gen" / M / "sorts" / "models" / "Counter.extracted.bend"
        real = BD.bind_law

        def boom(lw, m, root, cfg=None):
            if lw["facts"].endswith("/Guarded.extracted.json"):
                raise RuntimeError("planted")
            return real(lw, m, root, cfg)
        with mock.patch.object(BD, "model_path", lambda lw, m, root: shared), mock.patch.object(BD, "bind_law", boom):
            rc = BD.bind_unbound_skip(M, S, document=True)
        self.assertEqual(rc, 1)
        self.assertFalse((S / "spec" / "bindings" / f"{M}.json").exists())
        self.assertFalse((S / "spec" / "bindings" / f"{M}.fallback.json").exists())
        # the same failure on a model of its own falls back
        with mock.patch.object(BD, "bind_law", boom):
            rc = BD.bind_unbound_skip(M, S, document=True)
        self.assertEqual(rc, 0)
        fb = json.loads((S / "spec" / "bindings" / f"{M}.fallback.json").read_text(encoding="utf-8"))
        self.assertEqual([(d["class"], d["document"].rsplit("/", 1)[-1]) for d in fb["documents"]],
                         [("RuntimeError", "Guarded.extracted.json")])

    def test_p6_configuration(self):
        _c, C, _r, M, R = self.run_of(("Counter", "Guarded"))
        tmp = Path(tempfile.mkdtemp(prefix="holon-i118-c-", dir=self.tmp))
        S = tmp / "root"
        shutil.copytree(C, S, symlinks=True)
        for q in sorted((S / "spec" / "bindings").glob(f"{M}*.json")):
            q.unlink()
        (S / "config" / "holon.json").write_text("{not json\n")
        p = hl(R, ["bind", "--milestone", M, "--root", str(S), "--unbound", "document"])
        self.assertEqual(p.returncode, 1, p.stderr[-2000:])
        self.assertFalse((S / "spec" / "bindings" / f"{M}.json").exists())


# ----------------------------------------------------------------------------------------------- (3) the schema
class TestEvidenceSchema(unittest.TestCase):
    """P7: the optional fallback; Morph's committed evidence sets validate and are unchanged."""

    def schema(self) -> dict:
        return json.loads((ROOT / "spec" / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))

    def test_p7_schema(self):
        from holon.schema import errors
        sc = self.schema()
        self.assertIn("fallback", sc["properties"])
        self.assertNotIn("fallback", sc.get("required") or [])
        sets = sorted((ROOT / "gen").glob("*/evidence.json")) + sorted((ROOT / "spec").glob("*/lib/evidence.json"))
        self.assertTrue(sets)
        for p in sets:
            self.assertEqual(errors(json.loads(p.read_text(encoding="utf-8")), sc), [], p)
            rel = p.relative_to(ROOT).as_posix()
            old = subprocess.run(["git", "-C", str(ROOT), "show", f"{T12.BASE}:{rel}"], capture_output=True)
            if old.returncode == 0:
                self.assertEqual(old.stdout, p.read_bytes(), rel)
        base = json.loads(sets[0].read_text(encoding="utf-8"))
        ok = {"document": "results/eval/holon/x/facts/Listed.extracted.json", "sha256": "0" * 64,
              "model": "Listed.extracted", "class": "e2_unmapped", "error": "a path segment"}
        self.assertEqual(errors(dict(base, fallback=[ok]), sc), [])
        self.assertNotEqual(errors(dict(base, fallback=[dict(ok, extra=1)]), sc), [])
        self.assertNotEqual(errors(dict(base, fallback=[dict(ok, **{"class": "malformed"})]), sc), [])
        frozen = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", T12.BASE, "--", "schemas"])
        self.assertEqual(frozen.returncode, 0)


# ----------------------------------------------------------------------------------------------- bytes
class TestBytes(unittest.TestCase):
    """P8: byte-identity without the opt-ins."""

    def test_p8_no_sidecar_or_earlier_protocol_names_the_opt_ins(self):
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                self.assertFalse(set(NEW) & set((d.get("document_fallback") or {}) if isinstance(
                    d.get("document_fallback"), dict) else ()), p)
        for p in sorted((ROOT / "spec" / "M6" / "lib").glob("i1*_run.json")):
            if p.name == Path(PROTO).name:
                continue
            # amended (spec/M6/amendments/I118.jsonl): the protocols of I118 and later keys carry its opt-ins
            it = str(json.loads(p.read_text(encoding="utf-8")).get("iteration") or "")
            if it[1:].isdigit() and int(it[1:]) >= 118:
                continue
            fb = json.loads(p.read_text(encoding="utf-8")).get("document_fallback") or {}
            self.assertFalse(set(NEW) & set(fb), p.name)

    def test_p8_protocol_is_i116s_plus_the_opt_ins(self):
        a = json.loads((ROOT / PROTO_I116).read_text(encoding="utf-8"))
        b = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        fb = b.pop("document_fallback")
        self.assertEqual({k: fb.pop(k) for k in NEW}, {"bind": "unknown", "coverage": "typed_only", "run": "unknown"})
        self.assertEqual(fb, a.pop("document_fallback"))
        b.pop("document_fallback_i118_doc")
        for path in b.pop("i117_keys", []):
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

    def test_p8_report_without_flag(self):
        from holon import coverage as C
        src = (ROOT / "holon" / "coverage.py").read_text(encoding="utf-8")
        self.assertIn("typed_only", src)
        doc = {"documents": [], "unaccounted": 0}
        self.assertEqual(C.render(doc), (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode())
        for m in ("M2", "M3"):
            p = ROOT / "gen" / m / "coverage.json"
            if p.is_file():
                self.assertNotIn("skipped", json.loads(p.read_text(encoding="utf-8")), m)


# ----------------------------------------------------------------------------------------------- measured
class TestCorpusSmoke(unittest.TestCase):
    """P9: the counted composed run on I51's corpus (smoke: contaminated)."""

    def doc(self) -> dict:
        if not HOLON_CORPUS.is_file():
            self.skipTest("the counted corpus run is not committed yet")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def test_p9_corpus(self):
        e = pred("I118-P9")["expected"]
        d = self.doc()
        self.assertEqual(d["preflight"]["status"], "ok")
        reach: dict = {}
        for r in d["rows"]:
            self.assertTrue(r.get("compose"), r["id"])
            self.assertEqual(r.get("laws"), [], r["id"])   # Q56: per-law rows withheld
            for s, v in (r.get("stages") or {}).items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(r["id"])
            if "coverage" in (r.get("stages") or {}):
                self.assertEqual(r["stages"]["coverage"]["status"], "ok", r["id"])
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)
        aggs = [f for r in d["rows"] for f in (r.get("laws_aggregate") or {}).values()]
        for f in aggs:
            self.assertEqual(set(f), {"derived", "decided", "unknown"})
            self.assertEqual(f["derived"], f["decided"] + f["unknown"])
        self.assertGreaterEqual(sum(f["derived"] for f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for f in aggs), e["decided_at_least"])
        hits = []
        base = OUT / "holon"
        for p in sorted(base.rglob("*")):
            if p.is_file():
                try:
                    text = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if p.name == "corpus.json":
                    text = json.dumps([{k: v for k, v in r.items() if k != "laws_aggregate"}
                                       for r in json.loads(text)["rows"]])
                if LAW_ID.search(p.relative_to(base).as_posix()) or LAW_ID.search(text):
                    hits.append(p.relative_to(base).as_posix())
        self.assertEqual(hits, [])


class TestSealedContaminated(unittest.TestCase):
    """P10-P12: I106's targets, contaminated: post-I107 (aggregates only; Q56, Q72, Q89)."""

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
        e = pred("I118-P10")["expected"]
        t = self.targets()
        for i, x in t.items():
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, i)
        s1, s2 = t["s1"], t["s2"]
        for s in ("coverage", "run", "bind"):
            self.assertEqual(s2["stages"].get(s), "ok", s)
        self.assertGreaterEqual(self.total(s2, "derived"), e["aave_derived_at_least"])
        self.assertGreaterEqual(self.total(s2, "decided"), e["aave_decided_at_least"])
        self.assertEqual(sum(v.get("records", 0) for v in s2["run_runners"].values()), self.total(s2, "derived"))
        self.assertEqual(self.total(s1, "derived"), e["eigen_derived"])
        for s in ("extract", "sorts", "types", "model", "disch", "evidence", "derive"):
            self.assertEqual(s1["stages"].get(s), "ok", s)

    def test_p11_families(self):
        if not FAMILIES.is_file():
            self.skipTest("the per-family record was not written (recorded under Not done)")
        d = json.loads(FAMILIES.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        fam = {x["id"]: x["families"] for x in d["targets"]}
        self.assertEqual(set(fam), {"s1", "s2"})
        for i, fs in fam.items():
            self.assertTrue(fs, i)
            for k, v in fs.items():
                self.assertIn(v["reason"], ("derived", "no_input", "input_no_law", "part_absent"), (i, k))
                self.assertEqual(v["reason"] == "derived", v["laws"] > 0, (i, k))
        self.assertEqual(sum(v["laws"] for v in fam["s1"].values()), 0)
        self.assertTrue(any(v["reason"] == "no_input" for v in fam["s1"].values()))

    def test_p12_gate(self):
        """Q88 (1): at least 1 law decided on the corpus and at least 1 on at least one spent target."""
        t = self.targets()
        rows = json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))["rows"]
        corpus = sum(f["decided"] for r in rows for f in (r.get("laws_aggregate") or {}).values())
        self.assertGreaterEqual(corpus, 1)
        self.assertGreaterEqual(max(self.total(x, "decided") for x in t.values()), 1)


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_p13_morph_record_moves_only_by_restamp(self):
        T12.TestRegressions.test_p14_morph_record_moves_only_by_restamp(self)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i116",
                    "tests-m6-i118"):
            self.assertIn(f"name: {job}", wf, job)


if __name__ == "__main__":
    unittest.main()
