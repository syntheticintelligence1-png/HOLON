"""I115 (M6, generality): the binding wall. Contract tests (spec/M6/predictions/I115.json; prompts/I115_binding_wall.md).

The wall I112 measured: on the corpus the milestone runner writes no record for any of its 93 PAR laws. Found on the
planted fixture before the prereg: the Go-op model (holon.gen.goloop) models an op only in its loop class, so a law
over any other op names a definition its model does not define; holon.codecrun.decide computes that law's kernel cone,
holon.bindings.kernel_cone raises BindingError, and the whole runner stops. The composed route runs no holon bind
either, so G2 could check none of its decided laws. HUMAN_ANSWERS Q88 (2) and Q87, justified by the binding's
semantics, never by a corpus entry.

  (1) The binding.
      holon run --unbound unknown (protocol run_unbound "unknown", passed to the milestone runner): before a law is
      decided its binding is computed, the kernel cone of its statement roots over the kernel entries of its model. A
      BindingError makes the law UNKNOWN with nothing attempted: kernel and checker not_run, no witness, no law or proof
      file, attempts [{kind: binding, error}], bound "not decided: the statement cannot be bound to its model: ...". A
      BindingError on the decided statement text drops the decision the same way. Every other law is decided as before;
      only BindingError is caught. Without the option a BindingError stops the runner, as before.
      Protocol bind "derived": after the run step the composed driver runs holon bind --milestone M --root <scratch>
      --unbound skip (stage bind): holon.bindings.bind_law for every derived law, as route A's milestones are bound,
      into the scratch root's spec/bindings/<M>.json; a law bind_law cannot bind is listed in
      spec/bindings/<M>.unbound.json {law: error}. --unbound skip refuses a milestone that already has a bindings file.
      Then holon_run.binding_check: a PROVED or REFUTED record is admitted only when its law is bound with the record's
      statement_hash and artifacts.model; any other decided record is rewritten UNKNOWN (attempts + [{kind:
      binding_check, error}]). No family is exempt (G2 binds every law of a milestone). The stage's detail and the
      row's bind field are aggregates only; the bindings name law ids and go to the vault.
  (2) Q87, the go pins: every go_set release of config/toolchains.json carries bin_sha256, its installed bin/go's
      sha256. Under preflight "toolchain_sets" with preflight_go "bin_sha256" the preflight checks it as well as the
      version line; a failure refuses the run (exit 2) and is recorded in <out>/preflight.json, nothing else written.
      I112's protocol keeps the version line alone.

The planted fixture tests_m6/fixtures/i115 is a Go package written for these tests: Blob, an interface carrier whose two
ops each loop over the blob's bytes (goloop's class: their laws are bound and decided), and Counter, a Go machine
whose Bump the static go_ops role also takes as an op of a component, outside the loop class: the totality law over it
names a definition its model does not define (the planted control). Expectations are known by construction.

The corpus smoke measures are results/M6/I115/holon/corpus.json (holon eval holon --protocol spec/M6/lib/i115_run.json
--compose). A run on I106's targets, labelled contaminated: post-I107, commits aggregates only
(results/M6/I115/sealed.json; Q56, Q72).
"""
from __future__ import annotations

import hashlib
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
FIX = ROOT / "tests_m6" / "fixtures" / "i115"
GOSRC = FIX / "src"
PROTO = "spec/M6/lib/i115_run.json"
PROTO_I112 = "spec/M6/lib/i112_run.json"
OUT = ROOT / "results" / "M6" / "I115"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
BASE = "a813b2b9"   # the lead before I110-I112 (#184): Morph's record as landed
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
CONTROL = "L_par_tot_scan_Counter_Bump"   # the law over the op goloop leaves out (by construction of the fixture)
OPT_INS = ("run_unbound", "bind", "preflight_go")


def run_holon(args: list[str], timeout: int = 1800, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env or ENV, capture_output=True,
                          text=True, timeout=timeout)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I115.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def records(S: Path, M: str) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((S / "results" / M).glob("L*.json"))}


def derived(S: Path, M: str) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((S / "laws" / M).glob("L*.json"))}


