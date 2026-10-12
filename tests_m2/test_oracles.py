"""I12: hashes and oracles as parameters (whitepaper §8.3 HASH and oracle rows, §8.5, Thm 6.15, Cor 6.16;
BUILD_PLAN I12).

M2+ models (every milestone except M0 and M1) take hash functions and oracles as parameters, with CF and
hypothesis premises in the frozen statements; agg survives only as the concrete instance the refuter and the
inhabitants use. No M2 law exists yet, so the run-level checks use fixture milestone T12 over a toy machine
(tests_m2/fixtures/oracles/): `commit(x)` stores agg([x]); `post(x)` stores dec(x + PAD), PAD = 8. Each
fixture law carries its expected status in `predicted`, fixed at the prereg.

Background (docs/iterations/I7.md, Surprises): a Bend function value is Type, never Data, so a binder of
function type can be erased or affine but never reusable, and a model that applies h more than once cannot
take h as a plain function argument. The encoding is the implementer's choice (a function parameter where
Bend allows it, or the plan's fallback: an opaque oracle table, with CF over it). These tests read only
statuses, records, the checker's verdicts and the BendTT kernel forms, never the encoding.

API and file formats these tests read
-------------------------------------
Oracle sidecar, holon-oracles/0.1. The oracle records of a facts file F live in F/../../lib/oracles.json,
next to its target libraries: spec/M2/facts/*.json -> spec/M2/lib/oracles.json, and the fixture
tests_m2/fixtures/oracles/facts/toy_oracle.facts.json -> tests_m2/fixtures/oracles/lib/oracles.json. It
changes no facts hash. M0 and M1 never read one.
  {"oracles_version": "holon-oracles/0.1", "doc": str, "oracles": [entry, ...]}
  entry = {"id": str, unique;
           "oracle": str, the canonical oracle name (variants of one oracle share it);
           "parameter": {"name": ident, "type": "Fn<A,B>" (required when modelled)};
           "hypothesis": {"id": str matching ^[A-Za-z0-9][A-Za-z0-9-]*$, unique over the file; "doc": str;
                          "kind": "cf" | "hyp" (required when modelled);
                          "family": str (optional; hypothesis variants share a family; default: the id);
                          "predicate": [premise, ...] (kind hyp: required, non-empty)};
           "instance": {"bend": holon-lib/0.1 builtin template ($0 is the argument, ${param:NAME:DEFAULT} a
                        facts parameter), "doc": str} | null (null only when not_in_scope);
           "status": "modelled" | "not_in_scope";
           "reason": non-empty str (required when not_in_scope);
           "ledger": [ids of the M1 ledger stand-ins (spec/ledger/assumptions.json) the entry generalises]}
  kind cf : the hypothesis CF(p, S) for every finite S. A law states its own S as the IR premise
            {"cf": {"fn": p, "set": [terms]}} over a Fn binder named p.
  kind hyp: the conjunction of `predicate`, ground IR 0.3 premises (eq, neq, or cf over a finite set) whose
            terms are built only from nat, bool, nats, {"app": p, "args": [..]} with p the entry's own parameter,
            and the IR builtins eq_nat, eq_bool, eq_nats. A law states it as {"hyp": {"name": <hypothesis id>}}
            over a Fn binder named p.
  A cf over "*" anywhere (global injectivity) is rejected (G3, whitepaper L13).

Parameters. For M2+ milestones a facts call ["call", p, ..] to the parameter p of a modelled entry applies
the model's oracle parameter p, never a builtin, and the model threads its parameters through step and run.
A Fn<A,B> binder of a law named p is parameter p: every run/step/obs/obsv term of the statement is
evaluated with p bound to it. (Every fixture law binds both parameters, agg and dec.) A Fn binder whose name
is no modelled parameter of the facts' sidecar keeps its I7 meaning (L3_cf in tests_m2/test_ir03.py). A
refutation or inhabitant witness that takes an entry's concrete instance is recorded as
{"instance": <entry id>}. The refuter's candidates for a parameter include the instances of its entries; a
counter-law carries the law's hypothesis premises as `exs hN: {X}` lines (as M1 counter-laws carry theirs), so
its witness satisfies them. A sidecar instance that violates its hypothesis does not stop a run: the
inhabitant or counter-law that would use it does not check.

Law files. A law's emitted LAWS.bend imports Base and exactly one model module, as M (as today), so that
holon.bindings.kernel_cone over holon.bindings.kernel_entries(<that module>) is everything the statement
reaches (the same condition G2's bindings rely on).

Term size (I12-P1), a mechanical measure: for a PROVED law, whose LAWS.bend is the statement itself,
  term_size = sum of len(entry text) over the law's kernel cone (BendTT entries of its model module)
            + len(its LAWS.bend without comment lines), the normalisation of holon.bindings.text_sha256.
It is measured per law on every fixture law that is PROVED in both encodings: L_orc_cf_commit (a CF premise),
L_orc_runs_ok and L_orc_run_post (both parameters threaded, no premise) and L_orc_dec_pad (a hyp premise).
The baseline is the M1 model on the same laws. The M1 model of the machine: tests_m2/fixtures/oracles_standin/
holds byte-identical facts and, in place of an oracle sidecar, a target library compiling each oracle into the
model as a stand-in builtin, exactly as spec/M1/lib/morph_rollup.lib.json compiles agg (dec takes its HypD-pad
instance). The same laws in their M1 form (m1_form below): M1 states no hash or oracle binder and no CF or
hypothesis premise (its CF assumptions are ledger entries), so those go and the claim stays; the statement
cost of the parameters is thereby counted on the parametric side. The baseline runs as the same fixture
milestone T12, so both sides carry the M2+ machinery (core import, Reach, prover separation) and the
comparison isolates the cost of the parameters.

Records (M2+ laws).
  model_assumptions == exactly the sorted set of the law's hypothesis premises (§8.5): {"hyp": {"name": H}}
    gives H; {"cf": {"fn": p, ..}} gives the hypothesis id of the modelled kind-cf entry whose parameter is
    p. Nothing else: no ledger abstraction (the fixture ledger has one that meets every cone), no Reach.
  statement_hash == holon.gen.refs.law_hash(law, facts, oracles=<the parsed sidecar>). A hyp premise is a
    reference: its ref is the content hash of its hypothesis's entry restricted to {parameter, hypothesis} (the
    instance, doc and ledger are not hashed: an instance only serves refutation and inhabitation), so editing a
    hypothesis changes the hash of every law that names it, and of no other law; editing a not_in_scope entry,
    or an entry's instance or doc, changes no hash.
  non_vacuity (G11V): a PROVED law with hypothesis premises is "inhabited", each parameter its hypothesis
    premises constrain taking the instance of the entry whose hypothesis it is
    (non_vacuity.witness[p] == {"instance": <entry id>}); the inhabitant (non_vacuity.law and the PROOF.bend
    beside it) checks, and states the parent's premises in I3's form: premises are emitted as binder lines
    `for hN: {X}` (as today, every premise kind), and each such line of the parent's LAWS.bend is a line `{X}`
    of the inhabitant law, its witness supplied by the proof
    (tests_m2/test_nonvacuity.py::test_m1_inhabitant_premises_are_the_parents).

Splits. `holon run` writes <out>/splits.json (results/<M>/splits.json by default) for M2+ milestones:
  {"splits_version": "holon-splits/0.1", "milestone": M,
   "pairs": [{"family": F, "laws": {law_id: {"hypothesis": H, "status": S}, ..}, "split": bool}, ..]}
  Laws pair on family F when they name different hypotheses of F and their statements are equal once every
  hyp premise name of family F is replaced by F (pairs come from statements, never from law ids). split is
  true iff at least one law of the pair is PROVED and at least one REFUTED (§8.5: it holds under one
  hypothesis and fails under another). pairs sorted by (family, law ids).

holon/oracle_check.py
  validate(doc: dict) -> [problem]          the sidecar rules above; [] when valid
  check(sidecar: Path, out_dir: Path, root: Path = ROOT) -> {hypothesis id: result}
    result = {"oracle": <entry id>, "kind": "cf" | "hyp" | None,
              "status": "checked" | "mismatch" | "untestable_here" | "not_in_scope"   (A4: the hypothesis tested
                        against the real oracle where one is available here),
              "reason": str (required for untestable_here and not_in_scope),
              "instance": {"status": "checked" | "failed" | "per_premise" | "not_applicable",
                           "law": path, "proof": path (when a law was generated)}}             (G11V)
    instance.status is "checked" when Bend accepts a generated law stating that the entry's concrete instance
    satisfies its predicate (by evaluation), written to out_dir/<hypothesis id>/{LAWS.bend, PROOF.bend};
    "failed" when Bend does not; "per_premise" for kind cf (each law's premise supplies S and is inhabited
    per law); "not_applicable" for not_in_scope entries. A sidecar is checked on its own: templates render
    ${param:NAME:DEFAULT} as DEFAULT. Paths are repo-relative under root, else absolute.
  python -m holon oracle check --milestone M2
    reads spec/M2/lib/oracles.json and writes results/M2/hypotheses.json (keyed by hypothesis id, sorted)
    and the instance laws under gen/M2/oracles/. It merges: Hyp-Z0-kzg (I3, `holon oracle zero-blob`) is
    kept exactly as written, and every other sidecar hypothesis gets a result.

spec/M2/lib/oracles.json covers the oracle names agg (keccak over the blob versioned hashes, stood in by
agg), header_presentation (CF(keccak, headers)), ISubmitter, verifier, messenger, and the whitepaper §11.1
list: compression_codec, circuits, KZG, transaction_codec, L2_predeploys, fetcher, sealing_loop. agg and
header_presentation are modelled kind-cf entries; agg's instance is the M1 stand-in template. The verifier
is a modelled kind-hyp entry; its hypothesis (the proof == 1 rule) is labelled untestable_here. The entries of agg,
header_presentation, ISubmitter, verifier and messenger cite their M1 stand-ins in "ledger".
"""
import copy
import functools
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.reference import mini_schema
from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json

