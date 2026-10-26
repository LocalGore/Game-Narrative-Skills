---
name: branching-dialogue
description: Readable pseudo-code format for branching dialogue, events, and quests, plus a converter to Yarn Spinner. Load when writing or reviewing anything with player choices, or when converting scripts to .yarn.
---

# Branching Dialogue

Draft and discuss in the pseudo-code below (easy to read in chat). Save approved scenes as `.dlg` files and convert to Yarn with `scripts/pseudo2yarn.py`. A full example is in `examples/guild_meeting.dlg` and its generated `examples/guild_meeting.yarn`.

## Pseudo-code format

```
VARS
  met_envoy: bool = false
  gold: int = 25

== node_id == #entry #tag
SPEAKER: [emotion] Dialogue line.
Narration line with no speaker.
(set met_envoy = true)
(gold -= 10)
(call play_sfx "door")

(if gold >= 10)
  SPEAKER: Branch text.
(elif met_envoy)
  SPEAKER: Other text.
(else)
  SPEAKER: Fallback.
(end)

> "Choice text."                          -> target_node
> "Pay." {if gold >= 10} {gold -= 10}     -> target_node
> "Refuse." {reputation -= 1}
    SPEAKER: Inline reply under the choice.
    -> END

-> other_node       // standalone jump; -> END ends the conversation
```

Rules:
- Speakers are ALL CAPS before a colon. Lines without one are narration.
- `[emotion]` after the speaker becomes a `#emotion:` line tag in Yarn.
- Choices: `{if cond}` gates a choice; any other `{...}` is an effect that runs when picked; `-> target` jumps. Indented lines below a choice are its inline body.
- A choice with no `->` and no body falls through to whatever follows the choice group (the bottleneck pattern).
- Effects: `x = v`, `x += n`, `x -= n` (optionally prefixed with `set`). Conditions use `and`/`or`/`not` or `&&`/`||`/`!`.
- `(call name args)` becomes a custom Yarn command, for example `<<play_sfx "door">>`.
- Node ids are `snake_case` and unique. `#entry` marks a node called from outside the file.
- Every variable is declared once in `VARS`. Shared variables live in one file; other files pass it with `--vars-file`.

## Converting

Run after the designer approves a scene, or whenever they ask for the file:

```
python3 -I <skill-dir>/scripts/pseudo2yarn.py scene.dlg -o scene.yarn
python3 -I <skill-dir>/scripts/pseudo2yarn.py scene.dlg --lint-only
python3 -I <skill-dir>/scripts/pseudo2yarn.py scene.dlg --vars-file globals.dlg -o scene.yarn
python3 -I <skill-dir>/scripts/pseudo2yarn.py scene.dlg --speaker-case title -o scene.yarn
```

The script lints as it converts: unknown jump targets, undeclared variables, duplicate nodes, dead ends, unreachable nodes, and variables never set or never read. Errors stop the conversion; fix them in the `.dlg` source, never by hand-editing the `.yarn`. The `.dlg` is the source of truth; regenerate `.yarn` after every edit.

The converter has not been run against Yarn Spinner's own compiler. After a first conversion in a real project, open the `.yarn` in Unity and fix any converter gaps in the script.

## Choice design

1. Every choice must change state, change felt tone, or carry a cost. Otherwise merge or cut.
2. Show costs and requirements in the choice text, never hide them after the click.
3. 2-4 choices per node. If more, split the node.
4. Avoid false choices that converge immediately unless the one-line reaction differs.
5. Offer a refuse/leave option when the player might want out.

## Structure patterns

- **Bottleneck**: branches diverge, then reconverge at a fixed node. Cheapest to write and test.
- **Gated**: later nodes check flags set earlier; declare every flag in `VARS`.
- **Hub**: a node the player returns to, with options that disappear once used (track with a flag per option).

## Review checklist

- Every node reachable? Every flag both set and read?
- Any dead ends that are not `END`?
- Does each branch deliver something different by the next bottleneck?
