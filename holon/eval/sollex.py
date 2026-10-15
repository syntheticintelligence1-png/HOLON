"""A Solidity lexer over bytes (I48 rules N1 and N3), written from the Solidity 0.8.24 lexical grammar
(docs/grammar/SolidityLexer.g4 of solc v0.8.24) and the contract's text.

lex(src) -> [(kind, start, end)]: the tokens of src in order, as byte offsets. Every byte of src lies in exactly one
token, or in a run of the grammar's whitespace (space, tab, CR, LF, form feed) between tokens, so the tokens with the
whitespace between them give back src byte for byte. src may be any bytes (invalid UTF-8 included). Kinds:

  comment  a line comment (// up to, not including, the next CR or LF) or a block comment (/* to the first */;
           an unterminated one runs to the end of src);
  str      a string literal "..." or '...', a unicode literal unicode"..." or unicode'...', or a hex literal hex"..."
           or hex'...', each one token (a prefix and its quote are adjacent, as the grammar has it); a backslash
           escapes the next byte (in a hex literal too, which has no escapes, so a hex literal simply runs to its
           closing quote); a literal stops before a CR or LF that is not escaped, so an unterminated literal is the
           token up to its line's end;
  id       an identifier, [a-zA-Z$_][a-zA-Z0-9$_]* (keywords and Yul builtins included);
  num      a number by the grammar's longest match: HexNumber 0x h('_'?h)*, DecimalNumber (with its exponent
           [eE]-?digits), OctalNumber, and DecimalNumberFollowedByIdentifier (a decimal number directly followed by an
           identifier, one token: solc rejects it, the grammar names it);
  op       a punctuator or operator of the grammar (longest match), with Yul's := and -> recognised everywhere (they
           occur in no valid Solidity outside assembly);
  other    any other byte: one well-formed UTF-8 character, or one byte that does not start one.

The lexer has one mode: assembly blocks need none (Yul's tokens are a subset of the above, given := and ->), and a
pragma's text is lexed like any other (as solc's scanner does; the grammar's PragmaMode would make it one token).

value(token) -> bytes: the value of a str token's literal (escapes decoded; a hex literal's bytes; the raw bytes of a
unicode literal's characters), for rule N1 (d).
kept(comment) -> bool: rule N1's kept Solidity comment (it holds @solidity or @custom:).
"""
from __future__ import annotations

