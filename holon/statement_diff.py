"""laws/STATEMENT_DIFF.jsonl: every statement change goes through an auditable channel (I10; whitepaper
§9.4, §9.5 A3, L14, L22).

The log is append-only: one JSON object per line, {"kind", "law_id", "old": IR, "new": IR, "reason", ...}.
A frozen statement may change only through an entry that this module accepts:

  reextraction     the changed refs come from extractor output that G1 reproduces from the pinned code with
                   the pinned extractor, and `holon derive` reproduces the new statement from the same (rule,
                   subform, basis element) (I20; holon.sorts.reextract). Accepted unsigned only when: the
                   entry's "facts" is an extracted document (extraction.method "extracted") whose sidecar,
                   extracted again from the pinned checkout by its frontend, gives it byte for byte; the
                   statement is unchanged and the refs whose hashes differ between the old derivation (the
                   reextract sidecar disabled) and the new are exactly the entry's "refs", each SORT-site spec
                   carrying that document's evidence; the entry's old_hash/new_hash are the recomputed ones; and
                   holon.rules.compute on the tree gives the new statement with new_hash from the entry's
                   "derivation" (rule, subform, basis), which is also the old law's in HEAD's DERIVATION.json. A
                   facts file written by hand never qualifies. `python -m holon.statement_diff reextract
                   --milestone M [--append]` builds the entries a re-derivation needs (reextraction_entries).
  binding_change   an emitted def changed under a fixed statement: a generated, kernel-checked equivalence, or a
                   signature. Unsigned (F31, _binding_change): the entry names milestone, bound_commit (the commit
                   whose spec/bindings/<m>.json and model gave the law its old binding) and defs (exactly the
                   changed definitions); the check reads the old model from git at bound_commit, verifies both
                   models against the two bindings entry by entry, and runs holon.gen.equivalence.prove: every root
                   the statement names must be unchanged or proven extensionally equal old vs new, by bend and
                   BendTT. A proof carried by the entry is never read. `python -m holon.statement_diff rebind
                   --milestone M [--append]` builds the entries (binding_change_entries).
  strengthening    a kernel-checked S' => S (holon.gen.implication generates the obligation and its proof;
                   Bend, and BendTT when available, must accept it).
  weakening        a gpg signature verifiable against a public key in keys/ (Q3) and an auditor review. A
                   signature is a human act: no key exists, so every weakening is rejected.
  cross_milestone  a later milestone's analogue S_new of an earlier law S_old: a checked S_new => S_old, or a
                   signed weakening. Pairs come from DERIVATION.json back-test links, never from ids
                   (check_cross_milestone).
  catalog_rederivation
                   (F30) the milestone moved to a later rule catalog and its laws were derived again under it. A
                   holon-ir/0.3 statement hash covers rule_catalog_version, so every law's hash changes although no
                   claim does. Accepted unsigned only when all of these hold mechanically (_catalog_rederivation):
                   old and new are 0.3 IR of one law of the entry's milestone; old names old_catalog and new names
                   new_catalog, two different versions of holon.rules.CATALOGS; the two law files are identical with
                   rule_catalog_version masked (claim, binders, premises, scope, facts, facts_sha256, notes, rule,
                   subform: every key); the law's (rule, subform) producer is the same object in both catalogs; and
                   holon derive on the tree under each catalog gives exactly old (with old_hash) and exactly new (with
                   new_hash) from DERIVATION entries that are equal apart from the statement hash, with the entry's
                   (rule, subform, basis). So old_hash and new_hash differ only by the catalog version, never by a
                   ref. The statement-change tie (covers) also requires the entry's two hashes to be the registry
                   change's. It never covers a claim change, a binding change or a deletion. `python -m
                   holon.statement_diff recatalog --milestone M [--append]` builds the entries the milestone's
                   uncovered registry changes need (catalog_rederivation_entries).
  remodel          (I68, rule S11 of tests_m3/test_structural_keys.py; Q21's H1) the model a law is bound to is replaced
                   by a remodel a human answer licenses (REMODELS: Q21's structural storage keys, holon-model-m3/0.2 to
                   0.3, adding A-keccak-structural). The store's type and aliasing differ by design, so no extensional
                   equivalence exists and a binding_change cannot carry it; the statement does not change. Accepted
                   unsigned only when all of _remodel's conditions (a)-(e) hold mechanically: the law file, the
                   emitted statement and counter-law and the model path unchanged since bound_commit, only the cone
                   differs; the license, the two model versions and the ledger entry named and true of the two models
                   and spec/<m>/ledger.json; the typed model regenerated byte for byte; its R5 record on the frozen I20
                   corpus with I20's counts and 0 disagreements, and its keys check with no collision; the law's record
                   remade on it. `python -m holon.statement_diff remodel --milestone M [--append]` builds the entries
                   (remodel_entries), and `holon bind --remodel` appends them before it rebinds. It never covers a
                   statement change.

API:
  check_entry(entry, root) -> {"ok", "reason", "implication"}      implication: holon.gen.implication.prove
  check_file(path, root) -> [problem]                              every line, plus append-only over git history
  scan(path, root) -> {"problems", "entries", "git", "note"}       check_file with each line's verdict
  check_cross_milestone(derivation, laws, entries, root, accepted=None) -> [problem]
  registry_changes(milestone, root) -> {"git", "changes", "note"}  statement-hash changes the log must cover
  tie_problems(milestone, root, scanned) -> ([problem], note)      G2: every change covered by an accepted entry
  catalog_rederivation_entries(milestone, root) -> (entries, notes) the catalog_rederivation entries still needed

Each line is checked once, against the tree it was appended to (audit F-M2-22). `python -m holon.statement_diff
append ENTRY.json` runs check_entry on the working tree and, only when it accepts, appends the entry with an
`accepted` record: the sha256 of every facts file the entry's statements are about and, for an implication, the
sha256 of the generated obligation and of the proof Bend accepted. Then:
  * a line not yet committed (beyond HEAD's version of the log) is checked in full against the working tree, and
    its recorded hashes must equal the ones the check gives now;
  * a committed line is not re-proved: its recorded facts hashes must equal those files at the commit that
    appended it (read-only git cat-file). A later facts change therefore never invalidates an accepted line, and
    the append-only log never keeps G2 red because of one.
Off git (a copied tree) every line counts as new and is checked against the working tree.

The statement-change tie (audit F-M2-08, whitepaper G2 "changes only per §9.4"): every law whose registry hash
changed, in a commit after the log was introduced or in the working tree against HEAD, or which was deleted, needs
an accepted entry for that law whose old and new statements are exactly the two versions (a deletion: an accepted
weakening whose old is the deleted statement). Off git the tie cannot run, and G2 says so instead of passing it
silently.

Self-certified until the human freezes this module, keys/ and the registries (Q1): A3
(holon audit regress) and human review are the backstop.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import ir

KINDS = ("reextraction", "binding_change", "strengthening", "weakening", "cross_milestone", "catalog_rederivation",
         "remodel")
KEY_SUFFIXES = (".asc", ".gpg", ".pub", ".key")
LOG = Path("laws") / "STATEMENT_DIFF.jsonl"
STATEMENT_KINDS = ("reextraction", "binding_change", "strengthening", "weakening",
                   "catalog_rederivation")   # kinds that change one law
CATALOG_KEY = "rule_catalog_version"   # the one IR key a catalog_rederivation may change
# (I68) the remodels a human answer licenses: (license, old model version, new model version) -> the ledger entry the
# new model adds. Q21 (docs/HUMAN_ANSWERS.md): the M3 model keys its storage structurally.
REMODELS = {("Q21", "holon-model-m3/0.2", "holon-model-m3/0.3"): "A-keccak-structural"}
I20_RECORD = Path("results") / "M2" / "refinement" / "extracted.json"   # I20's record of the frozen extracted corpus
# what identifies a statement (the hashed keys of every IR version, and the facts file it is about)
_CORE = tuple(dict.fromkeys(ir.HASHED_KEYS + ir.HASHED_KEYS_03 + ("facts",)))


def _res(ok: bool, reason: str, implication: dict | None = None, equivalence: dict | None = None,
         remodel: dict | None = None) -> dict:
    out = {"ok": ok, "reason": reason, "implication": implication}
    if equivalence is not None:
        out["equivalence"] = equivalence
    if remodel is not None:
        out["remodel"] = remodel
    return out


def _is_law(x) -> bool:
    return isinstance(x, dict) and isinstance(x.get("law_id"), str) and isinstance(x.get("statement"), dict)


def core(law: dict) -> bytes:
    return ir.canonical_json({k: law.get(k) for k in _CORE})


# ---------------------------------------------------------------- signatures (Q3)
def signed_payload(entry: dict) -> bytes:
    """What a signature covers: the entry without its signature and without the acceptance record the append tool
    adds after checking it, as canonical JSON."""
    return ir.canonical_json({k: v for k, v in entry.items() if k not in ("signature", "accepted")})


FREEZE_TOOL = Path("tools") / "freeze.py"
FROZEN_MANIFEST = "FROZEN.sha256"


def _frozen_listing(data: bytes | None) -> dict[str, str]:
    """{path: sha256} of a FROZEN.sha256 text (`<sha256>  <path>` per line), as tools/freeze.py check reads it."""
    out = {}
    for line in (data or b"").decode("utf-8", "replace").splitlines():
        h, sep, f = line.partition("  ")
        if sep and len(h) == 64 and all(c in "0123456789abcdef" for c in h):
            out[f] = h
    return out


def _freeze_roots(data: bytes | None) -> list[str]:
    """FROZEN_ROOTS of a tools/freeze.py text, read as a literal (never executed; anything else reads as none), each
    without a trailing slash."""
    import ast
    try:
        for node in ast.parse((data or b"").decode("utf-8", "replace")).body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            else:
                continue
            if any(isinstance(t, ast.Name) and t.id == "FROZEN_ROOTS" for t in targets):
                roots = ast.literal_eval(node.value)
                return [r.rstrip("/") for r in roots if isinstance(r, str)]
    except (SyntaxError, ValueError, TypeError):
        pass
    return []


def _key_path(rel: str) -> bool:
    """keys/<name>: one plain file name directly under keys/ with a KEY_SUFFIXES suffix."""
    parts = rel.split("/")
    return (len(parts) == 2 and parts[0] == "keys" and parts[1] not in ("", ".", "..")
            and "\\" not in parts[1] and Path(parts[1]).suffix in KEY_SUFFIXES)


def frozen_keys(root: Path, commit: str | None = None) -> tuple[list[bytes], str]:
    """The public keys a signature is verified against (F38, Q39): only keys the human froze. A key keys/<name>
    counts when tools/freeze.py puts it under the freeze (FROZEN_ROOTS names keys/ or the file), FROZEN.sha256
    lists it, and its bytes hash to the listed sha256, all in the tree being checked; for a committed line
    (`commit`, the commit that appended it), FROZEN.sha256 at that commit must list the same key with the same hash
    and the key's bytes there must match it too (a key frozen later, or changed, signs nothing earlier). Agents
    never freeze (AGENTS.md rule 1): until the human freezes a key, every signature fails. ([keys], why)."""
    root = Path(root)
    tool, manifest = root / FREEZE_TOOL, root / FROZEN_MANIFEST
    roots = _freeze_roots(tool.read_bytes() if tool.is_file() else None)
    listed = _frozen_listing(manifest.read_bytes() if manifest.is_file() else None)
    cand = sorted(f for f in listed if _key_path(f) and ("keys" in roots or f in roots))
    if not cand:
        return [], ("no public key is frozen: a signature counts only against a key in keys/ that the human froze "
                    "(under tools/freeze.py FROZEN_ROOTS and listed in FROZEN.sha256, Q3); none is")
    then = _frozen_listing(blob_at(root, commit, FROZEN_MANIFEST)) if commit else listed
    keys, skipped = [], []
    for f in cand:
        b = blob_at(root, commit, f) if commit else ((root / f).read_bytes() if (root / f).is_file() else None)
        if b is not None and _sha(b) == listed[f] == then.get(f):
            keys.append(b)
        else:
            skipped.append(f)
    if not keys:
        at = f" at {commit[:7]}" if commit else ""
        return [], f"no frozen public key{at} matches FROZEN.sha256 ({', '.join(skipped)})"
    return keys, f"{len(keys)} frozen key(s)"


def verify_signature(entry: dict, root: Path, commit: str | None = None) -> tuple[bool, str]:
    """A detached, ASCII-armored gpg signature over signed_payload(entry), made by a frozen key (frozen_keys; for
    a committed line, as the commit that appended it had the key). The keys are imported into a throwaway
    GNUPGHOME under names of their own, so no keyring outside them is trusted and no path in the tree is."""
    sig = entry.get("signature")
    if not isinstance(sig, str) or not sig.strip():
        return False, "no gpg signature: this needs a signature verifiable against a frozen key in keys/ (Q3)"
    keys, why = frozen_keys(root, commit)
    if not keys:
        return False, f"the signature cannot be verified: {why} (a signature is a human act, Q3)"
    gpg = shutil.which("gpg")
    if not gpg:
        return False, "the signature cannot be verified: gpg is not installed"
    home = Path(tempfile.mkdtemp(prefix="holon-gpg-"))
    try:
        os.chmod(home, 0o700)
        env = {"GNUPGHOME": str(home), "PATH": os.environ.get("PATH", ""), "LC_ALL": "C"}
        files = []
        for i, b in enumerate(keys):
            (home / f"key{i}").write_bytes(b)
            files.append(str(home / f"key{i}"))
        imp = subprocess.run([gpg, "--batch", "--quiet", "--import", *files], env=env, capture_output=True)
        if imp.returncode != 0:
            return False, "the signature cannot be verified: the frozen keys do not import"
        (home / "payload").write_bytes(signed_payload(entry))
        (home / "payload.asc").write_text(sig)
        v = subprocess.run([gpg, "--batch", "--status-fd", "1", "--verify", str(home / "payload.asc"), str(home / "payload")],
                           env=env, capture_output=True, text=True)
        if v.returncode == 0 and "[GNUPG:] VALIDSIG" in v.stdout:
            return True, "gpg signature verified against a frozen key in keys/"
        return False, "the gpg signature does not verify against the frozen keys in keys/"
    finally:
        shutil.rmtree(home, ignore_errors=True)


# ---------------------------------------------------------------- entries
def check_entry(entry: dict, root: Path | None = None) -> dict:
    root = Path(root or ir.ROOT)
    if not isinstance(entry, dict):
        return _res(False, "an entry is a JSON object")
    kind = entry.get("kind")
    if kind not in KINDS:
        return _res(False, f"unknown entry kind {kind!r} (one of {', '.join(KINDS)})")
    old, new = entry.get("old"), entry.get("new")
    if not (_is_law(old) and _is_law(new)):
        return _res(False, "an entry carries the old and the new statement as law IR")
    if kind in ("reextraction", "binding_change", "strengthening", "catalog_rederivation", "remodel"):
        lid = entry.get("law_id", old["law_id"])
        if not old["law_id"] == new["law_id"] == lid:
            return _res(False, f"a {kind} changes one law: old, new and law_id must name the same law")
    if kind == "catalog_rederivation":
        return _catalog_rederivation(entry, old, new, root)
    if kind == "remodel":
        if core(old) != core(new):
            return _res(False, "a remodel keeps the statement fixed, and this entry changes it")
        return _remodel(entry, old, new, root)
    if kind == "weakening":
        ok, why = verify_signature(entry, root)
        if not ok:
            return _res(False, f"unsigned or unverified weakening: {why}")
        if not entry.get("review"):
            return _res(False, "a signed weakening also needs an auditor review (\"review\")")
        return _res(True, f"weakening: {why}; reviewed")
    if kind == "reextraction":
        return _reextraction(entry, old, new, root)
    if kind == "binding_change":
        if core(old) != core(new):
            return _res(False, "a binding_change keeps the statement fixed, and this entry changes it")
        if entry.get("signature"):
            ok, why = verify_signature(entry, root)
            if ok:
                return _res(True, f"binding_change: {why}")
            return _res(False, f"binding_change: {why}")
        return _binding_change(entry, old, new, root)
    if kind == "cross_milestone" and old.get("milestone") == new.get("milestone"):
        return _res(False, "a cross_milestone entry links laws of two milestones (a change within one is a strengthening)")
    # strengthening, cross_milestone: a checked new => old
    from .gen import implication
    bm = entry.get("binder_map")
    imp = implication.prove(old, new, root, binder_map=bm if isinstance(bm, dict) else None)
    if imp["status"] == "PROVED":
        return _res(True, f"{kind}: {imp['reason']}", imp)
    return _res(False, f"{kind} without a checked {new['law_id']} => {old['law_id']} ({imp['status']}: {imp['reason']})", imp)


_REPRO: dict = {}     # (root, document, its sha256, sidecar sha256) -> (ok, why): one re-extraction per process
_DERIVED: dict = {}   # (root, milestone, inputs fingerprint) -> holon.rules.compute(..)


def reproduce_extraction(rel: str, root: Path) -> tuple[bool, str]:
    """G1 for one extracted document: its sidecar (extraction.sidecar.path, still at extraction.sidecar.sha256)
    extracted again by its frontend from the pinned code (holon.frontends.extract checks the source checkout's commit
    and cleanliness and the pinned solc) gives the document byte for byte. A document whose extraction.method says it
    was written by hand never qualifies."""
    root = Path(root)
    p = root / rel
    if not p.is_file():
        return False, f"the reextraction names {rel!r}, which does not exist"
    data = p.read_bytes()
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError as e:
        return False, f"{rel} is not JSON: {e}"
    ext = doc.get("extraction") if isinstance(doc, dict) else None
    method = str(ext.get("method", "")) if isinstance(ext, dict) else ""
    if not method or "hand" in method.lower():
        return False, (f"{rel} is hand-written (extraction.method = {method!r}): a reextraction must come from "
                       "extractor output that G1 reproduces from the pinned code with the pinned extractor")
    if doc.get("facts_version") != "holon-facts/0.3" or method != "extracted":
        return False, (f"{rel} is not extractor output (facts_version {doc.get('facts_version')!r}, extraction.method "
                       f"{method!r}): a reextraction must come from extractor output that G1 reproduces from the pinned "
                       "code with the pinned extractor")
    side = (ext or {}).get("sidecar") or {}
    srel, ssha = side.get("path"), side.get("sha256")
    if not isinstance(srel, str) or not (root / srel).is_file():
        return False, f"{rel}: its extraction names no sidecar in the tree ({srel!r})"
    got = hashlib.sha256((root / srel).read_bytes()).hexdigest()
    if got != ssha:
        return False, f"{rel}: its sidecar {srel} hashes to {got[:12]}.., the document records {str(ssha)[:12]}.."
    key = (str(root.resolve()), rel, hashlib.sha256(data).hexdigest(), got)
    if key not in _REPRO:
        from . import frontends
        try:
            fresh = frontends.render(frontends.extract(root / srel, root))
        except (frontends.Refused, frontends.ExtractionError) as e:
            _REPRO[key] = (False, f"G1 cannot re-extract {rel} from the pinned code: {type(e).__name__}: {e}")
        else:
            _REPRO[key] = ((True, f"G1 re-extracts {rel} byte for byte with {ext.get('frontend_version')}")
                           if fresh == data else
                           (False, f"G1 re-extracts {rel} from the pinned code with the pinned extractor and gets other "
                                   "bytes: the document is not what the extractor writes"))
    return _REPRO[key]


def _derived(milestone: str, root: Path) -> dict:
    from . import rules
    from .sorts import reextract
    fp = []
    for p in [reextract.sidecar_path(milestone, root)] + sorted((root / "spec").glob("*/lib/window_*.json")):
        fp.append((p.as_posix(), hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None))
    sc = reextract.sidecar(milestone, root) or {}
    for rel in sc.get("documents") or []:
        q = root / rel
        fp.append((rel, hashlib.sha256(q.read_bytes()).hexdigest() if q.is_file() else None))
    key = (str(root.resolve()), milestone, json.dumps(fp))
    if key not in _DERIVED:
        _DERIVED[key] = rules.compute(milestone, root)
    return _DERIVED[key]


def _facts_of(law: dict, root: Path) -> dict:
    return json.loads((root / law["facts"]).read_text())


def _ref_view(law: dict, root: Path, old: bool) -> tuple[dict, str]:
    """(refs, statement hash) of a law on the current tree; old: as before the milestone adopted extracted documents
    (holon.sorts.reextract.disabled)."""
    from .gen import refs as R
    from .sorts import reextract
    facts = _facts_of(law, root)
    if old:
        with reextract.disabled():
            return R.refs(law, facts, root=root), R.law_hash(law, facts, root=root)
    return R.refs(law, facts, root=root), R.law_hash(law, facts, root=root)


def _reextraction(entry: dict, old: dict, new: dict, root: Path) -> dict:
    """A reextraction is accepted unsigned only when (1) G1 reproduces the document it names from the pinned code with
    the pinned extractor, (2) the statement's refs that changed are exactly the entry's, each now hashing what the
    entry says and each carrying that document's evidence, with no other ref and no statement field changed, and (3)
    holon derive reproduces the new statement, with its hash, from the same (rule, subform, basis element) as the old
    one. (I20; holon.sorts.reextract.)"""
    rel = entry.get("facts")
    if not isinstance(rel, str):
        return _res(False, f"a reextraction names the extracted document its changed refs come from (got {rel!r})")
    ok, why = reproduce_extraction(rel, root)
    if not ok:
        return _res(False, why)
    for k in ("old_hash", "new_hash", "refs", "derivation", "milestone"):
        if k not in entry:
            return _res(False, f"a reextraction entry carries {k!r}")
    if core(old) != core(new):
        return _res(False, "a reextraction changes the statement's refs, not the statement: old and new differ")
    refs = entry["refs"]
    if not isinstance(refs, dict) or not refs:
        return _res(False, "a reextraction lists the refs that changed")
    try:
        r_old, h_old = _ref_view(old, root, old=True)
        r_new, h_new = _ref_view(new, root, old=False)
    except (OSError, ValueError, KeyError) as e:
        return _res(False, f"the refs cannot be recomputed: {type(e).__name__}: {e}")
    changed = sorted(k for k in set(r_old) | set(r_new) if r_old.get(k) != r_new.get(k))
    if changed != sorted(refs):
        return _res(False, f"the refs that changed are {changed}, the entry lists {sorted(refs)}")
    for k in changed:
        if refs[k] != {"old": r_old.get(k), "new": r_new.get(k)}:
            return _res(False, f"ref {k}: the entry's hashes are not the recomputed ones")
        if not k.startswith("site:"):
            return _res(False, f"ref {k}: only a SORT-site spec carries extracted evidence")
        from .sorts.sites import site_ref
        from .gen.targetlib import Library, lib_files
        f = _facts_of(new, root)
        lib = Library([json.loads(p.read_text()) for p in lib_files(root / new["facts"], root)], f.get("params", {}))
        spec = site_ref(k[len("site:"):], new, f, lib.builtins, root)
        docs = [x.get("document") for x in spec.get("extracted") or []] if isinstance(spec, dict) else []
        if rel not in docs:
            return _res(False, f"ref {k}: its spec carries no evidence of {rel}")
    if (h_old, h_new) != (entry["old_hash"], entry["new_hash"]):
        return _res(False, "the entry's statement hashes are not the recomputed ones")
    try:
        der = _derived(entry["milestone"], root)
    except Exception as e:  # noqa: BLE001  (a derive that fails reproduces nothing)
        return _res(False, f"holon derive fails on the tree: {type(e).__name__}: {e}")
    law = der["laws"].get(new["law_id"])
    de = next((e for e in der["derivation"]["laws"] if e["law_id"] == new["law_id"]), None)
    if law is None or de is None or core(law) != core(new):
        return _res(False, f"holon derive does not reproduce the new statement of {new['law_id']}")
    if de.get("statement_hash") != entry["new_hash"]:
        return _res(False, f"holon derive gives {new['law_id']} the hash {de.get('statement_hash')}, the entry "
                           f"{entry['new_hash']}")
    same = {k: de.get(k) for k in ("rule", "subform", "basis")}
    if same != entry["derivation"]:
        return _res(False, "holon derive derives the law from another (rule, subform, basis element) than the entry's")
    if in_git(root):
        before = _json_or_none(blob_at(root, "HEAD", f"laws/{entry['milestone']}/DERIVATION.json"))
        if isinstance(before, dict):
            ob = next((e for e in before.get("laws") or [] if e.get("law_id") == old["law_id"]), None)
            if ob is None or {k: ob.get(k) for k in ("rule", "subform", "basis")} != same:
                return _res(False, "the old statement was not derived from the same (rule, subform, basis element)")
    return _res(True, f"reextraction: {why}; refs {', '.join(changed)} carry its evidence; holon derive reproduces "
                      f"the new statement from {same['rule']}/{same['subform']} {json.dumps(same['basis'], sort_keys=True)[:120]}")


def reextraction_entries(milestone: str, root: Path) -> list[dict]:
    """The reextraction entries the milestone's re-derivation needs (holon.sorts.reextract): for every law of
    laws/<M> whose committed statement hash (laws/<M>/REGISTRY.json) differs from holon derive's on the tree and whose
    derivation carries extracted evidence, {"kind": "reextraction", ...} with the law as committed (old) and as derived
    (new). Entries are not appended here (append checks each one)."""
    root = Path(root)
    reg = json.loads((root / "laws" / milestone / "REGISTRY.json").read_text())
    der = _derived(milestone, root)
    out = []
    for e in der["derivation"]["laws"]:
        lid = e["law_id"]
        if "extracted" not in e or lid not in (reg.get("statements") or {}):
            continue
        if reg["statements"][lid] == e["statement_hash"]:
            continue
        old = json.loads((root / "laws" / milestone / f"{lid}.json").read_text())
        new = der["laws"][lid]
        r_old, h_old = _ref_view(old, root, old=True)
        r_new, h_new = _ref_view(new, root, old=False)
        changed = sorted(k for k in set(r_old) | set(r_new) if r_old.get(k) != r_new.get(k))
        docs = sorted({x["document"] for x in e["extracted"]})
        out.append({"kind": "reextraction", "law_id": lid, "milestone": milestone, "old": old, "new": new,
                    "facts": docs[0] if docs else None, "old_hash": h_old, "new_hash": h_new,
                    "refs": {k: {"old": r_old.get(k), "new": r_new.get(k)} for k in changed},
                    "derivation": {k: e.get(k) for k in ("rule", "subform", "basis")},
                    "reason": f"{lid} re-derived on the extracted facts {', '.join(docs)} (holon.sorts.reextract): "
                              "its site spec gains the extracted checks at its span"})
    return out


# ---------------------------------------------------------------- catalog re-derivations (F30)
_CATALOG_DERIVED: dict = {}   # (root, milestone, catalog) -> (inputs listing, holon.rules.compute(..))


def masked(law: dict) -> bytes:
    """A law file without the one key a catalog re-derivation may change, as canonical JSON."""
    return ir.canonical_json({k: v for k, v in law.items() if k != CATALOG_KEY})


def _inputs_fresh(listing: list, root: Path) -> bool:
    for x in listing:
        p = x.get("path", "")
        if p.startswith("<outside>/"):
            return False
        q = root / p
        if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest() != x.get("sha256"):
            return False
    return True


def derived_under(milestone: str, root: Path, catalog: str) -> dict:
    """holon.rules.compute(milestone, root, catalog=catalog), reused within a process while every file it read is
    unchanged."""
    from . import rules
    root = Path(root)
    key = (str(root.resolve()), milestone, catalog)
    hit = _CATALOG_DERIVED.get(key)
    if hit is not None and _inputs_fresh(hit[0], root):
        return hit[1]
    der = rules.compute(milestone, root, catalog=catalog)
    _CATALOG_DERIVED[key] = (der["derivation"].get("inputs") or [{"path": "<outside>/"}], der)
    return der


def _derivation_entry(der: dict, lid: str) -> dict | None:
    return next((e for e in der["derivation"]["laws"] if e.get("law_id") == lid), None)


def _catalog_rederivation(entry: dict, old: dict, new: dict, root: Path) -> dict:
    """A catalog_rederivation (see the module docstring) is accepted only when the two law files differ in
    rule_catalog_version alone, the law's producer is shared by the two catalogs, and holon derive under each
    catalog reproduces each side with its hash from the same basis element."""
    from . import rules
    for k in ("milestone", "old_catalog", "new_catalog", "old_hash", "new_hash", "derivation"):
        if k not in entry:
            return _res(False, f"a catalog_rederivation entry carries {k!r}")
    m, oc, nc = entry["milestone"], entry["old_catalog"], entry["new_catalog"]
    lid = new["law_id"]
    if not (old.get("ir_version") == new.get("ir_version") == "holon-ir/0.3"):
        return _res(False, "only a holon-ir/0.3 statement hash covers the rule catalog version: old and new must be 0.3")
    if old.get("milestone") != m or new.get("milestone") != m:
        return _res(False, f"old and new must be laws of the entry's milestone {m!r}")
    if old.get(CATALOG_KEY) != oc or new.get(CATALOG_KEY) != nc:
        return _res(False, f"old must name {oc!r} and new {nc!r} as their {CATALOG_KEY} (they name "
                           f"{old.get(CATALOG_KEY)!r} and {new.get(CATALOG_KEY)!r})")
    if oc == nc:
        return _res(False, "old and new name the same rule catalog: nothing was re-derived under another catalog")
    if masked(old) != masked(new):
        diff = sorted(k for k in (set(old) | set(new)) - {CATALOG_KEY}
                      if ir.canonical_json(old.get(k)) != ir.canonical_json(new.get(k)))
        return _res(False, f"the law files differ in {diff}, not only in {CATALOG_KEY}: a claim, binder, premise or "
                           "metadata change is never a catalog re-derivation")
    if oc not in rules.CATALOGS or nc not in rules.CATALOGS:
        return _res(False, f"unknown rule catalog: {[c for c in (oc, nc) if c not in rules.CATALOGS]} (known: "
                           f"{sorted(rules.CATALOGS)})")
    rule, sub = new.get("rule"), new.get("subform")
    p_old = (rules.CATALOGS[oc].get(rule) or {}).get(sub)
    p_new = (rules.CATALOGS[nc].get(rule) or {}).get(sub)
    if p_old is None or p_new is None:
        return _res(False, f"{rule}/{sub} is not in both catalogs ({oc}: {p_old is not None}, {nc}: {p_new is not None})")
    if p_old is not p_new:
        return _res(False, f"{rule}/{sub} has another producer in {nc} than in {oc}: a rule change is not a catalog "
                           "re-derivation")
    sides = {}
    for tag, cv, law, h in (("old", oc, old, entry["old_hash"]), ("new", nc, new, entry["new_hash"])):
        try:
            der = derived_under(m, root, cv)
        except Exception as e:  # noqa: BLE001  (a derive that fails reproduces nothing)
            return _res(False, f"holon derive --milestone {m} under {cv} fails on the tree: {type(e).__name__}: {e}")
        got, de = der["laws"].get(lid), _derivation_entry(der, lid)
        if got is None or de is None or ir.canonical_json(got) != ir.canonical_json(law):
            return _res(False, f"holon derive --milestone {m} under {cv} does not reproduce the {tag} law file of {lid}")
        if de.get("statement_hash") != h:
            return _res(False, f"holon derive under {cv} gives {lid} the hash {de.get('statement_hash')}, the entry's "
                               f"{tag}_hash is {h}")
        sides[tag] = de
    a, b = ({k: v for k, v in sides[t].items() if k != "statement_hash"} for t in ("old", "new"))
    if ir.canonical_json(a) != ir.canonical_json(b):
        diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        return _res(False, f"the two catalogs derive {lid} from DERIVATION entries that differ in {diff}")
    same = {k: b.get(k) for k in ("rule", "subform", "basis")}
    if ir.canonical_json(same) != ir.canonical_json(entry["derivation"]):
        return _res(False, "holon derive derives the law from another (rule, subform, basis element) than the entry's")
    return _res(True, f"catalog_rederivation {oc} -> {nc}: the law files are identical with {CATALOG_KEY} masked; "
                      f"{rule}/{sub} is the same producer in both catalogs; holon derive under each catalog reproduces "
                      f"old ({entry['old_hash'][:19]}..) and new ({entry['new_hash'][:19]}..) from "
                      f"{json.dumps(same['basis'], sort_keys=True)[:120]}")


def catalog_rederivation_entries(milestone: str, root: Path) -> tuple[list[dict], list[str]]:
    """(entries, notes): one catalog_rederivation entry for every statement-hash change of laws/<M>/REGISTRY.json
    (registry_changes: every commit since the log was introduced, and the working tree) that no accepted entry covers
    yet and whose old and new law files differ only in rule_catalog_version, carrying the two statements and hashes as
    the registry history holds them and the law's (rule, subform, basis) from holon derive under the new catalog. Every
    other uncovered change is named in notes (it needs another kind). Nothing is appended here (append checks each
    entry). Without git history there is no registry history to read: ([], [why])."""
    root = Path(root)
    rc = registry_changes(milestone, root)
    if not rc["git"]:
        return [], [rc["note"]]
    ok = [x["entry"] for x in scan(root / LOG, root)["entries"] if x.get("ok")]
    out, notes, seen = [], [], set()
    for ch in rc["changes"]:
        lid, old, new = ch["law_id"], ch.get("old"), ch.get("new")
        if any(covers(e, ch) for e in ok):
            continue
        if not (_is_law(old) and _is_law(new)):
            notes.append(f"{lid} ({ch['at']}): {'deleted' if new is None else 'no law IR on one side'}: not a catalog "
                         "re-derivation")
            continue
        if masked(old) != masked(new) or old.get(CATALOG_KEY) == new.get(CATALOG_KEY):
            notes.append(f"{lid} ({ch['at']}): the law files differ beyond {CATALOG_KEY}: not a catalog re-derivation")
            continue
        key = (lid, ch["old_hash"], ch["new_hash"])
        if key in seen:
            continue
        seen.add(key)
        nc = new[CATALOG_KEY]
        try:
            de = _derivation_entry(derived_under(milestone, root, nc), lid) or {}
        except Exception as e:  # noqa: BLE001
            notes.append(f"{lid} ({ch['at']}): holon derive under {nc} fails: {type(e).__name__}: {e}")
            continue
        out.append({"kind": "catalog_rederivation", "law_id": lid, "milestone": milestone,
                    "old_catalog": old[CATALOG_KEY], "new_catalog": nc,
                    "old_hash": ch["old_hash"], "new_hash": ch["new_hash"],
                    "derivation": {k: de.get(k) for k in ("rule", "subform", "basis")},
                    "old": old, "new": new,
                    "reason": f"{lid} derived again under {nc} (was {old[CATALOG_KEY]}) when {milestone} moved to that "
                              f"catalog (registry change at {ch['at']}); the claim is unchanged: the statement hash "
                              "covers the catalog version"})
    return out, notes


# ---------------------------------------------------------------- binding changes (F31)
EQV_DEADLINE: float | None = None   # F33: a time.monotonic() deadline for the equivalence searches (rebind --deadline)
BINDING_KEYS = ("statement_hash", "statement_sha256", "counter_sha256", "model")   # fixed by a binding_change


def model_at(root: Path, commit: str, rel: str) -> bytes | None:
    """A file's bytes at a commit (read-only git), following symbolic links inside the tree (a typed model's
    records name it by a link, docs/HUMAN_ANSWERS.md Q25)."""
    root = Path(root).resolve()
    for _ in range(8):
        ls = _git(root, "ls-tree", commit, "--", rel)
        line = ls.stdout.decode().strip() if ls.returncode == 0 else ""
        if not line:
            return None
        mode = line.split()[0]
        b = blob_at(root, commit, rel)
        if b is None or mode != "120000":
            return b
        rel = (Path(rel).parent / b.decode().strip()).as_posix()
    return None


def _binding_at(root: Path, commit: str, milestone: str, lid: str) -> dict | None:
    from .bindings import BINDINGS_DIR
    doc = _json_or_none(blob_at(root, commit, (BINDINGS_DIR / f"{milestone}.json").as_posix()))
    x = (doc or {}).get("laws", {}).get(lid) if isinstance(doc, dict) else None
    return x if isinstance(x, dict) else None


def _binding_change(entry: dict, old: dict, new: dict, root: Path) -> dict:
    """An unsigned binding_change is accepted only with a generated, kernel-checked equivalence (holon.gen.equivalence),
    re-derived here from the entry and never taken from it:
      * the entry names the law, its milestone and bound_commit, a commit in HEAD's history whose
        spec/bindings/<m>.json holds the law's binding being replaced (the old one), and whose model file is that
        binding's model: its kernel entries hash to the binding's cone, entry by entry;
      * the law's binding on the tree (holon.bindings.bind_law) differs from the old one only in its cone: the statement
        hash, the emitted statement and counter-law and the model path are the same (anything else is not a
        binding change), and the entry's "defs" are exactly the definitions whose kernel form changed or that entered
        or left the cone;
      * holon.gen.equivalence.prove on the old model text (from git at bound_commit), the new one (the tree) and the
        emitted statement gives PROVED: every root the statement names is unchanged or proven extensionally equal,
        by bend and by BendTT (--verdict) when it is available.
    A proof carried by the entry (any key) is never read."""
    from . import bindings as B
    from .gen import equivalence as EQ
    m, lid, commit_b = entry.get("milestone"), new["law_id"], entry.get("bound_commit")
    if not isinstance(m, str) or not isinstance(commit_b, str) or not isinstance(entry.get("defs"), list):
        return _res(False, "an unsigned binding_change carries milestone, bound_commit and defs (the equivalence is "
                           "generated and checked here; a supplied proof does not count)")
    if not in_git(root):
        return _res(False, "a binding_change is checked against the bound kernel forms at bound_commit, which needs the "
                           "git history (a copied tree cannot check it)")
    if _git(root, "merge-base", "--is-ancestor", commit_b, "HEAD").returncode != 0:
        return _res(False, f"bound_commit {commit_b[:12]} is not a commit in HEAD's history")
    cur = root / "laws" / m / f"{lid}.json"
    law = _json_or_none(cur.read_bytes()) if cur.is_file() else None
    if not _is_law(law) or core(law) != core(new):
        return _res(False, f"the entry's statement is not {lid}'s statement on the tree")
    ob = _binding_at(root, commit_b, m, lid)
    if ob is None:
        return _res(False, f"spec/bindings/{m}.json at {commit_b[:12]} binds no {lid}")
    try:
        nb = B.bind_law(law, m, root)
    except Exception as e:  # noqa: BLE001  (a law that cannot be bound now has no binding change to check)
        return _res(False, f"{lid} cannot be bound on the tree: {type(e).__name__}: {e}")
    diff = [k for k in BINDING_KEYS if ob.get(k) != nb.get(k)]
    bridge = None
    if diff == ["statement_hash"]:   # F33: a catalog re-derivation moved the hash; it must be an accepted entry
        bridge = catalog_bridge(m, lid, ob.get("statement_hash"), nb.get("statement_hash"), root)
        want = {"old": ob.get("statement_hash"), "new": nb.get("statement_hash")}
        if entry.get("statement_hash") != want:
            return _res(False, f"the binding of {lid} changes its statement hash too: the entry must name it as "
                               f"statement_hash {want} (bridged by an accepted catalog_rederivation)")
        if bridge is None:
            return _res(False, f"the binding of {lid} changes its statement hash, and no accepted catalog_rederivation "
                               f"line of laws/STATEMENT_DIFF.jsonl maps {want['old']} to {want['new']}")
        diff = []
    elif entry.get("statement_hash") is not None:
        return _res(False, f"the entry names a statement_hash change, but the binding of {lid} keeps its statement hash")
    if diff:
        return _res(False, f"the binding of {lid} changes {diff}, not only its cone: not a binding change")
    changed = B.changed_defs(ob, nb)
    if not changed:
        return _res(False, f"the binding of {lid} at {commit_b[:12]} is the binding on the tree: nothing changed")
    if sorted(entry["defs"]) != changed:
        return _res(False, f"the entry's defs are not the changed definitions of {lid}'s binding ({len(changed)}: "
                           f"{', '.join(changed[:6])}{' ...' if len(changed) > 6 else ''})")
    old_bytes = model_at(root, commit_b, ob["model"])
    if old_bytes is None:
        return _res(False, f"{ob['model']} does not exist at {commit_b[:12]}")
    old_text, new_text = old_bytes.decode("utf-8"), (root / nb["model"]).read_text()
    try:
        eo = EQ.kernel_entries_of(old_text, None, f"{ob['model']} at {commit_b[:12]}")
        en = EQ.kernel_entries_of(new_text, None, nb["model"])
    except Exception as e:  # noqa: BLE001
        return _res(False, f"a model does not translate to BendTT: {e}")
    for tag, bnd, es in (("old", ob, eo), ("new", nb, en)):
        bad = sorted(d for d, h in bnd["cone"].items() if d not in es or hashlib.sha256(es[d].encode()).hexdigest() != h)
        if bad:
            return _res(False, f"the {tag} model's kernel forms are not the {tag} binding's ({', '.join(bad[:5])}): "
                               f"{ob['model']} at {commit_b[:12]} is not the bound model" if tag == "old" else
                               f"the {tag} model's kernel forms are not the {tag} binding's ({', '.join(bad[:5])})")
    eqv = EQ.prove(old_text, new_text, B.statement_text(law, m, root), eo=eo, en=en,
                   cache=EQ.default_cache(old_text, new_text), deadline=EQV_DEADLINE)
    eqv["bound_commit"] = commit_b
    eqv["models"] = {"old": _sha(old_bytes), "new": _sha(new_text.encode("utf-8")), "path": nb["model"]}
    if bridge is not None:
        eqv["catalog_bridge"] = bridge
    if eqv["status"] == "PROVED":
        return _res(True, f"binding_change: every root of {lid}'s statement is unchanged or proven extensionally equal "
                          f"old vs new ({eqv['reason']}), checked by {' and '.join(eqv['kernels']) or 'no kernel'}",
                    equivalence=eqv)
    return _res(False, f"binding_change without a checked equivalence ({eqv['status']}): {eqv['reason']}",
                equivalence=eqv)


def catalog_bridge(m: str, lid: str, old_hash, new_hash, root: Path) -> dict | None:
    """(F33) {"old", "new", "line"}: the accepted catalog_rederivation line of laws/STATEMENT_DIFF.jsonl for law lid of
    milestone m whose old_hash and new_hash are the two binding statement hashes, or None. Such a line establishes that
    the hash moved only with rule_catalog_version (the claim is the same), so a binding_change may carry the hash change
    with it; the change of the cone still needs the binding_change's own equivalence. Only catalog_rederivation lines
    are checked here (scan with kinds), so a binding_change line never checks itself."""
    if not isinstance(old_hash, str) or not isinstance(new_hash, str):
        return None
    s = scan(Path(root) / LOG, root, kinds=("catalog_rederivation",))
    for x in s["entries"]:
        e = x["entry"]
        if (x.get("ok") and isinstance(e, dict) and e.get("milestone") == m and e.get("law_id") == lid
                and e.get("old_hash") == old_hash and e.get("new_hash") == new_hash):
            return {"old": old_hash, "new": new_hash, "line": x["line"]}
    return None


def binding_change_entries(milestone: str, root: Path) -> tuple[list[dict], list[str]]:
    """(entries, notes): one binding_change entry for every law of laws/<M> whose binding on the tree
    (holon.bindings.bind_law) differs from spec/bindings/<M>.json only in its cone. Its bound_commit is the commit that
    gave the law its current binding (the oldest commit, in HEAD's history of spec/bindings/<M>.json, from which the
    law's binding has been the same), where the model and the binding were written together. Nothing is checked or
    appended here (append checks each entry). Laws whose binding changed otherwise are named in notes."""
    from . import bindings as B
    root = Path(root)
    p = B.path(milestone, root)
    if not p.is_file() or not in_git(root):
        return [], [f"{p} or the git history is missing"]
    cur = json.loads(p.read_text()).get("laws", {})
    rel = p.relative_to(root).as_posix()
    hist = _git(root, "log", "--topo-order", "--format=%H", "HEAD", "--", rel).stdout.decode().split()
    out, notes = [], []
    for law in ir.load_laws_any(milestone, root):
        lid = law["law_id"]
        if lid not in cur:
            continue
        try:
            nb = B.bind_law(law, milestone, root)
        except Exception as e:  # noqa: BLE001
            notes.append(f"{lid}: cannot be bound on the tree: {type(e).__name__}: {e}")
            continue
        ob = cur[lid]
        changed = B.changed_defs(ob, nb)
        if not changed:
            continue
        moved = [k for k in BINDING_KEYS if ob.get(k) != nb.get(k)]
        hashes = None
        if moved == ["statement_hash"]:   # F33: bridged by an accepted catalog_rederivation, or not a binding change
            if catalog_bridge(milestone, lid, ob.get("statement_hash"), nb.get("statement_hash"), root) is None:
                notes.append(f"{lid}: its statement hash changed too, and no accepted catalog_rederivation maps "
                             "the bound hash to the current one: not a binding change")
                continue
            hashes = {"old": ob.get("statement_hash"), "new": nb.get("statement_hash")}
        elif moved:
            notes.append(f"{lid}: its binding changes beyond the cone: not a binding change")
            continue
        commit_b = _bound_commit(root, hist, milestone, lid, ob)
        if commit_b is None:
            notes.append(f"{lid}: no commit holds its current binding (commit spec/bindings/{milestone}.json first)")
            continue
        e = {"kind": "binding_change", "law_id": lid, "milestone": milestone, "old": law, "new": law,
             "bound_commit": commit_b, "defs": changed,
             "reason": f"{lid}: {len(changed)} definitions of its cone changed under the fixed statement "
                       f"(model {nb['model']}); bound at {commit_b[:12]}"
                       + (" (its statement hash moved with an accepted catalog_rederivation)" if hashes else "")}
        if hashes:
            e["statement_hash"] = hashes
        out.append(e)
    return out, notes


def _bound_commit(root: Path, hist: list, milestone: str, lid: str, ob: dict) -> str | None:
    """The commit that gave law lid its binding ob: the oldest of hist (HEAD's history of spec/bindings/<M>.json,
    newest first) from which the law's binding has been ob, or None."""
    commit_b = None
    for c in hist:   # newest first: keep going back while the law's binding is the current one
        x = _binding_at(root, c, milestone, lid)
        if ir.canonical_json(x) != ir.canonical_json(ob):
            break
        commit_b = c
    return commit_b


_REGEN: dict = {}   # (root, milestone, document, model sha256, init sha256) -> (ok, why): one regeneration per process


def _model_version(data: bytes | None) -> str | None:
    """The model_version a generated model's header names (holon.sorts.model3), or None."""
    m = re.search(r"(?m)^# model_version: (\S+)", (data or b"")[:4000].decode("utf-8", errors="replace"))
    return m.group(1) if m else None


def _typed_regenerated(m: str, root: Path, doc_rel: str) -> tuple[bool, str]:
    """(I68, _remodel (c)) Are the typed model of a document and its init on the tree holon.sorts.model3.generate's
    output, byte for byte, as holon.sorts.run3 writes them (the deployment with its code table)?"""
    from .sorts import model3 as M3
    from .sorts.envcode3 import with_code
    from .sorts.run3 import dumps
    d = Path(root) / "gen" / m / "sorts" / "models"
    name = M3.model_name(doc_rel)
    mp, ip = d / M3.importable(name), d / f"{name}.init.json"
    if not (mp.is_file() and ip.is_file()):
        return False, f"{mp.relative_to(root)} or {ip.relative_to(root)} does not exist"
    key = (str(root), m, doc_rel, _sha(mp.read_bytes()), _sha(ip.read_bytes()))
    if key not in _REGEN:
        try:
            init = with_code(M3.init_of(m, root, None, doc_rel), root, doc_rel)
            text, _mm = M3.generate(m, root, doc_rel, typed=True, init=init)
        except Exception as e:  # noqa: BLE001  (a model that cannot be generated is not reproduced)
            _REGEN[key] = (False, f"holon.sorts.model3 cannot generate {name}: {type(e).__name__}: {e}")
        else:
            bad = [p.name for p, want in ((mp, text), (ip, dumps(init))) if p.read_text(encoding="utf-8") != want]
            _REGEN[key] = (not bad, f"{', '.join(bad)} differ from holon.sorts.model3's regeneration" if bad else
                           f"{mp.name} and {ip.name} regenerate byte for byte")
    return _REGEN[key]


def _remodel(entry: dict, old: dict, new: dict, root: Path) -> dict:
    """(I68, rule S11 of tests_m3/test_structural_keys.py; Q21's H1) The model a law is bound to replaced by a licensed
    remodel. Accepted unsigned only when all of these hold mechanically:
      (a) the entry names the law's milestone and bound_commit, a commit in HEAD's history whose
          spec/bindings/<m>.json binds the law; the law file is the same bytes there and on the tree, the law is one of
          the typed model's (a typed-SORT, DISCH, UNDO or FACT law) and its binding on the tree (holon.bindings.bind_law)
          differs from that one only in its cone: the statement hash, the emitted statement and counter-law and the
          model path are the same, and some definition of the cone changed;
      (b) (license, old_model_version, new_model_version) is a remodel REMODELS licenses and the entry's assumption is
          the ledger entry it adds; docs/HUMAN_ANSWERS.md holds that answer naming the entry; the typed model the law
          reaches names old_model_version at bound_commit and new_model_version, with the entry, on the tree; and
          spec/<m>/ledger.json adds the entry to the law's facts bundle (holon.records.milestone_entries);
      (c) that typed model and its init are holon.sorts.model3.generate's output on the tree, byte for byte
          (_typed_regenerated; the sections a law imports are its rule's G1);
      (d) results/<m>/sorts/refinement.json evaluated the frozen I20 corpus with that model (evaluator, evaluator_sha256):
          I20's binding, corpus and counts (I20_RECORD), 0 disagreements and 0 unexplained; and gen/<m>/sorts/keys.json
          was taken over that model and lists no collision;
      (e) the law's record results/<m>/<law>.json is remade on the new model: the binding's statement hash and model,
          that model's sha256, and the entry's assumption among its model_assumptions (ledger_assumptions for UNDO and
          FACT records). Its status is an outcome, never part of the check.
    The result carries the files checked (sha256), which the acceptance record keeps (_verify_remodel)."""
    from . import bindings as B
    from . import records as R
    m, lid, commit_b = entry.get("milestone"), new["law_id"], entry.get("bound_commit")
    lic = (entry.get("license"), entry.get("old_model_version"), entry.get("new_model_version"))
    if not isinstance(m, str) or not isinstance(commit_b, str):
        return _res(False, "a remodel names its milestone and bound_commit")
    if lic not in REMODELS:
        return _res(False, f"no human answer licenses the remodel {lic} (licensed: {sorted(REMODELS)})")
    want = REMODELS[lic]
    if entry.get("assumption") != want:
        return _res(False, f"the remodel {lic} adds the ledger entry {want}, not {entry.get('assumption')!r}")
    ans = root / "docs" / "HUMAN_ANSWERS.md"
    row = rf"(?m)^\| \*\*{re.escape(lic[0])}\*\*.*{re.escape(want)}"   # the answer's table row names the entry
    if not (ans.is_file() and re.search(row, ans.read_text())):
        return _res(False, f"docs/HUMAN_ANSWERS.md holds no answer {lic[0]} naming {want}")
    if not in_git(root):
        return _res(False, "a remodel is checked against the binding at bound_commit, which needs the git history")
    if _git(root, "merge-base", "--is-ancestor", commit_b, "HEAD").returncode != 0:
        return _res(False, f"bound_commit {commit_b[:12]} is not a commit in HEAD's history")
    # (a)
    rel = f"laws/{m}/{lid}.json"
    cur = root / rel
    law = _json_or_none(cur.read_bytes()) if cur.is_file() else None
    if not _is_law(law) or core(law) != core(new):
        return _res(False, f"the entry's statement is not {lid}'s statement on the tree")
    if blob_at(root, commit_b, rel) != cur.read_bytes():
        return _res(False, f"{rel} changed since bound_commit {commit_b[:12]}: a remodel keeps the law file")
    if not (B._typed(law) or B._disch(law) or B._undo(law) or B._fact(law)):
        return _res(False, f"{lid} is not a law over the typed model (typed-SORT, DISCH, UNDO or FACT)")
    ob = _binding_at(root, commit_b, m, lid)
    if ob is None:
        return _res(False, f"spec/bindings/{m}.json at {commit_b[:12]} binds no {lid}")
    try:
        nb = B.bind_law(law, m, root)
    except Exception as e:  # noqa: BLE001  (a law that cannot be bound now has no remodel to check)
        return _res(False, f"{lid} cannot be bound on the tree: {type(e).__name__}: {e}")
    diff = [k for k in BINDING_KEYS if ob.get(k) != nb.get(k)]
    if diff:
        return _res(False, f"the binding of {lid} changes {diff}, not only its cone: not a remodel")
    if not B.changed_defs(ob, nb):
        return _res(False, f"the binding of {lid} at {commit_b[:12]} is the binding on the tree: nothing changed")
    # (b)
    tm = B._typed_model(law, m, root)
    trel = tm.relative_to(root).as_posix()
    old_t, new_t = model_at(root, commit_b, trel), tm.read_bytes() if tm.is_file() else None
    if (_model_version(old_t), _model_version(new_t)) != lic[1:]:
        return _res(False, f"{trel} names model versions {_model_version(old_t)} at {commit_b[:12]} and "
                           f"{_model_version(new_t)} on the tree, not {lic[1]} and {lic[2]}")
    if f"({want})" not in (new_t or b"")[:4000].decode("utf-8", errors="replace"):
        return _res(False, f"{trel}'s header does not name {want}")
    try:
        fb = R.bundle(_sha((root / law["facts"]).read_bytes()), root, law["facts"])
    except (OSError, R.LedgerError) as e:
        return _res(False, f"no ledger bundle for {law['facts']}: {e}")
    if want not in [x.get("id") for x in R.milestone_entries(root, m, fb)]:
        return _res(False, f"spec/{m}/ledger.json adds no entry {want} to the bundle of {law['facts']}")
    # (c)
    ok, why = _typed_regenerated(m, root, law["facts"])
    if not ok:
        return _res(False, f"the new model is not regenerated: {why}")
    # (d)
    rp, kp, ip = root / "results" / m / "sorts" / "refinement.json", root / "gen" / m / "sorts" / "keys.json", \
        root / I20_RECORD
    r5, keys, i20 = (_json_or_none(q.read_bytes()) if q.is_file() else None for q in (rp, kp, ip))
    if not (isinstance(r5, dict) and isinstance(i20, dict)):
        return _res(False, f"{rp.relative_to(root)} or {I20_RECORD} is missing")
    same = ("binding", "corpus", "facts_sha256", "traces", "steps", "storage_slots")
    if (r5.get("evaluator"), r5.get("evaluator_sha256")) != (trel, _sha(new_t)):
        return _res(False, f"{rp.relative_to(root)} did not evaluate with {trel} as it is on the tree")
    if [r5.get(k) for k in same] != [i20.get(k) for k in same]:
        return _res(False, f"{rp.relative_to(root)} is not on I20's corpus: "
                           f"{[k for k in same if r5.get(k) != i20.get(k)]} differ from {I20_RECORD}")
    if r5.get("disagreements") != [] or r5.get("unexplained") != 0:
        return _res(False, f"{rp.relative_to(root)} has {len(r5.get('disagreements') or [])} disagreements and "
                           f"{r5.get('unexplained')} unexplained")
    if not isinstance(keys, dict) or (keys.get("models") or {}).get(trel) != _sha(new_t):
        return _res(False, f"{kp.relative_to(root)} was not taken over {trel} as it is on the tree")
    if keys.get("collisions") != []:
        return _res(False, f"{kp.relative_to(root)} lists {len(keys.get('collisions') or [])} collisions (findings)")
    # (e)
    qp = root / "results" / m / f"{lid}.json"
    rec = _json_or_none(qp.read_bytes()) if qp.is_file() else None
    if not isinstance(rec, dict):
        return _res(False, f"{qp.relative_to(root)} does not exist")
    where = "ledger_assumptions" if rec.get("rule") in ("UNDO", "FACT") else "model_assumptions"
    mf = root / nb["model"]
    if (rec.get("statement_hash"), (rec.get("artifacts") or {}).get("model")) != (nb["statement_hash"], nb["model"]):
        return _res(False, f"{qp.relative_to(root)} is not a record of the bound statement over {nb['model']}")
    if not mf.is_file() or rec.get("model_sha256") != _sha(mf.read_bytes()):
        return _res(False, f"{qp.relative_to(root)} was not remade on {nb['model']} as it is on the tree")
    if want not in (rec.get(where) or []):
        return _res(False, f"{qp.relative_to(root)} does not list {want} in {where}")
    checked = {"bound_commit": commit_b, "model": trel, "old_sha256": _sha(old_t), "new_sha256": _sha(new_t),
               "files": {q.relative_to(root).as_posix(): _sha(q.read_bytes()) for q in (rp, kp, qp, mf)}}
    return _res(True, f"remodel {lic[0]}: {lid}'s binding changes only in its cone ({len(B.changed_defs(ob, nb))} "
                      f"definitions), {trel} goes from {lic[1]} to {lic[2]} and regenerates, R5 agrees on I20's corpus, "
                      f"no key collides, and its record is remade with {want}", remodel=checked)


def remodel_entries(milestone: str, root: Path, license: str = "Q21") -> tuple[list[dict], list[str]]:
    """(entries, notes): one remodel entry under the license for every law of laws/<M> over the typed model whose
    binding on the tree differs from spec/bindings/<M>.json only in its cone, bound_commit found as binding_change_entries
    finds it. Nothing is checked or appended here (append checks each entry). Laws whose binding changed otherwise are
    named in notes."""
    from . import bindings as B
    root = Path(root)
    lic = next((k for k in REMODELS if k[0] == license), None)
    p = B.path(milestone, root)
    if lic is None:
        return [], [f"no remodel is licensed by {license!r}"]
    if not p.is_file() or not in_git(root):
        return [], [f"{p} or the git history is missing"]
    cur = json.loads(p.read_text()).get("laws", {})
    rel = p.relative_to(root).as_posix()
    hist = _git(root, "log", "--topo-order", "--format=%H", "HEAD", "--", rel).stdout.decode().split()
    out, notes = [], []
    for law in ir.load_laws_any(milestone, root):
        lid = law["law_id"]
        if lid not in cur or not (B._typed(law) or B._disch(law) or B._undo(law) or B._fact(law)):
            continue
        try:
            nb = B.bind_law(law, milestone, root)
        except Exception as e:  # noqa: BLE001
            notes.append(f"{lid}: cannot be bound on the tree: {type(e).__name__}: {e}")
            continue
        ob = cur[lid]
        if not B.changed_defs(ob, nb):
            continue
        if [k for k in BINDING_KEYS if ob.get(k) != nb.get(k)]:
            notes.append(f"{lid}: its binding changes beyond the cone: not a remodel")
            continue
        commit_b = _bound_commit(root, hist, milestone, lid, ob)
        if commit_b is None:
            notes.append(f"{lid}: no commit holds its current binding (commit spec/bindings/{milestone}.json first)")
            continue
        out.append({"kind": "remodel", "law_id": lid, "milestone": milestone, "license": lic[0],
                    "old_model_version": lic[1], "new_model_version": lic[2], "assumption": REMODELS[lic],
                    "bound_commit": commit_b,
                    "reason": f"{lid}: its model {nb['model']} is remodelled from {lic[1]} to {lic[2]} ({lic[0]}: "
                              f"{REMODELS[lic]}); {len(B.changed_defs(ob, nb))} definitions of its cone changed under "
                              f"the fixed statement; bound at {commit_b[:12]}",
                    "old": law, "new": law})
    return out, notes


# ---------------------------------------------------------------- the log
def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1", LC_ALL="C")
    return subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args], capture_output=True, env=env,
                          stdin=subprocess.DEVNULL)


