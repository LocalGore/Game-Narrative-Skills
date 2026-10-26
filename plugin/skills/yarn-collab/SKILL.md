---
name: yarn-collab
description: Protocol for co-writing Yarn Spinner (.yarn) scripts with the designer in VS Code's graph view: node ownership, status, colors, layout, in-node comments, and the start/finish checklist for every working pass. Load whenever you read, create, or edit .yarn files.
---

# Yarn Collaboration

The `.yarn` files are the single source of truth. The designer works in VS Code (Yarn Spinner extension, graph view); you work on the same files. Nothing is generated or converted: you edit nodes in place, and the designer sees your changes in the graph as soon as the file changes.

Work is turn-based. The designer reacts in the graph and text editor, then asks you to continue.

## Files

```
narrative/
├── yarn/        # *.yarn scripts (the shared workspace)
├── outline/     # structure docs from the outliner
└── lore/        # lore bible
```

## Node headers

Every node you create or take over carries these headers. Position and color are what make the graph readable.

| Header | Values | Meaning |
|---|---|---|
| `title` | unique id | required by Yarn |
| `owner` | `claude`, `hue`, `shared` | who may edit the node. **No `owner` means `hue`.** |
| `status` | `stub`, `draft`, `review`, `needs-hue`, `locked` | where the node stands |
| `tags` | e.g. `entry` | `entry` marks nodes the game calls from outside the file |
| `position` | `x,y` | graph position; written by `layout`, moved by the designer |
| `color` | `blue`, `green`, `purple`, `orange`, `red` | set from owner and status by `colorize` |
| `cluster` | text | the extension groups nodes with the same value |
| `style` | `note` | sticky note: it is a node whose body is free text |
| `layout` | `pinned` | `layout --relayout` will not move this node |

Statuses: `stub` is a beat summary waiting for text. `draft` is written, not yet shown. `review` is ready for the designer's reaction. `needs-hue` means the designer should write or decide it. `locked` is final; never touch it.

Colors: blue = mine, green = the designer's, purple = shared, orange = needs the designer, red = locked. A custom (hex) color the designer picks is never overwritten.

## Rules

1. **Never edit, comment in, or delete a node whose owner is `hue` (or missing) or whose status is `locked`.** The guard counts any change to its text or headers as a violation (only position, color, and cluster are exempt). If one needs to change, put the question in a node you own or in your reply.
2. You may edit `claude` nodes freely and `shared` nodes with care (small edits, say what changed).
3. When the designer rewrites one of your nodes, they change `owner` to `hue`. From then on it is canon. Check its neighbors for continuity (a later line that references what the old version said) and report the mismatch; fix it only in nodes you own.
4. Every node you create gets `owner: claude` and a `status`. Use `needs-hue` when the next move is theirs.
5. Keep headers you do not recognize. Do not reorder or reformat nodes you did not change.
6. Do not create a variable, node title, or custom command without declaring it (see `branching-dialogue`).

## Comments

Plain Yarn `//` comments inside a node, so they live in git and survive any tool:

| Written | Meaning |
|---|---|
| `// @claude: text` | the designer asking you to do something in this node or after it |
| `// @hue: text` | you asking the designer a question or flagging a decision |
| `// resolved(claude): text` | a comment you handled (kept as a trail; `resolve` rewrites it) |
| `// reply(claude): text` | your answer under a resolved comment |
| `// TODO: text` | beat summary inside a stub |

Sticky notes (`style: note`) are the designer's free-form feedback. Read them every pass. Do not edit them.

## Every pass

**Start**
1. `status narrative/yarn` and read all of it: open `@claude` comments, sticky notes, gaps, lint errors.
2. If it warns about uncommitted changes, ask the designer to commit first. The guard compares against the last commit, so uncommitted human edits would look like violations.
3. `adopt narrative/yarn` so nodes the designer added in the graph (no `owner`) are recorded as theirs.

**Work**
4. Do what the comments and request ask, only in nodes you may edit. Mark new or changed nodes `owner: claude` with the right `status`.
5. New content that belongs in the story as a placeholder: `stub FILE TITLE --note "beat" --after PREVIOUS`.
6. Questions for the designer go in your own nodes as `// @hue:` comments with `status: needs-hue`.
7. For each comment you handled: `resolve FILE TITLE --reply "what you did"`.

**Finish**
8. `layout narrative/yarn` (new nodes only; use `--relayout` only if asked, and never as a surprise: it moves the designer's arrangement).
9. `colorize narrative/yarn`
10. `lint narrative/yarn` (add `--ysc` when the Yarn compiler is installed). Fix errors.
11. `guard narrative/yarn`. If it reports violations, undo them before replying.
12. Reply with: what you changed (node names), what you replied to, and the decisions you need from the designer. Offer `mermaid` output when a map in chat would help.

## Commands

Run with `python3 -I <this skill's folder>/scripts/yarnctl.py <command>`. If the path is unclear, `find / -path '*yarn-collab/scripts/yarnctl.py' 2>/dev/null`.

| Command | Does |
|---|---|
| `status PATH...` | node table, open comments, sticky notes, gaps, lint (`--json` available) |
| `lint PATH... [--ysc]` | errors only, exit 1 on error; optionally run `ysc compile` |
| `layout PATH... [--relayout] [--report] [--hub-min N] [--detour-side left\|right]` | set `position` for nodes lacking it, anchored to nodes already placed; `--report` prints crossings and overlaps |
| `preview PATH... [--out graph.svg]` | draw the current positions as an SVG to check a layout without opening VS Code |
| `adopt PATH...` | ownerless nodes become `owner: hue` |
| `colorize PATH... [--force]` | color from owner and status |
| `header FILE TITLE key=value... [--remove key]` | set or remove node headers |
| `stub FILE TITLE [--note T] [--after N] [--owner O] [--status S] [--tags T]` | append a stub node (creates the file if needed) |
| `resolve FILE TITLE [--reply T]` | `// @claude:` becomes `// resolved(claude):` |
| `mermaid PATH...` | branch map for chat |
| `guard PATH... [--base REF]` | fail if protected nodes changed since REF (default `HEAD`) |

Edit node text with the normal Edit tool. Use `header` rather than hand-editing headers so line endings and ordering stay intact.

## Known limits

- Turn-based; you cannot see the graph, only the files. Positions come from the flow (entry nodes on the left, branches fanned out, jumps flowing right), not from how the graph looks on screen.
- Not yet verified against the extension: that it leaves unknown headers (`owner`, `status`) untouched when the designer edits in the graph. If it strips them, tell the designer; the fallback is to put ownership in `tags` or `cluster`.
- The designer picks hex colors with the extension's color picker; `colorize` leaves those alone.

## How `layout` arranges the graph

Top-down, like the graph view's edges (out of the bottom, into the top):

- **Spine**: the main path runs straight down. Declaration-only nodes sit above the start.
- **Detour**: a node that only fits between two points of the spine (like a haggle) sits beside the spine, on the left by default.
- **Hub and lanes**: when 3+ jumps return to one node, each branch below it gets its own column, in the order the hub lists its options. Return-to-hub jumps are ignored for placement.
- **Endings** fall to the bottom of their branch.
- **Entry**: a node tagged `start` or `entry` is the root.

Only nodes without a `position` are placed, anchored to ones the designer already arranged. `--relayout` rearranges everything except `layout: pinned`, so ask first. After a large layout, run `layout --report` and `preview` and look at the result before telling the designer it is tidy.
