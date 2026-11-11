"""I100: rule PAR_record_round_trip: the record law dec(enc(h)) = some(view_N(h)) over an encoder into a byte record
and its getter family, the constant read-back laws, and the back-test's record bridges (the coordinator's I100 brief;
the L7 candidate PAR_record_round_trip of audit/rule_gaps.jsonl, instances RG-M3-01 to RG-M3-03 (F-M3-08) and
RG-M3-06 (F-M3-10); BUILD_PLAN row I100; the key I100 of spec/M3/predictions.json). The instrument is
tests_m3/_i100.py; it imports nothing from holon/ or tools/. The instrument, this docstring and the record map
spec/M3/lib/backtest_record_map.json are fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <B> is the key's base_commit (4fd64a52, the lead after #131), OUT is docs/iterations/I100/, CODEC the
committed linked codec documents gen/M3/codec/*.json; the candidate's basis (its argument and obligations (1)-(5))
is read as written.

F  The gap. At <B> no catalog rule states a whole-record round trip. PAR's round_trip (P1) states one law per E1
   inverse atom; a slot an encoder fills with a constant is no atom (I25's six constant_read elements, no_rule). The
   back-test's exit blockers include gap:M0:L_rt_go_v0, _v1 and _v2: B1's name map gives dec_go and view no image.
   Under round 3's m08 and m06 the derivation drops PROVED round trips and adds no law (F-M3-10).
L  Admission (L7). The rule lands only after `holon audit gaps` admits the candidate: two instances on two findings
   (met at <B>), a basis (met) and the human's signature over the candidate line (not met at <B>). No producer reads
   audit/.
S  The build.
   S1 Catalog holon-rules/1.16: the rules of holon-rules/1.15 unchanged (the same producer objects) plus PAR's
      sub-forms constant_read and record_round_trip (holon.rules.par_record), run by derive's par_record part over a
      target milestone's CODEC (M3 on); catalog_version(M3) is holon-rules/1.16.
   S2 Instances. In a CODEC document D, for each carrier C of kind bytes, each encoder e of D into C with a versions
      list (an encoder without one is listed as unversioned and gives nothing), each N of e's versions and each getter
      family F of C: the decoders of D from C with one source qualifier (the source before its last "."; "(pkg.T)" for
      a Go method "(pkg.T).M"), F named by the qualifier's last identifier (T). F_N: F's members active at N (versions
      null or holding N), in (read offset, read width, name) order; an empty F_N gives no instance.
   S3 Components (obligation 3). From e's layout at N and a member's read range, never from laws: field f when the
      layout places f's bytes 0..w-1 there in order (the E1 inverse atom of rule X7); constant c when every cell there
      is a constant; else none: the member is missing.
   S4 constant_read (obligation 2). For every decoder d of D from C active at N whose read range e's layout at N fills
      with constants c: L_par_rt_<e>_<d>_v<N>, the binder h of e's source record, rule P1's version premise (a record
      with a field version gets version = N), the claim d(e(h)) == some(c).
   S5 record_round_trip (obligation 4). For an instance with no missing member: L_par_rec_<e>_<F>_v<N>, the same
      binder and premises, the claim the conjunction {"all": [...]} of one conjunct per member of F_N in its order:
      d(e(h)) == some(h.f) for a field (P1's claim of that atom) or d(e(h)) == some(c) for a constant (S4's claim).
      Nothing else is added or dropped. An instance with a missing member gives no law: its basis element is an
      obstruction (missing_component) naming each missing member and what its read range holds instead.
      gen/<M>/par_record/basis.json, written by holon derive, lists every instance (members, components, the law or
      the missing members) and every unversioned encoder.
   S6 Deciding a conjunction. holon run decides a conjunction claim of a CODEC law: LAWS.bend states it as an exs
      telescope; the proof class open_refl opens the record binders and gives one reflexivity per conjunct; a
      refutation is the counter-law of the first conjunct that a fill separates on the compiled model, Bend-checked,
      recorded as failing_conjunct (the binding holds one counter-law sha256 per conjunct,
      holon.bindings.counter_binding).
   S7 The record map (obligation 5, B1 amended). spec/M3/lib/backtest_record_map.json is the computation
      tests_m3/_i100.py::record_map_doc: a hand decoder whose getters are a hand projection's order (dec_go, view),
      and each getter slot's component decoder: the one implementing the method the slot's getter code calls first.
      holon backtest reads it beside B1's map and never recomputes it; the derivation never reads it.
   S8 B2 amended (pairing a conjunction). A conjunction claim over one record binder v collapses when each conjunct
      is g(x) == some(t), with one x for all and g a member of the record map's family, at least one g a slot's
      getter; each conjunct of a slot's getter has t the slot's image: v's field that B1's field map takes the slot
      to, or a constant c where the field map takes the slot to no field of v's carrier, which adds the hand premise
      slot = c; conjuncts of the family's other members are dropped (they add on the component's side only). The
      claim becomes decoder(x) == some(projection(v)); the rest is B2 (renaming, alpha-equivalence). X is the matched
      slots in the map's order.
   S9 B3 amended (the record bridges). For a row paired by S8, under the M0 law's binders and pinned premises: the
      decoder's bridge decoder(a) == pack_X(a), a the M0 law's argument of the decoder on the hand model and pack_X
      the matched getters of the component model in X's order (Some of their values when each is Some, else None);
      the projection's bridge projection(h) == tup_X(mv(h)), the matched slots' images at the moved value (its field,
      or the constant). Proof open_refl; else both sides are evaluated on the compiled models at hand fills (zeros,
      ones, counting, 0xff), the pins applied, and the first difference gives a counter-law, REFUTED when Bend accepts
      it; else UNKNOWN. A bridge imports the component model holon run generates from the document (a stale one is
      refused). B4 and B5 are unchanged: acceptance "bridges" when every bridge is PROVED.
   S10 Generated, deterministic and target-agnostic: no law id and no name of a target document in the lines I100
      adds under holon/; the same inputs give the same bytes.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, the instrument imports nothing from holon/ or
   tools/, the record map is its computation, and I100's own commits write no frozen root.
B  The build's checks.
   B0 `holon audit gaps --json` reports PAR_record_round_trip admitted (L). Red until the human's signature lands.
   B1 The catalog: S1.
   B2 holon.rules.par_record over CODEC is _i100.expected (instances, members, components, laws and statements), and
      gen/M3/par_record/basis.json is its document.
   B3 Coverage reads the family: on CODEC with _i100.plant_shift (enc_sol's parentBatchHash written one byte low at
      version 1) the producer obstructs (enc_sol, BatchHeaderBytes, 1), naming BatchHeaderBytes_ParentBatchHash and
      BatchHeaderBytes_SequencerSetVerifyHash, and states neither that record law nor that constant_read law; with
      _i100.plant_guard (BatchHeaderBytes_LastBlockNumber without version 1) it states the version-1 record laws with
      12 conjuncts and obstructs nothing; on each planted document it gives what _i100.expected gives.
   B4 A conjunction decides (S6): each record law's emitted LAWS.bend is its exs telescope, and a copy of
      L_par_rec_enc_sol_BatchHeaderBytes_v1 whose SequencerSetVerifyHash conjunct claims 32 bytes 0x01 is REFUTED by
      holon.gen.linked.decide, failing conjunct that conjunct's index, by a Bend-checked counter-law.
   B5 The back-test: holon.backtest pairs each L_rt_go_vN with L_par_rec_enc_sol_BatchHeaderBytes_vN under the record
      map and no other M0 law with a record law; the table names the record map (path, sha256) under "record_map".
   B6 Target-agnostic: _i100.scan of _i100.added_lines against _i100.target_names finds nothing.
   B7 Deterministic: the par_record part computed twice gives the same documents, byte for byte.
   B8 CI runs this module's TestBuild in a job of its own.
P  The outcomes (OUT written after C_K).
   P1 Obligation (2): six constant_read laws, exactly _i100.expected's: enc_sol's SequencerSetVerifyHash at versions
      0, 1 and 2 (32 zero bytes, premise version = N), and the Version slot of BatchHeaderV0_Bytes (0x00, v0),
      BatchHeaderV1_Bytes (0x01, v1) and BatchCache_createBatchHeaderWithSequencerSetHash (0x02, v2), without premises;
      they are I25's six constant_read elements; each PROVED (open_refl), BendTT's verdict checked, its premises
      inhabited (G11V) where it has any.
   P2 Obligations (3) and (4): six record laws, exactly _i100.expected's, with 12 conjuncts (enc_sol v0,
      BatchHeaderV0_Bytes v0) or 13 (enc_sol v1 and v2, BatchHeaderV1_Bytes v1, BatchCache v2), each PROVED
      (open_refl), BendTT's verdict checked, its premises inhabited where it has any; the basis at HEAD has no
      obstruction.
   P3 Obligation (1): every field conjunct of a record law is the claim, under the same premises, of the round_trip
      law L_par_rt_<e>_<d>_v<N>, PROVED at HEAD and at <B>.
   P4 12 laws added, 0 statuses moved: the M3 registry at HEAD is <B>'s plus the 12 (every <B> hash kept) under
      holon-rules/1.16, and every record of <B> keeps its status (OUT/registry.json, OUT/statuses.json).
   P5 Obligation (5): the back-test pairs L_rt_go_v0, _v1 and _v2 with L_par_rec_enc_sol_BatchHeaderBytes_v0, _v1 and
      _v2, their bridges dec_go, enc_sol and view all PROVED, acceptance bridges; the other five rows are <B>'s; the
      exit blockers go from <B>'s four to [gap:M0:L_par_hdr_v2] (OUT/backtest.json).
   P6-P9 Round 3's mutants on HEAD's tree (OUT/mutations.json, _i100.mutations):
   P6 m08 is caught, obstructed: (enc_sol, BatchHeaderBytes, N) for N = 0, 1 and 2, each missing exactly
      BatchHeaderBytes_ParentBatchHash and BatchHeaderBytes_SequencerSetVerifyHash; no instance dropped.
   P7 m06 is caught, refuted: no obstruction; the mutant's L_par_rec_enc_sol_BatchHeaderBytes_v1 has 12 conjuncts (no
      BatchHeaderBytes_LastBlockNumber); the mutant's back-test pairs L_rt_go_v1 with it, its dec_go and view bridges
      REFUTED and its enc_sol bridge PROVED, and gap:M0:L_rt_go_v1 is an exit blocker.
   P8 m07 is caught, obstructed: (BatchHeaderV1_Bytes, BatchHeaderBytes, 1) and
      (BatchCache_createBatchHeaderWithSequencerSetHash, BatchHeaderBytes, 2), each missing exactly
      BatchHeaderBytes_LastBlockNumber and BatchHeaderBytes_ParentBatchHash; enc_sol's instances are HEAD's.
   P9 m05 is not caught: the block-context functions are in no CODEC document, so the mutant's instances are HEAD's
      and its verdict is not_caught.
"""
from __future__ import annotations

