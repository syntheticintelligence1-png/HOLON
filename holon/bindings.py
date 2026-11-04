"""Semantic bindings (whitepaper §8.9 references by hash, §9.4 stale propagation, L22).

A frozen statement's hash covers its IR and the facts hash, not the model definitions
it calls (generator names such as `perm` or `no_code`, the observers, the `b_*`
builtins). The bindings close that gap: each law is bound to the sha256 of the *kernel
form* of every definition its statement reaches.

The kernel form comes from the pinned checker itself: `bend model.bend -o model.bendtt`
writes the BendTT translation of every definition and datatype the model uses (Base
definitions included), alpha-normalized (locals become x0, x1, ...), with every global
reference resolved. So:
  * the dependency graph is the elaborator's, not a reading of HOLON's own text;
  * renaming a local or editing a comment changes no entry, so it binds the same;
  * any change of meaning in a reached definition changes its entry, so the binding
    fails and names exactly the laws whose cone contains it (results/<m>/deps.json).

Roots of a law: the `M.<name>` references of its emitted frozen statement (a constructor
maps to the datatype that declares it), closed over the BendTT graph. An `M.` reference
that resolves to nothing, a definition BendTT leaves out of scope, an empty cone, or a
model definition named like a BendTT local (x<digits>) is an error, never a silent gap.

A binding also pins what the emitter prints: the sha256 of the emitted statement and of the
emitted counter-law (comment lines removed). They include the law-local definitions the
cone cannot see (pin_h, the View types and projections), so an emitter change that adds,
drops or alters a premise, a quantifier or the erased fields fails G2 even when the IR and
the model are unchanged. (BUILD_PLAN I2 also listed generator_sha256 in each binding; it is
not bound: a refactor that emits identical text changes no meaning, and the records carry
it for G1.)

Files:
  gen/<m>/model/<model>.defs.json   kernel index: definition -> {sha256, refs}   (generated, G1)
  results/<m>/deps.json             model -> definition -> laws whose cone contains it (generated,
                                    G1); "dependents" is the same index by bare name, which merges
                                    same-named definitions of different models
  spec/bindings/<m>.json            law -> {statement_hash, model, statement_sha256, counter_sha256,
                                    cone: {def: sha256}}; an I30 typed-SORT law is bound to the typed model
                                    gen/<m>/sorts/models/<model>.bend as its records name it, and to its law file
                                    and counter-law as holon.sorts.proofs3 emits them (F30); an UNDO law (I27) is
                                    bound to its trace section gen/<m>/undo/models/<model>.bend (which imports the
                                    typed model as M) and to its law file and counter-law as holon.undo.proofs emits
                                    them; its kernel form is the typed model followed by the trace section unqualified,
                                    and its roots are the M. and U. references of its statement
  spec/bindings/changes.jsonl       append-only log of every write: creations and accepted changes
`python -m holon bind` writes a missing bindings file (logging the creation); with --laws it (re)binds only the laws named
and keeps every other law's binding as it is. On an existing one it adds the
bindings of new laws and drops those of laws no longer in laws/<m>, but it changes the binding of an existing law
only through the statement lifecycle (I10; audit F-M2-09): every changed law needs an accepted entry of
laws/STATEMENT_DIFF.jsonl (holon.statement_diff.scan) for exactly that law and its current statement, either a
statement change (strengthening, weakening, reextraction) when its statement hash changed, a catalog_rederivation
(F30) when the statement hash is all that changed in the binding, a binding_change naming every definition whose
kernel form changed under the fixed statement, or (I68) a remodel of the law's model, which its own check
(holon.statement_diff._remodel) accepts only when nothing but the cone changed; --remodel LICENSE appends those entries
first (holon.statement_diff.remodel_entries, each checked before it is appended). --accept-change "<reason>" is the
human-readable reason, logged with the covering entry line numbers; it is no longer sufficient on its own. Gate G2
re-derives the bindings from the committed models and checks that every change line logged after the log was
introduced (holon.statement_diff.cutoff_commit) maps to such accepted entries (check_change_log). Off git that
check cannot run, and G2 says so. Self-certified until the human's freeze (Q1): spec/bindings is agent-writable.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from . import bend, ir, records
from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
BINDINGS_DIR = Path("spec") / "bindings"
CHANGES = BINDINGS_DIR / "changes.jsonl"

_ENTRY = re.compile(r"^(?:opaque )?(\S+) : ", re.M)
_QNAME = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
_TAG = re.compile(r"(?<![\w])\.([A-Za-z_][A-Za-z0-9_]*)")
_QUAL = re.compile(r"(?<![\w.])M\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
_LOCAL = re.compile(r"^x[0-9]+$")
_DTYPE_ENUM = re.compile(r"=\s*Σx[0-9]+ : <([A-Za-z0-9_, ]+)>")


class BindingError(Exception):
    pass


# ---------------------------------------------------------------- kernel form
def bendtt_text(model: Path, cfg: dict | None = None, shown: str | None = None, keep_dir: bool = False) -> str:
    """The BendTT translation of a model file, copied alone to a fresh directory (keep_dir: translated where it is,
    beside the modules it imports)."""
    model = Path(model)
    shown = shown or model.name
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-"))
    try:
        src = tmp / model.name
        if keep_dir:
            src = model
        else:
            shutil.copy(model, src)
        out = tmp / (model.stem + ".bendtt")
        r = bend.run([src.name, "-o", str(out) if keep_dir else out.name], cwd=src.parent, cfg=cfg)
        if r.code != 0 or not out.exists():
            raise BindingError(f"bend could not translate {shown} to BendTT: {r.out[:1500]}")
        if "out of scope" in r.out:
            raise BindingError(f"BendTT left definitions of {shown} out of scope (they would be unbound): "
                               f"{r.out[:800]}")
        return out.read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@lru_cache(maxsize=None)
def _entries_cached(model_text: str, cfg_json: str, shown: str) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-src-"))
    try:
        f = tmp / "model.bend"
        f.write_text(model_text)
        text = bendtt_text(f, json.loads(cfg_json) if cfg_json else None, shown)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    entries = parse_entries(text, shown)
    bad = sorted(n for n in entries if _LOCAL.match(n))
    if bad:
        raise BindingError(f"{shown}: definitions named like BendTT locals ({bad}) would rename every local of "
                           "the translation and change every binding")
    return tuple(sorted(entries.items()))


def kernel_entries(model: Path, cfg: dict | None = None) -> dict[str, str]:
    """BendTT entry name -> its full text (type and body), for a model file."""
    model = Path(model)
    try:
        shown = model.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown = model.name
    return dict(_entries_cached(model.read_text(), json.dumps(cfg, sort_keys=True) if cfg else "", shown))


def parse_entries(text: str, shown: str = "BendTT text") -> dict[str, str]:
    ms = list(_ENTRY.finditer(text))
    if text[:ms[0].start() if ms else len(text)].strip():
        raise BindingError(f"{shown}: unexpected text before the first BendTT entry")
    for line in text.splitlines():
        if line and not line[0].isspace() and not _ENTRY.match(line + " "):
            raise BindingError(f"{shown}: unrecognised BendTT line {line[:80]!r}")
    out = {}
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out[m.group(1)] = text[m.start():end].strip() + "\n"
    return out


def tag_owner(entries: dict[str, str]) -> dict[str, str]:
    """Constructor tag -> the datatype whose body (`= Σx : <tags> -> ...`) enumerates it."""
    own = {}
    for name, text in entries.items():
        for m in _DTYPE_ENUM.finditer(text):
            for tag in (t.strip() for t in m.group(1).split(",")):
                if tag:
                    own.setdefault(tag, name)
    return own


def kernel_graph(entries: dict[str, str]) -> dict[str, list[str]]:
    own = tag_owner(entries)
    g = {}
    for name, text in entries.items():
        body = text[len(name):]
        refs = {t for t in _QNAME.findall(body) if t in entries and t != name}
        refs |= {own[t] for t in _TAG.findall(body) if t in own and own[t] != name}
        g[name] = sorted(refs)
    return g


def defs_index(model: Path, cfg: dict | None = None) -> dict:
    entries = kernel_entries(model, cfg)
    g = kernel_graph(entries)
    return {"model": Path(model).stem, "kernel": "bendtt",
            "defs": {n: {"sha256": hashlib.sha256(t.encode()).hexdigest(), "refs": g[n]} for n, t in sorted(entries.items())}}


def _resolve_root(tok: str, entries: dict[str, str], own: dict[str, str]) -> str | None:
    """The longest dotted prefix that names a kernel entry, else a constructor's datatype."""
    parts = tok.split(".")
    for k in range(len(parts), 0, -1):
        name = ".".join(parts[:k])
        if name in entries:
            return name
    return own.get(parts[0])


