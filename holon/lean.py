"""`holon lean`: the Lean 4 second kernel for M0 (I9; whitepaper §8.8, §8.9; closes D-d for M0).

  python -m holon lean --milestone M0 [--json] [--jobs N]

For each M0 law, regenerate gen/M0/lean/<law_id>.lean (holon.gen.lean_proofs: model, statement with the
IR statement hash, and a proof re-checking the Bend verdict recorded in results/M0/<law_id>.json: the
law for PROVED, the counter-law at the recorded witness for REFUTED), check it in a fresh temporary lake
project (Lean 4.34.0, no Mathlib, no dependencies, nothing reused from an earlier build), and audit it:

  * Lean G3: the file, comments removed, holds none of FORBIDDEN (the comments located by a lexer that mirrors
    Lean 4.34.0's tokenizer, F36; a file it cannot classify exactly is refused), and nothing outside the allowlists
    (set_option names, `#` commands, no attribute: structure_violations);
  * `#print axioms` for every theorem the file declares (appended by the runner, whatever the file says)
    lists only ALLOWED_AXIOMS;
  * the theorem carrying the verdict is among them; each file checks within lean.budget_s_per_file.

The committed report gen/M0/lean/report.json binds each result to the sha256 of the exact text checked. It
holds no timings, so a re-run over the same records rewrites gen/M0/lean byte for byte; timings are in the
printed report and, from the gate, in results/M0/gate_timing.json (G7_lean). The M0 pipeline reads it
(`kernel_entry`): a record lists lean4 as checked only when the text it would emit now, from the law, the
facts and the run's own verdict and witness, has the checked sha256; independence_class is I2 only then.
G7 re-checks every such file from scratch.

Order of a full regeneration: `holon run` (Bend verdicts and witnesses), `holon lean` (re-checks them from
the records), `holon run` again (records pick up the Lean result). The Lean files depend only on each
record's status and witness, so once those are stable the second run changes nothing else.

check_text(src, tmpdir) and flip_canary(src) are the building blocks (and the I9-P4 canary).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEAN_VERSION = "4.34.0"
TOOLCHAIN = f"leanprover/lean4:v{LEAN_VERSION}"
ALLOWED_AXIOMS = frozenset({"propext", "Quot.sound"})
FORBIDDEN = re.compile(r"\b(sorry|admit|native_decide|bv_decide|decide\s*\+\s*native|axiom|unsafe|implemented_by|"
                       r"extern|ofReduceBool|ofReduceNat|opaque|partial|macro|macro_rules|syntax|elab|notation|"
                       r"infix|infixl|infixr|prefix|postfix|import|run_cmd|run_tac|run_elab|initialize|"
                       r"builtin_initialize|debug\.skipKernelTC|Lean\.Elab|Lean\.Meta|"
                       # F36: sorry by its constant, and the commands that add tokens (a token may hold `--`)
                       r"sorryAx|binder_predicate|declare_syntax_cat|declare_simp_like_tactic|"
                       # F36 review: code run at elaboration or a grammar extension by another name
                       r"unsafeBaseIO|unsafeIO|unsafeEIO|unsafeCast|elab_rules|simproc|dsimproc|grind_propagator|"
                       r"unif_hint|ParserDescr|TrailingParserDescr)\b")
# commands that run code or cut elaboration short (#eval runs IO during the lake build; #exit stops checking the rest
# of the file): forbidden like the tactics above (audit F-M2-32)
FORBIDDEN_CMD = re.compile(r"#\s*(eval|exit)\b")   # anywhere: a command may start mid-line (F36)
# F36 review: allowlists over the code tokens, since a word list cannot name everything that changes what Lean reads
# or runs. Only what the Lean generators emit is admitted (holon.gen.lean_proofs, holon.gen.theory):
#   * set_option: these option names only. `doc.verso` makes Lean elaborate the `lean` code blocks of a doc comment
#     as commands (#eval included) while the scan reads the doc comment as a comment;
#   * `#` commands: `#print` only (`#guard`, `#reduce`, `#check_failure`, `#guard_msgs` and the rest are refused);
#   * no attribute at all (`@[...]` or the `attribute` command): a parser attribute (command_parser, term_parser, ...)
#     takes a ParserDescr from Init.Prelude and adds tokens, which the static token sets below cannot know.
# What remains assumed: the file extends no grammar, so Lean reads it with the 4.34.0 token table.
SET_OPTION_ALLOWED = frozenset({"maxRecDepth", "autoImplicit"})
HASH_CMD_ALLOWED = frozenset({"print"})
# A canary counts as rejected only for a semantic reason (audit F-M2-32): the kernel decided the flipped claim false,
# or found the two sides not definitionally equal. A parse, name or goal-shape error rejects it vacuously, and
# "unsolved goals" alone is not enough (a syntax error can surface first as an empty tactic block's unsolved goal).
SEMANTIC_REJECTION = re.compile(r"Tactic `decide` proved that the proposition|is not definitionally equal|"
                                r"Tactic `rfl` failed: The left-hand side|type mismatch")
NON_SEMANTIC = re.compile(r"unexpected token|unexpected identifier|unknown identifier|unknown constant|unknown tactic|"
                          r"expected term|unterminated|invalid syntax|Expected the goal to be a binary relation")
CLAIM_MARK = "-- holon:claim"
REPORT = "report.json"
SUBDIR = "lean"
MODULE = "HolonCheck"
RESULTS = ("checked", "rejected", "forbidden", "bad_axioms", "missing_theorem", "timeout", "unavailable",
           "unsupported", "not_run")


# ------------------------------------------------------------------ configuration and toolchain
def config(root: Path | str = ROOT) -> dict:
    p = Path(root) / "config" / "holon.json"
    cfg = json.loads(p.read_text()) if p.exists() else {}
    lean = {"toolchain": TOOLCHAIN, "pinned_version": LEAN_VERSION, "budget_s_per_file": 120, "timeout_s": 300}
    lean.update(cfg.get("lean", {}))
    return lean


class LeanUnavailable(RuntimeError):
    pass


def toolchain_bin(cfg: dict | None = None) -> Path:
    """The bin directory of the pinned toolchain under ~/.elan (absolute; never a PATH lookup)."""
    cfg = cfg or config()
    tc = cfg["toolchain"]
    d = Path.home() / ".elan" / "toolchains" / tc.replace("/", "--").replace(":", "---") / "bin"
    if not (d / "lean").is_file() or not (d / "lake").is_file():
        raise LeanUnavailable(f"Lean toolchain {tc} not installed (no lean/lake in {d})")
    return d


def _env(bin_dir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LEAN", "LAKE", "ELAN"))}
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])  # prepended: the pinned lean wins
    return env


def lean_version(cfg: dict | None = None) -> str:
    b = toolchain_bin(cfg)
    p = subprocess.run([str(b / "lean"), "--version"], capture_output=True, text=True, timeout=60, env=_env(b))
    out = p.stdout.strip()
    m = re.match(r"Lean \(version (\d+\.\d+\.\d+)", out)
    if p.returncode != 0 or not m:
        raise LeanUnavailable(f"cannot run lean --version: {out or p.stderr.strip()}")
    return out


# What the fingerprint hashes, relative to the toolchain directory: the executables and the shared libraries
# that hold the elaborator, the kernel and Lake. The Init/Std .olean files (2.4 GB) are not hashed.
FINGERPRINT_FILES = ("bin/lean", "bin/lake", "lib/lean/libleanshared.so", "lib/lean/libLake_shared.so")


def _file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


_FP_CACHE: dict[str, dict] = {}


def fingerprint(cfg: dict | None = None) -> dict:
    """sha256 over FINGERPRINT_FILES of the pinned toolchain (resolved through links), as in bend.fingerprint."""
    home = Path(os.path.realpath(toolchain_bin(cfg))).parent
    if str(home) not in _FP_CACHE:
        files, h = {}, hashlib.sha256()
        for rel in FINGERPRINT_FILES:
            p = home / rel
            if not p.is_file():
                raise LeanUnavailable(f"Lean toolchain file {p} is missing")
            files[rel] = _file_sha256(p)
            h.update(rel.encode() + b"\0" + files[rel].encode() + b"\n")
        _FP_CACHE[str(home)] = {"toolchain_dir": str(home), "files": files, "fingerprint": "sha256:" + h.hexdigest()}
    return _FP_CACHE[str(home)]


def toolchain_ok(cfg: dict | None = None) -> tuple[bool, str]:
    """(ok, detail): `lean --version` is the pinned version and, when lean.pinned_fingerprint is set, the
    toolchain's fingerprint equals it."""
    cfg = cfg or config()
    try:
        v = lean_version(cfg)
        fp = fingerprint(cfg)
    except LeanUnavailable as e:
        return False, str(e)
    got = re.match(r"Lean \(version (\d+\.\d+\.\d+)", v).group(1)
    if got != cfg["pinned_version"]:
        return False, f"{v} is not the pinned {cfg['pinned_version']}"
    pin = cfg.get("pinned_fingerprint")
    if pin and fp["fingerprint"] != pin:
        return False, f"Lean toolchain fingerprint {fp['fingerprint']} ({fp['toolchain_dir']}) is not the pinned {pin}"
    return True, f"{v}; fingerprint {fp['fingerprint']}" + (" pinned" if pin else " (no pin configured)")


