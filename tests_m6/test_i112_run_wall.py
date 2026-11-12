"""I112 (M6, generality): the run wall. Contract tests (spec/M6/predictions/I112.json; prompts/I112_run_wall.md).

The wall I111 measured: 107 laws derived on the corpus, 0 decided. The composed driver's run call sends route C's laws
to holon.pipeline with typed-only arguments, and one DISCH section error stops the whole DISCH runner. HUMAN_ANSWERS
Q80-Q85, justified by the runners' and the typed model's semantics, never by a corpus entry.

  (1) Per-runner routing (protocol run_routing "per_runner"; holon.eval.holon_run.route). Each derived law goes to the
      runner of its rule family, read from laws/<M>/DERIVATION.json:
        disch      rule DISCH with a sub-form of holon.disch.run.SUBFORMS: --sidecar, --disch, and --section-errors
                   unknown when the protocol names disch.section_errors;
        fact       rule FACT: --sidecar, --fact-sidecar;
        typed      rule SORT (as_member, realize, reinterpret), UNDO, SYM: --sidecar;
        milestone  every other law (PAR, route C's families): no sidecar argument.
      One `holon run --laws` per non-empty group, in that order; a failed call is recorded and the next one runs; a law
      with no record afterwards is UNKNOWN. The run detail holds aggregates only. Without run_routing the run step is
      I110's two calls, unchanged.
      Section errors (holon run --section-errors unknown, holon.disch.run): when building a document's DISCH section
      raises holon.disch.section.SectionError, every DISCH law the run names over that document is UNKNOWN, recorded
      with the error (attempts [{kind: section, error}], kernel and checker not_run, no witness); nothing is attempted
      for it, so an error never yields PROVED or REFUTED. Every other section is built and decided as before. Only
      SectionError is caught.
  (2) O1 widened (typed.types_opaque_classes, under types_fallback "opaque"): GenError is class gen_error (I111),
      holon.machine.MemberLayoutError (the member-layout refusal, a ModelError subclass) member_layout, and
      holon.extracted_eval.Unsupported unsupported. A named class makes the document opaque, with a class field on its
      miss. Absent, the classes are I111's [gen_error] and every output is I111's. Every other error, ModelError
      included, still refuses the milestone (a milestone-wide input error stays a refusal).
  (3) withhold() covers gen/ and the run details (no committed file names a derived law id).
  (4) Q80's preflight (protocol preflight "toolchain_sets"): every toolchain-set binary the protocol can select is
      checked before any entry runs; any missing or different refuses the run (exit 2, nothing written); the check is
      recorded in corpus.json.

The planted fixture tests_m6/fixtures/i112 is written for these tests: a Go package (Ledger, and Gated, whose guard
reads the answer of a function value the package does not define, which the DISCH section refuses), and Solidity
contracts compiled by the pinned solc 0.8.24 (Counter, well typed; Packed, whose typed model raises Unsupported on
abi.encodePacked of a storage string; PackedKept, Packed without that action; LayoutKept, and Layout, LayoutKept's
document with one struct field's offset moved off the compiler's member layout by tools/i112_fixture.py). Their
expectations are known by construction.

The corpus smoke measures are results/M6/I112/holon/corpus.json (holon eval holon --protocol spec/M6/lib/i112_run.json
--compose). A run on I106's targets, labelled contaminated: post-I107, commits aggregates only
(results/M6/I112/sealed.json; Q56, Q72).
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
FIX = ROOT / "tests_m6" / "fixtures" / "i112"
GOSRC = FIX / "src"
SOL = FIX / "sol"
PROTO = "spec/M6/lib/i112_run.json"
PROTO_I111 = "spec/M6/lib/i111_run.json"
OUT = ROOT / "results" / "M6" / "I112"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
BASE = "a813b2b9"   # the lead before I110-I112 (#184): Morph's record as landed
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")


def run_holon(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I112.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def unseconds(x):
    if isinstance(x, dict):
        return {k: unseconds(v) for k, v in x.items() if k not in ("seconds", "model_sha256")}
    if isinstance(x, list):
        return [unseconds(v) for v in x]
    return x


def verdicts(S: Path, M: str) -> dict:
    facts = law_facts(S, M)
    out = {}
    for p in sorted((S / "results" / M).glob("L*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[p.stem] = (r.get("status"), facts.get(p.stem))
    return out


def law_facts(S: Path, M: str) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")).get("facts")
            for p in sorted((S / "laws" / M).glob("L*.json"))}


def _gitify(src: Path) -> str:
    e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
         "GIT_COMMITTER_EMAIL": "t@t"}
    for a in (["init", "-q"], ["add", "."], ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(src), *a], check=True, capture_output=True, env=e)
    return subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


def scratch(tmp: Path, proto: dict, src: Path):
    from holon.eval import holon_run as H
    S = H.scratch_root(ROOT, tmp, "holon/i112", src)
    rel = "results/eval/holon/i112"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    return S, rel, H.Runner(H.Ctx(tmp, src), S, proto, {})


def typed_part(S: Path, rel: str, R, proto: dict, files: list[str]) -> dict:
    """roles (installed where none exists), then holon_run._rules with route C (the composed route's typed part)."""
    from holon.eval import holon_run as H
    M = proto["milestone"]
    stages: dict = {}
    rels = [f"{rel}/facts/{f}" for f in files]
    stages["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents", ",".join(rels),
                                        "--out-dir", str(S / rel / "sidecars" / "roles"), "--mode", "static",
                                        "--install", "--roles", "hand"])
    lib = S / "spec" / M / "lib"
    H._rules(R, S, rel, M, proto, [{"file": f} for f in files], stages, lambda: H._route_c(R, S, M, lib, stages))
    return stages


