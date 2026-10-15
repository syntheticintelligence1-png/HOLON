"""I48 binding-aware renaming acceptance, red until the implementation exists."""
from __future__ import annotations

import importlib
import unittest

from tests_m4._i48 import (
    ROOT, KEYWORDS, check_bundle_syntax, corpus, extract_comments_and_strings,
    inside, instrument, lex_source, load, reference_binding_signature,
)


SYNTHETIC = {
    "go": [
        b'package p\nfunc f(x int) int { y := x; { x := 3; y += x }; return y }\n',
        b'package p\nimport "fmt"\ntype T struct { X int }\nfunc (t T) F() { fmt.Println(t.X, "X") }\n',
    ],
    "solidity": [
        b'pragma solidity ^0.8.20; contract C { uint x; function f(uint x) public returns (uint) { this.f(x); return x; } }',
        b'pragma solidity ^0.8.20; contract C { string s = "name"; /* name */ function name(uint x) public pure returns (uint) { return x; } }',
    ],
}


class TestRenamingInstrument(unittest.TestCase):
    def test_preregistered_contract(self):
        rules = instrument()["renaming_rules"]
        self.assertEqual(rules["module"], "holon/eval/renaming.py")
        self.assertEqual(rules["languages"], ["go", "solidity"])
        self.assertIn("binding-aware", rules["algorithm"])
        self.assertIn("byte for byte", rules["inverse"])
        self.assertEqual(rules["verification_report"], "results/M4/I48/renaming_report.json")


