"""A2 held-out mutant sampler, implementing docs/M2_A2_SPEC.md "Held-out mutant set A2".

Sites: lines inside the bodies of FUNCS in Rollup.sol @ target that are a require, an
assignment, or carry a comparison or arithmetic; comment lines and A1 lines are excluded.
Operators are the A1 classes, applied mechanically (at most one candidate per (line, operator)):
  relational          first comparison: < -> <=, <= -> <, > -> >=, >= -> >, == -> !=, != -> ==
  arith_drop          `x += e` / `x -= e` -> rhs 0; else drop the last `+ t` / `- t` binary operand
  guard_deletion      delete a require(...) line
  statement_deletion  delete an assignment that is not a declaration
  condition_drop      drop the last operand of a top-level && / || chain; else if/while (c) -> (true)
  logical             first && <-> ||
  constant            first decimal literal n -> n+1
A candidate whose text equals the original is skipped. The candidates, in file order (line,
then operator in the order above), are put in a random order by random.Random(seed) shuffle,
with seed = int(sha256("\\n".join(sorted A2 statement hashes)), 16) mod 2**32.
The campaign walks that order and keeps the first 30 mutants that compile.
Usage: sample_mutants.py <morph_dir> <registry.json> <out.json>
"""
import hashlib, json, random, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILE = "contracts/contracts/l1/rollup/Rollup.sol"
FUNCS = ["commitBatch", "commitState", "_commitBatchWithBatchData", "revertBatch", "challengeState",
         "proveState", "finalizeBatch", "setPause", "batchInChallenge", "batchInsideChallengeWindow",
         "batchExist"]
OPS = ["relational", "arith_drop", "guard_deletion", "statement_deletion", "condition_drop",
       "logical", "constant"]
TAKE = 30
REL = {"<=": "<", ">=": ">", "==": "!=", "!=": "==", "<": "<=", ">": ">="}
DECL = re.compile(r"^(uint\d*|int\d*|bytes\d*|bool|address|string|BatchDataInput|BatchSignatureInput|"
                  r"BatchData|BatchChallenge\w*|BatchHeader\w*)\b")
CMP_RE = re.compile(r"(<=|>=|==|!=|(?<![<>=!])<(?![<=])|(?<![<>=])>(?![>=]))")


def bodies(lines):
    out = []
    for i, l in enumerate(lines):
        m = re.search(r"\bfunction\s+(\w+)\s*\(", l)
        if not m or m.group(1) not in FUNCS:
            continue
        depth, started = 0, False
        for j in range(i, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            started = started or "{" in lines[j]
            if started and depth == 0:
                out.append((m.group(1), j0 := next(k for k in range(i, j + 1) if "{" in lines[k]) + 2, j))
                break
    return out


def is_assign(code):
    return code.endswith(";") and re.match(r"^[\w\[\]().+\- ]+?\s*(=|\+=|-=)\s*[^=]", code) \
        and not DECL.match(code) and not code.startswith(("require", "return", "emit"))


def operand_end(code, i):
    """end of the operand starting at i: an identifier/number chain (a.b, f(..), m[..])
    with balanced brackets; None if it does not end cleanly."""
    m = re.match(r"[\w.]+", code[i:])
    if m is None:
        if code[i:i + 1] != "(":
            return None
        j = i
    else:
        j = i + m.end()
    while j < len(code) and code[j] in "([":
        close, depth, k = {"(": ")", "[": "]"}[code[j]], 0, j
        while k < len(code):
            depth += code[k] in "([" ; depth -= code[k] in ")]"
            k += 1
            if depth == 0:
                break
        if depth:
            return None
        j = k
        m = re.match(r"\.[\w]+", code[j:])
        if m:
            j += m.end()
    return j


def candidates(code):
    out = {}
    m = CMP_RE.search(code)
    if m:
        out["relational"] = code[:m.start()] + REL[m.group(1)] + code[m.end():]
    m = re.match(r"^(.*?\s(\+=|-=)\s)(.+);$", code)
    if m:
        out["arith_drop"] = m.group(1) + "0;"
    else:
        drops = [(m.start(), operand_end(code, m.end())) for m in re.finditer(r"\s[+-]\s+(?=[\w(])", code)]
        drops = [d for d in drops if d[1] is not None]
        if drops:
            a, b = drops[-1]
            out["arith_drop"] = code[:a] + code[b:]
    if code.startswith("require(") and code.endswith(");"):
        out["guard_deletion"] = ""
    elif is_assign(code):
        out["statement_deletion"] = ""
    ms = list(re.finditer(r"\s(&&|\|\|)\s", code))
    if ms:
        t = ms[-1]
        depth, k = 0, t.end()
        while k < len(code):
            ch = code[k]
            if ch in "([":
                depth += 1
            elif ch in ")]":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and ch in ",;":
                break
            k += 1
        if k < len(code):
            out["condition_drop"] = code[:t.start()] + code[k:]
    else:
        m = re.match(r"^(\}\s*else\s+)?(if|while)\s*\((.*)\)\s*\{$", code)
        if m:
            out["condition_drop"] = (m.group(1) or "") + f"{m.group(2)} (true) {{"
    m = re.search(r"&&|\|\|", code)
    if m:
        out["logical"] = code[:m.start()] + ("||" if m.group() == "&&" else "&&") + code[m.end():]
    m = re.search(r"(?<![\w.])(\d+)(?![\w.])", code)
    if m:
        out["constant"] = code[:m.start()] + str(int(m.group(1)) + 1) + code[m.end():]
    return out


def pool(morph):
    src = (morph / FILE).read_text().splitlines()
    a1 = {(m["file"], m["line"]) for m in json.loads((ROOT / "spec/M2/mutants.json").read_text())["mutants"]}
    out = []
    for fn, lo, hi in bodies(src):
        for ln in range(lo, hi + 1):
            code = src[ln - 1].strip()
            if (FILE, ln) in a1 or not code or code.startswith(("//", "*", "/*", "emit ")):
                continue
            c = candidates(code)
            for op in OPS:
                if op in c and c[op] != code:
                    out.append({"file": FILE, "line": ln, "function": fn, "operator": op,
                                "original": code, "replacement": c[op]})
    return out


def main():
    morph, reg, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    hashes = sorted(json.loads(reg.read_text())["statements"].values())
    seed = int(hashlib.sha256("\n".join(hashes).encode()).hexdigest(), 16) % 2**32
    p = pool(morph)
    order = list(p)
    random.Random(seed).shuffle(order)
    for i, d in enumerate(order, 1):
        d.update(id=f"A{i:03d}", equivalent=False)
    dst.write_text(json.dumps({
        "milestone": "M2-A2", "threshold": 0.8, "take": TAKE,
        "registry_sha256": hashlib.sha256(reg.read_bytes()).hexdigest(), "seed": seed,
        "pool_size": len(p), "rule": "walk `order`; keep the first `take` mutants that compile",
        "order": order}, indent=1) + "\n")
    print(len(p), "candidates, seed", seed)


if __name__ == "__main__":
    main()
