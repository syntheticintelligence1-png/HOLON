// I32 prereg instrument (tests_m3/_i32.py drives it): the T32 obligation evaluated on the compiled M1 machine,
// written without holon/js. Every outcome is the model's (M.step, M.last_ok, M.cost, M.elapsed); the M1 search hints
// (spec/M1/policy_hints.mjs, a target input) only propose moves, as spec/M3/lib/disch_profile.json says.
//
// stdin: {"module", "hints", "facts", "sidecar", "task", ...task inputs}
//   task "sstar":      {}                      -> {"ok", "reasons": {n: reason}}  (commitBatch at s* for n = 0..3)
//   task "frontier":   {"moves"}               -> {"outcomes": [[c, d, trace]], "frontier": [[c, d]]}
//   task "outcomes":   {"moves"}               -> {"outcomes": [[c, d]]}  (exhaustive, no pruning)
//   task "persistent": {"moves"}               -> {"frontier": [[c, d]], "outcomes": [[c, d, trace]]}
//   task "check":      {"table", "ax", "ae", "H", "moves", "cost", "delay"} -> {"schedules", "failures": [..]}
//   task "alphabet":   {"H"}                   -> {"ae": [move]}  (the E-moves at s* and every state H E-moves reach)
//   task "abstraction": {"ax", "ae", "horizon"} -> {"checked", "mismatches": [..]}
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const { policyOf } = await import(pathToFileURL(req.hints).href);
const facts = req.facts;
const side = req.sidecar;
const ob = side.obligations[0];
const ACT = Object.fromEntries(facts.actions.map((a) => [a.name, a]));
const XP = new Set([ob.class.principal, "anyone"]);
const EP = new Set(side.schedule.principals);

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
function act(m) {
  if (m.op === "wait") return { $: "A_wait", dt: BigInt(m.dt) };
  const o = { $: "A_" + m.op };
  for (const [n] of ACT[m.op].inputs) o[n] = enc(m[n]);
  return o;
}
const canon = (v) => (Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v);
const key = (v) => JSON.stringify(canon(v));
const step = (m, s) => M.step(act(m), s);
const ok = (s) => M.last_ok(s) === true;
const costOf = (xs) => Number(M.cost(toList(xs.map(act))));
const delayOf = (xs) => Number(M.elapsed(toList(xs.map(act))));
// the model logs newest first (O_Ok, or O_Rev{code})
function lastReason(s) { const d = dec(s); const l = d.log[0]; return l && l.$ === "O_Rev" ? l.code : 0; }
function stateKey(s) { const d = dec(s); delete d.log; return key(d); }
const isTarget = (m) => m.op === ob.target && m.who === ob.agent;

let sstar = M.s0();
for (const m of ob.prefix) {
  sstar = step(m, sstar);
  if (!ok(sstar)) throw new Error("the prefix fails at " + JSON.stringify(m));
}

