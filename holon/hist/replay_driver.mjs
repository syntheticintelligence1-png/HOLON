// replay_driver.mjs — the ONLY process boundary for the S6 historical replay.
// Loads the COMPILED generated models (M0 header codec + M1 machine), evaluates
// them, and computes keccak/sha256 for oracle-side comparison. No transition
// logic is reimplemented here; calls go straight to the compiled artifacts.
//
// The two compiled artifacts use different Nat encodings (verified against
// holon/js/eval.mjs and holon/js/machine.mjs):
//   hdr jobs  (gen/M0 model): Nat = JS number; Maybe = {$some:v}/null JSON side
//   mach jobs (gen/M1 model): Nat = BigInt;   Maybe/other ctors decoded as {$:..}
//
// protocol: line-delimited JSON on stdin/stdout.
// request  line: {"header_module": <path>|null, "machine_module": <path>|null, "jobs": [...]}
//   (module paths only needed on the first line; they are cached)
// response line: {"results": [<result>..]} same order. Errors -> {"error": msg} per job.
// job kinds:
//   {"kind":"hdr",   "fn":<name>, "bytes":[n..]}          header model, Bytes arg
//   {"kind":"hdr",   "fn":<name>, "hdr":{cell:byte}}      header model, Hdr arg
//   {"kind":"mach",  "fn":<name>, "args":[<val>..]}       machine model
//   {"kind":"keccak","data":"0x.."}                       keccak256 hex
//   {"kind":"sha256","data":"0x.."}                       sha256 hex
import { createHash } from "node:crypto";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

// ---------- keccak-256 (pure JS, BigInt lanes; keccak pad, NOT sha3) ----------
const RC = [
  0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
  0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
  0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
  0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
  0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
  0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n,
];
const ROT = [
  [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
  [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
];
const M64 = (1n << 64n) - 1n;
function rol(x, n) {
  n = BigInt(n) % 64n;
  if (n === 0n) return x;
  return ((x << n) | (x >> (64n - n))) & M64;
}
function keccakF(st) {
  for (let r = 0; r < 24; r++) {
    const c = [], d = [], b = new Array(25).fill(0n);
    for (let x = 0; x < 5; x++) c[x] = st[x] ^ st[x + 5] ^ st[x + 10] ^ st[x + 15] ^ st[x + 20];
    for (let x = 0; x < 5; x++) d[x] = c[(x + 4) % 5] ^ rol(c[(x + 1) % 5], 1);
    for (let x = 0; x < 5; x++) for (let y = 0; y < 5; y++) st[x + 5 * y] ^= d[x];
    for (let x = 0; x < 5; x++)
      for (let y = 0; y < 5; y++)
        b[y + 5 * ((2 * x + 3 * y) % 5)] = rol(st[x + 5 * y], ROT[x][y]);
    for (let x = 0; x < 5; x++)
      for (let y = 0; y < 5; y++)
        st[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y]);
    st[0] ^= RC[r];
  }
}
export function keccak256(data) {
  const rate = 136;
  const st = new Array(25).fill(0n);
  const padLen = rate - (data.length % rate);
  const buf = Buffer.concat([Buffer.from(data), Buffer.alloc(padLen)]);
  buf[data.length] = 0x01;
  buf[buf.length - 1] |= 0x80;
  for (let off = 0; off < buf.length; off += rate) {
    for (let i = 0; i < rate / 8; i++) {
      let lane = 0n;
      for (let j = 7; j >= 0; j--) lane = (lane << 8n) | BigInt(buf[off + 8 * i + j]);
      st[i] ^= lane;
    }
    keccakF(st);
  }
  const out = Buffer.alloc(32);
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 8; j++) out[8 * i + j] = Number((st[i] >> (8n * BigInt(j))) & 0xffn);
  return out;
}