def kernel_cone(statement_text: str, entries: dict[str, str]) -> list[str]:
    own = tag_owner(entries)
    g = kernel_graph(entries)
    roots = set()
    for tok in _QUAL.findall(re.sub(r"#[^\n]*", "", statement_text)):
        r = _resolve_root(tok, entries, own)
        if r is None:
            raise BindingError(f"M.{tok} in the statement resolves to no kernel entry: it would be unbound")
        roots.add(r)
    if not roots:
        raise BindingError("the statement names no model definition: an empty cone binds nothing")
    seen, todo = set(), sorted(roots)
    while todo:
        d = todo.pop()
        if d not in seen:
            seen.add(d)
            todo.extend(x for x in g[d] if x not in seen)
    return sorted(seen)


# ---------------------------------------------------------------- statements and models
def registry_facts(m: str, root: Path) -> str:
    return ir.load_registry(m, root).get("facts", "facts/morph_header.json")


def law_facts(law: dict, m: str, root: Path) -> str:
    return law.get("facts") or registry_facts(m, root)


def _width(law: dict) -> bool:
    """A SORT-width law (I20, holon.sorts.width): about the extracted model, which no law emitter targets."""
    from .sorts.width import width_law
    return width_law(law) is not None


def _typed(law: dict) -> bool:
    """An I30 typed-SORT law: a holon-ir/0.3 law of holon.rules.sort's subforms (realize, as_member, reinterpret) whose
    claim is a coerce term. holon.sorts.run3 decides it over the typed model of its transitions document, and
    holon.sorts.proofs3 emits its law file (F30). A hand-written holon-ir/0.2 law naming the same subform (M1's
    L_sort_remaining) is not one."""
    from .rules.sort import RULE, SUBFORMS
    if law.get("ir_version") != "holon-ir/0.3" or law.get("rule") != RULE or law.get("subform") not in SUBFORMS:
        return False

    def coerce(t) -> bool:
        if isinstance(t, dict):
            return "coerce" in t or any(coerce(v) for v in t.values())
        return isinstance(t, list) and any(coerce(v) for v in t)
    return coerce((law.get("statement") or {}).get("claim"))


def _disch(law: dict) -> bool:
    """An I31 DISCH law (holon.rules.disch): a holon-ir/0.3 law whose claim is a disch term. holon.disch.run decides
    it over the typed model of its document and the DISCH section, and writes its law file with
    holon.disch.proofs.laws_text."""
    if law.get("ir_version") != "holon-ir/0.3" or law.get("rule") != "DISCH":
        return False
    c = (law.get("statement") or {}).get("claim") or {}
    return any(isinstance(x, dict) and "disch" in x for x in c.get("eq") or [])


def _disch_section(law: dict, m: str, root: Path) -> Path:
    """The DISCH section a DISCH law's file imports (gen/<m>/disch/models/<importable section name>)."""
    from .disch.section import section_file
    from .sorts.model3 import model_name as typed_name
    return Path(root) / "gen" / m / "disch" / "models" / section_file(typed_name(law["facts"]))


def _contract3(law: dict) -> bool:
    """A typed contract law (I33): a holon-ir/0.3 intended_weak law whose statement uses the typed terms (sread, wnat,
    cmp, ok, is, env). holon.sorts.contract3_run decides it over the typed model of its document, and
    holon.sorts.contract3.law_file emits its law file (imported by name, as FACT's generator is, so it stays out of
    the records' closures)."""
    if law.get("ir_version") != "holon-ir/0.3" or law.get("subform") != "intended_weak":
        return False
    import importlib
    return importlib.import_module("holon.sorts.contract3").uses_b1(law.get("statement") or {})


def _typed_model(law: dict, m: str, root: Path, importable: bool = False) -> Path:
    """The typed model of a typed-SORT law, as its records name it (gen/<m>/sorts/models/<model>.bend, a link: docs/
    HUMAN_ANSWERS.md Q25) or, with importable, the file behind that link which its law file imports."""
    from .sorts.model3 import importable as plain, model_name as typed_name
    name = typed_name(law["facts"])
    return Path(root) / "gen" / m / "sorts" / "models" / (plain(name) if importable else f"{name}.bend")


def _undo(law: dict) -> bool:
    """An UNDO law (I27): a holon-ir/0.3 law of holon.rules.undo whose claim is an undo term. holon.undo.run decides it
    over the typed model of its document and the trace section, and holon.undo.proofs emits its law file."""
    from .rules.undo import RULE

    def term(t) -> bool:
        if isinstance(t, dict):
            return "undo" in t or any(term(v) for v in t.values())
        return isinstance(t, list) and any(term(v) for v in t)
    return law.get("ir_version") == "holon-ir/0.3" and law.get("rule") == RULE and \
        term((law.get("statement") or {}).get("claim"))


def _trace_model(law: dict, m: str, root: Path, importable: bool = False) -> Path:
    """The trace section of an UNDO law's document, as its records name it (gen/<m>/undo/models/<model>.bend, a link)
    or, with importable, the file behind that link which its law file imports."""
    from .sorts.model3 import importable as plain, model_name as typed_name
    name = typed_name(law["facts"])
    return Path(root) / "gen" / m / "undo" / "models" / (plain(name) if importable else f"{name}.bend")


def _sym(law: dict) -> bool:
    """A SYM law (I34): a holon-ir/0.3 law of holon.rules.sym, of one of its sub-forms (its claim a sym term).
    holon.symd.run decides it over the typed model of its document and the sym section, and holon.symd.proofs emits its
    law file. Rule SYM's member sub-forms (I92) are _symb's."""
    from .rules.sym import RULE, SUBFORMS
    return law.get("ir_version") == "holon-ir/0.3" and law.get("rule") == RULE and law.get("subform") in SUBFORMS


def _symb(law: dict) -> bool:
    """A SYM member law (I92): a holon-ir/0.3 law of holon.rules.symb (its claim a symb term). holon.symb.lawrun decides
    it over its member's bundle model and generated section, and emits its law file (law_text)."""
    from .rules.symb import is_symb_law
    return is_symb_law(law)


def _gox(law: dict) -> bool:
    """A PAR Go law (I93): a holon-ir/0.3 law of holon.rules.gox (its claim a gox term). holon.gox.lawrun decides it
    over its generated module gen/<m>/gox/<law>.bend; the binding is its statement hash, as a slash law's is."""
    from .rules.gox import is_gox_law
    return is_gox_law(law)


def _symb_files(law: dict, m: str, root: Path) -> tuple:
    """(the member's bundle model, its SYM section, its sections index entry) of a SYM member law."""
    member = Path(law["facts"]).stem
    root = Path(root)
    idx = json.loads((root / "gen" / m / "symb" / "sections" / "index.json").read_text())["laws"]
    return (root / "gen" / m / "bundle" / "models" / f"{member}.bend",
            root / "gen" / m / "symb" / "sections" / f"{member}.bend", idx.get(law["law_id"]))


def _symb_kernel_text(law: dict, m: str, root: Path) -> str:
    """The member's bundle model followed by its SYM section unqualified (its imports dropped, `M.` removed), one
    module BendTT translates whole."""
    mp, sp, _e = _symb_files(law, m, root)
    model = mp.read_text()
    section = _M_QUAL.sub("", _IMPORT_LINE.sub("", sp.read_text()))
    own = set(records.model_defs(model))
    keep, drop = [], False
    for line in section.splitlines():
        top = _TOP.match(line)
        if top:
            drop = top.group(1) in own
        elif line and not line[0].isspace() and not line.startswith("#"):
            drop = False
        if not drop:
            keep.append(line)
    return model.rstrip("\n") + "\n\n" + "\n".join(keep) + "\n"


def _sym_section(law: dict, m: str, root: Path) -> Path:
    """The sym section of a SYM law's document, gen/<m>/sym/models/<model>.bend under the importable name holon.symd.run
    writes it at (its law files import it as U)."""
    from .sorts.model3 import importable as plain, model_name as typed_name
    return Path(root) / "gen" / m / "sym" / "models" / plain(typed_name(law["facts"]))