function dedup(ms) { const seen = new Set(); return ms.filter((m) => { const k = key(m); if (seen.has(k)) return false; seen.add(k); return true; }); }
function xMoves(s) {
  const out = [];
  for (const c of policyOf(dec(s), facts)) {
    if (c.op === "wait") out.push({ op: "wait", dt: c.dt });
    else if (ACT[c.op] && XP.has(ACT[c.op].principal)) out.push({ ...c, who: ob.agent });
  }
  return dedup(out);
}
function eMoves(s) {
  return dedup(policyOf(dec(s), facts).filter((c) => c.op !== "wait" && EP.has(c.who)));
}
const dominated = (labels, c, d) => labels.some(([c2, d2]) => c2 <= c && d2 <= d);
function pareto(outs) {
  const pts = [...new Map(outs.map(([c, d]) => [`${c},${d}`, [c, d]])).values()];
  return pts.filter(([c, d]) => !pts.some(([c2, d2]) => (c2 <= c && d2 <= d) && (c2 < c || d2 < d)))
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

// one occurrence: the agent's moves from s, at most `moves`, ending with a successful target move.
// done(s, xs) decides whether a successful target move completes the obligation (persistent: kappa false after it)
function search(s0, moves, prune, done) {
  const outcomes = [];
  const labels = new Map();
  let level = [[s0, []]];
  for (let depth = 0; depth < moves && level.length; depth++) {
    const next = [];
    for (const [s, xs] of level) {
      for (const m of xMoves(s)) {
        const s2 = step(m, s);
        if (!ok(s2)) continue;
        const xs2 = [...xs, m];
        const c = costOf(xs2), d = delayOf(xs2);
        if (isTarget(m)) { if (done(s2, xs2)) outcomes.push([c, d, xs2]); continue; }
        if (depth + 1 >= moves) continue;
        if (prune) {
          const k = stateKey(s2);
          const ls = labels.get(k) || [];
          if (dominated(ls, c, d)) continue;
          labels.set(k, [...ls.filter(([c2, d2]) => !(c <= c2 && d <= d2)), [c, d]]);
        }
        next.push([s2, xs2]);
      }
    }
    level = next;
  }
  return outcomes;
}

// kappa on a decoded state, as the facts define it: enq_first(qpend, qlen, enq, t) + D < t (spec/M1/facts defs)
function kappa(s) {
  const d = dec(s);
  const ef = d.qpend < d.qlen && d.enq[d.qpend] !== 0 ? d.enq[d.qpend] : d.t;
  return ef + d.D < d.t;
}

function play(table, ax, ae, sched, moves) {
  let s = sstar;
  const xs = [];
  const hist = [];
  for (let turn = 0; turn < moves; turn++) {
    for (const [t, mv] of sched) if (t === turn) { s = step(ae[mv], s); hist.push([t, mv]); }
    const row = table.find((r) => r.turn === turn && key(r.hist) === key(hist));
    if (!row) return { ok: false, why: `no row at turn ${turn} for ${key(hist)}` };
    const m = ax[row.move];
    s = step(m, s);
    if (!ok(s)) return { ok: false, why: `turn ${turn}: ${key(m)} reverts (${lastReason(s)})` };
    xs.push(m);
    if (isTarget(m)) return { ok: true, cost: costOf(xs), delay: delayOf(xs) };
  }
  return { ok: false, why: "no target move" };
}
function* schedules(H, moves, n) {
  function* rec(prefix) {
    yield prefix;
    if (prefix.length === H) return;
    const t0 = prefix.length ? prefix[prefix.length - 1][0] : 0;
    for (let t = t0; t < moves; t++) for (let mv = 0; mv < n; mv++) yield* rec([...prefix, [t, mv]]);
  }
  yield* rec([]);
}

const out = {};
const task = req.task;
if (task === "sstar") {
  out.ok = true;
  out.reasons = {};
  const d = dec(sstar);
  const lci = d.lfi + d.win.length - 1;
  const last = d.win[d.win.length - 1];
  for (let n = 0; n <= 3; n++) {
    const s2 = step({ op: ob.target, who: ob.agent, ver: 1, parent: lci, n, lbn: lci + 1, prev: last.csr, post: 121, blobs: [17] }, sstar);
    out.reasons[n] = ok(s2) ? 0 : lastReason(s2);
  }
} else if (task === "frontier" || task === "outcomes") {
  const outs = search(sstar, req.moves, task === "frontier", () => true);
  out.outcomes = task === "frontier" ? outs : [...new Map(outs.map(([c, d]) => [`${c},${d}`, [c, d]])).values()];
  out.frontier = pareto(outs);
} else if (task === "persistent") {
  const outs = search(sstar, req.moves, true, (s) => !kappa(s));
  out.outcomes = outs;
  out.frontier = pareto(outs);
} else if (task === "check") {
  let n = 0;
  const failures = [];
  for (const sched of schedules(req.H, req.moves, req.ae.length)) {
    n++;
    const r = play(req.table, req.ax, req.ae, sched, req.moves);
    if (!r.ok || r.cost > req.cost || r.delay > req.delay) {
      if (failures.length < 5) failures.push({ schedule: sched, result: r });
    }
  }
  out.schedules = n;
  out.failures = failures;
} else if (task === "alphabet") {
  // the E-closure: the hints' E-moves at every state reachable from s* by at most H E-moves (breadth first, a
  // reverting move leaving the state as it is), first seen first
  const ae = [];
  const seen = new Set();
  let level = [sstar];
  for (let depth = 0; depth <= req.H; depth++) {
    const next = [];
    for (const s of level) {
      for (const m of eMoves(s)) {
        const k = key(m);
        if (!seen.has(k)) { seen.add(k); ae.push(m); }
        if (depth < req.H) next.push(step(m, s));
      }
    }
    level = next;
  }
  out.ae = ae;
} else if (task === "abstraction") {
  // a wait of dt is represented by the greatest hinted deadline <= dt (0: no wait), never longer
  const dts = xMoves(sstar).filter((m) => m.op === "wait").map((m) => m.dt).sort((a, b) => a - b);
  const rep = (dt) => [0, ...dts].filter((x) => x <= dt).pop();
  const mismatches = [];
  let checked = 0;
  const outcome = (s, m) => { const s2 = step(m, s); return ok(s2) ? 0 : lastReason(s2); };
  const base = (dt) => (dt === 0 ? sstar : step({ op: "wait", dt }, sstar));
  for (let dt = 0; dt <= req.horizon; dt++) {
    const r = rep(dt);
    const a = base(dt), b = base(r);
    for (const m of [...req.ax.filter((x) => x.op !== "wait"), ...req.ae]) {
      checked++;
      if (outcome(a, m) !== outcome(b, m) && mismatches.length < 10) mismatches.push({ dt, rep: r, move: m });
    }
  }
  out.checked = checked;
  out.mismatches = mismatches;
}
process.stdout.write(JSON.stringify(out));