# ----------------------------------------------------------------------------------------------- fixtures
class _Go(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i112-go-"))
        p = run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(FIX / "go_config.json"),
                       "--src", str(GOSRC), "--out-dir", str(cls.tmp / "docs")])
        if p.returncode != 0:
            raise AssertionError(p.stderr[-3000:])
        cls.docs = {json.loads(x.read_text(encoding="utf-8"))["contract"].rsplit(".", 1)[-1]: x
                    for x in sorted((cls.tmp / "docs").glob("*.extracted.json"))}
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self, names: tuple, proto_name: str = PROTO, section_errors: bool = True):
        k = (names, proto_name, section_errors)
        if k not in self.runs:
            t = self.tmp / f"run{len(self.runs)}"
            t.mkdir()
            proto = protocol(proto_name)
            if not section_errors:
                proto["disch"].pop("section_errors", None)
            S, rel, R = scratch(t, proto, GOSRC)
            for n in names:
                shutil.copy(self.docs[n], S / rel / "facts" / self.docs[n].name)
            st = typed_part(S, rel, R, proto, [self.docs[n].name for n in names])
            self.runs[k] = (st, S, rel, proto["milestone"])
        return self.runs[k]


class _Sol(unittest.TestCase):
    """The Solidity contracts of tests_m6/fixtures/i112/sol, extracted by the pinned solc 0.8.24 inside the scratch root
    (the frontend reads a clean git checkout: the fixture, committed in scratch); Layout is planted from LayoutKept's
    document by tools/i112_fixture.py."""
    CONTRACTS = ("Counter", "Packed", "PackedKept", "LayoutKept")

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i112-sol-"))
        cls.src = cls.tmp / "src"
        shutil.copytree(SOL, cls.src)
        cls.head = _gitify(cls.src)
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def extract(self, S: Path, rel: str, R, names: tuple) -> list[str]:
        files = []
        for n in names:
            base = "LayoutKept" if n == "Layout" else n
            side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I112 planted fixture",
                    "target": {"repo": "holon/i112", "commit": self.head, "scope": f"contract {base}"},
                    "output": f"{rel}/facts/{base}.extracted.json", "sources": ["Fixture.sol"],
                    "compiler": {"version": "0.8.24", "settings": {"optimizer": {"enabled": False}}},
                    "transitions": {"commit_interfaces": [], "contract": base}}
            sp = S / rel / "sidecars" / f"extract_{base}.json"
            sp.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
            out = S / rel / "facts" / f"{base}.extracted.json"
            r = R.holon("extract", ["extract", "solidity", "--root", str(S), "--sidecar", str(sp), "--source",
                                    str(self.src), "--out", str(out)])
            if r["status"] != "ok":
                raise AssertionError(r["detail"][-2000:])
            if n == "Layout":
                p = subprocess.run([sys.executable, str(ROOT / "tools" / "i112_fixture.py"), "layout", str(out),
                                    str(S / rel / "facts" / "Layout.extracted.json")], capture_output=True, text=True)
                if p.returncode != 0:
                    raise AssertionError(p.stderr[-2000:])
                out.unlink()
                files.append("Layout.extracted.json")
            else:
                files.append(out.name)
        return files

    def run_of(self, names: tuple, classes: bool = True):
        k = (names, classes)
        if k not in self.runs:
            t = self.tmp / f"run{len(self.runs)}"
            t.mkdir()
            proto = protocol(PROTO)
            if not classes:
                proto["typed"].pop("types_opaque_classes", None)
            S, rel, R = scratch(t, proto, self.src)
            files = self.extract(S, rel, R, names)
            st = typed_part(S, rel, R, proto, files)
            self.runs[k] = (st, S, rel, proto["milestone"])
        return self.runs[k]

    def opaque(self, S: Path, M: str) -> dict:
        op = json.loads((S / "gen" / M / "sorts" / "opaque.json").read_text(encoding="utf-8"))
        return {x["model"]: x for x in op["documents"]}

    def no_decision_over(self, S: Path, M: str, doc: str):
        self.assertEqual([k for k, f in law_facts(S, M).items() if f and f.endswith(doc)], [])
        self.assertEqual([k for k, (v, f) in verdicts(S, M).items() if f and f.endswith(doc)], [])

    def three_shapes(self, bad: str, kept: str, cls: str):
        # refused under I111's classes (the milestone), opaque with its class under the widened ones
        st0, *_ = self.run_of((bad,), classes=False)
        self.assertNotEqual(st0["types"]["status"], "ok")
        st, S, _rel, M = self.run_of((bad,))
        self.assertEqual(st["types"]["status"], "ok", st["types"]["detail"][-2000:])
        (m,) = self.opaque(S, M).values()
        self.assertEqual(m["class"], cls)
        self.assertTrue(m["term"] and m["reason"])
        # alone: no law over it
        self.no_decision_over(S, M, f"{bad}.extracted.json")
        self.assertEqual(law_facts(S, M), {})
        # cross-document: the typed neighbour's laws byte-identical and its records as alone
        _a, A, _r, _M = self.run_of(("Counter",))
        stb, B, _r, _M = self.run_of(("Counter", bad))
        self.assertEqual(stb["types"]["status"], "ok", stb["types"]["detail"][-2000:])
        self.no_decision_over(B, M, f"{bad}.extracted.json")
        la = sorted(p.name for p in (A / "laws" / M).glob("L*.json"))
        self.assertTrue(la)
        self.assertEqual(la, sorted(p.name for p in (B / "laws" / M).glob("L*.json")))
        for n in la:
            self.assertEqual((A / "laws" / M / n).read_bytes(), (B / "laws" / M / n).read_bytes(), n)
            ra, rb = (A / "results" / M / n), (B / "results" / M / n)
            self.assertEqual(ra.is_file(), rb.is_file(), n)
            if ra.is_file():
                self.assertEqual(unseconds(json.loads(ra.read_text())), unseconds(json.loads(rb.read_text())), n)
        # constrained state: the control decides what the opaque document leaves UNKNOWN
        stk, K, _r, _M = self.run_of((kept,))
        self.assertEqual(stk["types"]["status"], "ok", stk["types"]["detail"][-2000:])
        v = [x for x, _f in verdicts(K, M).values()]
        self.assertTrue(any(x in ("PROVED", "REFUTED") for x in v), v)


