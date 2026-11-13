"""I125 (M6 follow-on): F-M6-05's consistency, derive against goops' refusals. Contract tests
(spec/M6/predictions/I125.json; prompts/I125_derive_goops_consistency.md; HUMAN_ANSWERS Q105 (6), Q117 (3) and (5)).

The mechanism (F-M6-05): PAR derives a totality law over every op of a Go-op document, while holon.gen.goloop writes an
op outside its classes as the comment line '# <op>: unsupported (<reason>)' and defines neither <op> nor ok_<op>. A law
over such an op names something its model never defines, so holon run --unbound unknown records it UNKNOWN by its
binding error. UNKNOWN is right; the binding error just does not say why. Choice (B): under the protocol opt-in
run_unbound_reason "goops" (holon run --unbound-reason goops) such a law stays UNKNOWN, and its reason is goops' own
refusal, read from the generated model file. The derived law set is the same with and without the opt-in.

The planted fixture tests_m6/fixtures/i125 is a Go package written from the Go specification alone (its doc comment):
Low (supported, the straight-line class), Quot (a straight-line refusal: division by a non-constant) and Twice (a loop
refusal: two loops in sequence). It runs through the composed route's own stages (extract, Go machines, roles, route C,
derive, run, bind) in a scratch root, once per (code, protocol): this branch's code under the base protocol and under
I125's, and the base code (a git worktree at the key's base) under the base protocol.
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

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i125"
GOSRC = FIX / "src"
PROTO = "spec/M6/lib/i125_run.json"
BASE_PROTO = "spec/M6/lib/base_run.json"
KEY = ROOT / "spec" / "M6" / "predictions" / "I125.json"
OUT = ROOT / "results" / "M6" / "I125"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
BASE_CORPUS = OUT / "base" / "corpus.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
SUPPORTED, STRAIGHT, LOOP = "gate_Low", "gate_Quot", "gate_Twice"
REFUSED = {STRAIGHT: "straight-line", LOOP: "loop"}
G1_STRIP = ("generator_sha256", "seconds")


def key() -> dict:
    return json.loads(KEY.read_text(encoding="utf-8"))


def protocol(name: str = PROTO) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def strip(x):
    """A record compared as G1 compares: generator_sha256 and every seconds field left out."""
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in G1_STRIP}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


# ----------------------------------------------------------------------------------------------- the planted run
def planted_run(code_root: str, proto_path: str, out_json: str) -> None:
    """Run in a subprocess: the planted package through the composed route's stages with the holon/ of code_root (its
    scratch copy), under the protocol at proto_path. Writes {laws, derivation, records, models, stages} to out_json."""
    sys.path.insert(0, code_root)
    from holon.eval import holon_run as H
    t = Path(tempfile.mkdtemp(prefix="holon-i125-run-"))
    try:
        proto = json.loads(Path(proto_path).read_text(encoding="utf-8"))
        S = H.scratch_root(Path(code_root), t, "holon/i125", GOSRC)
        rel = "results/eval/holon/i125"
        (S / rel / "sidecars").mkdir(parents=True)
        (S / rel / "facts").mkdir(parents=True)
        R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
        M = proto["milestone"]
        cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
        cfg["source"] = {"path": "<given by --src>"}
        cp = S / rel / "sidecars" / "gate.json"
        cp.write_text(H.dumps(cfg))
        st: dict = {}
        st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                            str(GOSRC), "--out-dir", str(S / rel / "facts")])
        assert st["extract"]["status"] == "ok", st["extract"]["detail"][-2000:]
        ms = H.go_machines(R, S, rel, proto, {"id": "i125"}, {"stem": "gate", "unit": cfg["documents"]["gate"][0]},
                           cfg, GOSRC, t)
        files = sorted(p.name for p in (S / rel / "facts").glob("*.extracted.json"))
        st["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents",
                                        ",".join(f"{rel}/facts/{f}" for f in files), "--out-dir",
                                        str(S / rel / "sidecars" / "roles"), "--mode", "static", "--install",
                                        "--roles", "hand"])
        lib = S / "spec" / M / "lib"
        H._rules(R, S, rel, M, proto, [{"file": f} for m in ms for f in m["files"]], st,
                 lambda: H._route_c(R, S, M, lib, st))

        def jl(d: Path) -> dict:
            return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("L*.json"))}
        der = S / "laws" / M / "DERIVATION.json"
        out = {"laws": jl(S / "laws" / M), "records": jl(S / "results" / M),
               "derivation": json.loads(der.read_text(encoding="utf-8")) if der.is_file() else None,
               "models": {p.name: p.read_text(encoding="utf-8") for p in sorted((S / "gen" / M / "model").glob("*.bend"))},
               "stages": {k: {kk: vv for kk, vv in v.items() if kk in ("status", "aggregate", "runners")}
                          for k, v in st.items() if isinstance(v, dict)}}
        Path(out_json).write_text(json.dumps(out, sort_keys=True))
    finally:
        shutil.rmtree(t, ignore_errors=True)


_RUNS: dict = {}


def run(which: str) -> dict:
    """which: "opt" (this code, I125's protocol), "base" (this code, the base protocol), "basecode" (the key's base
    commit's code, the base protocol). Each is run once per test process."""
    if which not in _RUNS:
        tmp = Path(tempfile.mkdtemp(prefix=f"holon-i125-{which}-"))
        try:
            code = ROOT
            if which == "basecode":
                code = tmp / "wt"
                base = key()["thresholds"]["base_commit"]
                subprocess.run(["git", "worktree", "add", "--detach", str(code), base], cwd=ROOT, check=True,
                               capture_output=True)
            proto = ROOT / BASE_PROTO
            if which == "opt":   # amended (I125.jsonl): the base protocol plus exactly the opt-in, nothing of I125's
                # own metadata (its iteration tag is written into the Go machine documents, so it moves facts hashes)
                d = protocol(BASE_PROTO)
                d.update({k: protocol()[k] for k in ("run_unbound_reason", "run_unbound_reason_doc")})
                proto = tmp / "opt_run.json"
                proto.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
            out = tmp / "out.json"
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--planted-run", str(code), str(proto),
                                str(out)], cwd=code, env=ENV, capture_output=True, text=True, timeout=3600)
            assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-3000:]
            _RUNS[which] = json.loads(out.read_text(encoding="utf-8"))
        finally:
            if which == "basecode":
                subprocess.run(["git", "worktree", "remove", "--force", str(tmp / "wt")], cwd=ROOT, capture_output=True)
            shutil.rmtree(tmp, ignore_errors=True)
    return _RUNS[which]


