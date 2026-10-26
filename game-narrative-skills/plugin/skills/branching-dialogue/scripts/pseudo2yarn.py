#!/usr/bin/env python3
"""Convert the plugin's readable dialogue pseudo-code (.dlg) into Yarn Spinner (.yarn).

Usage:
  pseudo2yarn.py input.dlg [-o output.yarn] [--vars-file globals.dlg]
                 [--speaker-case keep|title] [--lint-only]

Exit code 1 if lint errors are found. Warnings never fail the run.
Format reference: SKILL.md next to this folder.
"""
import argparse
import re
import sys

KEYWORDS = {"true", "false", "and", "or", "not", "null"}
SPEAKER_RE = re.compile(r"^([A-Z][A-Z0-9_]*(?: [A-Z][A-Z0-9_]*)*):\s*(?:\[([^\]]+)\]\s*)?(.*)$")
NODE_RE = re.compile(r"^==\s*([A-Za-z_]\w*)\s*==\s*(.*)$")
VAR_RE = re.compile(r"^\s+([A-Za-z_]\w*)\s*(?::\s*\w+)?\s*=\s*(.+?)\s*$")
EFFECT_RE = re.compile(r"^(?:set\s+)?([A-Za-z_]\w*)\s*(\+=|-=|=)\s*(.+)$")


class Ctx:
    def __init__(self):
        self.vars = {}       # name -> default literal
        self.errors = []
        self.warnings = []
        self.reads = set()
        self.writes = set()
        self.nodes = {}      # id -> {"line":n, "jumps":set()}
        self.order = []
        self.entry_tags = set()

    def err(self, ln, msg):
        self.errors.append(f"line {ln}: {msg}")

    def warn(self, ln, msg):
        self.warnings.append(f"line {ln}: {msg}")


def split_strings(expr):
    """Split into (is_string, text) parts so quoted text is never rewritten."""
    parts, buf, in_str = [], "", False
    for ch in expr:
        if ch == '"':
            if in_str:
                parts.append((True, buf + ch))
                buf, in_str = "", False
            else:
                if buf:
                    parts.append((False, buf))
                buf, in_str = ch, True
        else:
            buf += ch
    if buf:
        parts.append((in_str, buf))
    return parts


def to_yarn_expr(expr, ctx, ln, writing=False):
    expr = expr.strip()
    expr = expr.replace("&&", " and ").replace("||", " or ")
    out = []
    for is_str, text in split_strings(expr):
        if is_str:
            out.append(text)
            continue
        text = re.sub(r"!(?!=)", " not ", text)

        def sub(m):
            name = m.group(0)
            if name in KEYWORDS:
                return name
            end = m.end()
            if text[end:end + 1] == "(":      # function call, e.g. visited("x")
                return name
            if name not in ctx.vars:
                ctx.err(ln, f"undeclared variable '{name}'")
            ctx.reads.add(name)
            return "$" + name

        out.append(re.sub(r"[A-Za-z_]\w*", sub, text))
    return re.sub(r"\s+", " ", "".join(out)).strip()


def effect_to_yarn(body, ctx, ln):
    m = EFFECT_RE.match(body.strip())
    if not m:
        ctx.err(ln, f"cannot parse effect '{body}'")
        return None
    name, op, rhs = m.groups()
    if name not in ctx.vars:
        ctx.err(ln, f"undeclared variable '{name}'")
    ctx.writes.add(name)
    rhs_y = to_yarn_expr(rhs, ctx, ln)
    if op == "=":
        return f"<<set ${name} to {rhs_y}>>"
    sign = "+" if op == "+=" else "-"
    ctx.reads.add(name)
    return f"<<set ${name} to ${name} {sign} {rhs_y}>>"


def parse_vars(lines, ctx):
    in_vars = False
    for ln, raw in enumerate(lines, 1):
        if raw.strip() == "VARS":
            in_vars = True
            continue
        if in_vars:
            m = VAR_RE.match(raw)
            if m:
                ctx.vars[m.group(1)] = m.group(2)
            elif raw.strip() and not raw.startswith((" ", "\t")):
                in_vars = False


