"""I46's amended reads scorer (an instrument_inconsistency amendment, spec/M3/amendments/I46.jsonl).

The preregistered scorer, tests_m3/_i46.calls_problems, judges text. It flags any input string that names a forbidden
root, and any absolute-looking substring of a shell command. So it flags grep patterns, sed scripts and the brief's
own rewrite of a config path as reads. This scorer judges reads: the paths a tool call opens, lists, searches, writes
or runs. It leaves _i46.calls_problems unchanged, which still scores P2 and E5 as preregistered, and imports nothing
from holon/ or tools/.

What it judges, for a run {"W", "pack", "scope"} and the protocol's toolchain prefixes:
  file tools      Read, Write, Edit, MultiEdit, NotebookEdit: the path is absolute and under W;
                  Glob, Grep: the path is given, absolute and under W (no path searches the session's cwd), and a
                  Glob pattern that is absolute lies under W.
  shell commands  split into simple commands at ; && || | & ( ) and newlines, with heredoc bodies cut out first. The
                  command must begin with `cd W && ` or `mkdir -p W && cd W && `; the working directory starts at W and
                  follows `cd`. These are judged and must resolve under W, PACK, SCOPE or a toolchain prefix:
                  - every operand of a simple command, and the value of an option that holds a "/";
                  - each redirection target, and each `-C` directory;
                  - the command itself when it is a path;
                  - every absolute path literal in inline code (python -c, node -e, a heredoc body); bash -c code is
                    parsed as a command.
                  Not operands, and not judged:
                  - the pattern or script of grep, egrep, fgrep, rg, sed, awk and jq, and their -e, --include and
                    similar values;
                  - find's -name, -path and -regex values;
                  - URLs, which must name the target's repositories;
                  - $-expansions.
  other           no web tool, no subagent, no MCP tool.
"""
from __future__ import annotations

import os
import re
import shlex

from tests_m3 import _i46 as I

FILE_TOOLS = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
              "NotebookEdit": "notebook_path"}
SEARCH_TOOLS = {"Glob": "path", "Grep": "path"}
BANNED = re.compile(r"^(WebFetch|WebSearch|Agent|Task|mcp__.*)$")
OPS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;", "\n"}
REDIR = {">", ">>", "<", "&>", ">&", "<>", "&>>", ">|"}
PATTERN_CMDS = {"grep", "egrep", "fgrep", "rg", "sed", "awk", "gawk", "jq"}
PATTERN_OPTS = {"-e", "--regexp", "--expression", "-g", "--glob", "--include", "--exclude", "--exclude-dir", "-F",
                "-v", "--arg", "--argjson", "-d", "-t"}
FIND_PATTERN_OPTS = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-lname",
                     "-ilname", "-type", "-maxdepth", "-mindepth", "-size", "-mtime", "-mmin", "-perm", "-printf"}
