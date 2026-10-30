"""The I87 instrument (tests_m3/test_audit_loop.py), written from the contract's text without holon's audit code.

It reads committed files only, at a given commit, through git (never the working tree's copies of laws, records or
generated files, so a later merge of the lead cannot move what a round's target commit decides). It never imports
holon/. Its parts:
  - the vacuity classes V1-V6 and the degenerate rules D1-D3, by its own reading of the laws, records and witnesses;
  - the oracle tables O3, checked with tests_m2/_keccak.py and hashlib (never holon/keccak.py);
  - the convergence rules CV1-CV4 and RD1-RD3, with synthetic round fixtures;
  - the L7 admission rule, with synthetic rule-gap fixtures (gpg verification done here, independently);
  - the expected values the predictions name.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests._util import ROOT
from tests_m2._keccak import keccak256

KEY = "I87"
M = "M3"
BASE = "92c98e40b17a8bdbe516c67e46190098a898f270"   # the lead at I87's branch point (I72's build merged: 136 M3 laws)
POLICY_REL = "spec/M3/lib/audit_loop.json"
STATE_TYPES = ("State", "Reach")
CLASSES = ("no_premises", "not_decided", "counter_witness", "vacuous", "degenerate", "unreadable", "ok")

# I87-P1: the classes of the base's 136 M3 laws
EXPECTED_COUNTS = {"no_premises": 40, "not_decided": 24, "counter_witness": 20, "vacuous": 0, "degenerate": 40,
                   "unreadable": 0, "ok": 12}
# I87-P1: the degenerate inhabitants, by (rule, subform) -> {D-rule set (sorted tuple): count}
EXPECTED_DEGENERATE = {("PAR", "round_trip"): {("D3",): 35}, ("PAR", "cross_component_codec"): {("D3",): 3},
                       ("FACT", "kernel"): {("D2",): 1}, ("DISCH", "revert"): {("D1",): 1}}
# I87-P3: representatives
EXPECTED_REPRESENTATIVES = {"found": 38, "not_found": 0, "not_searched": 2}


# ====================================================================== reading a commit's tree
class Tree:
    """Files of one commit, read with git show / ls-tree (never the working tree)."""

    def __init__(self, commit: str, root: Path = ROOT):
        self.commit, self.root = commit, Path(root)
        self._ls: set | None = None

    def git(self, *args: str) -> bytes:
        p = subprocess.run(["git", "-C", str(self.root), "-c", "core.quotepath=false", *args], capture_output=True,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if p.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()}")
        return p.stdout

    def files(self) -> set:
        if self._ls is None:
            self._ls = set(self.git("ls-tree", "-r", "--name-only", self.commit).decode().split("\n")) - {""}
        return self._ls

    def exists(self, rel: str) -> bool:
        return rel in self.files()

    def read(self, rel: str) -> bytes:
        return self.git("show", f"{self.commit}:{rel}")

    def json(self, rel: str):
        return json.loads(self.read(rel))

    def glob_json(self, prefix: str) -> dict:
        """{stem: json} of prefix/L*.json (one directory level)."""
        out = {}
        for f in sorted(self.files()):
            if f.startswith(prefix + "/") and "/" not in f[len(prefix) + 1:]:
                name = f[len(prefix) + 1:]
                if name.startswith("L") and name.endswith(".json"):
                    out[name[:-5]] = self.json(f)
        return out


def laws_at(tree: Tree, m: str = M) -> dict:
    return tree.glob_json(f"laws/{m}")


def records_at(tree: Tree, m: str = M) -> dict:
    return tree.glob_json(f"results/{m}")


def registry_at(tree: Tree, m: str = M) -> dict:
    return tree.json(f"laws/{m}/REGISTRY.json")["statements"]


def policy(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / POLICY_REL).read_text())


# ====================================================================== vacuity: V1-V6, D1-D3
def premised(law: dict) -> bool:
    st = law["statement"]
    return bool(st.get("assume")) or any(b.get("type") == "Reach" for b in st.get("binders", []))


def state_binders(law: dict) -> list:
    return [b for b in law["statement"].get("binders", []) if b.get("type") in STATE_TYPES]


def _field_term(t):
    if isinstance(t, dict) and set(t) == {"field", "of"} and isinstance(t["of"], dict) and set(t["of"]) == {"var"}:
        return (t["of"]["var"], t["field"])
    return None


def _classes(law: dict) -> tuple[dict, set]:
    """(find: (var, field) -> root, fixed roots): the premises' field equalities as classes; a pin fixes its class."""
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    pins = []
    for p in law["statement"].get("assume") or []:
        if not isinstance(p, dict) or "eq" not in p:
            continue
        a, b = p["eq"]
        fa, fb = _field_term(a), _field_term(b)
        if fa and fb:
            parent[find(fa)] = find(fb)
        elif fa and isinstance(b, dict) and "bytes" in b:
            pins.append(fa)
        elif fb and isinstance(a, dict) and "bytes" in a:
            pins.append(fb)
    fixed = {find(x) for x in pins}
    return find, fixed


