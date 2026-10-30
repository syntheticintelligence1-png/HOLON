"""holon bundle2 model (rules M1-M2 of the contract): each modelled member's document compiled by holon.sorts.model3's
untyped machine, extended additively for what a member adds:

  struct values   a whole storage struct read (a struct-typed storage path read as a value, e.g. a struct copied to
                  memory) is a record value SR_<struct>{member...} of its elementary members, read at the compiler's
                  slots and offsets; a member of it is the record's field; ["update", base, ["member", base, m], v] is
                  the record with field m replaced; a struct write takes its fields
  dynamic arrays  an index into a storage dynamic array is the element at keccak256(slot) + i * the element's slots (the
                  keccak256 through the model's hash table, as a mapping's slot is); its length is the word at its slot;
                  a write whose value is ["push", array, v] writes v at element n (n the length in the state the
                  action's earlier writes left) and n + 1 at the slot; ["pop", array] zeroes element n - 1 and writes
                  n - 1 (elements of 16 bytes or fewer, which the compiler packs several per slot, are a GenError)

The subclass lives here, outside every generator closure: model3's text for a document without these constructs is
unchanged (the adopted document's models regenerate byte for byte). The model text is assembled as model3's untyped
build_text assembles it, over the actions the generator compiled; an action it cannot compile is debt with its
GenError, never left out of models.json.
"""
from __future__ import annotations

import json


from . import Ctx, Refused, Writer, file_sha, render
from .members import doc_rel, load_member

MODELS_VERSION = "holon-bundle2-models/0.1"


def _model3():
    from ..sorts import model3 as M3
    return M3