# ----------------------------------------------------------------------------------------------- (1) routing
class TestRouting(unittest.TestCase):
    """P1: holon_run.route, unit level."""
    DER = {"laws": [
        {"law_id": "L_a", "rule": "DISCH", "subform": "revert"},
        {"law_id": "L_b", "rule": "FACT", "subform": "public_input_x"},
        {"law_id": "L_c", "rule": "SORT", "subform": "realize"},
        {"law_id": "L_d", "rule": "UNDO", "subform": "undo"},
        {"law_id": "L_e", "rule": "SYM", "subform": "sym"},
        {"law_id": "L_f", "rule": "PAR", "subform": "totality"},
        {"law_id": "L_g", "rule": "PAR", "subform": "domain_coherence"},
    ]}

    def test_p1_groups(self):
        from holon.eval import holon_run as H
        g = H.route(self.DER, [e["law_id"] for e in self.DER["laws"]])
        self.assertEqual(g, {"disch": ["L_a"], "fact": ["L_b"], "typed": ["L_c", "L_d", "L_e"],
                             "milestone": ["L_f", "L_g"]})
        self.assertEqual(list(g), list(H.RUNNERS))

    def test_p1_arguments(self):
        from holon.eval import holon_run as H
        proto = protocol(PROTO)
        a = H.runner_args("milestone", proto, "ts", "ds", "fs")
        for x in ("--sidecar", "--disch", "--fact-sidecar", "--section-errors"):
            self.assertNotIn(x, a)
        self.assertEqual(H.runner_args("disch", proto, "ts", "ds", "fs"),
                         ["--sidecar", "ts", "--disch", "ds", "--section-errors", "unknown"])
        self.assertEqual(H.runner_args("fact", proto, "ts", "ds", "fs"), ["--sidecar", "ts", "--fact-sidecar", "fs"])
        self.assertEqual(H.runner_args("typed", proto, "ts", "ds", "fs"), ["--sidecar", "ts"])
        proto["disch"].pop("section_errors")
        self.assertEqual(H.runner_args("disch", proto, "ts", "ds", "fs"), ["--sidecar", "ts", "--disch", "ds"])

    def test_p1_earlier_protocols_unrouted(self):
        for n in sorted((ROOT / "spec").glob("M[4-6]/lib/i*_run.json")):
            if n.name == "i112_run.json":
                continue
            d = json.loads(n.read_text(encoding="utf-8"))
            self.assertNotIn("run_routing", d, n.name)
            self.assertNotIn("section_errors", d.get("disch") or {}, n.name)
            self.assertNotIn("preflight", d, n.name)