FIX = ROOT / "tests_m2" / "fixtures" / "oracles"
LAWS = FIX / "laws"
FACTS = "tests_m2/fixtures/oracles/facts/toy_oracle.facts.json"
SIDECAR = FIX / "lib" / "oracles.json"
STANDIN_FACTS = "tests_m2/fixtures/oracles_standin/facts/toy_oracle.facts.json"
M2_SIDECAR = ROOT / "spec" / "M2" / "lib" / "oracles.json"
HYPS = ROOT / "results" / "M2" / "hypotheses.json"
IR03 = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
MILESTONE = "T12"

PARAM_IDS = ["L_orc_cf_commit", "L_orc_runs_ok", "L_orc_run_post", "L_orc_agg_value"]
# every fixture law PROVED in both encodings (for a REFUTED law LAWS.bend is the counter-law, not the statement)
SIZE_IDS = ["L_orc_cf_commit", "L_orc_runs_ok", "L_orc_run_post", "L_orc_dec_pad"]
SPLIT = ("L_orc_dec_pad", "L_orc_dec_exact")
NO_SPLIT = ("L_orc_dec2_pad", "L_orc_two_exact")   # ids share no stem: pairs come from statements, never from ids
ALL_IDS = PARAM_IDS + list(SPLIT) + list(NO_SPLIT)
RATIO_MAX = 1.5