# ----------------------------------------------------------------------------------------------- the fixture
class _Planted(unittest.TestCase):
    """The composed route's Go part, route C and typed part over the planted package, in a scratch root: the codec
    extraction (holon extract go), the Go machines (holon_run.go_machines), the static roles installed where none
    exists, then holon_run._rules with route C before derive (run, and under the I115 protocol bind)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i115-"))
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self, proto_name: str = PROTO):
        if proto_name not in self.runs:
            from holon.eval import holon_run as H
            t = self.tmp / f"run{len(self.runs)}"
            t.mkdir()
            proto = protocol(proto_name)
            S = H.scratch_root(ROOT, t, "holon/i115", GOSRC)
            rel = "results/eval/holon/i115"
            (S / rel / "sidecars").mkdir(parents=True)
            (S / rel / "facts").mkdir(parents=True)
            R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
            M = proto["milestone"]
            cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
            cfg["source"] = {"path": "<given by --src>"}
            cp = S / rel / "sidecars" / "scan.json"
            cp.write_text(H.dumps(cfg))
            st: dict = {}
            st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                                str(GOSRC), "--out-dir", str(S / rel / "facts")])
            self.assertEqual(st["extract"]["status"], "ok", st["extract"]["detail"][-2000:])
            ms = H.go_machines(R, S, rel, proto, {"id": "i115"}, {"stem": "scan", "unit": cfg["documents"]["scan"][0]},
                               cfg, GOSRC, t)
            self.assertEqual(ms[0]["status"], "extracted", ms[0]["reason"])
            files = sorted(p.name for p in (S / rel / "facts").glob("*.extracted.json"))
            st["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents",
                                            ",".join(f"{rel}/facts/{f}" for f in files), "--out-dir",
                                            str(S / rel / "sidecars" / "roles"), "--mode", "static", "--install",
                                            "--roles", "hand"])
            lib = S / "spec" / M / "lib"
            H._rules(R, S, rel, M, proto, [{"file": f} for m in ms for f in m["files"]], st,
                     lambda: H._route_c(R, S, M, lib, st))
            self.runs[proto_name] = (st, S, M)
        return self.runs[proto_name]


class TestUnbound(_Planted):
    """P1: holon run --unbound unknown."""

    def test_p1_unbound_law_unknown_others_decided(self):
        st, S, M = self.run_of()
        self.assertEqual(st["derive"]["status"], "ok", st["derive"].get("detail", "")[-2000:])
        laws = derived(S, M)
        self.assertIn(CONTROL, laws)
        mil = st["run"]["runners"]["milestone"] if "runners" in st["run"] else None
        recs = records(S, M)
        self.assertEqual(sorted(recs), sorted(laws), st["run"]["detail"][-2000:])
        if mil is not None:
            self.assertEqual(mil["exit"], 0)
            self.assertEqual(mil["records"], mil["laws"])
        c = recs[CONTROL]
        self.assertEqual(c["status"], "UNKNOWN")
        self.assertEqual([a.get("kind") for a in c["attempts"]], ["binding"])
        self.assertIn("resolves to no kernel entry", c["attempts"][0]["error"])
        self.assertIsNone(c["witness"])
        self.assertEqual(c["kernel"]["verdict"], "not_run")
        self.assertIsNone(c["artifacts"]["laws"])
        par = [k for k, r in recs.items() if k.startswith("L_par_") and k != CONTROL
               and r["status"] in ("PROVED", "REFUTED")]
        self.assertTrue(par, {k: r["status"] for k, r in recs.items()})

    def test_p1_without_the_option_the_runner_stops(self):
        st, S, M = self.run_of(PROTO_I112)
        self.assertNotIn(CONTROL, records(S, M))
        mil = st["run"]["runners"]["milestone"]
        self.assertNotEqual(mil["exit"], 0)
        self.assertNotIn("bind", st)


class TestBind(_Planted):
    """P2, P4: the bind stage and the binding check over the planted run."""

    def test_p2_bind_stage(self):
        st, S, M = self.run_of()
        self.assertEqual(st["bind"]["status"], "ok", st["bind"].get("detail", "")[-2000:])
        self.assertNotRegex(st["bind"]["detail"], LAW_ID)
        b = json.loads((S / "spec" / "bindings" / f"{M}.json").read_text(encoding="utf-8"))
        u = json.loads((S / "spec" / "bindings" / f"{M}.unbound.json").read_text(encoding="utf-8"))
        laws = derived(S, M)
        self.assertEqual(sorted(u["laws"]), [CONTROL])
        self.assertEqual(sorted(set(b["laws"]) | set(u["laws"])), sorted(laws))
        self.assertFalse(set(b["laws"]) & set(u["laws"]))
        recs = records(S, M)
        for k, r in recs.items():
            if r["status"] in ("PROVED", "REFUTED"):
                self.assertEqual(b["laws"][k]["statement_hash"], r["statement_hash"], k)
                self.assertEqual(b["laws"][k]["model"], r["artifacts"]["model"], k)
            self.assertNotIn("binding_check", [a.get("kind") for a in r["attempts"]], k)
        self.assertEqual(st["bind"]["aggregate"], {"laws": len(laws), "bound": len(laws) - 1, "unbound": 1,
                                                   "refused": 0})
        self.assertEqual(git("status", "--porcelain", "--", "spec/bindings"), b"")

    def test_p4_every_family_bound(self):
        st, S, M = self.run_of()
        b = json.loads((S / "spec" / "bindings" / f"{M}.json").read_text(encoding="utf-8"))
        rules = {k: v.get("rule") for k, v in derived(S, M).items()}
        self.assertIn("DISCH", set(rules.values()))
        self.assertIn("PAR", set(rules.values()))
        for k, r in rules.items():
            if r == "DISCH":
                self.assertIn(k, b["laws"], k)
        if HOLON_CORPUS.is_file():   # the composed rows' aggregates keep every derived record's roles_source
            for row in json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))["rows"]:
                for key in row.get("laws_aggregate") or {}:
                    self.assertIn(" roles_source=", key, row["id"])


class TestBindingCheck(unittest.TestCase):
    """P3: the planted control of the binding check, unit level."""

    def _rec(self, lid: str, status: str, model: str = "gen/M9/model/m.bend", sh: str = "a" * 64) -> dict:
        return {"law_id": lid, "status": status, "statement_hash": sh, "kernel": {"verdict": "checked"},
                "checker": {"exit_code": 0, "marker": "ALL PROOFS CHECK"}, "witness": {"b": 1} if status == "REFUTED"
                else None, "difference": None, "artifacts": {"model": model, "laws": "x/LAWS.bend",
                                                             "proof": "x/PROOF.bend", "law_name": "l"},
                "attempts": [{"kind": "counter-law"}], "scope": "unbounded"}

    def test_p3_misbound_refused(self):
        from holon.eval import holon_run as H
        tmp = Path(tempfile.mkdtemp(prefix="holon-i115-bc-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        M = "M9"
        (tmp / "results" / M).mkdir(parents=True)
        (tmp / "spec" / "bindings").mkdir(parents=True)
        recs = {"L_ok": self._rec("L_ok", "PROVED"), "L_unk": {**self._rec("L_unk", "UNKNOWN"), "witness": None},
                "L_missing": self._rec("L_missing", "REFUTED"), "L_model": self._rec("L_model", "REFUTED"),
                "L_hash": self._rec("L_hash", "REFUTED")}
        for k, r in recs.items():
            (tmp / "results" / M / f"{k}.json").write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
        bound = {"L_ok": {"statement_hash": "a" * 64, "model": "gen/M9/model/m.bend", "cone": {}},
                 "L_unk": {"statement_hash": "a" * 64, "model": "gen/M9/model/m.bend", "cone": {}},
                 "L_model": {"statement_hash": "a" * 64, "model": "gen/M9/model/other.bend", "cone": {}},
                 "L_hash": {"statement_hash": "b" * 64, "model": "gen/M9/model/m.bend", "cone": {}}}
        (tmp / "spec" / "bindings" / f"{M}.json").write_text(json.dumps({"milestone": M, "laws": bound}))
        before = {k: (tmp / "results" / M / f"{k}.json").read_bytes() for k in recs}
        refused = H.binding_check(tmp, M, sorted(recs))
        self.assertEqual(refused, 3)
        for k in ("L_ok", "L_unk"):
            self.assertEqual((tmp / "results" / M / f"{k}.json").read_bytes(), before[k], k)
        for k in ("L_missing", "L_model", "L_hash"):
            r = json.loads((tmp / "results" / M / f"{k}.json").read_text())
            self.assertEqual(r["status"], "UNKNOWN", k)
            self.assertEqual(r["attempts"][-1]["kind"], "binding_check", k)
            self.assertIsNone(r["witness"], k)
            self.assertIsNone(r["artifacts"]["laws"], k)
            self.assertIsNone(r["artifacts"]["proof"], k)
            self.assertEqual(r["kernel"]["verdict"], "not_run", k)

    def test_p3_unbound_skip_refuses_an_existing_binding(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i115-bs-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "spec" / "bindings").mkdir(parents=True)
        (tmp / "spec" / "bindings" / "M9.json").write_text('{"milestone": "M9", "laws": {}}\n')
        r = run_holon(["bind", "--milestone", "M9", "--root", str(tmp), "--unbound", "skip"], timeout=600)
        self.assertEqual(r.returncode, 1, r.stderr[-2000:])
        self.assertIn("--unbound skip", r.stderr)


class TestGoPins(unittest.TestCase):
    """P5: Q87's go pins."""

    def test_p5_every_go_release_pins_its_binary(self):
        c = json.loads((ROOT / "config" / "toolchains.json").read_text(encoding="utf-8"))
        for v, r in c["go_set"]["releases"].items():
            self.assertRegex(r.get("bin_sha256") or "", r"^[0-9a-f]{64}$", v)

    def _sets(self, tmp: Path, pin: str | None) -> Path:
        gr = tmp / "go1"
        (gr / "bin").mkdir(parents=True)
        (gr / "bin" / "go").write_text("#!/bin/sh\necho 'go version go9.9.9 linux/amd64'\n")
        (gr / "bin" / "go").chmod(0o755)
        good = hashlib.sha256((gr / "bin" / "go").read_bytes()).hexdigest()
        rel = {"goroot": str(gr), "version_line": "go version go9.9.9 linux/amd64"}
        if pin == "good":
            rel["bin_sha256"] = good
        elif pin == "bad":
            rel["bin_sha256"] = "0" * 64
        d = tmp / "solc-set"
        d.mkdir()
        (d / "solc-0.8.1").write_bytes(b"solc 0.8.1")
        cfg = {"solc_set": {"dir": str(d), "releases": {"0.8.1": hashlib.sha256(b"solc 0.8.1").hexdigest()}},
               "go_set": {"releases": {"9.9.9": rel}}}
        p = tmp / "toolchains.json"
        p.write_text(json.dumps(cfg))
        return p

    def test_p5_preflight_checks_the_binary(self):
        from holon.eval import holon_run as H
        for pin, ok_i115, ok_i112 in (("good", True, True), ("bad", False, True), (None, False, True)):
            tmp = Path(tempfile.mkdtemp(prefix="holon-i115-pf-"))
            self.addCleanup(shutil.rmtree, tmp, True)
            sets = json.loads(self._sets(tmp, pin).read_text())
            r = H.preflight(protocol(PROTO), sets)
            self.assertEqual(r["status"] == "ok", ok_i115, (pin, r))
            (g,) = [b for b in r["binaries"] if b["tool"] == "go"]
            self.assertIn("bin_sha256", g)
            r2 = H.preflight(protocol(PROTO_I112), sets)
            self.assertEqual(r2["status"] == "ok", ok_i112, (pin, r2))
            (g2,) = [b for b in r2["binaries"] if b["tool"] == "go"]
            self.assertNotIn("bin_sha256", g2)

    def test_p5_refusal_recorded(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i115-pf2-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        p = self._sets(tmp, "bad")
        out = tmp / "out"
        r = run_holon(["eval", "holon", "--protocol", PROTO, "--compose", "--entries", "c99", "--out", str(out)],
                      timeout=600, env={**ENV, "HOLON_TOOLCHAINS": str(p)})
        self.assertEqual(r.returncode, 2, r.stderr[-2000:])
        self.assertIn("preflight", r.stderr)
        self.assertEqual(sorted(x.name for x in out.iterdir()), ["preflight.json"])
        pf = json.loads((out / "preflight.json").read_text())
        self.assertEqual(pf["status"], "failed")
        self.assertFalse(all(b["ok"] for b in pf["binaries"]))


# ----------------------------------------------------------------------------------------------- the corpus
class TestCorpusSmoke(unittest.TestCase):
    """P7-P10: smoke measures on I51's 20 entries (contaminated by I51, I103-I112 and I107)."""

    def doc(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I115/holon/corpus.json is missing")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def rows(self) -> dict:
        return {r["id"]: r for r in self.doc()["rows"]}

    def test_p7_stage_reach(self):
        e = pred("I115-P7")["expected"]
        pf = self.doc()["preflight"]
        self.assertEqual(pf["status"], "ok")
        self.assertEqual(pf["go"], {"checked": 2, "ok": 2})
        self.assertTrue(all("bin_sha256" in b for b in pf["binaries"] if b["tool"] == "go"))
        reach: dict = {}
        for i, r in self.rows().items():
            self.assertTrue(r.get("compose"), i)
            st = r.get("stages") or {}
            for s, v in st.items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(i)
                elif v.get("status") not in ("not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {s} has no reason")
            if r.get("laws_aggregate"):
                self.assertEqual((st.get("bind") or {}).get("status"), "ok", i)
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)

    def test_p8_milestone_runner(self):
        e = pred("I115-P8")["expected"]
        unb, refused = 0, 0
        for i, r in self.rows().items():
            m = (r.get("run_runners") or {}).get("milestone")
            if m:
                self.assertEqual(m["records"], m["laws"], i)
                unb += m.get("binding_unknown", 0)
            if r.get("bind"):
                refused += r["bind"]["refused"]
        self.assertGreaterEqual(unb, e["unbound_unknown_at_least"])
        self.assertEqual(refused, e["refused"])

    def test_p9_laws_aggregate(self):
        e = pred("I115-P9")["expected"]
        rows = self.rows()
        aggs = [(k, f) for r in rows.values() for k, f in (r.get("laws_aggregate") or {}).items()]
        for i, r in rows.items():
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
        for k, f in aggs:
            self.assertIn(" roles_source=", k)
            self.assertEqual(set(f), {"derived", "decided", "unknown"}, k)
            self.assertEqual(f["derived"], f["decided"] + f["unknown"], k)
        self.assertGreaterEqual(sum(f["derived"] for _k, f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for _k, f in aggs), e["decided_at_least"])
        self.assertLessEqual(sum(f["decided"] for k, f in aggs if k.startswith("PAR/")), e["par_decided_at_most"])

    def test_p10_nothing_per_law_committed(self):
        base = OUT / "holon"
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base).as_posix()
            if LAW_ID.search(rel) or "/bindings/" in f"/{rel}" or p.name.endswith(".unbound.json"):
                hits.append(rel)
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
                hits.append(rel)
        self.assertEqual(hits, [])
        for r in self.rows().values():
            if r.get("laws_aggregate"):
                self.assertEqual(len(r["laws_bundle_sha256"]), 64, r["id"])