def pinned_version_ok(cfg: dict | None = None) -> tuple[bool, str]:
    return toolchain_ok(cfg)


# ------------------------------------------------------------------ source audit
# The G3 scan must see exactly the code Lean compiles (F36). A regex comment stripper does not: Lean starts a comment
# only at a token boundary, and a «…» identifier, a raw string, a char literal or a multi-character token can hold
# `--` or `/-` without starting one. So the audit lexes the file the way Lean 4.34.0's tokenizer does
# (src/lean/Lean/Parser/Basic.lean: whitespace, finishCommentBlock, strLitFnAux, charLitFnAux, rawStrLitFnAux,
# numberFnAux, identFnAux, tokenFnAux), and refuses (LeanLexError) whatever it cannot classify the same way Lean
# would: the conservative direction, so a file the scan cannot read is a G3 failure, never a silent strip.


class LeanLexError(ValueError):
    """The source holds a lexical form the G3 audit cannot classify exactly as Lean does: refuse the file."""


def _letter_like(c: str) -> bool:   # Init/Meta/Defs.lean isLetterLike
    v = ord(c)
    return ((0x3b1 <= v <= 0x3c9 and v != 0x3bb) or (0x391 <= v <= 0x3a9 and v not in (0x3a0, 0x3a3))
            or 0x3ca <= v <= 0x3fb or 0x1f00 <= v <= 0x1ffe or 0x2100 <= v <= 0x214f or 0x1d49c <= v <= 0x1d59f
            or (0xc0 <= v <= 0xff and v not in (0xd7, 0xf7)) or 0x100 <= v <= 0x17f)


