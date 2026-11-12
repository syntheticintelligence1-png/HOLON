"""Grounding audit: enumerate the code sites each abstract transition stands for, and fail if the code has a site the
model does not account for (completeness of the abstraction w.r.t. the guarded state).

Usage: python3 sites.py <path to across-protocol/contracts checkout> <out.md>
"""

import re
import sys
from pathlib import Path


def functions(src):
    """Yield (name, header, start_line, end_line, body) for each function/modifier in a Solidity source."""
    for m in re.finditer(r"\b(function|modifier)\s+(\w+)\s*\(", src):
        i = src.index("{", m.end()) if "{" in src[m.end():] else None
        semi = src.find(";", m.end())
        if i is None or (semi != -1 and semi < i):
            continue  # declaration without body
        depth, j = 0, i
        while True:
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        start = src.count("\n", 0, m.start()) + 1
        end = src.count("\n", 0, j) + 1
        yield m.group(2), src[m.start():i], start, end, src[i:j + 1]


def line_of(src, idx):
    return src.count("\n", 0, idx) + 1


def sites(root, rel, pattern):
    src = (root / rel).read_text()
    out = []
    funcs = list(functions(src))
    for m in re.finditer(pattern, src):
        ln = line_of(src, m.start())
        enclosing = [f for f in funcs if f[2] <= ln <= f[3]]
        name = min(enclosing, key=lambda f: f[3] - f[2])[0] if enclosing else "<top>"
        out.append((rel, ln, name, src.splitlines()[ln - 1].strip()))
    return out


