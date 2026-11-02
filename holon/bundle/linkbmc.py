"""holon bundle bmc (I86; the contract is the docstring of tests_m3/test_bundle_laws.py, rules Q1-Q5): Q28's BMC
over the linked queue.

  python -m holon bundle bmc [--milestone M3] [--root DIR] [--check]

I40's engine (holon.bmc) runs unchanged, with I40's budget (the refute sidecar's bmc.H and solver.rlimit_per_query)
and I40's answer model for every external call the link does not answer. The link enters through the engine's own
answer model, so the engine's code and every result it gave before stay as they are:

  Q1 The targets: every check of the adopted member's actions whose expression calls (call or callok) a linked
     function of the clock kind: a link row of the declaration from the adopted member into another member's action,
     whose answer in I40's answer model is an environment term (the empty queue's answer). The callee member of those
     rows is the linked member. A target's kind: callok (the call's success), fits (an overflow panic), guard (a guard
     reach) or checks (an implicit check).
  Q2 The encoding. The linked member's storage families join the state as the engine's ghost arrays (a scalar at key
     0, a mapping at its key, a dynamic array's elements at their index and its length as "<family>.length" at key 0),
     at R0 the deployment record's slots of the member decoded by its document's layout. Every link row from the
     adopted member into the linked member is answered by the callee action's program, compiled into an answer: its
     checks are the answer's success, its return term the answer's value, its writes the answer's ghost writes, every
     term over the callee's storage, parameters and environment rewritten to the ghosts, the call's arguments and the
     calling context (the caller is the adopted member, the call carries no value, its calldata is the ABI encoding of
     its arguments, an immutable is the deployment's value). A term the rewriting cannot carry (memory built by the
     callee's loops) is a fresh value, an over-approximation noted in every query that uses it. The moves: every action
     of the linked member that another member's link rows call and that writes a family a linked function reads,
     added to the adopted document as an action of its own (one step: the compiled answer, its caller the calling
     member's deployment address). R0 of the adopted member is the deployment record's slots of it, decoded by I40's
     decoder with the byte strings I40's capture hashed, each used only where its hash is a slot (or, for a longer
     string, a word) of the record.
  Q3 Verdicts as I40's search gives them (path, no_path, unknown), each with its bound (H, the rlimit, the largest k
     decided). A path whose clock I40's label calls unrealistic is solved again at the same k with every step's
     block.timestamp at most 2^64; a model of that query is the path recorded and replayed (the verdict and k stay
     the search's). A path counts once replayed on the real bundle (the bundle harness, a fresh deployment): a move as
     the calling member's sender action with the fewest parameters, by the sidecar's replay actor, its address
     parameter the sidecar's target, its bytes parameter the sidecar's data, its last unsigned parameter the sidecar's
     gas limit (any other 0), with the value its fee needs (the price call of the sender action's payer site in the
     bundle-laws basis, read on the real bundle at the deployment for the replay actor; no value without a payer
     site; a fee the path's state raises makes the move revert, which fails the replay); every other step as a call
     of the adopted member by the path's caller with the path's arguments and value, time moving by warps to the
     path's timestamps. The replay passes when every step but the last succeeds, every move writes the linked
     member's storage, and the last step reverts with the target check's revert data; a path whose replay fails is
     unknown, with the replay's account.
  Q4 results/<M>/bundle_laws/bmc.json: {"bmc_version", "settings", "targets": {id: {"kind", "verdict", "k", "path",
     "reason", "replay", "bound"}}}; --check re-runs everything and compares. A target whose search did not finish
     has no verdict: "not_run", with why (I40's crash guard fired or the solver crashed, which is never a verdict; or
     the document was written with --cached-only before a run finished it). --check searches every target, so a
     not-run target reproduces only while the check's own search of it does not finish either.
  Q5 No law and no I40 output changes.

holon.bundle.linkbmc_out replays the paths and writes the document (Q3's replay, Q4); this module is the search
(Q1, Q2, Q3's verdicts). Its results may be cached under the digest of its code and inputs (cache_digest), a run's and
a check's apart, so an interrupted run or check resumes; --cached-only writes the document from a run's cache alone.
Exit codes as holon bundle's. Nothing here names a target.
"""
from __future__ import annotations