def _subscript(c: str) -> bool:     # isSubScriptAlnum
    v = ord(c)
    return 0x2080 <= v <= 0x2089 or 0x2090 <= v <= 0x209c or 0x1d62 <= v <= 0x1d6a or v == 0x2c7c


def _ascii_alpha(c: str) -> bool:
    return "a" <= c <= "z" or "A" <= c <= "Z"


def _id_first(c: str) -> bool:      # isIdFirst (Char.isAlpha is ASCII only)
    return _ascii_alpha(c) or c == "_" or _letter_like(c)


def _id_rest(c: str) -> bool:       # isIdRest
    return _ascii_alpha(c) or "0" <= c <= "9" or c in "_'!?" or _letter_like(c) or _subscript(c)


# From the token table of Lean 4.34.0 with `import Lean` (a superset of what a file without imports sees), plus the
# scoped tokens Init declares: the characters c for which some token holds c followed by '-' (resp. '/'), so that a
# `--` (resp. `/-`) right after c may be the inside of a token rather than a comment (`<-` then `-x`; `//` then
# `-x`; `\/` then `-x`). The scan refuses such a spot instead of guessing. These sets, and the quote sets below, are
# checked against a dump of that table (tests_m3/test_lean_lexer.py TestTokenTable). They hold only while the file
# adds no token, which the allowlists enforce (no attribute, so no parser attribute; FORBIDDEN names the commands).
_TOKEN_BEFORE_DASH = frozenset("<-/")
_TOKEN_BEFORE_SLASH = frozenset("/=\\")
# Tokens that end in a quote ("]'", "⊕'", "Σ'", "×'"): a ' right after one of these characters is the token's last
# character, not the start of a char literal. The scoped token "#'" is active only in some namespaces: refused.
_TICK_TOKEN_BEFORE = frozenset("]⊕Σ×")
_TICK_REFUSE_BEFORE = frozenset("#")
_RAW_START = re.compile(r'r(#*)"')   # isRawStrLitStart, at a token start
_QUOTABLE = frozenset("\\\"'rnt")
_HEX = frozenset("0123456789abcdefABCDEF")


def _escape(src: str, i: int, in_string: bool) -> int:
    """End of the escape sequence whose backslash is at i (quotedCharCoreFn)."""
    n = len(src)
    if i + 1 >= n:
        raise LeanLexError(f"offset {i}: unterminated escape")
    c = src[i + 1]
    if c in _QUOTABLE:
        return i + 2
    if c == "x" and i + 3 < n and src[i + 2] in _HEX and src[i + 3] in _HEX:
        return i + 4
    if c == "u" and i + 5 < n and all(ch in _HEX for ch in src[i + 2:i + 6]):
        return i + 6
    if in_string and c == "\n":   # a string gap (stringGapFn): whitespace holding exactly this one newline
        j = i + 2
        while j < n and src[j] in " \t\r\n":
            if src[j] == "\n":
                raise LeanLexError(f"offset {i}: string gap with two newlines")
            j += 1
        return j
    raise LeanLexError(f"offset {i}: escape sequence the audit does not classify")