def main(root, out_md):
    root = Path(root)
    rows = []
    failures = []

    def expect(title, found, expected_funcs):
        got = sorted({f for (_, _, f, _) in found})
        ok = got == sorted(expected_funcs)
        rows.append((title, found, ok, expected_funcs))
        if not ok:
            failures.append(f"{title}: expected {sorted(expected_funcs)}, found {got}")

    sp = "contracts/spoke-pools/SpokePool.sol"
    hp = "contracts/hub-pool/HubPool.sol"
    # K_fill: every write to fillStatuses (F layer transitions requestSlowFill / fillRelay+executeSlowRelayLeaf).
    all_sol = [p.relative_to(root).as_posix() for p in (root / "contracts").rglob("*.sol") if "/test/" not in p.as_posix()]
    fs = []
    for rel in sorted(all_sol):
        fs += sites(root, rel, r"fillStatuses\[[^\]]+\]\s*=(?!=)")
    expect("writes to fillStatuses (EVM fill key space)", fs, ["_fillRelay", "requestSlowFill"])
    # Callers of the fill pipeline and their guards (V5 quarantine coverage).
    calls = sites(root, sp, r"\b_fillRelay(V3)?\(")
    calls = [c for c in calls if not c[3].startswith("function")]
    expect("callers of _fillRelay/_fillRelayV3", calls, ["_fillRelayV3", "_fillV5", "executeSlowRelayLeaf", "fillRelay", "fillRelayWithUpdatedDeposit"])
    src = (root / sp).read_text()
    guard = {}
    for name, header, _, _, _ in functions(src):
        if name in ("fillRelay", "fillRelayWithUpdatedDeposit", "executeSlowRelayLeaf", "requestSlowFill"):
            guard[name] = "nonV5Fill" in header
    if not all(guard.values()):
        failures.append(f"nonV5Fill missing on {sorted(k for k, v in guard.items() if not v)}")
    rows.append(("nonV5Fill guard on V3 settlement entrypoints", [(sp, 0, k, str(v)) for k, v in sorted(guard.items())], all(guard.values()), list(guard)))
    # K_refund: claimed-bitmap writes on the spoke and HubPool.
    expect("spoke refund-leaf key consumption (MerkleLib.setClaimed)", sites(root, sp, r"MerkleLib\.setClaimed\("), ["_setClaimedLeaf"])
    expect("hub leaf key consumption (setClaimed1D)", sites(root, hp, r"MerkleLib\.setClaimed1D\("), ["executeRootBundle"])
    # Root delivery: the only writer of rootBundles.
    expect("spoke root-bundle creation (rootBundles.push)", sites(root, sp, r"rootBundles\.push\("), ["relayRootBundle"])
    expect("HubPool relays roots (relayRootBundle payload)", sites(root, hp, r"\"relayRootBundle\(bytes32,bytes32\)\""), ["executeRootBundle"])
    # L layer: every write to the pooled-token ledger and protocol-fee ledger.
    for var, fns in (
        ("liquidReserves", ["_sendTokensToChainAndUpdatePooledTokenTrackers", "_sync", "addLiquidity", "removeLiquidity"]),
        ("utilizedReserves", ["_allocateLpAndProtocolFees", "_sendTokensToChainAndUpdatePooledTokenTrackers", "_sync", "haircutReserves"]),
        ("undistributedLpFees", ["_allocateLpAndProtocolFees", "_updateAccumulatedLpFees"]),
    ):
        expect(f"HubPool writes to {var}", sites(root, hp, rf"\.{var}\s*(\+|-)?=(?!=)"), fns)
    expect("HubPool writes to unclaimedAccumulatedProtocolFees",
           sites(root, hp, r"unclaimedAccumulatedProtocolFees\[[^\]]+\]\s*(\+)?=(?!=)"),
           ["_allocateLpAndProtocolFees", "claimProtocolFeesCaptured"])
    # Bond custody: every bondToken transfer out of / into the HubPool.
    expect("HubPool bondToken movements", sites(root, hp, r"bondToken\.(safeTransfer|safeTransferFrom|transfer)\("),
           ["_cancelBundle", "disputeRootBundle", "emergencyDeleteProposal", "executeRootBundle", "proposeRootBundle"])
    # A layer: classify each spoke's _requireAdminSender (following inheritance for spokes that do not override it).
    kinds, parents = {}, {}
    for p in sorted((root / "contracts/spoke-pools").glob("*_SpokePool.sol")):
        s = p.read_text()
        m = re.search(r"function _requireAdminSender\(\)[^{]*\{(.*?)\n    \}", s, re.S)
        mod = re.search(r"function _requireAdminSender\(\)[^{;]*(only\w+)", s)
        inh = re.search(r"contract\s+" + p.stem + r"\s+is\s+([^{]+)\{", s)
        parents[p.stem] = [x.strip() for x in inh.group(1).split(",")] if inh else []
        if not (m or mod):
            continue
        body = (m.group(1) if m else "") + (" " + mod.group(1) if mod else "")
        if re.search(r"if \(!\s*_?\w*[Cc]allValidated\)", body):
            kinds[p.stem] = "flag (temporal)"
        elif any(k in body for k in ("msg.sender", "onlyFromCrossDomainAdmin", "onlyOwner", "crossChainSender")):
            kinds[p.stem] = "principal"

    def kind_of(name):
        if name in kinds:
            return kinds[name], name
        for par in parents.get(name, []):
            if par.endswith("_SpokePool"):
                k, origin = kind_of(par)
                if k:
                    return k, origin
        return None, None

    auth = []
    for name in sorted(parents):
        k, origin = kind_of(name)
        auth.append(("contracts/spoke-pools/" + name + ".sol", 0, name, f"{k} (defined in {origin})"))
    rows.append(("_requireAdminSender classification", auth, True, []))
    # _authorizeUpgrade is the only onlyAdmin function without nonReentrant (ambient-authority sink).
    no_nr = []
    for name, header, ln, _, _ in functions(src):
        if header.startswith("function") and "onlyAdmin" in header and "nonReentrant" not in header:
            no_nr.append((sp, ln, name, header.split("\n")[0].strip()))
    expect("onlyAdmin functions in SpokePool without nonReentrant", no_nr, ["_authorizeUpgrade"])

    lines = ["# Grounding audit (generated by model/sites.py; do not edit)", ""]
    for title, found, ok, exp in rows:
        lines.append(f"## {title} -- {'OK' if ok else 'MISMATCH'}")
        for rel, ln, fn, text in found:
            loc = f"{rel}:{ln}" if ln else rel
            lines.append(f"- `{loc}` in `{fn}`: `{text[:110]}`")
        lines.append("")
    Path(out_md).write_text("\n".join(lines))
    print("\n".join(lines))
    if failures:
        print("FAILURES:\n" + "\n".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