def _zero(hexstr) -> bool:
    return isinstance(hexstr, str) and hexstr.startswith("0x") and all(c == "0" for c in hexstr[2:])


def d_rules(law: dict, w) -> tuple[set, bool]:
    """(the D-rules that hold at the inhabitant w, readable): the contract's D1-D3 by this instrument's reading."""
    states = state_binders(law)
    rules: set = set()
    if not isinstance(w, dict):
        return rules, False
    if states:
        if isinstance(w.get("steps"), list):
            if len(w["steps"]) <= 1:
                rules.add("D1")
            return rules, True
        if "prefix" in w and "x" in w:
            if not w["prefix"]:
                rules.add("D1")
            if len(states) >= 2:
                rules.add("D2")
            return rules, True
        if isinstance(w.get("runs"), list):
            runs = w["runs"]
            if runs and all(isinstance(r, dict) and not r.get("prefix") for r in runs):
                rules.add("D1")
            if len(states) >= 2 and len(runs) >= 2 and runs[0] == runs[1]:
                rules.add("D2")
            return rules, True
        runs = [w.get(b["name"]) for b in states]
        if all(isinstance(r, dict) and isinstance(r.get("run"), list) for r in runs):
            if all(not r["run"] for r in runs):
                rules.add("D1")
            if len(runs) >= 2 and runs[0]["run"] == runs[1]["run"]:
                rules.add("D2")
            return rules, True
        return rules, False
    find, fixed = _classes(law)
    readable, free_bytes, all_zero = True, 0, True
    for b in law["statement"].get("binders", []):
        v = w.get(b["name"])
        if isinstance(v, dict):
            for f, hx in v.items():
                if not isinstance(hx, str) or not hx.startswith("0x"):
                    readable = False
                    continue
                if find((b["name"], f)) in fixed:
                    continue
                free_bytes += (len(hx) - 2) // 2
                all_zero = all_zero and _zero(hx)
        elif isinstance(v, str) and v.startswith("0x"):
            free_bytes += (len(v) - 2) // 2
            all_zero = all_zero and _zero(v)
    if readable and all_zero:
        rules.add("D3")
    return rules, readable


def classify(law: dict, rec: dict, registry_hash: str | None, tree: Tree) -> dict:
    """{class, rules}: V1-V6 of the contract."""
    if not premised(law):
        return {"class": "no_premises", "rules": []}
    st = rec.get("status")
    if st == "UNKNOWN":
        return {"class": "not_decided", "rules": []}
    if st == "REFUTED":
        return {"class": "counter_witness", "rules": []}
    nv = rec.get("non_vacuity") or {}
    if (nv.get("status") != "inhabited" or nv.get("parent_statement_hash") != rec.get("statement_hash")
            or rec.get("statement_hash") != registry_hash or nv.get("witness") is None
            or not isinstance(nv.get("law"), str) or not tree.exists(nv["law"])):
        return {"class": "vacuous", "rules": []}
    rules, readable = d_rules(law, nv["witness"])
    if not readable:
        return {"class": "unreadable", "rules": sorted(rules)}
    return {"class": "degenerate" if rules else "ok", "rules": sorted(rules)}