_WS = frozenset(b" \t\r\n\f")
_ID_START = frozenset(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ$_")
_ID_PART = _ID_START | frozenset(b"0123456789")
_DIGIT = frozenset(b"0123456789")
_HEX = frozenset(b"0123456789abcdefABCDEF")
_LINE_END = frozenset(b"\r\n")
_QUOTES = frozenset(b"\"'")

# The grammar's punctuators and operators (SolidityLexer.g4, default mode) plus Yul's := and ->, longest first.
_OPERATORS = (
    (b">>>=",),
    (b"<<=", b">>=", b">>>"),
    (b"=>", b"->", b"|=", b"^=", b"&=", b"+=", b"-=", b"*=", b"/=", b"%=", b"||", b"&&", b"<<", b">>", b"**", b"==",
     b"!=", b"<=", b">=", b"++", b"--", b":="),
    (b"(", b")", b"[", b"]", b"{", b"}", b":", b";", b".", b"?", b"=", b",", b"|", b"^", b"&", b"+", b"-", b"*",
     b"/", b"%", b"<", b">", b"!", b"~"),
)


def _digits(src: bytes, i: int, allowed: frozenset) -> int:
    """The end of the grammar's `c ('_'? c)*` at i (i itself when src[i] is not in allowed)."""
    n = len(src)
    if i >= n or src[i] not in allowed:
        return i
    i += 1
    while i < n:
        if src[i] in allowed:
            i += 1
        elif src[i] == 0x5F and i + 1 < n and src[i + 1] in allowed:
            i += 2
        else:
            break
    return i


def _identifier_end(src: bytes, i: int) -> int:
    n = len(src)
    if i >= n or src[i] not in _ID_START:
        return i
    i += 1
    while i < n and src[i] in _ID_PART:
        i += 1
    return i


def _decimal_end(src: bytes, i: int) -> int:
    """The end of the longest DecimalNumber (or OctalNumber, never longer) at i, or i."""
    n = len(src)
    j = _digits(src, i, _DIGIT)
    if j < n and src[j] == 0x2E:                       # DecimalDigits? '.' DecimalDigits
        k = _digits(src, j + 1, _DIGIT)
        if k > j + 1:
            j = k
    if j == i:
        return i
    if j < n and src[j] in b"eE":                      # ([eE] '-'? DecimalDigits)?
        k = j + 1
        if k < n and src[k] == 0x2D:
            k += 1
        e = _digits(src, k, _DIGIT)
        if e > k:
            j = e
    return j


def _number_end(src: bytes, i: int) -> int:
    """The end of the longest number token at i, or i."""
    best = i
    n = len(src)
    if src.startswith(b"0x", i):                       # HexNumber
        h = _digits(src, i + 2, _HEX)
        if h > i + 2:
            best = h
    d = _decimal_end(src, i)
    if d > i:
        d = max(d, _identifier_end(src, d))            # DecimalNumberFollowedByIdentifier
    if d > best:
        best = d
    return best if best <= n else n


def _quoted_end(src: bytes, i: int) -> int:
    """src[i] is a quote: the end of the literal it opens (after its closing quote, or before the unescaped line
    end or end of src that leaves it unterminated)."""
    q = src[i]
    n = len(src)
    j = i + 1
    while j < n:
        c = src[j]
        if c == q:
            return j + 1
        if c in _LINE_END:
            return j
        if c == 0x5C:                                  # backslash: escapes the next byte
            j += 2 if j + 1 < n else 1
        else:
            j += 1
    return n


def _utf8_len(src: bytes, i: int) -> int:
    """The length of the well-formed UTF-8 character at i, or 1."""
    c = src[i]
    want = 1 if c >= 0xC2 and c <= 0xDF else 2 if 0xE0 <= c <= 0xEF else 3 if 0xF0 <= c <= 0xF4 else 0
    if want:
        try:
            src[i:i + want + 1].decode("utf-8")
            return want + 1
        except UnicodeDecodeError:
            pass
    return 1


def lex(src: bytes) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    n = len(src)
    i = 0
    while i < n:
        c = src[i]
        if c in _WS:
            i += 1
            continue
        if src.startswith(b"//", i):
            j = i + 2
            while j < n and src[j] not in _LINE_END:
                j += 1
            out.append(("comment", i, j))
            i = j
            continue
        if src.startswith(b"/*", i):
            j = src.find(b"*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(("comment", i, j))
            i = j
            continue
        if c in _QUOTES:
            j = _quoted_end(src, i)
            out.append(("str", i, j))
            i = j
            continue
        if c in _ID_START:
            j = _identifier_end(src, i)
            if src[i:j] in (b"hex", b"unicode") and j < n and src[j] in _QUOTES:
                j = _quoted_end(src, j)
                out.append(("str", i, j))
            else:
                out.append(("id", i, j))
            i = j
            continue
        if c in _DIGIT or (c == 0x2E and i + 1 < n and src[i + 1] in _DIGIT):
            j = _number_end(src, i)
            out.append(("num", i, j))
            i = j
            continue
        for group in _OPERATORS:
            op = next((o for o in group if src.startswith(o, i)), None)
            if op is not None:
                out.append(("op", i, i + len(op)))
                i += len(op)
                break
        else:
            j = i + _utf8_len(src, i)
            out.append(("other", i, j))
            i = j
    return out


_SIMPLE_ESCAPES = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("\\"): b"\\", ord("'"): b"'",
                   ord('"'): b'"', ord("\n"): b"", ord("\r"): b""}


def value(tok: bytes) -> bytes:
    """The value of a str token's literal."""
    if tok.startswith(b"hex"):
        body = tok[4:-1] if len(tok) >= 5 and tok[-1] == tok[3] else tok[4:]
        digits = bytes(b for b in body if b in _HEX)
        return bytes.fromhex(digits[:len(digits) // 2 * 2].decode("ascii"))
    if tok.startswith(b"unicode"):
        tok = tok[7:]
    body = tok[1:-1] if len(tok) >= 2 and tok[-1] == tok[0] else tok[1:]
    out = bytearray()
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c != 0x5C or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        e = body[i + 1]
        if e in _SIMPLE_ESCAPES:
            out += _SIMPLE_ESCAPES[e]
            i += 2
        elif e == ord("x") and i + 4 <= n and all(b in _HEX for b in body[i + 2:i + 4]):
            out.append(int(body[i + 2:i + 4], 16))
            i += 4
        elif e == ord("u") and i + 6 <= n and all(b in _HEX for b in body[i + 2:i + 6]):
            out += chr(int(body[i + 2:i + 6], 16)).encode("utf-8", errors="surrogatepass")
            i += 6
        else:                                          # not an escape of the grammar: the byte after the backslash
            out.append(e)
            i += 2
    return bytes(out)


def kept(comment: bytes) -> bool:
    """Rule N1: a Solidity comment stays verbatim when it holds @solidity or @custom:."""
    return b"@solidity" in comment or b"@custom:" in comment