REQUIRED_ORACLES = ["agg", "header_presentation", "ISubmitter", "verifier", "messenger", "compression_codec",
                    "circuits", "KZG", "transaction_codec", "L2_predeploys", "fetcher", "sealing_loop"]
LEDGER_OF = {"agg": "CF-keccak-blobhashes", "header_presentation": "CF-keccak-headers",
             "ISubmitter": "oracle-ISubmitter", "verifier": "oracle-verifier", "messenger": "oracle-messenger"}
A4_STATUS = {"checked", "mismatch", "untestable_here", "not_in_scope"}
ZERO_BLOB = "Hyp-Z0-kzg"
MODEL_TERMS = {"var", "s0", "run", "step", "obs", "obsv", "act", "trace", "mig", "proj", "cat", "plus"}
LAWS_PIN = "c227f94823219feab4f565e8c7192f26890ab968935e0fc5ccd44f03e31debc5"   # laws/M0 + laws/M1 at the prereg

_KEEP: list[Path] = []


def tearDownModule():
    for d in _KEEP:
        shutil.rmtree(d, ignore_errors=True)


def law(lid: str) -> dict:
    return load_json(LAWS / f"{lid}.json")


def bend(args: list) -> tuple[int, str]:
    from tests._util import run_bend
    return run_bend([str(a) for a in args])


def law_count(text: str) -> int:
    return len(re.findall(r"^law\s+[A-Za-z0-9_.]+\s*:", text, re.M))


def m1_form(x: dict) -> dict:
    """The M1 form of a fixture law, for the M1-encoding baseline: M1 states no hash or oracle binder (its
    hashes are stand-ins compiled into the model, its CF assumptions ledger entries), so the Fn binders and
    the cf/hyp premises go; the claim, which applies no parameter, stays."""
    y = copy.deepcopy(x)
    st = y["statement"]
    gone = {b["name"] for b in st["binders"] if b["type"].startswith("Fn<")}
    st["binders"] = [b for b in st["binders"] if b["name"] not in gone]
    st["assume"] = [p for p in st.get("assume", []) if not ({"cf", "hyp"} & set(p))]
    if not st["assume"]:
        st.pop("assume")
    if {"app:" + n for n in gone} & _keys(st, set()):
        raise AssertionError(f"{x['law_id']}: a claim that applies a parameter has no M1 form")
    return y


def run_fixture(facts_rel: str, ids: tuple, tag: str, form=None, sidecar: dict | None = None) -> dict:
    """Run fixture laws `ids` (each through `form`, if given) over `facts_rel` as milestone T12 in a throwaway
    copy of the repo (with the fixture sidecar replaced by `sidecar`, if given). Returns {"recs", "log", "root"}:
    root is a kept directory holding t12_out/ and t12_gen/ at the repo-relative paths the records name."""
    repo = copy_repo()
    keep = Path(tempfile.mkdtemp(prefix=f"holon-oracles-{tag}-"))
    _KEEP.append(keep)
    try:
        if sidecar is not None:
            write_json(repo / SIDECAR.relative_to(ROOT), sidecar)
        sha = hashlib.sha256((repo / facts_rel).read_bytes()).hexdigest()
        d = repo / "laws" / MILESTONE
        d.mkdir(parents=True)
        for lid in ids:
            x = form(law(lid)) if form else law(lid)
            x["facts"], x["facts_sha256"] = facts_rel, sha
            write_json(d / f"{lid}.json", x)
        write_json(d / "REGISTRY.json", {"milestone": MILESTONE, "facts": facts_rel, "facts_sha256": sha,
                                         "facts_files": {facts_rel: sha}, "statements": {i: None for i in ids}})
        out, gen = repo / "t12_out", repo / "t12_gen"
        p = run_holon(["run", "--milestone", MILESTONE, "--no-registry", "--out", str(out), "--gen-dir", str(gen)],
                      cwd=repo)
        for x in (out, gen):
            if x.exists():
                shutil.copytree(x, keep / x.name)
        recs = {lid: load_json(out / f"{lid}.json") for lid in ids if (out / f"{lid}.json").exists()}
        return {"recs": recs, "log": p.stdout[-3000:] + p.stderr[-3000:], "root": keep}
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


@functools.lru_cache(maxsize=None)
def param_run() -> dict:
    return run_fixture(FACTS, tuple(ALL_IDS), "param")


@functools.lru_cache(maxsize=None)
def standin_run() -> dict:
    return run_fixture(STANDIN_FACTS, tuple(SIZE_IDS), "standin", form=m1_form)


@functools.lru_cache(maxsize=None)
def canary_run() -> dict:
    """The fixture laws whose premises are inhabited, run with instances that violate their hypotheses: agg
    the constant AGG_BASE (not CF on {[1], [2]}) and dec-pad the identity (not HypD-pad). Their proofs use
    only the premises, so they stay PROVED; an inhabitant that really is the instance's no longer checks."""
    sc = load_json(SIDECAR)
    E = {e["id"]: e for e in sc["oracles"]}
    E["agg"]["instance"]["bend"] = "${param:AGG_BASE:1000}n"
    E["dec-pad"]["instance"]["bend"] = "$0"
    return run_fixture(FACTS, ("L_orc_cf_commit", "L_orc_dec_pad"), "canary", sidecar=sc)