class TestRoutingPlanted(_Go):
    """P2: on I111's planted milestone shape (Ledger alone here), the per-runner route decides as the two-call route."""

    def test_p2_same_verdicts(self):
        st, S, _rel, M = self.run_of(("Ledger",))
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        laws = law_facts(S, M)
        self.assertTrue(laws)
        self.assertEqual(sorted(verdicts(S, M)), sorted(laws))
        self.assertIsNone(LAW_ID.search(st["run"]["detail"]), st["run"]["detail"])
        st0, S0, _rel, _M = self.run_of(("Ledger",), proto_name=PROTO_I111)
        self.assertEqual({k: v for k, (v, _f) in verdicts(S0, M).items()},
                         {k: v for k, (v, _f) in verdicts(S, M).items()})


class TestSectionErrors(_Go):
    """P3: a planted DISCH section error makes that section's laws UNKNOWN; every other section runs."""

    def test_p3_fixture_shape(self):
        self.assertEqual(sorted(self.docs), ["Gated", "Ledger"])

    def test_p3_section_error_unknown(self):
        _a, A, _rel, M = self.run_of(("Ledger",))
        st, B, _rel, _M = self.run_of(("Ledger", "Gated"))
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        facts = law_facts(B, M)
        gated = sorted(k for k, f in facts.items() if f and f.endswith("bank.Gated.extracted.json"))
        self.assertTrue(gated)
        for k in gated:
            r = json.loads((B / "results" / M / f"{k}.json").read_text(encoding="utf-8"))
            if r.get("rule") != "DISCH":
                continue
            self.assertEqual(r["status"], "UNKNOWN", k)
            self.assertEqual([a["kind"] for a in r["attempts"]], ["section"], k)
            self.assertIn("reads more of the context than storage and time", r["attempts"][0]["error"])
            self.assertIn("DISCH section", r["bound"])
            self.assertNotIn("witness", r)
        self.assertTrue(any(json.loads((B / "results" / M / f"{k}.json").read_text()).get("rule") == "DISCH"
                            for k in gated))
        for n in sorted(k for k, f in law_facts(A, M).items()):
            ra = json.loads((A / "results" / M / f"{n}.json").read_text(encoding="utf-8"))
            rb = json.loads((B / "results" / M / f"{n}.json").read_text(encoding="utf-8"))
            self.assertEqual(unseconds(ra), unseconds(rb), n)
        self.assertIn('"section_errors": 1', st["run"]["detail"])

    def test_p3_without_the_option_refused_as_before(self):
        st, B, _rel, M = self.run_of(("Ledger", "Gated"), section_errors=False)
        self.assertNotEqual(st["run"]["status"], "ok")
        disch = [k for k, f in law_facts(B, M).items()
                 if json.loads((B / "laws" / M / f"{k}.json").read_text()).get("rule") == "DISCH"]
        self.assertTrue(disch)
        self.assertEqual([k for k in disch if (B / "results" / M / f"{k}.json").is_file()], [])


