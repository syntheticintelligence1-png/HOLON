// HOLON I21 (audit round M2/2, auditor A4) vacuity harness (holon/audit/vacuity.py). It replays inhabitants on a
// compiled model, evaluates a SORT-site law's hit and the operands of its subtraction there, and runs the
// representative search. It decides nothing: holon/audit/vacuity.py reads its output.
//
// stdin: {
//   "module":   the compiled model (.mjs): the model a law record names, plus the probe definitions i21_e<k>
//               holon/audit/vacuity.py appends (one per expression the walk evaluates: a let, a require, a path
//               condition, an operand of the site's subtraction, an argument of a definition call),
//   "facts":    the facts the model is compiled from (actions and their inputs, for the action values),
//   "policy":   the search policy module: the facts' search hints (holon.gen.targetlib.hints_for), else
//               holon/js/policy_gen.mjs,
//   "state":    [the state field names], "tables": {table variable: oracle parameter} (in the order step takes them),
//   "plans":    {law id: {"hit": "hit_<x>", "actions": {action: {"inputs": [..], "steps": [step..]}},
//                         "defs": {definition: {"params": [..], "positions": [position..]}}}}
//                 step      {"k": "let", "name": v, "e": E} | {"k": "req", "e": E} | {"k": "hit", "positions": [..]}
//                 position  {"conds": [{"e": E, "pol": bool}..], "node": {"min": E, "sub": E}}
//                           | {"conds": [..], "call": {"def": f, "args": [E..]}}
//                 E         {"fn": "i21_e<k>", "args": [variable..]}
//   "jobs":     [{"id", "law": law id | null, "runs": [[action..]..], "act": action | null,
//                 "tabs": {table variable: [[k, v]..]}}],
//   "search":   null | {"laws": [law id..], "max_run_length": n, "max_states": n, "any": bool}
// }
// stdout: {"jobs": {id: {"replayed": bool, "failed_at": [run, step] | null, "hit": bool | null,
//                         "evaluations": [[minuend, subtrahend]..] | null}},
//          "search": {law id: {"run": [..], "act": {..}, "evaluations": [..]} | null}, "explored": n, "bound": ".."}
//
// The walk mirrors the ghost section of holon.sorts.sites (R8-R10): an action's guards in order up to the first
// failing require, its effects only when every require holds; at a hit, every position of the subtraction (or of a
// call of a definition reaching it) whose path conditions hold, in order. Values are the compiled model's own: every
// expression is evaluated by a probe definition generated from the facts by the model's own generator.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const facts = req.facts;
const ACTIONS = Object.fromEntries(facts.actions.map((a) => [a.name, a]));
const TABLES = Object.entries(req.tables || {});

const toList = (xs) => xs.reduceRight((t, h) => ({ $: "Con", head: h, tail: t }), { $: "Nil" });
function enc(v) {
  if (typeof v === "number") return BigInt(v);
  if (typeof v === "boolean") return v;
  if (Array.isArray(v)) return toList(v.map(enc));
  throw new Error("enc " + JSON.stringify(v));
}
function dec(x) {
  if (typeof x === "bigint") return Number(x);
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (x && (x.$ === "Nil" || x.$ === "Con")) { const o = []; for (let c = x; c.$ === "Con"; c = c.tail) o.push(dec(c.head)); return o; }
  if (x && typeof x === "object") { const o = {}; for (const [k, y] of Object.entries(x)) o[k] = k === "$" ? y : dec(y); return o; }
  throw new Error("dec " + String(x));
}
const big = (x) => (typeof x === "bigint" ? x.toString() : String(x));
function mkAct(a) {
  const spec = ACTIONS[a.op];
  if (!spec) throw new Error("no action " + a.op);
  const o = { $: "A_" + a.op };
  for (const [n] of spec.inputs) o[n] = enc(a[n]);
  return o;
}
function tabsOf(t) {
  return TABLES.map(([tv, p]) => toList(((t || {})[tv] || []).map(([k, v]) => ({ $: "HO_" + p, k: enc(k), v: enc(v) }))));
}
const EMPTY = tabsOf({});
const s0 = M.s0();
const stepJ = (a, s, tabs) => M.step(mkAct(a), s, ...tabs);

// ---------------------------------------------------------------- replay
function replay(run, tabs) {
  let s = s0;
  for (let i = 0; i < run.length; i++) {
    s = stepJ(run[i], s, tabs);
    if (!M.last_ok(s)) return { s, failedAt: i };
  }
  return { s, failedAt: null };
}

