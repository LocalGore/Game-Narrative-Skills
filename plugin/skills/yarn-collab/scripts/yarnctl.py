#!/usr/bin/env python3
"""yarnctl: collaboration helper for Yarn Spinner (.yarn) projects.

The .yarn files are the single source of truth. This tool never regenerates them;
it edits node headers in place and leaves every other byte of the file alone.

Commands (PATH is a .yarn file or a folder searched recursively):
  status   PATH...            node table, open @claude/@hue comments, sticky notes, gaps, lint
  lint     PATH... [--ysc]    errors only; exit 1 on errors; --ysc also runs the Yarn compiler if installed
  layout   PATH... [--relayout] [--dx N --dy N]
                              set `position:` for nodes that lack one (or all, with --relayout)
  adopt    PATH...            give nodes with no `owner:` the owner `hue` (run at the start of a pass)
  colorize PATH... [--force]  color nodes by owner/status
  header   FILE TITLE key=value... [--remove key]
  stub     FILE TITLE [--note TEXT] [--after TITLE] [--owner O] [--status S] [--tags T]
  resolve  FILE TITLE [--reply TEXT]   turn `// @claude:` comments into `// resolved(claude):`
  mermaid  PATH...            branch map as a Mermaid flowchart
  guard    PATH... [--base REF]  fail if hue-owned or locked nodes changed since REF (default HEAD)

Conventions are documented in SKILL.md next to this folder.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict

sys.setrecursionlimit(10000)

HDR_RE = re.compile(r"^([A-Za-z_][\w.-]*)\s*:\s?(.*?)\s*$")
JUMP_RE = re.compile(r"<<\s*(?:jump|detour)\s+([\w.]+)\s*>>")
DECL_RE = re.compile(r"<<\s*declare\s+\$([A-Za-z_]\w*)")
SET_RE = re.compile(r"<<\s*set\s+\$([A-Za-z_]\w*)\s*(to|=|\+=|-=|\*=|/=)\s*")
VAR_RE = re.compile(r"\$([A-Za-z_]\w*)")
COMMENT_RE = re.compile(r"^\s*//\s*@(claude|hue)\b\s*:?\s*(.*)$", re.I)
POS_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
COSMETIC = {"position", "color", "cluster"}
PALETTE = {"red", "green", "blue", "orange", "yellow", "purple"}
SKIP_DIRS = {".git", "node_modules", "Library", "Temp", "obj"}
OWNERS = ("claude", "hue", "shared")
STATUSES = ("stub", "draft", "review", "needs-hue", "locked")


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


# ----------------------------------------------------------------- parsing

class Node:
    def __init__(self, yfile):
        self.file = yfile
        self.head = []
        self.sep = "---"
        self.body = []
        self.end = "==="

    def _hdrs(self):
        for i, line in enumerate(self.head):
            m = HDR_RE.match(line.rstrip("\r"))
            if m:
                yield i, m.group(1), m.group(2)

    def get(self, key, default=None):
        for _, k, v in self._hdrs():
            if k == key:
                return v
        return default

    def set(self, key, value):
        nl = "\r" if self.file.crlf else ""
        line = f"{key}: {value}{nl}"
        for i, k, _ in self._hdrs():
            if k == key:
                self.head[i] = line
                return
        self.head.append(line)

    def remove(self, key):
        keep = []
        for line in self.head:
            m = HDR_RE.match(line.rstrip("\r"))
            if not (m and m.group(1) == key):
                keep.append(line)
        self.head = keep

    @property
    def title(self):
        return self.get("title")

    @property
    def tags(self):
        return (self.get("tags") or "").replace(",", " ").split()

    @property
    def is_note(self):
        return (self.get("style") or "").lower() == "note"

    @property
    def owner(self):
        o = (self.get("owner") or "").lower()
        return o or None

    @property
    def eff_owner(self):
        return self.owner or "hue"          # unowned nodes are treated as the human's

    @property
    def status(self):
        return (self.get("status") or "").lower()

    @property
    def protected(self):
        return (not self.is_note) and (self.eff_owner == "hue" or self.status == "locked")

    @property
    def position(self):
        m = POS_RE.match(self.get("position") or "")
        return (float(m.group(1)), float(m.group(2))) if m else None

    def code_lines(self):
        return [l.rstrip("\r") for l in self.body if not l.strip().startswith("//")]

    def targets(self):
        out = []
        for line in self.code_lines():
            for t in JUMP_RE.findall(line):
                if t not in out:
                    out.append(t)
        return out

    def comments(self):
        out = []
        for i, line in enumerate(self.body):
            m = COMMENT_RE.match(line.rstrip("\r"))
            if m:
                out.append((m.group(1).lower(), m.group(2).strip(), i))
        return out

    def is_declarations(self):
        code = [l.strip() for l in self.code_lines() if l.strip()]
        return bool(code) and all(l.startswith("<<declare") for l in code)

    def is_empty(self):
        return not any(l.strip() and not l.strip().startswith("//") for l in self.body)

    def variables(self):
        reads, writes, decls = set(), set(), set()
        for line in self.code_lines():
            for m in DECL_RE.finditer(line):
                decls.add(m.group(1))
            tmp = DECL_RE.sub("<<declare ", line)

            def setrepl(m):
                writes.add(m.group(1))
                if m.group(2) in ("+=", "-=", "*=", "/="):
                    reads.add(m.group(1))
                return "<<set "

            tmp = SET_RE.sub(setrepl, tmp)
            reads.update(VAR_RE.findall(tmp))
        return reads, writes, decls

    def sig(self):
        head = [(k, v) for _, k, v in self._hdrs()
                if k not in COSMETIC and not (k == "owner" and v.lower() == "hue")]
        body = [l.rstrip() for l in self.body]
        while body and not body[-1]:
            body.pop()
        return head, body


class YFile:
    def __init__(self, path, text):
        self.path = path
        self.crlf = "\r\n" in text
        self.items = []
        gap, cur, state = [], None, "gap"
        for line in text.split("\n"):
            s = line.rstrip("\r")
            if state == "gap":
                if (HDR_RE.match(s) and s.strip() not in ("---", "===")):
                    self.items.append(("gap", gap))
                    gap = []
                    cur = Node(self)
                    cur.head = [line]
                    state = "head"
                else:
                    gap.append(line)
            elif state == "head":
                if s.strip() == "---":
                    cur.sep = line
                    state = "body"
                else:
                    cur.head.append(line)
            else:
                if s.strip() == "===":
                    cur.end = line
                    self.items.append(("node", cur))
                    cur, state = None, "gap"
                else:
                    cur.body.append(line)
        if cur is not None:
            cur.end = None
            self.items.append(("node", cur))
        self.items.append(("gap", gap))

    @property
    def nodes(self):
        return [n for k, n in self.items if k == "node"]

    def text(self):
        out = []
        for kind, x in self.items:
            if kind == "gap":
                out += x
            else:
                out += x.head + [x.sep] + x.body
                if x.end is not None:
                    out.append(x.end)
        return "\n".join(out)

    def save(self):
        with open(self.path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.text())


def collect_files(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
                out += [os.path.join(root, f) for f in sorted(files) if f.endswith(".yarn")]
        elif os.path.isfile(p):
            out.append(p)
        else:
            die(f"no such file or folder: {p}")
    return out


def load(paths):
    files = []
    for f in collect_files(paths):
        with open(f, encoding="utf-8", newline="") as fh:
            files.append(YFile(f, fh.read()))
    return files


def all_nodes(files):
    return [n for f in files for n in f.nodes]


def find_node(yf, title):
    for n in yf.nodes:
        if n.title == title:
            return n
    die(f"node '{title}' not found in {yf.path}")


# ---------------------------------------------------------------- analysis

def git(args, cwd):
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        return None


def git_dirty(paths):
    for p in paths:
        d = p if os.path.isdir(p) else os.path.dirname(os.path.abspath(p))
        r = git(["status", "--porcelain", "--", os.path.abspath(p)], d)
        if r and r.returncode == 0 and r.stdout.strip():
            return True
    return False


def analyze(files):
    nodes = all_nodes(files)
    errors, warnings, infos = [], [], []
    by_title = defaultdict(list)
    for n in nodes:
        if n.is_note:
            continue
        if not n.title:
            errors.append(f"{n.file.path}: node without a title header")
            continue
        by_title[n.title].append(n)
    for t, ns in by_title.items():
        if len(ns) > 1:
            where = ", ".join(os.path.basename(n.file.path) for n in ns)
            errors.append(f"duplicate node title '{t}' ({where})")
    indeg = defaultdict(int)
    for n in nodes:
        if n.is_note or not n.title:
            continue
        for t in n.targets():
            if t not in by_title:
                errors.append(f"{os.path.basename(n.file.path)}:{n.title}: jump to unknown node '{t}'")
            else:
                indeg[t] += 1
    for t, ns in by_title.items():
        n = ns[0]
        if indeg[t] == 0 and "entry" not in n.tags and not n.is_declarations():
            warnings.append(f"{t}: nothing jumps here (add `tags: entry` if the game starts it)")
    reads, writes, decls = set(), set(), set()
    for n in nodes:
        if n.is_note:
            continue
        r, w, d = n.variables()
        reads |= r
        writes |= w
        decls |= d
    for v in sorted(reads | writes):
        if v not in decls:
            warnings.append(f"${v} is used but not declared (fine if the game code provides it)")
    for v in sorted(decls):
        if v not in reads and v not in writes:
            infos.append(f"${v} is declared but never used")
        elif v in writes and v not in reads:
            infos.append(f"${v} is set but never read")
        elif v in reads and v not in writes:
            infos.append(f"${v} is read but never set (always its default)")
    comments, gaps, notes = [], [], []
    for n in nodes:
        base = os.path.basename(n.file.path)
        if n.is_note:
            text = " ".join(l.strip() for l in n.body if l.strip())
            if text:
                notes.append((base, n.get("title") or "(note)", text))
            continue
        for who, text, i in n.comments():
            comments.append((who, base, n.title, i + 1, text))
        if n.status in ("stub", "needs-hue") or n.is_empty():
            gaps.append((base, n.title, n.status or "empty", n.get("owner") or "-"))
    return dict(errors=errors, warnings=warnings, infos=infos, comments=comments,
                gaps=gaps, notes=notes)


def table(rows, headers):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    lines = [fmt.format(*headers)]
    lines += [fmt.format(*[str(c) for c in r]) for r in rows]
    return "\n".join(lines)


def cmd_status(a):
    files = load(a.paths)
    nodes = [n for n in all_nodes(files) if not n.is_note]
    res = analyze(files)
    if a.json:
        print(json.dumps(res, indent=2))
        return 1 if res["errors"] else 0
    print(f"== {len(files)} file(s), {len(nodes)} node(s) ==")
    if git_dirty(a.paths):
        print("! uncommitted changes in these files. Ask the designer to commit first, otherwise "
              "`guard` cannot tell their edits from mine.")
    rows = []
    for n in nodes:
        rows.append((n.title or "?", os.path.basename(n.file.path),
                     n.owner or "(none→hue)", n.status or "-", len(n.code_lines()), ",".join(n.targets()) or "-"))
    print(table(rows, ("NODE", "FILE", "OWNER", "STATUS", "LINES", "JUMPS TO")))
    if res["comments"]:
        print("\n== Open comments ==")
        for who, f, t, ln, text in res["comments"]:
            print(f"@{who:<6} {f}:{t} (body line {ln}): {text}")
    if res["notes"]:
        print("\n== Sticky notes ==")
        for f, t, text in res["notes"]:
            print(f"{f}:{t}: {text}")
    if res["gaps"]:
        print("\n== Gaps (stubs, needs-hue, empty) ==")
        for f, t, why, o in res["gaps"]:
            print(f"{f}:{t}  [{why}, owner {o}]")
    for label, key in (("Errors", "errors"), ("Warnings", "warnings"), ("Info", "infos")):
        if res[key]:
            print(f"\n== {label} ==")
            for x in res[key]:
                print("-", x)
    return 1 if res["errors"] else 0


def cmd_lint(a):
    files = load(a.paths)
    res = analyze(files)
    for x in res["errors"]:
        print("error:", x)
    for x in res["warnings"]:
        print("warning:", x)
    rc = 1 if res["errors"] else 0
    if a.ysc:
        exe = shutil.which("ysc")
        if not exe:
            print("note: `ysc` not found on PATH; skipped the Yarn compiler check "
                  "(https://github.com/YarnSpinnerTool/YarnSpinner-Console)")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                r = subprocess.run([exe, "compile", "--output-directory", tmp] + [f.path for f in files],
                                   capture_output=True, text=True)
                print((r.stdout + r.stderr).strip() or "ysc: ok")
                if r.returncode:
                    rc = 1
    if not res["errors"] and rc == 0:
        print(f"ok: {len(all_nodes(files))} nodes, {len(res['warnings'])} warnings")
    return rc


# ------------------------------------------------------------------ layout

def compute_layout(nodes, dx, dy):
    ns = [n for n in nodes if n.title and not n.is_note]
    titles = [n.title for n in ns]
    tset = set(titles)
    out = {t: [] for t in titles}
    for n in ns:
        for tgt in n.targets():
            if tgt in tset and tgt != n.title and tgt not in out[n.title]:
                out[n.title].append(tgt)
    indeg = defaultdict(int)
    for t in titles:
        for v in out[t]:
            indeg[v] += 1
    roots = [n.title for n in ns if "entry" in n.tags or indeg[n.title] == 0]
    state, back, order = {}, set(), []

    def dfs(u):
        state[u] = 1
        for v in out[u]:
            if state.get(v) == 1:
                back.add((u, v))
            elif v not in state:
                dfs(v)
        state[u] = 2
        order.append(u)

    for r in roots:
        if r not in state:
            dfs(r)
    for t in titles:
        if t not in state:
            dfs(t)
    layer = {t: 0 for t in titles}
    for u in reversed(order):
        for v in out[u]:
            if (u, v) not in back:
                layer[v] = max(layer[v], layer[u] + 1)
    parents = defaultdict(list)
    for u in titles:
        for v in out[u]:
            if (u, v) not in back:
                parents[v].append(u)
    idx = {t: i for i, t in enumerate(titles)}
    pos = {}
    for L in range(max(layer.values(), default=0) + 1):
        col = [t for t in titles if layer[t] == L]
        want = {}
        for t in col:
            ys = [pos[p][1] for p in parents[t] if p in pos]
            want[t] = sum(ys) / len(ys) if ys else None
        col.sort(key=lambda t: (want[t] if want[t] is not None else 1e9, idx[t]))
        prev = None
        for t in col:
            w = want[t]
            if w is None:
                w = 0 if prev is None else prev + dy
            y = w if prev is None else max(w, prev + dy)
            pos[t] = (L * dx, y)
            prev = y
    return pos


def fmt_pos(x, y):
    return f"{int(round(x))},{int(round(y))}"


def cmd_layout(a):
    files = load(a.paths)
    for yf in files:
        nodes = yf.nodes
        comp = compute_layout(nodes, a.dx, a.dy)
        have = [(n.title, n.position) for n in nodes if n.title in comp and n.position]
        offset = (0, 0)
        if have and not a.relayout:
            t, p = have[0]
            offset = (p[0] - comp[t][0], p[1] - comp[t][1])
        occupied = [] if a.relayout else [p for _, p in have]
        changed = 0
        for n in nodes:
            if n.title not in comp or n.is_note:
                continue
            if a.relayout:
                if (n.get("layout") or "").lower() == "pinned":
                    occupied.append(n.position) if n.position else None
                    continue
            elif n.position:
                continue
            x, y = comp[n.title][0] + offset[0], comp[n.title][1] + offset[1]
            while any(abs(x - ox) < a.dx * 0.8 and abs(y - oy) < a.dy * 0.8 for ox, oy in occupied):
                y += a.dy
            occupied.append((x, y))
            n.set("position", fmt_pos(x, y))
            changed += 1
        if changed:
            yf.save()
        print(f"{yf.path}: positioned {changed} node(s)")
    return 0


# ---------------------------------------------------------------- headers

def color_for(n):
    if n.status == "locked":
        return "red"
    if n.status == "needs-hue":
        return "orange"
    return {"claude": "blue", "shared": "purple", "hue": "green"}.get(n.eff_owner)


def cmd_adopt(a):
    files = load(a.paths)
    count = 0
    for yf in files:
        dirty = False
        for n in yf.nodes:
            if n.is_note or not n.title or n.owner:
                continue
            n.set("owner", "hue")
            if not n.get("color"):
                n.set("color", "green")
            print(f"adopted {n.title} for hue")
            count += 1
            dirty = True
        if dirty:
            yf.save()
    print(f"{count} node(s) adopted")
    return 0


def cmd_colorize(a):
    files = load(a.paths)
    count = 0
    for yf in files:
        dirty = False
        for n in yf.nodes:
            if n.is_note or not n.title:
                continue
            want = color_for(n)
            cur = (n.get("color") or "").lower()
            if not want or cur == want:
                continue
            custom = cur and cur not in PALETTE            # e.g. a hex color the designer picked
            if custom and not a.force:
                continue
            n.set("color", want)
            count += 1
            dirty = True
        if dirty:
            yf.save()
    print(f"{count} node(s) recolored")
    return 0


def cmd_header(a):
    yf = load([a.file])[0]
    n = find_node(yf, a.title)
    for kv in a.pairs:
        if "=" not in kv:
            die(f"expected key=value, got '{kv}'")
        k, v = kv.split("=", 1)
        n.set(k.strip(), v.strip())
    for k in a.remove or []:
        n.remove(k)
    yf.save()
    print(f"updated {a.title}")
    return 0


def cmd_stub(a):
    if os.path.exists(a.file):
        yf = load([a.file])[0]
        if any(n.title == a.title for n in yf.nodes):
            die(f"node '{a.title}' already exists in {a.file}")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(a.file)), exist_ok=True)
        yf = YFile(a.file, "")
    nl = "\r" if yf.crlf else ""
    node = Node(yf)
    node.head = [f"title: {a.title}{nl}", f"owner: {a.owner}{nl}", f"status: {a.status}{nl}"]
    if a.tags:
        node.head.append(f"tags: {a.tags}{nl}")
    node.set("color", color_for_values(a.owner, a.status))
    if a.after:
        ref = next((n for n in yf.nodes if n.title == a.after), None)
        if ref is not None and ref.position:
            node.set("position", fmt_pos(ref.position[0] + 320, ref.position[1]))
    node.sep = "---" + nl
    node.end = "===" + nl
    node.body = [f"// TODO: {a.note or 'beat summary'}{nl}"]
    if any(k == "node" for k, _ in yf.items):
        sep = yf.items[-1][1]
        while len(sep) > 1 and not sep[-1].strip():
            sep.pop()
        if not sep or sep[-1].strip():
            sep.append(nl)
        elif sep[-1] == "":
            sep[-1] = nl
        yf.items.append(("node", node))
        yf.items.append(("gap", [""]))
    else:
        yf.items.insert(len(yf.items) - 1, ("node", node))
    yf.save()
    print(f"added stub '{a.title}' to {a.file}")
    return 0


def color_for_values(owner, status):
    class _N:
        pass
    n = _N()
    n.status, n.eff_owner = status, owner
    return color_for(n)


def cmd_resolve(a):
    yf = load([a.file])[0]
    n = find_node(yf, a.title)
    count = 0
    last = None
    for i, line in enumerate(n.body):
        m = COMMENT_RE.match(line.rstrip("\r"))
        if m and m.group(1).lower() == "claude":
            indent = line[: len(line) - len(line.lstrip())]
            cr = "\r" if line.endswith("\r") else ""
            n.body[i] = f"{indent}// resolved(claude): {m.group(2).strip()}{cr}"
            count += 1
            last = i
    if a.reply and last is not None:
        indent = n.body[last][: len(n.body[last]) - len(n.body[last].lstrip())]
        cr = "\r" if n.body[last].endswith("\r") else ""
        n.body.insert(last + 1, f"{indent}// reply(claude): {a.reply}{cr}")
    if count:
        yf.save()
    print(f"resolved {count} comment(s) in {a.title}")
    return 0


# --------------------------------------------------------------- mermaid

def cmd_mermaid(a):
    files = load(a.paths)
    nodes = [n for n in all_nodes(files) if n.title and not n.is_note]
    ids = {n.title: "n%d" % i for i, n in enumerate(nodes)}
    print("flowchart TD")
    for n in nodes:
        label = n.title + (f"<br/>{n.status}" if n.status in ("stub", "needs-hue", "locked") else "")
        print(f'  {ids[n.title]}["{label}"]:::{n.eff_owner}')
    seen = set()
    for n in nodes:
        for t in n.targets():
            if t in ids and (n.title, t) not in seen:
                seen.add((n.title, t))
                print(f"  {ids[n.title]} --> {ids[t]}")
    print("  classDef claude fill:#cfe3ff,stroke:#3b6fb6")
    print("  classDef hue fill:#d4f0d4,stroke:#3b8f3b")
    print("  classDef shared fill:#e6d9f5,stroke:#7a4fb0")
    return 0


# ----------------------------------------------------------------- guard

def cmd_guard(a):
    cur_files = load(a.paths)
    cur = {}
    for n in all_nodes(cur_files):
        if n.title and not n.is_note:
            cur[n.title] = n
    first = a.paths[0]
    d = first if os.path.isdir(first) else os.path.dirname(os.path.abspath(first))
    r = git(["rev-parse", "--show-toplevel"], d)
    if not r or r.returncode:
        die("guard needs the folder to be inside a git repository")
    root = r.stdout.strip()
    rels = [os.path.relpath(os.path.abspath(p), root) for p in a.paths]
    ls = git(["ls-tree", "-r", "--name-only", a.base, "--"] + rels, root)
    if ls.returncode:
        die(f"git could not read {a.base}: {ls.stderr.strip()}")
    base = {}
    for rel in [x for x in ls.stdout.split("\n") if x.endswith(".yarn")]:
        show = git(["show", f"{a.base}:{rel}"], root)
        for n in YFile(rel, show.stdout).nodes:
            if n.title and not n.is_note:
                base[n.title] = n
    violations, changed, added, removed = [], [], [], []
    for t, bn in base.items():
        cn = cur.get(t)
        if cn is None:
            removed.append(t)
            if bn.protected:
                violations.append(f"{t}: {bn.eff_owner}-owned node was deleted")
        elif cn.sig() != bn.sig():
            changed.append(t)
            if bn.protected:
                hb, bb = bn.sig()
                hc, bc = cn.sig()
                what = "headers" if hb != hc else "text"
                violations.append(f"{t}: {'locked' if bn.status == 'locked' else bn.eff_owner + '-owned'} "
                                  f"node was modified ({what})")
    added = [t for t in cur if t not in base]
    protected_n = sum(1 for n in base.values() if n.protected)
    print(f"guard vs {a.base}: {len(violations)} violation(s); {protected_n} protected node(s) checked")
    for v in violations:
        print("  VIOLATION:", v)
    print("  changed:", ", ".join(changed) or "-")
    print("  added:  ", ", ".join(added) or "-")
    print("  removed:", ", ".join(removed) or "-")
    if violations:
        print("Restore those nodes (git checkout -- <file> or revert the edit) before continuing.")
    return 1 if violations else 0


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status"); p.add_argument("paths", nargs="+"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("lint"); p.add_argument("paths", nargs="+"); p.add_argument("--ysc", action="store_true")
    p.set_defaults(fn=cmd_lint)
    p = sub.add_parser("layout"); p.add_argument("paths", nargs="+"); p.add_argument("--relayout", action="store_true")
    p.add_argument("--dx", type=int, default=320); p.add_argument("--dy", type=int, default=200)
    p.set_defaults(fn=cmd_layout)
    p = sub.add_parser("adopt"); p.add_argument("paths", nargs="+"); p.set_defaults(fn=cmd_adopt)
    p = sub.add_parser("colorize"); p.add_argument("paths", nargs="+"); p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_colorize)
    p = sub.add_parser("header"); p.add_argument("file"); p.add_argument("title"); p.add_argument("pairs", nargs="*")
    p.add_argument("--remove", action="append"); p.set_defaults(fn=cmd_header)
    p = sub.add_parser("stub"); p.add_argument("file"); p.add_argument("title")
    p.add_argument("--note"); p.add_argument("--after"); p.add_argument("--tags")
    p.add_argument("--owner", default="claude", choices=OWNERS)
    p.add_argument("--status", default="stub", choices=STATUSES)
    p.set_defaults(fn=cmd_stub)
    p = sub.add_parser("resolve"); p.add_argument("file"); p.add_argument("title"); p.add_argument("--reply")
    p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("mermaid"); p.add_argument("paths", nargs="+"); p.set_defaults(fn=cmd_mermaid)
    p = sub.add_parser("guard"); p.add_argument("paths", nargs="+"); p.add_argument("--base", default="HEAD")
    p.set_defaults(fn=cmd_guard)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
