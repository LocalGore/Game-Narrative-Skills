# Game Narrative Skills

A Claude Code / Cowork plugin for writing game narrative: branching dialogue, events, lore, and Unity-ready export. Structure adapted from [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) (Apache-2.0): a lead agent routes to focused workers, and shared skills carry the craft knowledge.

## Install

```
/plugin marketplace add LocalGore/Game-Narrative-Skills
/plugin install game-narrative-skills@gn
```

Then start a session with the lead agent:

```
claude --agent game-narrative-skills:narrative-director
```

## Agents

| Agent | Role |
|---|---|
| narrative-director | Entry point; interprets requests, routes work, keeps the lore bible current |
| dialogue-writer | Drafts dialogue, barks, events, quest beats from a brief |
| narrative-critic | Reviews drafts for voice, branch value, pacing, canon, repetition |
| outliner | Acts, routes, chapters, scenes, beats; flag ledger and Mermaid branch maps |
| character-sim | Read-only in-character conversation for voice, relationships, and choice reactions |

## Skills

| Skill | Purpose |
|---|---|
| game-narrative-craft | Writing for surfaces, systems, and repetition |
| branching-dialogue | Pseudo-code format, pseudo2yarn.py converter and linter, choice design |
| game-story-structure | Spine and branches, branch cost, flag ledger, scene template |
| character-sim | Route-aware character simulation modes |
| lore-bible | Bible layout, character template, canon rules |
| unity-narrative-export | Yarn Spinner delivery, variables, localization |

## Layout

```
.claude-plugin/marketplace.json
plugin/
├── .claude-plugin/plugin.json
├── agents/
└── skills/
```

## License

Add a LICENSE file before publishing. If you reuse text from the upstream repo, keep its Apache-2.0 notice.