def _number(src: str, i: int) -> int:
    """End of the numeric literal starting at the digit at i (numberFnAux, decimalNumberFn)."""
    n = len(src)

    def digits(j, ok, need):
        start, seen_digit = j, False
        while j < n and (src[j] == "_" or ok(src[j])):
            seen_digit = seen_digit or src[j] != "_"
            j += 1
        if need and not seen_digit or (j > start and src[j - 1] == "_"):
            raise LeanLexError(f"offset {start}: malformed numeric literal")
        return j

    if src[i] == "0" and i + 1 < n and src[i + 1] in "bBoOxX":
        ok = {"b": lambda c: c in "01", "o": lambda c: "0" <= c <= "7", "x": lambda c: c in _HEX}[src[i + 1].lower()]
        return digits(i + 2, ok, True)
    j = digits(i, lambda c: "0" <= c <= "9", True)   # Char.isDigit is ASCII only
    if src.startswith("..", j):
        return j
    if j < n and src[j] in ".eE":
        if src[j] == ".":
            j += 1
            if j < n and "0" <= src[j] <= "9":
                j = digits(j, lambda c: "0" <= c <= "9", False)
            elif j < n and src[j] not in "eE" and (_id_first(src[j]) or src[j] == "«"):
                raise LeanLexError(f"offset {j}: identifier after a decimal point")
        if j < n and src[j] in "eE":
            j += 1
            if j < n and src[j] in "+-":
                j += 1
            if not (j < n and "0" <= src[j] <= "9"):
                raise LeanLexError(f"offset {j}: missing exponent digits")
            j = digits(j, lambda c: "0" <= c <= "9", False)
    return j


def lex(src: str) -> list[tuple[str, str]]:
    """[(kind, text)] covering src exactly, kind in ws, comment, ident, string, char, number, symbol. Raises
    LeanLexError on anything the audit cannot classify exactly as Lean 4.34.0 would."""
    out, i, n = [], 0, len(src)
    if "\r" in src.replace("\r\n", ""):
        raise LeanLexError("a carriage return outside a CRLF pair (Lean does not end a line comment there)")

    def block(j: int) -> int:   # finishCommentBlock from j at nesting 1; returns the end
        depth = 1
        while j < n:
            if src.startswith("-/", j):
                depth -= 1
                j += 2
                if depth == 0:
                    return j
            elif src.startswith("/-", j):
                depth += 1
                j += 2
            else:
                j += 1
        raise LeanLexError("unterminated comment")

    while i < n:
        c = src[i]
        prev = out[-1][1][-1] if out and out[-1][0] == "symbol" else ""   # the last character of a code token
        if c in " \t\n\r":
            j = i
            while j < n and src[j] in " \t\n\r":
                j += 1
            out.append(("ws", src[i:j]))
            i = j
        elif src.startswith("--", i):
            if prev in _TOKEN_BEFORE_DASH:
                raise LeanLexError(f"offset {i}: `--` right after {prev!r} may be inside a token")
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(("comment", src[i:j]))
            i = j
        elif src.startswith("/-", i):
            if prev in _TOKEN_BEFORE_SLASH:
                raise LeanLexError(f"offset {i}: `/-` right after {prev!r} may be inside a token")
            # `/--` and `/-!` are tokens followed by a comment body; after a plain `/-`, whitespace skips the third
            # character too (so `/-/-` opens one level, not two): either way the body is scanned from i + 3
            j = block(i + 3)
            out.append(("comment", src[i:j]))
            i = j
        elif c == '"':
            j = i + 1
            while True:
                if j >= n:
                    raise LeanLexError(f"offset {i}: unterminated string literal")
                if src[j] == '"':
                    break
                if src[j] == "{":
                    raise LeanLexError(f"offset {j}: `{{` in a string literal (an interpolated string runs code)")
                j = _escape(src, j, True) if src[j] == "\\" else j + 1
            out.append(("string", src[i:j + 1]))
            i = j + 1
        elif c == "'":
            if prev in _TICK_REFUSE_BEFORE:
                raise LeanLexError(f"offset {i}: a quote right after {prev!r} may be a scoped token")
            if prev in _TICK_TOKEN_BEFORE:
                out.append(("symbol", c))
                i += 1
                continue
            if i + 1 >= n or src[i + 1] == "'":
                raise LeanLexError(f"offset {i}: a quote that starts no char literal")
            j = _escape(src, i + 1, False) if src[i + 1] == "\\" else i + 2
            if j >= n or src[j] != "'":
                raise LeanLexError(f"offset {i}: missing end of character literal")
            out.append(("char", src[i:j + 1]))
            i = j + 1
        elif "0" <= c <= "9":
            if prev == ".":   # a projection `x.1` (fieldIdxFn): digits only
                j = i
                while j < n and "0" <= src[j] <= "9":
                    j += 1
            else:
                j = _number(src, i)
            out.append(("number", src[i:j]))
            i = j
        elif c == "r" and _RAW_START.match(src, i):
            hashes = len(_RAW_START.match(src, i).group(1))
            close = '"' + "#" * hashes
            j = src.find(close, i + 2 + hashes)
            if j < 0:
                raise LeanLexError(f"offset {i}: unterminated raw string literal")
            out.append(("string", src[i:j + len(close)]))
            i = j + len(close)
        elif _id_first(c) or c == "«":
            j = i
            while True:
                if src[j] == "«":
                    k = src.find("»", j + 1)
                    if k < 0:
                        raise LeanLexError(f"offset {j}: unterminated identifier escape")
                    j = k + 1
                else:
                    j += 1
                    while j < n and _id_rest(src[j]):
                        j += 1
                if j + 1 < n and src[j] == "." and (_id_first(src[j + 1]) or src[j + 1] == "«"):
                    j += 1
                    continue
                break
            out.append(("ident", src[i:j]))
            i = j
        else:
            out.append(("symbol", c))
            i += 1
    return out


