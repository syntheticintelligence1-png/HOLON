"""I18 honesty and toolchain construction checks (I18-R5, I18-R7). Contract: the docstring of
tests_m2/test_extract_go.py (Toolchain, Honesty).

- Generic code: holon/frontends/go/ holds no name of the target sidecar spec/M2/lib/go_frontend.json (its repo,
  document stems, import paths, primitive names), no Morph identifier, no header or blob constant, no source span,
  and imports no test oracle. The target's vocabulary lives only in the sidecar.
- Toolchain pin: holon/frontends/go/ssadump is exactly main.go, go.mod and go.sum, requiring golang.org/x/tools
  v0.36.0 with the go.sum hashes verified at the prereg; there is no vendored tree and no bun configuration; a go
  that is not the pinned version makes the extractor exit 2 and write nothing.
- Mutations (on scratch copies of the pinned Morph tree; the checkout is never touched):
    semantic  BatchHeaderV1.Bytes writes version byte 2, expectedLengthV0 becomes 250, and the blob retrieval error
              path indexes the blob instead of the buffer: the layouts, the predicate's accepted points, the
              absences and the O4 site follow the code;
    rename    BatchData, validate, EncodedBytes, blockContexts, txsPayload and TxsPayloadV2 renamed to unique
              tokens of the same length: every document equals the committed one once the tokens are mapped back
              (extraction.inputs aside), so no rule keys on a name.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i18 as H

CB, NT, GEN = "morph-l2/common/batch", "morph-l2/node/types", "morph-l2/morph-deployer/morph-chain-ops/genesis"
V0, V1 = f"({CB}.BatchHeaderV0).Bytes", f"({CB}.BatchHeaderV1).Bytes"
VALIDATE = f"({CB}.BatchHeaderBytes).validate"
GENESIS = f"{GEN}.GenesisBatchHeader"
SEMANTIC = (("common/batch/batch_header.go", "\tbatchBytes[0] = BatchHeaderVersion1\n",
             "\tbatchBytes[0] = BatchHeaderVersion2\n"),
            ("common/batch/batch_header.go", "\texpectedLengthV0 = 249\n", "\texpectedLengthV0 = 250\n"),
            ("common/batch/blob.go", "of field element %d\", data[i*32], i)", "of field element %d\", blob[i*32], i)"))
RENAME = {"BatchData": "Qzqqqqqqq", "validate": "qzzzzzzz", "EncodedBytes": "Qzeeeeeeeeee",
          "blockContexts": "qzbbbbbbbbbbb", "txsPayload": "qzpppppppp", "TxsPayloadV2": "Qzvvvvvvvvvv"}
RENAME_ELSEWHERE = {"node/derivation": ("TxsPayloadV2",)}


def canon(x):
    """Order-insensitive canonical form: lists become sorted lists of canonical elements."""
    if isinstance(x, dict):
        return {k: canon(v) for k, v in x.items()}
    if isinstance(x, list):
        return sorted((canon(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    return x


def without_inputs(doc: dict) -> dict:
    d = json.loads(json.dumps(doc))
    d["extraction"].pop("inputs", None)
    return d


class TestGenericCode(unittest.TestCase):
    def test_the_frontend_holds_no_target_vocabulary(self):
        files = H.frontend_sources()
        rels = [p.relative_to(H.ROOT).as_posix() for p in files]
        for need in ("holon/frontends/go/extract.py", "holon/frontends/go/ssadump/main.go"):
            self.assertIn(need, rels)
        vocab = sorted(H.config_vocabulary(H.load_json(H.CONFIG)), key=len, reverse=True)
        self.assertTrue(vocab)
        for p in files:
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.relative_to(H.ROOT).as_posix()):
                self.assertEqual([w for w in vocab if re.search(rf"(?<![\w/.-]){re.escape(w)}(?![\w/-])", text)], [])
                self.assertEqual(sorted(set(H.MORPH_WORDS.findall(text))), [])
                self.assertEqual(sorted(set(H.MAGIC_NUMBERS.findall(text))), [])
                self.assertIsNone(H.SPAN_TEXT.search(text))
                self.assertNotRegex(text, r"\btests(_m\d+)?\b\.|from tests|import tests")

    def test_the_sidecar_is_the_only_target_vocabulary(self):
        cfg = H.load_json(H.CONFIG)
        self.assertEqual(cfg["config_version"], "holon-go-frontend/0.1")
        self.assertEqual(sorted(cfg["documents"]), ["morph_batch", "morph_blob", "morph_derivation", "morph_genesis",
                                                     "morph_nodetypes"])
        for name, p in cfg["primitives"].items():
            self.assertIn(p["kind"], ("to_array", "hash", "array_bytes"), name)
            self.assertNotRegex(name, r"^\(?\*?(encoding/binary|errors|fmt)\.",
                                "standard-library semantics belong to the generic frontend, not the sidecar")


class TestToolchainPin(unittest.TestCase):
    def test_ssadump_holds_exactly_the_pinned_module(self):
        self.assertTrue(H.SSADUMP.is_dir(), H.SSADUMP)
        self.assertEqual(sorted(p.name for p in H.SSADUMP.iterdir()), ["go.mod", "go.sum", "main.go"])
        mod = (H.SSADUMP / "go.mod").read_text()
        self.assertRegex(mod, r"(?m)^go 1\.24(\.0)?$")
        req = re.findall(r"(?m)^\s*(?:require\s+)?golang\.org/x/tools\s+(\S+)(.*)$", mod)
        self.assertEqual([(v, "indirect" in rest) for v, rest in req], [(H.X_TOOLS, False)])
        lines = [ln.strip() for ln in (H.SSADUMP / "go.sum").read_text().splitlines() if ln.strip()]
        self.assertEqual([ln for ln in lines if ln not in H.GO_SUM_ALLOWED], [])
        for ln in H.GO_SUM_REQUIRED:
            self.assertIn(ln, lines)
        main = (H.SSADUMP / "main.go").read_text()
        for imp in ("golang.org/x/tools/go/packages", "golang.org/x/tools/go/ssa"):
            self.assertIn(f'"{imp}"', main)
        self.assertIn(H.SSADUMP_VERSION, main)

    def test_no_vendored_tree_and_no_bun_configuration(self):
        front = H.ROOT / "holon" / "frontends"
        self.assertTrue(front.is_dir(), front)
        found = [p.relative_to(H.ROOT).as_posix() for p in front.rglob("*")
                 if p.name == "vendor" or p.name == "bunfig.toml" or p.name.startswith(".env")]
        self.assertEqual(found, [])
        binaries = [p.relative_to(H.ROOT).as_posix() for p in front.rglob("*")
                    if p.is_file() and p.stat().st_mode & stat.S_IXUSR and p.suffix not in (".py", ".go")]
        self.assertEqual(binaries, [], "built tools live under ~/.holon/tools, never in the repo")

    def test_a_go_that_is_not_the_pinned_version_is_refused(self):
        fake = Path(tempfile.mkdtemp(prefix="holon-i18-fakego-"))
        try:
            (fake / "go").write_text("#!/bin/sh\nif [ \"$1\" = version ]; then echo 'go version go1.0 linux/amd64'; "
                                     "exit 0; fi\nexit 1\n")
            (fake / "go").chmod(0o755)
            out = fake / "out"
            out.mkdir()
            env = dict(os.environ)
            env["PATH"] = str(fake) + os.pathsep + env.get("PATH", "")
            env["PYTHONPATH"] = str(H.ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            p = subprocess.run([sys.executable, "-m", "holon", "extract", "go", "--root", str(H.ROOT), "--config",
                                str(H.TOY_CONFIG), "--out-dir", str(out)], cwd=H.ROOT, env=env, capture_output=True,
                               text=True, timeout=600)
            self.assertEqual(p.returncode, 2, p.stdout[-1000:] + p.stderr[-1000:])
            self.assertEqual(list(out.iterdir()), [])
            self.assertRegex(p.stdout + p.stderr, r"go1\.24\.7|go version")
        finally:
            shutil.rmtree(fake, ignore_errors=True)


class _Mutated(unittest.TestCase):
    @staticmethod
    def mutated_run(edits) -> "H.Run":
        morph = H.morph_checkout()
        tmp = Path(tempfile.mkdtemp(prefix="holon-i18-mut-"))
        src = H.copy_go_tree(morph, tmp / "src")
        for rel, old, new in edits:
            p = src / rel
            text = p.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise AssertionError(f"{rel}: the mutation anchor {old!r} occurs {text.count(old)} times")
            p.write_text(text.replace(old, new), encoding="utf-8")
        run = H.Run.morph(src=src)
        run.src_tmp = tmp
        return run

    @staticmethod
    def committed() -> dict:
        docs = {}
        for stem in ("morph_batch", "morph_blob", "morph_derivation", "morph_genesis", "morph_nodetypes"):
            p = H.FACTS_DIR / f"{stem}.go.extracted.json"
            if not p.exists():
                raise AssertionError(f"{p.relative_to(H.ROOT)} is not committed")
            docs[stem] = json.loads(p.read_text(encoding="utf-8"))
        return docs


class TestMutations(_Mutated):
    def test_a_mutated_source_moves_the_extraction(self):
        base = self.committed()
        r = self.mutated_run(SEMANTIC)
        try:
            docs = r.need()
            enc = {e["function"]: e for e in H.section(docs, "codecs", "encoders") if e["function"] in (V0, V1)}
            benc = {e["function"]: e for e in H.section(base, "codecs", "encoders") if e["function"] in (V0, V1)}
            self.assertEqual(enc[V1]["cells"][0], ["const", 2])
            self.assertEqual(enc[V1]["cells"][1:], benc[V1]["cells"][1:])
            self.assertEqual(enc[V0]["length"], 250)
            self.assertEqual(enc[V0]["cells"], benc[V0]["cells"] + [["const", 0]])
            b = docs["morph_batch"]["go"]["codecs"]
            self.assertEqual([p["accepts"] for p in b["predicates"] if p["function"] == VALIDATE],
                             [[{"value": 0, "length": 250}, {"value": 1, "length": 257}, {"value": 2, "length": 257}]])
            self.assertEqual(b["absences"], [{"predicate": VALIDATE, "index": 0, "value": 1, "length": 257,
                                              "elsewhere": []}])
            nt = docs["morph_nodetypes"]["go"]["codecs"]["absences"]
            self.assertEqual([(a["value"], a["length"], a["elsewhere"]) for a in nt],
                             [(0, 249, []), (1, 257, []), (2, 257, [V1, GENESIS])])
            sites = H.function(docs, f"{CB}.RetrieveBlobBytes")["sites"]
            self.assertEqual([s["status"] for s in sites], ["safe"] * 4)
        finally:
            r.cleanup()
            shutil.rmtree(r.src_tmp, ignore_errors=True)

    def test_renaming_identifiers_renames_the_extraction_and_nothing_else(self):
        base = self.committed()
        edits = []
        morph = H.morph_checkout()
        for f in sorted((morph / "common" / "batch").glob("*.go")):
            if f.name.endswith("_test.go"):
                continue
            text = f.read_text(encoding="utf-8")
            new = text
            for old, tok in RENAME.items():
                new = re.sub(rf"\b{old}\b", tok, new)
            if new != text:
                edits.append((f.relative_to(morph).as_posix(), text, new))
        for d, names in RENAME_ELSEWHERE.items():
            for f in sorted((morph / d).glob("*.go")):
                if f.name.endswith("_test.go"):
                    continue
                text = f.read_text(encoding="utf-8")
                new = text
                for old in names:
                    new = re.sub(rf"\b{old}\b", RENAME[old], new)
                if new != text:
                    edits.append((f.relative_to(morph).as_posix(), text, new))
        self.assertTrue(edits)
        r = self.mutated_run(edits)
        try:
            docs = r.need()
            back = {v: k for k, v in RENAME.items()}
            pat = re.compile("|".join(map(re.escape, sorted(back, key=len, reverse=True))))
            for stem, d in docs.items():
                with self.subTest(doc=stem):
                    text = pat.sub(lambda m: back[m.group(0)], json.dumps(without_inputs(d), sort_keys=True,
                                                                           ensure_ascii=False))
                    self.assertEqual(canon(json.loads(text)), canon(without_inputs(base[stem])))
        finally:
            r.cleanup()
            shutil.rmtree(r.src_tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
