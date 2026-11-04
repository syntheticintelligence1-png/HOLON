// Discharge profiles on a compiled state-machine model (whitepaper Def 6.20, Prop 6.21, §10.7; BUILD_PLAN I32).
// Untrusted: it proposes outcomes, strategies and tables; a law holds only when Bend accepts its proof.
//
// stdin: {"module", "hints", "facts", "obligation", "schedule", "bounds", "task"}
//   obligation: {"target", "agent", "x_actions": [the actions X may call], "prefix": [move]}
//   lhs?:     {"module", "fn"} (the obligation's lhs, compiled by holon.gen.profile)
//   schedule:   {"H", "principals": [who]}
//   bounds:     {"moves", "dominance_moves", "persistent_moves", "horizon"}
// stdout (task "analyze"): {
//   "sstar_ok", "ax": [move], "ae": [move],
//   "outcomes": [[c, d, trace]], "frontier": [[c, d]], "persistent": [[c, d, trace]],
//   "tables": {"<c>_<d>": {"rows": [row], "ok": bool, "why"?: str}}, "dominance": {"ok", "worst"?: ..},
//   "deadlines": [dt], "abstraction": {"checked", "mismatches": [..]}}
//
// Moves come from the target's search hints (policyOf(state, facts)), as for holon/js/explore.mjs: X-moves are the
// candidates whose action X may call (who set to the agent) and the waits; E-moves are the candidates whose who is
// a schedule principal, never a wait. Every outcome is the model's: step, last_ok, cost, elapsed.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const { policyOf } = await import(pathToFileURL(req.hints).href);
const facts = req.facts;
const ob = req.obligation;
const SCH = req.schedule;
const B = req.bounds;
const ACT = Object.fromEntries(facts.actions.map((a) => [a.name, a]));
const XACT = new Set(ob.x_actions);
const EWHO = new Set(SCH.principals);

// ---------------------------------------------------------------- values
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
const cmpStr = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const byPoint = (a, b) => { const [ca, da] = a.split("_").map(Number), [cb, db] = b.split("_").map(Number); return ca - cb || da - db; };
const canon = (v) => (Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v);
const key = (v) => JSON.stringify(canon(v));
function act(m) {
  if (m.op === "wait") return { $: "A_wait", dt: BigInt(m.dt) };
  const o = { $: "A_" + m.op };
  for (const [n] of ACT[m.op].inputs) o[n] = enc(m[n]);
  return o;
}
function step(m, s) { return M.step(act(m), s); }
const ok = (s) => M.last_ok(s) === true;
// the model's observations are newest first: O_Ok, or O_Rev{code}
function code(s) { const l = dec(M.log_of(s))[0]; return l && l.$ === "O_Rev" ? l.code : 0; }
const unitCost = new Map();
function costOf1(m) { const k = key(m); if (!unitCost.has(k)) unitCost.set(k, Number(M.cost(toList([act(m)])))); return unitCost.get(k); }
const unitDelay = new Map();
function delayOf1(m) { const k = key(m); if (!unitDelay.has(k)) unitDelay.set(k, Number(M.elapsed(toList([act(m)])))); return unitDelay.get(k); }
function stateKey(s) { const d = dec(s); delete d.log; return key(d); }
const isTarget = (m) => m.op === ob.target && m.who === ob.agent;
// lhs, compiled by holon.gen.profile from the facts' guard into its own module (req.lhs), never written here
const K = req.lhs ? (await import(pathToFileURL(req.lhs.module).href)).default : null;
function lhs(s) { return K ? K[req.lhs.fn](s) === true : null; }

// ---------------------------------------------------------------- moves
function dedup(ms) { const seen = new Set(); return ms.filter((m) => { const k = key(m); if (seen.has(k)) return false; seen.add(k); return true; }); }
function xMoves(s) {
  const out = [];
  for (const c of policyOf(dec(s), facts)) {
    if (c.op === "wait") out.push({ op: "wait", dt: c.dt });
    else if (XACT.has(c.op)) out.push({ ...c, who: ob.agent });
  }
  return dedup(out);
}
function eMoves(s) { return dedup(policyOf(dec(s), facts).filter((c) => c.op !== "wait" && EWHO.has(c.who))); }

let sstar = M.s0();
let sstarOk = true;
for (const m of ob.prefix) { sstar = step(m, sstar); if (!ok(sstar)) sstarOk = false; }

