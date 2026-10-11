// Deterministic refutation search for holon-ir/0.2 laws on a compiled Bend state-machine model.
// Untrusted: it only proposes witnesses; a law becomes REFUTED only when Bend accepts the counter-law.
//
// stdin: {"module": path, "facts": {...}, "law": {...IR...}, "budget": {...}}
// stdout: {"witness": {binder: value} | null, "tried": n, "bound": "...", "notes": [..]}
//
// Values: Trace = [{"op": name, input: value..}], Act = {"op":..}, Nat = int, Bool, State = {"run": Trace}.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
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
const stepJ = (a, s) => M.step(mkAct(a), s);
const runJ = (tr, s) => tr.reduce((st, a) => stepJ(a, st), s);
const lastOk = (s) => M.last_ok(s);

// ---------------------------------------------------------------- policy (search heuristics, untrusted)
import { policyOf } from "./policy_lib.mjs";
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
function evalT(t, env) {
  if ("var" in t) { const v = env[t.var]; if (v === undefined) throw new Unassigned(t.var); return v; }
  if ("nat" in t) return { ty: "Nat", v: BigInt(t.nat) };
  if ("bool" in t) return { ty: "Bool", v: t.bool };
  if ("nats" in t) return { ty: "List<Nat>", v: enc(t.nats) };
  if ("s0" in t) return { ty: "State", v: s0 };
  if ("run" in t) return { ty: "State", v: M.run(evalT(t.run, env).v, evalT(t.from, env).v) };
  if ("step" in t) return { ty: "State", v: M.step(evalT(t.step, env).v, evalT(t.from, env).v) };
  if ("obs" in t) return { ty: "Obs", v: M.obs(evalT(t.obs, env).v, evalT(t.from, env).v) };
  if ("trace" in t) return { ty: "Trace", v: toList(t.trace.map((a) => evalT(a, env).v)) };
  if ("cat" in t) { const [x, y] = t.cat.map((z) => dec(evalT(z, env).v)); return { ty: "Trace", v: toList([...x, ...y].map(reAct)) }; }
  if ("act" in t) {
    const spec = ACTIONS[t.act]; const o = { $: "A_" + t.act };
    for (const [n] of spec.inputs) o[n] = evalT(t.args[n], env).v;
    return { ty: "Act", v: o };
  }
  if ("proj" in t) { const s = dec(evalT(t.of, env).v); for (const f of t.proj) delete s[f]; return { ty: "View", v: s, plain: true }; }
  if ("obsv" in t) return { ty: "?", v: FN(t.obsv)(evalT(t.of, env).v) };
  if ("mig" in t) return { ty: "State", v: FN("mig_" + t.mig)(evalT(t.of, env).v, ...(t.args || []).map((a) => evalT(a, env).v)) };
  if ("fn" in t) return { ty: "?", v: FN(t.fn)(...t.args.map((a) => evalT(a, env).v)) };
  if ("plus" in t) return { ty: "Nat", v: evalT(t.plus[0], env).v + evalT(t.plus[1], env).v };
  throw new Error("term " + JSON.stringify(t));
}
function reAct(a) { const o = { $: a.$ }; for (const [k, v] of Object.entries(a)) if (k !== "$") o[k] = enc(v); return o; }
class Unassigned extends Error { constructor(v) { super("unassigned " + v); this.v = v; } }
const val = (r) => (r.plain ? r.v : dec(r.v));
function holds(p, env) {
  const [a, b] = p.eq;
  return key(val(evalT(a, env))) === key(val(evalT(b, env)));
}
function tryHolds(p, env) { try { return holds(p, env); } catch (e) { if (e instanceof Unassigned) return null; throw e; } }

// ---------------------------------------------------------------- binder enumeration
const st = law.statement;
const binders = st.binders;
// enumerate states and prefixes first, then actions and numbers, then continuation traces
const rank = (b) => (b.type === "State" || (b.type === "Trace" && (JSON.stringify(law.statement).includes(JSON.stringify({ run: { var: b.name }, from: { s0: {} } }))
  || JSON.stringify(law.statement).includes(JSON.stringify({ obs: { var: b.name }, from: { s0: {} } }))))) ? 0
  : b.type === "Act" ? 1 : b.type === "Nat" ? 2 : 3;
const forall = binders.filter((b) => b.q === "forall").map((b, i) => [b, i]).sort((x, y) => rank(x[0]) - rank(y[0]) || x[1] - y[1]).map((x) => x[0]);
const assume = st.assume || [];
const claims = st.claim.all || [st.claim];
const mentions = (t, v) => JSON.stringify(t).includes(JSON.stringify({ var: v }));
const isPrefixVar = (v) => JSON.stringify(st).includes(JSON.stringify({ run: { var: v }, from: { s0: {} } }));
// a trace observed from the initial state: reachable prefixes, each possibly ending in one failing action
const isObsPrefixVar = (v) => JSON.stringify(st).includes(JSON.stringify({ obs: { var: v }, from: { s0: {} } }));
const isObsSuffix = (v) => claims.length === 1 && claims[0].eq.every((s) => s.obs && JSON.stringify(s.obs) === JSON.stringify({ var: v }));