import copy
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

from tests_m3 import _i100 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I100.json"
CODEC = "gen/M3/codec/header_length.json"
SSVH, PBH, LBN = ("BatchHeaderBytes_SequencerSetVerifyHash", "BatchHeaderBytes_ParentBatchHash",
                  "BatchHeaderBytes_LastBlockNumber")
FROZEN = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
          "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _out(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _law(lid: str) -> dict:
    return I.load(ROOT, f"laws/M3/{lid}.json")


def _rec(lid: str) -> dict:
    return I.load(ROOT, f"results/M3/{lid}.json")


def _cj(x) -> str:
    return json.dumps(x, sort_keys=True)


def _build():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _derive(items):
    _build()
    from holon.rules import par_record as PR
    return PR.derive_documents(items)


def _shape(res: dict) -> dict:
    """The producer's result in the instrument's shape."""
    return {"instances": res["instances"], "obstructions": res["obstructions"], "unversioned": res["unversioned"],
            **{s: {lid: x["statement"] for lid, x in res["laws"].items() if x["subform"] == s} for s in I.SUBFORMS}}


def _codec() -> tuple[str, dict, dict]:
    doc = I.load(ROOT, CODEC)
    return CODEC, doc, I.load(ROOT, f"gen/M3/diagram/{doc['component']}.json")


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
        src = (ROOT / "tests_m3" / "_i100.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))

    def test_r3_the_record_map_is_the_computation(self):
        sc = I.load(ROOT, I.RECORD_MAP)
        self.assertEqual({k: v for k, v in sc.items() if k != "doc"}, I.record_map_doc(ROOT))

    def test_r4_own_commits_write_no_frozen_root(self):
        ck = I.git(ROOT, "log", "--diff-filter=A", "--format=%H", "--", "spec/M3/predictions/I100.json").split()[-1]
        for c in I.git(ROOT, "log", "--first-parent", "--no-merges", "--format=%H", f"{ck}^..HEAD").split():
            for f in I.git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n"):
                self.assertFalse(f and f.startswith(FROZEN), f"{c[:8]}: {f}")


class TestAdmission(unittest.TestCase):
    def test_b0_the_audit_admits_the_rule(self):
        r = _holon("audit", "gaps", "--json", timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        v = json.loads(r.stdout)["candidates"].get("PAR_record_round_trip") or {}
        self.assertTrue(v.get("admitted"), v.get("why"))


class TestBuild(unittest.TestCase):
    def test_b1_the_catalog(self):
        _build()
        from holon import rules
        from holon.rules import par_record as PR
        self.assertEqual(rules.catalog_version("M3"), I.CATALOG)
        new, old = rules.CATALOGS[I.CATALOG], rules.CATALOGS[I.PREVIOUS]
        self.assertEqual(sorted(new), sorted(old))
        for r, subs in old.items():
            for s, p in subs.items():
                self.assertIs(new[r][s], p, (r, s))
        self.assertEqual(sorted(set(new["PAR"]) - set(old["PAR"])), sorted(I.SUBFORMS))
        for s in I.SUBFORMS:
            self.assertIs(new["PAR"][s], PR.PRODUCERS[s], s)

    def test_b2_the_producer_is_the_instrument(self):
        got = _shape(_derive([_codec()]))
        self.assertEqual(_cj(got), _cj(I.expected(ROOT)))
        basis = I.load(ROOT, I.BASIS)
        self.assertEqual(_cj({k: basis[k] for k in ("instances", "obstructions", "unversioned")}),
                         _cj({k: got[k] for k in ("instances", "obstructions", "unversioned")}))

    def test_b3_coverage_reads_the_family(self):
        rel, doc, diag = _codec()
        shifted = I.plant_shift(doc, "enc_sol", 1, "parentBatchHash")
        got = _shape(_derive([(rel, shifted, diag)]))
        self.assertEqual(_cj(got), _cj(I.expected(ROOT, [(rel, shifted)])))
        self.assertEqual([(o["encoder"], o["family"], o["version"], sorted(o["getters"])) for o in got["obstructions"]],
                         [("enc_sol", "BatchHeaderBytes", 1, sorted([PBH, SSVH]))])
        self.assertNotIn("L_par_rec_enc_sol_BatchHeaderBytes_v1", got["record_round_trip"])
        self.assertNotIn("L_par_rt_enc_sol_BatchHeaderBytes_SequencerSetVerifyHash_v1", got["constant_read"])
        guarded = I.plant_guard(doc, LBN, 1)
        got = _shape(_derive([(rel, guarded, diag)]))
        self.assertEqual(_cj(got), _cj(I.expected(ROOT, [(rel, guarded)])))
        self.assertEqual(got["obstructions"], [])
        self.assertEqual({k: len(v["claim"]["all"]) for k, v in got["record_round_trip"].items() if k.endswith("_v1")},
                         {"L_par_rec_enc_sol_BatchHeaderBytes_v1": 12,
                          "L_par_rec_BatchHeaderV1_Bytes_BatchHeaderBytes_v1": 12})

    def test_b4_a_conjunction_decides(self):
        _build()
        from holon import bend
        from holon.gen import linked as GL
        from holon.mpipeline import accepted, write_pair
        raw = (ROOT / CODEC).read_bytes()
        doc, sha = json.loads(raw), hashlib.sha256(raw).hexdigest()
        for lid in sorted(_th()["record_laws"]):
            law = _law(lid)
            text = GL.emit(law, doc, "../../model/x.bend").text
            n = len(law["statement"]["claim"]["all"])
            self.assertEqual(len(re.findall(r"(?m)^  exs c\d+: \{", text)), n - 1, lid)
        law = copy.deepcopy(_law("L_par_rec_enc_sol_BatchHeaderBytes_v1"))
        conj = law["statement"]["claim"]["all"]
        i = next(k for k, c in enumerate(conj) if c["eq"][0]["call"] == SSVH)
        conj[i]["eq"][1] = {"some": {"bytes": "0x" + "01" * 32}}
        law["law_id"] += "_planted"
        tmp = Path(tempfile.mkdtemp(prefix="i100-b4-"))
        try:
            cfg = bend.config()
            (tmp / "model").mkdir()
            (tmp / "model" / f"{doc['role']}.bend").write_text(GL.generate(doc, sha))
            cm = GL.CompiledModel.build(doc, sha, doc["role"], cfg)
            imp = f"../../model/{doc['role']}.bend"
            d = GL.decide(law, cm, tmp / "laws" / law["law_id"], tmp / "proofs" / law["law_id"], imp, imp, cfg,
                          "planted", write_pair, accepted)
            self.assertEqual((d.status, d.conjunct), ("REFUTED", i), d.attempts)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_b5_the_backtest_pairs_by_the_record_map(self):
        _build()
        from holon import backtest as BT
        mu = BT.name_map("M3", ROOT)
        m0 = {p.stem: json.loads(p.read_text(encoding="utf-8"))
              for p in sorted((ROOT / "laws" / "M0").glob("L_*.json"))}
        recs = {lid: _law(lid) for lid in _th()["record_laws"]}
        pairs = sorted((o, n) for o, ol in m0.items() for n, nl in recs.items() if BT.paired(ol, nl, mu))
        self.assertEqual(pairs, [(f"L_rt_go_v{v}", f"L_par_rec_enc_sol_BatchHeaderBytes_v{v}") for v in (0, 1, 2)])
        self.assertEqual(I.load(ROOT, I.BACKTEST)["record_map"], {"path": I.RECORD_MAP, "sha256": _sha(I.RECORD_MAP)})

    def test_b6_target_agnostic(self):
        """B6. (Amended, spec/M3/amendments/I100.jsonl: _i100.added_lines diffs the base against HEAD, so any later
        key's lines under holon/ counted as I100's. The lines I100 adds are now the diff from the base to R, the
        oldest commit of HEAD's history that adds docs/iterations/I100.md (I100's report), scanned by _i100.scan
        against _i100.target_names as before.)"""
        added = I.git(ROOT, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                      "docs/iterations/I100.md").split()
        self.assertTrue(added, "docs/iterations/I100.md is added by no commit of HEAD's history")
        out, cur = [], None
        for ln in I.git(ROOT, "diff", "-U0", f"{I.BASE}..{added[0]}", "--", "holon/").splitlines():
            if ln.startswith("+++ "):
                cur = ln[6:] if ln.startswith("+++ b/") else None
            elif ln.startswith("+") and cur:
                out.append((cur, ln[1:]))
        self.assertTrue(out, "I100 adds no line under holon/ before its report")
        self.assertEqual(I.scan(out, I.target_names(ROOT)), [])

    def test_b7_deterministic(self):
        _build()
        from holon import rules
        a, b = (rules._par_record_part("M3", ROOT, I.CATALOG, 2) for _ in range(2))
        self.assertEqual(rules.dumps(a["basis"]), rules.dumps(b["basis"]))
        self.assertEqual(rules.dumps(a["laws"]), rules.dumps(b["laws"]))
        self.assertEqual(rules.dumps(a["basis"]), (ROOT / I.BASIS).read_text(encoding="utf-8"))
        for lid, law in a["laws"].items():
            self.assertEqual(rules.dumps(law), (ROOT / "laws" / "M3" / f"{lid}.json").read_text(encoding="utf-8"), lid)

    def test_b8_ci_runs_this_module(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests_m3.test_par_record_i100.TestBuild", wf)


class TestOutcome(unittest.TestCase):
    def test_p1_the_constant_read_back_laws(self):
        x = I.expected(ROOT)
        self.assertEqual(sorted(x["constant_read"]), sorted(_th()["constant_read_laws"]))
        lossy = I.load(ROOT, "gen/M3/par_lossy/header_length.json")
        els = sorted((e["p"].split(".", 1)[1], e["q"].split(".", 1)[1], e["version"], e["bytes"])
                     for e in lossy["elements"] if e["kind"] == "constant_read")
        mine = []
        for lid, st in sorted(x["constant_read"].items()):
            lhs, rhs = st["claim"]["eq"]
            mine.append((lhs["args"][0]["call"], lhs["call"], int(lid.rsplit("_v", 1)[1]), rhs["some"]["bytes"]))
            law, r = _law(lid), _rec(lid)
            self.assertEqual((law["rule"], law["subform"], law["rule_catalog_version"]),
                             ("PAR", "constant_read", I.CATALOG))
            self.assertEqual(_cj(law["statement"]), _cj(st), lid)
            self.assertEqual((r["status"], r["kernel"]["verdict"]), ("PROVED", "checked"), lid)
            self.assertIn("open_refl", [a.get("generator") for a in r["attempts"]], lid)
            self.assertEqual(r["non_vacuity"]["status"], "inhabited" if st["assume"] else "no_premises", lid)
        self.assertEqual(sorted(mine), els)

    def test_p2_the_record_laws(self):
        x = I.expected(ROOT)
        want = _th()["record_laws"]
        self.assertEqual(sorted(x["record_round_trip"]), sorted(want))
        for lid, st in sorted(x["record_round_trip"].items()):
            law, r = _law(lid), _rec(lid)
            self.assertEqual((law["rule"], law["subform"]), ("PAR", "record_round_trip"), lid)
            self.assertEqual(_cj(law["statement"]), _cj(st), lid)
            self.assertEqual(len(st["claim"]["all"]), want[lid], lid)
            self.assertEqual((r["status"], r["kernel"]["verdict"]), ("PROVED", "checked"), lid)
            self.assertIn("open_refl", [a.get("generator") for a in r["attempts"]], lid)
            self.assertEqual(r["non_vacuity"]["status"], "inhabited" if st["assume"] else "no_premises", lid)
        self.assertEqual(I.load(ROOT, I.BASIS)["obstructions"], [])

    def test_p3_the_field_conjuncts_are_the_round_trips(self):
        for lid, st in sorted(I.expected(ROOT)["record_round_trip"].items()):
            v = int(lid.rsplit("_v", 1)[1])
            for c in st["claim"]["all"]:
                lhs, rhs = c["eq"]
                if "field" not in rhs["some"]:
                    continue
                rt = f"L_par_rt_{lhs['args'][0]['call']}_{lhs['call']}_v{v}"
                with self.subTest(law=lid, round_trip=rt):
                    law = _law(rt)
                    self.assertEqual(law["subform"], "round_trip")
                    self.assertEqual(_cj(law["statement"]["claim"]), _cj(c))
                    self.assertEqual(_cj(law["statement"]["assume"]), _cj(st["assume"]))
                    self.assertEqual(_rec(rt)["status"], "PROVED")
                    self.assertEqual((I.at(ROOT, I.BASE, f"results/M3/{rt}.json") or {}).get("status"), "PROVED")

    def test_p4_twelve_laws_added_none_moved(self):
        reg, st = _out("registry.json"), _out("statuses.json")
        new = sorted(_th()["constant_read_laws"]) + sorted(_th()["record_laws"])
        self.assertEqual(reg["head"]["rule_catalog_version"], I.CATALOG)
        self.assertEqual(sorted(set(reg["head"]["statements"]) - set(reg["base"]["statements"])), sorted(new))
        self.assertEqual({k: reg["head"]["statements"].get(k) for k in reg["base"]["statements"]},
                         reg["base"]["statements"])
        self.assertEqual({k: st["head"].get(k) for k in st["base"]}, st["base"])
        self.assertEqual(sorted(set(st["head"]) - set(st["base"])), sorted(new))
        live = I.load(ROOT, "laws/M3/REGISTRY.json")
        self.assertEqual((live["rule_catalog_version"], live["statements"]),
                         (reg["head"]["rule_catalog_version"], reg["head"]["statements"]))

    def test_p5_the_backtest(self):
        bt = _out("backtest.json")
        th = _th()
        self.assertEqual(bt["before"]["exit_blockers"], th["exit_blockers_before"])
        self.assertEqual(bt["after"]["exit_blockers"], th["exit_blockers_after"])
        for v, old in enumerate(I.ROWS):
            self.assertEqual(bt["after"]["rows"][old],
                             {"new": f"L_par_rec_enc_sol_BatchHeaderBytes_v{v}", "acceptance": "bridges",
                              "implication": "accepted", "gap": None,
                              "bridges": [["dec_go", "PROVED"], ["enc_sol", "PROVED"], ["view", "PROVED"]]}, old)
        for old, row in bt["before"]["rows"].items():
            if old not in I.ROWS:
                self.assertEqual(bt["after"]["rows"][old], row, old)
        self.assertEqual(I._table(I.load(ROOT, I.BACKTEST)), bt["after"])

    def _m(self, mid: str) -> dict:
        m = _out("mutations.json")["mutants"][mid]
        self.assertEqual(m["spec_sha256"], _sha(I.SPEC.format(mid)))
        return m

    def test_p6_m08_obstructed(self):
        m = self._m("m08")
        self.assertIn("obstructed", m["verdict"])
        self.assertTrue(m["caught"])
        self.assertEqual(m["obstructed"], [f"enc_sol|BatchHeaderBytes|v{v}" for v in (0, 1, 2)])
        for v in (0, 1, 2):
            self.assertEqual(m["instances"][f"enc_sol|BatchHeaderBytes|v{v}"]["missing"], sorted([PBH, SSVH]))
        self.assertEqual(m["dropped"], [])

    def test_p7_m06_refuted(self):
        m = self._m("m06")
        self.assertIn("refuted", m["verdict"])
        self.assertTrue(m["caught"])
        self.assertEqual(m["obstructed"], [])
        x = m["instances"]["enc_sol|BatchHeaderBytes|v1"]
        self.assertEqual((x["law"], x["conjuncts"]), ("L_par_rec_enc_sol_BatchHeaderBytes_v1", 12))
        row = m["backtest"]["rows"]["L_rt_go_v1"]
        self.assertEqual((row["new"], row["bridges"]), ("L_par_rec_enc_sol_BatchHeaderBytes_v1",
                                                        [["dec_go", "REFUTED"], ["enc_sol", "PROVED"],
                                                         ["view", "REFUTED"]]))
        self.assertIn("gap:M0:L_rt_go_v1", m["backtest"]["exit_blockers"])

    def test_p8_m07_obstructed(self):
        m = self._m("m07")
        self.assertIn("obstructed", m["verdict"])
        self.assertTrue(m["caught"])
        self.assertEqual(m["obstructed"], ["BatchCache_createBatchHeaderWithSequencerSetHash|BatchHeaderBytes|v2",
                                           "BatchHeaderV1_Bytes|BatchHeaderBytes|v1"])
        for k in m["obstructed"]:
            self.assertEqual(m["instances"][k]["missing"], sorted([LBN, PBH]), k)
        self.assertFalse([k for k in m["changed"] if k.startswith("enc_sol|")])

    def test_p9_m05_not_caught(self):
        m = self._m("m05")
        self.assertEqual(m["verdict"], ["not_caught"])
        self.assertFalse(m["caught"])
        self.assertEqual((m["changed"], m["obstructed"], m["dropped"]), ([], [], []))


class TestRound6(unittest.TestCase):
    """I100-P10, added by a scope_amendment (spec/M3/amendments/I100.jsonl) after the prereg and before any build
    result: the lead's round-6 triage files F-M3-22 as a duplicate of F-M3-10, and its mutant go_getter_batchindex
    (round 6's A1 spec; Go BatchHeaderBytes.BatchIndex reads b[2:10] for b[1:9]) joins round 3's m05-m08. Predicted:
    caught, obstructed. The getter's read range moves to bytes 2..9, which every encoder's layout fills with
    BatchIndex's bytes 1..7 and L1MessagePopped's byte 0, neither one field in order nor constants; so each of the six
    instances (enc_sol at versions 0, 1 and 2, BatchHeaderV0_Bytes v0, BatchHeaderV1_Bytes v1,
    BatchCache_createBatchHeaderWithSequencerSetHash v2) is an obstruction missing exactly BatchHeaderBytes_BatchIndex;
    no instance is dropped and no record law is stated. The record is OUT/mutations_round6.json
    (tests_m3/_i100r6.py)."""

    def test_p10_go_getter_batchindex_obstructed(self):
        from tests_m3 import _i100r6 as R6
        m = _out(R6.OUT_NAME)["mutants"][R6.MUTANT]
        self.assertEqual((m["source_commit"], m["mutant_sha256"]), (R6.SOURCE_COMMIT, R6.MUTANT_SHA256))
        self.assertEqual(m["verdict"], ["obstructed"])
        self.assertTrue(m["caught"])
        want = sorted(["enc_sol|BatchHeaderBytes|v0", "enc_sol|BatchHeaderBytes|v1", "enc_sol|BatchHeaderBytes|v2",
                       "BatchHeaderV0_Bytes|BatchHeaderBytes|v0", "BatchHeaderV1_Bytes|BatchHeaderBytes|v1",
                       "BatchCache_createBatchHeaderWithSequencerSetHash|BatchHeaderBytes|v2"])
        self.assertEqual(m["obstructed"], want)
        for k in want:
            self.assertEqual((m["instances"][k]["missing"], m["instances"][k]["law"]),
                             (["BatchHeaderBytes_BatchIndex"], None), k)
        self.assertEqual(m["dropped"], [])


if __name__ == "__main__":
    unittest.main()
