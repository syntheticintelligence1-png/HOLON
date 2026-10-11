"""A2 held-out mutant sampler (lead-authored, preregistered before the A2 law freeze).

Pool: every mechanical mutation of the M1 Rollup slice in Rollup.sol @ target commit, from four
operators: require_delete, statement_delete (state writes), cmp_flip (first comparison on the
line: < <-> <=, > <-> >=, == <-> !=) and neg_drop (drop the first `!` that is not part of `!=`).
A1 sites (same file+line) are excluded, so A2 is held out from A1. The pool is sorted, then
N = 30 mutants are drawn with random.Random(seed), where
seed = sha256 of the sorted statement_hash values in laws/A2/REGISTRY.json at freeze.
Usage: sample_mutants.py <morph_dir> <seed_hex> <out.json> [--pool]
"""
import hashlib, json, random, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILE = "contracts/contracts/l1/rollup/Rollup.sol"
FUNCS = ["commitBatch", "commitState", "commitBatchWithProof", "revertBatch", "challengeState",
         "proveState", "finalizeBatch", "setPause", "batchInChallenge", "batchInsideChallengeWindow",
         "_commitBatchWithBatchData", "_finalizeBatch", "_verifyProof", "_challengerWin",
         "_defenderWin", "_loadBatchHeader"]
MODS = ["onlyOwner", "onlyChallenger", "onlyActiveStaker", "nonReqRevert", "whenNotPaused"]
N = 30
CMP = [("<=", "<"), (">=", ">"), ("==", "!="), ("!=", "=="), ("<", "<="), (">", ">=")]


def ranges(lines, names, kw):
    out = []
    for i, l in enumerate(lines):
        m = re.search(rf"\b{kw}\s+(\w+)\s*\(", l)
        if not m or m.group(1) not in names:
            continue
        depth, started = 0, False
        for j in range(i, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            started = started or "{" in lines[j]
            if started and depth == 0:
                out.append((m.group(1), i + 1, j + 1))
                break
    return out


def cmp_flip(code):
    best = None
    for a, b in CMP:
        for m in re.finditer(re.escape(a), code):
            s = m.start()
            if a in ("<", ">") and (code[s + 1:s + 2] == "=" or code[s - 1:s] in "<>=-" or code[s + 1:s + 2] in "<>"):
                continue
            if a in ("<", ">") and re.match(r"\s*\w+\s*[,>]", code[s + 1:]) and "mapping" in code:
                continue
            if best is None or s < best[0]:
                best = (s, a, b)
    if best is None:
        return None
    s, a, b = best
    return code[:s] + b + code[s + len(a):]


def pool(morph: Path):
    src = (morph / FILE).read_text().splitlines()
    a1 = {(m["file"], m["line"]) for m in json.loads((ROOT / "spec/M2/mutants.json").read_text())["mutants"]}
    out = []
    for fn, lo, hi in ranges(src, set(FUNCS), "function") + ranges(src, set(MODS), "modifier"):
        for ln in range(lo + 1, hi):
            code = src[ln - 1].strip()
            if (FILE, ln) in a1 or not code or code.startswith(("//", "*", "/*", "emit ", "}", "{")):
                continue
            if not code.endswith((";", "{", ")")) or code.startswith(("function", "modifier", "else")):
                continue
            cands = []
            if code.startswith("require(") and code.endswith(");"):
                cands.append(("require_delete", ""))
            elif code.endswith(";") and re.match(r"^[\w\[\].]+\s*(=|\+=|-=)[^=]", code) \
                    and not re.match(r"^(uint|int|bytes|bool|address|BatchData|BatchChallenge)\w*\s", code):
                cands.append(("statement_delete", ""))
            f = cmp_flip(code)
            if f and f != code:
                cands.append(("cmp_flip", f))
            m = re.search(r"!(?!=)", code)
            if m:
                cands.append(("neg_drop", code[:m.start()] + code[m.end():]))
            for op, rep in cands:
                out.append({"file": FILE, "line": ln, "function": fn, "original": code,
                            "replacement": rep, "operator": op})
    out.sort(key=lambda d: (d["line"], d["operator"], d["replacement"]))
    return out


def main():
    morph, seed, dst = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    p = pool(morph)
    if "--pool" in sys.argv:
        dst.write_text(json.dumps(p, indent=1) + "\n")
        print(len(p), "pool candidates")
        return
    pick = random.Random(int(seed, 16)).sample(p, N)
    pick.sort(key=lambda d: (d["line"], d["operator"]))
    for i, d in enumerate(pick, 1):
        d.update(id=f"A{i:02d}", equivalent=False)
    pool_sha = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
    dst.write_text(json.dumps({"seed": seed, "pool_size": len(p), "pool_sha256": pool_sha,
                               "mutants": pick}, indent=1) + "\n")
    print(len(p), "pool,", N, "drawn")


if __name__ == "__main__":
    main()
