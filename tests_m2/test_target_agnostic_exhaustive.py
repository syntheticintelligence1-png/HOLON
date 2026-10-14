"""Audit M2/1 F-M2-14: the Morph-identifier grep is exhaustive (I6-P3, re-scored as a Surprise in docs/iterations/I6.md).

The preregistered I6 grep (tests_m2/test_target_agnostic.py) reads 11 hand-listed files with a hand-written regex
that holds no state, def or observer name, so mcanary's Morph field list passed it. This test reads every module of
holon/ (holon/**/*.py and holon/js/*.mjs) and derives the identifiers from the target itself:

  * spec/M1/facts/*.json: state fields, types (and their generated model names H<type>), defs, observers, actions,
    migrations and parameters;
  * spec/M1/lib/*.lib.json: builtin names;
  * the target's own names: Rollup, Morph, morph, batchdata.

It reads code: identifiers and string literals; Python comments and docstrings, and JS comments, are documentation
and may cite the Morph example. Two lists are explicit and reported here, so a reader sees every exception:

  GENERIC   identifiers of the target that are ordinary words of generic code: single letters (t, w, D, F, W, Z),
            `log` (every generated machine's own log field: holon.gen.machine requires one), and common words the
            generic modules use in their ordinary sense (append, ctx, classes, view, live, heap, snap, active, wait,
            legacy).
  ALLOWLIST the modules that are replay adapters for this target (they drive the real Morph code, so they name it)
            and the one pinned emitted text, each with the identifiers it may hold.

A listed file that is missing fails (a rename must update the list).
"""
import ast
import io
import json
import re
import tokenize
import unittest

from tests_m2._m2 import ROOT

GENERIC = {"t", "w", "D", "F", "W", "Z", "log", "append", "ctx", "classes", "view", "live", "heap", "snap", "active",
           "wait", "legacy"}
# replay adapters (whitepaper §8.7; BUILD_PLAN I40 replaces their hand op tables with generated harness encoders)
ADAPTERS = ["holon/replay.py", "holon/mreplay.py", "holon/consumers.py", "holon/refinement.py",
            "holon/oracles/zero_blob.py"]
ALLOWLIST: dict[str, list[str]] = {
    # the --morph checkout flags of the replay adapters' commands (replay, refine, oracle zero-blob)
    "holon/__main__.py": ["morph"],
    # the M0 commit-side trace builder (replay evidence for the M0 codec witnesses on the real Rollup)
    "holon/evidence.py": ["commitBatch", "fsr"],
    # the M1 deadline class's emitted comment "kappa = b && w + start(chs[i]) < t" is part of gen/M1, pinned byte for
    # byte (tests_m2/test_target_agnostic.py GEN_PIN); M2+ use deadline_linear, which names no field
    "holon/gen/mproofs.py": ["chs", "kappa"],
    # I24's preregistered contract fixes the cycle-rank key 'kappa' (|E| - |V| + kappa, the number of connected
    # components; spec/M3/lib/par_basis.json, laws/M3/DERIVATION.json cycle_rank): graph theory, not a Morph field
    "holon/rules/__init__.py": ["kappa"],
    "holon/rules/par.py": ["kappa"],
}
TARGET_NAMES = {"Rollup", "Morph", "morph", "batchdata"}


def identifiers() -> set:
    out = set(TARGET_NAMES)
    for f in sorted((ROOT / "spec" / "M1" / "facts").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out |= {s[0] for s in d.get("state", [])}
        out |= set(d.get("defs", {})) | set(d.get("observers", {})) | set(d.get("migrations", {}))
        out |= set(d.get("types", {})) | {"H" + t for t in d.get("types", {})} | set(d.get("params", {}))
        out |= {a["name"] for a in d.get("actions", [])}
    for f in sorted((ROOT / "spec" / "M1" / "lib").glob("*.lib.json")):
        out |= set(json.loads(f.read_text(encoding="utf-8")).get("builtins", {}))
    return out - GENERIC


def code_py(text: str) -> str:
    """Python source without comments and docstrings (module, class and function docstrings)."""
    lines = text.splitlines(keepends=True)
    drop: set = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                drop |= set(range(first.lineno - 1, first.end_lineno))
    src = "".join("\n" if i in drop else line for i, line in enumerate(lines))
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type != tokenize.COMMENT]
    return tokenize.untokenize(toks)


def code_js(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<![:\\])//[^\n]*", "", text)


def modules() -> list:
    return sorted(list((ROOT / "holon").rglob("*.py")) + list((ROOT / "holon" / "js").glob("*.mjs")))


class TestNoMorphIdentifierAnywhere(unittest.TestCase):
    def test_identifier_set_is_derived_from_the_target(self):
        ids = identifiers()
        for must in ("s_bvh", "s_tag", "inch", "qlen", "kappa", "lci", "win_at", "nth_ch", "agg", "commitBatch",
                     "HEntry", "Entry", "AGG_BASE", "eta2"):
            self.assertIn(must, ids)
        self.assertGreater(len(ids), 50)

    def test_listed_files_exist(self):
        for rel in ADAPTERS + list(ALLOWLIST):
            with self.subTest(file=rel):
                self.assertTrue((ROOT / rel).is_file(), f"{rel} is listed but missing: update the list")

    def test_generic_code_holds_no_morph_identifier(self):
        ids = identifiers()
        pat = re.compile(r"(?<![\w$])(" + "|".join(sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![\w$])")
        mods = modules()
        self.assertGreater(len(mods), 60)
        for f in mods:
            rel = f.relative_to(ROOT).as_posix()
            if rel in ADAPTERS:
                continue
            text = f.read_text(encoding="utf-8")
            code = code_py(text) if f.suffix == ".py" else code_js(text)
            with self.subTest(file=rel):
                self.assertEqual(sorted(set(pat.findall(code))), sorted(ALLOWLIST.get(rel, [])))

    def test_the_audit_mutations_are_caught(self):
        """The audit's mutation: a MORPH_SPECIAL table in holon/gen/core.py and a commitBatch case in
        holon/js/policy_gen.mjs passed the I6 grep; here both are found."""
        ids = identifiers()
        pat = re.compile(r"(?<![\w$])(" + "|".join(sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![\w$])")
        py = (ROOT / "holon" / "gen" / "core.py").read_text() + '\nMORPH_SPECIAL = {"commitBatch": "win_at", "Rollup": "nth_ch"}\n'
        js = (ROOT / "holon" / "js" / "policy_gen.mjs").read_text() + '\nif (a.name === "commitBatch") { w = 1; }\n'
        self.assertEqual(sorted(set(pat.findall(code_py(py)))), ["Rollup", "commitBatch", "nth_ch", "win_at"])
        self.assertEqual(sorted(set(pat.findall(code_js(js)))), ["commitBatch"])
        old = "LIVE_FIELDS = [\"s_bvh\", \"s_tag\", \"t\", \"paused\", \"inch\", \"qlen\"]\n"
        self.assertEqual(sorted(set(pat.findall(code_py(old)))), ["inch", "paused", "qlen", "s_bvh", "s_tag"])


if __name__ == "__main__":
    unittest.main()
