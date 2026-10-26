---
name: branching-dialogue
description: Writing branching dialogue, events, and quests directly in Yarn Spinner syntax, with choice-design rules and structure patterns. Load when writing or reviewing anything with player choices.
---

# Branching Dialogue (Yarn Spinner)

Write native Yarn. There is no intermediate format. The files are shared with the designer, so follow `yarn-collab` for headers, ownership, and comments. A full example is in `examples/guild_meeting.yarn`.

## Syntax you will use

```
title: node_id
owner: claude
status: draft
---
Envoy: You're late. The Guild doesn't wait. #emotion:wary
The envoy slides a sealed ledger across the table.     // narration: a line with no "Name:"

<<set $met_envoy to true>>
<<set $gold to $gold - 10>>

<<if $reputation_guild >= 3>>
    Envoy: ...though for you, I'll make an exception.
<<else>>
    Envoy: State your business or leave.
<<endif>>

-> "I came about the contract."
    <<jump ask_terms>>
-> "Here. For your trouble." <<if $gold >= 10>>
    <<set $gold to $gold - 10>>
    <<jump ask_terms>>
-> "Not telling you."
    Envoy: Then we're done here.
    <<stop>>

<<play_sfx "ledger_slam">>      // custom command, needs a C# handler
===
```

- `Name: text` is dialogue; text without a name is narration. Line tags start with `#` (for example `#emotion:cold`).
- `->` starts an option. Lines indented under it run when it is chosen. A `<<if ...>>` on the option line hides it unless true.
- `<<jump node>>` goes to a node and does not return. `<<detour node>>` runs a node and comes back. `<<stop>>` ends the dialogue.
- Variables start with `$`. Declare each once: `<<declare $gold = 25>>`, ideally in one `Declarations` node per project. Use `{$gold}` to insert a value in a line.
- `//` starts a comment. Comments are also how you and the designer talk to each other (see `yarn-collab`).
- `<<name args>>` calls a custom command the game must implement. List every one you use.

When unsure about a feature, say so and check the Yarn Spinner docs rather than guessing syntax. A scene that does not compile is worse than a plainer one.

## Choice design

1. Every choice must change state, change felt tone, or carry a cost. Otherwise merge or cut.
2. Show costs and requirements in the choice text, never hide them after the click.
3. 2-4 choices per node. If more, split the node.
4. Avoid false choices that converge immediately unless the one-line reaction differs.
5. Offer a refuse/leave option when the player might want out.

## Structure patterns

- **Bottleneck**: branches diverge, then reconverge at a fixed node. Cheapest to write and test.
- **Gated**: later nodes check flags set earlier; declare every flag.
- **Hub**: a node the player returns to, with options that disappear once used (one flag per option).

Keep one beat per node and name nodes for what happens (`guild_haggle`, not `node_7`). Small nodes make the graph readable and give the designer something to replace.

## Review checklist

- Every node reachable (or tagged `entry`)? Run `yarnctl lint`.
- Every flag both set and read?
- Does each branch deliver something different by the next bottleneck?
- Any option text that makes a promise the next node does not keep?