// ---------------------------------------------------------------- the walk
function call(E, env) {
  const f = M[E.fn];
  if (typeof f !== "function") throw new Error("no probe " + E.fn);
  return f(...E.args.map((v) => { if (!(v in env)) throw new Error(`${E.fn}: unbound ${v}`); return env[v]; }));
}
function positions(plan, ps, env, out) {
  for (const p of ps) {
    let live = true;
    for (const c of p.conds) if (call(c.e, env) !== c.pol) { live = false; break; }
    if (!live) continue;
    if (p.node) out.push([big(call(p.node.min, env)), big(call(p.node.sub, env))]);
    else {
      const d = plan.defs[p.call.def];
      const inner = { ...tabEnv(env) };
      d.params.forEach((n, i) => { inner[n] = call(p.call.args[i], env); });
      positions(plan, d.positions, inner, out);
    }
  }
}
function tabEnv(env) { const o = {}; for (const [tv] of TABLES) o[tv] = env[tv]; return o; }
// the evaluations of the site while act runs from s (null: the action has no hit of this site)
function walk(plan, act, s, tabs) {
  const ap = plan.actions[act.op];
  if (!ap) return [];
  const env = {};
  for (const f of req.state) env[f] = s[f];
  for (const n of ap.inputs) env[n] = enc(act[n]);
  TABLES.forEach(([tv], i) => { env[tv] = tabs[i]; });
  const out = [];
  for (const st of ap.steps) {
    if (st.k === "let") env[st.name] = call(st.e, env);
    else if (st.k === "req") { if (call(st.e, env) !== true) break; }
    else positions(plan, st.positions, env, out);
  }
  return out;
}
function hitOf(plan, act, s, tabs) { return M[plan.hit](mkAct(act), s, ...tabs) === true; }

// ---------------------------------------------------------------- jobs
const outJobs = {};
for (const j of req.jobs || []) {
  const tabs = tabsOf(j.tabs);
  let replayed = true, failedAt = null, last = s0;
  (j.runs || []).forEach((run, r) => {
    const x = replay(run, tabs);
    if (x.failedAt !== null && failedAt === null) { replayed = false; failedAt = [r, x.failedAt]; }
    last = x.s;
  });
  const o = { replayed, failed_at: failedAt, hit: null, evaluations: null };
  if (j.law && j.act) {
    const plan = req.plans[j.law];
    o.hit = hitOf(plan, j.act, last, tabs);
    o.evaluations = walk(plan, j.act, last, tabs);
  }
  outJobs[j.id] = o;
}

// ---------------------------------------------------------------- representative search
const res = { jobs: outJobs, search: null, explored: 0, bound: null };
if (req.search) {
  const { policyOf } = await import(pathToFileURL(req.policy).href);
  const S = req.search;
  const pending = new Set(S.laws);
  const found = Object.fromEntries(S.laws.map((l) => [l, null]));
  const canon = (v) => (Array.isArray(v) ? v.map(canon)
    : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v);
  const stateKey = (sj) => { const s = dec(sj); delete s.log; return JSON.stringify(canon(s)); };
  const policy = (sj) => policyOf(dec(sj), facts);
  // a state: check every pending law at every policy action there (policy order, laws in the given order)
  function check(node) {
    for (const a of policy(node.state)) {
      for (const law of S.laws) {
        if (!pending.has(law)) continue;
        const plan = req.plans[law];
        if (!plan.actions[a.op]) continue;
        if (!hitOf(plan, a, node.state, EMPTY)) continue;
        const ev = walk(plan, a, node.state, EMPTY);
        if (!ev.length) continue;
        if (!S.any && (node.trace.length === 0 || ev[0][1] === "0")) continue;
        found[law] = { run: node.trace, act: a, evaluations: ev };
        pending.delete(law);
      }
      if (!pending.size) return;
    }
  }
  const seen = new Set([stateKey(s0)]);
  let frontier = [{ trace: [], state: s0 }];
  let explored = 1;
  check(frontier[0]);
  let capped = false;
  for (let d = 0; d < S.max_run_length && pending.size && !capped; d++) {
    const next = [];
    for (const node of frontier) {
      for (const a of policy(node.state)) {
        const st = stepJ(a, node.state, EMPTY);
        if (!M.last_ok(st)) continue;
        const k = stateKey(st);
        if (seen.has(k)) continue;
        seen.add(k);
        const child = { trace: [...node.trace, a], state: st };
        explored++;
        check(child);
        if (!pending.size) break;
        next.push(child);
        if (explored >= S.max_states) { capped = true; break; }
      }
      if (!pending.size || capped) break;
    }
    frontier = next;
  }
  res.search = found;
  res.explored = explored;
  res.bound = `breadth-first over runs of at most ${S.max_run_length} successful policy actions from the initial ` +
    `state (states deduplicated, observation log excluded), every policy action at each state as the inhabitant's ` +
    `action; ${explored} states${capped ? `, capped at ${S.max_states}` : ""}`;
}
process.stdout.write(JSON.stringify(res));