def in_git(root: Path) -> bool:
    """Is root the top of a git checkout with a HEAD (read-only)? A copied tree is not."""
    root = Path(root).resolve()
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.decode().strip()).resolve() != root:
        return False
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}").returncode == 0


def blob_at(root: Path, commit: str, rel: str) -> bytes | None:
    b = _git(Path(root).resolve(), "cat-file", "blob", f"{commit}:{rel}")
    return b.stdout if b.returncode == 0 else None


def committed_history(path: Path, root: Path, first_parent: bool = False) -> list[tuple[str, bytes]] | None:
    """[(commit, bytes)] of every committed version of `path` reachable from HEAD (with first_parent, only along
    HEAD's first-parent chain), oldest first (read-only git); None without git history (e.g. a copy of the tree)."""
    root = Path(root).resolve()
    try:
        rel = Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    if not in_git(root):
        return None
    p = _git(root, "log", "--topo-order", "--reverse", *(["--first-parent"] if first_parent else []), "--format=%H",
             "HEAD", "--", rel)
    if p.returncode != 0:
        return None
    out = []
    for c in p.stdout.decode().split():
        b = blob_at(root, c, rel)
        if b is not None:
            out.append((c, b))
    return out


def merged_lines(data: bytes, path: Path, root: Path) -> tuple[list[tuple[int, str]], dict, list[str]]:
    """Append-only over a history with merges. The file must extend every committed version along HEAD's first-parent
    chain (spans: (end offset, commit) of the bytes each of them appended), and keep every line of every other
    committed version (a version a merge brought in from a side line): a line is never dropped or rewritten, only
    appended. Returns (spans, {line bytes: the oldest commit whose version holds that line, for lines of side
    versions}, [problem])."""
    problems = []
    chain = committed_history(path, root, first_parent=True) or []
    spans, prev = [], 0
    for c, v in chain:
        if not data.startswith(v):
            problems.append("append-only: the file no longer extends a committed version of itself")
            return [], {}, problems
        if len(v) > prev:
            spans.append((len(v), c))
            prev = len(v)
    on_chain = {c for c, _v in chain}
    have = data.splitlines(keepends=True)
    counts: dict = {}
    for ln in have:
        counts[ln] = counts.get(ln, 0) + 1
    side: dict = {}
    for c, v in committed_history(path, root) or []:
        if c in on_chain:
            continue
        need: dict = {}
        for ln in v.splitlines(keepends=True):
            need[ln] = need.get(ln, 0) + 1
            side.setdefault(ln, c)
        if any(counts.get(ln, 0) < k for ln, k in need.items()):
            problems.append(f"append-only: the file drops or rewrites a line of the version committed at {c[:7]} "
                            "(merged from another line of history)")
            return [], {}, problems
    return spans, side, problems