def _fact(law: dict) -> bool:
    """A FACT law (I26): a holon-ir/0.3 law of holon.rules.fact whose claim is a fact term. holon.fact.run decides it
    over the typed model of its document and the FACT section, and holon.fact.proofs.law_file emits its law file."""
    from .rules.fact import RULE

    def term(t) -> bool:
        if isinstance(t, dict):
            return "fact" in t or any(term(v) for v in t.values())
        return isinstance(t, list) and any(term(v) for v in t)
    return law.get("ir_version") == "holon-ir/0.3" and law.get("rule") == RULE and \
        term((law.get("statement") or {}).get("claim"))


def _fact_section(law: dict, m: str, root: Path, importable: bool = False) -> Path:
    """The FACT section of a FACT law's document, as its records name it (gen/<m>/fact/models/<model>.fact.bend, a
    link) or, with importable, the file behind that link which its law file imports."""
    from .sorts.model3 import importable as plain, model_name as typed_name
    name = typed_name(law["facts"]) + ".fact"
    return Path(root) / "gen" / m / "fact" / "models" / (plain(name) if importable else f"{name}.bend")


def _pinit(law: dict) -> bool:
    """A PAR-init law (I28): a holon-ir/0.3 law of rule PAR, sub-form init_chain, over a versioned document.
    holon.versions.run decides it over the versioned layer, and holon.versions.proofs.law_file emits its law file."""
    from .rules.par_init import RULE, SUBFORM
    return law.get("ir_version") == "holon-ir/0.3" and law.get("rule") == RULE and law.get("subform") == SUBFORM


def _nat(law: dict) -> bool:
    """A NAT law (I29): a holon-ir/0.3 law of rule NAT, of one of I29's sub-forms (holon.rules.nat.SUBFORMS), over a
    versioned document. holon.rules.nat_run decides it over the versioned layer and its claims module, and emits its
    law file (holon.rules.nat_run.law_file)."""
    from .rules.nat import SUBFORMS
    return law.get("ir_version") == "holon-ir/0.3" and law.get("rule") == "NAT" and law.get("subform") in SUBFORMS


def _slash(law: dict) -> bool:
    """A slash law (I70, holon.rules.slash: rules NAT and SORT, sub-form slash): a holon-ir/0.3 law whose claim is a
    slash term. holon.cutover.lawrun decides it over the linked layer and its claims module; while those are not built
    no emitter states it, so its binding is its statement hash alone, over the registry model the cutover's model step
    writes (the sidecar's outputs.models)."""
    from .rules import slash as S
    if law.get("ir_version") != "holon-ir/0.3" or law.get("subform") != S.SUBFORM or law.get("rule") not in S.RULES:
        return False
    c = (law.get("statement") or {}).get("claim") or {}
    return any(isinstance(x, dict) and "slash" in x for x in c.get("eq") or [])


def _slash_model(m: str, root: Path) -> Path:
    side = json.loads((Path(root) / S_SIDECAR.format(m)).read_text())
    return Path(root) / side["outputs"]["models"] / f"{side['link']['a']['registry']}.bend"


S_SIDECAR = "spec/{}/lib/cutover_slash.json"


def _nat_run():
    """holon.rules.nat_run, imported by name (as holon.versions is) so that NAT's decider stays out of the M1-M3
    records' closure."""
    import importlib
    return importlib.import_module("holon.rules.nat_run")


_N_QUAL = re.compile(r"(?<![\w.])N\.")


def nat_layer_entries(law: dict, m: str, root: Path, cfg: dict | None = None) -> dict[str, str]:
    """BendTT entry name -> its full text for a NAT law: the versioned layer with the claims module's definitions
    appended unqualified (its imports dropped, `M.` removed), translated together with the version modules the layer
    imports (an imported module's entries are named by its file's stem): one module, as the UNDO and FACT sections."""
    nr = _nat_run()
    nctx = nr.NatCtx(Path(root), m)
    layer = nctx.layer_path().resolve()
    files, todo = {}, [layer.name]
    while todo:
        name = todo.pop()
        if name in files:
            continue
        text = (layer.parent / name).read_text()
        files[name] = text
        todo.extend(_LOCAL_IMPORT.findall(text))
    claims = nctx.module_path().read_text()
    body = "\n".join(ln for ln in claims.splitlines() if not ln.startswith("import "))
    files[layer.name] = files[layer.name].rstrip("\n") + "\n\n" + re.sub(r"(?<![\w.])M\.", "", body) + "\n"
    try:
        shown = nctx.module_path().relative_to(Path(root)).as_posix()
    except ValueError:
        shown = nctx.module_path().name
    return dict(_layer_entries_cached(tuple(sorted(files.items())), layer.name,
                                      json.dumps(cfg, sort_keys=True) if cfg else "", shown))


def _bundle(law: dict) -> bool:
    """A bundle law of holon-rules/1.10 (I84, holon.rules.bundle2: PAR link_domain, FACT public_input, DISCH
    self_controlled): a holon-ir/0.3 law whose claim is a bundle term of those sub-forms (the term's id names them:
    holon.rules.bundle_terms; holon-rules/1.11's are _bundle_law's). holon.bundle2.laws_decide decides it over the typed
    model at the laws' deployment and the claims module (which holds the callee's model's copy), and writes its law
    file."""
    from .rules import bundle2, bundle_terms
    return bundle_terms.law_owner(law) is bundle2


def _bundle_files(law: dict, m: str, root: Path) -> tuple[Path, Path]:
    """(the typed model at the laws' deployment, the claims module) of a bundle law: the bundle-laws sidecar's
    outputs.claims_dir (spec/<m>/lib/bundle2_laws.json)."""
    side = json.loads((Path(root) / "spec" / m / "lib" / "bundle2_laws.json").read_text())
    d = Path(root) / side["outputs"]["claims_dir"]
    return d / "rollup.bend", d / "claims.bend"


def _versions(name: str):
    """A holon.versions module, imported by name (as holon.fact.proofs is) so that the versioned layer's generator
    stays out of the M1-M3 records' closure."""
    import importlib
    return importlib.import_module(f"holon.versions.{name}")


def _bundle_law(law: dict) -> bool:
    """A bundle law of holon-rules/1.11 (I86, holon.rules.bundle): a holon-ir/0.3 law whose claim is a bundle term of
    its sub-forms (the term's id names them: holon.rules.bundle_terms; holon-rules/1.10's are _bundle's).
    holon.bundle.lawrun decides it over its member's law model and claims module, and emits its law file
    (holon.bundle.lawrun.law_file)."""
    from .rules import bundle, bundle_terms
    return bundle_terms.law_owner(law) is bundle


def _lawrun():
    """holon.bundle.lawrun, imported by name (as holon.versions is) so that the bundle laws' decider stays out of the
    M1-M3 records' closure."""
    import importlib
    return importlib.import_module("holon.bundle.lawrun")


_C_QUAL = re.compile(r"(?<![\w.])C\.")


def _bundle_law_kernel_text(law: dict, m: str, root: Path) -> str:
    """The kernel form's source of an I86 bundle law: its law model followed by its claims module unqualified (the claims'
    imports dropped, `M.` removed), one module BendTT translates whole; a claims definition named like a model
    definition is an error, never a silent shadow."""
    lr = _lawrun()
    lctx = lr.LawCtx(Path(root), m)
    _sub, mname, _site, _cls = lr.site_of(lctx, law["law_id"])
    model = lctx.model_path(mname).read_text()
    claims = _M_QUAL.sub("", _IMPORT_LINE.sub("", lctx.claims_path(mname).read_text()))
    clash = sorted(set(records.model_defs(claims)) & set(records.model_defs(model)))
    if clash:
        raise BindingError(f"{law['law_id']}: claims definitions named like model definitions: {clash[:5]}")
    return model.rstrip("\n") + "\n\n" + claims.rstrip("\n") + "\n"


_LOCAL_IMPORT = re.compile(r"(?m)^import\s+\./([A-Za-z0-9_]+\.bend)\s+as\s+[A-Za-z0-9_]+\s*$")


