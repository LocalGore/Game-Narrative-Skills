# Game Narrative Skills

A Claude Code / Cowork plugin for writing game narrative with a designer who edits in VS Code: branching dialogue, events, lore, and Unity-ready Yarn Spinner scripts. Structure adapted from [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) (Apache-2.0): a lead agent routes to focused workers, and shared skills carry the craft knowledge.

## Install

```
/plugin marketplace add LocalGore/Game-Narrative-Skills
/plugin install game-narrative-skills@gn
```

Then start a session with the lead agent:

```
claude --agent game-narrative-skills:narrative-director
```

## How you work together

The `.yarn` files are the single source of truth. There is no intermediate format and no conversion step. You open them in VS Code with the [Yarn Spinner VS Code extension](https://docs.yarnspinner.dev/write-yarn-scripts/yarn-spinner-editor/writing-yarn-in-vs-code.md) and use its graph view; Claude edits the same files and arranges the graph.

1. **Claude lays out the graph.** New nodes get a `position`, and colors show who owns what: blue is Claude's, green is yours, purple is shared, orange needs you, red is locked.
2. **You react in place.** Write `// @claude: make this colder` inside a node, drop a sticky note, or just rewrite a node and set `owner: hue`.
3. **Claude never overwrites your nodes.** A node with `owner: hue`, no owner at all, or `status: locked` is protected, and a guard check fails if one changes.
4. **Gaps stay visible.** Claude creates `status: stub` nodes for beats you will write yourself, and asks questions in its own nodes with `// @hue:` and `status: needs-hue`.
5. **Commit before each pass.** The guard compares against the last commit, so commit your edits and ask Claude to continue.

See `plugin/skills/yarn-collab/SKILL.md` for the full conventions.

## Agents

| Agent | Role |
|---|---|
| narrative-director | Entry point; interprets requests, runs each pass, routes work, keeps the lore bible current |
| dialogue-writer | Writes Yarn nodes for dialogue, barks, events, quest beats |
| narrative-critic | Reviews drafts for voice, branch value, pacing, canon, repetition |
| outliner | Acts, routes, chapters, scenes, beats; flag ledger, Mermaid branch maps, Yarn stubs |
| character-sim | Read-only in-character conversation for voice, relationships, and choice reactions |

## Skills

| Skill | Purpose |
|---|---|
| yarn-collab | Collaboration protocol for `.yarn` files, plus the `yarnctl.py` tool |
| branching-dialogue | Native Yarn syntax, choice design, structure patterns |
| game-narrative-craft | Writing for surfaces, systems, and repetition |
| game-story-structure | Spine and branches, branch cost, flag ledger, scene template |
| character-sim | Route-aware character simulation modes |
| lore-bible | Bible layout, character template, canon rules |
| unity-narrative-export | Getting scripts into Unity: variables, commands, localization, checks |

## yarnctl

`plugin/skills/yarn-collab/scripts/yarnctl.py` is a dependency-free Python 3 tool that edits node headers in place and leaves every other byte of a file alone (LF and CRLF files are both preserved).

```
status   PATH...      nodes, owners, open comments, sticky notes, gaps, lint
lint     PATH...      errors only; --ysc also runs the Yarn compiler if installed
layout   PATH...      top-down layout (spine, detours, hub lanes) for nodes that lack a position
preview  PATH...      draw current positions to an SVG for a quick look
adopt    PATH...      nodes you added in the graph (no owner) are recorded as yours
colorize PATH...      color by owner and status
header   FILE TITLE   set or remove node headers
stub     FILE TITLE   add a stub node
resolve  FILE TITLE   mark @claude comments as handled
mermaid  PATH...      branch map as a Mermaid flowchart
guard    PATH...      fail if protected nodes changed since a git ref
```

Not yet checked against a real Yarn Spinner compile or the extension itself. See "Known limits" in the yarn-collab skill.

## Layout

```
.claude-plugin/marketplace.json
plugin/
├── .claude-plugin/plugin.json
├── agents/
└── skills/
    └── yarn-collab/scripts/yarnctl.py
```

Project files the agents create in your game folder:

```
narrative/
├── CLAUDE.md
├── yarn/      # shared .yarn scripts
├── outline/
└── lore/
```

## License

Apache License 2.0. Add a LICENSE file before publishing; if you reuse text from the upstream repo, keep its notice.