def committed_versions(path: Path, root: Path) -> list[bytes]:
    """Every committed version of `path` reachable from HEAD, oldest first (read-only git); [] without git."""
    return [b for _, b in committed_history(path, root) or []]


def _sha(text) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8") if isinstance(text, str) else text).hexdigest()


def acceptance(entry: dict, result: dict, root: Path) -> dict:
    """The record of what an accepted entry was checked against: every facts file its statements are about
    (sha256), and for an implication the generated obligation and the proof Bend accepted (sha256)."""
    root = Path(root)
    facts = {}
    for side in ("old", "new"):
        rel = entry.get(side, {}).get("facts") if _is_law(entry.get(side)) else None
        if isinstance(rel, str) and (root / rel).is_file():
            facts[rel] = _sha((root / rel).read_bytes())
    if entry.get("kind") == "reextraction" and isinstance(entry.get("facts"), str) and (root / entry["facts"]).is_file():
        facts[entry["facts"]] = _sha((root / entry["facts"]).read_bytes())   # the extracted document (I20)
    acc = {"kind": entry.get("kind"), "facts": dict(sorted(facts.items()))}
    if entry.get("kind") == "catalog_rederivation":   # F30: the two catalogs holon derive reproduced each side under
        acc["catalogs"] = [entry.get("old_catalog"), entry.get("new_catalog")]
    imp = result.get("implication") or {}
    if imp.get("status") == "PROVED":
        acc["implication"] = {"law_id": imp.get("law_id"), "generator": imp.get("generator"),
                              "kernels": imp.get("kernels"), "laws_sha256": _sha(imp.get("laws")),
                              "proof_sha256": _sha(imp.get("proof"))}
    eqv = result.get("equivalence") or {}
    if entry.get("kind") == "binding_change" and eqv.get("status") == "PROVED":   # F31
        acc["equivalence"] = {"generator": eqv.get("generator"), "bound_commit": eqv.get("bound_commit"),
                              "models": eqv.get("models"), "kernels": eqv.get("kernels"),
                              "pair_sha256": eqv.get("pair_sha256"), "laws_sha256": _sha(eqv.get("laws")),
                              "proof_sha256": _sha(eqv.get("proof")),
                              "roots": {i["root"]: i.get("class") for i in eqv.get("roots") or []}}
        if eqv.get("catalog_bridge"):
            acc["equivalence"]["catalog_bridge"] = eqv["catalog_bridge"]
    if entry.get("kind") == "remodel" and isinstance(result.get("remodel"), dict):   # I68: the files _remodel checked
        acc["remodel"] = result["remodel"]
    if entry.get("signature"):
        acc["signature"] = "verified against keys/"
    return acc