def classify_all(tree: Tree, m: str = M) -> dict:
    lw, rc, reg = laws_at(tree, m), records_at(tree, m), registry_at(tree, m)
    return {lid: classify(law, rc[lid], reg.get(lid), tree) for lid, law in sorted(lw.items())}


def representative_ok(law: dict, w) -> bool:
    """A representative of a pure law: every pin and every field equality of the premises holds at w, and D3 does
    not."""
    find, _fixed = _classes(law)
    for p in law["statement"].get("assume") or []:
        a, b = p["eq"]
        fa, fb = _field_term(a), _field_term(b)

        def val(f):
            return (w.get(f[0]) or {}).get(f[1])
        if fa and fb:
            if val(fa) != val(fb):
                return False
        elif fa and "bytes" in b:
            if val(fa) != b["bytes"]:
                return False
        elif fb and "bytes" in a:
            if val(fb) != a["bytes"]:
                return False
    rules, readable = d_rules(law, w)
    return readable and "D3" not in rules


# ====================================================================== oracle tables (O3)
def tables(rec: dict) -> list[tuple[str, str, str, str]]:
    """(where, oracle, key, word) of every hash-table entry in a record's witness, witnesses and non_vacuity
    witness."""
    out: list = []

    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "hashes" and isinstance(v, dict):
                    for o, lst in sorted(v.items()):
                        for e in lst if isinstance(lst, list) else []:
                            out.append((where, o, e[0], e[1]))
                else:
                    walk(v, where)
        elif isinstance(x, list):
            for v in x:
                walk(v, where)
    walk(rec.get("witness"), "witness")
    walk(rec.get("witnesses"), "witnesses")
    walk((rec.get("non_vacuity") or {}).get("witness"), "non_vacuity")
    return out


def real_word(oracle: str, key: str) -> str | None:
    b = bytes.fromhex(key[2:])
    if oracle == "keccak256":
        return "0x" + keccak256(b).hex()
    if oracle == "sha256":
        return "0x" + hashlib.sha256(b).hexdigest()
    return None


def table_mismatches(records: dict) -> tuple[int, list]:
    n, bad = 0, []
    for lid, rec in sorted(records.items()):
        for where, o, k, wd in tables(rec):
            n += 1
            rw = real_word(o, k)
            if rw is None or int(rw, 16) != int(wd, 16):
                bad.append({"law": lid, "where": where, "oracle": o, "key": k})
    return n, bad


# ====================================================================== convergence (CV1-CV4, RD1-RD3)
CATEGORY_TYPE = {"mutation_adequacy": "A1", "model_vs_code": "A2", "statement_fidelity": "A3", "vacuity": "A4",
                 "bindings_ledger": "A4", "gate_evasion": None, "determinism": None}


def round_types(r: dict) -> set:
    return {a["auditor_type"] for a in r.get("attacks", []) if a.get("auditor_type") and a.get("run", True)}


def converge(rounds: list, findings: list, pol: dict) -> dict:
    """The instrument's CV1-CV4 with RD1-RD3: {valid, converged, streak, counted, rounds: {n: (counted, clean)},
    open_high}."""
    cv = pol["convergence"]
    k, types, fam, high = cv["k"], set(cv["auditor_types"]), cv["counted_family"], set(cv["high_priority_severities"])
    sev = {f["id"]: f.get("severity") for f in findings}
    problems = []
    rs = sorted(rounds, key=lambda r: r["round"])
    if [r["round"] for r in rs] != list(range(1, len(rs) + 1)):
        problems.append("RD3 numbering")
    seen, streak, counted, per = set(), 0, 0, {}
    for r in rs:
        a = r["auditor"]
        claims = a.get("counts_toward_convergence") is True
        if (a["family"] == "same" or r.get("dry_run")) and claims:
            problems.append(f"RD1 round {r['round']}")
        qualifies = (a["family"] == fam and not r.get("dry_run") and types <= round_types(r)
                     and a["session"] not in seen)
        if claims and not qualifies:
            problems.append(f"RD2 round {r['round']}")
        union = sorted({f for at in r.get("attacks", []) for f in at.get("findings", [])})
        if union != sorted(set(r.get("findings", []))):
            problems.append(f"RD3 findings of round {r['round']}")
        is_counted = claims and qualifies
        clean = all(fid in sev and sev[fid] not in high for fid in r.get("findings", []))
        seen.add(a["session"])
        if not clean:
            streak = 0
        elif is_counted:
            streak += 1
        counted += int(is_counted)
        per[r["round"]] = (is_counted, clean)
    open_high = sorted(f["id"] for f in findings if f.get("severity") in high and f.get("status") == "open")
    valid = not problems
    return {"valid": valid, "converged": valid and streak >= k and not open_high, "streak": streak,
            "counted": counted, "rounds": per, "open_high": open_high, "problems": problems}