def over(lid: str, op: str) -> bool:
    return lid.endswith("_" + op) or f"_{op}_" in lid


# ----------------------------------------------------------------------------------------------- P1: goops' output
class TestGenerator(unittest.TestCase):
    """P1: the generated model of the planted package defines the supported op and writes the two refused ones as
    goops' refusal lines (holon.gen.goloop's output, nothing hand-written)."""

    def test_p1_model_refusal_lines(self):
        r = run("base")
        (text,) = [t for t in r["models"].values() if f"def {SUPPORTED}(" in t]   # amended (I125.jsonl)
        self.assertIn(f"def {SUPPORTED}(", text)
        self.assertIn(f"def ok_{SUPPORTED}(", text)
        from holon import codecrun
        ref = codecrun.goops_refusals(text)
        self.assertEqual(sorted(ref), sorted(REFUSED))
        for op, cls in REFUSED.items():
            self.assertEqual(ref[op]["class"], cls, ref[op])
            self.assertNotIn(f"def {op}(", text)
            self.assertNotIn(f"def ok_{op}(", text)


# ----------------------------------------------------------------------------------------------- P2-P4: planted
class TestPlanted(unittest.TestCase):
    """P2: under the opt-in every law over a refused op is UNKNOWN with goops' refusal as its reason; P3: the derived
    law set and every other law's record are byte-identical without the opt-in; P4: without the opt-in every output is
    the base code's."""

    def test_p2_refused_ops_carry_goops_reason(self):
        opt = run("opt")
        (text,) = [t for t in opt["models"].values() if f"def {SUPPORTED}(" in t]   # amended (I125.jsonl)
        from holon import codecrun
        ref = codecrun.goops_refusals(text)
        touched, seen = 0, set()
        for op, cls in REFUSED.items():
            lids = sorted(lid for lid in opt["laws"] if over(lid, op) and lid not in seen)
            self.assertGreaterEqual(len(lids), 1, op)
            for lid in lids:
                rec = opt["records"][lid]
                self.assertEqual(rec["status"], "UNKNOWN", lid)
                (a,) = rec["attempts"]
                self.assertEqual(a["kind"], "op_refused", lid)
                # amended (I125.jsonl): a pair law (PAR's dom and weak) names two ops, each refused one listed
                self.assertEqual(a["ops"], [{"op": o, "class": REFUSED[o], "reason": ref[o]["reason"]}
                                            for o in sorted(REFUSED) if over(lid, o)], lid)
                self.assertIsInstance(a["binding_error"], str)
                self.assertIn(ref[op]["reason"], rec["bound"])
                self.assertIsNone(rec["witness"])
                self.assertIsNone(rec["artifacts"]["laws"])
                self.assertIsNone(rec["artifacts"]["proof"])
                touched += 1
                seen.add(lid)
        base = run("base")
        for lid in opt["laws"]:   # the same laws were UNKNOWN by their binding without the opt-in
            if any(over(lid, op) for op in REFUSED):
                self.assertEqual(base["records"][lid]["status"], "UNKNOWN", lid)
                self.assertEqual([x["kind"] for x in base["records"][lid]["attempts"]], ["binding"], lid)
        self.assertEqual(touched, sum(1 for lid in opt["laws"] if any(over(lid, op) for op in REFUSED)))

    def test_p3_law_set_and_other_records_unchanged(self):
        opt, base = run("opt"), run("base")
        self.assertEqual(opt["laws"], base["laws"])
        self.assertEqual(opt["derivation"], base["derivation"])
        self.assertEqual(opt["models"], base["models"])
        self.assertEqual(sorted(opt["records"]), sorted(base["records"]))
        sup = [lid for lid in opt["laws"] if over(lid, SUPPORTED)]
        self.assertGreaterEqual(len(sup), 1)
        for lid, rec in opt["records"].items():
            if not any(over(lid, op) for op in REFUSED):
                self.assertEqual(strip(rec), strip(base["records"][lid]), lid)
        dec = lambda r: sum(1 for x in r["records"].values() if x["status"] in ("PROVED", "REFUTED"))
        self.assertEqual(dec(opt), dec(base))

    def test_p4_without_the_opt_in_as_the_base_code(self):
        base, bc = run("base"), run("basecode")
        self.assertEqual(base["laws"], bc["laws"])
        self.assertEqual(base["derivation"], bc["derivation"])
        self.assertEqual(base["models"], bc["models"])
        self.assertEqual(strip(base["records"]), strip(bc["records"]))