def ident_name(text: str) -> str:
    """An identifier as Lean names it: the escapes «…» dropped, components joined by '.'."""
    parts = re.findall(r"«([^»]*)»|([^.«]+)", text)
    return ".".join(a or b for a, b in parts)


def strip_comments(src: str) -> str:
    """Lean source without comments (line, block and doc comments, located as Lean's tokenizer locates them);
    everything else is kept verbatim. Raises LeanLexError when the source cannot be classified exactly."""
    return "".join(t for k, t in lex(src) if k != "comment")


def scan_text(src: str) -> str:
    """What the G3 scan reads: the code tokens, comments dropped, each identifier by its Lean name between spaces
    (so `«sorry»` reads as sorry, and no neighbouring symbol hides a word boundary), string and char literals
    emptied (lexed exactly, and none interpolated). Raises LeanLexError like lex."""
    out = []
    for k, t in lex(src):
        if k == "comment":
            out.append(" ")
        elif k == "ident":
            out.append(" " + ident_name(t) + " ")
        elif k == "string":
            out.append(' "" ')
        elif k == "char":
            out.append(" '' ")
        elif k == "number":
            out.append(" " + t + " ")
        else:
            out.append(t)
    return "".join(out)


def _code_tokens(src: str) -> list[tuple[str, str]]:
    """The code tokens of src (whitespace and comments dropped). Raises LeanLexError like lex."""
    return [(k, t) for k, t in lex(src) if k not in ("ws", "comment")]


def structure_violations(toks: list[tuple[str, str]]) -> list[str]:
    """What the allowlists refuse (F36 review): a set_option outside SET_OPTION_ALLOWED, a `#` command outside
    HASH_CMD_ALLOWED, and any attribute (`@[` or the `attribute` command)."""
    bad = set()
    for i, (k, t) in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ("", "")
        if k == "ident" and ident_name(t) == "set_option":
            name = ident_name(nxt[1]) if nxt[0] == "ident" else nxt[1]
            if name not in SET_OPTION_ALLOWED:
                bad.add(f"set_option {name}")
        elif k == "ident" and ident_name(t) == "attribute":
            bad.add("attribute")
        elif k == "symbol" and t == "@" and nxt == ("symbol", "["):
            bad.add("@[")
        elif k == "symbol" and t == "#" and nxt[0] == "ident" and ident_name(nxt[1]) not in HASH_CMD_ALLOWED:
            bad.add("#" + ident_name(nxt[1]))
    return sorted(bad)


def forbidden(src: str) -> list[str]:
    """The FORBIDDEN words and commands in the code Lean compiles, and what the allowlists refuse; a file the audit
    cannot lex exactly yields ['unlexable: <reason>'] (refused, never silently passed)."""
    try:
        code = scan_text(src)
        toks = _code_tokens(src)
    except LeanLexError as e:
        return [f"unlexable: {e}"]
    return sorted(set(m.group(0) for m in FORBIDDEN.finditer(code))
                  | {"#" + m.group(1) for m in FORBIDDEN_CMD.finditer(code)}
                  | set(structure_violations(toks)))


def g3_violations(files, root: Path | str = ROOT) -> list[str]:
    """Lean G3 over committed files: '<path>: <hits>' for each file whose code holds a FORBIDDEN word or command, or
    that the audit cannot lex. Each file is decoded from its bytes, never read in text mode: universal newlines
    would turn a lone carriage return (which does not end a Lean line comment) into a line end (F36)."""
    bad = []
    for f in files:
        f = Path(f)
        try:
            hits = forbidden(f.read_bytes().decode("utf-8"))
        except UnicodeDecodeError as e:
            hits = [f"unlexable: not UTF-8 ({e})"]
        if hits:
            try:
                name = f.resolve().relative_to(Path(root).resolve()).as_posix()
            except ValueError:
                name = f.as_posix()
            bad.append(f"{name}: {hits}")
    return bad