@lru_cache(maxsize=None)
def _layer_entries_cached(files: tuple, top: str, cfg_json: str, shown: str) -> tuple:
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-layer-"))
    try:
        for name, text in files:
            (tmp / name).write_text(text)
        text = bendtt_text(tmp / top, json.loads(cfg_json) if cfg_json else None, shown, keep_dir=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    entries = parse_entries(text, shown)
    bad = sorted(n for n in entries if _LOCAL.match(n))
    if bad:
        raise BindingError(f"{shown}: definitions named like BendTT locals ({bad}) would rename every local of "
                           "the translation and change every binding")
    return tuple(sorted(entries.items()))


def layer_entries(model: Path, cfg: dict | None = None) -> dict[str, str]:
    """BendTT entry name -> its full text, for a module with the modules of its directory it imports (`import ./x.bend
    as X`, transitively): the versioned layer (I28) and its version modules, translated together (an imported
    module's entries are named by its file's stem)."""
    model = Path(model).resolve()
    files, todo = {}, [model.name]
    while todo:
        name = todo.pop()
        if name in files:
            continue
        text = (model.parent / name).read_text()
        files[name] = text
        todo.extend(_LOCAL_IMPORT.findall(text))
    try:
        shown = model.relative_to(ROOT).as_posix()
    except ValueError:
        shown = model.name
    return dict(_layer_entries_cached(tuple(sorted(files.items())), model.name,
                                      json.dumps(cfg, sort_keys=True) if cfg else "", shown))


_IMPORT_LINE = re.compile(r"(?m)^import [^\n]*\n")
_M_QUAL = re.compile(r"(?<![\w.])M\.")
_U_QUAL = re.compile(r"(?<![\w.])U\.")
_F_QUAL = re.compile(r"(?<![\w.])F\.")
_TOP = re.compile(r"^(?:def|type)\s+([A-Za-z_][A-Za-z0-9_]*)")


def _undo_kernel_text(law: dict, m: str, root: Path) -> str:
    """The kernel form's source of an UNDO law: the typed model followed by its trace section unqualified (its imports
    dropped, `M.` removed, and its re-exports of the model's own definitions, such as run, dropped: unqualified they
    would redeclare them), one module BendTT translates whole. A FACT law's is the same with its FACT section."""
    model = _typed_model(law, m, root, importable=True).read_text()
    section = (_fact_section(law, m, root, importable=True) if _fact(law) else
               _sym_section(law, m, root) if _sym(law) else _trace_model(law, m, root, importable=True))
    trace = _M_QUAL.sub("", _IMPORT_LINE.sub("", section.read_text()))
    own = set(records.model_defs(model))
    keep, drop = [], False
    for line in trace.splitlines():
        top = _TOP.match(line)
        if top:
            drop = top.group(1) in own
        elif line and not line[0].isspace() and not line.startswith("#"):
            drop = False
        if not drop:
            keep.append(line)
    return model.rstrip("\n") + "\n\n" + "\n".join(keep) + "\n"


def _bundle_kernel_text(law: dict, m: str, root: Path) -> str:
    """The kernel form's source of a bundle law: the typed model at the laws' deployment followed by the claims module
    unqualified (its imports dropped, `M.` removed), one module BendTT translates whole, as a FACT law's."""
    mp, cp = _bundle_files(law, m, root)
    model = mp.read_text()
    section = _M_QUAL.sub("", _IMPORT_LINE.sub("", cp.read_text()))
    own = set(records.model_defs(model))
    keep, drop = [], False
    for line in section.splitlines():
        top = _TOP.match(line)
        if top:
            drop = top.group(1) in own
        elif line and not line[0].isspace() and not line.startswith("#"):
            drop = False
        if not drop:
            keep.append(line)
    return model.rstrip("\n") + "\n\n" + "\n".join(keep) + "\n"


def model_path(law: dict, m: str, root: Path) -> Path:
    from .model_eval import model_name
    if _gox(law):   # I93: the law's generated module gen/<m>/gox/<law>.bend
        return Path(root) / "gen" / m / "gox" / f"{law['law_id']}.bend"
    if _symb(law):   # I92: the member's bundle model gen/<m>/bundle/models/<member>.bend (its section is U)
        return _symb_files(law, m, root)[0]
    if _slash(law):   # I70: the registry model gen/<m>/cutover/models/<registry>.bend (the cutover's model step)
        return _slash_model(m, root)
    if _bundle(law):   # I84: the claims module gen/<m>/bundle2/claims/claims.bend (its record's artifacts.model)
        return _bundle_files(law, m, root)[1]
    if _bundle_law(law):   # I86: the member's law model (holon.bundle.laws: I69's model, or the adopted member's)
        lr = _lawrun()
        lctx = lr.LawCtx(Path(root), m)
        return lctx.model_path(lr.site_of(lctx, law["law_id"])[1])
    if _pinit(law):   # I28: the versioned model gen/<m>/versions/models/<model>.bend (a link to the layer)
        return _versions("proofs").model_paths(m, root)[0]
    if _nat(law):   # I29: the claims module gen/<m>/nat/models/<stem>_nat.bend (over the versioned layer)
        return _nat_run().NatCtx(Path(root), m).module_path()
    if _undo(law):   # I27: the trace section gen/<m>/undo/models/<model>.bend
        return _trace_model(law, m, root)
    if _sym(law):   # I34: the sym section gen/<m>/sym/models/<model>.bend
        return _sym_section(law, m, root)
    if _fact(law):   # I26: the FACT section gen/<m>/fact/models/<model>.fact.bend
        return _fact_section(law, m, root)
    if _width(law):   # the extracted model (holon model's gen/<m>/extracted/model.bend)
        from .sorts.width import model_path as width_model
        return width_model(m, root)
    if _typed(law) or _disch(law) or _contract3(law):   # F30: the typed model gen/<m>/sorts/models/<model>.bend (I30;
        return _typed_model(law, m, root)                # I31's DISCH laws; I33's typed contract laws)
    from .codecrun import codec_kind
    kind = codec_kind(law, root)
    if kind == "linked":   # I24: the component model gen/<m>/model/<role>.bend (rule X9)
        return root / "gen" / m / "model" / f"{F.load(root / law['facts'])['role']}.bend"
    if kind == "goops":   # I67 (rule Y8d): the Go-op component's model gen/<m>/model/<component>.bend
        return root / "gen" / m / "model" / f"{F.load(root / law['facts'])['component']}.bend"
    if kind == "gocount":   # I90 (rule C6d): the count component's model gen/<m>/model/<component>.bend
        return root / "gen" / m / "model" / f"{F.load(root / law['facts'])['component']}.bend"
    if kind == "own":   # I35 (rule W11): the carrier's model gen/<m>/model/own_<stem>.bend
        return root / "gen" / m / "model" / f"own_{F.load(root / law['facts'])['stem']}.bend"
    return root / "gen" / m / "model" / f"{model_name(law_facts(law, m, root))}.bend"


def _emit(law: dict, m: str, root: Path, counter: bool, conjunct: int | None = None) -> str | None:
    """The emitter's text for a law (statement or counter-law, of conjunct `conjunct` for a conjunction), as the
    pipelines emit it; None when the emitter cannot express that form."""
    from .model_eval import model_name
    from .mpipeline import layout
    if _width(law):   # no emitter states a width law: its record's cone roots are its entry points' steps
        return None
    if _slash(law):   # I70: no emitter states a slash law until the linked layer is built (holon.cutover.lawrun)
        return None
    if _gox(law):   # I93: as holon.gox.lawrun writes it from the basis; imported by name (outside the closures)
        import importlib
        return importlib.import_module("holon.gox.emit").emit(law, m, Path(root), counter)
    if _symb(law):   # I92: as holon.symb.lawrun writes it; imported by name, so the decider stays out of the closures
        import importlib
        SL = importlib.import_module("holon.symb.lawrun")
        _mp, _sp, e = _symb_files(law, m, root)
        if e is None:   # the sections no longer state the law (holon symb sections)
            return None
        laws_dir = Path(root) / "gen" / m / "laws" / law["law_id"]
        return SL.law_text(e, law["law_id"], statement_hash(law, m, root), laws_dir, Path(root), m, counter)
    if _bundle_law(law):   # I86: as holon.bundle.lawrun writes it (None: an existential law's counter-law, or a claim
        # the M3 model cannot express, CS3's outflow class)
        return _lawrun().law_file(law, m, root, statement_hash(law, m, root), counter)
    if _bundle(law):   # I84: as holon.bundle2.laws_decide writes it; imported by name, as FACT's emitter is
        import importlib
        from .sorts.proofs3 import rel_import
        LD = importlib.import_module("holon.bundle2.laws_decide")
        laws_dir = Path(root) / "gen" / m / "laws" / law["law_id"]
        mp, cp = _bundle_files(law, m, root)
        hashes = [b["name"] for b in law["statement"].get("binders", []) if str(b.get("type", "")).startswith("Fn<")]
        return LD.law_text(law, statement_hash(law, m, root), rel_import(laws_dir, mp), rel_import(laws_dir, cp),
                           hashes, counter)
    if _pinit(law):   # I28: emitted as holon.versions.run writes it (holon.versions.proofs.law_file)
        return _versions("proofs").law_file(law, m, root, statement_hash(law, m, root), counter)
    if _nat(law):   # I29: emitted as holon.rules.nat_run writes it (holon.rules.nat_run.law_file)
        return _nat_run().law_file(law, m, root, statement_hash(law, m, root), counter)
    if _disch(law):   # I31: as holon.disch.run writes it (holon.disch.proofs.laws_text); an external law (an
        from .disch import proofs as DP   # existential law, never REFUTED) has no counter-law
        from .disch.section import tables
        from .gen.mlaws import law_name
        from .sorts.proofs3 import rel_import
        if counter and law.get("subform") == "external":
            return None
        laws_dir = Path(root) / "gen" / m / "laws" / law["law_id"]
        hashes = [b["name"] for b in law["statement"].get("binders", []) if str(b.get("type", "")).startswith("Fn<")]
        kind = "counter" if counter else ("exists" if law.get("subform") == "external" else "forall")
        return DP.laws_text(law["law_id"], statement_hash(law, m, root),
                            rel_import(laws_dir, _typed_model(law, m, root, importable=True)),
                            rel_import(laws_dir, _disch_section(law, m, root)), tables(hashes),
                            law_name(law["law_id"], counter), kind)
    if _sym(law):   # I34: emitted as holon.symd.run writes it (holon.symd.proofs.law_file); imported by name, as FACT's
        import importlib   # generator is, so SYM's decider stays out of the M1-M3 records' closure
        from .rules import sym as RS
        from .sorts.evaluate3 import hashes_of
        from .sorts.model3 import model_name as typed_name
        from .sorts.proofs3 import rel_import
        SP = importlib.import_module("holon.symd.proofs")
        laws_dir = layout(m, Path(root) / "gen" / m, law["law_id"])[0]
        doc_rel = law["facts"]
        doc = json.loads((Path(root) / doc_rel).read_text())
        sorts = json.loads((Path(root) / "gen" / m / "sorts" / "assignment.json").read_text())
        els = RS.elements(doc, sorts["models"][typed_name(doc_rel)]["assignment"], doc_rel)
        n = next((i for i, e in enumerate(els) if e["law_id"] == law["law_id"]), None)
        if n is None:   # the document's analysis no longer gives the law (derive again)
            return None
        return SP.law_file(law, n, statement_hash(law, m, root),
                           rel_import(laws_dir, _typed_model(law, m, root, importable=True)),
                           rel_import(laws_dir, _sym_section(law, m, root)),
                           hashes_of(_typed_model(law, m, root, importable=True).read_text()), counter=counter)
    if _undo(law):   # I27: emitted as holon.undo.run writes it (holon.undo.proofs.law_file)
        import os
        from .undo import proofs as UP
        laws_dir = layout(m, Path(root) / "gen" / m, law["law_id"])[0]
        hashes = [b["name"] for b in law["statement"].get("binders", []) if str(b.get("type", "")).startswith("Fn<")]

        def rel(p: Path) -> str:
            return os.path.relpath(p, laws_dir).replace(os.sep, "/")
        return UP.law_file(law, statement_hash(law, m, root), rel(_typed_model(law, m, root, importable=True)),
                           rel(_trace_model(law, m, root, importable=True)), hashes, counter=counter)
    if _fact(law):   # I26: emitted as holon.fact.run writes it (holon.fact.proofs.law_file); imported by name, as
        import importlib   # holon.rules.fact does, so FACT's generator stays out of the M1-M3 records' closure
        from .sorts.proofs3 import rel_import
        FP = importlib.import_module("holon.fact.proofs")
        laws_dir = layout(m, Path(root) / "gen" / m, law["law_id"])[0]
        hashes = [b["name"] for b in law["statement"].get("binders", []) if str(b.get("type", "")).startswith("Fn<")]
        return FP.law_file(law, statement_hash(law, m, root),
                           rel_import(laws_dir, _typed_model(law, m, root, importable=True)),
                           rel_import(laws_dir, _fact_section(law, m, root, importable=True)), hashes, counter=counter)
    if _contract3(law):   # I33: emitted as holon.sorts.contract3_run writes it (holon.sorts.contract3.law_file), its
        import importlib   # tables the typed model's hash parameters; the counter-law of conjunct 0 by default
        from .sorts.evaluate3 import hashes_of
        from .sorts.proofs3 import rel_import, tabs_binders
        C3 = importlib.import_module("holon.sorts.contract3")
        laws_dir = layout(m, Path(root) / "gen" / m, law["law_id"])[0]
        tm = _typed_model(law, m, root, importable=True)
        tables = [n for n, _h in tabs_binders(hashes_of(tm.read_text()))]
        return C3.law_file(law, F.load(root / law["facts"]), statement_hash(law, m, root), rel_import(laws_dir, tm),
                           tables, "counter" if counter else "law", (conjunct or 0) if counter else None)
    if _typed(law):   # F30: emitted as holon.sorts.run3 writes it (holon.sorts.proofs3.law_file), one law-parameter
        from .sorts import proofs3 as P3   # table per hash function the IR's Fn binders name, importing the typed model
        laws_dir = layout(m, Path(root) / "gen" / m, law["law_id"])[0]
        hashes = [b["name"] for b in law["statement"].get("binders", []) if str(b.get("type", "")).startswith("Fn<")]
        return P3.law_file(law, statement_hash(law, m, root),
                           P3.rel_import(laws_dir, _typed_model(law, m, root, importable=True)), hashes, counter=counter)
    fp = root / law_facts(law, m, root)
    from .codecrun import codec_kind
    kind = codec_kind(law, root)
    if kind is not None:   # I24: a codec law, emitted as holon.codecrun emits it
        from .gen import codec01 as C1
        from .gen import gocount as GN
        from .gen import goloop as GG
        from .gen import linked as GL
        imp = f"{layout(m, root, law['law_id'])[2]}model/{model_path(law, m, root).name}"
        note = statement_hash(law, m, root)
        try:
            if kind == "linked":
                return GL.emit(law, F.load(fp), imp, counter=counter, note=note).text
            if kind == "goops":   # I67: as holon.codecrun writes a Go-op law's file (holon.gen.goloop.emit)
                return GG.emit(law, F.load(fp), imp, counter=counter, note=note).text
            if kind == "gocount":   # I90: as holon.codecrun writes a count law's file (holon.gen.gocount.emit)
                return GN.emit(law, F.load(fp), imp, counter=counter, note=note).text
            if kind == "own":   # I35: as holon.own_run writes an OWN law's file (holon.gen.ownheap.emit)
                from .gen import ownheap as OH
                try:
                    return OH.emit(law, F.load(fp), imp, counter=counter, note=note).text
                except OH.Unsupported:
                    return None
            return C1.emit(C1.to01(law), F.load(fp), imp, counter=counter, header_note=note).text
        except (GL.Unsupported, GG.Unsupported, GN.Unsupported, C1.Unsupported):
            return None
    imp = f"{layout(m, root, law['law_id'])[2]}model/{model_name(fp)}.bend"   # as the pipelines import it (I10)
    if law["ir_version"] == "holon-ir/0.1":
        from .gen import laws as LG
        try:
            return LG.emit(law, F.load(fp), imp, counter=counter, header_note=ir.statement_hash(law)).text
        except LG.Unsupported:
            return None
    from .gen import mlaws
    from .gen.machine import Machine
    from .gen.oracles import Oracles
    from .mpipeline import m2plus
    orc = Oracles.for_milestone(m, fp, root)   # M2+ models take their oracles as parameters (I12; F-M2-11)
    try:
        return mlaws.Emitter(Machine(F.load(fp), fp, oracles=orc, m2plus=m2plus(m))).emit(law, imp, counter=counter,
                                                                                          note=ir.statement_hash(law),
                                                                                          conjunct=conjunct).text
    except mlaws.Unsupported:
        return None


def counter_binding(law: dict, m: str, root: Path):
    """The bound counter-law: the sha256 of its emission; for a holon-ir/0.3 conjunction, whose counter-law states
    the negation of the failing conjunct (I7), the list of one sha256 per conjunct (G2 picks the record's
    failing_conjunct). 0.1/0.2 bindings keep their pinned form."""
    c = law["statement"].get("claim", {})
    if law.get("ir_version") == "holon-ir/0.3" and len(c.get("all", [])) > 1:
        return [text_sha256(_emit(law, m, root, counter=True, conjunct=i)) for i in range(len(c["all"]))]
    return text_sha256(_emit(law, m, root, counter=True))


def bound_counter(bound: dict, rec: dict) -> str | None:
    """The counter-law sha256 a REFUTED record's checked LAWS.bend must have (counter_binding)."""
    v = bound.get("counter_sha256")
    if isinstance(v, list):
        i = rec.get("failing_conjunct")
        return v[i] if isinstance(i, int) and 0 <= i < len(v) else None
    return v


def statement_text(law: dict, m: str, root: Path) -> str:
    """The emitted frozen statement (never a counter-law), or the IR's names when it is inexpressible (a width law:
    the roots its record's cone is computed from, holon.sorts.width.roots_text)."""
    if _width(law):
        from .sorts.width import roots_text
        return roots_text(law, root)
    t = _emit(law, m, root, counter=False)
    if t is not None and _disch(law):   # I31: the statement reaches the model through the DISCH section's terms
        sp = _disch_section(law, m, root)
        if sp.is_file():
            t = t + "\n" + sp.read_text()
    return t if t is not None else records.ir_roots_text(law)


def text_sha256(text: str | None) -> str | None:
    if text is None:
        return None
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return hashlib.sha256(body.encode()).hexdigest()


def model_definitions(m: str, rec: dict, root: Path = ROOT) -> set[str]:
    """Names defined in the model file itself (def and type), as opposed to Base."""
    p = Path(rec["artifacts"]["model"])
    p = p if p.is_absolute() else Path(root) / p
    return set(records.model_defs(p.read_text()))


# ---------------------------------------------------------------- derive, compare, write
def statement_hash(law: dict, m: str, root: Path) -> str:
    """The registry's hash of a law (holon.ir.statement_hash under its hash scheme): 0.1/0.2 over the IR; 0.3 with its
    refs (holon.gen.refs), the oracle sidecar of an M2+ milestone included, as `holon run` and G2 compute it."""
    def refs(law):
        from .gen import refs as R
        from .gen.oracles import Oracles
        from .mpipeline import m2plus
        fp = Path(root) / law_facts(law, m, root)
        return R.refs(law, F.load(fp), Oracles.for_facts(fp) if m2plus(m) else None, None, root)
    return ir.statement_hash(law, refs)


def bind_law(law: dict, m: str, root: Path, cfg: dict | None = None) -> dict:
    """One law's binding on the tree (derive's entry for it)."""
    root = Path(root)
    mp = model_path(law, m, root)
    if _slash(law):   # I70: no statement over the linked layer yet, so the binding is its statement hash alone
        return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                "statement_sha256": None, "counter_sha256": None, "cone": {}}
    if _gox(law):   # I93: the emitted law and counter-law (each None where the decider writes no such form); the
        # module's definitions bind through the statement hash, whose gox: ref hashes the basis they are generated from
        st, ct = _emit(law, m, root, counter=False), _emit(law, m, root, counter=True)
        return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                "statement_sha256": text_sha256(st) if st is not None else None,
                "counter_sha256": text_sha256(ct) if ct is not None else None, "cone": {}}
    if _symb(law):   # I92: the member's model and section as one module; U. roots are the section's (the versioned
        # and link modules' own names, V. and K., bind through the statement hash: their inputs are in its basis)
        st = _emit(law, m, root, counter=False)
        if st is None:
            return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                    "statement_sha256": None, "counter_sha256": None, "cone": {}}
        cfg = cfg or bend.config(root)
        entries = dict(_entries_cached(_symb_kernel_text(law, m, root), json.dumps(cfg, sort_keys=True) if cfg else "",
                                       mp.relative_to(root).as_posix()))
        c = kernel_cone(_U_QUAL.sub("M.", st), entries)
        return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                "statement_sha256": text_sha256(st), "counter_sha256": counter_binding(law, m, root),
                "cone": {d: hashlib.sha256(entries[d].encode()).hexdigest() for d in c}}
    if _bundle_law(law):   # I86: the law model and the claims module as one module; C. roots are the claims module's
        st = _emit(law, m, root, counter=False)
        if st is None:   # CS3's outflow class: no claim over the M3 model, so the binding is its statement hash alone
            return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                    "statement_sha256": None, "counter_sha256": None, "cone": {}}
        cfg = cfg or bend.config(root)
        entries = dict(_entries_cached(_bundle_law_kernel_text(law, m, root),
                                       json.dumps(cfg, sort_keys=True) if cfg else "", mp.relative_to(root).as_posix()))
        c = kernel_cone(_C_QUAL.sub("M.", st), entries)
        return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
                "statement_sha256": text_sha256(st), "counter_sha256": counter_binding(law, m, root),
                "cone": {d: hashlib.sha256(entries[d].encode()).hexdigest() for d in c}}
    if _bundle(law):   # I84: the typed model at the laws' deployment and the claims module as one module
        cfg = cfg or bend.config(root)
        entries = dict(_entries_cached(_bundle_kernel_text(law, m, root),
                                       json.dumps(cfg, sort_keys=True) if cfg else "", mp.relative_to(root).as_posix()))
        c = kernel_cone(_F_QUAL.sub("M.", statement_text(law, m, root)), entries)
    elif _undo(law) or _fact(law) or _sym(law):   # I27, I26, I34: the typed model and the section as one module; U./F.
        # roots are its own (a SYM law file imports its sym section as U, as an UNDO law file its trace section)
        cfg = cfg or bend.config(root)
        entries = dict(_entries_cached(_undo_kernel_text(law, m, root), json.dumps(cfg, sort_keys=True) if cfg else "",
                                       mp.relative_to(root).as_posix()))
        c = kernel_cone((_F_QUAL if _fact(law) else _U_QUAL).sub("M.", statement_text(law, m, root)), entries)
    elif _pinit(law):   # I28: the layer translated with the version modules it imports
        entries = layer_entries(mp, cfg or bend.config(root))
        c = kernel_cone(statement_text(law, m, root), entries)
    elif _nat(law):   # I29: the layer and the claims module as one module (N. roots are the claims module's)
        entries = nat_layer_entries(law, m, root, cfg or bend.config(root))
        c = kernel_cone(_N_QUAL.sub("M.", statement_text(law, m, root)), entries)
    else:
        entries = kernel_entries(mp, cfg or bend.config(root))
        c = kernel_cone(statement_text(law, m, root), entries)
    return {"statement_hash": statement_hash(law, m, root), "model": mp.relative_to(root).as_posix(),
            "statement_sha256": text_sha256(_emit(law, m, root, counter=False)),
            "counter_sha256": counter_binding(law, m, root),
            "cone": {d: hashlib.sha256(entries[d].encode()).hexdigest() for d in c}}