# ----------------------------------------------------------------------------------------------- P5: units
class TestUnits(unittest.TestCase):
    """P5 (soundness): the reason is swapped only for a law already UNKNOWN by its binding that names a refused op;
    nothing else is touched, and the option off computes nothing."""

    MODEL = ("# GENERATED\nimport Base\n\ndef ok_a(hs: U32) -> Bool:\n  True\n\n"
             "# b: unsupported (b: straight-line class: b: a division by a non-constant, x)\n\n"
             "# c: unsupported (c: 2 loop bodies (the class has one))\n")

    def test_p5_refusals_parsed_from_the_model_text(self):
        from holon import codecrun
        ref = codecrun.goops_refusals(self.MODEL)
        self.assertEqual(ref, {"b": {"class": "straight-line",
                                     "reason": "b: straight-line class: b: a division by a non-constant, x"},
                               "c": {"class": "loop", "reason": "c: 2 loop bodies (the class has one)"}})

    def test_p5_only_unbound_laws_naming_a_refused_op(self):
        from holon import codecrun
        old = codecrun.UNBOUND_REASON
        try:
            codecrun.UNBOUND_REASON = "goops"
            m = self.MODEL
            self.assertIsNone(codecrun.op_refused_res("goops", "M.ok_b(x) == True", m, None))   # binds: untouched
            self.assertIsNone(codecrun.op_refused_res("goops", "M.ok_a(x) == M.zz(x)", m, "M.zz ..."))   # another cause
            self.assertIsNone(codecrun.op_refused_res("linked", "M.ok_b(x) == True", m, "err"))   # not a Go-op law
            self.assertIsNone(codecrun.op_refused_res("goops", "# M.ok_b in a comment\nM.zz(x)", m, "err"))
            r = codecrun.op_refused_res("goops", "M.ok_c(x) == M.b(x)", m, "err")
            self.assertEqual(r["status"], "UNKNOWN")
            self.assertEqual(r["attempts"], [{"kind": "op_refused", "binding_error": "err", "ops": [
                {"op": "b", "class": "straight-line", "reason": "b: straight-line class: b: a division by a non-constant, x"},
                {"op": "c", "class": "loop", "reason": "c: 2 loop bodies (the class has one)"}]}])
            codecrun.UNBOUND_REASON = None
            self.assertIsNone(codecrun.op_refused_res("goops", "M.ok_c(x)", m, "err"))   # option off: nothing
        finally:
            codecrun.UNBOUND_REASON = old