def convert(lines, ctx, speaker_case="keep", emit_declarations=True):
    out = []
    in_vars = False
    cur = None                  # current node id
    node_out = []
    choice_stack = []           # source indents of open choices
    node_has_exit = False
    cond_depth = 0

    def flush():
        nonlocal node_out, cur, node_has_exit
        if cur is not None:
            out.extend(node_out)
            out.append("===")
            out.append("")
        node_out, cur, node_has_exit = [], None, False

    def emit(depth, text):
        node_out.append("    " * depth + text)

    for ln, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if raw.strip() == "VARS":
            in_vars = True
            continue
        if in_vars:
            if not stripped or raw.startswith((" ", "\t")):
                continue
            in_vars = False
        if not stripped:
            continue
        if stripped.startswith("//"):
            if cur is not None:
                emit(len(choice_stack), stripped)
            continue

        m = NODE_RE.match(stripped)
        if m:
            if cur is not None and cond_depth:
                ctx.err(ln, "unclosed (if) block before next node")
                cond_depth = 0
            if cur is not None and not node_has_exit:
                ctx.warn(ln, f"node '{cur}' has no choice, jump, or END (dead end)")
            flush()
            cur = m.group(1)
            tags = re.findall(r"#([\w:-]+)", m.group(2))
            if cur in ctx.nodes:
                ctx.err(ln, f"duplicate node id '{cur}'")
            ctx.nodes[cur] = {"line": ln, "jumps": set()}
            ctx.order.append(cur)
            if "entry" in tags:
                ctx.entry_tags.add(cur)
            node_out = [f"title: {cur}"]
            if tags:
                node_out.append("tags: " + " ".join(tags))
            node_out.append("---")
            choice_stack = []
            node_has_exit = False
            continue

        if cur is None:
            ctx.err(ln, "text outside a node (missing '== id ==' header?)")
            continue

        indent = len(raw) - len(raw.lstrip(" \t"))
        while choice_stack and indent <= choice_stack[-1]:
            choice_stack.pop()
        depth = len(choice_stack)

        # choice
        if stripped.startswith(">"):
            body = stripped[1:].strip()
            target = None
            tm = re.search(r"->\s*([A-Za-z_]\w*)\s*$", body)
            if tm:
                target = tm.group(1)
                body = body[:tm.start()].strip()
            conds, effects = [], []
            for g in re.findall(r"\{([^}]*)\}", body):
                g = g.strip()
                if g.startswith("if "):
                    conds.append(to_yarn_expr(g[3:], ctx, ln))
                else:
                    effects.append(g)
            text = re.sub(r"\{[^}]*\}", "", body).strip()
            line = f"-> {text}"
            if conds:
                line += f" <<if {' and '.join(conds)}>>"
            emit(depth, line)
            node_has_exit = True
            for e in effects:
                y = effect_to_yarn(e, ctx, ln)
                if y:
                    emit(depth + 1, y)
            if target:
                if target == "END":
                    emit(depth + 1, "<<stop>>")
                else:
                    emit(depth + 1, f"<<jump {target}>>")
                    ctx.nodes[cur]["jumps"].add((target, ln))
            choice_stack.append(indent)
            continue

        # standalone jump / end
        jm = re.match(r"^->\s*([A-Za-z_]\w*)$", stripped)
        if jm:
            t = jm.group(1)
            node_has_exit = True
            if t == "END":
                emit(depth, "<<stop>>")
            else:
                emit(depth, f"<<jump {t}>>")
                ctx.nodes[cur]["jumps"].add((t, ln))
            continue

        # parenthesised statements
        pm = re.match(r"^\((.*)\)$", stripped)
        if pm:
            s = pm.group(1).strip()
            if s.startswith("if "):
                emit(depth, f"<<if {to_yarn_expr(s[3:], ctx, ln)}>>")
                cond_depth += 1
            elif s.startswith("elif "):
                emit(depth, f"<<elseif {to_yarn_expr(s[5:], ctx, ln)}>>")
            elif s == "else":
                emit(depth, "<<else>>")
            elif s == "end":
                if cond_depth == 0:
                    ctx.err(ln, "(end) without matching (if)")
                else:
                    cond_depth -= 1
                emit(depth, "<<endif>>")
            elif s.startswith("call "):
                cmd, _, args = s[5:].strip().partition(" ")
                args_y = to_yarn_expr(args, ctx, ln) if args.strip() else ""
                emit(depth, f"<<{cmd} {args_y}".rstrip() + ">>")
            elif s.startswith("jump "):
                t = s[5:].strip()
                node_has_exit = True
                emit(depth, f"<<jump {t}>>")
                ctx.nodes[cur]["jumps"].add((t, ln))
            else:
                y = effect_to_yarn(s, ctx, ln)
                if y:
                    emit(depth, y)
            continue

        # dialogue / narration
        sm = SPEAKER_RE.match(stripped)
        if sm:
            name, emotion, text = sm.groups()
            if speaker_case == "title":
                name = name.title()
            line = f"{name}: {text}"
            if emotion:
                line += " #emotion:" + emotion.strip().replace(" ", "_")
            emit(depth, line)
        else:
            emit(depth, stripped)

    if cur is not None and cond_depth:
        ctx.err(len(lines), "unclosed (if) block at end of file")
    if cur is not None and not node_has_exit:
        ctx.warn(len(lines), f"node '{cur}' has no choice, jump, or END (dead end)")
    flush()

    header = []
    if emit_declarations and ctx.local_vars:
        header = ["title: Declarations", "---"]
        for k, v in ctx.local_vars.items():
            header.append(f"<<declare ${k} = {v}>>")
        header += ["===", ""]
    return header + out


