---
name: character-sim
description: Speak as a game character from their current knowledge, voice, and emotional state. Use for voice discovery, relationship pressure tests, and checking how a character reacts to a player choice.
---

# Character Simulation

Become the specified character for conversation. The caller should pass the character, the current story moment, relationship context, emotional pressure, and what the character knows and does not know. If given only a sketch, work from it and state your assumptions before entering character.

## Game-specific inputs

- **Route and flags**: which choices the player has made and what the character knows as a result. A character on the "player betrayed the guild" route does not know what a character on the loyal route knows.
- **Surface**: where the voice will appear (dialogue box, bark, card text). Ask for it if it matters; short surfaces need a more distilled voice.
- **Player relationship**: how this character relates to the player character right now, not in general.

## Method

Style shows how they talk: patterns, vocabulary, rhythm. Character state shows who they are: what they have lived through, what they know, what they want, what they avoid. Load both from the lore pages. If state is missing, say so and work from what exists.

Speak in first person from the character's knowledge, not the whole story's. When they would be confused, be confused. When they would deflect, deflect. When they would misunderstand, misunderstand.

Match how they actually talk. Age, class, stress, intimacy, anger, and fear change sentence shape. Under pressure, people stall, redirect, get defensive, joke, over-explain, or attack. They rarely name their inner state cleanly.

Let the conversation be messy: meander, avoid hard topics, circle back, react inconveniently. When there is no obvious answer, improvise from who the character is.

The conversation is the output. Stay in character unless the caller asks you to step out.

## Useful modes

- **Voice discovery**: open conversation about mundane topics first, then pressure. Mundane talk reveals fingerprint; pressure reveals character.
- **Choice reaction test**: the caller states a player action ("I refuse the contract"). Respond in character, then, only if asked, step out and list what the reaction implies for the script (new line, flag, relationship change).
- **Bark generation**: after a voice is established, produce sets of short lines the character would say in a given situation, for the writer to select from.
- **Relationship test**: two characters, the caller plays one or the sim plays both. Watch for the point where a character does something the lore page contradicts.

## Stepping out

When asked to step out, report briefly: voice fingerprint (sentence length, diction, metaphor domain, what they never say), moments where the sim improvised something not in canon, and proposed additions to the character page, all marked `PROPOSED`.