def first_error_block(out: str) -> str:
    """The text of Lean's first error, up to the next error or warning."""
    lines = out.splitlines()
    i = next((k for k, line in enumerate(lines) if re.search(r"(^|: )error:", line)), None)
    if i is None:
        return ""
    j = next((k for k in range(i + 1, len(lines)) if re.search(r"(^|: )(error|warning):", lines[k])), len(lines))
    return "\n".join(lines[i:j])


def semantic_rejection(out: str) -> bool:
    """Was a canary rejected for a semantic reason (SEMANTIC_REJECTION in its first error, and no parse, name or
    goal-shape error anywhere)? A canary rejected for any other reason proves nothing about the kernel."""
    return bool(SEMANTIC_REJECTION.search(first_error_block(out))) and not NON_SEMANTIC.search(out)


def theorems(src: str) -> list[str]:
    """Every theorem the file declares, by its name token after the `theorem` keyword wherever it stands (mid-line,
    after a modifier or a doc comment; F36 review), in source order, each once. A name `#print axioms` cannot
    resolve from the end of the file (one inside a namespace) gets no audit line and the check fails closed
    (missing_theorem)."""
    toks = _code_tokens(src)
    names = []
    for i, (k, t) in enumerate(toks[:-1]):
        if k == "ident" and t == "theorem" and toks[i + 1][0] == "ident":
            name = ident_name(toks[i + 1][1])
            if name not in names:
                names.append(name)
    return names


_AX = re.compile(r"'([^']+)' (does not depend on any axioms|depends on axioms: \[([^\]]*)\])", re.S)


def parse_axioms(out: str) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    for m in _AX.finditer(out):
        res[m.group(1)] = sorted(a.strip() for a in (m.group(3) or "").replace("\n", " ").split(",") if a.strip())
    return res


# ------------------------------------------------------------------ checking one text
def _project(d: Path, src: str, names: list[str], cfg: dict) -> None:
    d.mkdir(parents=True)
    (d / "lean-toolchain").write_text(cfg["toolchain"] + "\n")
    (d / "lakefile.toml").write_text(f'name = "holoncheck"\ndefaultTargets = ["{MODULE}"]\n\n'
                                     f'[[lean_lib]]\nname = "{MODULE}"\n')
    audit = "".join(f"\n#print axioms {t}" for t in names)
    (d / f"{MODULE}.lean").write_text(src.rstrip("\n") + "\n\n-- appended by holon.lean (axiom audit)" + audit + "\n")


def check_text(src: str, tmpdir, expect: list[str] | None = None, cfg: dict | None = None,
               timeout: float | None = None) -> dict:
    """Check one Lean source in a fresh lake project under tmpdir.

    result: checked (Lean accepts it, every declared theorem is audited, axioms within ALLOWED_AXIOMS and
    every `expect`ed theorem present) | rejected | forbidden | bad_axioms | missing_theorem | timeout |
    unavailable. Also returns axioms (union over the theorems), per-theorem axioms, seconds and out."""
    cfg = cfg or config()
    base = {"result": "rejected", "axioms": [], "theorems": {}, "seconds": 0.0, "out": ""}
    bad = forbidden(src)   # first: theorems() lexes the source, and a source the audit cannot lex is refused here
    if bad:
        return {**base, "result": "forbidden", "out": f"forbidden in the source: {bad}"}
    names = theorems(src)
    try:
        b = toolchain_bin(cfg)
    except LeanUnavailable as e:
        return {**base, "result": "unavailable", "out": str(e)}
    d = Path(tmpdir) / f"proj-{hashlib.sha256(src.encode()).hexdigest()[:12]}"
    if d.exists():
        shutil.rmtree(d)  # never reuse a build
    _project(d, src, names, cfg)
    t0 = time.monotonic()
    try:
        p = subprocess.run([str(b / "lake"), "build", "--no-cache", "--log-level=info"], cwd=d, env=_env(b),
                           capture_output=True, text=True, timeout=timeout or cfg["timeout_s"])
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return {**base, "result": "timeout", "seconds": round(time.monotonic() - t0, 3),
                "out": f"timeout after {timeout or cfg['timeout_s']} s\n{out[-4000:]}"}
    secs = round(time.monotonic() - t0, 3)
    out = p.stdout + p.stderr
    ax = parse_axioms(out)
    union = sorted({a for t in names for a in ax.get(t, [])})
    res = {**base, "axioms": union, "theorems": {t: ax.get(t) for t in names}, "seconds": secs, "out": out}
    if p.returncode != 0 or re.search(r"(^|\n)error:|: error:", out):
        return {**res, "result": "rejected"}
    if not names or any(ax.get(t) is None for t in names) or any(t not in names for t in (expect or [])):
        return {**res, "result": "missing_theorem"}
    if not set(union) <= ALLOWED_AXIOMS:
        return {**res, "result": "bad_axioms"}
    return {**res, "result": "checked"}