def make_class():
    M3 = _model3()
    GenError, StoragePath, wlit, bname = M3.GenError, M3.StoragePath, M3.wlit, M3.bname

    class BModel3(M3.Model3):
        # ---------------------------------------------------------- struct values
        def struct_record(self, tid: str, sc) -> tuple[str, list]:
            t = self.m.type_of(tid)
            rec = "SR_" + bname(str(t.get("label", "struct")).split(".")[-1].replace("struct ", ""))
            fields = []
            for mm in t.get("members") or []:
                mt = self.m.type_of(mm["type"])
                if mt.get("encoding") != "inplace" or "members" in mt or "base" in mt:
                    raise GenError(f"{sc.action}: a struct value with a non-elementary member {mm['label']}")
                fields.append(mm)
            if rec not in self.records:
                self.records[rec] = [(bname(mm["label"]), "W", {"name": mm["label"], "type": "uint256"})
                                     for mm in fields]
            return rec, fields

        def read_path(self, p, sc):
            slot, off, tid, _lit = self.locate(p, sc)
            t = self.m.type_of(tid)
            if t.get("encoding") == "inplace" and "members" in t and p.accessors:
                rec, fields = self.struct_record(tid, sc)
                vals = []
                for mm in fields:
                    ms = slot if not int(mm["slot"]) else f"w_add({slot}, {wlit(int(mm['slot']))})"
                    vals.append(self.read_word(p.view, ms, int(mm["offset"]), mm["type"]))
                return f"{rec}{{{', '.join(vals)}}}", "r:" + rec
            return super().read_path(p, sc)

        def compile_action(self, a: str) -> None:
            """model3's compile_action, with a default value for the extension's struct records: an action whose
            context holds a struct value (a loop that carries one, such as a search's current element) initializes
            that field to the record of its members' defaults. model3's own _default (a module function) knows
            only model3's types, so it is extended for the duration of this call and restored after it: model3's
            text for any document without struct records is unchanged."""
            orig = M3._default
            recs = self.records

            def default_ext(ty: str) -> str:
                if ty.startswith("SR_") and ty in recs:
                    return f"{ty}{{{', '.join(default_ext(fty) for _f, fty, _p in recs[ty])}}}"
                return orig(ty)
            M3._default = default_ext
            try:
                return super().compile_action(a)
            finally:
                M3._default = orig

        def t_update(self, t, sc):
            c, k = self.value(t[1], sc)
            tgt = t[2]
            if not k.startswith("r:") or not (isinstance(tgt, list) and len(tgt) == 3 and tgt[0] == "member"):
                raise GenError(f"{sc.action}: an update of a {k} value")
            rec = k[2:]
            fs = self.records.get(rec) or []
            name = bname(tgt[2])
            if name not in [f for f, _ty, _p in fs]:
                raise GenError(f"{sc.action}: no member {tgt[2]} in {rec}")
            v = self.w(t[3], sc)
            vals = [v if f == name else f"g_{rec}_{f}({c})" for f, _ty, _p in fs]
            return f"{rec}{{{', '.join(vals)}}}", k

        def struct_value(self, t, sc, lines: list) -> dict:
            if isinstance(t, list) and t and t[0] not in ("struct",):
                c, k = self.tx(t, sc)
                if k == "p":
                    slot, _off, tid, _l = self.locate(c, sc)
                    if "members" in self.m.type_of(tid):
                        return super().struct_value(t, sc, lines)
                    c, k = self.read_path(c, sc)
                if k.startswith("r:"):
                    rec = k[2:]
                    tid_members = {bname(f): f for f, _ty, _p in self.records.get(rec) or []}
                    out = {}
                    for f, _ty, p in self.records.get(rec) or []:
                        out[p["name"]] = f"g_{rec}_{f}({c})"
                    if len(out) != len(tid_members):
                        raise GenError(f"{sc.action}: a struct value of {rec}")
                    return out
            return super().struct_value(t, sc, lines)

        # ---------------------------------------------------------- dynamic arrays
        def locate(self, p, sc):
            idx = next((i for i, (kind, _x, _xk) in enumerate(p.accessors) if kind == "index"), None)
            if idx is None:
                return super().locate(p, sc)
            head = StoragePath(p.view, p.family, p.accessors[:idx], p.var)
            slot, off, tid, _lit = self.locate(head, sc)
            t = self.m.type_of(tid)
            if t.get("encoding") != "dynamic_array":
                return super().locate(p, sc)
            bt = self.m.type_of(t["base"])
            size = int(bt["numberOfBytes"])
            if size <= 16:
                raise GenError(f"{sc.action}: {p.family}: an index into a packed {t.get('label')}")
            _kind, x, xk = p.accessors[idx]
            base = f"h_get({self.gx(sc, 'kh')}, b_of_w({slot}))"
            per = (size + 31) // 32
            iv = self.to_w(x, xk)
            code = f"w_add({base}, {iv if per == 1 else f'w_mul({iv}, {wlit(per)})'})"
            tid = t["base"]
            rest = p.accessors[idx + 1:]
            for kind, xx, _xxk in rest:
                tt = self.m.type_of(tid)
                if kind == "member":
                    mm = next((y for y in tt.get("members") or [] if y["label"] == xx), None)
                    if mm is None:
                        raise GenError(f"{sc.action}: {p.family}: no member {xx} in {tt.get('label')}")
                    if int(mm["slot"]):
                        code = f"w_add({code}, {wlit(int(mm['slot']))})"
                    off, tid = int(mm["offset"]), mm["type"]
                else:
                    raise GenError(f"{sc.action}: {p.family}: a {kind} below an array element")
            if not rest:
                off = 0
            return code, off, tid, False

        def t_len(self, t, sc):
            c, k = self.tx(t[1], sc)
            if k == "p":
                slot, _off, tid, _l = self.locate(c, sc)
                if self.m.type_of(tid).get("encoding") == "dynamic_array":
                    return f"sload({c.view}, {slot})", "w"
                c, k = self.read_path(c, sc)
            return super().t_len(["len", t[1]], sc) if k != "p" else (c, k)

        def write_body(self, w, sc):
            v = w.value
            if not (isinstance(v, list) and v and v[0] in ("push", "pop")):
                return super().write_body(w, sc)
            fam = w.family
            self.m.family(fam)
            p = StoragePath("o0", fam, [], fam)
            for acc in w.path:
                kind, key = acc[0], acc[1]
                if kind == "member":
                    p = p.extend("member", key, "name", f"{p.var}.{key}")
                else:
                    kc, kk = self.value(key, sc)
                    p = p.extend(kind, kc, kk, p.var)
            slot, _off, tid, _lit = self.locate(p, sc)
            t = self.m.type_of(tid)
            if t.get("encoding") != "dynamic_array":
                raise GenError(f"{sc.action}: a {v[0]} on a {t.get('label')}")
            bt = self.m.type_of(t["base"])
            size = int(bt["numberOfBytes"])
            if size <= 16:
                raise GenError(f"{sc.action}: a {v[0]} on a packed {t.get('label')}")
            per = (size + 31) // 32
            lines = [f"  +o0 = {self.gx(sc, 'ov')}", f"  +k = {{{slot} : W}}", "  +n = {sload(o0, k) : W}"]
            if v[0] == "push":
                lines.append(f"  +e = {{w_add(h_get({self.gx(sc, 'kh')}, b_of_w(k)), "
                             f"{'n' if per == 1 else f'w_mul(n, {wlit(per)})'}) : W}}")
            else:
                lines.append(f"  +e = {{w_add(h_get({self.gx(sc, 'kh')}, b_of_w(k)), "
                             f"{'w_sub(n, w_u(1))' if per == 1 else f'w_mul(w_sub(n, w_u(1)), {wlit(per)})'}) : W}}")
            if "members" in bt:
                vals = self.struct_value(v[2], sc, lines) if v[0] == "push" else {}
                members = [(mm["label"], int(mm["slot"]), int(mm["offset"]), mm["type"]) for mm in bt["members"]]
            else:
                if v[0] == "push":
                    vc, vk = self.value(v[2], sc)
                    vals = {"_": self.to_w(vc, vk)}
                else:
                    vals = {}
                members = [("_", 0, 0, t["base"])]
            cur, n, slots = "o0", 0, []
            for label, ms_, mo, mt in members:
                mtt = self.m.type_of(mt)
                if mtt.get("encoding") != "inplace" or "members" in mtt or "base" in mtt:
                    raise GenError(f"{sc.action}: a {v[0]} of an element with a non-elementary member {label}")
                ms = "e" if not ms_ else f"w_add(e, {wlit(ms_)})"
                n += 1
                lines.append(f"  +o{n} = {{{self.write_word(cur, ms, mo, mt, vals.get(label, 'w0()'))} : HSt}}")
                cur = f"o{n}"
                if ms not in slots:
                    slots.append(ms)
            n += 1
            newlen = "w_add(n, w_u(1))" if v[0] == "push" else "w_sub(n, w_u(1))"
            lines.append(f"  +o{n} = {{sstore({cur}, k, {newlen}) : HSt}}")
            cur = f"o{n}"
            slots.append("k")
            tw = self.gx(sc, "tw")
            for s_ in reversed(slots):
                tw = f"Con{{{s_}, {tw}}}"
            lines.append(f"  {self.sx(sc, 'tw', self.sx(sc, 'ov', 'x', cur), tw)}")
            return lines

    return BModel3