def model_of(laws_bend: Path) -> Path:
    """The one model module a law file imports, as M."""
    text = laws_bend.read_text(encoding="utf-8")
    imports = re.findall(r"^import\s+(\S+)(?:\s+as\s+(\S+))?\s*$", text, re.M)
    others = [(p, a) for p, a in imports if p != "Base"]
    if len(others) != 1 or others[0][1] != "M":
        raise AssertionError(f"{laws_bend}: a law file imports Base and exactly one model module as M, got {imports}")
    return (laws_bend.parent / others[0][0]).resolve()


def term_size(root: Path, rec: dict) -> int:
    """I12-P1's measure (module docstring)."""
    B = holon_module("holon.bindings")
    lb = root / rec["artifacts"]["laws"]
    text = lb.read_text(encoding="utf-8")
    entries = B.kernel_entries(model_of(lb))
    cone = B.kernel_cone(text, entries)
    stmt = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return sum(len(entries[d]) for d in cone) + len(stmt)


def hypothesis_premises(x: dict, sidecar: dict) -> list[str]:
    """The record's expected model_assumptions (module docstring)."""
    out = set()
    for p in x["statement"].get("assume", []):
        if "hyp" in p:
            out.add(p["hyp"]["name"])
        elif "cf" in p:
            ids = [e["hypothesis"]["id"] for e in sidecar["oracles"] if e["status"] == "modelled"
                   and e["hypothesis"].get("kind") == "cf" and e["parameter"]["name"] == p["cf"]["fn"]]
            assert len(ids) == 1, (p, ids)
            out.add(ids[0])
    return sorted(out)


def _keys(t, out: set) -> set:
    """Every key of a term tree, plus fn:<name> for each call {fn, args} and app:<name> for each application."""
    if isinstance(t, dict):
        out |= set(t)
        if "fn" in t and "args" in t:
            out.add("fn:" + str(t["fn"]))
        if "app" in t:
            out.add("app:" + str(t["app"]))
        for v in t.values():
            _keys(v, out)
    elif isinstance(t, list):
        for v in t:
            _keys(v, out)
    return out


def sidecar_problems(doc: dict) -> list[str]:
    """An independent reading of the holon-oracles/0.1 rules (module docstring); [] when they hold."""
    bad = []
    schema = load_json(IR03)
    if doc.get("oracles_version") != "holon-oracles/0.1":
        bad.append("oracles_version")
    entries = doc.get("oracles")
    if not isinstance(entries, list) or not entries:
        return bad + ["no oracles"]
    ids = [e.get("id") for e in entries]
    hids = [e["hypothesis"].get("id") if isinstance(e.get("hypothesis"), dict) else None for e in entries]
    if len(set(ids)) != len(ids):
        bad.append("duplicate entry ids")
    if len(set(hids)) != len(hids):
        bad.append("duplicate hypothesis ids")
    for e in entries:
        w = e.get("id")
        par, hyp = e.get("parameter"), e.get("hypothesis")
        if not isinstance(e.get("oracle"), str) or not e["oracle"]:
            bad.append(f"{w}: oracle")
        if not isinstance(par, dict) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(par.get("name"))):
            bad.append(f"{w}: parameter")
            continue
        if not isinstance(hyp, dict) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", str(hyp.get("id"))) \
                or not isinstance(hyp.get("doc"), str):
            bad.append(f"{w}: hypothesis")
            continue
        if "instance" not in e:
            bad.append(f"{w}: no instance key")
        if e.get("status") == "not_in_scope":
            if not isinstance(e.get("reason"), str) or not e["reason"].strip():
                bad.append(f"{w}: not_in_scope without a reason")
            continue
        if e.get("status") != "modelled":
            bad.append(f"{w}: status {e.get('status')!r}")
            continue
        if not re.fullmatch(r"Fn<.+>", str(par.get("type"))):
            bad.append(f"{w}: a modelled parameter needs a Fn type")
        inst = e.get("instance")
        if not isinstance(inst, dict) or not isinstance(inst.get("bend"), str) or not inst["bend"].strip():
            bad.append(f"{w}: a modelled entry needs a concrete instance")
        kind = hyp.get("kind")
        if kind not in ("cf", "hyp"):
            bad.append(f"{w}: kind {kind!r}")
        if kind == "hyp":
            pred = hyp.get("predicate")
            if not isinstance(pred, list) or not pred:
                bad.append(f"{w}: a hyp hypothesis needs a predicate")
                continue
            for p in pred:
                if mini_schema.errors(p, {"$ref": "#/$defs/premise"}, root=schema):
                    bad.append(f"{w}: predicate item is not an IR 0.3 premise: {p}")
                if "cf" in p and not isinstance(p["cf"].get("set"), list):
                    bad.append(f"{w}: global injectivity in a predicate")
                ks = _keys(p, set())
                if ks & MODEL_TERMS:
                    bad.append(f"{w}: predicate is not ground ({sorted(ks & MODEL_TERMS)})")
                if {k for k in ks if k.startswith("app:")} - {"app:" + par["name"]}:
                    bad.append(f"{w}: predicate applies something other than its parameter")
                if {k for k in ks if k.startswith("fn:")} - {"fn:eq_nat", "fn:eq_bool", "fn:eq_nats"}:
                    bad.append(f"{w}: predicate calls a model function")
                if "cf" in p and p["cf"].get("fn") != par["name"]:
                    bad.append(f"{w}: cf over something other than its parameter")
    return bad


# ====================================================================== run-level (fixture milestone T12)
class _Run(unittest.TestCase):
    def rec(self, lid: str) -> dict:
        r = param_run()
        self.assertIn(lid, r["recs"], r["log"])
        return r["recs"][lid]

    def assert_checks(self, laws_bend: Path, proof: Path) -> None:
        self.assertTrue(laws_bend.exists(), laws_bend)
        self.assertTrue(proof.exists(), proof)
        self.assertEqual(law_count(laws_bend.read_text(encoding="utf-8")), 1, laws_bend)
        code, out = bend([proof])
        self.assertEqual(code, 0, out[-800:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])