def _line_tag(e) -> str:
    if not isinstance(e, dict):
        return "? None"
    lid = e.get("law_id") or (e["new"].get("law_id") if _is_law(e.get("new")) else None)
    return f"{e.get('kind')} {lid}"


def scan(path: Path, root: Path, kinds=None, milestone: str | None = None) -> dict:
    """Every line of a STATEMENT_DIFF.jsonl with its verdict (see the module docstring):
    {"problems": [..], "entries": [{"line", "entry", "ok", "committed", "commit"}], "git": bool, "note": str,
     "unchecked": [line numbers] (off git, below), "elsewhere": [line numbers] (on git, below),
     "crashes": [{"law_id", "kernel", "seconds", "message"}]}.
    milestone (F35, F38): the milestone being gated. On git, a committed binding_change line of a law that lives in
    ANOTHER milestone's laws/ gets every check (its artifacts regenerated and tied to the two models and the statement)
    but bend's and BendTT's runs on its PROOF.bend, which that milestone's G2 makes (listed in "elsewhere" and in the
    note); a line about a law found in no milestone (or in several) is re-checked in full by every gate. So a proof is
    re-run only where its law's milestone is gated: CI gates M0-M2 in full and M3's G2 in its own job (gate-M3-G2).
    Off git (a copied tree), a binding_change line of a law of ANOTHER milestone (no laws/<milestone>/<law_id>.json,
    whatever the line's own label says) cannot be checked (it needs the old model at its bound commit) and is not that
    gate's claim: it is listed in the note as not checked, never as accepted. Its own milestone's binding_change lines still fail off git. Every checker crash a re-check of a
    binding_change line retried in this scan (Q34: retried and logged, never a verdict) is listed in "crashes" and
    named in the note."""
    path, root = Path(path), Path(root)
    out = {"problems": [], "entries": [], "git": False, "note": ""}
    if not path.is_file():
        out["problems"].append(f"{path} does not exist")
        return out
    data = path.read_bytes()
    n_crashes = len(_RECHECKED.get("crashes", []))
    hist = committed_history(path, root)
    out["git"] = hist is not None
    # (end offset, commit): the bytes up to `end` were appended by `commit` (HEAD's first-parent chain); a line a
    # merge brought in from another line of history is committed by the oldest commit whose version holds it
    spans, side, probs = merged_lines(data, path, root) if hist is not None else ([], {}, [])
    out["problems"] += probs
    committed_len = spans[-1][0] if spans else 0
    out["note"] = ("no git history (a copied tree): every line checked against the working tree" if hist is None else
                   f"{len(hist)} committed versions, {committed_len} committed bytes; committed lines verified against "
                   "the commit that appended them, new lines checked against the working tree")
    offset = 0
    for n, raw in enumerate(data.splitlines(keepends=True), start=1):
        start, offset = offset, offset + len(raw)
        line = raw.decode("utf-8", errors="replace")
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError as ex:
            out["problems"].append(f"line {n}: not JSON ({ex})")
            continue
        if kinds is not None and (not isinstance(e, dict) or e.get("kind") not in kinds):
            continue   # only these kinds are checked (catalog_bridge)
        if hist is None and milestone and isinstance(e, dict) and e.get("kind") == "binding_change" \
                and e.get("law_id") and not (root / "laws" / milestone / f"{e['law_id']}.json").is_file():
            out.setdefault("unchecked", []).append(n)
            continue
        commit = next((c for end, c in spans if start < end), None) if start < committed_len else side.get(raw)
        item = {"line": n, "entry": e, "ok": False, "committed": commit is not None, "commit": commit}
        out["entries"].append(item)
        acc = e.get("accepted") if isinstance(e, dict) else None
        # F38: a committed binding_change line of a law of another milestone gets every check here but the kernels'
        # runs on its proof, which its own milestone's G2 makes (each proof re-checked once per CI run)
        own = not (milestone and isinstance(e, dict) and e.get("kind") == "binding_change"
                   and _law_milestone(root, e.get("law_id")) not in (None, milestone))
        if commit is not None:
            if not own:
                out.setdefault("elsewhere", []).append(n)
            why = _verify_committed(e, acc, commit, root, recheck=own)
            if why:
                out["problems"].append(f"line {n}: {_line_tag(e)}: {why}")
            else:
                item["ok"] = True
            continue
        r = check_entry(e, root)
        if not r["ok"]:
            out["problems"].append(f"line {n}: {_line_tag(e)}: {r['reason']}")
        elif not isinstance(acc, dict):
            out["problems"].append(f"line {n}: {_line_tag(e)}: accepted, but the line carries no acceptance record "
                                   "(append entries with `python -m holon.statement_diff append ENTRY.json`)")
        elif ir.canonical_json(acc) != ir.canonical_json(acceptance(e, r, root)):
            out["problems"].append(f"line {n}: {_line_tag(e)}: its acceptance record differs from the check of the "
                                   "working tree")
        else:
            item["ok"] = True
    if out.get("unchecked"):
        out["note"] += (f"; {len(out['unchecked'])} binding_change line(s) of another milestone not checked here (no git "
                        f"history; lines {', '.join(map(str, out['unchecked']))})")
    if out.get("elsewhere"):
        lines = out["elsewhere"]
        out["note"] += (f"; {len(lines)} binding_change line(s) of other milestones (line(s) {', '.join(map(str, lines[:8]))}"
                        f"{' ...' if len(lines) > 8 else ''}): every check here but the two kernels' runs on their "
                        f"PROOF.bend, which their own milestone's G2 makes")
    cr = _RECHECKED.get("crashes", [])[n_crashes:]
    if cr:
        out["crashes"] = [{"law_id": lid, **c} for lid, c in cr]
        out["note"] += (f"; {len(cr)} checker crash(es) retried while re-checking binding_change lines (Q34: never a "
                        f"verdict): " + ", ".join(f"{lid} {c.get('kernel')} {c.get('seconds')} s" for lid, c in cr[:8])
                        + (" ..." if len(cr) > 8 else ""))
    return out