from pathlib import Path

from . import BundleError, Ctx, Refused

BMC_VERSION = "holon-bundle-bmc/0.1"
LOOP_SYMS = ("iter", "carried", "exit", "count", "returned")
MEMORY_HEADS = ("mem", "mload", "slice")


def _int(x) -> int:
    if isinstance(x, int):
        return x
    s = str(x)
    return int(s, 16) if s.startswith("0x") else int(s)


def _calls(t, out: set) -> None:
    if isinstance(t, list):
        if t and t[0] in ("call", "callok") and len(t) > 1 and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _calls(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _calls(x, out)


def _storage(t, out: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            _storage(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _storage(x, out)


# ------------------------------------------------------------------------------------------------ the link
class Link:
    """The declaration's link rows read for Q1-Q2: the adopted member, the linked member, its functions and moves."""

    def __init__(self, ctx: Ctx, env: dict):
        self.ctx = ctx
        decl = ctx.load(ctx.out("declaration"))
        self.adopted = next(m["name"] for m in ctx.members() if m.get("adopted"))
        answers = env.get("answers") or {}
        rows = [r for r in decl["links"] if r[0] == self.adopted and r[5] == "action"]
        clock = sorted({r[3] for r in rows if isinstance((answers.get(r[3]) or {}).get("ret"), list)
                        and (answers[r[3]]["ret"][:1] == ["env"])})
        if not clock:
            raise Refused("no link row of the adopted member reaches a function whose answer is an environment term")
        callees = sorted({r[4] for r in rows if r[3] in clock})
        if len(callees) != 1:
            raise Refused(f"the clock functions {clock} are answered by {len(callees)} members")
        self.clock, self.callee = clock, callees[0]
        self.fns = {}
        for r in rows:
            if r[4] == self.callee:
                if self.fns.get(r[3], r[6]) != r[6]:
                    raise Refused(f"{r[3]} is linked to two actions of {self.callee}")
                self.fns[r[3]] = r[6]
        self.doc = ctx.load(ctx.document_rel(ctx.member(self.callee)))
        self.actions = {a["name"]: a for a in self.doc["actions"]}
        reads = set()
        for a in sorted(set(self.fns.values())):
            _storage(self.actions[a], reads)
        moves = {}
        for r in decl["links"]:
            if r[0] != self.adopted and r[4] == self.callee and r[5] == "action":
                a = self.actions[r[6]]
                if {w["family"] for w in a.get("writes") or []} & reads:
                    moves.setdefault((r[6], r[0]), []).append(r[1])
        if not moves:
            raise Refused(f"no other member's link row calls an action of {self.callee} that writes what it answers")
        self.moves = {k: sorted(set(v)) for k, v in sorted(moves.items())}


# ------------------------------------------------------------------------------------------------ the callee's state
class Ghosts:
    """The linked member's storage families as ghost arrays: names, R0 values from the deployment record."""

    def __init__(self, ns: str, doc: dict):
        self.ns = ns
        self.fams = {}
        for s in list(doc.get("inherited_storage") or []) + list(doc.get("storage") or []):
            if s.get("kind") == "array" and s.get("length") is not None:
                continue                      # a fixed-size array (a gap): no term names it
            self.fams.setdefault(s["name"], s)

    def name(self, fam: str, member: str | None = None) -> str:
        return f"{self.ns}.{fam}" + (f".{member}" if member else "")

    def length(self, fam: str) -> str:
        return f"{self.ns}.{fam}.length"

    def all_names(self) -> list:
        out = []
        for n, f in sorted(self.fams.items()):
            if f.get("kind") == "array":
                out += [self.name(n), self.length(n)]
            elif f.get("kind") == "mapping" and f.get("fields"):
                out += [self.name(n, fl["name"]) for fl in f["fields"]]
            elif f.get("kind") == "scalar" and f.get("fields"):
                continue                      # a struct scalar (a library's storage struct): no linked term reads it
            else:
                out.append(self.name(n))
        return out

    def r0(self, storage: dict) -> tuple[dict, list]:
        """({ghost: {key: value}}, the slots of the record no family decodes)."""
        from ..keccak import keccak256
        st = {_int(k): _int(v) for k, v in storage.items()}
        used, out = set(), {g: {} for g in self.all_names()}
        for n, f in sorted(self.fams.items()):
            slot = int(f["slot"])
            if f.get("kind") == "scalar" and not f.get("fields"):
                w = st.get(slot, 0)
                v = (w >> (8 * int(f.get("offset") or 0))) & ((1 << int(f.get("width") or 256)) - 1)
                if v:
                    out[self.name(n)][0] = v
                if slot in st:
                    used.add(slot)
            elif f.get("kind") == "array":
                ln = st.get(slot, 0)
                if slot in st:
                    used.add(slot)
                if ln:
                    out[self.length(n)][0] = ln
                base = int.from_bytes(keccak256(slot.to_bytes(32, "big")), "big")
                for i in range(ln):
                    w = st.get(base + i, 0)
                    if w:
                        out[self.name(n)][i] = w
                    if base + i in st:
                        used.add(base + i)
        return out, sorted("0x%064x" % s for s in st if s not in used)


# ------------------------------------------------------------------------------------------------ the callee's answers
class Compile:
    """A callee action's program as an answer of I40's answer model ({"ok", "ret", "ghost", "prose"}), in the calling
    context: actor (the caller term), this (the callee's address), immutables (the callee's deployment values)."""

    def __init__(self, ghosts: Ghosts, action: dict, actor, this: int, immutables: dict, value=0):
        self.g, self.a, self.actor, self.this = ghosts, action, actor, this
        self.imm = {k: _int(v) for k, v in (immutables or {}).items()}
        self.value = value
        self.params = [p["name"] for p in action.get("params") or []]
        self.notes: list = []

    def unknown(self, why: str):
        self.notes.append(why)
        return ["unknown", f"{self.a['name']}: {why}"]

    def calldata_length(self):
        """The ABI encoding's length of the call's arguments: 4 + 32 per head word, and per dynamic byte string its
        length word and its words."""
        n = 4 + 32 * len(self.params)
        terms = [n]
        for i, p in enumerate(self.a.get("params") or []):
            if str(p.get("type") or "") in ("bytes", "string"):
                terms.append(["+", 32, ["*", 32, ["/", ["+", ["len", ["arg", i]], 31], 32]]])
        out = terms[0]
        for t in terms[1:]:
            out = ["+", out, t]
        return out

    def term(self, t):
        g = self.g
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return t
        h = t[0]
        if h in LOOP_SYMS:
            raise _Carry(f"a loop symbol ({h})")
        if h in MEMORY_HEADS:
            raise _Carry(f"memory the callee builds ({h})")
        if h == "storage":
            f = g.fams.get(t[1])
            if f is None:
                raise _Carry(f"storage {t[1]} outside the callee's families")
            if f.get("kind") == "scalar" and not f.get("fields"):
                return ["ghost", g.name(t[1]), 0]
            raise _Carry(f"storage {t[1]} read as a whole")
        if h == "map" and isinstance(t[1], list) and t[1][:1] == ["storage"]:
            f = g.fams.get(t[1][1])
            if f is None or f.get("kind") != "mapping" or f.get("fields"):
                raise _Carry(f"a map access into {t[1][1]}")
            return ["ghost", g.name(t[1][1]), self.term(t[2])]
        if h == "member" and isinstance(t[1], list) and t[1][:1] == ["map"] and isinstance(t[1][1], list) \
                and t[1][1][:1] == ["storage"]:
            f = g.fams.get(t[1][1][1])
            if f is None or not f.get("fields") or t[2] not in {fl["name"] for fl in f["fields"]}:
                raise _Carry(f"a member access into {t[1][1][1]}")
            return ["ghost", g.name(t[1][1][1], t[2]), self.term(t[1][2])]
        if h == "len" and isinstance(t[1], list) and t[1][:1] == ["storage"]:
            f = g.fams.get(t[1][1])
            if f is None or f.get("kind") != "array":
                raise _Carry(f"the length of {t[1][1]}")
            return ["ghost", g.length(t[1][1]), 0]
        if h == "index" and isinstance(t[1], list) and t[1][:1] == ["storage"]:
            f = g.fams.get(t[1][1])
            if f is None or f.get("kind") != "array":
                raise _Carry(f"an index into {t[1][1]}")
            return ["ghost", g.name(t[1][1]), self.term(t[2])]
        if h == "param":
            if t[1] not in self.params:
                raise _Carry(f"parameter {t[1]}")
            return ["arg", self.params.index(t[1])]
        if h == "caller":
            return self.actor
        if h == "this":
            return self.this
        if h == "env" and t[1] == "msg.value":
            return self.value
        if h == "env" and t[1] == "msg.data.length":
            return self.calldata_length()
        if h == "immutable":
            if t[1] not in self.imm:
                raise _Carry(f"immutable {t[1]} without a deployment value")
            return self.imm[t[1]]
        if h in ("call", "callok", "ghost", "arg", "receiver"):
            raise _Carry(f"a nested {h}")
        return [h] + [self.term(x) for x in t[1:]]

    def safe(self, t, why: str):
        try:
            return self.term(t)
        except _Carry as e:
            return self.unknown(f"{why}: {e}")

    def answer(self, prog) -> dict:
        from ..machine import Check, Loop, Write
        oks, ghost = [], []
        for x in prog.steps:
            if isinstance(x, Check):
                oks.append(self.safe(x.expr, f"check {x.id}"))
            elif isinstance(x, Loop):
                # a loop of the callee that only builds memory (its values reach the answer through a written or
                # returned term, which then is fresh); one that checks or writes cannot be carried
                inner = [y for y in _walk(x.body) if isinstance(y, (Check, Write))]
                if inner:
                    raise BundleError(f"{self.a['name']}: a loop holds checks or writes; the link cannot compile it")
            elif isinstance(x, Write):
                ghost += self.write(x)
        ok = 1
        for c in oks:
            ok = c if ok == 1 else ["&&", ok, c]
        ret = self.a.get("returns")
        out = {"ok": ok, "ret": self.safe(ret, "the return value") if ret is not None else None,
               "prose": f"the linked {self.g.ns} document's {self.a['name']} (compiled by holon.bundle.linkbmc)"}
        if ghost:
            out["ghost"] = ghost
        return out

    def write(self, w) -> list:
        """A write record as ghost writes (key and value over the pre-state)."""
        f = self.g.fams.get(w.family)
        if f is None:
            raise BundleError(f"{self.a['name']}: a write of {w.family}, not a family of the callee")
        cond = self.safe(w.cond, f"the condition of the write of {w.family}") if w.cond != 1 else 1

        def guarded(name, key, val):
            return {"name": name, "key": key,
                    "value": val if cond == 1 else ["?", cond, val, ["ghost", name, key]]}
        if f.get("kind") == "array" and not w.path and isinstance(w.value, list) and w.value[:1] == ["push"]:
            ln = ["ghost", self.g.length(w.family), 0]
            v = self.safe(w.value[2], f"the element pushed to {w.family}")
            return [guarded(self.g.name(w.family), ln, v), guarded(self.g.length(w.family), 0, ["+", ln, 1])]
        if f.get("kind") == "scalar" and not f.get("fields") and not w.path:
            return [guarded(self.g.name(w.family), 0, self.safe(w.value, f"the value written to {w.family}"))]
        if f.get("kind") == "mapping" and not f.get("fields") and len(w.path) == 1 and w.path[0][0] == "map":
            k = self.safe(w.path[0][1], f"the key written in {w.family}")
            return [guarded(self.g.name(w.family), k, self.safe(w.value, f"the value written to {w.family}"))]
        raise BundleError(f"{self.a['name']}: a write of {w.family} at {w.path}, which the link cannot compile")


class _Carry(Exception):
    pass


def _walk(steps):
    from ..machine import Loop
    for x in steps:
        yield x
        if isinstance(x, Loop):
            yield from _walk(x.body)


def _eip1967_slots() -> set:
    """The proxy's own slots (EIP-1967 implementation and admin): no family of the implementation holds them."""
    from ..keccak import keccak256
    return {int.from_bytes(keccak256(s.encode()), "big") - 1
            for s in ("eip1967.proxy.implementation", "eip1967.proxy.admin")}


# ------------------------------------------------------------------------------------------------ the problem
class Setup:
    """Everything Q1-Q3 read: I40's sidecar and answer model, the declaration's link, the deployment record."""

    def __init__(self, ctx: Ctx):
        from ..machine import document_programs
        self.ctx = ctx
        m = ctx.milestone
        self.refute_rel, self.env_rel = f"spec/{m}/lib/refute.json", f"spec/{m}/refute_env.json"
        self.laws_side_rel = f"spec/{m}/lib/bundle_laws.json"
        self.side = ctx.load(self.refute_rel)
        self.env = ctx.load(self.env_rel)
        self.q28 = ctx.load(self.laws_side_rel)["q28"]
        self.link = Link(ctx, self.env)
        self.dep = ctx.load(ctx.out("deployment"))
        members = self.dep["members"]
        self.adopted_rel = ctx.document_rel(ctx.member(self.link.adopted))
        self.adoc = ctx.load(self.adopted_rel)
        self.ghosts = Ghosts(self.link.callee, self.link.doc)
        callee = members[self.link.callee]
        self.callee_addr = _int(callee["address"])
        progs = document_programs(self.link.doc)
        self.answers = {k: v for k, v in (self.env.get("answers") or {}).items() if k not in self.link.fns}
        self.notes = {}
        for fn, act in sorted(self.link.fns.items()):
            c = Compile(self.ghosts, self.link.actions[act], ["this"], self.callee_addr, callee.get("immutables"))
            self.answers[fn] = c.answer(progs[act])
            self.notes[fn] = sorted(set(c.notes))
        self.moves = {}
        extra = []
        for (act, caller), senders in sorted(self.link.moves.items()):
            name = f"{self.link.callee}.{act}"
            c = Compile(self.ghosts, self.link.actions[act], _int(members[caller]["address"]), self.callee_addr,
                        callee.get("immutables"))
            self.answers[name] = c.answer(progs[act])
            self.notes[name] = sorted(set(c.notes))
            self.moves[name] = {"action": act, "member": caller, "senders": senders}
            extra.append(move_action(name, self.link.actions[act]))
        self.doc = dict(self.adoc, actions=list(self.adoc["actions"]) + extra)
        r0g, unknown = self.ghosts.r0(callee["storage"])
        proxy = _eip1967_slots()
        rest = [s for s in unknown if _int(s) not in proxy]
        if rest:
            raise Refused(f"the deployment record's slots {rest[:4]} of {self.link.callee} decode to no family")
        self.r0_ghosts = r0g

    def principals(self) -> list:
        actors = self.ctx.side["deployment"]["actors"]
        harness = self.dep["named"]["harness"]
        return [(k, _int(harness if v == "harness" else v)) for k, v in sorted(actors.items())]

    def problem(self):
        from .. import bmc as BMC
        from ..keccak import keccak256
        from ..refute_m3 import r0_families
        rol = self.dep["members"][self.link.adopted]
        st = {_int(k): _int(v) for k, v in rol["storage"].items()}
        cap = self.ctx.load(self.side["deployment"]["capture"])
        pre64, longer = [], []
        for x in cap.get("preimages") or []:
            b = bytes.fromhex(x[2:])
            h = int.from_bytes(keccak256(b), "big")
            if len(b) == 64 and h in st:
                pre64.append(x)
            elif len(b) > 64 and h in set(st.values()):
                longer.append(b)
        r0, info = r0_families(self.doc, {"storage": rol["storage"], "preimages": pre64})
        self.r0_info = {"preimages": len(pre64), "hashed_strings": len(longer), "unknown_slots": info["unknown_slots"]}
        m = BMC.Machine(self.doc, int(self.side["smt"]["byte_length_max"]))
        p = BMC.Problem(m, r0, self.principals(), int(self.side["deployment"]["deployed_at"]),
                        int(self.side["bmc"]["H"]), int(self.side["solver"]["rlimit_per_query"]),
                        int(self.side["blob_count_max"]), answers=self.answers,
                        immutables={k: _int(v) for k, v in (rol.get("immutables") or {}).items()},
                        this=_int(rol["address"]), ghosts=self.r0_ghosts)
        p.gas_limit = int(self.side.get("gas_limit") or 30000000)
        p.preimages = longer
        p.raw_slots = {_int(x): st[_int(x)] for x in info["unknown_slots"]}
        return p

    def input_refs(self) -> list:
        ctx = self.ctx
        return [ctx.ref(r) for r in sorted({self.refute_rel, self.env_rel, self.laws_side_rel, ctx.out("declaration"),
                                            ctx.out("deployment"), self.adopted_rel,
                                            ctx.document_rel(ctx.member(self.link.callee)),
                                            self.side["deployment"]["capture"]})]

    def targets(self) -> list:
        """Q1: the adopted member's checks whose expression calls a clock function, with their kinds."""
        from ..machine import document_programs
        out = []
        for a, prog in sorted(document_programs(self.adoc).items()):
            for c in prog.checks():
                fns = set()
                _calls(c.expr, fns)
                if not fns & set(self.link.clock):
                    continue
                head = c.expr[0] if isinstance(c.expr, list) and c.expr else None
                kind = "callok" if head == "callok" else ("fits" if head == "fits" else
                                                           ("guard" if c.section == "guards" else c.section))
                out.append({"id": c.id, "kind": kind, "action": a})
        return sorted(out, key=lambda r: r["id"])


def move_action(name: str, act: dict) -> dict:
    """A move as an action of the adopted document: one step, the call of the move's compiled answer."""
    params = list(act.get("params") or [])
    args = [["param", p["name"]] for p in params]
    return {"name": name, "params": params, "selector": act.get("selector"), "mutability": "nonpayable",
            "payable": False, "src": name, "declared_in": name, "modifiers": [], "principal": None, "returns": None,
            "guards": [], "panics": [], "checks": [], "writes": [], "mstores": [], "events": [], "loops": [],
            "calls": [{"args": args, "commit": False, "cond": 1, "expr": ["callok", name, None] + args, "fn": name,
                       "mutability": "nonpayable", "receiver": None, "seq": 0, "src": name, "stack": [],
                       "value": 0}]}


# ------------------------------------------------------------------------------------------------ Q3: the search
CACHE_ENV = "HOLON_BUNDLE_BMC_CACHE"
CODE = ("holon/bmc.py", "holon/bundle/linkbmc.py", "holon/machine.py", "holon/refute_m3.py", "holon/keccak.py",
        "holon/extracted_eval.py")


def cache_digest(s: Setup) -> str:
    """The digest a search result is cached under: the engine's code, the link's code and every input file. A cached
    result is the search's own output for these bytes (the search is deterministic: a fixed seed and the rlimit)."""
    import hashlib
    root = s.ctx.root
    rels = sorted(set(CODE) | {p.relative_to(root).as_posix() for p in (root / "holon" / "smt").glob("*.py")}
                  | {r["path"] for r in s.input_refs()})
    h = hashlib.sha256()
    for rel in rels:
        h.update(rel.encode() + b"\0" + (root / rel).read_bytes() + b"\0")
    return h.hexdigest()


def not_run(t: dict, why: str) -> dict:
    """A target without a verdict: its search did not finish (Q3 has no verdict for it)."""
    return {"verdict": "not_run", "length": None, "path": None, "largest_k": None, "queries": [], "approx": [],
            "reason": why, "kind": t["kind"], "action": t["action"]}


def search_all(s: Setup, log=print, cache: str | None = None, *, check: bool = False, cached_only: bool = False,
               jobs: int = 1) -> dict:
    """Each target's search with I40's engine (iterative deepening k = 1..H, the cone's levels): {id: result}.

    cache: a directory (the environment's HOLON_BUNDLE_BMC_CACHE) where each finished search is kept under the digest
    of the code and the inputs, so an interrupted run resumes. A run and a check keep separate entries (a check's are
    named check-<digest>): a check reads only its own recomputations, never a run's, so an interrupted check resumes
    too. cached_only: no search; a target without an entry is not run.

    Each target's search builds its own Problem, so jobs > 1 searches targets side by side with the same results. A
    search that the solver's crash guard aborts (I40's watchdog), or whose solver crashes, gives no verdict: the target
    is not run and nothing is cached (I40's rule: a crash is never a verdict)."""
    import json
    import os
    from concurrent.futures import ThreadPoolExecutor
    from .. import bmc as BMC
    from ..smt.run import SolverCrash, WatchdogAbort
    dig = cache_digest(s) if cache else None
    pre = ("check-" if check else "") + (dig[:16] if dig else "")

    def one(t):
        cf = Path(cache) / f"{pre}-{t['id'].replace('/', '_').replace('#', '_').replace(':', '_')}.json" \
            if cache else None
        if cf is not None and cf.is_file():
            r = json.loads(cf.read_text(encoding="utf-8"))
            log(f"{t['id']} ({t['kind']}): cached, {r['verdict']}")
            return t["id"], r
        if cached_only:
            log(f"{t['id']} ({t['kind']}): not run (no cached result)")
            return t["id"], not_run(t, "not run: this document was written from the cache alone, and no run had "
                                       "finished this target's search")
        log(f"{t['id']} ({t['kind']})")
        p = s.problem()
        tgt = {"kind": "check", "action": t["action"], "check": t["id"]}
        try:
            r = BMC.search(p, tgt, s.side["solver"], qdir=None,
                           name=t["id"].replace("#", "_").replace("/", "_").replace(":", "_"), log=log)
            out = dict(r, kind=t["kind"], action=t["action"])
            if r["verdict"] == "path":
                rr = realistic(p, tgt, r, s.side["solver"], log)
                if rr is not None:
                    out["realistic"] = list(rr)
        except (WatchdogAbort, SolverCrash) as x:
            log(f"{t['id']}: not run ({x})")
            return t["id"], not_run(t, f"not run: {x} (a crash is never a verdict; nothing was cached)")
        if cf is not None:
            cf.parent.mkdir(parents=True, exist_ok=True)
            tmp = cf.with_name(cf.name + f".{os.getpid()}.part")
            tmp.write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
            os.replace(tmp, cf)
        return t["id"], out
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        return dict(ex.map(one, s.targets()))


def realistic(p, target: dict, r: dict, solver: dict, log=print):
    """A path whose clock I40's label calls unrealistic, solved again at the same k (the whole cone) with every step's
    block.timestamp at most the realistic bound: (path or None, why); None when the clock needs no re-solve. The
    search's verdict and k stay; only the path recorded and replayed is the re-solve's."""
    from ..refute_m3 import CLOCK_REALISTIC, clock
    ck = clock(r.get("path"))
    if not ck or not ck.get("label"):
        return None
    return _resolve(p, target, solver, r["length"], CLOCK_REALISTIC, log)


def _resolve(p, target: dict, solver: dict, k: int, bound: int, log=print):
    from .. import bmc as BMC
    from ..smt.encode import lit
    from ..smt.run import Session, registered_limits
    e1_max = int(registered_limits()["e1_rounds_max"])
    u = BMC.Unrolled(p, target, k, None)
    if u.trivial:
        return None, "the goal is constant"
    for st in u.steps:
        u.q.add(f"(bvule {st['env']['block.timestamp']} {lit(bound)})")
    sess = Session(solver, rlimit=p.rlimit)
    try:
        res = sess.check(u.q.text())
        u.sent_defs = len(u.q.defs)
        rounds = 0
        while res == "sat" and rounds < e1_max:
            viol = u.violations(sess)
            if not viol:
                break
            rounds += 1
            nd, na = u.sent_defs, len(u.q.asserts)
            for a, b in viol:
                u.q.pending.remove((a, b))
                u.q.assert_pair(a, b)
            res = sess.more("".join(f"(define-fun {n} () {srt} {e})\n" for n, srt, e in u.q.defs[nd:]) +
                            "".join(f"(assert {x})\n" for x in u.q.asserts[na:]))
            u.sent_defs = len(u.q.defs)
        if log:
            log(f"  realistic clock re-solve at k = {k}: {res} (E1 rounds {rounds})")
        if res == "sat" and rounds < e1_max:
            return u.decode(sess), f"re-solved at k = {k} with every block.timestamp <= {bound}"
        return None, f"no re-solve at k = {k} with every block.timestamp <= {bound}: {res}"
    finally:
        sess.close()
