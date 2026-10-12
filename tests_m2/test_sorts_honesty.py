"""I13 honesty: sorts are inferred mechanically, not read from hand annotations (BUILD_PLAN I13 Goal: "Infer
refined sorts mechanically"; AGENTS rules 2 and 4). Contract: tests_m2/test_sorts_morph.py docstring.

The M1 facts carry hand-written sort hints:
  - a "site" annotation on the three duplicated :363 guards ({"rule": "SORT", "kind": "realize",
    "expr": "W + cstart - t", "sort": "Dur(signed) realized in uint256"});
  - "note" strings on guards (e.g. "checked uint256 subtraction (Panic 0x11)");
  - docs that state sorts or sites: Entry.doc_fields.tag ("GHOST: writer sort of bvh ..."), the s_tag field doc,
    and the observers kappa ("the realize site at :363 underflows") and tags_ok ("... has the sort its version
    implies");
  - the ghost tag itself: Entry.tag, the ghost field s_tag, the def tag_at, the lets named tag, the s_tag
    effects and the observer tags_ok, which record by hand which member of the bvh union each write has.
One copy of the repo is mutated four ways; each time the diagram is regenerated in the copy
(`holon diagram --milestone M2 --root COPY`) and `holon sorts --milestone M2 --root COPY --out DIR` runs:
  baseline  unmodified;
  strip     every "site" and "note" key removed from every fact document, and every doc string matching
            /\\bsort\\b|realiz|\\bsite\\b|signed|uint256|ghost/i removed (state docs become ""). Nothing structural
            changes, so assignment.json (sites and sorts_sha256 included) and unions.json must equal the
            baseline's apart from "inputs" (the facts hashes); the unresolved variables (model, var, base_type)
            and the conflicts (model, kind, src, core size) must be the same. Constraint texts and ids may differ
            (a seed may list fewer grounds), the inferred sorts may not;
  ghost     strip, plus the whole ghost tag erased from the rollup facts. Every contract variable that survives
            keeps its sort; Entry.tag and s_tag disappear and no variable appears; the bvh union keeps its
            members and registers; sites keep span, expression, sort, obligation and entry points (occurrence
            "where" fields may shift, since guards are removed); conflicts are the same;
  rename    the rollup facts' hand-chosen identifiers renamed consistently (state fields t, W, F, D, qpend, qlen,
            enq, s_bvh; input wait.dt; lets cstart, prt, btot, bn, ef; def parameters of the same names), docs,
            src strings, action names and record fields untouched. The assignment of every contract variable
            (state fields, record fields, action inputs) is the baseline's under the renaming, and so are sites
            (expressions renamed), unions, unresolved variables and conflict kinds. Lexical seeds may read docs
            and source text (real-code identifiers such as block.timestamp or proofWindow); they may not key on
            the facts' own abbreviations.
"""
import copy
import json
import re
import shutil
import unittest
from collections import Counter
from pathlib import Path

from tests_m2._m2 import copy_repo, run_holon
from tests_m2._sorts import Run, required_keys, without

HINT = re.compile(r"\bsort\b|realiz|\bsite\b|signed|uint256|ghost", re.I)
ROLLUP = Path("spec/M1/facts/morph_rollup.json")
GHOST_KEYS = {"Entry.tag", "s_tag"}
STATE_RN = {"t": "zz_a", "W": "zz_b", "F": "zz_c", "D": "zz_d", "qpend": "zz_e", "qlen": "zz_f", "enq": "zz_g",
            "s_bvh": "zz_h"}
INPUT_RN = {("wait", "dt"): "zz_i"}
LET_RN = {"cstart": "zz_j", "prt": "zz_k", "btot": "zz_l", "bn": "zz_m", "ef": "zz_n"}
LEAF_RN = {**STATE_RN, **LET_RN, "dt": "zz_i"}


def fact_paths(repo: Path) -> list[Path]:
    return sorted((repo / "facts").glob("*.json")) + sorted((repo / "spec" / "M1" / "facts").glob("*.json"))


