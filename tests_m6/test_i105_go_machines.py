"""I105 (M6, generality): Go state machines. Contract tests (spec/M6/predictions/I105.json; prompts/I105_go_machines.md).

The Go frontend emits transitions documents in the Solidity frontend's IR (holon-facts/0.3, extraction.kind
"transitions", the term language of holon.frontends.solidity.transitions), one per machine:

  python -m holon extract go_machines --root ROOT --config CFG --src SRC --out-dir DIR

reads a holon-go-frontend/0.3 config (the codec frontend's, unchanged) and writes DIR/<stem>.<Type>.extracted.json for
every machine of the config's documents. A machine is a named struct type declared in a document package with at least
one exported method declared there; its fields are the state (one family per field; a field used as a KV store
(Get/Set/Has/Delete over []byte keys) is one mapping family keyed by the key bytes), its exported methods the actions.
doc["contract"] is "<package path>.<Type>". Guards come from paths that return a non-nil error or panic before any
write; writes from field assignments (through the receiver pointer, local aliases of field addresses, and the map
fields a value receiver shares). A write the frontend cannot model makes the write set over-approximate: the family is
written with a value that holds ["unknown", ...] (havoc), and the cause is a doc["debt"] entry {action, kind, src, what}.

The planted fixture tests_m6/fixtures/i105/src is written for these tests; every expectation below is known from its
source by construction. The corpus smoke measures (results/M6/I105/corpus.json) are I105's predictions P6-P8, written by
python -m holon eval go-machines.
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

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i105"
SRC = FIX / "src"
CFG = FIX / "go_config.json"
CORPUS = ROOT / "results" / "M6" / "I105" / "corpus.json"
PKG = "example.com/holon/i105"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}


def run_holon(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


def extract(out: Path) -> subprocess.CompletedProcess:
    return run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(CFG), "--src", str(SRC),
                      "--out-dir", str(out)])


def mentions(term, sub) -> bool:
    """sub occurs in term (a term is an int or a list whose first element is its tag)."""
    if term == sub:
        return True
    return isinstance(term, list) and any(mentions(t, sub) for t in term)


def has_tag(term, tag: str) -> bool:
    return isinstance(term, list) and ((term[:1] == [tag]) or any(has_tag(t, tag) for t in term))


def havoc(value) -> bool:
    return has_tag(value, "unknown")


class _Docs(unittest.TestCase):
    docs: dict = {}
    files: dict = {}
    proc = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i105-"))
        cls.proc = extract(cls.tmp / "a")
        cls.docs, cls.files = {}, {}
        if cls.proc.returncode == 0:
            for p in sorted((cls.tmp / "a").glob("*.extracted.json")):
                d = json.loads(p.read_text(encoding="utf-8"))
                cls.docs[d["contract"]] = d
                cls.files[d["contract"]] = p

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def doc(self, typ: str) -> dict:
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-3000:])
        name = f"{PKG}/{typ}"
        self.assertIn(name, self.docs, sorted(self.docs))
        return self.docs[name]

    def action(self, typ: str, name: str) -> dict:
        acts = {a["name"]: a for a in self.doc(typ)["actions"]}
        self.assertIn(name, acts, sorted(acts))
        return acts[name]

    def written(self, typ: str, name: str) -> dict:
        """{family: [write]} of an action."""
        out: dict = {}
        for w in self.action(typ, name)["writes"]:
            out.setdefault(w["family"], []).append(w)
        return out


class TestStructMachines(_Docs):
    """P1: the struct-field pattern."""

    def test_p1_envelope(self):
        d = self.doc("machines.Bank")
        self.assertEqual(d["facts_version"], "holon-facts/0.3")
        self.assertEqual(d["extraction"]["kind"], "transitions")
        self.assertEqual(d["extraction"]["frontend"], "go")
        for k in ("target", "extraction", "contract", "constants", "storage", "actions", "assumptions",
                  "inherited_storage"):
            self.assertIn(k, d)

    def test_p1_machines_of_the_fixture(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-3000:])
        self.assertEqual(sorted(self.docs), [f"{PKG}/keeper.Keeper", f"{PKG}/machines.Alias", f"{PKG}/machines.Bank",
                                             f"{PKG}/machines.Loop", f"{PKG}/machines.Spawn"])

    def test_p1_bank_state_and_actions(self):
        d = self.doc("machines.Bank")
        fams = {f["name"]: f for f in d["storage"]}
        self.assertEqual(sorted(fams), ["Bal", "Count", "Owner", "Paused"])
        self.assertEqual(fams["Bal"]["kind"], "mapping")
        self.assertEqual(fams["Count"]["kind"], "scalar")
        self.assertEqual(sorted(a["name"] for a in d["actions"]),
                         ["Credit", "Deposit", "Halt", "Lose", "SetPaused", "Tick", "Total", "Withdraw"])

    def test_p1_bank_writes(self):
        dep = self.written("machines.Bank", "Deposit")
        self.assertEqual(sorted(dep), ["Bal", "Count"])
        self.assertEqual(dep["Bal"][0]["path"], [["map", ["param", "who"]]])
        self.assertFalse(havoc(dep["Count"][0]["value"]))
        self.assertTrue(mentions(dep["Count"][0]["value"], ["storage", "Count"]))
        self.assertEqual(sorted(self.written("machines.Bank", "SetPaused")), ["Paused"])
        self.assertEqual(self.written("machines.Bank", "SetPaused")["Paused"][0]["value"], ["param", "p"])
        self.assertEqual(sorted(self.written("machines.Bank", "Withdraw")), ["Bal"])
        self.assertEqual(sorted(self.written("machines.Bank", "Credit")), ["Bal"], "a value receiver shares its maps")
        self.assertEqual(self.written("machines.Bank", "Lose"), {}, "a value receiver's field write is to a copy")
        self.assertEqual(self.written("machines.Bank", "Total"), {})
        self.assertEqual(sorted(self.written("machines.Bank", "Tick")), ["Count"], "an unexported helper is inlined")

    def test_p1_bank_guards(self):
        sp = self.action("machines.Bank", "SetPaused")["guards"]
        self.assertTrue(any(mentions(g["expr"], ["param", "caller"]) and mentions(g["expr"], ["storage", "Owner"])
                            for g in sp), sp)
        wd = self.action("machines.Bank", "Withdraw")["guards"]
        self.assertTrue(any(mentions(g["expr"], ["storage", "Paused"]) for g in wd), wd)
        self.assertTrue(any(mentions(g["expr"], ["param", "n"]) for g in wd), wd)
        ht = self.action("machines.Bank", "Halt")["guards"]
        self.assertTrue(any(mentions(g["expr"], ["storage", "Paused"]) for g in ht), ht)
        self.assertEqual(self.action("machines.Bank", "Total")["returns"], ["storage", "Count"])


class TestSoundness(_Docs):
    """P2: a write the frontend cannot model over-approximates the write set (havoc); none is dropped."""

    def test_p2_alias_resolved(self):
        w = self.written("machines.Alias", "Through")
        self.assertEqual(sorted(w), ["X"])
        self.assertEqual(w["X"][-1]["value"], ["param", "v"])

    def test_p2_alias_dynamic_call(self):
        w = self.written("machines.Alias", "Leak")
        self.assertIn("Y", w)
        self.assertTrue(havoc(w["Y"][-1]["value"]))

    def test_p2_write_through_state_pointer(self):
        w = self.written("machines.Alias", "Deref")
        self.assertEqual(sorted(w), ["P", "X", "Y"], "a pointer read from the state may alias every family")
        self.assertTrue(all(havoc(ws[-1]["value"]) for ws in w.values()))

    def test_p2_unbounded_loop(self):
        w = self.written("machines.Loop", "Fill")
        self.assertTrue({"Arr", "N"} <= set(w), w)
        self.assertTrue(havoc(w["Arr"][-1]["value"]) and havoc(w["N"][-1]["value"]))
        self.assertEqual(w["K"][-1]["value"], 7)
        debt = [x for x in self.doc("machines.Loop")["debt"] if x["action"] == "Fill"]
        self.assertTrue(any(x["kind"] == "loop" for x in debt), debt)

    def test_p2_goroutine(self):
        w = self.written("machines.Spawn", "Go")
        self.assertIn("X", w)
        self.assertTrue(havoc(w["X"][-1]["value"]))
        self.assertEqual(w["Z"][-1]["value"], 2)
        debt = [x for x in self.doc("machines.Spawn")["debt"] if x["action"] == "Go"]
        self.assertTrue(any(x["kind"] == "goroutine" for x in debt), debt)


class TestKVMachines(_Docs):
    """P3: the KV-store pattern (constant prefix plus argument keys, a structural mapping family)."""

    def test_p3_kv_family(self):
        d = self.doc("keeper.Keeper")
        fams = {f["name"]: f for f in d["storage"]}
        self.assertIn("store", fams)
        self.assertEqual(fams["store"]["kind"], "mapping")
        self.assertEqual(sorted(a["name"] for a in d["actions"]), ["Balance", "Remove", "SetBalance"])

    def test_p3_kv_writes(self):
        w = self.written("keeper.Keeper", "SetBalance")
        self.assertEqual(sorted(w), ["store"])
        (key,) = [k for kind, k in w["store"][0]["path"] if kind == "map"]
        self.assertTrue(mentions(key, ["param", "addr"]), key)
        self.assertTrue(mentions(key, ["str", "bal/".encode().hex()]), key)
        self.assertTrue(mentions(w["store"][0]["value"], ["param", "amt"]))
        g = self.action("keeper.Keeper", "SetBalance")["guards"]
        self.assertTrue(any(mentions(x["expr"], ["param", "caller"]) for x in g), g)
        r = self.written("keeper.Keeper", "Remove")
        self.assertEqual(sorted(r), ["store"])
        self.assertEqual(r["store"][0]["value"], 0)
        rg = self.action("keeper.Keeper", "Remove")["guards"]
        self.assertTrue(any(mentions(x["expr"], ["storage", "store"]) for x in rg), rg)


class TestDeterminism(_Docs):
    """P5: byte-identical documents across runs."""

    def test_p5_byte_identical(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-3000:])
        p2 = extract(self.tmp / "b")
        self.assertEqual(p2.returncode, 0, p2.stderr[-3000:])
        a = {p.name: p.read_bytes() for p in (self.tmp / "a").glob("*.extracted.json")}
        b = {p.name: p.read_bytes() for p in (self.tmp / "b").glob("*.extracted.json")}
        self.assertEqual(sorted(a), sorted(b))
        self.assertTrue(all(a[k] == b[k] for k in a))


class TestTypedPipeline(_Docs):
    """P4: the typed pipeline (I51's stages sorts, types, model, disch, derive) runs unchanged on a Go machine."""

    def test_p4_bank_end_to_end(self):
        from holon.eval import common, holon_run as H
        d = self.doc("machines.Bank")
        proto = common.load_json(ROOT / "spec" / "M4" / "lib" / "i51_run.json")
        tmp = self.tmp / "pipe"
        tmp.mkdir()
        S = H.scratch_root(ROOT, tmp, d["target"]["repo"], SRC)
        rel = "results/eval/holon/i105"
        (S / rel / "sidecars").mkdir(parents=True)
        (S / rel / "facts").mkdir(parents=True)
        name = self.files[d["contract"]].name
        shutil.copy(self.files[d["contract"]], S / rel / "facts" / name)
        stages: dict = {}
        H._rules(H.Runner(H.Ctx(tmp, SRC), S, proto, {}), S, rel, proto["milestone"], proto, [{"file": name}], stages)
        for st in ("sorts", "types", "model", "disch", "derive"):
            self.assertIn(st, stages, stages)
            self.assertEqual(stages[st]["status"], "ok", f"{st}: {stages[st]['detail'][-2000:]}")
        laws = sorted(p.stem for p in (S / "laws" / proto["milestone"]).glob("L*.json"))
        self.assertGreaterEqual(len(laws), 1, stages["derive"]["detail"])


class TestCorpusSmoke(unittest.TestCase):
    """P6-P8: the smoke measures on I51's Go entries (results/M6/I105/corpus.json, holon eval go-machines)."""

    @classmethod
    def setUpClass(cls):
        cls.key = json.loads((ROOT / "spec" / "M6" / "predictions" / "I105.json").read_text(encoding="utf-8"))
        cls.pred = {p["id"]: p for p in cls.key["predictions"]}

    def corpus(self) -> dict:
        self.assertTrue(CORPUS.is_file(), f"{CORPUS.relative_to(ROOT)} is missing: python -m holon eval go-machines")
        return {r["id"]: r for r in json.loads(CORPUS.read_text(encoding="utf-8"))["rows"]}

    def test_p6_machines_and_actions(self):
        rows = self.corpus()
        exp = self.pred["I105-P6"]["expected"]
        self.assertEqual(sorted(rows), sorted(exp))
        for cid, (mlo, mhi, alo, ahi) in sorted(exp.items()):
            with self.subTest(entry=cid):
                self.assertTrue(mlo <= rows[cid]["machines"] <= mhi, (cid, rows[cid]["machines"]))
                self.assertTrue(alo <= rows[cid]["actions"] <= ahi, (cid, rows[cid]["actions"]))

    def test_p7_pipeline_completes(self):
        rows = self.corpus()
        done = sorted(cid for cid, r in rows.items() if r["pipeline"] == "complete")
        self.assertGreaterEqual(len(done), self.pred["I105-P7"]["expected"]["complete_at_least"], rows)
        for cid, r in rows.items():
            if r["pipeline"] != "complete":
                self.assertIn(r["refused_at"], ("extract", "sorts", "types", "model", "disch", "derive"), (cid, r))

    def test_p8_laws(self):
        rows = self.corpus()
        lo, hi = self.pred["I105-P8"]["expected"]["total_laws"]
        tot = sum(r["laws"] for r in rows.values())
        self.assertTrue(lo <= tot <= hi, tot)


class TestRegressions(unittest.TestCase):
    """R1: the existing frontends are unchanged (Solidity documents and Go codec documents byte-identical by
    construction)."""

    def test_r1_frontends_unchanged(self):
        import hashlib
        key = json.loads((ROOT / "spec" / "M6" / "predictions" / "I105.json").read_text(encoding="utf-8"))
        pins = key["thresholds"]["pins"]
        self.assertTrue(pins)
        for rel, sha in sorted(pins.items()):
            with self.subTest(path=rel):
                self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), sha)


if __name__ == "__main__":
    unittest.main()
