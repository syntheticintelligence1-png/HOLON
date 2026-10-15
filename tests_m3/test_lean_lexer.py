"""F36: Lean G3 reads the code tokens the way Lean 4.34.0 lexes them (holon.lean.lex, strip_comments, scan_text,
forbidden), and refuses what would change that reading or run code.

Before F36, holon.lean.strip_comments was a character scanner: it started a comment at every `--` and `/-` outside a
"..." or '.' literal, and forbidden() then blanked every "..."-shaped span. Lean 4.34.0 starts a comment only at a
token boundary, so a file could hide forbidden code from G3 while Lean compiled it (Q35; I42 Surprise 8): a «/-»
identifier, a raw string r"\\" or r#".."#, a char literal '"', an interpolated string s!"{..}", a `/-/-` opener (Lean
skips the third character of a plain block-comment opener), a token such as `<-`, `//` or `\\/` right before `-`, a
lone carriage return inside a line comment (Python's universal newlines end the line there, Lean does not), a command
started mid-line (`... := 1 #eval ...`), and a token added by binder_predicate.

PROBES below are the probe set (each is a whole .lean file; the expected acceptance by the pinned Lean 4.34.0 was
recorded with `lean <file>`, no imports). For every probe Lean accepts that holds a forbidden construct in its code
(`hides`), forbidden() must now report something; for the ones whose construct sits in a real comment, nothing. The
Lean-backed tests re-check each recorded acceptance with the pinned toolchain when it is installed, and skip (with
the reason) when it is not. Every committed Lean file must still pass G3 and lex back to its exact text.

F36 review: what is shown is that every probe below is caught, not that no other route exists. Two routes the first
probe set missed are closed by allowlists (holon.lean.structure_violations): `set_option doc.verso true` (Lean then
elaborates the `lean` code blocks of a doc comment as commands, #eval included, while the scan reads a comment) and a
parser attribute (`@[term_parser]` or `attribute [term_parser]` over a ParserDescr from Init.Prelude adds a token that
may hold `--`). The static token-character sets of holon.lean are derived here from Lean's own token table
(TestTokenTable). The assumption left: the file extends no grammar, so Lean reads it with that table.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, holon_module

# name: (source, Lean 4.34.0 accepts it, its code holds a forbidden construct)
PROBES = {
    # «…» identifiers holding comment openers (Q35)
    "guill_block": ('def «/-» : Nat := 1\naxiom bad : False\ndef «-/» : Nat := 2\ntheorem t : False := bad\n', True, True),
    "guill_line": ('def «--» : Nat := 0\ndef x : Nat := «--» + (sorry : Nat)\n', True, True),
    "guill_namelit": ('def n : Lean.Name := `«/-»\naxiom bad : False\ndef m : Lean.Name := `«-/»\n', True, True),
    "guill_dotted": ('namespace A\ndef «x/-» : Nat := 1\nend A\naxiom bad : False\ndef «-/y» : Nat := A.«x/-»\n',
                     True, True),
    # raw strings: no escapes inside, and `#` delimiters
    "raw_backslash": ('def a : String := r"\\"\ndef b : String := "--" ++ (sorry : String)\n', True, True),
    "raw_hash": ('def a : String := r#"x"--"# ++ (sorry : String)\n', True, True),
    "raw_hash_block": ('def a : String := r#"q"/-"#\naxiom bad : False\ndef b : String := r#"-/"#\n', True, True),
    "raw_plain_block": ('def a : String := r"/-"\naxiom bad : False\ndef b : String := r"-/"\n', True, True),
    # char literals and primes
    "char_dquote": ("def c : Char := '\"'\naxiom bad : False\ndef s : String := \"x\"\n", True, True),
    "char_dquote_line": ("def c : Char := '\"'\ndef s : String := \"--\" ++ (sorry : String)\n", True, True),
    "char_escape_quote": ("def c : Char := '\\''\naxiom bad : False\n", True, True),
    "char_dash": ("def c : List Char := ['-', '-']\naxiom bad : False\n", True, True),
    "prime_ident": ("def x' : Nat := 1\ndef y' : Char := '-'\naxiom bad : False\n", True, True),
    "prime_then_char": ("def f (x' : Nat) (c : Char) : Nat := x'\ndef g : Nat := f 1 '\"'\n"
                        "def s : String := \"--\" ++ (sorry : String)\n", True, True),
    "tick_token": ("def f (xs : List Nat) (h : 0 < xs.length) : Nat := xs[0]'h\naxiom bad : False\n", True, True),
    "sigma_tick": ("def S := Σ' (n : Nat), n = n\naxiom bad : False\n", True, True),
    # interpolated strings: `{` opens code inside the literal
    "interp_dash": ('def s : String := s!"{"--"}" ++ (sorry : String)\n', True, True),
    "interp_sorry": ('def s : String := s!"{(sorry : Nat)}"\n', True, True),
    "interp_block": ('def s : String := s!"{"/-"}"\naxiom bad : False\ndef t : String := "-/"\n', True, True),
    # string escapes and gaps
    "str_escape_dash": ('def s : String := "\\"--"\naxiom bad : False\n', True, True),
    "str_gap": ('def s : String := "a\\\n  b"\naxiom bad : False\n', True, True),
    "str_unicode_escape": ('def s : String := "\\u002d\\u002d"\naxiom bad : False\n', True, True),
    # block, doc and module-doc comments
    "doc_nested": ('/-- doc /- inner -/ still doc -/\naxiom bad : False\n', True, True),
    "doc_slash": ('/--/ x -/\naxiom bad : False\n', True, True),
    "block_line_inside": ('/- -- -/ axiom bad : False\n', True, True),
    "block_slash_skip": ('/-/- -/\naxiom bad : False\n-- -/\n', True, True),
    "doc_nest_trick": ('/-- a /- b -/\naxiom bad : False\n-- -/\ndef z : Nat := 0\n', True, False),
    "modoc_nest_trick": ('/-! a /- b -/\naxiom bad : False\n-- -/\n', True, False),
    "verso_doc": ('set_option doc.verso true\n/-- {lean}`(sorry : Nat)` -/\ndef z : Nat := 0\n', True, False),
    # F36 review: a Verso doc comment's `lean` code block is elaborated as commands; its IO runs (the environment
    # changes are discarded after the doc comment, so the probe shows the IO: Lean writes verso_ran.txt)
    "verso_codeblock": ('set_option doc.verso true\n/--\n```lean\n#eval IO.FS.writeFile "verso_ran.txt" "x"\n```\n-/\n'
                        'def z : Nat := 0\n', True, True),
    "verso_codeblock_in": ('set_option doc.verso true in\n/--\n```lean\n#eval IO.FS.writeFile "verso_ran_in.txt" "x"\n'
                           '```\n-/\ndef z : Nat := 0\n', True, True),
    # F36 review: a parser attribute adds the token "≺--" (a hole), which hides the rest of its line from a lexer
    # that reads `--` as a comment
    "parser_attr": ('@[term_parser] def holeTok : Lean.ParserDescr := Lean.ParserDescr.node `Lean.Parser.Term.hole 1024 '
                    '(Lean.ParserDescr.symbol "≺--")\ndef x : Nat := @id ≺-- 0 axiom bad : False\n', True, True),
    "parser_attr_cmd": ('def holeTok : Lean.ParserDescr := Lean.ParserDescr.node `Lean.Parser.Term.hole 1024 '
                        '(Lean.ParserDescr.symbol "≺--")\nattribute [term_parser] holeTok\n'
                        'def x : Nat := @id ≺-- 0 axiom bad : False\n', True, True),
    # multi-character tokens right before `-`
    "arrow_dashdash": ('instance : Neg (IO Int) := ⟨fun x => x⟩\ndef f : IO Int := do\n  let y <--(pure (sorry : Int))\n'
                       '  return y\n', True, True),
    "subtype_slashslash": ('def T := { x : Int //-x = 0 }\naxiom bad : False\ndef u : String := "-/"\n', True, True),
    "or_backslash": ('theorem t (p : Prop) (h : p) : p \\/-(0 : Int) = 0 ∨ p := Or.inl h\naxiom bad : False\n'
                     'def u : String := "-/"\n', True, True),
    # commands started mid-line
    "eval_midline": ('def x : Nat := 1 #eval (2 : Nat)\n', True, True),
    "exit_midline": ('def x : Nat := 1 #exit\naxiom bad : False\n', True, True),
    # carriage returns: Lean ends a line comment at LF only
    "cr_line_comment": ('-- note\raxiom bad : False\n', True, False),
    "cr_line_comment2": ('-- note\r"\naxiom bad : False\ndef s : String := "--" ++ (sorry : String)\n', True, True),
    "crlf_ok": ('def x : Nat := 1\r\ntheorem t : x = 1 := rfl\r\n', True, False),
    # tokens added by a command
    "binder_pred": ('binder_predicate x " ≺--" y:term => `($x < $y)\n'
                    'theorem t : ∃ x ≺--1, x = 0 := ⟨0, by decide, rfl⟩ theorem u : False := sorry\n', True, True),
    # sorry by its constant
    "sorryax": ('theorem t : False := sorryAx False false\n', True, True),
    # forms Lean itself rejects (recorded so the set stays honest)
    "lambda_adjacent": ('def g : Nat := (fun (_ : Nat) (h : Nat → Nat) => h 0) sorryλ x => x\n', False, True),
    "unicode_dash": ('def a : Nat := 1 ‐‐ 2\naxiom bad : False\n', False, True),
    "sorry_guill": ('theorem t : False := «sorry»\n', False, True),
    "tab_indent": ('def x : Nat :=\n\t1\naxiom bad : False\n', False, True),
    "nbsp": ('axiom\u00a0bad : False\n', False, True),
    "guill_prime": ("def «a»' : Nat := 1\n", False, False),
}
# accepted by Lean, nothing forbidden in the code Lean compiles, and lexable: G3 must pass them
CLEAN = ("doc_nest_trick", "modoc_nest_trick", "crlf_ok")
# F36 review: verso_doc hides nothing (its `{lean}` role declares nothing), but any set_option outside the allowlist,
# doc.verso included, is refused: a Verso doc comment's code blocks run (verso_codeblock)
REFUSED_BY_ALLOWLIST = {"verso_doc": "set_option doc.verso", "verso_codeblock": "set_option doc.verso",
                        "verso_codeblock_in": "set_option doc.verso", "parser_attr": "@[",
                        "parser_attr_cmd": "attribute"}


def committed_lean_files() -> list[Path]:
    """Every committed Lean file the repo generates: gen/*/lean*/ and gen/M3/theory/lean/."""
    files = set(ROOT.glob("gen/*/lean*/**/*.lean")) | set(ROOT.glob("gen/M3/theory/lean/**/*.lean"))
    return sorted(files)


class TestProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L = holon_module("holon.lean")

    def test_every_hiding_probe_is_caught(self):
        for name, (src, accepts, hides) in sorted(PROBES.items()):
            if accepts and hides:
                with self.subTest(probe=name):
                    self.assertNotEqual(self.L.forbidden(src), [], f"{name}: Lean compiles a forbidden construct")

    def test_the_bytes_the_gate_reads_are_the_bytes_lean_reads(self):
        """A lone carriage return (cr_line_comment): read in text mode, Python ends the line comment there and the
        lexer can no longer see it; G3 decodes the file's bytes and refuses it."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-f36-"))
        try:
            for name in ("cr_line_comment", "cr_line_comment2"):
                f = tmp / f"{name}.lean"
                f.write_bytes(PROBES[name][0].encode("utf-8"))
                with self.subTest(probe=name):
                    bad = self.L.g3_violations([f], tmp)
                    self.assertEqual(len(bad), 1, bad)
                    self.assertIn("unlexable", bad[0])
            ok = tmp / "crlf_ok.lean"
            ok.write_bytes(PROBES["crlf_ok"][0].encode("utf-8"))
            self.assertEqual(self.L.g3_violations([ok], tmp), [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_real_comments_still_do_not_count(self):
        for name in CLEAN:
            with self.subTest(probe=name):
                self.assertEqual(self.L.forbidden(PROBES[name][0]), [])

    def test_the_allowlists_refuse_grammar_and_option_changes(self):
        for name, hit in sorted(REFUSED_BY_ALLOWLIST.items()):
            with self.subTest(probe=name):
                self.assertIn(hit, self.L.forbidden(PROBES[name][0]))
        L = self.L
        for src, hit in (("set_option «doc».verso true\n", "set_option doc.verso"),
                         ("set_option doc.verso.module true\n", "set_option doc.verso.module"),
                         ("theorem t : True := by set_option pp.all true in trivial\n", "set_option pp.all"),
                         ("#guard 1 = 1\n", "#guard"), ("#reduce 1\n", "#reduce"),
                         ("#guard_msgs in\n#check 1\n", "#guard_msgs"),
                         ("@[simp] theorem t : True := trivial\n", "@["),
                         ("def f : IO Unit := unsafeBaseIO (pure ())\n", "unsafeBaseIO"),
                         ("def p : Lean.TrailingParserDescr := default\n", "TrailingParserDescr")):
            with self.subTest(src=src):
                self.assertIn(hit, L.forbidden(src))
        self.assertEqual(L.forbidden("set_option maxRecDepth 20000\nset_option autoImplicit false\n"
                                     "theorem t : True := trivial\n#print axioms t\n"), [])

    def test_theorems_are_found_wherever_they_stand(self):
        src = ("theorem a : True := trivial\nprivate theorem b : True := trivial\n"
               "def x : Nat := 1 theorem c : True := trivial\n/-- d -/ theorem d : True := trivial\n"
               "-- theorem e : True := trivial\n")
        self.assertEqual(self.L.theorems(src), ["a", "b", "c", "d"])

    def test_lex_covers_the_source_exactly(self):
        for name, (src, _, _) in sorted(PROBES.items()):
            try:
                toks = self.L.lex(src)
            except self.L.LeanLexError:
                continue
            with self.subTest(probe=name):
                self.assertEqual("".join(t for _, t in toks), src)

    def test_lexer_details(self):
        L = self.L
        self.assertEqual(L.ident_name("«a b».«c»"), "a b.c")
        self.assertEqual(L.forbidden("theorem t : False := «sorry»\n"), ["sorry"])
        self.assertEqual(L.forbidden("set_option «debug».«skipKernelTC» true\n"),
                         ["debug.skipKernelTC", "set_option debug.skipKernelTC"])
        self.assertEqual(L.strip_comments("a /-/- -/ b -/ c\n"), "a  b -/ c\n")   # `/-/-` opens one level
        self.assertEqual(L.strip_comments("x /-- d /- e -/ f -/ y"), "x  y")
        self.assertEqual(L.strip_comments('r#"a"--"# -- c'), 'r#"a"--"# ')
        self.assertEqual(L.strip_comments("h.2.1 -- c"), "h.2.1 ")
        self.assertEqual(L.strip_comments("x' -- c"), "x' ")
        for src in ("x <-- y", "{ x // -1 }//-1", "a \\/-b", "#'x'", '"{x}"', "'ab'", "-- c\r more", "'"):
            with self.subTest(src=src):
                with self.assertRaises(L.LeanLexError):
                    L.lex(src)
                self.assertTrue(L.forbidden(src)[0].startswith("unlexable"))

    def test_check_text_refuses_an_unlexable_source_before_lean(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-f36-"))
        try:
            r = self.L.check_text(PROBES["guill_block"][0], tmp)
            self.assertEqual(r["result"], "forbidden")
            r = self.L.check_text(PROBES["interp_dash"][0], tmp)
            self.assertEqual(r["result"], "forbidden")
            self.assertIn("unlexable", r["out"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCommittedLean(unittest.TestCase):
    def test_every_committed_lean_file_passes_g3(self):
        L = holon_module("holon.lean")
        files = committed_lean_files()
        self.assertTrue(files, "no committed Lean file found")
        self.assertEqual(L.g3_violations(files, ROOT), [])
        for f in files:
            src = f.read_bytes().decode("utf-8")
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertEqual("".join(t for _, t in L.lex(src)), src)
                self.assertTrue(L.theorems(src), "a committed Lean file declares at least one theorem")


class TestProbesWithLean(unittest.TestCase):
    """The recorded acceptance of every probe, re-checked with the pinned Lean 4.34.0 (`lean <file>`, no lake)."""

    @classmethod
    def setUpClass(cls):
        cls.L = holon_module("holon.lean")
        try:
            cls.bin = cls.L.toolchain_bin()
            ok, detail = cls.L.toolchain_ok()
        except cls.L.LeanUnavailable as e:
            cls.bin, ok, detail = None, False, str(e)
        cls.skip = None if ok else f"the pinned Lean toolchain is not available: {detail}"
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-f36-lean-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def lean(self, name: str, src: str) -> tuple[bool, str]:
        f = self.tmp / f"{name}.lean"
        f.write_bytes(src.encode("utf-8"))
        p = subprocess.run(["nice", str(self.bin / "lean"), str(f)], capture_output=True, text=True, timeout=300,
                           env=self.L._env(self.bin), cwd=self.tmp)
        out = p.stdout + p.stderr
        return p.returncode == 0 and ": error" not in out, out

    def test_recorded_acceptance(self):
        if self.skip:
            self.skipTest(self.skip)
        for name, (src, accepts, _) in sorted(PROBES.items()):
            with self.subTest(probe=name):
                got, out = self.lean(name, src)
                self.assertEqual(got, accepts, out[-800:])

    def test_hidden_axioms_are_real(self):
        """Where a probe hides `axiom bad`, Lean declares it (so G3 had something to find)."""
        if self.skip:
            self.skipTest(self.skip)
        for name, (src, accepts, hides) in sorted(PROBES.items()):
            if accepts and hides and "axiom bad" in src and name not in ("exit_midline",):
                with self.subTest(probe=name):
                    got, out = self.lean(name + "_ax", src.rstrip("\n") + "\n#print axioms bad\n")
                    self.assertTrue(got, out[-800:])
                    self.assertIn("'bad' depends on axioms: [bad]", out)
        for name in ("doc_nest_trick", "modoc_nest_trick", "cr_line_comment"):
            with self.subTest(probe=name):
                got, out = self.lean(name + "_ax", PROBES[name][0].rstrip("\n") + "\n#print axioms bad\n")
                self.assertIn("Unknown constant `bad`", out)

    def test_a_verso_code_block_runs_io(self):
        """verso_codeblock: Lean runs the #eval in the doc comment's code block (the file it writes exists)."""
        if self.skip:
            self.skipTest(self.skip)
        for name, out_file in (("verso_codeblock", "verso_ran.txt"), ("verso_codeblock_in", "verso_ran_in.txt")):
            with self.subTest(probe=name):
                f = self.tmp / out_file
                if f.exists():
                    f.unlink()
                got, out = self.lean(name + "_io", PROBES[name][0])
                self.assertTrue(got, out[-800:])
                self.assertTrue(f.exists(), f"{name}: the code block's #eval did not run")


class TestTokenTable(unittest.TestCase):
    """The static token-character sets of holon.lean, derived from the token table of the pinned Lean 4.34.0 with
    `import Lean` (global tokens and every namespace's scoped tokens; a superset of what a file without imports sees).
    One Lean run per test class."""

    @classmethod
    def setUpClass(cls):
        cls.L = holon_module("holon.lean")
        cls.tokens, cls.skip = None, None
        try:
            b = cls.L.toolchain_bin()
            ok, detail = cls.L.toolchain_ok()
        except cls.L.LeanUnavailable as e:
            ok, detail = False, str(e)
        if not ok:
            cls.skip = f"the pinned Lean toolchain is not available: {detail}"
            return
        tmp = Path(tempfile.mkdtemp(prefix="holon-f36-tok-"))
        try:
            f = tmp / "Tokens.lean"
            f.write_text(TOKEN_DUMP, encoding="utf-8")
            p = subprocess.run(["nice", str(b / "lean"), str(f)], capture_output=True, text=True, timeout=600,
                               env=cls.L._env(b), cwd=tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if p.returncode != 0:
            raise AssertionError(f"the token dump failed: {(p.stdout + p.stderr)[-800:]}")
        cls.tokens = sorted({json.loads(line) for line in p.stdout.splitlines() if line.startswith('"')})

    def setUp(self):
        if self.skip:
            self.skipTest(self.skip)

    def test_the_dump_is_the_token_table(self):
        self.assertGreater(len(self.tokens), 500)
        for t in ("<-", "//", "]'", "#'", "/--", "/-!"):
            self.assertIn(t, self.tokens)

    def before(self, ch: str) -> set:
        return {t[i - 1] for t in self.tokens for i in range(1, len(t)) if t[i] == ch}

    def test_characters_before_dash_and_slash(self):
        self.assertEqual(self.before("-"), set(self.L._TOKEN_BEFORE_DASH))
        self.assertEqual(self.before("/"), set(self.L._TOKEN_BEFORE_SLASH))

    def test_tokens_ending_in_a_quote(self):
        ends = {t[-2] for t in self.tokens if len(t) > 1 and t.endswith("'")}
        self.assertEqual(ends, set(self.L._TICK_TOKEN_BEFORE) | set(self.L._TICK_REFUSE_BEFORE))

    def test_no_token_opens_a_comment_or_a_literal(self):
        """No token but the doc-comment openers starts with `--` or `/-`, and none holds a string quote."""
        self.assertEqual(sorted({t for t in self.tokens if t.startswith(("--", "/-"))}), ["/-!", "/--"])
        self.assertEqual([t for t in self.tokens if '"' in t], [])


# the token dump: Lean.Parser.getTokenTable (global tokens) and the scoped token entries of parserExtension
TOKEN_DUMP = """import Lean
open Lean Lean.Parser in
#eval show CoreM Unit from do
  let env ← getEnv
  let mut out : Array String := (getTokenTable env).findPrefix ""
  for (_, arr) in (parserExtension.ext.getState env).scopedEntries.map.toList do
    for e in arr.toList do
      match e with
      | .token tk => out := out.push tk
      | _ => pure ()
  for t in out.qsort (· < ·) do
    IO.println (repr t)
"""


if __name__ == "__main__":
    unittest.main()