def dump(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ expression walker (holon-facts DSL)
def map_expr(e, leaf):
    """Rebuild a DSL expression, applying `leaf` to every variable position (string leaf)."""
    if isinstance(e, str):
        return leaf(e)
    if not isinstance(e, list) or not e:
        return e
    h = e[0]
    if h == "call":
        return [h, e[1], *(map_expr(x, leaf) for x in e[2:])]
    if h == "get":
        return [h, map_expr(e[1], leaf), e[2]]
    if h == "mk":
        return [h, e[1], {k: map_expr(v, leaf) for k, v in e[2].items()}]
    if h == "with":
        return [h, e[1], map_expr(e[2], leaf), {k: map_expr(v, leaf) for k, v in e[3].items()}]
    if h == "list":
        return [h, e[1], *(map_expr(x, leaf) for x in e[2:])]
    return [h, *(map_expr(x, leaf) for x in e[1:])]


def drop_mk_field(e, tname: str, field: str):
    if isinstance(e, list) and e:
        if e[0] == "mk" and e[1] == tname:
            return ["mk", tname, {k: drop_mk_field(v, tname, field) for k, v in e[2].items() if k != field}]
        if e[0] == "with" and e[1] == tname:
            return ["with", tname, drop_mk_field(e[2], tname, field),
                    {k: drop_mk_field(v, tname, field) for k, v in e[3].items() if k != field}]
        return [drop_mk_field(x, tname, field) if isinstance(x, (list, dict)) else x for x in e]
    if isinstance(e, dict):
        return {k: drop_mk_field(v, tname, field) for k, v in e.items()}
    return e


# ------------------------------------------------------------------ the three mutations
def strip_hints(x):
    """Remove "site" and "note" keys everywhere, and doc strings that state sorts, sites or ghosts."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in ("site", "note"):
                continue
            if k == "doc" and isinstance(v, str) and HINT.search(v):
                continue
            if k == "doc_fields" and isinstance(v, dict):
                v = {f: d for f, d in v.items() if not (isinstance(d, str) and HINT.search(d))}
            out[k] = strip_hints(v)
        return out
    if isinstance(x, list):
        return [strip_hints(v) for v in x]
    return x


def strip_state_docs(f: dict) -> dict:
    f = copy.deepcopy(f)
    if f.get("facts_version") == "holon-facts/0.2":
        f["state"] = [[s[0], s[1], "" if HINT.search(s[2]) else s[2]] if len(s) > 2 else s for s in f["state"]]
    return f


def erase_ghost_tag(f: dict) -> dict:
    """The rollup facts without their hand-written ghost tag (Entry.tag, s_tag, tag_at, lets tag, tags_ok)."""
    f = copy.deepcopy(f)
    e = f["types"]["Entry"]
    e["fields"] = [fl for fl in e["fields"] if fl[0] != "tag"]
    e["ghost"] = [g for g in e.get("ghost", []) if g != "tag"]
    e.get("doc_fields", {}).pop("tag", None)
    f["state"] = [s for s in f["state"] if s[0] != "s_tag"]
    f["ghost_state"] = [g for g in f.get("ghost_state", []) if g != "s_tag"]
    f.get("shadow", {}).pop("s_tag", None)
    f["initial"].pop("s_tag", None)
    for ent in f["initial"].get("win", []):
        ent.pop("tag", None)
    f["defs"].pop("tag_at", None)
    for a in f["actions"]:
        a["guards"] = [g for g in a.get("guards", []) if g.get("let") != "tag"]
        a["effects"] = {k: drop_mk_field(v, "Entry", "tag") for k, v in a.get("effects", {}).items() if k != "s_tag"}
    for mg in f.get("migrations", {}).values():
        mg["effects"] = {k: drop_mk_field(v, "Entry", "tag") for k, v in mg.get("effects", {}).items() if k != "s_tag"}
    f.get("observers", {}).pop("tags_ok", None)
    blob = json.dumps(f)
    for gone in ('"tag_at"', '"s_tag"', '"tags_ok"', '"es_tag"'):
        assert gone not in blob, f"ghost erasure left {gone}"
    return f


def rename_identifiers(f: dict) -> dict:
    """The rollup facts with STATE_RN, INPUT_RN, LET_RN applied to binders and uses (docs and src untouched)."""
    f = copy.deepcopy(f)
    leaf = lambda s: LEAF_RN.get(s, s)  # noqa: E731
    f["state"] = [[STATE_RN.get(s[0], s[0]), *s[1:]] for s in f["state"]]
    f["ghost_state"] = [STATE_RN.get(g, g) for g in f.get("ghost_state", [])]
    f["shadow"] = {STATE_RN.get(k, k): v for k, v in f.get("shadow", {}).items()}
    f["initial"] = {STATE_RN.get(k, k): v for k, v in f["initial"].items()}
    for d in f["defs"].values():
        d["params"] = [[LEAF_RN.get(p, p), ty] for p, ty in d["params"]]
        d["body"] = map_expr(d["body"], leaf)
    for a in f["actions"]:
        a["inputs"] = [[INPUT_RN.get((a["name"], x), x), ty] for x, ty in a.get("inputs", [])]
        for g in a.get("guards", []):
            if "let" in g:
                g["let"] = LET_RN.get(g["let"], g["let"])
            for k in ("require", "expr"):
                if k in g:
                    g[k] = map_expr(g[k], leaf)
        a["effects"] = {STATE_RN.get(k, k): map_expr(v, leaf) for k, v in a.get("effects", {}).items()}
    for mg in f.get("migrations", {}).values():
        mg["effects"] = {STATE_RN.get(k, k): map_expr(v, leaf) for k, v in mg.get("effects", {}).items()}
    for o in f.get("observers", {}).values():
        o["body"] = map_expr(o["body"], leaf)
    dl = f.get("disch", {}).get("delay")
    if dl:
        dl["input"] = INPUT_RN.get((dl["action"], dl["input"]), dl["input"])
    return f


def rename_key(k: str, actions: set[str]) -> str:
    if k in STATE_RN:
        return STATE_RN[k]
    a, _, x = k.partition(".")
    if (a, x) in INPUT_RN:
        return f"{a}.{INPUT_RN[(a, x)]}"
    if a in actions and x in LET_RN:
        return f"{a}.{LET_RN[x]}"
    return k


def site_key(s: dict) -> tuple:
    return (s["model"], s["span"], json.dumps(s["expr"], sort_keys=True))


def site_value(s: dict) -> tuple:
    return (s["sort"], s.get("obligation"), tuple(s["entry_points"]), tuple(sorted(o["action"] for o in s["occurrences"])))


class TestHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        try:
            cls._run_all()
        except BaseException:
            shutil.rmtree(cls.repo.parent, ignore_errors=True)
            raise

    @classmethod
    def _run_all(cls):
        repo = cls.repo
        paths = fact_paths(repo)
        orig = {p: json.loads(p.read_text(encoding="utf-8")) for p in paths}
        rollup = repo / ROLLUP

        def strip_all():
            for p, f in orig.items():
                dump(p, strip_state_docs(strip_hints(f)))

        def ghost_all():
            strip_all()
            dump(rollup, erase_ghost_tag(json.loads(rollup.read_text(encoding="utf-8"))))

        def rename_all():
            dump(rollup, rename_identifiers(orig[rollup]))

        cls.runs, cls.diagram_logs = {}, {}
        for name, mutate in (("baseline", None), ("strip", strip_all), ("ghost", ghost_all), ("rename", rename_all)):
            for p, f in orig.items():
                dump(p, f)
            if mutate:
                mutate()
            d = run_holon(["diagram", "--milestone", "M2", "--root", str(repo)], cwd=repo)
            cls.diagram_logs[name] = (d.returncode, d.stdout[-1500:] + d.stderr[-1500:])
            cls.runs[name] = Run(["--milestone", "M2", "--root", str(repo)], cwd=repo, out=repo / f"sorts_{name}")
        cls.rollup_facts = orig[rollup]
        cls.rollup_actions = {a["name"] for a in orig[rollup]["actions"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def ran(self, name: str) -> Run:
        code, log = self.diagram_logs[name]
        self.assertEqual(code, 0, f"holon diagram on the {name} copy failed:\n{log}")
        r = self.runs[name]
        self.assertEqual(r.code, 0, f"{name}: {r.log}")
        return r

    def conflicts(self, r: Run) -> Counter:
        return Counter((c["model"], c["kind"], c.get("src"), len(c["core"])) for c in r.doc("conflicts")["conflicts"])

    def test_stripping_hand_hints_changes_nothing(self):
        """strip: the frozen assignment (sorts_sha256 included), the sites, the unions, the unresolved variables
        and the conflicts are those of the baseline."""
        base, strip = self.ran("baseline"), self.ran("strip")
        self.assertEqual(without(strip.doc("assignment"), "inputs"), without(base.doc("assignment"), "inputs"))
        self.assertEqual(strip.doc("assignment")["sorts_sha256"], base.doc("assignment")["sorts_sha256"])
        self.assertEqual(without(strip.doc("unions"), "inputs"), without(base.doc("unions"), "inputs"))
        self.assertEqual(unresolved_set(strip), unresolved_set(base))
        self.assertEqual(self.conflicts(strip), self.conflicts(base))

    def test_erasing_the_ghost_tag_changes_no_other_sort(self):
        """ghost: only the ghost variables disappear; every other sort, the bvh union, the sites and the conflicts
        are those of the baseline."""
        base, ghost = self.ran("baseline"), self.ran("ghost")
        m = "morph_rollup"
        req = set(required_keys(self.rollup_facts))
        A0, A1 = base.assignment(m), ghost.assignment(m)
        kept = req - GHOST_KEYS
        for k in sorted(kept):
            with self.subTest(var=k):
                self.assertIn(k, A0)
                self.assertEqual(A1.get(k), A0[k])
        for k in sorted(GHOST_KEYS):
            self.assertNotIn(k, A1, "an erased ghost variable is not assigned")
        self.assertLessEqual(set(A1), set(A0), "erasing the ghost adds no variable")
        for other in ("morph_header", "morph_batchdata"):
            self.assertEqual(ghost.assignment(other), base.assignment(other), other)

        def bvh_unions(r):
            return sorted((tuple(u["members"]), tuple(sorted(set(u["vars"]) & kept)))
                          for u in r.doc("unions")["unions"] if u["model"] == m and "Entry.bvh" in u["vars"])
        self.assertTrue(bvh_unions(base), "the baseline has a union holding Entry.bvh")
        self.assertEqual(bvh_unions(ghost), bvh_unions(base))
        s0 = {site_key(s): site_value(s) for s in base.doc("assignment")["sites"]}
        s1 = {site_key(s): site_value(s) for s in ghost.doc("assignment")["sites"]}
        self.assertEqual(s1, s0)
        self.assertEqual(self.conflicts(ghost), self.conflicts(base))

    def test_renaming_fact_identifiers_renames_the_assignment_and_nothing_else(self):
        """rename: every contract variable keeps its sort under the renaming; sites (expressions renamed),
        unions, unresolved variables and conflicts are those of the baseline."""
        base, ren = self.ran("baseline"), self.ran("rename")
        m = "morph_rollup"
        acts = self.rollup_actions
        req = set(required_keys(self.rollup_facts))
        renamed_req = {rename_key(k, acts) for k in req}
        A0, A1 = base.assignment(m), ren.assignment(m)
        for k in sorted(req):
            with self.subTest(var=k):
                self.assertIn(k, A0)
                self.assertEqual(A1.get(rename_key(k, acts)), A0[k])
        for other in ("morph_header", "morph_batchdata"):
            self.assertEqual(ren.assignment(other), base.assignment(other), other)
        leaf = lambda s: LEAF_RN.get(s, s)  # noqa: E731
        s0 = {(s["model"], s["span"], json.dumps(map_expr(s["expr"], leaf) if s["model"] == m else s["expr"],
                                                  sort_keys=True)): site_value(s) for s in base.doc("assignment")["sites"]}
        s1 = {site_key(s): site_value(s) for s in ren.doc("assignment")["sites"]}
        self.assertEqual(s1, s0)

        def unions(r, renamed: bool):
            out = []
            for u in r.doc("unions")["unions"]:
                vs = list(u["vars"])
                if u["model"] == m:
                    vs = [v for v in vs if v in renamed_req] if renamed else [rename_key(v, acts) for v in vs if v in req]
                out.append((u["model"], tuple(u["members"]), tuple(sorted(vs))))
            return sorted(out)
        self.assertEqual(unions(ren, True), unions(base, False))

        def unresolved(r, renamed: bool):
            out = set()
            for model, var, base_type in unresolved_set(r):
                if model == m:
                    if renamed and var not in renamed_req or not renamed and var not in req:
                        continue
                    var = var if renamed else rename_key(var, acts)
                out.add((model, var, base_type))
            return out
        self.assertEqual(unresolved(ren, True), unresolved(base, False))
        self.assertEqual(self.conflicts(ren), self.conflicts(base))


def unresolved_set(r: Run) -> set:
    return {(e["model"], e["var"], e.get("base_type")) for e in r.doc("unresolved")["unresolved"]}


if __name__ == "__main__":
    unittest.main()