class TestSealedContaminated(unittest.TestCase):
    """P11: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p11_spent_targets(self):
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        derived_n = 0
        for x in d["targets"]:
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, x["id"])
            for k in x.get("laws_aggregate", {}).values():
                self.assertEqual(set(k), {"derived", "decided", "unknown"}, x["id"])
                derived_n += k["derived"]
        self.assertEqual(derived_n, 0)
        self.assertFalse(d["gate_q88_1"]["met"])


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_p12_morph_record_moves_only_by_restamp(self):
        """Compared as G1 compares: generator_sha256 and every `seconds` stripped, G1_EXCLUDED skipped."""
        from holon.gate import G1_EXCLUDED

        def unstamp(x):
            if isinstance(x, dict):
                return {k: unstamp(v) for k, v in x.items() if k not in ("generator_sha256", "seconds")}
            if isinstance(x, list):
                return [unstamp(v) for v in x]
            return x
        moved = []
        for d in MORPH_DIRS:
            base = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", BASE, "--", d)
                    .decode().splitlines()}
            head = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", "HEAD", "--", d)
                    .decode().splitlines()}
            for p in sorted(set(base) | set(head)):
                if base.get(p) == head.get(p) or p.rsplit("/", 1)[-1] in G1_EXCLUDED:
                    continue
                if p not in base or p not in head or not p.endswith(".json"):
                    moved.append(p)
                    continue
                if unstamp(json.loads(git("cat-file", "blob", base[p]))) != \
                        unstamp(json.loads(git("cat-file", "blob", head[p]))):
                    moved.append(p)
        self.assertEqual(moved, [])

    def test_p12_morph_sidecars_name_no_opt_in(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and any(k in d for k in OPT_INS + ("unbound",)):
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_p6_earlier_protocols_name_no_opt_in(self):
        for p in sorted((ROOT / "spec" / "M6" / "lib").glob("i1*_run.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            # amended (spec/M6/amendments/I115.jsonl): the protocols of I115 and later keys are not earlier ones
            it = str(d.get("iteration") or "")
            if p.name == "i115_run.json" or (it[1:].isdigit() and int(it[1:]) >= 115):
                continue
            self.assertEqual([k for k in OPT_INS if k in d], [], p.name)

    def test_p12_protocol_is_i112s_plus_the_opt_ins(self):
        a = json.loads((ROOT / PROTO_I112).read_text(encoding="utf-8"))
        b = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(b.pop("run_unbound"), "unknown")
        self.assertEqual(b.pop("bind"), "derived")
        self.assertEqual(b.pop("preflight_go"), "bin_sha256")
        b.pop("bind_doc")
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i115"):
            self.assertIn(f"name: {job}", wf, job)


if __name__ == "__main__":
    unittest.main()
