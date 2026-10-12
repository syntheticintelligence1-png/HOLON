"""I17 honesty (construction checks, not counted; AGENTS rules 2 and 4; contract: tests_m2/test_extract_solidity_layout.py).

The frontend's inputs are the compiler's output and the source tree. It must not name the target (its vocabulary lives
only in the frozen sidecar spec/M2/lib/extract_solidity.json), must not read a fact document, law, result or generated
file, and the sidecar must state nothing the extraction is supposed to find.

- Vocabulary: every name the pinned checkout declares in the codec sources that is distinctive (tests_m2/_i17.py
  distinctive: batchPtr, BatchHeaderCodecV0, storeBatchIndex, BATCH_HEADER_LENGTH, ...), the frozen header facts'
  function and field names when distinctive, the sidecar's edge names, every require/revert message of three or more
  words of Rollup.sol and the two codec libraries, the layout constants 249 and 257, any "<file>.sol:<line>" span and the word morph (any case)
  are absent from holon/frontends/__init__.py and every file of holon/frontends/solidity/, docstrings and comments
  included.
- Imports: those files import no module that reads fact documents or results (holon.facts, holon.layout,
  holon.diagram, holon.sorts, holon.gen, holon.model_eval, holon.records, holon.pipeline, holon.mpipeline,
  holon.replay, holon.mreplay, holon.refinement, holon.evidence), and I17's own modules (FRONTEND_FILES) import no
  analysis tool (slither, crytic_compile, z3, solcx); a later SlithIR module of I19 under holon/frontends/solidity/
  may, if it is imported lazily (I17's extraction must still load none: test_extract_toolchain.py).
- Reads: under a Python audit hook, `holon extract` opens, inside the HOLON checkout, only holon/ (its own modules),
  config/, spec/schemas/ and the sidecar (and, for the toy, the toy fixture directory); it starts the pinned solc.
- Poison: in a copy whose frozen fact documents (facts/*.json, spec/M1/facts/*.json) and committed extraction are
  overwritten with junk, the extraction writes exactly the committed bytes.
- Mutation (reviewer addition at the prereg): on a scratch copy of the pinned contracts with a store offset, a library
  length constant, the version bound and a store formal's name changed (tests_m2/_i17.py MUTATION_EDITS and
  MUTATION_RENAME), the document moves exactly where the code moved and nowhere else.
"""
import ast
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i17 as H
from tests_m2._i16 import morph_checkout
from tests_m2._m2 import ROOT, copy_repo, load_json

FRONTEND_FILES = ("holon/frontends/__init__.py", "holon/frontends/solidity/__init__.py",
                  "holon/frontends/solidity/compile.py", "holon/frontends/solidity/ast.py",
                  "holon/frontends/solidity/layout_extract.py")
FACT_READERS = ("holon.facts", "holon.layout", "holon.diagram", "holon.sorts", "holon.gen", "holon.model_eval",
                "holon.records", "holon.pipeline", "holon.mpipeline", "holon.replay", "holon.mreplay",
                "holon.refinement", "holon.evidence")
ANALYSIS_TOOLS = ("slither", "crytic_compile", "z3", "solcx")
# The analysis-tool ban covers I17's own modules (FRONTEND_FILES): I19 may add a SlithIR module under
# holon/frontends/solidity/ (whitepaper 10.1), imported lazily so that I17's extraction still loads no tool
# (tests_m2/test_extract_toolchain.py TestNoToolDependency). The fact-reader ban covers every frontend file.


def frontend_files() -> list[Path]:
    files = [ROOT / f for f in FRONTEND_FILES]
    sol = ROOT / "holon" / "frontends" / "solidity"
    if sol.is_dir():
        files += [f for f in sorted(sol.rglob("*")) if f.is_file() and "__pycache__" not in f.parts and f not in files]
    return files


def imported_modules(path: Path) -> set[str]:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    pkg = parts[:-1]   # the package the module belongs to (for __init__.py: the package itself)
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[:len(pkg) - (node.level - 1)] if node.level > 1 else pkg
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            out.add(mod)
            out |= {f"{mod}.{a.name}" for a in node.names}
    return out