# ----------------------------------------------------------------------------------------------- P6: regressions
class TestRegressions(unittest.TestCase):
    """P6: Morph's M0-M3 records carry no op_refused attempt and no earlier protocol names the opt-in; the protocol is
    its base plus the opt-in; the base runs pass no new argument."""

    def test_p6_no_committed_record_carries_the_opt_in(self):
        for m in ("M0", "M1", "M2", "M3"):
            for p in sorted((ROOT / "results" / m).rglob("*.json")):
                self.assertNotIn('"op_refused"', p.read_text(encoding="utf-8", errors="replace"), p.as_posix())

    def test_p6_no_earlier_protocol_names_the_opt_in(self):
        for p in sorted((ROOT / "spec").glob("*/lib/*.json")):
            if p.name == "i125_run.json":
                continue
            self.assertNotIn("run_unbound_reason", p.read_text(encoding="utf-8"), p.relative_to(ROOT).as_posix())

    def test_p6_protocol_is_its_base_plus_the_opt_in(self):
        b = protocol()
        a = protocol(b["base_protocol"])
        self.assertEqual(b.pop("run_unbound_reason"), "goops")
        b.pop("run_unbound_reason_doc")
        b.pop("base_protocol")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_p6_runner_args(self):
        from holon.eval import holon_run as H
        base = protocol(BASE_PROTO)
        self.assertEqual(H.runner_args("milestone", base, "t", "d", "f"), ["--unbound", "unknown"])
        self.assertEqual(H.runner_args("milestone", protocol(), "t", "d", "f"),
                         ["--unbound", "unknown", "--unbound-reason", "goops"])


# ----------------------------------------------------------------------------------------------- P7-P9: corpus smoke
class TestCorpusSmoke(unittest.TestCase):
    """P7-P9: smoke on contaminated data (I51's corpus): the base protocol's run and I125's on the same base and code.
    Aggregates only (Q72, Q89)."""

    def docs(self):
        self.assertTrue(HOLON_CORPUS.is_file() and BASE_CORPUS.is_file(), "the measured runs are not committed")
        return (json.loads(HOLON_CORPUS.read_text(encoding="utf-8")),
                json.loads(BASE_CORPUS.read_text(encoding="utf-8")))

    @staticmethod
    def tot(doc: dict, f) -> int:
        return sum(f(r) for r in doc.get("rows") or [])

    @staticmethod
    def agg(r: dict, k: str) -> int:
        return sum((v or {}).get(k, 0) for v in (r.get("laws_aggregate") or {}).values())

    @staticmethod
    def runners(r: dict) -> dict:
        """The run stage's per-runner aggregates, from its detail line ("per runner: {...}; N laws with no record")."""
        d = ((r.get("stages") or {}).get("run") or {}).get("detail") or ""
        m = re.match(r"per runner: (\{.*\}); \d+ laws with no record$", d)
        return json.loads(m.group(1)) if m else {}

    def ru(self, r: dict, k: str) -> int:
        return sum((v or {}).get(k, 0) for v in self.runners(r).values())

    def test_p7_same_laws_same_decided(self):
        opt, base = self.docs()
        for k in ("derived", "decided", "unknown"):
            self.assertEqual(self.tot(opt, lambda r: self.agg(r, k)), self.tot(base, lambda r: self.agg(r, k)), k)

    def test_p8_touched_laws(self):
        opt, base = self.docs()
        p = next(x for x in key()["predictions"] if x["id"] == "I125-P8")["expected"]
        b_unb = self.tot(base, lambda r: self.ru(r, "binding_unknown"))
        o_ref = self.tot(opt, lambda r: self.ru(r, "op_refused_unknown"))
        o_unb = self.tot(opt, lambda r: self.ru(r, "binding_unknown"))
        self.assertEqual(o_ref + o_unb, b_unb)
        self.assertEqual(o_unb, p["binding_unknown_left"])
        self.assertEqual(o_ref, b_unb - p["binding_unknown_left"])
        cls = {}
        for r in opt.get("rows") or []:
            for v in self.runners(r).values():
                for c, n in ((v or {}).get("op_refused_classes") or {}).items():
                    cls[c] = cls.get(c, 0) + n
        self.assertEqual(sum(cls.values()), o_ref)
        self.assertEqual(sorted(cls), sorted(p["classes"]))
        for c, (lo, hi) in p["classes"].items():
            self.assertTrue(lo <= cls.get(c, 0) <= hi, (c, cls.get(c, 0)))

    def test_p9_nothing_per_law_committed(self):
        for p in sorted(OUT.rglob("*.json")):
            self.assertEqual(LAW_ID.findall(p.read_text(encoding="utf-8")), [], p.as_posix())


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--planted-run":
        planted_run(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        unittest.main()
