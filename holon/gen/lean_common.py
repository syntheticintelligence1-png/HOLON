"""The shared vocabulary of the I43 Lean emitters (holon.gen.lean_machine, lean_mlaws, lean_mproofs, lean_sites,
lean_linked) and of holon.lean, which dispatches to them.

An emitter returns Lean text as data: a Model (the declarations of `namespace Model`) and, per law, a LawFile (the
model, then the marker line, then the law's theorems). LawFile.text() is the file holon lean writes; a law file's
model section is its model file's text verbatim, which is rule L4's model consistency by construction.

Generic: nothing here names a target, a law or a document; it imports only the standard library, so the emitters'
import closure stays off the Bend side (rule L1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

MARKER = "-- holon:theorems"
KINDS = ("machine", "machine_oracle", "linked")
# a lean4 kernel entry's not_run reasons (rule L8) and the ones a REFUTED attempted law may keep (resource limits)
ALLOWED_REASONS = ("timeout", "recursion_depth", "heartbeats", "unsupported_form", "no_report", "toolchain_unavailable")
REFUTED_REASONS = ("timeout", "recursion_depth", "heartbeats")
# every lean4 entry's reading of its model kind (gap LP-G1), exactly as the I43 contract states it
READINGS = {
    "machine": (
        "Lean reads the holon-facts/0.2 document itself (holon.gen.lean_machine), the target library through its "
        "Lean twin (hand-written target input, like the Bend library: common mode, I9 Question 4); Nat, Bool and "
        "lists as in Bend; premises are hypotheses as in Bend; the statement is the frozen Lean text of the same IR"),
    "machine_oracle": (
        "as machine, and: the Fn<List<Nat>,Nat> oracle parameter is a Lean function (List Nat -> Nat) where Bend "
        "ranges over finite tables (first matching entry, else 0), each of which is such a function, so the Lean "
        "theorem implies the Bend one; Reach is the same inductive set; the site predicate is Lean's own reading of "
        "rules R8-R10 (holon.gen.lean_sites) over the site's raw obligation ro_<x>; on every PROVED site the site "
        "predicate is constantly true (coercion_guard never uses Reach), so rule L7 pins where a site is hit "
        "(hit_<x>) and the raw obligation (ro_<x>), each taking both values on the samples, and rule L4 requires "
        "site_<x> to reach ro_<x>"),
    "linked": (
        "Lean cells are Option (BitVec 8): a record's byte is a BitVec 8 where Bend's is a U32, so Lean's theorems "
        "cover byte-valued records only (a narrower domain than Bend's, I9 Surprise 5); an undefined cell (Bend "
        "57005) is none, and the decoders' orderings compare it as 57005; every premise is a hypothesis where Bend "
        "pins a field to a constant or to another record's field (an equivalent statement)"),
}
# the options every emitted file starts with (rule L4 allows only these three); they also govern the differential
# theorems the tests append to a model file
PREAMBLE = ("set_option autoImplicit false", "set_option maxRecDepth 20000", "set_option maxHeartbeats 2000000")
# the Lean proof classes: the Bend class of the verdict re-checked, and counter_decide for a REFUTED law's counter-law
PROVED_CLASSES = ("evaluate", "nat_split", "noninterference", "deadline", "chain_revert", "coercion_guard", "open_refl")
COUNTER_CLASS = "counter_decide"

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Unsupported(Exception):
    """A form an emitter cannot express (an IR form, a facts construct, a proof class): the law is not run, with
    reason unsupported_form and this message as its detail. Never a silent fallback."""


@dataclass(frozen=True)
class Theorem:
    """One top-level theorem after the marker line.

    statement: "theorem <name> : <prop>", for a law's frozen theorem exactly its rule-L3 text, with no ":=";
    proof: the text after ":= " (a term, or a tactic block "by\\n  ..." indented by two);
    before: helper declarations (theorem, def or noncomputable def, each starting in column 0) emitted before it;
    option: a "set_option maxHeartbeats <n> in" or "set_option maxRecDepth <n> in" line emitted just before it."""
    name: str
    statement: str
    proof: str
    before: tuple[str, ...] = ()
    option: str | None = None

    def text(self) -> str:
        parts = [b.rstrip("\n") for b in self.before]
        head = f"{self.option}\n" if self.option else ""
        parts.append(f"{head}{self.statement} := {self.proof.rstrip()}")
        return "\n\n".join(parts)


@dataclass(frozen=True)
class Model:
    """The Lean model of one Bend model: models/<stem>.lean, and the model section of every law file over it.
    decls: the top-level declarations inside `namespace Model`, in order, each a full text."""
    stem: str
    decls: tuple[str, ...]
    preamble: tuple[str, ...] = PREAMBLE

    def text(self) -> str:
        body = "\n\n".join(d.rstrip("\n") for d in self.decls)
        return "\n".join(list(self.preamble) + ["", "namespace Model", "", body, "", "end Model", ""])


@dataclass(frozen=True)
class LawFile:
    """<lean dir>/<law id>.lean: the model, the marker line, the theorems. main: the theorem carrying the verdict
    (the law id, or <law id>_counter); generator: the Lean class that wrote the proofs."""
    law_id: str
    model: Model
    theorems: tuple[Theorem, ...]
    main: str
    generator: str

    def text(self) -> str:
        return self.model.text() + "\n" + MARKER + "\n\n" + "\n\n".join(t.text() for t in self.theorems) + "\n"

    def replace_statement(self, name: str, statement: str) -> "LawFile":
        """The same file with theorem `name`'s statement replaced, its proof kept (G7's canaries)."""
        if sum(1 for t in self.theorems if t.name == name) != 1:
            raise ValueError(f"theorem {name} is not declared exactly once")
        return replace(self, theorems=tuple(replace(t, statement=statement) if t.name == name else t
                                            for t in self.theorems))

    def without(self, name: str) -> "LawFile":
        """The same file without theorem `name` (G7's flip canary drops the refutation built on the counter-law)."""
        return replace(self, theorems=tuple(t for t in self.theorems if t.name != name))


def ident(prefix: str, name: str) -> str:
    """A Lean identifier for a name taken from a document: its fixed prefix and the name, which must be plain."""
    if not isinstance(name, str) or not _IDENT.fullmatch(name):
        raise Unsupported(f"{name!r} is not a plain identifier")
    return prefix + name


def model_kind(facts_doc: dict, law: dict) -> str:
    """Rule L1: linked (a holon-linked codec document), machine (a holon-facts/0.2 document under holon-ir/0.2),
    machine_oracle (the same under holon-ir/0.3), or other (no Lean emitter covers it)."""
    if facts_doc.get("linked_version"):
        return "linked"
    if facts_doc.get("facts_version") == "holon-facts/0.2":
        if law.get("ir_version") == "holon-ir/0.2":
            return "machine"
        if law.get("ir_version") == "holon-ir/0.3":
            return "machine_oracle"
    return "other"


def bend_class(record: dict) -> str | None:
    """The Bend class of a record's verdict: the generator of its successful proof attempt (PROVED) or counter-law
    attempt (REFUTED); None when there is none."""
    want = {"PROVED": "proof", "REFUTED": "counter-law"}.get(record.get("status"))
    for a in record.get("attempts") or []:
        if want and a.get("kind") == want and a.get("exit_code") == 0:
            return a.get("generator")
    return None


def lean_class(record: dict) -> str:
    """The Lean class that re-checks a record's verdict: its Bend proof class for a PROVED law, counter_decide for a
    REFUTED one."""
    c = bend_class(record)
    if record.get("status") == "PROVED" and c in PROVED_CLASSES:
        return c
    if record.get("status") == "REFUTED" and c == "counter":
        return COUNTER_CLASS
    raise Unsupported(f"no Lean class re-checks a {record.get('status')} verdict of Bend class {c!r}")
