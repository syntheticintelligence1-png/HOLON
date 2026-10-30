"""I91 (= I38c): the compression oracle, HypZ and HypZ_len, tested on the real codec at the bound the code implies
(BUILD_PLAN rows I91 and I93; whitepaper §8.5 the compression hypotheses, §8.3 oracles as parameters, §11.3 O5, §11.6;
distinct from D2's Hyp-Z0-kzg). This docstring is the contract.

Scope. A model of the batch codec takes the compressor Enc and the decompressor Dec as uninterpreted parameters and two
hypotheses about them as premises. HypZ: forall x non-empty, k <= K. Dec(Enc x ++ 0^k) = x (the derivation decompresses
the concatenated blob bodies, so a compressed payload arrives followed by the zero bytes of its last blob). HypZ_len:
|Enc x| is at most zstd's compress bound of |x|. I91 states both with the bound K the pinned code implies and tests
them, without a proof, on the real codec: the submitter's compressor and the derivation's decompressor, which link the
real zstd, with the real blob pipeline between them. It writes one results document and changes no law, record, rule
catalog, frontend, Go document or model. O5, O6, D3 and the frontend 0.3 config are I93 (BUILD_PLAN).

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i91.py and its Go file tests_m3/fixtures/compression/holon_i91_instrument.go.txt
(the capacity as the source text declares it, the sample inputs, what the real codec and pipeline do on the sample, and
the entries those outcomes give), written without holon/.

Z1 Sidecar. spec/M3/lib/compression.json (compression_version holon-compression/0.1): document (the Go document: its
   target commit, and its extraction config's source tree), probe_package (a package of the document), codec {enc, dec,
   split, retrieve: function ids "<package path>.<Name>"; split_blobs: a field name; capacity: a constant id "<package
   path>.<Name>"; library: a module path}, hypotheses {HypZ {statement, K: an expression, ...}, HypZ_len {statement,
   bound {shift, small, small_shift}, ...}} and sample {seed, kinds (zero, ramp, stream, a subset in that order),
   lengths, paddings and beyond (lists of expressions), expansion {kind, limit (an expression), window (an integer
   >= 1)}}. An expression is an integer, C, C-d, C+d or m*C (d, m integers >= 1), C being the capacity constant as the
   compiled code holds it. A sidecar that does not have this shape is refused (exit 2). holon/oracles/compression.py
   holds no target name: every package path, function, field, constant and module name comes from the sidecar, and no
   string literal or identifier of its code contains one of the sidecar's codec values, their package paths or last
   names, or "morph" in any case.
Z2 Probe. holon.oracles.compression writes a Go test in the external test package of probe_package (package
   <name>_test) into a scratch copy of the source tree's go.work modules (holon.frontends.go.extract's workspace: the
   tree clean and at the document's target commit, the toolchain the pinned one), runs it with `go test` and reads its
   JSON output; nothing is written into the source tree. The test reads C from the compiled constant, resolves the
   sample's expressions, and for every kind and length (kinds outer, lengths inner, in sidecar order) builds x (zero: n
   zero bytes; ramp: byte i is i mod 256; stream: the first n bytes of SHA-256(seed || be32(0)) || SHA-256(seed ||
   be32(1)) || ..., seed as UTF-8) and computes c = enc(x); then the blob count b = max(1, ceil(|c| / C)), split(c, b),
   the concatenation p of retrieve(&blob) over its split_blobs in order, dec(p), and dec(c ++ 0^k) for every padding
   and every beyond value k. A point whose enc fails records the error and nothing else. The library's version is the
   one `go list -m` reports for it in the probe package's module.
Z3 Capacity. The results' capacity is {"C": the compiled constant, "K": the value of HypZ's K}. A point records blobs
   (len of split_blobs), padded_len (|p|), padding (|p| - |c|) and padded_ok (whether p is c followed by zero bytes
   only). The build refuses (exit 3) when a padding value of the sample exceeds K or a beyond value does not.
Z4 HypZ. Over the points: "checked" when every point's enc succeeds, its pipeline gives x and dec(c ++ 0^k) gives x for
   every padding k of the sample; else "mismatch". The entry: {statement, K, status, detail, points (how many), decodes
   (how many dec results were compared: the pipeline and the paddings of every point whose enc succeeded), failures:
   the first ten {kind, n, k ("enc", "pipeline" or the padding), got} in point order, the pipeline before the paddings,
   the paddings in sample order}. "checked" is a test on the sample, not a proof. The beyond values are recorded per
   point and never enter a status.
Z5 HypZ_len. Over the points: "checked" when every point's enc succeeds with |c| <= CB(n), CB(n) = n + (n >> shift) +
   (n < small ? (small - n) >> small_shift : 0) from the sidecar's bound; else "mismatch". The entry: {statement,
   status, detail, points, max_excess (the largest |c| - n over the points whose enc succeeded), failures: the first ten
   {kind, n, enc_len (null when enc failed), bound}}.
Z6 Expansion. For the expansion kind, at every length n of the window [L - window + 1, L], L the limit's value, x_n
   as in Z2 and |enc(x_n)|. The results' expansion: {kind, limit: L, window: [L - window + 1, L], enc_len_at_limit,
   overhead (enc_len_at_limit - L), exceeding {count (how many n of the window give |enc(x_n)| > L), min (the least
   such n, or null), interval (true when count >= 1 and they are exactly min..L, else false)}}.
Z7 Empty payload (outside HypZ's domain). The results' empty: {enc_len, enc_nil (whether enc returned a nil slice),
   dec_empty (dec(enc(ε)) against ε), pipeline {blobs, padded_len, zero (whether p is all zero bytes), dec (dec(p)
   against ε)}} for p the concatenation of split(enc(ε), 1); {"enc_error": message} when enc fails, and pipeline
   {"error": outcome} when the split or a retrieve fails.
Z8 Output. `python -m holon oracle compression --milestone M3 [--root DIR] [--check]` writes
   results/M3/compression_oracle.json, holon.oracles.compression.render(build(root, milestone)) (JSON, indent 2, sorted
   keys, one trailing newline): {"compression_oracle_version": "holon-compression-oracle/0.1", sidecar {path, sha256},
   document {path, sha256}, target {repo, commit}, codec (the sidecar's), library {module, version}, toolchain (the go
   version token), capacity, sample {seed, kinds, lengths, paddings, beyond (integers), expansion {kind, limit,
   window}}, points, hypotheses {HypZ, HypZ_len}, expansion, empty, command}. A point: {kind, n, x_sha256, enc_error,
   enc_len, enc_sha256, blobs, padded_len, padding, padded_ok, pipeline, paddings, beyond}; an outcome (pipeline, each
   paddings or beyond value keyed by k in decimal, dec_empty, the empty pipeline's dec) is "ok" (dec gave the expected
   bytes), "differs:<length>" (other bytes) or "error: <message>" (the message cut at 200 characters). No timestamp: two
   runs on one tree give the same bytes. --check exits 1 when the file differs from a fresh build, 0 when it is equal.
   Exit 2: a refused input (sidecar, document, source tree, toolchain); 3: the probe fails to build or run, or Z3's
   refusal.
Z9 Scope. I91's own commits after its prereg (judged at those commits, each against its first parent, along the
   first-parent line of the merge that brings I91 into the lead when there is one) change only
   holon/oracles/compression.py, holon/__main__.py (the dispatch of `oracle compression`),
   results/M3/compression_oracle.json, docs/iterations/I91.md, spec/M3/amendments.jsonl, and docs/M3_COMPARISON.md and
   spec/M3/appendixA_map.json (holon report --milestone M3 after BUILD_PLAN's rows I91 and I93). So no law, record,
   registry, generated model, replay report, Go document or rule catalog changes, and results/M2/hypotheses.json (D2's
   Hyp-Z0-kzg) stays as it is. Only holon/__main__.py imports holon.oracles.compression.

Predictions are in spec/M3/predictions.json under I91; the tests below check them and the rules above.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m3 import _i91 as I

ROOT = Path(__file__).resolve().parents[1]
KEY = "I91"
RESULTS = ROOT / "results" / "M3" / "compression_oracle.json"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "compression.json"
MODULE = ROOT / "holon" / "oracles" / "compression.py"
REPORT = "docs/iterations/I91.md"
ALLOWED = {"holon/oracles/compression.py", "holon/__main__.py", "results/M3/compression_oracle.json", REPORT,
           "spec/M3/amendments.jsonl", "docs/M3_COMPARISON.md", "spec/M3/appendixA_map.json"}
EXPR = re.compile(r"^(?:\d+|C|C[+-]\d+|\d+\*C)$")
FUNC_ID = re.compile(r"^[^\s.]+(?:/[^\s/]+)*\.[A-Za-z_][A-Za-z0-9_]*$")
POINT_KEYS = {"kind", "n", "x_sha256", "enc_error", "enc_len", "enc_sha256", "blobs", "padded_len", "padding",
              "padded_ok", "pipeline", "paddings", "beyond"}
TOP_KEYS = {"compression_oracle_version", "sidecar", "document", "target", "codec", "library", "toolchain", "capacity",
            "sample", "points", "hypotheses", "expansion", "empty", "command"}


def load(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def committed() -> dict:
    if not RESULTS.exists():
        raise AssertionError(f"{RESULTS.relative_to(ROOT)} is not written (rule Z8)")
    return load(RESULTS)


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I91 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I91")


def i91_merge() -> tuple[str | None, str | None]:
    """(R, M) by ancestry: R the oldest commit reachable from HEAD that adds docs/iterations/I91.md, M the oldest merge of
    R..HEAD whose second parent reaches R and whose first parent does not (None on I91's own branch before its merge)."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", REPORT).split()
    if not added:
        return None, None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return r, c
    return r, None


def own_commits() -> tuple[dict[str, list[str]], str, str]:
    """I91's own non-merge commits after its prereg, each with the paths it changes, the commit they end at, and the
    prereg commit: along the first-parent line of M^2 back to the lead when I91 is merged, else prereg..HEAD."""
    pre = prereg_commit()
    _, m = i91_merge()
    if m is not None:
        first, second = git("rev-parse", f"{m}^1", f"{m}^2").split()
        revs, end = [second, f"^{first}", f"^{pre}"], second
    else:
        revs, end = [f"{pre}..HEAD"], "HEAD"
    out: dict[str, list[str]] = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out, end, pre


def sidecar_tokens(sc: dict) -> set[str]:
    """Rule Z1's target names: the codec values, the package paths and last names of its function and constant ids."""
    out = set()
    for k, v in sc["codec"].items():
        out.add(v)
        if k in ("enc", "dec", "split", "retrieve", "capacity"):
            path, _, name = v.rpartition(".")
            out |= {path, name}
    return {t for t in out if t}


def code_strings(path: Path) -> list[str]:
    """Identifiers and string literals of a module's code (docstrings excluded)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docs.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            out.append(node.value)
        elif isinstance(node, ast.Name):
            out.append(node.id)
        elif isinstance(node, ast.Attribute):
            out.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.arg):
            out.append(node.arg)
        elif isinstance(node, ast.alias):
            out += [node.name, node.asname or ""]
        elif isinstance(node, ast.keyword) and node.arg:
            out.append(node.arg)
    return out


def instrument() -> tuple[dict, dict]:
    sc = load(SIDECAR)
    return sc, I.expected(sc, I.run_instrument())


def th() -> dict:
    return load(ROOT / "spec" / "M3" / "predictions.json")["iterations"][KEY]["thresholds"]


class TestInstrument(unittest.TestCase):
    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(I.sha256_file(ROOT / "tests_m3" / "_i91.py"), t["instrument_sha256"])
        self.assertEqual(I.sha256_file(I.INSTRUMENT_GO), t["go_instrument_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for k in ("sidecar", "document"):
            with self.subTest(pinned=k):
                self.assertEqual(I.sha256_file(ROOT / t[k]["path"]), t[k]["sha256"])


# ====================================================================== Z1
class TestSidecar(unittest.TestCase):
    def test_z1_sidecar_shape(self):
        sc = load(SIDECAR)
        self.assertEqual(sc["compression_version"], "holon-compression/0.1")
        doc = load(ROOT / sc["document"])
        self.assertIn(sc["probe_package"], {p["path"] for p in doc["go"]["packages"]})
        c = sc["codec"]
        self.assertEqual(set(c), {"enc", "dec", "split", "split_blobs", "retrieve", "capacity", "library"})
        for k in ("enc", "dec", "split", "retrieve", "capacity"):
            self.assertRegex(c[k], FUNC_ID, k)
        for k in ("enc", "split", "retrieve"):
            self.assertIn(c[k], doc["go"]["functions"], f"{k} is a function of the Go document")
        h = sc["hypotheses"]
        self.assertEqual(set(h), {"HypZ", "HypZ_len"})
        self.assertRegex(h["HypZ"]["K"], EXPR)
        self.assertEqual(set(h["HypZ_len"]["bound"]), {"shift", "small", "small_shift"})
        s = sc["sample"]
        self.assertTrue(s["kinds"] and [k for k in ("zero", "ramp", "stream") if k in s["kinds"]] == s["kinds"])
        for k in ("lengths", "paddings", "beyond"):
            self.assertTrue(s[k])
            for e in s[k]:
                self.assertRegex(e, EXPR, k)
        self.assertIn(s["expansion"]["kind"], s["kinds"])
        self.assertRegex(s["expansion"]["limit"], EXPR)
        self.assertGreaterEqual(s["expansion"]["window"], 1)

    def test_z1_module_holds_no_target_name(self):
        sc = load(SIDECAR)
        toks = sidecar_tokens(sc)
        bad = sorted({s for s in code_strings(MODULE) for t in toks if t in s}
                     | {s for s in code_strings(MODULE) if "morph" in s.lower()})
        self.assertEqual(bad, [], "target names in holon/oracles/compression.py's code (rule Z1)")


# ====================================================================== Z2-Z8
class TestOracle(unittest.TestCase):
    def test_z8_check_reproduces_the_committed_document(self):
        committed()
        p = subprocess.run([sys.executable, "-m", "holon", "oracle", "compression", "--milestone", "M3", "--check"],
                           cwd=ROOT, capture_output=True, text=True, timeout=3600)
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])

    def test_z8_document_shape(self):
        d = committed()
        sc = load(SIDECAR)
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["compression_oracle_version"], "holon-compression-oracle/0.1")
        self.assertEqual(d["sidecar"], {"path": "spec/M3/lib/compression.json", "sha256": I.sha256_file(SIDECAR)})
        self.assertEqual(d["document"], {"path": sc["document"], "sha256": I.sha256_file(ROOT / sc["document"])})
        doc = load(ROOT / sc["document"])
        self.assertEqual(d["target"], {"repo": doc["target"]["repo"], "commit": doc["target"]["commit"]})
        self.assertEqual(d["codec"], sc["codec"])
        self.assertEqual(d["library"]["module"], sc["codec"]["library"])
        self.assertTrue(d["library"]["version"])
        for p in d["points"]:
            self.assertEqual(set(p), POINT_KEYS)
        self.assertEqual(RESULTS.read_text(encoding="utf-8"),
                         json.dumps(d, indent=2, sort_keys=True) + "\n")

    def test_z2_points_agree_with_the_instrument(self):
        d = committed()
        _, exp = instrument()
        self.assertEqual(d["sample"]["seed"], exp["sample"]["seed"])
        for k in ("kinds", "lengths", "paddings", "beyond"):
            self.assertEqual(d["sample"][k], exp["sample"][k], k)
        self.assertEqual([(p["kind"], p["n"]) for p in d["points"]], [(p["kind"], p["n"]) for p in exp["points"]])
        for got, want in zip(d["points"], exp["points"]):
            where = f"{got['kind']} n={got['n']}"
            self.assertEqual(got["x_sha256"], want["x_sha256"], where)
            self.assertEqual(want["go_x_sha256"], want["x_sha256"], where)
            for k in ("enc_error", "enc_len", "enc_sha256", "blobs", "padded_len", "padding", "pipeline", "paddings",
                      "beyond"):
                self.assertEqual(got[k], want[k], f"{where}: {k}")
            self.assertEqual(got["padded_ok"], want["padded_is_c_then_zeros"], where)

    def test_z3_capacity_and_padding(self):
        d = committed()
        sc, exp = instrument()
        self.assertEqual(d["capacity"], exp["capacity"])
        self.assertEqual(exp["capacity"]["C"], exp["source_capacity"], "compiled constant = source declaration")
        c, k = d["capacity"]["C"], d["capacity"]["K"]
        self.assertTrue(all(x <= k for x in d["sample"]["paddings"]))
        self.assertTrue(all(x > k for x in d["sample"]["beyond"]))
        for p in d["points"]:
            if p["enc_error"] is None and p["blobs"] is not None:
                self.assertEqual(p["padding"], p["padded_len"] - p["enc_len"])

    def test_z4_hypz_entry_follows_the_points(self):
        d = committed()
        _, exp = instrument()
        z = d["hypotheses"]["HypZ"]
        for k in ("status", "points", "decodes", "failures"):
            self.assertEqual(z[k], exp["HypZ"][k], k)
        self.assertEqual(z["K"], d["capacity"]["K"])
        self.assertEqual(z["statement"], load(SIDECAR)["hypotheses"]["HypZ"]["statement"])

    def test_z5_hypz_len_entry_follows_the_points(self):
        d = committed()
        _, exp = instrument()
        z = d["hypotheses"]["HypZ_len"]
        for k in ("status", "points", "max_excess", "failures"):
            self.assertEqual(z[k], exp["HypZ_len"][k], k)
        self.assertEqual(z["statement"], load(SIDECAR)["hypotheses"]["HypZ_len"]["statement"])

    def test_z6_expansion_agrees_with_the_instrument(self):
        d = committed()
        _, exp = instrument()
        self.assertEqual(d["expansion"], exp["expansion"])

    def test_z7_empty_agrees_with_the_instrument(self):
        d = committed()
        _, exp = instrument()
        self.assertEqual(d["empty"], exp["empty"])


# ====================================================================== predictions
class TestOutcomes(unittest.TestCase):
    def test_p1_k_is_the_capacity_minus_one(self):
        d = committed()
        self.assertEqual(d["capacity"], {"C": 126976, "K": 126975})
        for p in d["points"]:
            c = p["enc_len"]
            self.assertEqual(p["blobs"], max(1, -(-c // 126976)), p["n"])
            self.assertEqual(p["padded_len"], p["blobs"] * 126976)
            self.assertLessEqual(p["padding"], 126975)
            self.assertTrue(p["padded_ok"])

    def test_p2_hypz_checked(self):
        z = committed()["hypotheses"]["HypZ"]
        self.assertEqual((z["status"], z["points"], z["decodes"], z["failures"]), ("checked", 33, 330, []))

    def test_p3_hypz_len_checked(self):
        z = committed()["hypotheses"]["HypZ_len"]
        self.assertEqual((z["status"], z["points"], z["failures"]), ("checked", 33, []))

    def test_p4_expansion_at_the_smallest_limit(self):
        e = committed()["expansion"]
        self.assertEqual((e["kind"], e["limit"], e["window"]), ("stream", 126976, [125953, 126976]))
        self.assertTrue(5 <= e["overhead"] <= 25, e["overhead"])
        self.assertTrue(e["exceeding"]["interval"])
        self.assertEqual(e["exceeding"]["min"], 126976 - e["overhead"] + 1)
        self.assertEqual(e["exceeding"]["count"], e["overhead"])

    def test_p5_empty_payload_does_not_decode(self):
        e = committed()["empty"]
        self.assertEqual((e["enc_len"], e["enc_nil"], e["dec_empty"]), (0, True, "error: empty input"))
        pl = e["pipeline"]
        self.assertEqual((pl["blobs"], pl["padded_len"], pl["zero"]), (1, 126976, True))
        self.assertTrue(pl["dec"].startswith("error: "), pl["dec"])

    def test_p6_zeros_beyond_k_decode(self):
        for p in committed()["points"]:
            self.assertEqual(set(p["beyond"].values()), {"ok"}, (p["kind"], p["n"]))


# ====================================================================== regressions
class TestRegressions(unittest.TestCase):
    def test_r1_d2_unchanged(self):
        h = load(ROOT / "results" / "M2" / "hypotheses.json")
        self.assertEqual(h["Hyp-Z0-kzg"]["status"], "checked")
        commits, _, _ = own_commits()
        touched = sorted(c for c, paths in commits.items() if "results/M2/hypotheses.json" in paths)
        self.assertEqual(touched, [])

    def test_r2_own_commits_touch_only_what_the_contract_allows(self):
        commits, _, _ = own_commits()
        bad = {c[:12]: sorted(set(paths) - ALLOWED) for c, paths in commits.items() if set(paths) - ALLOWED}
        self.assertEqual(bad, {}, "rule Z9")

    def test_r3_only_the_cli_imports_the_module(self):
        users = []
        for p in sorted((ROOT / "holon").rglob("*.py")):
            if p == MODULE:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"oracles\.compression|from \.+oracles import .*\bcompression\b", text):
                users.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(users, ["holon/__main__.py"])


if __name__ == "__main__":
    unittest.main()