def make_round(n: int, m: str, session: str, family: str, counts: bool, *, dry: bool = False,
               types=("A1", "A2", "A3", "A4"), findings: dict | None = None) -> dict:
    """A synthetic round: one attack per I5 category; the A1-A4 attacks run iff their type is in `types`.
    findings: {category: [ids]}."""
    findings = findings or {}
    attacks = []
    for i, (cat, t) in enumerate(sorted(CATEGORY_TYPE.items()), start=1):
        at = {"id": f"A{i}", "category": cat, "tried": f"synthetic {cat}", "findings": list(findings.get(cat, [])),
              "run": t is None or t in types}
        at["result"] = "finding" if at["findings"] else "no_finding"
        if t is not None:
            at["auditor_type"] = t
        attacks.append(at)
    r = {"round": n, "milestone": m, "target_commit": "0" * 40, "round_version": "holon-audit-round/0.2",
         "dry_run": dry, "auditor": {"session": session, "family": family, "counts_toward_convergence": counts},
         "attacks": attacks, "findings": sorted({f for v in findings.values() for f in v})}
    return r


def finding(fid: str, severity: str, status: str) -> dict:
    return {"id": fid, "round": "synthetic", "severity": severity, "category": "vacuity", "title": f"synthetic {fid}",
            "reproduction": "synthetic", "status": status, "fix_iteration": "I87", "test": None}


def converge_fixtures(m: str = "M9") -> list[tuple[str, list, list]]:
    """(name, rounds, findings): the R1 scenarios. Expected verdicts come from converge() above."""
    d = lambda n, s, **kw: make_round(n, m, s, "different", True, **kw)   # noqa: E731
    sm = lambda n, s, **kw: make_round(n, m, s, "same", False, **kw)      # noqa: E731
    F = lambda i: f"F-{m}-{i:02d}"                                        # noqa: E731
    return [
        ("no rounds", [], []),
        ("three clean same-family rounds", [sm(1, "s1"), sm(2, "s2"), sm(3, "s3")], []),
        ("three clean different-family rounds", [d(1, "s1"), d(2, "s2"), d(3, "s3")], []),
        ("a repeated session does not count", [d(1, "s1"), d(2, "s2"),
                                               make_round(3, m, "s1", "different", False)], []),
        ("a repeated session claiming to count is invalid", [d(1, "s1"), d(2, "s2"), d(3, "s1")], []),
        ("a same-family high finding resets the streak",
         [d(1, "s1"), sm(2, "s2", findings={"vacuity": [F(1)]}), d(3, "s3"), d(4, "s4")],
         [finding(F(1), "high", "fixed")]),
        ("five rounds after the reset converge",
         [d(1, "s1"), sm(2, "s2", findings={"vacuity": [F(1)]}), d(3, "s3"), d(4, "s4"), d(5, "s5")],
         [finding(F(1), "high", "fixed")]),
        ("an open high finding blocks", [d(1, "s1"), d(2, "s2"), d(3, "s3")], [finding(F(1), "high", "open")]),
        ("medium findings keep a round clean",
         [d(1, "s1", findings={"vacuity": [F(1)]}), d(2, "s2"), d(3, "s3", findings={"model_vs_code": [F(2)]})],
         [finding(F(1), "medium", "open"), finding(F(2), "low", "fixed")]),
        ("a round without A3 does not count",
         [d(1, "s1"), make_round(2, m, "s2", "different", False, types=("A1", "A2", "A4")), d(3, "s3")], []),
        ("a round without A3 claiming to count is invalid",
         [d(1, "s1"), d(2, "s2", types=("A1", "A2", "A4")), d(3, "s3")], []),
        ("a dry run claiming to count is invalid", [d(1, "s1", dry=True), d(2, "s2"), d(3, "s3")], []),
        ("a dry run does not count",
         [make_round(1, m, "s1", "different", False, dry=True), d(2, "s2"), d(3, "s3")], []),
        ("a same-family round claiming to count is invalid",
         [make_round(1, m, "s1", "same", True), d(2, "s2"), d(3, "s3")], []),
        ("an unknown finding id is not clean",
         [d(1, "s1"), d(2, "s2"), d(3, "s3", findings={"vacuity": [F(7)]})], []),
        ("a gap in the numbering is invalid", [d(1, "s1"), d(3, "s3"), d(4, "s4")], []),
        ("a counted high finding resets, then three clean rounds converge",
         [d(1, "s1"), d(2, "s2", findings={"statement_fidelity": [F(1)]}), d(3, "s3"), d(4, "s4"), d(5, "s5")],
         [finding(F(1), "high", "fixed")]),
    ]


