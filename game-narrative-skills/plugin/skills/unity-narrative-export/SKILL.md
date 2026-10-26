---
name: unity-narrative-export
description: Deliver dialogue to Unity as Yarn Spinner scripts, keep it localization-friendly, and wire it into a project. Load when moving narrative into a Unity project or when the designer asks for .yarn files.
---

# Unity Narrative Export (Yarn Spinner)

Yarn Spinner (`.yarn`) is the default and preferred format. Other formats (Ink, JSON) only if the designer asks.

## Workflow

1. Draft and revise in the pseudo-code from `branching-dialogue` while chatting.
2. When a scene is approved (or the designer asks for files), save it as `narrative/scripts/<scene>.dlg`.
3. Convert with `branching-dialogue/scripts/pseudo2yarn.py` to `narrative/yarn/<scene>.yarn`. Fix lint errors in the `.dlg`.
4. Tell the designer the output path and any warnings. Do not paste the Yarn into chat unless asked.

If the Unity project already has a Yarn folder, put output there instead and match its naming.

## Variables

- Declarations are emitted as a `Declarations` node at the top of the file. Yarn rejects duplicate declarations, so keep shared variables in one `globals.dlg` and pass `--vars-file globals.dlg` when converting other scenes.
- Variables the game code reads or writes (gold, reputation) must match the C# variable storage names exactly, with `$` added in Yarn.

## Localization

- Do not hand-write line ids. In Unity, use the Yarn Spinner "Add Line Tags to Yarn Scripts" tool on the generated files, then export the string table for translators.
- Because `.yarn` is regenerated from `.dlg`, add line tags once the script is stable. Re-tagging after large rewrites can orphan translations, so avoid regenerating tagged files; edit tagged `.yarn` by hand only for small fixes and mirror them in the `.dlg`.
- Keep one sentence per line where possible and avoid string concatenation that breaks other languages.

## Custom commands

`(call name args)` becomes `<<name args>>`. The designer must register matching command handlers in C# (`[YarnCommand]` or `DialogueRunner.AddCommandHandler`). List every custom command used in a scene when delivering it.

## Testing in the Unity editor

If you run or test the scripts in a live Unity editor, always stop the play session when finished. Leaving it running can lead to editor crashes.
