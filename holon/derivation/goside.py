"""The Go side of holon derivation (rules G3, G4 and C2's compressor): one generated test file, placed in the consumer's
package of a scratch copy of the pinned checkout, with three tests run separately:

  TestHolonReplay    reads {"cases": [{"id", "batch"}]} (the batch by Go field names), builds each batch by reflection,
                     calls the consumer on a new receiver under recover and writes {id: {"status", "error", "panic",
                     "info"}} (info the receiver's dump, rule G5)
  TestHolonOracle    reads {"queries": [{"fn", "arg"}]} and runs each oracle function of the sidecar on its argument:
                     {"nil", "bytes"} or {"nil", "items"} (each element's encoding) or {"error"} or {"panic"}
  TestHolonCompress  reads {"payloads": [hex]} and runs the sidecar's compressor: {"bytes"} or {"error"}

Every name in the file comes from the sidecar or the document (checked against Go's identifier and import-path syntax);
nothing here names a target. The package's own test files are removed from the scratch copy, so the test binary holds
the package's code and this file only. The Go toolchain must be the pinned one (holon.frontends.go.extract.check_go),
the checkout must be at the sidecar's commit with no local change, and modules come from the module cache alone
(GOPROXY=off, GOFLAGS=-mod=readonly).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import DerivationError, Refused

TEST_FILE = "holon_derivation_test.go"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PATH = re.compile(r"^[A-Za-z0-9._~-]+(/[A-Za-z0-9._~-]+)*$")
METHOD = re.compile(r"^\(\*?([A-Za-z0-9._~/-]+)\.([A-Za-z_][A-Za-z0-9_]*)\)\.([A-Za-z_][A-Za-z0-9_]*)$")


def split_func(fid: str):
    """(import path, name) of a package-level function id "<path>.<Name>"."""
    if fid.startswith("("):
        raise Refused(f"{fid} is a method, not a package-level function")
    path, _, name = fid.rpartition(".")
    if not PATH.match(path) or ".." in path.split("/") or not IDENT.match(name):
        raise Refused(f"{fid[:120]!r} cannot be named in a generated test")
    return path, name


def split_method(fid: str):
    """(receiver package path, receiver type, method) of a method id "(*<path>.<T>).<M>" or "(<path>.<T>).<M>"."""
    m = METHOD.match(fid)
    if not m or ".." in m.group(1).split("/"):
        raise Refused(f"{fid[:120]!r} is not a method a generated test can call")
    return m.group(1), m.group(2), m.group(3)


def split_type(key: str):
    path, _, name = key.rpartition(".")
    if not PATH.match(path) or not IDENT.match(name):
        raise Refused(f"type {key[:120]!r} cannot be named in a generated test")
    return path, name


def test_text(section: dict, side: dict) -> str:
    ex, pr = side["extract"], side["product"]
    pkg = section["package"]
    if not IDENT.match(pkg["name"]):
        raise Refused(f"package name {pkg['name']!r}")
    rpath, rtype, method = split_method(section["entry"])
    if rpath != pkg["path"]:
        raise Refused("the consumer is not a method of a type of its own package")
    bpath, btype = split_type(pr["batch_type"])
    params = section["functions"][section["entry"]]["params"]
    if len(params) != 2 or params[1]["type"] != pr["batch_type"]:
        raise Refused(f"the consumer's parameter is not {pr['batch_type']}")
    imports = {bpath: "holonbatch"}
    oracles, enc_method = [], None
    for fid, e in sorted((ex.get("environment") or {}).items()):
        if e["kind"] == "oracle":
            p, n = split_func(fid)
            alias = imports.setdefault(p, f"holonenv{len(imports)}")
            if e.get("results") not in ("bytes", "encodings"):
                raise Refused(f"oracle {fid}: result shape {e.get('results')}")
            oracles.append((fid, alias, n, e["results"]))
        elif e["kind"] == "encoding":
            enc_method = split_method(fid)[2]
    if any(r == "encodings" for *_, r in oracles) and enc_method is None:
        raise Refused("an encodings oracle with no encoding method")
    cp, cn = split_func(ex["compressor"]["function"])
    calias = imports.setdefault(cp, f"holonenv{len(imports)}")
    cases = []
    for fid, alias, n, shape in oracles:
        if shape == "bytes":
            body = (f'\t\t\tr, err := {alias}.{n}(b)\n'
                    f'\t\t\tif err != nil {{\n\t\t\t\treturn map[string]any{{"error": err.Error()}}\n\t\t\t}}\n'
                    f'\t\t\treturn map[string]any{{"nil": r == nil, "bytes": "0x" + hex.EncodeToString(r)}}\n')
        else:
            body = (f'\t\t\txs, err := {alias}.{n}(b)\n'
                    f'\t\t\tif err != nil {{\n\t\t\t\treturn map[string]any{{"error": err.Error()}}\n\t\t\t}}\n'
                    f'\t\t\titems := []string{{}}\n'
                    f'\t\t\tfor _, x := range xs {{\n'
                    f'\t\t\t\tm, ok := any(x).(interface{{ {enc_method}() ([]byte, error) }})\n'
                    f'\t\t\t\tif !ok {{\n\t\t\t\t\treturn map[string]any{{"unsupported": "no {enc_method}"}}\n\t\t\t\t}}\n'
                    f'\t\t\t\tenc, e := m.{enc_method}()\n'
                    f'\t\t\t\tif e != nil {{\n\t\t\t\t\treturn map[string]any{{"unsupported": e.Error()}}\n\t\t\t\t}}\n'
                    f'\t\t\t\titems = append(items, "0x"+hex.EncodeToString(enc))\n'
                    f'\t\t\t}}\n'
                    f'\t\t\treturn map[string]any{{"nil": xs == nil, "items": items}}\n')
        cases.append(f'\t\tcase {json.dumps(fid)}:\n{body}')
    imp = "\n".join(f'\t{a} "{p}"' for p, a in sorted(imports.items(), key=lambda kv: kv[1]))
    return GO_TEMPLATE.format(pkg=pkg["name"], imports=imp, rtype=rtype, method=method, btype=btype,
                              oracle_cases="".join(cases), calias=calias, cname=cn)


GO_TEMPLATE = '''// GENERATED by holon.derivation.goside from a sidecar and a consumer document; do not edit.
package {pkg}

import (
\t"bytes"
\t"encoding/hex"
\t"encoding/json"
\t"fmt"
\t"math/big"
\t"os"
\t"reflect"
\t"strconv"
\t"strings"
\t"testing"
\t"unsafe"

{imports}
)

func holonHex(j any) ([]byte, error) {{
\ts, ok := j.(string)
\tif !ok || !strings.HasPrefix(s, "0x") {{
\t\treturn nil, fmt.Errorf("expected 0x hex, got %v", j)
\t}}
\treturn hex.DecodeString(s[2:])
}}

func holonSet(v reflect.Value, j any) error {{
\tv = reflect.NewAt(v.Type(), unsafe.Pointer(v.UnsafeAddr())).Elem()
\tswitch v.Kind() {{
\tcase reflect.Struct:
\t\tm, ok := j.(map[string]any)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs an object", v.Type())
\t\t}}
\t\tfor k, x := range m {{
\t\t\tf := v.FieldByName(k)
\t\t\tif !f.IsValid() {{
\t\t\t\treturn fmt.Errorf("%s has no field %s", v.Type(), k)
\t\t\t}}
\t\t\tif err := holonSet(f, x); err != nil {{
\t\t\t\treturn err
\t\t\t}}
\t\t}}
\tcase reflect.Slice:
\t\tif j == nil {{
\t\t\tv.Set(reflect.Zero(v.Type()))
\t\t\treturn nil
\t\t}}
\t\tif v.Type().Elem().Kind() == reflect.Uint8 {{
\t\t\tb, err := holonHex(j)
\t\t\tif err != nil {{
\t\t\t\treturn err
\t\t\t}}
\t\t\ts := reflect.MakeSlice(v.Type(), len(b), len(b))
\t\t\treflect.Copy(s, reflect.ValueOf(b))
\t\t\tv.Set(s)
\t\t\treturn nil
\t\t}}
\t\txs, ok := j.([]any)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs a list", v.Type())
\t\t}}
\t\ts := reflect.MakeSlice(v.Type(), len(xs), len(xs))
\t\tfor i, x := range xs {{
\t\t\tif err := holonSet(s.Index(i), x); err != nil {{
\t\t\t\treturn err
\t\t\t}}
\t\t}}
\t\tv.Set(s)
\tcase reflect.Array:
\t\tif v.Type().Elem().Kind() == reflect.Uint8 {{
\t\t\tb, err := holonHex(j)
\t\t\tif err != nil {{
\t\t\t\treturn err
\t\t\t}}
\t\t\tif len(b) != v.Len() {{
\t\t\t\treturn fmt.Errorf("%s needs %d bytes, got %d", v.Type(), v.Len(), len(b))
\t\t\t}}
\t\t\treflect.Copy(v, reflect.ValueOf(b))
\t\t\treturn nil
\t\t}}
\t\txs, ok := j.([]any)
\t\tif !ok || len(xs) != v.Len() {{
\t\t\treturn fmt.Errorf("%s needs a list of %d", v.Type(), v.Len())
\t\t}}
\t\tfor i, x := range xs {{
\t\t\tif err := holonSet(v.Index(i), x); err != nil {{
\t\t\t\treturn err
\t\t\t}}
\t\t}}
\tcase reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
\t\tn, ok := j.(json.Number)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs a number", v.Type())
\t\t}}
\t\tu, err := strconv.ParseUint(string(n), 10, v.Type().Bits())
\t\tif err != nil {{
\t\t\treturn err
\t\t}}
\t\tv.SetUint(u)
\tcase reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
\t\tn, ok := j.(json.Number)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs a number", v.Type())
\t\t}}
\t\ti, err := strconv.ParseInt(string(n), 10, v.Type().Bits())
\t\tif err != nil {{
\t\t\treturn err
\t\t}}
\t\tv.SetInt(i)
\tcase reflect.Bool:
\t\tb, ok := j.(bool)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs a boolean", v.Type())
\t\t}}
\t\tv.SetBool(b)
\tcase reflect.String:
\t\ts, ok := j.(string)
\t\tif !ok {{
\t\t\treturn fmt.Errorf("%s needs a string", v.Type())
\t\t}}
\t\tv.SetString(s)
\tcase reflect.Pointer:
\t\tif j != nil {{
\t\t\treturn fmt.Errorf("%s: only a nil pointer can be built", v.Type())
\t\t}}
\t\tv.Set(reflect.Zero(v.Type()))
\tdefault:
\t\treturn fmt.Errorf("cannot build a %s", v.Type())
\t}}
\treturn nil
}}

var holonBigType = reflect.TypeOf((*big.Int)(nil))

func holonBytes(v reflect.Value) string {{
\tb := make([]byte, v.Len())
\tfor i := range b {{
\t\tb[i] = byte(v.Index(i).Uint())
\t}}
\treturn "0x" + hex.EncodeToString(b)
}}

func holonDump(v reflect.Value) any {{
\tswitch v.Kind() {{
\tcase reflect.Bool:
\t\treturn v.Bool()
\tcase reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
\t\treturn json.Number(strconv.FormatInt(v.Int(), 10))
\tcase reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
\t\treturn json.Number(strconv.FormatUint(v.Uint(), 10))
\tcase reflect.String:
\t\treturn v.String()
\tcase reflect.Array:
\t\tif v.Type().Elem().Kind() == reflect.Uint8 {{
\t\t\treturn holonBytes(v)
\t\t}}
\t\tout := make([]any, v.Len())
\t\tfor i := range out {{
\t\t\tout[i] = holonDump(v.Index(i))
\t\t}}
\t\treturn out
\tcase reflect.Slice:
\t\tif v.IsNil() {{
\t\t\treturn nil
\t\t}}
\t\tif v.Type().Elem().Kind() == reflect.Uint8 {{
\t\t\treturn holonBytes(v)
\t\t}}
\t\tout := make([]any, v.Len())
\t\tfor i := range out {{
\t\t\tout[i] = holonDump(v.Index(i))
\t\t}}
\t\treturn out
\tcase reflect.Struct:
\t\tm := map[string]any{{}}
\t\tfor i := 0; i < v.NumField(); i++ {{
\t\t\tm[v.Type().Field(i).Name] = holonDump(v.Field(i))
\t\t}}
\t\treturn m
\tcase reflect.Pointer:
\t\tif v.IsNil() {{
\t\t\treturn nil
\t\t}}
\t\tif v.Type() == holonBigType {{
\t\t\tp := reflect.NewAt(v.Type().Elem(), unsafe.Pointer(v.Pointer())).Interface().(*big.Int)
\t\t\treturn map[string]any{{"big": p.String()}}
\t\t}}
\t\treturn holonDump(v.Elem())
\tcase reflect.Interface:
\t\tif v.IsNil() {{
\t\t\treturn nil
\t\t}}
\t\tx := reflect.NewAt(v.Type(), unsafe.Pointer(v.UnsafeAddr())).Elem().Interface()
\t\tif e, ok := x.(error); ok {{
\t\t\treturn map[string]any{{"error": e.Error()}}
\t\t}}
\t\treturn map[string]any{{"unsupported": v.Type().String()}}
\t}}
\treturn map[string]any{{"unsupported": v.Kind().String()}}
}}

func holonRead(t *testing.T, env string, into any) bool {{
\tp := os.Getenv(env)
\tif p == "" {{
\t\treturn false
\t}}
\traw, err := os.ReadFile(p)
\tif err != nil {{
\t\tt.Fatalf("read %s: %v", p, err)
\t}}
\td := json.NewDecoder(bytes.NewReader(raw))
\td.UseNumber()
\tif err := d.Decode(into); err != nil {{
\t\tt.Fatalf("parse %s: %v", p, err)
\t}}
\treturn true
}}

func holonWrite(t *testing.T, env string, out any) {{
\tjs, err := json.Marshal(out)
\tif err != nil {{
\t\tt.Fatalf("encode: %v", err)
\t}}
\tif err := os.WriteFile(os.Getenv(env), js, 0o644); err != nil {{
\t\tt.Fatalf("write: %v", err)
\t}}
}}

func holonRun(batch any) (out map[string]any) {{
\trecv := new({rtype})
\tv := reflect.New(reflect.TypeOf(holonbatch.{btype}{{}})).Elem()
\tif err := holonSet(v, batch); err != nil {{
\t\treturn map[string]any{{"status": "input", "error": err.Error(), "panic": nil, "info": nil}}
\t}}
\tout = map[string]any{{"status": nil, "error": nil, "panic": nil, "info": nil}}
\tfunc() {{
\t\tdefer func() {{
\t\t\tif r := recover(); r != nil {{
\t\t\t\tout["status"] = "panic"
\t\t\t\tout["panic"] = fmt.Sprint(r)
\t\t\t}}
\t\t}}()
\t\tif err := recv.{method}(v.Interface().(holonbatch.{btype})); err != nil {{
\t\t\tout["status"] = "error"
\t\t\tout["error"] = err.Error()
\t\t}} else {{
\t\t\tout["status"] = "ok"
\t\t}}
\t}}()
\tout["info"] = holonDump(reflect.ValueOf(recv).Elem())
\treturn out
}}

func TestHolonReplay(t *testing.T) {{
\tvar in struct {{
\t\tCases []struct {{
\t\t\tID    string `json:"id"`
\t\t\tBatch any    `json:"batch"`
\t\t}} `json:"cases"`
\t}}
\tif !holonRead(t, "HOLON_DERIV_REPLAY_IN", &in) {{
\t\tt.Skip("no input")
\t}}
\tout := map[string]any{{}}
\tfor _, c := range in.Cases {{
\t\tout[c.ID] = holonRun(c.Batch)
\t}}
\tholonWrite(t, "HOLON_DERIV_REPLAY_OUT", out)
}}

func holonOracle(fn string, b []byte) (out map[string]any) {{
\tdefer func() {{
\t\tif r := recover(); r != nil {{
\t\t\tout = map[string]any{{"panic": fmt.Sprint(r)}}
\t\t}}
\t}}()
\tswitch fn {{
{oracle_cases}\t}}
\treturn map[string]any{{"unsupported": "no oracle " + fn}}
}}

func TestHolonOracle(t *testing.T) {{
\tvar in struct {{
\t\tQueries []struct {{
\t\t\tFn  string `json:"fn"`
\t\t\tArg string `json:"arg"`
\t\t}} `json:"queries"`
\t}}
\tif !holonRead(t, "HOLON_DERIV_ORACLE_IN", &in) {{
\t\tt.Skip("no input")
\t}}
\tout := []any{{}}
\tfor _, q := range in.Queries {{
\t\tb, err := holonHex(q.Arg)
\t\tif err != nil {{
\t\t\tt.Fatalf("query: %v", err)
\t\t}}
\t\tout = append(out, holonOracle(q.Fn, b))
\t}}
\tholonWrite(t, "HOLON_DERIV_ORACLE_OUT", out)
}}

func TestHolonCompress(t *testing.T) {{
\tvar in struct {{
\t\tPayloads []string `json:"payloads"`
\t}}
\tif !holonRead(t, "HOLON_DERIV_COMPRESS_IN", &in) {{
\t\tt.Skip("no input")
\t}}
\tout := []any{{}}
\tfor _, p := range in.Payloads {{
\t\tb, err := holonHex(p)
\t\tif err != nil {{
\t\t\tt.Fatalf("payload: %v", err)
\t\t}}
\t\tr, err := {calias}.{cname}(b)
\t\tif err != nil {{
\t\t\tout = append(out, map[string]any{{"error": err.Error()}})
\t\t\tcontinue
\t\t}}
\t\tout = append(out, map[string]any{{"bytes": "0x" + hex.EncodeToString(r)}})
\t}}
\tholonWrite(t, "HOLON_DERIV_COMPRESS_OUT", out)
}}
'''


class Workspace:
    """A scratch copy of the pinned checkout with the generated test in the consumer's package (a context manager)."""

    def __init__(self, root: Path, side: dict, section: dict):
        self.root, self.side, self.section = root, side, section
        self.parent = None
        self.go = None
        self.go_version = None
        self.mod = None
        self.rel = None

    def __enter__(self):
        from ..frontends.go.extract import Refused as XRefused, check_go, load_config, make_workspace, resolve_src
        try:
            cfg = load_config(self.root / self.side["extract"]["frontend_config"])
            src = resolve_src(cfg, self.root)
            self.go, self.go_version = check_go(self.root)
        except XRefused as e:
            raise Refused(str(e))
        git = ["git", "-C", str(src), "-c", "protocol.allow=never"]
        head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head != self.side["target"]["commit"]:
            raise Refused(f"{src} is at {head!r}, not at the sidecar's commit {self.side['target']['commit']}")
        dirty = subprocess.run(git + ["status", "--porcelain", "--untracked-files=no"], capture_output=True,
                               text=True).stdout.strip()
        if dirty:
            raise Refused(f"{src} has local changes: {dirty[:300]}")
        self.parent = Path(tempfile.mkdtemp(prefix="holon-derivation-"))
        ws = self.parent / "src"
        ws.mkdir()
        try:
            make_workspace(src, ws)
        except XRefused as e:
            raise Refused(str(e))
        pdir = self.section["package"]["dir"]
        if Path(pdir).is_absolute() or ".." in Path(pdir).parts:
            raise Refused(f"package directory {pdir!r}")
        d = ws / pdir
        for f in sorted(d.glob("*_test.go")):
            f.unlink()
        (d / TEST_FILE).write_text(test_text(self.section, self.side), encoding="utf-8")
        m = d
        while not (m / "go.mod").is_file():
            if m == ws:
                raise Refused(f"no go.mod above {pdir}")
            m = m.parent
        self.mod = m
        self.rel = "./" + d.relative_to(m).as_posix()
        return self

    def __exit__(self, *exc):
        if self.parent is not None:
            shutil.rmtree(self.parent, ignore_errors=True)
        return False

    def command(self, test: str) -> str:
        return f"(cd {self.mod.relative_to(self.parent / 'src').as_posix()} && go test {self.rel} -run '^{test}$' -count=1)"

    def run(self, test: str, var: str, payload: dict):
        from ..frontends.go.extract import go_env
        inp, out = self.parent / f"{var}.in.json", self.parent / f"{var}.out.json"
        inp.write_text(json.dumps(payload), encoding="utf-8")
        if out.exists():
            out.unlink()
        env = go_env(GOTOOLCHAIN="local", GOFLAGS="-mod=readonly", GOPROXY="off",
                     **{f"{var}_IN": str(inp), f"{var}_OUT": str(out)})
        p = subprocess.run([self.go, "test", self.rel, "-run", f"^{test}$", "-count=1"], cwd=self.mod, env=env,
                           capture_output=True, text=True, timeout=7200)
        if p.returncode != 0 or not out.exists():
            raise DerivationError(f"the generated Go test {test} failed (exit {p.returncode}): "
                                  f"{(p.stdout + p.stderr)[-3000:]}")
        return json.loads(out.read_text(encoding="utf-8"))