def derive(m: str, root: Path | str = ROOT, cfg: dict | None = None) -> dict:
    root = Path(root)
    cfg = cfg or bend.config(root)
    out = {}
    for law in ir.load_laws_any(m, root):
        out[law["law_id"]] = bind_law(law, m, root, cfg)
    return {"milestone": m, "kernel": "bendtt", "laws": out}


def dependents(bound: dict) -> dict:
    """bound: {"milestone", "laws": {law: {"model": name, "cone": [defs]}}}."""
    flat: dict[str, set] = {}
    by_model: dict[str, dict[str, set]] = {}
    for lid, x in sorted(bound["laws"].items()):
        for d in x["cone"]:
            flat.setdefault(d, set()).add(lid)
            by_model.setdefault(x["model"], {}).setdefault(d, set()).add(lid)
    return {"milestone": bound["milestone"],
            "dependents": {d: sorted(ls) for d, ls in sorted(flat.items())},
            "dependents_by_model": {mdl: {d: sorted(ls) for d, ls in sorted(ds.items())}
                                    for mdl, ds in sorted(by_model.items())}}


def diff(old: dict, new: dict) -> tuple[list[str], list[str], list[str]]:
    """(changed laws, changed definitions, problems as text)."""
    laws, defs, msgs = set(), set(), []
    a, b = old.get("laws", {}), new.get("laws", {})
    for lid in sorted(set(a) | set(b)):
        if lid not in a or lid not in b:
            laws.add(lid)
            msgs.append(f"{lid}: {'not bound' if lid not in a else 'bound but no longer a law'}")
            continue
        x, y = a[lid], b[lid]
        for key, what in (("statement_hash", "statement hash"), ("statement_sha256", "emitted statement"),
                          ("counter_sha256", "emitted counter-law"), ("model", "model file")):
            if x.get(key) != y.get(key):
                laws.add(lid)
                msgs.append(f"{lid}: {what} differs from its binding")
        changed = sorted(d for d in set(x["cone"]) & set(y["cone"]) if x["cone"][d] != y["cone"][d])
        gone = sorted(set(x["cone"]) - set(y["cone"]))
        new = sorted(set(y["cone"]) - set(x["cone"]))
        for ds, what in ((changed, "meaning changed in"), (gone, "no longer reaches"), (new, "now also reaches")):
            if ds:
                laws.add(lid)
                defs.update(ds)
                msgs.append(f"{lid}: {what} {', '.join(ds[:8])}{' ...' if len(ds) > 8 else ''}")
    return sorted(laws), sorted(defs), msgs


