// CLI: candidate actions after a trace.  stdin {"module", "facts", "trace": [Act..]} -> stdout [Act..]
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
// target search hints (req.hints, from holon.gen.targetlib.hints_for) or the generic policy
const { policyOf } = await import(req.hints ? pathToFileURL(req.hints).href : "./policy_gen.mjs");
// req.oracles (M2+ models with oracle parameters, I12/I15): lookups answered by the sidecar instances
const { loadModel, tabsOf } = await import("./oracle_model.mjs");
const M = await loadModel(req.module, req.oracles || null);
const ACTIONS = Object.fromEntries(req.facts.actions.map((a) => [a.name, a]));
const enc = (v) => typeof v === "number" ? BigInt(v) : typeof v === "boolean" ? v
  : Array.isArray(v) ? v.reduceRight((t, h) => ({ $: "Con", head: enc(h), tail: t }), { $: "Nil" }) : v;
function dec(x) {
  if (typeof x === "bigint") return Number(x);
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (x && (x.$ === "Nil" || x.$ === "Con")) { const o = []; for (let c = x; c.$ === "Con"; c = c.tail) o.push(dec(c.head)); return o; }
  const o = {}; for (const [k, y] of Object.entries(x)) o[k] = k === "$" ? y : dec(y); return o;
}
let s = M.s0();
for (const a of req.trace) {
  const o = { $: "A_" + a.op };
  for (const [n] of ACTIONS[a.op].inputs) o[n] = enc(a[n]);
  s = M.step(o, s, ...tabsOf(req.oracles, "step"));
}
process.stdout.write(JSON.stringify(policyOf(dec(s), req.facts)));