def lint(ctx):
    for nid, info in ctx.nodes.items():
        for target, ln in info["jumps"]:
            if target not in ctx.nodes:
                ctx.err(ln, f"jump to unknown node '{target}'")
    if ctx.order:
        seen, stack = set(), [ctx.order[0]] + sorted(ctx.entry_tags)
        while stack:
            n = stack.pop()
            if n in seen or n not in ctx.nodes:
                continue
            seen.add(n)
            stack.extend(t for t, _ in ctx.nodes[n]["jumps"])
        for n in ctx.order:
            if n not in seen:
                ctx.warn(ctx.nodes[n]["line"],
                         f"node '{n}' is unreachable from the first node (tag it #entry if called from elsewhere)")
    for v in ctx.local_vars:
        if v not in ctx.reads and v not in ctx.writes:
            ctx.warnings.append(f"variable '{v}' is declared but never used")
        elif v not in ctx.writes:
            ctx.warnings.append(f"variable '{v}' is read but never set (always its default)")
        elif v not in ctx.reads:
            ctx.warnings.append(f"variable '{v}' is set but never read")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--vars-file", help="another .dlg whose VARS block is known but not re-declared")
    ap.add_argument("--speaker-case", choices=["keep", "title"], default="keep")
    ap.add_argument("--lint-only", action="store_true")
    a = ap.parse_args()

    ctx = Ctx()
    ctx.local_vars = {}
    ext = {}
    if a.vars_file:
        tmp = Ctx()
        parse_vars(open(a.vars_file, encoding="utf-8").read().splitlines(), tmp)
        ext = tmp.vars
    lines = open(a.input, encoding="utf-8").read().splitlines()
    tmp = Ctx()
    parse_vars(lines, tmp)
    ctx.local_vars = tmp.vars
    ctx.vars = {**ext, **tmp.vars}

    result = convert(lines, ctx, a.speaker_case)
    lint(ctx)

    for w in ctx.warnings:
        print("warning:", w, file=sys.stderr)
    for e in ctx.errors:
        print("error:", e, file=sys.stderr)
    if ctx.errors:
        sys.exit(1)
    if a.lint_only:
        print(f"ok: {len(ctx.nodes)} nodes, {len(ctx.local_vars)} vars, {len(ctx.warnings)} warnings")
        return
    text = "\n".join(result).rstrip() + "\n"
    if a.output:
        open(a.output, "w", encoding="utf-8").write(text)
        print(f"wrote {a.output} ({len(ctx.nodes)} nodes)")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