class TestParametricModel(_Run):
    def test_parametric_model_checks(self):
        """I12-P1 (first half): the parametric model module passes bend, and every parameter fixture law is
        decided with its fixture-predicted status (3 PROVED, 1 REFUTED), re-checked by BendTT."""
        for lid in PARAM_IDS:
            with self.subTest(law=lid):
                r = self.rec(lid)
                self.assertEqual(r["status"], law(lid)["predicted"], r.get("attempts"))
                self.assertEqual(r["kernel"]["verdict"], "checked", r.get("attempts"))
        root = param_run()["root"]
        model = model_of(root / self.rec("L_orc_cf_commit")["artifacts"]["laws"])
        code, out = bend([model])
        self.assertEqual(code, 0, out[-800:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])

    def test_model_is_parametric_in_agg(self):
        """I12-P1 (what "parametric" means): com after commit(1) is 1002 for the stand-in instance but not for
        every hash, so the law is REFUTED, by a witness other than the instance, exactly when agg is a
        parameter of the model rather than compiled into it."""
        r = self.rec("L_orc_agg_value")
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertEqual(r["kernel"]["verdict"], "checked", r.get("attempts"))
        self.assertIn("agg", r["witness"])
        self.assertNotEqual(r["witness"]["agg"], {"instance": "agg"})

    def test_term_size_at_most_1_5x_the_stand_in_model(self):
        """I12-P1 (second half): per fixture law PROVED in both encodings (SIZE_IDS: a CF premise, no premise,
        a hyp premise), term size on the parametric model <= 1.5x term size on the M1 encoding of the same
        machine (module docstring)."""
        for lid in SIZE_IDS:
            self.assertEqual(self.rec(lid)["status"], "PROVED", self.rec(lid).get("attempts"))
        self.assertEqual((ROOT / FACTS).read_bytes(), (ROOT / STANDIN_FACTS).read_bytes(),
                         "the baseline must be the same machine")
        base = standin_run()
        p_root, b_root = param_run()["root"], base["root"]
        for lid in SIZE_IDS:
            with self.subTest(law=lid):
                b = base["recs"].get(lid)
                self.assertIsNotNone(b, base["log"])
                self.assertEqual(b["status"], "PROVED", b.get("attempts"))
                sp, sb = term_size(p_root, self.rec(lid)), term_size(b_root, b)
                self.assertGreater(sb, 0)
                self.assertLessEqual(sp / sb, RATIO_MAX, f"{lid}: parametric {sp} vs stand-in {sb}")


class TestSplits(_Run):
    def splits(self) -> dict:
        p = param_run()["root"] / "t12_out" / "splits.json"
        self.assertTrue(p.exists(), param_run()["log"])
        s = load_json(p)
        self.assertEqual(s["splits_version"], "holon-splits/0.1")
        self.assertEqual(s["milestone"], MILESTONE)
        return s

    def pair(self, s: dict, ids: tuple) -> dict:
        got = [x for x in s["pairs"] if set(x["laws"]) == set(ids)]
        self.assertEqual(len(got), 1, s["pairs"])
        return got[0]

    def test_variant_pair_has_different_statuses(self):
        """I12-P2: the same obligation under HypD-pad is PROVED and under HypD-exact is REFUTED."""
        pad, exact = (self.rec(x) for x in SPLIT)
        self.assertEqual(pad["status"], "PROVED", pad.get("attempts"))
        self.assertEqual(exact["status"], "REFUTED", exact.get("attempts"))
        for r in (pad, exact):
            self.assertEqual(r["kernel"]["verdict"], "checked", r.get("attempts"))
        self.assertIn("dec", exact["witness"])

    def test_splits_json_reports_the_split(self):
        """I12-P2: splits.json pairs the two laws on family HypD, from their statements, and reports a split."""
        s = self.splits()
        x = self.pair(s, SPLIT)
        self.assertEqual(x["family"], "HypD")
        self.assertEqual(x["laws"]["L_orc_dec_pad"]["hypothesis"], "HypD-pad")
        self.assertEqual(x["laws"]["L_orc_dec_exact"]["hypothesis"], "HypD-exact")
        for lid in SPLIT:
            self.assertEqual(x["laws"][lid]["status"], self.rec(lid)["status"])
        self.assertIs(x["split"], True)

    def test_equal_statuses_are_not_a_split(self):
        """Both variants REFUTED (HypD-pad's needs a witness satisfying HypD-pad, such as its own concrete
        instance, which the refuter must try): a pair, not a split, found from the statements although the two
        ids share no stem. No other law pairs."""
        for lid in NO_SPLIT:
            with self.subTest(law=lid):
                r = self.rec(lid)
                self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
                self.assertEqual(r["kernel"]["verdict"], "checked", r.get("attempts"))
        # REFUTED under HypD-pad needs a witness satisfying HypD-pad (dec(9) = 1, dec(10) = 2; of the record
        # instances only dec-pad's does), so the counter-law must carry the hypothesis premise: the premise lines
        # of the PROVED variant L_orc_dec_pad (`for hN: {X}`) are those of the counter-law (`exs hN: {X}`, as in M1)
        root = param_run()["root"]
        stated = re.findall(r"^\s+for h\d+: (\{.*\})\s*$", (root / self.rec("L_orc_dec_pad")["artifacts"]["laws"])
                            .read_text(encoding="utf-8"), re.M)
        counter = re.findall(r"^\s+exs h\d+: (\{.*\})\s*$", (root / self.rec("L_orc_dec2_pad")["artifacts"]["laws"])
                             .read_text(encoding="utf-8"), re.M)
        self.assertTrue(stated, "L_orc_dec_pad states HypD-pad as `for hN: {...}` lines")
        self.assertEqual(counter, stated, "the counter-law of L_orc_dec2_pad carries HypD-pad")
        s = self.splits()
        x = self.pair(s, NO_SPLIT)
        self.assertEqual(x["family"], "HypD")
        self.assertIs(x["split"], False)
        self.assertEqual(len(s["pairs"]), 2, s["pairs"])
        self.assertEqual(s["pairs"], sorted(s["pairs"], key=lambda y: (y["family"], sorted(y["laws"]))))


