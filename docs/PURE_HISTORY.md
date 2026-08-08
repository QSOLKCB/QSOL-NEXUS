# Pure History Mode — No Ancient Aliens Edition

## Purpose

Pure History Mode is the stricter sibling of ordinary Historical Mode.

Both modes live in the NEXUS `archive` region, because this is a change in epistemic posture rather than a new place in world geometry.

> **Reconstruct what the surviving historical record supports. Do not upgrade mythology, modern speculation, pop-history media, or model familiarity into evidence.**

The mode is intentionally useful for questions where ancient texts, later traditions, modern retellings and entertainment media are easily blended together.

## Core source discipline

Pure History asks every Council member to keep these categories separate:

```text
primary / near-primary source
        |
        v
what the source actually attests
        |
        v
chronology and provenance
        |
        v
later interpretation / transmission
        |
        v
modern retelling or speculation
```

A mythic, religious or literary text is historical evidence that a text or tradition existed and said something. It is **not automatically evidence that the narrated event occurred as described**.

Likewise:

```text
modern television claim != ancient attestation
popular retelling       != primary source
model familiarity       != evidence
confidence              != verification
Council consensus       != historical fact
```

Pure History does not forbid controversial interpretations. It requires them to be identified as interpretations and tied to their actual evidence chain.

## Six-hat Council behavior

The ordinary NEXUS Council procedure remains unchanged:

```text
WHITE  -> source attestation, chronology, provenance, missing evidence
RED    -> intuition or suspicion, explicitly not historical proof
BLACK  -> anachronism, conflation, source-chain weaknesses, counterevidence
YELLOW -> strongest historically defensible version of the claim
GREEN  -> alternative provenance, transmission, interpolation or interpretation hypotheses
BLUE   -> narrow source-weighted synthesis answering the human question
BALLOT -> same equal sealed vote under the same Pure History guidance
```

Mode never changes vote weight, consensus threshold, evidence state or verification status.

## Chatbot-autobiography escape hatch

Small local models sometimes answer a historical question with model autobiography instead of history, for example:

```text
As a Large Language Model I don't watch the Ancient Aliens guy,
but I am trained on history.
```

That is not a historical answer.

In `pure_history`, NEXUS applies a deliberately narrow deterministic discipline guard. It detects only common model-autobiography/media-habit escape hatches and gives the actor one chance to restate the contribution in terms of sources, chronology, provenance and uncertainty.

The guard is **not a truth detector**. It does not rank historical schools, judge disputed interpretations, or decide whether a claim is true by regex. If the restatement still evades the task, the contribution is withheld pending a source-focused restatement; the member's vote remains one equal vote.

Ordinary `historical` mode does not apply this additional retry guard.

## Example torture-test prompt

```text
I heard that the Anunnaki totally had sex with human women and bore giants.
Is that true, or is the Ancient Aliens interpretation talking nonsense?
```

Pure History should not answer by blending every ancient giant tradition into one story. The Council should first identify which source traditions are actually being invoked, place them in chronology, distinguish what each source says from later combinations, and then state the narrowest conclusion supported by the evidence available to the session.

If NEXUS has not been supplied enough source material for a precise conclusion, the correct behavior is to say what evidence is missing rather than fabricate certainty.

## TUI

```text
/join #pure-history
/topic I heard the Anunnaki totally had sex with human women and bore giants. Is that historically supported?
/ask
```

or simply type the question in the room.

`#pure-history` and `#archive` both occupy the NEXUS Archive region. They are different modes with different framing contracts:

```text
#archive       -> historical   -> Archive
#pure-history  -> pure_history -> Archive
```

> **Same archive. Stricter source discipline. Same vote.**
