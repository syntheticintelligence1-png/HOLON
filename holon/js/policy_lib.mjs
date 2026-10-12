// Search policy: candidate actions from a decoded state.
// Untrusted heuristics (like a fuzzing dictionary): they only steer the search.
//
// Selection: named policies (facts.policy) win; otherwise the Rollup hand
// policy applies only when the facts are the Rollup machine (a commitBatch
// action is present), with derivedPolicy appending candidates for ops the
// hand policy doesn't emit (composed machines). Machines without commitBatch
// get derivedPolicy alone.
export function policyOf(s, facts) {
  if (facts.policy === "batchdata") return batchdataPolicy(s);
  if (facts.policy === "l1num") return [{ op: "appendBlock", k: 1 }, { op: "appendBlock", k: 65535 }];

  const isRollup = (facts.actions || []).some((a) => a.name === "commitBatch");
  if (!isRollup) return derivedPolicy(s, facts);
  const out = rollupPolicy(s, facts);
  const covered = new Set(out.map((a) => a.op));
  for (const a of derivedPolicy(s, facts)) if (!covered.has(a.op)) out.push(a);
  return out;
}

// Diagnostics from derivedPolicy (e.g. actions skipped for an untyped input);
// the explore driver drains this into its search notes.
export const policyNotes = [];

const NAT_D_CAP = 12;
const CAND_CAP = 48;

// The Nat dictionary for a state: {0,1,2}, every Nat literal <= 2^16 in the
// facts' guards/effects/defs, every scalar Nat in the decoded state and its
// value+1, and each list length. Sorted, unique, capped at NAT_D_CAP small values.
function natDict(s, facts) {
  const D = new Set([0, 1, 2]);
  const lit = (x) => {
    if (typeof x === "number" && Number.isInteger(x) && x >= 0 && x <= 65536) D.add(x);
    else if (Array.isArray(x)) for (const y of x) lit(y);
    else if (x && typeof x === "object") for (const y of Object.values(x)) lit(y);
  };
  for (const a of facts.actions || []) { lit(a.guards); lit(a.effects); }
  for (const d of Object.values(facts.defs || {})) lit(d.body);
  const st = (x) => {
    if (typeof x === "number" && Number.isInteger(x) && x >= 0) { D.add(x); D.add(x + 1); }
    else if (Array.isArray(x)) { D.add(x.length); for (const y of x) st(y); }
    else if (x && typeof x === "object") for (const y of Object.values(x)) st(y);
  };
  st(s);
  return [...D].sort((x, y) => x - y).slice(0, NAT_D_CAP);
}

// Candidate values for one input type. Returns null when the type has no
// derivable values (caller records an "untyped input" note once).
function inputValues(ty, D) {
  if (ty === "Nat") return D;
  if (ty === "Bool") return [false, true];
  if (ty === "List<Nat>") return [[], ...D.slice(0, 3).map((d) => [d])];
  return null;
}

// Deterministic diagonal enumeration of an input product: tuples ordered by
// index-sum first, then lexicographically, capped at CAND_CAP.
function* product(lists, acc = [], i = 0) {
  if (i === lists.length) { yield acc; return; }
  for (const v of lists[i]) yield* product(lists, [...acc, v], i + 1);
}
function diagonal(lists) {
  const out = [];
  const k = lists.length;
  const maxSum = lists.reduce((t, l) => t + l.length - 1, 0);
  for (let sum = 0; sum <= maxSum && out.length < CAND_CAP; sum++) {
    const rec = (i, rem, acc) => {
      if (out.length >= CAND_CAP) return;
      if (i === k - 1) { if (rem < lists[i].length) out.push([...acc, lists[i][rem]]); return; }
      for (let j = 0; j <= rem && j < lists[i].length; j++) rec(i + 1, rem - j, [...acc, lists[i][j]]);
    };
    if (k) rec(0, sum, []);
  }
  return out;
}