class TestRenamingOutcome(unittest.TestCase):
    def test_shadowing_and_scope_preservation_in_renamer(self):
        path = ROOT / "holon/eval/renaming.py"
        self.assertTrue(path.is_file(), f"Missing build outcome: {path}")
        module = importlib.import_module("holon.eval.renaming")
        snippets = {
            "go": b'''package p
import "context"
type Item struct { amount int }
func f(ctx context.Context, amount int) int {
    batchIndex := "batchIndex"
    result := amount
    { amount := 2; result += amount; _ = batchIndex }
    return result
}
''',
            "solidity": b'''pragma solidity ^0.8.24;
contract Example {
    uint256 batchIndex;
    function f(uint256 batchIndex) public pure returns (uint256) {
        uint256 result = batchIndex;
        { uint256 batchIndex = 2; result += batchIndex; }
        string memory text = "batchIndex";
        return result;
    }
}
''',
        }
        for language, source in snippets.items():
            with self.subTest(language=language):
                renamed = module.rename_bundle({"shadow": source}, language)["shadow"].decode()
                original = reference_binding_signature(source.decode(), language)
                changed = reference_binding_signature(renamed, language)
                self.assertEqual(original.token_skeleton, changed.token_skeleton)
                names = [name for _, _, name in changed.scope_bindings]
                target = "amount" if language == "go" else "batchIndex"
                renamed_names = [name for (old, new) in zip(original.scope_bindings,
                                                               changed.scope_bindings)
                                 if old[2] == target for name in [new[2]]]
                self.assertGreaterEqual(len(renamed_names), 2)
                self.assertEqual(len(set(renamed_names)), len(renamed_names))
                self.assertNotIn(target, renamed_names)
                self.assertIn('"batchIndex"', renamed)
                for keyword in (("context.Context", "error") if language == "go"
                                else ("uint256", "pure")):
                    if keyword in source.decode():
                        self.assertIn(keyword, renamed)

    def test_renaming(self):
        path = ROOT / instrument()["renaming_rules"]["module"]
        self.assertTrue(path.is_file(), f"Missing build outcome: {path}")
        module = importlib.import_module("holon.eval.renaming")
        # The implementation must expose binding maps for checking consistency and
        # non-capture; textual change alone is not a binding-aware guarantee.
        for api in ("rename_bundle", "restore_bundle", "binding_signature"):
            self.assertTrue(callable(getattr(module, api, None)), api)
        cases = []
        for e in corpus():
            bundle_dir = inside(e["source_bundle"], f"gen/M4/I48/bundles/{e['defect_id']}")
            renamed_dir = inside(e["renamed_bundle_dir"], f"gen/M4/I48/renamed/{e['defect_id']}")
            for revision in ("pre_fix", "fix"):
                originals = [bundle_dir / revision / file for file in e["source_files"]]
                renamed_files = [renamed_dir / revision / file for file in e["source_files"]]
                check_bundle_syntax(e["language"], originals)
                check_bundle_syntax(e["language"], renamed_files)
                bundle = {file: (bundle_dir / revision / file).read_bytes()
                          for file in e["source_files"]}
                cases.append((e["language"], bundle))
                for file in e["source_files"]:
                    original = bundle[file].decode()
                    transformed = (renamed_dir / revision / file).read_text()
                    self.assertEqual(reference_binding_signature(original, e["language"]).token_skeleton,
                                     reference_binding_signature(transformed, e["language"]).token_skeleton)
                    self.assertEqual(extract_comments_and_strings(original),
                                     extract_comments_and_strings(transformed))
        cases += [(language, {"edge": source}) for language, sources in SYNTHETIC.items()
                  for source in sources]
        self.assertGreaterEqual(len(cases), 44)
        for language, bundle in cases:
            with self.subTest(language=language, sample=next(iter(bundle.values()))[:32]):
                renamed = module.rename_bundle(bundle, language)
                self.assertEqual(renamed, module.rename_bundle(bundle, language))
                self.assertEqual(module.restore_bundle(renamed), bundle)
                self.assertEqual(set(renamed), set(bundle))
                self.assertTrue(any(renamed[k] != bundle[k] for k in bundle))
                for file in bundle:
                    self.assertEqual(
                        reference_binding_signature(bundle[file].decode(), language).token_skeleton,
                        reference_binding_signature(renamed[file].decode(), language).token_skeleton)
                    self.assertEqual(extract_comments_and_strings(bundle[file].decode()),
                                     extract_comments_and_strings(renamed[file].decode()))

    def test_report(self):
        entries = corpus()
        report = load(instrument()["renaming_rules"]["verification_report"])
        self.assertEqual(set(report["bundles"]), {e["defect_id"] for e in entries})
        self.assertEqual(set(report["synthetic"]), set(SYNTHETIC))
        self.assertEqual(report["pass_rate"], 1.0)
        for item in list(report["bundles"].values()) + [
            row for language in SYNTHETIC for row in report["synthetic"][language]]:
            self.assertTrue(item["inverse_byte_exact"])
            self.assertTrue(item["injective"])
            self.assertTrue(item["ast_preserved"])
            self.assertTrue(item["token_bindings_preserved"])
            self.assertTrue(item["keywords_preserved"])
        for e in entries:
            original_dir = inside(e["source_bundle"], f"gen/M4/I48/bundles/{e['defect_id']}")
            renamed_dir = inside(e["renamed_bundle_dir"], f"gen/M4/I48/renamed/{e['defect_id']}")
            domain_words = set(instrument()["renaming_rules"]["domain_words"])
            remaining = unchanged = 0
            alpha = True
            for revision in ("pre_fix", "fix"):
                for file in e["source_files"]:
                    original = (original_dir / revision / file).read_text()
                    renamed = (renamed_dir / revision / file).read_text()
                    old_sig = reference_binding_signature(original, e["language"])
                    new_sig = reference_binding_signature(renamed, e["language"])
                    alpha &= old_sig.token_skeleton == new_sig.token_skeleton
                    old_tokens = [(kind, value) for kind, value in lex_source(original, e["language"])
                                  if kind not in {"space", "comment"}]
                    new_tokens = [(kind, value) for kind, value in lex_source(renamed, e["language"])
                                  if kind not in {"space", "comment"}]
                    self.assertEqual(len(old_tokens), len(new_tokens))
                    unchanged += sum(kind == "id" and value not in KEYWORDS and
                                     (kind, value) == changed
                                     for (kind, value), changed in zip(old_tokens, new_tokens))
                    remaining += sum(value in domain_words for kind, value in
                                     lex_source(renamed, e["language"])
                                     if kind == "id" and value not in KEYWORDS)
            item = report["bundles"][e["defect_id"]]
            self.assertEqual(item["domain_words_remaining"], remaining)
            self.assertEqual(item["unchanged_user_identifiers"], unchanged)
            self.assertEqual(item["ast_alpha_equivalent"], alpha)
            self.assertEqual((remaining, unchanged, alpha), (0, 0, True))


if __name__ == "__main__":
    unittest.main()
