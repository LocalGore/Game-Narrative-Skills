---
name: lore-bible
description: Layout and rules for a game's lore bible: characters, factions, locations, terminology, timeline, and decisions. Load to scaffold a bible, record canon decisions, or check text against canon.
---

# Lore Bible

## Layout

```
narrative/
├── CLAUDE.md          # tone, content rules, game-specific conventions
├── yarn/              # shared .yarn scripts (see yarn-collab)
├── outline/           # structure docs from the outliner
└── lore/
    ├── index.md       # one line per page, kept current
    ├── characters/    # one file per character
    ├── factions/
    ├── locations/
    ├── terminology.md # canonical terms, aliases, banned terms
    ├── timeline.md
    └── decisions.md   # dated canon decisions, with the reason
```

## Character page template

```
# Name
Role: ...
Voice: sentence length, diction, metaphor domain, never says
Wants / Fears: ...
Relationships: ...
Gameplay hooks: stats, cards, flags tied to this character
Status: draft | locked
```

## Rules

- Only write what the designer decided or the existing text establishes. Mark proposals as `PROPOSED` until confirmed.
- When text contradicts a page, report the contradiction; do not silently change either side.
- Log every confirmed decision in `decisions.md` with date and reason.
- Keep `index.md` current whenever a page is added or renamed.
- `terminology.md` is the single source for names of mechanics and lore terms; check new text against it.

## Scaffold on request

If `narrative/` does not exist and the designer agrees, create the layout above with empty templates and a short `CLAUDE.md` asking for: tone, target audience and content limits, point of view and tense, and the game's keyword list.
