"""The compression oracle: HypZ and HypZ_len tested on the real codec (BUILD_PLAN I91 = I38c; whitepaper §8.5; the
contract is rules Z1-Z9 of the docstring of tests_m3/test_compress.py).

  python -m holon oracle compression --milestone M3 [--root DIR] [--check]

A model of a batch codec takes the compressor Enc and the decompressor Dec as uninterpreted parameters, under two
hypotheses: HypZ (forall x non-empty, k <= K. Dec(Enc x ++ 0^k) = x) and HypZ_len (|Enc x| is at most zstd's compress
bound of |x|). This module tests both, without a proof, on the target's real codec. The sidecar
spec/<M>/lib/compression.json (holon-compression/0.1) names the compressor, the decompressor, the blob pipeline between
them (the submitter's splitter and the field of its result that holds the blobs, the derivation's per-blob reader, the
capacity constant) and the fixed sample. A Go test generated from those names runs in a scratch copy of the source tree's
go.work modules (the tree is never written), and the result is results/<M>/compression_oracle.json: K, each hypothesis
"checked" (a test on the sample, not a proof) or "mismatch", the expansion of the sample's incompressible input at a
blob limit, and the empty payload's boundary.

Nothing here names a target: every package path, function, field, constant and module comes from the sidecar.
Exit 0 written (or --check equal); 1 --check differs; 2 a refused input (sidecar, Go document, source tree, toolchain);
3 the probe fails to build or run, or the sample's paddings do not sit on K's two sides.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR_VERSION = "holon-compression/0.1"
DOC_VERSION = "holon-compression-oracle/0.1"
KINDS = ("zero", "ramp", "stream")
CODEC_KEYS = ("enc", "dec", "split", "split_blobs", "retrieve", "capacity", "library")
EXPR = re.compile(r"^(?:(\d+)|C|C([+-])(\d+)|(\d+)\*C)$")
ID = re.compile(r"^(\S+)\.([A-Za-z_][A-Za-z0-9_]*)$")
FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEST_NAME = "TestHolonCompressionOracle"
TEST_FILE = "holon_compression_oracle_test.go"
FAIL_CAP = 10


class Refused(Exception):
    """A refused input (exit 2)."""


class ProbeError(Exception):
    """The probe does not build or run, or the sample is inconsistent with K (exit 3)."""


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/compression.json"


def results_rel(milestone: str) -> str:
    return f"results/{milestone}/compression_oracle.json"


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load(p: Path, what: str) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} {p}: unreadable ({type(e).__name__}: {e})") from e
    if not isinstance(d, dict):
        raise Refused(f"{what} {p}: not a JSON object")
    return d


def value(expr, c: int) -> int:
    """A sidecar expression (an integer, C, C-d, C+d or m*C) at capacity c."""
    m = EXPR.match(str(expr))
    if not m:
        raise Refused(f"not an expression over C: {expr!r}")
    if m.group(1) is not None:
        return int(m.group(1))
    if m.group(2) is not None:
        return c + int(m.group(3)) if m.group(2) == "+" else c - int(m.group(3))
    if m.group(4) is not None:
        return int(m.group(4)) * c
    return c


def split_id(fid: str) -> tuple[str, str]:
    m = ID.match(fid) if isinstance(fid, str) else None
    if not m:
        raise Refused(f"not a <package path>.<Name> id: {fid!r}")
    return m.group(1), m.group(2)


def load_sidecar(root: Path, milestone: str) -> dict:
    """The sidecar, checked against rule Z1 (Refused otherwise)."""
    sc = _load(root / sidecar_rel(milestone), "sidecar")
    if sc.get("compression_version") != SIDECAR_VERSION:
        raise Refused(f"{sidecar_rel(milestone)}: compression_version is not {SIDECAR_VERSION}")
    codec = sc.get("codec")
    if not isinstance(codec, dict) or set(codec) != set(CODEC_KEYS):
        raise Refused(f"{sidecar_rel(milestone)}: codec must hold exactly {list(CODEC_KEYS)}")
    for k in ("enc", "dec", "split", "retrieve", "capacity"):
        split_id(codec[k])
    if not isinstance(codec["split_blobs"], str) or not FIELD.match(codec["split_blobs"]):
        raise Refused("codec.split_blobs is not a field name")
    if not isinstance(codec["library"], str) or not codec["library"] or " " in codec["library"]:
        raise Refused("codec.library is not a module path")
    if not isinstance(sc.get("document"), str) or not isinstance(sc.get("probe_package"), str):
        raise Refused("document and probe_package must be strings")
    hyp = sc.get("hypotheses")
    if not isinstance(hyp, dict) or set(hyp) != {"HypZ", "HypZ_len"}:
        raise Refused("hypotheses must hold exactly HypZ and HypZ_len")
    for h in hyp.values():
        if not isinstance(h, dict) or not isinstance(h.get("statement"), str):
            raise Refused("every hypothesis needs a statement")
    if not EXPR.match(str(hyp["HypZ"].get("K"))):
        raise Refused("HypZ.K is not an expression over C")
    b = hyp["HypZ_len"].get("bound")
    if not isinstance(b, dict) or set(b) != {"shift", "small", "small_shift"} \
            or not all(isinstance(v, int) and v >= 0 for v in b.values()):
        raise Refused("HypZ_len.bound must hold the integers shift, small and small_shift")
    s = sc.get("sample")
    if not isinstance(s, dict) or not isinstance(s.get("seed"), str):
        raise Refused("sample.seed must be a string")
    kinds = s.get("kinds")
    if not isinstance(kinds, list) or not kinds or [k for k in KINDS if k in kinds] != kinds:
        raise Refused(f"sample.kinds must be a non-empty subset of {list(KINDS)}, in that order")
    for k in ("lengths", "paddings", "beyond"):
        if not isinstance(s.get(k), list) or not s[k] or not all(EXPR.match(str(e)) for e in s[k]):
            raise Refused(f"sample.{k} must be a non-empty list of expressions over C")
    e = s.get("expansion")
    if not isinstance(e, dict) or e.get("kind") not in kinds or not EXPR.match(str(e.get("limit"))) \
            or not isinstance(e.get("window"), int) or e["window"] < 1:
        raise Refused("sample.expansion must name a sample kind, a limit expression and a window >= 1")
    return sc


# ====================================================================== the probe (Z2)
GO_TEMPLATE = r'''package @PKG@_test

// Generated by the compression oracle (BUILD_PLAN I91, rule Z2 of the docstring of tests_m3/test_compress.py) from
// @SIDECAR@. It runs the codec the sidecar names on the sample it fixes and writes the outcomes as JSON.

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"testing"

@IMPORTS@
)

type hcoSample struct {
	Seed     string   `json:"seed"`
	Kinds    []string `json:"kinds"`
	Lengths  []string `json:"lengths"`
	Paddings []string `json:"paddings"`
	Beyond   []string `json:"beyond"`
	ExpKind  string   `json:"exp_kind"`
	ExpLimit string   `json:"exp_limit"`
	ExpWin   int      `json:"exp_window"`
}

func hcoAtoi(s string) int {
	v, err := strconv.Atoi(s)
	if err != nil || v < 0 {
		panic("not an expression over C: " + s)
	}
	return v
}

func hcoValue(e string, c int) int {
	switch {
	case e == "C":
		return c
	case strings.HasPrefix(e, "C-"):
		return c - hcoAtoi(e[2:])
	case strings.HasPrefix(e, "C+"):
		return c + hcoAtoi(e[2:])
	case strings.HasSuffix(e, "*C"):
		return hcoAtoi(e[:len(e)-2]) * c
	}
	return hcoAtoi(e)
}

func hcoValues(es []string, c int) []int {
	out := []int{}
	for _, e := range es {
		out = append(out, hcoValue(e, c))
	}
	return out
}

func hcoBytes(kind, seed string, n int) []byte {
	out := make([]byte, n)
	switch kind {
	case "zero":
	case "ramp":
		for i := range out {
			out[i] = byte(i % 256)
		}
	case "stream":
		var acc []byte
		for j := uint32(0); len(acc) < n; j++ {
			var be [4]byte
			binary.BigEndian.PutUint32(be[:], j)
			d := sha256.Sum256(append([]byte(seed), be[:]...))
			acc = append(acc, d[:]...)
		}
		copy(out, acc)
	default:
		panic("unknown kind " + kind)
	}
	return out
}

func hcoHex(b []byte) string {
	d := sha256.Sum256(b)
	return hex.EncodeToString(d[:])
}

func hcoErr(err error) string {
	m := err.Error()
	if len(m) > 200 {
		m = m[:200]
	}
	return "error: " + m
}

func hcoDec(in, want []byte) string {
	got, err := @DEC@(in)
	if err != nil {
		return hcoErr(err)
	}
	if !bytes.Equal(got, want) {
		return fmt.Sprintf("differs:%d", len(got))
	}
	return "ok"
}

func hcoZeros(b []byte) bool {
	for _, v := range b {
		if v != 0 {
			return false
		}
	}
	return true
}

func hcoSplit(c []byte, nb int) (int, []byte, error) {
	sc, err := @SPLIT@(c, nb)
	if err != nil {
		return 0, nil, fmt.Errorf("split: %w", err)
	}
	var p []byte
	for i := range sc.@FIELD@ {
		b := sc.@FIELD@[i]
		body, err := @RETRIEVE@(&b)
		if err != nil {
			return 0, nil, fmt.Errorf("retrieve: %w", err)
		}
		p = append(p, body...)
	}
	return len(sc.@FIELD@), p, nil
}

func hcoPadded(c []byte, k int) []byte {
	return append(append([]byte{}, c...), make([]byte, k)...)
}

func @TEST@(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_COMPRESSION_IN"))
	if err != nil {
		t.Fatal(err)
	}
	var in hcoSample
	if err := json.Unmarshal(raw, &in); err != nil {
		t.Fatal(err)
	}
	c := @CAPACITY@
	paddings, beyond := hcoValues(in.Paddings, c), hcoValues(in.Beyond, c)
	points := []map[string]any{}
	for _, kind := range in.Kinds {
		for _, n := range hcoValues(in.Lengths, c) {
			x := hcoBytes(kind, in.Seed, n)
			pt := map[string]any{"kind": kind, "n": n, "x_sha256": hcoHex(x)}
			enc, err := @ENC@(x)
			if err != nil {
				pt["enc_error"] = err.Error()
				points = append(points, pt)
				continue
			}
			pt["enc_len"], pt["enc_sha256"] = len(enc), hcoHex(enc)
			nb := (len(enc) + c - 1) / c
			if nb < 1 {
				nb = 1
			}
			if blobs, p, err := hcoSplit(enc, nb); err != nil {
				pt["pipeline"] = hcoErr(err)
			} else {
				pt["blobs"], pt["padded_len"] = blobs, len(p)
				pt["padded_ok"] = len(p) >= len(enc) && bytes.Equal(p[:len(enc)], enc) && hcoZeros(p[len(enc):])
				pt["pipeline"] = hcoDec(p, x)
			}
			pads, past := map[string]string{}, map[string]string{}
			for _, k := range paddings {
				pads[strconv.Itoa(k)] = hcoDec(hcoPadded(enc, k), x)
			}
			for _, k := range beyond {
				past[strconv.Itoa(k)] = hcoDec(hcoPadded(enc, k), x)
			}
			pt["paddings"], pt["beyond"] = pads, past
			points = append(points, pt)
		}
	}
	limit := hcoValue(in.ExpLimit, c)
	full := hcoBytes(in.ExpKind, in.Seed, limit)
	lens := [][2]int{}
	for n := limit - in.ExpWin + 1; n <= limit; n++ {
		enc, err := @ENC@(full[:n])
		if err != nil {
			t.Fatalf("expansion: enc of %d bytes: %v", n, err)
		}
		lens = append(lens, [2]int{n, len(enc)})
	}
	empty := map[string]any{}
	if enc, err := @ENC@([]byte{}); err != nil {
		empty["enc_error"] = err.Error()
	} else {
		empty["enc_len"], empty["enc_nil"] = len(enc), enc == nil
		empty["dec_empty"] = hcoDec(enc, []byte{})
		if blobs, p, err := hcoSplit(enc, 1); err != nil {
			empty["pipeline"] = map[string]any{"error": hcoErr(err)}
		} else {
			empty["pipeline"] = map[string]any{"blobs": blobs, "padded_len": len(p), "zero": hcoZeros(p),
				"dec": hcoDec(p, []byte{})}
		}
	}
	out, err := json.Marshal(map[string]any{"capacity": c, "points": points, "lens": lens, "empty": empty})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(os.Getenv("HOLON_COMPRESSION_OUT"), out, 0o644); err != nil {
		t.Fatal(err)
	}
}
'''


def go_text(sc: dict, pkg_name: str, sidecar: str) -> str:
    """The generated Go test of the external test package of the probe package (rule Z2)."""
    codec = sc["codec"]
    roles = ("enc", "dec", "split", "retrieve", "capacity")
    paths = sorted({split_id(codec[r])[0] for r in roles})
    alias = {p: f"hco{i}" for i, p in enumerate(paths)}
    ref = {}
    for r in roles:
        path, name = split_id(codec[r])
        ref[r] = f"{alias[path]}.{name}"
    imports = "\n".join(f'\t{alias[p]} "{p}"' for p in paths)
    text = GO_TEMPLATE
    for tok, val in (("@PKG@", pkg_name), ("@SIDECAR@", sidecar), ("@IMPORTS@", imports), ("@TEST@", TEST_NAME),
                     ("@ENC@", ref["enc"]), ("@DEC@", ref["dec"]), ("@SPLIT@", ref["split"]),
                     ("@RETRIEVE@", ref["retrieve"]), ("@CAPACITY@", ref["capacity"]),
                     ("@FIELD@", codec["split_blobs"])):
        text = text.replace(tok, val)
    return text


def run_probe(root: Path, sc: dict, doc: dict, sidecar: str) -> tuple[dict, str, str, str]:
    """(the probe's output, its command, the library's version, the go version token), run on a scratch copy of the
    source tree's go.work modules."""
    from ..frontends.go.extract import Refused as ExtractRefused
    from ..frontends.go.extract import check_go, go_env, make_workspace, resolve_src
    from ..goreplay import Refused as ReplayRefused
    from ..goreplay import _module_dir, _package_name
    try:
        cfg = _load(root / doc["extraction"]["config"]["path"], "extraction config")
        src = resolve_src(cfg, root)
        go, token = check_go(root)
    except ExtractRefused as e:
        raise Refused(str(e)) from e
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != doc["target"]["commit"]:
        raise Refused(f"{src} is at {head!r}, not at the Go document's commit {doc['target']['commit']}")
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise Refused(f"{src} has local changes: {dirty[:500]}")
    pkgs = {p["path"]: p["dir"] for p in doc["go"]["packages"]}
    if sc["probe_package"] not in pkgs:
        raise Refused(f"probe_package {sc['probe_package']} is not a package of {sc['document']}")
    s = sc["sample"]
    sample = {"seed": s["seed"], "kinds": s["kinds"], "lengths": s["lengths"], "paddings": s["paddings"],
              "beyond": s["beyond"], "exp_kind": s["expansion"]["kind"], "exp_limit": s["expansion"]["limit"],
              "exp_window": s["expansion"]["window"]}
    parent = Path(tempfile.mkdtemp(prefix="holon-compression-"))
    try:
        ws = parent / "src"
        ws.mkdir()
        try:
            make_workspace(src, ws)
            mod = _module_dir(ws, pkgs[sc["probe_package"]])
            pdir = ws / pkgs[sc["probe_package"]]
            pkg_name = _package_name(pdir)
        except (ExtractRefused, ReplayRefused) as e:
            raise Refused(str(e)) from e
        (pdir / TEST_FILE).write_text(go_text(sc, pkg_name, sidecar), encoding="utf-8")
        (parent / "in.json").write_text(json.dumps(sample), encoding="utf-8")
        env = go_env(GOTOOLCHAIN="local", HOLON_COMPRESSION_IN=str(parent / "in.json"),
                     HOLON_COMPRESSION_OUT=str(parent / "out.json"))
        rel = pdir.relative_to(mod).as_posix()
        cmd = ["go", "test", f"./{rel}", "-run", f"^{TEST_NAME}$", "-count=1", "-v"]
        p = subprocess.run([go] + cmd[1:], cwd=mod, env=env, capture_output=True, text=True, timeout=3600)
        if p.returncode != 0 or not (parent / "out.json").exists():
            raise ProbeError(f"the generated Go test failed (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
        out = json.loads((parent / "out.json").read_text(encoding="utf-8"))
        q = subprocess.run([go, "list", "-m", "-f", "{{.Version}}", sc["codec"]["library"]], cwd=mod,
                           env=go_env(GOTOOLCHAIN="local", GOWORK="off"), capture_output=True, text=True, timeout=600)
        version = q.stdout.strip()
        if q.returncode != 0 or not version:
            raise ProbeError(f"go list -m {sc['codec']['library']} failed: {(q.stdout + q.stderr)[-1000:]}")
        command = f"(cd {mod.relative_to(ws).as_posix()} && {' '.join(cmd)})"
        return out, command, version, token
    finally:
        shutil.rmtree(parent, ignore_errors=True)


# ====================================================================== the entries (Z3-Z7)
def cb(n: int, bound: dict) -> int:
    """zstd's compress bound with the sidecar's constants."""
    small = bound["small"]
    return n + (n >> bound["shift"]) + ((small - n) >> bound["small_shift"] if n < small else 0)


def _points(out: dict) -> list[dict]:
    pts = []
    for p in out["points"]:
        q = {"kind": p["kind"], "n": p["n"], "x_sha256": p["x_sha256"], "enc_error": p.get("enc_error"),
             "enc_len": p.get("enc_len"), "enc_sha256": p.get("enc_sha256"), "blobs": p.get("blobs"),
             "padded_len": p.get("padded_len"), "padded_ok": p.get("padded_ok"), "pipeline": p.get("pipeline"),
             "paddings": p.get("paddings"), "beyond": p.get("beyond")}
        q["padding"] = q["padded_len"] - q["enc_len"] if q["padded_len"] is not None else None
        pts.append(q)
    return pts


def hypz(sc: dict, points: list[dict], k_max: int, paddings: list[int]) -> dict:
    fails, decodes = [], 0
    for p in points:
        if p["enc_error"] is not None:
            fails.append({"kind": p["kind"], "n": p["n"], "k": "enc", "got": "error: " + p["enc_error"][:200]})
            continue
        for k, got in [("pipeline", p["pipeline"])] + [(k, p["paddings"][str(k)]) for k in paddings]:
            decodes += 1
            if got != "ok":
                fails.append({"kind": p["kind"], "n": p["n"], "k": k, "got": got})
    status = "mismatch" if fails else "checked"
    if fails:
        f = fails[0]
        detail = (f"mismatch: {len(fails)} failure(s) on the sample; the first: {f['kind']} bytes, n = {f['n']}, "
                  f"k = {f['k']}: {f['got']}")
    else:
        detail = (f"checked on the sample (a test, not a proof): at {len(points)} points the pipeline and every "
                  f"padding up to K = {k_max} gave x back ({decodes} decodes)")
    return {"statement": sc["hypotheses"]["HypZ"]["statement"], "K": k_max, "status": status, "detail": detail,
            "points": len(points), "decodes": decodes, "failures": fails[:FAIL_CAP]}


def hypz_len(sc: dict, points: list[dict]) -> dict:
    bound = sc["hypotheses"]["HypZ_len"]["bound"]
    fails, excess = [], None
    for p in points:
        if p["enc_error"] is not None:
            fails.append({"kind": p["kind"], "n": p["n"], "enc_len": None, "bound": cb(p["n"], bound)})
            continue
        e = p["enc_len"] - p["n"]
        excess = e if excess is None else max(excess, e)
        if p["enc_len"] > cb(p["n"], bound):
            fails.append({"kind": p["kind"], "n": p["n"], "enc_len": p["enc_len"], "bound": cb(p["n"], bound)})
    status = "mismatch" if fails else "checked"
    if fails:
        f = fails[0]
        detail = (f"mismatch: {len(fails)} point(s) over the bound; the first: {f['kind']} bytes, n = {f['n']}, "
                  f"|Enc x| = {f['enc_len']} > {f['bound']}")
    else:
        detail = (f"checked on the sample (a test, not a proof): |Enc x| <= CB(|x|) at {len(points)} points; the "
                  f"largest |Enc x| - |x| is {excess}")
    return {"statement": sc["hypotheses"]["HypZ_len"]["statement"], "status": status, "detail": detail,
            "points": len(points), "max_excess": excess, "failures": fails[:FAIL_CAP]}


def expansion(sc: dict, lens: list, limit: int) -> dict:
    by = {int(n): int(ln) for n, ln in lens}
    lo = limit - int(sc["sample"]["expansion"]["window"]) + 1
    over = sorted(n for n, ln in by.items() if ln > limit)
    return {"kind": sc["sample"]["expansion"]["kind"], "limit": limit, "window": [lo, limit],
            "enc_len_at_limit": by[limit], "overhead": by[limit] - limit,
            "exceeding": {"count": len(over), "min": over[0] if over else None,
                          "interval": bool(over) and over == list(range(over[0], limit + 1))}}


def build(root: Path | str, milestone: str) -> dict:
    """The results document (rule Z8)."""
    root = Path(root)
    rel = sidecar_rel(milestone)
    sc = load_sidecar(root, milestone)
    doc_p = root / sc["document"]
    doc = _load(doc_p, "Go document")
    out, command, version, token = run_probe(root, sc, doc, rel)
    c = int(out["capacity"])
    k_max = value(sc["hypotheses"]["HypZ"]["K"], c)
    s = sc["sample"]
    lengths = [value(e, c) for e in s["lengths"]]
    paddings = [value(e, c) for e in s["paddings"]]
    beyond = [value(e, c) for e in s["beyond"]]
    if any(k > k_max for k in paddings) or any(k <= k_max for k in beyond):
        raise ProbeError(f"the sample's paddings {paddings} must not exceed K = {k_max}, its beyond values {beyond} must")
    limit = value(s["expansion"]["limit"], c)
    points = _points(out)
    return {
        "compression_oracle_version": DOC_VERSION,
        "sidecar": {"path": rel, "sha256": _sha256(root / rel)},
        "document": {"path": sc["document"], "sha256": _sha256(doc_p)},
        "target": {"repo": doc["target"]["repo"], "commit": doc["target"]["commit"]},
        "codec": dict(sc["codec"]),
        "library": {"module": sc["codec"]["library"], "version": version},
        "toolchain": token,
        "capacity": {"C": c, "K": k_max},
        "sample": {"seed": s["seed"], "kinds": list(s["kinds"]), "lengths": lengths, "paddings": paddings,
                   "beyond": beyond, "expansion": {"kind": s["expansion"]["kind"], "limit": limit,
                                                   "window": int(s["expansion"]["window"])}},
        "points": points,
        "hypotheses": {"HypZ": hypz(sc, points, k_max, paddings), "HypZ_len": hypz_len(sc, points)},
        "expansion": expansion(sc, out["lens"], limit),
        "empty": out["empty"],
        "command": command,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon oracle compression",
                                 description="Test HypZ and HypZ_len on the target's real codec (rules Z1-Z9).")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--check", action="store_true", help="compare with the committed document; write nothing")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    try:
        doc = build(root, a.milestone)
    except Refused as e:
        print(f"holon oracle compression: refused: {e}", file=sys.stderr)
        return 2
    except ProbeError as e:
        print(f"holon oracle compression: {e}", file=sys.stderr)
        return 3
    text = render(doc)
    out = root / results_rel(a.milestone)
    h = doc["hypotheses"]
    summary = f"HypZ {h['HypZ']['status']}, HypZ_len {h['HypZ_len']['status']}, K = {doc['capacity']['K']}"
    if a.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != text:
            print(f"holon oracle compression: {results_rel(a.milestone)} differs from a fresh build ({summary})")
            return 1
        print(f"COMPRESSION ORACLE OK ({summary})")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"holon oracle compression: wrote {results_rel(a.milestone)} ({summary})")
    return 0