def _law_milestone(root: Path, lid) -> str | None:
    """The milestone whose laws/<M>/ holds law lid, or None (no such law anywhere: then every gate re-checks a line
    about it, F38, so no line escapes every re-check)."""
    if not isinstance(lid, str) or not lid or "/" in lid or lid.startswith("."):
        return None
    hits = sorted(d.name for d in (Path(root) / "laws").glob("M*") if (d / f"{lid}.json").is_file())
    return hits[0] if len(hits) == 1 else None


def verify_signature_at(entry: dict, commit: str, root: Path) -> tuple[bool, str]:
    """verify_signature for a committed line (F38): against the frozen keys as the commit that appended the line had
    them, read with git cat-file (no file of that commit is written anywhere)."""
    return verify_signature(entry, root, commit=commit)


def _verify_committed(e, acc, commit: str, root: Path, recheck: bool = True) -> str | None:
    """A committed line is not re-proved: its acceptance record must name the facts as they were at the commit
    that appended it. A signature it carries or its acceptance record claims is verified here, against the frozen keys
    as that commit had them (F38, frozen_keys: a claim is never taken on trust). An unsigned binding_change's
    equivalence is verified by _verify_equivalence; recheck=False (a law of another milestone than the gated one, F38)
    runs every tie of it but the two kernels' runs on its PROOF.bend, which its own milestone's G2 makes."""
    if not isinstance(e, dict) or not isinstance(acc, dict) or not isinstance(acc.get("facts"), dict):
        return f"committed at {commit[:7]} without an acceptance record (only `holon.statement_diff append` writes one)"
    if acc.get("kind") != e.get("kind"):
        return f"its acceptance record is for kind {acc.get('kind')!r}"
    signed = False
    if e.get("signature") or acc.get("signature") is not None:
        ok, why = verify_signature_at(e, commit, root)
        if not ok:
            return f"it carries or claims a signature, and G2 verifies it against the frozen keys at {commit[:7]}: {why}"
        signed = acc.get("signature") == "verified against keys/"
    if e.get("kind") in ("strengthening", "cross_milestone") and not isinstance(acc.get("implication"), dict):
        return "its acceptance record names no checked implication"
    if e.get("kind") == "weakening" and not signed:
        return "its acceptance record names no verified signature"
    if e.get("kind") == "weakening" and not e.get("review"):
        return "a signed weakening also needs an auditor review (\"review\"), as check_entry requires"
    if e.get("kind") == "binding_change" and not signed:
        why = _verify_equivalence(e, acc.get("equivalence"), commit, root, kernels=recheck)   # F31
        if why:
            return why
    if e.get("kind") == "reextraction" and e.get("facts") not in acc["facts"]:
        return "its acceptance record does not name the extracted document the entry comes from"
    if e.get("kind") == "catalog_rederivation" and acc.get("catalogs") != [e.get("old_catalog"), e.get("new_catalog")]:
        return "its acceptance record does not name the two catalogs the entry re-derives under"
    if e.get("kind") == "remodel":
        why = _verify_remodel(e, acc.get("remodel"), commit, root)
        if why:
            return why
    for rel, sha in sorted(acc["facts"].items()):
        b = blob_at(root, commit, rel)
        if b is None or _sha(b) != sha:
            return (f"its acceptance names {rel} at sha256 {str(sha)[:12]}.., but at {commit[:7]} that file "
                    f"{'does not exist' if b is None else 'hashes to ' + _sha(b)[:12] + '..'}")
    return None