// ---------- JSON <-> bend values ----------
// kind selects the encoding: "hdr" mirrors holon/js/eval.mjs (numbers, $some,
// null, $hdr), "mach" mirrors holon/js/machine.mjs (BigInt, generic ctors).
function enc(v, kind) {
  if (v === null) return kind === "hdr" ? { $: "None" } : { $: "None" };
  if (typeof v === "number" || typeof v === "bigint")
    return kind === "mach" ? BigInt(v) : v;
  if (typeof v === "boolean") return v;
  if (Array.isArray(v)) {
    let l = { $: "Nil" };
    for (let i = v.length - 1; i >= 0; i--) l = { $: "Con", head: enc(v[i], kind), tail: l };
    return l;
  }
  if (v && typeof v === "object") {
    if (kind === "hdr" && v.$hdr && typeof v.$hdr === "object") {
      const o = {};
      for (const k of Object.keys(v.$hdr)) o[k] = v.$hdr[k];
      return { $: "Hdr", ...o };
    }
    if (v.$some !== undefined) return { $: "Some", value: enc(v.$some, kind) };
    if (typeof v.$ === "string") {
      const o = {};
      for (const k of Object.keys(v)) if (k !== "$") o[k] = enc(v[k], kind);
      return { $: v.$, ...o };
    }
  }
  throw new Error("cannot encode: " + JSON.stringify(v));
}
function dec(x, kind) {
  if (typeof x === "bigint") return x <= 9007199254740991n ? Number(x) : x.toString();
  if (typeof x === "number" || typeof x === "boolean") return x;
  if (x === null || x === undefined) return x;
  if (typeof x === "object") {
    if (x.$ === "Nil") return [];
    if (x.$ === "Con") {
      const out = [];
      for (let c = x; c && c.$ === "Con"; c = c.tail) out.push(dec(c.head, kind));
      return out;
    }
    if (x.$ === "True") return true;
    if (x.$ === "False") return false;
    if (x.$ === "None") return kind === "hdr" ? null : { $: "None" };
    if (x.$ === "Some")
      return kind === "hdr" ? { $some: dec(x.value, kind) } : { $: "Some", value: dec(x.value, kind) };
    const o = { $: x.$ };
    for (const k of Object.keys(x)) if (k !== "$") o[k] = dec(x[k], kind);
    return o;
  }
  return x;
}

function hexToBytes(h) {
  h = h.startsWith("0x") ? h.slice(2) : h;
  if (h === "") return [];
  const b = [];
  for (let i = 0; i < h.length; i += 2) b.push(parseInt(h.slice(i, i + 2), 16));
  return b;
}
function bytesToHex(b) {
  return "0x" + b.map((n) => Number(n).toString(16).padStart(2, "0")).join("");
}

let HM = null;
let MM = null;
async function runBatch(req) {
  if (req.header_module) HM = (await import(pathToFileURL(req.header_module).href)).default;
  if (req.machine_module) MM = (await import(pathToFileURL(req.machine_module).href)).default;
  return req.jobs.map((job) => {
    try {
      if (job.kind === "keccak") return bytesToHex([...keccak256(Buffer.from(hexToBytes(job.data)))]);
      if (job.kind === "sha256")
        return "0x" + createHash("sha256").update(Buffer.from(hexToBytes(job.data))).digest("hex");
      if (job.kind === "hdr") {
        const fn = HM[job.fn];
        if (typeof fn !== "function") throw new Error("header model has no fn " + job.fn);
        if (job.bytes !== undefined) return dec(fn(enc(job.bytes, "hdr")), "hdr");
        if (job.hdr !== undefined) return dec(fn(enc({ $hdr: job.hdr }, "hdr")), "hdr");
        throw new Error("hdr job needs bytes or hdr");
      }
      if (job.kind === "mach") {
        const fn = MM[job.fn];
        if (typeof fn !== "function") throw new Error("machine model has no fn " + job.fn);
        const args = (job.args || []).map((a) => enc(a, "mach"));
        return dec(fn(...args), "mach");
      }
      throw new Error("unknown job kind " + job.kind);
    } catch (e) {
      return { error: String(e && e.message ? e.message : e) };
    }
  });
}

const rl = createInterface({ input: process.stdin, terminal: false });
for await (const line of rl) {
  if (!line.trim()) continue;
  let out;
  try {
    out = { results: await runBatch(JSON.parse(line)) };
  } catch (e) {
    out = { error: String(e && e.message ? e.message : e) };
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}
