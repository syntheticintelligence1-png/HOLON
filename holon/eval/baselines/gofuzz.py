"""The Go baselines (I52_baselines.json: go_fuzz, two_cycle, and spec_mining's Go beliefs).

Setup (outside the budget): the target's Go module is the nearest go.mod ancestor of each scope package; a submodule is
fetched only when it is a local replace target of that go.mod (clone_rule); modules come through the Go proxy by the
project's go.sum; GOTOOLCHAIN=local, so the pinned go1.24.7 is never substituted (a module that needs a newer Go is a
setup error). The generated harnesses are written as holon_*_test.go files beside the package's own files (the checkout
is a scratch tree) and compiled once (`go test -run ^$`) before any analysis.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath

from . import core

GOTOOL = core.TOOLS / "i52-gotool"
FUZZ_TYPES = {"[]byte", "string", "bool", "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16", "uint32",
              "uint64", "float32", "float64", "byte", "rune"}
ENCODERS = ("Bytes", "Encode", "Marshal", "MarshalBinary", "Serialize", "ToBytes")
DECODER_PREFIXES = ("Decode", "Unmarshal", "Parse")
DECODER_METHODS = ("UnmarshalBinary", "Unmarshal", "Decode", "SetBytes")


def env() -> dict:
    return {"GOTOOLCHAIN": "local", "GOFLAGS": "-buildvcs=false", "CGO_ENABLED": "1", "GOMAXPROCS": "1"}


def ensure_gotool() -> Path:
    if not GOTOOL.is_file():
        src = Path(__file__).parent / "gotool" / "main.go"
        subprocess.run(["go", "build", "-o", str(GOTOOL), str(src)], check=True, capture_output=True,
                       env={**__import__("os").environ, "GOTOOLCHAIN": "local"})
    return GOTOOL


def lister(d: Path) -> dict:
    p = subprocess.run([str(ensure_gotool()), "list", str(d)], capture_output=True, text=True, check=True)
    x = json.loads(p.stdout)
    for k in ("funcs", "types", "fuzz", "errors"):
        x[k] = x.get(k) or []
    for t in x["types"]:
        t["fields"] = t.get("fields") or []
    for f in x["funcs"]:
        f["params"] = f.get("params") or []
        f["results"] = f.get("results") or []
    return x


def go_packages(src: Path, system: str, target: str) -> list[str]:
    """The scope directories that hold a non-test .go file."""
    files = core.scope_files(src, system, target, ".go")
    return sorted({PurePosixPath(f).parent.as_posix() for f in files})


def module_root(src: Path, pkg: str) -> Path | None:
    p = src / pkg
    while True:
        if (p / "go.mod").is_file():
            return p
        if p == src:
            return None
        p = p.parent


def _local_replaces(gomod: Path) -> list[str]:
    out = []
    for m in re.finditer(r"=>\s*(\.\.?/[^\s]+)", gomod.read_text()):
        out.append(m.group(1))
    return out


def setup_module(src: Path, pkg: str, logs: list) -> tuple[Path | None, list, str | None]:
    mod = module_root(src, pkg)
    if mod is None:
        return None, [], f"no go.mod above {pkg}"
    subs = []
    if (src / ".gitmodules").is_file() and "/corpus/" in str(src):
        reps = {(mod / r).resolve() for r in _local_replaces(mod / "go.mod")}
        allsubs = core.submodules_list(src)
        want = [s for s in allsubs if any((src / s["path"]).resolve() == r or r.is_relative_to((src / s["path"]).resolve())
                                          for r in reps)]
        subs = core.fetch_submodules(src, want)
    return mod, subs, None


def _rel(src: Path, abspath: str) -> str | None:
    try:
        return Path(abspath).resolve().relative_to(src.resolve()).as_posix()
    except ValueError:
        return None


def _compile(mod: Path, pkg_rel_mod: str, logs: list) -> tuple[bool, str, float]:
    code, text, dt = core.run_setup(["go", "test", "-count=1", "-run", "^$", f"./{pkg_rel_mod}"], mod, 3600, env())
    logs.append(f"$ go test -run ^$ ./{pkg_rel_mod} (in {mod}, exit {code})\n{core.tail(text, 3000)}")
    return code == 0, text, dt


# ------------------------------------------------------------------------------------------------- go_fuzz harnesses
def _fuzz_type(t: str) -> str | None:
    return {"byte": "uint8", "rune": "int32"}.get(t, t) if t in FUZZ_TYPES else None


def fuzz_harness(pkg: dict) -> tuple[str, list[dict]]:
    """holon_fuzz_test.go: one FuzzHolon_<Name> per exported, non-generic top-level function whose parameters are all
    fuzz-engine types. Returns (source, units)."""
    units, body = [], []
    for f in sorted(pkg["funcs"], key=lambda f: (f["name"], f["file"], f["start"])):
        if f["recv"] or not f["exported"] or f["generic"] or f["name"].startswith(("Fuzz", "Test", "Benchmark", "Example")):
            continue
        ts = [_fuzz_type(t) for t in f["params"]]
        if any(t is None for t in ts) or any(t.startswith("...") for t in f["params"]):
            continue
        name = f"FuzzHolon_{f['name']}"
        if any(u["name"] == name for u in units):
            continue
        params = ", ".join(f"a{i} {t}" for i, t in enumerate(ts))
        args = ", ".join(f"{p}(a{i})" if p in ("byte", "rune") else f"a{i}" for i, p in enumerate(f["params"]))
        body.append(f"func {name}(f *testing.F) {{\n\tf.Fuzz(func(t *testing.T{', ' + params if params else ''}) {{\n"
                    f"\t\t{f['name']}({args})\n\t}})\n}}\n")
        units.append({"name": name, "target": f})
    src = f"package {pkg['package']}\n\nimport \"testing\"\n\n" + "\n".join(body) if body else ""
    return src, units


# ------------------------------------------------------------------------------------------------- two_cycle pairs
def _bytes_like(t: str, types: dict) -> bool:
    return t == "[]byte" or (t in types and types[t]["underlying"] in ("[]byte", "[]uint8"))


def pairs(pkg: dict) -> list[dict]:
    types = {t["name"]: t for t in pkg["types"] if not t["generic"]}
    methods: dict[str, list[dict]] = {}
    for f in pkg["funcs"]:
        if f["recv"]:
            methods.setdefault(f["recv"], []).append(f)
    out = []
    for tname in sorted(types):
        t = types[tname]
        if not t["struct"]:
            continue
        for enc in sorted(methods.get(tname, []), key=lambda f: f["name"]):
            if enc["name"] not in ENCODERS or enc["params"] or enc["generic"] or not enc["results"]:
                continue
            u = enc["results"][0]
            if not _bytes_like(u, types) or (len(enc["results"]) == 2 and enc["results"][1] != "error") or len(enc["results"]) > 2:
                continue
            enc_err = len(enc["results"]) == 2
            decs = []
            for f in sorted(pkg["funcs"], key=lambda f: (f["name"], f["start"])):
                if f["recv"] or f["generic"] or len(f["params"]) != 1 or not f["results"]:
                    continue
                if not (f["name"].startswith(DECODER_PREFIXES) or (f["name"].startswith("New") and "From" in f["name"])):
                    continue
                if f["params"][0] not in ("[]byte", u) or f["results"][0] not in (tname, "*" + tname):
                    continue
                if len(f["results"]) > 2 or (len(f["results"]) == 2 and f["results"][1] != "error"):
                    continue
                decs.append({"kind": "func", "f": f, "ptr": f["results"][0].startswith("*"), "err": len(f["results"]) == 2})
            for f in sorted(methods.get(tname, []), key=lambda f: f["name"]):
                if f["name"] in DECODER_METHODS and f["recv_ptr"] and f["params"] in (["[]byte"], [u]) and f["results"] == ["error"]:
                    decs.append({"kind": "method", "f": f})
            if u != "[]byte" and u in methods:
                gs = {g["name"]: g for g in methods[u] if not g["params"]}
                fields = [fl for fl in t["fields"] if fl["name"] in gs and gs[fl["name"]]["results"] and
                          gs[fl["name"]]["results"][0] == fl["type"] and
                          (len(gs[fl["name"]]["results"]) == 1 or gs[fl["name"]]["results"][1:] == ["error"])]
                if len(fields) >= 2:
                    decs.append({"kind": "getters", "fields": [{"name": fl["name"], "via": fl["via"],
                                                                "err": len(gs[fl["name"]]["results"]) == 2,
                                                                "getter": gs[fl["name"]]} for fl in fields]})
            for i, d in enumerate(decs):
                out.append({"T": tname, "U": u, "enc": enc, "enc_err": enc_err, "dec": d,
                            "name": f"FuzzHolonCycle_{tname}_{enc['name']}_{d['kind']}{i}"})
    return out


FILLER = r'''
type holonSrc struct{ b []byte; i int }

func (s *holonSrc) next() byte {
	if len(s.b) == 0 {
		return 0
	}
	v := s.b[s.i%len(s.b)]
	s.i++
	return v
}

func holonFill(v reflect.Value, s *holonSrc, depth int) {
	if depth > 6 || !v.CanSet() {
		return
	}
	switch v.Kind() {
	case reflect.Bool:
		v.SetBool(s.next()&1 == 1)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		var x uint64
		for i := 0; i < 8; i++ {
			x = x<<8 | uint64(s.next())
		}
		v.SetInt(int64(x))
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
		var x uint64
		for i := 0; i < 8; i++ {
			x = x<<8 | uint64(s.next())
		}
		v.SetUint(x)
	case reflect.String:
		n := int(s.next() % 16)
		b := make([]byte, n)
		for i := range b {
			b[i] = s.next()
		}
		v.SetString(string(b))
	case reflect.Slice:
		n := int(s.next() % 8)
		if v.Type().Elem().Kind() == reflect.Uint8 {
			n = int(s.next() % 64)
		}
		sl := reflect.MakeSlice(v.Type(), n, n)
		for i := 0; i < n; i++ {
			holonFill(sl.Index(i), s, depth+1)
		}
		v.Set(sl)
	case reflect.Array:
		for i := 0; i < v.Len(); i++ {
			holonFill(v.Index(i), s, depth+1)
		}
	case reflect.Struct:
		for i := 0; i < v.NumField(); i++ {
			if v.Type().Field(i).IsExported() {
				holonFill(v.Field(i), s, depth+1)
			}
		}
	case reflect.Ptr:
		if s.next()&3 != 0 {
			p := reflect.New(v.Type().Elem())
			holonFill(p.Elem(), s, depth+1)
			v.Set(p)
		}
	}
}

func holonExported(a, b reflect.Value) bool {
	if a.Kind() != reflect.Struct {
		return reflect.DeepEqual(a.Interface(), b.Interface())
	}
	for i := 0; i < a.NumField(); i++ {
		if a.Type().Field(i).IsExported() && !holonExported(a.Field(i), b.Field(i)) {
			return false
		}
	}
	return true
}
'''


def cycle_harness(pkg: dict, ps: list[dict]) -> str:
    if not ps:
        return ""
    body = []
    for p in ps:
        T, U, enc, d = p["T"], p["U"], p["enc"]["name"], p["dec"]
        encx = f"holonEnc_{p['name']}"
        decx = f"holonDec_{p['name']}"
        conv = "[]byte" if U == "[]byte" else U
        body.append(f"func {encx}(x {T}) ([]byte, bool) {{\n" +
                    (f"\tb, err := x.{enc}()\n\tif err != nil {{\n\t\treturn nil, false\n\t}}\n\treturn []byte(b), true\n}}\n"
                     if p["enc_err"] else f"\treturn []byte(x.{enc}()), true\n}}\n"))
        if d["kind"] == "func":
            f = d["f"]
            arg = "b" if f["params"][0] == "[]byte" else f"{conv}(b)"
            call = f"{f['name']}({arg})"
            res = "y, err := " + call if d["err"] else "y := " + call
            chk = "\tif err != nil {\n\t\treturn " + T + "{}, false\n\t}\n" if d["err"] else ""
            deref = "*y" if d["ptr"] else "y"
            nil_chk = f"\tif y == nil {{\n\t\treturn {T}{{}}, false\n\t}}\n" if d["ptr"] else ""
            body.append(f"func {decx}(b []byte) ({T}, bool) {{\n\t{res}\n{chk}{nil_chk}\treturn {deref}, true\n}}\n")
        elif d["kind"] == "method":
            f = d["f"]
            arg = "b" if f["params"][0] == "[]byte" else f"{conv}(b)"
            body.append(f"func {decx}(b []byte) ({T}, bool) {{\n\tvar y {T}\n\tif err := y.{f['name']}({arg}); err != nil {{\n"
                        f"\t\treturn {T}{{}}, false\n\t}}\n\treturn y, true\n}}\n")
        else:
            lines = [f"func {decx}(b []byte) ({T}, bool) {{", f"\tu := {conv}(b)", f"\tvar y {T}"]
            for fl in d["fields"]:
                tgt = "y." + fl["name"]
                if fl["err"]:
                    lines += [f"\tif v, err := u.{fl['name']}(); err != nil {{", f"\t\treturn {T}{{}}, false",
                              "\t} else {", f"\t\t{tgt} = v", "\t}"]
                else:
                    lines.append(f"\t{tgt} = u.{fl['name']}()")
            lines += ["\treturn y, true", "}"]
            body.append("\n".join(lines) + "\n")
        if d["kind"] == "getters":
            cmp = " &&\n\t\t".join(f"reflect.DeepEqual(x.{fl['name']}, y.{fl['name']})" for fl in d["fields"])
        else:
            cmp = "holonExported(reflect.ValueOf(x), reflect.ValueOf(y))"
        body.append(f'''func {p["name"]}(f *testing.F) {{
	for i := 0; i < 8; i++ {{
		seed := make([]byte, 64)
		for j := range seed {{
			seed[j] = byte(i*131 + j*7)
		}}
		var x {T}
		holonFill(reflect.ValueOf(&x).Elem(), &holonSrc{{b: seed}}, 0)
		if b, ok := {encx}(x); ok {{
			f.Add(append([]byte{{1}}, b...))
		}}
		f.Add(append([]byte{{0}}, seed...))
	}}
	f.Fuzz(func(t *testing.T, data []byte) {{
		if len(data) == 0 {{
			return
		}}
		if data[0]&1 == 0 {{
			var x {T}
			holonFill(reflect.ValueOf(&x).Elem(), &holonSrc{{b: data[1:]}}, 0)
			b, ok := {encx}(x)
			if !ok {{
				return
			}}
			y, ok := {decx}(b)
			if !ok {{
				t.Fatalf("value cycle: {T}.{enc} then decode fails: x=%+v enc=%x", x, b)
			}}
			if !({cmp}) {{
				t.Fatalf("value cycle: decode({T}.{enc}(x)) != x: x=%+v y=%+v enc=%x", x, y, b)
			}}
			return
		}}
		b := data[1:]
		y, ok := {decx}(b)
		if !ok {{
			return
		}}
		b2, ok := {encx}(y)
		if !ok || !bytes.Equal(b2, b) {{
			t.Fatalf("bytes cycle: {T}.{enc}(decode(b)) != b: b=%x enc=%x", b, b2)
		}}
	}})
}}
''')
    return (f"package {pkg['package']}\n\nimport (\n\t\"bytes\"\n\t\"reflect\"\n\t\"testing\"\n)\n" + FILLER + "\n" +
            "\n".join(body))


# ------------------------------------------------------------------------------------------------- the runners
_FRAME = re.compile(r"(/[^\s:]+\.go):(\d+)")


def _crash_loc(src: Path, text: str, scope: set, fallback: dict | None):
    for m in _FRAME.finditer(text):
        rel = _rel(src, m.group(1))
        if rel and rel in scope and not PurePosixPath(rel).name.startswith("holon_"):
            return core.loc(rel, int(m.group(2)))
    return fallback


def _prepare(system: str, target: str, kind: str) -> dict:
    """Per (target, kind in fuzz|cycle): the packages, harness units and the setup compile (cached)."""
    src = core.checkout(system, target)
    state = core.WORK / system / target / f"go-{kind}.json"
    if state.is_file():
        return core.load(state)
    logs, setup, units, pkgs, subs, errs = [], 0.0, [], [], [], []
    for pkg in go_packages(src, system, target):
        mod, s, err = setup_module(src, pkg, logs)
        subs += s
        if err:
            errs.append(f"{pkg}: {err}")
            continue
        info = lister(src / pkg)
        hfile = src / pkg / f"holon_{kind}_test.go"
        if kind == "fuzz":
            code, us = fuzz_harness(info)
            for name in info["fuzz"]:
                us.insert(0, {"name": name, "target": None, "existing": True})
        else:
            ps = pairs(info)
            code, us = cycle_harness(info, ps), [{"name": p["name"], "pair": {
                "T": p["T"], "U": p["U"], "enc": p["enc"], "dec": p["dec"]}} for p in ps]
        if code:
            hfile.write_text(code)
        if not us:
            pkgs.append({"pkg": pkg, "module": str(mod), "units": 0})
            continue
        rel = (src / pkg).relative_to(mod).as_posix()
        ok, text, dt = _compile(mod, rel, logs)
        setup += dt
        if not ok:
            errs.append(f"{pkg}: the package (with its harness) does not compile: {core.tail(text, 500)}")
            hfile.unlink(missing_ok=True)
            continue
        for u in us:
            u.update({"pkg": pkg, "module": str(mod), "rel": rel})
        units += us
        pkgs.append({"pkg": pkg, "module": str(mod), "units": len(us)})
    out = {"units": units, "packages": pkgs, "errors": errs, "setup_s": round(setup, 3), "submodules": subs,
           "src": str(src)}
    (core.WORK / system / target / f"go-{kind}.log").write_text("\n\n".join(logs))
    state.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def _run_units(system, target, wall, cpu, kind):
    prep = _prepare(system, target, kind)
    src = Path(prep["src"])
    scope = set(core.scope_files(src, system, target, ".go"))
    base = {"setup_s": prep["setup_s"], "submodules": prep["submodules"], "packages": prep["packages"],
            "setup_errors": prep["errors"]}
    if not prep["units"]:
        reason = "; ".join(prep["errors"]) or ("no fuzz target: no scope function with only fuzz-engine parameter types"
                                               if kind == "fuzz" else "no codec pair discovered in the scope packages")
        status = "error" if prep["errors"] else "run"
        return {"status": status, "reason": reason, "findings": [], "units": [], "commands": [], "seeds": {},
                "budget_exhausted": False, **base}
    units = sorted(prep["units"], key=lambda u: (u["pkg"], u["name"]))
    u = core.Units(wall, len(units))
    fs, cmds, exhausted = [], [], False
    for un in units:
        share = u.share()
        ft = max(int(share) - 5, 1)
        argv = ["go", "test", "-run", "^$", "-fuzz", f"^{un['name']}$", "-fuzztime", f"{ft}s", "-parallel", "1",
                f"./{un['rel']}"]
        r = core.run_bounded(argv, Path(un["module"]), share, cpu, env(),
                             core.WORK / system / target / "logs" / f"{kind}_{un['name']}.log")
        u.done(un["name"], r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
        exhausted |= r["timed_out"] or (r["exit"] == 0)
        cmds.append(" ".join(argv))
        out = r["output"]
        if r["exit"] != 0 and "--- FAIL" in out:
            if kind == "fuzz":
                tgt = un.get("target")
                fb = core.loc(f"{un['pkg']}/{tgt['file']}", tgt["start"], tgt["end"], tgt["name"]) if tgt else None
                l = _crash_loc(src, out[out.find("--- FAIL"):], scope, fb)
                msg = re.search(r"(panic: [^\n]+|runtime error: [^\n]+|fuzz: [^\n]+)", out)
                fs.append(core.finding("panic" if "panic" in out else "fuzz-failure",
                                       f"go_fuzz {un['name']}: {msg.group(1) if msg else 'failing input'}",
                                       [l] if l else [], None, {"output": core.tail(out[out.find('--- FAIL'):], 1500)}))
            else:
                p = un["pair"]
                enc = p["enc"]
                locs = [core.loc(f"{un['pkg']}/{enc['file']}", enc["start"], enc["end"], f"{p['T']}.{enc['name']}")]
                d = p["dec"]
                if d["kind"] in ("func", "method"):
                    f = d["f"]
                    locs.append(core.loc(f"{un['pkg']}/{f['file']}", f["start"], f["end"], f["name"]))
                else:
                    for fl in d["fields"]:
                        g = fl["getter"]
                        locs.append(core.loc(f"{un['pkg']}/{g['file']}", g["start"], g["end"], f"{p['U']}.{g['name']}"))
                m = re.search(r"(value cycle|bytes cycle)[^\n]*", out)
                which = m.group(1) if m else "cycle"
                panic = re.search(r"panic: [^\n]+", out)
                fs.append(core.finding(which.replace(" ", "-"), f"two_cycle {p['T']}.{enc['name']} / "
                                       f"{d['kind']} decoder: {(m.group(0) if m else (panic.group(0) if panic else 'failure'))[:600]}",
                                       locs, None, {"output": core.tail(out[out.find('--- FAIL'):], 1500)}))
        elif r["exit"] != 0 and not r["timed_out"]:
            exhausted = exhausted
    return {"status": "run", "reason": "; ".join(prep["errors"]) or None, "findings": fs, "units": u.used,
            "commands": cmds, "seeds": {"go": "Go's fuzz engine is not seedable; the 2-cycle filler is a deterministic "
                                        "function of each input"}, "budget_exhausted": exhausted, **base}


def run_go_fuzz(system, target, wall, cpu):
    return _run_units(system, target, wall, cpu, "fuzz")


def run_two_cycle(system, target, wall, cpu):
    return _run_units(system, target, wall, cpu, "cycle")


def mine_go(src: Path, system: str, target: str) -> list[dict]:
    dirs = [str(src / p) for p in go_packages(src, system, target)]
    if not dirs:
        return []
    p = subprocess.run([str(ensure_gotool()), "mine", str(src), *dirs], capture_output=True, text=True, check=True)
    out = []
    for d in json.loads(p.stdout) or []:
        s = d["site"]
        out.append(core.finding(f"belief-{d['belief']}", d["message"], [core.loc(s["file"], s["line"], None, s["func"])],
                                None, {"subject": d["subject"], "support": d["support"],
                                       "confidence": round(d["confidence"], 4)}))
    return out


RUNNERS = {"go_fuzz": run_go_fuzz, "two_cycle": run_two_cycle}