def _verify_remodel(e: dict, rm, commit: str, root: Path) -> str | None:
    """(I68) A committed remodel line is not re-checked: its license must still be one REMODELS lists, and the files its
    acceptance record names must hash as recorded at the commit that appended it (the typed model at bound_commit and
    there, the R5 record, the keys check, the law's record and its model)."""
    lic = (e.get("license"), e.get("old_model_version"), e.get("new_model_version"))
    if lic not in REMODELS or e.get("assumption") != REMODELS[lic]:
        return f"no human answer licenses the remodel {lic} adding {e.get('assumption')!r}"
    if not isinstance(rm, dict) or rm.get("bound_commit") != e.get("bound_commit") or not isinstance(rm.get("files"), dict):
        return "its acceptance record names no checked remodel"
    pairs = [(rm.get("bound_commit"), rm.get("model"), rm.get("old_sha256")), (commit, rm.get("model"), rm.get("new_sha256"))]
    pairs += [(commit, rel, sha) for rel, sha in sorted(rm["files"].items())]
    for c, rel, sha in pairs:
        b = model_at(root, c, rel) if isinstance(c, str) and isinstance(rel, str) else None
        if b is None or _sha(b) != sha:
            return (f"its acceptance names {rel} at sha256 {str(sha)[:12]}.., but at {str(c)[:7]} that file "
                    f"{'does not exist' if b is None else 'hashes to ' + _sha(b)[:12] + '..'}")
    return None


