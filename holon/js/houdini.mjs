// Houdini-style strengthening proposals for Reach invariants (I8; whitepaper §10.3). Untrusted: it only
// proposes facts; a strengthening counts only inside a proof that Bend accepts, and it lives only in
// the proof file, never in a law.
//
// stdin: {"module": path, "facts": {...}, "hints": path | null, "budget": {...}}
// stdout: {"candidates": [{"field", "type", "value"}], "states": n, "bound": "..."}
//
// Candidates are the Nat and Bool state fields that hold the same value on every explored reachable
// state (BFS over successful policy actions from s0, deduplicated by state without the log), in the
// facts' field order.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const facts = req.facts;
const B = Object.assign({ prefixDepth: 3, maxPrefixes: 3000 }, facts.search || {}, req.budget || {});
const ACTIONS = Object.fromEntries(facts.actions.map((a) => [a.name, a]));
const { policyOf } = await import(req.hints ? pathToFileURL(req.hints).href : "./policy_gen.mjs");

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
const canon = (v) => (Array.isArray(v) ? v.map(canon)
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])])) : v);
const key = (v) => JSON.stringify(canon(v));
function mkAct(a) { const o = { $: "A_" + a.op }; for (const [n] of ACTIONS[a.op].inputs) o[n] = enc(a[n]); return o; }

const s0 = M.s0();
const seen = new Map();
const sk = (sj) => { const s = dec(sj); delete s.log; return [key(s), s]; };
{ const [k, s] = sk(s0); seen.set(k, s); }
let frontier = [s0];
for (let d = 0; d < B.prefixDepth && seen.size < B.maxPrefixes; d++) {
  const next = [];
  for (const st of frontier) {
    for (const a of policyOf(dec(st), facts)) {
      const s2 = M.step(mkAct(a), st);
      if (!M.last_ok(s2)) continue;
      const [k, s] = sk(s2);
      if (seen.has(k)) continue;
      seen.set(k, s); next.push(s2);
      if (seen.size >= B.maxPrefixes) break;
    }
    if (seen.size >= B.maxPrefixes) break;
  }
  frontier = next;
}
const states = [...seen.values()];
const candidates = [];
for (const [f, ty] of facts.state) {
  if (f === "log" || (ty !== "Nat" && ty !== "Bool")) continue;
  const vals = new Set(states.map((s) => JSON.stringify(s[f])));
  if (vals.size === 1) candidates.push({ field: f, type: ty, value: JSON.parse([...vals][0]) });
}
process.stdout.write(JSON.stringify({ candidates, states: states.length,
  bound: `BFS depth ${B.prefixDepth} over policy actions from s0 (<= ${B.maxPrefixes} states)` }));
