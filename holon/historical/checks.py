"""Per-header checks of the historical replay, without the chain (`holon.historical.header_checks`).

Every value comes from the frozen M0 header model (facts/morph_header.json) compiled with the pinned Bend: the
native C model when results/M2/native.json says native, else the .mjs model (the recorded I16 fallback), as
holon.refinement chooses. Python only moves bytes in and out and compares them.

    length       len(header)
    version      header[0] (None for an empty header)
    keccak       "0x" + keccak256(header) (holon.keccak)
    ok_sol       the model's ok_sol(header)
    ok_go        the model's ok_go(header)
    roundtrip    "ok" iff enc_sol(dec(header)) == header byte for byte, else "diff". dec is the model's dec_go:
                 its getters, in the facts' order, fill the Header record (a getter the version skips, e.g.
                 lastBlockNumber on version 0, fills zeros, which enc_sol does not write for that version).
                 When dec_go is None (outside ok_go) there is nothing to re-encode: "diff", every cell.
    diff_cells   the indices where enc_sol(dec(header)) and header differ, a missing cell on either side and
                 a cell enc_sol leaves unknown (dirty EVM memory) included
    ssvh_zero    the sequencerSetVerifyHash cells (the dec_go getter's offset and width) are all zero

The field offsets used outside the model (batch index, blob versioned hash, ssvh) are the dec_go getters'
offsets in the facts, so a different layout in the facts moves them too.
"""
from __future__ import annotations

from pathlib import Path

from .. import facts as F
from .. import ir
from ..keccak import keccak256

ROOT = Path(__file__).resolve().parents[2]


class HeaderModel:
    def __init__(self, root: Path = ROOT):
        from ..refinement import build_engine, model_engine
        reg = ir.load_registry("M0", root)
        self.facts_rel = reg.get("facts", "facts/morph_header.json")
        self.facts_path = Path(root) / self.facts_rel
        self.facts = F.load(self.facts_path)
        self.engine = model_engine(root)
        self.model = build_engine(self.engine, self.facts_path)
        self.widths = F.widths(self.facts)
        self.getters = self.facts["functions"]["dec_go"]["getters"]
        self.offsets = {g["name"]: (g["offset"], g["width"]) for g in self.getters}

    # ---------------------------------------------------------------- facts structure
    def present(self, version: int) -> list[str]:
        """The getters dec_go returns for this version, in order (a getter's `when` from the facts)."""
        out = []
        for g in self.getters:
            w = g.get("when")
            if isinstance(w, dict) and "version_ge" in w and not version >= w["version_ge"]:
                continue
            out.append(g["name"])
        return out

    def field(self, header: bytes, name: str) -> bytes | None:
        off, width = self.offsets[name]
        return header[off:off + width] if len(header) >= off + width else None

    # ---------------------------------------------------------------- the checks
    def check(self, headers: list[bytes]) -> list[dict]:
        if not headers:
            return []
        jobs = [{"terms": [{"call": f, "args": [{"var": "x"}]} for f in ("ok_sol", "ok_go", "dec_go")],
                 "env": {"x": list(h)}} for h in headers]
        res = self.model.run_jobs(jobs)
        enc_jobs, enc_of = [], {}
        out = []
        for i, (h, (ok_sol, ok_go, dec)) in enumerate(zip(headers, res)):
            for v, name in ((ok_sol, "ok_sol"), (ok_go, "ok_go")):
                if not isinstance(v, bool):
                    raise RuntimeError(f"model {name} returned {v!r:.200} on a {len(h)}-byte header")
            ssvh = self.field(h, "sequencerSetVerifyHash")
            off, width = self.offsets["sequencerSetVerifyHash"]
            row = {"length": len(h), "version": h[0] if h else None, "keccak": "0x" + keccak256(h).hex(),
                   "ok_sol": ok_sol, "ok_go": ok_go, "ssvh_zero": all(b == 0 for b in h[off:off + width]),
                   "dec_go": None if dec is None else ["0x" + bytes(x).hex() for x in dec["$some"]]}
            if ssvh is None:
                row["ssvh_zero"] = all(b == 0 for b in h[off:off + width])
            out.append(row)
            if isinstance(dec, dict) and "$some" in dec:
                names = self.present(h[0])
                vals = dec["$some"]
                if len(vals) != len(names):
                    raise RuntimeError(f"dec_go gave {len(vals)} fields for {len(names)} getters")
                obj = {n: "0x" + "00" * w for n, w in self.widths.items()}
                for n, v in zip(names, vals):
                    obj[n] = "0x" + bytes(v).hex()
                from ..model_eval import header_in
                enc_of[i] = len(enc_jobs)
                enc_jobs.append({"terms": [{"call": "enc_sol", "args": [{"var": "h"}]}],
                                 "env": {"h": header_in(self.facts, obj)}})
            elif dec is not None:
                raise RuntimeError(f"model dec_go returned {dec!r:.200}")
        encs = self.model.run_jobs(enc_jobs) if enc_jobs else []
        for i, (h, row) in enumerate(zip(headers, out)):
            if i not in enc_of:
                row["roundtrip"], row["diff_cells"] = "diff", list(range(len(h)))
                continue
            (enc,) = encs[enc_of[i]]
            if isinstance(enc, dict):
                raise RuntimeError(f"model enc_sol returned {enc!r:.200}")
            n = max(len(enc), len(h))
            diff = [k for k in range(n) if k >= len(enc) or k >= len(h) or enc[k] != h[k]]
            row["roundtrip"], row["diff_cells"] = ("ok" if not diff else "diff"), diff
        return out


_MODEL: HeaderModel | None = None


def model(root: Path = ROOT) -> HeaderModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = HeaderModel(root)
    return _MODEL


def header_checks(header: bytes) -> dict:
    """The per-header checks (module docstring) of one header, on the compiled frozen M0 model."""
    row = model().check([bytes(header)])[0]
    return {k: row[k] for k in ("length", "version", "keccak", "ok_sol", "ok_go", "roundtrip", "diff_cells", "ssvh_zero")}