def path(m: str, root: Path) -> Path:
    return Path(root) / BINDINGS_DIR / f"{m}.json"


def dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def main_bind(args) -> int:
    root = Path(getattr(args, "root", None) or ROOT).resolve()
    m = args.milestone
    new = derive(m, root)
    p = path(m, root)
    log = root / CHANGES
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dump(new))
        with log.open("a") as fh:
            fh.write(json.dumps({"milestone": m, "created": True, "laws": sorted(new["laws"]),
                                 "reason": getattr(args, "accept_change", None) or "initial binding"},
                                sort_keys=True) + "\n")
        print(f"wrote {p.relative_to(root)}: {len(new['laws'])} laws bound (logged in {CHANGES})")
        return 0
    old = json.loads(p.read_text())
    if getattr(args, "remodel", None):   # I68: the remodel entries first, each checked by holon.statement_diff.append
        from .statement_diff import append as sd_append, remodel_entries
        es, notes = remodel_entries(m, root, args.remodel)
        for n in notes:
            print(f"no remodel entry: {n}", file=sys.stderr)
        rejected = []
        for e in es:
            r = sd_append(e, root)
            print(f"{e['law_id']}: remodel {'appended' if r['ok'] else 'REJECTED'}: {r['reason']}")
            if not r["ok"]:
                rejected.append(e["law_id"])
        if rejected or notes:
            print(f"refusing to rebind: {len(rejected)} remodel entries rejected, {len(notes)} laws need another kind",
                  file=sys.stderr)
            return 1
    only = [x.strip() for x in (getattr(args, "laws", None) or "").split(",") if x.strip()]
    if only:   # rebind only these laws: every other law keeps its current binding, or stays unbound
        unknown = sorted(set(only) - set(new["laws"]))
        if unknown:
            print(f"--laws names laws that are not laws of {m}: {unknown}", file=sys.stderr)
            return 1
        keep = {lid: x for lid, x in old.get("laws", {}).items() if lid not in only}
        new = {**new, "laws": dict(sorted({**keep, **{lid: new["laws"][lid] for lid in only}}.items()))}
    laws, defs, msgs = diff(old, new)
    if not laws:
        print(f"{p.relative_to(root)}: bindings unchanged")
        return 0
    for line in msgs:
        print(line)
    a, b = old.get("laws", {}), new["laws"]
    added, removed = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    changed = sorted(lid for lid in laws if lid in a and lid in b)
    law_defs = {lid: changed_defs(a[lid], b[lid]) for lid in changed}
    covered, missing = covering_entries(m, root, a, b, changed, law_defs)
    reason = getattr(args, "accept_change", None)
    if missing:
        for lid, why in missing:
            print(f"{lid}: {why}", file=sys.stderr)
        print(f"refusing to rebind {len(missing)} of {len(changed)} changed laws: each needs an accepted "
              "laws/STATEMENT_DIFF.jsonl entry for exactly that law (a binding_change naming every changed definition, "
              "or a statement change); --accept-change alone no longer suffices (I10, audit F-M2-09)", file=sys.stderr)
        return 1
    if changed and not reason:
        print(f"refusing to rebind {len(changed)} laws: give --accept-change \"<reason>\" (logged in {CHANGES}, with the "
              "covering STATEMENT_DIFF lines)", file=sys.stderr)
        return 1
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        fh.write(json.dumps({"milestone": m, "laws": changed, "defs": defs, "law_defs": law_defs, "added": added,
                             "removed": removed, "covered_by": covered,
                             "reason": reason or "laws added to or removed from laws/" + m}, sort_keys=True) + "\n")
    p.write_text(dump(new))
    print(f"rebound {len(changed)} laws, added {len(added)}, removed {len(removed)} in {p.relative_to(root)}; logged in "
          f"{CHANGES}")
    return 0