class TestNonVacuity(_Run):
    def inhabitant(self, lid: str) -> dict:
        """The law's inhabitant: it checks, and states exactly the parent's premises (I3's form)."""
        r, root = self.rec(lid), param_run()["root"]
        nv = r["non_vacuity"]
        self.assertEqual(nv["status"], "inhabited", nv)
        lb = root / nv["law"]
        self.assert_checks(lb, lb.parent / "PROOF.bend")
        parent = (root / r["artifacts"]["laws"]).read_text(encoding="utf-8")
        want = re.findall(r"^\s+for h\d+: (\{.*\})\s*$", parent, re.M)
        self.assertTrue(want, f"{lid}: the parent states its premises as `for hN: {{...}}` lines\n{parent}")
        text = lb.read_text(encoding="utf-8")
        body = text[re.search(r"^law\s+[A-Za-z0-9_.]+\s*:", text, re.M).start():]
        got = re.findall(r"^\s+(?:exs c\d+: )?(\{.*\})\s*$", body, re.M)
        self.assertEqual(got, want, f"{lid}: the inhabitant states the parent's premises\n{text}")
        return nv

    def canary(self, lid: str) -> dict:
        c = canary_run()
        self.assertIn(lid, c["recs"], c["log"])
        r = c["recs"][lid]
        self.assertEqual(r["status"], "PROVED", r.get("attempts"))
        return r.get("non_vacuity") or {}

    def test_cf_premise_inhabited_by_the_agg_instance(self):
        """I12-P3: CF(agg, {[1], [2]}) is inhabited by agg := the oracle record's concrete instance
        (AGG_BASE + enc(xs)), and the inhabitant checks."""
        self.assertEqual(self.rec("L_orc_cf_commit")["status"], "PROVED", self.rec("L_orc_cf_commit").get("attempts"))
        nv = self.inhabitant("L_orc_cf_commit")
        self.assertEqual(nv["witness"]["agg"], {"instance": "agg"}, nv)

    def test_cf_inhabitant_is_the_instance_not_a_label(self):
        """I12-P3 (canary): with an agg instance that is not CF on {[1], [2]} (a constant), no inhabitant
        claims the instance: the recorded witness is the instance the checked inhabitant uses."""
        nv = self.canary("L_orc_cf_commit")
        self.assertNotEqual((nv.get("witness") or {}).get("agg"), {"instance": "agg"}, nv)

    def test_hyp_premise_inhabited_by_its_variant_instance(self):
        """G11V for hyp premises: HypD-pad is inhabited by dec := the dec-pad entry's instance."""
        self.assertEqual(self.rec("L_orc_dec_pad")["status"], "PROVED", self.rec("L_orc_dec_pad").get("attempts"))
        nv = self.inhabitant("L_orc_dec_pad")
        self.assertEqual(nv["witness"]["dec"], {"instance": "dec-pad"}, nv)

    def test_hyp_inhabitant_is_the_instance_not_a_label(self):
        """G11V canary: with a dec-pad instance that violates HypD-pad (the identity), no inhabitant claims it."""
        nv = self.canary("L_orc_dec_pad")
        self.assertNotEqual((nv.get("witness") or {}).get("dec"), {"instance": "dec-pad"}, nv)


class TestRecords(_Run):
    def test_model_assumptions_are_exactly_the_hypothesis_premises(self):
        """§8.5: for M2+ laws, model_assumptions is the set of hypothesis premises and nothing else."""
        sc = load_json(SIDECAR)
        want = {"L_orc_cf_commit": ["CF-agg"], "L_orc_runs_ok": [], "L_orc_run_post": [], "L_orc_agg_value": [],
                "L_orc_dec_pad": ["HypD-pad"], "L_orc_dec_exact": ["HypD-exact"],
                "L_orc_dec2_pad": ["HypD-pad"], "L_orc_two_exact": ["HypD-exact"]}
        for lid in ALL_IDS:
            with self.subTest(law=lid):
                self.assertEqual(hypothesis_premises(law(lid), sc), want[lid])
                self.assertEqual(self.rec(lid)["model_assumptions"], want[lid])

    def test_statement_hash_covers_the_hypotheses(self):
        """Each record's statement hash is the 0.3 hash with the oracle sidecar's refs."""
        R = holon_module("holon.gen.refs")
        facts, sc = load_json(ROOT / FACTS), load_json(SIDECAR)
        for lid in ALL_IDS:
            with self.subTest(law=lid):
                self.assertEqual(self.rec(lid)["statement_hash"], R.law_hash(law(lid), facts, oracles=sc))