def build_text(m, init: dict, hashes: list, header: list) -> tuple[str, object, list]:
    """model3's untyped build_text over the actions the extended generator compiles; (text, generator, debt)."""
    M3 = _model3()
    from ..machine_bend import bname
    cls = make_class()
    mm = cls(m, typed=False, sorts={}, seeds={}, init_storage=init, hashes=hashes)
    acts, debt = [], []
    for a in sorted(a for a in m.actions if m.params(a) is not None):
        try:
            mm.compile_action(a)
            acts.append(a)
        except M3.GenError as e:
            debt.append({"action": a, "error": str(e)[:600]})
    hs = ", ".join(f"+{'kh' if h == 'keccak256' else 'sh'}: List<&2, HKB>" for h in hashes)
    hv = ", ".join("kh" if h == "keccak256" else "sh" for h in hashes)
    parts = ["\n".join(header) + "\nimport Base\n", M3.PRELUDE, M3._COMMON]
    parts += mm.shift_defs()
    parts += M3._env_record(mm)
    parts += M3._arg_records(mm, acts)
    for a in acts:
        parts += mm.action_defs[a]
    parts.append("# an action with its arguments and its environment (A-env: free per step)\ntype HAct is Data:\n"
                 + "".join(f"  A_{bname(a)}{{ar: AR_{bname(a)}, en: HEnv}}\n" for a in acts))
    parts.append(f"def step(a: HAct, +s: HSt{', ' + hs if hs else ''}) -> HSt:\n  match a:\n"
                 + "".join(f"    case A_{bname(a)}{{ar, en}}:\n      step_{bname(a)}(s, ar, en{', ' + hv if hv else ''})\n"
                           for a in acts))
    parts.append("# the initial state: the target's storage after the deployment of the binding (zero without one)\n"
                 + M3.s0_text(init))
    idx = ", ".join(f"-{v}: List<&2, HKB>" for v in hv.split(", ")) if hv else ""
    ix = (hv + ", ") if hv else ""
    parts.append(f"def run(tr: List<&2, HAct>, s: HSt{', ' + hs if hs else ''}) -> HSt:\n  match tr:\n"
                 f"    case Nil{{}}:\n      s\n    case Con{{a, rest}}:\n"
                 f"      run(rest, step(a, s{', ' + hv if hv else ''}){', ' + hv if hv else ''})\n")
    parts.append(f"# the reachable states: the deployment (R0) and one step of any action (RStep)\n"
                 f"type Reach<{idx + ', ' if idx else ''}-s: HSt> is Type:\n  R0{{e: {{s == s0() : HSt}}}}\n"
                 f"  RStep{{a: HAct, p: HSt, r: Reach<{ix}p>, e: {{s == step(a, p{', ' + hv if hv else ''}) : HSt}}}}\n")
    text = "\n".join(p.rstrip("\n") + "\n" for p in parts if p)
    return M3.affine(M3.fold_bytes(text)), mm, debt