def changed_defs(x: dict, y: dict) -> list[str]:
    """The definitions whose kernel form changed, or that entered or left the cone, between two bindings of a law."""
    cx, cy = x.get("cone", {}), y.get("cone", {})
    return sorted(d for d in set(cx) | set(cy) if cx.get(d) != cy.get(d))


def _accepted_entries(root: Path, m: str | None = None) -> dict[int, dict]:
    """Accepted lines of laws/STATEMENT_DIFF.jsonl; with m, as milestone m's G2 scans them (F38: another milestone's
    binding_change proofs are re-checked by that milestone's G2, not again here)."""
    from .statement_diff import LOG, scan
    s = scan(Path(root) / LOG, root, milestone=m)
    return {x["line"]: x["entry"] for x in s["entries"] if x.get("ok")}


def entry_covers(e: dict, lid: str, law: dict | None, stmt_changed: bool, defs: list[str],
                 hash_only: bool = True, hashes: tuple | None = None) -> bool:
    """Does an accepted STATEMENT_DIFF entry cover rebinding law lid? law: its current IR, which the entry's new
    statement must be (None: not compared, for a logged line whose law may have changed again since). defs: the
    definitions whose kernel form changed or that entered or left the cone. hash_only: nothing in the binding changed
    but the statement hash (F30: a catalog_rederivation changes no claim, so it covers a rebinding only when no
    definition, emitted statement, counter-law or model changed; anything more needs its own entry). F33: a
    binding_change whose statement hash moved with an accepted catalog_rederivation (its "statement_hash" bridge, which
    its own acceptance verified) covers a rebinding that changes the hash and the cone together; hashes: (bound,
    current) statement hashes, which must then be the bridge's (None: not compared). PV2A: a hash_migration (the law
    moved to hash scheme 2) covers a rebinding exactly as a catalog_rederivation does. I68: an accepted remodel covers
    a rebinding that changes the cone alone (its check compared the two bindings, _remodel (a))."""
    from .statement_diff import core
    if not isinstance(e, dict) or (e.get("law_id") or (e.get("new") or {}).get("law_id")) != lid:
        return False
    if not isinstance(e.get("new"), dict) or (law is not None and core(e["new"]) != core(law)):
        return False
    if stmt_changed:
        if e.get("kind") in ("catalog_rederivation", "hash_migration"):   # F30; PV2A: a scheme move changes no claim
            return hash_only and not defs
        br = e.get("statement_hash")
        if e.get("kind") == "binding_change" and isinstance(br, dict):
            return (isinstance(e.get("old"), dict) and core(e["old"]) == core(e["new"]) and bool(defs)
                    and set(defs) <= set(e.get("defs") or [])
                    and (hashes is None or (br.get("old"), br.get("new")) == tuple(hashes)))
        return e.get("kind") in ("strengthening", "weakening", "reextraction")
    if e.get("kind") == "remodel":   # I68: its check accepted a change of the cone alone (holon.statement_diff._remodel)
        return isinstance(e.get("old"), dict) and core(e["old"]) == core(e["new"]) and bool(defs)
    # a fixed statement: a binding_change, or (I83) a model_extension, naming every changed definition
    return (e.get("kind") in ("binding_change", "model_extension") and isinstance(e.get("old"), dict)
            and core(e["old"]) == core(e["new"]) and set(defs) <= set(e.get("defs") or []))