# ====================================================================== L7 admission
def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload(candidate: dict) -> bytes:
    """What the human signs: the candidate line without its approval, as canonical JSON."""
    return canonical({k: v for k, v in candidate.items() if k != "approval"})


def gpg_verify(sig: str, data: bytes, key: bytes | None) -> bool:
    if not key or not sig:
        return False
    home = Path(tempfile.mkdtemp(prefix="i87-gpg-"))
    try:
        os.chmod(home, 0o700)
        env = {"GNUPGHOME": str(home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
        (home / "k").write_bytes(key)
        if subprocess.run(["gpg", "--batch", "--quiet", "--import", str(home / "k")], env=env,
                          capture_output=True).returncode != 0:
            return False
        (home / "p").write_bytes(data)
        (home / "p.asc").write_text(sig)
        v = subprocess.run(["gpg", "--batch", "--status-fd", "1", "--verify", str(home / "p.asc"), str(home / "p")],
                           env=env, capture_output=True, text=True)
        return v.returncode == 0 and "[GNUPG:] VALIDSIG" in v.stdout
    finally:
        shutil.rmtree(home, ignore_errors=True)


def admission(lines: list, findings_by_m: dict, frozen_key: bytes | None) -> dict:
    """{candidate name: {"admitted", "fails": [a|b|c]}} by the contract's L7 rule."""
    gaps = {x["id"]: x for x in lines if x.get("kind") == "gap"}
    out = {}
    for c in (x for x in lines if x.get("kind") == "candidate"):
        fails = []
        inst = list(dict.fromkeys(c.get("instances") or []))
        good = [g for g in (gaps.get(i) for i in inst) if g is not None and g.get("candidate") == c["name"]
                and g.get("finding") in findings_by_m.get(g.get("milestone"), set())]
        if len(good) != len(inst) or len({(g["milestone"], g["finding"]) for g in good}) < 2:
            fails.append("a")
        b = c.get("basis") or {}
        if not (isinstance(b.get("argument"), str) and b["argument"].strip()
                and isinstance(b.get("obligation"), str) and b["obligation"].strip()):
            fails.append("b")
        ap = c.get("approval")
        if not (isinstance(ap, dict) and gpg_verify(ap.get("signature") or "", payload(c), frozen_key)):
            fails.append("c")
        out[c["name"]] = {"admitted": not fails, "fails": fails}
    return out


def gap(i: int, m: str, fid: str, cand: str | None) -> dict:
    return {"kind": "gap", "id": f"RG-{m}-{i:02d}", "milestone": m, "finding": fid, "title": f"synthetic gap {i}",
            "outside": "synthetic: no rule of the catalog states it", "candidate": cand}


def candidate(name: str, inst: list, argument: str = "a basis argument", obligation: str = "an obligation",
              approval: dict | None = None) -> dict:
    return {"kind": "candidate", "name": name, "instances": inst,
            "basis": {"argument": argument, "obligation": obligation}, "approval": approval}


def gap_fixtures(m: str = "M9") -> tuple[list, list]:
    """(lines, findings) of the R7 scenarios; the candidate 'SIGNED' is signed by the test with a key it freezes in
    its scratch root."""
    F = lambda i: f"F-{m}-{i:02d}"   # noqa: E731
    lines = [gap(1, m, F(1), "ONE"),
             gap(2, m, F(2), "SAMEF"), gap(3, m, F(2), "SAMEF"),
             gap(4, m, F(3), "NOBASIS"), gap(5, m, F(4), "NOBASIS"),
             gap(6, m, F(5), "UNSIGNED"), gap(7, m, F(6), "UNSIGNED"),
             gap(8, m, F(7), "BOGUS"), gap(9, m, F(8), "BOGUS"),
             gap(10, m, F(90), "GHOST"), gap(11, m, F(91), "GHOST"),
             gap(12, m, F(9), "SIGNED"), gap(13, m, F(10), "SIGNED"),
             candidate("ONE", ["RG-%s-01" % m]),
             candidate("SAMEF", ["RG-%s-02" % m, "RG-%s-03" % m]),
             candidate("NOBASIS", ["RG-%s-04" % m, "RG-%s-05" % m], argument=" "),
             candidate("UNSIGNED", ["RG-%s-06" % m, "RG-%s-07" % m]),
             candidate("BOGUS", ["RG-%s-08" % m, "RG-%s-09" % m],
                       approval={"by": "synthetic", "signature": "-----BEGIN PGP SIGNATURE-----\nAAAA\n"
                                                                 "-----END PGP SIGNATURE-----\n"}),
             candidate("GHOST", ["RG-%s-10" % m, "RG-%s-11" % m]),
             candidate("SIGNED", ["RG-%s-12" % m, "RG-%s-13" % m])]
    findings = [finding(F(i), "medium", "open") for i in range(1, 11)]
    return lines, findings


def make_frozen_root(dest: Path) -> tuple[bytes, str]:
    """A scratch root whose human froze one key: tools/freeze.py with FROZEN_ROOTS naming keys/, FROZEN.sha256
    listing keys/human.asc. Returns (the public key, the GNUPGHOME holding its secret half)."""
    home = Path(tempfile.mkdtemp(prefix="i87-human-"))
    os.chmod(home, 0o700)
    env = {"GNUPGHOME": str(home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
    subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key",
                    "I87 synthetic human <human@invalid>", "ed25519", "sign", "never"], env=env, check=True,
                   capture_output=True)
    pub = subprocess.run(["gpg", "--batch", "--armor", "--export", "human@invalid"], env=env, check=True,
                         capture_output=True).stdout
    (dest / "keys").mkdir(parents=True, exist_ok=True)
    (dest / "keys" / "human.asc").write_bytes(pub)
    (dest / "tools").mkdir(parents=True, exist_ok=True)
    (dest / "tools" / "freeze.py").write_text('FROZEN_ROOTS = ["keys/"]\n')
    (dest / "FROZEN.sha256").write_text(f"{hashlib.sha256(pub).hexdigest()}  keys/human.asc\n")
    return pub, str(home)


def sign(home: str, data: bytes) -> str:
    env = {"GNUPGHOME": home, "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
    p = subprocess.run(["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--armor",
                        "--detach-sign", "--local-user", "human@invalid"], input=data, env=env, check=True,
                       capture_output=True)
    return p.stdout.decode()


def signed_fixture(lines: list, home: str) -> list:
    out = copy.deepcopy(lines)
    for c in out:
        if c.get("kind") == "candidate" and c["name"] == "SIGNED":
            c["approval"] = {"by": "synthetic human", "signature": sign(home, payload(c))}
    return out