def flip_canary(src: str) -> str:
    """The source with its main claim's relation flipped (= to ≠, or ≠ to =), proof unchanged: Lean must
    reject it. The main claim is the one line carrying CLAIM_MARK (holon.gen.lean_laws)."""
    lines = src.split("\n")
    idx = [i for i, l in enumerate(lines) if l.rstrip().endswith(CLAIM_MARK)]
    if len(idx) != 1:
        raise ValueError(f"expected exactly one line marked {CLAIM_MARK!r}, found {len(idx)}")
    i = idx[0]
    code = lines[i][: lines[i].rindex(CLAIM_MARK)]
    if code.count(" ≠ ") == 1 and code.count(" = ") == 0:
        code = code.replace(" ≠ ", " = ")
    elif code.count(" = ") == 1 and code.count(" ≠ ") == 0:
        code = code.replace(" = ", " ≠ ")
    else:
        raise ValueError(f"the marked claim has no single top-level relation: {code.strip()[:200]}")
    lines[i] = code + CLAIM_MARK + " (flipped canary)"
    return "\n".join(lines)


# ------------------------------------------------------------------ emission for a milestone
def facts_path(milestone: str, root: Path) -> Path:
    reg = json.loads((root / "laws" / milestone / "REGISTRY.json").read_text())
    return root / reg.get("facts", "facts/morph_header.json")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def emit_for(law: dict, facts: dict, facts_sha256: str, verdict: str, witness: dict | None) -> tuple[str, dict]:
    """(Lean text, info) for a law and the verdict to re-check; raises LeanUnsupported."""
    from . import ir
    from .gen import lean_laws, lean_proofs
    ll = lean_laws.emit(law, facts, ir.statement_hash(law))
    return lean_proofs.emit_file(law, facts, facts_sha256, ll, verdict, ir.render_statement(law), witness)


def lean_dir(milestone: str, root: Path | str = ROOT) -> Path:
    return Path(root) / "gen" / milestone / SUBDIR


def applicable(milestone: str, root: Path | str = ROOT) -> bool:
    from . import ir
    return ir.ir_version_of(milestone, root) == "holon-ir/0.1"


def plan(milestone: str, root: Path) -> tuple[list[dict], dict, str]:
    """[(law, verdict, witness, text | None, info | error)] from the laws and the committed records."""
    from . import ir
    from .gen.lean_model import LeanUnsupported, load_facts
    fp = facts_path(milestone, root)
    facts, fsha = load_facts(fp), hashlib.sha256(fp.read_bytes()).hexdigest()
    out = []
    for law in ir.load_laws(milestone, root):
        lid = law["law_id"]
        rp = root / "results" / milestone / f"{lid}.json"
        rec = json.loads(rp.read_text()) if rp.exists() else {}
        verdict = rec.get("status", "UNKNOWN")
        item = {"law": law, "law_id": lid, "verdict": verdict, "witness": rec.get("witness"), "text": None}
        if verdict not in ("PROVED", "REFUTED"):
            item["error"] = f"no Bend verdict to re-check (status {verdict})"
        else:
            try:
                item["text"], item["info"] = emit_for(law, facts, fsha, verdict, rec.get("witness"))
            except LeanUnsupported as e:
                item["error"] = f"unsupported: {e}"
        out.append(item)
    return out, facts, fsha