def hash_only_change(x: dict, y: dict) -> bool:
    """Do two bindings of a law differ in nothing but the statement hash?"""
    return {k: v for k, v in x.items() if k != "statement_hash"} == {k: v for k, v in y.items() if k != "statement_hash"}


def covering_entries(m: str, root: Path, a: dict, b: dict, changed: list, law_defs: dict):
    """({law: STATEMENT_DIFF line id, or line number for a line without one}, [(law, why)]) for the changed laws. With none (laws only added or removed) there is
    nothing to cover, so the accepted entries' proofs are not re-checked (I67: that re-check takes most of an hour)."""
    if not changed:
        return {}, []
    entries = _accepted_entries(root, m)
    current = {l["law_id"]: l for l in ir.load_laws_any(m, root)}
    covered, missing = {}, []
    for lid in changed:
        sc = a[lid].get("statement_hash") != b[lid].get("statement_hash")
        ho = hash_only_change(a[lid], b[lid])
        hs = (a[lid].get("statement_hash"), b[lid].get("statement_hash"))
        n = next((n for n, e in sorted(entries.items())
                  if entry_covers(e, lid, current.get(lid), sc, law_defs[lid], ho, hs)), None)
        if n is not None:
            if isinstance(entries[n].get("id"), str):
                n = entries[n]["id"]   # PV2A: a line with an id is named by it, not by its line number
            covered[lid] = n
        else:
            missing.append((lid, "no accepted laws/STATEMENT_DIFF.jsonl entry covers it ("
                                 + ("its statement hash changed: a strengthening, weakening or reextraction, or a "
                                    "catalog_rederivation when nothing else in its binding changed" if sc else
                                    f"its statement is fixed: a binding_change or a model_extension naming "
                                    f"{law_defs[lid]}, or a licensed remodel") + ")"))
    return covered, missing


def _json_line(b: bytes):
    try:
        return json.loads(b) if b.strip() else None
    except ValueError:
        return None


def resolve_covered(n, commit, log_at, where: dict, by_id: dict | None = None) -> tuple[list[int], str | None]:
    """(I83; the coordinator's decision, revocable) The lines of the current laws/STATEMENT_DIFF.jsonl that a change line's
    covered_by number n names. For a change line appended by `commit`, n is a line of the log as it was at that commit:
    its exact text there (log_at(commit): that version's lines, or None when it cannot be read: a problem, never a fall
    back to the position), found by that text in the current file (where: {line text: [current line numbers]}). A lead
    merge appends other lines before a branch's own, so only the content is a stable address. For a change line not yet
    committed (commit None), n is a current line number, as before. PV2A: n may instead be a line id ("sha256:..",
    holon.statement_diff.line_id), which names the current lines carrying it (by_id), whichever commit appended either
    line. Returns (current line numbers, problem or None)."""
    if isinstance(n, str) and n.startswith("sha256:"):
        hits = list((by_id or {}).get(n, []))
        return (hits, None) if hits else ([], f"laws/STATEMENT_DIFF.jsonl has no line with id {n}")
    if not isinstance(n, int) or isinstance(n, bool):
        return [], "its covered_by entry is not a line number"
    if commit is None:
        return [n], None
    old = log_at(commit)
    if old is None:
        return [], (f"laws/STATEMENT_DIFF.jsonl cannot be read at {commit[:12]}, the commit that appended the change line "
                    "(a shallow clone?)")
    if not 0 < n <= len(old):
        return [], f"laws/STATEMENT_DIFF.jsonl has no line {n} at {commit[:12]}, the commit that appended the change line"
    return list(where.get(old[n - 1], [])), None


def change_line_problems(ln: dict, i: int, commit, entries: dict, log_at, where: dict,
                         by_id: dict | None = None) -> list[str]:
    """What keeps change line i (ln; appended by `commit`, None while not committed) from naming, for each law it
    rebinds, an accepted laws/STATEMENT_DIFF.jsonl entry that covers it (entries: {current line number: accepted
    entry}; resolve_covered maps its covered_by numbers to current lines)."""
    probs = []
    cov = ln.get("covered_by") if isinstance(ln.get("covered_by"), dict) else {}
    defs = ln.get("law_defs") if isinstance(ln.get("law_defs"), dict) else {}
    for lid in ln.get("laws") or []:
        ld = defs.get(lid, ln.get("defs") or [])   # a catalog_rederivation covers a line only when it logs no def
        cands, why = resolve_covered(cov.get(lid), commit, log_at, where, by_id)
        ok = why is None and any(e is not None and (entry_covers(e, lid, None, True, ld) or
                                                    entry_covers(e, lid, None, False, ld))
                                 for e in (entries.get(k) for k in cands))
        if not ok:
            probs.append(f"{CHANGES}: post-I10 line {i} rebinds {lid} without an accepted laws/STATEMENT_DIFF.jsonl entry "
                         "covering it" + (f": {why}" if why else ""))
    return probs


def check_change_log(m: str, root: Path) -> tuple[list[str], str]:
    """G2 (audit F-M2-09): every change line of spec/bindings/changes.jsonl for milestone m logged after
    laws/STATEMENT_DIFF.jsonl was introduced maps each changed law to an accepted entry that covers it; the log
    extends its version at that commit and every committed version (append-only). Lines before the I10 commit
    are grandfathered. A committed change line's covered_by numbers are read at the commit that appended it (I83:
    resolve_covered). Returns (problems, note); off git the check cannot run, and the note says so."""
    from .statement_diff import LOG, _line_origins, blob_at, cutoff_commit, in_git, line_id, merged_lines
    root = Path(root)
    if not in_git(root):
        return [], "binding change log not checked: no git history (a copied tree)"
    cut = cutoff_commit(root)
    if cut is None:
        return [], "binding change log not checked: laws/STATEMENT_DIFF.jsonl is not committed (no I10 boundary)"
    p = root / CHANGES
    data = p.read_bytes() if p.exists() else b""
    base = blob_at(root, cut, CHANGES.as_posix()) or b""
    problems = []
    spans, side, mprobs = merged_lines(data, p, root)
    if not data.startswith(base) or mprobs:   # append-only, merges included
        problems.append(f"{CHANGES} does not extend its committed versions (append-only)")
        return problems, ""
    entries = _accepted_entries(root, m)
    where: dict = {}
    by_id: dict = {}   # PV2A: a line id -> the current lines that carry it (a covered_by entry may name a line by its id)
    for k, x in enumerate((root / LOG).read_bytes().splitlines() if (root / LOG).exists() else [], start=1):
        where.setdefault(x, []).append(k)
        e = _json_line(x)
        if isinstance(e, dict) and isinstance(e.get("id"), str) and e["id"] == line_id(e):
            by_id.setdefault(e["id"], []).append(k)
    logs: dict = {}

    def log_at(commit: str):
        if commit not in logs:
            b = blob_at(root, commit, LOG.as_posix())
            logs[commit] = None if b is None else b.splitlines()
        return logs[commit]

    committed_len = spans[-1][0] if spans else 0
    origins = None
    n_lines, offset = 0, len(base)
    for i, rawb in enumerate(data[len(base):].splitlines(keepends=True), start=1):
        start, offset = offset, offset + len(rawb)
        raw = rawb.decode("utf-8", errors="replace")
        if not raw.strip():
            continue
        try:
            ln = json.loads(raw)
        except ValueError:
            problems.append(f"{CHANGES}: post-I10 line {i} is not JSON")
            continue
        if not isinstance(ln, dict) or ln.get("milestone") != m or ln.get("created"):
            continue
        n_lines += 1
        # the commit that appended it: along HEAD's first-parent chain, or the oldest side version holding it (a line a
        # merge brought in); None only for a line beyond every committed version (not yet committed)
        commit = next((c for end, c in spans if start < end), None) if start < committed_len else side.get(rawb)
        # a line a merge on HEAD's first-parent chain brought in from another line of history was appended by the oldest
        # commit whose version holds it, and its covered_by numbers are lines of the log at THAT commit: a lead-first
        # merge numbers the log differently at the merge commit (as statement_diff does for model_extension lines)
        if commit is not None:
            origins = origins if origins is not None else _line_origins(p, root)
            commit = origins.get(rawb, commit)
        problems += change_line_problems(ln, i, commit, entries, log_at, where, by_id)
    return problems, f"{n_lines} post-I10 binding change lines of {m}, each covered by an accepted statement-diff entry"