# ====================================================================== statement hash (no run)
class TestStatementHash(unittest.TestCase):
    def test_hypothesis_edit_restales_exactly_the_laws_that_name_it(self):
        R = holon_module("holon.gen.refs")
        facts, sc = load_json(ROOT / FACTS), load_json(SIDECAR)
        base = {lid: R.law_hash(law(lid), facts, oracles=sc) for lid in ALL_IDS}
        edited = copy.deepcopy(sc)
        e = next(x for x in edited["oracles"] if x["hypothesis"]["id"] == "HypD-pad")
        e["hypothesis"]["predicate"][0]["eq"][1] = {"nat": 3}
        h = {lid: R.law_hash(law(lid), facts, oracles=edited) for lid in ALL_IDS}
        naming = {"L_orc_dec_pad", "L_orc_dec2_pad"}
        for lid in ALL_IDS:
            with self.subTest(law=lid):
                if lid in naming:
                    self.assertNotEqual(h[lid], base[lid])
                else:
                    self.assertEqual(h[lid], base[lid])
        unrelated = copy.deepcopy(sc)
        next(x for x in unrelated["oracles"] if x["status"] == "not_in_scope")["reason"] += " (edited)"
        self.assertEqual({lid: R.law_hash(law(lid), facts, oracles=unrelated) for lid in ALL_IDS}, base)


# ====================================================================== oracle sidecars
class TestSidecarRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.OC = holon_module("holon.oracle_check")

    def test_fixture_sidecar_is_valid(self):
        sc = load_json(SIDECAR)
        self.assertEqual(sidecar_problems(sc), [])
        self.assertEqual(self.OC.validate(sc), [])

    def test_invalid_sidecars_are_rejected(self):
        """Exit (G3): a predicate stating global injectivity is rejected; so are a modelled entry without an
        instance, a not_in_scope entry without a reason, a hyp hypothesis without a predicate and a predicate
        that applies another parameter."""
        sc = load_json(SIDECAR)

        def mutate(fn):
            x = copy.deepcopy(sc)
            fn({e["id"]: e for e in x["oracles"]})
            return x
        canaries = {
            "global injectivity": mutate(lambda E: E["dec-pad"]["hypothesis"].update(
                predicate=[{"cf": {"fn": "dec", "set": "*"}}])),
            "no instance": mutate(lambda E: E["dec-exact"].update(instance=None)),
            "no reason": mutate(lambda E: E["fetcher"].pop("reason")),
            "no predicate": mutate(lambda E: E["dec-pad"]["hypothesis"].pop("predicate")),
            "foreign parameter": mutate(lambda E: E["dec-pad"]["hypothesis"]["predicate"][0]["eq"].__setitem__(
                0, {"app": "agg", "args": [{"nats": [9]}]})),
        }
        for name, doc in canaries.items():
            with self.subTest(canary=name):
                self.assertTrue(sidecar_problems(doc), name)
                self.assertTrue(self.OC.validate(doc), name)


class TestInstanceCheck(unittest.TestCase):
    """G11V for hypotheses: each modelled hypothesis has a concrete instance satisfying it, proved by a checked
    law (kind hyp), or inhabited per law premise (kind cf)."""

    @classmethod
    def setUpClass(cls):
        cls.OC = holon_module("holon.oracle_check")
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-oracle-check-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def path(self, p: str) -> Path:
        return Path(p) if Path(p).is_absolute() else ROOT / p

    def test_fixture_instances(self):
        r = self.OC.check(SIDECAR, self.tmp / "ok", ROOT)
        self.assertEqual(set(r), {"CF-agg", "HypD-exact", "HypD-pad", "HypF"})
        self.assertEqual(r["CF-agg"]["instance"]["status"], "per_premise")
        for h in ("HypD-exact", "HypD-pad"):
            with self.subTest(hypothesis=h):
                inst = r[h]["instance"]
                self.assertEqual(inst["status"], "checked", r[h])
                lb, pf = self.path(inst["law"]), self.path(inst["proof"])
                self.assertEqual(law_count(lb.read_text(encoding="utf-8")), 1)
                code, out = bend([pf])
                self.assertEqual(code, 0, out[-800:])
                self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
        self.assertEqual(r["HypF"]["status"], "not_in_scope")
        self.assertTrue(r["HypF"]["reason"].strip())
        self.assertEqual(r["HypF"]["instance"]["status"], "not_applicable")
        for h, x in r.items():
            with self.subTest(hypothesis=h):
                self.assertIn(x["status"], A4_STATUS)
                self.assertEqual(x["oracle"], next(e["id"] for e in load_json(SIDECAR)["oracles"]
                                                   if e["hypothesis"]["id"] == h))

    def test_an_instance_that_violates_its_hypothesis_fails(self):
        sc = load_json(SIDECAR)
        bad = copy.deepcopy(sc)
        next(e for e in bad["oracles"] if e["id"] == "dec-exact")["instance"]["bend"] = "Nat.sub($0, ${param:PAD:8}n)"
        p = self.tmp / "bad_sidecar" / "lib" / "oracles.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        write_json(p, bad)
        r = self.OC.check(p, self.tmp / "bad", ROOT)
        self.assertEqual(r["HypD-exact"]["instance"]["status"], "failed", r["HypD-exact"])
        self.assertEqual(r["HypD-pad"]["instance"]["status"], "checked", r["HypD-pad"])