function baseState(env) {
  for (const b of forall) if (b.type === "State" && env[b.name]) return env[b.name].v;
  for (const b of forall) if (b.type === "Trace" && isPrefixVar(b.name) && env[b.name]) return M.run(env[b.name].v, s0);
  return s0;
}

function candidates(b, env) {
  if (b.type === "Trace" && isPrefixVar(b.name)) return prefixes().map((p) => ({ ty: "Trace", v: toList(p.trace.map(mkAct)), raw: p.trace }));
  if (b.type === "Trace" && isObsPrefixVar(b.name)) {
    const out = [];
    for (const p of prefixes()) {
      out.push({ ty: "Trace", v: toList(p.trace.map(mkAct)), raw: p.trace });
      for (const a of policy(p.state)) out.push({ ty: "Trace", v: toList([...p.trace, a].map(mkAct)), raw: [...p.trace, a] });
    }
    return out;
  }
  if (b.type === "Act") return policy(baseState(env)).map((a) => ({ ty: "Act", v: mkAct(a), raw: a }));
  if (b.type === "Nat") {
    const xs = new Set(); for (let i = 0; i <= B.natMax; i++) xs.add(i);
    for (const p of assume) { // premise-directed: var == term
      const [l, r] = p.eq;
      if (l.var === b.name) { try { xs.add(Number(evalT(r, env).v)); } catch (e) { if (!(e instanceof Unassigned)) throw e; } }
    }
    return [...xs].sort((x, y) => x - y).map((n) => ({ ty: "Nat", v: BigInt(n), raw: n }));
  }
  if (b.type === "State") {
    // premise-directed: s2 differs from an assigned s1 only in the fields a proj premise erases
    for (const p of assume) {
      const [l, r] = p.eq;
      if (l.proj && r.proj && r.of.var === b.name && l.of.var && env[l.of.var]) {
        const base = dec(env[l.of.var].v);
        return perturb(base, l.proj).map((st) => ({ ty: "State", v: enc(st), raw: { state: st } }));
      }
    }
    // a prefix state is reachable: report it as the trace from s0 that reaches it (run(p, s0))
    return prefixes().map((p) => ({ ty: "State", v: p.state, raw: { run: p.trace } }));
  }
  if (b.type === "Trace") return suffixes(baseState(env)).map((tr) => ({ ty: "Trace", v: toList(tr.map(mkAct)), raw: tr }));
  return [];
}

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
  for (let d = 0; d < B.suffixDepth; d++) {
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
    for (const p of assume) if (!holds(p, env)) return null;
    tried++;
    for (const c of claims) if (!holds(c, env)) return raw;
    return null;
  }
  const b = forall[i];
  if (b.type === "Trace" && !isPrefixVar(b.name) && isObsSuffix(b.name) && i === forall.length - 1) {
    for (const p of assume) { const h = tryHolds(p, env); if (h === false) return null; }
    const q = divergence(env, b.name);
    return q ? { ...raw, [b.name]: q } : null;
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
function strategies() {
  const ex = binders.filter((b) => b.q === "exists");
  if (ex.length !== 1 || ex[0].type !== "Trace") return null;
  const v = ex[0].name;
  const base = evalT(findRunBase(st.claim, v), {}).v;
  let frontier = [{ tr: [], s: base }];
  const check = (tr) => { tried++; const env = { [v]: { ty: "Trace", v: toList(tr.map(mkAct)) } }; return claims.every((c) => holds(c, env)); };
  if (check([])) return { [v]: [] };
  for (let d = 0; d < B.suffixDepth; d++) {
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
if (req.evaluate) {
  // evaluate a law at a given assignment: {"premises": [bool], "claims": [bool]}
  const env = {};
  for (const b of binders) {
    const w = req.evaluate[b.name];
    if (b.type === "Trace") env[b.name] = { ty: "Trace", v: toList(w.map(mkAct)) };
    else if (b.type === "Act") env[b.name] = { ty: "Act", v: mkAct(w) };
    else if (b.type === "Nat") env[b.name] = { ty: "Nat", v: BigInt(w) };
    else if (b.type === "Bool") env[b.name] = { ty: "Bool", v: w };
    else if (b.type === "State") env[b.name] = { ty: "State", v: w.run ? runJ(w.run, s0) : enc(w.state) };
  }
  process.stdout.write(JSON.stringify({ premises: assume.map((p) => holds(p, env)), claims: claims.map((c) => holds(c, env)) }));
  process.exit(0);
}
let witness = null;
if (binders.some((b) => b.q === "exists")) { witness = strategies(); notes.push("exists law: strategy search"); }
else witness = search(0, {}, {});
const bound = `prefixes: BFS depth ${B.prefixDepth} over policy actions (<= ${B.maxPrefixes} states); suffixes: divergence BFS depth ${B.suffixDepth}; Nat binders 0..${B.natMax} plus premise-solved values`;
process.stdout.write(JSON.stringify({ witness, tried, bound, notes }));