def run(milestone: str = "M0", root: Path | str = ROOT, jobs: int = 1, log=print) -> dict:
    root = Path(root).resolve()
    cfg = config(root)
    if not applicable(milestone, root):
        raise SystemExit(f"holon lean: {milestone} is not a holon-ir/0.1 milestone (Lean emitters cover M0's IR)")
    items, _, fsha = plan(milestone, root)
    ok, version = toolchain_ok(cfg)
    d = lean_dir(milestone, root)
    tmp = Path(tempfile.mkdtemp(prefix="holon-lean-"))

    def one(it):
        if it["text"] is None:
            return {"result": "unsupported" if it["error"].startswith("unsupported") else "not_run",
                    "axioms": [], "theorems": {}, "seconds": 0.0, "out": it["error"]}
        if not ok:
            return {"result": "unavailable", "axioms": [], "theorems": {}, "seconds": 0.0,
                    "out": f"Lean is not the pinned toolchain: {version}"}
        r = check_text(it["text"], tmp / it["law_id"], expect=[it["info"]["main"]], cfg=cfg)
        if r["result"] == "checked" and r["seconds"] > cfg["budget_s_per_file"]:
            r = {**r, "result": "timeout", "out": f"over the budget of {cfg['budget_s_per_file']} s\n" + r["out"]}
        return r

    try:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
            results = list(ex.map(one, items))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    report = {"milestone": milestone, "kernel": "lean4", "lean_version": cfg["pinned_version"],
              "toolchain": cfg["toolchain"], "lean": lean_version(cfg) if ok else None,
              "fingerprint": fingerprint(cfg)["fingerprint"] if ok else None, "facts_sha256": fsha,
              "allowed_axioms": sorted(ALLOWED_AXIOMS), "laws": {}}
    cli = {"laws": {}}
    for it, r in zip(items, results):
        lid = it["law_id"]
        entry = {"result": r["result"], "axioms": r["axioms"], "verdict": it["verdict"],
                 "statement_hash": _hash(it["law"]),
                 "source": f"gen/{milestone}/{SUBDIR}/{lid}.lean" if it["text"] is not None else None,
                 "source_sha256": sha256_text(it["text"]) if it["text"] is not None else None,
                 "theorems": r["theorems"], "main": (it.get("info") or {}).get("main"),
                 "generator": (it.get("info") or {}).get("generator")}
        if r["result"] != "checked":
            entry["error"] = _first_error(r["out"])
        report["laws"][lid] = entry
        cli["laws"][lid] ={"result": r["result"], "axioms": r["axioms"], "seconds": r["seconds"],
                            "verdict": it["verdict"], **({"error": entry["error"]} if "error" in entry else {})}
        log(f"{lid:16s} {it['verdict']:8s} lean4 {r['result']:10s} {r['seconds']:7.2f} s  axioms {r['axioms']}")
    # written only now, after every check, so an interrupted run never leaves files without their report
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for it in items:
        if it["text"] is not None:
            (d / f"{it['law_id']}.lean").write_text(it["text"], encoding="utf-8")
    (d / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return cli


def _hash(law: dict) -> str:
    from . import ir
    return ir.statement_hash(law)


def _first_error(out: str, n: int = 12) -> str:
    lines = [l for l in out.splitlines() if "error" in l.lower()] or out.strip().splitlines()
    return "\n".join(lines[:n])[:2000]


# ------------------------------------------------------------------ what records may claim
def load_report(milestone: str, root: Path | str = ROOT) -> dict | None:
    p = lean_dir(milestone, root) / REPORT
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def kernel_entry(law: dict, facts: dict, facts_sha256: str, status: str, witness: dict | None,
                 report: dict | None, milestone: str = "M0") -> dict | None:
    """The lean4 entry of a record's kernels[] (None for a milestone the Lean emitters do not cover).

    checked only when the committed report checked exactly the text emitted now for this law, these facts,
    this status and this witness, with allowed axioms; failed when it checked that text and Lean did not
    accept it; otherwise not_run, with the reason."""
    entry = {"name": "lean4", "version": LEAN_VERSION, "role": "second-independent"}
    if status not in ("PROVED", "REFUTED"):
        return {**entry, "result": "not_run", "note": "no verdict to re-check"}
    try:
        text, info = emit_for(law, facts, facts_sha256, status, witness)
    except Exception as e:  # noqa: BLE001  (any facts the Lean emitters cannot express: not run, never a crash)
        return {**entry, "result": "not_run", "note": f"the Lean emitters cannot express this law: "
                                                      f"{type(e).__name__}: {e}"}
    sha = sha256_text(text)
    r = (report or {}).get("laws", {}).get(law["law_id"])
    entry.update({"source": f"gen/{milestone}/{SUBDIR}/{law['law_id']}.lean", "source_sha256": sha,
                  "theorem": info["main"]})
    if not report or report.get("lean_version") != LEAN_VERSION or r is None:
        return {**entry, "result": "not_run", "note": "no Lean report for this law (run `holon lean`)"}
    if r.get("source_sha256") != sha or r.get("verdict") != status or r.get("statement_hash") != _hash(law):
        return {**entry, "result": "not_run",
                "note": "the Lean report is stale: it checked another text (re-run `holon lean`)"}
    if r.get("result") == "checked" and set(r.get("axioms", [])) <= ALLOWED_AXIOMS and r.get("main") == info["main"]:
        return {**entry, "result": "checked", "axioms": sorted(r.get("axioms", []))}
    return {**entry, "result": "failed", "note": f"Lean result {r.get('result')}"}


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon lean")
    ap.add_argument("--milestone", default="M0")
    ap.add_argument("--root")
    ap.add_argument("--json", action="store_true", help="print the report as JSON on stdout")
    ap.add_argument("--jobs", type=int, default=1, help="files checked in parallel (default 1: honest timings)")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    log = (lambda s: print(s, file=sys.stderr)) if a.json else print
    rep = run(a.milestone, root, a.jobs, log)
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep["laws"] and all(r["result"] == "checked" for r in rep["laws"].values()) else 1