// Facts-derived policy: candidate actions built from action input names/types
// alone. Deterministic and byte-stable: facts order, sorted dictionaries,
// diagonal product.
export function derivedPolicy(s, facts) {
  const D = natDict(s, facts);
  const out = [];
  for (const a of facts.actions || []) {
    const lists = [];
    let ok = true;
    for (const [n, ty] of a.inputs || []) {
      const l = inputValues(ty, D);
      if (l === null) { policyNotes.push(`untyped input: ${a.name}.${n} (${ty})`); ok = false; break; }
      lists.push(l);
    }
    if (!ok) continue;
    for (const combo of diagonal(lists)) {
      const o = { op: a.name };
      (a.inputs || []).forEach(([n], i) => { o[n] = combo[i]; });
      out.push(o);
    }
  }
  return out;
}

// Hand policy for the Morph rollup machine (a commitBatch action exists).
export function rollupPolicy(s, facts) {
  const lci = s.lfi + s.win.length - 1;
  const last = s.win[s.win.length - 1] || {};
  const fresh = 100 + 10 * (lci + 1) + (s.log.length % 7);
  const blob = 7 + 10 * (lci + 1);
  const room = Math.max(0, s.qlen - (last.tot || 0));
  const ns = room > 0 ? [0, 1] : [0];
  const P = facts.params;
  const out = [];
  for (const ver of [1, 2, 0]) for (const n of ns) {
    const blobsList = ver === 2 ? [[blob]] : [[blob], [], [P.Z]];
    for (const blobs of blobsList)
      out.push({ op: "commitBatch", who: 2, ver, parent: lci, n, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs });
  }
  for (const ver of [1, 2]) out.push({ op: "commitState", who: 2, ver, parent: lci, n: 0, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs: [] });
  for (const n of ns) out.push({ op: "commitBatchWithProof", who: 5, ver: 1, parent: lci, n, lbn: lci + 1, prev: last.csr || 0, post: fresh, blobs: [blob], proof: 1 });
  if (lci > s.lfi) out.push({ op: "revertBatch", who: 1, idx: lci, count: 1 });
  if (lci > s.lfi + 1) out.push({ op: "revertBatch", who: 1, idx: s.lfi + 1, count: lci - s.lfi });
  for (const idx of [...new Set([lci, s.lfi + 1])]) if (idx > s.lfi && idx <= lci) for (const who of s.chals) out.push({ op: "challengeState", who, idx, value: 1 });
  for (const a of facts.policy_extra || []) out.push({ ...a });
  out.push({ op: "proveState", who: 2, idx: s.bc, proof: 1 });
  out.push({ op: "finalizeBatch", who: 5, idx: s.lfi + 1 });
  out.push({ op: "setPause", who: 1, status: !s.paused });
  out.push({ op: "sendMessage", who: 5 });
  // time abstraction: wait exactly until the next relevant deadline (finalization, proof window, delay guard)
  const dts = new Set([1, s.W, s.W + 1, s.F, s.D + 1]);
  for (const e of s.win) if (e.bdf >= s.t) { dts.add(e.bdf - s.t); dts.add(e.bdf - s.t + 1); }
  const ch = s.chs[s.bc]; if (ch && s.inch) for (const d of [ch.s + s.W - s.t, ch.s + s.W - s.t + 1]) if (d > 0) dts.add(d);
  if (s.qpend < s.qlen) { const d = s.enq[s.qpend] + s.D + 1 - s.t; if (d > 0) dts.add(d); }
  dts.delete(0);
  for (const dt of [...dts].sort((x, y) => x - y)) out.push({ op: "wait", dt });
  return out;
}


// Go BatchData (OWN): Append 60-byte block contexts with small/empty/medium/large payloads; TxsPayloadV2.
function batchdataPolicy(s) {
  const k = (s.log.length % 200) + 1;
  // small 8-byte contexts first (they reach the same growth regimes with smaller kernel terms), then real 60-byte ones
  const out = [];
  for (const n of [8, 60]) {
    const ctx = Array(n).fill(k);
    for (const payload of [[k], [], Array(8).fill(k), Array(80).fill(k)]) out.push({ op: "append", bctx: ctx, payload });
  }
  out.push({ op: "txsPayloadV2" });
  return out;
}