def _verify_equivalence(e: dict, eqv, commit: str, root: Path, kernels: bool = True) -> str | None:
    """A committed unsigned binding_change (F31) is not re-proved: its acceptance record must name a generated
    equivalence checked by bend (and BendTT when it ran), for the entry's bound commit, and the two models it was proved
    on must be the model at the bound commit and the model at the commit that appended the line. kernels=False (F38):
    every tie (recheck_artifacts) but the kernels' runs."""
    if not isinstance(eqv, dict) or "bend" not in (eqv.get("kernels") or []):
        return "its acceptance record names no verified signature and no kernel-checked equivalence"
    if eqv.get("generator") != "holon.gen.equivalence" or eqv.get("bound_commit") != e.get("bound_commit"):
        return "its acceptance record names another generator or bound commit than the entry"
    models = eqv.get("models") or {}
    m, lid = e.get("milestone"), e.get("law_id")
    ob = _binding_at(root, str(e.get("bound_commit")), str(m), str(lid)) if m and lid else None
    old = model_at(root, str(e.get("bound_commit")), ob["model"]) if ob else None
    new = model_at(root, commit, str(models.get("path"))) if models.get("path") else None
    if old is None or _sha(old) != models.get("old"):
        return "the old model its equivalence was proved on is not the model at its bound commit"
    if new is None or _sha(new) != models.get("new"):
        return f"the new model its equivalence was proved on is not {models.get('path')} at {commit[:7]}"
    br = e.get("statement_hash")
    if br is not None:   # F33: the statement hash moved with an accepted catalog_rederivation line
        cb = eqv.get("catalog_bridge") or {}
        if not isinstance(br, dict) or (cb.get("old"), cb.get("new")) != (br.get("old"), br.get("new")):
            return "its acceptance record names no catalog_rederivation bridging its statement hashes"
        log = blob_at(root, commit, LOG.as_posix()) or b""
        lines = log.decode("utf-8", errors="replace").splitlines()
        n = cb.get("line")
        x = _json_or_none(lines[n - 1].encode()) if isinstance(n, int) and 0 < n <= len(lines) else None
        if not (isinstance(x, dict) and x.get("kind") == "catalog_rederivation" and x.get("law_id") == lid
                and x.get("old_hash") == br.get("old") and x.get("new_hash") == br.get("new")):
            return f"line {n} of {LOG} at {commit[:7]} is not the catalog_rederivation its statement hash moved with"
    law = _json_or_none(blob_at(root, commit, f"laws/{m}/{lid}.json") or b"")
    try:   # the law's statement as it was when the line was appended, emitted as bind_law emits it
        from . import bindings as B
        stmt = B.statement_text(law, str(m), root) if _is_law(law) else None
    except Exception:  # noqa: BLE001  (a statement that cannot be emitted ties nothing)
        stmt = None
    if stmt is None:
        return f"laws/{m}/{lid}.json at {commit[:7]} gives no statement to tie its equivalence to"
    return recheck_artifacts(e, eqv, root, old, new, stmt, old_cone=(ob or {}).get("cone"), kernels=kernels)


# ---------------------------------------------------------------- binding_change proof artifacts (F33)
EQV_DIR = Path("spec") / "bindings" / "equivalence"
ARTIFACTS = ("pair.bend", "LAWS.bend", "PROOF.bend")
_RECHECKED: dict = {}


def artifact_dir(e: dict, eqv: dict) -> Path:
    """Where an accepted binding_change's proof artifacts live: spec/bindings/equivalence/<M>/<law>-<proof sha256[:16]>/
    (pair.bend.gz, LAWS.bend.gz, PROOF.bend.gz; gzip without a timestamp, so the bytes are deterministic)."""
    return EQV_DIR / str(e.get("milestone")) / f"{e.get('law_id')}-{str(eqv.get('proof_sha256'))[:16]}"


def write_artifacts(e: dict, acc_eqv: dict, result: dict, root: Path) -> None:
    import gzip
    d = Path(root) / artifact_dir(e, acc_eqv)
    d.mkdir(parents=True, exist_ok=True)
    for name, text in zip(ARTIFACTS, (result.get("pair_text"), result.get("laws"), result.get("proof"))):
        (d / (name + ".gz")).write_bytes(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))


def recheck_artifacts(e: dict, eqv: dict, root: Path, old_model: bytes | None, new_model: bytes | None,
                      statement: str | None, old_cone: dict | None = None, kernels: bool = True) -> str | None:
    """G2 on an accepted binding_change, never a re-search (F33): its committed proof artifacts are the files its
    acceptance record hashes, and every claim in them is regenerated rather than read from the record (which the
    appending agent wrote):
      * the pair module is holon.gen.equivalence.pair_module of the old model (at the bound commit), the new model (at
        the appending commit) and the law's statement, byte for byte (so its roots come from the statement, and its
        old side is the old model; when the old binding's cone is given, it hashes to it too);
      * LAWS.bend is holon.gen.equivalence.root_laws_text of that pair module, byte for byte (eq_<r> / to_<r>,
        from_<r> for every changed root), and states at least one law;
      * no file holds an escape hatch;
      * bend2 accepts PROOF.bend again, and BendTT (--verdict) too whenever it is enabled or the record names it.
    The two models and the statement are required (a copied tree without the history cannot give them). None when all
    of it holds, else the problem. kernels=False (F38: a gate of another milestone than the law's): all of it but the
    last item, which the law's own milestone's G2 runs."""
    import gzip
    import shutil
    import tempfile
    from . import bend
    from .gen import equivalence as EQ
    root = Path(root)
    d = root / artifact_dir(e, eqv)
    texts = {}
    for name in ARTIFACTS:
        p = d / (name + ".gz")
        if not p.is_file():
            return f"its proof artifact {p.relative_to(root)} is missing (G2 re-checks the committed proof in both kernels)"
        try:
            texts[name] = gzip.decompress(p.read_bytes()).decode("utf-8")
        except (OSError, EOFError, UnicodeDecodeError) as ex:
            return f"its proof artifact {p.relative_to(root)} does not decompress: {ex}"
    for name, key in zip(ARTIFACTS, ("pair_sha256", "laws_sha256", "proof_sha256")):
        if _sha(texts[name]) != eqv.get(key):
            return f"its proof artifact {name} is not the file its acceptance record hashes ({key})"
    if old_model is None or new_model is None or not isinstance(statement, str):
        return ("its proof artifacts cannot be tied to the two models and the statement here (G2 needs the old model at "
                "the bound commit, the new model and the law's statement: the git history)")
    memo = (eqv.get("pair_sha256"), eqv.get("laws_sha256"), eqv.get("proof_sha256"), _sha(old_model),
            _sha(new_model), _sha(statement), _sha(json.dumps(old_cone, sort_keys=True)), bool(kernels))
    if memo in _RECHECKED:
        return _RECHECKED[memo]
    why = None
    if bend.escape_hatches(texts["pair.bend"] + texts["LAWS.bend"] + texts["PROOF.bend"]):
        why = "its proof artifacts hold an escape hatch"
    if why is None:
        try:
            eo = EQ.kernel_entries_of(old_model.decode("utf-8"), None, "old model")
            en = EQ.kernel_entries_of(new_model.decode("utf-8"), None, "new model")
            pm = EQ.pair_module(old_model.decode("utf-8"), new_model.decode("utf-8"), statement, None, eo, en)
        except Exception as ex:  # noqa: BLE001  (no pair module, nothing proved)
            pm, why = None, f"the pair module of its two models and statement cannot be built: {ex}"
        if why is None and pm.text != texts["pair.bend"]:
            why = "its pair module is not the pair module of the old model, the new model and the law's statement"
        if why is None:
            try:
                laws_text, names = EQ.root_laws_text(pm)
            except EQ.Unsupported as ex:
                laws_text, names, why = None, [], f"its root laws cannot be regenerated: {ex}"
            if why is None and not names:
                why = "its statement's roots are all unchanged: an equivalence with no law proves nothing"
            elif why is None and laws_text != texts["LAWS.bend"]:
                why = (f"its LAWS.bend is not the root laws regenerated from the statement and the pair module "
                       f"({', '.join(names)})")
        if why is None and old_cone is not None:
            bad = sorted(n for n, h in old_cone.items() if n not in eo or _sha(eo[n]) != h)
            if bad:
                why = f"its old model is not the old binding's cone ({', '.join(bad[:5])})"
    if why is None and kernels:
        tmp = Path(tempfile.mkdtemp(prefix="holon-eqv-g2-"))
        try:
            for name in ARTIFACTS:
                (tmp / name).write_text(texts[name])
            # Q34: bounded by equivalence.timeout_s in each kernel; a crash is retried and logged, never a verdict
            r, crashes = bend.check_equivalence(tmp / "PROOF.bend")
            need_tt = bend.verdict_enabled() or "BendTT" in (eqv.get("kernels") or [])
            v = None
            if r.ok and need_tt:
                v, more = bend.check_equivalence(tmp / "PROOF.bend", verdict=True)
                crashes += more
            for c in crashes:
                _RECHECKED.setdefault("crashes", []).append((e.get("law_id"), c))

            def _why(kernel, run):
                if run is not None and bend.timed_out(run):
                    return (f"{kernel} did not finish its PROOF.bend within equivalence.timeout_s "
                            f"({bend.equivalence_timeout()} s): UNKNOWN, not re-checked")
                if run is not None and bend.crashed(run):
                    return f"{kernel} crashed on its PROOF.bend on every try (no verdict): not re-checked"
                return None
            if not r.ok:
                why = _why("bend2", r) or f"bend2 no longer accepts its PROOF.bend: {EQ.kernel_message(r.out, 6)}"
            elif need_tt and not (v is not None and v.ok):
                why = _why("BendTT", v) or f"BendTT does not accept its PROOF.bend: {EQ.kernel_message(v.out if v else '', 6)}"
            _RECHECKED.setdefault("seconds", []).append((e.get("law_id"), r.seconds, v.seconds if v else None))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    _RECHECKED[memo] = why
    return why


def check_file(path: Path, root: Path) -> list[str]:
    """Problems with a STATEMENT_DIFF.jsonl: a line that is not an accepted entry, or a committed version
    that the file does not extend (append-only)."""
    return scan(path, root)["problems"]


def append(entry: dict, root: Path) -> dict:
    """Check an entry against the working tree and, when accepted, append it with its acceptance record to
    laws/STATEMENT_DIFF.jsonl. Returns check_entry's result."""
    root = Path(root)
    r = check_entry(entry, root)
    if r["ok"]:
        acc = acceptance(entry, r, root)
        if acc.get("equivalence"):   # F33: the proof artifacts G2 re-checks in both kernels
            write_artifacts(entry, acc["equivalence"], r["equivalence"], root)
        line = json.dumps({**entry, "accepted": acc}, sort_keys=True, ensure_ascii=False)
        p = root / LOG
        data = p.read_bytes() if p.exists() else b""
        if data and not data.endswith(b"\n"):
            data += b"\n"
        p.write_bytes(data + line.encode("utf-8") + b"\n")
    return r


# ---------------------------------------------------------------- the statement-change tie (G2, F-M2-08)
def cutoff_commit(root: Path) -> str | None:
    """The first commit (in HEAD's history) that added the log: statement changes after it need an entry."""
    p = _git(Path(root).resolve(), "log", "--topo-order", "--reverse", "--diff-filter=A", "--format=%H", "HEAD",
             "--", LOG.as_posix())
    cs = p.stdout.decode().split() if p.returncode == 0 else []
    return cs[0] if cs else None


def _json_or_none(b: bytes | None):
    try:
        return json.loads(b) if b is not None else None
    except ValueError:
        return None