// ---------------------------------------------------------------- Pareto
const dominatedBy = (labels, c, d) => labels.some(([c2, d2]) => c2 <= c && d2 <= d);
function pareto(pts) {
  const u = [...new Map(pts.map(([c, d]) => [`${c},${d}`, [c, d]])).values()];
  return u.filter(([c, d]) => !u.some(([c2, d2]) => c2 <= c && d2 <= d && (c2 < c || d2 < d)))
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

// Prop 6.21: bi-criteria label-correcting search from s*, breadth first by moves; a state's labels are its
// Pareto-minimal (cost, delay) pairs, a label dominated at the same state is dropped. done(s) decides whether a
// successful target move completes the occurrence (the persistent variant asks lhs false there).
function labelSearch(moves, done) {
  const outcomes = [];
  const labels = new Map();
  let level = [[sstar, [], 0, 0]];
  for (let depth = 0; depth < moves && level.length; depth++) {
    const next = [];
    for (const [s, xs, c0, d0] of level) {
      for (const m of xMoves(s)) {
        const s2 = step(m, s);
        if (!ok(s2)) continue;
        const xs2 = [...xs, m];
        const c = c0 + costOf1(m), d = d0 + delayOf1(m);
        if (isTarget(m)) { if (done(s2)) outcomes.push([c, d, xs2]); continue; }
        if (depth + 1 >= moves) continue;
        const k = stateKey(s2);
        const ls = labels.get(k) || [];
        if (dominatedBy(ls, c, d)) continue;
        labels.set(k, [...ls.filter(([c2, d2]) => !(c <= c2 && d <= d2)), [c, d]]);
        next.push([s2, xs2, c, d]);
      }
    }
    level = next;
  }
  // one outcome per (cost, delay): the first found (fewest moves, then the hints' order)
  const seen = new Set();
  return outcomes.filter(([c, d]) => { const k = `${c},${d}`; if (seen.has(k)) return false; seen.add(k); return true; })
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

// the closures: the hints' X-moves at every state reachable from s* by at most depth successful X-moves, and the
// hints' E-moves at every state reachable from s* by at most H E-moves (a reverting move leaves the state)
function xClosure(depth) {
  const out = [], seen = new Set(), states = new Set();
  let level = [sstar];
  for (let k = 0; k <= depth; k++) {
    const next = [];
    for (const s of level) {
      for (const m of xMoves(s)) {
        const km = key(m);
        if (!seen.has(km)) { seen.add(km); out.push(m); }
        if (k < depth && m.op !== ob.target) {
          const s2 = step(m, s);
          if (!ok(s2)) continue;
          const ks = stateKey(s2);
          if (states.has(ks)) continue;
          states.add(ks);
          next.push(s2);
        }
      }
    }
    level = next;
  }
  return out;
}
function eClosure(H) {
  const out = [], seen = new Set();
  let level = [sstar];
  for (let k = 0; k <= H; k++) {
    const next = [];
    for (const s of level) for (const m of eMoves(s)) {
      const km = key(m);
      if (!seen.has(km)) { seen.add(km); out.push(m); }
      if (k < H) next.push(step(m, s));
    }
    level = next;
  }
  return out;
}

// ---------------------------------------------------------------- the game (§8.4: ∃ strategy ∀ schedule ≤ H)
// A schedule is at most H events (E-moves), each played before one of the strategy's turns, in order, at that
// turn's block time. The strategy's witness is a priority list P: at each turn it plays the first move of P that
// stays within the point's cost and delay and succeeds; a successful target move wins, a turn with no such move,
// or K turns without the target, loses. solve() decides the game exactly over the hints' moves (∃ table ∀ events,
// memoized by state), then looks for a priority list among the winning table's moves that wins every schedule;
// when the strategy side loses, adversary() records the environment's winning answers over the game's X-alphabet.
function seqsUpTo(h, n) {
  const out = [[]];
  let lv = [[]];
  for (let k = 0; k < h; k++) {
    const nx = [];
    for (const q of lv) for (let i = 0; i < n; i++) nx.push([...q, i]);
    out.push(...nx);
    lv = nx;
  }
  return out;
}
function* schedules(H, moves, n, prefix = []) {
  yield prefix;
  if (prefix.length === H) return;
  const t0 = prefix.length ? prefix[prefix.length - 1][0] : 0;
  for (let t = t0; t < moves; t++) for (let i = 0; i < n; i++) yield* schedules(H, moves, n, [...prefix, [t, i]]);
}
function greedyMove(P, s, c0, d0, c, d) {
  for (const m of P) {
    const c1 = c0 + costOf1(m), d1 = d0 + delayOf1(m);
    if (c1 > c || d1 > d) continue;
    const s2 = step(m, s);
    if (ok(s2)) return [m, s2, c1, d1];
  }
  return null;
}
// the greedy play of P against one schedule; rows (when given) collect (turn, events so far) -> move
function greedyPlay(P, ae, sched, moves, c, d, rows) {
  let s = sstar, c0 = 0, d0 = 0;
  const hist = [];
  for (let turn = 0; turn < moves; turn++) {
    for (const [t, i] of sched) if (t === turn) { s = step(ae[i], s); hist.push([t, i]); }
    const g = greedyMove(P, s, c0, d0, c, d);
    if (!g) return false;
    const [m, s2, c1, d1] = g;
    if (rows) {
      const rk = `${turn}|${key(hist)}`;
      if (!rows.has(rk)) rows.set(rk, { turn, hist: hist.map((x) => [...x]), move: m });
    }
    s = s2; c0 = c1; d0 = d1;
    if (isTarget(m)) return true;
  }
  return false;
}
function solve(c, d, plan, ae, H, moves) {
  const memo = new Map();
  const seqs = [0, 1, 2, 3, 4].map((h) => (h <= H ? seqsUpTo(h, ae.length) : []));
  let nodes = 0;
  function xturn(s, turn, h, c0, d0) {
    const mk = `${stateKey(s)}|${turn}|${h}|${c0}|${d0}`;
    if (memo.has(mk)) return memo.get(mk);
    let won = null;
    for (const m of dedup([...(turn < plan.length ? [plan[turn]] : []), ...xMoves(s)])) {
      nodes++;
      const c1 = c0 + costOf1(m), d1 = d0 + delayOf1(m);
      if (c1 > c || d1 > d) continue;
      const s2 = step(m, s);
      if (!ok(s2)) continue;
      if (isTarget(m)) { won = m; break; }
      if (turn + 1 < moves && envturn(s2, turn + 1, h, c1, d1)) { won = m; break; }
    }
    memo.set(mk, won);
    return won;
  }
  function envturn(s, turn, h, c0, d0) {
    for (const q of seqs[h]) {
      let s2 = s;
      for (const i of q) s2 = step(ae[i], s2);
      if (!xturn(s2, turn, h - q.length, c0, d0)) return false;
    }
    return true;
  }
  if (!envturn(sstar, 0, H, 0, 0)) return { robust: false, nodes };
  // the winning table's moves, in first use (by turn, then schedule order), as candidates for P
  const used = [];
  for (const sched of schedules(H, moves, ae.length)) {
    let s = sstar, c0 = 0, d0 = 0, h = H;
    for (let turn = 0; turn < moves; turn++) {
      for (const [t, i] of sched) if (t === turn) { s = step(ae[i], s); h--; }
      const m = memo.get(`${stateKey(s)}|${turn}|${h}|${c0}|${d0}`);
      if (!m) break;
      used.push([turn, m]);
      s = step(m, s); c0 += costOf1(m); d0 += delayOf1(m);
      if (isTarget(m)) break;
    }
  }
  const firstUse = dedup(used.sort((a, b) => a[0] - b[0]).map(([, m]) => m));
  const targets = firstUse.filter((m) => isTarget(m));
  const others = firstUse.filter((m) => !isTarget(m) && m.op !== "wait");
  const waits = firstUse.filter((m) => m.op === "wait");
  const orders = [
    [...targets, ...others, ...[...waits].sort((a, b) => b.dt - a.dt)],
    [...targets, ...others, ...[...waits].sort((a, b) => a.dt - b.dt)],
    firstUse,
  ];
  for (const P of orders) {
    let all = true;
    for (const sched of schedules(H, moves, ae.length)) if (!greedyPlay(P, ae, sched, moves, c, d, null)) { all = false; break; }
    if (!all) continue;
    const rows = new Map();
    for (const sched of schedules(H, moves, ae.length)) greedyPlay(P, ae, sched, moves, c, d, rows);
    const list = [...rows.values()].sort((a, b) => a.turn - b.turn || cmpStr(key(a.hist), key(b.hist)));
    return { robust: true, policy: P, rows: list, nodes };
  }
  return { robust: true, policy: null, rows: [], nodes, why: "a winning table exists, but no priority list of its moves wins every schedule" };
}
// the bounded game's X-alphabet: the hints' X-moves at every decision state the game can reach (every event
// sequence the budget allows before each turn, every successful X-move within the point's cost and delay)
function gameAlphabet(c, d, ae, H, moves) {
  const out = [], seen = new Set(), nodes = new Set();
  const seqs = [0, 1, 2, 3, 4].map((h) => (h <= H ? seqsUpTo(h, ae.length) : []));
  let level = [[sstar, H, 0, 0]];
  for (let turn = 0; turn < moves && level.length; turn++) {
    const next = [];
    for (const [s, h, c0, d0] of level) {
      for (const q of seqs[h]) {
        let s2 = s;
        for (const i of q) s2 = step(ae[i], s2);
        for (const m of xMoves(s2)) {
          const km = key(m);
          if (!seen.has(km)) { seen.add(km); out.push(m); }
          const c1 = c0 + costOf1(m), d1 = d0 + delayOf1(m);
          if (c1 > c || d1 > d || isTarget(m) || turn + 1 >= moves) continue;
          const s3 = step(m, s2);
          if (!ok(s3)) continue;
          const nk = `${stateKey(s3)}|${h - q.length}|${c1}|${d1}`;
          if (nodes.has(nk)) continue;
          nodes.add(nk);
          next.push([s3, h - q.length, c1, d1]);
        }
      }
    }
    level = next;
  }
  return out;
}
// the environment's winning answers: before each turn, the event sequence it plays after X's moves so far (their
// indices in the game alphabet ax); every X-move of ax then loses (reverts, leaves the budget, or leads on to a
// turn the environment answers again), and no target move succeeds
function adversary(c, d, ae, ax, H, moves) {
  const seqs = [0, 1, 2, 3, 4].map((h) => (h <= H ? seqsUpTo(h, ae.length) : []));
  const answers = new Map();
  function envWins(s, turn, h, c0, d0, xh) {
    for (const q of seqs[h]) {
      let s2 = s;
      for (const i of q) s2 = step(ae[i], s2);
      if (xLoses(s2, turn, h - q.length, c0, d0, xh)) { answers.set(key(xh), { xhist: [...xh], events: q }); return true; }
    }
    return false;
  }
  function xLoses(s, turn, h, c0, d0, xh) {
    for (let i = 0; i < ax.length; i++) {
      const m = ax[i];
      const c1 = c0 + costOf1(m), d1 = d0 + delayOf1(m);
      if (c1 > c || d1 > d) continue;
      const s2 = step(m, s);
      if (!ok(s2)) continue;
      if (isTarget(m)) return false;
      if (turn + 1 >= moves) continue;
      if (!envWins(s2, turn + 1, h, c1, d1, [...xh, i])) return false;
    }
    return true;
  }
  if (!envWins(sstar, 0, H, 0, 0, [])) return null;
  return [...answers.values()].sort((a, b) => a.xhist.length - b.xhist.length || cmpStr(key(a.xhist), key(b.xhist)));
}

// the robust frontier: the Pareto-minimal outcomes some priority list wins against every schedule (each outcome of
// the one-occurrence search not dominated by one already found, in (cost, delay) order, decided by solve())
function robustFrontier(outcomes, ae, H, moves) {
  const pts = [...new Map(outcomes.map(([c, d, tr]) => [`${c},${d}`, [c, d, tr]])).values()]
    .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const found = [];
  for (const [c, d, tr] of pts) {
    if (found.some(([c2, d2]) => c2 <= c && d2 <= d)) continue;
    const r = solve(c, d, tr, ae, H, moves);
    if (r.robust && r.policy) found.push([c, d, r.policy]);
  }
  return found.filter(([c, d]) => !found.some(([c2, d2]) => c2 <= c && d2 <= d && (c2 < c || d2 < d)));
}

// ---------------------------------------------------------------- bounded dominance (∀ form)
// every sequence of at most `moves` moves over ax from s*, each succeeding, the last a successful target move,
// has cost >= gc or delay >= gd for every gap (gc, gd): a branch is cut once every gap is met (costs never fall)
function dominance(ax, gaps, moves) {
  let checked = 0;
  const bad = [];
  const met = (c, d) => gaps.every(([gc, gd]) => c >= gc || d >= gd);
  function go(s, c0, d0, depth, xs) {
    for (const m of ax) {
      const c = c0 + costOf1(m), d = d0 + delayOf1(m);
      if (met(c, d)) continue;
      const s2 = step(m, s);
      checked++;
      if (!ok(s2)) continue;
      if (isTarget(m)) { if (bad.length < 3) bad.push([c, d, [...xs, m]]); continue; }
      if (depth + 1 < moves) go(s2, c, d, depth + 1, [...xs, m]);
    }
  }
  go(sstar, 0, 0, 0, []);
  return { ok: bad.length === 0, checked, bad };
}

// ---------------------------------------------------------------- the time abstraction
function abstraction(moves, horizon) {
  const dts = xMoves(sstar).filter((m) => m.op === "wait").map((m) => m.dt).sort((a, b) => a - b);
  const rep = (dt) => [0, ...dts].filter((x) => x <= dt).pop();
  const at = (dt) => (dt === 0 ? sstar : step({ op: "wait", dt }, sstar));
  let checked = 0;
  const mismatches = [];
  for (let dt = 0; dt <= horizon; dt++) {
    const a = at(dt), b = at(rep(dt));
    for (const m of moves) {
      checked++;
      const ca = (() => { const s2 = step(m, a); return ok(s2) ? 0 : code(s2); })();
      const cb = (() => { const s2 = step(m, b); return ok(s2) ? 0 : code(s2); })();
      if (ca !== cb && mismatches.length < 10) mismatches.push({ dt, rep: rep(dt), move: m, codes: [ca, cb] });
    }
  }
  return { deadlines: dts, checked, mismatches };
}

// ---------------------------------------------------------------- analyze
const out = { sstar_ok: sstarOk };
if (req.task === "analyze") {
  const outcomes = labelSearch(B.moves, () => true);
  const frontier = pareto(outcomes.map(([c, d]) => [c, d]));
  const persistent = labelSearch(B.persistent_moves, (s) => lhs(s) === false);
  const ae = eClosure(SCH.H);
  const ax = xClosure(B.dominance_moves - 1);
  const points = {};
  for (const [c, d] of frontier) {
    const plan = outcomes.find(([c2, d2]) => c2 === c && d2 === d)[2];
    const r = solve(c, d, plan, ae, SCH.H, B.moves);
    r.plan = plan;
    r.ax = gameAlphabet(c, d, ae, SCH.H, B.moves);
    if (r.robust && r.policy) {
      const ix = new Map(r.ax.map((m, i) => [key(m), i]));
      r.policy_ix = r.policy.map((m) => ix.get(key(m)));
      if (r.policy_ix.some((i) => i === undefined)) { r.policy_ix = null; r.why = "a policy move lies outside the game alphabet"; }
    }
    if (!r.robust) r.adversary = adversary(c, d, ae, r.ax, SCH.H, B.moves);
    points[`${c}_${d}`] = r;
  }
  // the gaps of the staircase (points by cost, c_1 < .. < c_k, d_1 > .. > d_k): (c_1, INF) if c_1 > 0, then
  // (c_{i+1}, d_i), then (INF, d_k) if d_k > 0; an outcome is below the staircase iff it misses a gap
  const INF = 1000000000;
  const gaps = [];
  if (frontier.length) {
    if (frontier[0][0] > 0) gaps.push([frontier[0][0], INF]);
    for (let i = 0; i + 1 < frontier.length; i++) gaps.push([frontier[i + 1][0], frontier[i][1]]);
    if (frontier[frontier.length - 1][1] > 0) gaps.push([INF, frontier[frontier.length - 1][1]]);
  }
  out.outcomes = outcomes;
  out.frontier = frontier;
  out.persistent = persistent;
  out.ae = ae;
  out.ax = ax;
  out.points = points;
  out.robust_frontier = robustFrontier(outcomes, ae, SCH.H, B.moves);
  out.gaps = gaps;
  out.dominance = dominance(ax, gaps, B.dominance_moves);
  const absMoves = dedup([...ax, ...ae, ...Object.keys(points).sort(byPoint).flatMap((k) => points[k].ax)]
    .filter((m) => m.op !== "wait"));
  const abs = abstraction(absMoves, B.horizon);
  out.deadlines = abs.deadlines;
  out.abstraction = { checked: abs.checked, mismatches: abs.mismatches };
  out.abs_moves = absMoves;
}
process.stdout.write(JSON.stringify(out));
