---
name: unity-narrative-export
description: Get shared Yarn Spinner scripts into a Unity project cleanly: variables, custom commands, localization line tags, and pre-delivery checks. Load when moving narrative into Unity or preparing .yarn files for the game.
---

# Unity Narrative Export (Yarn Spinner)

The `.yarn` files in `narrative/yarn/` are what the game imports. There is nothing to convert. This skill covers what has to be true about them before and after they reach Unity.

## Where files live

Keep `narrative/yarn/` as the source. Either point the Unity project at it (symlink or copy step) or keep a `Assets/` subfolder as the source and treat `narrative/` as a pointer to it. Ask the designer which, and match the project's existing layout. Do not keep two divergent copies.

## Before handing off

1. `yarnctl lint narrative/yarn --ysc` (the compiler check runs only if `ysc` is installed; otherwise the designer's VS Code Problems panel is the check).
2. Every `$variable` is declared once. Variables the game code reads or writes (gold, reputation) must match the C# variable storage names exactly, with `$` added in Yarn.
3. Every custom command (`<<name args>>`) has a handler in C# (`[YarnCommand]` or `DialogueRunner.AddCommandHandler`). List every custom command used in a scene.
4. No leftover `// TODO:` stubs or `// @claude` / `// @hue` comments in files going to a build. `status` lists them. Stubs and nodes marked `needs-hue` are unfinished.
5. Positions, colors, `owner`, and `status` headers are harmless to the game. Leave them in.

## Localization

- Do not hand-write line ids. In Unity, use the Yarn Spinner "Add Line Tags to Yarn Scripts" tool once a scene is stable, then export the string table for translators.
- Line tags (`#line:...`) are part of the file once added. After that, rewriting a line orphans its translation, so edit text in place rather than deleting and recreating nodes, and say so when a change affects tagged lines.
- Keep one sentence per line where possible and avoid building sentences from variables, which breaks other languages.

## Testing in the Unity editor

If you run or test the scripts in a live Unity editor, always stop the play session when finished. Leaving it running can lead to editor crashes.
