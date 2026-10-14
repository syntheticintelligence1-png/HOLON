// Deterministic refutation search for holon-ir/0.2 laws on a compiled Bend state-machine model.
// Untrusted: it only proposes witnesses; a law becomes REFUTED only when Bend accepts the counter-law.
//
// stdin: {"module": path, "facts": {...}, "law": {...IR...}, "budget": {...}}
// stdout: {"witness": {binder: value} | null, "tried": n, "bound": "...", "notes": [..]}
//
// Values: Trace = [{"op": name, input: value..}], Act = {"op":..}, Nat = int, Bool, State = {"run": Trace},
// Fn<Nat,Nat> = {"lam": "id" | "zero" | "succ"} (holon-ir/0.3: a small fixed family, enumerated in this order).
//
// Oracle parameters (I12; req.oracles, from holon.mpipeline.CompiledMachine.oracle_req): a Fn binder named like a
// modelled parameter p ranges over oracle tables. Its candidates are the sidecar's concrete instances of p, in
// sidecar order (computed by the instance module req.oracles.instModule: the model plus one inst_<entry> def per
// instance), then the empty table; a witness value is {"instance": entry id} or {"table": [[k, v], ..]}. An
// instance is materialised as the table of its values at the points the statement queries: the evaluation runs on
// an instrumented copy of the compiled model whose lookups ap_p log their argument (values unchanged), and is
// repeated with the instance's values at every logged point until no new point appears. The output then also
// holds `tables`: {p: [[k, v], ..]}, the table each parameter's witness denotes. Reachable prefixes of a model
// that threads tables are explored with the empty tables (a heuristic: a state binder is re-run from its trace
// under the candidate tables when the statement is evaluated).
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
let M = (await import(pathToFileURL(req.module).href)).default;
const ORC = req.oracles || null;
const PARAMS = ORC ? ORC.params : {};
const PROBE = [];
if (ORC && Object.keys(PARAMS).length) {
  let src = readFileSync(req.module, "utf8");
  let ok = true;
  for (const p of Object.keys(PARAMS)) {
    const head = `function $ap_${p}$(`;
    if (src.split(head).length !== 2) { ok = false; break; }
    // an override (globalThis.__HOLON_OVR[p], set by the SORT-site search, I15) answers every lookup of p with a
    // concrete instance, whatever table the model threads; without one the table answers (I12)
    src = src.replace(head, `function $ap_${p}$__holon(`)
      + `\nfunction $ap_${p}$(t, x) { globalThis.__HOLON_PROBE.push(["${p}", x]); `
      + `const o = globalThis.__HOLON_OVR && globalThis.__HOLON_OVR["${p}"]; `
      + `return o ? o(x) : $ap_${p}$__holon(t, x); }\n`;
  }
  globalThis.__HOLON_PROBE = PROBE;
  if (ok) M = (await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"))).default;
}
const INST = ORC && ORC.instModule ? (await import(pathToFileURL(ORC.instModule).href)).default : null;
const facts = req.facts;
const law = req.law;
const B = Object.assign({ prefixDepth: 3, suffixDepth: 4, natMax: 5, maxNodes: 400000, maxPrefixes: 3000 }, req.facts.search || {}, req.budget || {});
const ACTIONS = Object.fromEntries(facts.actions.map((a) => [a.name, a]));
const notes = [];
let tried = 0;

// ---------------------------------------------------------------- values
const toList = (xs) => xs.reduceRight((t, h) => ({ $: "Con", head: h, tail: t }), { $: "Nil" });
function enc(v) {
  if (typeof v === "number") return BigInt(v);
  if (typeof v === "boolean") return v;
  if (Array.isArray(v)) return toList(v.map(enc));
  if (v && typeof v === "object" && "$" in v) { const o = { $: v.$ }; for (const [k, x] of Object.entries(v)) if (k !== "$") o[k] = enc(x); return o; }
  throw new Error("enc " + JSON.stringify(v));
}
function dec(x) {
  if (typeof x === "bigint") return Number(x);
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (x && (x.$ === "Nil" || x.$ === "Con")) { const o = []; for (let c = x; c.$ === "Con"; c = c.tail) o.push(dec(c.head)); return o; }
  if (x && typeof x === "object") { const o = {}; for (const [k, y] of Object.entries(x)) o[k] = k === "$" ? y : dec(y); return o; }
  throw new Error("dec " + String(x));
}
function mkAct(a) {
  const spec = ACTIONS[a.op];
  const o = { $: "A_" + a.op };
  for (const [n] of spec.inputs) o[n] = enc(a[n]);
  return o;
}
// equality by canonical form: object keys sorted, so a value's key order (model field order, or the sorted
// order of a witness read back from JSON) never decides an equation
const canon = (v) => (Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v);
const key = (v) => JSON.stringify(canon(v), (_, x) => (typeof x === "bigint" ? `${x}n` : x));
const s0 = M.s0();
// a model that threads oracle tables is stepped with the empty tables while prefixes are explored (I12)
const DEFAULT_TABS = (ORC ? ORC.threaded : []).map(() => ({ $: "Nil" }));
const stepJ = (a, s) => M.step(mkAct(a), s, ...DEFAULT_TABS);
const runJ = (tr, s) => tr.reduce((st, a) => stepJ(a, st), s);
const lastOk = (s) => M.last_ok(s);

// ---------------------------------------------------------------- policy (search heuristics, untrusted)
// target search hints (req.hints, from holon.gen.targetlib.hints_for) or the generic policy
const { policyOf } = await import(req.hints ? pathToFileURL(req.hints).href : "./policy_gen.mjs");
const policy = (sj) => policyOf(dec(sj), facts);

// reachable prefixes: BFS over successful actions, deduplicated by state (log excluded)
function stateKey(sj) { const s = dec(sj); delete s.log; return key(s); }
let PREFIXES = null;
function prefixes() {
  if (PREFIXES) return PREFIXES;
  const seen = new Set([stateKey(s0)]);
  let frontier = [{ trace: [], state: s0 }];
  const all = [...frontier];
  for (let d = 0; d < B.prefixDepth && all.length < B.maxPrefixes; d++) {
    const next = [];
    for (const { trace, state } of frontier) {
      for (const a of policy(state)) {
        const st = stepJ(a, state);
        tried++;
        if (!lastOk(st)) continue;
        const k = stateKey(st);
        if (seen.has(k)) continue;
        seen.add(k);
        const node = { trace: [...trace, a], state: st };
        next.push(node); all.push(node);
        if (all.length >= B.maxPrefixes) break;
      }
      if (all.length >= B.maxPrefixes) break;
    }
    frontier = next;
  }
  PREFIXES = all;
  return all;
}

// ---------------------------------------------------------------- IR evaluation
const FN = (name) => { const f = M[name]; if (typeof f !== "function") throw new Error("no model fn " + name); return f; };
// I24: the expr terms of the statement and their helpers (req.exprs: [{term, fn, binds}], req.module then being the
// model with the helpers appended, holon.mpipeline.CompiledMachine.expr_module)
const EXPRS = new Map((req.exprs || []).map((x) => [key(x.term), x]));
// holon-ir/0.3 builtins (holon.gen.mlaws.BUILTINS): eq_nat is Nat.is_eq, the others are model functions
const BUILTIN = { eq_nat: (x, y) => x === y, eq_bool: (x, y) => FN("eq_bool")(x, y), eq_nats: (x, y) => FN("eq_list_nat")(x, y) };
const LAMS = { id: (x) => x, zero: (x) => 0n, succ: (x) => x + 1n };
const fnVal = (raw) => ({ ty: "Fn", v: LAMS[raw.lam], raw });
// ---------------------------------------------------------------- oracle parameters (I12)
const isParamB = (b) => b.type.startsWith("Fn<") && PARAMS[b.name] !== undefined && PARAMS[b.name].type === b.type;
function dflt(ty) {
  if (ty === "Nat") return 0n;
  if (ty === "Bool") return false;
  if (ty.startsWith("List<")) return { $: "Nil" };
  return FN("empty_" + ty)();
}
function instCand(p, i) { return { ty: "Param", p, v: (x) => INST[i.fn](x), raw: { instance: i.id } }; }
function tableCand(p, entries) {
  const cod = PARAMS[p].cod;
  return { ty: "Param", p, table: entries, raw: { table: entries },
    v: (x) => { const hit = entries.find(([k]) => key(k) === key(dec(x))); return hit ? enc(hit[1]) : dflt(cod); } };
}
function paramCands(b) {
  const fixed = (B.fixed || {})[b.name];
  const insts = ((ORC && ORC.instances) || []).filter((i) => i.param === b.name && INST && typeof INST[i.fn] === "function");
  if (fixed) {
    if (fixed.table) return [tableCand(b.name, fixed.table)];
    return insts.filter((i) => i.id === fixed.instance).map((i) => instCand(b.name, i));
  }
  return [...insts.map((i) => instCand(b.name, i)), tableCand(b.name, [])];
}
let CTX = null;   // {tables: {p: {entries, host}}} while a statement is evaluated
let LAST = null;
class NoFix extends Error {}
const paramsIn = (env) => Object.keys(env).filter((k) => env[k] && env[k].ty === "Param");
function hostTable(c, pts) {
  const entries = c.table ? c.table : [...pts.values()].map((k) => [k, dec(c.v(enc(k)))]);
  return { entries, host: toList(entries.map(([k, v]) => ({ $: "HO_" + c.p, k: enc(k), v: enc(v) }))) };
}
// evaluate thunk with every parameter's table materialised at the points the evaluation queries (fixpoint)
function withTables(env, thunk) {
  const ps = paramsIn(env);
  if (!ps.length || CTX) return thunk();
  const Q = Object.fromEntries(ps.map((p) => [p, new Map()]));
  for (let it = 0; it < 32; it++) {
    const T = Object.fromEntries(ps.map((p) => [p, hostTable(env[p], Q[p])]));
    PROBE.length = 0;
    CTX = { tables: T };
    let r, err = null;
    try { r = thunk(); } catch (e) { err = e; } finally { CTX = null; }
    let grew = false;
    for (const [p, x] of PROBE) {
      if (!(p in Q) || env[p].table) continue;
      const d = dec(x), k = key(d);
      if (!Q[p].has(k)) { Q[p].set(k, d); grew = true; }
    }
    if (!grew) { if (err) throw err; LAST = { T }; return r; }
  }
  notes.push("oracle query points did not converge within 32 rounds");
  throw new NoFix("no fixpoint");
}
const tabArgs = (name) => ((ORC && ORC.fnTabs[name]) || []).map((p) => {
  if (!CTX || !CTX.tables[p]) throw new Error(`${name} needs the oracle table ${p}, which the statement does not bind`);
  return CTX.tables[p].host;
});
function evalT(t, env) {
  if ("var" in t) {
    const v = env[t.var]; if (v === undefined) throw new Unassigned(t.var);
    // a state reached by a trace is re-run under the candidate tables (I12)
    if (v.trace && CTX && DEFAULT_TABS.length) return { ...v, v: M.run(v.trace, s0, ...tabArgs("run")) };
    return v;
  }
  if ("nat" in t) return { ty: "Nat", v: BigInt(t.nat) };
  if ("bool" in t) return { ty: "Bool", v: t.bool };
  if ("nats" in t) return { ty: "List<Nat>", v: enc(t.nats) };
  if ("s0" in t) return { ty: "State", v: s0 };
  if ("run" in t) return { ty: "State", v: M.run(evalT(t.run, env).v, evalT(t.from, env).v, ...tabArgs("run")) };
  if ("step" in t) return { ty: "State", v: M.step(evalT(t.step, env).v, evalT(t.from, env).v, ...tabArgs("step")) };
  if ("obs" in t) return { ty: "Obs", v: M.obs(evalT(t.obs, env).v, evalT(t.from, env).v, ...tabArgs("obs")) };
  if ("trace" in t) return { ty: "Trace", v: toList(t.trace.map((a) => evalT(a, env).v)) };
  if ("cat" in t) { const [x, y] = t.cat.map((z) => dec(evalT(z, env).v)); return { ty: "Trace", v: toList([...x, ...y].map(reAct)) }; }
  if ("act" in t) {
    const spec = ACTIONS[t.act]; const o = { $: "A_" + t.act };
    for (const [n] of spec.inputs) o[n] = evalT(t.args[n], env).v;
    return { ty: "Act", v: o };
  }
  if ("proj" in t) { const s = dec(evalT(t.of, env).v); for (const f of t.proj) delete s[f]; return { ty: "View", v: s, plain: true }; }
  if ("obsv" in t) return { ty: "?", v: FN(t.obsv)(evalT(t.of, env).v, ...tabArgs(t.obsv)) };
  if ("mig" in t) return { ty: "State", v: FN("mig_" + t.mig)(evalT(t.of, env).v, ...(t.args || []).map((a) => evalT(a, env).v), ...tabArgs("mig_" + t.mig)) };
  if ("fn" in t && t.fn in BUILTIN) return { ty: "Bool", v: BUILTIN[t.fn](...t.args.map((a) => evalT(a, env).v)) };
  if ("fn" in t) return { ty: "?", v: FN(t.fn)(...t.args.map((a) => evalT(a, env).v), ...tabArgs(t.fn)) };
  if ("app" in t) {
    const f = evalT({ var: t.app }, env), x = evalT(t.args[0], env).v;
    if (f.ty === "Param") PROBE.push([t.app, x]);   // a point the statement queries (I12)
    return { ty: "?", v: f.v(x) };
  }
  if ("plus" in t) return { ty: "Nat", v: evalT(t.plus[0], env).v + evalT(t.plus[1], env).v };
  if ("expr" in t && "from" in t) {   // an expr term (I24): its statement helper, compiled with the model (req.exprs)
    const spec = EXPRS.get(key(t));
    if (!spec) throw new Error("no compiled helper for the expr term " + JSON.stringify(t));
    const args = [evalT(t.from, env).v];
    if ("on" in t) args.push(evalT(t.on, env).v);
    for (const n of spec.binds) args.push(evalT(t.bind[n], env).v);
    return { ty: "?", v: FN(spec.fn)(...args) };
  }
  if ("site" in t && "on" in t && "from" in t) {   // a SORT-site term (I15): site_<x> of the instrumented model
    const g = (req.sites || {})[t.site];
    if (!g) throw new Error(`no ghost predicate for the site ${t.site} (req.sites)`);
    return { ty: "Bool", v: FN(g.site)(evalT(t.on, env).v, evalT(t.from, env).v, ...siteTabs(g)) };
  }
  throw new Error("term " + JSON.stringify(t));
}
// the oracle tables a ghost predicate takes (the ones the model threads), from the statement's tables
const siteTabs = (g) => (g.tabs || []).map((p) => {
  if (CTX && CTX.tables[p]) return CTX.tables[p].host;
  if (globalThis.__HOLON_OVR && globalThis.__HOLON_OVR[p]) return { $: "Nil" };   // answered by the override
  throw new Error(`${g.site} needs the oracle table ${p}, which the statement does not bind`);
});
function reAct(a) { const o = { $: a.$ }; for (const [k, v] of Object.entries(a)) if (k !== "$") o[k] = enc(v); return o; }
class Unassigned extends Error { constructor(v) { super("unassigned " + v); this.v = v; } }
const val = (r) => (r.plain ? r.v : dec(r.v));
function holds(p, env) { return withTables(env, () => holdsRaw(p, env)); }
function holdsRaw(p, env) {
  if (p.cf) { // collision-freedom over a finite set: pairwise distinct images
    const ks = p.cf.set.map((x) => key(val(evalT({ app: p.cf.fn, args: [x] }, env))));
    return new Set(ks).size === ks.length;
  }
  if (p.neq) return key(val(evalT(p.neq[0], env))) !== key(val(evalT(p.neq[1], env)));
  const [a, b] = p.eq;
  return key(val(evalT(a, env))) === key(val(evalT(b, env)));
}
function tryHolds(p, env) {
  try { return holds(p, env); } catch (e) {
    if (e instanceof Unassigned) return null;
    if (e instanceof NoFix) return false;   // oracle query points did not converge: the candidate is skipped (I12)
    throw e;
  }
}

// ---------------------------------------------------------------- binder enumeration
const st = law.statement;
const binders = st.binders;
// statement.scope (holon-ir/0.3; audit F-M2-01): bounded{H} bounds every Trace binder to at most H actions, so a
// longer trace is never proposed as a witness (the emitted law states the bound as a premise the kernel checks)
const SCOPE_H = st.scope && st.scope.kind === "bounded" && Number.isInteger(st.scope.H) ? st.scope.H : null;
const inScope = (raw) => SCOPE_H === null || !Array.isArray(raw) || raw.length <= SCOPE_H;
// enumerate states and prefixes first, then actions and numbers, then continuation traces
// key-order independent: does term t contain {kind: {var: v}, from: {s0: {}}}? (I6: a law in canonical,
// sorted-key form must search exactly like the same law in authored key order)
const isVar = (x, v) => x && typeof x === "object" && Object.keys(x).length === 1 && x.var === v;
const isS0 = (x) => x && typeof x === "object" && Object.keys(x).length === 1 && x.s0 && Object.keys(x.s0).length === 0;
const hasFromS0 = (t, kind, v) => {
  if (Array.isArray(t)) return t.some((x) => hasFromS0(x, kind, v));
  if (!t || typeof t !== "object") return false;
  if (Object.keys(t).length === 2 && isVar(t[kind], v) && isS0(t.from)) return true;
  return Object.values(t).some((x) => hasFromS0(x, kind, v));
};
// a trace whose success from s0 the statement tests (runs_ok(p, s0)): failing traces are candidates too
const isRunsOkVar = (v) => hasFromS0Fn(st, v);
function hasFromS0Fn(t, v) {
  if (Array.isArray(t)) return t.some((x) => hasFromS0Fn(x, v));
  if (!t || typeof t !== "object") return false;
  if (t.fn === "runs_ok" && Array.isArray(t.args) && t.args.length === 2 && isVar(t.args[0], v) && isS0(t.args[1])) return true;
  return Object.values(t).some((x) => hasFromS0Fn(x, v));
}
const rank = (b) => (b.type === "State" || b.type === "Reach" || (b.type === "Trace" && (hasFromS0(law.statement, "run", b.name)
  || hasFromS0(law.statement, "obs", b.name)))) ? 0
  : b.type === "Act" ? 1 : b.type === "Nat" ? 2 : 3;
const forall = binders.filter((b) => b.q === "forall").map((b, i) => [b, i]).sort((x, y) => rank(x[0]) - rank(y[0]) || x[1] - y[1]).map((x) => x[0]);
const assume = st.assume || [];
const claims = st.claim.all || [st.claim];
const mentions = (t, v) => JSON.stringify(t).includes(JSON.stringify({ var: v }));
const isPrefixVar = (v) => hasFromS0(st, "run", v);
// a trace observed from the initial state: reachable prefixes, each possibly ending in one failing action
const isObsPrefixVar = (v) => hasFromS0(st, "obs", v);
const isObsSuffix = (v) => claims.length === 1 && Array.isArray(claims[0].eq) && claims[0].eq.every((s) => s.obs && JSON.stringify(s.obs) === JSON.stringify({ var: v }));

function baseState(env) {
  for (const b of forall) if ((b.type === "State" || b.type === "Reach") && env[b.name]) return env[b.name].v;
  for (const b of forall) if (b.type === "Trace" && isPrefixVar(b.name) && env[b.name]) return M.run(env[b.name].v, s0);
  return s0;
}

function candidates(b, env) {
  const cs = candidatesAll(b, env);
  return b.type === "Trace" && SCOPE_H !== null ? cs.filter((c) => inScope(c.raw)) : cs;
}
function candidatesAll(b, env) {
  if (isParamB(b)) return paramCands(b);
  if (b.type === "Fn<Nat,Nat>") return Object.keys(LAMS).map((lam) => fnVal({ lam }));
  // a Reach binder (I8) ranges over reachable states only: the prefixes, as traces from s0
  if (b.type === "Reach") return prefixes().map((p) => ({ ty: "State", v: p.state, raw: { run: p.trace }, trace: traceOf(p) }));
  if (b.type === "Trace" && isPrefixVar(b.name) && !isRunsOkVar(b.name)) return prefixes().map((p) => ({ ty: "Trace", v: toList(p.trace.map(mkAct)), raw: p.trace }));
  if (b.type === "Trace" && (isObsPrefixVar(b.name) || isRunsOkVar(b.name))) {
    const out = [];
    for (const p of prefixes()) {
      out.push({ ty: "Trace", v: toList(p.trace.map(mkAct)), raw: p.trace });
      for (const a of policy(p.state)) out.push({ ty: "Trace", v: toList([...p.trace, a].map(mkAct)), raw: [...p.trace, a] });
    }
    return out;
  }
  if (b.type === "Act") return actVariants(policy(baseState(env))).map((a) => ({ ty: "Act", v: mkAct(a), raw: a }));
  if (b.type === "Nat") {
    const xs = new Set(); for (let i = 0; i <= B.natMax; i++) xs.add(i);
    for (const p of assume) { // premise-directed: var == term
      const [l, r] = p.eq;
      if (l.var === b.name) { try { xs.add(Number(evalT(r, env).v)); } catch (e) { if (!(e instanceof Unassigned)) throw e; } }
    }
    return [...xs].sort((x, y) => x - y).map((n) => ({ ty: "Nat", v: BigInt(n), raw: n }));
  }
  if (b.type === "State") {
    // premise-directed: s2 agrees with an assigned s1 outside the fields a proj premise erases.
    // Reachable states with the same projection come first (run(p, s0)); constructed perturbations
    // of s1 only after them.
    for (const p of assume) {
      const [l, r] = p.eq;
      if (l.proj && r.proj && r.of.var === b.name && l.of.var && env[l.of.var]) {
        const base = dec(env[l.of.var].v);
        const same = (prefixesByProj(l.proj).get(projKey(base, l.proj)) || [])
          .map((q) => ({ ty: "State", v: q.state, raw: { run: q.trace }, trace: traceOf(q) }));
        if (B.noPerturb) return same;  // reachable pairs only (a first pass that prefers run(p, s0) witnesses)
        return [...same, ...perturb(base, l.proj).map((st) => ({ ty: "State", v: enc(st), raw: { state: st } }))];
      }
    }
    // a prefix state is reachable: report it as the trace from s0 that reaches it (run(p, s0))
    return prefixes().map((p) => ({ ty: "State", v: p.state, raw: { run: p.trace }, trace: traceOf(p) }));
  }
  if (b.type === "Trace") return suffixes(baseState(env)).map((tr) => ({ ty: "Trace", v: toList(tr.map(mkAct)), raw: tr }));
  return [];
}

// I24 (req.parAct: the actions a PAR law's expr terms name): the policy's actions of those actions plus, for each, the
// boundary variants of every Nat input (v - 1 when v >= 1, v + 1, 0; I15's S1) and the empty list for every List<Nat>
// input (§8.7: sort boundary values); without req.parAct, the policy's actions unchanged
function actVariants(acts) {
  if (!req.parAct) return acts;
  const want = new Set(req.parAct);
  const out = [], seen = new Set();
  const add = (a) => { const k = key(a); if (!seen.has(k)) { seen.add(k); out.push(a); } };
  for (const a of acts) if (want.has(a.op)) add(a);
  for (const a of acts) {
    if (!want.has(a.op)) continue;
    for (const [n, ty] of ACTIONS[a.op].inputs) {
      if (ty === "Nat") {
        const v = Number(a[n]);
        for (const x of [...(v >= 1 ? [v - 1] : []), v + 1, 0]) add({ ...a, [n]: x });
      } else if (ty === "List<Nat>") add({ ...a, [n]: [] });
    }
  }
  return out;
}

// a prefix's trace, kept (as a host list) only when the model threads oracle tables (I12)
function traceOf(p) { return DEFAULT_TABS.length ? toList(p.trace.map(mkAct)) : undefined; }

// the declared type of each state field (facts "state": [name, type, doc]); perturbations respect it
const FIELD_TYPE = Object.fromEntries((facts.state || []).map((x) => [x[0], x[1]]));
function zeroOf(ty) {
  if (ty === "Nat") return 0;
  if (ty === "Bool") return false;
  if (ty.startsWith("List<")) return [];
  const rec = (facts.types || {})[ty];
  if (!rec) throw new Error(`perturb: no type ${ty}`);
  const o = { $: "H" + ty };
  for (const [fn, ft] of rec.fields) o[fn] = zeroOf(ft);
  return o;
}

// the state with the erased fields removed, as a canonical key
function projKey(st, fields) { const c = { ...st }; for (const f of fields) delete c[f]; return key(c); }
const BY_PROJ = new Map();
function prefixesByProj(fields) {
  const k = fields.join(",");
  if (!BY_PROJ.has(k)) {
    const m = new Map();
    for (const q of prefixes()) { const pk = projKey(dec(q.state), fields); if (!m.has(pk)) m.set(pk, []); m.get(pk).push(q); }
    BY_PROJ.set(k, m);
  }
  return BY_PROJ.get(k);
}

function perturb(st, fields) {
  const out = [];
  for (const f of fields) {
    const v = st[f];
    const ty = FIELD_TYPE[f] || "";
    const elem = ty.startsWith("List<") ? ty.slice(5, -1) : null;
    const alts = typeof v === "number" ? [v + 1, v + 5, Math.max(0, v - 1)]
      : typeof v === "boolean" ? [!v]
      : Array.isArray(v) ? (elem && elem !== "Nat" && elem !== "Bool"
          ? [[], v.slice(1), [zeroOf(elem), ...v]]          // a list of records: never fill it with numbers
          : [[], [1], [7], [1, ...v], v.slice(1)])
      : [];
    for (const a of alts) { const c = JSON.parse(JSON.stringify(st)); c[f] = a; if (key(c) !== key(st)) out.push(c); }
  }
  return out;
}

function suffixes(sj) {
  // small BFS of action sequences from sj (any outcome), depth <= 2
  const out = [[]];
  let frontier = [{ tr: [], s: sj }];
  for (let d = 0; d < 2; d++) {
    const next = [];
    for (const { tr, s } of frontier) for (const a of policy(s)) { const n = { tr: [...tr, a], s: stepJ(a, s) }; next.push(n); out.push(n.tr); }
    frontier = next.slice(0, 200);
  }
  return out;
}

// divergence search for claims obs(q, L) == obs(q, R): BFS on q, extending only while the logs agree
function divergence(env, qname) {
  const [l, r] = claims[0].eq;
  const L = evalT(l.from, env).v, R = evalT(r.from, env).v;
  let frontier = [{ tr: [], a: M.clear_log(L), b: M.clear_log(R) }];
  let nodes = 0;
  for (let d = 0; d < Math.min(B.suffixDepth, SCOPE_H === null ? Infinity : SCOPE_H); d++) {
    const next = [];
    for (const n of frontier) {
      const seenHere = new Set();
      for (const act of [...policy(n.a), ...policy(n.b)]) {
        const k = key(act); if (seenHere.has(k)) continue; seenHere.add(k);
        const a2 = stepJ(act, n.a), b2 = stepJ(act, n.b);
        nodes++; tried++;
        const oa = key(dec(M.log_of(a2))), ob = key(dec(M.log_of(b2)));
        if (oa !== ob) return [...n.tr, act];
        if (!lastOk(a2) && !lastOk(b2)) continue; // fails on both sides: no information
        next.push({ tr: [...n.tr, act], a: a2, b: b2 });
        if (nodes > B.maxNodes) return null;
      }
    }
    frontier = next;
  }
  return null;
}

function search(i, env, raw) {
  if (i === forall.length) {
    try {
      for (const p of assume) if (!holds(p, env)) return null;
      tried++;
      for (const c of claims) if (!holds(c, env)) return raw;
    } catch (e) { if (e instanceof NoFix) return null; throw e; }   // no fixpoint: never a witness (I12)
    return null;
  }
  const b = forall[i];
  if (b.type === "Trace" && !isPrefixVar(b.name) && isObsSuffix(b.name) && i === forall.length - 1) {
    for (const p of assume) { const h = tryHolds(p, env); if (h === false) return null; }
    const q = divergence(env, b.name);
    return q && inScope(q) ? { ...raw, [b.name]: q } : null;
  }
  for (const c of candidates(b, env)) {
    const env2 = { ...env, [b.name]: c };
    let ok = true;
    for (const p of assume) { const h = tryHolds(p, env2); if (h === false) { ok = false; break; } }
    if (!ok) continue;
    const r = search(i + 1, env2, { ...raw, [b.name]: c.raw });
    if (r) return r;
    if (tried > B.maxNodes * 4) return null;
  }
  return null;
}

// strategy search for exists laws: BFS over successful action sequences from the state the claims run them from
function findRunBase(t, v) {
  if (t && typeof t === "object") {
    if (t.run && t.run.var === v) return t.from;
    if (t.fn === "runs_ok" && t.args[0].var === v) return t.args[1];
    for (const x of Object.values(t)) { const r = findRunBase(x, v); if (r) return r; }
  }
  return null;
}
// exists laws over finite candidate sets (Act, Nat 0..natMax, Bool, Fn): enumerate, in candidate order
function enumExists(ex, i, env, raw) {
  if (i === ex.length) {
    tried++;
    try { return claims.every((c) => holds(c, env)) ? raw : null; } catch (e) { if (e instanceof NoFix) return null; throw e; }
  }
  const b = ex[i];
  const cs = b.type === "Bool" ? [false, true].map((x) => ({ ty: "Bool", v: x, raw: x })) : candidates(b, env);
  for (const c of cs) {
    const r = enumExists(ex, i + 1, { ...env, [b.name]: c }, { ...raw, [b.name]: c.raw });
    if (r) return r;
  }
  return null;
}
function strategies() {
  const ex = binders.filter((b) => b.q === "exists");
  if (ex.length && ex.every((b) => ["Act", "Nat", "Bool", "Fn<Nat,Nat>"].includes(b.type) || isParamB(b))) return enumExists(ex, 0, {}, {});
  if (ex.length !== 1 || ex[0].type !== "Trace") return null;
  const v = ex[0].name;
  const base = evalT(findRunBase(st.claim, v), {}).v;
  let frontier = [{ tr: [], s: base }];
  const check = (tr) => { tried++; const env = { [v]: { ty: "Trace", v: toList(tr.map(mkAct)) } }; return claims.every((c) => holds(c, env)); };
  if (check([])) return { [v]: [] };
  for (let d = 0; d < Math.min(B.suffixDepth, SCOPE_H === null ? Infinity : SCOPE_H); d++) {
    const next = [];
    for (const n of frontier) for (const a of policy(n.s)) {
      const s2 = stepJ(a, n.s);
      if (!lastOk(s2)) continue;
      const tr = [...n.tr, a];
      if (check(tr)) return { [v]: tr };
      next.push({ tr, s: s2 });
    }
    frontier = next.slice(0, 20000);
  }
  return null;
}
// the environment of an assignment (a witness as recorded)
function envOf(asg) {
  const env = {};
  for (const b of binders) {
    const w = asg[b.name];
    if (w === undefined) continue;
    if (isParamB(b)) {
      if (w.table) env[b.name] = tableCand(b.name, w.table);
      else { const i = ((ORC && ORC.instances) || []).find((x) => x.id === w.instance && INST && INST[x.fn]);
        if (!i) throw new Error(`no compiled instance ${JSON.stringify(w)} of ${b.name}`); env[b.name] = instCand(b.name, i); }
    } else if (b.type === "Trace") env[b.name] = { ty: "Trace", v: toList(w.map(mkAct)) };
    else if (b.type === "Act") env[b.name] = { ty: "Act", v: mkAct(w) };
    else if (b.type === "Nat") env[b.name] = { ty: "Nat", v: BigInt(w) };
    else if (b.type === "Bool") env[b.name] = { ty: "Bool", v: w };
    else if (b.type === "State" || b.type === "Reach") env[b.name] = { ty: "State", v: w.run ? runJ(w.run, s0) : enc(w.state),
      trace: w.run ? traceOf({ trace: w.run }) : undefined };
    else if (b.type === "Fn<Nat,Nat>") env[b.name] = fnVal(w);
  }
  return env;
}
// the table each parameter's witness denotes, over every premise and claim of the statement (I12)
function finalTables(env) {
  const ps = paramsIn(env);
  if (!ps.length) return null;
  LAST = null;
  withTables(env, () => { for (const p of assume) holdsRaw(p, env); for (const c of claims) holdsRaw(c, env); });
  return Object.fromEntries(ps.map((p) => [p, LAST.T[p].entries]));
}
// ---------------------------------------------------------------- SORT-site search (I15)
// req.site = {"fn": site_<x>, "hit": hit_<x>, "entries": [entry points, sorted], "mode": "refute" | "inhabit",
//             "stage": "S2" | "S3", "seeds": {entry point: prefix} (S3: Bend-checked witnesses of the other entry
//             points), "s3max": prefixes per entry point (S3)}
// Stages (the thresholds of spec/M2/predictions.json, key I15):
//   S1 candidates at a state: the entry point's actions from the search policy, then, for each of them and each Nat
//      input in input order, the variants v - 1 (when v >= 1), v + 1 and 0, without repeats (boundary values);
//   S2 the reachable prefixes (BFS over successful policy actions; prefixDepth, maxPrefixes) in order: the first
//      (prefix, candidate) where the ghost predicate is false (refute) / its at_site predicate true (inhabit);
//   S3 (refute, only for entry points S2 left without a witness) for each seed (entry points sorted), each insertion
//      position i of its prefix and each sequence of one or two successful policy actions at the state after
//      prefix[:i] (BFS order), the prefix prefix[:i] ++ seq ++ prefix[i:] if all of its actions succeed, then S1's
//      candidates there; at most s3max prefixes per entry point.
// Every oracle parameter of the law is the sidecar's concrete instance (the I12 design; the empty table where a
// parameter has none): a lookup override answers it while prefixes are explored and candidates evaluated. A witness's
// tables are then materialised at the points its evaluation queries, and the predicate re-evaluated on them without
// the override (untrusted: only a Bend-checked counter-law or inhabitant counts).
function siteSearch(S) {
  const bs = law.statement.binders;
  const sB = bs.find((b) => b.type === "Reach" || b.type === "State");
  const aB = bs.find((b) => b.type === "Act");
  const pBs = bs.filter(isParamB);
  const threaded = ORC ? ORC.threaded : [];
  const OVR = {}, pvals = {};
  for (const b of pBs) {
    const ins = ((ORC && ORC.instances) || []).filter((i) => i.param === b.name && INST && typeof INST[i.fn] === "function");
    if (ins.length) { pvals[b.name] = { instance: ins[0].id }; OVR[b.name] = (x) => INST[ins[0].fn](x); }
    else { const cod = PARAMS[b.name].cod; pvals[b.name] = { table: [] }; OVR[b.name] = () => dflt(cod); }
  }
  for (const p of threaded) if (!OVR[p]) throw new Error(`the site law binds no oracle parameter ${p}, which the model threads`);
  globalThis.__HOLON_OVR = OVR;
  const nil = threaded.map(() => ({ $: "Nil" }));
  const pred = (fn, a, st) => { tried++; PROBE.length = 0; return M[fn](mkAct(a), st, ...nil) === true; };
  const want = S.mode === "inhabit";   // the value that makes a witness: hit true, or site false
  const fn = want ? S.hit : S.fn;
  const POL = new Map();
  const pol = (st) => { const k = stateKey(st); if (!POL.has(k)) POL.set(k, policy(st)); return POL.get(k); };
  function s1(st, e) {
    const base = pol(st).filter((a) => a.op === e);
    const out = [], seen = new Set();
    const push = (a) => { const k = key(a); if (!seen.has(k)) { seen.add(k); out.push(a); } };
    base.forEach(push);
    for (const a of base) for (const [n, ty] of ACTIONS[e].inputs) {
      if (ty !== "Nat") continue;
      const v = a[n];
      for (const w of [v >= 1 ? v - 1 : null, v + 1, 0]) if (w !== null) push({ ...a, [n]: w });
    }
    return out;
  }
  // a witness's tables, materialised at the points its evaluation queries (fixpoint), and its predicate value there
  function materialise(trace, a) {
    const pts = Object.fromEntries(threaded.map((p) => [p, new Map()]));
    const collect = () => { let grew = false; for (const [p, x] of PROBE) { if (!(p in pts)) continue;
      const d = dec(x), k = key(d); if (!pts[p].has(k)) { pts[p].set(k, d); grew = true; } } return grew; };
    globalThis.__HOLON_OVR = OVR;
    PROBE.length = 0;
    M[fn](mkAct(a), M.run(toList(trace.map(mkAct)), s0, ...nil), ...nil);
    collect();
    globalThis.__HOLON_OVR = null;
    let val = null, tabs = null;
    for (let it = 0; it < 32; it++) {
      tabs = Object.fromEntries(threaded.map((p) => [p, [...pts[p].values()].map((k) => [k, dec(OVR[p](enc(k)))])]));
      const hosts = threaded.map((p) => toList(tabs[p].map(([k, v]) => ({ $: "HO_" + p, k: enc(k), v: enc(v) }))));
      PROBE.length = 0;
      val = M[fn](mkAct(a), M.run(toList(trace.map(mkAct)), s0, ...hosts), ...hosts) === true;
      if (!collect()) break;
    }
    globalThis.__HOLON_OVR = OVR;
    return { val, tabs: threaded.length ? tabs : null };
  }
  const W = (trace, a) => ({ [sB.name]: { run: trace }, [aB.name]: a, ...pvals });
  const prefixBound = () => `S1+S2: reachable prefixes, BFS depth ${B.prefixDepth} over successful policy actions `
    + `(<= ${B.maxPrefixes} states; ${prefixes().length} explored), at each the entry point's policy actions and their `
    + `Nat boundary variants (v - 1 when v >= 1, v + 1, 0)` + (pBs.length ? `; oracle parameters: ${pBs.map((b) =>
      `${b.name} = ${pvals[b.name].instance ? "the sidecar instance " + pvals[b.name].instance : "the empty table"}`).join(", ")}` : "");
  const out = {};
  if (S.mode === "inhabit") {
    let hit = null;
    for (const p of prefixes()) {
      for (const e of S.entries) { for (const a of s1(p.state, e)) if (pred(fn, a, p.state)) { hit = { e, trace: p.trace, a }; break; } if (hit) break; }
      if (hit) break;
    }
    let w = null, tabs = null;
    if (hit) {
      const m = materialise(hit.trace, hit.a);
      if (m.val) { w = W(hit.trace, hit.a); tabs = m.tabs; }
      else notes.push("the at_site witness did not hold on its materialised tables: dropped");
    }
    return { inhabit: { witness: w, entry: hit ? hit.e : null, tables: tabs, bound: prefixBound() }, tried };
  }
  for (const e of S.entries) {
    let found = null, stage = S.stage, extra = "";
    if (S.stage === "S2") {
      for (const p of prefixes()) {
        for (const a of s1(p.state, e)) if (!pred(fn, a, p.state)) { found = { trace: p.trace, a }; break; }
        if (found) break;
      }
    } else {
      const seen = new Set(), max = S.s3max || 20000;
      let n = 0;
      const seeds = Object.keys(S.seeds || {}).filter((x) => x !== e).sort();
      outer:
      for (const se of seeds) {
        const pre = S.seeds[se];
        for (let i = 0; i <= pre.length; i++) {
          const base = runJ(pre.slice(0, i), s0);
          const seqs = [];
          for (const a1 of pol(base)) { const t1 = stepJ(a1, base); tried++; if (lastOk(t1)) seqs.push([[a1], t1]); }
          const ones = seqs.slice();
          for (const [[a1], t1] of ones) for (const a2 of pol(t1)) { const t2 = stepJ(a2, t1); tried++; if (lastOk(t2)) seqs.push([[a1, a2], t2]); }
          for (const [seq, t] of seqs) {
            let st = t, ok = true;
            for (const a of pre.slice(i)) { st = stepJ(a, st); if (!lastOk(st)) { ok = false; break; } }
            if (!ok) continue;
            const tr = [...pre.slice(0, i), ...seq, ...pre.slice(i)];
            const k = key(tr);
            if (seen.has(k)) continue;
            seen.add(k);
            if (++n > max) break outer;
            for (const a of s1(st, e)) if (!pred(fn, a, st)) { found = { trace: tr, a }; break outer; }
          }
        }
      }
      extra = `; S3: one or two successful policy actions inserted at every position of the prefixes of the checked `
        + `witnesses of ${seeds.join(", ") || "no other entry point"} (<= ${max} prefixes; ${Math.min(n, max)} searched)`;
    }
    let w = null, tabs = null;
    if (found) {
      const m = materialise(found.trace, found.a);
      if (!m.val) { w = W(found.trace, found.a); tabs = m.tabs; }
      else notes.push(`${e}: the witness did not refute on its materialised tables: dropped`);
    }
    out[e] = { witness: w, stage: w ? stage : null, tables: tabs, bound: prefixBound() + extra };
  }
  return { site: out, tried };
}
if (req.site) {
  const r = siteSearch(req.site);
  process.stdout.write(JSON.stringify({ ...r, notes }));
  process.exit(0);
}
if (req.evaluate) {
  // evaluate a law at a given assignment: {"premises": [bool], "claims": [bool]} (and, with oracle parameters,
  // "sides": each claim's two sides, and "tables")
  const env = envOf(req.evaluate);
  const out = { premises: assume.map((p) => holds(p, env)), claims: claims.map((c) => holds(c, env)) };
  if (paramsIn(env).length) {
    out.tables = finalTables(env);
    out.sides = claims.map((c) => (c.eq ? withTables(env, () => c.eq.map((s) => val(evalT(s, env)))) : null));
  } else if (EXPRS.size) {   // expr terms (I24): their sides, evaluated through the compiled helpers
    out.sides = claims.map((c) => (c.eq ? c.eq.map((s) => val(evalT(s, env))) : null));
  }
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
}
let witness = null;
if (binders.some((b) => b.q === "exists")) { witness = strategies(); notes.push("exists law: strategy search"); }
else witness = search(0, {}, {});
const hasParams = binders.some(isParamB);
const finite = (binders.every((b) => b.q === "exists") || binders.some((b) => b.type.startsWith("Fn<")))
  && binders.every((b) => ["Act", "Nat", "Bool", "Fn<Nat,Nat>"].includes(b.type) || isParamB(b));
let bound = finite ? `finite candidates: Act from the policy at s0, Nat 0..${B.natMax} plus premise-solved values, Bool, Fn<Nat,Nat> in {id, zero, succ}`
  : `prefixes: BFS depth ${B.prefixDepth} over policy actions (<= ${B.maxPrefixes} states); suffixes: divergence BFS depth ${B.suffixDepth}; Nat binders 0..${B.natMax} plus premise-solved values`;
if (hasParams) bound += "; oracle parameters: the sidecar's concrete instances, then the empty table (tables at the points the statement queries)";
if (SCOPE_H !== null) bound += `; scope bounded{H=${SCOPE_H}}: traces of at most ${SCOPE_H} actions`;
const out = { witness, tried, bound, notes };
if (witness && hasParams) out.tables = finalTables(envOf(witness));
process.stdout.write(JSON.stringify(out));