class TestGenericFrontendCode(unittest.TestCase):
    def test_frontend_code_holds_no_target_vocabulary(self):
        morph = morph_checkout()
        vocab = H.target_vocabulary(morph) | set(load_json(H.SIDECAR)["edges"])
        for must in ("BatchHeaderCodecV0", "storeBatchIndex", "BATCH_HEADER_LENGTH", "_commitBatchWithBatchData",
                     "batchPtr", "enc_sol", "load_sol", "batchIndex", "sequencerSetVerifyHash", "loadAndValidate"):
            self.assertIn(must, vocab, "the instrument derives the vocabulary")
        msgs = H.revert_messages(morph)
        self.assertIn("invalid version", msgs)
        msgs = {m for m in msgs if len(m.split()) >= 3}   # two-word texts ("invalid version") are ordinary prose
        word = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, vocab), key=len, reverse=True))
                          + r")(?![A-Za-z0-9_])")
        for f in frontend_files():
            rel = f.relative_to(ROOT).as_posix()
            with self.subTest(file=rel):
                self.assertTrue(f.exists(), f"{rel} is missing")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(sorted(set(word.findall(text))), [])
                self.assertEqual(re.findall(r"(?<![\w.])(249|257)(?![\w.])", text), [])
                self.assertIsNone(re.search(r"\.sol:\d", text))
                self.assertIsNone(re.search(r"(?i)morph", text))
                self.assertEqual(sorted(m for m in msgs if m in text), [])

    def test_frontend_code_imports_no_fact_reader_and_no_analysis_tool(self):
        for f in frontend_files():
            rel = f.relative_to(ROOT).as_posix()
            with self.subTest(file=rel):
                self.assertTrue(f.exists(), f"{rel} is missing")
                if f.suffix != ".py":
                    continue
                mods = imported_modules(f)
                banned = FACT_READERS + (ANALYSIS_TOOLS if rel in FRONTEND_FILES else ())
                bad = sorted(m for m in mods for x in banned if m == x or m.startswith(x + "."))
                self.assertEqual(bad, [])
                text = f.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"facts/morph_header|spec/M[01]\b|laws/M\d|results/M\d|gen/M\d", text))


ALLOWED = ("holon/", "config/", "spec/schemas/", "spec/M2/lib/extract_solidity.json")


