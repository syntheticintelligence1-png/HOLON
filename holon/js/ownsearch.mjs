// The bounded witness search of an OWN alias law over a compiled carrier model (holon.gen.ownheap; `bend model.bend
// -o model.mjs`), enumerating the candidates in exactly holon.gen.ownheap.candidates' order.
// stdin:  {"module": path, "fn": the model's Bool function of (trace, call), "stop_on": true | false,
//          "methods": [{"ctor", "nparams"}, ..] (the modelled methods, in candidates' order),
//          "writer": {"ctor", "nparams"}, "max_calls": N, "byte_lengths": [L, ..]}
// stdout: {"index": the first candidate whose value is stop_on, or null, "tried": candidates evaluated}
// Untrusted: it only proposes; the caller re-evaluates the candidate it names and Bend decides every status.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const req = JSON.parse(readFileSync(0, "utf8"));
const M = (await import(pathToFileURL(req.module).href)).default;
const fn = M[req.fn];
if (typeof fn !== "function") throw new Error("model has no function " + req.fn);
const lens = req.byte_lengths;

const bytesCache = new Map();
function bytes(n, v) {   // a byte list of length n, every byte v
  const k = n * 256 + v;
  if (!bytesCache.has(k)) {
    let t = { $: "Nil" };
    for (let i = 0; i < n; i++) t = { $: "Con", head: v, tail: t };
    bytesCache.set(k, t);
  }
  return bytesCache.get(k);
}

// itertools.product order: the last position varies fastest
function* product(sizes) {
  const idx = sizes.map(() => 0);
  if (sizes.some((s) => s === 0)) return;
  while (true) {
    yield idx.slice();
    let p = sizes.length - 1;
    while (p >= 0) {
      idx[p] += 1;
      if (idx[p] < sizes[p]) break;
      idx[p] = 0;
      p -= 1;
    }
    if (p < 0) return;
  }
}

function truthy(r) {
  return r === true || (r && r.$ === "True");
}

let tried = 0;
for (let depth = 0; depth < req.max_calls; depth++) {
  for (const names of product(Array(depth).fill(req.methods.length))) {
    const ms = names.map((i) => req.methods[i]).concat([req.writer]);
    // one shape per call: a tuple of byte lengths, one per byte-slice parameter
    const shapeSizes = ms.map((m) => lens.length ** m.nparams);
    for (const combo of product(shapeSizes)) {
      const calls = [];
      let arg = 0;
      for (let c = 0; c < ms.length; c++) {
        const m = ms[c];
        const call = { $: m.ctor };
        let s = combo[c];
        const ls = [];
        for (let j = 0; j < m.nparams; j++) {   // the shape's lengths, most significant first
          ls.unshift(lens[s % lens.length]);
          s = Math.floor(s / lens.length);
        }
        for (let j = 0; j < m.nparams; j++) {
          call["a" + j] = bytes(ls[j], (arg + 1) % 256);
          arg += 1;
        }
        calls.push(call);
      }
      let trace = { $: "Nil" };
      for (let c = calls.length - 2; c >= 0; c--) trace = { $: "Con", head: calls[c], tail: trace };
      const r = fn(trace, calls[calls.length - 1]);
      tried += 1;
      if (truthy(r) === req.stop_on) {
        process.stdout.write(JSON.stringify({ index: tried - 1, tried }));
        process.exit(0);
      }
    }
  }
}
process.stdout.write(JSON.stringify({ index: null, tried }));