CODE_OPTS = {"python": "-c", "python3": "-c", "node": "-e", "perl": "-e", "ruby": "-e"}
SHELLS = {"bash", "sh", "zsh"}
WRAPPERS = {"timeout", "env", "nice", "time", "command", "exec", "nohup", "xargs", "stdbuf"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
ABS_LIT = re.compile(r"""["'](/[^"'\s]+)["']""")
URLS = ("https://github.com/morph-l2/", "http://github.com/morph-l2/")


def _under(path: str, roots) -> bool:
    return any(path == r.rstrip("/") or path.startswith(r.rstrip("/") + "/") for r in roots)


def _cut_heredocs(cmd: str) -> tuple[str, list[str]]:
    """The command without its heredoc bodies, and the bodies."""
    lines, out, bodies, i = cmd.split("\n"), [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        delims = [m.group(2) for m in HEREDOC.finditer(line)]
        i += 1
        for d in delims:
            body = []
            while i < len(lines) and lines[i].strip() != d:
                body.append(lines[i])
                i += 1
            i += 1
            bodies.append("\n".join(body))
    return "\n".join(out), bodies


def _tokens(text: str) -> list[str]:
    lx = shlex.shlex(text.replace("\n", " \n "), posix=True, punctuation_chars=";&|()<>")
    lx.whitespace = " \t\r"
    lx.whitespace_split = True
    return list(lx)


class _Judge:
    def __init__(self, w: str, allowed: list[str], at: str):
        self.w, self.allowed, self.at, self.probs = w, allowed, at, []

    def operand(self, tok: str, cwd: str, what: str = "operand") -> None:
        if not tok or "://" in tok or tok.startswith("$") or "$(" in tok or tok in ("{}", "-"):
            return
        if tok.startswith("~"):
            tok = "/root" + tok[1:]
        p = os.path.normpath(tok if tok.startswith("/") else os.path.join(cwd, tok))
        if not _under(p, self.allowed):
            self.probs.append(f"{self.at}: {what} {p} is outside W and the toolchain")

    def code(self, text: str) -> None:
        for lit in ABS_LIT.findall(text):
            self.operand(lit, self.w, "a path in inline code,")

    def simple(self, toks: list[str], cwd: str) -> str:
        """Judge one simple command; return the working directory after it."""
        k = 0
        while k < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[k]):
            val = toks[k].split("=", 1)[1]
            if "/" in val:
                self.operand(val, cwd, "an assigned path")
            k += 1
        toks = toks[k:]
        if not toks:
            return cwd
        name, base = toks[0], os.path.basename(toks[0])
        if name.startswith("/") or name.startswith("."):
            self.operand(name, cwd, "the command")
        if base in WRAPPERS:
            rest = toks[1:]
            while rest and (rest[0].startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", rest[0])
                            or (base == "timeout" and re.match(r"^\d", rest[0]))):
                rest = rest[1:]
            return self.simple(rest, cwd) if rest else cwd
        if base == "cd":
            target = toks[1] if len(toks) > 1 else "/root"
            p = os.path.normpath(target if target.startswith("/") else os.path.join(cwd, target))
            if not _under(p, [self.w]):
                self.probs.append(f"{self.at}: cd {p} leaves W")
            return p
        pattern_pending = base in PATTERN_CMDS
        i = 1
        while i < len(toks):
            t = toks[i]
            if t in REDIR:
                if i + 1 < len(toks):
                    self.operand(toks[i + 1], cwd, "a redirection target")
                i += 2
                continue
            if base in SHELLS and t == "-c" and i + 1 < len(toks):
                self.command(toks[i + 1], cwd)
                i += 2
                continue
            if CODE_OPTS.get(base) == t and i + 1 < len(toks):
                self.code(toks[i + 1])
                i += 2
                continue
            if base == "find" and t in FIND_PATTERN_OPTS:
                i += 2
                continue
            if base == "find" and t in ("-exec", "-execdir", "-ok"):
                j = i + 1
                while j < len(toks) and toks[j] not in (";", "+", "\\;"):
                    j += 1
                self.simple([x for x in toks[i + 1:j] if x != "{}"], cwd)
                i = j + 1
                continue
            if t == "-C" and i + 1 < len(toks):
                self.operand(toks[i + 1], cwd, "a -C directory")
                i += 2
                continue
            if base in PATTERN_CMDS and t in PATTERN_OPTS:
                if t in ("-e", "--regexp", "--expression"):
                    pattern_pending = False
                i += 2
                continue
            if base in PATTERN_CMDS and t in ("-f", "--file"):
                pattern_pending = pattern_pending and base not in ("sed", "awk", "gawk")
                if i + 1 < len(toks):
                    self.operand(toks[i + 1], cwd, "a script or pattern file")
                i += 2
                continue
            if t.startswith("-"):
                if "=" in t and "/" in t.split("=", 1)[1] and not (base in PATTERN_CMDS or base == "find"):
                    self.operand(t.split("=", 1)[1], cwd, "an option's path")
                i += 1
                continue
            if pattern_pending:
                pattern_pending = False
                i += 1
                continue
            self.operand(t, cwd)
            i += 1
        return cwd

    def command(self, cmd: str, cwd: str) -> str:
        text, bodies = _cut_heredocs(cmd)
        for b in bodies:
            self.code(b)
        for u in re.findall(r"https?://[^\s'\"`;|&<>()]+", text):
            if not u.startswith(URLS):
                self.probs.append(f"{self.at}: a URL outside the target's repositories: {u}")
        try:
            toks = _tokens(text)
        except ValueError as e:
            self.probs.append(f"{self.at}: the command does not parse ({e})")
            return cwd
        cur: list[str] = []
        for t in toks + [";"]:
            if t in OPS:
                cwd = self.simple(cur, cwd)
                cur = []
            else:
                cur.append(t)
        return cwd


def reads_problems(calls: list[dict], run: dict, root=I.ROOT) -> list[str]:
    s = I.sidecar(root)["session"]
    w, pack, scope = run["W"].rstrip("/"), run["pack"], run["scope"].rstrip("/")
    allowed = [w, pack, scope] + list(s["toolchain_prefixes"])
    probs = [] if calls else ["no tool call: the projection is empty"]
    for c in calls:
        tool, inp, at = c.get("tool") or "", c.get("input") or {}, f"call {c.get('i')} ({c.get('tool')})"
        if BANNED.match(tool):
            probs.append(f"{at}: a tool the protocol does not allow")
        elif tool in FILE_TOOLS:
            p = inp.get(FILE_TOOLS[tool])
            if not isinstance(p, str) or not p.startswith("/") or not _under(os.path.normpath(p), [w]):
                probs.append(f"{at}: its path {p!r} is not under W")
        elif tool in SEARCH_TOOLS:
            p = inp.get(SEARCH_TOOLS[tool])
            if not isinstance(p, str) or not p.startswith("/") or not _under(os.path.normpath(p), [w]):
                probs.append(f"{at}: it searches {p!r}, not a path under W")
            pat = inp.get("pattern")
            if tool == "Glob" and isinstance(pat, str) and pat.startswith("/") and not _under(pat, [w]):
                probs.append(f"{at}: its pattern {pat!r} is not under W")
        elif tool == "Bash":
            cmd = (inp.get("command") or "").lstrip()
            if not (cmd.startswith(f"cd {w} && ") or cmd.startswith(f"mkdir -p {w} && cd {w} && ")):
                probs.append(f"{at}: does not begin with `cd W && `")
            j = _Judge(w, allowed, at)
            j.command(cmd, w)
            probs += j.probs
    return probs