class TestExtractionReads(unittest.TestCase):
    def _check(self, args: list[str], extra_allowed: tuple = ()) -> tuple[list, list]:
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-reads-"))
        try:
            code, opened, execs = H.opened_during(["extract", *args, "--out", str(tmp / "o.json")])
            self.assertEqual(code, 0, f"exit {code}; opened {opened[-20:]}")
            root = os.path.realpath(ROOT) + os.sep
            inside = sorted({p[len(root):] for p, _ in opened if p.startswith(root)})
            bad = [p for p in inside if not p.startswith(ALLOWED + extra_allowed)]
            self.assertEqual(bad, [], "the extraction read files it must not read")
            for argv in execs:
                for a in argv:
                    if a.startswith(root):
                        self.assertTrue(a[len(root):].startswith(ALLOWED + extra_allowed), f"a process got {a}")
            return inside, execs
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_extraction_opens_no_fact_document(self):
        inside, execs = self._check(H.morph_args())
        self.assertIn(H.SIDECAR_REL, inside, "the hook saw the sidecar being read (it works)")
        solc = os.path.realpath(load_json(ROOT / "config" / "holon.json")["replay"]["solc"])
        self.assertTrue(any(argv and os.path.realpath(argv[0]) == solc for argv in execs), f"solc not run: {execs}")

    def test_the_toy_extraction_opens_only_the_toy(self):
        toy = H.TOY.relative_to(ROOT).as_posix() + "/"
        inside, _ = self._check(H.toy_args(), (toy,))
        self.assertIn(H.TOY_SIDECAR.relative_to(ROOT).as_posix(), inside)

    def test_poisoned_fact_documents_change_no_byte(self):
        repo = copy_repo()
        try:
            junk = '{"poisoned": "the extractor must not read this file"}\n'
            targets = sorted((repo / "facts").glob("*.json")) + sorted((repo / "spec" / "M1" / "facts").glob("*.json"))
            targets.append(repo / H.OUTPUT_REL)
            self.assertGreaterEqual(len(targets), 4)
            for p in targets:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(junk)
            run = H.Extract(H.morph_args(), cwd=repo)
            try:
                self.assertEqual(run.code, 0, run.log)
                self.assertTrue(H.OUTPUT.exists(), f"{H.OUTPUT_REL} is not committed")
                self.assertEqual(run.bytes(), H.OUTPUT.read_bytes())
            finally:
                run.cleanup()
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestMutations(unittest.TestCase):
    def test_a_mutated_codec_moves_the_extraction_and_nothing_else(self):
        """The extraction follows the code (reviewer addition at the prereg): on a scratch copy of the pinned contracts
        with a store offset moved (storeBlobVersionedHash 57 -> 58), BatchHeaderCodecV0.BATCH_HEADER_LENGTH 249 -> 250,
        the version bound 2 -> 3 and the formal _withdrawRootHash renamed _exitRootHash (tests_m2/_i17.py
        MUTATION_EDITS, MUTATION_RENAME; sidecar copy with target.commit null), the document differs from the committed
        one exactly there: that op's offset, the version-0 ok length and the loader's version-0 bound, the invalid-version
        condition, the field name; types, every other path, op, walk and assumption are equal."""
        self.assertTrue(H.OUTPUT.exists(), f"{H.OUTPUT_REL} is not committed")
        base = load_json(H.OUTPUT)
        tmp, src = H.mutated_source(morph_checkout())
        try:
            run = H.Extract(["solidity", "--sidecar", str(tmp / "extract_solidity.json"), "--source", str(src)])
            try:
                self.assertEqual(run.code, 0, run.log)
                mut = run.doc()
            finally:
                run.cleanup()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIsNone(mut["target"]["commit"])
        enc, load = mut["functions"]["enc_sol"], mut["functions"]["load_sol"]
        moved = [op for p in enc["paths"] if p["outcome"] == "ok" for op in p["ops"]
                 if op["origin"]["fn"] == "BatchHeaderCodecV0.storeBlobVersionedHash"]
        self.assertEqual(sorted({op["offset"] for op in moved}), [58], moved)
        names = [f["name"] for f in mut["types"][enc["from"]]["fields"]]
        self.assertIn("exitRootHash", names)
        self.assertNotIn("withdrawRootHash", names)
        inv = [p for p in enc["paths"] if p["outcome"] == "revert" and p["reason"] == "invalid version"]
        self.assertEqual([p["cond"] for p in inv], [[["!", ["<=", "version", 3]]]])
        self.assertEqual(sorted(p["length"] for p in enc["paths"] if p["outcome"] == "ok"), [250, 257])
        for length in (248, 249, 250, 251, 257):
            for b0 in (0, 1, 2, 3):
                got = H.loader_outcome(load, "batchHeader", b0, length)["outcome"] == "ok"
                want = (b0 == 0 and length >= 250) or (b0 in (1, 2) and length == 257)
                self.assertEqual(got, want, (b0, length))
        # back to the committed form: nothing else moved
        norm = H.replace_exact(mut, "exitRootHash", "withdrawRootHash")
        e = norm["functions"]["enc_sol"]
        e["paths"] = H.replace_exact(e["paths"], ["<=", "version", 3], ["<=", "version", 2])
        for p in e["paths"]:
            if p["outcome"] == "ok":
                p["length"] = 249 if p["length"] == 250 else p["length"]
                for op in p["ops"]:
                    if op["origin"]["fn"] == "BatchHeaderCodecV0.storeBlobVersionedHash":
                        op["offset"] = 57
        ld = norm["functions"]["load_sol"]
        for p in ld["paths"]:
            p["cond"] = H.replace_int(p["cond"], 250, 249)
        for key in ("types", "functions", "assumptions"):
            with self.subTest(key=key):
                self.assertEqual(norm[key], base[key])


class TestSidecar(unittest.TestCase):
    def test_the_sidecar_states_no_layout_fact(self):
        """The frozen sidecar names entries, edges and sinks only: no Header field name, no Maybe/length/offset
        vocabulary and no integer other than sidecar_version."""
        side = load_json(H.SIDECAR)
        fields = {f["name"] for f in H.frozen()["types"]["Header"]["fields"]}
        strings, ints = [], []

        def walk(x, key=None):
            if isinstance(x, dict):
                for k, v in x.items():
                    walk(v, k)
            elif isinstance(x, list):
                for v in x:
                    walk(v, key)
            elif isinstance(x, bool):
                pass
            elif isinstance(x, int):
                ints.append((key, x))
            elif isinstance(x, str):
                strings.append(x)
        walk(side)
        self.assertEqual(ints, [("sidecar_version", 1)])
        for s in strings:
            for f in sorted(fields):
                self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){re.escape(f)}(?![A-Za-z0-9_])", s), (f, s))
            self.assertIsNone(re.search(r"(?<![\w.])(249|257|185|217)(?![\w.])", s), s)
        self.assertEqual(side["frontend"], "solidity")
        self.assertEqual(side["output"], H.OUTPUT_REL)


if __name__ == "__main__":
    unittest.main()