# ----------------------------------------------------------------------------------------------- (2) O1 widened
class TestUnsupportedClass(_Sol):
    """P4: class unsupported, three shapes."""

    def test_p4_three_shapes(self):
        self.three_shapes("Packed", "PackedKept", "unsupported")


class TestMemberLayoutClass(_Sol):
    """P5: class member_layout, three shapes."""

    def test_p5_three_shapes(self):
        self.three_shapes("Layout", "LayoutKept", "member_layout")


class TestMilestoneWide(_Sol):
    """P6: a milestone-wide input error stays a refusal; the key's values; I111's bytes without the key."""

    def test_p6_family_slot_error_refuses(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i112-slot-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        proto = protocol(PROTO)
        S, rel, R = scratch(tmp, proto, self.src)
        (f,) = self.extract(S, rel, R, ("LayoutKept",))
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "i112_fixture.py"), "slot", str(S / rel / "facts" / f),
                            str(S / rel / "facts" / "Slot.extracted.json")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        (S / rel / "facts" / f).unlink()
        st = typed_part(S, rel, R, proto, ["Slot.extracted.json"])
        self.assertEqual(st["types"]["status"], "failed")
        self.assertEqual(st["types"]["exit"], 1)
        self.assertFalse((S / "gen" / proto["milestone"] / "sorts" / "types.json").exists())

    def test_p6_values_refused(self):
        from holon.sorts import opaque
        with self.assertRaises(ValueError):
            opaque.classes({"types_fallback": "opaque", "types_opaque_classes": ["gen_error", "anything"]})
        with self.assertRaises(ValueError):
            opaque.classes({"types_opaque_classes": ["gen_error"]})
        with self.assertRaises(ValueError):
            opaque.classes({"types_fallback": "opaque", "types_opaque_classes": []})
        self.assertEqual(opaque.classes({"types_fallback": "opaque"}), ("gen_error",))
        self.assertEqual(opaque.classes({}), ())

    def test_p6_class_of(self):
        from holon import extracted_eval, machine
        from holon.sorts import model3, opaque
        self.assertEqual(opaque.class_of(model3.GenError("x")), "gen_error")
        self.assertEqual(opaque.class_of(machine.MemberLayoutError("x")), "member_layout")
        self.assertEqual(opaque.class_of(extracted_eval.Unsupported("x")), "unsupported")
        self.assertIsNone(opaque.class_of(machine.ModelError("x")))
        self.assertIsNone(opaque.class_of(ValueError("x")))