class TestMorphSidecar(unittest.TestCase):
    def doc(self) -> dict:
        self.assertTrue(M2_SIDECAR.exists(), M2_SIDECAR)
        return load_json(M2_SIDECAR)

    def test_valid(self):
        d = self.doc()
        self.assertEqual(sidecar_problems(d), [])
        self.assertEqual(holon_module("holon.oracle_check").validate(d), [])

    def test_covers_the_stand_ins_and_the_section_11_1_oracles(self):
        names = {e["oracle"] for e in self.doc()["oracles"]}
        self.assertEqual(sorted(set(REQUIRED_ORACLES) - names), [])

    def test_hashes_are_modelled_cf_parameters_and_agg_is_the_m1_instance(self):
        es = self.doc()["oracles"]
        for name in ("agg", "header_presentation"):
            with self.subTest(oracle=name):
                mine = [e for e in es if e["oracle"] == name]
                self.assertTrue(mine)
                for e in mine:
                    self.assertEqual(e["status"], "modelled")
                    self.assertEqual(e["hypothesis"]["kind"], "cf")
        m1 = load_json(ROOT / "spec" / "M1" / "lib" / "morph_rollup.lib.json")["builtins"]["agg"]["bend"]
        self.assertEqual({e["instance"]["bend"] for e in es if e["oracle"] == "agg"}, {m1})

    def test_stand_ins_cite_their_m1_ledger_entries(self):
        es = self.doc()["oracles"]
        rollup = next(b for b in load_json(ROOT / "spec" / "ledger" / "assumptions.json")["bundles"]
                      if b["facts"] == "spec/M1/facts/morph_rollup.json")
        known = {x["id"] for x in rollup["entries"]}
        for name, lid in LEDGER_OF.items():
            with self.subTest(oracle=name):
                self.assertIn(lid, known)
                self.assertTrue(any(lid in e.get("ledger", []) for e in es if e["oracle"] == name))

    def test_verifier_is_modelled(self):
        """The proof == 1 rule is a modelled hyp hypothesis (its A4 label is in results/M2/hypotheses.json)."""
        es = [e for e in self.doc()["oracles"] if e["oracle"] == "verifier"]
        self.assertTrue(es)
        for e in es:
            self.assertEqual(e["status"], "modelled")
            self.assertEqual(e["hypothesis"]["kind"], "hyp")


class TestHypotheses(unittest.TestCase):
    """results/M2/hypotheses.json, written by `holon oracle check --milestone M2` (A4 and G11V per hypothesis)."""

    def test_every_sidecar_hypothesis_has_a_result(self):
        hyps, es = load_json(HYPS), load_json(M2_SIDECAR)["oracles"]
        self.assertEqual(hyps[ZERO_BLOB]["status"], "checked")
        for e in es:
            h = e["hypothesis"]["id"]
            if h == ZERO_BLOB:
                continue
            with self.subTest(hypothesis=h):
                x = hyps[h]
                self.assertEqual(x["oracle"], e["id"])
                self.assertIn(x["status"], A4_STATUS)
                if x["status"] in ("untestable_here", "not_in_scope"):
                    self.assertTrue(x["reason"].strip())
                self.assertEqual(x["status"] == "not_in_scope", e["status"] == "not_in_scope")
                want = ("not_applicable" if e["status"] == "not_in_scope"
                        else "per_premise" if e["hypothesis"]["kind"] == "cf" else "checked")
                self.assertEqual(x["instance"]["status"], want, x)

    def test_verifier_rule_is_untestable_here(self):
        hyps = load_json(HYPS)
        es = [e for e in load_json(M2_SIDECAR)["oracles"] if e["oracle"] == "verifier"]
        self.assertTrue(es)
        for e in es:
            self.assertEqual(hyps[e["hypothesis"]["id"]]["status"], "untestable_here")

    def test_checked_instances_check(self):
        """G11V: every instance law the file names is accepted by Bend."""
        hyps = load_json(HYPS)
        n = 0
        for h, x in sorted(hyps.items()):
            if h == ZERO_BLOB or x["instance"]["status"] != "checked":
                continue
            with self.subTest(hypothesis=h):
                lb, pf = (ROOT / x["instance"][k] for k in ("law", "proof"))
                self.assertEqual(law_count(lb.read_text(encoding="utf-8")), 1)
                code, out = bend([pf])
                self.assertEqual(code, 0, out[-800:])
                self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
                n += 1
        self.assertGreater(n, 0, "the verifier's hypothesis at least has a checked instance")

    def test_oracle_check_reproduces_and_keeps_zero_blob(self):
        """From I3's file (only Hyp-Z0-kzg), `holon oracle check --milestone M2` rebuilds the committed
        hypotheses.json and gen/M2/oracles byte for byte, and leaves Hyp-Z0-kzg exactly as it was."""
        repo = copy_repo()
        try:
            hp = repo / "results" / "M2" / "hypotheses.json"
            zb = load_json(hp)[ZERO_BLOB]
            hp.write_text(json.dumps({ZERO_BLOB: zb}, indent=2, sort_keys=True) + "\n")
            shutil.rmtree(repo / "gen" / "M2" / "oracles", ignore_errors=True)
            p = run_holon(["oracle", "check", "--milestone", "M2"], cwd=repo, timeout=1200)
            self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
            self.assertEqual(load_json(hp)[ZERO_BLOB], zb)
            self.assertEqual(hp.read_bytes(), HYPS.read_bytes())

            def tree(r: Path) -> dict:
                d = r / "gen" / "M2" / "oracles"
                return {f.relative_to(d).as_posix(): f.read_bytes() for f in sorted(d.rglob("*")) if f.is_file()}
            self.assertTrue(tree(ROOT))
            self.assertEqual(tree(repo), tree(ROOT))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ====================================================================== regressions
class TestRegression(unittest.TestCase):
    def test_m0_m1_laws_untouched(self):
        """I12-R2: laws/M0 and laws/M1 are byte-identical to the prereg tree."""
        h = hashlib.sha256()
        for d in ("laws/M0", "laws/M1"):
            for f in sorted((ROOT / d).rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    h.update(f.relative_to(ROOT).as_posix().encode() + b"\0"
                             + hashlib.sha256(f.read_bytes()).hexdigest().encode() + b"\n")
        self.assertEqual(h.hexdigest(), LAWS_PIN)


if __name__ == "__main__":
    unittest.main()
