// Search hints for the Morph rollup machine (and the Go BatchData machine): candidate actions from a
// decoded state. Moved out of holon/js in I6: a target input chosen by the facts' milestone, loaded by
// holon/js/explore.mjs and policy.mjs. Untrusted heuristics (like a fuzzing dictionary): they only
// steer the search; a refutation still needs Bend to accept the counter-law.
export function policyOf(s, facts) {
  if (facts.policy === "batchdata") return batchdataPolicy(s);

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
  for (const idx of [...new Set([lci, s.lfi + 1])]) if (idx > s.lfi && idx <= lci) out.push({ op: "challengeState", who: 4, idx, value: 1 });
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