# ----------------------------------------------------------------------------------------------- (3), (4)
class TestWithholdPreflight(unittest.TestCase):
    """P7."""

    def test_p7_withhold_gen_and_details(self):
        from holon.eval import holon_run as H
        tmp = Path(tempfile.mkdtemp(prefix="holon-i112-wh-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        e = tmp / "c99"
        (e / "laws").mkdir(parents=True)
        (e / "records").mkdir()
        (e / "gen" / "laws" / "L_x_1").mkdir(parents=True)
        (e / "laws" / "L_x_1.json").write_text("{}")
        (e / "records" / "L_x_1.json").write_text('{"status": "PROVED"}')
        (e / "gen" / "laws" / "L_x_1" / "LAWS.bend").write_text("law l_x_1\n")
        (e / "gen" / "disch.txt").write_text("names L_x_1 here")
        (e / "gen" / "kept.txt").write_text("nothing per law")
        row = {"id": "c99", "laws": [{"law_id": "L_x_1", "rule": "DISCH", "subform": "revert", "status": "PROVED"}],
               "stages": {"run": {"status": "failed", "detail": "L_x_1: refused"}}}
        H.withhold(row, e)
        self.assertEqual(sorted(p.relative_to(e).as_posix() for p in e.rglob("*") if p.is_file()),
                         ["gen/kept.txt", "gen_withheld.json"])
        gw = json.loads((e / "gen_withheld.json").read_text())
        self.assertEqual(gw["files"], 2)
        self.assertEqual(len(gw["sha256"]), 64)
        self.assertNotIn("L_x_1", json.dumps(row))
        self.assertIn("<law id withheld>", row["stages"]["run"]["detail"])

    def _sets(self, tmp: Path, good: bool = True, go_line: str | None = None) -> Path:
        import hashlib
        d = tmp / "solc-set"
        d.mkdir()
        rel = {}
        for v in ("0.8.1", "0.8.2"):
            b = f"solc {v}".encode()
            (d / f"solc-{v}").write_bytes(b)
            rel[v] = hashlib.sha256(b).hexdigest()
        if not good:
            rel["0.8.2"] = "0" * 64
        gr = tmp / "go1"
        (gr / "bin").mkdir(parents=True)
        (gr / "bin" / "go").write_text("#!/bin/sh\necho 'go version go9.9.9 linux/amd64'\n")
        (gr / "bin" / "go").chmod(0o755)
        cfg = {"solc_set": {"dir": str(d), "releases": rel},
               "go_set": {"releases": {"9.9.9": {"goroot": str(gr),
                                                 "version_line": go_line or "go version go9.9.9 linux/amd64"}}}}
        p = tmp / "toolchains.json"
        p.write_text(json.dumps(cfg))
        return p

    def test_p7_preflight(self):
        from holon.eval import holon_run as H
        proto = protocol(PROTO)
        for good, line, missing, ok in ((True, None, False, True), (False, None, False, False),
                                        (True, "go version go1.0 linux/amd64", False, False), (True, None, True, False)):
            tmp = Path(tempfile.mkdtemp(prefix="holon-i112-pf-"))
            self.addCleanup(shutil.rmtree, tmp, True)
            p = self._sets(tmp, good, line)
            if missing:
                (tmp / "solc-set" / "solc-0.8.1").unlink()
            r = H.preflight(proto, json.loads(p.read_text()))
            self.assertEqual(r["status"] == "ok", ok, r)
            self.assertEqual(r["solc"]["checked"], 2)
            self.assertEqual(r["go"]["checked"], 1)
        self.assertIsNone(H.preflight(protocol(PROTO_I111), {}))

    def test_p7_preflight_refuses_to_start(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i112-pf2-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        p = self._sets(tmp, good=False)
        out = tmp / "out"
        r = subprocess.run([sys.executable, "-m", "holon", "eval", "holon", "--protocol", PROTO, "--compose",
                            "--entries", "c99", "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                           env={**ENV, "HOLON_TOOLCHAINS": str(p)}, timeout=600)
        self.assertEqual(r.returncode, 2, r.stderr[-2000:])
        self.assertIn("preflight", r.stderr)
        self.assertFalse(out.exists())


# ----------------------------------------------------------------------------------------------- the corpus
class TestCorpusSmoke(unittest.TestCase):
    """P8-P12: smoke measures on I51's 20 entries (contaminated by I51, I103-I111 and I107)."""

    def doc(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I112/holon/corpus.json is missing")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def rows(self) -> dict:
        return {r["id"]: r for r in self.doc()["rows"]}

    def test_p8_stage_reach(self):
        e = pred("I112-P8")["expected"]
        self.assertEqual(self.doc()["preflight"]["status"], "ok")
        reach: dict = {}
        for i, r in self.rows().items():
            self.assertTrue(r.get("compose"), i)
            for s, v in (r.get("stages") or {}).items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(i)
                elif v.get("status") not in ("not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {s} has no reason")
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)

    def test_p9_laws_aggregate(self):
        e = pred("I112-P9")["expected"]
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
        for s in ("sorts", "types"):
            self.assertEqual(sorted(i for i, r in rows.items() if ((r.get("stages") or {}).get(s) or {})
                                    .get("status") == "timeout"), [], s)

    def test_p10_runners(self):
        e = pred("I112-P10")["expected"]
        n = 0
        for i, r in self.rows().items():
            run = (r.get("stages") or {}).get("run") or {}
            self.assertNotIn("unrecognized arguments", run.get("detail") or "", i)
            if run.get("status") in ("ok", "failed") and r.get("run_runners"):
                for k, v in r["run_runners"].items():
                    if k != "disch":
                        self.assertEqual(v.get("section_errors", 0), 0, (i, k))
                if r["run_runners"].get("disch", {}).get("section_errors", 0) > 0:
                    n += 1
        self.assertGreaterEqual(n, e["section_error_entries_at_least"])

    def test_p11_opaque_classes(self):
        e = pred("I112-P11")["expected"]
        by: dict = {}
        for i, r in sorted(self.rows().items()):
            t = r.get("types_opaque")
            if not t:
                continue
            self.assertEqual(t["typed"] + t["opaque"], t["documents"], i)
            for m in t["misses"]:
                self.assertIn(m["class"], ("gen_error", "member_layout", "unsupported"), i)
                by[m["class"]] = by.get(m["class"], 0) + 1
        self.assertGreaterEqual(by.get("gen_error", 0), e["gen_error_at_least"])
        self.assertGreaterEqual(by.get("unsupported", 0), e["unsupported_at_least"])

    def test_p12_nothing_per_law_committed(self):
        base = OUT / "holon"
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if LAW_ID.search(p.relative_to(base).as_posix()):
                hits.append(p.relative_to(base).as_posix())
                continue
            if p.name == "corpus.json":
                rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
                for r in rows:
                    t = json.dumps({k: v for k, v in r.items() if k != "laws_aggregate"})
                    if LAW_ID.search(t):
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
            if r.get("laws_aggregate"):
                self.assertEqual(len(r["laws_bundle_sha256"]), 64, r["id"])


class TestSealedContaminated(unittest.TestCase):
    """P13: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p13_spent_targets(self):
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        t = {x["id"]: x for x in d["targets"]}
        for i, x in t.items():
            self.assertEqual(x["stages"].get("types"), "ok", i)
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, i)
            for k in x.get("laws_aggregate", {}).values():
                self.assertEqual(set(k), {"derived", "decided", "unknown"}, i)
        self.assertNotEqual(t["s2"]["stages"].get("disch"), "ok")


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_p14_morph_record_moves_only_by_restamp(self):
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

    def test_p14_morph_sidecars_name_no_opt_in(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and any(k in d for k in ("types_fallback", "types_opaque_classes", "run_routing",
                                                            "section_errors")):
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_p14_protocol_is_i111s_plus_the_opt_ins(self):
        a = json.loads((ROOT / PROTO_I111).read_text(encoding="utf-8"))
        b = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(b.pop("run_routing"), "per_runner")
        self.assertEqual(b["disch"].pop("section_errors"), "unknown")
        self.assertEqual(b["typed"].pop("types_opaque_classes"), ["gen_error", "member_layout", "unsupported"])
        self.assertEqual(b.pop("preflight"), "toolchain_sets")
        b.pop("preflight_doc")
        for d in (a, b):
            for k in ("doc", "iteration", "out", "typed_doc", "run"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112"):
            self.assertIn(f"name: {job}", wf, job)


if __name__ == "__main__":
    unittest.main()