def registry_changes(milestone: str, root: Path) -> dict:
    """Statement-hash changes of laws/<m>/REGISTRY.json the log must cover: in every commit after the log was
    introduced (against its first parent) and in the working tree against HEAD. Each change: {"law_id", "old",
    "new" (law IR or None for a deletion), "at"}. {"git": False} without history."""
    root = Path(root).resolve()
    reg_rel = f"laws/{milestone}/REGISTRY.json"
    if not in_git(root):
        return {"git": False, "changes": [], "note": "not run: no git history (a copied tree), so the registry cannot "
                                                     "be compared with its committed versions"}
    cut = cutoff_commit(root)
    pairs = []   # (at, parent registry, child registry, old laws dir rev, new laws dir rev | None for the tree)
    if cut is not None:
        p = _git(root, "log", "--topo-order", "--reverse", "--format=%H", "HEAD", "--", reg_rel)
        for c in (p.stdout.decode().split() if p.returncode == 0 else []):
            if _git(root, "merge-base", "--is-ancestor", cut, c).returncode != 0:
                continue
            parent = _git(root, "rev-parse", "--verify", "-q", f"{c}^1")
            if parent.returncode != 0:
                continue
            pc = parent.stdout.decode().strip()
            first = _json_or_none(blob_at(root, pc, reg_rel))
            child = _json_or_none(blob_at(root, c, reg_rel))
            pairs.append((c[:7], first, child, pc, c, None))
            # a merge: a law the first parent does not hold, held by another parent under another hash, changed in
            # the merge against that parent (a law the first parent holds is compared with the first parent only)
            fs = (first or {}).get("statements") if isinstance(first, dict) else None
            ps = _git(root, "rev-parse", f"{c}^@")
            for po in (ps.stdout.decode().split()[1:] if ps.returncode == 0 else []):
                pairs.append((c[:7], _json_or_none(blob_at(root, po, reg_rel)), child, po, c,
                              set(fs) if isinstance(fs, dict) else set()))
    cur = root / reg_rel
    head = _json_or_none(blob_at(root, "HEAD", reg_rel))
    if cur.is_file():
        pairs.append(("working tree", head, _json_or_none(cur.read_bytes()), "HEAD", None, None))
    changes, seen = [], set()
    for at, a, b, ra, rb, skip in pairs:
        sa = (a or {}).get("statements") if isinstance(a, dict) else None
        sb = (b or {}).get("statements") if isinstance(b, dict) else None
        if not isinstance(sa, dict):
            continue   # no earlier registry: every law is an addition
        sb = sb if isinstance(sb, dict) else {}
        for lid in sorted(sa):
            if lid in sb and sb[lid] == sa[lid]:
                continue
            if skip is not None and (lid in skip or lid not in sb):
                continue
            old = _json_or_none(blob_at(root, ra, f"laws/{milestone}/{lid}.json"))
            if lid in sb:
                f = root / "laws" / milestone / f"{lid}.json"
                new = _json_or_none(f.read_bytes() if rb is None and f.is_file() else
                                    blob_at(root, rb, f"laws/{milestone}/{lid}.json") if rb else None)
            else:
                new = None
            key = (lid, core(old) if _is_law(old) else None, core(new) if _is_law(new) else None)
            if key in seen:
                continue
            seen.add(key)
            changes.append({"law_id": lid, "old": old, "new": new, "at": at,
                            "old_hash": sa[lid], "new_hash": sb.get(lid)})
    return {"git": True, "changes": changes,
            "note": f"{len(changes)} statement-hash changes since the log was introduced"
                    + (f" ({cut[:7]})" if cut else " (log not committed yet: working tree against HEAD only)")}


def covers(e: dict, ch: dict) -> bool:
    """Does an entry carry exactly the two statements of a registry change? A catalog_rederivation must also carry the
    change's two statement hashes (old_hash, new_hash) exactly: a change that does not name them is not covered by
    one (F30)."""
    if not isinstance(e, dict) or e.get("kind") not in STATEMENT_KINDS or not _is_law(e.get("old")):
        return False
    if (e.get("law_id") or e["old"].get("law_id")) != ch["law_id"] or not _is_law(ch.get("old")):
        return False
    if core(e["old"]) != core(ch["old"]):
        return False
    if ch.get("new") is None:   # a deletion drops a claim: only a signed weakening covers it
        return e.get("kind") == "weakening"
    if e.get("kind") == "catalog_rederivation":
        for k in ("old_hash", "new_hash"):
            if not isinstance(ch.get(k), str) or e.get(k) != ch[k]:
                return False
    return _is_law(e.get("new")) and _is_law(ch["new"]) and core(e["new"]) == core(ch["new"])


def tie_problems(milestone: str, root: Path, scanned: dict) -> tuple[list[str], str]:
    """G2: every registry change of the milestone is covered by an accepted entry. Returns (problems, note)."""
    rc = registry_changes(milestone, root)
    if not rc["git"]:
        return [], rc["note"]
    ok = [x["entry"] for x in scanned.get("entries", []) if x.get("ok")]
    bad = []
    for ch in rc["changes"]:
        if not any(covers(e, ch) for e in ok):
            what = "deleted" if ch.get("new") is None else f"hash {str(ch['old_hash'])[:19]}.. -> {str(ch['new_hash'])[:19]}.."
            bad.append(f"{ch['law_id']} {what} ({ch['at']}) without an accepted laws/STATEMENT_DIFF.jsonl entry "
                       "carrying exactly those statements")
    return bad, rc["note"]


# ---------------------------------------------------------------- cross-milestone links (A3, L22)
def check_cross_milestone(derivation: dict, laws: dict, entries: list, root: Path, accepted=None) -> list[str]:
    """Every DERIVATION.json back-test link {old, old_milestone, new, new_milestone, basis} needs an accepted
    cross_milestone entry (a checked S_new => S_old) or an accepted signed weakening for exactly that pair,
    carrying the linked statements as they are. A cross_milestone entry for a pair no link names is a
    problem too: pairs come from the derivation, never from ids. A link may carry a binder_map {new binder: old
    binder} (audit F-M2-23); an entry without its own map is checked with the link's. accepted: a predicate over
    entries (G2 passes scan()'s verdicts, so a committed entry is not re-proved); default check_entry."""
    links = derivation.get("links") if isinstance(derivation, dict) else None
    if not isinstance(links, list):
        return ["the derivation has no list of links"]
    problems, pairs = [], set()
    for i, ln in enumerate(links):
        if not isinstance(ln, dict) or not all(isinstance(ln.get(k), str) and ln[k]
                                               for k in ("old", "old_milestone", "new", "new_milestone", "basis")):
            problems.append(f"link {i}: needs old, old_milestone, new, new_milestone and basis")
            continue
        old, new = ln["old"], ln["new"]
        tag = f"link {new} ({ln['new_milestone']}) -> {old} ({ln['old_milestone']})"
        pairs.add((old, new))
        if ln["old_milestone"] == ln["new_milestone"]:
            problems.append(f"{tag}: both laws are in one milestone")
            continue
        lo, lnw = laws.get(old), laws.get(new)
        if not (_is_law(lo) and _is_law(lnw)):
            problems.append(f"{tag}: the linked laws are not both given")
            continue
        if lo.get("milestone", ln["old_milestone"]) != ln["old_milestone"] or \
                lnw.get("milestone", ln["new_milestone"]) != ln["new_milestone"]:
            problems.append(f"{tag}: the laws' milestones differ from the link's")
            continue
        cands = [e for e in entries if isinstance(e, dict) and e.get("kind") in ("cross_milestone", "weakening")
                 and _is_law(e.get("old")) and _is_law(e.get("new"))
                 and e["old"]["law_id"] == old and e["new"]["law_id"] == new]
        if not cands:
            problems.append(f"{tag}: no cross_milestone entry with a checked {new} => {old}, and no signed weakening")
            continue
        why = []
        for e in cands:
            if core(e["old"]) != core(lo) or core(e["new"]) != core(lnw):
                why.append(f"{e['kind']} entry does not carry the linked statements as they are")
                continue
            if isinstance(ln.get("binder_map"), dict) and "binder_map" not in e:
                e = {**e, "binder_map": ln["binder_map"]}
            if accepted is not None:
                if accepted(e):
                    break
                why.append(f"{e['kind']}: not an accepted entry of laws/STATEMENT_DIFF.jsonl")
                continue
            r = check_entry(e, root)
            if r["ok"]:
                break
            why.append(f"{e['kind']}: {r['reason']}")
        else:
            problems.append(f"{tag}: " + "; ".join(why))
    for e in entries:
        if isinstance(e, dict) and e.get("kind") == "cross_milestone" and _is_law(e.get("old")) and _is_law(e.get("new")) \
                and (e["old"]["law_id"], e["new"]["law_id"]) not in pairs:
            problems.append(f"cross_milestone entry pairs {e['new']['law_id']} with {e['old']['law_id']}, but no "
                            "DERIVATION.json link does (pairs come from back-test links, never from ids)")
    return problems


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    """python -m holon.statement_diff append ENTRY.json [--root DIR]: check the entry against the working tree and
    append it, with its acceptance record, only if accepted. python -m holon.statement_diff check [--root DIR]:
    print the verdict of every line. reextract / recatalog --milestone M [--append]: build (and append the accepted
    ones of) the reextraction / catalog_rederivation entries the milestone needs."""
    import argparse
    ap = argparse.ArgumentParser(prog="python -m holon.statement_diff")
    ap.add_argument("command", choices=("append", "check", "reextract", "recatalog", "rebind", "remodel"))
    ap.add_argument("entry", nargs="?")
    ap.add_argument("--root", default=str(ir.ROOT))
    ap.add_argument("--milestone", default="M2", help="reextract, recatalog: the milestone whose laws are re-derived")
    ap.add_argument("--append", action="store_true",
                    help="reextract, recatalog, rebind, remodel: append every accepted entry")
    ap.add_argument("--license", default="Q21", help="remodel: the human answer licensing it (REMODELS)")
    ap.add_argument("--report", help="rebind: write every entry's equivalence result (JSON) to this file, rewritten "
                                     "after each entry")
    ap.add_argument("--deadline", type=float, help="rebind: a time box in seconds for the whole run; when it fires, the "
                                                   "lemma search stops and the entry is UNKNOWN (search_stop: time box), "
                                                   "with its stats in the report")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.command == "rebind":   # F31: the binding_change entries of laws whose cone changed under a fixed statement
        global EQV_DEADLINE
        if a.deadline is not None:
            import time
            EQV_DEADLINE = time.monotonic() + a.deadline
        es, notes = binding_change_entries(a.milestone, root)
        bad, report = 0, {}
        for e in es:
            r = append(e, root) if a.append else check_entry(e, root)
            eqv = {k: v for k, v in (r.get("equivalence") or {}).items() if k not in ("pair_text", "proof", "laws")}
            report[e["law_id"]] = {"ok": r["ok"], "reason": r["reason"], "equivalence": eqv}
            print(f"{e['law_id']}: {'accepted' if r['ok'] else 'REJECTED'}{' and appended' if r['ok'] and a.append else ''}"
                  f": {r['reason']}")
            bad += not r["ok"]
            if a.report:   # incrementally: a killed run keeps the entries it finished
                Path(a.report).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        for n in notes:
            print(f"no binding_change entry: {n}")
        if a.report:
            Path(a.report).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
        print(f"{len(es)} binding_change entries, {bad} rejected; {len(notes)} laws need another kind")
        return 0 if not bad else 1
    if a.command == "remodel":   # I68: the remodel entries of the typed model's laws whose cone the remodel changed
        es, notes = remodel_entries(a.milestone, root, a.license)
        bad = 0
        for e in es:
            r = append(e, root) if a.append else check_entry(e, root)
            print(f"{e['law_id']}: {'accepted' if r['ok'] else 'REJECTED'}{' and appended' if r['ok'] and a.append else ''}"
                  f": {r['reason']}")
            bad += not r["ok"]
        for n in notes:
            print(f"no remodel entry: {n}")
        print(f"{len(es)} remodel entries, {bad} rejected; {len(notes)} laws need another kind")
        return 0 if not bad and not notes else 1
    if a.command == "recatalog":   # F30: the catalog_rederivation entries of the milestone's uncovered registry changes
        es, notes = catalog_rederivation_entries(a.milestone, root)
        bad = 0
        for e in es:
            r = append(e, root) if a.append else check_entry(e, root)
            print(f"{e['law_id']}: {'accepted' if r['ok'] else 'REJECTED'}{' and appended' if r['ok'] and a.append else ''}"
                  f": {r['reason']}")
            bad += not r["ok"]
        for n in notes:
            print(f"not a catalog re-derivation, no entry: {n}")
        print(f"{len(es)} catalog_rederivation entries, {bad} rejected; {len(notes)} uncovered changes of another kind")
        return 0 if not bad else 1
    if a.command == "reextract":
        es = reextraction_entries(a.milestone, root)
        bad = 0
        for e in es:
            r = append(e, root) if a.append else check_entry(e, root)
            print(f"{e['law_id']}: {'accepted' if r['ok'] else 'REJECTED'}{' and appended' if r['ok'] and a.append else ''}"
                  f": {r['reason']}")
            bad += not r["ok"]
        print(f"{len(es)} reextraction entries, {bad} rejected")
        return 0 if not bad else 1
    if a.command == "append":
        if not a.entry:
            ap.error("append needs ENTRY.json")
        r = append(json.loads(Path(a.entry).read_text()), root)
        print(("appended: " if r["ok"] else "rejected, not appended: ") + r["reason"])
        return 0 if r["ok"] else 1
    s = scan(root / LOG, root)
    print(s["note"])
    for x in s["entries"]:
        print(f"line {x['line']}: {_line_tag(x['entry'])}: {'accepted' if x['ok'] else 'NOT accepted'}"
              + (f" (committed at {x['commit'][:7]})" if x["committed"] else " (new)"))
    for p in s["problems"]:
        print("PROBLEM", p)
    return 0 if not s["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