def run(ctx: Ctx, check: bool) -> int:
    from ..rules.sort import hash_functions
    dep_p = ctx.path("deployment")
    if not dep_p.is_file():
        raise Refused(f"{ctx.rel(dep_p)} is missing (run holon bundle2 deploy)")
    dep = json.loads(dep_p.read_text())
    w = Writer(check)
    models, debt = {}, []
    out = ctx.path("models")
    for m in ctx.members():
        if m.get("adopted"):
            continue
        rel = doc_rel(ctx, m)
        model = load_member(ctx, m)
        storage = {int(k, 16): int(v, 16) for k, v in (dep["members"][m["name"]]["storage"]).items()}
        hashes = hash_functions(model.doc) or ["keccak256"]
        header = [f"# GENERATED by holon bundle2 model (holon.sorts.model3's untyped machine, holon.bundle2.modelx's "
                  f"extension) from {rel}; do not edit (fix the generator instead).",
                  f"# facts_sha256: {file_sha(ctx.root / rel)}",
                  f"# model_version: {_model3().MODEL3_VERSION} (untyped: the sort section off), bundle2 extension",
                  f"# initial state: the deployment of {ctx.rel(dep_p)} ({len([v for v in storage.values() if v])} "
                  "non-zero slots)",
                  "# chk_<action>(st, ar, en, kh..): 0 when every check holds, k + 1 when check k is the first that fails;",
                  "# post_<action>, logs_<action>: its post-state and logs; step_<action>: the post-state when chk is 0, "
                  "else st."]
        text, _mm, d = build_text(model, storage, hashes, header)
        mp = out / f"{m['name']}.bend"
        w.put(mp, text.encode("utf-8"))
        init = {"binding": ctx.rel(dep_p), "storage": {"0x%064x" % k: "0x%064x" % v for k, v in sorted(storage.items())},
                "preimages": []}
        w.put(out / f"{m['name']}.init.json", render(init))
        models[m["name"]] = {"path": ctx.rel(mp), "sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
                             "document_sha256": file_sha(ctx.root / rel)}
        debt += [dict(x, member=m["name"]) for x in d]
        print(f"holon bundle2 model: {m['name']}: {len(model.actions) - len(d)} actions compiled, {len(d)} debt")
    w.put(out / "models.json", render({"models_version": MODELS_VERSION, "models": models,
                                       "debt": sorted(debt, key=lambda x: (x["member"], x["action"]))}))
    return w.finish("model")



